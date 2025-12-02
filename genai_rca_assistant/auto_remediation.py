"""
Auto-Remediation Engine for AIOps RCA System

This module provides automated recovery capabilities for common infrastructure failures:
- Retry with exponential backoff
- Cluster restart/scale-out
- Library reinstallation with version fallback
- Pipeline retry with upstream dependency checks

Supported Error Types:
    ADF: GatewayTimeout, HttpConnectionFailed, ThrottlingError, UserErrorSourceBlobNotExists
    Databricks: ClusterStartFailure, TimeoutError, LibraryInstallationError, DriverNotResponding
"""

import os
import logging
import asyncio
import json
from typing import Dict, Optional, Any, List
from datetime import datetime, timezone
import requests

logger = logging.getLogger("aiops_rca.auto_remediation")

# =============================================================================
# RETRY CONFIGURATION - Maps error types to retry strategies
# =============================================================================

RETRY_ELIGIBLE_ERRORS: Dict[str, Dict[str, Any]] = {
    # Azure Data Factory Errors
    "GatewayTimeout": {
        "max_retries": 3,
        "backoff_seconds": [10, 30, 60],
        "playbook_type": "retry_pipeline",
        "description": "Gateway timeout - retry with exponential backoff"
    },
    "HttpConnectionFailed": {
        "max_retries": 3,
        "backoff_seconds": [5, 15, 30],
        "playbook_type": "retry_pipeline",
        "description": "HTTP connection failed - retry with connection reset"
    },
    "ThrottlingError": {
        "max_retries": 5,
        "backoff_seconds": [30, 60, 120, 300, 600],
        "playbook_type": "retry_pipeline",
        "description": "Rate limited - retry with delay based on Retry-After header"
    },
    "InternalServerError": {
        "max_retries": 2,
        "backoff_seconds": [30, 60],
        "playbook_type": "retry_pipeline",
        "description": "Internal server error - retry after delay"
    },
    "UserErrorSourceBlobNotExists": {
        "max_retries": 3,
        "backoff_seconds": [60, 120, 300],
        "playbook_type": "rerun_upstream",
        "description": "Source blob missing - check upstream and retry"
    },

    # Databricks Errors
    "DatabricksClusterStartFailure": {
        "max_retries": 2,
        "backoff_seconds": [60, 120],
        "playbook_type": "restart_cluster",
        "description": "Cluster failed to start - restart with fallback node type"
    },
    "DatabricksTimeoutError": {
        "max_retries": 2,
        "backoff_seconds": [30, 60],
        "playbook_type": "retry_job",
        "description": "Job timeout - retry with increased timeout"
    },
    "DatabricksDriverNotResponding": {
        "max_retries": 1,
        "backoff_seconds": [60],
        "playbook_type": "restart_cluster",
        "description": "Driver not responding - restart cluster"
    },
    "DatabricksLibraryInstallationError": {
        "max_retries": 2,
        "backoff_seconds": [30, 60],
        "playbook_type": "reinstall_libraries",
        "description": "Library install failed - retry with version fallback"
    },
    "DatabricksResourceExhausted": {
        "max_retries": 2,
        "backoff_seconds": [60, 120],
        "playbook_type": "scale_cluster",
        "description": "Resources exhausted - scale up cluster or retry with smaller batch"
    },
    "ClusterUnexpectedTermination": {
        "max_retries": 2,
        "backoff_seconds": [60, 120],
        "playbook_type": "restart_cluster",
        "description": "Cluster terminated unexpectedly - auto-restart"
    },
}

# =============================================================================
# PLAYBOOK REGISTRY - Maps playbook types to environment variable keys
# =============================================================================

PLAYBOOK_ENV_VARS = {
    "retry_pipeline": "PLAYBOOK_RETRY_PIPELINE",
    "rerun_upstream": "PLAYBOOK_RERUN_UPSTREAM",
    "restart_cluster": "PLAYBOOK_RESTART_CLUSTER",
    "retry_job": "PLAYBOOK_RETRY_JOB",
    "reinstall_libraries": "PLAYBOOK_REINSTALL_LIBRARIES",
    "scale_cluster": "PLAYBOOK_SCALE_CLUSTER",
    "check_permissions": "PLAYBOOK_CHECK_PERMISSIONS",
}


# =============================================================================
# CORE AUTO-REMEDIATION FUNCTION
# =============================================================================

