#!/bin/bash

################################################################################
# Configure Databricks Cluster Webhooks for RCA System
# Works with OLD Databricks CLI (v0.x) and NEW CLI (v2.x)
################################################################################

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Databricks Cluster Webhook Configuration            ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

################################################################################
# Step 1: Get Configuration
################################################################################

read -p "Enter FastAPI webhook URL (e.g., https://your-app.azurewebsites.net/databricks-monitor): " WEBHOOK_URL
if [ -z "$WEBHOOK_URL" ]; then
    echo -e "${RED}Error: Webhook URL is required${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}Webhook URL: $WEBHOOK_URL${NC}"
echo ""

################################################################################
# Step 2: Detect Databricks CLI Version
################################################################################

CLI_VERSION=$(databricks --version 2>&1 | grep -oP 'Version \K[0-9]+' | head -1)

if [ "$CLI_VERSION" -ge 2 ]; then
    echo -e "${GREEN}Detected: New Databricks CLI v2.x${NC}"
    USE_NEW_CLI=true
else
    echo -e "${YELLOW}Detected: Old Databricks CLI v0.x${NC}"
    echo -e "${YELLOW}Note: Old CLI is deprecated. Consider upgrading to v2.x${NC}"
    echo -e "${YELLOW}See: https://docs.databricks.com/dev-tools/cli/migrate.html${NC}"
    echo ""
    USE_NEW_CLI=false
fi

################################################################################
# Step 3: Get List of Clusters
################################################################################

echo ""
echo -e "${GREEN}Fetching clusters...${NC}"
echo ""

if [ "$USE_NEW_CLI" = true ]; then
    # New CLI
    databricks clusters list --output json > clusters.json
else
    # Old CLI - different format
    databricks clusters list --output JSON > clusters.json 2>/dev/null || {
        # Old CLI doesn't support --output, use default format
        echo -e "${YELLOW}Using alternative method for old CLI...${NC}"
        databricks clusters list > clusters_raw.txt

        # Parse the output manually
        # Format: CLUSTER_ID  NAME  CREATED_TIME  STATE
        tail -n +2 clusters_raw.txt | awk '{print $1}' > cluster_ids.txt

        # Create a simple JSON array
        echo '{"clusters": [' > clusters.json
        first=true
        while read CLUSTER_ID; do
            if [ "$first" = false ]; then
                echo "," >> clusters.json
            fi
            echo "{\"cluster_id\": \"$CLUSTER_ID\"}" >> clusters.json
            first=false
        done < cluster_ids.txt
        echo ']}' >> clusters.json
    fi
fi

# Count clusters
CLUSTER_COUNT=$(cat clusters.json | grep -o "cluster_id" | wc -l)
echo -e "${GREEN}Found $CLUSTER_COUNT cluster(s)${NC}"
echo ""

if [ $CLUSTER_COUNT -eq 0 ]; then
    echo -e "${YELLOW}No clusters found. Exiting.${NC}"
    exit 0
fi

################################################################################
# Step 4: Show Clusters and Confirm
################################################################################

echo -e "${BLUE}Clusters to configure:${NC}"
if [ "$USE_NEW_CLI" = true ]; then
    databricks clusters list
else
    databricks clusters list
fi

echo ""
read -p "Do you want to add webhooks to ALL these clusters? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Operation cancelled${NC}"
    exit 0
fi

################################################################################
# Step 5: Configure Each Cluster
################################################################################

echo ""
echo -e "${GREEN}Configuring cluster webhooks...${NC}"
echo ""

# Extract cluster IDs
cat clusters.json | grep -oP '"cluster_id"\s*:\s*"\K[^"]+' | while read CLUSTER_ID; do
    echo -e "${BLUE}Processing cluster: $CLUSTER_ID${NC}"

    # Get current cluster configuration
    if [ "$USE_NEW_CLI" = true ]; then
        databricks clusters get --cluster-id "$CLUSTER_ID" --output json > cluster_config.json 2>/dev/null || {
            echo -e "${RED}  ✗ Failed to get cluster config${NC}"
            continue
        }
    else
        # Old CLI
        databricks clusters get --cluster-id "$CLUSTER_ID" > cluster_config.json 2>/dev/null || {
            echo -e "${RED}  ✗ Failed to get cluster config${NC}"
            continue
        }
    fi

    # Check if cluster config was retrieved
    if [ ! -s cluster_config.json ]; then
        echo -e "${RED}  ✗ Empty cluster config${NC}"
        continue
    fi

    # Add webhook notifications to the configuration
    # This preserves existing config and adds webhooks
    cat cluster_config.json | jq '. + {
        "webhook_notifications": {
            "on_unexpected_termination": [{
                "id": "cluster-terminated-rca-'$(date +%s)'",
                "url": "'$WEBHOOK_URL'"
            }],
            "on_failed_start": [{
                "id": "cluster-failed-start-rca-'$(date +%s)'",
                "url": "'$WEBHOOK_URL'"
            }]
        }
    }' > cluster_config_updated.json 2>/dev/null || {
        echo -e "${RED}  ✗ Failed to update cluster config (jq error)${NC}"
        echo -e "${YELLOW}  Make sure 'jq' is installed: sudo apt-get install jq${NC}"
        continue
    }

    # Update the cluster
    echo "  Updating cluster configuration..."
    if [ "$USE_NEW_CLI" = true ]; then
        databricks clusters edit --json @cluster_config_updated.json > /dev/null 2>&1 || {
            echo -e "${RED}  ✗ Failed to update cluster${NC}"
            continue
        }
    else
        # Old CLI uses different syntax
        databricks clusters edit --json-file cluster_config_updated.json > /dev/null 2>&1 || {
            # Try alternative method
            databricks clusters edit --json "$(cat cluster_config_updated.json)" > /dev/null 2>&1 || {
                echo -e "${RED}  ✗ Failed to update cluster${NC}"
                continue
            }
        }
    fi

    echo -e "${GREEN}  ✓ Configured cluster: $CLUSTER_ID${NC}"
    echo ""
done

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              Configuration Complete!                    ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

################################################################################
# Step 6: Cleanup
################################################################################

rm -f clusters.json clusters_raw.txt cluster_ids.txt cluster_config.json cluster_config_updated.json

################################################################################
# Step 7: Test Instructions
################################################################################

echo -e "${BLUE}Next Steps:${NC}"
echo ""
echo "1. Test cluster webhook by terminating a cluster:"
echo "   databricks clusters delete --cluster-id <CLUSTER_ID>"
echo ""
echo "2. Check FastAPI logs for webhook:"
echo "   tail -f /path/to/app.log | grep 'DATABRICKS WEBHOOK'"
echo ""
echo "3. Expected log output:"
echo "   ✓ Databricks Cluster Extractor: cluster=YourCluster"
echo "   ✓ Event type: cluster.terminated"
echo ""
echo -e "${YELLOW}Note: For new clusters, you'll need to run this script again${NC}"
echo -e "${YELLOW}      or configure webhooks manually in Databricks UI${NC}"
echo ""
