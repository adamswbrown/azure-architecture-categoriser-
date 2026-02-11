---
layout: default
title: Blob Storage Upload
---

# Azure Blob Storage Upload

The Catalog Builder can upload the generated `architecture-catalog.json` directly to Azure Blob Storage. This is useful for CI/CD pipelines where the catalog is built and then published to a known storage account for consumption by downstream services.

## Installation

Blob upload requires the `azure` optional dependency group:

```bash
pip install -e ".[azure]"
```

This installs:
- `azure-storage-blob` -- Azure Blob Storage client
- `azure-identity` -- DefaultAzureCredential support (managed identity, Azure CLI, OIDC)

## Authentication Methods

Three authentication methods are supported, in priority order:

### 1. SAS URL (Recommended for CI/CD)

A Shared Access Signature (SAS) URL embeds the authentication token directly in the URL. This is the simplest option for pipelines -- no SDK configuration needed beyond the URL itself.

```bash
# Blob-level SAS URL (uploads to exact blob path)
catalog-builder upload \
  --catalog architecture-catalog.json \
  --blob-url "https://myaccount.blob.core.windows.net/catalogs/architecture-catalog.json?sv=2022-11-02&ss=b&srt=o&sp=cw&se=2025-12-31&sig=..."

# Container-level SAS URL (blob name derived from filename)
catalog-builder upload \
  --catalog architecture-catalog.json \
  --blob-url "https://myaccount.blob.core.windows.net/catalogs?sv=2022-11-02&ss=b&srt=co&sp=cw&se=2025-12-31&sig=..."
```

**Generating a SAS token** (Azure CLI):

```bash
# Generate a blob-level SAS URL valid for 24 hours
az storage blob generate-sas \
  --account-name myaccount \
  --container-name catalogs \
  --name architecture-catalog.json \
  --permissions cw \
  --expiry $(date -u -d "+24 hours" +%Y-%m-%dT%H:%MZ) \
  --auth-mode login \
  --as-user \
  --full-uri

# Generate a container-level SAS URL
az storage container generate-sas \
  --account-name myaccount \
  --name catalogs \
  --permissions cw \
  --expiry $(date -u -d "+24 hours" +%Y-%m-%dT%H:%MZ) \
  --auth-mode login \
  --as-user
```

### 2. Connection String

Standard Azure Storage connection string. Common for application configuration and local development.

```bash
catalog-builder upload \
  --catalog architecture-catalog.json \
  --connection-string "DefaultEndpointsProtocol=https;AccountName=myaccount;AccountKey=...;EndpointSuffix=core.windows.net" \
  --container-name catalogs
```

You can also set the connection string via environment variable:

```bash
export AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;..."
catalog-builder upload --catalog architecture-catalog.json
```

### 3. DefaultAzureCredential

Uses the Azure Identity library to authenticate via managed identity, Azure CLI, environment variables, or OIDC. Best for production environments with RBAC.

```bash
# Uses az login credentials, managed identity, or OIDC
catalog-builder upload \
  --catalog architecture-catalog.json \
  --account-url "https://myaccount.blob.core.windows.net" \
  --container-name catalogs
```

**Required RBAC role**: The identity needs `Storage Blob Data Contributor` on the target container.

## CLI Reference

### `upload` Command

Upload an existing catalog file to Azure Blob Storage.

```bash
catalog-builder upload --catalog <path> [auth-options] [options]
```

| Option | Env Var | Description |
|--------|---------|-------------|
| `--catalog` | -- | Path to catalog JSON file (required) |
| `--blob-url` | `CATALOG_BLOB_URL` | Full SAS URL (blob or container level) |
| `--connection-string` | `AZURE_STORAGE_CONNECTION_STRING` | Storage account connection string |
| `--account-url` | `AZURE_STORAGE_ACCOUNT_URL` | Storage account URL (for DefaultAzureCredential) |
| `--container-name` | `CATALOG_CONTAINER_NAME` | Blob container name (default: `catalogs`) |
| `--blob-name` | -- | Blob name (defaults to catalog filename) |
| `--overwrite/--no-overwrite` | -- | Overwrite existing blob (default: overwrite) |
| `-v, --verbose` | -- | Show detailed output |

### `build-catalog --upload-url`

