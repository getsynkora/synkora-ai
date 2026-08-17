"""
AWS Tools Registry

Registers CloudWatch Logs/Metrics/Alarms, EC2 status, and Security Hub tools
with the ADK tool registry. All 5 tools are read-only (tool_category="read")
so they don't trigger HITL approval gating.
"""

import logging
from typing import Any

from src.services.agents.internal_tools.aws_tools import (
    internal_aws_get_logs,
    internal_aws_get_metrics,
    internal_aws_get_resource_health,
    internal_aws_list_alerts,
    internal_aws_list_security_findings,
)

logger = logging.getLogger(__name__)


def register_aws_tools(registry):
    """
    Register all AWS tools with the ADK tool registry.

    Args:
        registry: ADKToolRegistry instance
    """

    async def aws_get_logs_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_aws_get_logs(
            runtime_context=runtime_context,
            log_source=kwargs.get("log_source", ""),
            start_time=kwargs.get("start_time", ""),
            end_time=kwargs.get("end_time", ""),
            filter_query=kwargs.get("filter_query", ""),
            limit=kwargs.get("limit", 100),
        )

    async def aws_get_metrics_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_aws_get_metrics(
            runtime_context=runtime_context,
            metric_name=kwargs.get("metric_name", ""),
            start_time=kwargs.get("start_time", ""),
            end_time=kwargs.get("end_time", ""),
            resource_id=kwargs.get("resource_id", ""),
            period_seconds=kwargs.get("period_seconds", 300),
        )

    async def aws_list_alerts_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_aws_list_alerts(
            runtime_context=runtime_context,
            active_only=kwargs.get("active_only", True),
        )

    async def aws_get_resource_health_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_aws_get_resource_health(
            runtime_context=runtime_context,
            resource_id=kwargs.get("resource_id", ""),
        )

    async def aws_list_security_findings_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_aws_list_security_findings(
            runtime_context=runtime_context,
            severity=kwargs.get("severity", ""),
        )

    registry.register_tool(
        name="internal_aws_get_logs",
        description=(
            "Fetch AWS CloudWatch Logs entries from a log group. Use during incident investigation "
            "to pull application/Lambda/ECS logs. Keywords: AWS, CloudWatch Logs, log group, Lambda logs."
        ),
        parameters={
            "type": "object",
            "properties": {
                "log_source": {
                    "type": "string",
                    "description": "CloudWatch Logs log group name, e.g. '/aws/lambda/my-function'",
                },
                "start_time": {"type": "string", "description": "Start of time range, ISO 8601"},
                "end_time": {"type": "string", "description": "End of time range, ISO 8601"},
                "filter_query": {"type": "string", "description": "Optional CloudWatch Logs filter pattern"},
                "limit": {"type": "integer", "description": "Max entries to return (default 100)", "default": 100},
            },
            "required": ["log_source", "start_time", "end_time"],
        },
        function=aws_get_logs_wrapper,
        requires_auth="aws",
        tool_category="read",
    )

    registry.register_tool(
        name="internal_aws_get_metrics",
        description=(
            "Fetch an AWS CloudWatch metric time series (e.g. CPUUtilization, latency). "
            "Keywords: AWS, CloudWatch Metrics, EC2 metrics, get_metric_statistics."
        ),
        parameters={
            "type": "object",
            "properties": {
                "metric_name": {
                    "type": "string",
                    "description": "Metric name, optionally 'Namespace:MetricName' (default namespace AWS/EC2)",
                },
                "start_time": {"type": "string", "description": "Start of time range, ISO 8601"},
                "end_time": {"type": "string", "description": "End of time range, ISO 8601"},
                "resource_id": {"type": "string", "description": "Optional EC2 instance ID to scope to"},
                "period_seconds": {
                    "type": "integer",
                    "description": "Datapoint granularity in seconds (default 300)",
                    "default": 300,
                },
            },
            "required": ["metric_name", "start_time", "end_time"],
        },
        function=aws_get_metrics_wrapper,
        requires_auth="aws",
        tool_category="read",
    )

    registry.register_tool(
        name="internal_aws_list_alerts",
        description=("List AWS CloudWatch Alarms. Keywords: AWS, CloudWatch Alarms, alerting, describe_alarms."),
        parameters={
            "type": "object",
            "properties": {
                "active_only": {
                    "type": "boolean",
                    "description": "If true (default), only return alarms currently in ALARM state",
                    "default": True,
                },
            },
            "required": [],
        },
        function=aws_list_alerts_wrapper,
        requires_auth="aws",
        tool_category="read",
    )

    registry.register_tool(
        name="internal_aws_get_resource_health",
        description=("Get AWS EC2 instance health/status. Keywords: AWS, EC2, instance status, resource health."),
        parameters={
            "type": "object",
            "properties": {
                "resource_id": {
                    "type": "string",
                    "description": "Optional EC2 instance ID; omit to check all instances",
                },
            },
            "required": [],
        },
        function=aws_get_resource_health_wrapper,
        requires_auth="aws",
        tool_category="read",
    )

    registry.register_tool(
        name="internal_aws_list_security_findings",
        description=(
            "List AWS Security Hub findings. Keywords: AWS, Security Hub, GuardDuty, security findings, "
            "vulnerabilities."
        ),
        parameters={
            "type": "object",
            "properties": {
                "severity": {
                    "type": "string",
                    "description": "Optional severity filter: INFORMATIONAL, LOW, MEDIUM, HIGH, CRITICAL",
                },
            },
            "required": [],
        },
        function=aws_list_security_findings_wrapper,
        requires_auth="aws",
        tool_category="read",
    )

    logger.info("Registered 5 AWS tools")
