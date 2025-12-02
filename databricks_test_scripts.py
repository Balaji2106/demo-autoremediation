# =============================================================================
# Databricks Auto-Heal Test Scripts
# =============================================================================
# These notebooks test different failure scenarios that trigger auto-remediation
# =============================================================================

# -----------------------------------------------------------------------------
# Test 1: Cluster Termination (Auto-Healable)
# -----------------------------------------------------------------------------
# Notebook: test_cluster_termination.py
# Expected: Auto-heal will restart cluster

"""
Test 1: Force Cluster Termination
This simulates a cluster crash/termination
Auto-heal should: Restart the cluster automatically
"""

import os
import sys

print("=" * 80)
print("🧪 TEST 1: Cluster Termination")
print("=" * 80)
print("")
print("This test will force the driver to crash.")
print("Expected behavior:")
print("  1. Job fails with 'Cluster terminated unexpectedly'")
print("  2. Webhook sent to auto-heal system")
print("  3. AI analyzes: error_type = ClusterUnexpectedTermination")
print("  4. Auto-remediation triggered")
print("  5. Cluster restarted automatically")
print("")
print("Triggering cluster termination in 3 seconds...")

import time
time.sleep(3)

# Force driver crash (this will kill the cluster)
os.system("kill -9 1")

# This line will never execute
print("This should not print")

# -----------------------------------------------------------------------------
# Test 2: Out of Memory (Auto-Healable)
# -----------------------------------------------------------------------------
# Notebook: test_out_of_memory.py
# Expected: Auto-heal will scale up cluster

"""
Test 2: Simulate Out of Memory Error
This creates a large dataset that exhausts memory
Auto-heal should: Scale up cluster by 50%
"""

print("=" * 80)
print("🧪 TEST 2: Out of Memory Error")
print("=" * 80)
print("")
print("Creating large dataset to exhaust memory...")

try:
    # Create increasingly large arrays until OOM
    data = []
    for i in range(1000000):
        data.append([0] * 1000000)  # This will cause OOM
        if i % 10 == 0:
            print(f"Iteration {i}, memory usage increasing...")
except MemoryError:
    print("❌ Out of Memory Error triggered!")
    raise

# -----------------------------------------------------------------------------
# Test 3: Library Installation Error (Auto-Healable)
# -----------------------------------------------------------------------------
# Notebook: test_library_error.py
# Expected: Auto-heal will try fallback versions

"""
Test 3: Library Installation Failure
This tries to install a non-existent library version
Auto-heal should: Try fallback versions
"""

print("=" * 80)
print("🧪 TEST 3: Library Installation Error")
print("=" * 80)
print("")
print("This test requires library installation via cluster init script.")
print("Configure your cluster with a library that will fail to install.")
print("")

# In cluster init script, add:
# pip install pandas==999.999.999  # Non-existent version

# For this test, just simulate the error message
raise Exception("Could not find a version that satisfies the requirement pandas==999.999.999")

# -----------------------------------------------------------------------------
# Test 4: Job Timeout (Auto-Healable)
# -----------------------------------------------------------------------------
# Notebook: test_job_timeout.py
# Expected: Auto-heal will retry with longer timeout

"""
Test 4: Job Timeout
This creates a long-running operation that exceeds timeout
Auto-heal should: Retry job
"""

print("=" * 80)
print("🧪 TEST 4: Job Timeout")
print("=" * 80)
print("")
print("Starting long-running operation...")
print("(Set job timeout to 60 seconds for quick test)")

import time

# Sleep for longer than job timeout
for i in range(600):  # 10 minutes
    time.sleep(1)
    if i % 10 == 0:
        print(f"Running for {i} seconds...")

print("Completed (this won't print if timeout occurs)")

# -----------------------------------------------------------------------------
# Test 5: Generic Error (NOT Auto-Healable)
# -----------------------------------------------------------------------------
# Notebook: test_code_error.py
# Expected: Auto-heal will NOT trigger (code error)

"""
Test 5: Code Error (Not Auto-Healable)
This is a code bug that requires manual fix
Auto-heal should: Create ticket but NOT auto-remediate
"""

print("=" * 80)
print("🧪 TEST 5: Code Error (Not Auto-Healable)")
print("=" * 80)
print("")
print("This error requires manual code fix.")
print("Expected behavior:")
print("  1. Job fails")
print("  2. Webhook sent to auto-heal system")
print("  3. AI analyzes: auto_heal_possible = false")
print("  4. Ticket created but NO auto-remediation")
print("  5. Jira ticket created for manual intervention")
print("")

# Code bug - dividing by zero
result = 10 / 0

