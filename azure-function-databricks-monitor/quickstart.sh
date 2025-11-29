#!/bin/bash

################################################################################
# QUICKSTART: Deploy Azure Function for Databricks Monitoring
# This script automates the entire deployment process
################################################################################

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Databricks Cluster Monitor - Azure Function Quickstart     ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

################################################################################
# Step 1: Prerequisites Check
################################################################################

echo -e "${GREEN}Step 1: Checking Prerequisites${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check Azure CLI
if ! command -v az &> /dev/null; then
    echo -e "${RED}✗ Azure CLI not found${NC}"
    echo "Install: https://docs.microsoft.com/cli/azure/install-azure-cli"
    exit 1
fi
echo -e "${GREEN}✓ Azure CLI found${NC}"

# Check Azure Functions Core Tools
if ! command -v func &> /dev/null; then
    echo -e "${YELLOW}⚠ Azure Functions Core Tools not found${NC}"
    echo "Installing Azure Functions Core Tools..."

    # Install for Ubuntu/Debian
    wget -q https://packages.microsoft.com/config/ubuntu/20.04/packages-microsoft-prod.deb
    sudo dpkg -i packages-microsoft-prod.deb
    sudo apt-get update
    sudo apt-get install -y azure-functions-core-tools-4
    rm packages-microsoft-prod.deb

    echo -e "${GREEN}✓ Azure Functions Core Tools installed${NC}"
else
    echo -e "${GREEN}✓ Azure Functions Core Tools found${NC}"
fi

# Check Azure login
if ! az account show &> /dev/null; then
    echo -e "${YELLOW}⚠ Not logged in to Azure${NC}"
    echo "Logging in..."
    az login
fi
echo -e "${GREEN}✓ Azure CLI logged in${NC}"

echo ""

################################################################################
# Step 2: Collect Configuration
################################################################################

echo -e "${GREEN}Step 2: Configuration${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Resource Group
read -p "Resource Group name [rg_techdemo_2025_Q4]: " RESOURCE_GROUP
RESOURCE_GROUP=${RESOURCE_GROUP:-rg_techdemo_2025_Q4}

# Location
read -p "Azure region [eastus]: " LOCATION
LOCATION=${LOCATION:-eastus}

# Generate unique names
TIMESTAMP=$(date +%s)
FUNCTION_APP_NAME="func-dbx-monitor-${TIMESTAMP}"
STORAGE_NAME="stdbxmon${TIMESTAMP: -5}"
APP_INSIGHTS_NAME="appi-dbx-monitor-${TIMESTAMP}"

echo ""
echo -e "${BLUE}Configuration:${NC}"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  Location: $LOCATION"
echo "  Function App: $FUNCTION_APP_NAME"
echo "  Storage: $STORAGE_NAME"
echo "  App Insights: $APP_INSIGHTS_NAME"
echo ""

# Databricks configuration
echo -e "${YELLOW}Databricks Configuration:${NC}"
read -p "Databricks Host URL (e.g., https://adb-xxx.azuredatabricks.net): " DATABRICKS_HOST
read -sp "Databricks Personal Access Token: " DATABRICKS_TOKEN
echo ""

# FastAPI configuration
read -p "FastAPI URL (e.g., https://your-app.azurewebsites.net/databricks-monitor): " FASTAPI_URL

# Polling interval
read -p "Polling interval in minutes [5]: " POLLING_INTERVAL
POLLING_INTERVAL=${POLLING_INTERVAL:-5}

echo ""

################################################################################
# Step 3: Create Azure Resources
################################################################################

echo -e "${GREEN}Step 3: Creating Azure Resources${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Verify resource group
if ! az group show --name "$RESOURCE_GROUP" &> /dev/null; then
    echo -e "${RED}✗ Resource group not found: $RESOURCE_GROUP${NC}"
    read -p "Create it? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        az group create --name "$RESOURCE_GROUP" --location "$LOCATION"
        echo -e "${GREEN}✓ Resource group created${NC}"
    else
        exit 1
    fi
else
    echo -e "${GREEN}✓ Resource group exists${NC}"
fi

# Create storage account
echo "Creating storage account..."
if az storage account create \
    --name "$STORAGE_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --sku Standard_LRS \
    --kind StorageV2 \
    --output none; then
    echo -e "${GREEN}✓ Storage account created${NC}"
else
    echo -e "${RED}✗ Failed to create storage account${NC}"
    exit 1
fi

# Create Application Insights
echo "Creating Application Insights..."
if az monitor app-insights component create \
    --app "$APP_INSIGHTS_NAME" \
    --location "$LOCATION" \
    --resource-group "$RESOURCE_GROUP" \
    --application-type web \
    --output none; then
    echo -e "${GREEN}✓ Application Insights created${NC}"
else
    echo -e "${RED}✗ Failed to create Application Insights${NC}"
    exit 1
fi

