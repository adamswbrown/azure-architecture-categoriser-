"""
Factory for creating LLM model clients.

Creates appropriate clients based on cloud provider, configuration, and framework.
Supports both pydantic-ai and native cloud SDK clients.
"""
from typing import Literal, Union
from collections.abc import Mapping, Sequence

from ..core.endpoints import EndpointConfig
from ..core.constants import (
    AZURE_COGNITIVE_SERVICES_SCOPE,
    AZURE_OPENAI_DEFAULT_API_VERSION,
)
from ..auth import (
    BaseAuthenticator,
    AWSAuthenticator,
    AWSLocalAuthenticator,
    AzureAuthenticator,
    AzureLocalAuthenticator,
    GCPAuthenticator,
    GCPLocalAuthenticator,
)
from ..logger import get_logger
from .pydantic_ai import PydanticAIClient
from .native import NativeClient

logger = get_logger('clients.factory')


SENSITIVE_KEYWORDS = ('token', 'secret', 'key', 'credential', 'password', 'signature', 'auth')


def _sanitize_value(value, depth: int = 0, max_depth: int = 3):
    """Recursively sanitize data structures before logging."""
    if depth > max_depth:
        return '...'

    if isinstance(value, Mapping):
        sanitized = {}
        for k, v in value.items():
            if isinstance(k, str) and any(keyword in k.lower() for keyword in SENSITIVE_KEYWORDS):
                sanitized[k] = '<redacted>'
            else:
                sanitized[k] = _sanitize_value(v, depth + 1, max_depth)
        return sanitized

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_sanitize_value(item, depth + 1, max_depth) for item in value]

    if isinstance(value, (str, int, float, bool)) or value is None:
        if isinstance(value, str) and any(keyword in value.lower() for keyword in SENSITIVE_KEYWORDS):
            return '<redacted>'
        return value

    return repr(value)


def _capture_object_state(obj) -> dict:
    """Capture a dictionary of public attributes for logging."""
    state: dict[str, Union[str, dict, list]] = {
        'class': obj.__class__.__name__
    }

    for attr in ('_client', '_config', '_client_kwargs', '_client_init_kwargs'):
        nested_obj = getattr(obj, attr, None)
        if nested_obj is None:
            continue

        try:
            state[attr.strip('_')] = vars(nested_obj)
        except TypeError:
            state[attr.strip('_')] = repr(nested_obj)

    try:
        state['attributes'] = vars(obj)
    except TypeError:
        pass

    return _sanitize_value(state)


class FactoryError(Exception):
    """Base exception for factory-related errors."""
    pass


