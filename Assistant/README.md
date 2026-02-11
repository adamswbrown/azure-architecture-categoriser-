# Dr. Migrate Chat

This repository contains a **multi-agent AI system** built on Pydantic AI for database migration consulting. The system uses a **delegator pattern** where a router agent analyzes user requests and routes them to specialized persona agents.

## Architecture Overview

### Core Components
- **Frontend** (`frontend/`): Static Next.js React application
  - Deployed as static files (S3, CDN, or any web server)
  - CopilotKit UI for chat interface
  - Persona management and SSE integration
  - Direct HTTP calls to Python backend for persona/data endpoints

- **CopilotKit Proxy Server** (`copilotkit-server/`): Standalone Node.js service
  - Port 8001 (configurable)
  - Protocol translation: CopilotKit ↔ AG-UI
  - Proxies chat requests to Python backend
  - Independent deployment and scaling

- **Python Backend** (`agents/`): Pydantic AI multi-agent system
  - Port 8000 (configurable)
  - Starlette ASGI server using `DrMChatApp` architecture
  - AG-UI protocol for agent communication
  - Thread-safe VirtualDatabase with DuckDB
  - Specialized AI personas with dependency injection

### Available Agent Personas
- **Core**: Default agent for general migration questions and coordination
- **Project Manager**: Project management, timelines, resource allocation, and migration activity coordination
- **System Architect**: Technical architecture design, migration strategy optimization, and infrastructure planning
- **Financial Planner**: Cost analysis, budget optimization, and financial ROI assessment
- **Network Specialist**: Network configuration, security architecture, and cloud connectivity setup
- **Migration Engineer**: Technical execution, troubleshooting, and migration implementation

## Running the System

### Setup

