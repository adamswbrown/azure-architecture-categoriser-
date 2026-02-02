# Configuration Reference

This document covers configuration for both the **Catalog Builder** and **Architecture Scorer**.

## Components with Configuration

| Component | Config File | Generate Command |
|-----------|-------------|------------------|
| Catalog Builder | `catalog-config.yaml` | `catalog-builder init-config` |
| Architecture Scorer | `scorer-config.yaml` | `architecture-scorer init-config` |

---

# Architecture Scorer Configuration

The scorer configuration controls how applications are matched to architectures.

## Quick Start - Scorer

```bash
# Generate default config file
architecture-scorer init-config --out scorer-config.yaml

# Edit the config file
vim scorer-config.yaml

# Score with custom config (auto-detected if in current directory)
architecture-scorer score --catalog catalog.json --context app.json
```

## Scorer Config File Locations

The scorer searches for config in this order:

1. `ARCHITECTURE_SCORER_CONFIG` environment variable
2. `./scorer-config.yaml`
3. `./scorer-config.yml`
4. `~/.config/architecture-scorer/config.yaml`

## Scorer Configuration Structure

```yaml
# scorer-config.yaml

scoring_weights:
  treatment_alignment: 0.20      # Migration treatment match weight
  runtime_model_compatibility: 0.10  # Runtime model match
  platform_compatibility: 0.15    # Platform/technology match
  app_mod_recommended: 0.10       # Boost for App Mod recommended
  service_overlap: 0.10           # Service overlap weight
  browse_tag_overlap: 0.05        # Browse tag match weight
  availability_alignment: 0.10    # Availability requirements
  operating_model_fit: 0.08       # Operational maturity match
  complexity_tolerance: 0.07      # Complexity vs capability
  cost_posture_alignment: 0.05    # Cost strategy match

quality_weights:
  curated: 1.0                    # Weight for curated architectures
  ai_enriched: 0.95              # Weight for AI-enriched
  ai_suggested: 0.90             # Weight for AI-suggested
  example_only: 0.85             # Weight for examples

confidence_thresholds:
  high_score_threshold: 60.0     # Min score for "High" confidence
  medium_score_threshold: 50.0   # Min score for "Medium" confidence (changed from 40.0)
  high_penalty_limit: 0.10       # Max penalty for "High" confidence
  medium_penalty_limit: 0.20     # Max penalty for "Medium" confidence
  high_max_low_signals: 1        # Max low-confidence signals for "High"
  medium_max_low_signals: 3      # Max low-confidence signals for "Medium"
  high_max_assumptions: 2        # Max assumptions for "High"

question_generation:
  question_threshold: low        # Generate questions for signals at/below
  max_questions: 5               # Maximum questions to generate
```

## Scoring Weights Explained

| Weight | Description | Range |
|--------|-------------|-------|
| `treatment_alignment` | How well the migration treatment (rehost, replatform, refactor) matches the architecture's supported treatments | 0.0-1.0 |
| `runtime_model_compatibility` | How well the expected runtime model (microservices, n-tier, serverless) matches | 0.0-1.0 |
| `platform_compatibility` | Technology/platform compatibility based on App Mod assessment | 0.0-1.0 |
| `app_mod_recommended` | Boost when App Mod explicitly recommends the target platform | 0.0-1.0 |
| `service_overlap` | Overlap between required services and architecture services | 0.0-1.0 |
| `browse_tag_overlap` | Match on browse/topic tags | 0.0-1.0 |
| `availability_alignment` | How well availability requirements align | 0.0-1.0 |
| `operating_model_fit` | Alignment between team maturity and required operating model | 0.0-1.0 |
| `complexity_tolerance` | Match between complexity and team capability | 0.0-1.0 |
| `cost_posture_alignment` | Alignment with cost optimization strategy | 0.0-1.0 |

**Note:** Weights should sum to approximately 1.0 for normalized scoring.

## Confidence Threshold Tuning

