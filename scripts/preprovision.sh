#!/bin/bash
set -e

# Add here commands that need to be executed before provisioning
# Typically: preparing additional environment variables, creating app registrations, etc.
# see https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/azd-extensibility

if [ -z "$AZURE_AUTH_TENANT_ID" ]; then
    AZURE_AUTH_TENANT_ID=$(az account show --query tenantId -o tsv)
     echo -e "\033[3;33mAZURE_AUTH_TENANT_ID not provided: Default to $AZURE_AUTH_TENANT_ID from AZ CLI\033[0m"
fi
azd env set AZURE_AUTH_TENANT_ID "$AZURE_AUTH_TENANT_ID"

    if [ -z "$AZURE_AUTH_TENANT_ID" ]; then
        AZURE_AUTH_TENANT_ID=$(az account show --query tenantId -o tsv)
        printf "      \033[3;33mAZURE_AUTH_TENANT_ID not provided: Default to $AZURE_AUTH_TENANT_ID from AZ CLI\033[0m"
    fi
    azd env set AZURE_AUTH_TENANT_ID "$AZURE_AUTH_TENANT_ID"

echo "Current user          : $CURRENT_USER_UPN"
echo "Current tenant        : $AZURE_AUTH_TENANT_ID"
echo "App Registration name : $APP_NAME"

    printf "      Current user          : $current_user_upn"
    printf "      Current tenant        : $AZURE_AUTH_TENANT_ID"
    printf "      App Registration name : $app_name"

    az ad app update \
        --id $AZURE_CLIENT_APP_ID \
        --identifier-uris "api://$AZURE_CLIENT_APP_ID" \
        --enable-id-token-issuance true \
        --enable-access-token-issuance true \
        --required-resource-accesses @scripts/requiredResourceAccess.json

    SERVICE_PRINCIPAL_ID=$(
        az ad sp create \
            --id "$AZURE_CLIENT_APP_ID" \
            --query id \
            --output tsv
    )

    az ad app owner add \
        --id "$AZURE_CLIENT_APP_ID" \
        --owner-object-id "$CURRENT_USER_ID"

    AZURE_CLIENT_APP_SECRET="$(
        az ad app credential reset \
            --id $AZURE_CLIENT_APP_ID \
            --display-name "client-secret" \
            --query password \
            --years 1 \
            --output tsv
    )"

    az rest \
        --method PATCH \
        --headers 'Content-Type=application/json' \
        --uri "https://graph.microsoft.com/v1.0/applications/$AZURE_APP_ID" \
        --body @scripts/oauth2PermissionScopes.json

    az rest \
        --method PATCH \
        --headers 'Content-Type=application/json' \
        --uri "https://graph.microsoft.com/v1.0/applications/$AZURE_APP_ID" \
        --body @scripts/preAuthorizedApplications.json

        printf "      App $app_name created with ID $AZURE_CLIENT_APP_ID and SP ID $SERVICE_PRINCIPAL_ID"
    else
        printf "      \033[3;33mApp '$AZURE_CLIENT_APP_ID' already exists, skipping creation\033[0m"
    fi

    azd env set AZURE_CLIENT_APP_ID "$AZURE_CLIENT_APP_ID"

    printf "    \033[32m➜\033[0m Application registration ${app_name} (${AZURE_CLIENT_APP_ID}) done.\n"

    # Credits: inspired by https://gpiskas.com/posts/automate-creation-app-registration-azure-cli/#creating-and-modifying-the-app-registration
fi

azd env set AZURE_CLIENT_APP_ID "$AZURE_CLIENT_APP_ID"

# Credits: inspired by https://gpiskas.com/posts/automate-creation-app-registration-azure-cli/#creating-and-modifying-the-app-registration
