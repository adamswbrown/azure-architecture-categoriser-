# Dr.Migrate Assistant - Production Deployment Guide

## Overview

This guide covers the production deployment of Dr.Migrate Assistant services, including the Agents Server and CopilotKit Proxy, using Windows Services with WinSW.

## Architecture

### Services

The Assistant consists of three main components:

1. **Agents Server** (Python/Uvicorn)
   - Port: 8002
   - Framework: Starlette (ASGI) + Pydantic AI
   - Entry Point: `uv run agents`
   - Service Name: `DrMigrate-AgentsServer`

2. **CopilotKit Proxy** (Node.js/Express)
   - Port: 8001
   - Framework: Express.js + TypeScript
   - Entry Point: `node dist/server.js`
   - Service Name: `DrMigrate-CopilotKitProxy`

3. **IIS Reverse Proxy**
   - Endpoint: `/chat/*`
   - Proxies to both services above
   - Handles authentication and routing

### Data Flow

```
User Browser
    ↓
IIS (/chat)
    ↓
    ├──→ /chat/copilotkit-api/* → CopilotKit Proxy (8001)
    │                                    ↓
    └──→ /chat/backend/* ────────────→ Agents Server (8000)
```

## Automated Deployment (Bootstrap)

The Assistant services are automatically deployed during the Dr.Migrate bootstrap process.

### Bootstrap Process

When `SetupDrMigrate.ps1` runs, it executes the following steps:

1. **Install UV** - Python package manager
2. **Install Assistant Dependencies** - `Install-AssistantDependencies`
   - Runs `uv sync` to install Python packages
   - Runs `pnpm install` for CopilotKit server
   - Builds CopilotKit TypeScript server (`pnpm run build`)
3. **Configure Services** - `New-AssistantConfiguration`
   - Loads secrets from HashiCorp Vault
   - Sets environment variables
   - Creates `config.toml` from template
   - Creates `.env.production` for CopilotKit
4. **Install Windows Services** - `Install-AssistantServices`
   - Downloads WinSW.NET461.exe
   - Installs services using XML configurations
   - Starts services and verifies health

### Bootstrap Script Location

- **Main Script**: `Bootstrap/Scripts/SetupDrMigrate.ps1`
- **Functions**: Lines 646-910
- **Execution**: Lines 1599-1606

## Manual Deployment

If you need to deploy or redeploy the services manually, follow these steps:

### Prerequisites

1. **System Requirements**
   - Windows Server 2019 or later
   - PowerShell 7.4.5+
   - IIS with URL Rewrite and ARR modules
   - Python 3.9.6+ (installed via bootstrap)
   - Node.js 24.11.1+ (installed via bootstrap)
   - UV 0.9.13+ (installed via bootstrap)
   - HashiCorp Vault (optional, for secret management)

2. **Network Requirements**
   - Ports 8000 and 8001 must be available
   - SQL Server accessible (for virtual database)
   - Internet access for LLM providers (Azure/AWS/GCP)

### Installation Steps

#### 1. Install Dependencies

```powershell
cd C:\DrMigrate\Assistant

# Install Python dependencies
C:\Program Files\uv\uv.exe sync

# Install and build CopilotKit server
cd services\copilotkit-proxy
pnpm install --prod
pnpm run build
cd ..\..
```

#### 2. Configure Services

**Option A: Using Vault (Production)**

```powershell
cd C:\DrMigrate\Assistant\config
.\secrets-loader.ps1 -Scope Machine
```

This will:
- Fetch database credentials from Vault at `secret/data/assistant`
- Set machine-level environment variables (DB_USERNAME, DB_PASSWORD)
- Services will inherit these variables and use XML config for other settings

**Option B: Manual Configuration (Development)**

1. Copy configuration template:
   ```powershell
   Copy-Item config.example.toml config.toml
   ```

2. Edit `config.toml` with your settings:
   ```toml
   [agents]
   MODE = "prod"
   CLOUD_PROVIDER = "AZURE"
   LLM_PROVIDER = "openai"
   DEFAULT_TIER = "heavy"

   [db]
   DB_HOST = "localhost\\SQLEXPRESS"
   DB_NAME = "Assessments"
   # DB_USERNAME and DB_PASSWORD from environment (Vault)
   ```

3. Set database credentials as environment variables:
   ```powershell
   [Environment]::SetEnvironmentVariable('DB_USERNAME', 'DrMigrate_AgentsReader', 'Machine')
   [Environment]::SetEnvironmentVariable('DB_PASSWORD', 'your_password', 'Machine')
   ```

