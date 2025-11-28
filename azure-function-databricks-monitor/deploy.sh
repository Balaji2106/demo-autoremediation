#!/bin/bash

################################################################################
# Deploy Azure Function for Databricks Cluster Monitoring
################################################################################

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Deploy Databricks Monitor Azure Function             ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if Azure CLI is logged in
if ! az account show &> /dev/null; then
    echo -e "${RED}Error: Not logged in to Azure CLI${NC}"
    echo "Run: az login"
    exit 1
fi

echo -e "${GREEN}Step 1: Collect Information${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Get function app name
read -p "Enter Function App name: " FUNCTION_APP_NAME
read -p "Enter Resource Group: " RESOURCE_GROUP

# Verify function app exists
if ! az functionapp show --name "$FUNCTION_APP_NAME" --resource-group "$RESOURCE_GROUP" &> /dev/null; then
    echo -e "${RED}Error: Function App not found${NC}"
    echo "Create it first or check the name/resource group"
    exit 1
fi

echo -e "${GREEN}✓ Function App found: $FUNCTION_APP_NAME${NC}"
echo ""

# Deploy
echo -e "${GREEN}Step 2: Deploying Function Code${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Deploy using func azure functionapp publish
func azure functionapp publish "$FUNCTION_APP_NAME" --python

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              Deployment Complete!                       ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${BLUE}Function App URL:${NC}"
FUNCTION_URL=$(az functionapp show --name "$FUNCTION_APP_NAME" --resource-group "$RESOURCE_GROUP" --query defaultHostName -o tsv)
echo "https://$FUNCTION_URL"
echo ""

echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Verify app settings are configured:"
echo "   az functionapp config appsettings list --name $FUNCTION_APP_NAME --resource-group $RESOURCE_GROUP"
echo ""
echo "2. Test the function manually:"
echo "   func azure functionapp run $FUNCTION_APP_NAME --name DatabricksMonitor"
echo ""
echo "3. Monitor logs:"
echo "   func azure functionapp logstream $FUNCTION_APP_NAME"
echo ""
echo "4. View in portal:"
echo "   https://portal.azure.com/#@/resource/subscriptions/.../resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Web/sites/$FUNCTION_APP_NAME"
echo ""

echo -e "${GREEN}Deployment completed successfully!${NC}"
