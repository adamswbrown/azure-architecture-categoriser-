# Development Guide - drm-chat-poc

This guide explains how to run drm-chat-poc locally on your development machine using cloud CLI credentials.

## Overview

drm-chat-poc now uses `llm_router` for identity-based, multi-cloud authentication. This means:

- ✅ **No API keys needed** - Use your cloud CLI credentials (az login, gcloud auth, aws configure)
- ✅ **Test all clouds locally** - Azure OpenAI, AWS Bedrock, GCP Vertex AI
- ✅ **Same code as production** - Dev and prod use the same codebase, different auth methods
- ✅ **Easy cloud switching** - Change `CLOUD_PROVIDER` in config.toml

---

## Quick Start

### 1. Install Dependencies

```bash
cd /path/to/drm-chat-poc

# Install with uv (recommended)
uv sync

# OR install with pip
pip install -e .
```

### 2. Set Up Configuration

```bash
# Copy example config
cp config.example.toml config.toml

# Edit config.toml
# Set MODE = "dev" (should already be set in example)
# Set CLOUD_PROVIDER = "AZURE" (or "AWS" or "GCP")
```

Your `config.toml` should look like:

```toml
[agents]
MODE = "dev"
CLOUD_PROVIDER = "AZURE"  # "AZURE" | "AWS" | "GCP"
LLM_PROVIDER = "openai"  # "openai" | "claude" | "gemini"
DEFAULT_TIER = "heavy"  # "light" | "heavy" | "reasoning"
MIGRATION_TARGET = "Azure"  # Target cloud for migration prompts
ENDPOINTS_JSON_PATH = "./endpoints.json"

[server]
PORT = 8002

[db]
DB_HOST = "your-database-host"
DB_PORT = 1433
DB_USER = "your-username"
DB_PASSWORD = "your-password"
DB_NAME = "Assessments"
```

### 3. Authenticate with Cloud CLI

Choose the cloud provider you want to use and authenticate:

#### Azure (GPT models)

```bash
# Login to Azure
az login

# Verify authentication
az account show

# Check Azure OpenAI access (optional)
az cognitiveservices account list --resource-group YOUR_RG
```

#### AWS (Claude models)

```bash
# Configure AWS CLI
aws configure
# Enter:
#   - AWS Access Key ID
#   - AWS Secret Access Key
#   - Default region (e.g., us-east-1)
#   - Default output format (json)

# Verify authentication
aws sts get-caller-identity

# Check Bedrock access (optional)
aws bedrock list-foundation-models --region us-east-1
```

#### GCP (Gemini models)

```bash
# Login to GCP
gcloud auth login

# Set up Application Default Credentials
gcloud auth application-default login

# Set your project ID
gcloud config set project YOUR_GCP_PROJECT_ID

# Enable Vertex AI API (if not already enabled)
gcloud services enable aiplatform.googleapis.com

# Verify access (optional)
gcloud ai models list --region=us-east1
```

### 4. Run the Server

```bash
# Start the development server
agents

# OR
python -m agents.server

# Server will be available at http://localhost:8002
```

---

## Testing Different Cloud Providers

### Test Azure OpenAI (GPT models)

```bash
# 1. Authenticate with Azure
az login

# 2. Update config.toml
#    Set CLOUD_PROVIDER = "AZURE"

# 3. Start server
agents
```

**Models used:**
- Light tier: `gpt-5-mini`
- Heavy tier: `gpt-5`
- Reasoning tier: `o3-mini`

### Test AWS Bedrock (Claude models)

```bash
# 1. Authenticate with AWS
aws configure

# 2. Update config.toml
#    Set CLOUD_PROVIDER = "AWS"

# 3. Start server
agents
```

**Models used:**
- Light tier: `claude-haiku-4-5`
- Heavy tier: `claude-sonnet-4-5`
- Reasoning tier: `claude-sonnet-4-5`

### Test GCP Vertex AI (Gemini models)

```bash
# 1. Authenticate with GCP
gcloud auth application-default login
gcloud config set project YOUR_GCP_PROJECT_ID

# 2. Update config.toml
#    Set CLOUD_PROVIDER = "GCP"

# 3. Start server
agents
```

**Models used:**
- Light tier: `gemini-2.5-flash`
- Heavy tier: `gemini-2.5-pro`
- Reasoning tier: `gemini-2.5-pro`

