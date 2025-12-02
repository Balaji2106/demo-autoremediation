"""
Auto-Remediation Playbook Server

This is a lightweight HTTP server that exposes the playbook handlers as REST endpoints.
Use this if you want to test auto-remediation without setting up Azure Logic Apps.

Usage:
    python3 playbook_server.py

Endpoints:
    POST /playbooks/retry-pipeline       - Retry ADF pipeline
    POST /playbooks/restart-cluster      - Restart Databricks cluster
    POST /playbooks/retry-job            - Retry Databricks job
    POST /playbooks/scale-cluster        - Scale Databricks cluster
    POST /playbooks/reinstall-libraries  - Reinstall libraries with fallback
    GET  /playbooks/health              - Health check

Then update .env:
    PLAYBOOK_RETRY_PIPELINE=http://localhost:8001/playbooks/retry-pipeline
    PLAYBOOK_RESTART_CLUSTER=http://localhost:8001/playbooks/restart-cluster
    PLAYBOOK_RETRY_JOB=http://localhost:8001/playbooks/retry-job
    PLAYBOOK_SCALE_CLUSTER=http://localhost:8001/playbooks/scale-cluster
    PLAYBOOK_REINSTALL_LIBRARIES=http://localhost:8001/playbooks/reinstall-libraries
"""

import logging
import sys
import os
from typing import Dict, Any

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

# Import playbook handlers
from playbook_handlers import (
    retry_adf_pipeline,
    restart_databricks_cluster,
    retry_databricks_job,
    scale_databricks_cluster,
    reinstall_databricks_libraries,
    check_upstream_adf_pipeline
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("playbook_server")

# Create FastAPI app
app = FastAPI(
    title="Auto-Remediation Playbook Server",
    description="HTTP endpoints for automated recovery playbooks",
    version="1.0.0"
)


# =============================================================================
# ADF PLAYBOOKS
# =============================================================================

@app.post("/playbooks/retry-pipeline")
async def retry_pipeline_endpoint(request: Request):
    """
    Retry an Azure Data Factory pipeline

    Request Body:
    {
        "ticket_id": "ADF-123",
        "error_type": "GatewayTimeout",
        "metadata": {
            "run_id": "abc-123",
            "pipeline": "My_Pipeline",
            "source": "adf"
        }
    }
    """
    try:
        body = await request.json()
        logger.info(f"Retry pipeline playbook triggered for ticket: {body.get('ticket_id')}")

        metadata = body.get('metadata', {})
        pipeline_name = metadata.get('pipeline')

        if not pipeline_name:
            raise HTTPException(status_code=400, detail="Missing pipeline name in metadata")

        # Call playbook handler
        success, result = await retry_adf_pipeline(pipeline_name=pipeline_name)

        if success:
            logger.info(f"✅ Pipeline retry successful: {result}")
            return JSONResponse({
                "status": "success",
                "ticket_id": body.get('ticket_id'),
                **result
            })
        else:
            logger.error(f"❌ Pipeline retry failed: {result}")
            return JSONResponse({
                "status": "error",
                "ticket_id": body.get('ticket_id'),
                **result
            }, status_code=500)

    except Exception as e:
        logger.error(f"Exception in retry-pipeline: {e}")
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)


@app.post("/playbooks/check-upstream")
async def check_upstream_endpoint(request: Request):
    """
    Check if upstream ADF pipeline is ready

    Request Body:
    {
        "ticket_id": "ADF-123",
        "metadata": {
            "upstream_pipeline": "Upstream_Pipeline"
        }
    }
    """
    try:
        body = await request.json()
        metadata = body.get('metadata', {})
        upstream_pipeline = metadata.get('upstream_pipeline')

        if not upstream_pipeline:
            raise HTTPException(status_code=400, detail="Missing upstream_pipeline in metadata")

        is_ready, status = await check_upstream_adf_pipeline(upstream_pipeline)

        return JSONResponse({
            "status": "success",
            "is_ready": is_ready,
            "upstream_status": status,
            "ticket_id": body.get('ticket_id')
        })

    except Exception as e:
        logger.error(f"Exception in check-upstream: {e}")
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)


