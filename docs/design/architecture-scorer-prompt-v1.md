# Architecture Scorer Prompt v2.0

**Purpose**: Document the design intent and rules for the Architecture Scoring and Recommendation Engine.

---

## Overview

Build a deterministic, explainable Architecture Scoring and Recommendation Engine that runs at RUNTIME. It evaluates application contexts against the Azure Architecture Catalog and returns ranked recommendations with clear reasoning.

### Architecture Separation

| Component | Role | Characteristics |
|-----------|------|-----------------|
| **Catalog Builder** (Prompt 1) | Neutral catalog compiler | Build-time, deterministic |
| **Scorer** (this engine) | Scoring and recommendation | Runtime, explainable |
| **Recommendations App** (Prompt 3) | User interface | Explainability and confirmation |

---

## Hard Constraints

### MUST:
- Load and trust architecture-catalog.json (version >= 1.0)
- Consume application context files from AppCatContextFileCreator
- Use App Mod results as **authoritative** feasibility signals
- Score architectures deterministically
- Explain every recommendation and exclusion

### MUST NOT:
- Crawl documentation or repositories
- Modify the architecture catalog
- Invent architectures
- Use machine learning or embeddings
- Persist customer data

---

## Input Formats

### Architecture Catalog
```json
{
  "version": "1.0.0",
  "generation_settings": {
    "allowed_topics": ["reference-architecture", "example-scenario"],
    "exclude_examples": false
  },
  "architectures": [...]
}
```

### Application Context File
```json
[{
  "app_overview": [{
    "application": "AppName",
    "app_type": "Web Application",
    "business_crtiticality": "High",
    "treatment": "Replatform"
  }],
  "detected_technology_running": ["Microsoft IIS", "ASP.NET Framework 4.7"],
  "app_approved_azure_services": [{"Microsoft IIS": "Azure App Service"}],
  "server_details": [...],
  "App Mod results": [...]
}]
```

---

## Processing Phases

### Phase 0: Load & Validate
- Validate catalog schema_version >= 1.0
- Validate context file structure
- Fail fast on invalid input

### Phase 1: Normalize Application Signals
Extract and normalize from context:

**From app_overview:**
- application_name
- business_criticality (Low, Medium, High, MissionCritical)
- declared_treatment (Gartner 8R)
- app_type

**From server_details:**
- server_count
- environments_present
- OS mix (Windows/Linux)
- VM readiness distribution (Ready, ReadyWithConditions, NotReady)
- utilization_profile (low, medium, high)

**From detected_technology_running:**
- primary_runtime (.NET, Java, etc.)
- database_present
- middleware_present
- messaging_present

**From App Mod results (AUTHORITATIVE):**
- container_ready
- compatibility per target platform (FullySupported, Supported, SupportedWithChanges, SupportedWithRefactor, NotSupported)
- explicit blockers
- recommended_targets

### Phase 2: Derive Architectural Intent
Infer 10 signal dimensions with confidence levels:

| Signal | Values | Source Priority |
|--------|--------|-----------------|
| likely_runtime_model | monolith, n_tier, microservices, mixed, unknown | App type, server count |
| modernization_depth_feasible | tolerate, rehost, replatform, refactor, rebuild | App Mod > tech detection |
| cloud_native_feasibility | low, medium, high | App Mod container_ready |
| operational_maturity_estimate | traditional_it, transitional, devops, sre | CI/CD indicators |
| availability_requirement | single_region, zone_redundant, multi_region_* | Business criticality |
| security_requirement | basic, enterprise, regulated, highly_regulated | Compliance keywords |
| cost_posture | cost_minimized, balanced, scale_optimized, innovation_first | Criticality, utilization |
| treatment | retire, tolerate, rehost, replatform, refactor, replace, rebuild, retain | Declared or inferred |
| time_category | tolerate, migrate, invest, eliminate | Treatment mapping |
| network_exposure | external, internal, mixed | App type inference |

**Key Rule**: App Mod results override inference when they conflict.

