# AI Coding Agent Instructions - Dr. Migrate Chat POC

## Architecture Overview

This is a **multi-agent AI system** built on Pydantic AI for database migration consulting. The system uses a **delegator pattern** where a router agent (`delegator.py`) analyzes user requests and routes them to specialized persona agents.

### Core Components
- **Server**: Starlette ASGI server (`server/`) serving both API and static frontend
- **Agents**: Pydantic AI agents with specialized personas (`agents/`)  
- **Frontend**: Next.js React app (`frontend/`) using CopilotKit and AG-UI
- **Database Tools**: DuckDB-powered SQL query tools with predefined views (`agents/tools/db_tools/`)

## Key Architectural Patterns

### Agent Delegation System
```python
# All user requests flow through delegator.py first
delegator_agent -> routes to -> persona.agent (core, project_manager, etc.)
```

Each persona in `agents/personas/` must:
1. Export an `agent` variable (Pydantic AI Agent instance)
2. Have a module docstring describing its capabilities (used by delegator)
3. Follow the enum pattern defined in `agents/personas/__init__.py`

### Database Integration Pattern
Agents use a **view-based abstraction** over SQL Server:
- Views defined in `agents/tools/db_tools/views.json`
- `DATABASE.views` provides cached pandas DataFrames  
- Tools: `query_dataset()` for DuckDB queries, `view_schema()` for metadata
- Results stored as references to avoid context bloat: `ref = DATABASE.store(dataframe)`

### Configuration System
- **Root config**: `config.toml` with Azure OpenAI, database, server settings
- **Agent config**: `agents/config.py` loads TOML, creates clients with retry logic
- **MCP config**: `agents/tools/mcp_tools/mcp_config.json` for external tool servers

## Development Workflows

### Running the System
```bash
# Backend (agents + server)
uv run python -m server  # http://localhost:8002

# Frontend (separate terminal)
cd frontend && pnpm dev  # http://localhost:3000

# Agent CLI testing
uv run python -m agents  # Direct agent interaction
```

### Adding New Personas
1. Create `agents/personas/new_persona.py` with agent variable and docstring
2. Add to `Persona` enum in `agents/personas/__init__.py`
3. Update delegator instructions in `agents/delegator.py`

### Database Tools Development
- Views are cached at startup - restart server after schema changes
- Use `query_dataset(view_name, sql)` for DuckDB operations on views
- Return references for large results: `DATABASE.store(df)` → `ref_123`

## Project-Specific Conventions

### Agent Instructions Pattern
All personas follow this structure:
```python
INSTRUCTIONS = f"""You are the **[Role] Agent**.
### Responsibilities
- Specific tasks for this persona
### Database
{tools.DATABASE.list_database_views()}  # Inject available views
"""
```

### Error Handling
- Use `ModelRetry` for recoverable LLM errors (invalid queries, missing data)
- Database tools have built-in retry logic (5 attempts)
- HTTP clients use exponential backoff with Retry-After header support

### Frontend Integration
- Uses AG-UI for Pydantic AI integration (`@ag-ui/pydantic-ai`)
- Server streams responses via `/api` endpoint using `ag_ui_endpoint()`
- Static build: `pnpm run build:static` → served from `server/frontend/out/`

## Critical Files & Dependencies

### Configuration Files
- `config.toml` - Azure OpenAI, database credentials (copy from `config.example.toml`)
- `agents/tools/mcp_tools/mcp_config.json` - External tool server URLs
- `agents/tools/db_tools/views.json` - Database view definitions

### Core Integration Points
- `agents/ag_ui.py` - Frontend ↔ Agent communication
- `agents/delegator.py` - Agent routing logic  
- `agents/tools/__init__.py` - Tool registration for all agents
- `server/__main__.py` - ASGI app with CORS, static serving, logfire

### Database Schema
Views in SQL Server `copilots` schema provide migration assessment data. Schema metadata fetched via `sys.views`, `sys.columns`, `sys.extended_properties`.

## Testing & Debugging

- **Agent CLI**: `uv run python -m agents` for direct testing
- **Logs**: Logfire instrumentation on OpenAI, Pydantic AI, MCP
- **Database**: Test queries via `query_dataset()` tool in agent CLI
- **Frontend**: Check browser console for AG-UI connection issues

## Dependencies
- **Backend**: `pydantic-ai-slim[ag-ui,cli,mcp,openai,retries]`, `duckdb`, `starlette`, `logfire`  
- **Frontend**: `@ag-ui/pydantic-ai`, `@copilotkitnext/react`, Next.js 15
- **Build**: `uv` for Python, `pnpm` for Node.js