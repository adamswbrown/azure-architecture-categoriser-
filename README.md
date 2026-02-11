# Azure Architecture Recommender

A complete solution for matching applications to Azure architecture patterns based on assessment data.

## What Does This Tool Do?

The **Recommendations App** is a web-based wizard that helps you find the right Azure architecture for your application. Simply upload your application assessment data, answer a few optional questions, and receive ranked architecture recommendations with detailed explanations.

![Azure Architecture Recommendations App](docs/images/architecture%20recommendations-gui.png)

**The 3-step process:**

1. **Upload & Review** - Upload your Dr. Migrate context file and review the detected technologies, servers, and modernization assessment
2. **Answer Questions** - Optionally answer clarifying questions to improve recommendation accuracy (e.g., availability requirements, security level, cost priorities)
3. **Get Results** - Receive ranked Azure architecture recommendations with:
   - Match scores showing how well each architecture fits your needs
   - Detailed explanations of why each architecture is recommended
   - Potential challenges and considerations
   - Links to official Microsoft documentation
   - PDF report export for stakeholders

The tool matches your application profile against **~50 reference architectures** from the [Azure Architecture Center](https://learn.microsoft.com/azure/architecture/browse), using multi-dimensional scoring across factors like runtime model, modernization depth, security requirements, and cost optimization.

---

## Prerequisites: Application Context File

This tool accepts **two types of input files**, both generated from [Dr. Migrate](https://drmigrate.com):

### Option 1: App Cat Context Files (Java/.NET Applications)

For Java and .NET applications, Dr. Migrate uses [AppCat](https://learn.microsoft.com/en-us/azure/migrate/appcat/dotnet) (Microsoft's application assessment tool) to evaluate Azure readiness. This generates a context file containing:

- **Application Overview** - Application name, type, business criticality, and recommended migration treatment
- **Detected Technologies** - Runtime environments, frameworks, databases, and middleware
- **Server Details** - Infrastructure metrics, OS information, and Azure VM readiness
- **App Modernization Results** - Platform compatibility and recommended Azure targets

### Option 2: Dr. Migrate Data Exports (ALL Applications)

For applications **without Java/.NET components**, you can generate context data directly from Dr. Migrate's AI Advisor. This enables architecture recommendations for your **entire portfolio** - not just Java/.NET apps.

Simply paste the provided LLM prompt into Dr. Migrate AI Advisor, save the JSON response, and upload it. The tool auto-detects the format and converts it automatically.

See the [Dr. Migrate Integration Guide](https://adamswbrown.github.io/azure-architecture-categoriser/drmigrate-integration.html) for the full LLM prompt and details.

### Integration with Dr. Migrate

This tool **integrates with** Dr. Migrate's workflow - it is not a feature of Dr. Migrate itself. The workflow is:

1. **In Dr. Migrate**: Either assess with AppCat (Java/.NET) OR use AI Advisor to export data (all apps)
2. **In this tool**: Upload the context file to get architecture recommendations
3. **Back to Dr. Migrate**: Use the recommendations to inform your migration strategy

## Components

The application is a unified multi-page Streamlit app with three pages:

| Page | Purpose | For Who |
|------|---------|---------|
| **Recommendations** | Upload context files and get architecture recommendations | End users / customers |
| **Catalog Stats** | Browse and analyze the architecture catalog | All users |
| **Catalog Builder** | Generate custom catalogs from Azure Architecture Center | Admins / power users |

**Note:** The Recommendations page uses the Architecture Scorer as its backend engine. The CLI is also available for automation and scripting.

## Prerequisites

- **Python 3.9+** - Required to run the application
- **Git** - Required to clone the Azure Architecture Center repository when generating catalogs
- **pip** - Python package manager for installing dependencies

## Quick Start (Typical User Flow)

### Step 1: Install

```bash
# Clone this repository
git clone https://github.com/adamswbrown/azure-architecture-categoriser.git
cd azure-architecture-categoriser

# Install with GUI support
pip install -e ".[recommendations-app,gui]"
```

### Step 2: Launch the Application

```bash
# Launch the unified app (port 8501)
./bin/start-recommendations-app.sh

# Or on Windows:
.\bin\start-recommendations-app.ps1
```

### Step 3: Generate a Catalog (if needed)

If no catalog exists, the app will prompt you to generate one:
1. Go to the **Catalog Builder** page in the sidebar
2. Click **Clone Repository** to get Azure Architecture Center
3. Click **Generate with Defaults** to create `architecture-catalog.json`

### Step 4: Get Recommendations

1. Go to the **Recommendations** page (main page)
2. Upload your Dr. Migrate context file
3. Answer optional clarification questions
4. Download your PDF report

---

## Docker (Recommended for End Users)

The easiest way to run the application is via Docker - no Python installation required.

### Quick Start with Docker

```bash
# Pull and run the container
docker run -p 8501:8501 ghcr.io/adamswbrown/azure-architecture-categoriser:latest
```

Then open: http://localhost:8501

Use the sidebar to navigate between pages:
- **Recommendations** - Upload context files and get architecture recommendations
- **Catalog Stats** - View analytics and browse the catalog
- **Catalog Builder** - Generate custom catalogs with advanced filtering

### Using Docker Compose

```bash
# Clone the repo (for docker-compose.yml)
git clone https://github.com/adamswbrown/azure-architecture-categoriser.git
cd azure-architecture-categoriser

# Start services
docker compose up -d

# View logs
docker compose logs -f

# Stop
docker compose down
```

### Building Locally

```bash
# Build the image
docker build -t azure-architecture-categoriser .

# Run it
docker run -p 8501:8501 azure-architecture-categoriser
```

### What's Included in the Container

- Python 3.11 runtime
- All dependencies (Streamlit, ReportLab, etc.)
- Both applications (Recommendations + Catalog Builder)
- Pre-built architecture catalog
- Git (for catalog updates)

---

## Alternative: CLI for Automation

For scripting, CI/CD pipelines, or batch processing, use the CLI directly:

```bash
# Install base package (no GUI)
pip install -e .

# Build catalog
catalog-builder build-catalog \
  --repo-path ./architecture-center \
  --out architecture-catalog.json

# Build and upload catalog to Azure Blob Storage in one step
catalog-builder build-catalog \
  --repo-path ./architecture-center \
  --out architecture-catalog.json \
  --upload-url "$CATALOG_BLOB_SAS_URL"

# Or upload an existing catalog separately
catalog-builder upload \
  --catalog architecture-catalog.json \
  --blob-url "$CATALOG_BLOB_SAS_URL"

# Score an application
architecture-scorer score \
  --catalog architecture-catalog.json \
  --context my-app-context.json
```

## Installation

```bash
# Clone this repository
git clone https://github.com/adamswbrown/azure-architecture-categoriser.git
cd azure-architecture-categoriser

# Base installation (CLI tools)
pip install -e .

# With web app
pip install -e ".[recommendations-app]"

# With GUI catalog builder
pip install -e ".[gui]"

# With Azure Blob Storage upload support
pip install -e ".[azure]"

# Development
pip install -e ".[dev]"
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Azure Architecture Recommender                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────┐         ┌──────────────────────────────────────┐  │
│  │  Catalog Builder │         │       Recommendations App            │  │
│  │       GUI        │         │         (Customer UI)                │  │
│  │                  │         │                                      │  │
│  │  One-time setup  │         │  ┌──────────────────────────────┐   │  │
│  │  to generate     │────────▶│  │  Architecture Scorer         │   │  │
│  │  catalog         │         │  │  (Backend Engine)            │   │  │
│  └──────────────────┘         │  │                              │   │  │
│           │                    │  │  Matching + Scoring + Q&A   │   │  │
│           ▼                    │  └──────────────────────────────┘   │  │
│  ┌──────────────────┐         └──────────────────────────────────────┘  │
│  │ architecture-    │                          │                        │
│  │ catalog.json     │                          ▼                        │
│  │ (~50 reference   │         ┌──────────────────────────────────────┐  │
│  │  architectures)  │         │  PDF Report / JSON Export            │  │
│  └──────────────────┘         └──────────────────────────────────────┘  │
│                                                                          │
│  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─   │
│  For automation/scripting: architecture-scorer CLI (same engine)        │
└─────────────────────────────────────────────────────────────────────────┘
```

## Typical Workflow

1. **One-Time Setup: Build Catalog**
   - Launch Catalog Builder GUI
   - Clone Azure Architecture Center repository
   - Generate `architecture-catalog.json` (~50 reference architectures)

2. **Assess Application** (in Dr. Migrate)
   - Use Dr. Migrate to assess your application with AppCat
   - Export the context JSON file

3. **Get Recommendations**
   - Launch Recommendations App
   - Upload your context file
   - Answer optional clarification questions
   - View ranked recommendations with explanations

4. **Export & Share**
   - Download PDF report for stakeholders
   - Download JSON for integration with other tools

5. **Periodic: Refresh Catalog**
   - Click "Refresh Catalog" in Recommendations App when catalog is stale
   - Or re-run Catalog Builder for custom filtering

## Key Features

- **~50 Reference Architectures** from official Azure Architecture Center (production-ready patterns)
- **Quality Indicators** - Each architecture marked as curated, AI-enriched, or example (learning/POC)
- **Explainable Recommendations** - See why each architecture fits or struggles
- **Confidence Levels** - Know how certain the recommendations are
- **Interactive Questions** - Improve accuracy by answering clarifying questions
- **PDF Reports** - Professional reports for stakeholders
- **Configurable Scoring** - Tune weights and thresholds via config file or UI
- **Multiple Interfaces** - Web app for users, CLI for automation

## Sample Data

The repository includes 25 sample context files demonstrating different migration scenarios:

| Scenario | Description |
|----------|-------------|
| Java Refactor to AKS | Spring Boot microservices to Kubernetes |
| .NET Replatform | Web app to Azure App Service |
| Legacy Tolerate | VB6 application requiring VM hosting |
| Healthcare HIPAA | Regulated application with compliance requirements |
| AI/ML Platform | Machine learning workload with GPU needs |
| Mainframe COBOL | Legacy mainframe with modernization blockers |
| Startup Cost-Optimized | Serverless/consumption-based architecture |
| Multi-Region Active-Active | Mission-critical global deployment |

Generate or regenerate sample files:

```bash
# macOS/Linux
./bin/generate-sample-data.sh

# Windows PowerShell
.\bin\generate-sample-data.ps1

# List all available scenarios
./bin/generate-sample-data.sh --list
```

See [examples/context_files/README.md](examples/context_files/README.md) for the full list.

## Documentation

**📖 [Full Documentation on GitHub Pages](https://adamswbrown.github.io/azure-architecture-categoriser)** ← Start here for guides and references!

### Key Guides

| Document | Description |
|----------|-------------|
| [Getting Started](https://adamswbrown.github.io/azure-architecture-categoriser/getting-started.html) | Installation and first run |
| [Recommendations App](https://adamswbrown.github.io/azure-architecture-categoriser/recommendations-app.html) | Customer-facing web app guide |
| [Catalog Builder](https://adamswbrown.github.io/azure-architecture-categoriser/catalog-builder.html) | Building architecture catalogs |
| [Architecture Scorer](https://adamswbrown.github.io/azure-architecture-categoriser/architecture-scorer.html) | Scoring engine details |
| [Dr. Migrate Integration](https://adamswbrown.github.io/azure-architecture-categoriser/drmigrate-integration.html) | Get recommendations for ALL apps |
| [Configuration](https://adamswbrown.github.io/azure-architecture-categoriser/configuration.html) | Full configuration reference |
| [Blob Storage Upload](https://adamswbrown.github.io/azure-architecture-categoriser/blob-storage-upload.html) | Publish catalogs to Azure Blob Storage |
| [Design Decisions](https://adamswbrown.github.io/azure-architecture-categoriser/design/) | Why does it work this way? |
| [Azure Deployment](https://adamswbrown.github.io/azure-architecture-categoriser/azure-deployment.html) | Deploy to Azure Container Apps |

## Repository Structure

```
azure-architecture-recommender/
├── bin/                           # Launcher scripts
│   ├── start-recommendations-app.sh/.ps1    # Launch recommendations app
│   ├── start-catalog-builder-gui.sh/.ps1    # Launch catalog builder GUI
│   └── generate-sample-data.sh/.ps1         # Generate test context files
├── src/                           # Source code
│   ├── catalog_builder/           # Catalog generation CLI
│   ├── catalog_builder_gui/       # Catalog Builder GUI
│   ├── architecture_scorer/       # Scoring engine
│   └── architecture_recommendations_app/  # Customer web app
├── docs/                          # Documentation
│   ├── design/                    # Design decisions & specifications
│   │   ├── decisions/             # Architecture Decision Records (ADRs)
│   │   ├── glossary.md            # Key terms
│   │   └── README.md              # "Why does it work this way?"
│   ├── images/                    # Screenshots
│   └── *.md                       # Component docs
├── infra/                         # Infrastructure as Code
│   ├── main.bicep                 # Azure deployment template
│   └── modules/                   # Bicep modules
├── tests/                         # Tests
│   └── generate_sample_data.py    # Sample data generator
├── examples/                      # Example files
│   └── context_files/             # Sample context files (25 scenarios)
└── architecture-catalog.json      # Generated catalog
```

## Version

**Current: v1.4.0** (2026-02-04)

Latest features:
- **Dr. Migrate Integration** - Get recommendations for ALL applications (not just Java/.NET)
- Auto-detection of Dr. Migrate vs App Cat file formats
- LLM prompt for extracting data from Dr. Migrate AI Advisor
- CLI commands for batch context file generation

See [CHANGELOG.md](CHANGELOG.md) for full release history.

## License

MIT
