"""Tests for AzureAdapter (Azure Monitor Logs/Metrics/Alerts, Resource Health, Defender)."""

import pytest

from src.services.cloud_providers.azure_adapter import AzureAdapter


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.is_success = 200 <= status_code < 300
        self.text = str(json_data)

    def json(self):
        return self._json_data


class _FakeAsyncClient:
    """Routes requests by URL substring against a class-level `responses` dict.

    Each test sets `_FakeAsyncClient.responses = {"substring": _FakeResponse(...)}`
    before invoking the adapter, mirroring the pattern already used in
    tests/unit/services/slack/test_slack_message_handler.py for httpx mocking.
    """

    responses: dict[str, _FakeResponse] = {}
    requests: list[tuple[str, str, dict]] = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, **kwargs):
        type(self).requests.append(("POST", url, kwargs))
        for substring, resp in type(self).responses.items():
            if substring in url:
                return resp
        raise AssertionError(f"No fake response configured for POST {url}")

    async def request(self, method, url, **kwargs):
        type(self).requests.append((method, url, kwargs))
        for substring, resp in type(self).responses.items():
            if substring in url:
                return resp
        raise AssertionError(f"No fake response configured for {method} {url}")


@pytest.fixture(autouse=True)
def _reset_fake_client(monkeypatch):
    import httpx

    _FakeAsyncClient.responses = {}
    _FakeAsyncClient.requests = []
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    yield


def _credentials(config=None):
    return {
        "client_id": "app-client-id",
        "api_token": "app-client-secret",
        "config": config or {"azure_tenant_id": "tenant-123", "subscription_id": "sub-456"},
    }


class TestAzureAdapterInit:
    def test_stores_tenant_subscription_and_app_credentials(self):
        adapter = AzureAdapter(_credentials())

        assert adapter.tenant_id == "tenant-123"
        assert adapter.subscription_id == "sub-456"
        assert adapter.client_id == "app-client-id"
        assert adapter.client_secret == "app-client-secret"


class TestGetLogs:
    @pytest.mark.asyncio
    async def test_get_logs_success(self):
        _FakeAsyncClient.responses = {
            "oauth2/v2.0/token": _FakeResponse(200, {"access_token": "tok-logs"}),
            "query": _FakeResponse(
                200,
                {
                    "tables": [
                        {
                            "columns": [{"name": "TimeGenerated"}, {"name": "Message"}],
                            "rows": [["2026-08-16T00:00:00Z", "disk usage high"]],
                        }
                    ]
                },
            ),
        }
        adapter = AzureAdapter(_credentials())

        result = await adapter.get_logs(
            log_source="workspace-abc",
            start_time="2026-08-16T00:00:00Z",
            end_time="2026-08-16T01:00:00Z",
        )

        assert result["success"] is True
        assert result["data"][0]["Message"] == "disk usage high"

    @pytest.mark.asyncio
    async def test_get_logs_token_exchange_failure(self):
        _FakeAsyncClient.responses = {
            "oauth2/v2.0/token": _FakeResponse(401, {"error": "invalid_client"}),
        }
        adapter = AzureAdapter(_credentials())

        result = await adapter.get_logs(
            log_source="workspace-abc", start_time="2026-08-16T00:00:00Z", end_time="2026-08-16T01:00:00Z"
        )

        assert result["success"] is False
        assert "invalid or expired" in result["error"]


class TestGetMetrics:
    @pytest.mark.asyncio
    async def test_get_metrics_requires_resource_id(self):
        adapter = AzureAdapter(_credentials())

        result = await adapter.get_metrics(
            metric_name="Percentage CPU", start_time="2026-08-16T00:00:00Z", end_time="2026-08-16T01:00:00Z"
        )

        assert result["success"] is False
        assert "resource_id" in result["error"]

    @pytest.mark.asyncio
    async def test_get_metrics_success(self):
        _FakeAsyncClient.responses = {
            "oauth2/v2.0/token": _FakeResponse(200, {"access_token": "tok-mgmt"}),
            "/providers/microsoft.insights/metrics": _FakeResponse(
                200,
                {"value": [{"name": {"value": "Percentage CPU"}, "timeseries": [{"data": [{"average": 12.5}]}]}]},
            ),
        }
        adapter = AzureAdapter(_credentials())

        result = await adapter.get_metrics(
            metric_name="Percentage CPU",
            start_time="2026-08-16T00:00:00Z",
            end_time="2026-08-16T01:00:00Z",
            resource_id="/subscriptions/sub-456/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
        )

        assert result["success"] is True
        assert result["data"][0]["name"]["value"] == "Percentage CPU"


class TestListAlerts:
    @pytest.mark.asyncio
    async def test_list_alerts_filters_active(self):
        _FakeAsyncClient.responses = {
            "oauth2/v2.0/token": _FakeResponse(200, {"access_token": "tok-mgmt"}),
            "providers/Microsoft.AlertsManagement/alerts": _FakeResponse(
                200,
                {
                    "value": [
                        {"properties": {"essentials": {"alertState": "New"}}},
                        {"properties": {"essentials": {"alertState": "Closed"}}},
                    ]
                },
            ),
        }
        adapter = AzureAdapter(_credentials())

        result = await adapter.list_alerts(active_only=True)

        assert result["success"] is True
        assert len(result["data"]) == 1
        assert result["data"][0]["properties"]["essentials"]["alertState"] == "New"


class TestGetResourceHealth:
    @pytest.mark.asyncio
    async def test_get_resource_health_requires_resource_id(self):
        adapter = AzureAdapter(_credentials())

        result = await adapter.get_resource_health(resource_id="")

        assert result["success"] is False
        assert "resource_id" in result["error"]

    @pytest.mark.asyncio
    async def test_get_resource_health_success(self):
        _FakeAsyncClient.responses = {
            "oauth2/v2.0/token": _FakeResponse(200, {"access_token": "tok-mgmt"}),
            "providers/Microsoft.ResourceHealth/availabilityStatuses": _FakeResponse(
                200, {"properties": {"availabilityState": "Available"}}
            ),
        }
        adapter = AzureAdapter(_credentials())

        result = await adapter.get_resource_health(
            resource_id="/subscriptions/sub-456/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1"
        )

        assert result["success"] is True
        assert result["data"]["properties"]["availabilityState"] == "Available"


class TestListSecurityFindings:
    @pytest.mark.asyncio
    async def test_list_security_findings_filters_by_severity(self):
        _FakeAsyncClient.responses = {
            "oauth2/v2.0/token": _FakeResponse(200, {"access_token": "tok-mgmt"}),
            "providers/Microsoft.Security/assessments": _FakeResponse(
                200,
                {
                    "value": [
                        {"properties": {"status": {"severity": "High"}}},
                        {"properties": {"status": {"severity": "Low"}}},
                    ]
                },
            ),
        }
        adapter = AzureAdapter(_credentials())

        result = await adapter.list_security_findings(severity="high")

        assert result["success"] is True
        assert len(result["data"]) == 1
        assert result["data"][0]["properties"]["status"]["severity"] == "High"
