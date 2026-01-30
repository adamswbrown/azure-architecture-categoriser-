# Azure Architecture Recommender - Project State

## Current Phase
**Phase 5: Containerization - COMPLETE**

## Status

### Docker & CI/CD (NEW - 2026-01-30)
- [x] Multi-stage Dockerfile (Python 3.11-slim)
- [x] Multi-platform builds (amd64 + arm64)
- [x] GitHub Container Registry (ghcr.io)
- [x] GitHub Actions workflow for auto-publish
- [x] CodeQL security scanning workflow
- [x] docker-compose.yml for local development
- [x] Health checks configured

### Security (2026-01-30)
- [x] XSS protection via HTML entity escaping
- [x] SSRF protection via URL domain allowlist
- [x] Secure temp file handling (random names, 0o600 permissions)
- [x] Information disclosure prevention (conditional stack traces)
- [x] Security test suite (44 tests)
- [x] Security audit documentation

### Catalog Builder
- [x] Project structure created
- [x] Catalog schema defined
- [x] Markdown parser implemented
- [x] Architecture detection heuristics implemented
- [x] Metadata extraction implemented
- [x] AI-assisted classification implemented
- [x] CLI built and tested
- [x] Full integration test passed
- [x] Streamlit GUI implemented
- [x] Learn URLs working correctly

### Architecture Scorer
- [x] Context normalization (Phase 1)
- [x] Intent derivation (Phase 2)
- [x] Clarification questions (Phase 3)
- [x] Architecture matching (Phase 4)
- [x] Network exposure question (always asked)
- [x] 25 test context files covering all scenarios
- [x] Container-ready apps infer DevOps maturity
- [x] Treatment-based maturity inference (replatform/refactor → transitional)
- [x] Relaxed eligibility filter (1-level gap allowed)

### Recommendations App (NEW)
- [x] 3-step wizard flow (Upload → Questions → Results)
- [x] File validation with user-friendly errors
- [x] Application summary display
- [x] Interactive clarification questions
- [x] Results display with recommendation cards
- [x] Architecture diagram images (from catalog)
- [x] PDF report generation with reportlab
- [x] JSON export
- [x] Light theme with Azure branding
- [x] Session state management
- [x] Catalog build parameters displayed in sidebar (compact badges)

### Documentation (NEW)
- [x] Separated docs for each component
- [x] docs/catalog-builder.md
- [x] docs/recommendations-app.md
- [x] docs/architecture-scorer.md
- [x] Main README refactored as overview with navigation

## Architecture Decisions

### Technology Stack
- Python 3.11+
- Click for CLI
- Pydantic for schema validation
- PyYAML for frontmatter parsing
- Rich for terminal output
- GitPython for git metadata
- Streamlit for GUI and Recommendations App
- reportlab for PDF generation

### Project Structure
```
azure-architecture-categoriser-/
├── src/
│   ├── catalog_builder/              # Catalog generation
│   │   ├── cli.py, parser.py, detector.py
│   │   ├── extractor.py, classifier.py
│   │   ├── schema.py, catalog.py, config.py
│   ├── architecture_scorer/          # Architecture scoring
│   │   ├── cli.py, scorer.py, schema.py
│   │   ├── normalizer.py, intent_deriver.py
│   │   ├── question_generator.py, matcher.py
│   ├── catalog_builder_gui/          # Catalog Builder GUI
│   │   ├── app.py, state/
│   │   └── components/
│   └── architecture_recommendations_app/  # Customer App (NEW)
│       ├── app.py
│       ├── components/
│       │   ├── upload_section.py
│       │   ├── results_display.py
│       │   ├── questions_section.py
│       │   └── pdf_generator.py
│       ├── state/session_state.py
│       ├── utils/validation.py
│       └── .streamlit/config.toml
├── docs/                             # Documentation
│   ├── catalog-builder.md
│   ├── recommendations-app.md
│   ├── architecture-scorer.md
│   ├── configuration.md
│   └── design/                       # Design specifications
│       ├── catalog-builder-prompt-v1.md
│       └── architecture-scorer-prompt-v1.md
├── tests/
│   ├── test_catalog_builder.py
│   ├── test_architecture_scorer.py
│   └── fixtures/                     # Test fixtures
│       └── context_files/            # Test context files
├── examples/                         # Example files
│   └── example-java-context.json
├── scripts/                          # Utility scripts
├── .streamlit/config.toml            # Theme configuration
├── .github/workflows/                # CI/CD
│   ├── codeql.yml                    # Security scanning
│   └── docker-publish.yml            # Container build & publish
├── Dockerfile                        # Multi-stage container build
├── docker-compose.yml                # Local development
├── docker-entrypoint.sh              # Container entrypoint
├── pyproject.toml
├── README.md
├── state.md, worklog.md
└── architecture-catalog.json
```

## Test Results

### All Tests
```
152 passed in 0.94s
```

### Coverage
- Catalog Builder: 22 tests
- Architecture Scorer: 130 tests
- Context file validation: 20/25 files return recommendations (expected - 5 are edge cases)

## Blocking Issues
None.

## GitHub Issues
1. [#1 - Integrate Catalog Builder into Recommendations App](https://github.com/adamswbrown/azure-architecture-categoriser/issues/1) - Open
2. [#2 - Containerize the Application](https://github.com/adamswbrown/azure-architecture-categoriser/issues/2) - **COMPLETE**
3. [#3 - Add CodeQL Security Scanning](https://github.com/adamswbrown/azure-architecture-categoriser/issues/3) - **COMPLETE**

## Recent Changes (2026-01-30)
1. **v1.0 Release** - First public Docker container release
2. **Docker Containerization** - Multi-platform images (amd64 + arm64)
3. **GitHub Actions** - Auto-publish to ghcr.io on push/tag
4. **CodeQL Scanning** - Automated security analysis on PRs
5. **Security Audit** - XSS, SSRF, temp file hardening
6. **Scoring Bug Fixes** - Container-ready & treatment-based maturity inference
7. **Eligibility Filter Relaxation** - Allow 1-level maturity gap (transitional→devops)
8. **UI Improvements** - Compact catalog build parameters in sidebar

## Next Actions
1. Integrate catalog generation into Recommendations App (Issue #1)
2. Improve diagram asset extraction in catalog builder
3. Add more test context files for edge cases
