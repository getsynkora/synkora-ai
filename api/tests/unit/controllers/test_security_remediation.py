import base64
import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from src.controllers.console.auth import LoginRequest, login
from src.controllers.recall_webhooks import receive_recall_webhook
from src.middleware.auth_middleware import get_current_tenant_id
from src.services.auth_service import AuthService


def request(body=b"", headers=None):
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": headers or [],
            "query_string": b"agent_id=attacker",
            "client": ("test", 123),
        },
        receive,
    )


@pytest.mark.asyncio
async def test_removed_membership_rejects_still_valid_tenant_claim():
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db = SimpleNamespace(execute=AsyncMock(return_value=result))
    with pytest.raises(HTTPException) as error:
        await get_current_tenant_id(
            payload={"tenant_id": str(uuid4())}, _current_account=SimpleNamespace(id=uuid4()), db=db
        )
    assert error.value.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_query", [0, 1])
async def test_login_policy_lookup_failure_never_issues_session(failed_query):
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db = AsyncMock()
    db.execute.side_effect = [result] * failed_query + [RuntimeError("policy unavailable")]
    account = SimpleNamespace(id=uuid4())
    with (
        patch.object(AuthService, "authenticate", AsyncMock(return_value=account)),
        patch("src.controllers.console.auth.SessionService.create_session", AsyncMock()) as create,
    ):
        with pytest.raises(HTTPException) as error:
            await login(request(), LoginRequest(email="user@example.com", password="password"), db)
    assert error.value.status_code == 503
    create.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [False, RuntimeError("redis unavailable")])
async def test_reset_does_not_commit_when_revocation_fails(failure):
    account = SimpleNamespace(
        id=uuid4(),
        auth_version=0,
        password_history=[],
        reset_token_expires_at=(datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = account
    db = AsyncMock()
    db.execute.return_value = result
    kwargs = {"side_effect": failure} if isinstance(failure, Exception) else {"return_value": failure}
    with patch("src.services.security.token_blacklist.TokenBlacklistService.blacklist_all_account_tokens", **kwargs):
        with pytest.raises(RuntimeError, match="temporarily unavailable"):
            await AuthService.reset_password(db, "reset-token", "new-password")
    db.commit.assert_not_awaited()
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "secret,signature,status", [(None, None, 503), ("secret", None, 401), ("secret", "invalid", 401)]
)
async def test_unverified_recall_does_not_reach_handler(secret, signature, status):
    body = json.dumps({"event": "bot.status_change", "data": {"bot": {"id": "test"}}}).encode()
    with (
        patch("src.controllers.recall_webhooks._get_webhook_secret", AsyncMock(return_value=secret)),
        patch("src.controllers.recall_webhooks._handle_bot_status_change", AsyncMock()) as handler,
    ):
        with pytest.raises(HTTPException) as error:
            await receive_recall_webhook(
                request(body, [(b"x-recall-signature", signature.encode())] if signature else []), AsyncMock()
            )
    assert error.value.status_code == status
    handler.assert_not_awaited()


@pytest.mark.asyncio
async def test_signed_recall_routes_only_signed_metadata():
    db = AsyncMock()
    db.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: "claimed")
    body = json.dumps(
        {
            "event": "bot.status_change",
            "data": {"bot": {"id": "test", "metadata": {"synkora_agent_id": "signed-agent"}}},
        }
    ).encode()
    timestamp = str(int(time.time()))
    signature = (
        "v1,"
        + base64.b64encode(
            hmac.new(b"secret", f"msg-test.{timestamp}.".encode() + body, hashlib.sha256).digest()
        ).decode()
    )
    with (
        patch("src.controllers.recall_webhooks._get_webhook_secret", AsyncMock(return_value="whsec_c2VjcmV0")),
        patch("src.controllers.recall_webhooks._handle_bot_status_change", AsyncMock()) as handler,
    ):
        response = await receive_recall_webhook(
            request(
                body,
                [
                    (b"webhook-id", b"msg-test"),
                    (b"webhook-timestamp", timestamp.encode()),
                    (b"webhook-signature", signature.encode()),
                ],
            ),
            db,
        )
    assert response["status"] == "ok"
    assert handler.await_args.args[2] == "signed-agent"


@pytest.mark.parametrize(
    "method,path,body,headers",
    [
        ("GET", "/widgets/chat/history?external_user_id=victim", None, {}),
        ("GET", f"/widgets/chat/history?conversation_id={uuid4()}", None, {}),
        ("GET", "/widgets/sessions", None, {"X-Widget-User-Id": "victim"}),
        ("POST", f"/widgets/sessions/{uuid4()}/close", {}, {}),
        (
            "POST",
            "/widgets/push/register",
            {"fcm_token": "attacker-device", "platform": "web", "user_id": "victim"},
            {},
        ),
        ("POST", f"/widgets/chat/approvals/{uuid4()}/respond", {"decision": "approved"}, {}),
    ],
)
def test_public_widget_key_cannot_access_customer_actions(method, path, body, headers):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from src.controllers.widgets import widgets_router
    from src.core.database import get_async_db

    widget = SimpleNamespace(
        id=uuid4(), agent_id=uuid4(), tenant_id=uuid4(), identity_secret="secret", identity_verification_required=False
    )
    db = AsyncMock()
    app = FastAPI()
    app.include_router(widgets_router)
    app.dependency_overrides[get_async_db] = lambda: db
    with patch("src.middleware.widget_auth.WidgetAuthMiddleware.validate_api_key", AsyncMock(return_value=widget)):
        with TestClient(app) as client:
            response = client.request(method, path, json=body, headers={"X-Widget-API-Key": "public-key", **headers})
    assert response.status_code == 403
    db.execute.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.parametrize("offset", [-601, 601])
def test_recall_rejects_old_and_future_signed_deliveries(offset):
    from src.services.recall.recall_service import RecallService

    body = b'{"event":"test"}'
    timestamp = str(int(time.time()) + offset)
    signature = base64.b64encode(
        hmac.new(b"secret", f"msg-test.{timestamp}.".encode() + body, hashlib.sha256).digest()
    ).decode()
    assert not RecallService.verify_webhook_signature(
        body,
        {"webhook-id": "msg-test", "webhook-timestamp": timestamp, "webhook-signature": "v1," + signature},
        "whsec_c2VjcmV0",
    )


@pytest.mark.asyncio
async def test_recall_duplicate_never_reaches_handler():
    body = json.dumps({"event": "bot.status_change", "data": {"bot": {"id": "test"}}}).encode()
    timestamp = str(int(time.time()))
    signature = base64.b64encode(
        hmac.new(b"secret", f"msg-test.{timestamp}.".encode() + body, hashlib.sha256).digest()
    ).decode()
    headers = [
        (b"webhook-id", b"msg-test"),
        (b"webhook-timestamp", timestamp.encode()),
        (b"webhook-signature", ("v1," + signature).encode()),
    ]
    db = AsyncMock()
    db.execute.side_effect = [
        SimpleNamespace(scalar_one_or_none=lambda: "claimed"),
        SimpleNamespace(scalar_one_or_none=lambda: None),
    ]
    with (
        patch("src.controllers.recall_webhooks._get_webhook_secret", AsyncMock(return_value="whsec_c2VjcmV0")),
        patch("src.controllers.recall_webhooks._handle_bot_status_change", AsyncMock()) as handler,
    ):
        await receive_recall_webhook(request(body, headers), db)
        result = await receive_recall_webhook(request(body, headers), db)
    assert result["status"] == "duplicate"
    handler.assert_awaited_once()
    db.commit.assert_awaited_once()
