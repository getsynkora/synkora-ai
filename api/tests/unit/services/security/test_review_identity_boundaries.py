"""HTTP regressions for Okta administration and widget/session origin separation."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

from src.controllers import okta_sso
from src.controllers.console import auth
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.middleware.cors_middleware import DynamicCORSMiddleware
from src.services.auth_service import AuthService
from src.services.security.origins import allowed_dashboard_origin


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "DELETE"])
async def test_okta_member_denied_before_configuration_query(monkeypatch, method):
    app = FastAPI()
    app.include_router(okta_sso.router)
    db = AsyncMock()
    app.dependency_overrides[get_async_db] = lambda: db
    app.dependency_overrides[get_current_account] = lambda: SimpleNamespace(id=uuid4())
    app.dependency_overrides[get_current_tenant_id] = uuid4
    permission = AsyncMock(return_value=False)
    monkeypatch.setattr(AuthService, "check_permission", permission)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://api.example.test") as client:
        response = await client.request(method, "/api/v1/sso/okta/config", json={})
    assert response.status_code == 403
    permission.assert_awaited_once()
    db.execute.assert_not_awaited()
    db.commit.assert_not_awaited()


def configuration():
    return SimpleNamespace(
        domain="org.okta.com",
        issuer_url="https://org.okta.com",
        client_id="old-client",
        client_secret="encrypted-old-secret",
        authorization_server_id=None,
        enabled="true",
    )


@pytest.mark.asyncio
async def test_okta_admin_can_update_without_forwarding_old_secret(monkeypatch):
    app = FastAPI()
    app.include_router(okta_sso.router)
    db, config = AsyncMock(), configuration()
    db.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: config)
    app.dependency_overrides[get_async_db] = lambda: db
    app.dependency_overrides[get_current_account] = lambda: SimpleNamespace(id=uuid4())
    app.dependency_overrides[get_current_tenant_id] = uuid4
    monkeypatch.setattr(AuthService, "check_permission", AsyncMock(return_value=True))
    monkeypatch.setattr(okta_sso, "encrypt_value", lambda s: "encrypted-" + s)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://api.example.test") as client:
        changed = {"domain": "new.okta.com", "issuer_url": "https://new.okta.com"}
        assert (await client.put("/api/v1/sso/okta/config", json=changed)).status_code == 400
        assert config.domain == "org.okta.com"
        db.commit.assert_not_awaited()
        changed["client_secret"] = "replacement"
        assert (await client.put("/api/v1/sso/okta/config", json=changed)).status_code == 200
        assert config.client_secret == "encrypted-replacement"


@pytest.mark.asyncio
async def test_okta_callback_rejects_changed_configuration_before_decryption(monkeypatch):
    config, tenant = configuration(), uuid4()
    state = {
        "tenant_id": str(tenant),
        "redirect_url": "https://app.example.test",
        "config_fingerprint": okta_sso._config_fingerprint(config),
    }
    config.domain = "changed.okta.com"
    monkeypatch.setattr(okta_sso, "_consume_okta_state", AsyncMock(return_value=state))
    decrypt = MagicMock()
    monkeypatch.setattr(okta_sso, "decrypt_value", decrypt)
    db = AsyncMock()
    db.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: config)
    with pytest.raises(Exception) as exc:
        await okta_sso.okta_callback("code", "state", db)
    assert exc.value.status_code == 400
    decrypt.assert_not_called()


@pytest.mark.parametrize(
    "domain", ["org.okta.com@evil.test", "org.okta.com/path", "https://org.okta.com", "org.okta.com:443"]
)
def test_okta_domain_cannot_rewrite_origin(domain):
    with pytest.raises(ValueError):
        okta_sso.OktaTenantUpdate(domain=domain)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "origin", ["https://evil.example.test", "https://app.example.test:8443", "http://app.example.test", "null", ""]
)
async def test_widget_key_cannot_refresh_cookie_session(monkeypatch, origin):
    app = FastAPI()
    app.include_router(auth.router, prefix="/console/api/auth")
    app.dependency_overrides[get_async_db] = lambda: AsyncMock()
    app.add_middleware(DynamicCORSMiddleware, dashboard_origins=["https://app.example.test"])
    widget = AsyncMock(side_effect=lambda key, origin: origin)
    monkeypatch.setattr(DynamicCORSMiddleware, "_validate_widget_origin", widget)
    monkeypatch.setattr(auth, "dashboard_origins", lambda: ["https://app.example.test"])
    refresh = AsyncMock()
    monkeypatch.setattr(auth.SessionService, "refresh_session", refresh)
    headers = {"Origin": origin, "X-Widget-API-Key": "valid-foreign-widget", "Cookie": "refresh_token=victim"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://api.example.test") as client:
        response = await client.post("/console/api/auth/refresh", headers=headers, json={})
    assert response.status_code == 403
    assert "access-control-allow-origin" not in response.headers
    refresh.assert_not_awaited()
    widget.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("cookie", [True, False])
async def test_dashboard_cookie_and_mobile_body_refresh_still_work(monkeypatch, cookie):
    app = FastAPI()
    app.include_router(auth.router)
    app.dependency_overrides[get_async_db] = lambda: AsyncMock()
    monkeypatch.setattr(auth, "dashboard_origins", lambda: ["https://app.example.test"])
    refresh = AsyncMock(return_value={"access_token": "access", "refresh_token": "rotated"})
    monkeypatch.setattr(auth.SessionService, "refresh_session", refresh)
    headers = {"Origin": "https://app.example.test:443", "Cookie": "refresh_token=browser"} if cookie else {}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://api.example.test") as client:
        response = await client.post("/refresh", headers=headers, json={} if cookie else {"refresh_token": "mobile"})
    assert response.status_code == 200
    assert response.json()["data"]["access_token"] == "access"
    assert refresh.call_args.args[1] == ("browser" if cookie else "mobile")


@pytest.mark.asyncio
async def test_widget_cors_is_route_limited_and_does_not_allow_cookies(monkeypatch):
    app = FastAPI()

    @app.get("/api/v1/widgets/config")
    async def config():
        return {"ok": True}

    app.add_middleware(DynamicCORSMiddleware, dashboard_origins=["https://app.example.test"])
    monkeypatch.setattr(
        DynamicCORSMiddleware, "_validate_widget_origin", AsyncMock(return_value="https://embed.example.org")
    )
    headers = {"Origin": "https://embed.example.org", "X-Widget-API-Key": "valid-widget"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://api.example.test") as client:
        response = await client.get("/api/v1/widgets/config", headers=headers)
        assert response.headers["access-control-allow-origin"] == headers["Origin"]
        assert "access-control-allow-credentials" not in response.headers
        preflight = {
            "Origin": headers["Origin"],
            "Access-Control-Request-Headers": "content-type, x-widget-api-key",
            "Access-Control-Request-Method": "POST",
        }
        for path in ("/console/api/auth/refresh", "/api/v1/widgets/123", "/api/v1/widgets"):
            assert (await client.options(path, headers=preflight)).status_code == 403
        response = await client.options("/api/v1/widgets/chat", headers=preflight)
        assert response.status_code == 200
        assert "access-control-allow-credentials" not in response.headers


@pytest.mark.parametrize(
    "origin",
    [
        "https://app.example.test:0",
        "https://@app.example.test",
        "https://app.example.test/path",
        "https://app.example.test\\evil",
    ],
)
def test_dashboard_origin_rejects_ambiguous_authorities(origin):
    assert not allowed_dashboard_origin(origin, ["https://app.example.test"])


def test_no_configured_dashboard_origins_does_not_enable_wildcard():
    middleware = DynamicCORSMiddleware(None, dashboard_origins=[])
    assert middleware._validate_dashboard_origin("https://untrusted.example") is None
