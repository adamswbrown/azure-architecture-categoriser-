# Azure Architecture Catalog Builder

A CLI tool that compiles Azure Architecture Center documentation into a structured architecture catalog.

## Purpose

This tool runs at **build time only**. It does NOT perform scoring, read application data, or produce recommendations. Its only responsibility is to create a static catalog describing architecture patterns and their architectural intent.

The output (`architecture-catalog.json`) is designed to be consumed by browser-based applications for runtime architecture matching.

## Installation

```bash
# Clone this repository
git clone https://github.com/adamswbrown/azure-architecture-categoriser-.git
cd azure-architecture-categoriser-

# Install the package
pip install -e .
```

## Usage

### Build the Catalog

```bash
# Clone the Azure Architecture Center repository
git clone https://github.com/MicrosoftDocs/architecture-center.git

# Build the catalog
catalog-builder build-catalog \
  --repo-path ./architecture-center \
  --out architecture-catalog.json
```

### Inspect the Catalog

```bash
# List all architectures
catalog-builder inspect --catalog architecture-catalog.json

# Filter by family
catalog-builder inspect --catalog architecture-catalog.json --family cloud_native

# View specific architecture details
catalog-builder inspect --catalog architecture-catalog.json --id example-scenario-web-app-baseline
```

### View Statistics

```bash
catalog-builder stats --catalog architecture-catalog.json
```

## Catalog Schema

Each architecture entry includes:

### Identity
- `architecture_id`: Unique identifier derived from path
- `name`: Architecture name/title
- `description`: Brief description
- `source_repo_path`: Path in source repository
- `learn_url`: Microsoft Learn URL

### Classification
- `family`: foundation, iaas, paas, cloud_native, data, integration, specialized
- `workload_domain`: web, data, integration, security, ai, infrastructure, general

### Architectural Expectations
- `expected_runtime_models`: monolith, n_tier, api, microservices, event_driven, batch, mixed, unknown
- `expected_characteristics`: containers, stateless, devops_required, ci_cd_required, private_networking_required

### Supported Change Models (Manual Only)
- `supported_treatments`: retire, tolerate, rehost, replatform, refactor, replace
- `supported_time_categories`: tolerate, migrate, invest, eliminate

### Operational Expectations
- `availability_models`: single_region, zone_redundant, multi_region_active_passive, multi_region_active_active
- `security_level`: basic, enterprise, regulated, highly_regulated
- `operating_model_required`: traditional_it, transitional, devops, sre

### Cost & Complexity
- `cost_profile`: cost_minimized, balanced, scale_optimized, innovation_first
- `complexity`: implementation (low/medium/high), operations (low/medium/high)

### Exclusion Rules (Manual Only)
- `not_suitable_for`: rehost_only, tolerate_only, low_maturity_teams, vm_only_apps, regulated_workloads, low_budget, skill_constrained

### Metadata
- `azure_services_used`: List of Azure services referenced
- `diagram_assets`: Paths to architecture diagrams
- `last_repo_update`: Last modification date from git

## Automation vs Manual

### Automatically Extracted
- Title, description, repo path
- Diagrams and Azure services
- Learn URL

### AI-Assisted (Human Review Required)
- Runtime model suggestions
- Complexity ratings
- Availability depth

### Manual Only
- `supported_treatments`
- `supported_time_categories`
- `operating_model_required`
- Exclusion rules

## Detection Heuristics

Architecture candidates are identified by:

1. **Location**: Files in `docs/example-scenario/`, workload domain folders
2. **Diagrams**: Contains SVG or PNG architecture diagrams
3. **Sections**: Contains Architecture, Components, or Diagram sections
4. **Keywords**: References "reference architecture", "baseline architecture", "solution idea"

### Excluded Content
- `docs/guide/` - Conceptual guidance
- Pattern descriptions
- Icons, templates, includes

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with verbose output
catalog-builder build-catalog --repo-path ./architecture-center --out catalog.json -v
```

## Core Principles

1. **This tool produces knowledge, not decisions**
2. **Output is deterministic and versionable**
3. **Catalog is consumable entirely client-side**
4. **Architecture intent must be explicit and explainable**

## License

MIT
