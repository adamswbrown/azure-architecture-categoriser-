# Dr.Migrate Assistant Infrastructure

This directory contains the infrastructure components for deploying and managing the Dr.Migrate Assistant services.

## Quick Start

```powershell
# Full installation (requires Administrator privileges)
cd C:\DrMigrate\Assistant\infrastructure\scripts
.\SetupAssistant.ps1

# Quick patch (update dependencies only)
.\SetupAssistant.ps1 -Patch
```

## Directory Structure

```
infrastructure/
├── iis/             - IIS reverse proxy configuration
│   ├── README.md
│   └── web.config files
├── scripts/         - PowerShell installation scripts
│   ├── SetupAssistant.ps1 (Main orchestrator)
│   ├── Install-*.ps1 (Component installers)
│   ├── New-*.ps1 (Resource creators)
│   └── Reset-Assistant.ps1 (Cleanup script)
└── winsw/           - Windows Service wrapper configurations
    ├── DrMigrate-AgentsServer.xml
    ├── DrMigrate-CopilotKitProxy.xml
    └── service management scripts
```

---

## SetupAssistant.ps1 - Main Setup Orchestrator

The primary installation script that automates the complete setup of Dr.Migrate Assistant services.

### Prerequisites

- **Operating System**: Windows Server 2016+ or Windows 10/11
- **PowerShell**: Version 7.0 or higher
- **Privileges**: Administrator rights required
- **Dependencies**:
  - Internet access (for downloading components) OR
  - Azure Storage access (for cached dependencies)
  - HashiCorp Vault instance (for secrets management)
  - SQL Server instance (for application database)
  - PostgreSQL 17 instance (for data storage)

### Usage

#### Standard Installation
```powershell
.\SetupAssistant.ps1
```

#### Production Installation with Cached Dependencies
```powershell
.\SetupAssistant.ps1 -Environment Production -UseCachedDependencies
```

#### Patch Mode (Quick Update)
```powershell
.\SetupAssistant.ps1 -Patch
```

#### Custom Installation Path
```powershell
.\SetupAssistant.ps1 -AssistantPath "D:\DrMigrate\Assistant"
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `AssistantPath` | String | `C:\DrMigrate\Assistant` | Installation directory path |
| `VaultAddress` | String | `https://localhost:8200` | HashiCorp Vault server address |
| `VaultPath` | String | `secret/data/assistant` | Vault secret path |
| `Environment` | String | `Development` | Environment (`Development` or `Production`) |
| `UseCachedDependencies` | Switch | `$false` | Use pre-built dependency caches from Azure Storage |
| `CacheVersion` | String | `latest` | Version of cached dependencies to use |
| `Patch` | Switch | `$false` | Enable patch mode (quick dependency update) |

### Setup Flow

The installation process consists of **9 steps** in Setup Mode:

#### **Step 1: Install IIS Modules**
- Downloads and installs URL Rewrite module
- Downloads and installs Application Request Routing (ARR) module
- Required for IIS reverse proxy functionality
- **Script**: `Install-IISModules.ps1`

#### **Step 2: Create IIS Reverse Proxy**
- Creates IIS application at `/chat` endpoint
- Configures reverse proxy to CopilotKit service (port 4000)
- Sets up URL rewrite rules
- **Script**: `New-IISReverseProxy.ps1`

