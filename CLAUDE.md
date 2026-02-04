# CLAUDE.md - AI Assistant Guide

This document provides essential context for AI assistants working with the Azure Architecture Recommender codebase.

## Project Overview

**Azure Architecture Recommender** is a cloud migration recommendation engine that matches applications to Azure architecture patterns. It integrates with Dr. Migrate (an application assessment tool) by accepting context files containing detected technologies, server details, and modernization assessment results, then recommending suitable Azure reference architectures using multi-dimensional scoring.

**Current Version**: 1.1.0
**License**: MIT
**Python**: 3.11+ required

## Quick Reference

### Common Commands

```bash
# Install for development
pip install -e ".[recommendations-app,gui,dev]"

# Run tests
pytest tests/

# Run tests with coverage
pytest --cov=src/ --cov-report=html

# Start Recommendations App (port 8501)
./bin/start-recommendations-app.sh

# Start Catalog Builder GUI (port 8502)
./bin/start-catalog-builder-gui.sh

# Generate sample test data
./bin/generate-sample-data.sh

# Build Docker image
docker build -t azure-architecture-categoriser .

# Run with Docker
docker run -p 8501:8501 -p 8502:8502 azure-architecture-categoriser
```

### CLI Entry Points

```bash
catalog-builder build-catalog --repo-path ./architecture-center --out catalog.json
catalog-builder stats --catalog catalog.json
catalog-builder inspect --catalog catalog.json --family cloud_native

architecture-scorer score --catalog catalog.json --context context.json
architecture-scorer questions --catalog catalog.json --context context.json
architecture-scorer validate --catalog catalog.json

# Dr. Migrate Integration (generate context files from Dr. Migrate data)
architecture-scorer generate-context --input drmigrate.json --out context.json
architecture-scorer generate-sample-drmigrate --out sample-input.json
```

## Repository Structure

```
azure-architecture-categoriser/
├── src/                                 # All source code
│   ├── catalog_builder/                 # CLI tool for building architecture catalogs
│   │   ├── cli.py                       # Click commands (build-catalog, stats, inspect)
│   │   ├── catalog.py                   # CatalogBuilder class & validation
│   │   ├── schema.py                    # Pydantic models (ArchitectureEntry, Catalog)
│   │   ├── parser.py                    # Markdown parser for .md files
│   │   ├── extractor.py                 # Metadata extraction from architecture docs
│   │   ├── detector.py                  # Architecture pattern detection heuristics
│   │   ├── classifier.py                # AI-assisted classification
│   │   └── config.py                    # Configuration management (YAML)
│   │
│   ├── architecture_scorer/             # Scoring engine & CLI
│   │   ├── cli.py                       # Click commands (score, questions, validate, generate-context)
│   │   ├── engine.py                    # ScoringEngine orchestrator (5-phase pipeline)
│   │   ├── schema.py                    # Input/output models (Pydantic)
│   │   ├── normalizer.py                # Phase 1: Normalize raw context
│   │   ├── intent_deriver.py            # Phase 2: Derive architectural intent
│   │   ├── question_generator.py        # Phase 3: Generate clarification questions
│   │   ├── eligibility_filter.py        # Phase 4: Filter by compatibility
│   │   ├── scorer.py                    # Phase 5: Score and rank architectures
│   │   ├── explainer.py                 # Phase 6: Build explanations
│   │   ├── config.py                    # Scorer configuration
│   │   ├── drmigrate_schema.py          # Dr. Migrate input data models
│   │   └── drmigrate_generator.py       # Context file generator from Dr. Migrate data
│   │
│   ├── architecture_recommendations_app/ # Streamlit customer-facing web app
│   │   ├── app.py                       # Main app entry point (3-step wizard)
│   │   ├── components/                  # Reusable UI components
│   │   │   ├── upload_section.py        # Context file upload
│   │   │   ├── questions_section.py     # Interactive questions
│   │   │   ├── results_display.py       # Recommendation cards
│   │   │   ├── pdf_generator.py         # PDF report generation
│   │   │   └── config_editor.py         # Config adjustments
│   │   ├── state/session_state.py       # Session state management
│   │   └── utils/                       # Utilities
│   │       ├── validation.py            # Input validation
│   │       └── sanitize.py              # XSS/SSRF protection
│   │
│   └── catalog_builder_gui/             # Streamlit catalog builder GUI
│       ├── app.py                       # Main app entry point
│       ├── components/                  # UI components
│       │   ├── config_editor.py         # YAML config visual editor
│       │   ├── filter_presets.py        # Pre-configured filter templates
│       │   ├── keywords_editor.py       # Classification dictionary editor
│       │   └── preview_panel.py         # Preview before generation
│       └── state/session_state.py       # Session state
│
├── tests/                               # Test suite
│   ├── test_architecture_scorer.py      # Scoring engine tests (400+)
│   ├── test_catalog_builder.py          # Catalog building tests
│   ├── test_sanitize.py                 # Security tests (44)
│   └── generate_sample_data.py          # Sample data generator
│
├── examples/                            # Example files
│   └── context_files/                   # 25 sample context files
│
├── docs/                                # Documentation
│   ├── catalog-builder.md               # Catalog building guide
│   ├── architecture-scorer.md           # Scoring engine details
│   ├── recommendations-app.md           # Web app guide
│   ├── configuration.md                 # Full config reference
│   ├── securityaudit.md                 # Security measures
│   ├── drmigrate-integration.md         # Dr. Migrate context file generation
│   └── design/                          # Design specifications
│
├── bin/                                 # Launcher scripts
│   ├── start-recommendations-app.sh     # Launch recommendations app
│   ├── start-catalog-builder-gui.sh     # Launch catalog builder
│   └── generate-sample-data.sh          # Generate test files
│
├── .github/workflows/                   # CI/CD
│   ├── docker-publish.yml               # Multi-platform Docker builds
│   └── codeql.yml                       # Security scanning
│
├── architecture-catalog.json            # Pre-built catalog (~50 architectures)
├── pyproject.toml                       # Project config & dependencies
├── Dockerfile                           # Multi-stage Docker build
├── docker-compose.yml                   # Local dev setup
└── docker-entrypoint.sh                 # Container startup script
```

