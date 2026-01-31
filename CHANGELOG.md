# Changelog

All notable changes to the Azure Architecture Recommender are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] - 2026-01-31

### Added
- **Azure Container Apps Deployment**: GitHub Actions workflow for automated deployment to Azure
  - Bicep infrastructure-as-code templates (`infra/main.bicep`, `infra/modules/container-app.bicep`)
  - OIDC authentication (no secrets stored)
  - Deploys to UK South region
  - Automatic image updates on push to main
- **Architecture Decision Records (ADRs)**: Design documentation explaining "why" decisions were made
  - `docs/design/README.md` - Entry point for design decisions
  - `docs/design/glossary.md` - Key terms and concepts
  - 5 ADRs covering scoring weights, confidence penalties, catalog quality, service whitelist, eligibility filters
- **Sample Files Dialog**: "Try a Sample" button with modal dialog showing 8 demo scenarios
- **Help Dialogs**: Moved help content from sidebar expanders to modal dialogs for cleaner UX
- **Catalog Comparison Doc**: `docs/catalog-comparison.md` comparing Quick Build vs Full Build

### Changed
- Renamed `app.py` to `Recommendations.py` for clearer sidebar navigation
- Help content now in modal dialogs (click "?" button)

---

## [1.2.0] - 2026-01-31

### Added
- **Path Security Utilities**: New `safe_path()`, `validate_repo_path()`, `validate_output_path()` functions in `utils/sanitize.py`
- **E2E Test Suite**: Comprehensive end-to-end tests with 36 tests covering security, pipeline, and integration (`test_e2e.py`)
- **Test Documentation**: `tests/README.md` with full test suite documentation and running instructions
- **Design Prompts v2.0**: Updated all three design prompts to reflect current project state

### Fixed
- **Path Injection Vulnerabilities**: Fixed 14 HIGH severity CodeQL path injection alerts across 4 files:
  - `pages/1_Catalog_Builder.py` - clone_repository() function
  - `catalog_builder_gui/app.py` - clone_repository() function
  - `catalog_builder_gui/components/preview_panel.py` - _generate_catalog() function
  - `catalog_builder_gui/components/config_editor.py` - save functionality
- **False Positive Suppression**: Added CodeQL suppression comments for 5 false positive URL sanitization alerts

### Security
- Null byte injection prevention in path validation
- Path traversal attack prevention (`../` sequences blocked)
- Base directory containment enforcement
- Existence validation for required paths

### Changed
- Test count increased to 253 tests (up from 217)
- All path operations now use validated paths

---

## [1.1.0] - 2026-01-30

### Added
- **Scoring Improvements**: Container-ready applications now correctly infer DevOps operational maturity
- **Treatment-Based Maturity**: Replatform/Refactor/Rebuild treatments imply transitional maturity
- **Relaxed Eligibility Filter**: Allow 1-level maturity gap (transitional apps can now match DevOps architectures)
- **Catalog Build Parameters Display**: Compact badge UI showing generation settings in sidebar

### Fixed
- Greenfield cloud-native applications returning 0 recommendations
- Replatform scenarios being excluded from DevOps-required architectures
- Overly strict operating model matching (was excluding 38/43 architectures)

### Changed
- Context file validation: 20/25 files now return recommendations (up from 16/25)
- Catalog details UI redesigned with compact badges instead of bullet lists

## [1.0.0] - 2026-01-30

### Added

#### Docker & Container Support
- Multi-stage Dockerfile for optimized image size (Python 3.11-slim)
- Multi-platform builds (linux/amd64 + linux/arm64 for Apple Silicon)
- GitHub Container Registry publishing (ghcr.io)
- GitHub Actions workflow for automatic container builds on push/tag
- docker-compose.yml for easy local development
- Health check endpoints configured

#### Security Hardening
- **XSS Protection**: HTML entity escaping for all user-controlled content
- **SSRF Protection**: URL domain allowlist (microsoft.com, azure.com, github.com)
- **Secure Temp Files**: Random filenames, 0o600 permissions, auto-cleanup
- **Information Disclosure Prevention**: Stack traces only shown in debug mode
- CodeQL security scanning workflow on PRs
- 44 security tests added