---

## Development Workflow

### Making Changes

1. **Update agent code** - Modify persona agents in `agents/personas/`
2. **Test locally** - Run `agents` to start server
3. **Switch clouds** - Change `CLOUD_PROVIDER` in config.toml to test different models
4. **Commit changes** - Same code works in production

### Adding New Agents

```python
# agents/personas/my_new_agent.py
from pydantic_ai import Agent
from .. import tools, config
from ..deps import AgentDeps
from ..prompts import Prompts

agent = Agent(
    name="My New Agent",
    model=config.agents.create_model(),  # Uses DEFAULT_TIER in config unless specified
    deps_type=AgentDeps,
    toolsets=[tools.common_tools],
    # Use dynamic instructions that adapt to LLM provider and templates
    dynamic_instructions=lambda ctx: Prompts.persona("my_new_agent").INSTRUCTIONS(ctx),
)
```

**To use a different tier:**

```python
# Heavy tier for complex reasoning
agent = Agent(
    name="Complex Agent",
    model=config.agents.create_model(tier="heavy"),
    deps_type=AgentDeps,
    toolsets=[tools.common_tools],
    dynamic_instructions=lambda ctx: Prompts.persona("complex_agent").INSTRUCTIONS(ctx),
)

# Reasoning tier for deep thinking (o1, o3-mini)
agent = Agent(
    name="Reasoning Agent",
    model=config.agents.create_model(tier="reasoning"),
    deps_type=AgentDeps,
    toolsets=[tools.common_tools],
    dynamic_instructions=lambda ctx: Prompts.persona("reasoning_agent").INSTRUCTIONS(ctx),
)
```

**Creating Prompt Files:**

Create persona-specific prompts in `agents/prompts/{persona_name}/`:
```bash
# Create directory for your persona
mkdir -p agents/prompts/my_new_agent

# Create prompt sections
echo "# Role\nYou are the My New Agent..." > agents/prompts/my_new_agent/ROLE.md
echo "### Responsibilities\n- Task 1\n- Task 2" > agents/prompts/my_new_agent/RESPONSIBILITIES.md

# Optional: Create LLM provider-specific overrides
mkdir -p agents/prompts/my_new_agent/gemini
echo "# Style\nUse graphs heavily..." > agents/prompts/my_new_agent/gemini/STYLE.md
```

See [agents/prompts/prompts.py](/agents/prompts/prompts.py) for full documentation on the prompt system.

---

## How It Works

### Environment Detection

llm_router automatically detects whether you're running locally or in production:

| Environment | Detection Method | Authentication |
|-------------|------------------|----------------|
| **Local (dev mode)** | `MODE = "dev"` in config.toml | Cloud CLI credentials |
| **Production (prod mode)** | `MODE = "prod"` in config.toml | Azure UMI + Storage |

### Authentication Flow (Dev Mode)

```
config.toml (MODE = "dev")
    ↓
llm_router detects local environment
    ↓
Uses cloud CLI credentials:
  - Azure: DefaultAzureCredential (az login)
  - AWS: boto3 credential chain (aws configure)
  - GCP: Application Default Credentials (gcloud auth)
    ↓
Reads endpoints.json from local file
    ↓
Creates Pydantic AI model
    ↓
Agent uses model for inference
```

### Configuration Files

**config.toml** (agent configuration):
- `MODE`: "dev" or "prod"
- `CLOUD_PROVIDER`: "AZURE", "AWS", or "GCP"
- `ENDPOINTS_JSON_PATH`: Path to local endpoints.json (dev mode)

**endpoints.json** (cloud endpoints and models):
- Lists available models per cloud/tier
- Contains authentication configuration
- Maps geos to regions

### Persona Management & Multi-User Architecture

The application uses thread-scoped persona state management for proper multi-user and multi-tab isolation.

#### Architecture Overview

```
Frontend (CopilotKit + Next.js)
    ↓ (HTTP POST with thread_id)
Backend AG-UI Endpoint (/api) - DrMChatApp
    ↓
DelegationRouter (per-thread state)
    ↓
PersonaAgent selected per thread (with AgentDeps)
    ↓ (agent has access to thread_id & VirtualDatabase)
Agent Tools (query data, store results)
    ↓
SSE broadcasts to thread-specific clients
```

#### Thread-Scoped State Management