async def attempt_auto_remediation(
    ticket_id: str,
    error_type: str,
    metadata: Dict[str, Any],
    db_query_func,
    db_execute_func,
    log_audit_func
) -> bool:
    """
    Attempt auto-remediation for eligible error types

    Args:
        ticket_id: Ticket ID to associate remediation with
        error_type: Type of error (must match RETRY_ELIGIBLE_ERRORS keys)
        metadata: Error context (run_id, pipeline, cluster_id, etc.)
        db_query_func: Function to query database
        db_execute_func: Function to execute database updates
        log_audit_func: Function to log audit trail

    Returns:
        True if remediation was attempted, False otherwise
    """
    logger.info(f"🤖 AUTO-REMEDIATION: Evaluating {error_type} for ticket {ticket_id}")

    # Check if error type is eligible for auto-remediation
    if error_type not in RETRY_ELIGIBLE_ERRORS:
        logger.info(f"❌ No auto-remediation available for error type: {error_type}")
        return False

    config = RETRY_ELIGIBLE_ERRORS[error_type]
    playbook_type = config.get("playbook_type")

    # Get playbook URL from environment
    playbook_env_var = PLAYBOOK_ENV_VARS.get(playbook_type)
    if not playbook_env_var:
        logger.error(f"❌ No environment variable mapping for playbook type: {playbook_type}")
        return False

    playbook_url = os.getenv(playbook_env_var)
    if not playbook_url:
        logger.warning(f"⚠️ Playbook URL not configured: {playbook_env_var}")
        log_audit_func(
            ticket_id=ticket_id,
            action="Auto-Remediation Skipped",
            run_id=metadata.get("run_id"),
            details=f"Playbook {playbook_type} not configured in environment"
        )
        return False

    max_retries = config.get("max_retries", 1)
    backoff_seconds = config.get("backoff_seconds", [30])

    # Check retry count to prevent infinite loops
    run_id = metadata.get("run_id")
    retry_count = 0

    if run_id:
        result = db_query_func(
            "SELECT COUNT(*) as count FROM audit_trail WHERE run_id = :run_id AND action = 'Auto-Remediation Attempted'",
            {"run_id": run_id},
            one=True
        )
        retry_count = result.get("count", 0) if result else 0

        if retry_count >= max_retries:
            logger.warning(f"🛑 Max retries ({max_retries}) reached for run_id {run_id}. Manual intervention required.")
            log_audit_func(
                ticket_id=ticket_id,
                action="Auto-Remediation Max Retries Reached",
                run_id=run_id,
                details=f"Attempted {retry_count} times. Error: {error_type}. Manual intervention required."
            )
            return False

    # Determine backoff delay for this attempt
    current_attempt = retry_count
    delay = backoff_seconds[min(current_attempt, len(backoff_seconds) - 1)]

    logger.info(f"🔄 AUTO-REMEDIATION: Attempting {config['description']}")
    logger.info(f"📊 Attempt {current_attempt + 1}/{max_retries}, Backoff: {delay}s")

    # Log the attempt
    log_audit_func(
        ticket_id=ticket_id,
        action="Auto-Remediation Attempted",
        run_id=run_id,
        details=json.dumps({
            "error_type": error_type,
            "attempt": current_attempt + 1,
            "max_retries": max_retries,
            "backoff_seconds": delay,
            "playbook_type": playbook_type,
            "playbook_url": playbook_url[:50] + "..." if len(playbook_url) > 50 else playbook_url
        })
    )

    # Wait for backoff period (in production, this could be a scheduled task)
    logger.info(f"⏳ Waiting {delay} seconds before triggering playbook...")
    await asyncio.sleep(delay)

    # Prepare playbook payload
    playbook_payload = {
        "ticket_id": ticket_id,
        "error_type": error_type,
        "metadata": metadata,
        "retry_attempt": current_attempt + 1,
        "max_retries": max_retries,
        "timestamp": datetime.utcnow().isoformat()
    }

    # Trigger the playbook
    try:
        logger.info(f"🚀 Triggering playbook: {playbook_type}")
        response = await asyncio.to_thread(
            _http_post_with_retries,
            playbook_url,
            playbook_payload,
            timeout=60,
            retries=3,
            backoff=1.5
        )

        if response.status_code == 200:
            result = response.json()
            new_run_id = result.get("new_run_id") or result.get("run_id")

            logger.info(f"✅ AUTO-REMEDIATION: Playbook executed successfully!")
            if new_run_id:
                logger.info(f"🆕 New run ID: {new_run_id}")

            log_audit_func(
                ticket_id=ticket_id,
                action="Auto-Remediation Succeeded",
                run_id=new_run_id or run_id,
                details=json.dumps({
                    "playbook_type": playbook_type,
                    "new_run_id": new_run_id,
                    "response": result
                })
            )

            # Update ticket with new run_id if different
            if new_run_id and run_id and new_run_id != run_id:
                db_execute_func(
                    "UPDATE tickets SET run_id = :new_run_id WHERE id = :ticket_id",
                    {"new_run_id": new_run_id, "ticket_id": ticket_id}
                )
                logger.info(f"📝 Updated ticket {ticket_id} with new run_id: {new_run_id}")

            return True
        else:
            logger.error(f"❌ AUTO-REMEDIATION: Playbook failed. Status: {response.status_code}")
            logger.error(f"Response: {response.text[:500]}")
            log_audit_func(
                ticket_id=ticket_id,
                action="Auto-Remediation Failed",
                run_id=run_id,
                details=f"Playbook returned {response.status_code}: {response.text[:500]}"
            )
            return False

    except Exception as e:
        logger.error(f"❌ AUTO-REMEDIATION: Exception during playbook execution: {e}")
        log_audit_func(
            ticket_id=ticket_id,
            action="Auto-Remediation Failed",
            run_id=run_id,
            details=f"Exception: {str(e)}"
        )
        return False


