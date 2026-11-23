"""Platform keys: tenant-level keys for integrations (no agent), managed by owners and admins only."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.controllers import agent_api_provisioning as prov
from src.controllers import platform_keys
from src.core.database import get_async_db
from src.middleware.agent_api_auth import AgentApiAuthMiddleware
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.services.agent_api.api_key_service import AgentApiKeyService, validate_platform_permissions
from src.services.tenant_provisioning_service import ProvisioningError, TenantProvisioningService

TENANT = uuid4()


def _key(**fields):
    defaults = {"agent_id": None, "permissions": ["tenants:manage", "billing:read", "webhooks:manage"]}
    return SimpleNamespace(**{**defaults, **fields})


# ---------------------------------------------------------------------------
# What a platform key can do
# ---------------------------------------------------------------------------


class TestPlatformKeyPermissions:
    @pytest.mark.parametrize("permission", ["tenants:manage", "billing:read", "webhooks:manage"])
    def test_listed_platform_permissions_are_granted(self, permission):
        assert AgentApiKeyService.check_permission(_key(), permission)

    @pytest.mark.parametrize(
        "permission", ["chat", "read", "write", "a2a", "mcp_server", "knowledge:read", "handoff:read", "handoff:write"]
    )
    def test_agent_permissions_are_never_granted(self, permission):
        # agent endpoints compare "the key's agent" with the requested one; a platform key has none
        assert not AgentApiKeyService.check_permission(_key(), permission)

    def test_agent_permissions_stored_on_a_platform_key_still_do_nothing(self):
        assert not AgentApiKeyService.check_permission(_key(permissions=["*", "chat"]), "chat")

    def test_a_platform_permission_must_be_listed(self):
        assert not AgentApiKeyService.check_permission(_key(permissions=["billing:read"]), "tenants:manage")

    def test_agent_keys_are_unchanged(self):
        agent_key = SimpleNamespace(agent_id=uuid4(), permissions=["chat"])
        assert AgentApiKeyService.check_permission(agent_key, "chat")

    def test_only_platform_permissions_can_be_requested(self):
        assert validate_platform_permissions(["billing:read", "tenants:manage", "billing:read"]) == [
            "billing:read",
            "tenants:manage",
        ]
        for bad in (["chat"], ["*"], [], ["tenants:manage", "handoff:write"]):
            with pytest.raises(ValueError):
                validate_platform_permissions(bad)


# ---------------------------------------------------------------------------
# Platform keys API (dashboard)
# ---------------------------------------------------------------------------


def _row(**fields):
    defaults = {
        "id": uuid4(),
        "key_name": "Otoride",
        "key_prefix": "sk_live_abcdefghijkl",
        "permissions": ["tenants:manage"],
        "is_active": True,
        "last_used_at": None,
        "created_at": datetime(2026, 11, 23, tzinfo=UTC),
        "agent_id": None,
    }
    return SimpleNamespace(**{**defaults, **fields})


class TestPlatformKeysApi:
    def test_router_requires_the_admin_role(self):
        dependencies = [d.dependency for d in platform_keys.router.dependencies]
        assert len(dependencies) == 1
        assert dependencies[0].__qualname__.startswith("require_role")

    def test_create_refuses_agent_permissions(self):
        with pytest.raises(ValidationError):
            platform_keys.CreatePlatformKeyRequest(name="x", permissions=["chat"])

    def _client(self, db):
        app = FastAPI()
        app.include_router(platform_keys.router)
        app.dependency_overrides[get_async_db] = lambda: db
        app.dependency_overrides[get_current_tenant_id] = lambda: TENANT
        app.dependency_overrides[get_current_account] = lambda: SimpleNamespace(id=uuid4())
        for dependency in platform_keys.router.dependencies:
            app.dependency_overrides[dependency.dependency] = lambda: None
        return TestClient(app)

    def test_create_makes_a_key_without_an_agent_and_shows_it_once(self):
        db = AsyncMock()
        db.scalars = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        created = _row(permissions=["billing:read", "tenants:manage"])
        with (
            patch.object(
                platform_keys.AgentApiKeyService, "create_api_key", AsyncMock(return_value=(created, "sk_live_full"))
            ) as create,
            patch.object(platform_keys.ActivityLogService, "queue_activity") as audit,
        ):
            response = self._client(db).post(
                "/api/v1/platform-keys", json={"name": "Otoride", "permissions": ["tenants:manage", "billing:read"]}
            )
        assert response.status_code == 201
        assert response.json()["api_key"] == "sk_live_full"
        assert create.call_args.kwargs["agent_id"] is None
        assert create.call_args.kwargs["tenant_id"] == TENANT
        assert audit.call_args.kwargs["action"] == "platform_key.created"

    def test_create_stops_at_the_key_limit(self):
        db = AsyncMock()
        many = [uuid4() for _ in range(platform_keys.MAX_PLATFORM_KEYS)]
        db.scalars = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=many)))
        with patch.object(platform_keys.AgentApiKeyService, "create_api_key", AsyncMock()) as create:
            response = self._client(db).post(
                "/api/v1/platform-keys", json={"name": "x", "permissions": ["billing:read"]}
            )
        assert response.status_code == 409
        create.assert_not_called()

    def test_an_agent_key_cannot_be_changed_here(self):
        db = AsyncMock()
        db.scalar = AsyncMock(return_value=None)  # the query only matches keys without an agent
        response = self._client(db).delete(f"/api/v1/platform-keys/{uuid4()}")
        assert response.status_code == 404
        query = str(db.scalar.call_args.args[0])
        assert "agent_api_keys.agent_id IS NULL" in query


# ---------------------------------------------------------------------------
# Self-serve workspace management
# ---------------------------------------------------------------------------


def _provisioning_client(manager):
    db = AsyncMock()
    db.get = AsyncMock(return_value=manager)
    app = FastAPI()
    app.include_router(prov.router)
    app.dependency_overrides[get_async_db] = lambda: db
    return TestClient(app)


class TestSelfServeManagement:
    def _authenticate_as(self, key):
        async def authenticate(_request, required_permission=None):
            return key

        return patch.object(AgentApiAuthMiddleware, "authenticate_request", authenticate)

    def test_a_platform_key_manages_workspaces_without_operator_enablement(self):
        client = _provisioning_client(MagicMock(id=TENANT, can_manage_tenants=False))
        with (
            self._authenticate_as(_key(tenant_id=TENANT)),
            patch.object(prov.TenantProvisioningService, "list_tenants", AsyncMock(return_value=([], 0))),
        ):
            response = client.get("/api/v1/public/tenants")
        assert response.status_code == 200

    def test_an_agent_key_still_needs_operator_enablement(self):
        client = _provisioning_client(MagicMock(id=TENANT, can_manage_tenants=False))
        with self._authenticate_as(SimpleNamespace(tenant_id=TENANT, agent_id=uuid4(), permissions=["tenants:manage"])):
            assert client.get("/api/v1/public/tenants").status_code == 403


class TestWorkspaceLimit:
    def _service(self, plan_features, managed_count):
        db = AsyncMock()
        db.scalar = AsyncMock(side_effect=[plan_features, managed_count])
        return TenantProvisioningService(db, MagicMock(id=TENANT))

    async def test_the_plan_sets_the_limit(self):
        service = self._service({"max_managed_tenants": 3}, 3)
        with pytest.raises(ProvisioningError) as err:
            await service._ensure_below_workspace_limit()
        assert err.value.status_code == 403

    async def test_below_the_limit_is_allowed(self):
        await self._service({"max_managed_tenants": 3}, 2)._ensure_below_workspace_limit()

    async def test_without_a_plan_value_the_default_applies(self):
        with patch("src.services.tenant_provisioning_service.settings") as settings:
            settings.max_managed_tenants_default = 1
            service = self._service(None, 1)
            with pytest.raises(ProvisioningError):
                await service._ensure_below_workspace_limit()

    async def test_a_bad_plan_value_falls_back_to_the_default(self):
        with patch("src.services.tenant_provisioning_service.settings") as settings:
            settings.max_managed_tenants_default = 5
            assert await self._service({"max_managed_tenants": "lots"}, 0).workspace_limit() == 5

    async def test_creating_a_workspace_checks_the_limit_first(self):
        db = AsyncMock()
        db.add = MagicMock()
        service = TenantProvisioningService(db, MagicMock(id=TENANT))
        with patch.object(
            service, "_ensure_below_workspace_limit", AsyncMock(side_effect=ProvisioningError("limit", 403))
        ):
            with pytest.raises(ProvisioningError):
                await service.create_tenant("Acme")
        db.add.assert_not_called()


# ---------------------------------------------------------------------------
# Agent key pages never show or change platform keys
# ---------------------------------------------------------------------------


class TestAgentKeyPagesSkipPlatformKeys:
    async def test_list_only_returns_agent_keys(self):
        from src.controllers import agent_api_keys

        db = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=result)
        await agent_api_keys.list_api_keys(agent_id=None, tenant_id=TENANT, db=db)
        assert "agent_api_keys.agent_id IS NOT NULL" in str(db.execute.call_args.args[0])
