"""Tests for AWSAdapter using moto to mock AWS APIs."""

from unittest.mock import patch

import boto3
import pytest
from botocore.config import Config
from botocore.exceptions import ClientError
from moto import mock_aws

from src.services.cloud_providers.aws_adapter import AWSAdapter

# This dev environment sets AWS_ENDPOINT_URL for the MinIO integration, which botocore
# would otherwise apply to every AWS client — including ones created directly in these
# tests for seeding moto data. Ignore it here too, same as AWSAdapter itself does.
_IGNORE_ENV_ENDPOINT_CONFIG = Config(ignore_configured_endpoint_urls=True)


def _credentials(region="us-east-1"):
    return {
        "client_id": "testing",
        "api_token": "testing",
        "config": {"region": region},
    }


@pytest.mark.unit
class TestAWSAdapterInit:
    def test_builds_boto3_session_from_credentials(self):
        adapter = AWSAdapter(_credentials())
        creds = adapter.session.get_credentials()
        assert creds.access_key == "testing"
        assert creds.secret_key == "testing"
        assert adapter.session.region_name == "us-east-1"

    def test_defaults_region_when_missing(self):
        adapter = AWSAdapter({"client_id": "testing", "api_token": "testing", "config": {}})
        assert adapter.session.region_name == "us-east-1"


@pytest.mark.unit
class TestAWSAdapterListAlerts:
    @pytest.mark.asyncio
    async def test_list_alerts_returns_alarms(self):
        with mock_aws():
            client = boto3.client("cloudwatch", region_name="us-east-1", config=_IGNORE_ENV_ENDPOINT_CONFIG)
            client.put_metric_alarm(
                AlarmName="high-cpu",
                MetricName="CPUUtilization",
                Namespace="AWS/EC2",
                Statistic="Average",
                Period=300,
                EvaluationPeriods=1,
                Threshold=80.0,
                ComparisonOperator="GreaterThanThreshold",
            )

            adapter = AWSAdapter(_credentials())
            result = await adapter.list_alerts(active_only=False)

            assert result["success"] is True
            assert any(a["AlarmName"] == "high-cpu" for a in result["alerts"])

    @pytest.mark.asyncio
    async def test_list_alerts_wraps_client_error(self):
        with mock_aws():
            adapter = AWSAdapter(_credentials())
            client_error = ClientError({"Error": {"Code": "Throttling", "Message": "Rate exceeded"}}, "DescribeAlarms")
            with patch("botocore.client.BaseClient._make_api_call", side_effect=client_error):
                result = await adapter.list_alerts()
            assert result["success"] is False
            assert "error" in result


@pytest.mark.unit
class TestAWSAdapterResourceHealth:
    @pytest.mark.asyncio
    async def test_get_resource_health_no_instances(self):
        with mock_aws():
            adapter = AWSAdapter(_credentials())
            result = await adapter.get_resource_health()
            assert result["success"] is True
            assert result["instances"] == []


@pytest.mark.unit
class TestAWSAdapterSecurityFindings:
    @pytest.mark.asyncio
    async def test_list_security_findings_when_hub_not_enabled(self):
        with mock_aws():
            adapter = AWSAdapter(_credentials())
            result = await adapter.list_security_findings()
            # Security Hub is not enabled by default in moto — must fail gracefully, not raise.
            assert isinstance(result, dict)
            assert "success" in result


@pytest.mark.unit
class TestAWSAdapterLogsAndMetrics:
    @pytest.mark.asyncio
    async def test_get_logs_missing_log_group_returns_user_actionable_error(self):
        with mock_aws():
            adapter = AWSAdapter(_credentials())
            result = await adapter.get_logs(
                log_source="/aws/lambda/does-not-exist",
                start_time="2026-01-01T00:00:00Z",
                end_time="2026-01-02T00:00:00Z",
            )
            assert result["success"] is False
            assert "does not exist" in result["error"].lower() or "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_get_metrics_returns_datapoints_shape(self):
        with mock_aws():
            adapter = AWSAdapter(_credentials())
            result = await adapter.get_metrics(
                metric_name="CPUUtilization",
                start_time="2026-01-01T00:00:00Z",
                end_time="2026-01-02T00:00:00Z",
            )
            assert result["success"] is True
            assert "datapoints" in result