### Phase 3: Clarification Questions (Dynamic Generation)

Questions are **dynamically generated** based on signal confidence levels, NOT statically defined.

**Generation Logic:**
```python
QUESTION_THRESHOLD = SignalConfidence.LOW

def should_ask(confidence: SignalConfidence) -> bool:
    """Ask question if confidence is LOW or worse."""
    confidence_order = {HIGH: 3, MEDIUM: 2, LOW: 1, UNKNOWN: 0}
    return confidence_order[confidence] <= confidence_order[QUESTION_THRESHOLD]
```

**Question Types (generated when conditions met):**

| Question ID | Dimension | Generation Condition |
|-------------|-----------|---------------------|
| `network_exposure` | Network exposure | **ALWAYS ASKED** - Critical for architecture selection |
| `treatment` | Migration strategy | No declared treatment AND confidence <= LOW |
| `time_category` | Strategic investment posture | UNKNOWN confidence only |
| `availability` | Availability requirements | Confidence <= LOW |
| `security_level` | Security/compliance level | No compliance requirements AND confidence <= LOW |
| `operating_model` | Operational maturity | Confidence <= LOW |
| `cost_posture` | Cost optimization priority | Confidence <= LOW |

**Network Exposure Question (Always Asked):**

The `network_exposure` question is ALWAYS asked because it critically affects architecture selection:

| Value | Label | Description | Architecture Impact |
|-------|-------|-------------|---------------------|
| `external` | External (Internet-facing) | Public access (customers, APIs) | Needs WAF, DDoS, CDN, public endpoints |
| `internal` | Internal Only | Corporate network only | Private endpoints, simpler security |
| `mixed` | Mixed (Both) | Public and internal components | Most complex, needs both patterns |

**Question Schema:**
```json
{
  "question_id": "security_level",
  "dimension": "security_requirement",
  "question_text": "What security/compliance level is required?",
  "options": [
    {"value": "basic", "label": "Basic", "description": "Standard security practices"},
    {"value": "enterprise", "label": "Enterprise", "description": "Zero Trust, private endpoints"},
    {"value": "regulated", "label": "Regulated", "description": "SOC 2, ISO 27001, GDPR"},
    {"value": "highly_regulated", "label": "Highly Regulated", "description": "HIPAA, PCI-DSS, FedRAMP"}
  ],
  "required": false,
  "affects_eligibility": true,
  "current_inference": "basic",
  "inference_confidence": "LOW"
}
```

**Question Principles:**
- Only ask when the answer materially affects eligibility or scoring
- Questions must be business-readable (no technical jargon)
- Constrained answer sets only (no free text)
- User answers override inferred values with HIGH confidence
- Questions are sorted: required first, then by eligibility impact

### Phase 4: Eligibility Filtering
EXCLUDE architecture immediately if ANY apply:

| Rule | Description |
|------|-------------|
| Treatment Mismatch | supported_treatments doesn't include app treatment |
| TIME Mismatch | supported_time_categories doesn't include app TIME |
| Security Gap | security_level < app requirement |
| Maturity Gap | operating_model_required > app maturity |
| App Mod Blocker | Platform marked NotSupported |
| Not Suitable For | Exclusion reason matches app characteristics |

### Phase 5: Scoring
Score eligible architectures 0-100 with weighted dimensions:

| Dimension | Weight | Description |
|-----------|--------|-------------|
| treatment_alignment | 20% | Hard gate + score |
| runtime_model_compatibility | 10% | Runtime model match |
| platform_compatibility | 15% | App Mod platform status |
| app_mod_recommended | 10% | Boost for recommended targets |
| service_overlap | 10% | Approved services match |
| browse_tag_overlap | 5% | Relevant tags match |
| availability_alignment | 10% | Availability model match |
| operating_model_fit | 8% | Maturity level fit |
| complexity_tolerance | 7% | Complexity vs criticality |
| cost_posture_alignment | 5% | Cost profile match |

