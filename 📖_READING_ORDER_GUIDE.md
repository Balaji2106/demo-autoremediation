# 📖 Reading Order Guide - How to Understand This Project

## For New Team Members / Interviewers / Code Reviewers

This guide tells you **exactly what order** to read the documentation and code to understand this project from scratch.

---

## 🎯 Quick Start (15 minutes)

If you only have 15 minutes, read these in order:

### 1. **Start Here: Before/After Comparison** (5 min)
**File:** `🔄_BEFORE_AFTER_COMPARISON.md`

**Why first:** Shows the REAL business value with a concrete example (Black Friday incident).

**You'll learn:**
- What problem this solves
- Why it matters (MTTR reduced 87%)
- ROI ($93k/year savings)

**Skip to:** Section "Comparison Summary" if pressed for time

---

### 2. **Project Overview** (5 min)
**File:** `📚_COMPLETE_PROJECT_EXPLANATION.md`

**Read sections:**
- "Project Overview" (top)
- "Architecture & Components" → High-Level Architecture diagram

**You'll learn:**
- What the system does (AI-powered RCA for ADF/Databricks failures)
- How data flows (Webhook → AI → Ticket → Notifications)
- Tech stack (FastAPI, Gemini, SQLite, WebSocket)

---

### 3. **Quick Demo** (5 min)
**File:** Open `genai_rca_assistant/dashboard.html` in browser

**What to do:**
- Just look at the HTML/CSS structure
- See the three tabs (Open, In Progress, Closed)
- Understand it's a single-page app with real-time updates

**You'll learn:**
- UI is simple and clean
- No frameworks (vanilla JS)
- Focus on functionality over fancy animations

---

## 📚 Full Understanding (2 hours)

If you have 2 hours to fully understand the project:

### Phase 1: High-Level Understanding (30 min)

#### 1. **Before/After Comparison** (10 min)
**File:** `🔄_BEFORE_AFTER_COMPARISON.md`

**Read fully:**
- Complete "BEFORE" timeline
- Complete "AFTER" timeline
- Comparison Summary table
- Business Impact section

**Key takeaway:** Understand why automation matters

---

#### 2. **Architecture Diagrams** (10 min)
**File:** `📚_COMPLETE_PROJECT_EXPLANATION.md`

**Read sections:**
- "Architecture & Components" → High-Level Architecture
- "Complete Workflow Diagrams":
  - Workflow 1: ADF Pipeline Failure
  - Workflow 2: Databricks Job Failure
  - Workflow 3: Cluster Termination

**Key takeaway:** Understand data flow from alert to resolution

---

#### 3. **README** (10 min)
**File:** `README.md`

**Read sections:**
- Features
- Quick Start
- Configuration (environment variables)

**Key takeaway:** How to actually run the system

---

### Phase 2: Technical Deep Dive (1 hour)

#### 4. **Database Schema** (10 min)
**File:** `📚_COMPLETE_PROJECT_EXPLANATION.md`

**Read section:** "Database Schema"

**Tables to understand:**
- `tickets` table (main data)
- `audit_trail` table (compliance)
- `users` table (authentication)

**Key takeaway:** How tickets are stored and deduplication works

---

#### 5. **Code Files Explained** (30 min)
**File:** `📚_COMPLETE_PROJECT_EXPLANATION.md`

**Read in this order:**

**A. error_extractors.py (5 min)**
- Purpose: Parse different webhook formats
- Classes: AzureDataFactoryExtractor, DatabricksExtractor
- Why it exists: Each service has different JSON structure

**B. databricks_api_utils.py (5 min)**
- Purpose: Fetch detailed errors from Databricks API
- Key functions: `fetch_databricks_run_details()`, `extract_error_message()`
- Why it exists: Webhooks have generic errors, API has specifics

**C. main.py - Authentication & DB (10 min)**
- Lines 1-371: Configuration, database, auth
- Understand: JWT tokens, bcrypt hashing, user management

**D. main.py - AI RCA (10 min)**
- Lines 446-558: Gemini integration
- Function: `call_ai_for_rca()`
- Understand: Prompt engineering, JSON parsing, fallback

**Key takeaway:** How each component works

---

#### 6. **API Endpoints** (20 min)
**File:** `📚_COMPLETE_PROJECT_EXPLANATION.md`

**Read sections:** "API Endpoints Detailed Explanation"

**Focus on these endpoints:**

