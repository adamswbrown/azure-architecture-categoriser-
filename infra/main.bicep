// Azure Container Apps infrastructure for Azure Architecture Recommender
// Deploy with: az deployment sub create --location <region> --template-file main.bicep

targetScope = 'subscription'

@description('Environment name (dev, staging, prod)')
@allowed(['dev', 'staging', 'prod'])
param environment string = 'prod'

@description('Azure region for resources')
param location string = 'australiaeast'

@description('Container image to deploy')
param containerImage string = 'ghcr.io/adamswbrown/azure-architecture-categoriser:latest'

@description('GitHub Container Registry username (for private repos)')
param ghcrUsername string = ''

@description('GitHub Container Registry token (for private repos)')
@secure()
param ghcrToken string = ''

// Resource naming
var prefix = 'azarch'
var resourceGroupName = 'rg-${prefix}-${environment}'
var containerAppEnvName = 'cae-${prefix}-${environment}'
var containerAppName = 'ca-${prefix}-recommender-${environment}'
var logAnalyticsName = 'log-${prefix}-${environment}'

// Create resource group
resource rg 'Microsoft.Resources/resourceGroups@2023-07-01' = {
  name: resourceGroupName
  location: location
  tags: {
    environment: environment
    application: 'azure-architecture-recommender'
    managedBy: 'bicep'
  }
}

// Deploy container app infrastructure
module containerApp 'modules/container-app.bicep' = {
  scope: rg
  name: 'container-app-deployment'
  params: {
    location: location
    environment: environment
    containerAppEnvName: containerAppEnvName
    containerAppName: containerAppName
    logAnalyticsName: logAnalyticsName
    containerImage: containerImage
    ghcrUsername: ghcrUsername
    ghcrToken: ghcrToken
  }
}

// Outputs
output resourceGroupName string = rg.name
output containerAppUrl string = containerApp.outputs.containerAppUrl
output containerAppName string = containerApp.outputs.containerAppName