# =============================================================================
# DATABRICKS CLUSTER PLAYBOOKS
# =============================================================================

@app.post("/playbooks/restart-cluster")
async def restart_cluster_endpoint(request: Request):
    """
    Restart a Databricks cluster

    Request Body:
    {
        "ticket_id": "DBX-123",
        "error_type": "DatabricksClusterStartFailure",
        "metadata": {
            "cluster_id": "1234-567890-abc123",
            "source": "databricks"
        }
    }
    """
    try:
        body = await request.json()
        logger.info(f"Restart cluster playbook triggered for ticket: {body.get('ticket_id')}")

        metadata = body.get('metadata', {})
        cluster_id = metadata.get('cluster_id')

        if not cluster_id:
            raise HTTPException(status_code=400, detail="Missing cluster_id in metadata")

        # Call playbook handler
        success, result = await restart_databricks_cluster(
            cluster_id=cluster_id,
            wait_for_ready=True,
            timeout_minutes=10
        )

        if success:
            logger.info(f"✅ Cluster restart successful: {result}")
            return JSONResponse({
                "status": "success",
                "ticket_id": body.get('ticket_id'),
                **result
            })
        else:
            logger.error(f"❌ Cluster restart failed: {result}")
            return JSONResponse({
                "status": "error",
                "ticket_id": body.get('ticket_id'),
                **result
            }, status_code=500)

    except Exception as e:
        logger.error(f"Exception in restart-cluster: {e}")
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)


@app.post("/playbooks/scale-cluster")
async def scale_cluster_endpoint(request: Request):
    """
    Scale up a Databricks cluster

    Request Body:
    {
        "ticket_id": "DBX-123",
        "error_type": "DatabricksResourceExhausted",
        "metadata": {
            "cluster_id": "1234-567890-abc123",
            "target_workers": 10  # Optional, defaults to 1.5x current
        }
    }
    """
    try:
        body = await request.json()
        logger.info(f"Scale cluster playbook triggered for ticket: {body.get('ticket_id')}")

        metadata = body.get('metadata', {})
        cluster_id = metadata.get('cluster_id')
        target_workers = metadata.get('target_workers')

        if not cluster_id:
            raise HTTPException(status_code=400, detail="Missing cluster_id in metadata")

        # Call playbook handler
        success, result = await scale_databricks_cluster(
            cluster_id=cluster_id,
            target_workers=target_workers,
            scale_percent=1.5  # 50% increase
        )

        if success:
            logger.info(f"✅ Cluster scaling successful: {result}")
            return JSONResponse({
                "status": "success",
                "ticket_id": body.get('ticket_id'),
                **result
            })
        else:
            logger.error(f"❌ Cluster scaling failed: {result}")
            return JSONResponse({
                "status": "error",
                "ticket_id": body.get('ticket_id'),
                **result
            }, status_code=500)

    except Exception as e:
        logger.error(f"Exception in scale-cluster: {e}")
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)


# =============================================================================
# DATABRICKS JOB PLAYBOOKS
# =============================================================================

