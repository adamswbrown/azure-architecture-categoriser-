# Agents Module

This module contains the multi-agent AI system built on Pydantic AI for database migration consulting. The system uses a **delegator pattern** where a router agent analyzes user requests and routes them to specialized persona agents.

## Module Structure

### `personas/` - Specialized Agent Personalities

The `personas` module contains specialized Pydantic AI agents, each with distinct expertise areas:

- **`core.py`** (Patch): Default generalist agent for cross-cutting queries and coordination
- **`costings_specialist.py`**: Expert in financial aspects and cost optimization of cloud migrations
- **`migration_architect.py`**: Technical architecture specialist for migration planning and execution
- **`project_manager.py`**: Specializes in project management, timelines, and resource coordination

Each persona follows a standardized pattern (see [Agent Definition Pattern](#agent-definition-pattern) below).

### `deps/` - Dependency Injection System

The `deps` module provides thread-scoped state management and dependencies for agents:

- **`__init__.py`**: Exports `AgentDeps` model for dependency injection
- **`virtual_database.py`**: Thread-safe `VirtualDatabase` class for data storage and retrieval
- **`abstract_template.py`**: Template dataclass definition for response formatting
- **`views.json`**: Database view definitions for migration data analysis

**Key Components:**

**`AgentDeps`**: Pydantic model providing thread-scoped context to agents
```python
class AgentDeps(BaseModel):
    thread_id: str  # Unique identifier for the conversation thread
    database: VirtualDatabase  # Thread-safe database instance
    migration_target: str  # Target cloud provider (e.g., "Azure", "AWS", "GCP")
    llm_provider: Literal["openai", "claude", "gemini"]  # LLM provider for prompt customization
    template: Optional[AbstractTemplate]  # Response template if applicable
```

**`VirtualDatabase`**: Thread-aware data storage system
- Stores DataFrames with string references (e.g., "applications", "cost_analysis")
- Provides thread-scoped isolation - data stored in one thread is not accessible from another
- Methods: `put(ref, df, thread_id)`, `get(ref, thread_id)`, `init_with_defaults()`

### `prompts/` - LLM Provider-Aware Prompt System

The `prompts` module provides a hierarchical, flexible prompt management system:

- **`prompts.py`**: Core `Prompts` interface with LLM provider-aware prompt loading
- **`templates.py`**: `Templates` interface for managing response format templates
- **`core/`**: Default prompt sections (ROLE, RESPONSIBILITIES, TOOLS, DATA, STYLE, FINAL_NOTE)
- **`core/{provider}/`**: Provider-specific prompt overrides (e.g., `core/gemini/STYLE.md`)
- **`{persona}/`**: Persona-specific prompt sections (e.g., `financial_planner/ROLE.md`)
- **`{persona}/{provider}/`**: Persona + provider-specific overrides
- **`templates/`**: Response template markdown files (e.g., `application_summary.md`)

**Prompt Lookup Priority** (first match wins):
1. `{persona}/{llm_provider}/{section}.md` - Most specific
2. `{persona}/{section}.md` - Persona-specific
3. `core/{llm_provider}/{section}.md` - Provider-specific default
4. `core/{section}.md` - Generic fallback

**Template Variables:**
- `{{MIGRATION_TARGET}}` - Replaced with `ctx.deps.migration_target`
- `{{DATA_SCHEMA}}` - Replaced with database schema (DATA.md only)

### `tools/` - Agent Capabilities

The `tools` module provides agents with specialized capabilities:

- **`common_tools.py`**: General-purpose tools available to all agents
- **`db_tools/`**: DuckDB-powered SQL query tools with predefined database views for migration data analysis
- **`mcp_tools/`**: Model Context Protocol (MCP) server integrations for external tool access

Tools are automatically registered and made available to all agents through the `tools.__init__.py` module.

## Running the Agents Backend

The agents backend consists of three key components that work together:

### `server.py` - ASGI Web Server
- Starlette-based server serving both API endpoints and static frontend
- Handles CORS configuration for frontend communication
- Serves the built Next.js frontend from `/frontend/out/` when available
- Configurable via CLI options (port, persona selection, delegation mode)

### `ag_ui.py` - Frontend Integration
- Provides `DrMChatApp` class - a Starlette application with AG-UI endpoints
- Streams agent responses in real-time using Server-Sent Events (SSE)
- Manages thread-scoped state via `DelegationRouter` and `ThreadState` classes
- Handles request routing through the delegator or directly to specific personas
- Supports both delegated mode (auto-routing) and single-persona mode
- Provides `/data` endpoint for retrieving stored data by reference
- **Pre-processes requests** to concurrently execute template agent and persona delegation
- Injects selected templates into agent prompts for structured response formatting

### `__main__.py` - Entry Point
Simple entry point that launches the server via `server.main()`.

**Usage:**
```bash
# Standard delegated mode
uv run agents

# Alternative delegation (starts with core agent)  
uv run agents --alt

# Single persona mode (bypass delegation)
uv run agents --persona "migration architect"

# Custom port
uv run agents --port 8080
```

## Configuration System

### `config.py` - Configuration Management

The configuration system reads from `config.toml` at the project root and provides:

**Structure:**
- **`agents` class**: LLM router configuration and model creation
- **`database` class**: SQL Server connection configuration
- **`server` class**: ASGI server settings (port, host)

**Key Features:**
- TOML file parsing with `tomllib`
- LLM router integration for multi-cloud, identity-based authentication
- Configurable LLM provider (OpenAI, Claude, Gemini) for prompt customization
- Configurable default model tier (light, heavy, reasoning)
- Migration target configuration for prompt variable replacement
- Logfire instrumentation for OpenAI, Pydantic AI, and MCP

**Configuration Sections:**
```toml
[agents]
MODE = "dev"  # "dev" or "prod"
CLOUD_PROVIDER = "AZURE"  # "AZURE" | "AWS" | "GCP"
LLM_PROVIDER = "openai"  # "openai" | "claude" | "gemini"
DEFAULT_TIER = "heavy"  # "light" | "heavy" | "reasoning"
MIGRATION_TARGET = "Azure"  # Target cloud for migration (used in prompts)
ENDPOINTS_JSON_PATH = "./endpoints.json"  # Dev mode

[database]
DB_HOST = "your-host"
DB_NAME = "Assessments"
DB_USER = "username"
DB_PASSWORD = "password"

[server]
PORT = 8002
```

## Agent Definition Pattern

All persona agents follow a consistent structure based on the root-level README.md architecture:

### 1. Module Docstring
Each persona module must have a detailed docstring describing:
- **Responsibilities**: What the agent specializes in
- **Best for**: Ideal use cases  
- **Not for**: What to avoid delegating to this agent
- **Delegation guidelines**: When to prefer this agent vs others

```python
"""
Handles queries about **financial aspects and cost optimization** of cloud migrations.
Specializes in budgeting, cost modeling, ROI analysis, and financial planning.

- **Best for**: 
  - Cost estimation and budgeting for migrations
  - ROI analysis and financial justification
  - Resource pricing and cost optimization strategies

- **Not for**:
  - Technical architecture decisions
  - Project timeline management  
  - General migration questions without financial focus
"""
```

### 2. Agent Export
Each module must export an `agent` variable containing the configured Pydantic AI Agent:

```python
from pydantic_ai import Agent, RunContext

from .. import tools, config
from ..deps import AgentDeps
from ..prompts import Prompts

agent = Agent(
    name="[Persona Name]",
    model=config.agents.create_model(),  # Uses DEFAULT_TIER unless specified
    deps_type=AgentDeps,
    toolsets=[
        tools.common_tools,
        tools.db_toolset,
        tools.mcp_servers,
    ],
    # Use dynamic instructions from prompts system
    dynamic_instructions=lambda ctx: Prompts.persona("[persona_name]").INSTRUCTIONS(ctx),
)
```

**For agents requiring specific model tiers:**
```python
# Heavy tier for complex reasoning
agent = Agent(
    name="Complex Agent",
    model=config.agents.create_model(tier="heavy"),
    deps_type=AgentDeps,
    toolsets=[tools.common_tools],
    dynamic_instructions=lambda ctx: Prompts.persona("complex_agent").INSTRUCTIONS(ctx),
)
```

**Key Changes from Previous Pattern:**
- Use `config.agents.create_model()` instead of `config.openai.create_provider()`
- Use `dynamic_instructions` with `Prompts.persona().INSTRUCTIONS(ctx)` for LLM provider-aware prompts
- Model tier defaults to `config.agents.DEFAULT_TIER` unless explicitly specified
- Instructions automatically adapt based on `ctx.deps.llm_provider` and `ctx.deps.template`

### 3. Persona Registration
Add the new persona to `personas/__init__.py`:

```python
# Import the agent and docstring
from .new_persona import agent as new_persona_agent, __doc__ as new_persona_doc

# Add to Persona enum
class Persona(Enum):
    NEW_PERSONA = "new persona"
    
# Add to agent mapping
def get_agent(self) -> Agent:
    match self:
        case Persona.NEW_PERSONA:
            return new_persona_agent
```

### 4. Create Prompt Files
Create persona-specific prompt sections in `agents/prompts/{persona_name}/`:
- `ROLE.md` - Define the agent's role
- `RESPONSIBILITIES.md` - List specific responsibilities
- Optional: Create LLM provider-specific overrides in `{persona_name}/{provider}/`

See [agents/prompts/prompts.py](prompts/prompts.py) for detailed documentation on the prompt system.

### 5. Delegator Integration
Update `delegator.py` instructions to include the new persona's capabilities and delegation criteria.

## Database Integration

Agents access migration data through a **thread-safe VirtualDatabase system**:

### Architecture

- **Views**: Defined in `deps/views.json`, loaded as pandas DataFrames at startup
- **Thread Isolation**: Each conversation thread has isolated data storage via `thread_id`
- **Query Tool**: `query_dataset(view_name, sql)` for DuckDB operations on views
- **Schema Tool**: `view_schema(view_name)` for metadata and column information
- **Storage**: Large results stored per-thread using `ctx.deps.database.put(ref, df, thread_id)`

### Accessing Thread-Scoped Data in Agents

**Within agent tools** (using `RunContext`):
```python
from pydantic_ai import RunContext
from ..deps import AgentDeps

@agent.tool
async def my_tool(ctx: RunContext[AgentDeps], param: str) -> str:
    # Access thread-scoped database
    database = ctx.deps.database
    thread_id = ctx.deps.thread_id

    # Store data for this thread
    result_df = perform_analysis()
    database.put("analysis_result", result_df, thread_id=thread_id)

    # Retrieve data for this thread
    stored_df = database.get("analysis_result", thread_id=thread_id)

    return f"Stored data reference: analysis_result"
```

**Example Usage in Agent:**
```python
# Query migration assessment data (standard database views)
result = query_dataset("applications", "SELECT * FROM applications WHERE complexity = 'High'")

# Get schema information
schema = view_schema("applications")

# Store large result for later retrieval (thread-scoped)
# This is handled within tools that have access to ctx.deps
```

**Key Points:**
- Data stored with `database.put()` is isolated per `thread_id`
- Other threads/users cannot access each other's stored data
- Pre-configured views (from `views.json`) are shared across all threads
- Frontend can retrieve stored data via `GET /data?ref=<ref>&thread_id=<id>`

## Development Workflow

1. **Test Agents**: Use `uv run python -m agents` for CLI-based agent interaction
2. **Add Personas**: Follow the agent definition pattern above
3. **Modify Tools**: Update `tools/` modules, restart server to reload database views
4. **Debug**: Check Logfire logs for OpenAI, Pydantic AI, and MCP instrumentation

The system is designed for extensibility - new personas and tools can be added following these established patterns.

