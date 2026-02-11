# LLM Router Module Design

## Overview
A Python module for detecting cloud VM location, selecting appropriate LLM endpoints, authenticating with cloud providers, and configuring PydanticAI clients for multi-tier AI inference.

## Package Structure

```
llm_router/
├── __init__.py                 # Main package entry point
├── MODULE_DESIGN.md           # This file
├── logger.py                  # Logging configuration and utilities
│
├── core/
│   ├── __init__.py            # Type exports (CLOUD_PROVIDER_TYPE, LLM_TIER_TYPE, etc.)
│   ├── location.py            # VM location detection
│   ├── identity.py            # Azure UMI discovery and management
│   ├── endpoints.py           # Endpoint selection logic (single-tier)
│   ├── config.py              # Configuration management
│   ├── schema.py              # Configuration schemas and validation
│   └── loader.py              # Config/endpoint file loader (local + Azure Storage)
│
├── auth/
│   ├── __init__.py            # Auth exports and base interfaces
│   ├── base.py                # Base authenticator interface
│   ├── azure.py               # Azure UMI authentication
│   ├── gcp.py                 # GCP Workload Identity Federation
│   └── aws.py                 # AWS AssumeRoleWithWebIdentity + RefreshableBedrockProvider
│
├── clients/
│   ├── __init__.py
│   ├── factory.py             # Framework-agnostic client factory
│   ├── pydantic_ai.py         # PydanticAI framework client wrapper
│   └── native.py              # Native cloud SDK client wrapper
│
└── router.py                   # Main orchestrator class (single-tier)
```

## Configuration Files

### config.json
**Default Search Paths** (searched in order):
1. User-provided path (via `initialize(config_path=...)`)
2. Current working directory: `./config.json`
3. User home directory: `~/.llm_router/config.json`
4. System-wide: `/etc/llm_router/config.json`

**Structure**:
```json
{
  "llm_cloud": "azure",
  "llm_provider": "openai",
  "tier": "gpt-4o-mini",
  "framework": "pydantic-ai",
  "endpoints_source": "./endpoints.json"
}
```

**Fields**:
- `llm_cloud`: Cloud provider (azure/gcp/aws)
- `llm_provider`: AI provider (openai/claude/gemini)
- `tier`: Default tier name from endpoints.json (e.g., "light", "gpt-4o-mini", "claude-opus") - optional
- `framework`: LLM framework to use ("pydantic-ai" or "native") - optional, defaults to "pydantic-ai"
- `endpoints_source`: Path or URL to endpoints.json - optional
  - Can be local path or Azure Storage URL
  - Defaults to `./endpoints.json` if not specified

**Note**: Tier names are flexible and configuration-driven. You can use any tier name defined in your endpoints.json file (not limited to "light"/"heavy").

### endpoints.json
**Location Options**:
1. **Local file path**: `/path/to/endpoints.json` or `./endpoints.json`
2. **Azure Storage Account URL**: `https://storageaccount.blob.core.windows.net/container/endpoints.json`
   - Authenticated using VM's User Managed Identity (UMI)
   - Automatically fetches storage access token
   - Supports both public and private storage accounts

**Specification**:
- Can be specified in `config.json` via `endpoints_source` field
- Can be overridden via `initialize(endpoints_source=...)`
- Defaults to `./endpoints.json` if not specified

**Structure** (Single-Tier Format):
```json
{
  "routing": {
    "defaults": {
      "tier": "light"
    }
  },
  "clouds": {
    "aws": {
      "providers": {
        "claude": {
          "endpoints": [
            {
              "geo": "US",
              "tier": "light",
              "model_id": "claude-haiku-4-5",
              "region": "us-east-1"
            },
            {
              "geo": "US",
              "tier": "heavy",
              "model_id": "claude-sonnet-4-5",
              "region": "us-east-1"
            },
            {
              "geo": "US",
              "tier": "claude-opus",
              "model_id": "claude-opus-4-5",
              "region": "us-west-2"
            }
          ],
          "auth": {
            "role_arn": "arn:aws:iam::139872254141:role/AzureWIFBedrockRole"
          }
        }
      }
    },
    "azure": {
      "providers": {
        "openai": {
          "endpoints": [
            {
              "geo": "US",
              "tier": "gpt-4o-mini",
              "model_id": "gpt-4o-mini",
              "endpoint": "https://eastus.openai.azure.com"
            },
            {
              "geo": "EU",
              "tier": "gpt-4o",
              "model_id": "gpt-4o",
              "endpoint": "https://westeurope.openai.azure.com"
            }
          ]
        }
      }
    }
  }
}
```

