"""LLM-facing internal_azure_* tool functions — thin wrappers around AzureAdapter."""

from typing import Any

from src.services.agents.internal_tools.cloud_shared import get_cloud_provider_config
from src.services.cloud_providers.azure_adapter import AzureAdapter


async def internal_azure_get_logs(
    runtime_context: Any,
    log_source: str,
    start_time: str,
    end_time: str,
    filter_query: str = "",
    limit: int = 100,
) -> dict[str, Any]:
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        config = await get_cloud_provider_config(runtime_context, "internal_azure_get_logs", "azure")
        adapter = AzureAdapter(config)
        return await adapter.get_logs(
            log_source=log_source, start_time=start_time, end_time=end_time, filter_query=filter_query, limit=limit
        )
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Azure Monitor Logs request failed: {e}"}


async def internal_azure_get_metrics(
    runtime_context: Any,
    metric_name: str,
    start_time: str,
    end_time: str,
    resource_id: str = "",
    period_seconds: int = 300,
) -> dict[str, Any]:
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        config = await get_cloud_provider_config(runtime_context, "internal_azure_get_metrics", "azure")
        adapter = AzureAdapter(config)
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
        return {"success": False, "error": f"Azure Monitor Metrics request failed: {e}"}


async def internal_azure_list_alerts(runtime_context: Any, active_only: bool = True) -> dict[str, Any]:
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        config = await get_cloud_provider_config(runtime_context, "internal_azure_list_alerts", "azure")
        adapter = AzureAdapter(config)
        return await adapter.list_alerts(active_only=active_only)
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Azure Monitor alerts request failed: {e}"}


async def internal_azure_get_resource_health(runtime_context: Any, resource_id: str = "") -> dict[str, Any]:
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        config = await get_cloud_provider_config(runtime_context, "internal_azure_get_resource_health", "azure")
        adapter = AzureAdapter(config)
        return await adapter.get_resource_health(resource_id=resource_id)
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Azure Resource Health request failed: {e}"}


async def internal_azure_list_security_findings(runtime_context: Any, severity: str = "") -> dict[str, Any]:
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        config = await get_cloud_provider_config(runtime_context, "internal_azure_list_security_findings", "azure")
        adapter = AzureAdapter(config)
        return await adapter.list_security_findings(severity=severity)
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Defender for Cloud request failed: {e}"}
