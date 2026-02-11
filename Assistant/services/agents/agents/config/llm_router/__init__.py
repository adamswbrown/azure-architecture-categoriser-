"""
LLM Router - Intelligent multi-cloud LLM inference routing.

Automatically configures LLM clients (pydantic-ai or native SDKs) based on:
- VM location (auto-detected via Azure IMDS)
- System-assigned Managed Identity (auto-discovered via IMDS)
- Configuration (from config.json)
- Geographic endpoint routing

Supports:
- AWS Bedrock (Claude)
- Azure OpenAI (GPT-5)
- GCP Vertex AI (Gemini)

Frameworks:
- pydantic-ai: Returns pydantic-ai Model clients (default)
- native: Returns native cloud SDK clients (boto3, Azure OpenAI SDK, Google SDK)

Example usage:
    ```python
    from llm_router import LLMRouter

    # Initialize router with pydantic-ai (default) for cost-effective tier
    mini_router = LLMRouter(tier='gpt-4o-mini')
    mini_client = mini_router.get_client()  # Returns pydantic-ai Model

    # Create router for reasoning tier
    reasoning_router = LLMRouter(tier='reasoning')
    reasoning_client = reasoning_router.get_client()  # Returns pydantic-ai Model

    # Use first available tier if not specified
    auto_router = LLMRouter()  # Automatically selects first tier
    auto_client = auto_router.get_client()

    # Or use native cloud SDKs
    router = LLMRouter(framework='native', tier='claude-opus')
    client = router.get_client()  # Returns boto3/Azure/Google client
    ```
"""

from .router import LLMRouter, LLMRouterError
from .core.config import ConfigurationError
from .core.endpoints import EndpointError, EndpointNotFoundError
from .core.identity import IdentityError, IdentityNotFoundError
from .core.location import LocationDetectionError
from .auth.aws import AWSAuthenticationError
from .auth.azure import AzureAuthenticationError
from .auth.gcp import GCPAuthenticationError
from .clients.factory import FactoryError
from .clients.pydantic_ai import ClientError
from .logger import get_logger, setup_logging

__version__ = '3.0.0'

# Public API
__all__ = [
    # Main router class
    'LLMRouter',

    # Setup
    'setup_logging',
    'get_logger',

    # Exceptions
    'LLMRouterError',
    'ConfigurationError',
    'EndpointError',
    'EndpointNotFoundError',
    'IdentityError',
    'IdentityNotFoundError',
    'LocationDetectionError',
    'AWSAuthenticationError',
    'AzureAuthenticationError',
    'GCPAuthenticationError',
    'FactoryError',
    'ClientError',
]

# Setup package-level logger
logger = get_logger('')
logger.info(f"LLM Router v{__version__} initialized")
