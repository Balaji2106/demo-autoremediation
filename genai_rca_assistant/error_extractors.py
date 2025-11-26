"""
Error extraction utilities for different services
Each service has its own extraction logic
"""
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger("error_extractors")


class AzureDataFactoryExtractor:
    """Extract error details from ADF webhook payloads"""

    @staticmethod
    def extract(payload: Dict) -> Tuple[str, str, str, Dict]:
        """
        Extract error details from ADF webhook

        Returns:
            (pipeline_name, run_id, error_message, metadata)
        """
        # Handle both common alert schema and custom payloads
        essentials = payload.get("data", {}).get("essentials") or payload.get("essentials") or {}
        alert_context = payload.get("data", {}).get("alertContext") or {}
        properties = alert_context.get("properties", {}) or payload.get("properties", {})

        # Extract pipeline name
        pipeline_name = (
            properties.get("PipelineName") or
            properties.get("pipelineName") or
            essentials.get("alertRule") or
            essentials.get("pipelineName") or
            "ADF Pipeline"
        )

        # Extract run ID
        run_id = (
            properties.get("PipelineRunId") or
            properties.get("pipelineRunId") or
            properties.get("RunId") or
            properties.get("runId") or
            essentials.get("alertId")
        )

        # Extract error message (Priority order)
        error_obj = properties.get("Error") or properties.get("error") or {}

        error_message = (
            # 1. Detailed error object message
            error_obj.get("message") or
            error_obj.get("Message") or
            # 2. Error message fields
            properties.get("ErrorMessage") or
            properties.get("errorMessage") or
            properties.get("detailedMessage") or
            # 3. Generic message
            properties.get("message") or
            essentials.get("description") or
            # 4. Fallback
            "ADF pipeline failed. No detailed error message available."
        )

        # Clean up Logic App forwarding messages
        if "forwarded to rca system" in error_message.lower():
            import re
            match = re.search(r"(ErrorMessage|Message)=(.+)(?=Forwarded to RCA system)",
                            error_message, re.IGNORECASE | re.DOTALL)
            if match:
                error_message = match.group(2).strip().strip("'")

        # Extract metadata
        metadata = {
            "activity_name": properties.get("ActivityName") or properties.get("activityName"),
            "activity_type": properties.get("ActivityType") or properties.get("activityType"),
            "error_code": (
                error_obj.get("errorCode") or
                properties.get("ErrorCode") or
                properties.get("errorCode")
            ),
            "failure_type": error_obj.get("failureType") or error_obj.get("FailureType"),
            "severity": essentials.get("severity"),
            "fired_time": essentials.get("firedDateTime"),
        }

        logger.info(f"✓ ADF Extractor: pipeline={pipeline_name}, run_id={run_id}")
        logger.info(f"✓ ADF Extractor: error_code={metadata['error_code']}, error_length={len(error_message)}")

        return pipeline_name, run_id, error_message, metadata


