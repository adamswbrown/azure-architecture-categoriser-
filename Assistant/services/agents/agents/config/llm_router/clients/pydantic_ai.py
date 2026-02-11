"""
PydanticAI client wrapper for a single model tier.
"""

from pydantic_ai.models import Model

from ..core import CLOUD_PROVIDER_TYPE, LLM_TIER_TYPE
from ..logger import get_logger

logger = get_logger('clients.pydantic_ai')


class ClientError(Exception):
    """Base exception for client-related errors."""
    pass


class PydanticAIClient:
    """
    Wrapper for a single PydanticAI model client.

    Manages a single-tier client for configuration-driven tier names.
    """

    def __init__(
        self,
        client: Model,
        tier: LLM_TIER_TYPE,
        cloud: CLOUD_PROVIDER_TYPE,
        provider: str,
        geo: str,
        region: str
    ):
        """
        Initialize PydanticAI client wrapper.

        Args:
            client: PydanticAI model client
            tier: Tier name (e.g., 'gpt-4o-mini', 'claude-opus', 'reasoning')
            cloud: Cloud provider (azure, gcp, aws)
            provider: AI provider (openai, claude, gemini)
            geo: Geographic zone (US, EU, APAC)
            region: Cloud region (e.g., 'us-east-1', 'australiaeast')
        """
        self._client = client
        self.tier = tier
        self.cloud = cloud
        self.provider = provider
        self.geo = geo
        self.region = region

        logger.info(
            f"PydanticAIClient initialized: "
            f"cloud={cloud}, provider={provider}, geo={geo}, "
            f"region={region}, tier={tier}"
        )

    @property
    def client(self) -> Model:
        """
        Get the client.

        Returns:
            PydanticAI model client
        """
        return self._client

    def __repr__(self) -> str:
        """String representation of client."""
        return (
            f"PydanticAIClient("
            f"cloud={self.cloud}, "
            f"provider={self.provider}, "
            f"geo={self.geo}, "
            f"region={self.region}, "
            f"tier={self.tier})"
        )