**Key Features**:
- **routing.defaults.tier**: Specifies the default tier to use when not explicitly provided
- **Flexible tier names**: Use any tier name (light, heavy, gpt-4o-mini, claude-opus, etc.)
- **Single-tier endpoints**: Each endpoint represents ONE tier (not dual light/heavy)
- **Per-geo configuration**: Different tiers can be available in different geographic regions

## Logging

### Overview
The module uses Python's standard `logging` library with a hierarchical logger structure. Users can configure logging in their application to see internal operations.

### Logger Hierarchy
```
llm_router                      # Root logger
├── llm_router.core.location    # Location detection
├── llm_router.core.loader      # File loading
├── llm_router.core.config      # Configuration
├── llm_router.core.endpoints   # Endpoint selection
├── llm_router.auth.azure       # Azure authentication
├── llm_router.auth.gcp         # GCP authentication
├── llm_router.auth.aws         # AWS authentication
├── llm_router.clients.factory  # Client factory
└── llm_router.router           # Main router
```

### Logging Levels

**DEBUG**: Detailed diagnostic information
- Token requests/responses (sanitized)
- Endpoint selection logic
- Configuration file contents
- Authentication flow details

**INFO**: General informational messages
- VM location detected: region, geo zone
- Config file loaded from: path/URL
- Endpoints file loaded from: path/URL
- Authentication successful for: cloud/provider
- Clients created for: light/heavy tiers

**WARNING**: Unexpected situations that don't prevent operation
- Config not found in default paths, using fallback
- Region not in geo_map, defaulting to US
- Token refresh needed

**ERROR**: Errors that prevent specific operations
- Failed to load config from Azure Storage
- Authentication failed for provider
- Endpoint not found for geo/tier combination

### User Configuration

**Basic Usage** - Enable INFO level logging:
```python
import logging
from llm_router import LLMRouter

# Configure logging before initializing router
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

router = LLMRouter()
router.initialize()
```

**Debug Mode** - See detailed diagnostics:
```python
import logging

# Enable DEBUG for entire module
logging.getLogger('llm_router').setLevel(logging.DEBUG)

# Or enable for specific component
logging.getLogger('llm_router.auth.azure').setLevel(logging.DEBUG)
```

**Custom Handler** - Send logs to file:
```python
import logging

logger = logging.getLogger('llm_router')
logger.setLevel(logging.INFO)

# Add file handler
handler = logging.FileHandler('/var/log/llm_router.log')
handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))
logger.addHandler(handler)
```

**Disable Logging** - Suppress all messages:
```python
import logging

logging.getLogger('llm_router').setLevel(logging.CRITICAL)
```

### Example Log Output

```
2025-10-24 10:30:15,123 - llm_router.router - INFO - Initializing LLM Router
2025-10-24 10:30:15,125 - llm_router.core.config - INFO - Searching for config.json in default paths
2025-10-24 10:30:15,126 - llm_router.core.config - INFO - Config loaded from: /home/user/.llm_router/config.json
2025-10-24 10:30:15,127 - llm_router.core.loader - INFO - Loading endpoints from: https://storage.blob.core.windows.net/config/endpoints.json
2025-10-24 10:30:15,128 - llm_router.core.loader - DEBUG - Detected Azure Storage URL, requesting storage token
2025-10-24 10:30:15,340 - llm_router.core.loader - DEBUG - Storage token obtained, downloading blob
2025-10-24 10:30:15,456 - llm_router.core.loader - INFO - Endpoints loaded successfully (version: 2.0.0)
2025-10-24 10:30:15,457 - llm_router.core.location - INFO - Querying Azure IMDS for VM location
2025-10-24 10:30:15,512 - llm_router.core.location - INFO - VM detected: region=australiaeast, vmId=5297991c-...
2025-10-24 10:30:15,513 - llm_router.core.location - INFO - Mapped region to geo zone: APAC
2025-10-24 10:30:15,514 - llm_router.core.endpoints - INFO - Selecting endpoints for: cloud=aws, provider=claude, geo=APAC
2025-10-24 10:30:15,515 - llm_router.core.endpoints - INFO - Found endpoints: light=claude-haiku, heavy=claude-sonnet
2025-10-24 10:30:15,516 - llm_router.auth.aws - INFO - Starting AWS authentication via AssumeRoleWithWebIdentity
2025-10-24 10:30:15,517 - llm_router.auth.aws - DEBUG - Fetching Azure UMI token for federation
2025-10-24 10:30:15,620 - llm_router.auth.aws - DEBUG - Assuming role: arn:aws:iam::139872254141:role/AzureWIFBedrockRole
2025-10-24 10:30:15,892 - llm_router.auth.aws - INFO - AWS credentials obtained, valid until: 2025-10-24 11:30:15
2025-10-24 10:30:15,893 - llm_router.clients.factory - INFO - Creating PydanticAI client for: provider=claude, tier=light
2025-10-24 10:30:15,920 - llm_router.clients.factory - INFO - Creating PydanticAI client for: provider=claude, tier=heavy
2025-10-24 10:30:15,945 - llm_router.router - INFO - LLM Router initialized successfully
```

