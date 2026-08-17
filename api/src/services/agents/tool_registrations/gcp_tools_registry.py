"""
GCP Tools Registry

Registers Cloud Logging/Monitoring/Compute/Security-Command-Center tools with
the ADK tool registry. All 5 tools are read-only (tool_category="read").
"""

import logging
from typing import Any

from src.services.agents.internal_tools.gcp_tools import (
    internal_gcp_get_logs,
    internal_gcp_get_metrics,
    internal_gcp_get_resource_health,
    internal_gcp_list_alerts,
    internal_gcp_list_security_findings,
)

logger = logging.getLogger(__name__)


def register_gcp_tools(registry):
    """
    Register all GCP tools with the ADK tool registry.

    Args:
        registry: ADKToolRegistry instance
    """

    async def gcp_get_logs_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gcp_get_logs(
            runtime_context=runtime_context,
            log_source=kwargs.get("log_source", ""),
            start_time=kwargs.get("start_time", ""),
            end_time=kwargs.get("end_time", ""),
            filter_query=kwargs.get("filter_query", ""),
            limit=kwargs.get("limit", 100),
        )

    async def gcp_get_metrics_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gcp_get_metrics(
            runtime_context=runtime_context,
            metric_name=kwargs.get("metric_name", ""),
            start_time=kwargs.get("start_time", ""),
            end_time=kwargs.get("end_time", ""),
            resource_id=kwargs.get("resource_id", ""),
            period_seconds=kwargs.get("period_seconds", 300),
        )

    async def gcp_list_alerts_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gcp_list_alerts(
            runtime_context=runtime_context,
            active_only=kwargs.get("active_only", True),
        )

    async def gcp_get_resource_health_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gcp_get_resource_health(
            runtime_context=runtime_context,
            resource_id=kwargs.get("resource_id", ""),
        )

    async def gcp_list_security_findings_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gcp_list_security_findings(
            runtime_context=runtime_context,
            severity=kwargs.get("severity", ""),
        )

    registry.register_tool(
        name="internal_gcp_get_logs",
        description=(
            "Fetch Google Cloud Logging entries. Use during incident investigation to pull "
            "Cloud Run/GKE/App Engine logs. Keywords: GCP, Google Cloud, Cloud Logging, Stackdriver."
        ),
        parameters={
            "type": "object",
            "properties": {
                "log_source": {
                    "type": "string",
                    "description": "Cloud Logging log ID, e.g. 'run.googleapis.com%2Fstderr'",
                },
                "start_time": {"type": "string", "description": "Start of time range, ISO 8601"},
                "end_time": {"type": "string", "description": "End of time range, ISO 8601"},
                "filter_query": {
                    "type": "string",
                    "description": "Optional additional Cloud Logging filter expression",
                },
                "limit": {"type": "integer", "description": "Max entries to return (default 100)", "default": 100},
            },
            "required": ["log_source", "start_time", "end_time"],
        },
        function=gcp_get_logs_wrapper,
        requires_auth="gcp",
        tool_category="read",
    )

    registry.register_tool(
        name="internal_gcp_get_metrics",
        description=(
            "Fetch a Google Cloud Monitoring metric time series (e.g. CPU utilization). "
            "Keywords: GCP, Google Cloud, Cloud Monitoring, Stackdriver Monitoring."
        ),
        parameters={
            "type": "object",
            "properties": {
                "metric_name": {
                    "type": "string",
                    "description": "Full metric type, e.g. 'compute.googleapis.com/instance/cpu/utilization'",
                },
                "start_time": {"type": "string", "description": "Start of time range, ISO 8601"},
                "end_time": {"type": "string", "description": "End of time range, ISO 8601"},
                "resource_id": {"type": "string", "description": "Optional Compute Engine instance ID to scope to"},
                "period_seconds": {
                    "type": "integer",
                    "description": "Alignment period in seconds (default 300)",
                    "default": 300,
                },
            },
            "required": ["metric_name", "start_time", "end_time"],
        },
        function=gcp_get_metrics_wrapper,
        requires_auth="gcp",
        tool_category="read",
    )

    registry.register_tool(
        name="internal_gcp_list_alerts",
        description=(
            "List Google Cloud Monitoring alerting policies. Keywords: GCP, Google Cloud, "
            "alert policies, Cloud Monitoring alerts."
        ),
        parameters={
            "type": "object",
            "properties": {
                "active_only": {
                    "type": "boolean",
                    "description": "If true (default), only return enabled policies",
                    "default": True,
                },
            },
            "required": [],
        },
        function=gcp_list_alerts_wrapper,
        requires_auth="gcp",
        tool_category="read",
    )

    registry.register_tool(
        name="internal_gcp_get_resource_health",
        description=(
            "Get Google Compute Engine instance health/status. Keywords: GCP, Google Cloud, "
            "Compute Engine, GKE, instance status."
        ),
        parameters={
            "type": "object",
            "properties": {
                "resource_id": {
                    "type": "string",
                    "description": "Optional Compute Engine instance name; omit to check all instances",
                },
            },
            "required": [],
        },
        function=gcp_get_resource_health_wrapper,
        requires_auth="gcp",
        tool_category="read",
    )

    registry.register_tool(
        name="internal_gcp_list_security_findings",
        description=(
            "List Google Cloud Security Command Center findings. Keywords: GCP, Google Cloud, "
            "Security Command Center, SCC, vulnerabilities."
        ),
        parameters={
            "type": "object",
            "properties": {
                "severity": {
                    "type": "string",
                    "description": "Optional severity filter: LOW, MEDIUM, HIGH, CRITICAL",
                },
            },
            "required": [],
        },
        function=gcp_list_security_findings_wrapper,
        requires_auth="gcp",
        tool_category="read",
    )

    logger.info("Registered 5 GCP tools")