**Backend** (`agents/ag_ui.py`):
- **DrMChatApp**: Starlette application class that encapsulates all AG-UI endpoints
- **DelegationRouter**: Maintains a `Dict[thread_id → ThreadState]` mapping (internal to DrMChatApp)
- **ThreadState**: Each thread has isolated state:
  - `waiting`: Auto-delegation enabled/disabled
  - `delegate`: Whether delegation occurred
  - `persona`: Currently active persona for this thread
  - `event_queues`: List of SSE connections for this thread
- **VirtualDatabase**: Thread-scoped data storage (shared across DrMChatApp)
  - Stores DataFrames per thread
  - Enables data isolation between users/sessions

**Frontend** (`frontend/components/PersonaContext.tsx`):
- Uses CopilotKit's official `useCopilotContext()` hook to access `threadId`
- All API requests include `thread_id` for session isolation
- SSE connections are scoped to specific threads via query parameter

#### Real-Time Persona Updates (SSE)

The application uses Server-Sent Events for real-time persona synchronization:

1. **Frontend connects** to `/persona/stream?thread_id={threadId}`
2. **Backend creates** a queue for this specific thread
3. **When persona changes** (auto-delegation or manual selection):
   - Backend broadcasts to queues belonging to that `thread_id` only
   - Other threads/users are not affected
4. **Frontend receives** persona change event and updates UI

#### Multi-User & Multi-Tab Behavior

**Multiple Users:**
- Each user has their own CopilotKit `thread_id`
- Persona selections are isolated per user
- SSE updates only reach the user who triggered the change

**Multiple Tabs (Same User):**
- Each tab maintains a separate CopilotKit thread
- Tabs have independent persona state
- Auto-delegation in one tab doesn't affect others

#### Key Implementation Details

**Component Hierarchy** (Frontend):
```tsx
<CopilotKit>          // Provides threadId context
  <PersonaProvider>   // Accesses threadId via useCopilotContext()
    <ChatInterface>
      <PersonaPanel>
      <CopilotChat>
```

**Thread Isolation** (Backend):
```python
# DrMChatApp handles all requests
class DrMChatApp(Starlette):
    async def handle_request(self, request: Request):
        # Each request includes thread_id from CopilotKit
        thread_id = run_input.thread_id

        # Get thread-specific state
        thread_state = await self._delegation_router.get_thread_state(thread_id)

        # Operate on this thread's state only
        thread_state.persona = selected_persona

        # Build deps for thread (includes VirtualDatabase access)
        deps = AgentDeps(thread_id=thread_id, database=self.database)

        # Run agent with thread-scoped dependencies
        adaptor = AGUIAdapter(persona.agent, run_input=run_input, ...)
        return adaptor.streaming_response(adaptor.run_stream(deps=deps))

        # Broadcast only to this thread's SSE clients
        await self._broadcast_persona_change(persona, thread_id)
```

**Important Notes:**
- Never generate custom session IDs - always use CopilotKit's `threadId`
- SSE endpoints require `thread_id` query parameter
- Persona state is thread-scoped, not global
- Backend expects `thread_id` in all persona-related requests

### Data Endpoint & Thread-Scoped Storage

The application provides a `/data` endpoint for retrieving stored data, with full thread isolation via `VirtualDatabase`.

#### VirtualDatabase Architecture

**Purpose**: Store and retrieve DataFrames with thread-scoped isolation

**Key Features:**
- **Thread Isolation**: Data stored in one thread is not accessible from another
- **Reference-Based Retrieval**: Store DataFrames with string references (e.g., "cost_analysis", "migration_plan")
- **Shared Views**: Pre-configured database views (from `agents/deps/views.json`) are available to all threads
- **Memory Management**: Thread-local storage prevents data leakage between users

**Implementation** (`agents/deps/virtual_database.py`):
```python
class VirtualDatabase:
    def __init__(self):
        self.views: dict[str, DatabaseView] = {}  # Shared across threads
        self._thread_data: dict[str, dict[str, pd.DataFrame]] = {}  # Per-thread storage
        self._lock = asyncio.Lock()

    def put(self, ref: str, df: pd.DataFrame, thread_id: Optional[str] = None):
        """Store a DataFrame with a reference for a specific thread."""
        # Stores in self._thread_data[thread_id][ref] = df

    def get(self, ref: str, thread_id: Optional[str] = None) -> Optional[pd.DataFrame]:
        """Retrieve a DataFrame by reference for a specific thread."""
        # Checks thread-specific storage first, then shared views
```