#### **Step 3: Install UV Package Manager**
- Downloads and installs UV (ultra-fast Python package manager)
- Installed to `C:\Program Files\uv\`
- Used for Python dependency management
- **Script**: `Install-UVPackageManager.ps1`

#### **Step 4: Install Node.js Runtime**
- Downloads and installs Node.js (v18+)
- Required for CopilotKit proxy service
- **Script**: `Install-NodeJS.ps1`

#### **Step 5: Install Dependencies**
- Installs Python dependencies via UV (`uv sync`)
- Installs Node.js dependencies via pnpm
- Builds CopilotKit TypeScript server
- Supports two modes:
  - **Standard**: Downloads from PyPI/npm (15-25 min)
  - **Cached**: Uses pre-built caches from Azure Storage (2-3 min)
- **Script**: `Install-AssistantDependencies.ps1`

#### **Step 6: Configure Services**
- Migrates legacy environment variables to Vault (via AltraVault)
- Creates `config.toml` from template
- Configures environment variables for WinSW services
- Secrets are loaded from Vault on service startup
- **Module**: `AltraVault` (external dependency)

#### **Step 7: Create SQL Server Database User**
- Creates dedicated SQL Server login and database user
- Grants minimal required permissions for Assistant agents
- Stores credentials in Vault at `secret/data/credentials/assistant/database`
- **Script**: `New-AssistantDatabaseUser.ps1`
- **Critical**: Setup fails if this step fails

#### **Step 7a: Create PostgreSQL Database User**
- Creates read-only PostgreSQL user (`drmigrate_agentsreader_pg`)
- Grants SELECT permissions on all schemas and tables
- Stores credentials in Vault at `secret/data/credentials/assistant/postgresql`
- **Script**: `New-AssistantPgDatabaseUser.ps1`
- **Critical**: Setup fails if this step fails

#### **Step 7b: FDW Setup (Handled by PostgreSQL Deployment)**
- FDW installation/configuration is handled by AltraPostgres during PostgreSQL deployment
- Assistant setup does not install FDW

#### **Step 9: Install Windows Services**
- Installs `DrMigrate-AgentsServer` service (Python agents)
- Installs `DrMigrate-CopilotKitProxy` service (CopilotKit proxy)
- Configures services using WinSW
- Starts services and verifies health
- **Script**: `infrastructure/winsw/install-services.ps1`

### Modes

#### Setup Mode (Default)
Full 9-step installation process. Use for initial setup or complete reinstallation.

**Duration**: 15-25 minutes (standard) or 2-3 minutes (cached)

**What it does**:
- Installs all prerequisites (IIS, UV, Node.js)
- Configures infrastructure components
- Creates database users (FDW handled by PostgreSQL deployment)
- Installs and starts Windows Services

#### Patch Mode (`-Patch`)
Quick dependency update without reconfiguring infrastructure.

**Duration**: 2-5 minutes

**What it does**:
1. Stops Windows Services
2. Updates Python and Node.js dependencies
3. Restarts Windows Services

**What it skips**:
- IIS module installation
- UV and Node.js installation
- Configuration and database setup

**When to use**: For deploying code updates or dependency upgrades without changing infrastructure.

### Error Handling

The script tracks errors and warnings throughout the installation process:

- **Exit Code 0**: Complete success (no errors, no warnings)
- **Exit Code 1**: Fatal error (setup failed, cannot continue)
- **Exit Code 2**: Completed with warnings (non-fatal issues)

Critical steps (Steps 7, 7a, 9) will fail the entire setup if they encounter errors.

---

## Supporting Scripts

### Installation Scripts

#### `Install-IISModules.ps1`
Downloads and installs IIS URL Rewrite and ARR modules from public Dr.Migrate Azure Storage.

**Usage:**
```powershell
.\Install-IISModules.ps1
```

#### `Install-UVPackageManager.ps1`
Downloads and installs UV Python package manager.

**Usage:**
```powershell
.\Install-UVPackageManager.ps1
```

#### `Install-NodeJS.ps1`
Downloads and installs Node.js runtime (v18+).

**Usage:**
```powershell
.\Install-NodeJS.ps1
```

#### `Install-AssistantDependencies.ps1`
Installs Python and Node.js dependencies for Assistant services.

**Usage:**
```powershell
# Standard installation (PyPI/npm)
.\Install-AssistantDependencies.ps1

