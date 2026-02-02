# Deploying to Azure Container Apps

This guide covers deploying the Azure Architecture Recommender to Azure Container Apps using GitHub Actions.

## Architecture

```
GitHub Actions                    Azure
┌─────────────────┐              ┌─────────────────────────────────────┐
│ docker-publish  │──(image)────▶│ ghcr.io                             │
│                 │              │ (GitHub Container Registry)         │
└────────┬────────┘              └───────────────┬─────────────────────┘
         │                                       │
         │ triggers                              │ pulls
         ▼                                       ▼
┌─────────────────┐              ┌─────────────────────────────────────┐
│ deploy-azure    │──(OIDC)─────▶│ Azure Container Apps                │
│                 │              │ ├── Log Analytics                   │
└─────────────────┘              │ ├── Container Apps Environment      │
                                 │ └── Container App (port 8501)       │
                                 └─────────────────────────────────────┘
```

## Prerequisites

1. **Azure Subscription** with permissions to create resources
2. **GitHub repository** with Actions enabled
3. **Azure CLI** installed locally (for initial setup)

## Setup Steps

### 1. Create Azure Service Principal with OIDC

Federated credentials allow GitHub Actions to authenticate without storing secrets.

```bash
# Set your variables
SUBSCRIPTION_ID="305b3db0-4019-485b-95e9-574f7c20ead4"  # azure@askadam.cloud
GITHUB_ORG="adamswbrown"
GITHUB_REPO="azure-architecture-categoriser"

# Create an App Registration
az ad app create --display-name "github-azarch-deployer"

# Get the App ID
APP_ID=$(az ad app list --display-name "github-azarch-deployer" --query "[0].appId" -o tsv)

# Create a Service Principal
az ad sp create --id $APP_ID

# Get the Object ID of the Service Principal
SP_OBJECT_ID=$(az ad sp show --id $APP_ID --query "id" -o tsv)

# Assign Contributor role at subscription level
az role assignment create \
  --assignee-object-id $SP_OBJECT_ID \
  --assignee-principal-type ServicePrincipal \
  --role "Contributor" \
  --scope "/subscriptions/${SUBSCRIPTION_ID}"

# Get Tenant ID
TENANT_ID=$(az account show --query tenantId -o tsv)

echo "=== Add these as GitHub Secrets ==="
echo "AZURE_CLIENT_ID: $APP_ID"
echo "AZURE_TENANT_ID: $TENANT_ID"
echo "AZURE_SUBSCRIPTION_ID: $SUBSCRIPTION_ID"
```

### 2. Add Federated Credential for GitHub Actions

```bash
# Create federated credential for main branch
az ad app federated-credential create \
  --id $APP_ID \
  --parameters '{
    "name": "github-main-branch",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:'${GITHUB_ORG}'/'${GITHUB_REPO}':ref:refs/heads/main",
    "audiences": ["api://AzureADTokenExchange"]
  }'

# Create federated credential for workflow_dispatch (manual runs)
az ad app federated-credential create \
  --id $APP_ID \
  --parameters '{
    "name": "github-workflow-dispatch",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:'${GITHUB_ORG}'/'${GITHUB_REPO}':environment:production",
    "audiences": ["api://AzureADTokenExchange"]
  }'
```

### 3. Add GitHub Secrets

Go to **Settings → Secrets and variables → Actions** and add:

| Secret Name | Value |
|-------------|-------|
| `AZURE_CLIENT_ID` | App Registration Application (client) ID |
| `AZURE_TENANT_ID` | Azure AD Tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Azure Subscription ID |

### 4. First Deployment (Create Infrastructure)

Run the workflow manually with infrastructure creation:

1. Go to **Actions → Deploy to Azure Container Apps**
2. Click **Run workflow**
3. Select:
   - Environment: `prod`
   - Image tag: `latest`
   - **Deploy/update infrastructure: ✅ checked**
4. Click **Run workflow**

