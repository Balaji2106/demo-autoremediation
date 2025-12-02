# 🔔 Databricks Webhook Setup for Auto-Heal

## Overview

This guide shows you how to configure Databricks to **automatically send webhooks** to your auto-heal system when jobs fail.

**When a Databricks job fails:**
```
Databricks Job Fails
       ↓
Databricks sends webhook (HTTP POST)
       ↓
Auto-Heal System receives alert
       ↓
AI analyzes error
       ↓
Auto-remediation triggered (if applicable)
       ↓
Cluster restarted / Job retried / Library fixed
```

---

## 🚀 Quick Setup (5 minutes)

### **Step 1: Install Databricks SDK**

```bash
cd /home/user/demo-autoremediation
pip install databricks-sdk
```

### **Step 2: Configure Credentials**

```bash
# Add to .env
cat >> .env << EOF
DATABRICKS_HOST=https://adb-1234567890123456.7.azuredatabricks.net
DATABRICKS_TOKEN=dapi1234567890abcdef...
AUTO_HEAL_WEBHOOK_URL=http://localhost:8000/databricks-monitor
EOF
```

**Get your Databricks token:**
1. Go to Databricks Workspace
2. Click your profile (top right) → **User Settings**
3. Go to **Access Tokens** tab
4. Click **Generate New Token**
5. Name it "Auto-Heal Webhooks"
6. Copy the token

### **Step 3: Run Setup Script**

```bash
python3 setup-databricks-webhooks.py
```

**Example output:**
```
🔧 Databricks Auto-Heal Webhook Setup
==================================================
Databricks Host: https://adb-123.azuredatabricks.net
Webhook URL: http://localhost:8000/databricks-monitor

📋 Fetching existing jobs...
Found 5 jobs

Select jobs to add auto-heal webhooks:

1. ETL_Daily_Load (ID: 123)
2. Data_Quality_Check (ID: 456)
3. ML_Model_Training (ID: 789)
4. Data_Export (ID: 101)
5. Reporting_Pipeline (ID: 112)

Enter job numbers (comma-separated, or 'all' for all jobs):
> 1,2,3

Adding webhooks to 3 jobs...

🔄 Configuring: ETL_Daily_Load
   ✅ Webhook added to: ETL_Daily_Load
🔄 Configuring: Data_Quality_Check
   ✅ Webhook added to: Data_Quality_Check
🔄 Configuring: ML_Model_Training
   ✅ Webhook added to: ML_Model_Training

🎉 Setup complete!
```

### **Step 4: Test It**

```bash
# Start auto-heal system
./quick-start-auto-heal.sh
# Choose option 3

# In Databricks: Trigger a test job failure
# (or wait for a real failure)

# Watch auto-heal work:
tail -f logs/autoheal.log
```

---

## 📋 Manual Configuration (Via Databricks UI)

### **Option A: Configure for Specific Job**

1. **Go to Workflows**
   - Databricks Workspace → **Workflows**
   - Select your job

2. **Edit Notifications**
   - Click **Edit Job**
   - Go to **Notifications** tab

3. **Add Webhook**
   - Click **Add notification destination**
   - Select **Webhook**
   - Configure:
     ```
     Name: Auto-Heal System
     URL: http://localhost:8000/databricks-monitor
     Method: POST
     Headers: (leave empty)
     ```

4. **Select Events**
   - ✅ On failure
   - ✅ On timeout
   - ✅ On unexpected termination

5. **Save**

### **Option B: Configure for All New Jobs (Global)**

1. **Go to Admin Settings**
   - Databricks → **Settings** → **Admin Console**

2. **Workspace Settings**
   - Go to **Workspace Settings**
   - Find **Job Notifications**

3. **Set Default Webhook**
   ```
   Default Webhook URL: http://localhost:8000/databricks-monitor
   ```

---

## 🌐 Production Deployment (Internet-Accessible URL)

### **Problem:** Databricks can't reach `localhost:8000`

You need an **internet-accessible URL**. Here are your options:

### **Option 1: Use ngrok (Quick Testing)**