# =============================================================================
# HTTP CLIENT WITH RETRIES
# =============================================================================

def _http_post_with_retries(
    url: str,
    payload: Dict[str, Any],
    timeout: int = 60,
    retries: int = 3,
    backoff: float = 1.5
) -> requests.Response:
    """
    Make HTTP POST request with exponential backoff retries

    Args:
        url: Endpoint URL
        payload: JSON payload
        timeout: Request timeout in seconds
        retries: Number of retry attempts
        backoff: Backoff multiplier

    Returns:
        requests.Response object

    Raises:
        requests.exceptions.RequestException if all retries fail
    """
    headers = {"Content-Type": "application/json"}

    for attempt in range(retries):
        try:
            logger.debug(f"HTTP POST attempt {attempt + 1}/{retries} to {url[:50]}...")
            response = requests.post(url, json=payload, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            if attempt < retries - 1:
                wait_time = (backoff ** attempt) * 2
                logger.warning(f"Request failed (attempt {attempt + 1}): {e}. Retrying in {wait_time}s...")
                import time
                time.sleep(wait_time)
            else:
                logger.error(f"All {retries} attempts failed for {url}")
                raise


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_supported_error_types() -> List[str]:
    """Return list of error types that support auto-remediation"""
    return list(RETRY_ELIGIBLE_ERRORS.keys())


def get_error_config(error_type: str) -> Optional[Dict[str, Any]]:
    """Get configuration for a specific error type"""
    return RETRY_ELIGIBLE_ERRORS.get(error_type)


def is_auto_remediable(error_type: str) -> bool:
    """Check if an error type supports auto-remediation"""
    return error_type in RETRY_ELIGIBLE_ERRORS


def get_playbook_url(error_type: str) -> Optional[str]:
    """Get playbook URL for an error type"""
    config = RETRY_ELIGIBLE_ERRORS.get(error_type)
    if not config:
        return None

    playbook_type = config.get("playbook_type")
    playbook_env_var = PLAYBOOK_ENV_VARS.get(playbook_type)

    if not playbook_env_var:
        return None

    return os.getenv(playbook_env_var)


# =============================================================================
# STATISTICS AND MONITORING
# =============================================================================

def get_remediation_stats(db_query_func, days: int = 7) -> Dict[str, Any]:
    """
    Get auto-remediation statistics for monitoring

    Args:
        db_query_func: Function to query database
        days: Number of days to look back

    Returns:
        Dictionary with success rate, attempt count, etc.
    """
    query = """
    SELECT
        action,
        COUNT(*) as count
    FROM audit_trail
    WHERE action LIKE 'Auto-Remediation%'
        AND timestamp >= datetime('now', '-' || :days || ' days')
    GROUP BY action
    """

    results = db_query_func(query, {"days": days})

    attempted = 0
    succeeded = 0
    failed = 0
    max_retries = 0

    for row in results:
        action = row.get("action", "")
        count = row.get("count", 0)

        if action == "Auto-Remediation Attempted":
            attempted = count
        elif action == "Auto-Remediation Succeeded":
            succeeded = count
        elif action == "Auto-Remediation Failed":
            failed = count
        elif action == "Auto-Remediation Max Retries Reached":
            max_retries = count

    success_rate = (succeeded / attempted * 100) if attempted > 0 else 0

    return {
        "period_days": days,
        "total_attempts": attempted,
        "succeeded": succeeded,
        "failed": failed,
        "max_retries_reached": max_retries,
        "success_rate": round(success_rate, 2),
        "supported_error_types": len(RETRY_ELIGIBLE_ERRORS)
    }