class DatabricksExtractor:
    """Extract error details from Databricks webhook payloads"""

    @staticmethod
    def extract(payload: Dict) -> Tuple[str, str, str, str, Dict]:
        """
        Extract error details from Databricks webhook

        Returns:
            (resource_name, run_id, event_type, error_message, metadata)
        """
        event_type = payload.get("event") or payload.get("event_type") or "unknown"

        # Determine if this is a job event or cluster event
        if "job" in event_type.lower() or "run" in payload:
            return DatabricksExtractor._extract_job_event(payload, event_type)
        elif "cluster" in event_type.lower() or "cluster" in payload:
            return DatabricksExtractor._extract_cluster_event(payload, event_type)
        elif "library" in event_type.lower():
            return DatabricksExtractor._extract_library_event(payload, event_type)
        else:
            return DatabricksExtractor._extract_generic_event(payload, event_type)

    @staticmethod
    def _extract_job_event(payload: Dict, event_type: str) -> Tuple[str, str, str, str, Dict]:
        """Extract job failure event details"""
        job_obj = payload.get("job", {})
        run_obj = payload.get("run", {})

        job_name = (
            job_obj.get("settings", {}).get("name") or
            run_obj.get("run_name") or
            payload.get("job_name") or
            "Databricks Job"
        )

        run_id = (
            run_obj.get("run_id") or
            payload.get("run_id") or
            payload.get("job_run_id")
        )

        # Initial error from webhook
        error_message = (
            run_obj.get("state", {}).get("state_message") or
            run_obj.get("state_message") or
            payload.get("error_message") or
            f"Databricks job event: {event_type}"
        )

        metadata = {
            "job_id": job_obj.get("job_id") or payload.get("job_id"),
            "cluster_id": run_obj.get("cluster_instance", {}).get("cluster_id"),
            "event_type": event_type,
            "resource_type": "job",
            "life_cycle_state": run_obj.get("state", {}).get("life_cycle_state"),
            "result_state": run_obj.get("state", {}).get("result_state"),
        }

        logger.info(f"✓ Databricks Job Extractor: job={job_name}, run_id={run_id}, event={event_type}")

        return job_name, run_id, event_type, error_message, metadata

    @staticmethod
    def _extract_cluster_event(payload: Dict, event_type: str) -> Tuple[str, str, str, str, Dict]:
        """Extract cluster event details (NEW)"""
        cluster_obj = payload.get("cluster", {})

        cluster_name = (
            cluster_obj.get("cluster_name") or
            payload.get("cluster_name") or
            "Databricks Cluster"
        )

        cluster_id = (
            cluster_obj.get("cluster_id") or
            payload.get("cluster_id")
        )

        # Extract termination reason
        termination_reason = cluster_obj.get("termination_reason", {})
        state_message = cluster_obj.get("state_message", "")

        if termination_reason:
            code = termination_reason.get("code")
            term_type = termination_reason.get("type")
            params = termination_reason.get("parameters", {})

            error_message = f"Cluster {event_type}: {state_message}. Reason: {code} ({term_type})"
            if params:
                param_str = ", ".join([f"{k}={v}" for k, v in params.items()])
                error_message += f". Details: {param_str}"
        else:
            error_message = state_message or f"Cluster {event_type}"

        metadata = {
            "cluster_id": cluster_id,
            "event_type": event_type,
            "resource_type": "cluster",
            "cluster_state": cluster_obj.get("state"),
            "termination_code": termination_reason.get("code"),
            "termination_type": termination_reason.get("type"),
            "driver_node_type": cluster_obj.get("driver_node_type_id"),
            "num_workers": cluster_obj.get("num_workers"),
        }

        logger.info(f"✓ Databricks Cluster Extractor: cluster={cluster_name}, id={cluster_id}, event={event_type}")

        return cluster_name, cluster_id, event_type, error_message, metadata

    @staticmethod
    def _extract_library_event(payload: Dict, event_type: str) -> Tuple[str, str, str, str, Dict]:
        """Extract library installation event details (NEW)"""
        library_obj = payload.get("library", {})
        cluster_obj = payload.get("cluster", {})

        cluster_name = cluster_obj.get("cluster_name") or "Unknown Cluster"
        cluster_id = cluster_obj.get("cluster_id") or payload.get("cluster_id")

        library_name = (
            library_obj.get("pypi", {}).get("package") or
            library_obj.get("maven", {}).get("coordinates") or
            library_obj.get("jar") or
            "Unknown Library"
        )

        error_message = (
            payload.get("error_message") or
            payload.get("message") or
            f"Library installation {event_type}: {library_name}"
        )

        metadata = {
            "cluster_id": cluster_id,
            "cluster_name": cluster_name,
            "library": library_name,
            "library_type": list(library_obj.keys())[0] if library_obj else "unknown",
            "event_type": event_type,
            "resource_type": "library",
            "status": payload.get("status"),
        }

        logger.info(f"✓ Databricks Library Extractor: cluster={cluster_name}, library={library_name}, event={event_type}")

        return f"{cluster_name} - {library_name}", cluster_id, event_type, error_message, metadata

    @staticmethod
    def _extract_generic_event(payload: Dict, event_type: str) -> Tuple[str, str, str, str, Dict]:
        """Fallback for unknown event types"""
        resource_name = (
            payload.get("name") or
            payload.get("resource_name") or
            "Databricks Resource"
        )

        resource_id = (
            payload.get("id") or
            payload.get("resource_id") or
            "unknown"
        )

        error_message = payload.get("message") or payload.get("error_message") or str(payload)

        metadata = {
            "event_type": event_type,
            "resource_type": "unknown",
            "raw_payload_keys": list(payload.keys())
        }

        logger.warning(f"⚠ Databricks Generic Extractor: Unrecognized event type: {event_type}")

        return resource_name, resource_id, event_type, error_message, metadata


