"""Handoff permissions and SQL scope must preserve the API key's authority."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from src.controllers.agents import handoff
from src.core.database import get_async_db
from src.middleware.agent_api_auth import AgentApiAuthMiddleware, HandoffAccess
from src.models.conversation import Conversation

ROUTES = [
    ("GET", "/conversations/handoffs", None),
    ("GET", "/conversations/{id}/handoff", None),
    ("GET", "/conversations/{id}/messages", None),
    ("POST", "/conversations/{id}/handoff/reply", {"message": "hello"}),
    ("POST", "/conversations/{id}/handoff/assign", {"operator_id": "operator"}),
    ("POST", "/conversations/{id}/handoff/resolve", None),
    ("POST", "/conversations/{id}/handoff/reopen", None),
]


@pytest.fixture(autouse=True)
def request_controls_tested_separately(monkeypatch):
    # This suite isolates permission/SQL scope; real controls run in test_remaining_auth_controls.
    monkeypatch.setattr(AgentApiAuthMiddleware, "enforce_request_controls", AsyncMock())


@pytest.mark.parametrize("method,path,body", ROUTES)
@pytest.mark.parametrize("permissions", [["chat"], ["history"], ["conversations"]])
def test_unprivileged_keys_cannot_read_or_modify_handoffs(monkeypatch, method, path, body, permissions):
    key = SimpleNamespace(tenant_id=uuid4(), agent_id=uuid4(), permissions=permissions)
    monkeypatch.setattr(AgentApiAuthMiddleware, "validate_api_key", AsyncMock(return_value=key))
    app = FastAPI()
    app.include_router(handoff.router)
    db = AsyncMock()
    app.dependency_overrides[get_async_db] = lambda: db
    with TestClient(app) as client:
        response = client.request(
            method, path.format(id=uuid4()), json=body, headers={"Authorization": "Bearer sk_synthetic"}
        )
    assert response.status_code == 403
    db.execute.assert_not_awaited()
    db.commit.assert_not_awaited()


def test_read_permission_does_not_grant_write():
    access = HandoffAccess(uuid4(), uuid4(), frozenset({"handoff:read"}))
    access.require("handoff:read")
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        access.require("handoff:write")


def test_real_sql_scopes_to_key_agent_and_tenant():
    tenant, foreign_tenant, agent_a, agent_b, foreign_agent = [uuid4() for _ in range(5)]
    conv_a, conv_b, conv_foreign = [uuid4() for _ in range(3)]
    engine = create_engine("sqlite://")
    with engine.begin() as db:
        db.execute(text("CREATE TABLE agents(id CHAR(32), tenant_id CHAR(32))"))
        db.execute(text("CREATE TABLE conversations(id CHAR(32), agent_id CHAR(32))"))
        for agent, owner in [(agent_a, tenant), (agent_b, tenant), (foreign_agent, foreign_tenant)]:
            db.execute(text("INSERT INTO agents VALUES (:id,:tenant)"), {"id": agent.hex, "tenant": owner.hex})
        for conv, agent in [(conv_a, agent_a), (conv_b, agent_b), (conv_foreign, foreign_agent)]:
            db.execute(text("INSERT INTO conversations VALUES (:id,:agent)"), {"id": conv.hex, "agent": agent.hex})
        for permission in ["handoff:read", "handoff:write", "*"]:
            access = HandoffAccess(tenant, agent_a, frozenset({permission}))
            query = handoff._scoped_conversations(access).with_only_columns(Conversation.id)
            assert db.execute(query).scalars().all() == [conv_a]
            assert db.execute(query.where(Conversation.id == conv_b)).scalars().all() == []
            assert db.execute(query.where(Conversation.id == conv_foreign)).scalars().all() == []
        account_query = handoff._scoped_conversations(HandoffAccess(tenant)).with_only_columns(Conversation.id)
        assert set(db.execute(account_query).scalars()) == {conv_a, conv_b}


@pytest.mark.parametrize("method,path,body", ROUTES[1:])
def test_authorized_key_gets_404_for_out_of_scope_conversation(monkeypatch, method, path, body):
    key = SimpleNamespace(tenant_id=uuid4(), agent_id=uuid4(), permissions=["handoff:read", "handoff:write"])
    monkeypatch.setattr(AgentApiAuthMiddleware, "validate_api_key", AsyncMock(return_value=key))
    app = FastAPI()
    app.include_router(handoff.router)
    db = AsyncMock()
    db.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: None)
    app.dependency_overrides[get_async_db] = lambda: db
    with TestClient(app) as client:
        response = client.request(
            method, path.format(id=uuid4()), json=body, headers={"Authorization": "Bearer sk_synthetic"}
        )
    assert response.status_code == 404
    # The denied lookup is scoped before any messages are loaded or writes run.
    compiled = db.execute.call_args.args[0].compile()
    assert key.tenant_id in compiled.params.values() and key.agent_id in compiled.params.values()
    db.commit.assert_not_awaited()


@pytest.mark.parametrize("method,path,body", ROUTES)
def test_scoped_key_can_perform_explicitly_allowed_operation(monkeypatch, method, path, body):
    from unittest.mock import MagicMock

    permission = "handoff:read" if method == "GET" else "handoff:write"
    key = SimpleNamespace(tenant_id=uuid4(), agent_id=uuid4(), permissions=[permission])
    monkeypatch.setattr(AgentApiAuthMiddleware, "validate_api_key", AsyncMock(return_value=key))
    monkeypatch.setattr(handoff, "_broadcast", AsyncMock())
    conv = Conversation(
        id=uuid4(),
        agent_id=key.agent_id,
        handoff_status="resolved" if path.endswith("/reopen") else "active",
        message_count=0,
    )
    conv.messages = []
    db = AsyncMock()
    db.add = MagicMock()

    async def execute(stmt):
        entity = stmt.column_descriptions[0].get("entity")
        rows = [] if entity is handoff.Message else [conv]
        return SimpleNamespace(
            scalar_one_or_none=lambda: conv, scalar_one=lambda: 1, scalars=lambda: SimpleNamespace(all=lambda: rows)
        )

    db.execute.side_effect = execute
    app = FastAPI()
    app.include_router(handoff.router)
    app.dependency_overrides[get_async_db] = lambda: db
    with TestClient(app) as client:
        response = client.request(
            method, path.format(id=conv.id), json=body, headers={"Authorization": "Bearer sk_synthetic"}
        )
    assert response.status_code == 200, response.text
    if method == "POST":
        db.commit.assert_awaited_once()
    else:
        db.commit.assert_not_awaited()