Setting up the environment requires [installing uv](https://docs.astral.sh/uv/getting-started/installation/)

Copy the example configuration and customize it:
```bash
cd services/agents
cp config.example.toml config.toml
# Edit config.toml with your cloud provider, LLM provider, and database settings
```

### Running the Agent Server

To start the multi-agent server, run from the `services/agents` directory:

```bash
cd services/agents
uv run agents
```

This will start an ASGI server on `http://localhost:8002`.

#### Advanced Server Options

You can customize the server behavior with additional options:

```bash
# Use alternative delegation mode (starts with core agent, delegates as needed)
uv run agents --alt

# Run only a specific persona (bypasses delegation)
uv run agents --persona core
uv run agents --persona "project manager"
uv run agents --persona "system architect"
uv run agents --persona "financial planner"
uv run agents --persona "network specialist"
uv run agents --persona "migration engineer"

# Run on a custom port (not advised, as frontend expects the value in the config.toml)
uv run agents --port 8080
```

## Frontend

The frontend is a Next.js React application that provides a user-friendly chat interface for interacting with the multi-agent system. It uses CopilotKit and AG-UI for seamless integration with Pydantic AI agents.

### Setup

The frontend requires [pnpm](https://pnpm.io/) to be installed.

To install the dependencies, navigate to the `frontend` directory:
```bash
cd services/agents/frontend
pnpm install
```

### Development Mode

To start the frontend in development mode, run:

```bash
cd services/agents/frontend
pnpm dev
```

This will start the frontend development server on `http://localhost:3000`.

### Production Build

To build the frontend for production and serve it from the agents server:

```bash
cd services/agents/frontend
pnpm run build:static
```

The built frontend will be served directly from the agents server at `http://localhost:8002`.

#### Advanced Frontend Options

If the port `3000` is inconvenient, you can specify a different port when starting the development server:

```bash
pnpm dev -p 3123
```

## Development Workflow

### Adding New Agent Personas

To add a new specialized agent persona:

1. Create `services/agents/agents/personas/<my_new_agent>.py` with an `agent` variable and docstring
    - the agent variable should be an instance of `Agent` from `pydantic_ai`
    - the docstring should describe the persona's role, expertise, and instructions and will be used as a prompt for delegation.
2. Add the persona to the `Persona` enum in `services/agents/agents/personas/__init__.py`
    - the pattern is hopefully pretty straightforward, just follow the existing examples.

#### Testing your new agent persona

You can restrict the agent server to only using your new agent persona by specifying it in the command:
```bash
uv run agents --persona="<name>"
```
where `<name>` is the name you added to the `Persona` enum.

### Configuration

- **`services/agents/config.toml`**: LLM provider, cloud provider, database connection, server settings
- **`services/agents/agents/deps/views.json`**: Database view definitions for migration analysis
- **`services/agents/frontend/.env.development`**: Development environment configuration (local development, no URL prefix)
- **`services/agents/frontend/.env.production`**: Production environment configuration (default `/chat` prefix for IIS)
- **`services/agents/frontend/.env.local`**: Local developer overrides (not committed to git)
- **`services/copilotkit-proxy/.env.*`**: CopilotKit proxy environment-specific configuration

## Architecture Details

The system implements a sophisticated delegation pattern where:

1. **Delegator Agent** analyzes incoming requests and routes them to appropriate personas
2. **Template Agent** selects response formatting templates based on user intent
3. **Specialized Personas** handle domain-specific tasks with expert knowledge
4. **Database Tools** provide migration assessment data via thread-scoped DuckDB and SQL Server views
5. **Frontend Integration** uses AG-UI and CopilotKit for real-time agent communication
6. **Thread-Scoped State** isolates data between concurrent conversations using `VirtualDatabase`

Each persona agent has access to the same set of tools but provides specialized expertise in their domain area, enabling more focused and expert responses for complex migration scenarios. The delegator and template agents use lightweight models for fast routing decisions, while persona agents use more powerful models for nuanced responses.

### Data Management

The system provides a `/data` endpoint for retrieving stored data by reference:

**Endpoint:** `GET /data`

**Query Parameters:**
- `ref` (required): Reference string for the data (e.g., view name or agent output reference)
- `thread_id` (optional): Thread ID for thread-scoped data retrieval
- `limit` (optional): Limit number of rows returned (default: all rows)

**Example:**
```bash
curl "http://localhost:8002/data?ref=applications&thread_id=thread_123&limit=100"
```

**Response:** JSON representation of the data table with columns and rows

This enables agents to store large datasets without bloating conversation context, and ensures data isolation between different user sessions.

## Deployment

The application supports multiple deployment scenarios with configurable base paths:

- **Local Development**: Runs on `http://localhost:3000` with no URL prefix
- **IIS Production**: Deployed as sub-application at `/chat` (e.g., `https://example.com/chat`)
- **Custom Deployments**: Configurable for any base path or reverse proxy setup

### Quick Start - Development

The system consists of three independent services that need to be running:

```bash
# Terminal 1: Start Python backend (port 8002)
cd services/agents
uv run agents

# Terminal 2: Start CopilotKit proxy server (port 8001)
cd services/copilotkit-proxy
pnpm install  # First time only
pnpm run dev

# Terminal 3: Build and serve static frontend
cd services/agents/frontend
pnpm install  # First time only
pnpm run build
pnpm exec serve out

# Access at: http://localhost:3000 (or port shown by serve)
```

**Note**: The frontend is now a static site. For development, you can also use `pnpm dev` but the production deployment will use static files from the `out/` directory.

### Quick Start - Production

The application consists of three independent components:

```bash
# 1. Build and deploy static frontend
cd services/agents/frontend
pnpm install
pnpm run build
# Deploy the 'out/' directory to your web server (IIS, nginx, S3, CDN, etc.)

# 2. Build and run CopilotKit proxy server
cd services/copilotkit-proxy
pnpm install
pnpm run build
pnpm start
# Or use PM2: pm2 start dist/server.js --name copilotkit-proxy

# 3. Run Python backend (from Assistant/ root)
cd services/agents
uv run agents

# Configure reverse proxy (IIS/nginx) to route:
# - Static files → Frontend (out/ directory)
# - /copilotkit or /copilotkit-api → CopilotKit server (port 8001)
# - /backend/* → Python backend (port 8002)
```

**Deployment Architecture**:
- **Frontend**: Static files on any web server
- **CopilotKit Proxy**: Standalone Node.js service (port 8001)
- **Python Backend**: ASGI service (port 8002)

### Production Deployment (Windows Services)

For production Windows Server deployments, the Assistant services run as Windows Services with WinSW, providing automatic startup, restart on failure, and integrated logging.

#### Automated Deployment

The services are automatically installed during the Dr.Migrate bootstrap process:

```powershell
# Runs automatically in Bootstrap/Scripts/SetupDrMigrate.ps1
Install-AssistantDependencies    # Installs Python and Node.js dependencies
New-AssistantConfiguration       # Configures services with Vault secrets
Install-AssistantServices        # Installs Windows Services with WinSW
```

#### Manual Service Management

After deployment, manage services using PowerShell scripts:

```powershell
cd C:\DrMigrate\Assistant\services

# Check service health
.\check-health.ps1

# Restart services
.\restart-services.ps1

# View detailed status
.\check-health.ps1 -Detailed

# Continuous monitoring
.\check-health.ps1 -ContinuousMonitor -MonitorInterval 60
```

#### Installed Services

- **DrMigrate-AgentsServer** - Python agents backend (port 8002)
  - Auto-starts on boot
  - Restarts on failure (3 attempts)
  - Logs: `Assistant/logs/` and `services/DrMigrate-AgentsServer.out.log`

- **DrMigrate-CopilotKitProxy** - Node.js proxy (port 8001)
  - Auto-starts after AgentsServer
  - Restarts on failure (3 attempts)
  - Logs: `copilotkit-server/logs/` and `services/DrMigrate-CopilotKitProxy.out.log`

#### Secret Management

Secrets are loaded from HashiCorp Vault during configuration:

```powershell
# Load secrets from Vault
cd C:\DrMigrate\Assistant\config
.\secrets-loader.ps1 -Scope Machine

# Secrets are stored at: secret/data/assistant
# Required: MODE, CLOUD_PROVIDER, LLM_PROVIDER
# Optional: DB_CONNECTION_STRING, AZURE_OPENAI_API_KEY, etc.
```

For manual configuration (development):
```powershell
# Copy template files
Copy-Item config.example.toml config.toml
Copy-Item copilotkit-server\.env.local.example copilotkit-server\.env.production

# Edit files with your credentials
notepad config.toml
notepad copilotkit-server\.env.production
```

#### Comprehensive Production Guide

For detailed production deployment instructions including:
- Service installation and configuration
- Secret management with Vault
- IIS reverse proxy setup
- Health monitoring and alerting
- Troubleshooting and performance tuning
- Backup and disaster recovery

See **[Production Deployment Guide](docs/PRODUCTION_DEPLOYMENT.md)**

### Detailed Deployment Guide

For comprehensive deployment instructions including:
- Environment-specific configuration
- Custom base path setup
- Docker deployments
- Nginx/IIS reverse proxy configuration
- Migration from hardcoded paths
- Troubleshooting

See **[Base Path Configuration Guide](docs/BASE_PATH_CONFIGURATION.md)**

## Additional Documentation

- **[Production Deployment](docs/PRODUCTION_DEPLOYMENT.md)** - Production Windows Services deployment guide
- **[Base Path Configuration](docs/BASE_PATH_CONFIGURATION.md)** - Comprehensive guide for configurable deployment paths
- **[Development Guide](docs/DEVELOPMENT.md)** - Development workflow and best practices
- **[Chat Security Implementation](docs/CHAT_SECURITY_IMPLEMENTATION.md)** - Security considerations
- **[SSE Improvement Plan](docs/SSE_IMPROVEMENT_PLAN.md)** - Server-Sent Events architecture
- **[LLM Router Migration](docs/LLM_ROUTER_MIGRATION.md)** - LLM provider configuration
