"""Registers internal_azure_* tools with the ADK tool registry (Microsoft Azure)."""

from typing import Any

from src.services.agents.internal_tools.azure_tools import (
    internal_azure_get_logs,
    internal_azure_get_metrics,
    internal_azure_get_resource_health,
    internal_azure_list_alerts,
    internal_azure_list_security_findings,
)


def register_azure_tools(registry: Any) -> None:
    async def get_logs_wrapper(
        config: dict | None = None,
        log_source: str = "",
        start_time: str = "",
        end_time: str = "",
        filter_query: str = "",
        limit: int = 100,
        **kwargs,
    ) -> dict[str, Any]:
        runtime_context = (config or {}).get("_runtime_context")
        return await internal_azure_get_logs(
            runtime_context=runtime_context,
            log_source=log_source,
            start_time=start_time,
            end_time=end_time,
            filter_query=filter_query,
            limit=limit,
        )

    async def get_metrics_wrapper(
        config: dict | None = None,
        metric_name: str = "",
        start_time: str = "",
        end_time: str = "",
        resource_id: str = "",
        period_seconds: int = 300,
        **kwargs,
    ) -> dict[str, Any]:
        runtime_context = (config or {}).get("_runtime_context")
        return await internal_azure_get_metrics(
            runtime_context=runtime_context,
            metric_name=metric_name,
            start_time=start_time,
            end_time=end_time,
            resource_id=resource_id,
            period_seconds=period_seconds,
        )

    async def list_alerts_wrapper(config: dict | None = None, active_only: bool = True, **kwargs) -> dict[str, Any]:
        runtime_context = (config or {}).get("_runtime_context")
        return await internal_azure_list_alerts(runtime_context=runtime_context, active_only=active_only)

    async def get_resource_health_wrapper(
        config: dict | None = None, resource_id: str = "", **kwargs
    ) -> dict[str, Any]:
        runtime_context = (config or {}).get("_runtime_context")
        return await internal_azure_get_resource_health(runtime_context=runtime_context, resource_id=resource_id)

    async def list_security_findings_wrapper(
        config: dict | None = None, severity: str = "", **kwargs
    ) -> dict[str, Any]:
        runtime_context = (config or {}).get("_runtime_context")
        return await internal_azure_list_security_findings(runtime_context=runtime_context, severity=severity)

    registry.register_tool(
        name="internal_azure_get_logs",
        description=(
            "Query Azure Monitor Logs (Log Analytics) for a workspace. Use for investigating "
            "application/VM/AKS log entries during an incident. Keywords: Azure, Log Analytics, "
            "Azure Monitor Logs, KQL, workspace logs."
        ),
        parameters={
            "type": "object",
            "properties": {
                "log_source": {"type": "string", "description": "Log Analytics workspace ID."},
                "start_time": {"type": "string", "description": "ISO 8601 start of the time range."},
                "end_time": {"type": "string", "description": "ISO 8601 end of the time range."},
                "filter_query": {
                    "type": "string",
                    "description": "Optional KQL query body (defaults to a recent-events query).",
                },
                "limit": {"type": "integer", "description": "Max rows to return.", "default": 100},
            },
            "required": ["log_source", "start_time", "end_time"],
        },
        function=get_logs_wrapper,
        requires_auth="azure",
        tool_category="read",
    )

    registry.register_tool(
        name="internal_azure_get_metrics",
        description=(
            "Get Azure Monitor Metrics (e.g. Percentage CPU, Network In) for a specific ARM "
            "resource. Keywords: Azure Monitor Metrics, VM metrics, AKS metrics, resource metrics."
        ),
        parameters={
            "type": "object",
            "properties": {
                "metric_name": {"type": "string", "description": "Azure metric name, e.g. 'Percentage CPU'."},
                "start_time": {"type": "string", "description": "ISO 8601 start of the time range."},
                "end_time": {"type": "string", "description": "ISO 8601 end of the time range."},
                "resource_id": {
                    "type": "string",
                    "description": "Full ARM resource ID (required — no cross-resource shortcut exists).",
                },
                "period_seconds": {
                    "type": "integer",
                    "description": "Aggregation interval in seconds.",
                    "default": 300,
                },
            },
            "required": ["metric_name", "start_time", "end_time", "resource_id"],
        },
        function=get_metrics_wrapper,
        requires_auth="azure",
        tool_category="read",
    )

    registry.register_tool(
        name="internal_azure_list_alerts",
        description=(
            "List Azure Monitor alert rule firings for the subscription. Keywords: Azure alerts, "
            "alert rules, AlertsManagement."
        ),
        parameters={
            "type": "object",
            "properties": {
                "active_only": {"type": "boolean", "description": "Only return active (New) alerts.", "default": True},
            },
            "required": [],
        },
        function=list_alerts_wrapper,
        requires_auth="azure",
        tool_category="read",
    )

    registry.register_tool(
        name="internal_azure_get_resource_health",
        description=(
            "Get the current availability status of an Azure resource (VM, AKS, etc). Keywords: "
            "Azure Resource Health, VM health, AKS health, availability status."
        ),
        parameters={
            "type": "object",
            "properties": {
                "resource_id": {"type": "string", "description": "Full ARM resource ID (required)."},
            },
            "required": ["resource_id"],
        },
        function=get_resource_health_wrapper,
        requires_auth="azure",
        tool_category="read",
    )

    registry.register_tool(
        name="internal_azure_list_security_findings",
        description=(
            "List Microsoft Defender for Cloud security assessments for the subscription, "
            "optionally filtered by severity. Keywords: Defender for Cloud, security assessments, "
            "Azure security findings."
        ),
        parameters={
            "type": "object",
            "properties": {
                "severity": {"type": "string", "description": "Filter by severity, e.g. 'High'. Empty for all."},
            },
            "required": [],
        },
        function=list_security_findings_wrapper,
        requires_auth="azure",
        tool_category="read",
    )
