# Azure Architecture Recommender - Work Log

## 2026-01-30

### Session: UX Polish & PDF Enhancements

**Goal:** Improve visual density, add missing features to PDF reports, handle edge cases.

**Changes Made:**

#### 1. Visual Density Improvements (Step 1 & Step 3)

**Step 1 (Upload):**
- Replaced oversized `st.subheader()` with compact CSS grid layout
- Reduced font sizes and removed redundant labels
- Technologies displayed as styled tags instead of plain list
- Server summary inline instead of separate metric cards

**Step 3 (Results):**
- Compact summary section using CSS grid (4-column layout)
- Changed confidence message for "Medium" from "consider answering questions" to "Good match based on available data"
- Made Learn more links visually prominent as styled blue buttons
- Collapsed Key Drivers and Key Considerations by default

#### 2. Architecture Diagram Sizing

- **Web UI:** Changed column ratio from `[1, 4, 1]` to `[1, 2, 1]` for smaller primary diagram
- **PDF:** Added SVG support using `svglib` library (Azure Architecture Center uses SVG diagrams)

#### 3. User Answers Display

- **Web UI:** Added "Your Answers" expander showing answered clarification questions
- **PDF Report:** Added "Your Answers" section before recommendations

#### 4. Sidebar Improvements

- Collapsed "Catalog Details" expander by default (`expanded=False`)

#### 5. No Recommendations Handling (Option 5)

When scoring returns zero recommendations, the app now shows:
- ⚠️ Warning banner explaining no strong matches found
- **What we understood** - Key drivers from context file
- **Possible reasons** - Common explanations for low scores
- **Suggestions** - Actionable steps to improve results:
  - Answer unanswered questions (if any)
  - Review context file
  - Browse Azure Architecture Center manually
  - Contact Azure specialist

#### 6. Sample Data Location

- Moved sample context files from `tests/fixtures/context_files/` to `examples/context_files/`
- Updated all references in tests, scripts, and documentation

**Files Modified:**
```
src/architecture_recommendations_app/
├── app.py                        # Sidebar collapse, pass has_unanswered_questions
├── components/
│   ├── results_display.py        # No-matches UI, smaller diagram, user answers
│   ├── pdf_generator.py          # SVG support, user answers section
│   └── upload_section.py         # Simplified layout
```

**Dependencies Added:**
- `svglib>=1.5.0` - SVG to ReportLab conversion for PDF diagrams

**Documentation Updated:**
- `docs/recommendations-app.md` - Added "No Strong Matches" section, PDF features
- `worklog.md` - This entry

---

## 2026-01-29

### Session: Documentation & GitHub Issues

**Goal:** Separate documentation, create GitHub issues for roadmap, update project state.

**Documentation Created:**
- `docs/catalog-builder.md` - Full catalog builder documentation
- `docs/recommendations-app.md` - Customer app documentation
- `docs/architecture-scorer.md` - Scoring engine documentation
- `README.md` - Refactored as high-level overview with navigation

**GitHub Issues Created:**
1. **#1 - Integrate Catalog Builder into Recommendations App**
   - Allow catalog generation from customer app
   - Single application for end users

2. **#2 - Containerize the Application**
   - Docker container for easy deployment
   - CI/CD pipeline for image publishing

3. **#3 - Add CodeQL Security Scanning**
   - Automated security analysis on PRs
   - Python vulnerability detection

---

### Session: Recommendations App UX Improvements

**Goal:** Improve app flow based on user feedback - make it a stepped wizard process.

**Changes Made:**

1. **3-Step Wizard Flow**
   - Step 1: Upload & Review (file upload, application summary)
   - Step 2: Answer Questions (clarification questions)
   - Step 3: Results (recommendations, export buttons)

2. **Step Indicator**
   - Visual progress indicator (✅ 🔵 ⚪)
   - Back/forward navigation between steps

