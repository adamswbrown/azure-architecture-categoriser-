# Catalog Builder Prompt v2.0

**Purpose**: Document the design intent and rules for the Azure Architecture Catalog Builder.

---

## Overview

Build a CLI tool that compiles Azure Architecture Center documentation into a structured JSON catalog. The catalog serves as input for a browser-based scoring/recommendation system.

### Architecture Separation

| Component | Role | Characteristics |
|-----------|------|-----------------|
| **Prompt 1** (this catalog builder) | Neutral catalog compiler | Explainable, deterministic, no scoring |
| **Prompt 2** (Architecture Scorer) | Scorer and recommender | Uses catalog as input |
| **Prompt 3** (Recommendations App) | Explainer and confirmer | User-facing interface |

---

## Core Principles

### 1. Clean Over Complete
- Better to lose services than include dirty/prose data
- Strict validation prevents downstream errors
- Quality markers indicate confidence level

### 2. Explainability
- Every classification includes confidence metadata
- Source attribution (filename, frontmatter, content_analysis)
- Extraction warnings surface issues

### 3. Neutrality
- No scoring or ranking in the catalog
- Classifications are descriptive, not prescriptive
- Consumer decides how to use the data

---

## Service Extraction Rules

### Allow-List Matching
Services must exactly match entries in a known Azure services whitelist (~165 services).

```python
# Examples of valid services
"Azure Kubernetes Service", "Azure Functions", "Azure SQL Database"

# Examples rejected (not in whitelist)
"Azure Kubernetes Service for microservices", "premium storage"
```

### Prose Filtering
Reject any extracted text containing sentence indicators:
- Conjunctions: "and", "or", "with", "for", "to"
- Articles preceding nouns: "a ", "an ", "the "
- Verbs: "using", "running", "deploying"
- Punctuation: periods, commas in non-list context

### Consistent Casing
All service names use canonical casing from the whitelist:
- "Azure Kubernetes Service"
- "azure kubernetes service"
- "AKS" (unless in whitelist)

### Service Classification
- **core_services**: Compute, data, networking services essential to the pattern
- **supporting_services**: Observability, security, operations services

---

## Pattern Name Rules

### Derivation Priority
1. YamlMime:Architecture `summary` field
2. Frontmatter `title` field (cleaned)
3. First H1 heading
4. Directory name (humanized)

### Cleaning Rules
- Remove "Azure" prefix (redundant)
- Remove common suffixes: "architecture", "solution", "reference"
- Truncate to 8 words maximum
- Strip leading/trailing punctuation

### Junk Name Detection
Detect and flag generic/meaningless names:

**Exact matches (case-insensitive):**
- "potential use case", "potential use cases"
- "solution idea", "solution ideas"
- "use case", "use cases"
- "scenario", "example", "overview"
- "introduction", "architecture", "diagram", "reference"

**Phrase substring matches:**
- "potential use case", "potential use cases"
- "solution idea"

**Action on junk name:**
- Add extraction warning
- Downgrade to `example_only` quality

---

## Quality Level Determination

### CatalogQuality Enum
```
curated > ai_enriched > ai_suggested > example_only
```

| Level | Criteria |
|-------|----------|
| `curated` | Has YamlMime:Architecture metadata, valid browse tags/categories |
| `ai_enriched` | Curated source enhanced with AI classifications |
| `ai_suggested` | AI-generated classifications, needs human review |
| `example_only` | Example scenarios (not reference architectures), junk names |

### Quality Downgrade Triggers
- Missing required fields: `ai_suggested`
- Junk pattern name detected: `example_only`
- Located in example-scenario paths: `example_only`
- No authoritative metadata source: `ai_suggested`

---

## Classification System

### Gartner 8R Treatments
```python
supported_treatments: list[Treatment]
# Values: retire, tolerate, rehost, replatform, refactor, replace, rebuild, retain
```

**Keyword scoring:**
| Treatment | Keywords |
|-----------|----------|
| rehost | lift and shift, no code changes, vm migration |
| replatform | minimal code changes, managed instance |
| refactor | code modernization, cloud-native, microservices |
| rebuild | greenfield, rearchitect, ground up |
| replace | saas, third-party solution |
| retain | hybrid, on-premises, expressroute, azure arc |

**Service boosting:**
| Service Pattern | Treatment Boost |
|-----------------|-----------------|
| Virtual Machines | rehost +2, retain +1 |
| AKS, Container Apps | refactor +2 |
| SQL Managed Instance | replatform +2 |
| ExpressRoute, Azure Arc | retain +2 |

