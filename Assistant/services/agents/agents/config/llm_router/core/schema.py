"""
Schema validation for endpoints and authentication configurations.

Uses Pydantic models to validate endpoint and auth config structures,
ensuring required fields are present and have correct types.
"""

from typing import Dict, Any, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
from .constants import AZURE_OPENAI_DEFAULT_API_VERSION
from ..logger import get_logger

logger = get_logger('core.schema')


class ValidationError(Exception):
    """Exception raised when validation fails."""
    pass


# ============================================================================
# Endpoint Schemas
# ============================================================================

class BaseEndpointSchema(BaseModel):
    """Base schema for endpoint configuration."""

    model: str = Field(..., description="Model name or deployment name")
    region: str = Field(..., description="Cloud region")

    class Config:
        extra = 'allow'  # Allow additional fields


class AzureEndpointSchema(BaseEndpointSchema):
    """Azure OpenAI endpoint configuration."""

    deployment: str = Field(..., description="Azure OpenAI deployment name")
    model: str = Field(..., description="Model name (e.g., gpt-4o-mini)")
    region: str = Field(..., description="Azure region (e.g., eastus, westus)")
    api_version: str = Field(default=AZURE_OPENAI_DEFAULT_API_VERSION, description="Azure OpenAI API version")
    endpoint_url: str = Field(..., description="Azure OpenAI endpoint URL (e.g., https://drm-openai-eastus2.openai.azure.com)")
    subscription_id: Optional[str] = Field(default=None, description="Azure subscription ID for subscription-specific routing")

    @field_validator('deployment')
    @classmethod
    def validate_deployment(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("deployment cannot be empty")
        return v

    @field_validator('region')
    @classmethod
    def validate_region(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("region cannot be empty")
        return v

    @field_validator('endpoint_url')
    @classmethod
    def validate_endpoint_url(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("endpoint_url cannot be empty")
        if not v.startswith('https://'):
            raise ValueError(f"endpoint_url must start with 'https://' but got: {v}")
        return v


class AWSEndpointSchema(BaseModel):
    """AWS Bedrock endpoint configuration."""

    model_id: str = Field(..., description="Bedrock model ID (e.g., anthropic.claude-3-haiku-20240307-v1:0)")
    region: str = Field(..., description="AWS region (e.g., us-east-1, ap-southeast-2)")

    class Config:
        extra = 'allow'  # Allow additional fields

    @field_validator('model_id')
    @classmethod
    def validate_model_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("model_id cannot be empty")
        return v

    @field_validator('region')
    @classmethod
    def validate_region(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("region cannot be empty")
        return v


class GCPEndpointSchema(BaseEndpointSchema):
    """GCP Vertex AI endpoint configuration."""

    model: str = Field(..., description="Gemini model name (e.g., gemini-2.0-flash-001)")
    region: str = Field(..., description="GCP region (e.g., us-central1, asia-southeast1)")

    @field_validator('model')
    @classmethod
    def validate_model(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("model cannot be empty")
        return v

    @field_validator('region')
    @classmethod
    def validate_region(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("region cannot be empty")
        return v


# ============================================================================
# Authentication Configuration Schemas
# ============================================================================

class BaseAuthSchema(BaseModel):
    """Base schema for authentication configuration."""

    class Config:
        extra = 'allow'  # Allow additional fields


class AzureAuthSchema(BaseAuthSchema):
    """Azure authentication configuration."""

    scope: str = Field(..., description="Azure Managed Identity scope/client_id")

    @field_validator('scope')
    @classmethod
    def validate_scope(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("scope cannot be empty")
        return v


class AWSAuthSchema(BaseAuthSchema):
    """AWS authentication configuration."""

    role_arn: str = Field(..., description="AWS IAM role ARN for cross-account access")

    @field_validator('role_arn')
    @classmethod
    def validate_role_arn(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("role_arn cannot be empty")
        if not v.startswith('arn:aws:iam::'):
            raise ValueError(f"role_arn must start with 'arn:aws:iam::' but got: {v}")
        return v


class GCPAuthSchema(BaseAuthSchema):
    """GCP Workload Identity Federation authentication configuration."""

    project_id: str = Field(..., description="GCP project ID")
    audience: str = Field(..., description="WIF audience URL")
    token_url: str = Field(..., description="STS token exchange URL")
    service_account: str = Field(..., description="Service account email")

    @field_validator('project_id')
    @classmethod
    def validate_project_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("project_id cannot be empty")
        return v

    @field_validator('audience')
    @classmethod
    def validate_audience(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("audience cannot be empty")
        if not v.startswith('//iam.googleapis.com/'):
            raise ValueError(f"audience must start with '//iam.googleapis.com/' but got: {v}")
        return v

    @field_validator('token_url')
    @classmethod
    def validate_token_url(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("token_url cannot be empty")
        if not v.startswith('https://'):
            raise ValueError(f"token_url must start with 'https://' but got: {v}")
        return v

    @field_validator('service_account')
    @classmethod
    def validate_service_account(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("service_account cannot be empty")
        if '@' not in v:
            raise ValueError(f"service_account must be a valid email address but got: {v}")
        return v


# ============================================================================
# Validation Functions
# ============================================================================

# Type alias for LLM tier - accepts any tier name defined in endpoints.json
# Common values: 'gpt-4o-mini' (cost-effective), 'claude-opus' (capable), 'reasoning' (deep thinking)
# The tier must exist in your endpoints.json for the selected cloud/provider/geo combination
LLM_TIER_TYPE = str
CLOUD_PROVIDER_TYPE = Literal['azure', 'aws', 'gcp']

def validate_endpoint(endpoint: Dict[str, Any], cloud: CLOUD_PROVIDER_TYPE, tier: LLM_TIER_TYPE = 'unknown') -> None:
    """
    Validate endpoint configuration for a specific cloud provider.

    Args:
        endpoint: Endpoint configuration dictionary
        cloud: Cloud provider ('azure', 'aws', 'gcp')
        tier: Endpoint tier name - used for error messages

    Raises:
        ValidationError: If endpoint configuration is invalid
    """
    try:
        if cloud == 'azure':
            AzureEndpointSchema(**endpoint)
        elif cloud == 'aws':
            AWSEndpointSchema(**endpoint)
        elif cloud == 'gcp':
            GCPEndpointSchema(**endpoint)
        else:
            raise ValidationError(f"Unknown cloud provider: {cloud}")

        logger.debug(f"✓ {tier.capitalize()} endpoint validated for {cloud}")

    except Exception as e:
        error_msg = f"Invalid {tier} endpoint configuration for {cloud}: {e}"
        logger.error(error_msg)
        raise ValidationError(error_msg) from e


def validate_auth_config(auth_config: Dict[str, Any], cloud: CLOUD_PROVIDER_TYPE) -> None:
    """
    Validate authentication configuration for a specific cloud provider.

    Args:
        auth_config: Authentication configuration dictionary
        cloud: Cloud provider ('azure', 'aws', 'gcp')

    Raises:
        ValidationError: If auth configuration is invalid
    """
    try:
        if cloud == 'azure':
            AzureAuthSchema(**auth_config)
        elif cloud == 'aws':
            AWSAuthSchema(**auth_config)
        elif cloud == 'gcp':
            GCPAuthSchema(**auth_config)
        else:
            raise ValidationError(f"Unknown cloud provider: {cloud}")

        logger.debug(f"✓ Auth configuration validated for {cloud}")

    except Exception as e:
        error_msg = f"Invalid auth configuration for {cloud}: {e}"
        logger.error(error_msg)
        raise ValidationError(error_msg) from e


def validate_endpoints_config(
    endpoint: Dict[str, Any],
    auth_config: Dict[str, Any],
    cloud: CLOUD_PROVIDER_TYPE
) -> None:
    """
    Validate complete endpoints configuration including auth.

    Args:
        endpoint: Endpoint configuration for the requested tier
        auth_config: Authentication configuration
        cloud: Cloud provider ('azure', 'aws', 'gcp')

    Raises:
        ValidationError: If any configuration is invalid
    """
    logger.info(f"Validating endpoints configuration for {cloud}")

    # Validate endpoint
    tier = endpoint.get('tier', 'unknown')
    validate_endpoint(endpoint, cloud, tier=tier)

    # Validate auth configuration
    validate_auth_config(auth_config, cloud)

    logger.info(f"✓ Endpoints and auth configuration validated for {cloud}")