**Modifiers:**
- Catalog quality weight: curated (1.0) > example_only (0.7)
- Confidence penalty: Up to -25% for assumptions

### Phase 6: Explanation Generation
For each recommendation:

**Why this fits:**
- Matched treatment
- Compatible runtime
- App Mod confirmation

**Where it struggles:**
- Missing capabilities
- Maturity gaps
- Required effort

**Assumptions made:**
- Inferred signals
- Unanswered questions
- Confidence caveats

---

## Output Schema

### ScoringResult
```json
{
  "scoring_version": "1.0.0",
  "scored_at": "2026-01-31T12:00:00Z",
  "application_name": "MyApp",
  "catalog_version": "1.0.0",
  "catalog_architecture_count": 170,
  "derived_intent": {...},
  "clarification_questions": [...],
  "questions_pending": false,
  "recommendations": [...],
  "excluded": [...],
  "summary": {...},
  "eligible_count": 45,
  "excluded_count": 125,
  "processing_warnings": []
}
```

### ArchitectureRecommendation
```json
{
  "architecture_id": "aks-baseline",
  "name": "AKS Baseline for Microservices",
  "pattern_name": "AKS Baseline",
  "description": "...",
  "likelihood_score": 87,
  "catalog_quality": "curated",
  "scoring_dimensions": [...],
  "matched_dimensions": [...],
  "mismatched_dimensions": [...],
  "assumptions": [...],
  "fit_summary": ["Spring Boot ready", "Container-native"],
  "struggle_summary": ["Requires AKS skills"],
  "core_services": ["Azure Kubernetes Service"],
  "supporting_services": ["Azure Monitor"],
  "learn_url": "https://learn.microsoft.com/...",
  "diagram_url": "https://raw.githubusercontent.com/...",
  "browse_tags": ["containers", "kubernetes"],
  "confidence_penalty": 0.05
}
```

### RecommendationSummary
```json
{
  "primary_recommendation": "AKS Baseline for Microservices",
  "primary_recommendation_id": "aks-baseline",
  "confidence_level": "High",
  "key_drivers": ["Container-ready", "Microservices architecture"],
  "key_risks": ["Team needs Kubernetes training"],
  "assumptions_count": 2,
  "clarifications_needed": 1
}
```

---

## Scoring Rules

### Hard Gates
1. Treatment must be supported (or no restrictions)
2. App Mod platform must not be NotSupported

### Confidence Penalties (Per Signal)

Each signal dimension has a confidence level that contributes to an overall penalty:

| Signal Confidence | Penalty |
|-------------------|---------|
| HIGH | 0% |
| MEDIUM | 5% |
| LOW | 15% |
| UNKNOWN | 25% |

**Tracked Signals (10 total):**

| Signal | Has Question? | Source When No Answer |
|--------|---------------|----------------------|
| network_exposure | **ALWAYS** | App type inference |
| treatment | Yes | App Mod or inference |
| time_category | Yes | Treatment inference |
| availability_requirement | Yes | Business criticality |
| security_requirement | Yes | Compliance detection |
| operational_maturity_estimate | Yes | Technology detection |
| cost_posture | Yes | Criticality heuristics |
| likely_runtime_model | No | App Mod or app type |
| modernization_depth_feasible | No | App Mod results only |
| cloud_native_feasibility | No | App Mod container_ready |

### Overall Confidence Level

The recommendation's overall confidence level is determined by **all four conditions**:

| Level | Score | Penalty | Low Signals | Assumptions |
|-------|-------|---------|-------------|-------------|
| **HIGH** | >=75% | <10% | <=1 | <=2 |
| **MEDIUM** | >=50% | <20% | <=3 | Any |
| **LOW** | Does not meet MEDIUM requirements | | |

### Catalog Quality Weights
| Quality | Weight |
|---------|--------|
| curated | 100% |
| ai_enriched | 95% |
| ai_suggested | 85% |
| example_only | 70% |

---

## CLI Usage

### Entry Points

