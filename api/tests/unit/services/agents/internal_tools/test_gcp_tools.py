"""Tests for internal_gcp_* tool functions."""

from unittest.mock import AsyncMock, patch

import pytest

from src.services.agents.internal_tools.gcp_tools import (
    internal_gcp_get_logs,
    internal_gcp_get_metrics,
    internal_gcp_get_resource_health,
    internal_gcp_list_alerts,
    internal_gcp_list_security_findings,
)

_CFG = {"client_id": None, "api_token": "{}", "config": {"project_id": "proj"}}


@pytest.mark.unit
class TestGCPToolsNoRuntimeContext:
    @pytest.mark.asyncio
    async def test_get_logs_without_runtime_context(self):
        result = await internal_gcp_get_logs(runtime_context=None, log_source="x", start_time="a", end_time="b")
        assert result == {"success": False, "error": "No runtime context available."}


@pytest.mark.unit
class TestGCPToolsHappyPath:
    @pytest.mark.asyncio
    async def test_get_logs_delegates_to_adapter(self):
        with (
            patch(
                "src.services.agents.internal_tools.gcp_tools.get_cloud_provider_config",
                new=AsyncMock(return_value=_CFG),
            ),
            patch("src.services.agents.internal_tools.gcp_tools.GCPAdapter") as MockAdapter,
        ):
            MockAdapter.return_value.get_logs = AsyncMock(return_value={"success": True, "error": None, "entries": []})
            result = await internal_gcp_get_logs(
                runtime_context=object(), log_source="my-log", start_time="a", end_time="b"
            )
            MockAdapter.assert_called_once_with(_CFG)
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_get_metrics_delegates_to_adapter(self):
        with (
            patch(
                "src.services.agents.internal_tools.gcp_tools.get_cloud_provider_config",
                new=AsyncMock(return_value=_CFG),
            ),
            patch("src.services.agents.internal_tools.gcp_tools.GCPAdapter") as MockAdapter,
        ):
            MockAdapter.return_value.get_metrics = AsyncMock(
                return_value={"success": True, "error": None, "datapoints": []}
            )
            result = await internal_gcp_get_metrics(
                runtime_context=object(),
                metric_name="compute.googleapis.com/instance/cpu/utilization",
                start_time="a",
                end_time="b",
            )
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_list_alerts_delegates_to_adapter(self):
        with (
            patch(
                "src.services.agents.internal_tools.gcp_tools.get_cloud_provider_config",
                new=AsyncMock(return_value=_CFG),
            ),
            patch("src.services.agents.internal_tools.gcp_tools.GCPAdapter") as MockAdapter,
        ):
            MockAdapter.return_value.list_alerts = AsyncMock(
                return_value={"success": True, "error": None, "alerts": []}
            )
            result = await internal_gcp_list_alerts(runtime_context=object())
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_get_resource_health_delegates_to_adapter(self):
        with (
            patch(
                "src.services.agents.internal_tools.gcp_tools.get_cloud_provider_config",
                new=AsyncMock(return_value=_CFG),
            ),
            patch("src.services.agents.internal_tools.gcp_tools.GCPAdapter") as MockAdapter,
        ):
            MockAdapter.return_value.get_resource_health = AsyncMock(
                return_value={"success": True, "error": None, "instances": []}
            )
            result = await internal_gcp_get_resource_health(runtime_context=object())
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_list_security_findings_delegates_to_adapter(self):
        with (
            patch(
                "src.services.agents.internal_tools.gcp_tools.get_cloud_provider_config",
                new=AsyncMock(return_value=_CFG),
            ),
            patch("src.services.agents.internal_tools.gcp_tools.GCPAdapter") as MockAdapter,
        ):
            MockAdapter.return_value.list_security_findings = AsyncMock(
                return_value={"success": True, "error": None, "findings": []}
            )
            result = await internal_gcp_list_security_findings(runtime_context=object())
            assert result["success"] is True


@pytest.mark.unit
class TestGCPToolsCredentialError:
    @pytest.mark.asyncio
    async def test_returns_error_dict_when_credential_resolution_fails(self):
        with patch(
            "src.services.agents.internal_tools.gcp_tools.get_cloud_provider_config",
            new=AsyncMock(side_effect=ValueError("No OAuth app configured for tool 'x'.")),
        ):
            result = await internal_gcp_list_alerts(runtime_context=object())
            assert result == {"success": False, "error": "No OAuth app configured for tool 'x'."}
