"""Registers internal_digitalocean_* tools with the ADK tool registry."""

from typing import Any

from src.services.agents.internal_tools.digitalocean_tools import (
    internal_digitalocean_get_logs,
    internal_digitalocean_get_metrics,
    internal_digitalocean_get_resource_health,
    internal_digitalocean_list_alerts,
    internal_digitalocean_list_security_findings,
)


def register_digitalocean_tools(registry: Any) -> None:
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
        return await internal_digitalocean_get_logs(
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
        return await internal_digitalocean_get_metrics(
            runtime_context=runtime_context,
            metric_name=metric_name,
            start_time=start_time,
            end_time=end_time,
            resource_id=resource_id,
            period_seconds=period_seconds,
        )

    async def list_alerts_wrapper(config: dict | None = None, active_only: bool = True, **kwargs) -> dict[str, Any]:
        runtime_context = (config or {}).get("_runtime_context")
        return await internal_digitalocean_list_alerts(runtime_context=runtime_context, active_only=active_only)

    async def get_resource_health_wrapper(
        config: dict | None = None, resource_id: str = "", **kwargs
    ) -> dict[str, Any]:
        runtime_context = (config or {}).get("_runtime_context")
        return await internal_digitalocean_get_resource_health(runtime_context=runtime_context, resource_id=resource_id)

    async def list_security_findings_wrapper(
        config: dict | None = None, severity: str = "", **kwargs
    ) -> dict[str, Any]:
        runtime_context = (config or {}).get("_runtime_context")
        return await internal_digitalocean_list_security_findings(runtime_context=runtime_context, severity=severity)

    registry.register_tool(
        name="internal_digitalocean_get_logs",
        description=(
            "Not supported by DigitalOcean — DO has no log-query API. Calling this always returns "
            "a 'Not supported by DigitalOcean' error so the agent gets an explicit answer instead "
            "of guessing. Keywords: DigitalOcean logs, droplet logs."
        ),
        parameters={
            "type": "object",
            "properties": {
                "log_source": {"type": "string", "description": "Unused — DO has no log-query API."},
                "start_time": {"type": "string", "description": "Unused."},
                "end_time": {"type": "string", "description": "Unused."},
                "filter_query": {"type": "string", "description": "Unused."},
                "limit": {"type": "integer", "description": "Unused.", "default": 100},
            },
            "required": ["log_source", "start_time", "end_time"],
        },
        function=get_logs_wrapper,
        requires_auth="digitalocean",
        tool_category="read",
    )

    registry.register_tool(
        name="internal_digitalocean_get_metrics",
        description=(
            "Get DigitalOcean Droplet monitoring metrics (e.g. cpu, memory, disk) for a specific "
            "droplet. Keywords: DigitalOcean metrics, droplet CPU, droplet memory, DO monitoring."
        ),
        parameters={
            "type": "object",
            "properties": {
                "metric_name": {"type": "string", "description": "Metric name, e.g. 'cpu', 'memory', 'disk'."},
                "start_time": {"type": "string", "description": "Unix timestamp (seconds) for range start."},
                "end_time": {"type": "string", "description": "Unix timestamp (seconds) for range end."},
                "resource_id": {"type": "string", "description": "Droplet ID (required)."},
                "period_seconds": {"type": "integer", "description": "Unused for DO metrics.", "default": 300},
            },
            "required": ["metric_name", "start_time", "end_time", "resource_id"],
        },
        function=get_metrics_wrapper,
        requires_auth="digitalocean",
        tool_category="read",
    )

    registry.register_tool(
        name="internal_digitalocean_list_alerts",
        description=(
            "List DigitalOcean monitoring alert policies. Keywords: DigitalOcean alerts, monitoring "
            "alert policies, DO alerts."
        ),
        parameters={
            "type": "object",
            "properties": {
                "active_only": {
                    "type": "boolean",
                    "description": "Only return enabled alert policies.",
                    "default": True,
                },
            },
            "required": [],
        },
        function=list_alerts_wrapper,
        requires_auth="digitalocean",
        tool_category="read",
    )

    registry.register_tool(
        name="internal_digitalocean_get_resource_health",
        description=(
            "Get the current status of a DigitalOcean Droplet (e.g. active, off, archive). "
            "Keywords: DigitalOcean droplet status, droplet health."
        ),
        parameters={
            "type": "object",
            "properties": {
                "resource_id": {"type": "string", "description": "Droplet ID (required)."},
            },
            "required": ["resource_id"],
        },
        function=get_resource_health_wrapper,
        requires_auth="digitalocean",
        tool_category="read",
    )

    registry.register_tool(
        name="internal_digitalocean_list_security_findings",
        description=(
            "Not supported by DigitalOcean — DO has no security-findings API equivalent. Calling "
            "this always returns a 'Not supported by DigitalOcean' error. Keywords: DigitalOcean "
            "security findings."
        ),
        parameters={
            "type": "object",
            "properties": {
                "severity": {"type": "string", "description": "Unused — not supported by DigitalOcean."},
            },
            "required": [],
        },
        function=list_security_findings_wrapper,
        requires_auth="digitalocean",
        tool_category="read",
    )