The confidence level (High/Medium/Low) is determined by multiple factors:

**High Confidence** requires ALL of:
- Match score >= `high_score_threshold`
- Confidence penalty < `high_penalty_limit`
- Low-confidence signals <= `high_max_low_signals`
- Assumptions <= `high_max_assumptions`

**Medium Confidence** requires ALL of:
- Match score >= `medium_score_threshold`
- Confidence penalty < `medium_penalty_limit`
- Low-confidence signals <= `medium_max_low_signals`

**Low Confidence**: Everything else.

### Tuning Examples

**More permissive (show more "High" confidence):**
```yaml
confidence_thresholds:
  high_score_threshold: 50.0     # Lower from 60
  high_max_low_signals: 2        # Allow more uncertain signals
  high_max_assumptions: 4        # Allow more assumptions
```

**More strict (higher bar for "High" confidence):**
```yaml
confidence_thresholds:
  high_score_threshold: 75.0     # Raise from 60
  high_penalty_limit: 0.05       # Lower penalty tolerance
  high_max_low_signals: 0        # Require all high-confidence signals
```

---

# Catalog Builder Configuration

For the complete design specification, see [design/catalog-builder-prompt-v1.md](design/catalog-builder-prompt-v1.md).

---

## Quick Start - Catalog Builder

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

### Azure Services Whitelist

The catalog uses a **known Azure services whitelist** to ensure only clean, validated service names are included. This prevents prose, sentences, and unrecognized text from polluting the `core_services` and `supporting_services` fields.

**Sanitization Rules:**
1. **Strip prose**: Everything after newlines, clause markers (`that`, `which`, `to`, `for`, `and`, `with`) is removed
2. **Word limit**: Entries with more than 6 words are dropped
3. **Whitelist validation**: Only services matching the known Azure services list are included
4. **Clean over complete**: It's better to lose services than include dirty data

**Included Service Categories:**
- Compute: App Service, Functions, AKS, Container Apps, VMs, Batch, Service Fabric
- Databases: SQL Database, Cosmos DB, PostgreSQL, MySQL, Redis
- Storage: Blob, Files, Queue, Data Lake, NetApp Files
- Networking: Virtual Network, Load Balancer, Application Gateway, Front Door, Firewall, ExpressRoute, VPN Gateway, Bastion, Private Link
- Integration: API Management, Logic Apps, Service Bus, Event Hubs, Event Grid
- Security: Key Vault, DDoS Protection, Defender, Sentinel
- Monitoring: Monitor, Application Insights, Log Analytics
- Analytics: Synapse, Databricks, Data Factory, Data Explorer, Stream Analytics
- AI/ML: OpenAI Service, Machine Learning, Cognitive Services, Bot Service
- IoT: IoT Hub, IoT Central, Digital Twins
- DevOps: Azure DevOps, GitHub, GitHub Actions

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

  # Exclude example scenarios and solution ideas (default: false)
  # Examples are learning/POC architectures, not production-ready patterns
  # Set to true for production catalogs (keeps ~50 curated architectures)
  exclude_examples: false

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

---

## Browse Metadata

The catalog extracts authoritative browse metadata from YamlMime:Architecture files.

### Browse Tags (`browse_tags`)

Browse tags are derived from the `products` field in YML files and mapped to human-readable categories.

| Product ID | Browse Tag |
|------------|------------|
| `azure-kubernetes-service` | Containers |
| `azure-container-apps` | Containers |
| `azure-app-service` | Web |
| `azure-functions` | Serverless |
| `azure-virtual-machines` | Compute |
| `azure-sql-database` | Databases |
| `azure-cosmos-db` | Databases |
| `azure-openai` | AI |
| `azure-machine-learning` | AI |
| `azure-event-hubs` | Messaging |
| `azure-service-bus` | Messaging |
| `azure-api-management` | Integration |
| `azure-key-vault` | Security |
| `azure-firewall` | Security |
| `azure-virtual-network` | Networking |
| `azure-front-door` | Networking |