@app.post("/playbooks/retry-job")
async def retry_job_endpoint(request: Request):
    """
    Retry a Databricks job

    Request Body:
    {
        "ticket_id": "DBX-123",
        "error_type": "DatabricksTimeoutError",
        "metadata": {
            "job_id": "12345",
            "notebook_params": {"key": "value"}  # Optional
        }
    }
    """
    try:
        body = await request.json()
        logger.info(f"Retry job playbook triggered for ticket: {body.get('ticket_id')}")

        metadata = body.get('metadata', {})
        job_id = metadata.get('job_id')
        notebook_params = metadata.get('notebook_params')

        if not job_id:
            raise HTTPException(status_code=400, detail="Missing job_id in metadata")

        # Call playbook handler
        success, result = await retry_databricks_job(
            job_id=job_id,
            notebook_params=notebook_params
        )

        if success:
            logger.info(f"✅ Job retry successful: {result}")
            return JSONResponse({
                "status": "success",
                "ticket_id": body.get('ticket_id'),
                **result
            })
        else:
            logger.error(f"❌ Job retry failed: {result}")
            return JSONResponse({
                "status": "error",
                "ticket_id": body.get('ticket_id'),
                **result
            }, status_code=500)

    except Exception as e:
        logger.error(f"Exception in retry-job: {e}")
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)


# =============================================================================
# DATABRICKS LIBRARY PLAYBOOKS
# =============================================================================

@app.post("/playbooks/reinstall-libraries")
async def reinstall_libraries_endpoint(request: Request):
    """
    Reinstall a library with version fallback

    Request Body:
    {
        "ticket_id": "DBX-123",
        "error_type": "DatabricksLibraryInstallationError",
        "metadata": {
            "cluster_id": "1234-567890-abc123",
            "library_spec": "pandas==2.2.0"
        }
    }
    """
    try:
        body = await request.json()
        logger.info(f"Reinstall libraries playbook triggered for ticket: {body.get('ticket_id')}")

        metadata = body.get('metadata', {})
        cluster_id = metadata.get('cluster_id')
        library_spec = metadata.get('library_spec', 'pandas')  # Default to pandas

        if not cluster_id:
            raise HTTPException(status_code=400, detail="Missing cluster_id in metadata")

        # Call playbook handler
        success, result = await reinstall_databricks_libraries(
            cluster_id=cluster_id,
            library_spec=library_spec,
            try_fallback_versions=True
        )

        if success:
            logger.info(f"✅ Library reinstall successful: {result}")
            return JSONResponse({
                "status": "success",
                "ticket_id": body.get('ticket_id'),
                **result
            })
        else:
            logger.error(f"❌ Library reinstall failed: {result}")
            return JSONResponse({
                "status": "error",
                "ticket_id": body.get('ticket_id'),
                **result
            }, status_code=500)

    except Exception as e:
        logger.error(f"Exception in reinstall-libraries: {e}")
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)


# =============================================================================
# HEALTH CHECK
# =============================================================================

@app.get("/playbooks/health")
async def health_check():
    """Health check endpoint"""
    return JSONResponse({
        "status": "healthy",
        "service": "Auto-Remediation Playbook Server",
        "version": "1.0.0",
        "endpoints": [
            "/playbooks/retry-pipeline",
            "/playbooks/check-upstream",
            "/playbooks/restart-cluster",
            "/playbooks/scale-cluster",
            "/playbooks/retry-job",
            "/playbooks/reinstall-libraries"
        ]
    })


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Auto-Remediation Playbook Server",
        "docs": "/docs",
        "health": "/playbooks/health"
    }


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    logger.info("🚀 Starting Auto-Remediation Playbook Server...")
    logger.info("📡 Server will be available at: http://localhost:8001")
    logger.info("📚 API docs available at: http://localhost:8001/docs")
    logger.info("")
    logger.info("Add these to your .env file:")
    logger.info("  PLAYBOOK_RETRY_PIPELINE=http://localhost:8001/playbooks/retry-pipeline")
    logger.info("  PLAYBOOK_RESTART_CLUSTER=http://localhost:8001/playbooks/restart-cluster")
    logger.info("  PLAYBOOK_RETRY_JOB=http://localhost:8001/playbooks/retry-job")
    logger.info("  PLAYBOOK_SCALE_CLUSTER=http://localhost:8001/playbooks/scale-cluster")
    logger.info("  PLAYBOOK_REINSTALL_LIBRARIES=http://localhost:8001/playbooks/reinstall-libraries")
    logger.info("")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="info"
    )