# Cached installation (Azure Storage)
.\Install-AssistantDependencies.ps1 -UseCachedDependencies
```

**Parameters:**
- `-AssistantPath`: Path to Assistant directory
- `-Environment`: Development or Production
- `-UseCachedDependencies`: Use pre-built dependency caches
- `-CacheVersion`: Version of cached dependencies to use


### Resource Creation Scripts

#### `New-IISReverseProxy.ps1`
Creates IIS reverse proxy application for CopilotKit.

**Usage:**
```powershell
.\New-IISReverseProxy.ps1
```

**What it creates:**
- IIS Application: `/chat` under Default Web Site
- Reverse proxy to `http://localhost:4000`
- URL rewrite rules for WebSocket support

#### `New-AssistantDatabaseUser.ps1`
Creates SQL Server database user for Assistant agents.

**Usage:**
```powershell
.\New-AssistantDatabaseUser.ps1
```

**What it creates:**
- SQL Server login with generated secure password
- Database user with minimal required permissions
- Vault credential at `secret/data/credentials/assistant/database`

**Parameters:**
- `-DatabaseName`: SQL Server database name
- `-Username`: Database username to create
- `-Force`: Force password rotation if user exists

#### `New-AssistantPgDatabaseUser.ps1`
Creates PostgreSQL read-only database user for Assistant agents.

**Usage:**
```powershell
.\New-AssistantPgDatabaseUser.ps1
```

**What it creates:**
- PostgreSQL user: `drmigrate_agentsreader_pg`
- Read-only access to all schemas and tables
- Vault credential at `secret/data/credentials/assistant/postgresql`

**Parameters:**
- `-DatabaseName`: PostgreSQL database name (default: `drmigrate`)
- `-Username`: Database username (default: `drmigrate_agentsreader_pg`)
- `-Force`: Force password rotation

### Utility Scripts

#### `Reset-Assistant.ps1`
Cleanup script for removing Assistant components.

**Usage:**
```powershell
.\Reset-Assistant.ps1
```

⚠️ **Warning**: This script removes Assistant configuration and services. Use with caution.

---

## Windows Services (WinSW)

The Assistant services run as Windows Services using WinSW (Windows Service Wrapper).

### Services

#### DrMigrate-AgentsServer
- **Executable**: UV-managed Python environment
- **Port**: 3001
- **Configuration**: `winsw/DrMigrate-AgentsServer.xml`
- **Log Location**: `C:\DrMigrate\Assistant\logs\agents-server.log`

**Purpose**: Runs the Python-based AI agents that power Dr.Migrate Assistant functionality.

#### DrMigrate-CopilotKitProxy
- **Executable**: Node.js
- **Port**: 4000
- **Configuration**: `winsw/DrMigrate-CopilotKitProxy.xml`
- **Log Location**: `C:\DrMigrate\Assistant\logs\copilotkit-proxy.log`

**Purpose**: Runs the CopilotKit proxy server that interfaces between the frontend and agents.

### Service Management Scripts

Located in `winsw/`:

#### `install-services.ps1`
Installs both Windows Services using WinSW.

```powershell
.\install-services.ps1
```

#### `uninstall-services.ps1`
Stops and uninstalls both Windows Services.

```powershell
.\uninstall-services.ps1
```

#### `restart-services.ps1`
Restarts both Windows Services.

```powershell
.\restart-services.ps1
```

#### `check-health.ps1`
Checks health status of both services.

```powershell
.\check-health.ps1
```

**Output**:
- Service status (Running/Stopped)
- Port availability (3001, 4000)
- Health endpoint responses

---

## IIS Configuration

See [iis/README.md](./iis/README.md) for detailed IIS configuration documentation.

**Quick Reference:**
- **Endpoint**: `/chat` under Default Web Site
- **Target**: `http://localhost:4000` (CopilotKit proxy)
- **Features**: WebSocket support, reverse proxy, URL rewriting

---

## Removal / Uninstall Instructions

To completely remove Dr.Migrate Assistant infrastructure:

### Step 1: Stop and Uninstall Windows Services

