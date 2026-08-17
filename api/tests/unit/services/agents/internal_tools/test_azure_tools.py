"""Tests for internal_azure_* tool functions."""

from unittest.mock import AsyncMock, patch

import pytest

from src.services.agents.internal_tools.azure_tools import (
    internal_azure_get_logs,
    internal_azure_get_metrics,
    internal_azure_get_resource_health,
    internal_azure_list_alerts,
    internal_azure_list_security_findings,
)


class _FakeRuntimeContext:
    agent_id = "agent-1"


@pytest.mark.asyncio
async def test_get_logs_no_runtime_context():
    result = await internal_azure_get_logs(runtime_context=None, log_source="ws-1", start_time="t0", end_time="t1")
    assert result["success"] is False
    assert "runtime context" in result["error"]


@pytest.mark.asyncio
async def test_get_logs_delegates_to_adapter():
    with (
        patch(
            "src.services.agents.internal_tools.azure_tools.get_cloud_provider_config",
            new=AsyncMock(return_value={"client_id": "c", "api_token": "s", "config": {}}),
        ),
        patch("src.services.agents.internal_tools.azure_tools.AzureAdapter") as MockAdapter,
    ):
        MockAdapter.return_value.get_logs = AsyncMock(return_value={"success": True, "data": []})

        result = await internal_azure_get_logs(
            runtime_context=_FakeRuntimeContext(), log_source="ws-1", start_time="t0", end_time="t1"
        )

        assert result == {"success": True, "data": []}
        MockAdapter.return_value.get_logs.assert_called_once_with(
            log_source="ws-1", start_time="t0", end_time="t1", filter_query="", limit=100
        )


@pytest.mark.asyncio
async def test_get_metrics_delegates_to_adapter():
    with (
        patch(
            "src.services.agents.internal_tools.azure_tools.get_cloud_provider_config",
            new=AsyncMock(return_value={"client_id": "c", "api_token": "s", "config": {}}),
        ),
        patch("src.services.agents.internal_tools.azure_tools.AzureAdapter") as MockAdapter,
    ):
        MockAdapter.return_value.get_metrics = AsyncMock(return_value={"success": True, "data": []})

        result = await internal_azure_get_metrics(
            runtime_context=_FakeRuntimeContext(),
            metric_name="Percentage CPU",
            start_time="t0",
            end_time="t1",
            resource_id="/subscriptions/s/resourceGroups/r/providers/Microsoft.Compute/virtualMachines/vm1",
        )

        assert result["success"] is True
        MockAdapter.return_value.get_metrics.assert_called_once()


@pytest.mark.asyncio
async def test_list_alerts_delegates_to_adapter():
    with (
        patch(
            "src.services.agents.internal_tools.azure_tools.get_cloud_provider_config",
            new=AsyncMock(return_value={"client_id": "c", "api_token": "s", "config": {}}),
        ),
        patch("src.services.agents.internal_tools.azure_tools.AzureAdapter") as MockAdapter,
    ):
        MockAdapter.return_value.list_alerts = AsyncMock(return_value={"success": True, "data": []})

        result = await internal_azure_list_alerts(runtime_context=_FakeRuntimeContext())

        assert result["success"] is True
        MockAdapter.return_value.list_alerts.assert_called_once_with(active_only=True)


@pytest.mark.asyncio
async def test_get_resource_health_delegates_to_adapter():
    with (
        patch(
            "src.services.agents.internal_tools.azure_tools.get_cloud_provider_config",
            new=AsyncMock(return_value={"client_id": "c", "api_token": "s", "config": {}}),
        ),
        patch("src.services.agents.internal_tools.azure_tools.AzureAdapter") as MockAdapter,
    ):
        MockAdapter.return_value.get_resource_health = AsyncMock(return_value={"success": True, "data": {}})

        result = await internal_azure_get_resource_health(
            runtime_context=_FakeRuntimeContext(), resource_id="/subscriptions/s/resourceGroups/r/x"
        )

        assert result["success"] is True
        MockAdapter.return_value.get_resource_health.assert_called_once_with(
            resource_id="/subscriptions/s/resourceGroups/r/x"
        )


@pytest.mark.asyncio
async def test_list_security_findings_delegates_to_adapter():
    with (
        patch(
            "src.services.agents.internal_tools.azure_tools.get_cloud_provider_config",
            new=AsyncMock(return_value={"client_id": "c", "api_token": "s", "config": {}}),
        ),
        patch("src.services.agents.internal_tools.azure_tools.AzureAdapter") as MockAdapter,
    ):
        MockAdapter.return_value.list_security_findings = AsyncMock(return_value={"success": True, "data": []})

        result = await internal_azure_list_security_findings(runtime_context=_FakeRuntimeContext(), severity="high")

        assert result["success"] is True
        MockAdapter.return_value.list_security_findings.assert_called_once_with(severity="high")


@pytest.mark.asyncio
async def test_credential_error_returns_failure_dict():
    with patch(
        "src.services.agents.internal_tools.azure_tools.get_cloud_provider_config",
        new=AsyncMock(side_effect=ValueError("No OAuth app configured for tool 'internal_azure_get_logs'.")),
    ):
        result = await internal_azure_get_logs(
            runtime_context=_FakeRuntimeContext(), log_source="ws-1", start_time="t0", end_time="t1"
        )

        assert result["success"] is False
        assert "No OAuth app configured" in result["error"]