#### Recommendations App (Customer-Facing)
- 3-step wizard flow: Upload → Questions → Results
- File validation with user-friendly error messages
- Application summary display with technology tags
- Interactive clarification questions with re-scoring
- Results display with recommendation cards
- Architecture diagram images (SVG support via svglib)
- PDF report generation with embedded diagrams
- JSON export for raw recommendation data
- Light theme with Azure branding (#0078D4)
- "Your Answers" section in PDF reports
- No-matches handling with helpful suggestions

#### Catalog Builder GUI
- Streamlit-based visual configuration
- Keywords editor for 9 classification dictionaries
- Filter presets (Azure Compute, Data Platform, AI/ML, etc.)
- Preview panel with metrics before generation
- Visual YAML config editor
- Getting Started guide with quick workflow

#### Architecture Scorer
- Context normalization (Phase 1)
- Intent derivation from Dr. Migrate context (Phase 2)
- Dynamic clarification questions (Phase 3)
- Architecture matching with weighted scoring (Phase 4)
- Network exposure question (always asked)
- 25 test context files covering all scenarios

#### CLI Tools
- `catalog-builder build-catalog` - Generate architecture catalog
- `catalog-builder stats` - View catalog statistics
- `catalog-builder inspect` - Browse architectures by family/ID
- `architecture-scorer score` - Score context against catalog

#### Documentation
- Separated docs for each component
- docs/catalog-builder.md - Catalog generation guide
- docs/recommendations-app.md - Customer app guide
- docs/architecture-scorer.md - Scoring engine reference
- docs/reviewing-the-catalog.md - Catalog review guide
- docs/securityaudit.md - Security audit report

### Changed
- Default catalog filter: Reference architectures only (~50 vs ~170 with examples)
- Learn URLs now correctly link to Microsoft Learn pages
- GitHub Octocat diagram bug fixed (skip github.svg files)

### Technical Details

#### Catalog Object Model
Each architecture entry includes:
- **Identity**: architecture_id, name, description, source_repo_path, learn_url
- **Classification**: family (foundation/iaas/paas/cloud_native/data/integration/specialized), workload_domain
- **Architectural Expectations**: expected_runtime_models, expected_characteristics
- **Operational Expectations**: availability_models, security_level, operating_model_required
- **Services**: Azure services detected from content

#### Detection Heuristics
Architecture candidates identified by:
1. Location in docs/example-scenario/ or workload domain folders
2. Presence of SVG/PNG architecture diagrams
3. Architecture/Components/Diagram sections
4. Keywords: "reference architecture", "baseline architecture", "solution idea"

#### Generation Settings Metadata
Catalogs now include build parameters:
```json
{
  "generation_settings": {
    "allowed_topics": ["reference-architecture"],
    "allowed_products": null,
    "allowed_categories": null,
    "require_architecture_yml": false,
    "exclude_examples": false
  }
}
```

## [0.1.0] - 2026-01-28

### Added
- Initial project structure
- Pydantic schema for catalog entries
- Markdown parser with frontmatter extraction
- Architecture detection heuristics
- Metadata and git metadata extraction
- AI-assisted classification suggestions
- Basic CLI with Click

### Technical Notes
- Integration test with Azure Architecture Center: 269 architectures detected
- Top services: Azure Monitor (194), Azure Functions (246), Microsoft Entra ID (112)

---

## Running the Application

### Docker (Recommended)
```bash
docker run -p 8501:8501 -p 8502:8502 ghcr.io/adamswbrown/azure-architecture-categoriser:latest
```

### From Source
```bash
pip install -e ".[recommendations-app,gui]"
streamlit run src/architecture_recommendations_app/Recommendations.py  # Port 8501
streamlit run src/catalog_builder_gui/app.py --server.port 8502  # Port 8502
```

### CLI
```bash
catalog-builder build-catalog --repo-path ./architecture-center --out catalog.json
architecture-scorer score -c catalog.json -x context.json
```

## Links

- [GitHub Repository](https://github.com/adamswbrown/azure-architecture-categoriser)
- [Docker Image](https://ghcr.io/adamswbrown/azure-architecture-categoriser)
- [Documentation](docs/)