### Security Considerations
- **Never log sensitive data**: Tokens, credentials, API keys are sanitized
- **Token logging**: Only first/last 4 characters shown in DEBUG mode (e.g., `xyz...abc`)
- **Endpoint URLs**: Full URLs logged for troubleshooting
- **VM metadata**: Safe to log (region, vmId, resource group)

## Module Responsibilities

### 1. `core/location.py`
**Purpose**: Detect current VM location using cloud metadata services

**Classes**:
- `LocationDetector`: Queries Azure IMDS for VM metadata
  - Methods:
    - `detect()`: Returns location info (region, vmId, etc.)
    - `get_region()`: Returns region string
    - `get_geo_zone(region)`: Maps region to geo (US/EU/APAC)

### 2. `core/endpoints.py`
**Purpose**: Select appropriate endpoints based on location and config (single-tier)

**Classes**:
- `EndpointSelector`: Selects single-tier endpoints from endpoints.json
  - Methods:
    - `select(geo, cloud, provider, tier=None)`: Returns single EndpointConfig for specified tier
      - If tier is None, uses routing.defaults.tier from endpoints.json
      - If default tier unavailable, selects first available tier alphabetically
    - `get_auth_config(cloud, provider)`: Returns auth configuration
  - Returns:
    - `EndpointConfig`: Dataclass containing tier and endpoint data
      - `tier`: str - The selected tier name
      - `endpoint`: Dict[str, Any] - Single endpoint configuration

### 3. `core/loader.py`
**Purpose**: Load configuration files from local filesystem or Azure Storage

**Classes**:
- `ConfigLoader`: Smart loader for JSON files
  - Methods:
    - `load(source)`: Load from local path or URL
    - `_load_local(path)`: Load from local file
    - `_load_azure_storage(url)`: Load from Azure Storage with UMI auth
    - `_get_storage_token()`: Get Azure Storage access token via UMI
  - Static Methods:
    - `is_azure_storage_url(source)`: Check if source is Azure Storage URL
    - `find_config(filename, search_paths)`: Search for config in default paths

### 4. `core/config.py`
**Purpose**: Manage and validate configuration

**Classes**:
- `Config`: Configuration manager
  - Properties:
    - `llm_cloud`: Selected cloud provider
    - `llm_provider`: Selected AI provider
    - `tier`: Optional[str] - Default tier (flexible, configuration-driven)
    - `framework`: str - LLM framework ('pydantic-ai' or 'native')
    - `endpoints_source`: Path or URL to endpoints.json
  - Methods:
    - `load(config_path=None)`: Load config (searches defaults if None)
    - `validate()`: Validate configuration
  - Constants:
    - `DEFAULT_SEARCH_PATHS`: List of default config locations

**Type Changes**:
- Tier type changed from `Literal['light', 'heavy']` to `Optional[str]`
- Supports any tier name defined in endpoints.json

### 5. `auth/base.py`
**Purpose**: Base interface for cloud authenticators

**Classes**:
- `BaseAuthenticator` (Abstract):
  - Methods:
    - `authenticate()`: Perform authentication, return credentials
    - `get_token()`: Get access token for API calls

### 6. `auth/azure.py`
**Purpose**: Azure-specific authentication using User Managed Identity

**Classes**:
- `AzureAuthenticator(BaseAuthenticator)`:
  - Detects Azure User Managed Identity (UMI)
  - Gets tokens for specified scope (e.g., Cognitive Services)
  - Methods:
    - `detect_umi()`: Find available UMIs on VM
    - `get_token(scope)`: Get token for specific scope
    - `authenticate()`: Setup authentication for PydanticAI

