# Architecture Scorer Prompt v1.0

**Purpose**: Document the design intent and rules for the Architecture Scoring and Recommendation Engine.

---

## Overview

Build a deterministic, explainable Architecture Scoring and Recommendation Engine that runs at RUNTIME. It evaluates application contexts against the Azure Architecture Catalog and returns ranked recommendations with clear reasoning.

### Architecture Separation

| Component | Role | Characteristics |
|-----------|------|-----------------|
| **Catalog Builder** (Prompt 1) | Neutral catalog compiler | Build-time, deterministic |
| **Scorer** (this engine) | Scoring and recommendation | Runtime, explainable |
| **Browser App** | User interface | Explainability and confirmation |

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
- business_criticality
- declared_treatment (Gartner 8R)
- app_type

**From server_details:**
- server_count
- environments_present
- OS mix (Windows/Linux)
- VM readiness distribution
- utilization profile

**From detected_technology_running:**
- primary_runtime (.NET, Java, etc.)
- database_present
- middleware_present

**From App Mod results (AUTHORITATIVE):**
- container_ready
- compatibility per target platform
- explicit blockers
- recommended_targets

### Phase 2: Derive Architectural Intent
Infer with confidence levels:

| Signal | Values | Source Priority |
|--------|--------|-----------------|
| likely_runtime_model | monolith, n_tier, microservices, mixed | App type, server count |
| modernization_depth_feasible | tolerate → rebuild | App Mod > tech detection |
| cloud_native_feasibility | low, medium, high | App Mod container_ready |
| operational_maturity_estimate | traditional_it → sre | CI/CD indicators |
| availability_requirement | single_region → active-active | Business criticality |
| security_requirement | basic → highly_regulated | Compliance keywords |
| cost_posture | cost_minimized → innovation_first | Criticality, utilization |

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
| `treatment` | Migration strategy | No declared treatment AND confidence ≤ LOW |
| `time_category` | Strategic investment posture | UNKNOWN confidence only |
| `availability` | Availability requirements | Confidence ≤ LOW |
| `security_level` | Security/compliance level | No compliance requirements AND confidence ≤ LOW |
| `operating_model` | Operational maturity | Confidence ≤ LOW |
| `cost_posture` | Cost optimization priority | Confidence ≤ LOW |

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

```json
{
  "recommendations": [{
    "architecture_id": "...",
    "name": "...",
    "likelihood_score": 87,
    "catalog_quality": "curated",
    "matched_dimensions": [...],
    "mismatched_dimensions": [...],
    "assumptions": [...],
    "learn_url": "..."
  }],
  "excluded": [{
    "architecture_id": "...",
    "reasons": [...]
  }],
  "summary": {
    "primary_recommendation": "...",
    "confidence_level": "High",
    "key_drivers": [...],
    "key_risks": [...]
  }
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
| network_exposure | ✅ **ALWAYS** | App type inference |
| treatment | ✅ Yes | App Mod or inference |
| time_category | ✅ Yes | Treatment inference |
| availability_requirement | ✅ Yes | Business criticality |
| security_requirement | ✅ Yes | Compliance detection |
| operational_maturity_estimate | ✅ Yes | Technology detection |
| cost_posture | ✅ Yes | Criticality heuristics |
| likely_runtime_model | ❌ No | App Mod or app type |
| modernization_depth_feasible | ❌ No | App Mod results only |
| cloud_native_feasibility | ❌ No | App Mod container_ready |

**Important**: 7 of 10 signals can be addressed via clarification questions. The `network_exposure` question is ALWAYS asked. The remaining 3 (`likely_runtime_model`, `modernization_depth_feasible`, `cloud_native_feasibility`) are derived from App Mod results or technology detection. Without App Mod data, these signals may remain at LOW/UNKNOWN confidence.

**Example Calculation:**
```
Signals: treatment=HIGH, availability=MEDIUM, security=MEDIUM, operating_model=LOW
Penalties: 0% + 5% + 5% + 15% = 25% total penalty
Final score: base_score × (1 - 0.25)
```

### Overall Confidence Level

The recommendation's overall confidence level is determined by **all four conditions**:

| Level | Score | Penalty | Low Signals | Assumptions |
|-------|-------|---------|-------------|-------------|
| **HIGH** | ≥75% | <10% | ≤1 | ≤2 |
| **MEDIUM** | ≥50% | <20% | ≤3 | Any |
| **LOW** | Does not meet MEDIUM requirements | | |

**Algorithm:**
```python
def calculate_confidence_level(score, penalty, low_signals, assumptions):
    if score >= 75 and penalty < 0.10 and low_signals <= 1 and assumptions <= 2:
        return "HIGH"
    elif score >= 50 and penalty < 0.20 and low_signals <= 3:
        return "MEDIUM"
    else:
        return "LOW"
