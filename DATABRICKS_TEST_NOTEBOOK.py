# Databricks notebook source
# MAGIC %md
# MAGIC # 🧪 Auto-Heal System Test Notebook
# MAGIC
# MAGIC This notebook tests the auto-remediation system by triggering different types of failures.
# MAGIC
# MAGIC **BEFORE RUNNING:**
# MAGIC 1. Make sure auto-heal system is running: `./quick-start-auto-heal.sh`
# MAGIC 2. Make sure ngrok is running: `ngrok http 8000`
# MAGIC 3. Configure webhook for this job: `python3 setup-databricks-webhooks.py`
# MAGIC
# MAGIC **WHAT THIS DOES:**
# MAGIC - Triggers a test failure
# MAGIC - Webhook automatically sent to your auto-heal system
# MAGIC - AI analyzes the error
# MAGIC - Auto-remediation triggered (if applicable)
# MAGIC - You can watch it work in real-time!

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup Widget (Select Test Type)

# COMMAND ----------

# Create widget to select test type
dbutils.widgets.dropdown("test_type", "cluster_crash",
                        ["cluster_crash", "timeout", "code_error", "transient"],
                        "Select Test Type")

test_type = dbutils.widgets.get("test_type")
print(f"Selected test: {test_type}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Test 1: Cluster Crash (Auto-Healable ✅)
# MAGIC
# MAGIC **What happens:**
# MAGIC 1. Driver crashes
# MAGIC 2. Webhook sent automatically
# MAGIC 3. AI detects: `ClusterUnexpectedTermination`
# MAGIC 4. Auto-heal restarts cluster
# MAGIC 5. Job can be retried

# COMMAND ----------

if test_type == "cluster_crash":
    print("=" * 80)
    print("🧪 TEST: Cluster Crash (Auto-Healable)")
    print("=" * 80)
    print("")
    print("This will crash the driver. Expected behavior:")
    print("  1. Job fails immediately")
    print("  2. Webhook sent to auto-heal system")
    print("  3. AI analyzes error")
    print("  4. Auto-remediation: Restart cluster")
    print("  5. Check dashboard to see the magic!")
    print("")
    print("Crashing driver in 3 seconds...")

    import time
    time.sleep(3)

    # Force driver crash
    import os
    os.system("kill -9 1")

    # This won't execute
    print("This line will never print")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Test 2: Job Timeout (Auto-Healable ✅)
# MAGIC
# MAGIC **What happens:**
# MAGIC 1. Job runs too long
# MAGIC 2. Timeout occurs
# MAGIC 3. Webhook sent automatically
# MAGIC 4. AI detects: `DatabricksTimeoutError`
# MAGIC 5. Auto-heal retries job

# COMMAND ----------

if test_type == "timeout":
    print("=" * 80)
    print("🧪 TEST: Job Timeout (Auto-Healable)")
    print("=" * 80)
    print("")
    print("This will run for 10 minutes. Set job timeout to 60 seconds for quick test.")
    print("")
    print("Expected behavior:")
    print("  1. Job times out after 60s")
    print("  2. Webhook sent to auto-heal system")
    print("  3. AI detects timeout")
    print("  4. Auto-remediation: Retry job")
    print("")

    import time
    for i in range(600):  # 10 minutes
        time.sleep(1)
        if i % 10 == 0:
            print(f"⏱️ Running for {i} seconds...")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Test 3: Code Error (NOT Auto-Healable ❌)
# MAGIC
# MAGIC **What happens:**
# MAGIC 1. Code has a bug (division by zero)
# MAGIC 2. Webhook sent automatically
# MAGIC 3. AI detects: Code error (not auto-healable)
# MAGIC 4. Ticket created but NO auto-remediation
# MAGIC 5. Jira ticket created for manual intervention

# COMMAND ----------

if test_type == "code_error":
    print("=" * 80)
    print("🧪 TEST: Code Error (NOT Auto-Healable)")
    print("=" * 80)
    print("")
    print("This is a code bug that requires manual fix.")
    print("")
    print("Expected behavior:")
    print("  1. Job fails with ZeroDivisionError")
    print("  2. Webhook sent to auto-heal system")
    print("  3. AI analyzes: auto_heal_possible = false")
    print("  4. Ticket created (no auto-remediation)")
    print("  5. Jira ticket for manual review")
    print("")
    print("Triggering error...")

    # Code bug
    result = 10 / 0

# COMMAND ----------

# MAGIC %md
# MAGIC ## Test 4: Transient Error (Auto-Healable ✅)
# MAGIC
# MAGIC **What happens:**
# MAGIC 1. First run: Fails with timeout
# MAGIC 2. Webhook sent automatically
# MAGIC 3. AI detects: `GatewayTimeout`
# MAGIC 4. Auto-heal waits 10s and retries
# MAGIC 5. Second run: Succeeds!

# COMMAND ----------

if test_type == "transient":
    print("=" * 80)
    print("🧪 TEST: Transient Error (Auto-Healable)")
    print("=" * 80)
    print("")
    print("This simulates a temporary network issue.")
    print("")
    print("Expected behavior:")
    print("  1. First run: Fails with 'GatewayTimeout'")
    print("  2. Webhook sent to auto-heal system")
    print("  3. AI detects transient error")
    print("  4. Auto-remediation: Retry after 10s")
    print("  5. Second run: Success!")
    print("")

    import random

    # 70% chance of failure (simulates transient issue)
    if random.random() < 0.7:
        print("❌ First attempt: Simulating network timeout...")
        raise Exception("GatewayTimeout: Connection timeout after 30 seconds")
    else:
        print("✅ Success! Connection established.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Check Results
# MAGIC
# MAGIC After running the test, check:
# MAGIC
# MAGIC ### 1. Dashboard (Real-time)
# MAGIC ```
# MAGIC http://localhost:8000/dashboard
# MAGIC ```
# MAGIC or
# MAGIC ```
# MAGIC https://your-ngrok-url.ngrok-free.dev/dashboard
# MAGIC ```
# MAGIC
# MAGIC ### 2. Database (Audit Trail)
# MAGIC ```bash
# MAGIC sqlite3 data/tickets.db "
# MAGIC SELECT
# MAGIC     id,
# MAGIC     pipeline,
# MAGIC     error_type,
# MAGIC     status,
# MAGIC     timestamp
# MAGIC FROM tickets
# MAGIC ORDER BY timestamp DESC
# MAGIC LIMIT 5
# MAGIC "
# MAGIC ```
# MAGIC
# MAGIC ### 3. Auto-Remediation Logs
# MAGIC ```bash
# MAGIC sqlite3 data/tickets.db "
# MAGIC SELECT
# MAGIC     action,
# MAGIC     details,
# MAGIC     timestamp
# MAGIC FROM audit_trail
# MAGIC WHERE action LIKE 'Auto-Remediation%'
# MAGIC ORDER BY timestamp DESC
# MAGIC LIMIT 10
# MAGIC "
# MAGIC ```
# MAGIC
# MAGIC ### 4. Check Jira
# MAGIC Go to: https://mypatibalaji65.atlassian.net/jira/software/projects/APAIOPS
# MAGIC
# MAGIC You should see a new ticket with full RCA!

# COMMAND ----------

print("✅ Test notebook ready!")
print("")
print("Next steps:")
print("1. Select test type from widget above")
print("2. Run the cells")
print("3. Watch auto-heal work!")
print("")
print("Dashboard: http://localhost:8000/dashboard")
