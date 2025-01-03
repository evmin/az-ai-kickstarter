metadata name = 'hello-ai-world'
metadata description = 'Deploys the infrastructure for Hello AI World'
metadata author = 'AI GBB EMEA <dominique.broeglin@microsoft.com>'

/* -------------------------------------------------------------------------- */
/*                                 PARAMETERS                                 */
/* -------------------------------------------------------------------------- */

@minLength(1)
@maxLength(64)
@description('Name of the environment which is used to generate a short unique hash used in all resources.')
param environmentName string

@description('Principal ID of the user running the deployment')
param azurePrincipalId string

@description('Extra tags to be applied to provisioned resources')
param extraTags object = {}

@description('Location for all resources')
param location string = resourceGroup().location

/* ---------------------------- Shared Resources ---------------------------- */

@maxLength(63)
@description('Name of the log analytics workspace to deploy. If not specified, a name will be generated. The maximum length is 63 characters.')
param logAnalyticsWorkspaceName string = ''

@maxLength(255)
@description('Name of the application insights to deploy. If not specified, a name will be generated. The maximum length is 255 characters.')
param applicationInsightsName string = ''

@description('Application Insights Location')
param appInsightsLocation string = location

@description('The auth tenant id for the frontend and backend app (leave blank in AZD to use your current tenant)')
param authTenantId string = '' // Make sure authTenantId is set if not using AZD

@description('Name of the authentication client secret in the key vault')
param authClientSecretName string = 'AZURE-AUTH-CLIENT-SECRET'

@description('The auth client id for the frontend and backend app')
param authClientId string = ''

@description('Client secret of the authentication client')
@secure()
param authClientSecret string = ''

@maxLength(50)
@description('Name of the container registry to deploy. If not specified, a name will be generated. The name is global and must be unique within Azure. The maximum length is 50 characters.')
param containerRegistryName string = ''

@maxLength(60)
@description('Name of the container apps environment to deploy. If not specified, a name will be generated. The maximum length is 60 characters.')
param containerAppsEnvironmentName string = ''

/* -------------------------------- Frontend -------------------------------- */

@maxLength(32)
@description('Name of the frontend container app to deploy. If not specified, a name will be generated. The maximum length is 32 characters.')
param frontendContainerAppName string = ''

@description('Set if the frontend container app already exists.')
param frontendExists bool = false

/* --------------------------------- Backend -------------------------------- */

@maxLength(32)
@description('Name of the backend container app to deploy. If not specified, a name will be generated. The maximum length is 32 characters.')
param backendContainerAppName string = ''

@description('Set if the backend container app already exists.')
param backendExists bool = false

/* -------------------------------------------------------------------------- */
/*                                  VARIABLES                                 */
/* -------------------------------------------------------------------------- */

// Load abbreviations from JSON file
var abbreviations = loadJsonContent('./abbreviations.json')

@description('Generate a unique token to make global resource names unique')
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))

@description('Name of the environment with only alphanumeric characters. Used for resource names that require alphanumeric characters only')
var alphaNumericEnvironmentName = replace(replace(environmentName, '-', ''), ' ', '')

@description('Tags to be applied to all provisioned resources')
var tags = union(
  {
    'azd-env-name': environmentName
    solution: 'hello-ai-world'
  },
  extraTags
)

/* --------------------- Globally Unique Resource Names --------------------- */

var _applicationInsightsName = !empty(applicationInsightsName)
  ? applicationInsightsName
  : take('${abbreviations.insightsComponents}${environmentName}', 255)
var _logAnalyticsWorkspaceName = !empty(logAnalyticsWorkspaceName)
  ? logAnalyticsWorkspaceName
  : take('${abbreviations.operationalInsightsWorkspaces}${environmentName}', 63)
var _containerRegistryName = !empty(containerRegistryName)
  ? containerRegistryName
  : take('${abbreviations.containerRegistryRegistries}${take(alphaNumericEnvironmentName, 35)}${resourceToken}', 50)
var _keyVaultName = take('${abbreviations.keyVaultVaults}${alphaNumericEnvironmentName}${resourceToken}', 24)
var _storageAccountName = take(
  '${abbreviations.storageStorageAccounts}${alphaNumericEnvironmentName}${resourceToken}',
  24
)
var _azureOpenAiName = take('${abbreviations.cognitiveServicesOpenAI}${alphaNumericEnvironmentName}', 63)
var _aiHubName = take('${abbreviations.aiPortalHub}${environmentName}', 260)
var _aiProjectName = take('${abbreviations.aiPortalProject}${environmentName}', 260)
var _aiSearchServiceName = take('${abbreviations.searchSearchServices}${environmentName}', 260)
var _containerAppsEnvironmentName = !empty(containerAppsEnvironmentName)
  ? containerAppsEnvironmentName
  : take('${abbreviations.appManagedEnvironments}${environmentName}', 60)

/* ----------------------------- Resource Names ----------------------------- */