This creates:
- Resource Group: `rg-azarch-prod`
- Log Analytics Workspace
- Container Apps Environment
- Container App with your image

### 5. Subsequent Deployments

After initial setup, deployments happen automatically:
- Push to `main` → builds image → deploys to Container Apps

Or trigger manually without infrastructure flag to just update the image.

## Environments

| Environment | Resource Group | Scale | Zone Redundant |
|-------------|----------------|-------|----------------|
| `dev` | rg-azarch-dev | 0-1 replicas | No |
| `staging` | rg-azarch-staging | 0-1 replicas | No |
| `prod` | rg-azarch-prod | 1-3 replicas | Yes |

## Cost Estimate

| Component | Dev/Staging | Prod |
|-----------|-------------|------|
| Container Apps | ~$0 (scale to zero) | ~$15-50/month |
| Log Analytics | ~$2/month | ~$5/month |
| **Total** | **~$2/month** | **~$20-55/month** |

*Costs vary based on usage and region.*

## Monitoring

View logs in Azure Portal:
1. Go to **Container Apps → Your App → Logs**
2. Or use Azure CLI:

```bash
az containerapp logs show \
  --name ca-azarch-recommender-prod \
  --resource-group rg-azarch-prod \
  --follow
```

## Troubleshooting

### Deployment fails with "Resource group not found"

First deployment must have **Deploy/update infrastructure** checked.

### App not accessible

Check the Container App logs:
```bash
az containerapp logs show \
  --name ca-azarch-recommender-prod \
  --resource-group rg-azarch-prod \
  --type system
```

### File uploads fail with 400 Bad Request

**Problem**: Uploading context files returns a 400 error in the browser, but uploads work locally.

**Cause**: Streamlit's CORS and XSRF protection configuration conflict in reverse proxy environments.

**Solution**: This is already configured correctly in the Dockerfile:
```dockerfile
ENV STREAMLIT_SERVER_ENABLE_CORS=true
ENV STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false
```

These settings are required because:
- Azure Container Apps acts as a reverse proxy with TLS termination
- Authentication and security are handled at the platform level (not by Streamlit)
- The combination of CORS enabled + XSRF disabled allows file uploads through the proxy

**If you're experiencing this after deployment:**
1. Rebuild the Docker image to ensure latest configuration
2. Redeploy the container app with the updated image
3. Check logs for any CORS-related warnings:
```bash
az containerapp logs show \
  --name ca-azarch-recommender-prod \
  --resource-group rg-azarch-prod \
  --follow | grep -i cors
```

### Sample files show "File not found"

**Problem**: Sample files are not accessible when clicking "Try a Sample" in Azure deployment.

**Cause**: Path resolution differences between local development and containerized environments.

**Solution**: This has been fixed with improved path resolution that searches multiple locations:
1. Relative to the application file
2. Current working directory
3. Docker standard path (`/app/examples/context_files`)
4. Common development locations

**If updating from an older version:**
1. Rebuild the Docker image
2. Redeploy to Azure Container Apps
3. Clear browser cache (Ctrl+Shift+Del or Cmd+Shift+Del on macOS)
4. Refresh the page

### OIDC authentication fails

Ensure federated credentials match exactly:
- Repository name is case-sensitive
- Branch name must match (`main` not `master`)

```bash
# List federated credentials
az ad app federated-credential list --id $APP_ID
```

## Manual Deployment (without GitHub Actions)

```bash
# Login to Azure
az login

# Deploy infrastructure
az deployment sub create \
  --location uksouth \
  --template-file infra/main.bicep \
  --parameters environment=prod

# Update image
az containerapp update \
  --name ca-azarch-recommender-prod \
  --resource-group rg-azarch-prod \
  --image ghcr.io/adamswbrown/azure-architecture-categoriser:latest
```

## Cleanup

To delete all resources:

```bash
# Delete resource group (includes all resources)
az group delete --name rg-azarch-prod --yes

# Delete the App Registration (optional)
az ad app delete --id $APP_ID
```
