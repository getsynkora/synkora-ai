"""
AWS Tools — CloudWatch Logs/Metrics/Alarms, EC2 instance status, Security Hub findings.

Auth: access_key_id/secret_access_key stored in OAuthApp (provider='aws',
auth_method='api_token'), region in OAuthApp.config.
"""

import logging
from typing import Any

from src.services.agents.internal_tools.cloud_shared import get_cloud_provider_config
from src.services.cloud_providers.aws_adapter import AWSAdapter

logger = logging.getLogger(__name__)


async def internal_aws_get_logs(
    runtime_context: Any | None = None,
    log_source: str = "",
    start_time: str = "",
    end_time: str = "",
    filter_query: str = "",
    limit: int = 100,
) -> dict[str, Any]:
    """
    Fetch CloudWatch Logs entries from a log group.

    Args:
        log_source: CloudWatch Logs log group name (e.g. '/aws/lambda/my-function')
        start_time: Start of the time range, ISO 8601 (e.g. '2026-01-01T00:00:00Z')
        end_time: End of the time range, ISO 8601
        filter_query: Optional CloudWatch Logs filter pattern
        limit: Max number of log entries to return (default 100)
    """
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        cfg = await get_cloud_provider_config(runtime_context, "internal_aws_get_logs", "aws")
        adapter = AWSAdapter(cfg)
        return await adapter.get_logs(
            log_source=log_source, start_time=start_time, end_time=end_time, filter_query=filter_query, limit=limit
        )
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"internal_aws_get_logs failed: {e}")
        return {"success": False, "error": str(e)}


async def internal_aws_get_metrics(
    runtime_context: Any | None = None,
    metric_name: str = "",
    start_time: str = "",
    end_time: str = "",
    resource_id: str = "",
    period_seconds: int = 300,
) -> dict[str, Any]:
    """
    Fetch a CloudWatch metric time series.

    Args:
        metric_name: Metric name, optionally prefixed with namespace (e.g. 'AWS/EC2:CPUUtilization').
            Defaults to the 'AWS/EC2' namespace if no prefix is given.
        start_time: Start of the time range, ISO 8601
        end_time: End of the time range, ISO 8601
        resource_id: Optional EC2 instance ID to scope the metric to
        period_seconds: Granularity of datapoints in seconds (default 300)
    """
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        cfg = await get_cloud_provider_config(runtime_context, "internal_aws_get_metrics", "aws")
        adapter = AWSAdapter(cfg)
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
        logger.error(f"internal_aws_get_metrics failed: {e}")
        return {"success": False, "error": str(e)}


async def internal_aws_list_alerts(
    runtime_context: Any | None = None,
    active_only: bool = True,
) -> dict[str, Any]:
    """
    List CloudWatch Alarms.

    Args:
        active_only: If True (default), only return alarms currently in ALARM state.
    """
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        cfg = await get_cloud_provider_config(runtime_context, "internal_aws_list_alerts", "aws")
        adapter = AWSAdapter(cfg)
        return await adapter.list_alerts(active_only=active_only)
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"internal_aws_list_alerts failed: {e}")
        return {"success": False, "error": str(e)}


async def internal_aws_get_resource_health(
    runtime_context: Any | None = None,
    resource_id: str = "",
) -> dict[str, Any]:
    """
    Get EC2 instance health/status.

    Args:
        resource_id: Optional EC2 instance ID. If omitted, returns status for all instances.
    """
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        cfg = await get_cloud_provider_config(runtime_context, "internal_aws_get_resource_health", "aws")
        adapter = AWSAdapter(cfg)
        return await adapter.get_resource_health(resource_id=resource_id)
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"internal_aws_get_resource_health failed: {e}")
        return {"success": False, "error": str(e)}


async def internal_aws_list_security_findings(
    runtime_context: Any | None = None,
    severity: str = "",
) -> dict[str, Any]:
    """
    List AWS Security Hub findings.

    Args:
        severity: Optional severity filter — one of 'INFORMATIONAL', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'.
    """
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        cfg = await get_cloud_provider_config(runtime_context, "internal_aws_list_security_findings", "aws")
        adapter = AWSAdapter(cfg)
        return await adapter.list_security_findings(severity=severity)
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"internal_aws_list_security_findings failed: {e}")
        return {"success": False, "error": str(e)}