var _frontendIdentityName = take(
  '${abbreviations.managedIdentityUserAssignedIdentities}frontend-${environmentName}',
  32
)
var _frontendContainerAppName = !empty(frontendContainerAppName)
  ? frontendContainerAppName
  : take('${abbreviations.appContainerApps}frontend-${environmentName}', 32)
var _backendIdentityName = take('${abbreviations.managedIdentityUserAssignedIdentities}backend-${environmentName}', 32)
var _backendContainerAppName = !empty(backendContainerAppName)
  ? backendContainerAppName
  : take('${abbreviations.appContainerApps}backend-${environmentName}', 32)

/* -------------------------------------------------------------------------- */
/*                                  RESOURCES                                 */
/* -------------------------------------------------------------------------- */

/* -------------------------------- AI Infra  ------------------------------- */

module hub 'modules/ai/hub.bicep' = {
  name: 'hub'
  params: {
    location: location
    tags: tags
    name: _aiHubName
    displayName: _aiHubName
    keyVaultId: keyVault.outputs.resourceId
    storageAccountId: storageAccount.outputs.resourceId
    containerRegistryId: containerRegistry.outputs.resourceId
    applicationInsightsId: appInsights.id
    openAiName: azureOpenAi.outputs.name
    openAiConnectionName: 'aoai-connection'
    openAiContentSafetyConnectionName: 'aoai-content-safety-connection'
    aiSearchName: searchService.outputs.name
    aiSearchConnectionName: 'search-service-connection'
  }
}

module project 'modules/ai/project.bicep' = {
  name: 'project'
  params: {
    location: location
    tags: tags
    name: _aiProjectName
    displayName: _aiProjectName
    hubName: hub.outputs.name
    
  }
}

module storageAccount 'br/public:avm/res/storage/storage-account:0.15.0' = {
  name: 'storageAccount'
  scope: resourceGroup()
  params: {
    location: location
    tags: tags
    name: _storageAccountName
    kind: 'StorageV2'
    blobServices: {
      corsRules: [
        {
          allowedOrigins: [
            'https://mlworkspace.azure.ai'
            'https://ml.azure.com'
            'https://*.ml.azure.com'
            'https://ai.azure.com'
            'https://*.ai.azure.com'
            'https://mlworkspacecanary.azure.ai'
            'https://mlworkspace.azureml-test.net'
          ]
          allowedMethods: [
            'GET'
            'HEAD'
            'POST'
            'PUT'
            'DELETE'
            'OPTIONS'
            'PATCH'
          ]
          maxAgeInSeconds: 1800
          exposedHeaders: [
            '*'
          ]
          allowedHeaders: [
            '*'
          ]
        }
      ]
      containers: [
        {
          name: 'default'
          roleAssignments: [
            {
              roleDefinitionIdOrName: 'Storage Blob Data Contributor'
              principalId: backendIdentity.outputs.principalId
              principalType: 'ServicePrincipal'
            }
          ]
        }
      ]
      deleteRetentionPolicy: {
        allowPermanentDelete: false
        enabled: false
      }
      shareDeleteRetentionPolicy: {
        enabled: true
        days: 7
      }
    }
  }
}

module azureOpenAi 'modules/ai/cognitiveservices.bicep' = {
  name: 'cognitiveServices'
  params: {
    location: location
    tags: tags
    name: _azureOpenAiName
    kind: 'AIServices'
    deployments: [
      {
        name: 'gpt-4o'
        model: {
          format: 'OpenAI'
          name: 'gpt-4o'
          version: '2024-05-13'
        }
      }
    ]
  }
}

module searchService 'br/public:avm/res/search/search-service:0.8.2' = {
  name: _aiSearchServiceName
  scope: resourceGroup()
  params: {
    location: location
    tags: tags
    name: _aiProjectName
    sku: 'standard'
  }
}


/* ---------------------------- Observability  ------------------------------ */

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: _logAnalyticsWorkspaceName
  location: location
  properties: {
    retentionInDays: 30
  }
  tags: tags
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: _applicationInsightsName
  location: appInsightsLocation
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

/* ------------------------ Common App Resources  -------------------------- */

module containerRegistry 'modules/app/container-registry.bicep' = {
  name: _containerRegistryName
  scope: resourceGroup()
  params: {
    location: location
    pullingIdentityNames: [
      _frontendIdentityName
      _backendIdentityName
    ]
    tags: tags
    name: '${abbreviations.containerRegistryRegistries}${resourceToken}'
  }
}

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: _containerAppsEnvironmentName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
    daprAIConnectionString: appInsights.properties.ConnectionString
  }
}

