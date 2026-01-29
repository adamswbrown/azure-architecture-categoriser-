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

## Enhanced Classification (Content-Based Scoring)

The following fields are now auto-classified using **keyword scoring** from document content. All classifications are marked as `AI_SUGGESTED` and require human review.

### Gartner 8R Treatments (`supported_treatments`)

Treatments are scored based on content keywords and Azure service usage.

| Treatment | Keyword Examples | Service Boost |
|-----------|------------------|---------------|
| `rehost` | lift and shift, no code changes, migrate as-is | +2 for Virtual Machines |
| `replatform` | managed instance, minimal code changes, database migration | +2 for SQL Managed Instance, +1.5 for App Service |
| `refactor` | cloud-native, microservices, containerize | +2 for AKS/Container Apps |
| `rebuild` | greenfield, rearchitect, start from scratch | +1 for containers |
| `replace` | SaaS, third-party solution, COTS | - |
| `retain` | hybrid, on-premises, expressroute | +2 for ExpressRoute/Arc |
| `tolerate` | legacy stable, maintain status quo | - |
| `retire` | decommission, sunset, end of life | - |

**Scoring threshold**: 1.5 (configurable via `classification.treatment_threshold`)

### Gartner TIME Categories (`supported_time_categories`)

TIME categories are scored from keywords and cross-referenced with treatments.

| Category | Keyword Examples | Treatment Cross-Reference |
|----------|------------------|---------------------------|
| `invest` | greenfield, digital transformation, innovation | +2 for REBUILD, +1.5 for REFACTOR |
| `migrate` | modernization, phased approach, strangler fig | +1.5 for REHOST, +1 for REFACTOR |
| `tolerate` | minimal disruption, status quo, maintain | +1.5 for RETAIN, +1 for REHOST |
| `eliminate` | obsolete, deprecated, end of support | +1.5 for REPLACE |

**Scoring threshold**: 1.5 (configurable via `classification.time_category_threshold`)

### Operating Model (`operating_model_required`)

Operating models are scored from CI/CD and operational keywords.

| Model | Keyword Examples | Architecture Influence |
|-------|------------------|----------------------|
| `devops` | CI/CD, GitHub Actions, Terraform, GitOps | +2 for cloud_native family, +1.5 for microservices |
| `sre` | SRE, observability, SLO, mission-critical | +2 for multi-region active-active |
| `transitional` | hybrid operations, partial automation | +1 for PaaS family |
| `traditional_it` | manual operations, ITIL, CAB | +1 for IaaS family |

### Security Level (`security_level`)

Security levels are detected from compliance framework mentions.

| Level | Keyword Examples | Priority |
|-------|------------------|----------|
| `highly_regulated` | HIPAA, PCI-DSS, FedRAMP, ITAR | 1 (highest) |
| `regulated` | ISO 27001, SOC 2, GDPR, compliance | 2 |
| `enterprise` | Zero Trust, Key Vault, private endpoint | 3 |
| `basic` | standard security, default | 4 (lowest) |

**Scoring threshold**: 2 keywords required for highly_regulated/regulated, 1 for enterprise

### Cost Profile (`cost_profile`)

Cost profiles are inferred from pricing keywords and services.

| Profile | Keyword Examples | Service Inference |
|---------|------------------|-------------------|
| `cost_minimized` | consumption plan, reserved instance, spot VM | +1 for Functions/Container Apps |
| `balanced` | general purpose, standard, production | - |
| `scale_optimized` | auto-scaling, premium tier, high performance | +2 for multi-region |
| `innovation_first` | OpenAI, preview, AI, cognitive services | +2 for OpenAI/Cognitive |

### Not Suitable For (`not_suitable_for`)

Exclusions are extracted using regex patterns from document content.

**Patterns searched**:
- "not suitable for: ..."
- "avoid this pattern when: ..."
- "limitations: ..."
- "when not to use: ..."

**Mapped to ExclusionReason**:
- `greenfield_only`, `simple_workloads`, `windows_only`, `linux_only`
- `low_maturity_teams`, `regulated_workloads`, `low_budget`, `skill_constrained`

---

## Classification Configuration

