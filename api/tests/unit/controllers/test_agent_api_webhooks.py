from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.controllers import agent_api_webhooks as hooks
from src.core.database import get_async_db
from src.middleware.agent_api_auth import AgentApiAuthMiddleware

TENANT = uuid4()


def _endpoint(**kw):
    e = MagicMock(
        id=uuid4(),
        tenant_id=TENANT,
        url="https://hooks.example.com/in",
        description=None,
        events=[],
        is_active=True,
        created_at=datetime(2026, 11, 1, tzinfo=UTC),
        secret="enc(secret)",
        last_tested_at=None,
    )
    for k, v in kw.items():
        setattr(e, k, v)
    return e


@pytest.fixture
def db():
    session = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    return session


@pytest.fixture
def client(db):
    app = FastAPI()
    app.include_router(hooks.router)
    app.dependency_overrides[get_async_db] = lambda: db
    seen: list = []

    async def authenticate(_request, required_permission=None):
        seen.append(required_permission)
        return MagicMock(tenant_id=TENANT)

    with patch.object(AgentApiAuthMiddleware, "authenticate_request", authenticate):
        test_client = TestClient(app)
        test_client.permissions_seen = seen
        yield test_client


class TestCreate:
    def test_returns_the_secret_once_and_stores_it_encrypted(self, client, db):
        db.scalar.return_value = 0

        async def refresh(obj):
            obj.id, obj.created_at = uuid4(), datetime(2026, 11, 1, tzinfo=UTC)

        db.refresh = refresh
        with (
            patch.object(hooks, "destination_error", return_value=None),
            patch.object(hooks, "encrypt_value", side_effect=lambda v: f"enc({v})"),
        ):
            response = client.post(
                "/api/v1/public/webhooks",
                json={"url": "https://hooks.example.com/in", "events": ["usage.threshold"]},
            )

        assert response.status_code == 201
        secret = response.json()["secret"]
        assert secret.startswith("whsec_")
        stored = db.add.call_args.args[0]
        assert stored.secret == f"enc({secret})" and stored.tenant_id == TENANT
        assert client.permissions_seen == ["webhooks:manage"]

    def test_unknown_event_is_refused(self, client, db):
        response = client.post("/api/v1/public/webhooks", json={"url": "https://x.example.com", "events": ["bogus"]})
        assert response.status_code == 400 and "bogus" in response.json()["detail"]

    def test_unsafe_url_is_refused(self, client, db):
        db.scalar.return_value = 0
        with patch.object(hooks, "destination_error", return_value="private address"):
            response = client.post("/api/v1/public/webhooks", json={"url": "https://10.0.0.1/x"})
        assert response.status_code == 400 and "private address" in response.json()["detail"]

    def test_the_endpoint_limit_is_checked_before_any_dns_lookup(self, client, db):
        db.scalar.return_value = hooks.MAX_ENDPOINTS_PER_TENANT
        with patch.object(hooks, "destination_error") as lookup:
            response = client.post("/api/v1/public/webhooks", json={"url": "https://x.example.com"})
        assert response.status_code == 409
        lookup.assert_not_called()

    def test_a_dns_lookup_that_never_answers_is_cut_off(self, client, db):
        """Reproduces a hostile nameserver tying up the threads every API request relies on."""
        import time

        db.scalar.return_value = 0

        def hang(_url):
            time.sleep(0.5)
            return None

        with (
            patch.object(hooks, "destination_error", side_effect=hang),
            patch.object(hooks, "DNS_DEADLINE_SECONDS", 0.05),
        ):
            response = client.post("/api/v1/public/webhooks", json={"url": "https://slow.example.com"})
        assert response.status_code == 400 and hooks.DESTINATION_REFUSED in response.json()["detail"]

    def test_endpoint_limit(self, client, db):
        db.scalar.return_value = hooks.MAX_ENDPOINTS_PER_TENANT
        with patch.object(hooks, "destination_error", return_value=None):
            response = client.post("/api/v1/public/webhooks", json={"url": "https://x.example.com"})
        assert response.status_code == 409


