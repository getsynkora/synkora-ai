import pytest

from src.services.cloud_providers.base_adapter import CloudProviderAdapter


class _FakeAdapter(CloudProviderAdapter):
    async def get_logs(self, log_source, start_time, end_time, filter_query="", limit=100):
        return self._ok(entries=["line1"])

    async def get_metrics(self, metric_name, start_time, end_time, resource_id="", period_seconds=300):
        return self._fail("not implemented in fake")

    async def list_alerts(self, active_only=True):
        return self._ok(alerts=[])

    async def get_resource_health(self, resource_id=""):
        return self._ok(status="healthy")

    async def list_security_findings(self, severity=""):
        return self._ok(findings=[])


@pytest.mark.unit
class TestCloudProviderAdapter:
    def test_cannot_instantiate_base_class_directly(self):
        with pytest.raises(TypeError):
            CloudProviderAdapter(credentials={})

    @pytest.mark.asyncio
    async def test_ok_helper_shape(self):
        adapter = _FakeAdapter(credentials={"api_token": "x"})
        result = await adapter.get_logs("app-logs", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z")
        assert result == {"success": True, "error": None, "entries": ["line1"]}

    @pytest.mark.asyncio
    async def test_fail_helper_shape(self):
        adapter = _FakeAdapter(credentials={"api_token": "x"})
        result = await adapter.get_metrics("cpu", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z")
        assert result == {"success": False, "error": "not implemented in fake"}

    def test_stores_credentials(self):
        adapter = _FakeAdapter(credentials={"api_token": "secret"})
        assert adapter.credentials == {"api_token": "secret"}