module keyVault 'br/public:avm/res/key-vault/vault:0.11.0' = {
  name: 'keyVault'
  scope: resourceGroup()
  params: {
    location: location
    tags: tags
    name: _keyVaultName
    enableRbacAuthorization: true
    enablePurgeProtection: false // Set to true to if you deploy in production and want to protect against accidental deletion
    roleAssignments: [
      {
        roleDefinitionIdOrName: 'Key Vault Secrets User'
        principalId: frontendIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
      }
      {
        roleDefinitionIdOrName: 'Key Vault Secrets User'
        principalId: backendIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
      }
      {
        principalId: azurePrincipalId
        roleDefinitionIdOrName: 'Key Vault Administrator'
      }
    ]
    secrets: empty(authClientSecret)
      ? []
      : [
          {
            name: authClientSecretName
            value: authClientSecret
          }
        ]
  }
}

/* ------------------------------ Frontend App ------------------------------ */

module frontendIdentity './modules/app/identity.bicep' = {
  name: 'frontendIdentity'
  scope: resourceGroup()
  params: {
    location: location
    identityName: _frontendIdentityName
  }
}

var keyvaultIdentities = authClientSecret != ''
  ? {
      'microsoft-provider-authentication-secret': {
        keyVaultUrl: '${keyVault.outputs.uri}secrets/${authClientSecretName}'
        identity: frontendIdentity.outputs.resourceId
      }
    }
  : {}

module frontendApp 'modules/app/container-apps.bicep' = {
  name: 'frontend-container-app'
  scope: resourceGroup()
  params: {
    name: _frontendContainerAppName
    tags: tags
    identityId: frontendIdentity.outputs.resourceId
    containerAppsEnvironmentName: containerAppsEnvironment.name
    containerRegistryName: containerRegistry.outputs.name
    exists: frontendExists
    serviceName: 'frontend' // Must match the service name in azure.yaml
    env: {
      // BACKEND_ENDPOINT: backendApp.outputs.URL
      BACKEND_ENDPOINT: backendApp.outputs.URL

      // Required for the frontend app to ask for a token for the backend app
      AZURE_CLIENT_APP_ID: authClientId

      // Required for container app daprAI
      APPLICATIONINSIGHTS_CONNECTION_STRING: appInsights.properties.ConnectionString

      // Required for managed identity
      AZURE_CLIENT_ID: frontendIdentity.outputs.clientId
    }
    keyvaultIdentities: keyvaultIdentities
  }
}

module frontendContainerAppAuth 'modules/app/container-apps-auth.bicep' = if (authClientSecret != '') {
  name: 'frontend-container-app-auth-module'
  params: {
    name: frontendApp.outputs.name
    clientId: authClientId
    clientSecretName: 'microsoft-provider-authentication-secret'
    openIdIssuer: '${environment().authentication.loginEndpoint}${authTenantId}/v2.0' // Works only for Microsoft Entra
    unauthenticatedClientAction: 'RedirectToLoginPage'
    allowedApplications: [
      '04b07795-8ddb-461a-bbee-02f9e1bf7b46' // AZ CLI for testing purposes
    ]
  }
}

/* ------------------------------ Backend App ------------------------------- */

module backendIdentity './modules/app/identity.bicep' = {
  name: 'backendIdentity'
  scope: resourceGroup()
  params: {
    location: location
    identityName: _backendIdentityName
  }
}

module backendApp 'modules/app/container-apps.bicep' = {
  name: 'backend-container-app'
  scope: resourceGroup()
  params: {
    name: _backendContainerAppName
    tags: tags
    identityId: backendIdentity.outputs.resourceId
    containerAppsEnvironmentName: containerAppsEnvironment.name
    containerRegistryName: containerRegistry.outputs.name
    exists: backendExists
    serviceName: 'backend' // Must match the service name in azure.yaml
    externalIngressAllowed: false // Set to true if you intend to call backend from the locallly deployed frontend
    // Setting to true will allow traffic from anywhere
    env: {
      // Required for container app daprAI
      APPLICATIONINSIGHTS_CONNECTION_STRING: appInsights.properties.ConnectionString

      // Required for managed identity
      AZURE_CLIENT_ID: backendIdentity.outputs.clientId
    }
  }
}

/* -------------------------------------------------------------------------- */
/*                                   OUTPUTS                                  */
/* -------------------------------------------------------------------------- */

// Outputs are automatically saved in the local azd environment .env file.
// To see these outputs, run `azd env get-values`,  or
// `azd env get-values --output json` for json output.
// To generate your own `.env` file run `azd env get-values > .env`

@description('The endpoint of the container registry.') // necessary for azd deploy
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.outputs.loginServer

@description('Endpoint URL of the Frontend service')
output SERVICE_FRONTEND_URL string = frontendApp.outputs.URL

@description('Endpoint URL of the Backend service')
output SERVICE_BACKEND_URL string = backendApp.outputs.URL

@description('ID of the tenant we are deploying to')
output AZURE_AUTH_TENANT_ID string = authTenantId

@description('Principal ID of the user running the deployment')
output AZURE_PRINCIPAL_ID string = azurePrincipalId

@description('Application registration client ID')
output AZURE_CLIENT_APP_ID string = authClientId