```powershell
cd C:\DrMigrate\Assistant\infrastructure\winsw
.\uninstall-services.ps1
```

This will:
- Stop `DrMigrate-AgentsServer` and `DrMigrate-CopilotKitProxy`
- Uninstall both Windows Services
- Remove service binaries

### Step 2: Remove IIS Applications

```powershell
# PowerShell 5.1 (required for IIS: drive)
Import-Module WebAdministration
Remove-WebApplication -Name "chat" -Site "Default Web Site"
```

### Step 3: Foreign Data Wrapper

FDW setup/cleanup is handled by AltraPostgres during PostgreSQL deployment.

### Step 4: Remove Database Users

#### SQL Server
```sql
USE Assessments;
DROP USER IF EXISTS DrMigrate_AgentUser;
USE master;
DROP LOGIN IF EXISTS DrMigrate_AgentUser;
```

#### PostgreSQL
```sql
-- As PostgreSQL superuser
DROP USER IF EXISTS drmigrate_agentsreader_pg;
```

### Step 5: Remove Vault Credentials

```powershell
# Using AltraVault module
Import-Module C:\DrMigrate\AltraVault\AltraVault.psm1
Remove-VaultCredential -Name "assistant/database"
Remove-VaultCredential -Name "assistant/postgresql"
```

### Step 6: Optional - Remove Installed Software

#### Remove UV
```powershell
Remove-Item -Path "C:\Program Files\uv" -Recurse -Force
```

#### Remove Node.js
Use Windows "Add or Remove Programs" to uninstall Node.js.

#### Remove IIS Modules
Use Windows "Add or Remove Programs" to uninstall:
- IIS URL Rewrite Module
- IIS Application Request Routing

### Step 7: Remove Application Files

```powershell
Remove-Item -Path "C:\DrMigrate\Assistant" -Recurse -Force
```

⚠️ **Warning**: This will delete all Assistant files, configurations, and logs.

---

## Troubleshooting

### Common Issues

#### Setup fails at Step 1 (IIS Modules)
- **Cause**: Internet connectivity issues or Azure Storage unavailable
- **Solution**: Check network connectivity and firewall rules

#### Setup fails at Step 7 (Database User)
- **Cause**: SQL Server unavailable or insufficient permissions
- **Solution**:
  - Verify SQL Server is running
  - Ensure current user has `sysadmin` role or equivalent
  - Check Vault is unsealed and accessible

#### Services won't start
- **Cause**: Port conflicts, missing dependencies, or Vault unavailable
- **Solution**:
  - Check ports 3001 and 4000 are available
  - Verify Python and Node.js are installed
  - Ensure Vault is unsealed
  - Check service logs in `C:\DrMigrate\Assistant\logs\`

#### Patch mode fails
- **Cause**: Services not installed or dependency cache unavailable
- **Solution**:
  - Run full setup first: `.\SetupAssistant.ps1`
  - If using cached dependencies, verify Azure Storage connectivity

### Log Locations

- **Setup Logs**: `C:\ProgramData\Dr.Migrate\DrMigrate_<date>.log`
- **AgentsServer Logs**: `C:\DrMigrate\Assistant\logs\agents-server.log`
- **CopilotKit Logs**: `C:\DrMigrate\Assistant\logs\copilotkit-proxy.log`
- **WinSW Logs**: `C:\DrMigrate\Assistant\infrastructure\winsw\logs\`

### Health Checks

```powershell
# Check service status
.\winsw\check-health.ps1

# Check agent server endpoint
curl http://localhost:3001/health

# Check CopilotKit proxy endpoint
curl http://localhost:4000/health
```

---

## Additional Resources

- **Main README**: [../README.md](../README.md)
- **IIS Configuration**: [iis/README.md](./iis/README.md)
- **AltraVault Module**: `C:\DrMigrate\AltraVault\`
- **AltraPostgres Module**: `C:\DrMigrate\AltraPostgres\`

---

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review setup logs
3. Contact Dr.Migrate development team