**1. `/azure-monitor` (5 min)**
- ADF pipeline failures
- Azure Monitor Common Alert Schema
- Deduplication by run_id

**2. `/databricks-monitor` (5 min)**
- Databricks native webhooks
- API enrichment workflow
- Task-level error extraction

**3. `/azure-monitor-alert` (5 min)**
- Databricks cluster failures via Log Analytics
- SearchResults table parsing
- Composite deduplication key

**4. Protected endpoints (5 min)**
- `/api/open-tickets`, `/api/closed-tickets`
- `/api/summary` (metrics)
- JWT authentication

**Key takeaway:** How webhooks are handled

---

### Phase 3: Frontend & Real-time (30 min)

#### 7. **Dashboard Architecture** (15 min)
**File:** `📚_COMPLETE_PROJECT_EXPLANATION.md`

**Read section:** "Dashboard (dashboard.html) - Complete Explanation"

**Then open:** `genai_rca_assistant/dashboard.html`

**Find these code sections:**

**A. Authentication (lines 218-266):**
```javascript
function checkAuth() { ... }
async function fetchWithAuth(url, options) { ... }
```

**B. Data Fetching (lines 278-323):**
```javascript
async function fetchOpen() { ... }
async function refreshAll() { ... }
```

**C. Rendering (lines 342-408):**
```javascript
function render() { ... }
function startTimer(ticket) { ... }
```

**D. WebSocket (lines 680-695):**
```javascript
const ws = new WebSocket('ws://...');
ws.onmessage = (event) => { ... }
```

**Key takeaway:** How real-time updates work

---

#### 8. **WebSocket Deep Dive** (15 min)
**File:** `📚_COMPLETE_PROJECT_EXPLANATION.md`

**Read section:** "WebSocket Manager"

**Then find in main.py:**
- Lines 625-641: `ConnectionManager` class
- Lines 1653-1660: `/ws` endpoint
- Search for: `manager.broadcast` (multiple locations)

**Understand:**
- Server maintains list of connections
- Broadcasts JSON messages to all clients
- Clients auto-refresh on events

**Key takeaway:** Real-time magic explained

---

## 🧑‍💼 For Interviews (1 hour prep)

If you're preparing for an interview about this project:

### Must-Read Documents (40 min)

#### 1. **Interview Q&A** (30 min)
**File:** `💬_INTERVIEW_QUESTIONS_AND_ANSWERS.md`

**Read ALL questions:**
- Q1: 2-minute project explanation
- Q2: What problem does it solve?
- Q3: Why this tech stack?
- Q4: Deduplication mechanism
- Q5: AI RCA generation
- Q6: error_extractors vs databricks_api_utils
- Q7: WebSocket real-time updates
- Q8: SLA and MTTR calculations
- Q9: Jira bi-directional sync
- Q10: Challenges and solutions

**Practice:** Explain Q1-Q3 out loud until you can do it without notes

---

#### 2. **Before/After Comparison** (10 min)
**File:** `🔄_BEFORE_AFTER_COMPARISON.md`

**Memorize these numbers:**
- MTTR: 105 min → 13.5 min (87% improvement)
- Detection: 30 min → 12 sec (99.3% faster)
- SLA compliance: 45% → 98%
- Annual savings: $93,636
- ROI: 1,276% first year

**Practice:** Explain the Black Friday scenario in 2 minutes

---

### Code Walkthrough Prep (20 min)

**Be ready to explain:**

#### 1. **Deduplication Code** (5 min)
**File:** `genai_rca_assistant/main.py` (lines 936-953, 1192-1209, 1432-1449)

```python
if run_id:
    existing = db_query("SELECT id FROM tickets WHERE run_id = :run_id",
                       {"run_id": run_id}, one=True)
    if existing:
        logger.warning(f"DUPLICATE: {run_id} → {existing['id']}")
        return JSONResponse({"status": "duplicate_ignored"})
```

**Be able to explain:**
- Why unique index on run_id
- How composite keys work (ClusterId + TerminationCode + Timestamp)
- Race condition handling

---

#### 2. **AI RCA Function** (5 min)
**File:** `genai_rca_assistant/main.py` (lines 455-528)

```python
def call_ai_for_rca(description: str, source_type: str = "adf"):
    prompt = f"""
    You are an expert AIOps RCA assistant for {service_name}.
    Analyze: {description}
    Return JSON: {{"root_cause": "...", "severity": "...", ...}}
    """
    model = genai.GenerativeModel(MODEL_ID)
    resp = model.generate_content(prompt)
    return json.loads(resp.text)
```

