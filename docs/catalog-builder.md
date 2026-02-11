---
layout: default
title: Catalog Builder
---

# Catalog Builder

The Catalog Builder compiles Azure Architecture Center documentation into a structured architecture catalog that can be used for matching applications to recommended architectures.

## Overview

This is a **build-time tool** that:
- Parses the Azure Architecture Center repository
- Extracts architecture patterns, services, and metadata
- Produces a deterministic, versionable `architecture-catalog.json`

The catalog is consumed by the [Architecture Recommendations App](./recommendations-app.md) for runtime scoring.

## Installation

```bash
# Clone the repository
git clone https://github.com/adamswbrown/azure-architecture-categoriser-.git
cd azure-architecture-categoriser-

# Install the package
pip install -e .
```

## Quick Start

```bash
# 1. Clone the Azure Architecture Center repository
git clone https://github.com/MicrosoftDocs/architecture-center.git

# 2. Build the catalog
catalog-builder build-catalog \
  --repo-path ./architecture-center \
  --out architecture-catalog.json

# 3. Inspect the results
catalog-builder stats --catalog architecture-catalog.json
```

## CLI Commands

### build-catalog

Build the architecture catalog from source documentation.

```bash
catalog-builder build-catalog \
  --repo-path ./architecture-center \
  --out architecture-catalog.json
```

**Options:**
| Option | Description |
|--------|-------------|
| `--repo-path` | Path to cloned architecture-center repository |
| `--out` | Output file path (default: `architecture-catalog.json`) |
| `--category` | Filter by Azure category (e.g., `containers`) |
| `--product` | Filter by Azure product (supports prefix matching) |
| `--require-yml` | Only include files with YamlMime:Architecture metadata |
| `--upload-url` | Azure Blob Storage SAS URL to upload the catalog after building (env: `CATALOG_BLOB_URL`) |
| `-v, --verbose` | Enable verbose output |

### list-filters

Show available filter values from the repository.

```bash
catalog-builder list-filters --repo-path ./architecture-center
```

**Options:**
| Option | Description |
|--------|-------------|
| `--type` | Filter type: `categories`, `products`, or `all` |
| `--min-count` | Only show values with N+ documents |

### inspect

Inspect catalog contents.

```bash
# List all architectures
catalog-builder inspect --catalog architecture-catalog.json

# Filter by family
catalog-builder inspect --catalog architecture-catalog.json --family cloud_native

# View specific architecture
catalog-builder inspect --catalog architecture-catalog.json --id example-scenario-aks-baseline
```

### stats

Display catalog statistics.

```bash
catalog-builder stats --catalog architecture-catalog.json
```

### upload

Upload a catalog JSON file to Azure Blob Storage. Supports SAS URL, connection string, and DefaultAzureCredential authentication.

```bash
# Upload with SAS URL
catalog-builder upload \
  --catalog architecture-catalog.json \
  --blob-url "https://acct.blob.core.windows.net/catalogs/catalog.json?sv=..."

# Upload with connection string
catalog-builder upload \
  --catalog architecture-catalog.json \
  --connection-string "DefaultEndpointsProtocol=https;..." \
  --container-name catalogs

# Upload with DefaultAzureCredential
catalog-builder upload \
  --catalog architecture-catalog.json \
  --account-url "https://acct.blob.core.windows.net"
```

See [Blob Storage Upload](./blob-storage-upload.md) for full details, CI/CD examples, and troubleshooting.

### init-config

Generate a default configuration file.

```bash
catalog-builder init-config --out catalog-config.yaml
```

## GUI Mode

A graphical interface is also available for building and inspecting catalogs:

```bash
# Install GUI dependencies
pip install -e ".[gui]"

# Launch the GUI (macOS/Linux)
./bin/start-catalog-builder-gui.sh

# Launch the GUI (Windows PowerShell)
.\bin\start-catalog-builder-gui.ps1
```

![Catalog Builder GUI](images/catalog-builder-gui.png)

The GUI provides:
- **Repository Configuration** - Point to your local Azure Architecture Center clone
- **Quick Generate** - One-click catalog generation with default settings
- **Custom Build** - Fine-tune filters by category, product, and quality requirements
- **Progress Tracking** - Visual feedback during catalog generation
- **Architecture Browsing** - Inspect individual entries in the generated catalog
- **Quality Statistics** - View distribution of curated vs AI-enriched entries
- **Export Options** - Save catalogs in different formats

## Catalog Schema

Each architecture entry includes:

### Identity
| Field | Description |
|-------|-------------|
| `architecture_id` | Unique identifier derived from path |
| `name` | Human-readable architecture name |
| `pattern_name` | Normalized pattern name |
| `description` | Brief description |
| `source_repo_path` | Path in source repository |
| `learn_url` | Microsoft Learn URL |

### Classification
| Field | Description |
|-------|-------------|
| `family` | foundation, iaas, paas, cloud_native, data, integration, specialized |
| `workload_domain` | web, data, integration, security, ai, infrastructure, general |
| `catalog_quality` | curated, ai_enriched, ai_suggested, example_only |

### Architectural Expectations
| Field | Description |
|-------|-------------|
| `expected_runtime_models` | monolith, n_tier, api, microservices, event_driven, batch, mixed |
| `expected_characteristics` | containers, stateless, devops_required, ci_cd_required, private_networking_required |

### Supported Change Models
| Field | Description |
|-------|-------------|
| `supported_treatments` | Gartner 8R: retire, tolerate, rehost, replatform, refactor, replace, rebuild, retain |
| `supported_time_categories` | TIME model: tolerate, migrate, invest, eliminate |

