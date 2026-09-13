"""Regression tests for alternate entry points using real token validation."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from src.controllers import portal
from src.controllers.agents import chat
from src.middleware import auth_middleware as auth
from src.middleware.agent_api_auth import get_handoff_access
from src.models import Account, AccountStatus, TenantAccountJoin
from src.services.auth_service import AuthService


@pytest.fixture
def identity(monkeypatch):
    account = SimpleNamespace(id=uuid4(), status=AccountStatus.ACTIVE, auth_version=0)
    tenant_id = uuid4()
    state = SimpleNamespace(account=account, member=True, revoked=False)
    db = AsyncMock()

    async def execute(stmt):
        entity = stmt.column_descriptions[0]["entity"]
        value = account if entity is Account else (object() if state.member else None)
        assert entity in (Account, TenantAccountJoin)
        return SimpleNamespace(scalar_one_or_none=lambda: value)

    db.execute.side_effect = execute
    pipe = MagicMock()
    pipe.execute = AsyncMock(side_effect=lambda: [state.revoked, b"0"])
    redis = MagicMock()
    redis.pipeline.return_value = pipe
    monkeypatch.setattr(auth, "get_redis_async", lambda: redis)
    token = AuthService.generate_access_token(account.id, tenant_id)
    return state, tenant_id, token, db


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["revoked", "removed", "inactive", "old_version", "refresh"])
async def test_handoff_rejects_invalid_identity(identity, failure):
    state, tenant, token, db = identity
    if failure == "revoked":
        state.revoked = True
    if failure == "removed":
        state.member = False
    if failure == "inactive":
        state.account.status = "DISABLED"
    if failure == "old_version":
        state.account.auth_version = 1
    if failure == "refresh":
        token = AuthService.generate_refresh_token(state.account.id)
    with pytest.raises(HTTPException) as exc:
        await get_handoff_access(Request({"type": "http", "headers": []}), "Bearer " + token, db)
    assert exc.value.status_code in (401, 403)


@pytest.mark.asyncio
async def test_handoff_allows_current_member(identity):
    _, tenant, token, db = identity
    assert (
        await get_handoff_access(Request({"type": "http", "headers": []}), "Bearer " + token, db)
    ).tenant_id == tenant
    assert db.execute.await_count == 2


@pytest.mark.asyncio
async def test_portal_only_recognizes_current_members(identity):
    state, tenant, token, db = identity
    request = Request({"type": "http", "headers": [(b"authorization", ("Bearer " + token).encode())]})
    assert await portal._is_portal_member(request, tenant, db)
    assert not await portal._is_portal_member(request, uuid4(), db)
    state.member = False
    assert not await portal._is_portal_member(request, tenant, db)
    state.member = True
    state.revoked = True
    assert not await portal._is_portal_member(request, tenant, db)
    assert not await portal._is_portal_member(Request({"type": "http", "headers": []}), tenant, db)


@pytest.mark.asyncio
async def test_websocket_rejects_stale_database_version(identity, monkeypatch):
    state, _, token, db = identity
    state.account.auth_version = 1

    @asynccontextmanager
    async def session():
        yield db

    monkeypatch.setattr(chat, "get_async_session_factory", lambda: session)
    ws = AsyncMock()
    ws.receive_json.return_value = {"type": "auth", "token": token}
    await chat.chat_websocket(ws)
    ws.close.assert_awaited_once_with(code=1008)
    assert not any(c.args[0]["type"] == "auth_ok" for c in ws.send_json.await_args_list)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["removed", "revoked", "inactive", "old_version", "expired"])
async def test_websocket_rechecks_before_later_chat(identity, monkeypatch, failure):
    state, _, token, db = identity

    @asynccontextmanager
    async def session():
        yield db

    monkeypatch.setattr(chat, "get_async_session_factory", lambda: session)
    dispatched = []

    async def pipeline(**kwargs):
        dispatched.append(kwargs)
        yield '{"type":"done"}'

    monkeypatch.setattr(chat, "_ws_chat_pipeline", pipeline)
    count = 0

    async def receive():
        nonlocal count
        count += 1
        if count == 1:
            return {"type": "auth", "token": token}
        if count == 3:
            if failure == "expired":
                future = datetime.now(UTC) + timedelta(days=36500)
                monkeypatch.setattr(jwt.api_jwt, "datetime", SimpleNamespace(now=lambda **kwargs: future))
            if failure == "removed":
                state.member = False
            if failure == "revoked":
                state.revoked = True
            if failure == "inactive":
                state.account.status = "DISABLED"
            if failure == "old_version":
                state.account.auth_version = 1
        assert count <= 3
        return {"type": "chat", "agent_slug": "example", "message": "hello"}

    ws = AsyncMock()
    ws.receive_json.side_effect = receive
    await chat.chat_websocket(ws)
    assert len(dispatched) == 1
    ws.close.assert_awaited_once_with(code=1008)
