"""Tests for DigitalOceanAdapter (Droplet metrics/alerts/health; logs & findings unsupported)."""

import pytest

from src.services.cloud_providers.digitalocean_adapter import DigitalOceanAdapter


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.is_success = 200 <= status_code < 300
        self.text = str(json_data)

    def json(self):
        return self._json_data


class _FakeAsyncClient:
    responses: dict[str, _FakeResponse] = {}

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def request(self, method, url, **kwargs):
        for substring, resp in type(self).responses.items():
            if substring in url:
                return resp
        raise AssertionError(f"No fake response configured for {method} {url}")


@pytest.fixture(autouse=True)
def _reset_fake_client(monkeypatch):
    import httpx

    _FakeAsyncClient.responses = {}
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    yield


def _credentials():
    return {"client_id": "", "api_token": "do-pat-token", "config": {}}


class TestUnsupportedCapabilities:
    @pytest.mark.asyncio
    async def test_get_logs_not_supported(self):
        adapter = DigitalOceanAdapter(_credentials())

        result = await adapter.get_logs(log_source="droplet-1", start_time="t0", end_time="t1")

        assert result == {"success": False, "error": "Not supported by DigitalOcean"}

    @pytest.mark.asyncio
    async def test_list_security_findings_not_supported(self):
        adapter = DigitalOceanAdapter(_credentials())

        result = await adapter.list_security_findings()

        assert result == {"success": False, "error": "Not supported by DigitalOcean"}


class TestGetMetrics:
    @pytest.mark.asyncio
    async def test_get_metrics_success(self):
        _FakeAsyncClient.responses = {
            "monitoring/metrics/droplet/cpu": _FakeResponse(
                200, {"data": {"result": [{"metric": {}, "values": [[1723766400, "12.5"]]}]}}
            ),
        }
        adapter = DigitalOceanAdapter(_credentials())

        result = await adapter.get_metrics(
            metric_name="cpu", start_time="1723766000", end_time="1723766400", resource_id="12345"
        )

        assert result["success"] is True
        assert result["data"][0]["values"][0][1] == "12.5"

    @pytest.mark.asyncio
    async def test_get_metrics_requires_resource_id(self):
        adapter = DigitalOceanAdapter(_credentials())

        result = await adapter.get_metrics(metric_name="cpu", start_time="t0", end_time="t1")

        assert result["success"] is False
        assert "resource_id" in result["error"]


class TestListAlerts:
    @pytest.mark.asyncio
    async def test_list_alerts_filters_enabled(self):
        _FakeAsyncClient.responses = {
            "monitoring/alerts": _FakeResponse(
                200,
                {
                    "policies": [
                        {"uuid": "p1", "enabled": True},
                        {"uuid": "p2", "enabled": False},
                    ]
                },
            ),
        }
        adapter = DigitalOceanAdapter(_credentials())

        result = await adapter.list_alerts(active_only=True)

        assert result["success"] is True
        assert len(result["data"]) == 1
        assert result["data"][0]["uuid"] == "p1"


class TestGetResourceHealth:
    @pytest.mark.asyncio
    async def test_get_resource_health_success(self):
        _FakeAsyncClient.responses = {
            "droplets/12345": _FakeResponse(200, {"droplet": {"id": 12345, "status": "active"}}),
        }
        adapter = DigitalOceanAdapter(_credentials())

        result = await adapter.get_resource_health(resource_id="12345")

        assert result["success"] is True
        assert result["data"]["status"] == "active"

    @pytest.mark.asyncio
    async def test_get_resource_health_requires_resource_id(self):
        adapter = DigitalOceanAdapter(_credentials())

        result = await adapter.get_resource_health(resource_id="")

        assert result["success"] is False
        assert "resource_id" in result["error"]

    @pytest.mark.asyncio
    async def test_get_resource_health_auth_failure(self):
        _FakeAsyncClient.responses = {
            "droplets/12345": _FakeResponse(401, {"message": "Unable to authenticate"}),
        }
        adapter = DigitalOceanAdapter(_credentials())

        result = await adapter.get_resource_health(resource_id="12345")

        assert result["success"] is False
        assert "invalid or expired" in result["error"]