Build and upload in a single step:

```bash
catalog-builder build-catalog \
  --repo-path ./architecture-center \
  --out architecture-catalog.json \
  --upload-url "https://myaccount.blob.core.windows.net/catalogs/catalog.json?sv=..."
```

The `--upload-url` option accepts a SAS URL (same as `--blob-url` on the `upload` command). If the build succeeds, the catalog is uploaded automatically. The `CATALOG_BLOB_URL` environment variable is also supported.

## Blob Metadata

Uploaded blobs include metadata extracted from the catalog for easy inspection in Azure Portal:

| Metadata Key | Example Value |
|-------------|---------------|
| `catalog_version` | `1.0.0` |
| `total_architectures` | `50` |
| `generated_at` | `2025-01-15T10:00:00Z` |
| `source_commit` | `abc123def456` |
| `source_repo` | `https://github.com/MicrosoftDocs/architecture-center` |

The content type is set to `application/json` with UTF-8 encoding.

## CI/CD Integration

### GitHub Actions

```yaml
name: Build and Publish Catalog

on:
  schedule:
    - cron: '0 6 * * 1'  # Weekly on Monday at 6am UTC
  workflow_dispatch:

jobs:
  build-catalog:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -e ".[azure]"

      - name: Clone Architecture Center
        run: git clone --depth 1 https://github.com/MicrosoftDocs/architecture-center.git

      - name: Build and upload catalog
        env:
          CATALOG_BLOB_URL: ${{ secrets.CATALOG_BLOB_SAS_URL }}
        run: |
          catalog-builder build-catalog \
            --repo-path ./architecture-center \
            --out architecture-catalog.json \
            --upload-url "$CATALOG_BLOB_URL"
```

### GitHub Actions with OIDC

For keyless authentication using federated identity:

```yaml
jobs:
  build-catalog:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -e ".[azure]"

      - name: Azure Login (OIDC)
        uses: azure/login@v2
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}

      - name: Clone Architecture Center
        run: git clone --depth 1 https://github.com/MicrosoftDocs/architecture-center.git

      - name: Build catalog
        run: |
          catalog-builder build-catalog \
            --repo-path ./architecture-center \
            --out architecture-catalog.json

      - name: Upload catalog
        run: |
          catalog-builder upload \
            --catalog architecture-catalog.json \
            --account-url "https://myaccount.blob.core.windows.net" \
            --container-name catalogs
```

### Azure DevOps Pipelines

```yaml
trigger:
  - main

pool:
  vmImage: 'ubuntu-latest'

steps:
  - task: UsePythonVersion@0
    inputs:
      versionSpec: '3.11'

  - script: pip install -e ".[azure]"
    displayName: Install dependencies

  - script: git clone --depth 1 https://github.com/MicrosoftDocs/architecture-center.git
    displayName: Clone Architecture Center

  - script: |
      catalog-builder build-catalog \
        --repo-path ./architecture-center \
        --out architecture-catalog.json \
        --upload-url "$(CATALOG_BLOB_SAS_URL)"
    displayName: Build and upload catalog
```

## Troubleshooting

### "Azure Blob Storage upload requires the 'azure' extras"

Install the Azure dependencies:

```bash
pip install -e ".[azure]"
```

### "No authentication method provided"

Supply at least one of `--blob-url`, `--connection-string`, or `--account-url`.

### "The specified blob already exists" (409 Conflict)

The blob already exists and `--no-overwrite` was specified. Either use `--overwrite` (the default) or delete the existing blob first.

### "AuthorizationPermissionMismatch" (403 Forbidden)

The SAS token or identity does not have write permissions on the target container. Ensure:
- SAS tokens include `c` (create) and `w` (write) permissions
- RBAC identities have `Storage Blob Data Contributor` role
- The token has not expired

### "ContainerNotFound" (404 Not Found)

The target container does not exist. Create it first:

```bash
az storage container create \
  --name catalogs \
  --account-name myaccount \
  --auth-mode login
```

## Related Documentation

- [Catalog Builder](./catalog-builder.md) -- Building architecture catalogs
- [Azure Deployment](./azure-deployment.md) -- Deploying the full application to Azure
- [Configuration Reference](./configuration.md) -- Full configuration options
