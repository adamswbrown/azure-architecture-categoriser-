# Architecture Recommendation Tool — Agent Integration

## Overview

This adds an architecture scoring capability to the Dr. Migrate Assistant's **System Architect** persona. When a user asks which Azure architecture fits an application, the agent queries the Dr. Migrate database, builds a scoring context from the application's tech stack and server data, runs it through the architecture scoring engine against the catalog (~170 reference architectures), and returns ranked recommendations with explanations.

The tool follows the agent's existing patterns: `FunctionToolset[AgentDeps]` with dependency injection, `config.toml`-driven configuration, identity-based Azure Blob Storage authentication via `ConfigLoader`, and results stored in DuckDB for charting.

## What It Does

```
User: "What Azure architecture would you recommend for Application X?"
                                    |
                                    v
        +--------------------------------------------------+
        |  get_architecture_recommendation(application_name) |
        +--------------------------------------------------+
                                    |
          1. Query DB views (application_overview,
             server_overview_current, key_software_overview,
             app_modernization_candidates)
                                    |
          2. Map DB columns -> RawContextFile
             (architecture_mapper.py)
                                    |
          3. Normalize -> Derive intent -> Score against catalog
             (ScoringEngine from architecture_scorer)
                                    |
          4. Store results in DuckDB for charting
                                    |
          5. Return structured markdown with recommendations,
             scores, Azure services, and Microsoft Learn links
                                    |
                                    v
        Agent presents: KPI tiles, narrative, bar chart, table
```

## Files

### New Files

| File | Purpose |
|------|---------|
| `agents/tools/architecture_tools.py` | Two tools: `get_architecture_recommendation` and `list_scorable_applications`. Manages catalog loading via `ConfigLoader` with identity-based auth. |
| `agents/tools/architecture_mapper.py` | Pure mapping module. Converts DataFrames from 4 DB views into a `RawContextFile`-compatible dict for the scoring engine. No tool decorators. |
| `agents/prompts/system_architect/TOOLS.md` | Prompt guidance for the System Architect persona on when to use the tool and how to present results (KPI tiles, chart, table, narrative). |

### Modified Files

| File | Change |
|------|--------|
| `agents/tools/__init__.py` | Added `architecture_toolset` import and export. |
| `agents/personas/system_architect.py` | Added `tools.architecture_toolset` to the persona's toolsets list. |
| `pyproject.toml` | Added `azure-architecture-catalog-builder` as a path dependency so `architecture_scorer` and `catalog_builder` are importable. |
| `agents/config/__init__.py` | Added `CATALOG_URL: Optional[str]` to the `agents` config class. |
| `config.example.toml` | Added `CATALOG_URL` setting with documentation. |
| `config.infra-dev.toml` | Added `CATALOG_URL` placeholder. |
| `config.infra-prod.toml` | Added `CATALOG_URL` placeholder. |

## Configuration

The catalog is loaded from Azure Blob Storage using the same identity-based authentication as the rest of the agent infrastructure.

### config.toml

```toml
[agents]
# Architecture catalog URL (HTTPS URL to architecture-catalog.json on Azure Blob Storage)
CATALOG_URL = "https://youraccount.blob.core.windows.net/catalog/architecture-catalog.json"
```

### Resolution Order

1. **`ARCHITECTURE_CATALOG_PATH` env var** — Local file path override (testing)
2. **`CATALOG_URL` from config.toml** — Standard production config
3. **`CATALOG_URL` env var** — Environment-level override
4. **Local file search** — Development fallback (project root, cwd)

### Authentication

Remote URLs are fetched via the agent's `ConfigLoader` (`llm_router.core.loader`):

- **Dev** (`MODE = "dev"`): Bearer token via `AzureCliCredential` (requires `az login`)
- **Prod** (`MODE = "prod"`): Bearer token via Azure IMDS (Managed Identity)

This is the same mechanism used for `ENDPOINTS_JSON_URL`.

## DB Column Mapping

The mapper translates Dr. Migrate database views into the scoring engine's `RawContextFile` format.

### app_overview (from application_overview view)

| RawContextFile field | DB column | Notes |
|---|---|---|
| `application` | `application` | Direct |
| `app_type` | `app_type` | e.g. "COTS/ISV", "In-House Custom Built" |
| `business_crtiticality` | `business_critical` + `inherent_risk` | "Yes" -> "High", "Extreme" -> "MissionCritical" |
| `treatment` | `assigned_migration_strategy` | e.g. "Rehost", "Refactor" |
| `description` | `app_function` | Application function description |
| `owner` | `app_owner` | Direct |

### detected_technology_running (combined from multiple sources)

- `key_software_overview.key_software` (per machine)
- `application_overview.other_tech_stack_components` (comma-separated)
- `application_overview.detected_app_components` (comma-separated)
- `application_overview.non_sql_databases` (comma-separated)
- "SQL Server" added if `sql_server_count > 0`

### server_details (from server_overview_current view)

| RawContextFile field | DB column |
|---|---|
| `machine` | `machine` |
| `environment` | `environment` |
| `OperatingSystem` | `OperatingSystem` |
| `Cores` | `Cores` |
| `MemoryGB` | `AllocatedMemoryInGB` |
| `CPUUsage` | `CPUUsageInPct` |
| `MemoryUsage` | `MemoryUsageInPct` |
| `StorageGB` | `StorageGB` |
| `AzureVMReadiness` | `CloudVMReadiness` |
| `AzureReadinessIssues` | `CloudReadinessIssues` |
| `migration_strategy` | `assigned_treatment` |
| `ip_address` | `IPAddress` (wrapped in list) |
| `detected_COTS` | `key_software` values for this machine |

### app_mod_results (from app_modernization_candidates view)

Built from `app_mod_candidate_technology` and `number_of_machines_with_tech`, enriched with `app_component_modernization_options` from application_overview.

## How Results Are Presented

The tool returns structured markdown. The System Architect agent is guided by `TOOLS.md` to present results in this order:

1. **KPI tiles** (4 metrics): Top match score, treatment, confidence, eligible architectures count
2. **Narrative**: Why the top recommendation fits, strengths, considerations, core Azure services, Microsoft Learn link
3. **Bar chart**: Architecture names vs scores (from stored DuckDB reference)
4. **Table**: Full ranked list with scores and services
5. **Runner-up**: Brief discussion of alternative and when it might be preferred

## Scope

This integration is **System Architect persona only**. Other personas (Financial Planner, Migration Engineer, etc.) do not have access to these tools.

The tool only reads from existing DB views — it does not write to the database or modify any state beyond storing chart data in the thread-scoped DuckDB instance.