4. CopilotKit configuration is set in `services/copilotkit-proxy.xml` (no .env.production needed)

#### 3. Install Windows Services

```powershell
cd C:\DrMigrate\Assistant\services

# Install both services
.\install-services.ps1

# Or install without auto-start
.\install-services.ps1 -SkipStart
```

#### 4. Verify Installation

```powershell
# Check service status
.\check-health.ps1

# Or detailed health check
.\check-health.ps1 -Detailed

# Continuous monitoring
.\check-health.ps1 -ContinuousMonitor -MonitorInterval 60
```

Expected output:
```
=== Dr.Migrate Assistant Health Report ===
✓ Agents Server
  Service: RUNNING
  HTTP: HTTP 200 in 45ms

✓ CopilotKit Proxy
  Service: RUNNING
  HTTP: HTTP 200 in 12ms

=== Summary ===
Services: 2/2 healthy
```

## Service Management

### Common Operations

#### Restart Services

```powershell
cd C:\DrMigrate\Assistant\services

# Restart both services
.\restart-services.ps1

# Restart specific service
.\restart-services.ps1 -ServiceName agents
.\restart-services.ps1 -ServiceName copilotkit

# Restart without health check
.\restart-services.ps1 -NoHealthCheck
```

#### Start/Stop Services

```powershell
# Using Windows Services
Start-Service DrMigrate-AgentsServer
Start-Service DrMigrate-CopilotKitProxy

Stop-Service DrMigrate-CopilotKitProxy
Stop-Service DrMigrate-AgentsServer  # Stop in reverse order

# Or using PowerShell cmdlets
Get-Service DrMigrate-*
```

#### View Logs

**WinSW Service Logs** (service wrapper stdout/stderr):
```powershell
# Agents Server logs
Get-Content C:\DrMigrate\Assistant\services\agents\logs\DrMigrate-AgentsServer.out.log -Tail 50 -Wait
Get-Content C:\DrMigrate\Assistant\services\agents\logs\DrMigrate-AgentsServer.err.log -Tail 50 -Wait

# CopilotKit Proxy logs
Get-Content C:\DrMigrate\Assistant\services\copilotkit-proxy\logs\DrMigrate-CopilotKitProxy.out.log -Tail 50 -Wait
Get-Content C:\DrMigrate\Assistant\services\copilotkit-proxy\logs\DrMigrate-CopilotKitProxy.err.log -Tail 50 -Wait
```

**Application Logs** (if services generate additional log files):
```powershell
# Agents Server logs
Get-Content C:\DrMigrate\Assistant\services\agents\logs\*.log -Tail 50 -Wait

# CopilotKit Proxy logs
Get-Content C:\DrMigrate\Assistant\services\copilotkit-proxy\logs\*.log -Tail 50 -Wait
```

#### Uninstall Services

```powershell
cd C:\DrMigrate\Assistant\infrastructure\winsw

# Uninstall with prompts
.\uninstall-services.ps1

# Uninstall without prompts
.\uninstall-services.ps1 -Force

# Preserve logs during uninstall
.\uninstall-services.ps1 -Force -KeepLogs
```

### Service Configuration

Service configurations are defined in XML files:

- **Agents Server**: `Assistant/services/agents-server.xml`
- **CopilotKit Proxy**: `Assistant/services/copilotkit-proxy.xml`

#### Key Configuration Options

**Restart Policy** (both services):
```xml
<onfailure action="restart" delay="60 sec"/>
<onfailure action="restart" delay="120 sec"/>
<onfailure action="restart" delay="240 sec"/>
<resetfailure>1 hour</resetfailure>
```

**Log Rotation** (both services):
```xml
<log mode="roll-by-size">
  <sizeThreshold>10240</sizeThreshold>  <!-- 10 MB -->
  <keepFiles>8</keepFiles>
</log>
```

**Environment Variables** (agents-server.xml):
```xml
<env name="MODE" value="prod"/>
<env name="PYTHONUNBUFFERED" value="1"/>
<env name="UV_SYSTEM_PYTHON" value="1"/>
```

**Environment Variables** (copilotkit-proxy.xml):
```xml
<env name="NODE_ENV" value="production"/>
<env name="PORT" value="8001"/>
<env name="PYTHON_BACKEND_URL" value="http://localhost:8002/api"/>
```