```bash
# Install ngrok
wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz
tar -xvzf ngrok-v3-stable-linux-amd64.tgz
sudo mv ngrok /usr/local/bin/

# Start ngrok tunnel
ngrok http 8000

# Output:
# Forwarding https://abc123.ngrok.io -> http://localhost:8000
```

**Use in Databricks:**
```
Webhook URL: https://abc123.ngrok.io/databricks-monitor
```

**Pros:**
- ✅ Instant setup (2 minutes)
- ✅ No server needed
- ✅ HTTPS included

**Cons:**
- ❌ URL changes on restart (use ngrok paid for static URLs)
- ❌ Free tier has limits

---

### **Option 2: Deploy to Azure App Service**

```bash
# Create App Service
az webapp create \
  --resource-group rg_techdemo_2025_Q4 \
  --plan AppServicePlan \
  --name aiops-autoheal-$(date +%s) \
  --runtime "PYTHON:3.11"

# Deploy
cd genai_rca_assistant
zip -r app.zip .
az webapp deployment source config-zip \
  --resource-group rg_techdemo_2025_Q4 \
  --name aiops-autoheal-xxx \
  --src app.zip

# Get URL
az webapp show \
  --resource-group rg_techdemo_2025_Q4 \
  --name aiops-autoheal-xxx \
  --query defaultHostName -o tsv

# Output: aiops-autoheal-xxx.azurewebsites.net
```

**Use in Databricks:**
```
Webhook URL: https://aiops-autoheal-xxx.azurewebsites.net/databricks-monitor
```

---

### **Option 3: Deploy to Azure Container Instances**

```bash
# Build and push Docker image
docker build -t aiops-autoheal .
az acr create --resource-group rg_techdemo_2025_Q4 --name myregistry --sku Basic
az acr login --name myregistry
docker tag aiops-autoheal myregistry.azurecr.io/aiops-autoheal:latest
docker push myregistry.azurecr.io/aiops-autoheal:latest

# Deploy container
az container create \
  --resource-group rg_techdemo_2025_Q4 \
  --name aiops-autoheal \
  --image myregistry.azurecr.io/aiops-autoheal:latest \
  --dns-name-label aiops-autoheal \
  --ports 8000

# Get URL
az container show \
  --resource-group rg_techdemo_2025_Q4 \
  --name aiops-autoheal \
  --query ipAddress.fqdn -o tsv

# Output: aiops-autoheal.eastus.azurecontainer.io
```

**Use in Databricks:**
```
Webhook URL: http://aiops-autoheal.eastus.azurecontainer.io:8000/databricks-monitor
```

---

## 🔐 Securing Webhooks (Recommended)

### **Option A: API Key Authentication**

The `/databricks-monitor` endpoint already supports this!

```bash
# In .env
RCA_API_KEY=my-super-secret-key-change-me
```

**In Databricks webhook config:**
```
URL: https://your-server.com/databricks-monitor?api_key=my-super-secret-key-change-me
```

### **Option B: Webhook Secret Validation**

Add HMAC signature validation (for production):

1. **Generate secret:**
```bash
openssl rand -hex 32
# Output: a1b2c3d4e5f6...
```

2. **Add to .env:**
```bash
DATABRICKS_WEBHOOK_SECRET=a1b2c3d4e5f6...
```

3. **Configure in Databricks:**
   - Webhook Headers:
     ```
     X-Databricks-Signature: <computed HMAC>
     ```

---

## 🧪 Testing Webhooks

### **Test 1: Manual Webhook Trigger**

```bash
# Simulate Databricks webhook
curl -X POST "http://localhost:8000/databricks-monitor" \
  -H "Content-Type: application/json" \
  -d '{
    "event": "job.failed",
    "job": {
      "settings": {
        "name": "Test_ETL_Job"
      }
    },
    "run": {
      "run_id": "test-run-001",
      "state": {
        "life_cycle_state": "TERMINATED",
        "state_message": "Cluster terminated unexpectedly"
      },
      "cluster_instance": {
        "cluster_id": "1234-567890-abc123"
      }
    }
  }'
```

**Expected Response:**
```json
{
  "status": "success",
  "ticket_id": "DBX-20251202T120000-abc123",
  "message": "Ticket created successfully from Databricks webhook"
}
```