3. **Light Theme**
   - Added `.streamlit/config.toml` with forced light mode
   - Azure-branded colors (#0078D4 primary)

4. **Bug Fixes**
   - Fixed PDF generation error: "Style 'Title' already defined"
   - Renamed custom styles to avoid conflicts with built-in reportlab styles

5. **Image Sizing**
   - Primary recommendation: 450px width
   - Alternative recommendations: 200px width
   - PDF images: 4x2 inches

**Note:** Only 35/171 catalog entries have diagram images. This is a catalog extraction issue, not an app bug.

---

### Session: Customer-Facing Recommendations App

**Goal:** Build a simple Streamlit app for customers to upload Dr. Migrate context and receive architecture recommendations.

**Features Implemented:**
1. **File Upload** - Validates JSON context files with user-friendly error messages
2. **Auto-Processing** - Automatically analyzes uploaded files
3. **Results Display** - Shows recommendations as cards with:
   - Architecture diagram images (from GitHub raw URLs)
   - Match score badges (color-coded)
   - Quality badges (Curated, AI Enriched, etc.)
   - Why it fits / Potential challenges
   - Azure services and Learn links
4. **Interactive Q&A** - Clarification questions with re-scoring
5. **PDF Export** - Professional report with embedded diagrams
6. **JSON Export** - Raw recommendation data

**Files Created:**
```
src/architecture_recommendations_app/
├── __init__.py
├── app.py                      # Main Streamlit app
├── components/
│   ├── upload_section.py       # File upload
│   ├── results_display.py      # Recommendation cards
│   ├── questions_section.py    # Interactive Q&A
│   └── pdf_generator.py        # PDF report
├── state/session_state.py      # Session management
└── utils/validation.py         # File validation
```

**Schema Changes:**
- Added `diagram_url` field to `ArchitectureRecommendation`
- Populated from catalog's `diagram_assets` via GitHub raw URLs

**Run with:** `streamlit run src/architecture_recommendations_app/app.py`

**Tests:** All 173 tests passing

---

### Session: Success Metrics Display Improvement

**Issue:** After catalog generation, the "Output File" metric was truncated and unreadable.

**Fix:** Replaced truncated filename metric with useful catalog statistics:
- Architectures (kept)
- Products (unique count across all architectures)
- Categories (unique count)
- File Size (kept)
- File path now shown as readable caption below metrics

---

### Session: Preview Panel Bug Fix & UI Restructure

**Bug Fix:** Preview showing "Parse error: 500" for all files.
- **Root Cause:** Code called `parser.parse(md_file)` but `MarkdownParser` has `parse_file()`, not `parse()`
- **Fix:** Changed to `parser.parse_file(md_file)` and added null check

**UI Restructure:** Clear separation between Quick Generate and Custom Build

The Build Catalog tab now has two distinct workflows:

**Option 1: Quick Generate**
- Uses default settings (no configuration needed)
- One-click "Generate with Defaults" button
- Expandable section showing what defaults include

**Option 2: Custom Build** (3-step workflow)
- Step 1: Configure (shows current settings status, directs to Filter Presets/Config Editor tabs)
- Step 2: Preview (optional - scan to see what matches current settings)
- Step 3: Generate with Current Settings

Both options are visually contained in bordered boxes for clear separation.

---

### Session: GUI, Network Exposure & URL Fixes - COMPLETE

**Goals Achieved:**
1. Built Streamlit GUI for catalog builder configuration
2. Added network exposure question to architecture scorer (always asked)
3. Fixed Learn URLs - now properly link to Microsoft Learn pages
4. All 173 tests passing

#### GUI Improvements (Later in Session)

Enhanced the GUI with comprehensive explanations and sensible defaults:

1. **Getting Started Guide** - Expandable overview in main app explaining:
   - What the tool does
   - Quick start workflow
   - Default settings table
   - CLI usage examples

2. **Preview Panel Fix** - Now scans architecture folders first (example-scenario,
   reference-architectures, ai-ml, etc.) instead of alphabetically, so previews
   show meaningful results with default 100 file limit

3. **Inline Documentation** - Added "How it Works" expanders to each tab:
   - Keywords Editor: Classification process and keyword tips
   - Filter Presets: Filter types, logic, and typical counts
   - Preview Panel: Detection process and key metadata fields
   - Config Editor: Complete configuration reference

#### Streamlit GUI (`catalog_builder_gui/`)

| Component | Purpose | Status |
|-----------|---------|--------|
| `app.py` | Main Streamlit app with clone/pull repo functionality | Complete |
| `state/session_state.py` | Session state management with auto-detect repo | Complete |
| `components/keywords_editor.py` | Edit 9 keyword dictionaries | Complete |
| `components/filter_presets.py` | Product/category filter presets | Complete |
| `components/preview_panel.py` | Preview catalog build with metrics | Complete |
| `components/config_editor.py` | Visual YAML config editor | Complete |

**Run with:** `streamlit run src/catalog_builder_gui/app.py`

#### Network Exposure Question (Architecture Scorer)

Added always-asked clarification question for Public vs Private Link architecture selection:
- **External (Internet-facing)**: Needs WAF, DDoS protection, public endpoints
- **Internal Only**: Can use private endpoints, simpler security
- **Mixed (Both)**: Needs both patterns

Files modified:
- `schema.py`: Added `NetworkExposure` enum and `network_exposure` to `DerivedIntent`
- `question_generator.py`: Added `_check_network_exposure()` method
- `intent_deriver.py`: Added `_derive_network_exposure()` method

#### Learn URL Fix

URLs now correctly link to Microsoft Learn pages:
- Remove `docs/` prefix
- Remove `.md` suffix
- Remove `-content` suffix (repo convention, not in Learn URLs)

Example:
- Repo path: `docs/networking/architecture/azure-dns-private-resolver-content.md`
- Learn URL: `https://learn.microsoft.com/en-us/azure/architecture/networking/architecture/azure-dns-private-resolver`

#### Test Results
```
173 passed in 1.03s
```

---

## 2026-01-28

### Session: Initial Implementation - COMPLETE

**Goals Achieved:**
1. Built complete CLI tool
2. Implemented all extraction and classification logic
3. Tested with Azure Architecture Center repo
4. All tests passing

---

## Implementation Summary

### Components Built

| Module | Purpose | Status |
|--------|---------|--------|
| `schema.py` | Pydantic models for catalog schema | Complete |
| `parser.py` | Markdown parsing with frontmatter extraction | Complete |
| `detector.py` | Architecture candidate detection heuristics | Complete |
| `extractor.py` | Metadata and git metadata extraction | Complete |
| `classifier.py` | AI-assisted classification suggestions | Complete |
| `catalog.py` | Catalog building orchestration | Complete |
| `cli.py` | Click CLI with build-catalog, inspect, stats | Complete |

### Catalog Object Model

Each architecture entry includes:

**Identity**
- architecture_id, name, description, source_repo_path, learn_url

**Classification** (AI-suggested)
- family: foundation, iaas, paas, cloud_native, data, integration, specialized
- workload_domain: web, data, integration, security, ai, infrastructure, general

**Architectural Expectations** (AI-suggested)
- expected_runtime_models
- expected_characteristics (containers, stateless, devops/ci-cd required)

**Operational Expectations**
- availability_models, security_level, operating_model_required

**Manual-Only Fields**
- supported_treatments, supported_time_categories, not_suitable_for

### Detection Heuristics

Architecture candidates identified by:
1. Location in docs/example-scenario/ or workload domain folders
2. Presence of SVG/PNG architecture diagrams
3. Architecture/Components/Diagram sections
4. Keywords: "reference architecture", "baseline architecture", "solution idea"

Exclusions:
- docs/guide/, docs/best-practices/, docs/patterns/
- index.md, toc.yml, readme.md

---

## Test Results

### Unit Tests
```
14 passed in 0.56s
```

### Integration Test
```
Repository: architecture-center (MicrosoftDocs)
Files scanned: 349
Architectures detected: 269
Diagrams found: 117
Unique services: 6,247
```

### Top Azure Services Detected
1. Azure Monitor (194)
2. Azure Well (164) - needs normalization
3. Azure Virtual Machine (149)
4. Azure Functions (145+101)
5. Microsoft Entra ID (112)
6. Azure Load Balancer (92)
7. Azure Kubernetes Service (89)
8. Azure SQL Database (84)
9. Azure Blob Storage (83)

---

## CLI Commands

```bash
# Build catalog
catalog-builder build-catalog --repo-path ./architecture-center --out catalog.json

# View statistics
catalog-builder stats --catalog catalog.json

# Inspect architectures
catalog-builder inspect --catalog catalog.json --family cloud_native
catalog-builder inspect --catalog catalog.json --id <arch-id>

# Run recommendations app
streamlit run src/architecture_recommendations_app/app.py

# Score via CLI
architecture-scorer score -c catalog.json -x context.json
```

---

## Progress Log

| Time | Action | Status |
|------|--------|--------|
| 22:30 | Project initialized | Complete |
| 22:35 | Schema defined | Complete |
| 22:40 | Parser implemented | Complete |
| 22:45 | Detector implemented | Complete |
| 22:50 | Extractor implemented | Complete |
| 22:55 | Classifier implemented | Complete |
| 23:00 | CLI implemented | Complete |
| 23:05 | Unit tests passing | Complete |
| 23:10 | Integration test complete | Complete |
| 23:15 | Documentation complete | Complete |
| 23:20 | Ready for commit | Complete |
