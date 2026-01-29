# Recommendations App Prompt v1.0

**Purpose**: Document the design intent and rules for the Azure Architecture Recommendations App.

---

## Overview

Build a Streamlit web application that allows customers to upload their application context file and receive architecture recommendations from the scoring engine.

### Architecture Separation

| Component | Role | Characteristics |
|-----------|------|-----------------|
| **Prompt 1** (Catalog Builder) | Neutral catalog compiler | Explainable, deterministic, no scoring |
| **Prompt 2** (Architecture Scorer) | Scorer and recommender | Uses catalog as input |
| **Prompt 3** (this app) | Explainer and confirmer | User-facing interface |

---

## Core Principles

### 1. Simple User Flow
- Upload JSON → See recommendations → (Optionally answer questions → Re-score) → Download PDF/JSON
- No unnecessary steps or configuration required
- Auto-process on file upload (no separate "analyze" button)

### 2. Professional Presentation
- Azure-branded with Microsoft design language
- Professional styling with clear visual hierarchy
- Color-coded confidence indicators
- Architecture diagrams where available

### 3. Actionable Results
- Clear primary recommendation with explanation
- Alternative options for comparison
- Links to Microsoft Learn documentation
- Exportable reports for stakeholder review

---

## File Structure

```
src/architecture_recommendations_app/
├── __init__.py
├── app.py                      # Main Streamlit application
├── components/
│   ├── __init__.py
│   ├── upload_section.py       # File upload component
│   ├── results_display.py      # Recommendation cards display
│   ├── questions_section.py    # Interactive clarification Q&A
│   ├── pdf_generator.py        # PDF report generation
│   └── config_editor.py        # Scorer configuration editor
├── state/
│   ├── __init__.py
│   └── session_state.py        # Session state management
└── utils/
    ├── __init__.py
    └── validation.py           # Context file validation
```

---

## UI Design