### 6. `auth/gcp.py`
**Purpose**: GCP Workload Identity Federation authentication

**Classes**:
- `GCPAuthenticator(BaseAuthenticator)`:
  - Uses Azure token to get GCP token via WIF
  - Methods:
    - `exchange_token(azure_token)`: Exchange Azure token for GCP
    - `get_service_account_token()`: Get SA token
    - `authenticate()`: Setup authentication for PydanticAI

### 7. `auth/aws.py`
**Purpose**: AWS AssumeRoleWithWebIdentity authentication

**Classes**:
- `AWSAuthenticator(BaseAuthenticator)`:
  - Uses Azure token to assume AWS role
  - Methods:
    - `assume_role(azure_token)`: Assume AWS role
    - `get_credentials()`: Get temporary AWS credentials
    - `authenticate()`: Setup authentication for PydanticAI

### 8. `clients/pydantic_ai.py`
**Purpose**: Wrapper for PydanticAI framework client

**Classes**:
- `PydanticAIClient`:
  - Wrapper around pydantic-ai Model for single tier
  - Properties:
    - `_client`: Model - The underlying pydantic-ai Model
    - `tier`: str - The tier name (e.g., 'light', 'gpt-4o-mini', 'claude-opus')
    - `cloud`: str - Cloud provider
    - `provider`: str - AI provider
    - `geo`: str - Geographic region
    - `region`: str - Cloud region
  - Methods:
    - Direct access to underlying pydantic-ai Model via `._client`
    - Use with `Agent(model=client._client, ...)`

**Note**: This client is specific to the pydantic-ai framework. For native cloud SDKs, use `NativeClient`.

### 9. `clients/native.py`
**Purpose**: Wrapper for native cloud SDK clients

**Classes**:
- `NativeClient`:
  - Wrapper around native cloud SDK clients (boto3, Azure OpenAI SDK, Google SDK)
  - Properties:
    - `_client`: The underlying native SDK client (e.g., boto3.client('bedrock-runtime'))
    - `tier`: str - The tier name
    - `cloud`: str - Cloud provider
    - `provider`: str - AI provider
    - `geo`: str - Geographic region
    - `region`: str - Cloud region
  - Methods:
    - Direct access to native SDK via `._client`
    - Use for LangChain, LlamaIndex, or custom integrations

**Supported Native Clients**:
- **AWS**: `boto3.client('bedrock-runtime')` with RefreshableBedrockProvider
- **Azure**: Azure OpenAI SDK client
- **GCP**: Google Generative AI SDK client

### 10. `clients/factory.py`
**Purpose**: Framework-agnostic factory for creating configured clients

**Classes**:
- `ClientFactory`:
  - Creates clients based on framework, cloud, provider, and authentication
  - **Main Method**:
    - `create_client(endpoint_config, authenticator, framework='pydantic-ai')`: Create single-tier client
      - Parameters:
        - `endpoint_config`: EndpointConfig - Contains tier and endpoint data
        - `authenticator`: BaseAuthenticator - Cloud authentication handler
        - `framework`: str - 'pydantic-ai' or 'native'
      - Returns: PydanticAIClient or NativeClient

  - **Factory Methods** (6 total):

    **PydanticAI Framework (3 methods)**:
    - `_create_aws_client(endpoint_config, authenticator)`: Create AWS Bedrock client with pydantic-ai
    - `_create_azure_client(endpoint_config, authenticator)`: Create Azure OpenAI client with pydantic-ai
    - `_create_gcp_client(endpoint_config, authenticator)`: Create GCP Vertex AI client with pydantic-ai

    **Native SDK Framework (3 methods)**:
    - `_create_native_aws_client(endpoint_config, authenticator)`: Create boto3 Bedrock client
    - `_create_native_azure_client(endpoint_config, authenticator)`: Create Azure OpenAI SDK client
    - `_create_native_gcp_client(endpoint_config, authenticator)`: Create Google SDK client

**Pattern**: Single-tier factory methods. Tier selection happens in EndpointSelector before factory is called.

### 11. `router.py`
**Purpose**: Main orchestrator that ties everything together (single-tier architecture)