class AzureFunctionsExtractor:
    """Extract error details from Azure Functions / Application Insights webhooks"""

    @staticmethod
    def extract(payload: Dict) -> Tuple[str, str, str, Dict]:
        """
        Extract error details from Azure Functions webhook

        Returns:
            (function_name, invocation_id, error_message, metadata)
        """
        essentials = payload.get("data", {}).get("essentials") or payload.get("essentials") or {}
        alert_context = payload.get("data", {}).get("alertContext") or {}

        function_name = (
            alert_context.get("properties", {}).get("FunctionName") or
            essentials.get("alertRule") or
            "Azure Function"
        )

        invocation_id = (
            alert_context.get("properties", {}).get("InvocationId") or
            essentials.get("alertId")
        )

        error_message = (
            alert_context.get("properties", {}).get("ExceptionMessage") or
            alert_context.get("properties", {}).get("ErrorMessage") or
            essentials.get("description") or
            "Azure Function failed"
        )

        metadata = {
            "function_app": alert_context.get("properties", {}).get("FunctionAppName"),
            "exception_type": alert_context.get("properties", {}).get("ExceptionType"),
            "severity": essentials.get("severity"),
            "timestamp": alert_context.get("properties", {}).get("Timestamp"),
        }

        logger.info(f"✓ Azure Functions Extractor: function={function_name}, invocation={invocation_id}")

        return function_name, invocation_id, error_message, metadata


class AzureSynapseExtractor:
    """Extract error details from Azure Synapse webhooks"""

    @staticmethod
    def extract(payload: Dict) -> Tuple[str, str, str, Dict]:
        """
        Extract error details from Synapse webhook

        Returns:
            (pipeline_name, run_id, error_message, metadata)
        """
        essentials = payload.get("data", {}).get("essentials") or payload.get("essentials") or {}
        properties = payload.get("data", {}).get("alertContext", {}).get("properties", {})

        pipeline_name = (
            properties.get("PipelineName") or
            properties.get("pipelineName") or
            essentials.get("alertRule") or
            "Synapse Pipeline"
        )

        run_id = (
            properties.get("RunId") or
            properties.get("runId") or
            essentials.get("alertId")
        )

        error_message = (
            properties.get("ErrorMessage") or
            properties.get("errorMessage") or
            essentials.get("description") or
            "Synapse pipeline failed"
        )

        metadata = {
            "workspace_name": properties.get("WorkspaceName"),
            "activity_name": properties.get("ActivityName"),
            "error_code": properties.get("ErrorCode"),
            "severity": essentials.get("severity"),
        }

        logger.info(f"✓ Synapse Extractor: pipeline={pipeline_name}, run_id={run_id}")

        return pipeline_name, run_id, error_message, metadata


# Factory function
def get_extractor(source_type: str):
    """Get appropriate extractor for source type"""
    extractors = {
        "adf": AzureDataFactoryExtractor,
        "azure_data_factory": AzureDataFactoryExtractor,
        "databricks": DatabricksExtractor,
        "azure_functions": AzureFunctionsExtractor,
        "functions": AzureFunctionsExtractor,
        "synapse": AzureSynapseExtractor,
        "azure_synapse": AzureSynapseExtractor,
    }
    return extractors.get(source_type.lower())
