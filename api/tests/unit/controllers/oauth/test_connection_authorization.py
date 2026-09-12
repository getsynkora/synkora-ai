"""Integration authorization must precede provider exchange and credential writes."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.controllers import oauth
from src.controllers.oauth import base, github
from src.core.database import get_async_db
from src.models import Account, AccountStatus, Tenant, TenantAccountJoin
from src.models.oauth_app import OAuthApp
from src.services.permissions.permission_service import PermissionService

AUTHORIZE_PATHS = [r.path for r in oauth.router.routes if r.path.endswith("/authorize")]
CALLBACK_PATHS = [r.path for r in oauth.router.routes if r.path.endswith("/callback")]


@pytest.mark.parametrize("path", AUTHORIZE_PATHS)
def test_all_provider_authorize_routes_require_login(path):
    app = FastAPI()
    app.include_router(oauth.router)
    db = AsyncMock()
    app.dependency_overrides[get_async_db] = lambda: db
    with TestClient(app) as client:
        response = client.get(path, params={"oauth_app_id": 12}, follow_redirects=False)
    assert response.status_code == 401
    db.execute.assert_not_awaited()


@pytest.mark.parametrize("path", CALLBACK_PATHS)
def test_all_callbacks_reject_unbound_legacy_state(path, monkeypatch):
    import importlib

    route = next(r for r in oauth.router.routes if r.path == path)
    module = importlib.import_module(route.endpoint.__module__)
    monkeypatch.setattr(
        module,
        "get_oauth_state",
        lambda *a, **k: {
            "oauth_app_id": 12,
            "redirect_url": "https://example.invalid",
            "user_level": False,
            "code_verifier": "test",
        },
    )
    app = FastAPI()
    app.include_router(oauth.router)
    db = AsyncMock()
    app.dependency_overrides[get_async_db] = lambda: db
    with TestClient(app) as client:
        response = client.get(path, params={"code": "synthetic", "state": "synthetic"}, follow_redirects=False)
    assert response.status_code == 401, response.text
    db.execute.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.fixture
def connection(monkeypatch):
    tenant = uuid4()
    account = SimpleNamespace(id=uuid4(), status=AccountStatus.ACTIVE, auth_version=0)
    app = SimpleNamespace(
        id=12,
        tenant_id=tenant,
        is_platform_app=False,
        provider="github",
        auth_method="oauth",
        client_id="test",
        client_secret="test",
        redirect_uri="https://example.invalid/callback",
        scopes=["repo"],
        access_token="original",
    )
    state = {
        "oauth_app_id": 12,
        "tenant_id": str(tenant),
        "account_id": str(account.id),
        "user_level": False,
        "auth_version": 0,
        "redirect_url": "https://example.invalid",
    }
    flags = SimpleNamespace(member=True)
    db = AsyncMock()

    async def execute(stmt):
        entity = stmt.column_descriptions[0]["entity"]
        value = {
            Account: account,
            TenantAccountJoin: object() if flags.member else None,
            OAuthApp: app,
            Tenant: SimpleNamespace(disabled_platform_oauth_providers=[]),
        }[entity]
        return SimpleNamespace(scalar_one_or_none=lambda: value)

    db.execute.side_effect = execute
    permission = AsyncMock(return_value=True)
    monkeypatch.setattr(PermissionService, "check_permission", permission)
    return account, tenant, app, state, flags, db, permission


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["removed", "inactive", "reset", "permission", "foreign_app", "missing_account"])
async def test_callback_rechecks_account_membership_permission_and_ownership(connection, failure):
    account, _, app, state, flags, db, permission = connection
    if failure == "removed":
        flags.member = False
    if failure == "inactive":
        account.status = "DISABLED"
    if failure == "reset":
        account.auth_version = 1
    if failure == "permission":
        permission.return_value = False
    if failure == "foreign_app":
        app.tenant_id = uuid4()
    if failure == "missing_account":
        state.pop("account_id")
    with pytest.raises(HTTPException):
        await base._get_callback_oauth_app(db, state)
    assert app.access_token == "original"
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_personal_connection_needs_membership_but_not_shared_write_permission(connection):
    _, _, app, state, _, db, permission = connection
    state["user_level"] = True
    permission.return_value = False
    assert await base._get_callback_oauth_app(db, state) is app
    permission.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("platform", [False, True])
async def test_authorized_github_roundtrip_binds_identity_and_updates_token(connection, monkeypatch, platform):
    account, tenant, app, state, _, db, _ = connection
    clone = SimpleNamespace(tenant_id=tenant, access_token="original")
    app.is_platform_app = platform
    clone_app = AsyncMock(return_value=clone)
    monkeypatch.setattr(github, "_get_or_create_tenant_clone", clone_app)
    provider = MagicMock()
    provider.get_authorization_url.return_value = "https://example.invalid/authorize"
    provider.get_access_token = AsyncMock(return_value="new-token")
    provider.get_user_info = AsyncMock(return_value={"id": 1, "login": "owner"})
    captured = {}

    def save(data):
        captured.update(data)
        return "state"

    monkeypatch.setattr(github, "create_oauth_state", save)
    monkeypatch.setattr(github, "get_oauth_state", lambda *a, **k: captured)
    monkeypatch.setattr(github, "GitHubOAuth", lambda **k: provider)
    monkeypatch.setattr(github, "decrypt_value", lambda x: x)
    monkeypatch.setattr(github, "encrypt_value", lambda x: "encrypted:" + x)
    monkeypatch.setattr(github, "get_app_base_url", AsyncMock(return_value="https://example.invalid"))
    response = await github.github_authorize(12, None, False, account, tenant, db)
    assert response.status_code == 307
    assert captured["account_id"] == str(account.id) and captured["tenant_id"] == str(tenant)
    assert captured["auth_version"] == 0
    await github.github_callback("code", "state", db)
    if platform:
        clone_app.assert_awaited_once_with(db, app, tenant)
        assert clone.access_token == "encrypted:new-token"
        assert app.access_token == "original"
    else:
        assert app.access_token == "encrypted:new-token"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider,class_name",
    [
        ("github", "GitHubOAuth"),
        ("hubspot", "HubSpotOAuth"),
        ("salesforce", "SalesforceOAuth"),
        ("intercom", "IntercomOAuth"),
        ("micromobility", "MicromobilityOAuth"),
    ],
)
async def test_dashboard_initiation_binds_shared_connection_identity(connection, monkeypatch, provider, class_name):
    import importlib

    account, tenant, app, _, _, db, _ = connection
    app.provider = provider
    app.config = {
        "oauth_authorize_url": "https://example.invalid/authorize",
        "oauth_token_url": "https://example.invalid/token",
    }
    module = base if provider == "github" else importlib.import_module("src.controllers.oauth." + provider)
    provider_client = MagicMock()
    provider_client.get_authorization_url.return_value = "https://example.invalid/authorize"
    monkeypatch.setattr(module, class_name, lambda **kwargs: provider_client)
    monkeypatch.setattr(module, "get_app_base_url", AsyncMock(return_value="https://example.invalid"))
    monkeypatch.setattr(module, "decrypt_value", lambda x: x)
    captured = {}

    def save(data):
        captured.update(data)
        return "synthetic-state"

    monkeypatch.setattr(module, "create_oauth_state", save)
    result = await base.initiate_oauth(
        base.InitiateOAuthRequest(oauth_app_id=12, redirect_url="https://example.invalid", user_level=False),
        account,
        tenant,
        db,
    )
    assert result["auth_url"] == "https://example.invalid/authorize"
    assert captured["account_id"] == str(account.id)
    assert captured["tenant_id"] == str(tenant)
    assert captured["auth_version"] == 0
    db.commit.assert_not_awaited()


def test_dashboard_initiation_requires_authentication():
    app = FastAPI()
    app.include_router(oauth.router)
    db = AsyncMock()
    app.dependency_overrides[get_async_db] = lambda: db
    with TestClient(app) as client:
        response = client.post("/api/v1/oauth/initiate", json={"oauth_app_id": 12, "user_level": False})
    assert response.status_code == 401
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_salesforce_shared_connection_writes_tenant_clone(connection, monkeypatch):
    from src.controllers.oauth import salesforce

    _, tenant, app, state, _, db, _ = connection
    app.is_platform_app = True
    app.provider = "salesforce"
    app.config = {}
    clone = SimpleNamespace(tenant_id=tenant, config={}, access_token=None)
    create_clone = AsyncMock(return_value=clone)
    provider = MagicMock()
    provider.get_access_token = AsyncMock(
        return_value={"access_token": "new-token", "instance_url": "https://instance.example.invalid"}
    )
    provider.get_user_info = AsyncMock(return_value={"email": "owner@example.invalid", "id": "owner", "name": "Owner"})
    monkeypatch.setattr(salesforce, "get_oauth_state", lambda *a, **k: state)
    monkeypatch.setattr(salesforce, "SalesforceOAuth", lambda **k: provider)
    monkeypatch.setattr(salesforce, "decrypt_value", lambda x: x)
    monkeypatch.setattr(salesforce, "encrypt_value", lambda x: "encrypted:" + x)
    monkeypatch.setattr(salesforce, "get_app_base_url", AsyncMock(return_value="https://example.invalid"))
    monkeypatch.setattr(salesforce, "_get_or_create_tenant_clone", create_clone)
    await salesforce.salesforce_callback("code", "state", db)
    create_clone.assert_awaited_once_with(db, app, tenant)
    assert clone.access_token == "encrypted:new-token"
    assert clone.config["instance_url"] == "https://instance.example.invalid"
    assert app.access_token == "original" and app.config == {}
    db.commit.assert_awaited_once()
