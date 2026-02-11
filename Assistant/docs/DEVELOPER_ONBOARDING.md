# Dr.Migrate Assistant - Developer Onboarding

Quick start guide for new developers joining the Dr.Migrate Assistant project.

## Prerequisites

### Required Software

| Software | Version | Installation |
|----------|---------|--------------|
| **Python** | 3.11+ | Installed by UV |
| **Node.js** | 18+ | [Download](https://nodejs.org/) or `winget install OpenJS.NodeJS` |
| **UV** | Latest | Auto-installed by bootstrap or [Download](https://docs.astral.sh/uv/) |
| **SQL Server** | 2019+ | SQL Express or Full |
| **Git** | Latest | `winget install Git.Git` |

### Cloud CLIs (Choose based on LLM provider)

| CLI | When Needed | Installation |
|-----|-------------|--------------|
| **Azure CLI** | For Azure OpenAI | `winget install Microsoft.Azure.CLI` |
| **Google Cloud SDK** | For GCP Vertex AI | `winget install Google.CloudSDK` |
| **AWS CLI** | For AWS Bedrock | `winget install Amazon.AWSCLI` |

---

## Quick Start (5 Minutes)

### Step 1: Clone Repository

```bash
git clone https://github.com/AltraCloud/Dr.Migrate.git
cd Dr.Migrate/Assistant
```

### Step 2: Authenticate with Cloud (Choose One)

**For Azure OpenAI** (most common):
```bash
az login
# Select your subscription when prompted
```

**For GCP Vertex AI**:
```bash
gcloud auth application-default login
```

**For AWS Bedrock**:
```bash
aws configure
# Enter your AWS credentials when prompted
```

**That's it for LLM authentication!** No API keys needed.

### Step 3: Configure Database

**Option A: Use existing database**

Get credentials from team lead, then:

```powershell
# PowerShell - Set environment variables
[Environment]::SetEnvironmentVariable('DB_USERNAME', 'DrMigrate_AgentsReader', 'User')
[Environment]::SetEnvironmentVariable('DB_PASSWORD', 'password_from_team', 'User')
```

**Option B: Create local config.toml**

```bash
# Copy example
cp config.example.toml config.toml

# Edit config.toml and set:
# [db]
# DB_HOST = "localhost\\SQLEXPRESS"
# DB_NAME = "Assessments"
# Note: DB_USERNAME and DB_PASSWORD should still be in environment
```

### Step 4: Install Dependencies

```bash
# Python dependencies (agents server)
cd services/agents
uv sync

# Node.js dependencies (CopilotKit proxy)
cd ../copilotkit-proxy
pnpm install
cd ../..
```

### Step 5: Run Locally

**Terminal 1 - Python Agents Server**:
```bash
cd services/agents
uv run agents
# Runs on http://localhost:8002
```

**Terminal 2 - CopilotKit Proxy** (optional):
```bash
cd services/copilotkit-proxy
pnpm run dev
# Runs on http://localhost:8001
```

**Terminal 3 - Test**:
```bash
# Health check
curl http://localhost:8002/health

# API test
curl http://localhost:8002/api
```

✅ **You're ready to develop!**

---

## Project Structure

```
Assistant/
├── services/                # Service components
│   ├── agents/             # Python agents backend
│   │   ├── agents/         # Agent implementation
│   │   │   ├── server.py            # Main entry point
│   │   │   ├── delegator.py         # Agent routing
│   │   │   ├── personas/            # AI personas (Core, Project Manager, etc.)
│   │   │   ├── deps/                # Dependencies (database, views)
│   │   │   ├── tools/               # Agent tools (DB, charts, etc.)
│   │   │   ├── config/              # LLM router configuration
│   │   │   └── prompts/             # Prompt templates
│   │   ├── frontend/       # Next.js static frontend
│   │   ├── config.toml     # Agent configuration
│   │   └── pyproject.toml  # Python dependencies
│   │
│   └── copilotkit-proxy/   # Node.js proxy for CopilotKit
│       ├── src/
│       │   ├── server.ts            # Express server
│       │   └── config.ts            # Configuration module
│       └── dist/                    # Compiled JavaScript (gitignored)
│
├── infrastructure/          # Deployment infrastructure
│   ├── config/             # Configuration loaders
│   │   └── secrets-loader.ps1      # Vault integration script
│   ├── scripts/            # Setup and utility scripts
│   │   ├── SetupAssistant.ps1      # Main setup orchestrator
│   │   └── New-AssistantDatabaseUser.ps1  # DB user creation
│   ├── winsw/              # WinSW service definitions
│   │   ├── DrMigrate-AgentsServer.xml      # Python service config
│   │   └── DrMigrate-CopilotKitProxy.xml   # Node.js service config
│   └── iis/                # IIS configuration
│       └── web.config      # Reverse proxy rules
│
└── docs/                    # Documentation
    ├── CONFIGURATION_GUIDE.md
    ├── DEVELOPER_ONBOARDING.md  # This file
    └── PRODUCTION_DEPLOYMENT.md
```

---

## Development Workflow

### Making Changes

**Python (agents server)**:
```bash
# Edit code in services/agents/agents/
# Changes auto-reload with uv run

cd services/agents

# Run specific module
uv run python -m agents.personas.core

# Run tests
uv run pytest
```

**TypeScript (CopilotKit proxy)**:
```bash
cd services/copilotkit-proxy

# Development mode (auto-reload)
pnpm run dev

# Type checking
pnpm run type-check

# Build for production
pnpm run build
```

### Adding Dependencies

**Python**:
```bash
cd services/agents

# Add package
uv add package-name

# Add dev dependency
uv add --dev package-name

# Install all
uv sync
```

**Node.js**:
```bash
cd services/copilotkit-proxy

# Add package
pnpm add package-name

# Add dev dependency
pnpm add --save-dev package-name
```

### Testing

**Python agents**:
```bash
cd services/agents

# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_personas.py

# Run with coverage
uv run pytest --cov=agents
```

**CopilotKit proxy**:
```bash
cd services/copilotkit-proxy

# Type check
pnpm run type-check

# Manual testing
curl -X POST http://localhost:8001/copilotkit \
  -H "Content-Type: application/json" \
  -d '{"test": true}'
```

---

## Configuration

### Where Configuration Lives

**NEVER in code or version control**:
- ❌ Database passwords
- ❌ API keys (we don't use them anyway!)
- ❌ Connection strings with credentials

**In version-controlled files**:
- ✅ Server ports, URLs
- ✅ Cloud provider selection (AZURE, AWS, GCP)
- ✅ LLM provider (openai, claude, gemini)
- ✅ Feature flags, log levels

**In environment variables or local config.toml**:
- ✅ Development database credentials
- ✅ Local overrides

### Key Configuration Files

**services/agents/config.toml** (Python agents):
```toml
[agents]
MODE = "dev"                    # Always "dev" for local development
CLOUD_PROVIDER = "AZURE"        # Which cloud you're using
LLM_PROVIDER = "openai"         # Which LLM provider
DEFAULT_TIER = "heavy"          # Default model tier

[server]
PORT = 8002

[db]
DB_HOST = "localhost\\SQLEXPRESS"
DB_NAME = "Assessments"
# DB_USERNAME and DB_PASSWORD from environment
```

**services/copilotkit-proxy/.env.development** (CopilotKit proxy):
```bash
PORT=8001
NODE_ENV=development
PYTHON_BACKEND_URL=http://localhost:8002/api
CORS_ORIGIN=*
LOG_LEVEL=debug
```

---

## Common Tasks

### Switch LLM Provider

Edit `config.toml`:
```toml
[agents]
CLOUD_PROVIDER = "AWS"          # Change cloud
LLM_PROVIDER = "claude"         # Change provider
```

Authenticate:
```bash
aws configure
```

Restart server - that's it!

### Update Database Credentials

```powershell
# Update environment variables
[Environment]::SetEnvironmentVariable('DB_USERNAME', 'new_user', 'User')
[Environment]::SetEnvironmentVariable('DB_PASSWORD', 'new_password', 'User')

# Restart Python server
# Ctrl+C in Terminal 1, then run again:
uv run python -m agents.server
```

### Add New AI Persona

1. Create persona file:
   ```bash
   cp services/agents/agents/personas/core.py services/agents/agents/personas/my_persona.py
   ```

2. Edit the new file:
   - Update the module docstring (used for delegation)
   - Update the agent name
   - Customize the instructions if needed

3. Register in `services/agents/agents/personas/__init__.py`:
   ```python
   from .my_persona import agent as my_persona_agent, __doc__ as my_persona_doc

   class Persona(Enum):
       MY_PERSONA = "my persona"
       # Add to agent and description properties too
   ```

4. Test:
   ```bash
   cd services/agents
   uv run agents --persona="my persona"
   ```

### Debug Issues

**Check logs**:
```bash
# Python server logs (stdout)
cd services/agents
uv run agents

# CopilotKit logs
cd services/copilotkit-proxy
pnpm run dev
```

**Verify configuration**:
```bash
cd services/agents

# Python
uv run python -c "from agents.config import get_config; print(get_config())"

# Database connection
uv run python -c "import os; print(f'User: {os.getenv(\"DB_USERNAME\")}')"
```

**Test LLM authentication**:
```bash
# Azure
az account show

# GCP
gcloud auth application-default print-access-token

# AWS
aws sts get-caller-identity
```

---

## Troubleshooting

### "Authentication failed for LLM"

**Azure**:
```bash
# Re-login
az login
az account show  # Verify subscription
```

**GCP**:
```bash
gcloud auth application-default login
gcloud config list
```

**AWS**:
```bash
aws configure
aws sts get-caller-identity  # Verify credentials
```

### "Cannot connect to database"

Check environment variables:
```powershell
# PowerShell
$env:DB_USERNAME
$env:DB_PASSWORD
```

Verify SQL Server is running:
```powershell
Get-Service MSSQLSERVER
# Or for named instance:
Get-Service 'MSSQL$SQLEXPRESS'
```

Test connection:
```bash
uv run python -c "from agents.deps.virtual_database import VirtualDatabase; vdb = VirtualDatabase(); print('Connected!')"
```

### "Module not found" errors

Reinstall dependencies:
```bash
# Python
uv sync --reinstall

# Node.js
cd copilotkit-server
rm -rf node_modules pnpm-lock.yaml
pnpm install
```

### "Port already in use"

Find and kill process:
```powershell
# Find process on port 8002
netstat -ano | findstr :8002

# Kill process (replace PID)
taskkill /PID <pid> /F
```

Or change port in config:
```toml
[server]
PORT = 8001  # Use different port
```

---

## Getting Help

### Documentation

- **Configuration**: See [CONFIGURATION_GUIDE.md](./CONFIGURATION_GUIDE.md)
- **Production**: See [PRODUCTION_DEPLOYMENT.md](./PRODUCTION_DEPLOYMENT.md)
- **Code docs**: Inline docstrings and type hints

### Resources

- **llm_router docs**: `agents/config/llm_router/MODULE_DESIGN.md`
- **PydanticAI**: https://ai.pydantic.dev/
- **CopilotKit**: https://docs.copilotkit.ai/
- **AG-UI**: https://github.com/pydantic/ag-ui

### Team Support

- Ask in team chat
- Check existing issues/PRs
- Create GitHub issue for bugs

---

## Next Steps

Now that you're set up:

1. **Explore the code**: Start with `services/agents/agents/server.py` and `services/agents/agents/delegator.py`
2. **Read personas**: Understand how AI agents work (`services/agents/agents/personas/`)
3. **Try the tools**: See what tools agents can use (`services/agents/agents/tools/`)
4. **Test locally**: Make API calls and see responses
5. **Make a change**: Fix a bug or add a small feature
6. **Submit PR**: Share your work!

Welcome to the team!