## Secret Management

### Vault Integration

The Assistant uses HashiCorp Vault for **database credentials ONLY**.

**Important**: LLM authentication uses Azure User Managed Identity (UMI) - **NO API KEYS NEEDED!**

#### Required Secrets (Database Credentials Only)

Create secrets at `secret/data/assistant` in Vault:

```json
{
  "DB_USERNAME": "DrMigrate_AgentsReader",
  "DB_PASSWORD": "secure_random_password_here"
}
```

**Optional** (can also be in config.toml):
```json
{
  "DB_USERNAME": "DrMigrate_AgentsReader",
  "DB_PASSWORD": "secure_random_password_here",
  "DB_SERVER": "localhost\\SQLEXPRESS",
  "DB_NAME": "Assessments",
  "DB_CONNECTION_STRING": "Server=localhost\\SQLEXPRESS;Database=Assessments;User Id=DrMigrate_AgentsReader;Password=...;TrustServerCertificate=True"
}
```

#### What NOT to Store in Vault

❌ **These are configuration (NOT secrets)** - put in `config.toml` instead:
- `MODE` - Operating mode (dev/prod)
- `CLOUD_PROVIDER` - Cloud selection (AZURE/AWS/GCP)
- `LLM_PROVIDER` - LLM provider (openai/claude/gemini)
- `DEFAULT_TIER` - Default model tier
- `PORT`, `CORS_ORIGIN`, `LOG_LEVEL` - Service configuration

❌ **These are NOT needed** - llm_router uses identity-based auth:
- `AZURE_OPENAI_API_KEY` - Uses Azure UMI instead
- `AZURE_OPENAI_ENDPOINT` - In endpoints.json instead
- `AWS_ACCESS_KEY_ID` - Uses AssumeRoleWithWebIdentity instead
- `AWS_SECRET_ACCESS_KEY` - Uses AssumeRoleWithWebIdentity instead
- `GCP_PROJECT_ID` - In config.toml instead

#### LLM Authentication (Identity-Based)

The `llm_router` module uses **Azure User Managed Identity** for all LLM providers:

**For Azure OpenAI**:
```
VM UMI → Cognitive Services token → Azure OpenAI
```

**For GCP Vertex AI**:
```
VM UMI → Workload Identity Federation → GCP token → Vertex AI
```

**For AWS Bedrock**:
```
VM UMI → AssumeRoleWithWebIdentity → Temporary AWS credentials → Bedrock
```

**Setup Requirements**:
1. Attach User Managed Identity to Azure VM
2. Grant appropriate roles:
   - Azure: `Cognitive Services User` role
   - GCP: Configure Workload Identity Federation pool
   - AWS: Configure federated identity provider + IAM role

**No API keys to rotate or manage!**

#### Loading Secrets

```powershell
# Load secrets and set machine-level environment variables
.\config\secrets-loader.ps1 -Scope Machine

# Load from custom Vault path
.\config\secrets-loader.ps1 -VaultPath "secret/data/assistant/production"

# Skip validation (for testing)
.\config\secrets-loader.ps1 -SkipValidation
```

#### Updating Secrets

1. Update secrets in Vault:
   ```powershell
   vault kv put secret/assistant MODE=prod CLOUD_PROVIDER=AZURE ...
   ```

2. Reload secrets:
   ```powershell
   .\config\secrets-loader.ps1 -Scope Machine
   ```

3. Restart services:
   ```powershell
   .\infrastructure\winsw\restart-services.ps1
   ```

## IIS Configuration

### Reverse Proxy Setup

The IIS reverse proxy is configured automatically during bootstrap.

**Configuration File**: `Assistant/iis/web-auth-static.config`

#### Key Routes

1. **CopilotKit API**:
   ```
   /chat/copilotkit-api/* → http://localhost:8001/*
   ```

2. **Agents Backend**:
   ```
   /chat/backend/* → http://localhost:8002/*
   /chat/data* → http://localhost:8002/data
   X-Accel-Buffering: no  (critical for streaming)
   ```

#### Authentication

Requests require `.AspNet.Cookies` authentication, except:
- Static assets: `_next/*`, `favicon.ico`
- CopilotKit API: `copilotkit-api/*`

### Manual IIS Configuration

If you need to reconfigure IIS manually:

```powershell
cd C:\DrMigrate\Bootstrap\Scripts

# Run the IIS setup function
. .\SetupDrMigrate.ps1
New-ChatReverseProxyApplication
```