```yaml
classification:
  # Gartner 8R Treatment keywords
  treatment_keywords:
    rehost:
      - lift and shift
      - no code changes
      - vm migration
    replatform:
      - managed instance
      - minimal code changes
    refactor:
      - cloud-native
      - microservices
      - containerize
    rebuild:
      - greenfield
      - rearchitect
    replace:
      - saas
      - third-party solution
    retain:
      - hybrid
      - on-premises
      - expressroute
    tolerate:
      - legacy stable
      - maintain status quo
    retire:
      - decommission
      - sunset

  # Gartner TIME category keywords
  time_category_keywords:
    invest:
      - greenfield
      - digital transformation
      - innovation
    migrate:
      - modernization
      - strangler fig
      - phased approach
    tolerate:
      - minimal disruption
      - status quo
    eliminate:
      - obsolete
      - deprecated

  # Operating model keywords
  operating_model_keywords:
    devops:
      - ci/cd
      - github actions
      - terraform
      - gitops
    sre:
      - site reliability
      - observability
      - slo
    transitional:
      - hybrid operations
      - partial automation
    traditional_it:
      - manual operations
      - itil

  # Security level keywords
  security_level_keywords:
    highly_regulated:
      - hipaa
      - pci-dss
      - fedramp
    regulated:
      - compliance
      - iso 27001
      - soc 2
    enterprise:
      - zero trust
      - key vault
      - private endpoint
    basic:
      - standard security

  # Cost profile keywords
  cost_profile_keywords:
    cost_minimized:
      - consumption plan
      - reserved instance
      - spot vm
    balanced:
      - general purpose
      - standard
    scale_optimized:
      - auto-scaling
      - premium tier
    innovation_first:
      - openai
      - cognitive services
      - ai

  # Regex patterns to extract exclusions
  not_suitable_patterns:
    - "(?:not|isn't)\\s+(?:suitable|recommended)\\s+for[:\\s]+([^.]+)"
    - "avoid.*?(?:for|when)[:\\s]+([^.]+)"
    - "limitations?[:\\s]+([^.]+)"

  # Scoring thresholds
  treatment_threshold: 1.5      # Min score for treatment selection
  time_category_threshold: 1.5  # Min score for TIME category selection
  security_score_threshold: 2   # Min keywords for regulated levels
```

---

## Filtering Options

### CLI Filter Flags

```bash
# Filter by Azure category (azureCategories from YML)
catalog-builder build-catalog --repo-path ./repo --category web

# Filter by Azure product (products from YML)
catalog-builder build-catalog --repo-path ./repo --product azure-app-service

# Filter by ms.topic
catalog-builder build-catalog --repo-path ./repo --topic reference-architecture

# Require YamlMime:Architecture files
catalog-builder build-catalog --repo-path ./repo --require-yml

# Combine filters
catalog-builder build-catalog --repo-path ./repo \
  --category web \
  --category containers \
  --topic example-scenario
```

### Filter Configuration

```yaml
filters:
  # Only include documents with these ms.topic values
  allowed_topics:
    - reference-architecture
    - example-scenario
    - solution-idea

  # Only include documents with these azureCategories
  allowed_categories: []  # Empty = all categories

  # Only include documents that use these products
  allowed_products: []    # Empty = all products

  # If true, only include documents with YamlMime:Architecture
  require_architecture_yml: false

  # Exclude documents with these ms.topic values
  excluded_topics:
    - concept-article
    - best-practice
    - include
    - hub-page
```

### Valid Azure Categories

From the Azure Architecture Center YML files:

| Category | Description |
|----------|-------------|
| `web` | Web applications |
| `ai-machine-learning` | AI and ML workloads |
| `analytics` | Analytics and BI |
| `compute` | Compute resources |
| `containers` | Container workloads |
| `databases` | Database solutions |
| `devops` | DevOps and CI/CD |
| `hybrid` | Hybrid cloud |
| `identity` | Identity and access |
| `integration` | Integration patterns |
| `iot` | IoT solutions |
| `management-and-governance` | Management |
| `media` | Media services |
| `migration` | Migration patterns |
| `networking` | Network architecture |
| `security` | Security patterns |
| `storage` | Storage solutions |

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

# List available filter values from repository
catalog-builder list-filters --repo-path ./repo

# List only products with minimum 5 documents
catalog-builder list-filters --repo-path ./repo --type products --min-count 5

# List only categories
catalog-builder list-filters --repo-path ./repo --type categories
```

---

## Hierarchical Product Filtering

Products support **prefix matching** for hierarchical filtering, similar to the Azure Architecture Center browse page.

### How It Works

When you specify `--product azure`, it matches ALL products starting with `azure-`:

```bash
# Matches: azure-kubernetes-service, azure-app-service, azure-functions, etc.
catalog-builder build-catalog --repo-path ./repo --product azure

# Matches: azure-sql-database, azure-sql-managed-instance
catalog-builder build-catalog --repo-path ./repo --product azure-sql

# Exact match only
catalog-builder build-catalog --repo-path ./repo --product azure-kubernetes-service
```

### Product Prefix Examples

| Prefix | Matches |
|--------|---------|
| `azure` | All Azure services (azure-*, ~140 products) |
| `azure-sql` | azure-sql-database, azure-sql-managed-instance, azure-sql-virtual-machines |
| `azure-virtual` | azure-virtual-machines, azure-virtual-network, azure-virtual-desktop |
| `azure-container` | azure-container-apps, azure-container-instances, azure-container-registry |
| `power` | power-apps, power-automate, power-bi, power-platform |
| `defender` | defender-for-cloud, defender-identity, defender-office365 |

### Discovering Available Filters

Use `list-filters` to see all available values:

```bash
# Show all categories, products, and topics with counts
catalog-builder list-filters --repo-path ./architecture-center

# Show products grouped by prefix
catalog-builder list-filters --repo-path ./repo --type products
```

Output includes:
- **Azure Categories**: Top-level workload types (web, containers, databases, etc.)
- **Azure Products**: Specific services with document counts
- **Product Prefixes**: Hierarchical groupings for prefix matching
- **Topics**: ms.topic values (reference-architecture, example-scenario, etc.)
