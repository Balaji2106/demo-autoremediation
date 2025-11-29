# 📚 Complete Project Explanation - AIOps RCA Assistant

## Table of Contents
1. [Project Overview](#project-overview)
2. [Architecture & Components](#architecture--components)
3. [Code Files Explained](#code-files-explained)
4. [Workflow Diagrams](#workflow-diagrams)
5. [Database Schema](#database-schema)
6. [API Endpoints](#api-endpoints)

---

## Project Overview

**Project Name:** AIOps RCA Assistant (AI-Powered Root Cause Analysis System)

**Purpose:** Automatically detect failures in Azure Data Factory and Databricks, perform AI-powered root cause analysis using Google Gemini, create tickets, send notifications, and integrate with ITSM tools.

**Key Technologies:**
- **Backend:** FastAPI (Python)
- **AI/ML:** Google Gemini 2.5 Flash (Root Cause Analysis)
- **Database:** SQLite / Azure SQL (configurable)
- **Frontend:** Vanilla JavaScript + HTML/CSS
- **Real-time:** WebSockets
- **Cloud:** Azure (Monitor, Data Factory, Databricks, Blob Storage)
- **ITSM:** Jira (optional)
- **Notifications:** Slack (optional)

---

## Architecture & Components

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      ALERT SOURCES                              │
├─────────────────────────────────────────────────────────────────┤
│  1. Azure Data Factory  →  Azure Monitor Alert  →  Webhook     │
│  2. Databricks Jobs     →  Native Webhook                      │
│  3. Databricks Clusters →  Azure Monitor Alert  →  Webhook     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                   FASTAPI APPLICATION                           │
│                   (genai_rca_assistant/)                        │
├─────────────────────────────────────────────────────────────────┤
│  • main.py              ← Core application                     │
│  • error_extractors.py  ← Parse different webhook formats      │
│  • databricks_api_utils ← Fetch detailed Databricks errors     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      PROCESSING FLOW                            │
├─────────────────────────────────────────────────────────────────┤
│  1. Extract error from webhook  (error_extractors.py)          │
│  2. Enrich with API details     (databricks_api_utils.py)      │
│  3. Generate RCA with AI        (Google Gemini)                │
│  4. Check deduplication         (SQLite/Azure SQL)             │
│  5. Create ticket               (Database + Audit Trail)       │
│  6. Send notifications          (Slack + Jira)                 │
│  7. Broadcast via WebSocket     (Real-time dashboard updates)  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     OUTPUT CHANNELS                             │
├─────────────────────────────────────────────────────────────────┤
│  • Dashboard (dashboard.html)  ← Real-time monitoring         │
│  • Slack Channel               ← Instant alerts               │
│  • Jira Tickets                ← ITSM integration             │
│  • Azure Blob Storage          ← Audit logs                   │
│  • SQLite/Azure SQL            ← Persistent storage           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Code Files Explained

### 1. `error_extractors.py` - Webhook Parser Module

**Purpose:** Parse different webhook payload formats from various Azure services.

**Why it exists:** Each service (ADF, Databricks, Azure Functions, Synapse) sends webhooks in different formats. This module standardizes extraction.

**Classes:**

#### `AzureDataFactoryExtractor`
```python
@staticmethod
def extract(payload: Dict) -> Tuple[str, str, str, Dict]:
    # Returns: (pipeline_name, run_id, error_message, metadata)
```

**What it does:**
- Parses Azure Monitor Common Alert Schema for ADF alerts
- Extracts from both Log Analytics alerts (dimensions array) and Metric alerts (properties object)
- Handles nested JSON structures: `data.essentials`, `data.alertContext`
- Extracts: PipelineName, RunId, ErrorMessage, ActivityName, ErrorCode, FailureType

**Example Input:**
```json
{
  "data": {
    "essentials": {
      "alertRule": "ADF-Pipeline-Failed",
      "severity": "Sev2"
    },
    "alertContext": {
      "condition": {
        "allOf": [{
          "dimensions": [
            {"name": "PipelineName", "value": "DataIngestionPipeline"},
            {"name": "PipelineRunId", "value": "abc123"},
            {"name": "ErrorMessage", "value": "Source blob not found"}
          ]
        }]
      }
    }
  }
}
```

**Example Output:**
```python
(
    "DataIngestionPipeline",  # pipeline_name
    "abc123",                  # run_id
    "Source blob not found",   # error_message
    {                          # metadata
        "activity_name": "CopyActivity1",
        "error_code": "UserErrorSourceBlobNotExists",
        "alert_type": "Log"
    }
)
```

**Where it's called:** In `main.py` → `/azure-monitor` endpoint (line 902)

---

#### `DatabricksExtractor`
```python
@staticmethod
def extract(payload: Dict) -> Tuple[str, str, str, str, Dict]:
    # Returns: (resource_name, run_id, event_type, error_message, metadata)
```

**What it does:**
- Routes to specific extractors based on event type:
  - `_extract_job_event()` - Job failures
  - `_extract_cluster_event()` - Cluster failures
  - `_extract_library_event()` - Library installation failures
  - `_extract_generic_event()` - Fallback for unknown events

**Job Event Example:**
```json
{
  "event": "job.run.failed",
  "job": {"settings": {"name": "ETL_Job"}},
  "run": {
    "run_id": 12345,
    "state": {
      "state_message": "Task failed with exception",
      "result_state": "FAILED"
    }
  }
}
```

**Output:**
```python
(
    "ETL_Job",                 # job_name
    "12345",                   # run_id
    "job.run.failed",          # event_type
    "Task failed with exception", # error_message
    {"resource_type": "job", "life_cycle_state": "TERMINATED"}
)
```

**Where it's called:** In `main.py` → `/databricks-monitor` endpoint (line 1089)

---

#### `AzureFunctionsExtractor`, `AzureSynapseExtractor`
Similar pattern for other Azure services (not currently used but available for extension).

---

### 2. `databricks_api_utils.py` - Databricks API Client

**Purpose:** Fetch detailed error information from Databricks Jobs API when a webhook provides only generic errors.

**Why it exists:** Databricks webhooks often contain generic error messages like "Task failed". The API call fetches the actual exception stack trace.

**Key Functions:**

#### `fetch_databricks_run_details(run_id: str)`
```python
def fetch_databricks_run_details(run_id: str) -> Optional[Dict]:
```

**What it does:**
1. Calls Databricks Jobs API: `GET /api/2.1/jobs/runs/get?run_id={run_id}`
2. Returns full run details including task states
3. For each failed task, calls `fetch_task_output()` to get actual error traces

**API Response Structure:**
```json
{
  "job_id": 123,
  "run_id": 456,
  "state": {
    "life_cycle_state": "TERMINATED",
    "result_state": "FAILED",
    "state_message": "Run failed with error"
  },
  "tasks": [
    {
      "task_key": "data_validation",
      "state": {"result_state": "FAILED"},
      "run_output": {
        "error": "FileNotFoundError: '/mnt/data/input.csv' not found"
      }
    }
  ]
}
```

**Where it's called:** In `main.py` → `/databricks-monitor` endpoint (line 1154)

---

#### `fetch_task_output(task_run_id: str)`
```python
def fetch_task_output(task_run_id: str) -> Optional[Dict]:
```

**What it does:**
- Calls `GET /api/2.1/jobs/runs/get-output?run_id={task_run_id}`
- Returns the actual error trace, logs, and exception details

**Example Output:**
```json
{
  "error": "FileNotFoundError: '/mnt/data/input.csv' not found",
  "error_trace": "Traceback (most recent call last):\n  File...",
  "logs": "Starting task...\nReading from /mnt/data/input.csv\nERROR: File not found"
}
```

---

#### `extract_error_message(run_data: Dict)`
```python
def extract_error_message(run_data: Dict) -> Optional[str]:
```

**What it does:**
Prioritizes error messages:
1. **PRIORITY 1:** Task `run_output.error` (actual exception - most detailed)
2. **PRIORITY 2:** Task `exception.message`
3. **PRIORITY 3:** Task `state.state_message` (generic)
4. **FALLBACK:** Job-level `state.state_message`

**Example:**
```python
# Input: run_data with 2 failed tasks
# Output: "[Task: data_validation] FileNotFoundError | [Task: transform] KeyError: 'customer_id'"
```

**Where it's called:** In `databricks_api_utils.py` → `fetch_databricks_run_details()` (line 105)

---

### 3. `main.py` - Core FastAPI Application

**Purpose:** Main application with all API endpoints, business logic, AI integration, and database operations.

**File Structure:**
- Lines 1-148: Imports, configuration, database setup
- Lines 150-286: Database initialization and helper functions
- Lines 288-371: Authentication (JWT, password hashing)
- Lines 373-418: Audit trail and blob storage helpers
- Lines 420-558: AI/RCA logic (Gemini integration)
- Lines 560-620: ITSM (Jira) integration
- Lines 622-728: Slack notifications and WebSocket
- Lines 730-773: Utility functions
- Lines 777-836: Public endpoints (health, login page)
- Lines 838-871: Deduplication check endpoint
- Lines 874-1071: `/azure-monitor` (ADF alerts)
- Lines 1074-1327: `/databricks-monitor` (Databricks native webhooks)
- Lines 1330-1611: `/azure-monitor-alert` (NEW - Databricks cluster alerts)
- Lines 1613-1660: Protected endpoints (tickets, audit trail)

**Let me explain each major section:**

---

#### Configuration & Environment Variables (Lines 1-98)

```python
RCA_API_KEY = os.getenv("RCA_API_KEY", "balaji-rca-secret-2025")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL_ID = os.getenv("MODEL_ID", "models/gemini-2.5-flash")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
DATABRICKS_HOST = os.getenv("DATABRICKS_HOST", "")
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN", "")
JIRA_DOMAIN = os.getenv("JIRA_DOMAIN", "")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "")
```

**Purpose:** Load all credentials and settings from environment variables (`.env` file).

**Security:** No hardcoded credentials; all sensitive data in environment.

---

#### Database Setup (Lines 110-286)

**Tables Created:**

**1. `tickets` table:**
```sql
CREATE TABLE tickets (
    id TEXT PRIMARY KEY,              -- e.g., "ADF-20251129T143022-a3f2c1"
    timestamp TEXT,                   -- ISO 8601 UTC
    pipeline TEXT,                    -- Pipeline/Job/Cluster name
    run_id TEXT,                      -- Unique run identifier (for deduplication)
    rca_result TEXT,                  -- AI-generated root cause
    recommendations TEXT,             -- JSON array of fix steps
    confidence TEXT,                  -- "Very High", "High", "Medium", "Low"
    severity TEXT,                    -- "Critical", "High", "Medium", "Low"
    priority TEXT,                    -- "P1", "P2", "P3", "P4"
    error_type TEXT,                  -- "UserErrorSourceBlobNotExists", etc.
    affected_entity TEXT,             -- Specific component that failed
    status TEXT,                      -- "open", "in_progress", "acknowledged"
    ack_user TEXT,                    -- Who closed the ticket
    ack_empid TEXT,                   -- Employee ID
    ack_ts TEXT,                      -- Acknowledgment timestamp
    ack_seconds INTEGER,              -- Time to acknowledge (MTTR)
    sla_seconds INTEGER,              -- SLA threshold (e.g., 900 for P1)
    sla_status TEXT,                  -- "Pending", "Met", "Breached"
    slack_ts TEXT,                    -- Slack message timestamp
    slack_channel TEXT,               -- Slack channel ID
    finops_team TEXT,                 -- Extracted team from resource name
    finops_owner TEXT,                -- Team email
    finops_cost_center TEXT,          -- Cost center code
    blob_log_url TEXT,                -- Azure Blob URL for raw payload
    itsm_ticket_id TEXT,              -- Jira ticket key (e.g., "PROJ-123")
    logic_app_run_id TEXT,            -- Azure Logic App run ID (if used)
    processing_mode TEXT              -- "direct_webhook", "azure_monitor_alert"
)
```

**Unique Index on `run_id`:**
```sql
CREATE UNIQUE INDEX idx_tickets_run_id ON tickets(run_id)
WHERE run_id IS NOT NULL
```

**Purpose:** Prevents duplicate tickets for the same failure event.

---

**2. `audit_trail` table:**
```sql
CREATE TABLE audit_trail (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    ticket_id TEXT NOT NULL,
    pipeline TEXT,
    run_id TEXT,
    action TEXT NOT NULL,            -- "Ticket Created", "Slack Notification Sent", etc.
    user_name TEXT,
    user_empid TEXT,
    time_taken_seconds INTEGER,
    mttr_minutes REAL,
    sla_status TEXT,
    rca_summary TEXT,
    finops_team TEXT,
    finops_owner TEXT,
    details TEXT,
    itsm_ticket_id TEXT
)
```

**Purpose:** Complete audit trail for compliance, debugging, and analytics.

**Example Audit Entries:**
```
| timestamp           | ticket_id  | action                    | details                    |
|---------------------|------------|---------------------------|----------------------------|
| 2025-11-29 14:30:00 | ADF-001    | Ticket Created            | Severity: High, Priority: P2 |
| 2025-11-29 14:30:02 | ADF-001    | Jira Ticket Created       | Jira ID: PROJ-456          |
| 2025-11-29 14:30:03 | ADF-001    | Slack Notification Sent   | Channel: aiops-rca-alerts  |
| 2025-11-29 14:35:12 | ADF-001    | Duplicate Run Detected    | Ignored duplicate webhook  |
| 2025-11-29 14:40:00 | ADF-001    | Ticket Closed             | User: john@company.com     |
```

---

**3. `users` table:**
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,     -- bcrypt hashed
    full_name TEXT,
    created_at TEXT NOT NULL,
    last_login TEXT
)
```

**Purpose:** User authentication for dashboard access.

**Security:** Passwords hashed with bcrypt, JWT tokens for sessions.

---

#### Authentication System (Lines 300-370)

**Functions:**

**1. `hash_password(password: str)`**
```python
def hash_password(password: str) -> str:
    # Uses bcrypt to hash passwords
    # Truncates to 72 bytes (bcrypt limit)
    return pwd_context.hash(password_truncated)
```

**2. `verify_password(plain_password: str, hashed_password: str)`**
```python
def verify_password(plain_password: str, hashed_password: str) -> bool:
    # Verifies bcrypt hash
    return pwd_context.verify(password_truncated, hashed_password)
```

**3. `create_access_token(data: dict)`**
```python
def create_access_token(data: dict) -> str:
    # Creates JWT token with 24-hour expiration
    to_encode = {"sub": email, "exp": expire_datetime}
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm="HS256")
```

**4. `get_current_user(credentials: HTTPAuthorizationCredentials)`**
```python
async def get_current_user(credentials: HTTPAuthorizationCredentials):
    # Dependency for protected endpoints
    # Decodes JWT token, validates, returns user object
    # Raises 401 if invalid/expired
```

**Flow:**
1. User registers: `/api/register` → Hash password → Store in DB → Return JWT
2. User logs in: `/api/login` → Verify password → Return JWT
3. Protected API calls: Send `Authorization: Bearer <JWT>` → Verify → Allow access

---

#### AI/RCA Generation (Lines 446-558)

**Main Function: `call_ai_for_rca(description: str, source_type: str)`**

```python
def call_ai_for_rca(description: str, source_type: str = "adf"):
    """
    Generate RCA using Google Gemini AI

    Args:
        description: Error message/description
        source_type: "adf" or "databricks" (determines error types list)

    Returns:
        {
            "root_cause": "Clear explanation",
            "error_type": "UserErrorSourceBlobNotExists",
            "affected_entity": "SourceDataset",
            "severity": "High",
            "priority": "P2",
            "confidence": "High",
            "recommendations": ["Step 1", "Step 2", "Step 3"],
            "auto_heal_possible": true
        }
    """
```

**Prompt Engineering:**

The AI prompt includes:
- Service-specific context (ADF vs Databricks)
- Error types list for classification
- Severity/Priority guidelines
- JSON format requirement
- Instructions to be specific and factual

**Example Prompt:**
```
You are an expert AIOps Root Cause Analysis assistant for Azure Data Factory.

Analyze the following Azure Data Factory failure message and provide a precise RCA.

Your `error_type` MUST be one of:
[UserErrorSourceBlobNotExists, GatewayTimeout, ...]

Return STRICT JSON:
{
  "root_cause": "...",
  "error_type": "...",
  "severity": "Critical|High|Medium|Low",
  "priority": "P1|P2|P3|P4",
  "recommendations": ["...", "...", "..."]
}

Severity Guidelines:
- Critical: Production data loss, complete outage
- High: Major functionality broken
- Medium: Partial functionality affected
- Low: Minor issues

Error Message:
"""Source blob '/data/input/file.csv' does not exist"""
```

**Example AI Response:**
```json
{
  "root_cause": "Azure Data Factory pipeline failed because the source blob '/data/input/file.csv' does not exist in the storage account.",
  "error_type": "UserErrorSourceBlobNotExists",
  "affected_entity": "SourceDataset: InputCSV",
  "severity": "High",
  "priority": "P2",
  "confidence": "Very High",
  "recommendations": [
    "Verify the upstream process that creates '/data/input/file.csv' completed successfully",
    "Check if the file path has changed or was renamed",
    "Add a data availability check before running the pipeline",
    "Configure blob storage lifecycle policies to prevent accidental deletion"
  ],
  "auto_heal_possible": false
}
```

**Fallback Handling:**

```python
def fallback_rca(desc: str, source_type: str = "adf"):
    # Used if AI call fails
    return {
        "root_cause": f"Pipeline failed. Unable to determine root cause.",
        "error_type": "UnknownError",
        "severity": "Medium",
        "priority": "P3",
        "confidence": "Low",
        "recommendations": ["Inspect logs for more context."],
        "auto_heal_possible": False
    }
```

---

#### Jira Integration (Lines 560-619)

**Function: `create_jira_ticket(ticket_id, pipeline, rca_data, finops, run_id)`**

```python
def create_jira_ticket(ticket_id: str, pipeline: str, rca_data: dict,
                       finops: dict, run_id: str) -> Optional[str]:
    """
    Create Jira ticket using REST API v3

    Returns: Jira key (e.g., "AIOPS-123") or None if failed
    """
```

**What it does:**
1. Builds Jira-formatted description using Atlassian Document Format (ADF):
   - Headings, panels, code blocks, bullet lists
2. Includes: Root cause, recommendations, ticket details, FinOps tags
3. Makes POST request to `/rest/api/3/issue`
4. Returns Jira ticket key

**Example Jira Ticket Created:**
```
Title: AIOps Alert: DataIngestionPipeline failed - UserErrorSourceBlobNotExists

Description:
═══════════════════════════════════════
AIOps RCA Details
This ticket was auto-generated by the AIOps RCA system for ticket ADF-20251129T143022-a3f2c1.

Root Cause Analysis
Source blob '/data/input/file.csv' does not exist in the storage account.

Recommendations
• Verify the upstream process completed successfully
• Check if the file path has changed
• Add a data availability check before pipeline runs

Ticket Details
{
  "AIOps_Ticket_ID": "ADF-20251129T143022-a3f2c1",
  "Pipeline_Name": "DataIngestionPipeline",
  "ADF_Run_ID": "abc123def456",
  "Severity": "High",
  "Priority": "P2",
  "Error_Type": "UserErrorSourceBlobNotExists",
  "FinOps_Team": "DataEngineering",
  "FinOps_Owner": "dataengineering@company.com",
  "FinOps_Cost_Center": "CC-DATA-001"
}
```

**Jira Webhook (Bi-directional Sync):**

When Jira ticket status changes → Jira sends webhook → `/webhook/jira` endpoint → Updates local ticket status

**Mapping:**
- Jira "Done/Resolved/Closed" → Local "acknowledged"
- Jira "In Progress/Selected for Development" → Local "in_progress"
- Jira "Open/Backlog" → Local "open"

**Code (Lines 1578-1650):**
```python
@app.post("/webhook/jira")
async def webhook_jira(request: Request):
    # Verify webhook secret
    # Extract Jira status change
    # Find matching local ticket by itsm_ticket_id
    # Update local ticket status
    # Broadcast via WebSocket to dashboard
```

---

#### Slack Integration (Lines 643-727)

**Function: `post_slack_notification(ticket_id, essentials, rca, itsm_ticket_id)`**

```python
def post_slack_notification(ticket_id: str, essentials: dict,
                            rca: dict, itsm_ticket_id: str = None):
    """
    Post rich Slack message with Block Kit

    Returns: Slack API response with message timestamp
    """
```

**Slack Message Format (Block Kit):**
```json
{
  "channel": "aiops-rca-alerts",
  "blocks": [
    {
      "type": "header",
      "text": "🚨 ALERT: DataIngestionPipeline - High (P2)"
    },
    {
      "type": "section",
      "text": "Ticket: ADF-001\nITSM Ticket: PROJ-456\nRun ID: abc123\nError Type: UserErrorSourceBlobNotExists"
    },
    {
      "type": "section",
      "text": "Root Cause: Source blob does not exist\nConfidence: High"
    },
    {
      "type": "section",
      "text": "Resolution Steps:\n• Verify upstream process\n• Check file path\n• Add availability check"
    },
    {
      "type": "actions",
      "elements": [
        {
          "type": "button",
          "text": "Open in Dashboard",
          "url": "http://localhost:8000/dashboard",
          "style": "primary"
        }
      ]
    }
  ]
}
```

**Update on Acknowledgment:**

```python
def update_slack_message_on_ack(ticket_id: str, user_name: str):
    # When ticket is closed, update the same Slack message
    # Uses slack_ts and slack_channel stored in DB
    # Changes header to "CLOSED" with timestamp and user
    # Updates message using chat.update API
```

---

#### WebSocket Manager (Lines 625-641, Dashboard real-time updates)

**Purpose:** Real-time updates to dashboard without page refresh.

**Class: `ConnectionManager`**
```python
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        # Send message to all connected clients
        for conn in self.active_connections:
            await conn.send_json(message)
```

**WebSocket Endpoint (Lines 1653-1660):**
```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # Keep connection alive
    except WebSocketDisconnect:
        manager.disconnect(websocket)
```

**Broadcasting Events:**
```python
# When new ticket created:
await manager.broadcast({
    "event": "new_ticket",
    "ticket_id": "ADF-001"
})

# When ticket status updated:
await manager.broadcast({
    "event": "status_update",
    "ticket_id": "ADF-001",
    "new_status": "acknowledged"
})
```

**Dashboard Client (JavaScript):**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws');
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.event === 'new_ticket' || data.event === 'status_update') {
        refreshAll();  // Reload all tickets
    }
};
```

---

### API Endpoints Detailed Explanation

#### 1. `/azure-monitor` (POST) - ADF Alerts

**Purpose:** Receive Azure Monitor alerts for Azure Data Factory failures.

**Called by:** Azure Monitor Action Group webhook

**Flow:**
```
1. Receive webhook payload
2. Extract using AzureDataFactoryExtractor
3. Generate RCA with Gemini AI
4. Check for duplicate (by run_id)
5. If duplicate: Return existing ticket_id
6. If new: Create ticket, send to Jira, send to Slack
7. Upload raw payload to Azure Blob
8. Return ticket details
```

**Deduplication Logic:**
```python
if runid:
    existing = db_query("SELECT id, status FROM tickets WHERE run_id = :run_id",
                       {"run_id": runid}, one=True)
    if existing:
        logger.warning(f"DUPLICATE DETECTED: {runid} → {existing['id']}")
        return JSONResponse({
            "status": "duplicate_ignored",
            "ticket_id": existing["id"]
        })
```

**Why important:** Azure Monitor may send same alert multiple times (e.g., alert resolution, retries). Deduplication prevents ticket spam.

---

#### 2. `/databricks-monitor` (POST) - Databricks Native Webhooks

**Purpose:** Receive webhooks directly from Databricks (Job/Cluster events).

**Called by:** Databricks Workspace webhook configuration

**Flow:**
```
1. Receive webhook (job.run.failed, cluster.terminated, etc.)
2. Extract basic info from webhook
3. If run_id exists: Call Databricks API for detailed error
4. Enrich error message with task-level exceptions
5. Generate RCA with Gemini (source_type="databricks")
6. Check deduplication
7. Create ticket, notifications
```

**API Enrichment:**
```python
if run_id and run_id != "N/A":
    dbx_details = fetch_databricks_run_details(run_id)
    if dbx_details:
        extracted_error = extract_error_message(dbx_details)
        if extracted_error:
            error_message = extracted_error  # Override webhook error
```

**Why important:** Databricks webhooks often have generic errors like "Task failed". API fetch gets actual Python exception traces.

---

#### 3. `/azure-monitor-alert` (POST) - NEW Databricks Cluster Alerts

**Purpose:** Receive Azure Monitor Log Analytics alerts for Databricks cluster failures.

**Called by:** Azure Monitor Action Group webhook (configured on your alert rule)

**Flow:**
```
1. Receive Common Alert Schema webhook
2. Extract from data.alertContext.SearchResults.tables[0].rows
3. Parse columns: ClusterId, ClusterName, TerminationCode, State, LastEvent
4. Create unique run_id: {ClusterId}_{TerminationCode}_{EventTimestamp}
5. Check deduplication with this run_id
6. Generate RCA
7. Create ticket, notifications
8. Can process multiple cluster failures in one alert
```

**Deduplication Example:**
```python
# Cluster terminated at 2025-11-29 04:18:48 UTC
cluster_id = "1121-055905-q5xcz4bm"
termination_code = "USER_REQUEST"
last_event = "2025-11-29T04:18:48Z"

# Convert timestamp
event_timestamp = "20251129041848"

# Create run_id
run_id = f"{cluster_id}_{termination_code}_{event_timestamp}"
# Result: "1121-055905-q5xcz4bm_USER_REQUEST_20251129041848"

# Check database
existing = db_query("SELECT id FROM tickets WHERE run_id = :run_id",
                   {"run_id": run_id}, one=True)
# If exists: return existing ticket
# If not: create new ticket
```

**Why important:** Azure Monitor alerts fire every 5 minutes. Without deduplication, same cluster termination would create tickets every 5 min until alert resolves.

---

#### 4. Protected Endpoints (Require JWT Authentication)

**All require `Authorization: Bearer <JWT>` header**

**GET `/api/open-tickets`**
- Returns all tickets with `status = 'open'`
- Ordered by timestamp DESC

**GET `/api/in-progress-tickets`**
- Returns tickets with `status = 'in_progress'`

**GET `/api/closed-tickets`**
- Returns tickets with `status = 'acknowledged'`
- Ordered by ack_ts DESC

**GET `/api/tickets/{ticket_id}`**
- Returns full details for specific ticket
- Used by dashboard modal

**GET `/api/summary`**
- Returns dashboard statistics:
  ```json
  {
    "total_tickets": 150,
    "open_tickets": 12,
    "acknowledged_tickets": 138,
    "sla_breached": 3,
    "avg_ack_time_sec": 1247,
    "mttr_min": 20.8
  }
  ```

**GET `/api/audit-trail?action=<filter>`**
- Returns audit trail entries
- Optional filter by action type
- Limit 500 rows

**GET `/api/export/open-tickets`**
- Downloads CSV of open tickets
- Filename: `open_tickets_20251129_143022.csv`

---

### Dashboard (dashboard.html) - Complete Explanation

**Technology:** Vanilla JavaScript (no frameworks), HTML5, CSS3

**Why no framework:** Keep it lightweight, no build process, works in any browser.

**Key Features:**
1. Real-time updates via WebSocket
2. Three tabs: Open, In Progress, Closed
3. Search/filter functionality
4. Live SLA countdown timers
5. Audit trail viewer
6. CSV export

---

#### JavaScript Architecture

**Global State:**
```javascript
let openTickets = [];
let inProgressTickets = [];
let closedTickets = [];
let allTickets = [];
let currentTab = 'open';
let authToken = localStorage.getItem('authToken');
let timers = {};  // SLA countdown intervals
```

**Authentication:**
```javascript
function checkAuth() {
    if (!authToken) {
        window.location.href = '/login';
        return false;
    }
    return true;
}

async function fetchWithAuth(url, options = {}) {
    options.headers = options.headers || {};
    options.headers['Authorization'] = `Bearer ${authToken}`;

    const response = await fetch(url, options);
    if (response.status === 401) {
        localStorage.removeItem('authToken');
        window.location.href = '/login';
    }
    return response;
}
```

**Data Fetching:**
```javascript
async function fetchOpen() {
    const res = await fetchWithAuth('/api/open-tickets');
    const data = await res.json();
    openTickets = data.tickets || [];
}

async function refreshAll() {
    await Promise.all([
        fetchOpen(),
        fetchInProgress(),
        fetchClosed()
    ]);
    allTickets = [...openTickets, ...inProgressTickets, ...closedTickets];
    render();
}
```

**Rendering Logic:**
```javascript
function render() {
    const list = currentTab === 'open' ? openTickets :
                 currentTab === 'in_progress' ? inProgressTickets :
                 closedTickets;

    // Sort by priority and severity
    list.sort((a, b) => {
        const priorityA = priorityNumber(a.priority);
        const priorityB = priorityNumber(b.priority);
        if (priorityA !== priorityB) return priorityA - priorityB;
        // Then by severity
    });

    // Filter by search
    const searchInput = document.getElementById('ticket-search').value;
    const filtered = list.filter(t =>
        t.id.includes(searchInput) ||
        t.pipeline.includes(searchInput) ||
        t.rca_result.includes(searchInput)
    );

    // Render cards
    filtered.forEach(ticket => renderTicketCard(ticket));
}
```

**SLA Countdown Timers:**
```javascript
function startTimer(ticket) {
    const created = new Date(ticket.timestamp);
    const sla_seconds = ticket.sla_seconds || 1800;

    function tick() {
        const now = new Date();
        const elapsed = Math.floor((now - created) / 1000);
        const remaining = sla_seconds - elapsed;

        if (remaining > 0) {
            const minutes = Math.floor(remaining / 60);
            const seconds = remaining % 60;
            const color = remaining < 120 ? '#d29922' : '#2ea043';
            el.innerHTML = `<span style="color:${color}">SLA ${minutes}m ${seconds}s left</span>`;
        } else {
            el.innerHTML = `<span style="color:#f85149">SLA Breached</span>`;
        }
    }

    tick();  // Run immediately
    if (ticket.status === 'open') {
        timers[ticket.id] = setInterval(tick, 1000);  // Update every second
    }
}
```

**WebSocket Connection:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('WebSocket received:', data);

    if (data.event === 'new_ticket' || data.event === 'status_update') {
        refreshAll();  // Reload all data
    }
};

ws.onclose = () => {
    console.log('WebSocket disconnected. Retrying...');
    setTimeout(() => location.reload(), 5000);
};
```

**Modal (Ticket Details):**
```javascript
async function openModal(ticket_id) {
    // Fetch full ticket details
    const res = await fetchWithAuth(`/api/tickets/${ticket_id}`);
    const data = await res.json();
    const ticket = data.ticket;

    // Populate modal
    document.getElementById('m-title').innerText = `${ticket.id} - ${ticket.pipeline}`;
    document.getElementById('m-rca').innerText = ticket.rca_result;
    document.getElementById('m-recs').innerText = ticket.recommendations.join('\n');

    // Show Jira link if exists
    if (ticket.itsm_ticket_id) {
        const jiraLink = `${jira_domain}/browse/${ticket.itsm_ticket_id}`;
        document.getElementById('m-itsm-link').innerHTML =
            `<a href="${jiraLink}" target="_blank">View in Jira</a>`;
    }

    // Display modal
    document.getElementById('modal').style.display = 'flex';
}
```

**Audit Trail Viewer:**
```javascript
async function loadAuditTrail() {
    const action = document.getElementById('action-filter').value;
    const url = action === 'all' ? '/api/audit-trail' :
                `/api/audit-trail?action=${action}`;

    const res = await fetchWithAuth(url);
    const data = await res.json();

    // Build table
    let html = '<table class="audit-table"><thead><tr>';
    html += '<th>Timestamp</th><th>Ticket ID</th><th>Action</th>';
    html += '<th>User</th><th>Details</th></tr></thead><tbody>';

    data.audits.forEach(audit => {
        const actionBadge = getActionBadgeClass(audit.action);
        html += `<tr>
            <td>${formatTimestamp(audit.timestamp)}</td>
            <td>${audit.ticket_id}</td>
            <td><span class="action-badge ${actionBadge}">${audit.action}</span></td>
            <td>${audit.user_name || 'System'}</td>
            <td>${audit.details || ''}</td>
        </tr>`;
    });

    html += '</tbody></table>';
    document.getElementById('audit-table-container').innerHTML = html;
}
```

**CSV Export:**
```javascript
async function downloadCurrentTab() {
    const endpoint = currentTab === 'open' ? '/api/export/open-tickets' :
                     currentTab === 'in_progress' ? '/api/export/in-progress-tickets' :
                     '/api/export/closed-tickets';

    const res = await fetchWithAuth(endpoint);
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `tickets_${currentTab}_${Date.now()}.csv`;
    a.click();
}
```

---

## Database Schema Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                        TICKETS                               │
├──────────────────────────────────────────────────────────────┤
│ id (PK)                    TEXT                              │
│ timestamp                  TEXT                              │
│ pipeline                   TEXT                              │
│ run_id (UNIQUE INDEX)      TEXT      ← Deduplication key    │
│ rca_result                 TEXT                              │
│ recommendations            TEXT (JSON array)                 │
│ severity                   TEXT      ← Critical/High/Med/Low │
│ priority                   TEXT      ← P1/P2/P3/P4          │
│ error_type                 TEXT                              │
│ status                     TEXT      ← open/in_progress/ack │
│ sla_seconds                INTEGER                           │
│ sla_status                 TEXT                              │
│ itsm_ticket_id            TEXT       ← Jira key             │
│ finops_team                TEXT                              │
│ slack_ts                   TEXT                              │
└──────────────────────────────────────────────────────────────┘
                              │
                              │ 1:N relationship
                              ↓
┌──────────────────────────────────────────────────────────────┐
│                      AUDIT_TRAIL                             │
├──────────────────────────────────────────────────────────────┤
│ id (PK AUTO)               INTEGER                           │
│ timestamp                  TEXT                              │
│ ticket_id (FK)             TEXT      → tickets.id            │
│ action                     TEXT                              │
│ user_name                  TEXT                              │
│ time_taken_seconds         INTEGER                           │
│ mttr_minutes               REAL                              │
│ details                    TEXT                              │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                         USERS                                │
├──────────────────────────────────────────────────────────────┤
│ id (PK AUTO)               INTEGER                           │
│ email (UNIQUE)             TEXT                              │
│ password_hash              TEXT      ← bcrypt hashed         │
│ full_name                  TEXT                              │
│ created_at                 TEXT                              │
│ last_login                 TEXT                              │
└──────────────────────────────────────────────────────────────┘
```

---

## Complete Workflow Diagrams

### Workflow 1: ADF Pipeline Failure → Ticket Creation

```
1. Azure Data Factory Pipeline Fails
   ↓
2. Azure Monitor Alert Rule Triggers
   (Condition: PipelineRunStatus == "Failed")
   ↓
3. Action Group Sends Webhook
   POST /azure-monitor
   {
     "data": {
       "essentials": {...},
       "alertContext": {
         "condition": {
           "allOf": [{
             "dimensions": [
               {"name": "PipelineName", "value": "ETL_Pipeline"},
               {"name": "PipelineRunId", "value": "abc123"},
               {"name": "ErrorMessage", "value": "Blob not found"}
             ]
           }]
         }
       }
     }
   }
   ↓
4. FastAPI Endpoint: /azure-monitor
   ├─ AzureDataFactoryExtractor.extract(payload)
   │  └─ Returns: ("ETL_Pipeline", "abc123", "Blob not found", metadata)
   ↓
5. Deduplication Check
   SELECT id FROM tickets WHERE run_id = 'abc123'
   ├─ If exists: Return duplicate_ignored
   └─ If not exists: Continue
   ↓
6. AI RCA Generation
   call_ai_for_rca("Blob not found", source_type="adf")
   ├─ Gemini API Call
   └─ Returns: {
       "root_cause": "Source blob doesn't exist",
       "error_type": "UserErrorSourceBlobNotExists",
       "severity": "High",
       "priority": "P2",
       "recommendations": [...]
     }
   ↓
7. Create Ticket in Database
   INSERT INTO tickets (id, pipeline, run_id, rca_result, ...)
   VALUES ('ADF-001', 'ETL_Pipeline', 'abc123', 'Source blob...', ...)
   ↓
8. Audit Log
   INSERT INTO audit_trail (ticket_id, action, details)
   VALUES ('ADF-001', 'Ticket Created', 'Severity: High...')
   ↓
9. Parallel Actions:
   ├─ Create Jira Ticket
   │  POST /rest/api/3/issue
   │  Returns: "PROJ-456"
   │  UPDATE tickets SET itsm_ticket_id = 'PROJ-456'
   │
   ├─ Send Slack Notification
   │  POST /api/chat.postMessage
   │  Store slack_ts for future updates
   │
   └─ Upload Payload to Blob
      Azure Blob Storage: 2025-11-29/ADF-001-payload.json
   ↓
10. WebSocket Broadcast
    manager.broadcast({"event": "new_ticket", "ticket_id": "ADF-001"})
    ├─ All connected dashboards receive event
    └─ Dashboards auto-refresh and show new ticket
    ↓
11. Return Response
    {
      "status": "success",
      "ticket_id": "ADF-001",
      "severity": "High",
      "itsm_ticket_id": "PROJ-456"
    }
```

---

### Workflow 2: Databricks Job Failure with API Enrichment

```
1. Databricks Job Fails
   ↓
2. Databricks Webhook Fires
   POST /databricks-monitor
   {
     "event": "job.run.failed",
     "run": {
       "run_id": 12345,
       "state": {
         "state_message": "Task failed"  ← Generic error
       }
     }
   }
   ↓
3. FastAPI: /databricks-monitor
   ├─ Extract from webhook: run_id = 12345
   ↓
4. API Enrichment (databricks_api_utils.py)
   fetch_databricks_run_details(12345)
   ├─ GET /api/2.1/jobs/runs/get?run_id=12345
   ├─ Returns full run details with tasks
   │
   ├─ For each failed task:
   │  └─ fetch_task_output(task_run_id)
   │     GET /api/2.1/jobs/runs/get-output?run_id=67890
   │     Returns: {
   │       "error": "FileNotFoundError: '/data/input.csv' not found",
   │       "error_trace": "Traceback (most recent call last)..."
   │     }
   │
   └─ extract_error_message(run_data)
      Returns: "[Task: validation] FileNotFoundError: '/data/input.csv'"
   ↓
5. AI RCA with Detailed Error
   call_ai_for_rca(
     "[Task: validation] FileNotFoundError: '/data/input.csv'",
     source_type="databricks"
   )
   └─ Much better RCA because of detailed error
   ↓
6. Same flow as ADF:
   Deduplication → Create Ticket → Jira → Slack → WebSocket
```

---

### Workflow 3: Databricks Cluster Termination → Azure Monitor Alert

```
1. User Terminates Databricks Cluster
   OR Cluster Auto-Terminates with Error
   ↓
2. Event Logged to Log Analytics
   (Databricks diagnostic logs → Log Analytics workspace)
   Table: DatabricksClusters
   Row: {
     ClusterId: "1121-055905-q5xcz4bm",
     ClusterName: "Production Cluster",
     TerminationCode: "DRIVER_NOT_RESPONDING",
     State: "TERMINATED",
     TimeGenerated: "2025-11-29T14:30:00Z"
   }
   ↓
3. Alert Rule Checks Every 5 Minutes
   KQL Query:
   DatabricksClusters
   | where TerminationCode !in ("INACTIVITY", "SUCCESS")
   | where TimeGenerated > ago(30m)

   ├─ If results found: Fire alert
   └─ If no results: Do nothing
   ↓
4. Action Group Webhook Triggered
   POST /azure-monitor-alert
   {
     "data": {
       "essentials": {
         "alertRule": "databricks-alert",
         "alertId": "alert-001"
       },
       "alertContext": {
         "SearchResults": {
           "tables": [{
             "columns": ["ClusterId", "ClusterName", "TerminationCode", ...],
             "rows": [
               ["1121-055905-q5xcz4bm", "Production Cluster", "DRIVER_NOT_RESPONDING", ...]
             ]
           }]
         }
       }
     }
   }
   ↓
5. FastAPI: /azure-monitor-alert
   ├─ Parse SearchResults table
   ├─ Extract row data:
   │  cluster_id = "1121-055905-q5xcz4bm"
   │  termination_code = "DRIVER_NOT_RESPONDING"
   │  last_event = "2025-11-29T14:30:00Z"
   │
   ├─ Create unique run_id:
   │  event_timestamp = "20251129143000"
   │  run_id = f"{cluster_id}_{termination_code}_{event_timestamp}"
   │  → "1121-055905-q5xcz4bm_DRIVER_NOT_RESPONDING_20251129143000"
   ↓
6. Deduplication Check
   SELECT * FROM tickets WHERE run_id = '1121-055905-q5xcz4bm_DRIVER_NOT_RESPONDING_20251129143000'

   ├─ If exists:
   │  └─ Return {"status": "duplicate_ignored", "ticket_id": "DBX-ALERT-001"}
   │     ↑ This prevents duplicate tickets when alert fires again in 5 min
   │
   └─ If not exists: Continue to create ticket
   ↓
7. Build Error Description
   """
   Databricks Cluster Failure Detected via Azure Monitor Alert

   Cluster Name: Production Cluster
   Cluster ID: 1121-055905-q5xcz4bm
   Termination Code: DRIVER_NOT_RESPONDING
   State: TERMINATED
   Last Event: 2025-11-29T14:30:00Z

   This cluster was terminated with code 'DRIVER_NOT_RESPONDING'
   which indicates a failure condition.
   """
   ↓
8. AI RCA Generation
   call_ai_for_rca(error_description, source_type="databricks")
   └─ Returns RCA specific to driver not responding
   ↓
9. Same completion flow:
   Create Ticket → Jira → Slack → WebSocket → Return
```

---

This completes Part 1 of the comprehensive documentation. Would you like me to continue with:
- Part 2: Interview Q&A
- Part 3: Before/After Comparison
- Part 4: Reading Order Guide?