**Be able to explain:**
- Prompt engineering choices
- Why JSON format is critical
- Fallback handling

---

#### 3. **WebSocket Broadcast** (5 min)
**File:** `genai_rca_assistant/main.py` (lines 625-641, 1037, 1299, 1563)

```python
await manager.broadcast({
    "event": "new_ticket",
    "ticket_id": tid
})
```

**Be able to explain:**
- When broadcasts happen
- How clients handle messages
- Why WebSocket vs polling

---

#### 4. **Error Extractors** (5 min)
**File:** `genai_rca_assistant/error_extractors.py` (lines 14-130)

```python
class AzureDataFactoryExtractor:
    @staticmethod
    def extract(payload: Dict) -> Tuple[str, str, str, Dict]:
        dimensions = payload["data"]["alertContext"]["condition"]["allOf"][0]["dimensions"]
        pipeline_name = dimensions_dict.get("PipelineName")
        run_id = dimensions_dict.get("PipelineRunId")
        error_message = dimensions_dict.get("ErrorMessage")
        return pipeline_name, run_id, error_message, metadata
```

**Be able to explain:**
- Why separate extractors for each service
- How nested JSON is parsed
- Difference from databricks_api_utils.py

---

## 🔧 For Development / Debugging

If you need to modify or debug the code:

### Setup Order

#### 1. **Environment Setup** (10 min)
**File:** `README.md`

**Steps:**
1. Copy `.env.example` to `.env`
2. Fill in API keys (Gemini, Slack, Databricks, Jira)
3. Install dependencies: `pip install -r requirements.txt`
4. Run: `python main.py`

---

#### 2. **Database Exploration** (10 min)
**File:** `genai_rca_assistant/main.py` (lines 150-286)

**Steps:**
1. Run app once to create `data/tickets.db`
2. Open with SQLite browser: `sqlite3 data/tickets.db`
3. Run: `.schema tickets`
4. Run: `SELECT * FROM tickets LIMIT 10;`

**Understand:** Table structure, constraints, indexes

---

#### 3. **Test Webhook** (15 min)
**File:** `README.md` → Testing section

**Steps:**
1. Start app: `python main.py`
2. Use curl to send test webhook:
```bash
curl -X POST http://localhost:8000/azure-monitor \
  -H "Content-Type: application/json" \
  -d @test_payload.json
```
3. Check logs for processing
4. Check database: `SELECT * FROM tickets;`
5. Open dashboard: `http://localhost:8000/dashboard`

---

### Debugging Order

#### If something doesn't work:

**1. Check logs:**
```bash
# Application logs show:
# - Webhook received
# - Extraction results
# - AI RCA response
# - Database operations
# - Jira/Slack API calls
```

**2. Check database:**
```sql
-- See all tickets
SELECT id, pipeline, status, run_id FROM tickets ORDER BY timestamp DESC LIMIT 10;

-- See audit trail
SELECT timestamp, ticket_id, action, details FROM audit_trail ORDER BY timestamp DESC LIMIT 20;
```

**3. Check specific components:**
- **Webhook not received:** Check Azure Monitor Action Group configuration
- **AI RCA fails:** Check `GEMINI_API_KEY` in .env
- **No Slack notification:** Check `SLACK_BOT_TOKEN` and channel
- **Jira creation fails:** Check `JIRA_DOMAIN`, `JIRA_API_TOKEN`
- **Duplicates created:** Check unique index: `PRAGMA index_list(tickets);`

---

## 📝 Summary Cheat Sheet

### File Purpose Quick Reference

| File | Purpose | When to Read |
|------|---------|--------------|
| `🔄_BEFORE_AFTER_COMPARISON.md` | Business value proof | First (understand why) |
| `📚_COMPLETE_PROJECT_EXPLANATION.md` | Technical deep dive | Second (understand how) |
| `💬_INTERVIEW_QUESTIONS_AND_ANSWERS.md` | Interview prep | Before interviews |
| `📖_READING_ORDER_GUIDE.md` | This file | Start here |
| `README.md` | Setup & quickstart | When running locally |
| `genai_rca_assistant/main.py` | Core application | Code review |
| `genai_rca_assistant/error_extractors.py` | Webhook parsers | Debugging webhooks |
| `genai_rca_assistant/databricks_api_utils.py` | API enrichment | Debugging Databricks |
| `genai_rca_assistant/dashboard.html` | Frontend UI | UI customization |