# Get instrumentation key
INSTRUMENTATION_KEY=$(az monitor app-insights component show \
    --app "$APP_INSIGHTS_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query instrumentationKey -o tsv)

# Create Function App
echo "Creating Function App (this takes 2-3 minutes)..."
if az functionapp create \
    --name "$FUNCTION_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --storage-account "$STORAGE_NAME" \
    --consumption-plan-location "$LOCATION" \
    --runtime python \
    --runtime-version 3.11 \
    --functions-version 4 \
    --os-type Linux \
    --app-insights "$APP_INSIGHTS_NAME" \
    --output none; then
    echo -e "${GREEN}✓ Function App created${NC}"
else
    echo -e "${RED}✗ Failed to create Function App${NC}"
    exit 1
fi

echo ""

################################################################################
# Step 4: Configure Function App
################################################################################

echo -e "${GREEN}Step 4: Configuring Function App${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Set app settings
az functionapp config appsettings set \
    --name "$FUNCTION_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --settings \
        DATABRICKS_HOST="$DATABRICKS_HOST" \
        DATABRICKS_TOKEN="$DATABRICKS_TOKEN" \
        FASTAPI_URL="$FASTAPI_URL" \
        POLLING_INTERVAL_MINUTES="$POLLING_INTERVAL" \
        APPINSIGHTS_INSTRUMENTATIONKEY="$INSTRUMENTATION_KEY" \
    --output none

echo -e "${GREEN}✓ App settings configured${NC}"
echo ""

################################################################################
# Step 5: Deploy Function Code
################################################################################

echo -e "${GREEN}Step 5: Deploying Function Code${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Deploy function
if func azure functionapp publish "$FUNCTION_APP_NAME" --python; then
    echo ""
    echo -e "${GREEN}✓ Function deployed successfully${NC}"
else
    echo -e "${RED}✗ Failed to deploy function${NC}"
    exit 1
fi

echo ""

################################################################################
# Step 6: Verification
################################################################################

echo -e "${GREEN}Step 6: Verification${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Get function URL
FUNCTION_URL=$(az functionapp show \
    --name "$FUNCTION_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query defaultHostName -o tsv)

echo -e "${GREEN}✓ Function App URL: https://$FUNCTION_URL${NC}"
echo ""

# Test Databricks connectivity
echo "Testing Databricks API connectivity..."
if curl -s -f -X GET \
    "${DATABRICKS_HOST}/api/2.0/clusters/list" \
    -H "Authorization: Bearer ${DATABRICKS_TOKEN}" \
    > /dev/null; then
    echo -e "${GREEN}✓ Databricks API accessible${NC}"
else
    echo -e "${YELLOW}⚠ Databricks API test failed - check token and URL${NC}"
fi

echo ""

################################################################################
# Summary
################################################################################

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                  Deployment Complete!                         ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${GREEN}Created Resources:${NC}"
echo "  ✓ Function App: $FUNCTION_APP_NAME"
echo "  ✓ Storage Account: $STORAGE_NAME"
echo "  ✓ Application Insights: $APP_INSIGHTS_NAME"
echo ""

echo -e "${GREEN}Configuration:${NC}"
echo "  ✓ Databricks Host: $DATABRICKS_HOST"
echo "  ✓ FastAPI URL: $FASTAPI_URL"
echo "  ✓ Polling Interval: $POLLING_INTERVAL minutes"
echo ""

echo -e "${YELLOW}Next Steps:${NC}"
echo ""
echo "1. Monitor function logs:"
echo "   func azure functionapp logstream $FUNCTION_APP_NAME"
echo ""
echo "2. View in Azure Portal:"
PORTAL_URL="https://portal.azure.com/#@/resource/subscriptions/$(az account show --query id -o tsv)/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Web/sites/$FUNCTION_APP_NAME"
echo "   $PORTAL_URL"
echo ""
echo "3. Test cluster failure detection:"
echo "   - Terminate a Databricks cluster"
echo "   - Wait 5-10 minutes"
echo "   - Check FastAPI logs for incoming event"
echo "   - Verify ticket creation in dashboard"
echo ""
echo "4. View Application Insights:"
INSIGHTS_URL="https://portal.azure.com/#@/resource/subscriptions/$(az account show --query id -o tsv)/resourceGroups/$RESOURCE_GROUP/providers/microsoft.insights/components/$APP_INSIGHTS_NAME"
echo "   $INSIGHTS_URL"
echo ""

echo -e "${GREEN}Function will run automatically every $POLLING_INTERVAL minutes!${NC}"
echo ""

# Save configuration
cat > deployment-info.txt <<EOF
Deployment Information
======================

Date: $(date)

Resources:
- Function App: $FUNCTION_APP_NAME
- Resource Group: $RESOURCE_GROUP
- Storage: $STORAGE_NAME
- App Insights: $APP_INSIGHTS_NAME

Configuration:
- Databricks Host: $DATABRICKS_HOST
- FastAPI URL: $FASTAPI_URL
- Polling Interval: $POLLING_INTERVAL minutes

URLs:
- Function App: https://$FUNCTION_URL
- Azure Portal: $PORTAL_URL
- App Insights: $INSIGHTS_URL

Monitoring Commands:
- View logs: func azure functionapp logstream $FUNCTION_APP_NAME
- Restart: az functionapp restart --name $FUNCTION_APP_NAME --resource-group $RESOURCE_GROUP
- Delete: az functionapp delete --name $FUNCTION_APP_NAME --resource-group $RESOURCE_GROUP

EOF

echo -e "${GREEN}✓ Deployment info saved to: deployment-info.txt${NC}"
echo ""