## Troubleshooting

### Service Won't Start

1. **Check logs**:
   ```powershell
   Get-Content C:\DrMigrate\Assistant\services\agents\logs\DrMigrate-AgentsServer.err.log
   ```

2. **Verify dependencies**:
   ```powershell
   # UV installed?
   Test-Path "C:\Program Files\uv\uv.exe"

   # Python packages installed?
   C:\Program Files\uv\uv.exe pip list

   # Node modules built?
   Test-Path C:\DrMigrate\Assistant\services\copilotkit-proxy\dist\server.js
   ```

3. **Test manual startup**:
   ```powershell
   # Agents Server
   cd C:\DrMigrate\Assistant\services\agents
   C:\Program Files\uv\uv.exe run agents

   # CopilotKit Proxy
   cd C:\DrMigrate\Assistant\services\copilotkit-proxy
   node dist\server.js
   ```

### Health Check Fails

1. **Check port availability**:
   ```powershell
   Get-NetTCPConnection -LocalPort 8000,8001 -State Listen
   ```

2. **Test endpoints directly**:
   ```powershell
   Invoke-WebRequest http://localhost:8002/health
   Invoke-WebRequest http://localhost:8001/health
   ```

3. **Check firewall**:
   ```powershell
   Get-NetFirewallRule | Where-Object {$_.DisplayName -like "*8000*" -or $_.DisplayName -like "*8001*"}
   ```

### Database Connection Errors

1. **Verify SQL Server is running**:
   ```powershell
   Get-Service MSSQL$SQLEXPRESS
   ```

2. **Test connection string**:
   ```powershell
   $connectionString = "Server=localhost\SQLEXPRESS;Database=DrMigrate;Integrated Security=True"
   $connection = New-Object System.Data.SqlClient.SqlConnection($connectionString)
   $connection.Open()
   $connection.State  # Should return "Open"
   $connection.Close()
   ```

3. **Check config.toml**:
   ```powershell
   Select-String -Path C:\DrMigrate\Assistant\config.toml -Pattern "connection_string"
   ```

### LLM Provider Errors

1. **Verify authentication is configured** (identity-based, NO API keys):
   ```powershell
   # Development: Check CLI authentication
   az account show                          # For Azure OpenAI
   gcloud auth application-default print-access-token  # For GCP Vertex AI
   aws sts get-caller-identity              # For AWS Bedrock

   # Production: Verify Azure UMI is attached to VM
   curl -H "Metadata:true" "http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://cognitiveservices.azure.com/"
   ```

2. **Test LLM connectivity**:
   ```powershell
   # Check endpoints.json
   Get-Content C:\DrMigrate\Assistant\endpoints.json | ConvertFrom-Json
   ```

3. **Verify UMI permissions** (Production):
   ```powershell
   # Check UMI has required role assignments:
   # - Cognitive Services User (Azure OpenAI)
   # - Workload Identity Federation configured (GCP)
   # - AssumeRole trust relationship (AWS)
   az role assignment list --assignee <umi-client-id>
   ```

## Performance Tuning

### Resource Allocation

**Agents Server**:
- **CPU**: 2-4 cores recommended
- **Memory**: 2-4 GB minimum (depends on LLM tier)
- **Disk I/O**: Fast SSD for DuckDB virtual database

**CopilotKit Proxy**:
- **CPU**: 1-2 cores sufficient
- **Memory**: 512 MB - 1 GB
- **Network**: Low latency to Agents Server

### Optimization Tips

1. **Use Heavy Tier for Production**:
   ```toml
   DEFAULT_TIER = "heavy"  # claude-sonnet-4-5
   ```

2. **Enable Connection Pooling** (SQL Server):
   ```toml
   connection_string = "...;Max Pool Size=100;Min Pool Size=10"
   ```

3. **Adjust Log Levels**:
   ```env
   LOG_LEVEL=info  # or "warn" for production
   ```

4. **Monitor Memory Usage**:
   ```powershell
   Get-Process -Name uv,node | Select-Object Name, CPU, WorkingSet
   ```

## Security Best Practices

1. **Use Vault for Database Secrets**: Store only DB credentials in Vault (DB_USERNAME, DB_PASSWORD)
   - LLM authentication uses identity-based auth (Azure UMI, CLI credentials)
   - NO API keys needed for LLM providers