**Classes**:
- `LLMRouter`:
  - Main entry point for the module - manages ONE tier per instance
  - **Constructor**:
    - `__init__(tier=None, framework='pydantic-ai', cloud=None, provider=None, geo=None)`
      - `tier`: Optional[str] - Tier name (uses routing.defaults.tier if None)
      - `framework`: str - 'pydantic-ai' or 'native' (default: 'pydantic-ai')
      - `cloud`: Optional[str] - Cloud provider override
      - `provider`: Optional[str] - AI provider override
      - `geo`: Optional[str] - Geographic region override

  - **Properties**:
    - `location`: Detected location info (region, vmId, etc.)
    - `endpoint_config`: EndpointConfig - Single selected endpoint configuration
    - `authenticator`: BaseAuthenticator - Cloud authentication handler
    - `client`: PydanticAIClient or NativeClient - The configured client for this tier

  - **Methods**:
    - `initialize(config_path=None, endpoints_source=None)`: Setup router (deprecated, auto-initialized in __init__)
    - `get_client()`: Get the configured client (returns self.client)
    - `get_endpoint_info()`: Get endpoint information

**Design Pattern**: Single Responsibility - each router instance manages ONE tier only.

**Example**:
```python
# Create separate routers for different tiers
light_router = LLMRouter(tier='light', framework='pydantic-ai')
heavy_router = LLMRouter(tier='claude-opus', framework='pydantic-ai')

# Get clients
light_client = light_router.get_client()
heavy_client = heavy_router.get_client()
```

## Usage Flow

### Single-Tier Architecture Pattern

```python
import logging
from llm_router import LLMRouter
from pydantic_ai import Agent

# Configure logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# === Single-Tier Pattern (Recommended) ===
# Create separate routers for different tiers

# Light tier for simple tasks
light_router = LLMRouter(tier='light', framework='pydantic-ai')
light_client = light_router.get_client()

# Heavy tier for complex reasoning
heavy_router = LLMRouter(tier='heavy', framework='pydantic-ai')
heavy_client = heavy_router.get_client()

# Use light client for simple queries
light_agent = Agent(
    model=light_client._client,  # Access underlying pydantic-ai Model
    system_prompt="You are a helpful assistant"
)
result = light_agent.run_sync("What is 2+2?")

# Use heavy client for complex reasoning
heavy_agent = Agent(
    model=heavy_client._client,
    system_prompt="You are an expert reasoning assistant"
)
result = heavy_agent.run_sync("Explain quantum computing in detail")
```

### Framework Selection

```python
# === PydanticAI Framework (default) ===
from llm_router import LLMRouter
from pydantic_ai import Agent

router = LLMRouter(tier='gpt-4o-mini', framework='pydantic-ai')
client = router.get_client()

agent = Agent(
    model=client._client,
    system_prompt="You are a helpful assistant"
)
result = agent.run_sync("Hello!")

# === Native SDK Framework ===
from llm_router import LLMRouter

# Get native boto3 client for AWS Bedrock
router = LLMRouter(tier='claude-opus', framework='native')
native_client = router.get_client()

# Use with LangChain, LlamaIndex, or direct SDK calls
bedrock = native_client._client  # boto3.client('bedrock-runtime')
# ... use bedrock client directly
```

### LLMIntegration Pattern (Lazy Loading)

```python
from llm_router import LLMRouter

class LLMIntegration:
    """Integration that lazily creates routers on-demand"""

    def __init__(self):
        self._routers = {}  # Cache tier-specific routers

    def create_model(self, tier='light', framework='pydantic-ai'):
        """Get or create router for specified tier"""
        cache_key = f"{tier}:{framework}"

        if cache_key not in self._routers:
            self._routers[cache_key] = LLMRouter(
                tier=tier,
                framework=framework
            )

        return self._routers[cache_key].get_client()

# Usage
integration = LLMIntegration()

# Only creates light router on first call
light_client = integration.create_model(tier='light')

# Only creates heavy router on first call
heavy_client = integration.create_model(tier='heavy')

# Reuses cached light router
light_client_again = integration.create_model(tier='light')
```

### Custom Configuration

```python
# Override cloud, provider, or geo
router = LLMRouter(
    tier='claude-opus',
    framework='pydantic-ai',
    cloud='aws',
    provider='claude',
    geo='US'
)

# Specify custom config and endpoints paths
# Note: initialize() is deprecated, config is auto-loaded in __init__
# But you can still set environment variables or config files
```

## Configuration Flow

**Single-Tier Initialization Flow**:

