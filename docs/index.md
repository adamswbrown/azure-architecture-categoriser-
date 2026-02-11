---
layout: default
title: Azure Architecture Categoriser
---

# Azure Architecture Categoriser

A complete solution for matching applications to Azure architecture patterns based on assessment data.

## What Does This Tool Do?

The **Recommendations App** is a web-based wizard that helps you find the right Azure architecture for your application. Simply upload your application assessment data, answer a few optional questions, and receive ranked architecture recommendations with detailed explanations.

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

## Quick Start

### Get Started in 5 Minutes

1. **Download a sample context file** - [Example Java Context File](https://github.com/adamswbrown/azure-architecture-categoriser/tree/main/examples)
2. **Open the Recommendations App** - Start the application using the provided scripts
3. **Upload & Explore** - Upload your context file and see your personalized recommendations

For detailed setup instructions, see [Getting Started Guide](./getting-started.md).

### Prerequisites

Before getting started, ensure you have:
- Python 3.9 or higher
- Docker (optional, for containerized deployment)
- An application context file from [Dr. Migrate](https://drmigrate.com)

---

## Key Components

### 📊 Architecture Recommendations App
An interactive web application that delivers personalized Azure architecture recommendations based on your application profile.

[Learn more →](./recommendations-app.md)

### 🏗️ Catalog Builder
A utility to generate and validate the architecture catalog from Azure Architecture Center content.

[Learn more →](./catalog-builder.md)

### ⭐ Architecture Scorer
The core scoring engine that evaluates how well architectures match your application needs.

[Learn more →](./architecture-scorer.md)

---

## Documentation

- **[Architecture Categorization Guide](./architecture-categorization-guide.md)** - Understanding how architectures are categorized and evaluated
- **[Recommendations App Guide](./recommendations-app.md)** - Using the recommendations application
- **[Catalog Builder Guide](./catalog-builder.md)** - Building and customizing the architecture catalog
- **[Architecture Scorer Documentation](./architecture-scorer.md)** - How the scoring algorithm works
- **[Configuration Guide](./configuration.md)** - Customizing application behavior
- **[Azure Deployment](./azure-deployment.md)** - Deploying to Azure
- **[Blob Storage Upload](./blob-storage-upload.md)** - Publishing catalogs to Azure Blob Storage
- **[Dr. Migrate Integration](./drmigrate-integration.md)** - Integrating with Dr. Migrate
- **[Design Decisions](./design/)** - Technical design documentation

---

## Input Formats

This tool accepts **two types of input files**:

### Option 1: App Cat Context Files (Java/.NET Applications)
For Java and .NET applications, Dr. Migrate uses [AppCat](https://learn.microsoft.com/en-us/azure/migrate/appcat/dotnet) to evaluate Azure readiness.

### Option 2: Dr. Migrate Data Exports (ALL Applications)
For any application, export your assessment data and use the provided LLM prompt to generate a context file.

[See Dr. Migrate Integration Guide →](./drmigrate-integration.md)

---

## Features

✅ Multi-dimensional architecture scoring
✅ Support for custom architecture catalogs
✅ Detailed recommendation explanations
✅ PDF report generation
✅ Web-based GUI for easy access
✅ Batch processing capabilities
✅ Flexible configuration options

---

## Support

- 📖 [Read the full documentation](.)
- 🐛 [Report issues on GitHub](https://github.com/adamswbrown/azure-architecture-categoriser/issues)
- 💬 [Review design decisions](./design/)

---

## License

See LICENSE file in the repository for details.

