#!/bin/bash

# =============================================================================
# Azure Logic Apps Setup for Auto-Remediation Playbooks
# =============================================================================

set -e

echo "🚀 Azure Logic Apps Setup for Auto-Remediation"
echo "=============================================="
echo ""

# Configuration
read -p "Enter Azure Resource Group name [rg_techdemo_2025_Q4]: " RESOURCE_GROUP
RESOURCE_GROUP=${RESOURCE_GROUP:-rg_techdemo_2025_Q4}

read -p "Enter Azure region [eastus]: " LOCATION
LOCATION=${LOCATION:-eastus}

read -p "Enter Azure Data Factory name (leave empty to skip ADF playbooks): " ADF_NAME

read -p "Enter Databricks Host URL (e.g., https://adb-123.azuredatabricks.net): " DATABRICKS_HOST

echo ""
echo "📋 Configuration:"
echo "   Resource Group: $RESOURCE_GROUP"
echo "   Location: $LOCATION"
echo "   ADF Name: ${ADF_NAME:-Not configured}"
echo "   Databricks Host: ${DATABRICKS_HOST:-Not configured}"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Setup cancelled"
    exit 1
fi

echo ""
echo "🔧 Creating Logic Apps..."
echo ""

# Array of playbooks to create
declare -A playbooks=(
    ["playbook-retry-adf-pipeline"]="ADF"
    ["playbook-restart-databricks-cluster"]="Databricks"
    ["playbook-retry-databricks-job"]="Databricks"
    ["playbook-scale-databricks-cluster"]="Databricks"
    ["playbook-reinstall-libraries"]="Databricks"
)

# Basic Logic App definition
read -r -d '' LOGIC_APP_DEF << 'EOF' || true
{
  "$schema": "https://schema.management.azure.com/schemas/2016-06-01/Microsoft.Logic.json",
  "contentVersion": "1.0.0.0",
  "triggers": {
    "manual": {
      "type": "Request",
      "kind": "Http",
      "inputs": {
        "schema": {
          "type": "object",
          "properties": {
            "ticket_id": {"type": "string"},
            "error_type": {"type": "string"},
            "metadata": {"type": "object"},
            "retry_attempt": {"type": "integer"},
            "max_retries": {"type": "integer"}
          }
        }
      }
    }
  },
  "actions": {
    "Response": {
      "type": "Response",
      "inputs": {
        "statusCode": 200,
        "body": {
          "status": "success",
          "message": "Playbook triggered. Configure actions in Azure Portal."
        }
      }
    }
  }
}
EOF

# Create each Logic App
for playbook in "${!playbooks[@]}"
do
    type=${playbooks[$playbook]}

    # Skip ADF playbooks if no ADF name provided
    if [ "$type" = "ADF" ] && [ -z "$ADF_NAME" ]; then
        echo "⏭️  Skipping $playbook (no ADF name provided)"
        continue
    fi

    # Skip Databricks playbooks if no host provided
    if [ "$type" = "Databricks" ] && [ -z "$DATABRICKS_HOST" ]; then
        echo "⏭️  Skipping $playbook (no Databricks host provided)"
        continue
    fi

    echo "📦 Creating $playbook..."

    # Create Logic App
    az logic workflow create \
      --resource-group "$RESOURCE_GROUP" \
      --location "$LOCATION" \
      --name "$playbook" \
      --definition "$LOGIC_APP_DEF" \
      > /dev/null 2>&1

    # Enable system-assigned managed identity
    az logic workflow identity assign \
      --resource-group "$RESOURCE_GROUP" \
      --name "$playbook" \
      > /dev/null 2>&1

    echo "✅ Created $playbook"
done

echo ""
echo "🔑 Configuring Permissions..."
echo ""

# Grant ADF permissions if applicable
if [ -n "$ADF_NAME" ]; then
    for playbook in playbook-retry-adf-pipeline
    do
        PRINCIPAL_ID=$(az logic workflow identity show \
          --resource-group "$RESOURCE_GROUP" \
          --name "$playbook" \
          --query principalId -o tsv 2>/dev/null || echo "")

        if [ -n "$PRINCIPAL_ID" ]; then
            ADF_RESOURCE_ID=$(az datafactory show \
              --resource-group "$RESOURCE_GROUP" \
              --name "$ADF_NAME" \
              --query id -o tsv 2>/dev/null || echo "")

            if [ -n "$ADF_RESOURCE_ID" ]; then
                az role assignment create \
                  --assignee "$PRINCIPAL_ID" \
                  --role "Data Factory Contributor" \
                  --scope "$ADF_RESOURCE_ID" \
                  > /dev/null 2>&1

                echo "✅ Granted ADF permissions to $playbook"
            fi
        fi
    done
fi

echo ""
echo "📋 Getting Logic App URLs..."
echo ""

# Output file
OUTPUT_FILE=".env.playbooks"
echo "# Auto-Remediation Playbook URLs - Generated $(date)" > $OUTPUT_FILE
echo "# Add these to your .env file" >> $OUTPUT_FILE
echo "" >> $OUTPUT_FILE

for playbook in "${!playbooks[@]}"
do
    type=${playbooks[$playbook]}

    # Skip if not created
    if [ "$type" = "ADF" ] && [ -z "$ADF_NAME" ]; then
        continue
    fi
    if [ "$type" = "Databricks" ] && [ -z "$DATABRICKS_HOST" ]; then
        continue
    fi

    # Get URL
    URL=$(az logic workflow trigger show \
      --resource-group "$RESOURCE_GROUP" \
      --name "$playbook" \
      --trigger-name manual \
      --query "listCallbackUrl().value" -o tsv 2>/dev/null || echo "")

    if [ -n "$URL" ]; then
        # Convert playbook name to env var name
        ENV_VAR=$(echo "$playbook" | tr '[:lower:]-' '[:upper:]_' | sed 's/PLAYBOOK_PLAYBOOK_/PLAYBOOK_/')

        echo "$ENV_VAR=$URL" >> $OUTPUT_FILE
        echo "✅ $playbook"
        echo "   $ENV_VAR"
    fi
done

echo ""
echo "🎉 Setup Complete!"
echo ""
echo "📝 Next Steps:"
echo ""
echo "1. Copy the URLs to your .env file:"
echo "   cat $OUTPUT_FILE >> .env"
echo ""
echo "2. Configure Logic App actions in Azure Portal:"
echo "   https://portal.azure.com/#blade/HubsExtension/BrowseResource/resourceType/Microsoft.Logic%2Fworkflows"
echo ""
echo "3. For each Logic App:"
echo "   - Click 'Logic app designer'"
echo "   - Add HTTP actions to call ADF/Databricks APIs"
echo "   - See PLAYBOOK_SETUP_GUIDE.md for detailed instructions"
echo ""
echo "4. Enable auto-remediation in .env:"
echo "   AUTO_REMEDIATION_ENABLED=true"
echo ""
echo "5. Test with curl (see PLAYBOOK_SETUP_GUIDE.md)"
echo ""

cat $OUTPUT_FILE
