# Dr.Migrate Assistant Configuration Guide

## Overview

The Dr.Migrate Assistant uses a **clear separation between configuration and secrets**:

- **Configuration**: Non-sensitive settings (ports, URLs, cloud providers) → Version controlled files
- **Secrets**: Sensitive credentials (database passwords) → HashiCorp Vault only

## Architecture Principles

### ✅ Configuration (Safe to Version Control)

Configuration includes non-sensitive settings that define how services run:

- Server ports, URLs, CORS origins
- Cloud provider selection (AZURE, AWS, GCP)
- LLM provider and tiers (openai, claude, gemini)
- Operating mode (dev, prod)
- Log levels, feature flags

**Where it lives:**
- `services/agents/config.toml` - Python agents configuration
- `services/copilotkit-proxy/src/config.ts` - TypeScript config module
- `infrastructure/winsw/*.xml` - WinSW service environment variables
- `services/copilotkit-proxy/.env.development` - Local development overrides

### 🔐 Secrets (NEVER in Version Control)

Secrets are **database credentials ONLY**:

- `DB_USERNAME` - Database user for agents
- `DB_PASSWORD` - Database password
- `DB_CONNECTION_STRING` - Complete connection string

**Where it lives:**
- HashiCorp Vault: `secret/data/assistant`
- Loaded by: `infrastructure/config/secrets-loader.ps1`
- Set as: Machine-level environment variables

### 🚫 What's NOT a Secret (No API Keys Needed!)

The `llm_router` module uses **identity-based authentication**, so these are NOT needed:

- ~~`AZURE_OPENAI_API_KEY`~~ → Uses `az login` (dev) or Azure UMI (prod)
- ~~`AWS_ACCESS_KEY_ID`~~ → Uses `aws configure` (dev) or AssumeRole (prod)
- ~~`AWS_SECRET_ACCESS_KEY`~~ → Uses `aws configure` (dev) or AssumeRole (prod)
- ~~`GCP_PROJECT_ID`~~ → In config.toml, not a secret

---

## Configuration Files

### 1. config.toml (Python Agents)

**Location**: `Assistant/services/agents/config.toml` (generated from `config.example.toml`)

**Purpose**: Main configuration for Python agents backend

```toml
[agents]
MODE = "dev"                    # "dev" or "prod"
CLOUD_PROVIDER = "AZURE"        # "AZURE" | "AWS" | "GCP"
LLM_PROVIDER = "openai"         # "openai" | "claude" | "gemini"
DEFAULT_TIER = "heavy"          # "light" | "heavy" | "reasoning"
ENDPOINTS_JSON_PATH = "./endpoints.json"

[server]
PORT = 8002

[db]
DB_HOST = "localhost\\SQLEXPRESS"
DB_PORT = 1433
DB_NAME = "Assessments"
# DB_USERNAME and DB_PASSWORD come from environment (Vault)
DB_TRUST_SERVER_CERTIFICATE = true
```

**How it's used:**
- Read by Python agents at startup
- MODE determines authentication method:
  - `dev`: Uses CLI credentials (az login, gcloud auth, aws configure)
  - `prod`: Uses Azure User Managed Identity + Workload Identity Federation

### 2. copilotkit-server/src/config.ts (CopilotKit Proxy)

**Location**: `Assistant/services/copilotkit-proxy/src/config.ts`

**Purpose**: Type-safe configuration for CopilotKit proxy

**Loads from environment variables** (set by WinSW XML):
- `PORT` - Server port (default: 8001)
- `NODE_ENV` - Environment (development/production)
- `PYTHON_BACKEND_URL` - Python agents URL
- `CORS_ORIGIN` - Allowed CORS origins
- `LOG_LEVEL` - Logging level
- `COPILOT_OBS_ENABLED` - Enable observability hooks

**How it's used:**
- Imported by `server.ts`
- Validates all settings on load
- Provides type-safe access to config

### 3. WinSW Service XML (Production Services)

**Locations**:
- `Assistant/infrastructure/winsw/DrMigrate-CopilotKitProxy.xml`
- `Assistant/infrastructure/winsw/DrMigrate-AgentsServer.xml`

**Purpose**: Configure Windows services via environment variables

**Example** (`copilotkit-proxy.xml`):
```xml
<env name="NODE_ENV" value="production"/>
<env name="PORT" value="8001"/>
<env name="PYTHON_BACKEND_URL" value="http://localhost:8002/api"/>
<env name="CORS_ORIGIN" value="*.drmigrate.com"/>
<env name="LOG_LEVEL" value="info"/>
```

**How it works:**
- WinSW reads XML and sets environment variables for the service process
- Service process reads from `process.env` (Node.js) or `os.environ` (Python)
- Secrets (DB credentials) inherited from Machine environment (set by Vault)

### 4. .env Files (Development Only)

**Locations**:
- `services/copilotkit-proxy/.env.development` (version controlled)
- `services/copilotkit-proxy/.env.local` (gitignored, optional overrides)