2. **Enable HTTPS Only**: Configure IIS with valid SSL certificates
3. **Restrict CORS**: Set specific origins in `services/copilotkit-proxy.xml`
   ```xml
   <env name="CORS_ORIGIN" value="*.drmigrate.com"/>
   ```
4. **Run with Least Privilege**: Use dedicated service account (not SYSTEM)
   - Database user should have READ-ONLY access to copilots schema
   - Azure UMI should have minimal role assignments
5. **Enable Audit Logging**: Monitor access to sensitive endpoints
6. **Regular Updates**: Keep dependencies current with `uv sync` and `pnpm update`

## Monitoring

### Health Checks

**Automated Monitoring**:
```powershell
# Create scheduled task for health monitoring
$action = New-ScheduledTaskAction -Execute "pwsh.exe" -Argument "-File C:\DrMigrate\Assistant\infrastructure\winsw\check-health.ps1 -Json"
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName "DrMigrate-HealthCheck" -Action $action -Trigger $trigger
```

**Metrics to Monitor**:
- Service uptime
- Response times (< 100ms for health checks)
- Error rates in logs
- Memory/CPU usage
- Database query performance

### Alerting

Configure alerts for:
- Service stopped unexpectedly
- Health check failures (> 3 consecutive)
- High error rate (> 5% of requests)
- Memory usage > 80%
- Disk space < 10% free

## Backup and Recovery

### Configuration Backup

```powershell
# Backup configuration files
$backupPath = "C:\DrMigrate\Backups\Assistant_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
New-Item -ItemType Directory -Path $backupPath

Copy-Item C:\DrMigrate\Assistant\services\agents\config.toml $backupPath
Copy-Item C:\DrMigrate\Assistant\services\copilotkit-proxy\.env.production $backupPath
Copy-Item C:\DrMigrate\Assistant\infrastructure\winsw\*.xml $backupPath
```

### Disaster Recovery

1. **Stop services**:
   ```powershell
   Stop-Service DrMigrate-*
   ```

2. **Restore configuration**:
   ```powershell
   Copy-Item $backupPath\* C:\DrMigrate\Assistant\ -Force
   ```

3. **Reinstall dependencies**:
   ```powershell
   .\infrastructure\winsw\uninstall-services.ps1 -Force
   .\infrastructure\winsw\install-services.ps1
   ```

4. **Verify health**:
   ```powershell
   .\infrastructure\winsw\check-health.ps1 -Detailed
   ```

## Support

For issues or questions:
- **Documentation**: `Assistant/docs/`
- **Logs**: `Assistant/services/agents/logs/` and `Assistant/services/copilotkit-proxy/logs/`
- **Health Check**: `.\infrastructure\winsw\check-health.ps1`
- **Service Status**: `Get-Service DrMigrate-*`

## Appendix

### File Structure

```
C:\DrMigrate\Assistant\
├── services/
│   ├── agents/                # Python agents server
│   │   ├── agents/            # Agent implementations
│   │   ├── server.py          # Main ASGI server
│   │   ├── config.toml        # Configuration
│   │   ├── pyproject.toml     # Python dependencies
│   │   └── logs/              # Application logs
│   └── copilotkit-proxy/      # Node.js proxy
│       ├── dist/              # Built TypeScript
│       ├── src/server.ts      # Source code
│       ├── .env.production    # Production config
│       └── logs/              # Application logs
├── infrastructure/
│   ├── winsw/                 # Windows Service management
│   │   ├── DrMigrate-AgentsServer.xml
│   │   ├── DrMigrate-CopilotKitProxy.xml
│   │   ├── install-services.ps1
│   │   ├── uninstall-services.ps1
│   │   ├── restart-services.ps1
│   │   └── check-health.ps1
│   ├── scripts/               # Setup scripts
│   ├── config/                # Configuration helpers
│   └── iis/                   # IIS configs
├── docs/                      # Documentation
│   └── secrets-loader.ps1     # Vault integration
├── iis/                       # IIS configuration
│   └── web-auth-static.config # Production IIS config
├── logs/                      # Application logs
├── config.toml                # Main configuration
└── README.md                  # User documentation
```

### Default Ports

- **Agents Server**: 8000
- **CopilotKit Proxy**: 8001
- **IIS (HTTPS)**: 443
- **Vault**: 8200

### Service Dependencies

```
MSSQLSERVER (SQL Server)
    ↓
DrMigrate-AgentsServer
    ↓
DrMigrate-CopilotKitProxy
```

Stop services in reverse order to avoid connection errors.