### Gartner TIME Model
```python
supported_time_categories: list[TimeCategory]
# Values: tolerate, migrate, invest, eliminate
```

**Cross-reference from treatments:**
- refactor: invest, migrate
- rehost: migrate, tolerate
- HIGH complexity: invest

### Operating Model
```python
operating_model_required: OperatingModel
# Values: traditional_it, transitional, devops, sre
```

**Keyword detection:**
| Model | Keywords |
|-------|----------|
| devops | ci/cd, github actions, terraform, gitops |
| sre | site reliability, observability, slo, mission-critical |
| transitional | hybrid operations, partial automation |
| traditional_it | manual operations, change advisory board |

### Security Level
```python
security_level: SecurityLevel
# Values: basic, enterprise, regulated, highly_regulated
```

**Compliance framework detection:**
| Level | Keywords |
|-------|----------|
| highly_regulated | fedramp, hipaa, pci-dss, government |
| regulated | compliance, audit, iso 27001, soc 2, gdpr |
| enterprise | zero trust, managed identity, key vault |
| basic | standard security, default |

### Cost Profile
```python
cost_profile: CostProfile
# Values: cost_minimized, balanced, scale_optimized, innovation_first
```

**Service inference:**
| Profile | Indicators |
|---------|------------|
| innovation_first | OpenAI, Cognitive Services |
| scale_optimized | Premium tiers, high-performance |
| cost_minimized | Consumption plans, serverless |
| balanced | General purpose, standard tiers |

---

## Confidence Metadata

Every classification includes:
```python
class ClassificationMeta:
    confidence: ExtractionConfidence  # curated, high, automatic, medium, ai_suggested, low, manual_required
    source: Optional[str]  # filename, frontmatter, content_analysis, heuristic_fallback
```

### Confidence Levels
| Level | Meaning |
|-------|---------|
| curated | From authoritative source (YamlMime, browse metadata) |
| high | High confidence from content analysis |
| automatic | Extracted automatically with high confidence |
| medium | Reasonable inference |
| ai_suggested | AI-assisted, needs human review |
| low | Heuristic fallback |
| manual_required | Cannot be determined automatically |

---

## Exclusion Reasons

```python
not_suitable_for: list[ExclusionReason]
```

**Values:**
- `rehost_only`, `tolerate_only`
- `low_maturity_teams`, `low_devops_maturity`
- `vm_only_apps`, `single_vm_workloads`
- `regulated_workloads`, `low_budget`, `skill_constrained`
- `greenfield_only`, `simple_workloads`
- `windows_only`, `linux_only`
- `high_latency_tolerance`, `legacy_systems`
- `no_container_experience`, `stateful_apps`

**Extraction method:**
Regex patterns searching for:
- "not suitable for..."
- "avoid when..."
- "limitations:..."

---

## Output Schema

### ArchitectureEntry
```python
{
    # Identity
    "architecture_id": str,  # Unique ID from path
    "name": str,  # Human-readable name
    "pattern_name": str,  # Normalized pattern name
    "description": str,  # Brief description
    "source_repo_path": str,  # Path in source repository
    "learn_url": Optional[str],  # Microsoft Learn URL

    # Browse Metadata
    "browse_tags": list[str],  # From YML
    "browse_categories": list[str],  # From YML

    # Classification
    "family": ArchitectureFamily,  # foundation, iaas, paas, cloud_native, data, integration, specialized
    "workload_domain": WorkloadDomain,  # web, data, integration, security, ai, infrastructure, general

    # Architectural Expectations
    "expected_runtime_models": list[RuntimeModel],  # monolith, n_tier, api, microservices, event_driven, batch, mixed, unknown
    "expected_characteristics": ExpectedCharacteristics,  # containers, stateless, devops_required, ci_cd_required, private_networking_required

    # Change Models
    "supported_treatments": list[Treatment],  # Gartner 8R
    "supported_time_categories": list[TimeCategory],  # TIME model

    # Operational
    "availability_models": list[AvailabilityModel],
    "security_level": SecurityLevel,
    "operating_model_required": OperatingModel,
    "cost_profile": CostProfile,
    "complexity": Complexity,

    # Exclusions
    "not_suitable_for": list[ExclusionReason],

    # Azure Services
    "core_services": list[str],
    "supporting_services": list[str],

    # Metadata
    "diagram_assets": list[str],
    "catalog_quality": CatalogQuality,
    "extraction_warnings": list[str],

    # Confidence metadata for each classification field
    "*_confidence": ClassificationMeta
}
```

