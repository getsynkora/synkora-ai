"""Tests for register_digitalocean_tools() ADK registry wiring."""

from unittest.mock import AsyncMock, patch

import pytest

from src.services.agents.adk_tools import ADKToolRegistry
from src.services.agents.tool_registrations.digitalocean_tools_registry import register_digitalocean_tools

_DO_TOOL_NAMES = [
    "internal_digitalocean_get_logs",
    "internal_digitalocean_get_metrics",
    "internal_digitalocean_list_alerts",
    "internal_digitalocean_get_resource_health",
    "internal_digitalocean_list_security_findings",
]


def test_register_digitalocean_tools_registers_all_five():
    registry = ADKToolRegistry.__new__(ADKToolRegistry)
    registry.tools = {}
    register_digitalocean_tools(registry)

    for name in _DO_TOOL_NAMES:
        assert name in registry.tools
        assert registry.tools[name]["requires_auth"] == "digitalocean"
        assert registry.tools[name]["tool_category"] == "read"


@pytest.mark.asyncio
async def test_get_metrics_wrapper_forwards_runtime_context():
    registry = ADKToolRegistry.__new__(ADKToolRegistry)
    registry.tools = {}
    register_digitalocean_tools(registry)
    wrapper = registry.tools["internal_digitalocean_get_metrics"]["function"]

    with patch(
        "src.services.agents.tool_registrations.digitalocean_tools_registry.internal_digitalocean_get_metrics",
        new=AsyncMock(return_value={"success": True, "data": []}),
    ) as mock_fn:
        fake_context = object()
        result = await wrapper(
            config={"_runtime_context": fake_context},
            metric_name="cpu",
            start_time="t0",
            end_time="t1",
            resource_id="123",
        )

        assert result == {"success": True, "data": []}
        mock_fn.assert_called_once_with(
            runtime_context=fake_context,
            metric_name="cpu",
            start_time="t0",
            end_time="t1",
            resource_id="123",
            period_seconds=300,
        )
