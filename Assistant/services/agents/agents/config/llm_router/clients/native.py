"""
Native cloud SDK client wrapper for a single model tier.

This wrapper provides access to native cloud SDK clients (boto3, Azure SDK, Google SDK)
instead of pydantic-ai wrappers, allowing the router to be used with any LLM framework.
"""

from typing import Any

from ..core import CLOUD_PROVIDER_TYPE, LLM_TIER_TYPE
from ..logger import get_logger

logger = get_logger('clients.native')


class ClientError(Exception):
    """Base exception for client-related errors."""
    pass


class NativeClient:
    """
    Wrapper for a single native cloud SDK client.

    Manages a single-tier client using native cloud SDKs:
    - AWS: boto3.client('bedrock-runtime')
    - Azure: Azure AI Inference client or OpenAI client
    - GCP: google.cloud.aiplatform client

    This allows the router to work with any LLM framework, not just pydantic-ai.
    """

    def __init__(
        self,
        client: Any,
        tier: LLM_TIER_TYPE,
        cloud: CLOUD_PROVIDER_TYPE,
        provider: str,
        geo: str,
        region: str
    ):
        """
        Initialize native cloud SDK client wrapper.

        Args:
            client: Native SDK client (boto3, Azure, or GCP)
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
            f"NativeClient initialized: "
            f"cloud={cloud}, provider={provider}, geo={geo}, "
            f"region={region}, tier={tier}"
        )

    @property
    def client(self) -> Any:
        """
        Get the client.

        Returns:
            Native SDK client
        """
        return self._client

    def __repr__(self) -> str:
        """String representation of client."""
        return (
            f"NativeClient("
            f"cloud={self.cloud}, "
            f"provider={self.provider}, "
            f"geo={self.geo}, "
            f"region={self.region}, "
            f"tier={self.tier})"
        )
