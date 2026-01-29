# Configuration Reference

All settings are now managed through a single YAML configuration file.

---

## Quick Start

```bash
# Generate default config file
catalog-builder init-config --out catalog-config.yaml

# Edit the config file
vim catalog-config.yaml

# Build catalog with custom config
catalog-builder build-catalog --repo-path ./architecture-center --config catalog-config.yaml
```

---

## Configuration File Locations

The CLI automatically searches for config files in this order:

1. `CATALOG_CONFIG` environment variable
2. `./catalog-config.yaml`
3. `./catalog-config.yml`
4. `./.catalog-config.yaml`
5. `~/.config/catalog-builder/config.yaml`

Or specify explicitly with `--config`:

```bash
catalog-builder build-catalog --repo-path ./repo --config my-config.yaml
```

---

## Configuration Structure

```yaml
detection:
  include_folders: [...]      # Folders to scan
  exclude_folders: [...]      # Folders to skip
  exclude_files: [...]        # Files to skip
  architecture_sections: [...] # Section names indicating architecture
  architecture_keywords: [...] # Regex patterns for detection
  diagram_patterns: [...]     # Patterns for finding diagrams
  folder_score: 0.3           # Confidence boost for included folders
  diagram_score: 0.3          # Confidence boost for diagrams
  section_score: 0.2          # Confidence boost for sections
  keyword_score: 0.2          # Confidence boost for keywords
  frontmatter_score: 0.1      # Confidence boost for frontmatter
  min_confidence: 0.4         # Minimum score to be an architecture
  min_signals: 2              # Minimum number of signals required

classification:
  domain_keywords:            # Keywords for workload domains
    web: [...]
    data: [...]
    integration: [...]
    security: [...]
    ai: [...]
    infrastructure: [...]
  family_keywords:            # Keywords for architecture families
    foundation: [...]
    iaas: [...]
    paas: [...]
    cloud_native: [...]
    data: [...]
    integration: [...]
    specialized: [...]
  runtime_keywords:           # Keywords for runtime models
    microservices: [...]
    event_driven: [...]
    api: [...]
    n_tier: [...]
    batch: [...]
    monolith: [...]
  availability_keywords:      # Keywords for availability models
    multi_region_active_active: [...]
    multi_region_active_passive: [...]
    zone_redundant: [...]

services:
  detection_patterns: [...]   # Regex patterns to find Azure services
  normalizations:             # Map abbreviations to canonical names
    aks: Azure Kubernetes Service
    vm: Azure Virtual Machines
    ...

urls:
  learn_base_url: https://learn.microsoft.com/en-us/azure/architecture
```

---

## Detection Settings

### include_folders

Folders that are scanned for architecture content. Files in these folders get a confidence boost.

```yaml
detection:
  include_folders:
    - docs/example-scenario
    - docs/web-apps
    - docs/data
    - docs/solution-ideas
    # Add your custom folders
    - docs/my-custom-folder
```

### exclude_folders

Folders that are never scanned (conceptual content, templates, etc.).

```yaml
detection:
  exclude_folders:
    - docs/guide
    - docs/best-practices
    - docs/patterns
    # Add folders to exclude
    - docs/drafts
```

### exclude_files

Specific filenames that are always skipped.

```yaml
detection:
  exclude_files:
    - index.md
    - toc.yml
    - toc.md
    - readme.md
    - changelog.md
```

### architecture_keywords

Regex patterns that indicate architecture content. These are case-insensitive.

```yaml
detection:
  architecture_keywords:
    - reference\s+architecture
    - baseline\s+architecture
    - solution\s+idea
    # Add custom patterns
    - my\s+custom\s+pattern
```

### Detection Thresholds

```yaml
detection:
  min_confidence: 0.4    # Minimum total score (0.0-1.0)
  min_signals: 2         # Minimum number of matching signals

  # Score weights
  folder_score: 0.3      # In included folder
  diagram_score: 0.3     # Has architecture diagrams
  section_score: 0.2     # Has architecture sections
  keyword_score: 0.2     # Contains keywords
  frontmatter_score: 0.1 # Frontmatter indicates architecture
```

---

## Classification Settings

### Workload Domain Keywords

Keywords used to suggest the `workload_domain` field.

```yaml
classification:
  domain_keywords:
    web:
      - web app
      - website
      - frontend
      - spa
    data:
      - data warehouse
      - data lake
      - analytics
    # Add custom keywords
    ai:
      - machine learning
      - openai
      - gpt
      - llm
```

### Architecture Family Keywords

Keywords used to suggest the `family` field.

```yaml
classification:
  family_keywords:
    cloud_native:
      - kubernetes
      - aks
      - container
      - microservice
      - serverless
    iaas:
      - virtual machine
      - vm
      - lift and shift
```

---

## Service Settings

### Azure Service Normalizations

Map common abbreviations to canonical Azure service names.

```yaml
services:
  normalizations:
    aks: Azure Kubernetes Service
    vm: Azure Virtual Machines
    cosmos db: Azure Cosmos DB
    # Add custom mappings
    my-service: Azure My Custom Service
```

### Detection Patterns

Regex patterns to find Azure services in content.

```yaml
services:
  detection_patterns:
    - Azure\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)
    - (App\s+Service|Functions?|Cosmos\s+DB)
    # Add custom patterns
    - (My\s+Custom\s+Service)
```

---

## URL Settings

```yaml
urls:
  learn_base_url: https://learn.microsoft.com/en-us/azure/architecture
```

---

## Example: Custom Configuration

```yaml
# catalog-config.yaml

detection:
  # Only scan specific folders
  include_folders:
    - docs/example-scenario
    - docs/reference-architectures

  # Lower the detection threshold
  min_confidence: 0.3
  min_signals: 1

classification:
  # Add custom domain keywords
  domain_keywords:
    ai:
      - machine learning
      - openai
      - gpt
      - llm
      - copilot
      - semantic kernel

services:
  # Add custom service normalizations
  normalizations:
    openai: Azure OpenAI Service
    semantic kernel: Semantic Kernel
    copilot: Microsoft Copilot
```

---

## Manual-Only Fields

These fields cannot be auto-detected and must be set by editing the output JSON:

| Field | Description |
|-------|-------------|
| `supported_treatments` | retire, tolerate, rehost, replatform, refactor, replace |
| `supported_time_categories` | tolerate, migrate, invest, eliminate |
| `operating_model_required` | traditional_it, transitional, devops, sre |
| `not_suitable_for` | Exclusion rules for the architecture |
| `cost_profile` | cost_minimized, balanced, scale_optimized, innovation_first |
| `security_level` | basic, enterprise, regulated, highly_regulated |

---

## CLI Reference

```bash
# Generate default config
catalog-builder init-config --out catalog-config.yaml

# Build with config
catalog-builder build-catalog --repo-path ./repo --config catalog-config.yaml

# Build with auto-discovered config
# (searches for catalog-config.yaml in current directory)
catalog-builder build-catalog --repo-path ./repo
```
