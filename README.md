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

### Filter by Category or Product

```bash
# Filter by Azure category
catalog-builder build-catalog --repo-path ./repo --category containers

# Filter by Azure product (supports prefix matching)
catalog-builder build-catalog --repo-path ./repo --product azure-kubernetes

# Require YamlMime:Architecture files only
catalog-builder build-catalog --repo-path ./repo --require-yml
```

### List Available Filters

```bash
# Show all available filter values
catalog-builder list-filters --repo-path ./architecture-center

# Show only products with 5+ documents
catalog-builder list-filters --repo-path ./repo --type products --min-count 5
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
- `name`: Human-readable architecture name (workload-intent focused)
- `pattern_name`: Normalized pattern name describing architectural intent
- `description`: Brief description
- `source_repo_path`: Path in source repository
- `learn_url`: Microsoft Learn URL

### Browse Metadata (from YamlMime:Architecture)
- `browse_tags`: Tags for filtering (e.g., `["Azure", "Containers", "Web"]`)
- `browse_categories`: Categories for classification (e.g., `["Architecture", "Reference", "Containers"]`)
- `catalog_quality`: Quality level - `curated` (from YML), `ai_enriched`, or `ai_suggested`

### Classification
- `family`: foundation, iaas, paas, cloud_native, data, integration, specialized
- `workload_domain`: web, data, integration, security, ai, infrastructure, general

### Architectural Expectations
- `expected_runtime_models`: monolith, n_tier, api, microservices, event_driven, batch, mixed
- `expected_characteristics`:
  - `containers`: true/false/optional
  - `stateless`: true/false/optional
  - `devops_required`: boolean (true for AKS, Container Apps, Functions, App Service)
  - `ci_cd_required`: boolean (true for PaaS and container workloads)
  - `private_networking_required`: boolean (detected from content)

### Supported Change Models
- `supported_treatments`: retire, tolerate, rehost, replatform, refactor, replace, rebuild, retain
- `supported_time_categories`: tolerate, migrate, invest, eliminate

### Operational Expectations
- `availability_models`: single_region, zone_redundant, multi_region_active_passive, multi_region_active_active
- `security_level`: basic, enterprise, regulated, highly_regulated
- `operating_model_required`: traditional_it, transitional, devops, sre

### Cost & Complexity
- `cost_profile`: cost_minimized, balanced, scale_optimized, innovation_first
- `complexity`: implementation (low/medium/high), operations (low/medium/high)

### Exclusion Rules
- `not_suitable_for`: Scenarios where this architecture is not suitable
  - `low_devops_maturity`, `single_vm_workloads`, `no_container_experience`, `stateful_apps`
  - `greenfield_only`, `simple_workloads`, `windows_only`, `linux_only`
  - `low_maturity_teams`, `regulated_workloads`, `low_budget`, `skill_constrained`

### Metadata
- `core_services`: Azure services required to realize the pattern (compute, data, networking)
- `supporting_services`: Supporting services for observability, security, and operations
- `diagram_assets`: Paths to architecture diagrams
- `last_repo_update`: Last modification date from git

## Automation Levels

### Curated (from YamlMime:Architecture)
- Browse tags and categories
- Product associations
- Document classification (reference-architecture, example-scenario, solution-idea)

### AI-Suggested (Human Review Recommended)
- Pattern name inference
- Runtime model classification
- Treatment and TIME category suggestions
- Security level detection
- Operating model requirements
- Complexity ratings

### Detected from Content
- `devops_required`: True when containers, AKS, or DevOps keywords present
- `ci_cd_required`: True for serverless/PaaS services
- `private_networking_required`: True when private endpoint/link mentioned

## Detection Heuristics

Architecture candidates are identified by:

1. **YamlMime:Architecture**: Files with paired `.yml` metadata (highest confidence)
2. **Location**: Files in `docs/example-scenario/`, workload domain folders
3. **Diagrams**: Contains SVG or PNG architecture diagrams
4. **Sections**: Contains Architecture, Components, or Diagram sections
5. **Keywords**: References "reference architecture", "baseline architecture", "solution idea"

### Excluded Content
- Non-architecture layouts (hub pages, landing pages, tutorials)
- `docs/guide/` - Conceptual guidance
- Pattern descriptions
- Icons, templates, includes
- Very short content with no diagrams
- High link density pages (navigation pages)

## Configuration

Generate a default config file:

```bash
catalog-builder init-config --out catalog-config.yaml
```

See [CONFIGURATION.md](CONFIGURATION.md) for full configuration reference.

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with verbose output
catalog-builder build-catalog --repo-path ./architecture-center --out catalog.json -v
```

## Sample Output

```json
{
  "architecture_id": "example-scenario-aks-baseline",
  "name": "Enterprise-grade AKS Cluster With Private Networking And Ingress",
  "pattern_name": "Enterprise-grade AKS Cluster With Private Networking And Ingress",
  "pattern_name_confidence": {
    "confidence": "curated",
    "source": "yml_metadata"
  },
  "browse_tags": ["Azure", "Containers"],
  "browse_categories": ["Architecture", "Reference", "Containers"],
  "catalog_quality": "curated",
  "expected_characteristics": {
    "containers": "true",
    "stateless": "optional",
    "devops_required": true,
    "ci_cd_required": true,
    "private_networking_required": true
  },
  "family": "cloud_native",
  "workload_domain": "infrastructure",
  "expected_runtime_models": ["microservices"],
  "supported_treatments": ["refactor", "rebuild"],
  "operating_model_required": "devops",
  "security_level": "enterprise"
}
```

## Core Principles

1. **This tool produces knowledge, not decisions**
2. **Output is deterministic and versionable**
3. **Catalog is consumable entirely client-side**
4. **Architecture intent must be explicit and explainable**
5. **Human-readable names first, machine-friendly second**
6. **Curated metadata from authoritative sources when available**
7. **Clean over complete** - Better to lose services than include dirty/prose data

## Prompt Documentation

The design decisions and rules for this catalog builder are documented in the `prompts/` folder:

- [catalog-builder-prompt-v1.md](prompts/catalog-builder-prompt-v1.md) - Complete specification for v1.0 catalog generation

This prompt documentation serves as the authoritative reference for:
- Service extraction rules (allow-list matching, prose filtering)
- Pattern name inference and truncation rules
- Quality level determination criteria
- Classification keyword scoring
- Junk name detection

## Architecture

This tool is part of a three-tier architecture:

| Component | Role | Characteristics |
|-----------|------|-----------------|
| **Catalog Builder** (this tool) | Neutral catalog compiler | Explainable, deterministic, no scoring |
| **Scorer** (future) | Scoring and recommendation | Uses catalog as input |
| **Browser App** (future) | User interface | Explainability and confirmation |

## Version

**v1.0** - Initial release with:
- 171 architectures from Azure Architecture Center
- Clean Azure services extraction (allow-list validated)
- Junk pattern name detection
- Enhanced classifications (Gartner 8R, TIME model)
- Quality differentiation (curated vs example_only)

## License

MIT
