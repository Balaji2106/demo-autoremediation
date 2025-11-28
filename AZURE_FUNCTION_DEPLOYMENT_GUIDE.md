# 🚀 AZURE FUNCTION DEPLOYMENT GUIDE
## Complete Step-by-Step Instructions

---

## 📋 TABLE OF CONTENTS

1. [Prerequisites](#prerequisites)
2. [Phase 1: Get Databricks Token](#phase-1-get-databricks-token)
3. [Phase 2: Create Azure Function App](#phase-2-create-azure-function-app)
4. [Phase 3: Configure Function Settings](#phase-3-configure-function-settings)
5. [Phase 4: Deploy Function Code](#phase-4-deploy-function-code)
6. [Phase 5: Test and Verify](#phase-5-test-and-verify)
7. [Phase 6: Monitor in Production](#phase-6-monitor-in-production)
8. [Troubleshooting](#troubleshooting)

---

## PREREQUISITES

### ✅ Check Azure Access

```bash
# 1. Login to Azure
az login

# 2. Set subscription (if you have multiple)
az account set --subscription "YOUR_SUBSCRIPTION_NAME"

# 3. Verify you're logged in
az account show

# Expected: Shows subscription details
```

### ✅ Check Databricks Access

```bash
# 1. Configure Databricks CLI
databricks configure --token

# When prompted:
# - Databricks Host: https://adb-XXXXX.XX.azuredatabricks.net
# - Token: (create in next step)

# 2. Test access
databricks workspace ls /

# Expected: Shows workspace folders
```

### ✅ Check Resource Group

```bash
# Verify resource group exists
RESOURCE_GROUP="rg_techdemo_2025_Q4"
az group show --name $RESOURCE_GROUP

# Expected: Shows resource group details
```

---

## PHASE 1: GET DATABRICKS TOKEN

### Step 1.1: Open Databricks Workspace

1. Go to **Azure Portal** → Search "Databricks"
2. Click your workspace: **techdemo_databricks**
3. Click **"Launch Workspace"** button
4. Databricks UI opens in new tab

### Step 1.2: Create Personal Access Token

1. In Databricks, click **your email** (top-right)
2. Select **"User Settings"**
3. Click **"Access tokens"** tab
4. Click **"Generate new token"**

**Fill in:**
- **Comment:** `Azure Function - Cluster Monitoring`
- **Lifetime (days):** `90` (or per your policy)

5. Click **"Generate"**
6. **COPY THE TOKEN** immediately - you'll only see it once!

**Example token:**
```
dapi1234567890abcdef1234567890abcdef1234567890abcdef1234567890ab
```

7. **Save token** in secure note temporarily

### Step 1.3: Get Databricks Host URL

**Find your workspace URL:**

```bash
# Option A: From Azure CLI
az databricks workspace show \
  --name techdemo_databricks \
  --resource-group rg_techdemo_2025_Q4 \
  --query workspaceUrl -o tsv

# Option B: From Databricks UI
# Look at browser URL bar when in Databricks workspace
# Example: https://adb-1234567890123456.7.azuredatabricks.net
```

**Save this URL** - you'll need it!

### Step 1.4: Test Token

```bash
# Set variables
DATABRICKS_HOST="https://adb-XXXXX.XX.azuredatabricks.net"  # Your URL
DATABRICKS_TOKEN="dapiXXXXXXXXXXXX"  # Your token

# Test API access
curl -X GET \
  "${DATABRICKS_HOST}/api/2.0/clusters/list" \
  -H "Authorization: Bearer ${DATABRICKS_TOKEN}"

# Expected: JSON response with cluster list
# If error 401: Token invalid - regenerate
# If error 403: Insufficient permissions - ask admin
```

---

## PHASE 2: CREATE AZURE FUNCTION APP

### Step 2.1: Set Variables

```bash
# Resource configuration
RESOURCE_GROUP="rg_techdemo_2025_Q4"
LOCATION="eastus"

# Generate unique names
TIMESTAMP=$(date +%s)
FUNCTION_APP_NAME="func-dbx-monitor-${TIMESTAMP}"
STORAGE_NAME="stdbxmon${TIMESTAMP: -5}"  # Last 5 digits
APP_INSIGHTS_NAME="appi-dbx-monitor"

# Print for verification
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Function App: $FUNCTION_APP_NAME"
echo "Storage: $STORAGE_NAME"
echo "App Insights: $APP_INSIGHTS_NAME"
echo "Resource Group: $RESOURCE_GROUP"
echo "Location: $LOCATION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
```

### Step 2.2: Create Storage Account

```bash
# Create storage (required for Functions)
az storage account create \
  --name $STORAGE_NAME \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --sku Standard_LRS \
  --kind StorageV2

# Expected: JSON output with provisioningState: "Succeeded"
# Wait time: 30-60 seconds
```

**Verify:**
```bash
az storage account show \
  --name $STORAGE_NAME \
  --resource-group $RESOURCE_GROUP \
  --query "{name:name, location:location, provisioningState:provisioningState}" -o table
```

### Step 2.3: Create Application Insights

```bash
# Create App Insights (for monitoring/logs)
az monitor app-insights component create \
  --app $APP_INSIGHTS_NAME \
  --location $LOCATION \
  --resource-group $RESOURCE_GROUP \
  --application-type web

# Expected: JSON output with provisioningState: "Succeeded"
# Wait time: 30-60 seconds
```

**Get instrumentation key:**
```bash
INSTRUMENTATION_KEY=$(az monitor app-insights component show \
  --app $APP_INSIGHTS_NAME \
  --resource-group $RESOURCE_GROUP \
  --query instrumentationKey -o tsv)

echo "Instrumentation Key: $INSTRUMENTATION_KEY"
```

### Step 2.4: Create Function App

```bash
# Create Function App (Consumption Plan = FREE)
az functionapp create \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --storage-account $STORAGE_NAME \
  --consumption-plan-location $LOCATION \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4 \
  --os-type Linux \
  --app-insights $APP_INSIGHTS_NAME

# Expected: JSON output with state: "Running"
# Wait time: 2-3 minutes
```

**Verify:**
```bash
az functionapp show \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query "{name:name, state:state, defaultHostName:defaultHostName}" -o table

# Expected output:
# Name                      State     DefaultHostName
# func-dbx-monitor-...      Running   func-dbx-monitor-....azurewebsites.net
```

---

## PHASE 3: CONFIGURE FUNCTION SETTINGS

### Step 3.1: Set Configuration Variables

**You need:**
- ✅ Databricks Host URL (from Step 1.3)
- ✅ Databricks Token (from Step 1.2)
- ✅ FastAPI URL (your RCA app endpoint)

**Set variables:**
```bash
# Your Databricks workspace URL
DATABRICKS_HOST="https://adb-XXXXX.XX.azuredatabricks.net"

# Your Databricks token from Step 1.2
DATABRICKS_TOKEN="dapiXXXXXXXXXXXXXXXXXXXX"

# Your FastAPI endpoint
FASTAPI_URL="https://your-rca-app.azurewebsites.net/databricks-monitor"

# Polling interval (5 minutes)
POLLING_INTERVAL="5"
```

### Step 3.2: Add Settings to Function App

```bash
# Configure app settings (stores as environment variables)
az functionapp config appsettings set \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --settings \
    DATABRICKS_HOST="$DATABRICKS_HOST" \
    DATABRICKS_TOKEN="$DATABRICKS_TOKEN" \
    FASTAPI_URL="$FASTAPI_URL" \
    POLLING_INTERVAL_MINUTES="$POLLING_INTERVAL" \
    APPINSIGHTS_INSTRUMENTATIONKEY="$INSTRUMENTATION_KEY"

# Expected: JSON output with all settings
# Wait time: 10-15 seconds
```

### Step 3.3: Verify Settings

```bash
# List all app settings
az functionapp config appsettings list \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --output table

# Expected: Table showing all settings
# Note: DATABRICKS_TOKEN value will be hidden for security
```

**Check specific setting:**
```bash
# Verify Databricks host
az functionapp config appsettings list \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query "[?name=='DATABRICKS_HOST'].value" -o tsv

# Expected: Your Databricks URL
```

---

## PHASE 4: DEPLOY FUNCTION CODE

### Step 4.1: Navigate to Function Code Directory

```bash
cd /home/user/demo-autoremediation/azure-function-databricks-monitor
```

### Step 4.2: Verify Code Files Exist

```bash
# Check all required files
ls -la

# Expected files:
# - DatabricksMonitor/
#   - __init__.py (main function code)
#   - function.json (trigger configuration)
# - host.json
# - requirements.txt
# - local.settings.json
# - .funcignore
# - deploy.sh
```

### Step 4.3: Make Deploy Script Executable

```bash
chmod +x deploy.sh
```

### Step 4.4: Deploy Function

```bash
# Deploy using Azure Functions Core Tools
func azure functionapp publish $FUNCTION_APP_NAME --python

# Expected output:
# Getting site publishing info...
# Preparing archive...
# Uploading content...
# Upload completed successfully.
# Deployment completed successfully.
# Syncing triggers...
# Functions in func-dbx-monitor-...:
#     DatabricksMonitor - [timerTrigger]

# Wait time: 1-2 minutes
```

**Alternative: Use deploy script**
```bash
./deploy.sh

# When prompted:
# - Enter Function App name: func-dbx-monitor-XXXXX
# - Enter Resource Group: rg_techdemo_2025_Q4
```

### Step 4.5: Verify Deployment

```bash
# List functions in app
az functionapp function show \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --function-name DatabricksMonitor

# Expected: JSON with function details
```

---

## PHASE 5: TEST AND VERIFY

### Step 5.1: Manual Trigger Test

```bash
# Manually trigger the function (don't wait for timer)
az functionapp function keys list \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --function-name DatabricksMonitor

# Get function URL and master key
FUNCTION_URL="https://${FUNCTION_APP_NAME}.azurewebsites.net/admin/functions/DatabricksMonitor"

# Trigger function manually
curl -X POST "$FUNCTION_URL" \
  -H "Content-Type: application/json" \
  -H "x-functions-key: YOUR_MASTER_KEY"

# Expected: 202 Accepted or 200 OK
```

### Step 5.2: Check Function Logs

```bash
# Stream live logs
func azure functionapp logstream $FUNCTION_APP_NAME

# Expected output (every 5 minutes):
# Databricks Monitor function started at 2025-11-28T...
# Querying events from ... to ...
# Retrieved X events from Databricks
# Filtered to Y error events
# Databricks Monitor completed. Processed Y errors.
```

**Alternative: View logs in portal**
```bash
# Get portal URL
echo "https://portal.azure.com/#@/resource/subscriptions/$(az account show --query id -o tsv)/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Web/sites/$FUNCTION_APP_NAME/logStream"
```

### Step 5.3: Check Application Insights

```bash
# Query recent function executions
az monitor app-insights query \
  --app $APP_INSIGHTS_NAME \
  --resource-group $RESOURCE_GROUP \
  --analytics-query "requests | where timestamp > ago(1h) | project timestamp, name, resultCode, duration | order by timestamp desc" \
  --output table

# Expected: Shows function executions with 200 status
```

### Step 5.4: Test End-to-End

**Create a test cluster failure:**

```bash
# Option A: Terminate a running cluster
databricks clusters delete --cluster-id YOUR_CLUSTER_ID

# Option B: Try to start cluster with invalid config
# (Will fail to start, triggering FAILED_TO_START event)
```

**Wait 5-10 minutes, then check:**

1. **Function logs** - Should show event was detected
2. **FastAPI logs** - Should show event was received
3. **Dashboard** - Should show new ticket
4. **Slack** - Should have notification

---

## PHASE 6: MONITOR IN PRODUCTION

### Step 6.1: Enable Monitoring

```bash
# Function automatically sends telemetry to Application Insights
# View metrics:
az monitor app-insights metrics show \
  --app $APP_INSIGHTS_NAME \
  --resource-group $RESOURCE_GROUP \
  --metric requests/count \
  --interval PT1H

# Expected: Shows request count per hour
```

### Step 6.2: Set Up Alerts (Optional)

```bash
# Create alert if function fails
az monitor metrics alert create \
  --name "DatabricksMonitorFailure" \
  --resource-group $RESOURCE_GROUP \
  --scopes "/subscriptions/$(az account show --query id -o tsv)/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Web/sites/$FUNCTION_APP_NAME" \
  --condition "count customMetrics/DatabricksMonitor/failures > 5" \
  --window-size 1h \
  --evaluation-frequency 5m \
  --action email me@company.com

# Expected: Alert created
```

### Step 6.3: Monitor Costs

```bash
# Check function execution count
az monitor app-insights metrics show \
  --app $APP_INSIGHTS_NAME \
  --resource-group $RESOURCE_GROUP \
  --metric requests/count \
  --interval P1D \
  --start-time $(date -d '7 days ago' -u +"%Y-%m-%dT%H:%M:%SZ") \
  --end-time $(date -u +"%Y-%m-%dT%H:%M:%SZ")

# At 5-min intervals: ~288 executions/day = ~8,640/month
# Well under 1M free tier limit!
```

---

## TROUBLESHOOTING

### Issue 1: Function Not Triggering

**Symptom:** No logs appear, function doesn't run

**Check timer configuration:**
```bash
# Verify function.json has correct schedule
cat DatabricksMonitor/function.json

# Expected: "schedule": "0 */5 * * * *"  (every 5 minutes)
```

**Restart function app:**
```bash
az functionapp restart \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP
```

### Issue 2: Databricks API Error 401

**Symptom:** Logs show "Databricks API error: 401"

**Cause:** Invalid or expired token

**Fix:**
```bash
# Regenerate token in Databricks (Step 1.2)
# Update app setting:
az functionapp config appsettings set \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --settings DATABRICKS_TOKEN="NEW_TOKEN_HERE"
```

### Issue 3: FastAPI Not Receiving Events

**Symptom:** Function runs, but FastAPI doesn't get events

**Check FastAPI URL:**
```bash
# Verify URL is correct
az functionapp config appsettings list \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query "[?name=='FASTAPI_URL'].value" -o tsv

# Test FastAPI endpoint manually:
curl -X POST "https://your-app.azurewebsites.net/databricks-monitor" \
  -H "Content-Type: application/json" \
  -d '{"event":"test","cluster":{"cluster_name":"test"}}'

# Expected: 200 OK or {"ticket_id":"..."}
```

### Issue 4: No Cluster Events Found

**Symptom:** Function runs but finds 0 events

**Check Events API:**
```bash
# Test Events API manually
curl -X POST "${DATABRICKS_HOST}/api/2.0/clusters/events" \
  -H "Authorization: Bearer ${DATABRICKS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "start_time": '$(date -d '1 hour ago' +%s000)',
    "end_time": '$(date +%s000)',
    "limit": 10
  }'

# Expected: JSON with events array
# If empty: No cluster events in last hour (normal if no activity)
```

### Issue 5: Function Deployment Failed

**Symptom:** Deploy command fails

**Solution:**
```bash
# Ensure Azure Functions Core Tools is installed
func --version

# If not installed (Ubuntu/Debian):
wget -q https://packages.microsoft.com/config/ubuntu/20.04/packages-microsoft-prod.deb
sudo dpkg -i packages-microsoft-prod.deb
sudo apt-get update
sudo apt-get install azure-functions-core-tools-4

# Try deploy again
func azure functionapp publish $FUNCTION_APP_NAME --python --build remote
```

---

## VERIFICATION CHECKLIST

After deployment, verify each step:

- [ ] Function App created and running
- [ ] Storage account created
- [ ] Application Insights created
- [ ] App settings configured (DATABRICKS_HOST, TOKEN, FASTAPI_URL)
- [ ] Function code deployed
- [ ] Function appears in portal
- [ ] Timer trigger working (check logs every 5 minutes)
- [ ] Events API accessible (no 401/403 errors)
- [ ] FastAPI receiving events (check FastAPI logs)
- [ ] Tickets being created (check dashboard)
- [ ] Slack notifications working

---

## USEFUL COMMANDS

### View Function Logs (Live)
```bash
func azure functionapp logstream $FUNCTION_APP_NAME
```

### List All Functions
```bash
az functionapp function list \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --output table
```

### Update App Settings
```bash
az functionapp config appsettings set \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --settings KEY="VALUE"
```

### Restart Function App
```bash
az functionapp restart \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP
```

### Delete Function App (Cleanup)
```bash
az functionapp delete \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP
```

### View in Azure Portal
```bash
# Get portal URL
echo "https://portal.azure.com/#@/resource/subscriptions/$(az account show --query id -o tsv)/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Web/sites/$FUNCTION_APP_NAME"
```

---

## COST BREAKDOWN

| Resource | Tier | Cost/Month |
|----------|------|------------|
| **Function App** | Consumption (Y1) | $0* |
| **Storage Account** | Standard LRS | $0.01 |
| **Application Insights** | Basic (5GB free) | $0* |
| **Total** | | **~$0.01/month** |

*Free tier: 1M executions/month (we use ~8,640)

---

## NEXT STEPS

After successful deployment:

1. **Monitor for 24 hours** - Verify function runs every 5 minutes
2. **Test cluster failure** - Terminate a cluster and verify detection
3. **Review tickets** - Check that cluster errors create proper tickets
4. **Document** - Update your runbook with this setup
5. **Schedule token rotation** - Set reminder to rotate Databricks token every 90 days

---

## SUPPORT

If you encounter issues:

1. Check Application Insights logs
2. Check FastAPI logs
3. Check Databricks audit logs
4. Review this troubleshooting guide
5. Contact Azure support if infrastructure issues

---

**Deployment complete! Your cluster monitoring is now automated.** 🎉