# -----------------------------------------------------------------------------
# Test 6: Permission Error (NOT Auto-Healable)
# -----------------------------------------------------------------------------
# Notebook: test_permission_error.py
# Expected: Auto-heal will NOT trigger (security)

"""
Test 6: Permission Error (Not Auto-Healable)
This simulates access denied to a table
Auto-heal should: Create ticket but NOT auto-remediate (security)
"""

print("=" * 80)
print("🧪 TEST 6: Permission Error (Not Auto-Healable)")
print("=" * 80)
print("")

from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

# Try to access a table you don't have permissions to
try:
    df = spark.sql("SELECT * FROM restricted_production_table")
    df.show()
except Exception as e:
    print(f"❌ Permission denied: {e}")
    raise

# -----------------------------------------------------------------------------
# Test 7: Mixed Success/Failure (Auto-Healable on Retry)
# -----------------------------------------------------------------------------
# Notebook: test_transient_error.py
# Expected: Auto-heal will retry and succeed

"""
Test 7: Transient Network Error
This simulates a temporary network issue
Auto-heal should: Retry and succeed
"""

print("=" * 80)
print("🧪 TEST 7: Transient Network Error")
print("=" * 80)
print("")

import random
import time

# Simulate transient error (succeeds on retry)
attempt_file = "/dbfs/tmp/auto_heal_test_attempt.txt"

try:
    with open(attempt_file, "r") as f:
        attempt = int(f.read())
except:
    attempt = 1

print(f"Attempt #{attempt}")

if attempt < 2:
    # First attempt fails
    with open(attempt_file, "w") as f:
        f.write(str(attempt + 1))
    raise Exception("GatewayTimeout: Connection timeout after 30 seconds")
else:
    # Second attempt succeeds
    print("✅ Success on retry!")
    import os
    if os.path.exists(attempt_file):
        os.remove(attempt_file)

# -----------------------------------------------------------------------------
# MASTER TEST SCRIPT (Run this in Databricks)
# -----------------------------------------------------------------------------
"""
Master Test Script - Run ALL tests sequentially

This script tests all auto-heal scenarios in order:
1. Auto-healable errors (cluster, OOM, timeout, etc.)
2. Non-auto-healable errors (code bugs, permissions)
3. Transient errors (succeed on retry)

After each test, check:
- Dashboard: http://localhost:8000/dashboard
- Audit trail: sqlite3 data/tickets.db "SELECT * FROM audit_trail WHERE action LIKE 'Auto-Remediation%'"
"""

print("=" * 80)
print("🧪 AUTO-HEAL SYSTEM - MASTER TEST SUITE")
print("=" * 80)
print("")
print("This will test all auto-heal scenarios.")
print("")
print("BEFORE RUNNING:")
print("1. Make sure auto-heal system is running")
print("2. Make sure ngrok is tunneling to localhost:8000")
print("3. Make sure webhooks are configured for this job")
print("")
print("SELECT TEST TO RUN:")
print("1 = Cluster Termination (auto-healable)")
print("2 = Out of Memory (auto-healable)")
print("3 = Library Error (auto-healable)")
print("4 = Job Timeout (auto-healable)")
print("5 = Code Error (NOT auto-healable)")
print("6 = Permission Error (NOT auto-healable)")
print("7 = Transient Error (auto-healable, succeeds on retry)")
print("")

# Get test number from widget or job parameter
dbutils.widgets.text("test_number", "1", "Test Number (1-7)")
test_number = int(dbutils.widgets.get("test_number"))

print(f"Running Test #{test_number}...")
print("")

if test_number == 1:
    print("🧪 TEST 1: Cluster Termination")
    import os
    os.system("kill -9 1")

elif test_number == 2:
    print("🧪 TEST 2: Out of Memory")
    data = []
    for i in range(1000000):
        data.append([0] * 1000000)

elif test_number == 3:
    print("🧪 TEST 3: Library Error")
    raise Exception("Could not find a version that satisfies the requirement pandas==999.999.999")

elif test_number == 4:
    print("🧪 TEST 4: Job Timeout")
    import time
    time.sleep(600)

elif test_number == 5:
    print("🧪 TEST 5: Code Error (Not Auto-Healable)")
    result = 10 / 0

elif test_number == 6:
    print("🧪 TEST 6: Permission Error (Not Auto-Healable)")
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.getOrCreate()
    df = spark.sql("SELECT * FROM nonexistent_restricted_table")

elif test_number == 7:
    print("🧪 TEST 7: Transient Error")
    import random
    if random.random() < 0.5:
        raise Exception("GatewayTimeout: Connection timeout")
    else:
        print("✅ Success!")

else:
    print("❌ Invalid test number")

print("")
print("✅ Test completed!")
