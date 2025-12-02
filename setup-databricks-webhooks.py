#!/usr/bin/env python3
"""
Setup Databricks Webhooks for Auto-Remediation

This script configures Databricks jobs to send webhook notifications
to the auto-heal system when failures occur.

Usage:
    python3 setup-databricks-webhooks.py

Requirements:
    pip install databricks-sdk
"""

import os
import sys
from databricks.sdk import WorkspaceClient
from databricks.sdk.service import jobs

# Configuration
DATABRICKS_HOST = os.getenv("DATABRICKS_HOST", "")
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN", "")
WEBHOOK_URL = os.getenv("AUTO_HEAL_WEBHOOK_URL", "http://localhost:8000/databricks-monitor")

if not DATABRICKS_HOST or not DATABRICKS_TOKEN:
    print("❌ Error: DATABRICKS_HOST and DATABRICKS_TOKEN must be set in .env")
    print("\nAdd to .env:")
    print("  DATABRICKS_HOST=https://adb-1234567890123456.7.azuredatabricks.net")
    print("  DATABRICKS_TOKEN=dapi1234567890abcdef...")
    print("  AUTO_HEAL_WEBHOOK_URL=https://your-server.com/databricks-monitor")
    sys.exit(1)

print("🔧 Databricks Auto-Heal Webhook Setup")
print("=" * 50)
print(f"Databricks Host: {DATABRICKS_HOST}")
print(f"Webhook URL: {WEBHOOK_URL}")
print()

# Initialize Databricks client
w = WorkspaceClient(
    host=DATABRICKS_HOST,
    token=DATABRICKS_TOKEN
)

print("📋 Fetching existing jobs...")
all_jobs = list(w.jobs.list())
print(f"Found {len(all_jobs)} jobs")
print()

if not all_jobs:
    print("⚠️  No jobs found. Create a job first in Databricks UI.")
    sys.exit(0)

print("Select jobs to add auto-heal webhooks:")
print()

for idx, job in enumerate(all_jobs, 1):
    print(f"{idx}. {job.settings.name} (ID: {job.job_id})")

print()
print("Enter job numbers (comma-separated, or 'all' for all jobs):")
selection = input("> ").strip()

if selection.lower() == 'all':
    selected_jobs = all_jobs
else:
    indices = [int(x.strip()) - 1 for x in selection.split(',')]
    selected_jobs = [all_jobs[i] for i in indices]

print()
print(f"Adding webhooks to {len(selected_jobs)} jobs...")
print()

for job in selected_jobs:
    job_id = job.job_id
    job_name = job.settings.name

    print(f"🔄 Configuring: {job_name}")

    try:
        # Get current job settings
        current_job = w.jobs.get(job_id)

        # Add webhook notification
        # Note: Databricks SDK uses 'url' in the Webhook object directly
        webhook_notifications = jobs.WebhookNotifications(
            on_failure=[{
                "id": "auto-heal-on-failure",
                "url": WEBHOOK_URL
            }],
            on_duration_warning_threshold_exceeded=[{
                "id": "auto-heal-on-timeout",
                "url": WEBHOOK_URL
            }]
        )

        # Update job with webhook
        w.jobs.update(
            job_id=job_id,
            new_settings=jobs.JobSettings(
                name=current_job.settings.name,
                tasks=current_job.settings.tasks,
                webhook_notifications=webhook_notifications,
                # Preserve existing settings
                email_notifications=current_job.settings.email_notifications,
                timeout_seconds=current_job.settings.timeout_seconds,
                max_concurrent_runs=current_job.settings.max_concurrent_runs,
                schedule=current_job.settings.schedule
            )
        )

        print(f"   ✅ Webhook added to: {job_name}")

    except Exception as e:
        print(f"   ❌ Failed to update {job_name}: {e}")

print()
print("🎉 Setup complete!")
print()
print("📝 Next steps:")
print("1. Start your auto-heal system:")
print("   ./quick-start-auto-heal.sh")
print()
print("2. Trigger a test job failure in Databricks")
print()
print("3. Watch auto-heal work:")
print("   tail -f logs/autoheal.log")
print()
print("4. Check audit trail:")
print("   sqlite3 data/tickets.db 'SELECT * FROM audit_trail ORDER BY timestamp DESC LIMIT 10'")
