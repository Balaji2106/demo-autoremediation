# 🔍 Complete Function Reference Guide - Every Function Explained

## Table of Contents

1. [main.py Functions (45 functions)](#mainpy-functions)
2. [error_extractors.py Functions (9 functions)](#error_extractorspy-functions)
3. [databricks_api_utils.py Functions (5 functions)](#databricks_api_utilspy-functions)

---

# main.py Functions

## Database & Infrastructure Functions

### 1. `build_azure_sqlalchemy_url()` (Line 111)

**What it does:** Constructs SQLAlchemy connection URL for Azure SQL Database

**Why it exists:** Azure SQL connection strings need special formatting (ODBC driver, URL encoding)

**Parameters:** None (uses environment variables)

**Returns:** `str` - SQLAlchemy connection URL

**Where it's called:** Line 134 in `get_engine_with_retry()`

**Example:**
```python
url = build_azure_sqlalchemy_url()
# Returns: "mssql+pyodbc://user:pass@server.database.windows.net/db?driver=ODBC+Driver+18+for+SQL+Server"
```

---

### 2. `get_engine_with_retry(retries=3, backoff=3)` (Line 130)

**What it does:** Creates database engine with retry logic for connection failures

**Why it exists:** Database connections can fail temporarily (network issues, Azure throttling)

**Parameters:**
- `retries` (int): Number of retry attempts (default: 3)
- `backoff` (int): Seconds to wait between retries (default: 3)

**Returns:** `sqlalchemy.Engine` object

**Where it's called:** Line 150 in `init_db()`

**Example:**
```python
engine = get_engine_with_retry(retries=5, backoff=2)
# Tries to connect, if fails, waits 2 sec and retries up to 5 times
```

---

### 3. `init_db()` (Line 150)

**What it does:** Creates database tables (tickets, audit_trail, users) if they don't exist

**Why it exists:** Sets up database schema on first run

**Parameters:** None

**Returns:** None

**Where it's called:** Line 1915 (when app starts)

**Creates 3 tables:**
1. **tickets** - Main ticket data with unique index on run_id
2. **audit_trail** - Complete log of all actions
3. **users** - User authentication data

**Example:**
```python
init_db()
# Creates tables if missing
# Adds unique index: CREATE UNIQUE INDEX idx_tickets_run_id ON tickets(run_id) WHERE run_id IS NOT NULL
```

---

### 4. `db_execute(q, params=None)` (Line 288)

**What it does:** Executes SQL queries that modify data (INSERT, UPDATE, DELETE)

**Why it exists:** Centralized database execution with connection handling

**Parameters:**
- `q` (str): SQL query with placeholders
- `params` (dict): Parameter values (optional)

**Returns:** None

**Where it's called:** Throughout main.py (90+ times)

**Example:**
```python
db_execute(
    "INSERT INTO tickets (id, pipeline, run_id) VALUES (:id, :pipeline, :run_id)",
    {"id": "ADF-001", "pipeline": "ETLPipeline", "run_id": "abc123"}
)
```

---

### 5. `db_query(q, params=None, one=False)` (Line 293)

**What it does:** Executes SQL SELECT queries and returns results

**Why it exists:** Centralized data retrieval with connection handling

**Parameters:**
- `q` (str): SQL SELECT query
- `params` (dict): Parameter values (optional)
- `one` (bool): If True, return single row instead of list

**Returns:** `list[dict]` or `dict` (if one=True) or `None`

**Where it's called:** Throughout main.py (50+ times)

**Example:**
```python
# Get all open tickets
tickets = db_query("SELECT * FROM tickets WHERE status = 'open'")

# Get specific ticket
ticket = db_query("SELECT * FROM tickets WHERE id = :id", {"id": "ADF-001"}, one=True)
```

---

## Authentication Functions

### 6. `hash_password(password)` (Line 301)

**What it does:** Hashes password using bcrypt

**Why it exists:** Never store plain text passwords (security)

**Parameters:**
- `password` (str): Plain text password

**Returns:** `str` - Bcrypt hash

**Where it's called:** Line 797 in `register()` endpoint

**Example:**
```python
hashed = hash_password("mypassword123")
# Returns: "$2b$12$KIX...hashed_value"
```

---

### 7. `verify_password(plain_password, hashed_password)` (Line 306)

**What it does:** Verifies password against bcrypt hash

**Why it exists:** Check login credentials securely

**Parameters:**
- `plain_password` (str): User's input
- `hashed_password` (str): Hash from database

**Returns:** `bool` - True if match, False otherwise

**Where it's called:** Line 815 in `login()` endpoint

**Example:**
```python
is_valid = verify_password("mypassword123", "$2b$12$KIX...")
# Returns: True or False
```

---

### 8. `create_access_token(data)` (Line 311)

**What it does:** Creates JWT token with 24-hour expiration

**Why it exists:** Stateless authentication for API and dashboard

**Parameters:**
- `data` (dict): Payload to encode (usually {"sub": email})

**Returns:** `str` - JWT token

**Where it's called:** Lines 802, 820 (after register/login)

**Example:**
```python
token = create_access_token({"sub": "user@example.com"})
# Returns: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

---

### 9. `decode_access_token(token)` (Line 318)

**What it does:** Decodes and validates JWT token

**Why it exists:** Verify user identity on protected endpoints

**Parameters:**
- `token` (str): JWT token from Authorization header

**Returns:** `dict` - Decoded payload or `None` if invalid/expired

**Where it's called:** Line 367 in `get_current_user()`

**Example:**
```python
payload = decode_access_token("eyJhbGciOi...")
# Returns: {"sub": "user@example.com", "exp": 1234567890}
# or None if expired/invalid
```

---

### 10. `get_current_user(credentials)` (Line 356)

**What it does:** FastAPI dependency to get authenticated user from JWT

**Why it exists:** Protect endpoints requiring authentication

**Parameters:**
- `credentials` (HTTPAuthorizationCredentials): Auto-injected by FastAPI

**Returns:** `dict` - User object from database

**Where it's called:** All protected endpoints as `Depends(get_current_user)`

**Example:**
```python
@app.get("/api/tickets")
async def get_tickets(current_user: dict = Depends(get_current_user)):
    # current_user = {"id": 1, "email": "user@example.com", ...}
    return tickets
```

---

## Audit & Logging Functions

### 11. `log_audit(ticket_id, action, pipeline=None, run_id=None, ...)` (Line 373)

**What it does:** Logs all actions to audit_trail table for compliance

**Why it exists:** Track who did what, when (SOC2, ISO27001 compliance)

**Parameters:**
- `ticket_id` (str): Ticket ID
- `action` (str): Action name ("Ticket Created", "Jira Ticket Created", etc.)
- `pipeline` (str): Pipeline name (optional)
- `run_id` (str): Run ID (optional)
- `user_name` (str): User who performed action (optional)
- `user_empid` (str): Employee ID (optional)
- `time_taken_seconds` (int): Time taken (optional)
- `mttr_minutes` (float): MTTR (optional)
- `sla_status` (str): SLA status (optional)
- `rca_summary` (str): RCA summary (optional)
- `finops_team` (str): FinOps team (optional)
- `finops_owner` (str): FinOps owner (optional)
- `details` (str): Additional details (optional)
- `itsm_ticket_id` (str): Jira ticket ID (optional)

**Returns:** None

**Where it's called:** Throughout main.py (40+ times)

**Example:**
```python
log_audit(
    ticket_id="ADF-001",
    action="Ticket Created",
    pipeline="ETLPipeline",
    run_id="abc123",
    rca_summary="Source blob not found",
    sla_status="Pending",
    details="Severity: High, Priority: P2"
)
```

---

### 12. `upload_payload_to_blob(ticket_id, payload)` (Line 401)

**What it does:** Uploads raw webhook payload to Azure Blob Storage for audit

**Why it exists:** Preserve original data for investigations, compliance

**Parameters:**
- `ticket_id` (str): Ticket ID
- `payload` (dict): Raw webhook JSON

**Returns:** `str` - Blob URL or `None` if disabled/failed

**Where it's called:** Lines 991, 1259, 1488 (in webhook endpoints)

**Example:**
```python
url = upload_payload_to_blob("ADF-001", {"data": {...}})
# Returns: "https://storage.blob.core.windows.net/audit-logs/2025-11-29/ADF-001-payload.json"
```

---

## FinOps Functions

### 13. `extract_finops_tags(resource_name, resource_type="adf")` (Line 420)

**What it does:** Extracts team, owner, cost-center from resource names using regex

**Why it exists:** Auto-populate FinOps fields for chargeback/showback

**Parameters:**
- `resource_name` (str): Pipeline/Job/Cluster name
- `resource_type` (str): "adf" or "databricks"

**Returns:** `dict` - {"team": str, "owner": str, "cost_center": str}

**Where it's called:** Lines 972, 1240, 1471 (in webhook endpoints)

**Regex Patterns:**
```python
# Matches: "DataEng_ETLPipeline" → team="DataEng"
# Matches: "owner-john.doe@company.com" → owner="john.doe@company.com"
# Matches: "cc-IT-12345" → cost_center="IT-12345"
```

**Example:**
```python
tags = extract_finops_tags("DataEng_ETLPipeline_owner-john@company.com_cc-IT-001", "adf")
# Returns: {
#     "team": "DataEng",
#     "owner": "john@company.com",
#     "cost_center": "IT-001"
# }
```

---

## AI/RCA Functions

### 14. `call_ai_for_rca(description, source_type="adf")` (Line 455)

**What it does:** Calls Google Gemini AI to generate root cause analysis

**Why it exists:** AI analyzes errors faster and more consistently than humans

**Parameters:**
- `description` (str): Error message/description
- `source_type` (str): "adf" or "databricks" (determines error types list)

**Returns:** `dict` - RCA with root_cause, severity, priority, recommendations, etc.

**Where it's called:** Line 557 in `generate_rca_and_recs()`

**Prompt includes:**
- Service-specific context
- Known error types list
- Severity/Priority guidelines
- JSON format requirement

**Example:**
```python
rca = call_ai_for_rca(
    "Source blob '/data/input.csv' does not exist",
    source_type="adf"
)
# Returns: {
#     "root_cause": "Source blob not found...",
#     "error_type": "UserErrorSourceBlobNotExists",
#     "severity": "High",
#     "priority": "P2",
#     "confidence": "Very High",
#     "recommendations": ["Verify upstream process...", ...]
# }
```

---

### 15. `derive_priority(sev)` (Line 530)

**What it does:** Maps severity to priority (Critical→P1, High→P2, Medium→P3, Low→P4)

**Why it exists:** Consistent priority assignment

**Parameters:**
- `sev` (str): Severity level

**Returns:** `str` - Priority (P1-P4)

**Where it's called:** Lines 558, 980, 1248, 1477

**Example:**
```python
priority = derive_priority("Critical")  # Returns: "P1"
priority = derive_priority("High")      # Returns: "P2"
priority = derive_priority("Medium")    # Returns: "P3"
```

---

### 16. `sla_for_priority(p)` (Line 534)

**What it does:** Maps priority to SLA seconds (P1=900, P2=1800, P3=7200, P4=86400)

**Why it exists:** Enforce SLA based on priority

**Parameters:**
- `p` (str): Priority

**Returns:** `int` - SLA in seconds

**Where it's called:** Lines 981, 1249, 1478

**Example:**
```python
sla = sla_for_priority("P1")  # Returns: 900 (15 minutes)
sla = sla_for_priority("P2")  # Returns: 1800 (30 minutes)
```

---

### 17. `fallback_rca(desc, source_type="adf")` (Line 537)

**What it does:** Returns generic RCA when AI fails

**Why it exists:** Always return something even if AI errors

**Parameters:**
- `desc` (str): Error description
- `source_type` (str): Service type

**Returns:** `dict` - Generic RCA

**Where it's called:** Line 559 in `generate_rca_and_recs()` (exception handler)

**Example:**
```python
rca = fallback_rca("Some error", "adf")
# Returns: {
#     "root_cause": "Pipeline failed. Unable to determine root cause.",
#     "error_type": "UnknownError",
#     "severity": "Medium",
#     "priority": "P3",
#     "recommendations": ["Check logs manually..."]
# }
```

---

### 18. `generate_rca_and_recs(desc, source_type="adf")` (Line 551)

**What it does:** Wrapper around `call_ai_for_rca()` with exception handling

**Why it exists:** Safe AI call with fallback

**Parameters:**
- `desc` (str): Error description
- `source_type` (str): Service type

**Returns:** `dict` - RCA from AI or fallback

**Where it's called:** Lines 978, 1246, 1474 (in webhook endpoints)

**Example:**
```python
rca = generate_rca_and_recs("Blob not found", "adf")
# Calls AI, if fails, returns fallback
```

---

## ITSM/Jira Functions

### 19. `_get_jira_auth()` (Line 561)

**What it does:** Creates HTTPBasicAuth object for Jira API

**Why it exists:** Centralize Jira authentication

**Parameters:** None (uses env vars)

**Returns:** `HTTPBasicAuth` or `None` if not configured

**Where it's called:** Lines 572, 690 (Jira API calls)

**Example:**
```python
auth = _get_jira_auth()
# Returns: HTTPBasicAuth("user@example.com", "api_token")
```

---

### 20. `create_jira_ticket(ticket_id, pipeline, rca_data, finops, run_id)` (Line 567)

**What it does:** Creates Jira ticket using REST API v3

**Why it exists:** Auto-create ITSM tickets for tracking

**Parameters:**
- `ticket_id` (str): Our ticket ID
- `pipeline` (str): Pipeline/Job name
- `rca_data` (dict): RCA from AI
- `finops` (dict): FinOps tags
- `run_id` (str): Run ID

**Returns:** `str` - Jira key (e.g., "AIOPS-456") or `None` if failed

**Where it's called:** Lines 1006, 1274, 1547 (in webhook endpoints)

**Creates Jira ticket with:**
- Summary: "AIOps Alert: {pipeline} failed - {error_type}"
- Description: Formatted with Atlassian Document Format (panels, headings, code blocks)
- Priority: Mapped from our priority
- Labels: ["aiops", "auto-generated"]

**Example:**
```python
jira_key = create_jira_ticket(
    "ADF-001",
    "ETLPipeline",
    {"root_cause": "Blob not found", "error_type": "UserErrorSourceBlobNotExists", ...},
    {"team": "DataEng", "owner": "john@company.com"},
    "abc123"
)
# Returns: "AIOPS-456"
```

---

## Slack Functions

### 21. `post_slack_notification(ticket_id, essentials, rca, itsm_ticket_id=None)` (Line 644)

**What it does:** Posts rich Slack message using Block Kit

**Why it exists:** Real-time notifications to team

**Parameters:**
- `ticket_id` (str): Our ticket ID
- `essentials` (dict): Alert metadata (alertRule, runId, pipelineName)
- `rca` (dict): RCA from AI
- `itsm_ticket_id` (str): Jira key (optional)

**Returns:** `dict` - Slack API response with timestamp or `None` if failed

**Where it's called:** Lines 1030, 1298, 1570 (in webhook endpoints)

**Slack message includes:**
- Header with severity/priority
- Ticket ID and ITSM link
- Root cause
- Recommendations
- Dashboard button link

**Example:**
```python
slack_resp = post_slack_notification(
    "ADF-001",
    {"alertRule": "ETLPipeline", "runId": "abc123"},
    {"root_cause": "Blob not found", "severity": "High", "recommendations": [...]},
    "AIOPS-456"
)
# Posts to Slack, returns: {"ts": "1732435216.123456", "channel": "C01234"}
```

---

### 22. `update_slack_message_on_ack(ticket_id, user_name)` (Line 687)

**What it does:** Updates Slack message when ticket is closed

**Why it exists:** Keep team informed of resolution

**Parameters:**
- `ticket_id` (str): Our ticket ID
- `user_name` (str): Who closed it

**Returns:** `dict` - Slack API response or `None`

**Where it's called:** Line 765 in `perform_close_from_jira()`

**Updates message to show:**
- ✅ CLOSED status
- Who closed it
- When it was closed
- MTTR

**Example:**
```python
update_slack_message_on_ack("ADF-001", "John Doe")
# Updates Slack message header to: "✅ ETLPipeline - CLOSED by John Doe at 14:30"
```

---

## Helper Functions

### 23. `_http_post_with_retries(url, payload, timeout=60, retries=3, backoff=1.5)` (Line 730)

**What it does:** Makes HTTP POST request with exponential backoff retry

**Why it exists:** Handle transient network failures

**Parameters:**
- `url` (str): API endpoint
- `payload` (dict): JSON body
- `timeout` (int): Request timeout (seconds)
- `retries` (int): Number of retries
- `backoff` (float): Backoff multiplier

**Returns:** `requests.Response` object or raises exception

**Where it's called:** Not currently used (was for auto-remediation playbooks)

**Example:**
```python
response = _http_post_with_retries(
    "https://api.example.com/endpoint",
    {"key": "value"},
    timeout=30,
    retries=5,
    backoff=2.0
)
# Tries POST, if fails, waits 2s, 4s, 8s, 16s, 32s between retries
```

---

### 24. `perform_close_from_jira(ticket_id, row, user_name, user_empid, details)` (Line 746)

**What it does:** Closes ticket when Jira status changes to Done

**Why it exists:** Bi-directional sync with Jira

**Parameters:**
- `ticket_id` (str): Our ticket ID
- `row` (dict): Ticket data from database
- `user_name` (str): Jira user
- `user_empid` (str): Employee ID
- `details` (str): Status change details

**Returns:** None

**Where it's called:** Line 1877 in `/webhook/jira` endpoint

**Actions:**
1. Calculates MTTR (time from creation to closure)
2. Updates ticket to "acknowledged" status
3. Updates Slack message to show closed
4. Logs audit trail
5. Broadcasts WebSocket event

**Example:**
```python
await perform_close_from_jira(
    "ADF-001",
    {"timestamp": "2025-11-29T14:00:00Z", ...},
    "John Doe",
    "EMP-789",
    "Status changed to 'Done' in Jira"
)
# Closes ticket, calculates MTTR, updates Slack, broadcasts to dashboard
```

---

## API Endpoints - Authentication

### 25. `register(user: UserRegister)` (Line 778)

**What it does:** POST /api/register - Creates new user account

**Why it exists:** User registration for dashboard access

**Parameters:**
- `user` (UserRegister): Pydantic model with email, password, full_name

**Returns:** `dict` - {"message": "...", "token": "...", "user": {...}}

**Called by:** Dashboard registration page (register.html)

**Example:**
```python
# POST /api/register
# Body: {"email": "user@example.com", "password": "secret123", "full_name": "John Doe"}
# Returns: {"message": "User created", "token": "eyJhbG...", "user": {...}}
```

---

### 26. `login(user: UserLogin)` (Line 806)

**What it does:** POST /api/login - Authenticates user and returns JWT

**Why it exists:** Dashboard login

**Parameters:**
- `user` (UserLogin): Pydantic model with email, password

**Returns:** `dict` - {"message": "...", "token": "...", "user": {...}}

**Called by:** Dashboard login page (login.html)

**Example:**
```python
# POST /api/login
# Body: {"email": "user@example.com", "password": "secret123"}
# Returns: {"message": "Login successful", "token": "eyJhbG...", "user": {...}}
```

---

### 27. `get_current_user_info(current_user)` (Line 823)

**What it does:** GET /api/me - Returns current authenticated user info

**Why it exists:** Dashboard displays logged-in user email

**Parameters:**
- `current_user` (dict): Auto-injected from JWT

**Returns:** `dict` - User object

**Called by:** Dashboard JavaScript (dashboard.html:252)

**Example:**
```python
# GET /api/me
# Headers: Authorization: Bearer eyJhbG...
# Returns: {"id": 1, "email": "user@example.com", "full_name": "John Doe"}
```

---

## API Endpoints - Public

### 28. `root()` (Line 833)

**What it does:** GET / - Redirects to /login

**Why it exists:** Entry point

**Returns:** RedirectResponse to /login

**Example:**
```python
# GET http://localhost:8000/
# → Redirects to http://localhost:8000/login
```

---

### 29. `login_page()` (Line 839)

**What it does:** GET /login - Serves login.html

**Why it exists:** User login UI

**Returns:** HTMLResponse with login.html content

**Example:**
```python
# GET http://localhost:8000/login
# → Returns login.html page
```

---

### 30. `check_ticket_exists(run_id, x_api_key)` (Line 848)

**What it does:** GET /check-ticket/{run_id} - Checks if ticket exists for run_id

**Why it exists:** Deduplication check before sending webhook

**Parameters:**
- `run_id` (str): Run ID to check
- `x_api_key` (str): API key from header

**Returns:** `dict` - {"exists": bool, "ticket_id": str or None}

**Called by:** External systems before sending webhooks

**Example:**
```python
# GET /check-ticket/abc123
# Headers: X-Api-Key: balaji-rca-secret-2025
# Returns: {"exists": true, "ticket_id": "ADF-001"} or {"exists": false, "ticket_id": null}
```

---

## API Endpoints - Webhook Receivers

### 31. `azure_monitor(request)` (Line 875)

**What it does:** POST /azure-monitor - Receives Azure Monitor alerts for ADF

**Why it exists:** Main webhook endpoint for ADF pipeline failures

**Parameters:**
- `request` (Request): FastAPI request object

**Returns:** JSONResponse with ticket details

**Called by:** Azure Monitor Action Group webhook

**Workflow:**
1. Parse webhook JSON (Azure Monitor Common Alert Schema)
2. Extract using AzureDataFactoryExtractor
3. Check deduplication by run_id
4. Generate AI RCA
5. Create ticket in database
6. Create Jira ticket
7. Send Slack notification
8. Upload payload to Blob
9. Broadcast WebSocket event
10. Return ticket details

**Example:**
```python
# POST /azure-monitor
# Body: {Azure Monitor Common Alert Schema}
# Returns: {
#     "status": "success",
#     "ticket_id": "ADF-001",
#     "severity": "High",
#     "itsm_ticket_id": "AIOPS-456"
# }
```

---

### 32. `databricks_monitor(request)` (Line 1076)

**What it does:** POST /databricks-monitor - Receives Databricks native webhooks

**Why it exists:** Webhook endpoint for Databricks job/cluster failures

**Parameters:**
- `request` (Request): FastAPI request object

**Returns:** JSONResponse with ticket details

**Called by:** Databricks Workspace webhook configuration

**Workflow:**
1. Parse Databricks webhook JSON
2. Extract using DatabricksExtractor
3. **Enrich with Databricks API** (fetch detailed error)
4. Check deduplication by run_id
5. Generate AI RCA
6. Create ticket, Jira, Slack (same as ADF)

**Key difference from azure_monitor:** Calls `fetch_databricks_run_details()` to get detailed stack traces

**Example:**
```python
# POST /databricks-monitor
# Body: {Databricks webhook format}
# Returns: {
#     "status": "success",
#     "ticket_id": "DBX-001",
#     "run_id": "12345",
#     "job_name": "ETL_Job"
# }
```

---

### 33. `azure_monitor_alert(request)` (Line 1332)

**What it does:** POST /azure-monitor-alert - Receives Azure Monitor alerts for Databricks clusters

**Why it exists:** NEW endpoint for cluster failures via Log Analytics

**Parameters:**
- `request` (Request): FastAPI request object

**Returns:** JSONResponse with ticket details

**Called by:** Azure Monitor Action Group webhook (configured on alert rule)

**Workflow:**
1. Parse Azure Monitor Common Alert Schema
2. Extract from SearchResults table (not dimensions)
3. Parse columns: ClusterId, ClusterName, TerminationCode, State, LastEvent
4. Create composite run_id: `{ClusterId}_{TerminationCode}_{EventTimestamp}`
5. Check deduplication
6. Generate AI RCA
7. Create ticket, Jira, Slack
8. Can process **multiple cluster failures** in single alert

**Key difference:** Composite deduplication key prevents duplicate tickets for same cluster termination

**Example:**
```python
# POST /azure-monitor-alert
# Body: {Azure Monitor Alert with SearchResults}
# Returns: {
#     "status": "success",
#     "alert_rule": "databricks-alert",
#     "total_failures": 1,
#     "tickets_created": 1,
#     "tickets": [{
#         "status": "success",
#         "ticket_id": "DBX-ALERT-001",
#         "cluster_id": "1121-055905-q5xcz4bm",
#         "termination_code": "DRIVER_NOT_RESPONDING"
#     }]
# }
```

---

## API Endpoints - Protected (Require JWT)

### 34. `_get_ticket_columns()` (Line 1614)

**What it does:** Helper function to get ticket column list for SELECT queries

**Why it exists:** DRY (Don't Repeat Yourself) - used in multiple endpoints

**Returns:** `str` - Comma-separated column names

**Where it's called:** Lines 1627, 1639, 1651, 1663

**Example:**
```python
cols = _get_ticket_columns()
# Returns: "id, timestamp, pipeline, run_id, rca_result, recommendations, ..."
```

---

### 35. `get_ticket_details(ticket_id, current_user)` (Line 1621)

**What it does:** GET /api/tickets/{ticket_id} - Get full ticket details

**Why it exists:** Dashboard modal view

**Parameters:**
- `ticket_id` (str): Ticket ID
- `current_user` (dict): From JWT

**Returns:** `dict` - {"ticket": {...}}

**Called by:** Dashboard JavaScript (dashboard.html:430)

**Example:**
```python
# GET /api/tickets/ADF-001
# Headers: Authorization: Bearer eyJhbG...
# Returns: {"ticket": {"id": "ADF-001", "pipeline": "ETL", ...}}
```

---

### 36. `api_open_tickets(current_user)` (Line 1634)

**What it does:** GET /api/open-tickets - Get all open tickets

**Why it exists:** Dashboard "Open" tab

**Parameters:**
- `current_user` (dict): From JWT

**Returns:** `dict` - {"tickets": [...]}

**Called by:** Dashboard JavaScript (dashboard.html:279)

**Example:**
```python
# GET /api/open-tickets
# Returns: {"tickets": [{"id": "ADF-001", "status": "open", ...}, ...]}
```

---

### 37. `api_in_progress_tickets(current_user)` (Line 1646)

**What it does:** GET /api/in-progress-tickets - Get all in-progress tickets

**Why it exists:** Dashboard "In Progress" tab

**Parameters:**
- `current_user` (dict): From JWT

**Returns:** `dict` - {"tickets": [...]}

**Called by:** Dashboard JavaScript (dashboard.html:293)

**Example:**
```python
# GET /api/in-progress-tickets
# Returns: {"tickets": [{"id": "ADF-002", "status": "in_progress", ...}, ...]}
```

---

### 38. `api_closed_tickets(current_user)` (Line 1658)

**What it does:** GET /api/closed-tickets - Get all acknowledged (closed) tickets

**Why it exists:** Dashboard "Closed" tab

**Parameters:**
- `current_user` (dict): From JWT

**Returns:** `dict` - {"tickets": [...]}

**Called by:** Dashboard JavaScript (dashboard.html:306)

**Example:**
```python
# GET /api/closed-tickets
# Returns: {"tickets": [{"id": "ADF-003", "status": "acknowledged", "ack_user": "John", ...}, ...]}
```

---

### 39. `api_summary(current_user)` (Line 1670)

**What it does:** GET /api/summary - Get dashboard statistics

**Why it exists:** Dashboard metrics/KPIs

**Parameters:**
- `current_user` (dict): From JWT

**Returns:** `dict` - Statistics

**Called by:** Dashboard JavaScript (if implemented)

**Calculates:**
- Total tickets
- Open/In Progress/Acknowledged counts
- SLA breached count
- Average acknowledgment time
- MTTR (Mean Time To Resolution)

**Example:**
```python
# GET /api/summary
# Returns: {
#     "total_tickets": 150,
#     "open_tickets": 12,
#     "in_progress_tickets": 8,
#     "acknowledged_tickets": 130,
#     "sla_breached": 3,
#     "avg_ack_time_sec": 1247,
#     "mttr_min": 20.8
# }
```

---

### 40. `dashboard()` (Line 1702)

**What it does:** GET /dashboard - Serves dashboard.html

**Why it exists:** Main UI

**Parameters:** None

**Returns:** HTMLResponse with dashboard.html

**Example:**
```python
# GET http://localhost:8000/dashboard
# → Returns dashboard.html page (requires login)
```

---

### 41. `api_audit_trail(action, current_user)` (Line 1710)

**What it does:** GET /api/audit-trail?action=... - Get audit logs

**Why it exists:** Dashboard "Audit Trail" tab

**Parameters:**
- `action` (str): Optional filter (e.g., "Ticket Created")
- `current_user` (dict): From JWT

**Returns:** `dict` - {"audits": [...]}

**Called by:** Dashboard JavaScript (dashboard.html:493)

**Example:**
```python
# GET /api/audit-trail?action=Jira%20Ticket%20Created
# Returns: {"audits": [
#     {"timestamp": "2025-11-29 14:30:00", "ticket_id": "ADF-001", "action": "Jira Ticket Created", ...},
#     ...
# ]}
```

---

### 42. `api_audit_summary(current_user)` (Line 1727)

**What it does:** GET /api/audit-summary - Get audit statistics

**Why it exists:** Dashboard audit metrics

**Parameters:**
- `current_user` (dict): From JWT

**Returns:** `dict` - Statistics

**Calculates:**
- Total audit entries
- Count by action type
- Recent activity

**Example:**
```python
# GET /api/audit-summary
# Returns: {
#     "total_entries": 450,
#     "ticket_created": 150,
#     "jira_created": 145,
#     "slack_sent": 150,
#     "duplicates_prevented": 23
# }
```

---

### 43. `api_config()` (Line 1750)

**What it does:** GET /api/config - Get app configuration

**Why it exists:** Dashboard needs to know if Jira is enabled for links

**Parameters:** None (public endpoint)

**Returns:** `dict` - Configuration

**Called by:** Dashboard JavaScript (dashboard.html:269)

**Example:**
```python
# GET /api/config
# Returns: {
#     "itsm_tool": "jira",
#     "jira_domain": "https://yourcompany.atlassian.net"
# }
```

---

## API Endpoints - CSV Export

### 44. `export_open_tickets(current_user)` (Line 1755)

**What it does:** GET /api/export/open-tickets - Download open tickets as CSV

**Why it exists:** Export for reporting/analysis

**Parameters:**
- `current_user` (dict): From JWT

**Returns:** StreamingResponse with CSV file

**Called by:** Dashboard "Download CSV" button

**Example:**
```python
# GET /api/export/open-tickets
# → Downloads: open_tickets_20251129_143022.csv
```

---

### 45. `export_in_progress_tickets(current_user)` (Line 1774)

**What it does:** GET /api/export/in-progress-tickets - Download in-progress tickets CSV

**Why it exists:** Export for reporting

**Parameters:**
- `current_user` (dict): From JWT

**Returns:** StreamingResponse with CSV

**Example:**
```python
# GET /api/export/in-progress-tickets
# → Downloads: in_progress_tickets_20251129_143022.csv
```

---

### 46. `export_closed_tickets(current_user)` (Line 1793)

**What it does:** GET /api/export/closed-tickets - Download closed tickets CSV

**Why it exists:** MTTR reporting

**Parameters:**
- `current_user` (dict): From JWT

**Returns:** StreamingResponse with CSV

**Example:**
```python
# GET /api/export/closed-tickets
# → Downloads: closed_tickets_20251129_143022.csv
```

---

### 47. `export_audit_trail(current_user)` (Line 1812)

**What it does:** GET /api/export/audit-trail - Download audit trail CSV

**Why it exists:** Compliance reporting

**Parameters:**
- `current_user` (dict): From JWT

**Returns:** StreamingResponse with CSV

**Example:**
```python
# GET /api/export/audit-trail
# → Downloads: audit_trail_20251129_143022.csv
```

---

## API Endpoints - Webhooks (Inbound)

### 48. `webhook_jira(request)` (Line 1831)

**What it does:** POST /webhook/jira?secret=... - Receives Jira status updates

**Why it exists:** Bi-directional sync with Jira

**Parameters:**
- `request` (Request): Jira webhook payload
- `secret` (str): Query parameter for auth

**Returns:** `dict` - {"status": "ok"}

**Called by:** Jira webhook configuration

**Workflow:**
1. Verify secret matches JIRA_WEBHOOK_SECRET
2. Check webhook event type (jira:issue_updated)
3. Extract status change from changelog
4. Find ticket by itsm_ticket_id
5. Map Jira status to local status:
   - "Done/Resolved/Closed" → "acknowledged"
   - "In Progress/In Review" → "in_progress"
   - "Open/Backlog" → "open"
6. Update ticket status
7. If closed: Calculate MTTR, update Slack
8. Broadcast WebSocket event
9. Log audit trail

**Example:**
```python
# POST /webhook/jira?secret=abc123
# Body: {
#     "webhookEvent": "jira:issue_updated",
#     "issue": {"key": "AIOPS-456"},
#     "changelog": {
#         "items": [{
#             "field": "status",
#             "toString": "Done"
#         }]
#     }
# }
# → Closes ticket, calculates MTTR, updates Slack, broadcasts to dashboard
```

---

## WebSocket Endpoint

### 49. `websocket_endpoint(websocket)` (Line 1906)

**What it does:** WebSocket /ws - Real-time dashboard updates

**Why it exists:** Push updates to dashboard without polling

**Parameters:**
- `websocket` (WebSocket): WebSocket connection

**Returns:** None (keeps connection alive)

**Called by:** Dashboard JavaScript (dashboard.html:680)

**Workflow:**
1. Accept connection
2. Add to manager.active_connections list
3. Keep connection alive (receive_text loop)
4. On disconnect: Remove from list

**Broadcasts sent:**
- When ticket created: `{"event": "new_ticket", "ticket_id": "ADF-001"}`
- When status updated: `{"event": "status_update", "ticket_id": "ADF-001", "new_status": "acknowledged"}`

**Example:**
```javascript
// Dashboard connects:
const ws = new WebSocket('ws://localhost:8000/ws');
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.event === 'new_ticket') {
        refreshAll();  // Reload tickets
    }
};
```

---

# error_extractors.py Functions

## Class: AzureDataFactoryExtractor

### 1. `AzureDataFactoryExtractor.extract(payload)` (Line 15)

**What it does:** Extracts error details from Azure Monitor ADF webhook

**Why it exists:** Parse nested Azure Monitor Common Alert Schema

**Parameters:**
- `payload` (dict): Raw webhook JSON

**Returns:** `Tuple[str, str, str, Dict]` - (pipeline_name, run_id, error_message, metadata)

**Where it's called:** main.py:902 in `/azure-monitor` endpoint

**Handles 3 formats:**
1. Log Analytics Alert (dimensions array) - Most detailed
2. Metric Alert (properties object)
3. Simple webhook format

**Example:**
```python
from error_extractors import AzureDataFactoryExtractor

payload = {
    "data": {
        "essentials": {"alertRule": "ADF-Failed"},
        "alertContext": {
            "condition": {
                "allOf": [{
                    "dimensions": [
                        {"name": "PipelineName", "value": "ETLPipeline"},
                        {"name": "PipelineRunId", "value": "abc123"},
                        {"name": "ErrorMessage", "value": "Blob not found"}
                    ]
                }]
            }
        }
    }
}

pipeline, run_id, error, metadata = AzureDataFactoryExtractor.extract(payload)
# Returns:
# ("ETLPipeline", "abc123", "Blob not found", {"activity_name": "...", ...})
```

---

## Class: DatabricksExtractor

### 2. `DatabricksExtractor.extract(payload)` (Line 137)

**What it does:** Routes Databricks webhook to appropriate extractor

**Why it exists:** Databricks has different event types (job, cluster, library)

**Parameters:**
- `payload` (dict): Databricks webhook JSON

**Returns:** `Tuple[str, str, str, str, Dict]` - (resource_name, run_id, event_type, error_message, metadata)

**Where it's called:** main.py:1089 in `/databricks-monitor` endpoint

**Routes to:**
- `_extract_job_event()` if "job" or "run" in payload
- `_extract_cluster_event()` if "cluster" in payload
- `_extract_library_event()` if "library" in payload
- `_extract_generic_event()` fallback

**Example:**
```python
from error_extractors import DatabricksExtractor

payload = {"event": "job.run.failed", "run": {"run_id": 12345, ...}}
name, run_id, event, error, meta = DatabricksExtractor.extract(payload)
```

---

### 3. `DatabricksExtractor._extract_job_event(payload, event_type)` (Line 157)

**What it does:** Extracts job failure details from Databricks webhook

**Why it exists:** Parse job-specific fields

**Parameters:**
- `payload` (dict): Webhook JSON
- `event_type` (str): Event type (e.g., "job.run.failed")

**Returns:** `Tuple[str, str, str, str, Dict]`

**Where it's called:** Line 148 in `extract()`

**Extracts:**
- Job name from `job.settings.name` or `run.run_name`
- Run ID from `run.run_id`
- Error message from `run.state.state_message`

**Example:**
```python
payload = {
    "event": "job.run.failed",
    "job": {"settings": {"name": "ETL_Job"}},
    "run": {
        "run_id": 12345,
        "state": {"state_message": "Task failed with exception"}
    }
}

name, run_id, event, error, meta = DatabricksExtractor._extract_job_event(payload, "job.run.failed")
# Returns: ("ETL_Job", "12345", "job.run.failed", "Task failed with exception", {...})
```

---

### 4. `DatabricksExtractor._extract_cluster_event(payload, event_type)` (Line 197)

**What it does:** Extracts cluster event details (termination, failure)

**Why it exists:** Parse cluster-specific fields including termination reason

**Parameters:**
- `payload` (dict): Webhook JSON
- `event_type` (str): Event type (e.g., "cluster.terminated")

**Returns:** `Tuple[str, str, str, str, Dict]`

**Where it's called:** Line 150 in `extract()`

**Extracts:**
- Cluster name/ID
- Termination reason (code, type, parameters)
- State message

**Example:**
```python
payload = {
    "event": "cluster.terminated",
    "cluster": {
        "cluster_id": "1121-055905-q5xcz4bm",
        "cluster_name": "Production Cluster",
        "state": "TERMINATED",
        "termination_reason": {
            "code": "DRIVER_NOT_RESPONDING",
            "type": "CLIENT_ERROR"
        }
    }
}

name, id, event, error, meta = DatabricksExtractor._extract_cluster_event(payload, "cluster.terminated")
# Returns: ("Production Cluster", "1121-055905-q5xcz4bm", "cluster.terminated", "Cluster terminated: DRIVER_NOT_RESPONDING (CLIENT_ERROR)", {...})
```

---

### 5. `DatabricksExtractor._extract_library_event(payload, event_type)` (Line 244)

**What it does:** Extracts library installation event details

**Why it exists:** Parse library-specific fields

**Parameters:**
- `payload` (dict): Webhook JSON
- `event_type` (str): Event type (e.g., "library.installation.failed")

**Returns:** `Tuple[str, str, str, str, Dict]`

**Where it's called:** Line 152 in `extract()`

**Extracts:**
- Library name (PyPI, Maven, JAR)
- Cluster ID
- Error message

**Example:**
```python
payload = {
    "event": "library.installation.failed",
    "cluster": {"cluster_id": "abc", "cluster_name": "Test"},
    "library": {"pypi": {"package": "pandas==1.5.0"}},
    "error_message": "Package not found"
}

name, id, event, error, meta = DatabricksExtractor._extract_library_event(payload, "library.installation.failed")
# Returns: ("Test - pandas==1.5.0", "abc", "library.installation.failed", "Package not found", {...})
```

---

### 6. `DatabricksExtractor._extract_generic_event(payload, event_type)` (Line 280)

**What it does:** Fallback extractor for unknown event types

**Why it exists:** Always return something even for unknown events

**Parameters:**
- `payload` (dict): Webhook JSON
- `event_type` (str): Event type

**Returns:** `Tuple[str, str, str, str, Dict]`

**Where it's called:** Line 154 in `extract()`

**Example:**
```python
payload = {"event": "custom.event", "name": "Something", "id": "123"}
name, id, event, error, meta = DatabricksExtractor._extract_generic_event(payload, "custom.event")
# Returns: ("Something", "123", "custom.event", str(payload), {...})
```

---

## Class: AzureFunctionsExtractor

### 7. `AzureFunctionsExtractor.extract(payload)` (Line 311)

**What it does:** Extracts error details from Azure Functions/App Insights webhooks

**Why it exists:** Support Azure Functions monitoring (not currently used)

**Parameters:**
- `payload` (dict): Webhook JSON

**Returns:** `Tuple[str, str, str, Dict]` - (function_name, invocation_id, error_message, metadata)

**Example:**
```python
from error_extractors import AzureFunctionsExtractor

payload = {
    "data": {
        "alertContext": {
            "properties": {
                "FunctionName": "ProcessData",
                "InvocationId": "inv-123",
                "ExceptionMessage": "Timeout error"
            }
        }
    }
}

func, inv_id, error, meta = AzureFunctionsExtractor.extract(payload)
# Returns: ("ProcessData", "inv-123", "Timeout error", {...})
```

---

## Class: AzureSynapseExtractor

### 8. `AzureSynapseExtractor.extract(payload)` (Line 355)

**What it does:** Extracts error details from Azure Synapse webhooks

**Why it exists:** Support Synapse Analytics monitoring (not currently used)

**Parameters:**
- `payload` (dict): Webhook JSON

**Returns:** `Tuple[str, str, str, Dict]` - (pipeline_name, run_id, error_message, metadata)

**Example:**
```python
from error_extractors import AzureSynapseExtractor

payload = {
    "data": {
        "alertContext": {
            "properties": {
                "PipelineName": "SynapsePipeline",
                "RunId": "run-456",
                "ErrorMessage": "SQL pool unavailable"
            }
        }
    }
}

pipeline, run_id, error, meta = AzureSynapseExtractor.extract(payload)
# Returns: ("SynapsePipeline", "run-456", "SQL pool unavailable", {...})
```

---

## Factory Function

### 9. `get_extractor(source_type)` (Line 398)

**What it does:** Returns appropriate extractor class for source type

**Why it exists:** Factory pattern for selecting extractor

**Parameters:**
- `source_type` (str): Service name ("adf", "databricks", "azure_functions", "synapse")

**Returns:** Extractor class or `None`

**Where it's called:** Not currently used (direct imports used instead)

**Example:**
```python
from error_extractors import get_extractor

extractor_class = get_extractor("adf")
# Returns: AzureDataFactoryExtractor

pipeline, run_id, error, meta = extractor_class.extract(payload)
```

---

# databricks_api_utils.py Functions

### 1. `fetch_databricks_run_details(run_id)` (Line 16)

**What it does:** Fetches full job run details from Databricks Jobs API

**Why it exists:** Webhooks have generic errors, API has detailed stack traces

**Parameters:**
- `run_id` (str): Databricks job run ID

**Returns:** `dict` - Full run details or `None` if failed

**Where it's called:** main.py:1154 in `/databricks-monitor` endpoint

**API Call:** `GET /api/2.1/jobs/runs/get?run_id={run_id}`

**Workflow:**
1. Check if credentials are configured (DATABRICKS_HOST, DATABRICKS_TOKEN)
2. Call Jobs API
3. For each failed task, call `fetch_task_output()` to get error traces
4. Call `extract_error_message()` to get detailed error

**Example:**
```python
from databricks_api_utils import fetch_databricks_run_details

run_details = fetch_databricks_run_details("12345")
# Returns: {
#     "job_id": 123,
#     "run_id": 12345,
#     "state": {"life_cycle_state": "TERMINATED", "result_state": "FAILED"},
#     "tasks": [{
#         "task_key": "data_validation",
#         "state": {"result_state": "FAILED"},
#         "run_output": {
#             "error": "FileNotFoundError: '/data/input.csv' not found",
#             "error_trace": "Traceback..."
#         }
#     }]
# }
```

---

### 2. `fetch_task_output(task_run_id)` (Line 119)

**What it does:** Fetches task-level output including error traces

**Why it exists:** Task output has actual Python exceptions, not available in run details

**Parameters:**
- `task_run_id` (str): Task run ID (different from job run ID)

**Returns:** `dict` - Task output or `None` if failed

**Where it's called:** Line 97 in `fetch_databricks_run_details()` (for each failed task)

**API Call:** `GET /api/2.1/jobs/runs/get-output?run_id={task_run_id}`

**Example:**
```python
from databricks_api_utils import fetch_task_output

task_output = fetch_task_output("67890")
# Returns: {
#     "error": "FileNotFoundError: '/mnt/data/input.csv' not found",
#     "error_trace": "Traceback (most recent call last):\n  File ...",
#     "logs": "Starting task...\nReading from /mnt/data/input.csv\nERROR: File not found"
# }
```

---

### 3. `extract_error_message(run_data)` (Line 154)

**What it does:** Extracts most detailed error message from run data

**Why it exists:** Prioritize task-level errors over generic job-level errors

**Parameters:**
- `run_data` (dict): Full run details from `fetch_databricks_run_details()`

**Returns:** `str` - Detailed error message or `None`

**Where it's called:** Line 105 in `fetch_databricks_run_details()`

**Priority:**
1. **Task `run_output.error`** (actual exception - BEST)
2. **Task `exception.message`**
3. **Task `state.state_message`** (generic)
4. **Job-level `state.state_message`** (fallback)

**Example:**
```python
from databricks_api_utils import extract_error_message

run_data = {
    "tasks": [{
        "task_key": "validation",
        "state": {"result_state": "FAILED"},
        "run_output": {
            "error": "FileNotFoundError: '/data/input.csv' not found"
        }
    }]
}

error = extract_error_message(run_data)
# Returns: "[Task: validation] FileNotFoundError: '/data/input.csv' not found"
```

---

### 4. `get_cluster_logs_url(run_data)` (Line 249)

**What it does:** Generates URL to cluster logs in Databricks UI

**Why it exists:** Provide quick link to logs for investigation

**Parameters:**
- `run_data` (dict): Run details

**Returns:** `str` - URL or `None`

**Where it's called:** Not currently used (can be added to ticket metadata)

**Example:**
```python
from databricks_api_utils import get_cluster_logs_url

run_data = {
    "cluster_instance": {"cluster_id": "1121-055905-q5xcz4bm"}
}

url = get_cluster_logs_url(run_data)
# Returns: "https://adb-1234567890123456.7.azuredatabricks.net/#/setting/clusters/1121-055905-q5xcz4bm/sparkUi"
```

---

### 5. `get_run_page_url(run_data)` (Line 269)

**What it does:** Generates URL to job run page in Databricks UI

**Why it exists:** Provide quick link to run details for investigation

**Parameters:**
- `run_data` (dict): Run details

**Returns:** `str` - URL or `None`

**Where it's called:** Not currently used (can be added to ticket metadata)

**Example:**
```python
from databricks_api_utils import get_run_page_url

run_data = {
    "job_id": 123,
    "run_id": 12345
}

url = get_run_page_url(run_data)
# Returns: "https://adb-1234567890123456.7.azuredatabricks.net/#job/123/run/12345"
```

---

## Summary Tables

### main.py Functions by Category

| Category | Count | Functions |
|----------|-------|-----------|
| **Database** | 5 | build_azure_sqlalchemy_url, get_engine_with_retry, init_db, db_execute, db_query |
| **Authentication** | 5 | hash_password, verify_password, create_access_token, decode_access_token, get_current_user |
| **Audit/Logging** | 2 | log_audit, upload_payload_to_blob |
| **FinOps** | 1 | extract_finops_tags |
| **AI/RCA** | 5 | call_ai_for_rca, derive_priority, sla_for_priority, fallback_rca, generate_rca_and_recs |
| **Jira** | 2 | _get_jira_auth, create_jira_ticket |
| **Slack** | 2 | post_slack_notification, update_slack_message_on_ack |
| **Helper** | 2 | _http_post_with_retries, perform_close_from_jira |
| **Auth Endpoints** | 3 | register, login, get_current_user_info |
| **Public Endpoints** | 3 | root, login_page, check_ticket_exists |
| **Webhook Endpoints** | 4 | azure_monitor, databricks_monitor, azure_monitor_alert, webhook_jira |
| **Protected Endpoints** | 10 | get_ticket_details, api_open_tickets, api_in_progress_tickets, api_closed_tickets, api_summary, dashboard, api_audit_trail, api_audit_summary, api_config, _get_ticket_columns |
| **Export Endpoints** | 4 | export_open_tickets, export_in_progress_tickets, export_closed_tickets, export_audit_trail |
| **WebSocket** | 1 | websocket_endpoint |

**Total: 49 functions**

---

### error_extractors.py Functions

| Class | Method | Purpose |
|-------|--------|---------|
| AzureDataFactoryExtractor | extract() | Parse ADF webhook |
| DatabricksExtractor | extract() | Route Databricks webhook |
| DatabricksExtractor | _extract_job_event() | Parse job failure |
| DatabricksExtractor | _extract_cluster_event() | Parse cluster failure |
| DatabricksExtractor | _extract_library_event() | Parse library failure |
| DatabricksExtractor | _extract_generic_event() | Fallback parser |
| AzureFunctionsExtractor | extract() | Parse Functions webhook |
| AzureSynapseExtractor | extract() | Parse Synapse webhook |
| (Factory) | get_extractor() | Return extractor class |

**Total: 9 functions**

---

### databricks_api_utils.py Functions

| Function | Purpose | API Call |
|----------|---------|----------|
| fetch_databricks_run_details() | Get full run details | GET /api/2.1/jobs/runs/get |
| fetch_task_output() | Get task error traces | GET /api/2.1/jobs/runs/get-output |
| extract_error_message() | Parse error from run data | (Parsing only) |
| get_cluster_logs_url() | Generate logs URL | (URL builder) |
| get_run_page_url() | Generate run page URL | (URL builder) |

**Total: 5 functions**

---

## Complete Project Function Count

- **main.py:** 49 functions
- **error_extractors.py:** 9 functions
- **databricks_api_utils.py:** 5 functions

**Grand Total: 63 functions**

All functions are now fully explained with:
- ✅ What it does
- ✅ Why it exists
- ✅ Where it's called
- ✅ Input parameters
- ✅ Output/return value
- ✅ Example usage
