"""Unit tests for TypeSafe triage in AWS tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.agents.internal_tools.issue_triage import MIN_ISSUES_TO_TRIAGE, IssueTriageNote
from src.services.agents.internal_tools.log_triage import MIN_LINES_TO_TRIAGE, TriageNote


def _make_log_entries(n: int) -> list[dict]:
    return [{"timestamp": i * 1000, "message": f"log line {i}", "log_stream": "stream1"} for i in range(n)]


def _make_alarms(n: int) -> list[dict]:
    return [
        {
            "AlarmName": f"alarm-{i}",
            "StateValue": "ALARM",
            "MetricName": f"Metric{i}",
            "Namespace": "AWS/EC2",
            "Threshold": 80.0,
        }
        for i in range(n)
    ]


def _make_findings(n: int) -> list[dict]:
    return [
        {
            "Id": f"finding-{i}",
            "Title": f"Finding {i}",
            "Severity": "HIGH",
            "ResourceId": f"res-{i}",
            "Description": f"Desc {i}",
        }
        for i in range(n)
    ]


class TestAwsLogTriage:
    @pytest.mark.asyncio
    async def test_triage_note_in_result_on_success(self):
        """triage field appears in result when adapter.get_logs succeeds."""
        entries = _make_log_entries(MIN_LINES_TO_TRIAGE - 1)  # below min → triage skips
        adapter_result = {"success": True, "entries": entries}

        with (
            patch(
                "src.services.agents.internal_tools.aws_tools.get_cloud_provider_config",
                AsyncMock(return_value={}),
            ),
            patch("src.services.agents.internal_tools.aws_tools.AWSAdapter") as MockAdapter,
            patch(
                "src.services.agents.internal_tools.aws_tools._get_typesafe_client",
                AsyncMock(return_value=None),
            ),
        ):
            MockAdapter.return_value.get_logs = AsyncMock(return_value=adapter_result)

            from src.services.agents.internal_tools.aws_tools import internal_aws_get_logs

            result = await internal_aws_get_logs(
                runtime_context=MagicMock(),
                log_source="/aws/lambda/fn",
                start_time="2026-01-01T00:00:00Z",
                end_time="2026-01-01T01:00:00Z",
            )

        assert result["success"] is True
        assert "triage" in result
        assert result["triage"]["applied"] is False  # too few entries

    @pytest.mark.asyncio
    async def test_triage_not_added_on_failure(self):
        """triage field NOT added when adapter returns success=False."""
        with (
            patch(
                "src.services.agents.internal_tools.aws_tools.get_cloud_provider_config",
                AsyncMock(return_value={}),
            ),
            patch("src.services.agents.internal_tools.aws_tools.AWSAdapter") as MockAdapter,
            patch(
                "src.services.agents.internal_tools.aws_tools._get_typesafe_client",
                AsyncMock(return_value=None),
            ),
        ):
            MockAdapter.return_value.get_logs = AsyncMock(return_value={"success": False, "error": "no group"})

            from src.services.agents.internal_tools.aws_tools import internal_aws_get_logs

            result = await internal_aws_get_logs(runtime_context=MagicMock(), log_source="/aws/lambda/fn")

        assert result["success"] is False
        assert "triage" not in result


class TestAwsAlertTriage:
    @pytest.mark.asyncio
    async def test_triage_note_in_alert_result(self):
        """triage field appears in result for list_alerts."""
        alarms = _make_alarms(MIN_ISSUES_TO_TRIAGE - 1)  # below min → triage skips
        with (
            patch(
                "src.services.agents.internal_tools.aws_tools.get_cloud_provider_config",
                AsyncMock(return_value={}),
            ),
            patch("src.services.agents.internal_tools.aws_tools.AWSAdapter") as MockAdapter,
            patch(
                "src.services.agents.internal_tools.aws_tools._get_typesafe_client",
                AsyncMock(return_value=None),
            ),
        ):
            MockAdapter.return_value.list_alerts = AsyncMock(return_value={"success": True, "alerts": alarms})

            from src.services.agents.internal_tools.aws_tools import internal_aws_list_alerts

            result = await internal_aws_list_alerts(runtime_context=MagicMock())

        assert result["success"] is True
        assert "triage" in result
        assert result["triage"]["applied"] is False


class TestAwsFindingTriage:
    @pytest.mark.asyncio
    async def test_triage_note_in_findings_result(self):
        """triage field appears in result for list_security_findings."""
        findings = _make_findings(MIN_ISSUES_TO_TRIAGE - 1)
        with (
            patch(
                "src.services.agents.internal_tools.aws_tools.get_cloud_provider_config",
                AsyncMock(return_value={}),
            ),
            patch("src.services.agents.internal_tools.aws_tools.AWSAdapter") as MockAdapter,
            patch(
                "src.services.agents.internal_tools.aws_tools._get_typesafe_client",
                AsyncMock(return_value=None),
            ),
        ):
            MockAdapter.return_value.list_security_findings = AsyncMock(
                return_value={"success": True, "findings": findings}
            )

            from src.services.agents.internal_tools.aws_tools import internal_aws_list_security_findings

            result = await internal_aws_list_security_findings(runtime_context=MagicMock())

        assert result["success"] is True
        assert "triage" in result
        assert result["triage"]["applied"] is False
