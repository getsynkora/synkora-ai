"""Real export/download round trips and tenant/file capability regressions."""

import base64
import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

from src.controllers import data_analysis
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.services.report_export_service import ReportExportService


@pytest.fixture
def report_app(monkeypatch, tmp_path):
    tenant = uuid4()
    monkeypatch.setattr(data_analysis.storage_config, "STORAGE_TYPE", "local")
    monkeypatch.setattr(data_analysis.storage_config, "STORAGE_LOCAL_PATH", str(tmp_path))
    app = FastAPI()
    app.include_router(data_analysis.router)
    app.dependency_overrides[get_current_tenant_id] = lambda: tenant
    app.dependency_overrides[get_current_account] = lambda: MagicMock()
    app.dependency_overrides[get_async_db] = lambda: AsyncMock()
    return app, tenant, tmp_path


@pytest.mark.asyncio
@pytest.mark.parametrize("format", ["csv", "json", "excel", "html"])
async def test_actual_export_download_roundtrip_and_foreign_tenant_denial(report_app, format):
    app, tenant, root = report_app
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://api.example.test") as client:
        response = await client.post(
            "/api/v1/data-analysis/export-report", json={"format": format, "data": [{"value": "hello"}]}
        )
        assert response.status_code == 200
        result = response.json()
        assert result["success"], result
        assert result["download_url"].startswith("/api/v1/data-analysis/download?")
        assert result["file_path"].startswith(f"reports/{tenant}/")
        download = await client.get(result["download_url"])
        assert download.status_code == 200
        assert download.content == (root / result["file_path"]).read_bytes()
        assert download.headers["cache-control"] == "no-store"
        assert "attachment" in download.headers["content-disposition"]
        app.dependency_overrides[get_current_tenant_id] = uuid4
        assert (await client.get(result["download_url"])).status_code == 400


def signed(payload, key):
    body = json.dumps(payload).encode()
    return base64.urlsafe_b64encode(body).decode() + "." + hmac.new(key, body, hashlib.sha256).hexdigest()


def test_dotenv_settings_used_when_process_env_missing(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setattr(data_analysis.settings, "secret_key", "dotenv-only-synthetic-secret-0123456789")
    tenant = uuid4()
    key = f"reports/{tenant}/report.csv"
    token = data_analysis._make_download_token(key, tenant)
    assert data_analysis._verify_download_token(token, tenant) == key
    forged = signed({"key": key, "tenant": str(tenant), "ts": int(time.time()), "purpose": "report-download-v1"}, b"")
    assert data_analysis._verify_download_token(forged, tenant) is None
    monkeypatch.setattr(data_analysis.settings, "secret_key", "")
    with pytest.raises(ValueError):
        data_analysis._make_download_token(key, tenant)
    assert data_analysis._verify_download_token(token, tenant) is None


@pytest.mark.parametrize(
    "change", ["future", "expired", "wrong_purpose", "foreign_key", "traversal", "absolute", "encoded", "wrong_type"]
)
def test_signed_token_still_requires_valid_scope_time_and_path(change):
    tenant = uuid4()
    payload = {
        "key": f"reports/{tenant}/report.csv",
        "tenant": str(tenant),
        "ts": int(time.time()),
        "purpose": "report-download-v1",
    }
    if change == "future":
        payload["ts"] += 60
    if change == "expired":
        payload["ts"] -= 3601
    if change == "wrong_type":
        payload["ts"] = "0"
    if change == "wrong_purpose":
        payload["purpose"] = "login"
    if change == "foreign_key":
        payload["key"] = f"reports/{uuid4()}/report.csv"
    if change == "traversal":
        payload["key"] = f"reports/{tenant}/../other/report.csv"
    if change == "absolute":
        payload["key"] = "/tmp/report.csv"
    if change == "encoded":
        payload["key"] = f"reports/{tenant}/%2e%2e/report.csv"
    assert (
        data_analysis._verify_download_token(signed(payload, data_analysis.settings.secret_key.encode()), tenant)
        is None
    )


@pytest.mark.asyncio
async def test_symlinks_and_legacy_tokens_cannot_download_files(report_app):
    app, tenant, root = report_app
    foreign = root / "foreign.txt"
    foreign.write_text("other tenant content")
    key = f"reports/{tenant}/report.csv"
    path = root / key
    path.parent.mkdir(parents=True)
    path.symlink_to(foreign)
    token = data_analysis._make_download_token(key, tenant)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://api.example.test") as client:
        assert (await client.get("/api/v1/data-analysis/download", params={"token": token})).status_code == 400
        legacy = base64.urlsafe_b64encode(
            json.dumps({"path": str(foreign), "ts": "0", "sig": "legacy"}).encode()
        ).decode()
        assert (await client.get("/api/v1/data-analysis/download", params={"token": legacy})).status_code == 400


@pytest.mark.asyncio
async def test_s3_signing_requires_current_tenant_before_storage_access(report_app, monkeypatch):
    app, tenant, _ = report_app
    monkeypatch.setattr(data_analysis.storage_config, "STORAGE_TYPE", "s3")
    storage = MagicMock()
    storage.get_presigned_url.return_value = "https://storage.example/report?synthetic-signature"
    monkeypatch.setattr(data_analysis, "get_storage_service", lambda: storage)
    key = f"reports/{tenant}/report.csv"
    token = data_analysis._make_download_token(key, tenant)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://api.example.test") as client:
        response = await client.get("/api/v1/data-analysis/download", params={"token": token})
        assert response.status_code == 303
        storage.get_presigned_url.assert_called_once_with(key, expiration=60)
        app.dependency_overrides[get_current_tenant_id] = uuid4
        assert (await client.get("/api/v1/data-analysis/download", params={"token": token})).status_code == 400
        assert storage.get_presigned_url.call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("filename", ["../foreign/report.csv", "/tmp/report.csv", "..\\report.csv", "x\n.csv"])
async def test_export_rejects_path_in_filename_before_write(report_app, filename):
    _, tenant, root = report_app
    service = ReportExportService(AsyncMock(), tenant)
    result = await service.export_to_csv([{"value": "hello"}], filename)
    assert not result["success"]
    assert list(root.rglob("*")) == []
