# Azure Architecture Recommender

A complete solution for matching applications to Azure architecture patterns based on assessment data.

## Components

| Component | Purpose | Documentation |
|-----------|---------|---------------|
| **Catalog Builder** | Compile Azure Architecture Center docs into a structured catalog | [docs/catalog-builder.md](docs/catalog-builder.md) |
| **Architecture Scorer** | Score and rank architectures for an application context | [docs/architecture-scorer.md](docs/architecture-scorer.md) |
| **Recommendations App** | Customer-facing web UI for recommendations | [docs/recommendations-app.md](docs/recommendations-app.md) |

## Quick Start

### Option 1: Customer-Facing Web App (Recommended)

```bash
# Install
pip install -e ".[recommendations-app]"

# Run (macOS/Linux)
./bin/start-recommendations-app.sh

# Run (Windows PowerShell)
.\bin\start-recommendations-app.ps1
```

Upload your Dr. Migrate context file and get architecture recommendations instantly.

### Option 2: CLI Scoring

```bash
# Install
pip install -e .

# Score an application
architecture-scorer score \
  --catalog architecture-catalog.json \
  --context my-app-context.json
```

### Option 3: Build Custom Catalog

```bash
# Clone Azure Architecture Center
git clone https://github.com/MicrosoftDocs/architecture-center.git

# Build catalog
catalog-builder build-catalog \
  --repo-path ./architecture-center \
  --out architecture-catalog.json
```

## Installation

```bash
# Clone this repository
git clone https://github.com/adamswbrown/azure-architecture-categoriser-.git
cd azure-architecture-categoriser-

# Base installation (CLI tools)
pip install -e .

# With web app
pip install -e ".[recommendations-app]"

# With GUI catalog builder
pip install -e ".[gui]"

# Development
pip install -e ".[dev]"
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Azure Architecture Recommender                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐  │
│  │  Catalog Builder │    │ Architecture     │    │ Recommendations  │  │
│  │                  │    │ Scorer           │    │ App              │  │
│  │  Build-time      │───▶│ Runtime engine   │───▶│ Customer UI      │  │
│  │  CLI / GUI       │    │ CLI / Library    │    │ Streamlit        │  │
│  └──────────────────┘    └──────────────────┘    └──────────────────┘  │
│           │                       │                       │             │
│           ▼                       ▼                       ▼             │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐  │
│  │ architecture-    │    │ Context JSON     │    │ PDF Report       │  │
│  │ catalog.json     │    │ (Dr. Migrate)    │    │ JSON Export      │  │
│  └──────────────────┘    └──────────────────┘    └──────────────────┘  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Workflow

1. **Build Catalog** (one-time or periodic)
   - Run Catalog Builder against Azure Architecture Center
   - Produces `architecture-catalog.json` with 170+ architectures

2. **Assess Application**
   - Use Dr. Migrate or similar tool to assess your application
   - Produces context JSON with technologies, servers, modernization results

3. **Get Recommendations**
   - Upload context to Recommendations App (or use CLI)
   - Answer optional clarification questions
   - Receive ranked architecture recommendations with explanations

4. **Export & Share**
   - Download PDF report for stakeholders
   - Download JSON for integration with other tools

## Key Features

- **171 Azure Architectures** from official Azure Architecture Center
- **Explainable Recommendations** - See why each architecture fits or struggles
- **Confidence Levels** - Know how certain the recommendations are
- **Interactive Questions** - Improve accuracy by answering clarifying questions
- **PDF Reports** - Professional reports for stakeholders
- **Multiple Interfaces** - Web app, CLI, or programmatic API

## Documentation

| Document | Description |
|----------|-------------|
| [Catalog Builder](docs/catalog-builder.md) | Building architecture catalogs |
| [Architecture Scorer](docs/architecture-scorer.md) | Scoring engine details |
| [Recommendations App](docs/recommendations-app.md) | Customer-facing web app |
| [Configuration](docs/configuration.md) | Full configuration reference |
| [Catalog Builder Spec](docs/design/catalog-builder-prompt-v1.md) | Design specification |
| [Scorer Spec](docs/design/architecture-scorer-prompt-v1.md) | Scoring specification |

## Repository Structure

```
azure-architecture-recommender/
├── bin/                           # Launcher scripts
│   ├── start-recommendations-app.sh/.ps1
│   └── start-catalog-builder-gui.sh/.ps1
├── src/                           # Source code
│   ├── catalog_builder/           # Catalog generation CLI
│   ├── catalog_builder_gui/       # Catalog Builder GUI
│   ├── architecture_scorer/       # Scoring engine
│   └── architecture_recommendations_app/  # Customer web app
├── docs/                          # Documentation
│   ├── design/                    # Design specifications
│   └── *.md                       # Component docs
├── tests/                         # Tests
│   └── fixtures/                  # Test data
├── examples/                      # Example files
└── architecture-catalog.json      # Generated catalog
```

## Version

**v1.2** - Recommendations App release:
- Customer-facing Streamlit web application
- 3-step wizard flow (Upload → Questions → Results)
- PDF report generation
- Light theme with Azure branding

**v1.1** - Architecture Scorer release:
- Interactive CLI with clarification questions
- Confidence level calculations
- Programmatic API

**v1.0** - Initial release:
- 171 architectures from Azure Architecture Center
- Clean Azure services extraction
- Quality differentiation (curated vs example_only)

## License

MIT