1. **Load Configuration** → `config.json` determines cloud, provider, framework
2. **Detect VM Location** → Get cloud region from IMDS
3. **Map Region to Geo** → Convert region to geo zone (US/EU/APAC)
4. **Select Endpoint** → Single-tier endpoint from `endpoints.json`
   - Use specified tier, or routing.defaults.tier, or first available
5. **Authenticate to Cloud** → Get credentials/tokens for target cloud
6. **Create Client** → Single client based on framework (pydantic-ai or native)
7. **Return Client** → Ready to use

**Key Differences from Previous Architecture**:
- ✅ Single-tier selection (not dual light/heavy)
- ✅ Framework-agnostic client creation
- ✅ Configuration-driven tier names
- ✅ Smart default tier selection from routing.defaults

## Authentication Strategies

### Azure OpenAI
1. Detect User Managed Identity on VM
2. Get token for scope: `https://cognitiveservices.azure.com/.default`
3. Configure PydanticAI with token authentication

### GCP Vertex AI (from Azure VM)
1. Get Azure UMI token
2. Exchange via Workload Identity Federation
3. Get service account token
4. Configure PydanticAI with GCP credentials

### AWS Bedrock (from Azure VM)
1. Get Azure UMI token
2. Assume AWS role using `AssumeRoleWithWebIdentity`
3. Get temporary AWS credentials
4. **RefreshableBedrockProvider**: Custom provider that inherits from `pydantic_ai.providers.Provider`
   - Automatically refreshes credentials when they expire
   - Explicitly inherits from Provider[BaseClient] for type safety
   - Manages boto3 bedrock-runtime client lifecycle
5. Configure framework client:
   - **PydanticAI**: Use RefreshableBedrockProvider with pydantic-ai
   - **Native**: Use boto3 bedrock-runtime client directly

## Architecture Design

### Framework Independence

The llm_router module supports multiple LLM frameworks through a pluggable architecture:

**Supported Frameworks**:
1. **pydantic-ai** (default): PydanticAI framework with structured outputs
   - Returns `PydanticAIClient` wrapper
   - Access underlying Model via `client._client`
   - Best for: Structured output, type-safe AI agents

2. **native**: Native cloud SDKs (boto3, Azure OpenAI SDK, Google SDK)
   - Returns `NativeClient` wrapper
   - Access underlying SDK client via `client._client`
   - Best for: LangChain, LlamaIndex, custom integrations

**Framework Selection**:
```python
# PydanticAI (default)
router = LLMRouter(tier='light', framework='pydantic-ai')

# Native SDKs
router = LLMRouter(tier='light', framework='native')
```

**Benefits**:
- ✅ Not locked into pydantic-ai
- ✅ Can use any LLM framework
- ✅ Direct SDK access when needed
- ✅ Future-proof architecture

### Single-Tier Architecture

**Design Decision**: Each `LLMRouter` instance manages ONE tier only.

**Before (Dual-Tier)**:
```python
router = LLMRouter()
light = router.light   # Both created simultaneously
heavy = router.heavy
```

**After (Single-Tier)**:
```python
light_router = LLMRouter(tier='light')   # Creates light only
heavy_router = LLMRouter(tier='heavy')   # Creates heavy only

light_client = light_router.get_client()
heavy_client = heavy_router.get_client()
```

**Rationale**:
1. **Simpler API**: Clear single responsibility per router
2. **Better Performance**: ~50% faster initialization, ~50% less memory
3. **Lazy Loading**: Only create routers for tiers you actually use
4. **Explicit Resource Management**: Clear ownership of resources
5. **Flexible Tier Names**: Not limited to "light" and "heavy"

**Performance Comparison**:
| Metric | Dual-Tier | Single-Tier | Improvement |
|--------|-----------|-------------|-------------|
| Init Time | ~2.0s | ~1.0s | 50% faster |
| Memory | ~200MB | ~100MB | 50% less |
| Auth Calls | 2 | 1 | 50% fewer |

### Configuration-Driven Tiers

**Design Decision**: Tier names are defined in `endpoints.json`, not hardcoded in Python.

**Benefits**:
1. **Flexibility**: Use any tier name (light, heavy, gpt-4o-mini, claude-opus, etc.)
2. **No Code Changes**: Add new tiers by updating configuration only
3. **Customer-Specific**: Different customers can have different tier names
4. **Per-Cloud Customization**: Different tier names for different clouds/providers