### **Test 2: Trigger Real Job Failure**

1. **Create test job in Databricks:**
```python
# In Databricks notebook
raise Exception("Test failure for auto-heal")
```

2. **Run the job**

3. **Check auto-heal logs:**
```bash
tail -f logs/autoheal.log

# Expected:
# INFO: Databricks webhook received
# INFO: error_type=DatabricksJobExecutionError
# INFO: 🤖 Auto-remediation candidate detected
# ...
```

---

## 📊 Webhook Payload Examples

### **Job Failure Event**

```json
{
  "event": "job.failed",
  "job_id": 123,
  "job": {
    "settings": {
      "name": "ETL_Daily_Load",
      "timeout_seconds": 3600
    }
  },
  "run": {
    "run_id": 456,
    "run_name": "ETL_Daily_Load_2025-12-02",
    "state": {
      "life_cycle_state": "TERMINATED",
      "result_state": "FAILED",
      "state_message": "Cluster terminated unexpectedly"
    },
    "start_time": 1701518400000,
    "cluster_instance": {
      "cluster_id": "1234-567890-abc123"
    },
    "tasks": [{
      "task_key": "main_task",
      "state": {
        "result_state": "FAILED"
      }
    }]
  }
}
```

### **Timeout Event**

```json
{
  "event": "job.timeout",
  "job_id": 123,
  "run": {
    "run_id": 456,
    "state": {
      "life_cycle_state": "RUNNING",
      "state_message": "Job exceeded timeout of 3600 seconds"
    }
  }
}
```

---

## 🔍 Troubleshooting

### **Problem: Webhook not received**

**Check 1: Verify webhook URL is accessible**
```bash
curl http://localhost:8000/databricks-monitor
# Should return: 405 Method Not Allowed (expected - needs POST)
```

**Check 2: Check Databricks job logs**
- Go to job run → **Event Log**
- Look for webhook delivery status

**Check 3: Check auto-heal system logs**
```bash
tail -f logs/autoheal.log | grep "Databricks webhook"
```

### **Problem: Webhook received but no auto-heal**

**Check 1: Verify error type is supported**
```bash
# Check if error type is in registry
python3 -c "
from genai_rca_assistant.auto_remediation import get_supported_error_types
print(get_supported_error_types())
"
```

**Check 2: Check AUTO_REMEDIATION_ENABLED**
```bash
grep AUTO_REMEDIATION_ENABLED .env
# Should be: AUTO_REMEDIATION_ENABLED=true
```

**Check 3: Check audit trail**
```sql
sqlite3 data/tickets.db "
SELECT action, details
FROM audit_trail
WHERE action LIKE '%Auto-Remediation%'
ORDER BY timestamp DESC LIMIT 5
"
```

---

## 📝 Complete Setup Checklist

- [ ] Install Databricks SDK: `pip install databricks-sdk`
- [ ] Configure credentials in `.env`
- [ ] Get internet-accessible URL (ngrok/Azure)
- [ ] Run `python3 setup-databricks-webhooks.py`
- [ ] OR manually configure webhooks in Databricks UI
- [ ] Start auto-heal system: `./quick-start-auto-heal.sh`
- [ ] Test with manual webhook: `curl -X POST ...`
- [ ] Test with real job failure
- [ ] Monitor audit trail: Check database
- [ ] Set up alerts: Slack/email notifications

---

## 🎯 Summary

| Setup Method | Time | Difficulty | Best For |
|--------------|------|------------|----------|
| **Python Script** | 5 min | Easy | Multiple jobs |
| **Databricks UI** | 2 min/job | Very Easy | Single job |
| **Databricks CLI** | 10 min | Medium | Automation |

**Recommended:** Start with Python script for bulk setup, then use UI for individual jobs.

---

## 🚀 Next Steps

1. **Start simple:** Configure 1-2 test jobs first
2. **Test thoroughly:** Trigger test failures
3. **Monitor success rate:** Check audit trail after 1 week
4. **Expand gradually:** Add more jobs as confidence grows
5. **Deploy to production:** Use Azure App Service/ACI for permanent URL

---

**Need help?** Run `./quick-start-auto-heal.sh` and choose the interactive setup! 🎯