```

**Why Confidence Can Remain "Low" Even With All Questions Answered:**

Since only 6 of 9 signals have clarification questions, applications without App Mod results will have at least 3 signals at LOW/UNKNOWN confidence. This means:

1. **Low Signal Count**: Even with all 6 questions answered at HIGH confidence, the 3 remaining signals (`likely_runtime_model`, `modernization_depth_feasible`, `cloud_native_feasibility`) may push `low_signals` count to 3 (borderline for MEDIUM)

2. **Score Threshold**: The score must also meet the threshold (≥50% for MEDIUM). If the best-matching architectures are `example_only` quality (70% weight), effective scores are reduced

3. **Penalty Accumulation**: LOW confidence signals contribute 15% penalty each, UNKNOWN contributes 25%

**Example:**
```
Application: GlobalTradingPlatform (no App Mod data)

User answers (all 6): HIGH confidence
  • treatment, time_category, availability, security, operating_model, cost_posture

Derived signals (no App Mod): LOW/UNKNOWN confidence
  • likely_runtime_model: LOW (inferred from app type)
  • modernization_depth_feasible: UNKNOWN
  • cloud_native_feasibility: UNKNOWN

Calculation:
  • low_signals = 3 (exactly at MEDIUM threshold)
  • penalty = 0.15 + 0.25 + 0.25 = 0.65 (capped at 0.25)
  • score = 50% (top recommendation)
  • catalog_quality = example_only (0.70 weight)

Result: "Low" confidence
  - Score is borderline at 50%
  - 3 low-confidence signals at threshold
  - Penalty exceeds 20% threshold
```

**To Improve Confidence:**
- Provide App Mod results (derives 3 signals at HIGH confidence)
- Use contexts with better-matching curated architectures
- Ensure declared treatment in app_overview (avoids treatment inference)

### Catalog Quality Weights
| Quality | Weight |
|---------|--------|
| curated | 100% |
| ai_enriched | 95% |
| ai_suggested | 85% |
| example_only | 70% |

---

## CLI Usage

### Basic Commands

```bash
# Score an application (interactive mode - default)
architecture-scorer score \
  -c architecture-catalog.json \
  -x app-context.json \
  -n 5 \
  --verbose

# Non-interactive mode (skip question prompts)
architecture-scorer score \
  -c catalog.json \
  -x context.json \
  --no-interactive

# With user answers (bypass prompts)
architecture-scorer score \
  -c catalog.json \
  -x context.json \
  -a treatment=replatform \
  -a security_level=enterprise \
  -a operating_model=devops \
  -a cost_posture=balanced

# Show clarification questions only
architecture-scorer questions \
  -c catalog.json \
  -x context.json

# Validate inputs
architecture-scorer validate \
  -c catalog.json \
  -x context.json
```

### Interactive Question Mode

By default, the CLI runs in interactive mode (`--interactive`/`-i`). When clarification questions are generated, the user is prompted with numbered options:

```
Question 1 of 3:
What security/compliance level is required for this application?
Current inference: basic (confidence: LOW)

    1. Basic - Standard security practices, no specific compliance
    2. Enterprise - Enterprise security (Zero Trust, private endpoints)
  → 3. Regulated - Industry compliance (SOC 2, ISO 27001, GDPR)
    4. Highly Regulated - Strict compliance (HIPAA, PCI-DSS, FedRAMP)

Enter choice (1-4) or value [press Enter to keep current]: 2
✓ Selected: enterprise
```

**Input Options:**
- Enter a number (1-4) to select an option
- Type the value directly (e.g., `enterprise`)
- Press Enter to keep the current inference

### Answer Display

User answers are displayed in the scoring summary:

```
Your Answers Applied:
  • security_level: enterprise
  • operating_model: devops
  • cost_posture: balanced
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

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-29 | Initial release with full scoring pipeline |
| 1.1 | 2026-01-29 | Added interactive CLI mode with numbered options, dynamic question generation, confidence level calculations, cost_posture question |