---

### Key Concepts Quick Reference

| Concept | Location | One-Line Explanation |
|---------|----------|----------------------|
| **Deduplication** | main.py:936-953 | Unique index on run_id prevents duplicate tickets |
| **AI RCA** | main.py:455-528 | Gemini analyzes errors and returns JSON |
| **WebSocket** | main.py:625-641 | Real-time dashboard updates via broadcast |
| **Error Extraction** | error_extractors.py | Parse different webhook JSON formats |
| **API Enrichment** | databricks_api_utils.py | Fetch detailed errors from Databricks API |
| **SLA Timer** | dashboard.html:410-421 | Live countdown with color coding |
| **Jira Sync** | main.py:1578-1650 | Bi-directional status updates |
| **Audit Trail** | main.py:373-398 | Complete compliance logging |

---

### Learning Paths

#### Path A: Business Analyst
```
1. 🔄_BEFORE_AFTER_COMPARISON.md (10 min)
2. README.md → Features (5 min)
3. 📚_COMPLETE_PROJECT_EXPLANATION.md → Architecture diagram (5 min)
Done! You understand business value and high-level architecture.
```

#### Path B: Frontend Developer
```
1. 📚_COMPLETE_PROJECT_EXPLANATION.md → Dashboard section (15 min)
2. dashboard.html → Read JavaScript code (30 min)
3. 💬_INTERVIEW_QUESTIONS_AND_ANSWERS.md → Q7 (WebSocket) (5 min)
Done! You understand the UI and real-time features.
```

#### Path C: Backend Developer
```
1. 📚_COMPLETE_PROJECT_EXPLANATION.md → Code Files Explained (30 min)
2. main.py → Read endpoints (30 min)
3. error_extractors.py + databricks_api_utils.py (15 min)
4. 💬_INTERVIEW_QUESTIONS_AND_ANSWERS.md → Q4, Q5, Q6 (15 min)
Done! You understand backend architecture and integrations.
```

#### Path D: DevOps / SRE
```
1. README.md → Setup & Configuration (10 min)
2. 📚_COMPLETE_PROJECT_EXPLANATION.md → Database Schema (10 min)
3. 💬_INTERVIEW_QUESTIONS_AND_ANSWERS.md → Q8 (SLA/MTTR) (10 min)
4. 🔄_BEFORE_AFTER_COMPARISON.md → Metrics (5 min)
Done! You understand deployment, monitoring, and metrics.
```

#### Path E: Complete Understanding (Everything)
```
Follow the "Full Understanding (2 hours)" section above.
```

---

## 🎓 Certification Quiz

After reading, you should be able to answer:

### Beginner (Business Value)
1. What problem does this system solve?
2. How much time does it save per incident?
3. What's the ROI in the first year?

**Answers:** Q2 in Interview Q&A

---

### Intermediate (Architecture)
1. What are the three main webhook sources?
2. How does deduplication work?
3. What's the difference between error_extractors.py and databricks_api_utils.py?

**Answers:** Arch diagram + Q6 in Interview Q&A

---

### Advanced (Implementation)
1. How does the AI RCA prompt engineering work?
2. Explain the WebSocket broadcast flow.
3. How does Jira bi-directional sync work?

**Answers:** Q5, Q7, Q9 in Interview Q&A

---

### Expert (Debugging)
1. What happens when two webhooks arrive simultaneously with same run_id?
2. How would you debug missing Slack notifications?
3. Why does the SLA timer use setInterval instead of polling the API?

**Answers:** Q10 (Race conditions), Debug section above, Performance optimization

---

## ✅ Next Steps

After reading this guide:

1. **For Understanding:** Read in order above
2. **For Setup:** Start with README.md
3. **For Interview:** Focus on Interview Q&A + Before/After
4. **For Development:** Read Full Understanding (2 hours)
5. **For Debugging:** Use Debugging Order section

---

## 📞 Questions?

If something is unclear after reading:
1. Check the relevant file in the priority order
2. Search for keywords in `📚_COMPLETE_PROJECT_EXPLANATION.md`
3. Look for specific code examples in `💬_INTERVIEW_QUESTIONS_AND_ANSWERS.md`

**Remember:** This is a complex system. Don't try to understand everything at once. Follow the reading order!