```bash
# Install
pip install -e ".[dev]"

# Score an application (interactive mode - default)
architecture-scorer score \
  --catalog architecture-catalog.json \
  --context app-context.json \
  --top 5 \
  --verbose

# Non-interactive mode
architecture-scorer score \
  --catalog catalog.json \
  --context context.json \
  --no-interactive

# With user answers (bypass prompts)
architecture-scorer score \
  --catalog catalog.json \
  --context context.json \
  --answer treatment=replatform \
  --answer security_level=enterprise \
  --answer operating_model=devops

# Show clarification questions only
architecture-scorer questions \
  --catalog catalog.json \
  --context context.json

# Validate inputs
architecture-scorer validate \
  --catalog catalog.json \
  --context context.json
```

### Interactive Question Mode

By default, the CLI runs in interactive mode. When clarification questions are generated:

```
Question 1 of 3:
What security/compliance level is required for this application?
Current inference: basic (confidence: LOW)

    1. Basic - Standard security practices, no specific compliance
    2. Enterprise - Enterprise security (Zero Trust, private endpoints)
  > 3. Regulated - Industry compliance (SOC 2, ISO 27001, GDPR)
    4. Highly Regulated - Strict compliance (HIPAA, PCI-DSS, FedRAMP)

Enter choice (1-4) or value [press Enter to keep current]: 2
Selected: enterprise
```

---

## Core Principles

1. **The catalog is knowledge, not decisions** - Scorer makes decisions
2. **App Mod results override inference** - Authoritative source
3. **Unknown is better than wrong** - Mark uncertainty
4. **Trust is built through explanation** - Every score explained
5. **This system assists architects; it does not replace them**
6. **Prefer exclusion over weak inclusion** - Quality over quantity
7. **Deterministic execution** - Same inputs = same outputs

---

## Testing

### Test Suite

```bash
# Run all scorer tests
pytest tests/test_architecture_scorer.py -v

# Run E2E tests
pytest tests/test_e2e.py -v

# With coverage
pytest tests/ --cov=src/ --cov-report=html
```

### Test Coverage
- 173 tests in `test_architecture_scorer.py`
- 36 tests in `test_e2e.py` (end-to-end)
- Context file validation, treatment scenarios, complexity scenarios
- App Mod blocker handling, clarification questions

### Example Context Files

25 pre-built context files in `examples/context_files/`:

| File | Scenario |
|------|----------|
| `01-java-refactor-aks.json` | Java app refactoring to AKS |
| `02-dotnet-replatform-appservice.json` | .NET replatform to App Service |
| `07-greenfield-cloud-native-perfect.json` | New cloud-native application |
| `09-rehost-vm-lift-shift.json` | VM lift-and-shift |
| `10-retire-end-of-life.json` | Application retirement |
| `13-highly-regulated-healthcare.json` | Regulated industry scenario |

---

## Security Considerations

The scorer validates all file paths before processing:

```python
from architecture_recommendations_app.utils.sanitize import (
    safe_path, PathValidationError
)

# Paths are validated before use
catalog_path = safe_path(user_catalog_path, must_exist=True)
context_path = safe_path(user_context_path, must_exist=True)
```

### Protections
- Null byte injection prevention
- Path traversal attack prevention
- File existence validation

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-29 | Initial release with full scoring pipeline |
| 1.1 | 2026-01-29 | Added interactive CLI, dynamic questions, cost_posture |
| 2.0 | 2026-01-31 | Added path security, E2E test suite, 25 example context files |

---

## Related Documents

- [Catalog Builder Prompt](catalog-builder-prompt-v1.md) - Catalog compilation design
- [Recommendations App Prompt](recommendations-app-prompt-v1.md) - Web app design
- [Scoring Weights ADR](decisions/0001-scoring-weights.md) - Weight decisions
- [Confidence Penalties ADR](decisions/0002-confidence-penalties.md) - Penalty calculations
- [Eligibility Filter Rules ADR](decisions/0005-eligibility-filter-rules.md) - Exclusion rules
