"""
Azure Function: Databricks Cluster Event Monitor
Polls Databricks Events API every 5 minutes for cluster failures
"""

import os
import json
import logging
import requests
from datetime import datetime, timedelta
import azure.functions as func

# Configuration from environment variables
DATABRICKS_HOST = os.getenv("DATABRICKS_HOST")
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN")
FASTAPI_URL = os.getenv("FASTAPI_URL")
POLLING_INTERVAL_MINUTES = int(os.getenv("POLLING_INTERVAL_MINUTES", "5"))

# State management (simple in-memory - for production use Azure Storage/Redis)
last_processed_timestamp = None


def main(mytimer: func.TimerRequest) -> None:
    """
    Timer trigger function that runs every 5 minutes
    """
    global last_processed_timestamp

    utc_timestamp = datetime.utcnow().replace(tzinfo=None).isoformat()

    logging.info(f"Databricks Monitor function started at {utc_timestamp}")

    # Validate configuration
    if not DATABRICKS_HOST or not DATABRICKS_TOKEN or not FASTAPI_URL:
        logging.error("Missing required configuration. Check app settings.")
        logging.error(f"DATABRICKS_HOST: {DATABRICKS_HOST}")
        logging.error(f"FASTAPI_URL: {FASTAPI_URL}")
        logging.error(f"DATABRICKS_TOKEN: {'Set' if DATABRICKS_TOKEN else 'Missing'}")
        return

    # Calculate time window for events
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(minutes=POLLING_INTERVAL_MINUTES + 1)  # +1 to avoid gaps

    # Convert to milliseconds (Databricks API format)
    start_time_ms = int(start_time.timestamp() * 1000)
    end_time_ms = int(end_time.timestamp() * 1000)

    logging.info(f"Querying events from {start_time} to {end_time}")

    # Get cluster events from Databricks
    events = get_cluster_events(start_time_ms, end_time_ms)

    if events is None:
        logging.error("Failed to retrieve cluster events")
        return

    logging.info(f"Retrieved {len(events)} events from Databricks")

    # Filter for error events only
    error_events = filter_error_events(events)

    logging.info(f"Filtered to {len(error_events)} error events")

    # Send each error to FastAPI
    for event in error_events:
        send_to_fastapi(event)

    logging.info(f"Databricks Monitor completed. Processed {len(error_events)} errors.")


def get_cluster_events(start_time_ms, end_time_ms):
    """
    Get cluster events from Databricks Events API
    """
    url = f"{DATABRICKS_HOST}/api/2.0/clusters/events"

    headers = {
        "Authorization": f"Bearer {DATABRICKS_TOKEN}",
        "Content-Type": "application/json"
    }

    # Request body
    data = {
        "start_time": start_time_ms,
        "end_time": end_time_ms,
        "event_types": [
            "TERMINATING",
            "TERMINATED",
            "FAILED_TO_START",
            "RESTARTING"
        ],
        "limit": 500
    }

    try:
        logging.info(f"Calling Databricks Events API: {url}")
        response = requests.post(url, headers=headers, json=data, timeout=30)

        if response.status_code == 200:
            result = response.json()
            events = result.get("events", [])
            logging.info(f"Successfully retrieved {len(events)} events")
            return events
        else:
            logging.error(f"Databricks API error: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        logging.error(f"Exception calling Databricks API: {str(e)}")
        return None


def filter_error_events(events):
    """
    Filter events to keep only actual errors (not normal terminations)
    """
    error_events = []

    for event in events:
        event_type = event.get("type")
        cluster_id = event.get("cluster_id", "unknown")

        # Check if this is an error event
        is_error = False

        # FAILED_TO_START is always an error
        if event_type == "FAILED_TO_START":
            is_error = True
            logging.info(f"Event {event_type} for cluster {cluster_id}: FAILED_TO_START")

        # TERMINATED/TERMINATING - check if it has error reason
        elif event_type in ["TERMINATED", "TERMINATING"]:
            reason = event.get("reason", {})
            reason_code = reason.get("code", "")
            reason_type = reason.get("type", "")

            # Skip user-initiated terminations
            if reason_code == "USER_REQUEST" or reason_type == "CUSTOMER_INITIATED":
                logging.debug(f"Skipping user-initiated termination for cluster {cluster_id}")
                continue

            # Skip job-related events (we have job webhooks for those)
            if "job_id" in event or "run_id" in event:
                logging.debug(f"Skipping job-related event for cluster {cluster_id}")
                continue

            # Keep error terminations
            if reason_type in ["ERROR", "CLOUD_FAILURE", "SERVICE_FAULT"]:
                is_error = True
                logging.info(f"Event {event_type} for cluster {cluster_id}: {reason_code} ({reason_type})")

        if is_error:
            error_events.append(event)

    return error_events


def send_to_fastapi(event):
    """
    Send error event to FastAPI endpoint in webhook format
    """
    # Extract cluster details
    cluster_id = event.get("cluster_id", "unknown")
    event_type = event.get("type")
    timestamp = event.get("timestamp", 0)

    # Get cluster details from event
    cluster_info = {
        "cluster_id": cluster_id,
        "cluster_name": event.get("cluster_name", "Unknown"),
        "state": event.get("state", event_type),
        "state_message": event.get("state_message", "")
    }

    # Add termination reason if present
    if "reason" in event:
        cluster_info["termination_reason"] = event["reason"]

    # Format as webhook payload (same format Databricks webhooks use)
    payload = {
        "event": f"cluster.{event_type.lower()}",
        "event_type": event_type,
        "timestamp": timestamp,
        "cluster": cluster_info
    }

    # Send to FastAPI
    try:
        logging.info(f"Sending event to FastAPI: {FASTAPI_URL}")
        logging.info(f"Cluster: {cluster_info['cluster_name']} ({cluster_id})")

        response = requests.post(
            FASTAPI_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )

        if response.status_code == 200:
            logging.info(f"✓ Successfully sent event to FastAPI")
            logging.info(f"  Response: {response.text[:200]}")
        else:
            logging.error(f"✗ FastAPI returned error: {response.status_code}")
            logging.error(f"  Response: {response.text[:500]}")

    except Exception as e:
        logging.error(f"✗ Exception sending to FastAPI: {str(e)}")