#### Data Endpoint

**Endpoint**: `GET /data`

**Query Parameters:**
- `ref` (required): Reference string for the data
- `thread_id` (optional): Thread ID for thread-scoped retrieval (defaults to "default")
- `limit` (optional): Limit number of rows (default: -1 for all rows)

**Example Requests:**
```bash
# Get shared database view (available to all threads)
curl "http://localhost:8002/data?ref=applications&limit=100"

# Get thread-specific stored data
curl "http://localhost:8002/data?ref=cost_analysis&thread_id=abc123&limit=50"
```

**Response Format** (JSON):
```json
{
  "columns": [
    {"name": "app_name", "type": "string"},
    {"name": "complexity", "type": "string"},
    {"name": "cost", "type": "number"}
  ],
  "rows": [
    ["App1", "High", 50000],
    ["App2", "Medium", 25000]
  ]
}
```

**Error Responses:**
- `400 Bad Request`: Missing `ref` parameter or invalid `limit`
- `404 Not Found`: Reference not found in specified thread
- `500 Internal Server Error`: Processing error

#### Using VirtualDatabase in Agent Tools

**Agent tools** access the VirtualDatabase via dependency injection:

```python
from pydantic_ai import RunContext
from ..deps import AgentDeps

@agent.tool
async def analyze_costs(ctx: RunContext[AgentDeps], filters: str) -> str:
    """Analyze migration costs and store results."""
    # Access thread-scoped dependencies
    database = ctx.deps.database
    thread_id = ctx.deps.thread_id

    # Query shared view
    view_df = database.get("cost_overview", thread_id=thread_id)

    # Perform analysis
    filtered_df = view_df.query(filters)
    summary_df = filtered_df.groupby("category").sum()

    # Store results for this thread
    database.put("cost_analysis", summary_df, thread_id=thread_id)

    return f"Analysis complete. View results: /data?ref=cost_analysis&thread_id={thread_id}"
```

**Key Points:**
- Agents receive `AgentDeps` via `ctx.deps` (dependency injection)
- Always use `ctx.deps.thread_id` to ensure proper isolation
- Frontend can fetch stored data via `/data` endpoint with matching `thread_id`
- Pre-configured views are shared; agent-generated data is thread-scoped

### Logging and Debugging

The application uses structured logging following the llm_router pattern for easy debugging and monitoring.

#### Module-Specific Loggers

All modules use `get_logger()` from `config`:

```python
from . import config

logger = config.get_logger('agents.my_module')  # Use module hierarchy
```

**Logger Naming Convention:**
- Follow Python module hierarchy: `agents.tools.db_tools`, `agents.delegator`, etc.
- Makes filtering logs by component easy
- Consistent with llm_router's internal logging

#### Log Levels and What They Show

**INFO** - Normal operations:
```
INFO - LLM Integration initializing: mode=dev, cloud=GCP
INFO - LLM Router initialized successfully
INFO - Server starting on port 8002
INFO - Processing request for thread: abc123
INFO - Delegator selected persona: system architect
```

**WARNING** - Non-critical issues:
```
WARNING - SSE queue put timeout for thread abc123
WARNING - Database connection slow: 2.5s
```

**ERROR** - Failures with full context:
```
ERROR - Failed to execute query for dataset 'sales_data'
ERROR - SQL: SELECT * FROM sales WHERE ...
ERROR - Description: Monthly sales analysis
ERROR - Error: Connection timeout
```

#### Debugging Tips

**Filter logs by module:**
```bash
# See only database operations
agents 2>&1 | grep "agents.tools.db_tools"

# See only delegation decisions
agents 2>&1 | grep "agents.delegator"

# See only llm_router activity
agents 2>&1 | grep "llm_router"
```

**Check llm_router initialization:**
```bash
# Look for these messages on startup
agents 2>&1 | grep "LLM.*initializ"

# Expected output:
# INFO - LLM Integration initializing: mode=dev, cloud=GCP
# INFO - LLM Router initialized successfully
```

**Monitor performance:**
```bash
# Database view loading times
agents 2>&1 | grep "Loading views"

# Query execution times
agents 2>&1 | grep "Query.*succeeded"
```

#### Thread-Scoped State (Multi-User Support)

