"""
Endpoint selection logic for LLM Router.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass

from .loader import ConfigLoader, LoaderError
from .schema import CLOUD_PROVIDER_TYPE, LLM_TIER_TYPE, validate_endpoints_config, ValidationError
from ..logger import get_logger

logger = get_logger('core.endpoints')


class EndpointError(Exception):
    """Base exception for endpoint-related errors."""
    pass


class EndpointNotFoundError(EndpointError):
    """Raised when no matching endpoint is found."""
    pass


@dataclass
class EndpointConfig:
    """Complete endpoint configuration including auth."""
    cloud: CLOUD_PROVIDER_TYPE
    provider: str
    geo: str
    tier: str
    auth: Dict[str, Any]
    endpoint: Dict[str, Any]


class EndpointSelector:
    """Selects appropriate endpoints based on configuration and location."""

    def __init__(self, endpoints_data: Dict[str, Any]):
        """
        Initialize endpoint selector.

        Args:
            endpoints_data: Parsed endpoints.json data
        """
        self.endpoints_data = endpoints_data
        self.version = endpoints_data.get('version', 'unknown')

        logger.info(f"Endpoint selector initialized (schema version: {self.version})")

    @classmethod
    def load(cls, source: str, client_id: Optional[str] = None, environment: Optional[str] = None) -> 'EndpointSelector':
        """
        Load endpoints from file or Azure Storage URL.

        Args:
            source: Path or URL to endpoints.json
            client_id: Optional Azure UMI client_id for storage authentication (production mode)
            environment: Optional environment type ('azure_vm' or 'local')

        Returns:
            EndpointSelector instance

        Raises:
            EndpointError: If loading fails
        """
        logger.info(f"Loading endpoints from: {source}")

        loader = ConfigLoader(client_id=client_id, environment=environment)

        try:
            data = loader.load(source)
            logger.info(f"Endpoints loaded successfully (version: {data.get('version', 'unknown')})")
            return cls(data)
        except LoaderError as e:
            error_msg = f"Failed to load endpoints: {e}"
            logger.error(error_msg)
            raise EndpointError(error_msg) from e

    def get_geo_map(self) -> Dict[str, str]:
        """
        Get region to geo zone mapping.

        Returns:
            Dictionary mapping regions to geo zones
        """
        return self.endpoints_data.get('routing', {}).get('geo_map', {})

    def select(
        self,
        cloud: CLOUD_PROVIDER_TYPE,
        provider: str,
        geo: str,
        tier: Optional[LLM_TIER_TYPE] = None,
        subscription_id: Optional[str] = None
    ) -> EndpointConfig:
        """
        Select endpoint for given cloud, provider, geo, tier, and optionally subscription.

        Args:
            cloud: Cloud provider (azure, gcp, aws)
            provider: AI provider (openai, claude, gemini)
            geo: Geographic zone (US, EU, APAC)
            tier: Which tier to select. If None, uses first available tier alphabetically.
            subscription_id: Azure subscription ID for subscription-specific routing.
                            If provided, endpoints with subscription_id field must match exactly.
                            Endpoints without subscription_id field are considered universal.

        Returns:
            EndpointConfig with requested tier endpoint

        Raises:
            EndpointNotFoundError: If endpoint not found
        """
        if subscription_id and subscription_id != 'local':
            logger.info(f"Subscription-based routing enabled for subscription: {subscription_id[:8]}...")
        elif subscription_id == 'local':
            logger.debug("Local development mode - subscription filtering disabled")

        # Navigate to cloud and provider
        clouds = self.endpoints_data.get('clouds', {})

        if cloud not in clouds:
            error_msg = f"Cloud '{cloud}' not found in endpoints. Available: {list(clouds.keys())}"
            logger.error(error_msg)
            raise EndpointNotFoundError(error_msg)

        cloud_config = clouds[cloud]
        providers = cloud_config.get('providers', {})

        if provider not in providers:
            error_msg = (
                f"Provider '{provider}' not found in cloud '{cloud}'. "
                f"Available: {list(providers.keys())}"
            )
            logger.error(error_msg)
            raise EndpointNotFoundError(error_msg)

        provider_config = providers[provider]
        auth_config = provider_config.get('auth', {})
        endpoints = provider_config.get('endpoints', [])

        # Helper function to check if endpoint matches subscription criteria
        def matches_subscription(ep: Dict[str, Any]) -> bool:
            """Check if endpoint matches the subscription_id criteria."""
            ep_sub = ep.get('subscription_id')
            if subscription_id is None or subscription_id == 'local':
                # No subscription filtering for None or 'local' (default for local development)
                # Match any endpoint regardless of its subscription_id
                return True
            if ep_sub is None:
                # Endpoint has no subscription_id - no fallback per design
                return False
            # Both have subscription_id - must match exactly
            return ep_sub == subscription_id

        # If tier not specified, use default from routing config or first available
        if tier is None:
            # Check for default tier in routing configuration
            default_tier = self.endpoints_data.get('routing', {}).get('defaults', {}).get('tier')

            if default_tier:
                # Verify default tier exists for this geo and subscription
                tier_exists = any(
                    ep.get('geo') == geo and ep.get('tier') == default_tier and matches_subscription(ep)
                    for ep in endpoints
                )
                if tier_exists:
                    tier = default_tier
                    logger.info(f"No tier specified, using default from routing config: {tier}")
                else:
                    logger.warning(
                        f"Default tier '{default_tier}' not available for geo={geo}, "
                        f"falling back to first available"
                    )

            # If no default or default not available, use first available tier
            if tier is None:
                available_tiers = sorted({
                    ep.get('tier')
                    for ep in endpoints
                    if ep.get('geo') == geo and ep.get('tier') and matches_subscription(ep)
                })

                if not available_tiers:
                    # Check if the issue is subscription mismatch
                    if subscription_id:
                        available_subscriptions = sorted({
                            ep.get('subscription_id')
                            for ep in endpoints
                            if ep.get('geo') == geo and ep.get('subscription_id')
                        })
                        if available_subscriptions:
                            error_msg = (
                                f"No endpoint found for subscription '{subscription_id}' with geo={geo} "
                                f"(cloud={cloud}, provider={provider}). "
                                f"Available subscriptions: {available_subscriptions}"
                            )
                            logger.error(error_msg)
                            raise EndpointNotFoundError(error_msg)

                    available_geos = sorted({ep.get('geo') for ep in endpoints if ep.get('geo')})
                    geos_str = ', '.join(available_geos)
                    error_msg = (
                        f"No endpoints found for geo={geo} (cloud={cloud}, provider={provider}). "
                        f"Available geos: {geos_str}"
                    )
                    logger.error(error_msg)
                    raise EndpointNotFoundError(error_msg)

                tier = available_tiers[0]
                logger.info(f"No tier specified or default unavailable, using first available tier: {tier}")

        if subscription_id and subscription_id != 'local':
            logger.info(f"Selecting endpoint for: cloud={cloud}, provider={provider}, geo={geo}, tier={tier}, subscription={subscription_id[:8]}...")
        else:
            logger.info(f"Selecting endpoint for: cloud={cloud}, provider={provider}, geo={geo}, tier={tier}")

        # Find the requested tier endpoint for the geo (and subscription if specified)
        tier_endpoint = None

        for endpoint in endpoints:
            if endpoint.get('geo') == geo and endpoint.get('tier') == tier and matches_subscription(endpoint):
                tier_endpoint = endpoint
                break

        # Validate endpoint was found
        if not tier_endpoint:
            # Check if the issue is subscription mismatch
            if subscription_id:
                # Check if there are endpoints for this geo/tier but different subscription
                geo_tier_endpoints = [
                    ep for ep in endpoints
                    if ep.get('geo') == geo and ep.get('tier') == tier
                ]
                if geo_tier_endpoints:
                    available_subscriptions = sorted({
                        ep.get('subscription_id')
                        for ep in geo_tier_endpoints
                        if ep.get('subscription_id')
                    })
                    error_msg = (
                        f"No endpoint found for subscription '{subscription_id}' with geo={geo}, tier={tier} "
                        f"(cloud={cloud}, provider={provider}). "
                        f"Available subscriptions for this geo/tier: {available_subscriptions}"
                    )
                    logger.error(error_msg)
                    raise EndpointNotFoundError(error_msg)

            # Extract available tiers for this cloud/provider/geo combination
            available_tiers = sorted({
                ep.get('tier')
                for ep in endpoints
                if ep.get('geo') == geo and ep.get('tier') and matches_subscription(ep)
            })

            if available_tiers:
                # The geo exists but the tier doesn't
                tiers_str = ', '.join(available_tiers)
                error_msg = (
                    f"No '{tier}' tier endpoint found for cloud={cloud}, provider={provider}, geo={geo}. "
                    f"Available tiers: {tiers_str}"
                )
            else:
                # The geo doesn't exist at all
                available_geos = sorted({ep.get('geo') for ep in endpoints if ep.get('geo')})
                geos_str = ', '.join(available_geos)
                error_msg = (
                    f"No endpoints found for geo={geo} (cloud={cloud}, provider={provider}). "
                    f"Available geos: {geos_str}"
                )

            logger.error(error_msg)
            raise EndpointNotFoundError(error_msg)

        if subscription_id and subscription_id != 'local':
            ep_sub = tier_endpoint.get('subscription_id', 'N/A')
            ep_sub_display = ep_sub[:8] + '...' if ep_sub and ep_sub != 'N/A' and len(ep_sub) > 8 else ep_sub
            logger.info(f"Found subscription-specific endpoint: tier={tier}, model={self._get_model_name(tier_endpoint)}, subscription={ep_sub_display}")
        else:
            logger.info(f"Found endpoint: {tier}={self._get_model_name(tier_endpoint)}")

        # Validate endpoint and auth configurations
        try:
            validate_endpoints_config(
                endpoint=tier_endpoint,
                auth_config=auth_config,
                cloud=cloud
            )
        except ValidationError as e:
            # Convert ValidationError to EndpointError for consistent error handling
            logger.error(f"Endpoint validation failed: {e}")
            raise EndpointError(f"Invalid endpoint configuration: {e}") from e

        return EndpointConfig(
            cloud=cloud,
            provider=provider,
            geo=geo,
            tier=tier,
            auth=auth_config,
            endpoint=tier_endpoint
        )

    @staticmethod
    def _get_model_name(endpoint: Dict[str, Any]) -> str:
        """Extract model name from endpoint for logging."""
        return endpoint.get('model') or endpoint.get('model_id') or 'unknown'
