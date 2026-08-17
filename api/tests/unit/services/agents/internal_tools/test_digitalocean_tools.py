"""Tests for internal_digitalocean_* tool functions."""

from unittest.mock import AsyncMock, patch

import pytest

from src.services.agents.internal_tools.digitalocean_tools import (
    internal_digitalocean_get_logs,
    internal_digitalocean_get_metrics,
    internal_digitalocean_get_resource_health,
    internal_digitalocean_list_alerts,
    internal_digitalocean_list_security_findings,
)


class _FakeRuntimeContext:
    agent_id = "agent-1"


@pytest.mark.asyncio
async def test_get_metrics_no_runtime_context():
    result = await internal_digitalocean_get_metrics(
        runtime_context=None, metric_name="cpu", start_time="t0", end_time="t1", resource_id="123"
    )
    assert result["success"] is False
    assert "runtime context" in result["error"]


@pytest.mark.asyncio
async def test_get_metrics_delegates_to_adapter():
    with (
        patch(
            "src.services.agents.internal_tools.digitalocean_tools.get_cloud_provider_config",
            new=AsyncMock(return_value={"client_id": "", "api_token": "s", "config": {}}),
        ),
        patch("src.services.agents.internal_tools.digitalocean_tools.DigitalOceanAdapter") as MockAdapter,
    ):
        MockAdapter.return_value.get_metrics = AsyncMock(return_value={"success": True, "data": []})

        result = await internal_digitalocean_get_metrics(
            runtime_context=_FakeRuntimeContext(), metric_name="cpu", start_time="t0", end_time="t1", resource_id="123"
        )

        assert result["success"] is True
        MockAdapter.return_value.get_metrics.assert_called_once_with(
            metric_name="cpu", start_time="t0", end_time="t1", resource_id="123", period_seconds=300
        )


@pytest.mark.asyncio
async def test_list_alerts_delegates_to_adapter():
    with (
        patch(
            "src.services.agents.internal_tools.digitalocean_tools.get_cloud_provider_config",
            new=AsyncMock(return_value={"client_id": "", "api_token": "s", "config": {}}),
        ),
        patch("src.services.agents.internal_tools.digitalocean_tools.DigitalOceanAdapter") as MockAdapter,
    ):
        MockAdapter.return_value.list_alerts = AsyncMock(return_value={"success": True, "data": []})

        result = await internal_digitalocean_list_alerts(runtime_context=_FakeRuntimeContext())

        assert result["success"] is True
        MockAdapter.return_value.list_alerts.assert_called_once_with(active_only=True)


@pytest.mark.asyncio
async def test_get_resource_health_delegates_to_adapter():
    with (
        patch(
            "src.services.agents.internal_tools.digitalocean_tools.get_cloud_provider_config",
            new=AsyncMock(return_value={"client_id": "", "api_token": "s", "config": {}}),
        ),
        patch("src.services.agents.internal_tools.digitalocean_tools.DigitalOceanAdapter") as MockAdapter,
    ):
        MockAdapter.return_value.get_resource_health = AsyncMock(return_value={"success": True, "data": {}})

        result = await internal_digitalocean_get_resource_health(
            runtime_context=_FakeRuntimeContext(), resource_id="123"
        )

        assert result["success"] is True
        MockAdapter.return_value.get_resource_health.assert_called_once_with(resource_id="123")


@pytest.mark.asyncio
async def test_get_logs_returns_not_supported_without_credential_lookup():
    with patch(
        "src.services.agents.internal_tools.digitalocean_tools.get_cloud_provider_config",
        new=AsyncMock(return_value={"client_id": "", "api_token": "s", "config": {}}),
    ):
        result = await internal_digitalocean_get_logs(
            runtime_context=_FakeRuntimeContext(), log_source="d-1", start_time="t0", end_time="t1"
        )

        assert result == {"success": False, "error": "Not supported by DigitalOcean"}


@pytest.mark.asyncio
async def test_list_security_findings_returns_not_supported():
    with patch(
        "src.services.agents.internal_tools.digitalocean_tools.get_cloud_provider_config",
        new=AsyncMock(return_value={"client_id": "", "api_token": "s", "config": {}}),
    ):
        result = await internal_digitalocean_list_security_findings(runtime_context=_FakeRuntimeContext())

        assert result == {"success": False, "error": "Not supported by DigitalOcean"}


@pytest.mark.asyncio
async def test_credential_error_returns_failure_dict():
    with patch(
        "src.services.agents.internal_tools.digitalocean_tools.get_cloud_provider_config",
        new=AsyncMock(side_effect=ValueError("No OAuth app configured for tool 'internal_digitalocean_list_alerts'.")),
    ):
        result = await internal_digitalocean_list_alerts(runtime_context=_FakeRuntimeContext())

        assert result["success"] is False
        assert "No OAuth app configured" in result["error"]
