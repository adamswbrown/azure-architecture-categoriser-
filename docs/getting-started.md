---
layout: default
title: Getting Started
---

# Getting Started with Azure Architecture Categoriser

This guide will help you set up and run the Azure Architecture Categoriser in just a few minutes.

## Installation

### Prerequisites

- **Python 3.9+**
- **Git**
- **Docker** (optional, for containerized deployment)

### Clone the Repository

```bash
git clone https://github.com/adamswbrown/azure-architecture-categoriser.git
cd azure-architecture-categoriser
```

### Option 1: Local Python Setup

1. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the Recommendations App:**
   ```bash
   python -m src.architecture_recommendations_app.app
   ```

   The app will start on `http://localhost:8000`

### Option 2: Docker Setup

1. **Build the Docker image:**
   ```bash
   docker build -t azure-arch-categoriser .
   ```

2. **Run the container:**
   ```bash
   docker run -p 8000:8000 azure-arch-categoriser
   ```

3. **Access at `http://localhost:8000`**

### Using Provided Scripts

The repository includes convenience scripts for both Linux/Mac and Windows:

**Linux/Mac:**
```bash
./bin/start-recommendations-app.sh
```

**Windows PowerShell:**
```powershell
.\bin\start-recommendations-app.ps1
```

---

## First Run: Step-by-Step

### Step 1: Get a Sample Context File

You have two options:

**Option A: Use a provided example**
- Download from `examples/context_files/` directory
- These are sample application assessment files

**Option B: Generate from Dr. Migrate**
- Export your application assessment from Dr. Migrate
- Use the provided LLM prompt (see [Dr. Migrate Integration](./drmigrate-integration.md))
- Save the JSON response as your context file

### Step 2: Start the Application

Follow the installation steps above to start the application.

### Step 3: Upload Your Context File

1. Open `http://localhost:8000` in your browser
2. Click "Upload Application Context"
3. Select your context file (JSON format)
4. Click "Upload"

### Step 4: Review Application Data

The system will automatically detect and display:
- Application name and type
- Detected technologies (frameworks, databases, etc.)
- Server information and complexity
- Current assessment data

### Step 5: Answer Optional Questions (Optional)

Answer clarifying questions to improve recommendation accuracy:
- **Availability Requirements** - Single region, multi-region active-passive, or active-active
- **Security Level** - Basic, enterprise, or highly regulated
- **Operating Model** - DevOps, SRE, or transitional
- **Cost Profile** - Cost-optimized, innovation-first, or scale-optimized

> **Tip:** If you're unsure about any answer, skip it! The system will use defaults based on your application profile.

### Step 6: Get Your Recommendations

Click "Get Recommendations" to see:
- **Top-ranked architectures** with match scores
- **Why each is recommended** based on your application
- **Potential challenges** to consider
- **Links to Microsoft Learn** for detailed implementation guides

### Step 7: Export Your Report

Click "Export as PDF" to save a professional report including:
- Executive summary
- Top recommendations with scores
- Detailed explanations
- Implementation guidance

---

## Common Tasks

### Exploring Different Scenarios

You can upload multiple context files and compare recommendations:

1. Upload your first application
2. Get recommendations
3. Use the back button to upload a different application
4. Compare the recommendations side-by-side

### Customizing the Architecture Catalog

By default, the system uses the pre-built catalog from the Azure Architecture Center. To customize:

See [Catalog Builder Guide](./catalog-builder.md) for details on:
- Filtering architectures
- Adding custom architectures
- Adjusting scoring weights
- Validating catalog quality

### Publishing the Catalog to Azure Blob Storage

After building a catalog, you can publish it to Azure Blob Storage so it can be shared across environments or consumed by other services.

**Install the Azure extras:**
```bash
pip install -e ".[azure]"
```

**Build and upload in one step:**
```bash
catalog-builder build-catalog \
  --repo-path ./architecture-center \
  --out catalog.json \
  --upload-url "https://myaccount.blob.core.windows.net/catalogs/catalog.json?sv=..."
```

**Or upload an existing catalog separately:**
```bash
catalog-builder upload \
  --catalog architecture-catalog.json \
  --blob-url "$CATALOG_BLOB_SAS_URL"
```

Three authentication methods are supported: SAS URLs, connection strings, and DefaultAzureCredential (managed identity). See [Blob Storage Upload](./blob-storage-upload.md) for full details and CI/CD examples.

### Batch Processing

Process multiple applications programmatically:

```python
from src.architecture_recommendations_app.recommendation_engine import RecommendationEngine

engine = RecommendationEngine()

# Load a context file
context = engine.load_context_file("path/to/context.json")

# Get recommendations
recommendations = engine.score_architectures(context)

# Export results
engine.export_report("output.pdf")
```

See [Architecture Scorer Documentation](./architecture-scorer.md) for API details.

---

## Understanding Your Results

### Match Score

Each architecture receives a match score (0-100) based on:
- **Runtime Model Match** (35% weight) - Does the architecture fit your application's execution model?
- **Modernization Fit** (25% weight) - Does it align with your desired migration path?
- **Security Alignment** (20% weight) - Does it meet your security requirements?
- **Cost Profile Match** (20% weight) - Does it align with your cost priorities?

### Recommendation Explanations

Each recommendation includes:
- **Strengths** - Why this architecture fits your needs
- **Considerations** - Potential challenges or required changes
- **Best For** - Ideal scenarios for this architecture
- **Learn More** - Links to official Microsoft documentation

---

## Troubleshooting

### "Unable to parse context file"
- Ensure your JSON file is valid
- Check the file format matches expected schema
- See [Dr. Migrate Integration](./drmigrate-integration.md) for correct format

### "No architectures matched"
- Check if your filter settings are too restrictive
- Try adjusting security level or operating model requirements
- Review [Configuration Guide](./configuration.md)

### Port already in use
- Change the port: `python -m src.architecture_recommendations_app.app --port 8001`
- Or kill the existing process on port 8000

### Need Help?
- Check [Configuration Guide](./configuration.md) for advanced settings
- Review [Architecture Categorization Guide](./architecture-categorization-guide.md)
- Open an issue on [GitHub](https://github.com/adamswbrown/azure-architecture-categoriser/issues)

---

## Next Steps

- 📚 [Read the full Architecture Categorization Guide](./architecture-categorization-guide.md)
- ⚙️ [Configure advanced settings](./configuration.md)
- 🚀 [Deploy to Azure](./azure-deployment.md)
- 🏗️ [Customize the architecture catalog](./catalog-builder.md)