The application maintains per-thread state using CopilotKit's `thread_id`:

- Each user/tab has a unique `thread_id` from CopilotKit
- Backend uses `thread_id` for persona state isolation
- SSE connections scoped to specific threads: `/persona/stream?thread_id={id}`
- Logs include `thread_id` for tracing requests: `Processing request for thread: abc123`
- **VirtualDatabase** provides thread-scoped data storage for agent outputs

**Key Architecture Points:**
- Frontend uses `useCopilotContext()` to access CopilotKit's official `threadId`
- Backend maintains `Dict[thread_id → ThreadState]` for persona isolation
- Backend maintains `Dict[thread_id → Dict[ref → DataFrame]]` for data isolation
- Multiple users and tabs operate independently without interference

---

## Troubleshooting

### Error: "Failed to initialize LLM Router"

**Cause**: Cloud authentication not set up

**Solution**:
```bash
# Azure
az login

# AWS
aws configure

# GCP
gcloud auth application-default login
```

### Error: "Config file not found"

**Cause**: No `config.toml` file

**Solution**:
```bash
cp config.example.toml config.toml
# Edit config.toml with your settings
```

### Error: "DefaultAzureCredential failed to retrieve a token"

**Cause**: Not logged into Azure CLI

**Solution**:
```bash
az login
az account show  # Verify you're logged in
```

### Error: "Unable to locate credentials" (AWS)

**Cause**: AWS CLI not configured

**Solution**:
```bash
aws configure
aws sts get-caller-identity  # Verify credentials
```

### Error: "Could not automatically determine credentials" (GCP)

**Cause**: GCP Application Default Credentials not set up

**Solution**:
```bash
gcloud auth application-default login
gcloud config set project YOUR_GCP_PROJECT_ID
```

### Error: "Location 'local' not found in geo_map"

**Cause**: endpoints.json missing "local" in geo_map

**Solution**: Already fixed in the provided `endpoints.json` - "local" is mapped to "US"

---

## Environment Variables

Optional environment variables for advanced use cases:

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_ROUTER_LOCATION` | `"local"` | Override location detection |
| `LLM_ROUTER_VM_NAME` | `"local-dev"` | VM name for identity discovery |
| `GOOGLE_CLOUD_PROJECT` | From gcloud config | GCP project ID |
| `AWS_DEFAULT_REGION` | From AWS config | AWS region |

---

## Testing Before Deployment

### Validate Configuration

```bash
# Check that all cloud CLIs are authenticated
az account show
aws sts get-caller-identity
gcloud auth list

# Test each cloud provider
# 1. Set CLOUD_PROVIDER = "AZURE" in config.toml
agents  # Test Azure

# 2. Set CLOUD_PROVIDER = "AWS" in config.toml
agents  # Test AWS

# 3. Set CLOUD_PROVIDER = "GCP" in config.toml
agents  # Test GCP
```

### Verify Endpoints

```bash
# Check endpoints.json is valid JSON
python -m json.tool endpoints.json

# Verify all required fields are present
cat endpoints.json | grep -E "(version|schema|clouds|auth|endpoints)"
```

---

## Production Deployment

When ready to deploy to production:

1. **Update config.toml** on production VM:
   ```toml
   [agents]
   MODE = "prod"  # Changed from "dev"
   CLOUD_PROVIDER = "AZURE"  # Based on customer's migration target
   ENDPOINTS_JSON_URL = "https://stgdrmigrate.blob.core.windows.net/config/endpoints.json"
   ```

2. **Ensure Azure UMI is assigned** to the VM

3. **Verify UMI has access** to:
   - Azure OpenAI (if using Azure)
   - Azure Storage (for downloading endpoints.json)

4. **No code changes needed** - same codebase, different authentication

---

## Getting Help

If you encounter issues:

1. **Check authentication**: Verify cloud CLI is logged in
2. **Check permissions**: Ensure you have access to cloud services
3. **Check logs**: Look for llm_router log messages
4. **Test CLIs directly**: Try using cloud CLI commands directly

**Common log messages:**

```
# Development (local)
INFO - LLM Integration initializing: mode=dev, cloud=AZURE
INFO - Development mode: using local credentials

# Production (Azure VM)
INFO - LLM Integration initializing: mode=prod, cloud=AZURE
INFO - Production mode: using Azure UMI
```

---

**Happy developing! 🚀**