**Example Tier Names**:
- Cost-effective: `gpt-4o-mini`, `claude-haiku`, `gemini-flash`
- Capable: `claude-opus`, `gpt-5`, `gemini-pro`
- Reasoning: `o3-mini`, `reasoning`
- Custom: Any name you define in endpoints.json

**Default Tier Selection**:
```json
{
  "routing": {
    "defaults": {
      "tier": "light"
    }
  }
}
```

**Selection Precedence**:
1. User-specified tier (via `LLMRouter(tier='...')`)
2. `routing.defaults.tier` from endpoints.json
3. First available tier alphabetically

## Migration Guide

### Breaking Changes from Dual-Tier Architecture

**1. API Change: Removed dual properties**
```python
# ❌ Old (Dual-Tier)
router = LLMRouter()
light = router.light
heavy = router.heavy

# ✅ New (Single-Tier)
light_router = LLMRouter(tier='light')
heavy_router = LLMRouter(tier='heavy')

light = light_router.get_client()
heavy = heavy_router.get_client()
```

**2. Type Change: Flexible tier names**
```python
# ❌ Old (Hardcoded)
tier: Literal['light', 'heavy']

# ✅ New (Configuration-Driven)
tier: Optional[str]  # Any tier from endpoints.json
```

**3. Client Access: Use _client property**
```python
# ❌ Old
agent = Agent(model=client.client)

# ✅ New
agent = Agent(model=client._client)
```

**4. LLMIntegration: Lazy router caching**
```python
# ❌ Old
class LLMIntegration:
    def __init__(self):
        self.router = LLMRouter()  # Both tiers created

    def create_model(self, tier='light'):
        return self.router.light if tier == 'light' else self.router.heavy

# ✅ New
class LLMIntegration:
    def __init__(self):
        self._routers = {}  # Lazy cache

    def create_model(self, tier='light', framework='pydantic-ai'):
        cache_key = f"{tier}:{framework}"
        if cache_key not in self._routers:
            self._routers[cache_key] = LLMRouter(tier=tier, framework=framework)
        return self._routers[cache_key].get_client()
```

**5. Endpoints.json: Single-tier format**
```json
// ❌ Old (Dual-Tier)
{
  "endpoints": [
    {
      "geo": "US",
      "light": { "model_id": "haiku", "tier": "light" },
      "heavy": { "model_id": "sonnet", "tier": "heavy" }
    }
  ]
}

// ✅ New (Single-Tier)
{
  "routing": {
    "defaults": { "tier": "light" }
  },
  "endpoints": [
    {
      "geo": "US",
      "tier": "light",
      "model_id": "claude-haiku-4-5",
      "region": "us-east-1"
    },
    {
      "geo": "US",
      "tier": "heavy",
      "model_id": "claude-sonnet-4-5",
      "region": "us-east-1"
    }
  ]
}
```

### Migration Checklist

- [ ] Update LLMIntegration to use lazy router caching
- [ ] Change `router.light`/`router.heavy` to separate router instances
- [ ] Update `client.client` to `client._client` in all Agent creations
- [ ] Update endpoints.json to single-tier format
- [ ] Add `routing.defaults.tier` to endpoints.json
- [ ] Update tier type annotations from `Literal['light', 'heavy']` to `Optional[str]`
- [ ] Test with both 'pydantic-ai' and 'native' frameworks
- [ ] Verify tier selection logic (default tier, fallback)

## Error Handling

- `LocationDetectionError`: Cannot detect VM location
- `EndpointNotFoundError`: No matching endpoint for tier/geo/cloud/provider
- `AuthenticationError`: Authentication failed
- `ConfigurationError`: Invalid configuration
- `ClientCreationError`: Cannot create client
- `TierNotFoundError`: Specified tier not available for geo
- `FrameworkNotSupportedError`: Unsupported framework specified

**Enhanced Error Messages**:
When a tier is not found, the error now shows available tiers:
```
No 'custom-tier' tier endpoint found for cloud=aws, provider=claude, geo=US.
Available tiers: light, heavy, claude-opus
```

## Extension Points

- **Add new clouds**: Implement new authenticator in `auth/`
- **Add new providers**: Update endpoint selection and client factory
- **Add new frameworks**: Extend `clients/factory.py` with new framework support
- **Add new tiers**: Update endpoints.json configuration (no code changes needed)
- **Custom providers**: Inherit from `pydantic_ai.providers.Provider` like RefreshableBedrockProvider