## Architecture & Data Flow

### Scoring Pipeline (5 Phases)

```
Dr. Migrate Context File (JSON)
         ↓
Phase 1: Normalize → ApplicationContext
Phase 2: Derive Intent → 10 signals with confidence
Phase 3: Generate Questions → Dynamic clarifications
Phase 4: Eligibility Filter → Exclude incompatible architectures
Phase 5: Score & Rank → Weighted scoring (8 dimensions)
Phase 6: Explain → Build detailed recommendations
         ↓
ScoringResult → PDF Report / JSON Export
```

### Key Components

| Component | Port | Purpose |
|-----------|------|---------|
| Recommendations App | 8501 | Customer-facing 3-step wizard |
| Catalog Builder GUI | 8502 | One-time catalog generation/customization |
| Architecture Scorer CLI | - | Backend engine for automation |
| Catalog Builder CLI | - | Build catalogs from Azure Architecture Center |

## Code Conventions

### Naming
- **snake_case**: variables, functions, module names
- **PascalCase**: classes
- **UPPER_CASE**: constants and enum values
- **Descriptive names**: `EligibilityFilter`, `IntentDeriver`, `ScoringEngine`

### Type Safety
- All data models use **Pydantic v2** for validation
- Type hints on all function signatures
- Enums for constrained values (`ArchitectureFamily`, `WorkloadDomain`, `RuntimeModel`, etc.)

### Module Organization
- Each module has a clear single responsibility
- Pydantic schemas in dedicated `schema.py` files
- Configuration in `config.py` files
- CLI commands in `cli.py` files using Click

### Testing
- Tests in `tests/` directory
- pytest as test runner
- 25 sample context files as fixtures in `examples/context_files/`
- Security tests cover XSS, SSRF, and temp file handling

## Key Pydantic Models

### Catalog Builder (`src/catalog_builder/schema.py`)
- `ArchitectureEntry` - Complete architecture with classification, services, complexity
- `ArchitectureCatalog` - Container with metadata & generation settings
- Key enums: `ArchitectureFamily`, `WorkloadDomain`, `Treatment`, `RuntimeModel`, `SecurityLevel`
- Quality levels: `CURATED`, `AI_ENRICHED`, `AI_SUGGESTED`, `EXAMPLE_ONLY`