All entries with products get an "Azure" base tag automatically.

### Browse Categories (`browse_categories`)

Browse categories are derived from `azureCategories` and `ms.topic` fields:

**From ms.topic**:
| Topic | Category |
|-------|----------|
| `reference-architecture` | Reference |
| `example-scenario` | Example Scenario |
| `solution-idea` | Solution Idea |

**From azureCategories**: Mapped to display names (e.g., `ai-machine-learning` → `AI + Machine Learning`).

All entries get an "Architecture" base category automatically.

---

## Catalog Quality

The `catalog_quality` field indicates the reliability of the entry's metadata:

| Quality Level | Description | Criteria |
|---------------|-------------|----------|
| `curated` | From authoritative YML metadata | Reference architectures with YamlMime:Architecture having both `azureCategories` and `products` |
| `ai_enriched` | Partial authoritative data | Has YamlMime:Architecture but missing categories or products |
| `ai_suggested` | Purely AI-extracted | No YamlMime:Architecture file found |
| `example_only` | Example scenarios | ms.topic is `example-scenario` or `solution-idea` - illustrative implementations, not prescriptive reference patterns |

### Understanding Example Scenarios

Example scenarios and solution ideas are marked as `example_only` because they are **learning/POC architectures**, not production-ready patterns. Microsoft's documentation often notes these are "not meant for production applications" and serve as "introductory setup for learning and proof of concept."

**Default Behavior:**
The catalog includes **all ~170 architectures** by default (curated + examples). Each architecture's quality level helps users understand what they're looking at.

**To exclude example scenarios (production catalogs only):**

**CLI Flag:**
```bash
# Exclude examples - keep only curated/ai_enriched/ai_suggested (~50 architectures)
catalog-builder build-catalog --repo-path ./repo --exclude-examples
```

**Config File:**
```yaml
filters:
  exclude_examples: true  # Exclude example_only architectures
```

**When to exclude examples:**
- Building production-ready recommendation catalogs
- When you only want validated, reproducible patterns
- Enterprise architecture decision frameworks

**When to include examples (default):**
- Exploring the full breadth of Azure architecture patterns
- Learning and proof-of-concept work
- Finding inspiration from real-world implementations

---

## Expected Characteristics

The `expected_characteristics` field now includes boolean flags for operational requirements:

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `containers` | true/false/optional | Whether containerization is expected |
| `stateless` | true/false/optional | Whether statelessness is expected |
| `devops_required` | boolean | DevOps practices are required |
| `ci_cd_required` | boolean | CI/CD pipeline is required |
| `private_networking_required` | boolean | Private networking is required |

### Detection Rules

**`devops_required` = true** when:
- Content mentions containers, AKS, or Kubernetes
- Content contains DevOps keywords: "ci/cd", "pipeline", "github actions", "azure devops", "gitops", "terraform"

**`ci_cd_required` = true** when:
- `devops_required` is true
- Services include: Functions, App Service, Container Apps, Logic Apps
- Content mentions deployment automation

**`private_networking_required` = true** when:
- Content mentions: "private endpoint", "private link", "vnet integration", "private network", "no public"

**`containers` = true** when:
- Services include: Kubernetes, AKS, Container Apps, Container Instances

**`stateless` = true** when:
- Content mentions: "stateless", "scale out", "horizontal scaling"
- And does NOT mention: "stateful", "session affinity", "sticky session"

---

## Pattern Name Inference

Pattern names are inferred to describe **architectural intent**, not just services.

### Format

```
[Quality/Tier] [Workload Type] with [Key Features]
```

### Quality Prefixes (Priority Order)

| Keyword in Content | Prefix |
|-------------------|--------|
| mission-critical | Mission-critical |
| enterprise-grade | Enterprise-grade |
| production-ready | Production-ready |
| highly available | Highly available |
| multi-region | Multi-region |
| zone-redundant | Zone-redundant |
| baseline | Baseline |

### Workload Type Inference

