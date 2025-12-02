# 🎯 Auto-Remediation Playbook Setup Guide

## Overview

This guide shows you how to set up the recovery playbooks that execute automated remediation actions. You have **3 options**:

1. ✅ **Azure Logic Apps** (Recommended - No Code, Visual Designer)
2. ⚙️ **Azure Functions** (More Control, Requires Code)
3. 🔧 **Direct API Integration** (No Azure Required, Uses Playbook Handlers Directly)

---

## 📋 Table of Contents

1. [Option 1: Azure Logic Apps (Recommended)](#option-1-azure-logic-apps-recommended)
2. [Option 2: Azure Functions](#option-2-azure-functions)
3. [Option 3: Direct API Integration (No Azure)](#option-3-direct-api-integration-no-azure)
4. [Testing Your Playbooks](#testing-your-playbooks)
5. [Troubleshooting](#troubleshooting)

---

## Option 1: Azure Logic Apps (Recommended)

### Why Logic Apps?
- ✅ No code required
- ✅ Visual workflow designer
- ✅ Built-in retry logic
- ✅ Easy to monitor and debug
- ✅ Azure-native authentication

### Prerequisites
```bash
# Azure CLI installed
az --version

# Login to Azure
az login

# Set your subscription
az account set --subscription "Your-Subscription-Name"
```

---

## 🔧 Playbook 1: Retry ADF Pipeline

### Step 1: Create Logic App
```bash
# Set variables
RESOURCE_GROUP="rg_techdemo_2025_Q4"
LOCATION="eastus"
LOGIC_APP_NAME="playbook-retry-adf-pipeline"

# Create Logic App
az logic workflow create \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --name $LOGIC_APP_NAME \
  --definition '{
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
              "ticket_id": { "type": "string" },
              "error_type": { "type": "string" },
              "metadata": {
                "type": "object",
                "properties": {
                  "run_id": { "type": "string" },
                  "pipeline": { "type": "string" },
                  "source": { "type": "string" }
                }
              },
              "retry_attempt": { "type": "integer" },
              "max_retries": { "type": "integer" }
            }
          }
        }
      }
    },
    "actions": {},
    "outputs": {}
  }'
```

### Step 2: Add Actions in Azure Portal

1. **Go to Azure Portal** → Logic Apps → `playbook-retry-adf-pipeline`
2. **Click "Logic app designer"**
3. **Add these actions:**

#### Action 1: Parse JSON
- **Action:** Data Operations → Parse JSON
- **Content:** `@triggerBody()`
- **Schema:** (Auto-generate from sample payload)

#### Action 2: HTTP - Retry Pipeline
- **Action:** HTTP
- **Method:** POST
- **URI:**
  ```
  https://management.azure.com/subscriptions/@{variables('subscriptionId')}/resourceGroups/@{variables('resourceGroup')}/providers/Microsoft.DataFactory/factories/@{variables('factoryName')}/pipelines/@{body('Parse_JSON')['metadata']['pipeline']}/createRun?api-version=2018-06-01
  ```
- **Headers:**
  ```json
  {
    "Content-Type": "application/json"
  }
  ```
- **Authentication:** Managed Identity (Enable System Assigned Identity on Logic App)
- **Body:**
  ```json
  {
    "parameters": {}
  }
  ```

#### Action 3: Response - Success
- **Action:** Response
- **Status Code:** 200
- **Headers:**
  ```json
  {
    "Content-Type": "application/json"
  }
  ```
- **Body:**
  ```json
  {
    "status": "success",
    "new_run_id": "@{body('HTTP')['runId']}",
    "ticket_id": "@{body('Parse_JSON')['ticket_id']}",
    "pipeline": "@{body('Parse_JSON')['metadata']['pipeline']}"
  }
  ```

### Step 3: Enable Managed Identity

```bash
# Enable system-assigned managed identity
az logic workflow identity assign \
  --resource-group $RESOURCE_GROUP \
  --name $LOGIC_APP_NAME

# Get the identity principal ID
PRINCIPAL_ID=$(az logic workflow identity show \
  --resource-group $RESOURCE_GROUP \
  --name $LOGIC_APP_NAME \
  --query principalId -o tsv)

# Grant ADF Contributor role
ADF_NAME="your-adf-name"
ADF_RESOURCE_ID=$(az datafactory show \
  --resource-group $RESOURCE_GROUP \
  --name $ADF_NAME \
  --query id -o tsv)

az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Data Factory Contributor" \
  --scope $ADF_RESOURCE_ID
```

### Step 4: Get Logic App URL

```bash
# Get the callback URL
az logic workflow trigger show \
  --resource-group $RESOURCE_GROUP \
  --name $LOGIC_APP_NAME \
  --trigger-name manual \
  --query "listCallbackUrl().value" -o tsv
```

**Copy this URL to your .env:**
```bash
PLAYBOOK_RETRY_PIPELINE=https://prod-123.eastus.logic.azure.com:443/workflows/.../triggers/manual/paths/invoke?api-version=2016-10-01&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=...
```

---

## 🔧 Playbook 2: Restart Databricks Cluster

### Step 1: Create Logic App

```bash
LOGIC_APP_NAME="playbook-restart-databricks-cluster"

az logic workflow create \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --name $LOGIC_APP_NAME \
  --definition @restart-cluster-definition.json
```

### Step 2: Configure in Portal

**Actions:**

#### Action 1: Parse JSON
- **Content:** `@triggerBody()`

#### Action 2: HTTP - Start Cluster
- **Method:** POST
- **URI:** `@{parameters('databricksHost')}/api/2.0/clusters/start`
- **Headers:**
  ```json
  {
    "Authorization": "Bearer @{parameters('databricksToken')}",
    "Content-Type": "application/json"
  }
  ```
- **Body:**
  ```json
  {
    "cluster_id": "@{body('Parse_JSON')['metadata']['cluster_id']}"
  }
  ```

#### Action 3: Until - Wait for Running
- **Condition:** `@equals(body('Get_Cluster_State')['state'], 'RUNNING')`
- **Timeout:** PT10M (10 minutes)
- **Interval:** 30 seconds

#### Action 4: Get Cluster State (Inside Until Loop)
- **Method:** GET
- **URI:** `@{parameters('databricksHost')}/api/2.0/clusters/get?cluster_id=@{body('Parse_JSON')['metadata']['cluster_id']}`

#### Action 5: Response
```json
{
  "status": "success",
  "cluster_id": "@{body('Parse_JSON')['metadata']['cluster_id']}",
  "state": "@{body('Get_Cluster_State')['state']}"
}
```

### Step 3: Add Parameters

In Logic App Designer → Parameters:
```json
{
  "databricksHost": {
    "type": "string",
    "defaultValue": "https://adb-1234567890123456.7.azuredatabricks.net"
  },
  "databricksToken": {
    "type": "securestring",
    "defaultValue": "dapi1234567890abcdef..."
  }
}
```

Or use **Azure Key Vault** (recommended):
1. Create Key Vault secret: `databricks-token`
2. In Logic App, add action: **Get Secret** from Key Vault
3. Use `@body('Get_secret')['value']` in HTTP action

---

## 🔧 Playbook 3: Retry Databricks Job

```bash
LOGIC_APP_NAME="playbook-retry-databricks-job"
```

**HTTP Action:**
- **Method:** POST
- **URI:** `@{parameters('databricksHost')}/api/2.1/jobs/run-now`
- **Body:**
  ```json
  {
    "job_id": @{body('Parse_JSON')['metadata']['job_id']}
  }
  ```

**Response:**
```json
{
  "status": "success",
  "new_run_id": "@{body('Run_Job')['run_id']}",
  "job_id": "@{body('Parse_JSON')['metadata']['job_id']}"
}
```

---

## 🔧 Playbook 4: Scale Databricks Cluster

```bash
LOGIC_APP_NAME="playbook-scale-databricks-cluster"
```

**Actions:**

1. **Get Cluster Config**
   - GET: `/api/2.0/clusters/get?cluster_id=...`

2. **Calculate New Workers**
   ```
   @mul(body('Get_Cluster')['num_workers'], 1.5)
   ```

3. **Edit Cluster**
   - POST: `/api/2.0/clusters/edit`
   - Body:
     ```json
     {
       "cluster_id": "...",
       "num_workers": @{variables('newWorkers')},
       "spark_version": "@{body('Get_Cluster')['spark_version']}",
       "node_type_id": "@{body('Get_Cluster')['node_type_id']}"
     }
     ```

---

## 🔧 Playbook 5: Reinstall Libraries

```bash
LOGIC_APP_NAME="playbook-reinstall-libraries"
```

**Actions:**

1. **Parse Library Spec**
   ```
   @split(body('Parse_JSON')['metadata']['library_spec'], '==')
   ```

2. **Try Original Version**
   - POST: `/api/2.0/libraries/install`

3. **On Failure - Try Fallback Versions**
   - Use **Switch** action based on library name
   - Array of fallback versions in parameters

---

## 🔧 Quick Setup Script (All Playbooks)

Save this as `setup-playbooks.sh`:

```bash
#!/bin/bash

# Configuration
RESOURCE_GROUP="rg_techdemo_2025_Q4"
LOCATION="eastus"
DATABRICKS_HOST="https://adb-1234567890123456.7.azuredatabricks.net"
DATABRICKS_TOKEN="dapi1234567890abcdef..."
ADF_NAME="your-adf-name"

# Array of playbooks
declare -a playbooks=(
  "playbook-retry-adf-pipeline"
  "playbook-restart-databricks-cluster"
  "playbook-retry-databricks-job"
  "playbook-scale-databricks-cluster"
  "playbook-reinstall-libraries"
)

echo "🚀 Creating Logic Apps for Auto-Remediation Playbooks..."

for playbook in "${playbooks[@]}"
do
  echo "Creating $playbook..."

  az logic workflow create \
    --resource-group $RESOURCE_GROUP \
    --location $LOCATION \
    --name $playbook \
    --definition '{
      "$schema": "https://schema.management.azure.com/schemas/2016-06-01/Microsoft.Logic.json",
      "contentVersion": "1.0.0.0",
      "triggers": {
        "manual": {
          "type": "Request",
          "kind": "Http",
          "inputs": {
            "schema": {}
          }
        }
      },
      "actions": {},
      "outputs": {}
    }'

  # Enable managed identity
  az logic workflow identity assign \
    --resource-group $RESOURCE_GROUP \
    --name $playbook

  # Get URL
  URL=$(az logic workflow trigger show \
    --resource-group $RESOURCE_GROUP \
    --name $playbook \
    --trigger-name manual \
    --query "listCallbackUrl().value" -o tsv)

  echo "✅ $playbook created!"
  echo "   URL: $URL"
  echo ""
done

echo "🎉 All playbooks created!"
echo ""
echo "📝 Add these URLs to your .env file:"
echo ""
for playbook in "${playbooks[@]}"
do
  URL=$(az logic workflow trigger show \
    --resource-group $RESOURCE_GROUP \
    --name $playbook \
    --trigger-name manual \
    --query "listCallbackUrl().value" -o tsv)

  ENV_VAR=$(echo $playbook | tr '[:lower:]-' '[:upper:]_' | sed 's/PLAYBOOK_/PLAYBOOK_/')
  echo "$ENV_VAR=$URL"
done
```

**Run it:**
```bash
chmod +x setup-playbooks.sh
./setup-playbooks.sh
```

---

## Option 2: Azure Functions

### Step 1: Create Function App

```bash
FUNCTION_APP_NAME="aiops-remediation-playbooks"
STORAGE_ACCOUNT="aiopsstorage$(date +%s)"

# Create storage account
az storage account create \
  --name $STORAGE_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION

# Create function app
az functionapp create \
  --resource-group $RESOURCE_GROUP \
  --name $FUNCTION_APP_NAME \
  --storage-account $STORAGE_ACCOUNT \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4 \
  --os-type Linux
```

### Step 2: Create Function - Retry ADF Pipeline

**File: `retry_adf_pipeline/__init__.py`**
```python
import logging
import json
import os
import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.mgmt.datafactory import DataFactoryManagementClient

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Retry ADF Pipeline playbook triggered')

    try:
        # Parse request
        req_body = req.get_json()
        ticket_id = req_body.get('ticket_id')
        metadata = req_body.get('metadata', {})
        pipeline_name = metadata.get('pipeline')

        # Azure credentials
        subscription_id = os.environ['AZURE_SUBSCRIPTION_ID']
        resource_group = os.environ['AZURE_RESOURCE_GROUP']
        factory_name = os.environ['AZURE_ADF_NAME']

        # Authenticate
        credential = DefaultAzureCredential()
        adf_client = DataFactoryManagementClient(credential, subscription_id)

        # Trigger pipeline run
        run_response = adf_client.pipelines.create_run(
            resource_group,
            factory_name,
            pipeline_name
        )

        # Return success
        return func.HttpResponse(
            json.dumps({
                "status": "success",
                "new_run_id": run_response.run_id,
                "ticket_id": ticket_id,
                "pipeline": pipeline_name
            }),
            mimetype="application/json",
            status_code=200
        )

    except Exception as e:
        logging.error(f"Error: {e}")
        return func.HttpResponse(
            json.dumps({"status": "error", "message": str(e)}),
            mimetype="application/json",
            status_code=500
        )
```

**File: `retry_adf_pipeline/function.json`**
```json
{
  "scriptFile": "__init__.py",
  "bindings": [
    {
      "authLevel": "function",
      "type": "httpTrigger",
      "direction": "in",
      "name": "req",
      "methods": ["post"]
    },
    {
      "type": "http",
      "direction": "out",
      "name": "$return"
    }
  ]
}
```

### Step 3: Deploy Functions

```bash
# Package and deploy
cd playbooks-functions
func azure functionapp publish $FUNCTION_APP_NAME

# Get function URL
FUNCTION_URL=$(az functionapp function show \
  --resource-group $RESOURCE_GROUP \
  --name $FUNCTION_APP_NAME \
  --function-name retry_adf_pipeline \
  --query "invokeUrlTemplate" -o tsv)

FUNCTION_KEY=$(az functionapp keys list \
  --resource-group $RESOURCE_GROUP \
  --name $FUNCTION_APP_NAME \
  --query "functionKeys.default" -o tsv)

echo "PLAYBOOK_RETRY_PIPELINE=${FUNCTION_URL}?code=${FUNCTION_KEY}"
```

---

## Option 3: Direct API Integration (No Azure)

### Use Built-in Playbook Handlers Directly

This option doesn't require Azure Logic Apps or Functions - it uses the playbook handlers we already created!

### Step 1: Create Simple Flask/FastAPI Wrapper

**File: `playbook_server.py`**
```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import sys
sys.path.append('/home/user/demo-autoremediation/genai_rca_assistant')

from playbook_handlers import (
    retry_adf_pipeline,
    restart_databricks_cluster,
    retry_databricks_job,
    scale_databricks_cluster,
    reinstall_databricks_libraries
)

app = FastAPI()

@app.post("/playbooks/retry-pipeline")
async def retry_pipeline_endpoint(request: Request):
    body = await request.json()
    metadata = body.get('metadata', {})

    success, result = await retry_adf_pipeline(
        pipeline_name=metadata.get('pipeline'),
        # Credentials from environment
    )

    return JSONResponse({
        "status": "success" if success else "error",
        **result
    })

@app.post("/playbooks/restart-cluster")
async def restart_cluster_endpoint(request: Request):
    body = await request.json()
    metadata = body.get('metadata', {})

    success, result = await restart_databricks_cluster(
        cluster_id=metadata.get('cluster_id')
    )

    return JSONResponse({
        "status": "success" if success else "error",
        **result
    })

@app.post("/playbooks/retry-job")
async def retry_job_endpoint(request: Request):
    body = await request.json()
    metadata = body.get('metadata', {})

    success, result = await retry_databricks_job(
        job_id=metadata.get('job_id')
    )

    return JSONResponse({
        "status": "success" if success else "error",
        **result
    })

@app.post("/playbooks/scale-cluster")
async def scale_cluster_endpoint(request: Request):
    body = await request.json()
    metadata = body.get('metadata', {})

    success, result = await scale_databricks_cluster(
        cluster_id=metadata.get('cluster_id')
    )

    return JSONResponse({
        "status": "success" if success else "error",
        **result
    })

@app.post("/playbooks/reinstall-libraries")
async def reinstall_libraries_endpoint(request: Request):
    body = await request.json()
    metadata = body.get('metadata', {})

    success, result = await reinstall_databricks_libraries(
        cluster_id=metadata.get('cluster_id'),
        library_spec=metadata.get('library_spec', 'pandas')
    )

    return JSONResponse({
        "status": "success" if success else "error",
        **result
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
```

### Step 2: Run Playbook Server

```bash
# In a separate terminal
cd /home/user/demo-autoremediation/genai_rca_assistant
python3 playbook_server.py
```

### Step 3: Update .env

```bash
# If running locally
PLAYBOOK_RETRY_PIPELINE=http://localhost:8001/playbooks/retry-pipeline
PLAYBOOK_RESTART_CLUSTER=http://localhost:8001/playbooks/restart-cluster
PLAYBOOK_RETRY_JOB=http://localhost:8001/playbooks/retry-job
PLAYBOOK_SCALE_CLUSTER=http://localhost:8001/playbooks/scale-cluster
PLAYBOOK_REINSTALL_LIBRARIES=http://localhost:8001/playbooks/reinstall-libraries

# If deployed on server
PLAYBOOK_RETRY_PIPELINE=https://your-server.com:8001/playbooks/retry-pipeline
# ... etc
```

**Advantages:**
- ✅ No Azure costs
- ✅ Full control
- ✅ Uses existing playbook_handlers.py
- ✅ Easy to test locally

**Disadvantages:**
- ❌ Need to deploy/host yourself
- ❌ Need to handle authentication
- ❌ Need to manage uptime

---

## Testing Your Playbooks

### Test 1: Manual Test via Curl

```bash
# Test retry pipeline playbook
curl -X POST "YOUR_PLAYBOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": "TEST-001",
    "error_type": "GatewayTimeout",
    "metadata": {
      "run_id": "test-run-001",
      "pipeline": "Test_Pipeline",
      "source": "adf"
    },
    "retry_attempt": 1,
    "max_retries": 3
  }'
```

**Expected Response:**
```json
{
  "status": "success",
  "new_run_id": "abc-123-def-456",
  "ticket_id": "TEST-001",
  "pipeline": "Test_Pipeline"
}
```

### Test 2: End-to-End Test

```bash
# 1. Set up .env with playbook URLs
cat > .env << 'EOF'
AUTO_REMEDIATION_ENABLED=true
PLAYBOOK_RETRY_PIPELINE=https://prod-123.logic.azure.com/.../invoke
DATABRICKS_HOST=https://adb-123.azuredatabricks.net
DATABRICKS_TOKEN=dapi123...
EOF

# 2. Start main application
cd genai_rca_assistant
python3 main.py

# 3. Send test webhook
curl -X POST "http://localhost:8000/azure-monitor?api_key=test" \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "essentials": {"alertRule": "Test_Pipeline"},
      "alertContext": {
        "properties": {
          "PipelineName": "Test_Pipeline",
          "PipelineRunId": "test-run-001",
          "ErrorCode": "GatewayTimeout",
          "ErrorMessage": "Gateway timeout"
        }
      }
    }
  }'

# 4. Check logs
tail -f /var/log/aiops/app.log
```

**Expected Log Output:**
```
🤖 Auto-remediation candidate detected: GatewayTimeout
✅ Auto-remediation task scheduled for ticket ADF-20251202-abc123
⏳ Waiting 10 seconds before triggering playbook...
🚀 Triggering playbook: retry_pipeline
✅ AUTO-REMEDIATION: Playbook executed successfully!
🆕 New run ID: new-run-789
```

---

## 🔍 Monitoring Your Playbooks

### In Azure Portal (Logic Apps)

1. Go to Logic App → Run History
2. Click on a run to see:
   - Input payload
   - Each action status
   - Output/errors
   - Duration

### Check Audit Trail

```sql
SELECT
    ticket_id,
    action,
    details,
    timestamp
FROM audit_trail
WHERE action LIKE 'Auto-Remediation%'
ORDER BY timestamp DESC
LIMIT 10;
```

---

## 🚨 Troubleshooting

### Problem: Playbook URL returns 404

**Solution:**
```bash
# Verify Logic App exists
az logic workflow show \
  --resource-group $RESOURCE_GROUP \
  --name $LOGIC_APP_NAME

# Get fresh URL
az logic workflow trigger show \
  --resource-group $RESOURCE_GROUP \
  --name $LOGIC_APP_NAME \
  --trigger-name manual \
  --query "listCallbackUrl().value" -o tsv
```

### Problem: "Unauthorized" error

**Solution:**
```bash
# Check managed identity
az logic workflow identity show \
  --resource-group $RESOURCE_GROUP \
  --name $LOGIC_APP_NAME

# Re-grant permissions
az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Data Factory Contributor" \
  --scope $ADF_RESOURCE_ID
```

### Problem: Databricks playbook times out

**Solution:**
- Increase timeout in Logic App (PT10M → PT30M)
- Check Databricks token is valid
- Verify cluster ID exists

### Problem: Playbook succeeds but no new run_id

**Solution:**
- Check Logic App run history for actual response
- Verify ADF pipeline exists
- Check ADF service health

---

## 📝 Summary

### Recommended Approach: **Option 1 (Azure Logic Apps)**

**Why?**
- No code to maintain
- Built-in retry/error handling
- Easy monitoring in Azure Portal
- Managed identity authentication
- Visual debugging

### Quick Start Checklist:

- [ ] Run `setup-playbooks.sh` script
- [ ] Configure managed identities
- [ ] Grant ADF Contributor role
- [ ] Add Databricks credentials to Key Vault
- [ ] Copy URLs to `.env`
- [ ] Test with curl
- [ ] Test end-to-end with webhook
- [ ] Monitor first auto-remediation in Azure Portal

---

## 🎓 Next Steps

1. **Start with ONE playbook** (e.g., retry-pipeline)
2. **Test it manually** with curl
3. **Enable auto-remediation** for that error type only
4. **Monitor for 24 hours**
5. **Add more playbooks** gradually

---

Need help with a specific playbook? Let me know which one and I'll provide detailed step-by-step instructions! 🚀
