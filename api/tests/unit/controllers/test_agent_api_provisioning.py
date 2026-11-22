from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.controllers import agent_api_provisioning as prov
from src.core.database import get_async_db
from src.middleware.agent_api_auth import AgentApiAuthMiddleware

MANAGER = uuid4()


def _client(manager_tenant):
    db = AsyncMock()
    db.get = AsyncMock(return_value=manager_tenant)
    app = FastAPI()
    app.include_router(prov.router)
    app.dependency_overrides[get_async_db] = lambda: db
    return TestClient(app)


def _authenticated(permission_seen: list):
    async def authenticate(_request, required_permission=None):
        permission_seen.append(required_permission)
        return MagicMock(tenant_id=MANAGER)

    return patch.object(AgentApiAuthMiddleware, "authenticate_request", authenticate)


class TestAccessControl:
    def test_tenant_not_enabled_for_management_is_refused(self):
        seen: list = []
        client = _client(MagicMock(id=MANAGER, can_manage_tenants=False))
        with _authenticated(seen):
            response = client.get("/api/v1/public/tenants")
        assert response.status_code == 403
        assert seen == ["tenants:manage"]

    def test_unknown_tenant_for_the_key_is_refused(self):
        client = _client(None)
        with _authenticated([]):
            assert client.get("/api/v1/public/tenants").status_code == 403

    def test_key_without_the_permission_is_refused(self):
        async def deny(_request, required_permission=None):
            raise HTTPException(403, f"API key does not have required permission: {required_permission}")

        client = _client(MagicMock(id=MANAGER, can_manage_tenants=True))
        with patch.object(AgentApiAuthMiddleware, "authenticate_request", deny):
            for method, path in [
                ("get", "/api/v1/public/tenants"),
                ("post", "/api/v1/public/tenants"),
                ("get", f"/api/v1/public/tenants/{uuid4()}"),
                ("put", f"/api/v1/public/tenants/{uuid4()}/subscription"),
                ("post", f"/api/v1/public/tenants/{uuid4()}/api-keys"),
            ]:
                response = getattr(client, method)(path, **({"json": {}} if method in ("post", "put") else {}))
                assert response.status_code == 403, (method, path)

    def test_enabled_manager_can_list_only_its_own_tenants(self):
        client = _client(MagicMock(id=MANAGER, can_manage_tenants=True))
        created = datetime(2026, 11, 1, tzinfo=UTC)
        mine = MagicMock(id=uuid4(), external_ref="c-1", status="ACTIVE", created_at=created)
        mine.name = "Customer one"
        with (
            _authenticated([]),
            patch.object(
                prov.TenantProvisioningService, "list_tenants", AsyncMock(return_value=([mine], 1))
            ) as listing,
        ):
            body = client.get("/api/v1/public/tenants?external_ref=c-1").json()
        assert body["total"] == 1 and body["tenants"][0]["external_ref"] == "c-1"
        assert listing.await_args.kwargs["external_ref"] == "c-1"

    def test_other_managers_tenant_is_reported_as_not_found(self):
        client = _client(MagicMock(id=MANAGER, can_manage_tenants=True))
        with (
            _authenticated([]),
            patch.object(
                prov.TenantProvisioningService,
                "get_managed",
                AsyncMock(side_effect=prov.ProvisioningError("Tenant not found", 404)),
            ),
        ):
            assert client.get(f"/api/v1/public/tenants/{uuid4()}").status_code == 404
            assert client.get(f"/api/v1/public/tenants/{uuid4()}/usage").status_code == 404
            assert client.put(f"/api/v1/public/tenants/{uuid4()}/subscription", json={}).status_code == 404


class TestKeyResponses:
    def test_created_key_is_returned_once_with_the_plain_key(self):
        client = _client(MagicMock(id=MANAGER, can_manage_tenants=True))
        key = MagicMock(
            id=uuid4(),
            agent_id=uuid4(),
            key_prefix="sk_live_abc",
            permissions=["chat"],
            is_active=True,
            created_at=datetime(2026, 11, 1, tzinfo=UTC),
        )
        key.key_name = "Frontend"
        with (
            _authenticated([]),
            patch.object(prov.TenantProvisioningService, "get_managed", AsyncMock(return_value=MagicMock(id=uuid4()))),
            patch.object(
                prov.TenantProvisioningService, "create_api_key", AsyncMock(return_value=(key, "sk_live_full"))
            ),
        ):
            response = client.post(
                f"/api/v1/public/tenants/{uuid4()}/api-keys", json={"agent_id": str(uuid4()), "name": "Frontend"}
            )
        assert response.status_code == 201
        assert response.json()["key"] == "sk_live_full"

    def test_refused_permission_comes_back_as_a_client_error(self):
        client = _client(MagicMock(id=MANAGER, can_manage_tenants=True))
        with (
            _authenticated([]),
            patch.object(prov.TenantProvisioningService, "get_managed", AsyncMock(return_value=MagicMock(id=uuid4()))),
            patch.object(
                prov.TenantProvisioningService,
                "create_api_key",
                AsyncMock(side_effect=prov.ProvisioningError("Permissions not allowed", 400)),
            ),
        ):
            response = client.post(
                f"/api/v1/public/tenants/{uuid4()}/api-keys",
                json={"agent_id": str(uuid4()), "name": "x", "permissions": ["tenants:manage"]},
            )
        assert response.status_code == 400