### Color Palette
- **Azure Blue** (#0078D4) - Headers, primary actions
- **Microsoft Green** (#107C10) - Success states, primary recommendation
- **Light Gray** (#F5F5F5) - Card backgrounds
- **White** - Page background

### Score Badges
- **High (≥60%)**: Green background (#DFF6DD)
- **Medium (40-59%)**: Orange background (#FFF4CE)
- **Low (<40%)**: Red background (#FDE7E9)

### Quality Badges
- **Curated**: Azure Blue (#0078D4)
- **AI Enriched**: Purple (#5C2D91)
- **AI Suggested**: Yellow (#FFB900)
- **Example Only**: Gray (#E6E6E6)

### Confidence Level Styling
- **High**: Green (#107C10) - "Strong match with clear requirements"
- **Medium**: Orange (#FFB900) - "Good match - consider answering questions for better accuracy"
- **Low**: Red (#D83B01) - "Limited data - answering questions will improve recommendations"

### Layout
```
┌─────────────────────────────────────────────────────┐
│  Azure Architecture Recommendations                  │
│  Upload your application context...                  │
├─────────────────────────────────────────────────────┤
│  [ Drop your context file here or click to browse ] │
│  ✓ Loaded: myapp-context.json                       │
├─────────────────────────────────────────────────────┤
│  ### Analysis Summary                               │
│  ┌────────┬────────┬────────┬────────┐             │
│  │ App    │Confid. │ Recs   │Evaluated│             │
│  │MyApp   │ High   │   5    │  170    │             │
│  └────────┴────────┴────────┴────────┘             │
│                                                      │
│  **Key Drivers:**           **Considerations:**      │
│  - Java Spring Boot         - Legacy dependencies    │
│  - Container-ready          - Team maturity needed   │
├─────────────────────────────────────────────────────┤
│  ### Primary Recommendation                         │
│  ┌─────────────────────────────────────────────────┐│
│  │ AKS Baseline for Microservices    [78% Match]  ││
│  │ Pattern: Cloud-Native Container    [Curated]   ││
│  │                                                 ││
│  │ ┌─────────────────────────────────────────────┐││
│  │ │  [Architecture Diagram Image]              │││
│  │ │  (SVG/PNG from GitHub raw URL)             │││
│  │ └─────────────────────────────────────────────┘││
│  │                                                 ││
│  │ Description...                                  ││
│  │                                                 ││
│  │ **Why it fits:**        **Challenges:**         ││
│  │ - Spring Boot ready     - Requires AKS skills   ││
│  │ - Kubernetes native     - Networking complexity ││
│  │                                                 ││
│  │ [Learn more on Microsoft Docs]                  ││
│  └─────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────┤
│  ### Alternative Recommendations                    │
│  [Card] [Card] [Card] [Card]                        │
├─────────────────────────────────────────────────────┤
│  ### Improve Recommendations (if questions exist)   │
│  ┌─────────────────────────────────────────────────┐│
│  │ Answer these to improve accuracy:               ││
│  │                                                 ││
│  │ Network exposure? [▼ External (internet)]      ││
│  │ Current: Internal (Low confidence)             ││
│  │                                                 ││
│  │ Availability needs? [▼ Zone redundant]         ││
│  │ Current: Unknown                               ││
│  │                                                 ││
│  │ [Re-analyze with Answers]                       ││
│  └─────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────┤
│  ### Export Results                                 │
│  [Download PDF Report] [Download JSON] [New Analysis]│
└─────────────────────────────────────────────────────┘
```

---

## Component Specifications

### Upload Section (`upload_section.py`)

**Functionality:**
- `st.file_uploader()` accepting `.json` files
- Immediate validation on upload
- Clear error messages with suggestions for common issues
- Success indicator when valid file loaded

**Validation checks:**
1. File size (max 10MB)
2. Valid JSON syntax
3. Required structure (array with one object)
4. Required fields: `app_overview`, `detected_technology_running`, `server_details`
5. `app_overview` has `application` name

**Error handling:**
- User-friendly error messages
- Suggestions for how to fix common issues
- No stack traces shown to customers

### Results Display (`results_display.py`)

**Summary Section:**
- 4 metrics: Application Name, Confidence Level, Recommendations Count, Architectures Evaluated
- Key Drivers list (why these recommendations)
- Key Considerations/Risks list

**Primary Recommendation (highlighted):**
- Architecture diagram image (prominent, at top of card)
- Name, pattern, description
- Match score badge (color-coded by threshold)
- Quality badge (Curated, AI Enriched, AI Suggested, Example)
- "Why it fits" bullet points
- "Potential challenges" bullet points
- Core Azure services
- Microsoft Learn link

**Alternative Recommendations:**
- Two-column grid layout for compact display
- Same card format but condensed
- Show up to 4 additional recommendations

### Questions Section (`questions_section.py`)

**Functionality:**
- Show questions the scorer identified
- Expandable by default if questions exist
- Display current inference and confidence for each
- Interactive dropdowns to answer each question
- "Re-analyze with Answers" button to re-score
- Updated results replace previous results

### PDF Generator (`pdf_generator.py`)

**Library:** `reportlab` (pure Python, container-friendly, no external deps)

**Report Structure:**
1. Title: "Azure Architecture Recommendations"
2. Application info and generation date
3. Executive Summary table
4. Key Drivers section
5. Recommendations (numbered, with scores and explanations)
6. Architecture diagrams (embedded from GitHub URLs)
7. Learn URLs for each recommendation

**Styling:**
- Azure Blue (#0078D4) for headings
- Microsoft Green (#107C10) for primary recommendation
- Professional table formatting

### Config Editor (`config_editor.py`)

**Functionality:**
- Edit scorer configuration settings in the sidebar
- Adjustable confidence thresholds
- Adjustable scoring weights with validation (should sum to ~1.0)
- Quality weight adjustments
- Save to disk and reset to defaults

---

## Architecture Diagram Images

**Source:** Catalog entries have `diagram_assets: list[str]` containing relative paths like:
- `docs/example-scenario/apps/contoso-app-architecture.svg`
- `docs/reference-architectures/containers/aks-baseline-architecture.png`

**URL Construction:**
Convert relative path to GitHub raw URL:
```
https://raw.githubusercontent.com/MicrosoftDocs/architecture-center/main/{path}
```

**Schema Changes:**
Add to `ArchitectureRecommendation` in `architecture_scorer/schema.py`:
```python
diagram_url: Optional[str] = Field(
    None,
    description="URL to the primary architecture diagram image"
)
```

**Display in UI:**
```python
if rec.diagram_url:
    st.image(rec.diagram_url, use_container_width=True)
```

**PDF Generation:**
```python
from reportlab.platypus import Image
from io import BytesIO
import requests

if rec.diagram_url:
    response = requests.get(rec.diagram_url, timeout=5)
    if response.ok:
        img = Image(BytesIO(response.content), width=6*inch, height=3*inch)
        story.append(img)
```

---

## Session State Management

Track:
- `scoring_result` - Cached ScoringResult
- `last_file_hash` - Hash of processed file (avoid re-processing)
- `error_state` - Any error messages

**Key Features:**
- Cache results by file hash to avoid re-processing on Streamlit reruns
- Clear state on "New Analysis" action

---

## Catalog Management

**Catalog Path Resolution (in order):**
1. Environment variable: `ARCHITECTURE_CATALOG_PATH` (for custom catalogs)
2. Local file: `./architecture-catalog.json`
3. Bundled default: Package resource (fallback)

**Catalog Freshness:**
- Warn when catalog is >30 days old
- One-click refresh with progress bar
- Auto clone/update of architecture-center repo
- Quick regenerate using catalog builder

**Catalog Builder Integration:**
- Launch button in sidebar to open Catalog Builder GUI
- Runs on separate port (8502) to avoid conflicts

---

## Integration Points

| Component | Existing Module | Usage |
|-----------|-----------------|-------|
| Scoring | `architecture_scorer.engine.ScoringEngine` | `load_catalog()`, `score()` |
| Validation | `architecture_scorer.engine.validate_context` | Pre-scoring validation |
| Schema | `architecture_scorer.schema.ScoringResult` | Result data access |
| Configuration | `architecture_scorer.config` | Load/save scorer config |
| Catalog | `architecture-catalog.json` | Load at startup |

---

## Dependencies

**New:**
- `streamlit>=1.30.0` - Web UI framework
- `reportlab>=4.0.0` - PDF generation

**Reused:**
- `architecture_scorer` - Scoring engine
- `pydantic>=2.0.0` - Data models
- `requests` - Fetch diagram images (transitive dep)

---

## Installation and Usage

### Install
```bash
pip install -e ".[recommendations-app]"
```

### Run
```bash
architecture-recommendations
# Or directly:
streamlit run src/architecture_recommendations_app/app.py
```

### Test Flow
1. Upload a test context file from `tests/context_files/`
2. Verify recommendations display correctly
3. Verify architecture diagram images load (from GitHub raw URL)
4. Download PDF and verify formatting (including embedded diagrams)
5. Download JSON and verify structure
6. Click "New Analysis" and verify state clears
7. Upload invalid JSON and verify error handling
8. Test clarification questions → re-analyze flow

---

## Decisions Made

1. **Single-page vertical flow** - No tabs, simpler navigation
2. **Auto-process on upload** - No separate "analyze" button needed
3. **Catalog location** - Bundle with app, allow override via env var or local file
4. **Clarification questions** - Interactive answering with re-score capability
5. **Branding** - Azure-branded with professional styling (blue/green palette)
6. **Architecture diagrams** - Display in results cards and embed in PDF reports
7. **Config editor** - Allow tuning scorer settings from the UI

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-29 | Initial release with upload, results display, PDF export |
| 1.1 | 2026-01-29 | Add catalog freshness warning, refresh functionality, config editor |

---

## Future Considerations

1. **Batch Processing**: Process multiple context files at once
2. **Comparison View**: Side-by-side comparison of recommendations for different applications
3. **History**: Track previous analyses for the same application over time
4. **Team Collaboration**: Share and discuss recommendations with team members
