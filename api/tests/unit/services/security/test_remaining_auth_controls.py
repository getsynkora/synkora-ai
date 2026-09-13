"""Regression coverage for credential isolation and handoff request restrictions."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

from src.controllers.agents import handoff
from src.core.database import get_async_db
from src.middleware.agent_api_auth import AgentApiAuthMiddleware
from src.models.agent_tool import AgentTool
from src.models.oauth_app import OAuthApp
from src.models.user_oauth_token import UserOAuthToken
from src.services.agent_api.api_key_service import AgentApiKeyService
from src.services.agents.credential_resolver import CredentialResolver
from src.services.agents.security import encrypt_value


@pytest.mark.parametrize(
    "pattern,origin,expected",
    [
        ("*.example.com", "https://sub.example.com", True),
        ("*.example.com", "https://a.b.example.com", True),
        ("*.example.com", "https://notexample.com", False),
        ("*.example.com", "https://example.com", False),
        ("*.example.com", "https://sub.example.com.evil.test", False),
        ("example.com", "https://EXAMPLE.COM", True),
        ("https://example.com", "https://example.com:443", True),
        ("https://example.com", "http://example.com", False),
        ("https://example.com", "https://example.com:444", False),
        ("https://example.com:444", "https://example.com:444", True),
        ("[::1]", "https://[::1]", True),
        ("*", "https://example.com", True),
        ("*", "null", False),
        ("*", "https://user:pass@example.com", False),
        ("*", "https://example.com/path", False),
        ("*", "https://example.com?query", False),
        ("*", "https://example.com#fragment", False),
        ("*", "https://example.com:99999", False),
        ("*", "https://example.com\\evil", False),
        ("*", "https://example.com\n", False),
        ("example.com", None, False),
    ],
)
def test_origin_boundaries(pattern, origin, expected):
    assert AgentApiKeyService.validate_origin(SimpleNamespace(allowed_origins=[pattern]), origin) is expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case,status",
    [("valid", 200), ("ip", 403), ("origin", 403), ("missing_origin", 403), ("quota", 429), ("outage", 503)],
)
async def test_handoff_enforces_request_controls(monkeypatch, case, status):
    key = SimpleNamespace(
        id=uuid4(),
        tenant_id=uuid4(),
        agent_id=uuid4(),
        permissions=["handoff:read"],
        allowed_ips=["198.51.100.20"],
        allowed_origins=["https://allowed.example.com"],
    )
    monkeypatch.setattr(AgentApiAuthMiddleware, "validate_api_key", AsyncMock(return_value=key))
    rate = MagicMock(return_value=(case != "quota", "Quota exhausted"))
    if case == "outage":
        rate.side_effect = RuntimeError("Synthetic Redis outage")
    monkeypatch.setattr(AgentApiKeyService, "check_rate_limit", rate)
    db = AsyncMock()
    db.execute.return_value = SimpleNamespace(scalar_one=lambda: 0, scalars=lambda: SimpleNamespace(all=lambda: []))
    app = FastAPI()
    app.include_router(handoff.router)
    app.dependency_overrides[get_async_db] = lambda: db
    headers = {"Authorization": "Bearer sk_synthetic", "Origin": "https://allowed.example.com"}
    if case == "origin":
        headers["Origin"] = "https://evil.example.net"
    if case == "missing_origin":
        headers.pop("Origin")
    ip = "203.0.113.10" if case == "ip" else "198.51.100.20"
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, client=(ip, 4321)), base_url="http://test"
    ) as client:
        response = await client.get("/conversations/handoffs", headers=headers)
    assert response.status_code == status
    if status != 200:
        db.execute.assert_not_awaited()
    if case in ("ip", "origin", "missing_origin"):
        rate.assert_not_called()
    else:
        rate.assert_called_once_with(key)


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("identity", ["member", "no_user", "no_tenant", "nonmember"])
async def test_micromobility_personal_token_boundary(monkeypatch, legacy, identity):
    tenant, user = uuid4(), uuid4()
    record = UserOAuthToken(account_id=user, oauth_app_id=12)
    record.access_token = encrypt_value("synthetic-token") if legacy else "synthetic-token"
    app = SimpleNamespace(
        id=12,
        app_name="Provider",
        auth_method="oauth",
        is_platform_app=True,
        config={"base_url": "https://example.invalid"},
        api_token=None,
        access_token=encrypt_value("platform-secret"),
    )
    db = AsyncMock()
    statements = []

    async def execute(stmt):
        statements.append(stmt)
        entity = stmt.column_descriptions[0]["entity"]
        if entity is UserOAuthToken:
            params = stmt.compile().params.values()
            assert tenant in params and user in params and 12 in params
            assert "JOIN tenant_account_joins" in str(stmt)
        value = {
            AgentTool: SimpleNamespace(oauth_app_id=12),
            OAuthApp: app,
            UserOAuthToken: record if identity == "member" else None,
        }[entity]
        if entity is OAuthApp:
            assert tenant in stmt.compile().params.values()
        return SimpleNamespace(scalar_one_or_none=lambda: value)

    db.execute.side_effect = execute

    @asynccontextmanager
    async def session():
        yield db

    monkeypatch.setattr("src.core.database.get_async_session_factory", lambda: session)
    outer_db = AsyncMock()
    context = SimpleNamespace(
        tenant_id=None if identity == "no_tenant" else tenant,
        user_id=None if identity == "no_user" else user,
        agent_id=uuid4(),
        db_session=outer_db,
    )
    result = await CredentialResolver(context).get_micromobility_credentials("tool")
    if identity == "member":
        assert result["access_token"] == "synthetic-token"
    else:
        assert result is None
    if identity in ("no_user", "no_tenant"):
        assert all(stmt.column_descriptions[0]["entity"] is not UserOAuthToken for stmt in statements)
    outer_db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_personal_lookup_executes_tenant_and_account_scope():
    from sqlalchemy import create_engine, text

    tenant, foreign_tenant, user, foreign_user = [uuid4() for _ in range(4)]
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE user_oauth_tokens(account_id CHAR(32), oauth_app_id INTEGER)"))
        connection.execute(text("CREATE TABLE tenant_account_joins(account_id CHAR(32), tenant_id CHAR(32))"))
        for account, owner in [(user, tenant), (foreign_user, foreign_tenant)]:
            connection.execute(text("INSERT INTO user_oauth_tokens VALUES (:account,12)"), {"account": account.hex})
            connection.execute(
                text("INSERT INTO tenant_account_joins VALUES (:account,:tenant)"),
                {"account": account.hex, "tenant": owner.hex},
            )

        async def execute(stmt):
            return connection.execute(stmt.with_only_columns(UserOAuthToken.account_id))

        db = SimpleNamespace(execute=execute)
        context = SimpleNamespace(user_id=user, tenant_id=tenant, db_session=db)
        resolver = CredentialResolver(context)
        assert await resolver._get_personal_provider_token_record(12) == user
        context.user_id = foreign_user
        assert await resolver._get_personal_provider_token_record(12) is None
        context.user_id = user
        assert await resolver._get_personal_provider_token_record(13) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("platform", [False, True])
async def test_background_micromobility_only_uses_tenant_app_token(monkeypatch, platform):
    app = SimpleNamespace(
        id=12,
        app_name="Provider",
        auth_method="oauth",
        is_platform_app=platform,
        config={"base_url": "https://example.invalid"},
        api_token=None,
        access_token=encrypt_value("tenant-app-token"),
    )
    db = AsyncMock()
    db.execute.side_effect = [
        SimpleNamespace(scalar_one_or_none=lambda: SimpleNamespace(oauth_app_id=12)),
        SimpleNamespace(scalar_one_or_none=lambda: app),
    ]

    @asynccontextmanager
    async def session():
        yield db

    monkeypatch.setattr("src.core.database.get_async_session_factory", lambda: session)
    context = SimpleNamespace(tenant_id=uuid4(), user_id=None, agent_id=uuid4(), db_session=AsyncMock())
    result = await CredentialResolver(context).get_micromobility_credentials("tool")
    if platform:
        assert result is None
    else:
        assert result["access_token"] == "tenant-app-token"
    assert db.execute.await_count == 2
