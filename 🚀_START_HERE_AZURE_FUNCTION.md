# 🚀 START HERE: Azure Function Deployment

## Quick Navigation

**Choose your path:**

1. [**AUTOMATED** - Quickstart Script (15 minutes)](#option-a-automated-quickstart) ⭐ RECOMMENDED
2. [**MANUAL** - Step-by-Step Guide (45 minutes)](#option-b-manual-step-by-step)
3. [**UNDERSTAND** - How It Works](#how-it-works)

---

## OPTION A: AUTOMATED QUICKSTART ⭐

**Total time: 15 minutes**

### What You Need Before Starting:

1. ✅ **Databricks Personal Access Token**
   - Go to Databricks → User Settings → Access Tokens → Generate
   - Copy the token (starts with `dapi...`)
   - [How to create token](#get-databricks-token)

2. ✅ **Databricks Workspace URL**
   - Example: `https://adb-1234567890123456.7.azuredatabricks.net`
   - Find it in Azure Portal or Databricks browser URL

3. ✅ **FastAPI Endpoint URL**
   - Example: `https://your-rca-app.azurewebsites.net/databricks-monitor`
   - This is your RCA app endpoint

### Run the Quickstart Script:

```bash
# Navigate to function directory
cd /home/user/demo-autoremediation/azure-function-databricks-monitor

# Run quickstart script
./quickstart.sh
```

### The script will:

1. ✅ Check prerequisites (Azure CLI, Functions Core Tools)
2. ✅ Ask for configuration (Databricks URL, token, FastAPI URL)
3. ✅ Create all Azure resources (Function App, Storage, App Insights)
4. ✅ Configure settings
5. ✅ Deploy function code
6. ✅ Verify deployment

### When Prompted, Enter:

```
Resource Group: rg_techdemo_2025_Q4
Azure region: eastus
Databricks Host URL: https://adb-XXXXX.XX.azuredatabricks.net
Databricks Token: dapi1234567890abcdef...
FastAPI URL: https://your-rca-app.azurewebsites.net/databricks-monitor
Polling interval: 5
```

### After Completion:

The script creates `deployment-info.txt` with all details.

**Verify deployment:**
```bash
# View function logs (runs every 5 minutes)
func azure functionapp logstream func-dbx-monitor-XXXXX
```

**Done!** Function will now monitor cluster failures every 5 minutes.

---

## OPTION B: MANUAL STEP-BY-STEP

**Total time: 45 minutes**

**Use this if:**
- You want to understand each step
- You need to customize the deployment
- Quickstart script failed and you want control

### Complete Manual Guide:

👉 **[AZURE_FUNCTION_DEPLOYMENT_GUIDE.md](AZURE_FUNCTION_DEPLOYMENT_GUIDE.md)**

**Sections:**
1. Prerequisites Check
2. Get Databricks Token
3. Create Azure Resources
4. Configure Function App
5. Deploy Function Code
6. Test and Verify
7. Troubleshooting

---

## GET DATABRICKS TOKEN

### Step 1: Open Databricks

1. Go to **Azure Portal**
2. Search for your Databricks workspace: **"techdemo_databricks"**
3. Click **"Launch Workspace"**

### Step 2: Create Token

1. Click **your email** (top-right corner)
2. Select **"User Settings"**
3. Go to **"Access tokens"** tab
4. Click **"Generate new token"**

**Fill in:**
- Comment: `Azure Function - Cluster Monitoring`
- Lifetime: `90` days

5. Click **"Generate"**
6. **COPY THE TOKEN** - You only see it once!

**Example:** `dapi1234567890abcdef1234567890abcdef1234567890ab`

### Step 3: Test Token

```bash
# Set variables
DATABRICKS_HOST="https://adb-XXXXX.XX.azuredatabricks.net"
DATABRICKS_TOKEN="dapiXXXXXXXXXX"

# Test
curl -X GET "${DATABRICKS_HOST}/api/2.0/clusters/list" \
  -H "Authorization: Bearer ${DATABRICKS_TOKEN}"

# Expected: JSON with cluster list
# If error: Token is invalid or expired
```

---

## HOW IT WORKS

### Architecture:

```
┌─────────────────────────────────────────────┐
│  Databricks Cluster Fails                    │
│  (startup failure, crash, OOM, etc.)        │
└─────────────────────────────────────────────┘
                  ↓
       (Databricks stores in Events API)
                  ↓
┌─────────────────────────────────────────────┐
│  Azure Function (Timer: Every 5 minutes)     │
│  - Wakes up automatically                    │
│  - Calls Databricks Events API              │
│  - GET /api/2.0/clusters/events             │
└─────────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│  Function Filters Events                     │
│  - Keep: Cluster errors (FAILED_TO_START)   │
│  - Keep: Terminations with error reason     │
│  - Skip: Normal events (RUNNING, etc.)      │
│  - Skip: Job events (have webhooks)         │
└─────────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│  Function Formats as Webhook                 │
│  {                                           │
│    "event": "cluster.terminated",           │
│    "cluster": {                             │
│      "cluster_name": "Production",          │
│      "termination_reason": {...}            │
│    }                                         │
│  }                                           │
└─────────────────────────────────────────────┘
                  ↓
       (HTTP POST to FastAPI)
                  ↓
┌─────────────────────────────────────────────┐
│  FastAPI /databricks-monitor                 │
│  - Receives event (looks like webhook!)     │
│  - DatabricksExtractor processes it         │
│  - No code changes needed!                  │
└─────────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│  Create Outputs                              │
│  ✓ Database ticket                          │
│  ✓ Slack notification                       │
│  ✓ Jira ticket                              │
│  ✓ Dashboard update                         │
└─────────────────────────────────────────────┘
```

### What Gets Monitored:

**Cluster Errors (NEW):**
- ✅ Cluster startup failures
- ✅ Cluster crashes (OOM, driver errors)
- ✅ Library installation failures
- ✅ Cloud capacity issues
- ✅ Driver not responding

**Job Errors (EXISTING):**
- ✅ Job execution failures (via webhooks)

**Together = Complete monitoring!**

### Timing:

- **Delay:** 2-5 minutes (acceptable for cluster failures)
- **Frequency:** Function runs every 5 minutes
- **Detection window:** Last 5 minutes of events

### Cost:

- **Azure Function:** $0/month (free tier: 1M executions)
- **Storage:** ~$0.01/month
- **App Insights:** $0/month (5GB free)
- **Total:** **~$0.01/month** ✅

---

## VERIFICATION STEPS

After deployment, verify it's working:

### 1. Check Function Logs

```bash
# View live logs
func azure functionapp logstream func-dbx-monitor-XXXXX

# Expected output (every 5 minutes):
# Databricks Monitor function started...
# Querying events from ... to ...
# Retrieved X events
# Filtered to Y errors
# Databricks Monitor completed
```

### 2. Test with Real Cluster Failure

**Option A: Terminate a cluster**
```bash
databricks clusters list
databricks clusters delete --cluster-id YOUR_CLUSTER_ID

# Wait 5-10 minutes
# Check function logs → Should detect TERMINATED event
# Check FastAPI logs → Should receive event
# Check dashboard → Should see new ticket
```

**Option B: Start cluster with invalid config**
```bash
# Try to start cluster with invalid instance type
# Will fail with FAILED_TO_START
# Function will detect within 5 minutes
```

### 3. Check Application Insights

```bash
# View recent executions
az monitor app-insights query \
  --app appi-dbx-monitor-XXXXX \
  --resource-group rg_techdemo_2025_Q4 \
  --analytics-query "requests | where timestamp > ago(1h) | project timestamp, resultCode" \
  --output table

# Expected: Shows function runs with 200 status
```

---

## TROUBLESHOOTING

### Issue: Function not running

**Check timer trigger:**
```bash
# View function configuration
az functionapp function show \
  --name func-dbx-monitor-XXXXX \
  --resource-group rg_techdemo_2025_Q4 \
  --function-name DatabricksMonitor

# Restart function app
az functionapp restart \
  --name func-dbx-monitor-XXXXX \
  --resource-group rg_techdemo_2025_Q4
```

### Issue: Databricks API error 401

**Cause:** Invalid or expired token

**Fix:**
1. Create new token in Databricks
2. Update app setting:
```bash
az functionapp config appsettings set \
  --name func-dbx-monitor-XXXXX \
  --resource-group rg_techdemo_2025_Q4 \
  --settings DATABRICKS_TOKEN="NEW_TOKEN"
```

### Issue: FastAPI not receiving events

**Check endpoint:**
```bash
# Test FastAPI manually
curl -X POST "https://your-rca-app.azurewebsites.net/databricks-monitor" \
  -H "Content-Type: application/json" \
  -d '{"event":"test","cluster":{"cluster_name":"test"}}'

# Expected: 200 OK or {"ticket_id":"..."}
```

### Issue: No events found

**This is NORMAL if:**
- No clusters have failed recently
- All clusters are running healthy
- No cluster activity in last 5 minutes

**Test manually:**
```bash
# Call Events API directly
curl -X POST "${DATABRICKS_HOST}/api/2.0/clusters/events" \
  -H "Authorization: Bearer ${DATABRICKS_TOKEN}" \
  -d '{
    "start_time": '$(date -d '24 hours ago' +%s000)',
    "limit": 10
  }'

# Shows recent events (should have some activity)
```

---

## FILES CREATED

All files are in: `/home/user/demo-autoremediation/azure-function-databricks-monitor/`

| File | Purpose |
|------|---------|
| `DatabricksMonitor/__init__.py` | Main function code |
| `DatabricksMonitor/function.json` | Timer trigger config (every 5 min) |
| `requirements.txt` | Python dependencies |
| `host.json` | Function app configuration |
| `quickstart.sh` | Automated deployment script ⭐ |
| `deploy.sh` | Deploy code only (after changes) |
| `local.settings.json` | Local testing configuration |

**Documentation:**
- `AZURE_FUNCTION_DEPLOYMENT_GUIDE.md` - Complete manual guide
- `🚀_START_HERE_AZURE_FUNCTION.md` - This file

---

## NEXT STEPS AFTER DEPLOYMENT

1. **Monitor for 24 hours** - Verify function runs reliably
2. **Test cluster failure** - Ensure end-to-end flow works
3. **Set up alerts** - Get notified if function fails
4. **Schedule token rotation** - Databricks tokens expire
5. **Document runbook** - Add to team documentation

---

## USEFUL COMMANDS

### View Logs
```bash
func azure functionapp logstream func-dbx-monitor-XXXXX
```

### Restart Function
```bash
az functionapp restart \
  --name func-dbx-monitor-XXXXX \
  --resource-group rg_techdemo_2025_Q4
```

### Update Settings
```bash
az functionapp config appsettings set \
  --name func-dbx-monitor-XXXXX \
  --resource-group rg_techdemo_2025_Q4 \
  --settings KEY="VALUE"
```

### View in Portal
```bash
# Get portal URL
az functionapp show \
  --name func-dbx-monitor-XXXXX \
  --resource-group rg_techdemo_2025_Q4 \
  --query "{url:defaultHostName}" -o table
```

### Delete (Cleanup)
```bash
az functionapp delete \
  --name func-dbx-monitor-XXXXX \
  --resource-group rg_techdemo_2025_Q4
```

---

## DECISION FLOWCHART

```
START: Need to deploy Azure Function?
  │
  ├─ Do you have Databricks token?
  │  ├─ NO → [Get Token](#get-databricks-token) first
  │  └─ YES → Continue
  │
  ├─ Do you want automated deployment?
  │  ├─ YES → Use [Quickstart Script](#option-a-automated-quickstart) ⭐
  │  └─ NO → Use [Manual Guide](#option-b-manual-step-by-step)
  │
  ├─ Deployment completed?
  │  ├─ YES → [Verify](#verification-steps)
  │  └─ NO → Check [Troubleshooting](#troubleshooting)
  │
  └─ Verification passed?
     ├─ YES → Done! Monitor in production
     └─ NO → Check logs, fix issues, re-verify
```

---

## RECOMMENDED PATH

**For most users:**

1. ✅ Read "How It Works" section (5 min)
2. ✅ Get Databricks token (5 min)
3. ✅ Run quickstart script (10 min)
4. ✅ Verify deployment (5 min)
5. ✅ Test with cluster failure (10 min)

**Total: ~35 minutes**

---

## SUPPORT

If you get stuck:

1. Check function logs (most issues show here)
2. Check [Troubleshooting](#troubleshooting) section
3. Review Application Insights metrics
4. Check FastAPI logs (verify events arriving)
5. Re-run deployment with verbose logging

---

**Ready to start? → [Run Quickstart Script](#option-a-automated-quickstart)** 🚀