class ClientFactory:
    """Factory for creating LLM model clients (pydantic-ai or native SDKs)."""

    @staticmethod
    def create_client(
        endpoint_config: EndpointConfig,
        authenticator: BaseAuthenticator,
        framework: Literal['pydantic-ai', 'native'] = 'pydantic-ai',
        model_settings: dict | None = None
    ) -> Union[PydanticAIClient, NativeClient]:
        """
        Create LLM client for the tier specified in endpoint_config.

        Args:
            endpoint_config: Endpoint configuration with cloud, provider, tier, and endpoint details
            authenticator: Authenticator instance for the cloud provider
            framework: Framework to use ('pydantic-ai' or 'native'). Defaults to 'pydantic-ai'.
            model_settings: Optional provider-specific model settings dict (OpenAI only).

        Returns:
            PydanticAIClient or NativeClient wrapper with single client for specified tier

        Raises:
            FactoryError: If client creation fails
        """
        tier = endpoint_config.tier
        logger.info(
            f"Creating {framework} client for: cloud={endpoint_config.cloud}, "
            f"provider={endpoint_config.provider}, geo={endpoint_config.geo}, tier={tier}"
        )

        # Route to appropriate factory method based on cloud provider and framework
        if endpoint_config.cloud == 'aws':
            # Validate authenticator type
            if not isinstance(authenticator, (AWSAuthenticator, AWSLocalAuthenticator)):
                raise TypeError(
                    f"Authenticator must be AWSAuthenticator or AWSLocalAuthenticator for AWS cloud, "
                    f"got {type(authenticator).__name__}"
                )
            if framework == 'pydantic-ai':
                return ClientFactory._create_aws_client(endpoint_config, authenticator)
            else:
                return ClientFactory._create_native_aws_client(endpoint_config, authenticator)
        elif endpoint_config.cloud == 'azure':
            # Validate authenticator type
            if not isinstance(authenticator, (AzureAuthenticator, AzureLocalAuthenticator)):
                raise TypeError(
                    f"Authenticator must be AzureAuthenticator or AzureLocalAuthenticator for Azure cloud, "
                    f"got {type(authenticator).__name__}"
                )
            if framework == 'pydantic-ai':
                return ClientFactory._create_azure_client(endpoint_config, authenticator, model_settings)
            else:
                return ClientFactory._create_native_azure_client(endpoint_config, authenticator)
        elif endpoint_config.cloud == 'gcp':
            # Validate authenticator type
            if not isinstance(authenticator, (GCPAuthenticator, GCPLocalAuthenticator)):
                raise TypeError(
                    f"Authenticator must be GCPAuthenticator or GCPLocalAuthenticator for GCP cloud, "
                    f"got {type(authenticator).__name__}"
                )
            if framework == 'pydantic-ai':
                return ClientFactory._create_gcp_client(endpoint_config, authenticator)
            else:
                return ClientFactory._create_native_gcp_client(endpoint_config, authenticator)
        else:
            error_msg = f"Unsupported cloud provider: {endpoint_config.cloud}"
            logger.error(error_msg)
            raise FactoryError(error_msg)

    @staticmethod
    def _create_aws_client(
        endpoint_config: EndpointConfig,
        authenticator: AWSAuthenticator | AWSLocalAuthenticator
    ) -> PydanticAIClient:
        """
        Create AWS Bedrock client with auto-refresh capability (pydantic-ai).

        Args:
            endpoint_config: Endpoint configuration
            authenticator: AWS authenticator

        Returns:
            PydanticAIClient with AWS Bedrock client
        """
        try:
            from pydantic_ai.models.bedrock import BedrockConverseModel
            from .refreshable_bedrock import RefreshableBedrockProvider
        except ImportError as e:
            error_msg = f"Failed to import AWS dependencies: {e}"
            logger.error(error_msg)
            raise FactoryError(error_msg) from e

        tier = endpoint_config.tier
        logger.info(f"Creating AWS Bedrock {tier} client with auto-refresh")

        # Get endpoint from config
        tier_endpoint = endpoint_config.endpoint

        # Create refreshable Bedrock provider
        provider = RefreshableBedrockProvider(
            authenticator=authenticator,
            region=tier_endpoint['region']
        )

        # Create Bedrock client
        client = BedrockConverseModel(
            model_name=tier_endpoint['model_id'],
            provider=provider
        )
        logger.info(f"Created {tier} client: {tier_endpoint['model_id']} in {tier_endpoint['region']}")

        return PydanticAIClient(
            client=client,
            tier=tier,
            cloud=endpoint_config.cloud,
            provider=endpoint_config.provider,
            geo=endpoint_config.geo,
            region=tier_endpoint['region']
        )

    @staticmethod
    def _create_azure_client(
        endpoint_config: EndpointConfig,
        authenticator: AzureAuthenticator | AzureLocalAuthenticator,
        model_settings: dict | None = None
    ) -> PydanticAIClient:
        """
        Create Azure OpenAI client (pydantic-ai).

        For production (Azure VM): Uses ManagedIdentityCredential
        For local dev: Uses DefaultAzureCredential (tries CLI, env vars, etc.)

        Args:
            endpoint_config: Endpoint configuration
            authenticator: Azure authenticator

        Returns:
            PydanticAIClient with Azure OpenAI client
        """
        try:
            from pydantic_ai.models.openai import OpenAIChatModel,OpenAIChatModelSettings
            from pydantic_ai.providers.azure import AzureProvider
            from openai import AsyncAzureOpenAI
            from azure.identity import ManagedIdentityCredential, AzureCliCredential, get_bearer_token_provider
            from ..auth.local import AzureLocalAuthenticator
        except ImportError as e:
            error_msg = f"Failed to import Azure OpenAI dependencies: {e}"
            logger.error(error_msg)
            raise FactoryError(error_msg) from e

        tier = endpoint_config.tier
        logger.info(f"Creating Azure OpenAI {tier} client")

        # Get endpoint from config
        tier_endpoint = endpoint_config.endpoint

        # Get Azure OpenAI endpoint URL from config
        azure_endpoint = tier_endpoint['endpoint_url']

        # Create appropriate credential based on authenticator type
        if isinstance(authenticator, AzureLocalAuthenticator):
            logger.info("Using AzureCliCredential for local development (az login user)")
            credential = AzureCliCredential()
        else:
            logger.info("Using ManagedIdentityCredential for production")
            client_id = authenticator.client_id
            credential = ManagedIdentityCredential(client_id=client_id)

        # Create token provider for Azure Cognitive Services
        token_provider = get_bearer_token_provider(
            credential, AZURE_COGNITIVE_SERVICES_SCOPE
        )

        # Create AsyncAzureOpenAI client
        azure_client = AsyncAzureOpenAI(
            azure_endpoint=azure_endpoint,
            api_version=tier_endpoint.get('api_version', AZURE_OPENAI_DEFAULT_API_VERSION),
            azure_ad_token_provider=token_provider
        )

        # Create Azure provider
        provider = AzureProvider(openai_client=azure_client)

        # Create OpenAI model instance with optional settings
        settings = OpenAIChatModelSettings(**model_settings) if model_settings else OpenAIChatModelSettings()
        client = OpenAIChatModel(
            model_name=tier_endpoint['deployment'],
            provider=provider,
            settings=settings
        )
        logger.info(
            f"Created {tier} client: {tier_endpoint['deployment']} "
            f"({tier_endpoint['model']}) in {tier_endpoint['region']}"
        )

        return PydanticAIClient(
            client=client,
            tier=tier,
            cloud=endpoint_config.cloud,
            provider=endpoint_config.provider,
            geo=endpoint_config.geo,
            region=tier_endpoint['region']
        )

    @staticmethod
    def _create_gcp_client(
        endpoint_config: EndpointConfig,
        authenticator: GCPAuthenticator | GCPLocalAuthenticator
    ) -> PydanticAIClient:
        """
        Create GCP Vertex AI client (pydantic-ai).

        Args:
            endpoint_config: Endpoint configuration
            authenticator: GCP authenticator

        Returns:
            PydanticAIClient with GCP Gemini client
        """
        try:
            from pydantic_ai.models.google import GoogleModel
            from pydantic_ai.providers.google import GoogleProvider
            from google.auth.credentials import Credentials
        except ImportError as e:
            error_msg = f"Failed to import GCP Gemini dependencies: {e}"
            logger.error(error_msg)
            raise FactoryError(error_msg) from e

        tier = endpoint_config.tier
        logger.info(f"Creating GCP Vertex AI {tier} client")

        # Get credentials from authenticator
        auth_result = authenticator.authenticate()
        project_id = auth_result['project_id']
        creds = auth_result['credentials']

        # Get endpoint from config
        tier_endpoint = endpoint_config.endpoint

        # Create GoogleProvider
        provider = GoogleProvider(
            credentials=creds,
            project=project_id,
            location=tier_endpoint['region'],
            vertexai=True
        )

        # Create client
        client = GoogleModel(
            model_name=tier_endpoint['model'],
            provider=provider
        )
        logger.info(
            f"Created {tier} client: {tier_endpoint['model']} "
            f"in {tier_endpoint['region']}"
        )

        return PydanticAIClient(
            client=client,
            tier=tier,
            cloud=endpoint_config.cloud,
            provider=endpoint_config.provider,
            geo=endpoint_config.geo,
            region=tier_endpoint['region']
        )

    # ============================================================
    # Native SDK Client Factory Methods
    # ============================================================

    @staticmethod
    def _create_native_aws_client(
        endpoint_config: EndpointConfig,
        authenticator: AWSAuthenticator | AWSLocalAuthenticator
    ) -> NativeClient:
        """
        Create native boto3 Bedrock client.

        Args:
            endpoint_config: Endpoint configuration
            authenticator: AWS authenticator

        Returns:
            NativeClient with native boto3 Bedrock client
        """
        try:
            import boto3
        except ImportError as e:
            error_msg = f"Failed to import boto3: {e}"
            logger.error(error_msg)
            raise FactoryError(error_msg) from e

        tier = endpoint_config.tier
        logger.info(f"Creating native boto3 Bedrock {tier} client")

        # Get endpoint from config
        tier_endpoint = endpoint_config.endpoint

        # Get credentials
        creds = authenticator.authenticate()

        # Create boto3 client
        client = boto3.client(
            'bedrock-runtime',
            region_name=tier_endpoint['region'],
            aws_access_key_id=creds['AccessKeyId'],
            aws_secret_access_key=creds['SecretAccessKey'],
            aws_session_token=creds.get('SessionToken')
        )
        logger.info(f"Created native {tier} client for {tier_endpoint['model_id']} in {tier_endpoint['region']}")

        return NativeClient(
            client=client,
            tier=tier,
            cloud=endpoint_config.cloud,
            provider=endpoint_config.provider,
            geo=endpoint_config.geo,
            region=tier_endpoint['region']
        )

    @staticmethod
    def _create_native_azure_client(
        endpoint_config: EndpointConfig,
        authenticator: AzureAuthenticator | AzureLocalAuthenticator
    ) -> NativeClient:
        """
        Create native Azure OpenAI client.

        Args:
            endpoint_config: Endpoint configuration
            authenticator: Azure authenticator

        Returns:
            NativeClient with native Azure OpenAI client
        """
        try:
            from openai import AzureOpenAI
            from azure.identity import ManagedIdentityCredential, AzureCliCredential, get_bearer_token_provider
            from ..auth.local import AzureLocalAuthenticator
        except ImportError as e:
            error_msg = f"Failed to import Azure OpenAI dependencies: {e}"
            logger.error(error_msg)
            raise FactoryError(error_msg) from e

        tier = endpoint_config.tier
        logger.info(f"Creating native Azure OpenAI {tier} client")

        # Get endpoint from config
        tier_endpoint = endpoint_config.endpoint

        # Get Azure OpenAI endpoint URL from config
        azure_endpoint = tier_endpoint['endpoint_url']

        # Create appropriate credential based on authenticator type
        if isinstance(authenticator, AzureLocalAuthenticator):
            logger.info("Using AzureCliCredential for local development")
            credential = AzureCliCredential()
        else:
            logger.info("Using ManagedIdentityCredential for production")
            client_id = authenticator.client_id
            credential = ManagedIdentityCredential(client_id=client_id)

        # Create token provider
        token_provider = get_bearer_token_provider(
            credential, "https://cognitiveservices.azure.com/.default"
        )

        # Create native AzureOpenAI client
        client = AzureOpenAI(
            azure_endpoint=azure_endpoint,
            api_version=tier_endpoint.get('api_version', AZURE_OPENAI_DEFAULT_API_VERSION),
            azure_ad_token_provider=token_provider
        )

        logger.info(
            f"Created native {tier} client for {tier_endpoint['deployment']} "
            f"in {tier_endpoint['region']}"
        )

        return NativeClient(
            client=client,
            tier=tier,
            cloud=endpoint_config.cloud,
            provider=endpoint_config.provider,
            geo=endpoint_config.geo,
            region=tier_endpoint['region']
        )

    @staticmethod
    def _create_native_gcp_client(
        endpoint_config: EndpointConfig,
        authenticator: GCPAuthenticator | GCPLocalAuthenticator
    ) -> NativeClient:
        """
        Create native GCP Vertex AI client.

        Args:
            endpoint_config: Endpoint configuration
            authenticator: GCP authenticator

        Returns:
            NativeClient with native GCP Vertex AI client
        """
        try:
            from google.cloud import aiplatform
            from vertexai.generative_models import GenerativeModel
        except ImportError as e:
            error_msg = f"Failed to import GCP Vertex AI dependencies: {e}"
            logger.error(error_msg)
            raise FactoryError(error_msg) from e

        tier = endpoint_config.tier
        logger.info(f"Creating native GCP Vertex AI {tier} client")

        # Get credentials from authenticator
        auth_result = authenticator.authenticate()
        project_id = auth_result['project_id']
        creds = auth_result['credentials']

        # Get endpoint from config
        tier_endpoint = endpoint_config.endpoint

        # Initialize Vertex AI
        aiplatform.init(
            project=project_id,
            location=tier_endpoint['region'],
            credentials=creds
        )

        # Create client
        client = GenerativeModel(tier_endpoint['model'])
        logger.info(f"Created native {tier} client for {tier_endpoint['model']} in {tier_endpoint['region']}")

        return NativeClient(
            client=client,
            tier=tier,
            cloud=endpoint_config.cloud,
            provider=endpoint_config.provider,
            geo=endpoint_config.geo,
            region=tier_endpoint['region']
        )
