"""
Main LLM Router orchestrator.

Automatically configures and provides LLM clients based on:
- VM location (auto-detected)
- Configuration (from config.json)
- Managed Identity (auto-discovered)
- Framework choice (pydantic-ai or native SDKs)
"""

import os
from typing import Any, Literal, Optional

from .core.config import Config
from .core.endpoints import EndpointSelector
from .core.identity import IdentityDiscovery
from .core.location import LocationDetector
from .core.environment import detect_environment
from .clients.factory import ClientFactory
from .auth.factory import AuthenticatorFactory, AuthenticatorFactoryError
from .logger import get_logger

logger = get_logger('router')


class LLMRouterError(Exception):
    """Base exception for LLM Router errors."""
    pass


class LLMRouter:
    """
    Main LLM Router orchestrator.

    Automatically:
    1. Detects VM location and maps to geo zone
    2. Discovers System-assigned Managed Identity (SMI)
    3. Loads configuration and endpoints
    4. Selects appropriate endpoints based on geo
    5. Creates authenticator for the cloud provider
    6. Returns configured LLM clients (pydantic-ai or native SDKs)
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        config_dict: Optional[dict] = None,
        endpoints_source: Optional[str] = None,
        vm_name: Optional[str] = None,
        force_environment: Optional[str] = None,
        force_location: Optional[str] = None,
        framework: Literal['pydantic-ai', 'native'] = 'pydantic-ai',
        tier: Optional[str] = None,
        model_settings: dict | None = None
    ):
        """
        Initialize LLM Router.

        Args:
            config_path: Optional explicit path to config.json. Ignored if config_dict provided.
            config_dict: Optional config dictionary. If provided, used instead of loading from file.
                        Required keys: llm_cloud, llm_provider
                        Optional keys: tier, endpoints_source, environment, location
            endpoints_source: Optional explicit path/URL to endpoints.json
            vm_name: Optional VM name for identity discovery. If None, auto-detected.
            force_environment: Optional environment override ('auto', 'azure_vm', 'local').
                              Precedence: force_environment param > config.json > env var > auto-detect
            force_location: Optional location/region override (e.g., 'australiaeast', 'eastus').
                           Overrides auto-detection for testing different geo endpoints.
                           Precedence: force_location param > config.json > env var > auto-detect
            framework: LLM framework to use ('pydantic-ai' or 'native'). Defaults to 'pydantic-ai'.
                      - 'pydantic-ai': Returns pydantic-ai Model clients
                      - 'native': Returns native cloud SDK clients (boto3, Azure SDK, Google SDK)
            tier: Which tier to create. If None, uses first available tier for the selected cloud/provider/geo.
                 Tier names must match those defined in endpoints.json for your cloud/provider/geo.
                 Common values: 'gpt-4o-mini' (cost-effective), 'claude-opus' (capable), 'reasoning' (deep thinking)
                 Creates only ONE client for the specified tier.
                 If you need multiple tiers, create separate router instances.
            model_settings: Optional provider-specific model settings dict (OpenAI only).
                          Example: {'openai_reasoning_effort': 'low', 'openai_max_completion_tokens': 100}

        Raises:
            LLMRouterError: If initialization fails
        """
        logger.info(f"Initializing LLM Router with {framework} framework, tier={tier}")
        self.model_settings = model_settings

        try:
            # Step 0: Determine initial environment (for config loading)
            logger.info("Step 0: Determining initial environment")
            initial_environment_override = force_environment or os.getenv('LLM_ROUTER_ENVIRONMENT')

            if initial_environment_override:
                logger.info(f"Initial environment override from parameter/env var: {initial_environment_override}")

                # Validate override value
                if initial_environment_override not in ('auto', 'azure_vm', 'local'):
                    raise LLMRouterError(
                        f"Invalid environment override '{initial_environment_override}'. "
                        f"Valid values: auto, azure_vm, local"
                    )

            initial_environment = detect_environment(override=initial_environment_override)
            logger.info(f"Initial environment: {initial_environment}")

            # Step 1: Load configuration
            logger.info("Step 1: Loading configuration")

            if config_dict:
                logger.info("Loading config from provided dictionary")
                self.config = Config.from_dict(config_dict)
            else:
                if config_path is None:
                    config_path = 'config.json'
                logger.info(f"Loading config from file (path={config_path})")
                self.config = Config.load(
                    config_path=config_path,
                    environment=initial_environment,
                    client_id=None  # Will be set later after identity discovery
                )

            logger.info(f"Config loaded: cloud={self.config.llm_cloud}, provider={self.config.llm_provider}")

            # Step 2: Determine final environment (from config or detection)
            logger.info("Step 2: Determining final environment")

            # Build final environment override with precedence
            final_environment_override = None
            if force_environment:
                final_environment_override = force_environment
                logger.info(f"Final environment override from parameter: {final_environment_override}")
            elif hasattr(self.config, 'environment') and self.config.environment:
                final_environment_override = self.config.environment
                logger.info(f"Final environment override from config: {final_environment_override}")
            elif os.getenv('LLM_ROUTER_ENVIRONMENT'):
                final_environment_override = os.getenv('LLM_ROUTER_ENVIRONMENT')
                logger.info(f"Final environment override from env var: {final_environment_override}")

            self.environment = detect_environment(override=final_environment_override)
            logger.info(f"Final environment: {self.environment}")

            # Step 3: Detect VM location (if on Azure VM)
            logger.info("Step 3: Detecting VM location")

            # Set overrides via environment variables if provided
            if force_location:
                os.environ['LLM_ROUTER_LOCATION'] = force_location
                logger.info(f"Location override from parameter: {force_location}")
            elif hasattr(self.config, 'location') and self.config.location:
                os.environ['LLM_ROUTER_LOCATION'] = self.config.location
                logger.info(f"Location override from config: {self.config.location}")

            if vm_name:
                os.environ['LLM_ROUTER_VM_NAME'] = vm_name
                logger.info(f"VM name override from parameter: {vm_name}")

            location_detector = LocationDetector()
            vm_info = location_detector.detect(environment=self.environment)

            self.location = vm_info.location
            self.vm_name = vm_info.name
            self.subscription_id = vm_info.subscription_id
            logger.info(f"Location detected: {self.location}")
            logger.info(f"VM Name: {self.vm_name}")
            logger.info(f"Subscription ID: {self.subscription_id}")

            # Step 4: Discover Managed Identity (only on Azure VMs)
            if self.environment == 'azure_vm':
                logger.info("Step 4: Discovering System-assigned Managed Identity")

                identity_discovery = IdentityDiscovery(vm_name=self.vm_name)
                self.managed_identity = identity_discovery.get_identity()

                logger.info(
                    f"Managed Identity discovered: "
                    f"{self.managed_identity.identity_type} ({self.managed_identity.name})"
                )
            else:
                logger.info("Step 4: Skipping identity discovery (local development mode)")
                self.managed_identity = None
                logger.info("Using Azure CLI credentials for local development")

            # Step 5: Load endpoints
            logger.info("Step 5: Loading endpoints")

            # Get endpoints source with precedence
            final_endpoints_source = endpoints_source
            if final_endpoints_source is None and hasattr(self.config, 'endpoints_source'):
                final_endpoints_source = self.config.endpoints_source
            if final_endpoints_source is None:
                final_endpoints_source = './endpoints.json'

            self.endpoint_selector = EndpointSelector.load(
                source=final_endpoints_source,
                environment=self.environment,
                client_id=self.managed_identity.client_id if self.managed_identity else None
            )

            logger.info(f"Endpoints loaded from: {final_endpoints_source}")

            # Step 6: Map location to geo zone
            logger.info("Step 6: Mapping location to geo zone")

            geo_map = self.endpoint_selector.get_geo_map()
            self.geo = geo_map.get(self.location)

            if self.geo is None:
                logger.warning(f"Region '{self.location}' not found in geo_map, defaulting to US")
                self.geo = 'US'

            logger.info(f"Geo zone mapped: {self.location} → {self.geo}")

            # Step 7: Select endpoint for tier
            logger.info("Step 7: Selecting endpoint for tier")

            # Get tier with precedence
            final_tier = tier
            if final_tier is None and hasattr(self.config, 'tier'):
                final_tier = self.config.tier

            self.tier = final_tier

            self.endpoint_config = self.endpoint_selector.select(
                cloud=self.config.llm_cloud,
                provider=self.config.llm_provider,
                geo=self.geo,
                tier=final_tier,
                subscription_id=self.subscription_id if self.config.llm_cloud == 'azure' else None
            )

            model_name = (
                self.endpoint_config.endpoint.get('model') or
                self.endpoint_config.endpoint.get('model_id')
            )
            logger.info(f"Endpoint selected: tier={self.endpoint_config.tier}, model={model_name}")

            # Step 8: Create authenticator
            logger.info("Step 8: Creating authenticator")

            try:
                # For AWS local, need region from endpoint
                auth_config = dict(self.endpoint_config.auth)
                if self.config.llm_cloud == 'aws' and self.environment == 'local':
                    auth_config['region'] = self.endpoint_config.endpoint['region']

                self.authenticator = AuthenticatorFactory.create(
                    cloud=self.config.llm_cloud,
                    environment=self.environment,
                    auth_config=auth_config,
                    client_id=self.managed_identity.client_id if self.managed_identity else None,
                    vm_name=self.vm_name
                )

                logger.info(f"Authenticator created for {self.config.llm_cloud} ({self.environment})")

            except AuthenticatorFactoryError as e:
                error_msg = f"Failed to create authenticator: {e}"
                logger.error(error_msg)
                raise LLMRouterError(error_msg) from e

            # Step 9: Create LLM client
            logger.info(f"Step 9: Creating {framework} LLM client")

            self.framework = framework

            self.client = ClientFactory.create_client(
                endpoint_config=self.endpoint_config,
                authenticator=self.authenticator,
                framework=framework,
                model_settings=self.model_settings
            )

            logger.info(f"Client created: framework={framework}, tier={self.endpoint_config.tier}")
            logger.info("LLM Router initialization complete")

        except LLMRouterError:
            # Re-raise LLMRouterError as-is
            raise
        except Exception as e:
            error_msg = f"Failed to initialize LLM Router: {e}"
            logger.error(error_msg)
            raise LLMRouterError(error_msg) from e

    def get_client(self) -> Any:
        """
        Get the LLM client.

        Returns:
            LLM client (pydantic-ai Model or native SDK client, depending on framework)
        """
        return self.client

    def __repr__(self) -> str:
        """String representation of router."""
        return (
            f"LLMRouter("
            f"location={self.location}, "
            f"geo={self.geo}, "
            f"cloud={self.config.llm_cloud}, "
            f"provider={self.config.llm_provider}, "
            f"tier={self.tier}, "
            f"subscription_id={self.subscription_id}, "
            f"framework={self.framework})"
        )