**Purpose**: Local development configuration

**NOT USED in production** - WinSW services use XML environment

---

## LLM Authentication (llm_router)

### How It Works

The `llm_router` module handles LLM authentication **automatically** using cloud identity:

**Development Mode** (`MODE=dev`):
```bash
# One-time setup per developer
az login                                    # For Azure OpenAI
gcloud auth application-default login       # For GCP Vertex AI
aws configure                               # For AWS Bedrock

# That's it! llm_router reads from:
# - ~/.azure/
# - ~/.config/gcloud/
# - ~/.aws/credentials
```

**Production Mode** (`MODE=prod`):
```
Azure VM with User Managed Identity (UMI)
    ↓
llm_router detects Azure IMDS
    ↓
For Azure OpenAI:
  - Gets token from UMI for scope: cognitiveservices.azure.com
    ↓
For GCP Vertex AI:
  - UMI token → Workload Identity Federation → GCP token
    ↓
For AWS Bedrock:
  - UMI token → AssumeRoleWithWebIdentity → Temporary AWS credentials
```

**No API keys needed!** Authentication happens transparently.

### Authentication Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Development (MODE=dev)                   │
├─────────────────────────────────────────────────────────────┤
│ Developer runs: az login / gcloud auth / aws configure      │
│         ↓                                                    │
│ Credentials stored in: ~/.azure, ~/.config/gcloud, ~/.aws   │
│         ↓                                                    │
│ llm_router uses SDK credential chains:                      │
│   - AzureCliCredential                                      │
│   - Application Default Credentials (GCP)                   │
│   - boto3 credential chain (AWS)                            │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    Production (MODE=prod)                    │
├─────────────────────────────────────────────────────────────┤
│ Azure VM with User Managed Identity (UMI)                   │
│         ↓                                                    │
│ llm_router queries Azure IMDS for UMI token                 │
│         ↓                                                    │
│ ┌─────────────┬─────────────┬──────────────┐               │
│ │ Azure       │ GCP         │ AWS          │               │
│ ├─────────────┼─────────────┼──────────────┤               │
│ │ Direct UMI  │ UMI → WIF   │ UMI →        │               │
│ │ token for   │ → GCP       │ AssumeRole   │               │
│ │ Cognitive   │ token       │ → AWS creds  │               │
│ │ Services    │             │              │               │
│ └─────────────┴─────────────┴──────────────┘               │
└─────────────────────────────────────────────────────────────┘
```

---

## Secrets Management

### Vault Structure

**Path**: `secret/data/assistant`

**Contents**:
```json
{
  "DB_USERNAME": "DrMigrate_AgentsReader",
  "DB_PASSWORD": "secure_random_password_here",
  "DB_SERVER": "localhost\\SQLEXPRESS",
  "DB_NAME": "Assessments",
  "DB_CONNECTION_STRING": "Server=localhost\\SQLEXPRESS;Database=Assessments;User Id=DrMigrate_AgentsReader;Password=...;TrustServerCertificate=True"
}
```

### How Secrets are Loaded

**During Bootstrap** (`SetupDrMigrate.ps1`):

1. **Vault is unsealed** (if needed)
2. **secrets-loader.ps1 runs**:
   ```powershell
   cd C:\DrMigrate\Assistant\config
   .\secrets-loader.ps1
   ```
3. **Secrets loaded from Vault** → Machine environment variables:
   - `DB_USERNAME`
   - `DB_PASSWORD`
   - `DB_CONNECTION_STRING` (optional)
4. **Services inherit** Machine environment when they start

**Service Access**:
```python
# Python (agents)
import os
db_user = os.environ['DB_USERNAME']
db_pass = os.environ['DB_PASSWORD']
```

```typescript
// Node.js (CopilotKit - if needed)
const dbUser = process.env.DB_USERNAME;
const dbPass = process.env.DB_PASSWORD;
```

---

## Environment Comparison

### Development Environment

| Component | Configuration | Secrets | LLM Auth |
|-----------|---------------|---------|----------|
| **Python Agents** | `config.toml` (MODE=dev) | Environment vars | `az login` / `gcloud auth` / `aws configure` |
| **CopilotKit** | `.env.development` | Not needed | N/A |
| **Database** | `config.toml` (DB_HOST, etc.) | Environment vars (DB_USERNAME, DB_PASSWORD) | N/A |

**Developer Setup**:
```bash
# 1. Install CLIs
winget install Microsoft.Azure.CLI
winget install Google.CloudSDK
winget install Amazon.AWSCLI

# 2. Authenticate
az login
gcloud auth application-default login
aws configure

# 3. Get DB credentials from team, set as environment variables or add to local Vault

