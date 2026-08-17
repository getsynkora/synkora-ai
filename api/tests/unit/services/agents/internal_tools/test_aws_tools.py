"""Tests for internal_aws_* tool functions."""

from unittest.mock import AsyncMock, patch

import pytest

from src.services.agents.internal_tools.aws_tools import (
    internal_aws_get_logs,
    internal_aws_get_metrics,
    internal_aws_get_resource_health,
    internal_aws_list_alerts,
    internal_aws_list_security_findings,
)

_CFG = {"client_id": "AKIA", "api_token": "secret", "config": {"region": "us-east-1"}}


@pytest.mark.unit
class TestAWSToolsNoRuntimeContext:
    @pytest.mark.asyncio
    async def test_get_logs_without_runtime_context(self):
        result = await internal_aws_get_logs(runtime_context=None, log_source="x", start_time="a", end_time="b")
        assert result == {"success": False, "error": "No runtime context available."}


@pytest.mark.unit
class TestAWSToolsHappyPath:
    @pytest.mark.asyncio
    async def test_get_logs_delegates_to_adapter(self):
        with (
            patch(
                "src.services.agents.internal_tools.aws_tools.get_cloud_provider_config",
                new=AsyncMock(return_value=_CFG),
            ),
            patch("src.services.agents.internal_tools.aws_tools.AWSAdapter") as MockAdapter,
        ):
            MockAdapter.return_value.get_logs = AsyncMock(return_value={"success": True, "error": None, "entries": []})
            result = await internal_aws_get_logs(
                runtime_context=object(), log_source="/aws/lambda/foo", start_time="a", end_time="b"
            )
            MockAdapter.assert_called_once_with(_CFG)
            MockAdapter.return_value.get_logs.assert_called_once_with(
                log_source="/aws/lambda/foo", start_time="a", end_time="b", filter_query="", limit=100
            )
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_get_metrics_delegates_to_adapter(self):
        with (
            patch(
                "src.services.agents.internal_tools.aws_tools.get_cloud_provider_config",
                new=AsyncMock(return_value=_CFG),
            ),
            patch("src.services.agents.internal_tools.aws_tools.AWSAdapter") as MockAdapter,
        ):
            MockAdapter.return_value.get_metrics = AsyncMock(
                return_value={"success": True, "error": None, "datapoints": []}
            )
            result = await internal_aws_get_metrics(
                runtime_context=object(), metric_name="CPUUtilization", start_time="a", end_time="b"
            )
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_list_alerts_delegates_to_adapter(self):
        with (
            patch(
                "src.services.agents.internal_tools.aws_tools.get_cloud_provider_config",
                new=AsyncMock(return_value=_CFG),
            ),
            patch("src.services.agents.internal_tools.aws_tools.AWSAdapter") as MockAdapter,
        ):
            MockAdapter.return_value.list_alerts = AsyncMock(
                return_value={"success": True, "error": None, "alerts": []}
            )
            result = await internal_aws_list_alerts(runtime_context=object())
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_get_resource_health_delegates_to_adapter(self):
        with (
            patch(
                "src.services.agents.internal_tools.aws_tools.get_cloud_provider_config",
                new=AsyncMock(return_value=_CFG),
            ),
            patch("src.services.agents.internal_tools.aws_tools.AWSAdapter") as MockAdapter,
        ):
            MockAdapter.return_value.get_resource_health = AsyncMock(
                return_value={"success": True, "error": None, "instances": []}
            )
            result = await internal_aws_get_resource_health(runtime_context=object())
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_list_security_findings_delegates_to_adapter(self):
        with (
            patch(
                "src.services.agents.internal_tools.aws_tools.get_cloud_provider_config",
                new=AsyncMock(return_value=_CFG),
            ),
            patch("src.services.agents.internal_tools.aws_tools.AWSAdapter") as MockAdapter,
        ):
            MockAdapter.return_value.list_security_findings = AsyncMock(
                return_value={"success": True, "error": None, "findings": []}
            )
            result = await internal_aws_list_security_findings(runtime_context=object())
            assert result["success"] is True


@pytest.mark.unit
class TestAWSToolsCredentialError:
    @pytest.mark.asyncio
    async def test_returns_error_dict_when_credential_resolution_fails(self):
        with patch(
            "src.services.agents.internal_tools.aws_tools.get_cloud_provider_config",
            new=AsyncMock(side_effect=ValueError("No OAuth app configured for tool 'x'.")),
        ):
            result = await internal_aws_list_alerts(runtime_context=object())
            assert result == {"success": False, "error": "No OAuth app configured for tool 'x'."}
