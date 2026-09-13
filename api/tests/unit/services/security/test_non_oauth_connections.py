"""Real SQL ownership checks for assignment and previously saved connections."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text

from src.controllers.agents.tools import SaveAgentToolRequest, _authorize_tool_connections, save_agent_tool
from src.models import AgentTool, CustomTool
from src.models.slack_bot import SlackBot
from src.services.agents.adk_tools import ADKToolRegistry
from src.services.agents.credential_resolver import CredentialResolver
from src.services.agents.security import encrypt_value

SCHEMA = {
    "openapi": "3.0.0",
    "info": {"title": "Synthetic", "version": "1"},
    "paths": {"/records": {"get": {"operationId": "read", "responses": {"200": {"description": "ok"}}}}},
}


@pytest.mark.asyncio
@pytest.mark.parametrize("foreign", [False, True])
async def test_assignment_and_runtime_execute_ownership_sql(foreign):
    tenant, other, agent, bot_id, custom_id = [uuid4() for _ in range(5)]
    owner = other if foreign else tenant
    custom = SimpleNamespace(
        id=custom_id,
        tenant_id=owner,
        name="Synthetic",
        openapi_schema=SCHEMA,
        server_url="https://example.invalid",
        auth_type="bearer",
        auth_config={"token": encrypt_value("synthetic")},
    )
    bot = SimpleNamespace(id=bot_id, tenant_id=owner, bot_name="Synthetic", slack_bot_token=encrypt_value("synthetic"))
    attached = SimpleNamespace(
        oauth_app_id=None,
        slack_bot_id=bot_id,
        custom_tool_id=custom_id,
        operation_id="read",
        tool_name="synthetic",
        config={},
    )
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE agents(id CHAR(32), tenant_id CHAR(32))"))
        connection.execute(
            text("CREATE TABLE slack_bots(id CHAR(32), tenant_id CHAR(32), agent_id CHAR(32), connection_status TEXT)")
        )
        connection.execute(text("CREATE TABLE custom_tools(id CHAR(32), tenant_id CHAR(32), enabled BOOLEAN)"))
        connection.execute(text("INSERT INTO agents VALUES (:id,:tenant)"), {"id": agent.hex, "tenant": tenant.hex})
        connection.execute(
            text("INSERT INTO slack_bots VALUES (:id,:tenant,:agent,'connected')"),
            {"id": bot_id.hex, "tenant": owner.hex, "agent": agent.hex},
        )
        connection.execute(
            text("INSERT INTO custom_tools VALUES (:id,:tenant,1)"), {"id": custom_id.hex, "tenant": owner.hex}
        )

        async def execute(stmt):
            entity = stmt.column_descriptions[0]["entity"]
            if entity is AgentTool:
                return SimpleNamespace(
                    scalar_one_or_none=lambda: attached, scalars=lambda: SimpleNamespace(all=lambda: [attached])
                )
            rows = connection.execute(stmt.with_only_columns(entity.id)).scalars().all()
            values = [custom if entity is CustomTool else bot for _ in rows]
            return SimpleNamespace(
                scalar_one_or_none=lambda: values[0] if values else None,
                scalars=lambda: SimpleNamespace(all=lambda: values),
            )

        db = SimpleNamespace(execute=execute)
        for kwargs in ({"slack_bot_id": str(bot_id)}, {"custom_tool_id": str(custom_id), "operation_id": "read"}):
            request = SaveAgentToolRequest(tool_name="synthetic", config={}, **kwargs)
            if foreign:
                with pytest.raises(HTTPException) as exc:
                    await _authorize_tool_connections(db, tenant, request)
                assert exc.value.status_code == 404
            else:
                await _authorize_tool_connections(db, tenant, request)
        resolver = CredentialResolver(SimpleNamespace(tenant_id=tenant, agent_id=agent, db_session=db))
        token = await resolver.get_slack_token("synthetic")
        assert token == (None if foreign else "synthetic")
        registry = object.__new__(ADKToolRegistry)
        registry.register_tool = MagicMock()
        await registry.load_agent_custom_tools(str(agent), db)
        assert registry.register_tool.call_count == (0 if foreign else 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["slack_bot_id", "custom_tool_id"])
async def test_save_rejects_foreign_connection_before_writes(field):
    db = AsyncMock()
    db.add = MagicMock()
    db.execute.side_effect = [
        SimpleNamespace(scalar_one_or_none=lambda: object()),
        SimpleNamespace(scalar_one_or_none=lambda: None),
    ]
    request = SaveAgentToolRequest(tool_name="synthetic", config={}, operation_id="read", **{field: str(uuid4())})
    with pytest.raises(HTTPException) as exc:
        await save_agent_tool(str(uuid4()), request, SimpleNamespace(id=uuid4()), uuid4(), db)
    assert exc.value.status_code == 404
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_custom_operation_is_rejected():
    db = AsyncMock()
    db.execute.return_value = SimpleNamespace(
        scalar_one_or_none=lambda: SimpleNamespace(openapi_schema=SCHEMA, server_url="https://example.invalid")
    )
    request = SaveAgentToolRequest(
        tool_name="synthetic", config={}, custom_tool_id=str(uuid4()), operation_id="missing"
    )
    with pytest.raises(HTTPException) as exc:
        await _authorize_tool_connections(db, uuid4(), request)
    assert exc.value.status_code == 400