### Architecture Scorer (`src/architecture_scorer/schema.py`)
- `RawContextFile` - Dr. Migrate output format
- `ApplicationContext` - Normalized application data
- `DerivedIntent` - 10 signal dimensions (runtime model, modernization depth, etc.)
- `ScoringResult` - Complete output with recommendations
- `ArchitectureRecommendation` - Ranked recommendation with explanations

## Security Considerations

The codebase includes security hardening that must be maintained:

1. **XSS Protection**: Use `safe_html()` from `utils/sanitize.py` for user-controlled content
2. **SSRF Protection**: URL domain allowlist (microsoft.com, azure.com, github.com)
3. **Secure Temp Files**: Random filenames, `0o600` permissions, auto-cleanup
4. **Input Validation**: All inputs validated via Pydantic models
5. **Information Disclosure**: Stack traces only in debug mode

## Development Workflow

### Adding New Features

1. Define Pydantic models in appropriate `schema.py`
2. Implement core logic in dedicated module
3. Add CLI command in `cli.py` if needed
4. Add UI component in `components/` if needed
5. Write tests in `tests/`
6. Update documentation in `docs/`

### Running Tests

```bash
# All tests
pytest tests/

# Specific test file
pytest tests/test_architecture_scorer.py

# With coverage
pytest --cov=src/ --cov-report=html

# Verbose output
pytest -v tests/
```

### Docker Development

```bash
# Build
docker build -t azure-architecture-categoriser .

# Run both apps
docker run -p 8501:8501 -p 8502:8502 azure-architecture-categoriser

# Use docker-compose for development (mounts cache)
docker compose up -d
docker compose logs -f
docker compose down
```

## Dependencies

### Core (always installed)
- `click>=8.1.0` - CLI framework
- `pydantic>=2.0.0` - Data validation
- `pyyaml>=6.0` - YAML parsing
- `rich>=13.0.0` - Terminal UI
- `gitpython>=3.1.0` - Git operations

### Optional Groups
- `[recommendations-app]` - Streamlit, ReportLab, svglib, requests
- `[gui]` - Streamlit
- `[dev]` - pytest, pytest-cov

## Important Files to Know

| File | Why It Matters |
|------|----------------|
| `src/architecture_scorer/engine.py` | Central orchestrator for all scoring logic |
| `src/architecture_scorer/schema.py` | All input/output data structures |
| `src/catalog_builder/schema.py` | Architecture catalog data models |
| `architecture-catalog.json` | Pre-built catalog with ~50 architectures |
| `pyproject.toml` | Dependencies and entry points |
| `examples/context_files/` | Test fixtures for all scenarios |

## Common Tasks

### Adding a New Scoring Dimension
1. Add field to `DerivedIntent` in `src/architecture_scorer/schema.py`
2. Add derivation logic in `src/architecture_scorer/intent_deriver.py`
3. Add scoring weight in `src/architecture_scorer/scorer.py`
4. Update tests in `tests/test_architecture_scorer.py`

### Adding a New Clarification Question
1. Add question logic in `src/architecture_scorer/question_generator.py`
2. Handle answer in `src/architecture_scorer/engine.py`
3. Update UI in `src/architecture_recommendations_app/components/questions_section.py`

### Adding a New Architecture Family
1. Add to `ArchitectureFamily` enum in `src/catalog_builder/schema.py`
2. Add detection logic in `src/catalog_builder/detector.py`
3. Add classification keywords in `src/catalog_builder/classifier.py`
4. Update eligibility rules in `src/architecture_scorer/eligibility_filter.py`

## Gotchas and Tips

1. **Pydantic v2**: Uses `model_dump()` not `dict()`, `model_validate()` not `parse_obj()`
2. **Streamlit reruns**: State must be stored in `st.session_state`
3. **Catalog location**: Apps look for `architecture-catalog.json` in env var → cwd → project root
4. **PDF generation**: Requires ReportLab and svglib for diagram embedding
5. **Git operations**: Catalog Builder needs Git installed to clone Azure Architecture Center
6. **Test fixtures**: Sample context files in `examples/context_files/` cover 25 migration scenarios

## Links

- [GitHub Repository](https://github.com/adamswbrown/azure-architecture-categoriser)
- [Docker Image](https://ghcr.io/adamswbrown/azure-architecture-categoriser)
- [Changelog](CHANGELOG.md)
- [Detailed Documentation](docs/)
