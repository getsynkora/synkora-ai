"""
GCP Tools — Cloud Logging, Cloud Monitoring, Compute Engine, Security Command Center.

Auth: full service-account JSON key stored in OAuthApp (provider='gcp',
auth_method='api_token'), project_id in OAuthApp.config (falls back to the
service account JSON's own project_id if omitted).
"""

import logging
from typing import Any

from src.services.agents.internal_tools.cloud_shared import get_cloud_provider_config
from src.services.cloud_providers.gcp_adapter import GCPAdapter

logger = logging.getLogger(__name__)


async def internal_gcp_get_logs(
    runtime_context: Any | None = None,
    log_source: str = "",
    start_time: str = "",
    end_time: str = "",
    filter_query: str = "",
    limit: int = 100,
) -> dict[str, Any]:
    """
    Fetch Cloud Logging entries.

    Args:
        log_source: Cloud Logging log ID (e.g. 'run.googleapis.com%2Fstderr')
        start_time: Start of time range, ISO 8601
        end_time: End of time range, ISO 8601
        filter_query: Optional additional Cloud Logging filter expression
        limit: Max entries to return (default 100)
    """
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        cfg = await get_cloud_provider_config(runtime_context, "internal_gcp_get_logs", "gcp")
        adapter = GCPAdapter(cfg)
        return await adapter.get_logs(
            log_source=log_source, start_time=start_time, end_time=end_time, filter_query=filter_query, limit=limit
        )
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"internal_gcp_get_logs failed: {e}")
        return {"success": False, "error": str(e)}


async def internal_gcp_get_metrics(
    runtime_context: Any | None = None,
    metric_name: str = "",
    start_time: str = "",
    end_time: str = "",
    resource_id: str = "",
    period_seconds: int = 300,
) -> dict[str, Any]:
    """
    Fetch a Cloud Monitoring metric time series.

    Args:
        metric_name: Full metric type, e.g. 'compute.googleapis.com/instance/cpu/utilization'
        start_time: Start of time range, ISO 8601
        end_time: End of time range, ISO 8601
        resource_id: Optional Compute Engine instance ID to scope to
        period_seconds: Alignment period in seconds (default 300)
    """
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        cfg = await get_cloud_provider_config(runtime_context, "internal_gcp_get_metrics", "gcp")
        adapter = GCPAdapter(cfg)
        return await adapter.get_metrics(
            metric_name=metric_name,
            start_time=start_time,
            end_time=end_time,
            resource_id=resource_id,
            period_seconds=period_seconds,
        )
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"internal_gcp_get_metrics failed: {e}")
        return {"success": False, "error": str(e)}


async def internal_gcp_list_alerts(
    runtime_context: Any | None = None,
    active_only: bool = True,
) -> dict[str, Any]:
    """
    List Cloud Monitoring alerting policies.

    Args:
        active_only: If True (default), only return enabled policies.
    """
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        cfg = await get_cloud_provider_config(runtime_context, "internal_gcp_list_alerts", "gcp")
        adapter = GCPAdapter(cfg)
        return await adapter.list_alerts(active_only=active_only)
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"internal_gcp_list_alerts failed: {e}")
        return {"success": False, "error": str(e)}


async def internal_gcp_get_resource_health(
    runtime_context: Any | None = None,
    resource_id: str = "",
) -> dict[str, Any]:
    """
    Get Compute Engine instance health/status.

    Args:
        resource_id: Optional instance name. If omitted, returns status for all instances.
    """
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        cfg = await get_cloud_provider_config(runtime_context, "internal_gcp_get_resource_health", "gcp")
        adapter = GCPAdapter(cfg)
        return await adapter.get_resource_health(resource_id=resource_id)
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"internal_gcp_get_resource_health failed: {e}")
        return {"success": False, "error": str(e)}


async def internal_gcp_list_security_findings(
    runtime_context: Any | None = None,
    severity: str = "",
) -> dict[str, Any]:
    """
    List Security Command Center findings.

    Args:
        severity: Optional severity filter — one of 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'.
    """
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        cfg = await get_cloud_provider_config(runtime_context, "internal_gcp_list_security_findings", "gcp")
        adapter = GCPAdapter(cfg)
        return await adapter.list_security_findings(severity=severity)
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"internal_gcp_list_security_findings failed: {e}")
        return {"success": False, "error": str(e)}