If the title is too generic, workload type is inferred from services:

| Service Pattern | Workload Type |
|-----------------|---------------|
| kubernetes, aks | AKS cluster |
| container apps | Container Apps deployment |
| app service | App Service web application |
| functions | Serverless application |
| virtual machine | VM-based workload |
| data factory, synapse | Data pipeline |
| openai, machine learning | AI/ML workload |
| event hub, service bus | Event-driven system |

### Key Features

| Keyword in Content | Feature |
|-------------------|---------|
| private endpoint, private link | private networking |
| zero trust | zero trust |
| waf | WAF |
| ingress controller, nginx | ingress |
| traffic manager, front door | global load balancing |
| active-active | active-active |
| active-passive | active-passive failover |
| geo-replication, geo-redundant | geo-redundancy |
| caching, redis | caching |
| gitops | GitOps |

### Name Post-Processing (Truncation Rules)

Pattern names are automatically cleaned to remove prose and keep them concise:

**Rule 1: Truncate before clause markers**
- `that`, `which`, `where`, `when`, `so that`, `in order to`, `designed to`, `used to`
- Example: "Web application that handles user requests" → "Web Application"

**Rule 2: Truncate before action verbs with 'to'**
- `to handle`, `to manage`, `to process`, `to support`, `to enable`, `to provide`
- Example: "API gateway to manage traffic" → "API Gateway"

**Rule 3: Word limit (max 8 words)**
- Natural break at prepositions (`and`, `or`, `using`, `through`) after 4 words
- Otherwise, truncate at 8 words
- Example: "Enterprise grade AKS cluster with private networking and GitOps and monitoring" → "Enterprise Grade AKS Cluster With Private Networking"

**Rule 4: Clean trailing artifacts**
- Remove trailing punctuation: `. , ; : - –`
- Remove trailing prepositions: `with`, `and`, `or`, `for`, `using`

### Examples

| Raw Title | Inferred Pattern Name |
|-----------|----------------------|
| "Baseline AKS architecture" | "Baseline AKS Cluster With Ingress And GitOps" |
| "Web app reference" | "Highly Available App Service Web Application With Caching" |
| "Architecture" | "Enterprise-grade AKS Cluster With Private Networking" |
| "API gateway to handle traffic from multiple regions" | "API Gateway" |
| "Container platform that provides enterprise..." | "Container Platform" |

### Junk Pattern Name Detection

Pattern names that are semantically meaningless are flagged and downgraded to `example_only` quality. This prevents generic names from polluting the scoring catalog.

**Configurable via:**
```yaml
classification:
  # Exact matches (case-insensitive) - flagged as junk
  junk_pattern_names:
    - potential use case
    - potential use cases
    - solution idea
    - solution ideas
    - use case
    - use cases
    - scenario
    - example
    - overview
    - introduction
    - architecture
    - diagram
    - reference

  # Substring matches (case-insensitive) - flagged if name contains phrase
  junk_pattern_phrases:
    - potential use case
    - potential use cases
    - solution idea
```

**Behavior:**
- Entries with junk names receive extraction warning: `Junk pattern name detected: 'X'`
- Catalog quality is automatically downgraded to `example_only`
- Junk entries are still included but should be deprioritized in scoring

**Examples of detected junk:**
- `Potential Use Case` (exact match)
- `Zone-redundant Potential Use Cases With Ingress` (contains phrase)
- `Solution Idea` (exact match)

---

## Non-Architecture Filtering

The detector automatically excludes documents that are not architecture content.

### Excluded ms.topic Values

- `article` - Generic articles
- `concept-article` - Conceptual articles
- `hub-page` - Landing/hub pages
- `landing-page` - Landing pages
- `include` - Include fragments
- `contributor-guide` - Contributor documentation
- `quickstart` - Quickstarts
- `tutorial` - Tutorials
- `how-to-guide` - How-to guides
- `overview` - Overview pages

### Excluded Layouts

- `LandingPage`
- `HubPage`
- `ContentPage`

