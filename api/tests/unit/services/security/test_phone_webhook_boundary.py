import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from src.controllers import phone_calls
from src.services.voice.inbound.vapi_provider import VapiProvider


@pytest.mark.asyncio
async def test_missing_phone_secret_never_dispatches(monkeypatch):
    provider = MagicMock()
    provider.handle_webhook = AsyncMock()
    monkeypatch.setattr(phone_calls, "get_call_provider", lambda name: provider)
    request = SimpleNamespace(body=AsyncMock(return_value=b'{"message":{"type":"call-started"}}'), headers={})
    with pytest.raises(HTTPException) as exc:
        await phone_calls.vapi_webhook(request, db=AsyncMock(), x_vapi_secret=None)
    assert exc.value.status_code == 401
    provider.handle_webhook.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["phone", "assistant", "existing"])
@pytest.mark.parametrize(
    "secret,configured,allowed", [("valid", "valid", True), ("wrong", "valid", False), ("valid", "", False)]
)
async def test_phone_credentials_checked_for_each_routing_mode(monkeypatch, route, secret, configured, allowed):
    agent = SimpleNamespace(
        id=uuid.uuid4(), is_active=True, phone_config={"webhook_secret": configured, "vapi_assistant_id": "assistant"}
    )
    call = {"id": "call"}
    if route == "phone":
        call["phoneNumber"] = {"number": "+15555550123"}
    elif route == "assistant":
        call["assistantId"] = "assistant"
    existing = SimpleNamespace(agent_id=agent.id) if route == "existing" else None
    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = existing
    db = SimpleNamespace(execute=AsyncMock(return_value=query_result), get=AsyncMock(return_value=agent))
    provider = VapiProvider()
    provider.handle_webhook = AsyncMock(return_value={})
    provider._find_phone_number = AsyncMock(return_value=SimpleNamespace(agent_id=agent.id))
    provider._find_agent_by_assistant_id = AsyncMock(return_value=agent)
    monkeypatch.setattr(phone_calls, "get_call_provider", lambda name: provider)
    body = {"message": {"type": "conversation-update" if existing else "call-started", "call": call}}
    request = SimpleNamespace(body=AsyncMock(return_value=json.dumps(body).encode()), headers={"x-vapi-secret": secret})
    if allowed:
        await phone_calls.vapi_webhook(request, db=db, x_vapi_secret=secret)
        provider.handle_webhook.assert_awaited_once()
    else:
        with pytest.raises(HTTPException) as exc:
            await phone_calls.vapi_webhook(request, db=db, x_vapi_secret=secret)
        assert exc.value.status_code == 401
        provider.handle_webhook.assert_not_awaited()


@pytest.mark.asyncio
async def test_foreign_call_id_cannot_be_authorized_by_own_secret(monkeypatch):
    victim = SimpleNamespace(id=uuid.uuid4(), is_active=True, phone_config={"webhook_secret": "victim"})
    attacker = SimpleNamespace(id=uuid.uuid4(), is_active=True, phone_config={"webhook_secret": "attacker"})
    result = MagicMock()
    result.scalar_one_or_none.return_value = SimpleNamespace(agent_id=victim.id)
    db = SimpleNamespace(execute=AsyncMock(return_value=result), get=AsyncMock(side_effect=[victim, attacker]))
    provider = VapiProvider()
    provider._find_phone_number = AsyncMock(return_value=SimpleNamespace(agent_id=attacker.id))
    provider.handle_webhook = AsyncMock()
    monkeypatch.setattr(phone_calls, "get_call_provider", lambda name: provider)
    request = SimpleNamespace(
        body=AsyncMock(
            return_value=json.dumps(
                {
                    "message": {
                        "type": "end-of-call-report",
                        "call": {"id": "victim-call", "phoneNumber": {"number": "+15555550123"}},
                    }
                }
            ).encode()
        ),
        headers={},
    )
    with pytest.raises(HTTPException) as exc:
        await phone_calls.vapi_webhook(request, db=db, x_vapi_secret="attacker")
    assert exc.value.status_code == 401
    provider.handle_webhook.assert_not_awaited()
