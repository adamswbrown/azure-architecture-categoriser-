"""
Centralized constants for llm_router module.

This module contains all configuration constants, timeouts, URLs, and magic values
used throughout the llm_router package. Centralizing these values makes them easier
to maintain and tune.
"""

from datetime import timedelta
from enum import Enum


# ============================================================================
# Cloud Provider Identifiers
# ============================================================================

class CloudProvider(str, Enum):
    """Supported cloud providers."""
    AWS = 'aws'
    AZURE = 'azure'
    GCP = 'gcp'


class EnvironmentType(str, Enum):
    """Runtime environment types."""
    AZURE_VM = 'azure_vm'
    LOCAL = 'local'


# ============================================================================
# Azure Instance Metadata Service (IMDS)
# ============================================================================

# IMDS endpoints
IMDS_BASE_URL = "http://169.254.169.254"
IMDS_TOKEN_URL = f"{IMDS_BASE_URL}/metadata/identity/oauth2/token"
IMDS_INSTANCE_URL = f"{IMDS_BASE_URL}/metadata/instance"

# IMDS API versions
IMDS_API_VERSION = "2018-02-01"
IMDS_INSTANCE_API_VERSION = "2021-02-01"

# IMDS timeouts
IMDS_TIMEOUT = 10  # seconds


# ============================================================================
# Azure Resource Manager (ARM)
# ============================================================================

ARM_RESOURCE = "https://management.azure.com/"
ARM_API_VERSION = "2023-03-01"
ARM_TIMEOUT = 10  # seconds


# ============================================================================
# Azure Services
# ============================================================================

# Azure Storage
AZURE_STORAGE_RESOURCE = "https://storage.azure.com/"
AZURE_STORAGE_SCOPE = "https://storage.azure.com/.default"
AZURE_STORAGE_API_VERSION = "2021-08-06"

# Azure Cognitive Services (OpenAI)
AZURE_COGNITIVE_SERVICES_SCOPE = "https://cognitiveservices.azure.com/.default"

# Azure OpenAI
AZURE_OPENAI_ENDPOINT_PATTERN = "https://drm-openai-{region}.openai.azure.com"
AZURE_OPENAI_DEFAULT_API_VERSION = "2024-12-01-preview"


# ============================================================================
# Token Expiry and Refresh
# ============================================================================

# Buffer before token expiration to trigger refresh
TOKEN_EXPIRY_BUFFER = timedelta(minutes=5)

# Idle refresh interval for long-running clients
# Refreshes credentials every 3 minutes if no recent activity
IDLE_REFRESH_INTERVAL = timedelta(seconds=180)

# Token cache TTL
TOKEN_CACHE_TTL = timedelta(minutes=55)  # Azure tokens valid for 1 hour


# ============================================================================
# HTTP and Network Settings
# ============================================================================

# General HTTP timeout
HTTP_TIMEOUT = 10  # seconds

# Environment detection timeout (should be very fast)
ENVIRONMENT_DETECTION_TIMEOUT = 0.5  # seconds

# Connection pool settings
MAX_POOL_CONNECTIONS = 50

# Retry settings
MAX_RETRY_ATTEMPTS = 3
RETRY_BACKOFF_FACTOR = 1.0  # seconds


# ============================================================================
# AWS Settings
# ============================================================================

# AWS STS endpoint
AWS_STS_URL = "https://sts.amazonaws.com/"

# AWS session duration (1 hour, max allowed for web identity federation)
AWS_SESSION_DURATION = 3600  # seconds


# ============================================================================
# GCP Settings
# ============================================================================

# GCP STS endpoint
GCP_STS_URL = "https://sts.googleapis.com/v1/token"

# GCP scopes
GCP_CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"
GCP_GENERATIVE_LANGUAGE_SCOPE = "https://www.googleapis.com/auth/generative-language"
GCP_DEFAULT_SCOPES = [GCP_CLOUD_PLATFORM_SCOPE, GCP_GENERATIVE_LANGUAGE_SCOPE]

# GCP IAM Credentials API
GCP_IAM_CREDENTIALS_BASE_URL = "https://iamcredentials.googleapis.com/v1"
GCP_SA_IMPERSONATION_URL_PATTERN = "{base}/projects/-/serviceAccounts/{sa}:generateAccessToken"


# ============================================================================
# Configuration and Schema
# ============================================================================

# Supported schema versions
SCHEMA_VERSION_2_0 = "2.0.0"
SCHEMA_VERSION_1_0 = "1.0.0"

# Default configuration paths
DEFAULT_CONFIG_PATH = "config.json"
DEFAULT_ENDPOINTS_PATH = "endpoints.json"


# ============================================================================
# Logging
# ============================================================================

# Characters to show when sanitizing tokens/secrets
TOKEN_PREFIX_LENGTH = 8
TOKEN_SUFFIX_LENGTH = 4

# Keys to sanitize in log output
SENSITIVE_KEYS = frozenset([
    'access_token',
    'AccessKeyId',
    'SecretAccessKey',
    'SessionToken',
    'token',
    'key',
    'secret',
    'password',
    'credential',
])


# ============================================================================
# Framework Support
# ============================================================================

class Framework(str, Enum):
    """Supported LLM frameworks."""
    PYDANTIC_AI = 'pydantic-ai'
    NATIVE = 'native'


# ============================================================================
# Default Values
# ============================================================================

# Default tier when none specified
DEFAULT_TIER = 'light'