### Excluded Title Patterns

Documents starting with:
- "What is "
- "About "
- "Introduction to "
- "Getting started"
- "Quickstart:"
- "Tutorial:"
- "How to:"
- "Browse all"
- "Index of"
- "Table of contents"

### Content-Based Exclusions

- **Very short content**: Less than 500 characters with no images
- **High link density**: More than 10 links per 1000 characters (likely navigation pages)

---

## Output Schema Reference

### Complete Entry Structure

```json
{
  "architecture_id": "string",
  "name": "string",
  "pattern_name": "string",
  "pattern_name_confidence": {
    "confidence": "curated|high|medium|ai_suggested|low|manual_required",
    "source": "string"
  },
  "description": "string",
  "source_repo_path": "string",
  "learn_url": "string",

  "browse_tags": ["string"],
  "browse_categories": ["string"],
  "catalog_quality": "curated|ai_enriched|ai_suggested|example_only",

  "family": "foundation|iaas|paas|cloud_native|data|integration|specialized",
  "family_confidence": { "confidence": "string", "source": "string" },
  "workload_domain": "web|data|integration|security|ai|infrastructure|general",
  "workload_domain_confidence": { "confidence": "string", "source": "string" },

  "expected_runtime_models": ["monolith|n_tier|api|microservices|event_driven|batch|mixed"],
  "runtime_models_confidence": { "confidence": "string", "source": "string" },

  "expected_characteristics": {
    "containers": "true|false|optional",
    "stateless": "true|false|optional",
    "devops_required": true|false,
    "ci_cd_required": true|false,
    "private_networking_required": true|false
  },

  "supported_treatments": ["retire|tolerate|rehost|replatform|refactor|replace|rebuild|retain"],
  "treatments_confidence": { "confidence": "string", "source": "string" },
  "supported_time_categories": ["tolerate|migrate|invest|eliminate"],
  "time_categories_confidence": { "confidence": "string", "source": "string" },

  "availability_models": ["single_region|zone_redundant|multi_region_active_passive|multi_region_active_active"],
  "availability_confidence": { "confidence": "string", "source": "string" },
  "security_level": "basic|enterprise|regulated|highly_regulated",
  "security_level_confidence": { "confidence": "string", "source": "string" },
  "operating_model_required": "traditional_it|transitional|devops|sre",
  "operating_model_confidence": { "confidence": "string", "source": "string" },

  "cost_profile": "cost_minimized|balanced|scale_optimized|innovation_first",
  "cost_profile_confidence": { "confidence": "string", "source": "string" },
  "complexity": {
    "implementation": "low|medium|high",
    "operations": "low|medium|high"
  },
  "complexity_confidence": { "confidence": "string", "source": "string" },

  "not_suitable_for": ["exclusion_reason"],

  "core_services": ["string"],
  "supporting_services": ["string"],
  "services_confidence": { "confidence": "string", "source": "string" },

  "diagram_assets": ["string"],
  "last_repo_update": "datetime",
  "extraction_warnings": ["string"]
}
```

### Confidence Levels

| Level | Description |
|-------|-------------|
| `curated` | From authoritative source (YML metadata) |
| `high` | High confidence from content analysis |
| `medium` | Reasonable inference |
| `ai_suggested` | AI-assisted, needs human review |
| `low` | Heuristic fallback |
| `manual_required` | Cannot be determined automatically |

---

## Design Specifications

The complete design specification for catalog generation is documented in the `docs/design/` folder:

| Version | File | Description |
|---------|------|-------------|
| v1.0 | [catalog-builder-prompt-v1.md](design/catalog-builder-prompt-v1.md) | Initial release specification |

The prompt documentation includes:
- Core principles and design philosophy
- Service extraction rules (allow-list, prose filtering)
- Pattern name inference and truncation rules
- Quality level determination criteria
- Classification keyword scoring methods
- Expected output metrics

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-29 | Initial release with clean services, junk name detection, enhanced classifications |