### Operational Expectations
| Field | Description |
|-------|-------------|
| `availability_models` | single_region, zone_redundant, multi_region_active_passive, multi_region_active_active |
| `security_level` | basic, enterprise, regulated, highly_regulated |
| `operating_model_required` | traditional_it, transitional, devops, sre |

### Azure Services
| Field | Description |
|-------|-------------|
| `core_services` | Required Azure services (compute, data, networking) |
| `supporting_services` | Supporting services (monitoring, security, operations) |

### Assets
| Field | Description |
|-------|-------------|
| `diagram_assets` | Paths to architecture diagram images |
| `browse_tags` | Tags for filtering |
| `browse_categories` | Categories for classification |

## Quality Levels

| Level | Source | Description |
|-------|--------|-------------|
| **curated** | YamlMime:Architecture | Authoritative metadata from Microsoft |
| **ai_enriched** | Partial authoritative | Some metadata curated, rest inferred |
| **ai_suggested** | Content analysis | All metadata extracted by AI |
| **example_only** | Example scenarios | Not prescriptive reference architectures |

## Document Types and Filtering

The Azure Architecture Center contains three main document types, identified by the `ms.topic` metadata field:

| Type | Description | Count | Default |
|------|-------------|-------|---------|
| **reference-architecture** | Curated, production-ready patterns designed for enterprise workloads | ~50 | ✅ Included |
| **example-scenario** | Real-world implementation examples showing specific use cases | ~100 | ❌ Excluded |
| **solution-idea** | Conceptual designs and starting points for solutions | ~80 | ❌ Excluded |

### Why Reference Architectures Only (Default)

By default, the catalog builder includes **only reference architectures**. This was a deliberate design choice:

1. **Production-Ready**: Reference architectures are Microsoft's curated, vetted patterns suitable for enterprise production workloads
2. **Higher Quality Metadata**: These documents have richer, more consistent metadata (YamlMime:Architecture)
3. **Better Recommendations**: Fewer, higher-quality entries produce more confident and relevant recommendations
4. **Enterprise Focus**: Organizations seeking architecture guidance typically need production-ready patterns, not conceptual examples

### When to Include Examples and Solution Ideas

You may want to include example scenarios and solution ideas when:

- **Broader Exploration**: Discovering a wider range of Azure patterns and possibilities
- **Learning**: Understanding different approaches to similar problems
- **Proof of Concept**: Building POCs where production-readiness is less critical
- **Niche Workloads**: Finding patterns for specialized use cases not covered by reference architectures
- **Inspiration**: Generating ideas before committing to a specific architecture

### How to Change the Filter

**GUI Method (Recommended):**
1. Open the Catalog Builder GUI: `./bin/start-catalog-builder-gui.sh`
2. Navigate to the **Filter Presets** tab
3. Under **Quality Presets**, click **"Examples Included"**
4. Build your catalog with the updated filter

**CLI Method:**
```bash
# Include all document types
catalog-builder build-catalog \
  --repo-path ./architecture-center \
  --topic reference-architecture \
  --topic example-scenario \
  --topic solution-idea \
  --out catalog-with-examples.json
```

**Configuration File Method:**
```yaml
# catalog-config.yaml
filters:
  allowed_topics:
    - reference-architecture
    - example-scenario
    - solution-idea
```

### Catalog Size Comparison

| Configuration | Architectures | Use Case |
|---------------|---------------|----------|
| Reference only (default) | ~50 | Production recommendations |
| + Example scenarios | ~150 | Learning and exploration |
| + Solution ideas | ~230 | Maximum coverage |

## Detection Heuristics

Architecture candidates are identified by:

1. **YamlMime:Architecture** - Files with paired `.yml` metadata (highest confidence)
2. **Location** - Files in `docs/example-scenario/`, workload domain folders
3. **Diagrams** - Contains SVG or PNG architecture diagrams
4. **Sections** - Contains Architecture, Components, or Diagram sections
5. **Keywords** - References "reference architecture", "baseline architecture", "solution idea"

### Excluded Content
- Non-architecture layouts (hub pages, landing pages, tutorials)
- `docs/guide/` - Conceptual guidance
- Pattern descriptions without implementations
- Icons, templates, includes
- Very short content with no diagrams
- High link density pages (navigation pages)

## Configuration

See [configuration.md](./configuration.md) for the full configuration reference.

## Example Output

```json
{
  "architecture_id": "example-scenario-aks-baseline",
  "name": "Enterprise-grade AKS Cluster With Private Networking And Ingress",
  "pattern_name": "Enterprise-grade AKS Cluster With Private Networking And Ingress",
  "catalog_quality": "curated",
  "family": "cloud_native",
  "workload_domain": "infrastructure",
  "expected_runtime_models": ["microservices"],
  "expected_characteristics": {
    "containers": "true",
    "stateless": "optional",
    "devops_required": true,
    "ci_cd_required": true,
    "private_networking_required": true
  },
  "supported_treatments": ["refactor", "rebuild"],
  "operating_model_required": "devops",
  "security_level": "enterprise",
  "core_services": ["Azure Kubernetes Service", "Azure Container Registry"],
  "browse_tags": ["Azure", "Containers"]
}
```

## Related Documentation

- [Reviewing the Catalog](./reviewing-the-catalog.md) - How to review and validate catalogs
- [Architecture Recommendations App](./recommendations-app.md) - Customer-facing web application
- [Architecture Scorer](./architecture-scorer.md) - Scoring engine documentation
- [Configuration Reference](./configuration.md) - Full configuration options
