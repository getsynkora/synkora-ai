import base64
import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.requests import Request

from src.controllers import recall_webhooks as webhooks
from src.models.recall_webhook_receipt import RecallWebhookReceipt


def signed_request():
    payload = json.dumps({"event": "bot.status_change", "data": {"bot": {"id": "synthetic"}}}).encode()
    timestamp = str(int(time.time()))
    signature = base64.b64encode(
        hmac.new(b"secret", f"msg-transaction.{timestamp}.".encode() + payload, hashlib.sha256).digest()
    ).decode()

    async def receive():
        return {"type": "http.request", "body": payload, "more_body": False}

    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "query_string": b"",
            "headers": [
                (b"webhook-id", b"msg-transaction"),
                (b"webhook-timestamp", timestamp.encode()),
                (b"webhook-signature", ("v1," + signature).encode()),
            ],
        },
        receive,
    )


@pytest.mark.asyncio
async def test_failed_delivery_rolls_back_and_retry_commits_once(monkeypatch, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/receipts.db")
    async with engine.begin() as connection:
        await connection.run_sync(RecallWebhookReceipt.__table__.create)
        await connection.execute(text("CREATE TABLE effects (value TEXT)"))
    sessions = async_sessionmaker(engine)
    monkeypatch.setattr(webhooks, "_get_webhook_secret", AsyncMock(return_value="whsec_c2VjcmV0"))
    attempts = []

    async def handle(db, *args):
        await db.execute(text("INSERT INTO effects VALUES ('synthetic')"))
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("transient failure after write")

    monkeypatch.setattr(webhooks, "_handle_bot_status_change", handle)
    try:
        async with sessions() as db:
            with pytest.raises(HTTPException) as error:
                await webhooks.receive_recall_webhook(signed_request(), db)
            assert error.value.status_code == 503
        async with sessions() as db:
            assert (await db.execute(text("SELECT COUNT(*) FROM effects"))).scalar() == 0
            assert (await db.execute(text("SELECT COUNT(*) FROM recall_webhook_receipts"))).scalar() == 0
            assert (await webhooks.receive_recall_webhook(signed_request(), db))["status"] == "ok"
        async with sessions() as db:
            assert (await webhooks.receive_recall_webhook(signed_request(), db))["status"] == "duplicate"
            assert (await db.execute(text("SELECT COUNT(*) FROM effects"))).scalar() == 1
            assert (await db.execute(text("SELECT COUNT(*) FROM recall_webhook_receipts"))).scalar() == 1
        assert len(attempts) == 2
    finally:
        await engine.dispose()
