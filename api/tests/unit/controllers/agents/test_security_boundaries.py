from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.controllers.agents.conversations import list_agent_conversations
from src.controllers.agents.llm_configs import get_llm_config, list_llm_configs
from src.controllers.agents.mcp_servers import list_agent_mcp_servers
from src.middleware.widget_auth import WidgetAuthMiddleware


@pytest.mark.parametrize("source", ["slack", "whatsapp", "widget", "flutter", "chrome"])
@pytest.mark.asyncio
async def test_public_agent_does_not_expose_other_tenants_channel_inbox(source):
    result = MagicMock()
    result.scalar_one_or_none.return_value = SimpleNamespace(id=uuid4(), tenant_id=uuid4(), is_public=True)
    db = SimpleNamespace(execute=AsyncMock(return_value=result))
    with pytest.raises(HTTPException) as error:
        await list_agent_conversations(
            str(uuid4()), source=source, current_account=SimpleNamespace(id=uuid4()), tenant_id=uuid4(), db=db
        )
    assert error.value.status_code == 404
    db.execute.assert_awaited_once()  # No conversation query was allowed.


@pytest.mark.asyncio
async def test_public_users_own_web_conversations_remain_available():
    tenant = uuid4()
    result = MagicMock()
    result.scalar_one_or_none.return_value = SimpleNamespace(id=uuid4(), tenant_id=uuid4(), is_public=True)
    result.scalars.return_value.all.return_value = []
    db = SimpleNamespace(execute=AsyncMock(return_value=result))
    response = await list_agent_conversations(
        str(uuid4()), source="web", current_account=SimpleNamespace(id=uuid4()), tenant_id=tenant, db=db
    )
    assert response.success
    assert "account_id" in str(db.execute.call_args.args[0])


@pytest.mark.asyncio
async def test_mcp_configuration_requires_owner_tenant_predicate():
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db = SimpleNamespace(execute=AsyncMock(return_value=result))
    tenant = uuid4()
    with pytest.raises(HTTPException) as error:
        await list_agent_mcp_servers(str(uuid4()), tenant_id=tenant, db=db)
    assert error.value.status_code == 404
    query = db.execute.call_args.args[0]
    where = str(query.whereclause)
    assert "tenant_id" in where
    assert "is_public" not in where
    assert tenant in query.compile().params.values()


@pytest.mark.parametrize("owner", [True, False])
@pytest.mark.asyncio
async def test_public_model_choices_omit_private_provider_settings(owner):
    tenant = uuid4()
    agent = SimpleNamespace(id=uuid4(), tenant_id=tenant if owner else uuid4())
    config = SimpleNamespace(
        id=uuid4(),
        agent_id=agent.id,
        tenant_id=agent.tenant_id,
        name="model",
        provider="openai",
        model_name="test",
        api_base="https://private.example",
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
        additional_params={"extra_headers": {"Authorization": "private-token"}},
        is_default=True,
        display_order=0,
        enabled=True,
        routing_rules=None,
        routing_weight=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    with (
        patch("src.controllers.agents.llm_configs.get_agent_by_name_or_id", AsyncMock(return_value=agent)),
        patch("src.controllers.agents.llm_configs.LLMConfigService") as service,
    ):
        service.get_agent_configs = AsyncMock(return_value=[config])
        service.get_config = AsyncMock(return_value=config)
        listed = await list_llm_configs("agent", db=MagicMock(), tenant_id=tenant)
        individual = await get_llm_config("agent", config.id, db=MagicMock(), tenant_id=tenant)
    for item in [*listed, individual]:
        assert item.model_name == "test"
        assert item.additional_params == (config.additional_params if owner else {})
        assert item.api_base == (config.api_base if owner else None)


@pytest.mark.parametrize(
    "origin,allowed",
    [
        ("https://app.example.com", True),
        ("https://deep.app.example.com/path", True),
        ("https://evil-example.com", False),
        ("https://example.com.evil.test", False),
        ("https://example.com", False),
        ("https://APP.EXAMPLE.COM:443/path", True),
        ("https://app.example.com:bad", False),
        ("https://app.example.com@evil.test", False),
        ("null", False),
        ("file://app.example.com", False),
    ],
)
def test_widget_wildcard_is_a_hostname_boundary(origin, allowed):
    widget = SimpleNamespace(allowed_domains=["*.example.com"])
    assert WidgetAuthMiddleware.validate_domain(widget, origin) is allowed


@pytest.mark.asyncio
async def test_owner_tenant_can_still_read_channel_inbox():
    tenant = uuid4()
    result = MagicMock()
    result.scalar_one_or_none.return_value = SimpleNamespace(id=uuid4(), tenant_id=tenant, is_public=True)
    result.scalars.return_value.all.return_value = []
    db = SimpleNamespace(execute=AsyncMock(return_value=result))
    response = await list_agent_conversations(
        str(uuid4()), source="slack", current_account=SimpleNamespace(id=uuid4()), tenant_id=tenant, db=db
    )
    assert response.success
    assert db.execute.await_count == 2