### ArchitectureCatalog
```python
{
    "version": "1.0.0",
    "generated_at": datetime,
    "source_repo": str,
    "source_commit": Optional[str],
    "generation_settings": GenerationSettings,  # Filter settings used
    "total_architectures": int,
    "architectures": list[ArchitectureEntry]
}
```

### GenerationSettings
```python
{
    "allowed_topics": list[str],  # e.g., ["reference-architecture", "example-scenario"]
    "allowed_products": Optional[list[str]],  # Product filters
    "allowed_categories": Optional[list[str]],  # Category filters
    "require_architecture_yml": bool,  # YamlMime:Architecture required
    "exclude_examples": bool  # Exclude example scenarios
}
```

---

## Expected Output Metrics (v2.0)

| Metric | Expected Value |
|--------|----------------|
| Total architectures | ~170 |
| Curated entries | ~40-50 |
| AI enriched | ~1-5 |
| AI suggested | ~5-15 |
| Example only | ~100-130 |
| Unique services | ~90 |
| Junk names flagged | ~10-20 |

---

## CLI Usage

### Entry Points

```bash
# Install
pip install -e ".[dev]"

# Build catalog
catalog-builder build-catalog \
    --repo-path /path/to/architecture-center \
    --out /path/to/catalog.json \
    --verbose

# Show catalog stats
catalog-builder stats --catalog /path/to/catalog.json

# Inspect specific family
catalog-builder inspect --catalog /path/to/catalog.json --family cloud_native

# Validate catalog
catalog-builder validate --catalog /path/to/catalog.json
```

### Configuration

```yaml
# catalog-config.yaml
detection:
  require_architecture_yml: false
  exclude_examples: false

filtering:
  allowed_topics:
    - reference-architecture
    - example-scenario
    - solution-idea
  allowed_products: null  # All products
  allowed_categories: null  # All categories

classification:
  domain_keywords:
    web: ["web app", "api", "frontend"]
    data: ["analytics", "data lake", "warehouse"]
```

---

## GUI Application

A Streamlit GUI is available for visual catalog configuration:

```bash
# Start Catalog Builder GUI (port 8502)
./bin/start-catalog-builder-gui.sh

# Or directly
streamlit run src/catalog_builder_gui/app.py --server.port 8502
```

### Features
- Repository cloning with git
- Filter presets (Quick Build, Full Build)
- Keyword dictionary editor
- Preview before generation
- YAML config export

---

## Security Considerations

The catalog builder includes security hardening:

### Path Validation
```python
from architecture_recommendations_app.utils.sanitize import (
    safe_path, validate_repo_path, validate_output_path, PathValidationError
)

# Validate repository path
is_valid, message, path = validate_repo_path(user_repo_path)

# Validate output path
is_valid, message, path = validate_output_path(user_output_path)
```

### Protections
- **Null byte rejection**: Paths with `\x00` are rejected
- **Path traversal prevention**: `../` sequences are blocked
- **Base directory containment**: Paths must stay within allowed directories
- **Existence validation**: Required paths must exist

---

## Docker Support

```bash
# Build image
docker build -t azure-architecture-categoriser .

# Run with docker-compose
docker compose up -d

# Access Catalog Builder GUI
open http://localhost:8502
```

---

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run catalog builder tests
pytest tests/test_catalog_builder.py -v

# With coverage
pytest tests/ --cov=src/ --cov-report=html
```

### Test Coverage
- 24 tests in `test_catalog_builder.py`
- Markdown parsing, architecture detection, metadata extraction
- Enhanced classification (treatment, security, operating model, cost)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-29 | Initial release with clean services, junk name detection, enhanced classifications |
| 2.0 | 2026-01-31 | Added GUI application, path security, Docker support, GenerationSettings schema |

---

## Dependencies

### Core
- `click>=8.1.0` - CLI framework
- `pydantic>=2.0.0` - Data validation
- `pyyaml>=6.0` - YAML parsing
- `rich>=13.0.0` - Terminal UI
- `gitpython>=3.1.0` - Git operations

### GUI
- `streamlit>=1.30.0` - Web UI framework

---

## Related Documents

- [Architecture Scorer Prompt](architecture-scorer-prompt-v1.md) - Scoring engine design
- [Recommendations App Prompt](recommendations-app-prompt-v1.md) - Web app design
- [Catalog Comparison](../catalog-comparison.md) - Quick vs Full build options
- [Scoring Weights ADR](decisions/0001-scoring-weights.md) - Weight decisions
