"""Tests for register_azure_tools() ADK registry wiring."""

from unittest.mock import AsyncMock, patch

import pytest

from src.services.agents.adk_tools import ADKToolRegistry
from src.services.agents.tool_registrations.azure_tools_registry import register_azure_tools

_AZURE_TOOL_NAMES = [
    "internal_azure_get_logs",
    "internal_azure_get_metrics",
    "internal_azure_list_alerts",
    "internal_azure_get_resource_health",
    "internal_azure_list_security_findings",
]


def test_register_azure_tools_registers_all_five():
    registry = ADKToolRegistry.__new__(ADKToolRegistry)
    registry.tools = {}
    register_azure_tools(registry)

    for name in _AZURE_TOOL_NAMES:
        assert name in registry.tools
        assert registry.tools[name]["requires_auth"] == "azure"
        assert registry.tools[name]["tool_category"] == "read"


@pytest.mark.asyncio
async def test_get_logs_wrapper_forwards_runtime_context():
    registry = ADKToolRegistry.__new__(ADKToolRegistry)
    registry.tools = {}
    register_azure_tools(registry)
    wrapper = registry.tools["internal_azure_get_logs"]["function"]

    with patch(
        "src.services.agents.tool_registrations.azure_tools_registry.internal_azure_get_logs",
        new=AsyncMock(return_value={"success": True, "data": []}),
    ) as mock_fn:
        fake_context = object()
        result = await wrapper(
            config={"_runtime_context": fake_context},
            log_source="ws-1",
            start_time="t0",
            end_time="t1",
        )

        assert result == {"success": True, "data": []}
        mock_fn.assert_called_once_with(
            runtime_context=fake_context, log_source="ws-1", start_time="t0", end_time="t1", filter_query="", limit=100
        )
