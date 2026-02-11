"""
LLM Router integration for drm-chat-poc agents.

Provides model creation using llm_router with support for:
- Development mode (local cloud CLI credentials)
- Production mode (Azure UMI + Storage)
- Configurable cloud provider selection
"""

from pathlib import Path
import tomllib
from typing import Any

from pydantic_ai.models import Model

from .llm_router import LLMRouter
from .llm_router.core.loader import ConfigLoader, LoaderError
from ..app_logging import get_logger

logger = get_logger('config.llm_integration')


class LLMIntegration:
    """Integration layer between drm-chat-poc and llm_router."""

    def __init__(self, config_data: dict[str, Any]):
        """
        Initialize LLM Router integration.

        Args:
            config_data: Configuration dictionary from config.toml
        """
        # Get agents configuration
        agents_config = config_data.get("agents", {})

        # Mode: "dev" or "prod"
        self.mode = agents_config.get("MODE", "dev")

        # Cloud provider: "AZURE", "AWS", or "GCP"
        self.cloud_provider = agents_config.get("CLOUD_PROVIDER", "AZURE")

        logger.info(f"LLM Integration initializing: mode={self.mode}, cloud={self.cloud_provider}")

        # Determine environment for llm_router
        # "dev" mode -> "local" environment (use cloud CLI credentials)
        # "prod" mode -> "azure_vm" environment (use Azure UMI)
        if self.mode == "dev":
            environment = "local"

            # Try local file first, fallback to Azure Storage URL if not found
            endpoints_path = agents_config.get("ENDPOINTS_JSON_PATH", "./endpoints.json")

            if Path(endpoints_path).exists():
                endpoints_source = endpoints_path
                logger.info(f"Development mode: using local credentials, endpoints from {endpoints_source}")
            else:
                # Fallback to Azure Storage URL if local file doesn't exist
                endpoints_url = agents_config.get("ENDPOINTS_JSON_URL")
                if endpoints_url:
                    endpoints_source = endpoints_url
                    logger.info(f"Local endpoints.json not found at {endpoints_path}, using Azure Storage: {endpoints_source}")
                else:
                    raise FileNotFoundError(
                        f"Endpoints file not found at {endpoints_path} and no ENDPOINTS_JSON_URL configured. "
                        f"Either create {endpoints_path} or set ENDPOINTS_JSON_URL in config.toml"
                    )
        else:
            environment = "azure_vm"
            endpoints_source = agents_config.get(
                "ENDPOINTS_JSON_URL",
                "https://stgdrmigrate.blob.core.windows.net/config/endpoints.json"
            )
            logger.info(f"Production mode: using Azure UMI, endpoints from {endpoints_source}")

        # Resolve LLM provider from endpoints.json if not explicitly set
        llm_provider = agents_config.get("LLM_PROVIDER")
        if llm_provider is not None:
            llm_provider = llm_provider.strip()
        if not llm_provider:
            try:
                loader = ConfigLoader(environment=environment)
                endpoints = loader.load(endpoints_source)
                providers = (
                    endpoints.get("clouds", {})
                    .get(self.cloud_provider.lower(), {})
                    .get("providers", {})
                )
                if providers:
                    llm_provider = next(iter(providers.keys()))
                    logger.info(
                        f"LLM_PROVIDER not set. Selected provider '{llm_provider}' "
                        f"for cloud '{self.cloud_provider}' from endpoints.json."
                    )
                else:
                    logger.warning(
                        f"No providers found for cloud '{self.cloud_provider}' in endpoints.json. "
                        "Falling back to 'openai'."
                    )
                    llm_provider = "openai"
            except (LoaderError, Exception) as e:
                logger.warning(
                    f"Failed to resolve LLM_PROVIDER from endpoints.json: {type(e).__name__}: {e}. "
                    "Falling back to 'openai'."
                )
                llm_provider = "openai"

        # Build config dict from config.toml for llm_router
        # This replaces the need for a separate config.json file
        config_dict = {
            "llm_cloud": self.cloud_provider.lower(),  # "AZURE" -> "azure"
            "llm_provider": llm_provider.lower(),
            "tier": agents_config.get("DEFAULT_TIER", "light"),
            "endpoints_source": endpoints_source,
        }

        logger.info(f"LLM Router config: {config_dict}")

        # Store config for creating tier-specific routers on demand
        self.router_config = {
            "config_dict": config_dict,
            "force_environment": environment,
        }
        self._routers = {}  # Cache routers by tier
        logger.info("LLM Integration initialized (routers will be created on-demand per tier)")

    def create_model(self, tier: str = "light", model_settings: dict | None = None) -> Model:
        """
        Create a Pydantic AI model for the specified tier.

        Args:
            tier: Model tier name as defined in endpoints.json.
                  Common values: "light" (cost-effective), "heavy" (capable), "reasoning" (deep thinking)
                  The tier must exist for your configured cloud/provider/geo combination.
                  Defaults to "light".
            model_settings: Optional provider-specific model settings dict.
                           For OpenAI: Can include openai_reasoning_effort, openai_max_completion_tokens, etc.
                           Ignored for non-OpenAI providers.

        Returns:
            Pydantic AI compatible model instance

        Raises:
            ValueError: If tier is invalid
            EndpointNotFoundError: If the specified tier doesn't exist in endpoints.json
        """
        # Validate tier is a string
        if not isinstance(tier, str):
            raise ValueError(f"Invalid tier: must be a string, got {type(tier)}")

        logger.debug(f"Creating model for tier: {tier}")

        try:
            # Get or create router for this tier
            if tier not in self._routers:
                logger.info(f"Creating new router for tier: {tier}")
                self._routers[tier] = LLMRouter(
                    **self.router_config,
                    tier=tier,
                    model_settings=model_settings
                )

            # Get client from tier-specific router
            wrapper = self._routers[tier].get_client()
            # Extract the actual Model from the wrapper
            model = wrapper.client
            logger.info(f"Model created: tier={tier}, type={type(model).__name__}")
            return model
        except Exception as e:
            logger.error(f"Failed to create model for tier '{tier}': {e}")
            raise


def create_llm_integration(config_path: str = "config.toml") -> LLMIntegration:
    """
    Create LLM integration from config file.

    Args:
        config_path: Path to config.toml file

    Returns:
        LLMIntegration instance
    """
    config_file = Path(config_path)

    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_file, "rb") as f:
        config_data = tomllib.load(f)

    return LLMIntegration(config_data)
