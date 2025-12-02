"""
Recovery Playbook Handlers for Auto-Remediation

This module implements concrete recovery actions that can be triggered by:
1. Auto-remediation engine directly
2. Azure Logic Apps (via HTTP triggers)
3. Azure Functions
4. Manual intervention through API

Implemented Playbooks:
- retry_adf_pipeline: Retry Azure Data Factory pipeline
- restart_databricks_cluster: Restart a Databricks cluster
- scale_databricks_cluster: Scale up cluster resources
- retry_databricks_job: Retry a failed Databricks job
- reinstall_databricks_libraries: Reinstall libraries with version fallback
- check_upstream_dependencies: Check if upstream pipelines are ready
"""

import os
import logging
import asyncio
from typing import Dict, Optional, Any, List, Tuple
from datetime import datetime
import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger("aiops_rca.playbooks")

# =============================================================================
# AZURE DATA FACTORY PLAYBOOKS
# =============================================================================

async def retry_adf_pipeline(
    pipeline_name: str,
    factory_name: Optional[str] = None,
    resource_group: Optional[str] = None,
    subscription_id: Optional[str] = None,
    access_token: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Retry an Azure Data Factory pipeline

    Args:
        pipeline_name: Name of the pipeline to retry
        factory_name: ADF factory name (from env if not provided)
        resource_group: Azure resource group (from env if not provided)
        subscription_id: Azure subscription ID (from env if not provided)
        access_token: Azure access token (from env if not provided)
        parameters: Pipeline parameters to pass

    Returns:
        Tuple of (success: bool, result: Dict)
    """
    factory_name = factory_name or os.getenv("AZURE_ADF_NAME")
    resource_group = resource_group or os.getenv("AZURE_RESOURCE_GROUP")
    subscription_id = subscription_id or os.getenv("AZURE_SUBSCRIPTION_ID")
    access_token = access_token or os.getenv("AZURE_ACCESS_TOKEN")

    if not all([factory_name, resource_group, subscription_id, access_token]):
        logger.error("❌ Missing Azure credentials for ADF pipeline retry")
        return False, {"error": "Missing Azure credentials"}

    # Azure Management API endpoint
    url = (
        f"https://management.azure.com/subscriptions/{subscription_id}/"
        f"resourceGroups/{resource_group}/"
        f"providers/Microsoft.DataFactory/factories/{factory_name}/"
        f"pipelines/{pipeline_name}/createRun?api-version=2018-06-01"
    )

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    payload = {"parameters": parameters or {}}

    try:
        logger.info(f"🔄 Retrying ADF pipeline: {pipeline_name}")
        response = await asyncio.to_thread(
            requests.post, url, json=payload, headers=headers, timeout=30
        )

        if response.status_code in (200, 202):
            result = response.json()
            run_id = result.get("runId")
            logger.info(f"✅ Successfully triggered pipeline retry. New run ID: {run_id}")
            return True, {"new_run_id": run_id, "pipeline": pipeline_name}
        else:
            logger.error(f"❌ Failed to retry pipeline: {response.status_code} - {response.text}")
            return False, {"error": response.text, "status_code": response.status_code}

    except Exception as e:
        logger.error(f"❌ Exception during pipeline retry: {e}")
        return False, {"error": str(e)}


async def check_upstream_adf_pipeline(
    upstream_pipeline_name: str,
    factory_name: Optional[str] = None,
    resource_group: Optional[str] = None,
    subscription_id: Optional[str] = None,
    access_token: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Check status of upstream ADF pipeline

    Returns:
        Tuple of (is_ready: bool, status: str)
    """
    factory_name = factory_name or os.getenv("AZURE_ADF_NAME")
    resource_group = resource_group or os.getenv("AZURE_RESOURCE_GROUP")
    subscription_id = subscription_id or os.getenv("AZURE_SUBSCRIPTION_ID")
    access_token = access_token or os.getenv("AZURE_ACCESS_TOKEN")

    if not all([factory_name, resource_group, subscription_id, access_token]):
        logger.error("❌ Missing Azure credentials")
        return False, "UNKNOWN"

    # Query pipeline runs
    url = (
        f"https://management.azure.com/subscriptions/{subscription_id}/"
        f"resourceGroups/{resource_group}/"
        f"providers/Microsoft.DataFactory/factories/{factory_name}/"
        f"queryPipelineRuns?api-version=2018-06-01"
    )

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # Get last run of the upstream pipeline
    from datetime import datetime, timedelta
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=24)

    payload = {
        "lastUpdatedAfter": start_time.isoformat() + "Z",
        "lastUpdatedBefore": end_time.isoformat() + "Z",
        "filters": [
            {
                "operand": "PipelineName",
                "operator": "Equals",
                "values": [upstream_pipeline_name]
            }
        ]
    }

    try:
        response = await asyncio.to_thread(
            requests.post, url, json=payload, headers=headers, timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            runs = data.get("value", [])
            if runs:
                # Get most recent run
                latest_run = runs[0]
                status = latest_run.get("status", "Unknown")
                logger.info(f"📊 Upstream pipeline {upstream_pipeline_name} status: {status}")
                return status == "Succeeded", status
            else:
                logger.warning(f"⚠️ No recent runs found for {upstream_pipeline_name}")
                return False, "NO_RUNS"
        else:
            logger.error(f"❌ Failed to check pipeline status: {response.status_code}")
            return False, "ERROR"

    except Exception as e:
        logger.error(f"❌ Exception checking upstream pipeline: {e}")
        return False, "EXCEPTION"


# =============================================================================
# DATABRICKS CLUSTER PLAYBOOKS
# =============================================================================

async def restart_databricks_cluster(
    cluster_id: str,
    host: Optional[str] = None,
    token: Optional[str] = None,
    wait_for_ready: bool = True,
    timeout_minutes: int = 10
) -> Tuple[bool, Dict[str, Any]]:
    """
    Restart a Databricks cluster

    Args:
        cluster_id: Cluster ID to restart
        host: Databricks host URL (from env if not provided)
        token: Databricks access token (from env if not provided)
        wait_for_ready: Wait for cluster to be in RUNNING state
        timeout_minutes: Max wait time for cluster to start

    Returns:
        Tuple of (success: bool, result: Dict)
    """
    host = (host or os.getenv("DATABRICKS_HOST", "")).rstrip('/')
    token = token or os.getenv("DATABRICKS_TOKEN")

    if not host or not token:
        logger.error("❌ Missing Databricks credentials")
        return False, {"error": "Missing Databricks credentials"}

    # Check current cluster state
    state = await _get_cluster_state(cluster_id, host, token)
    logger.info(f"📊 Current cluster state: {state}")

    # If already running, no need to restart
    if state == "RUNNING":
        logger.info(f"✅ Cluster {cluster_id} is already running")
        return True, {"status": "already_running", "cluster_id": cluster_id}

    # If pending, wait for it
    if state == "PENDING":
        logger.info(f"⏳ Cluster {cluster_id} is already starting...")
        if wait_for_ready:
            success = await _wait_for_cluster_state(cluster_id, "RUNNING", host, token, timeout_minutes)
            return success, {"status": "started", "cluster_id": cluster_id}
        return True, {"status": "pending", "cluster_id": cluster_id}

    # Start the cluster
    url = f"{host}/api/2.0/clusters/start"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {"cluster_id": cluster_id}

    try:
        logger.info(f"🔄 Starting Databricks cluster: {cluster_id}")
        response = await asyncio.to_thread(
            requests.post, url, json=payload, headers=headers, timeout=30
        )

        if response.status_code == 200:
            logger.info(f"✅ Cluster start request accepted")

            if wait_for_ready:
                logger.info(f"⏳ Waiting for cluster to be RUNNING (timeout: {timeout_minutes}m)...")
                success = await _wait_for_cluster_state(cluster_id, "RUNNING", host, token, timeout_minutes)
                if success:
                    logger.info(f"✅ Cluster {cluster_id} is now RUNNING")
                    return True, {"status": "running", "cluster_id": cluster_id}
                else:
                    logger.error(f"⏰ Timeout waiting for cluster to start")
                    return False, {"error": "Timeout", "cluster_id": cluster_id}

            return True, {"status": "starting", "cluster_id": cluster_id}
        else:
            logger.error(f"❌ Failed to start cluster: {response.status_code} - {response.text}")
            return False, {"error": response.text, "status_code": response.status_code}

    except Exception as e:
        logger.error(f"❌ Exception during cluster restart: {e}")
        return False, {"error": str(e)}


async def scale_databricks_cluster(
    cluster_id: str,
    target_workers: Optional[int] = None,
    scale_percent: float = 1.5,
    host: Optional[str] = None,
    token: Optional[str] = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Scale up a Databricks cluster

    Args:
        cluster_id: Cluster ID to scale
        target_workers: Target number of workers (if None, scales by scale_percent)
        scale_percent: Scale multiplier (default 1.5 = 50% increase)
        host: Databricks host URL
        token: Databricks access token

    Returns:
        Tuple of (success: bool, result: Dict)
    """
    host = (host or os.getenv("DATABRICKS_HOST", "")).rstrip('/')
    token = token or os.getenv("DATABRICKS_TOKEN")

    if not host or not token:
        logger.error("❌ Missing Databricks credentials")
        return False, {"error": "Missing Databricks credentials"}

    # Get current cluster configuration
    cluster_config = await _get_cluster_config(cluster_id, host, token)
    if not cluster_config:
        return False, {"error": "Failed to get cluster config"}

    current_workers = cluster_config.get("num_workers", 2)
    autoscale_config = cluster_config.get("autoscale", {})
    max_workers = autoscale_config.get("max_workers", current_workers * 2)

    # Calculate new worker count
    if target_workers:
        new_workers = min(target_workers, max_workers)
    else:
        new_workers = min(int(current_workers * scale_percent), max_workers)

    if new_workers <= current_workers:
        logger.info(f"ℹ️ Cluster already at maximum capacity ({current_workers} workers)")
        return True, {"status": "max_capacity", "workers": current_workers}

    logger.info(f"📈 Scaling cluster from {current_workers} to {new_workers} workers")

    # Update cluster configuration
    url = f"{host}/api/2.0/clusters/edit"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Preserve existing config, only update num_workers
    payload = {
        "cluster_id": cluster_id,
        "num_workers": new_workers,
        "spark_version": cluster_config.get("spark_version"),
        "node_type_id": cluster_config.get("node_type_id"),
    }

    try:
        response = await asyncio.to_thread(
            requests.post, url, json=payload, headers=headers, timeout=30
        )

        if response.status_code == 200:
            logger.info(f"✅ Successfully scaled cluster to {new_workers} workers")
            return True, {
                "status": "scaled",
                "previous_workers": current_workers,
                "new_workers": new_workers,
                "cluster_id": cluster_id
            }
        else:
            logger.error(f"❌ Failed to scale cluster: {response.status_code} - {response.text}")
            return False, {"error": response.text, "status_code": response.status_code}

    except Exception as e:
        logger.error(f"❌ Exception during cluster scaling: {e}")
        return False, {"error": str(e)}


# =============================================================================
# DATABRICKS JOB PLAYBOOKS
# =============================================================================

async def retry_databricks_job(
    job_id: str,
    host: Optional[str] = None,
    token: Optional[str] = None,
    notebook_params: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Retry a Databricks job

    Args:
        job_id: Job ID to retry
        host: Databricks host URL
        token: Databricks access token
        notebook_params: Parameters to pass to the job

    Returns:
        Tuple of (success: bool, result: Dict)
    """
    host = (host or os.getenv("DATABRICKS_HOST", "")).rstrip('/')
    token = token or os.getenv("DATABRICKS_TOKEN")

    if not host or not token:
        logger.error("❌ Missing Databricks credentials")
        return False, {"error": "Missing Databricks credentials"}

    url = f"{host}/api/2.1/jobs/run-now"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "job_id": int(job_id)
    }

    if notebook_params:
        payload["notebook_params"] = notebook_params

    try:
        logger.info(f"🔄 Retrying Databricks job: {job_id}")
        response = await asyncio.to_thread(
            requests.post, url, json=payload, headers=headers, timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            run_id = result.get("run_id")
            logger.info(f"✅ Successfully triggered job retry. New run ID: {run_id}")
            return True, {"new_run_id": run_id, "job_id": job_id}
        else:
            logger.error(f"❌ Failed to retry job: {response.status_code} - {response.text}")
            return False, {"error": response.text, "status_code": response.status_code}

    except Exception as e:
        logger.error(f"❌ Exception during job retry: {e}")
        return False, {"error": str(e)}


# =============================================================================
# DATABRICKS LIBRARY PLAYBOOKS
# =============================================================================

# Library version fallback registry
LIBRARY_VERSION_FALLBACKS = {
    "pandas": ["2.1.4", "2.1.0", "2.0.3", "1.5.3"],
    "numpy": ["1.26.3", "1.24.3", "1.23.5", "1.22.4"],
    "pyspark": ["3.5.0", "3.4.1", "3.4.0", "3.3.2"],
    "scikit-learn": ["1.4.0", "1.3.2", "1.3.0", "1.2.2"],
    "pyarrow": ["14.0.2", "14.0.1", "13.0.0", "12.0.1"],
}


async def reinstall_databricks_libraries(
    cluster_id: str,
    library_spec: str,
    host: Optional[str] = None,
    token: Optional[str] = None,
    try_fallback_versions: bool = True
) -> Tuple[bool, Dict[str, Any]]:
    """
    Reinstall a library on Databricks cluster with version fallback

    Args:
        cluster_id: Cluster ID
        library_spec: Library specification (e.g., "pandas==2.2.0" or "pandas")
        host: Databricks host URL
        token: Databricks access token
        try_fallback_versions: Try fallback versions if installation fails

    Returns:
        Tuple of (success: bool, result: Dict)
    """
    host = (host or os.getenv("DATABRICKS_HOST", "")).rstrip('/')
    token = token or os.getenv("DATABRICKS_TOKEN")

    if not host or not token:
        logger.error("❌ Missing Databricks credentials")
        return False, {"error": "Missing Databricks credentials"}

    # Parse library name and version
    library_name, requested_version = _parse_library_spec(library_spec)

    # Try original version first
    success, result = await _install_library(cluster_id, library_name, requested_version, host, token)
    if success:
        return True, result

    # If failed and fallback enabled, try fallback versions
    if try_fallback_versions and library_name in LIBRARY_VERSION_FALLBACKS:
        fallback_versions = LIBRARY_VERSION_FALLBACKS[library_name]
        logger.info(f"🔄 Trying fallback versions for {library_name}: {fallback_versions}")

        for version in fallback_versions:
            if version == requested_version:
                continue  # Skip the version that just failed

            logger.info(f"🔄 Attempting fallback: {library_name}=={version}")
            success, result = await _install_library(cluster_id, library_name, version, host, token)

            if success:
                logger.info(f"✅ Successfully installed fallback version: {library_name}=={version}")
                return True, {
                    **result,
                    "fallback_used": True,
                    "requested_version": requested_version,
                    "installed_version": version
                }

        logger.error(f"❌ All fallback versions failed for {library_name}")
        return False, {"error": "All fallback versions failed"}

    return False, result


async def _install_library(
    cluster_id: str,
    library_name: str,
    version: Optional[str],
    host: str,
    token: str
) -> Tuple[bool, Dict[str, Any]]:
    """Install a specific library version"""
    url = f"{host}/api/2.0/libraries/install"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    package = f"{library_name}=={version}" if version else library_name
    payload = {
        "cluster_id": cluster_id,
        "libraries": [
            {"pypi": {"package": package}}
        ]
    }

    try:
        response = await asyncio.to_thread(
            requests.post, url, json=payload, headers=headers, timeout=30
        )

        if response.status_code == 200:
            logger.info(f"✅ Library install request accepted: {package}")
            return True, {"package": package, "cluster_id": cluster_id}
        else:
            logger.error(f"❌ Failed to install library: {response.text}")
            return False, {"error": response.text, "status_code": response.status_code}

    except Exception as e:
        logger.error(f"❌ Exception during library installation: {e}")
        return False, {"error": str(e)}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

async def _get_cluster_state(cluster_id: str, host: str, token: str) -> str:
    """Get current state of a Databricks cluster"""
    url = f"{host}/api/2.0/clusters/get"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"cluster_id": cluster_id}

    try:
        response = await asyncio.to_thread(
            requests.get, url, headers=headers, params=params, timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("state", "UNKNOWN")
        return "UNKNOWN"
    except Exception:
        return "UNKNOWN"


async def _get_cluster_config(cluster_id: str, host: str, token: str) -> Optional[Dict[str, Any]]:
    """Get cluster configuration"""
    url = f"{host}/api/2.0/clusters/get"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"cluster_id": cluster_id}

    try:
        response = await asyncio.to_thread(
            requests.get, url, headers=headers, params=params, timeout=10
        )
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None


async def _wait_for_cluster_state(
    cluster_id: str,
    desired_state: str,
    host: str,
    token: str,
    timeout_minutes: int
) -> bool:
    """Wait for cluster to reach desired state"""
    max_iterations = timeout_minutes * 6  # Check every 10 seconds

    for i in range(max_iterations):
        state = await _get_cluster_state(cluster_id, host, token)

        if state == desired_state:
            return True
        elif state == "ERROR":
            logger.error(f"❌ Cluster entered ERROR state")
            return False

        await asyncio.sleep(10)

    return False


def _parse_library_spec(library_spec: str) -> Tuple[str, Optional[str]]:
    """
    Parse library specification into name and version

    Examples:
        "pandas==2.2.0" -> ("pandas", "2.2.0")
        "pandas>=2.0.0" -> ("pandas", None)
        "pandas" -> ("pandas", None)
    """
    for separator in ["==", ">=", "<=", "~=", ">", "<"]:
        if separator in library_spec:
            parts = library_spec.split(separator)
            return parts[0].strip(), parts[1].strip() if len(parts) > 1 else None

    return library_spec.strip(), None
