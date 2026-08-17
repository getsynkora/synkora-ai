"""Tests for GCPAdapter using a fake httpx.AsyncClient (no respx dependency)."""

import json

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from src.services.cloud_providers.gcp_adapter import GCPAdapter


def _test_private_key_pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


_PRIVATE_KEY_PEM = _test_private_key_pem()


def _credentials(project_id="my-project"):
    service_account = {
        "type": "service_account",
        "project_id": project_id,
        "private_key": _PRIVATE_KEY_PEM,
        "client_email": "agent@my-project.iam.gserviceaccount.com",
    }
    return {
        "client_id": None,
        "api_token": json.dumps(service_account),
        "config": {"project_id": project_id},
    }


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = json.dumps(self._json)

    @property
    def is_success(self):
        return 200 <= self.status_code < 300

    def json(self):
        return self._json


class _FakeAsyncClient:
    """Routes requests by matching a substring of the URL against `responses`."""

    responses: dict[str, _FakeResponse] = {}

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    def _resolve(self, url):
        for key, resp in self.responses.items():
            if key in url:
                return resp
        raise AssertionError(f"unexpected URL in test: {url}")

    async def post(self, url, **kwargs):
        return self._resolve(url)

    async def get(self, url, **kwargs):
        return self._resolve(url)

    async def request(self, method, url, **kwargs):
        return self._resolve(url)


@pytest.fixture(autouse=True)
def _patch_httpx(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.responses = {
        "oauth2.googleapis.com/token": _FakeResponse(json_data={"access_token": "fake-access-token"}),
    }
    yield


@pytest.mark.unit
class TestGCPAdapterInit:
    def test_parses_service_account_and_project_id(self):
        adapter = GCPAdapter(_credentials(project_id="proj-a"))
        assert adapter.project_id == "proj-a"
        assert adapter.service_account["client_email"] == "agent@my-project.iam.gserviceaccount.com"

    def test_falls_back_to_service_account_project_id_when_config_missing(self):
        creds = _credentials(project_id="proj-b")
        creds["config"] = {}
        adapter = GCPAdapter(creds)
        assert adapter.project_id == "proj-b"


@pytest.mark.unit
class TestGCPAdapterGetLogs:
    @pytest.mark.asyncio
    async def test_get_logs_returns_entries(self):
        _FakeAsyncClient.responses["logging.googleapis.com"] = _FakeResponse(
            json_data={"entries": [{"textPayload": "hello"}]}
        )
        adapter = GCPAdapter(_credentials())
        result = await adapter.get_logs("my-log", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z")
        assert result["success"] is True
        assert result["entries"] == [{"textPayload": "hello"}]

    @pytest.mark.asyncio
    async def test_get_logs_returns_error_on_failed_token_exchange(self):
        _FakeAsyncClient.responses["oauth2.googleapis.com/token"] = _FakeResponse(status_code=401, json_data={})
        adapter = GCPAdapter(_credentials())
        result = await adapter.get_logs("my-log", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z")
        assert result["success"] is False
        assert "credentials are invalid" in result["error"]


@pytest.mark.unit
class TestGCPAdapterOtherCapabilities:
    @pytest.mark.asyncio
    async def test_get_metrics_returns_datapoints(self):
        _FakeAsyncClient.responses["monitoring.googleapis.com"] = _FakeResponse(
            json_data={"timeSeries": [{"points": []}]}
        )
        adapter = GCPAdapter(_credentials())
        result = await adapter.get_metrics("compute.googleapis.com/instance/cpu/utilization", "a", "b")
        assert result["success"] is True
        assert result["datapoints"] == [{"points": []}]

    @pytest.mark.asyncio
    async def test_list_alerts_filters_disabled_when_active_only(self):
        _FakeAsyncClient.responses["monitoring.googleapis.com"] = _FakeResponse(
            json_data={
                "alertPolicies": [{"displayName": "on", "enabled": True}, {"displayName": "off", "enabled": False}]
            }
        )
        adapter = GCPAdapter(_credentials())
        result = await adapter.list_alerts(active_only=True)
        assert result["success"] is True
        assert [a["displayName"] for a in result["alerts"]] == ["on"]

    @pytest.mark.asyncio
    async def test_get_resource_health_filters_by_resource_id(self):
        _FakeAsyncClient.responses["compute.googleapis.com"] = _FakeResponse(
            json_data={
                "items": {
                    "zones/us-central1-a": {
                        "instances": [
                            {"name": "vm-1", "status": "RUNNING", "zone": "z1"},
                            {"name": "vm-2", "status": "STOPPED", "zone": "z1"},
                        ]
                    }
                }
            }
        )
        adapter = GCPAdapter(_credentials())
        result = await adapter.get_resource_health(resource_id="vm-2")
        assert result["success"] is True
        assert [i["name"] for i in result["instances"]] == ["vm-2"]

    @pytest.mark.asyncio
    async def test_list_security_findings_returns_findings(self):
        _FakeAsyncClient.responses["securitycenter.googleapis.com"] = _FakeResponse(
            json_data={"listFindingsResults": [{"finding": {"name": "f1", "severity": "HIGH"}}]}
        )
        adapter = GCPAdapter(_credentials())
        result = await adapter.list_security_findings(severity="HIGH")
        assert result["success"] is True
        assert result["findings"] == [{"name": "f1", "severity": "HIGH"}]