# 4. Run
cd Assistant
uv sync
uv run python -m agents.server
```

### Production Environment

| Component | Configuration | Secrets | LLM Auth |
|-----------|---------------|---------|----------|
| **Python Agents** | `config.toml` (MODE=prod) + WinSW XML | Vault → Machine env | Azure UMI (automatic) |
| **CopilotKit** | WinSW XML | Vault → Machine env | N/A |
| **Database** | `config.toml` (DB_HOST, etc.) + WinSW XML | Vault → Machine env | N/A |

**Production Setup** (via Bootstrap):
```powershell
# Run bootstrap - handles everything
cd C:\DrMigrate\Bootstrap\Scripts
.\SetupDrMigrate.ps1

# What it does:
# 1. Installs Vault, unseals it
# 2. Stores DB credentials in Vault (via New-AssistantDatabaseUser.ps1)
# 3. Runs secrets-loader.ps1 → Sets Machine environment
# 4. Installs services with WinSW (reads XML config)
# 5. Starts services (inherit Machine environment + XML config)
```

---

## Configuration Precedence

### Python Agents

1. **Environment variables** (highest priority)
2. **config.toml**
3. **Hard-coded defaults** (lowest priority)

Example:
```python
# If DB_USERNAME is set in environment, it overrides config.toml
db_user = os.getenv('DB_USERNAME') or config['db']['DB_USER']
```

### CopilotKit Proxy

1. **Environment variables from WinSW XML** (highest priority)
2. **config.ts defaults** (lowest priority)

In development with .env files:
1. **.env.local** (gitignored, highest priority)
2. **.env.development** (version controlled)
3. **config.ts defaults**

---

## Troubleshooting

### LLM Authentication Issues

**Error**: `Authentication failed for Azure OpenAI`

**Development**:
```bash
# Re-authenticate
az login
az account show  # Verify correct subscription
```

**Production**:
```bash
# Verify UMI is attached to VM
az vm identity show --name <vm-name> --resource-group <rg>

# Check UMI has Cognitive Services User role
az role assignment list --assignee <umi-client-id>
```

### Database Connection Issues

**Error**: `Login failed for user 'DrMigrate_AgentsReader'`

**Check environment variables**:
```powershell
# PowerShell
[Environment]::GetEnvironmentVariable('DB_USERNAME', 'Machine')
[Environment]::GetEnvironmentVariable('DB_PASSWORD', 'Machine')
```

**Reload secrets** (if changed in Vault):
```powershell
cd C:\DrMigrate\Assistant\config
.\secrets-loader.ps1

# Restart services
Restart-Service DrMigrate-AgentsServer
Restart-Service DrMigrate-CopilotKitProxy
```

### CORS Issues

**Error**: `Blocked by CORS policy`

**Check configuration**:
```powershell
# View current CORS setting
Get-Content C:\DrMigrate\Assistant\services\copilotkit-proxy.xml | Select-String CORS_ORIGIN

# Expected values:
# Production: *.drmigrate.com
# Development: *.drmigrate.com.au or *
```

**Update if needed**:
```xml
<!-- copilotkit-proxy.xml -->
<env name="CORS_ORIGIN" value="*.drmigrate.com"/>
```

Then restart service:
```powershell
Restart-Service DrMigrate-CopilotKitProxy
```

---

## Best Practices

### ✅ DO

- Store all secrets in Vault
- Use identity-based auth (az login, UMI) for LLMs
- Version control configuration files (config.toml, .env.development)
- Document environment-specific settings
- Use separate configs for dev/prod

### ❌ DON'T

- Commit secrets to version control (.env.local, config.toml with passwords)
- Hardcode API keys in code
- Use wildcards (*) for CORS in production
- Store configuration in Vault (only secrets belong there)
- Share credentials via email/chat

---

## Migration from Old Architecture

If you're migrating from the old approach with API keys in Vault:

1. **Remove old secrets from Vault**:
   ```powershell
   # These are no longer needed:
   vault kv delete secret/data/assistant/AZURE_OPENAI_API_KEY
   vault kv delete secret/data/assistant/AWS_ACCESS_KEY_ID
   vault kv delete secret/data/assistant/AWS_SECRET_ACCESS_KEY
   ```

2. **Keep only DB credentials**:
   ```powershell
   vault kv put secret/data/assistant \
     DB_USERNAME="DrMigrate_AgentsReader" \
     DB_PASSWORD="your_secure_password"
   ```

3. **Set up CLI authentication**:
   ```bash
   az login
   gcloud auth application-default login
   aws configure
   ```

4. **Restart services**:
   ```powershell
   Restart-Service DrMigrate-AgentsServer
   Restart-Service DrMigrate-CopilotKitProxy
   ```

Services will automatically use identity-based auth instead of API keys.

---

## Summary

**The Golden Rules**:

1. **Configuration** = Non-sensitive settings → Version control
2. **Secrets** = Database credentials ONLY → Vault
3. **LLM Auth** = Identity (CLI/UMI) → No API keys needed!

This architecture is:
- ✅ More secure (identity-based auth, minimal secrets)
- ✅ Easier to maintain (fewer secrets to rotate)
- ✅ Simpler to onboard (just `az login`)
- ✅ Production-ready (Azure UMI, auto-rotating credentials)