class TestManage:
    def test_list_never_exposes_secrets(self, client, db):
        result = MagicMock()
        result.scalars.return_value.all.return_value = [_endpoint()]
        db.execute.return_value = result
        body = client.get("/api/v1/public/webhooks").json()
        assert len(body) == 1 and "secret" not in body[0]

    def test_endpoint_of_another_tenant_is_not_found(self, client, db):
        db.scalar.return_value = None
        assert client.delete(f"/api/v1/public/webhooks/{uuid4()}").status_code == 404
        assert client.post(f"/api/v1/public/webhooks/{uuid4()}/test").status_code == 404
        assert client.post(f"/api/v1/public/webhooks/{uuid4()}/reactivate").status_code == 404

    def test_endpoint_lookup_is_limited_to_the_keys_tenant(self, client, db):
        db.scalar.return_value = _endpoint()
        client.delete(f"/api/v1/public/webhooks/{uuid4()}")
        assert TENANT in db.scalar.call_args[0][0].compile().params.values()

    def test_delete(self, client, db):
        db.scalar.return_value = _endpoint()
        assert client.delete(f"/api/v1/public/webhooks/{uuid4()}").status_code == 204
        db.delete.assert_awaited_once()

    def test_reactivate_clears_the_failure_count(self, client, db):
        endpoint = _endpoint(is_active=False, consecutive_failures=10)
        db.scalar.return_value = endpoint
        db.refresh = AsyncMock()
        assert client.post(f"/api/v1/public/webhooks/{uuid4()}/reactivate").json()["is_active"] is True
        assert endpoint.consecutive_failures == 0

    def test_a_switched_off_endpoint_cannot_be_tested(self, client, db):
        """Reproduces the API saying a ping was queued when nothing would ever be sent."""
        db.scalar.return_value = _endpoint(is_active=False)
        with patch.object(hooks, "deliver_to") as deliver:
            response = client.post(f"/api/v1/public/webhooks/{uuid4()}/test")
        assert response.status_code == 409 and "Reactivate" in response.json()["detail"]
        deliver.assert_not_called()

    def test_an_endpoint_can_be_tested_once_a_minute(self, client, db):
        """Reproduces the test action being used to flood the delivery workers."""
        from datetime import timedelta

        endpoint = _endpoint(last_tested_at=datetime.now(UTC) - timedelta(seconds=10))
        db.scalar.return_value = endpoint
        with patch.object(hooks, "deliver_to") as deliver:
            response = client.post(f"/api/v1/public/webhooks/{uuid4()}/test")
        assert response.status_code == 429
        deliver.assert_not_called()

        endpoint.last_tested_at = datetime.now(UTC) - timedelta(seconds=hooks.TEST_COOLDOWN_SECONDS + 1)
        with patch.object(hooks, "deliver_to") as deliver:
            assert client.post(f"/api/v1/public/webhooks/{uuid4()}/test").status_code == 202
        deliver.assert_called_once()
        assert (datetime.now(UTC) - endpoint.last_tested_at).total_seconds() < 5

    def test_test_sends_a_ping(self, client, db):
        endpoint = _endpoint()
        db.scalar.return_value = endpoint
        with patch.object(hooks, "deliver_to") as deliver:
            response = client.post(f"/api/v1/public/webhooks/{uuid4()}/test")
        assert response.status_code == 202
        assert deliver.call_args.args[0] == endpoint.id
        assert deliver.call_args.args[1]["type"] == "ping"


def test_key_without_the_permission_is_refused(db):
    app = FastAPI()
    app.include_router(hooks.router)
    app.dependency_overrides[get_async_db] = lambda: db

    async def deny(_request, required_permission=None):
        raise HTTPException(403, f"API key does not have required permission: {required_permission}")

    with patch.object(AgentApiAuthMiddleware, "authenticate_request", deny):
        client = TestClient(app)
        assert client.get("/api/v1/public/webhooks").status_code == 403
        assert client.post("/api/v1/public/webhooks", json={"url": "https://x.example.com"}).status_code == 403
