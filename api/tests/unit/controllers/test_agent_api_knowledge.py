from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.controllers import agent_api_knowledge as kb_api
from src.controllers import knowledge_bases as kb_controller
from src.core.database import get_async_db
from src.middleware import agent_api_auth as auth
from src.middleware.agent_api_auth import AgentApiAuthMiddleware, knowledge_tenant
from src.models.knowledge_base import KnowledgeBaseStatus

TENANT = uuid4()
AGENT = uuid4()

# The only knowledge-base routes an API key may reach, and the permission each needs.
KEY_ACCESSIBLE = {
    ("GET", "/knowledge-bases/{kb_id}/stats"): "knowledge:read",
    ("POST", "/knowledge-bases/{kb_id}/search"): "knowledge:read",
    ("POST", "/knowledge-bases/{kb_id}/documents/upload"): "knowledge:write",
    ("POST", "/knowledge-bases/{kb_id}/documents/text"): "knowledge:write",
    ("GET", "/knowledge-bases/{kb_id}/documents"): "knowledge:read",
    ("GET", "/knowledge-bases/{kb_id}/documents/{doc_id}"): "knowledge:read",
    ("DELETE", "/knowledge-bases/{kb_id}/documents/{doc_id}"): "knowledge:write",
    ("POST", "/knowledge-bases/{kb_id}/documents/{doc_id}/reprocess"): "knowledge:write",
}


def _knowledge_permission(route):
    for dependency in route.dependant.dependencies:
        permission = getattr(dependency.call, "knowledge_permission", None)
        if permission:
            return permission
    return None


class TestRouteInventory:
    def test_only_the_intended_routes_accept_api_keys(self):
        found = {}
        for route in kb_controller.router.routes:
            permission = _knowledge_permission(route)
            if permission:
                for method in route.methods:
                    found[(method, route.path)] = permission
        assert found == KEY_ACCESSIBLE

    def test_routes_that_return_secrets_or_fetch_urls_stay_login_only(self):
        sensitive = {
            ("GET", "/knowledge-bases/{kb_id}"),  # returns decrypted embedding and vector DB config
            ("POST", "/knowledge-bases/{kb_id}/documents/crawl"),  # fetches arbitrary URLs
            ("POST", "/knowledge-bases"),
            ("PUT", "/knowledge-bases/{kb_id}"),
            ("DELETE", "/knowledge-bases/{kb_id}"),
            ("POST", "/knowledge-bases/{kb_id}/documents/bulk-delete"),
            ("GET", "/knowledge-bases/{kb_id}/documents/{doc_id}/download"),
        }
        for route in kb_controller.router.routes:
            for method in route.methods:
                if (method, route.path) in sensitive:
                    assert _knowledge_permission(route) is None, (method, route.path)


def _request(kb_id=None):
    request = MagicMock()
    request.path_params = {"kb_id": kb_id} if kb_id is not None else {}
    return request


class TestKnowledgeTenantDependency:
    async def test_missing_credentials_are_rejected(self):
        dependency = knowledge_tenant("knowledge:read")
        with pytest.raises(HTTPException) as err:
            await dependency(_request(), None, AsyncMock())
        assert err.value.status_code == 401

    async def test_logged_in_users_are_checked_as_before(self):
        dependency = knowledge_tenant("knowledge:read")
        with patch(
            "src.middleware.auth_middleware.authenticate_tenant_token", AsyncMock(return_value=(MagicMock(), TENANT))
        ) as check:
            assert await dependency(_request("5"), "Bearer jwt.token.here", AsyncMock()) == TENANT
        assert check.await_args.args[0] == "jwt.token.here"

    async def test_a_key_for_a_linked_knowledge_base_gets_its_tenant(self):
        db = AsyncMock()
        db.scalar.return_value = 1
        key = MagicMock(tenant_id=TENANT, agent_id=AGENT)
        permissions = []

        async def authenticate(_request, required_permission=None):
            permissions.append(required_permission)
            return key

        with patch.object(AgentApiAuthMiddleware, "authenticate_request", authenticate):
            tenant = await knowledge_tenant("knowledge:write")(_request("7"), "Bearer sk_live_abc", db)
        assert tenant == TENANT and permissions == ["knowledge:write"]
        compiled = db.scalar.call_args[0][0].compile()
        assert AGENT in compiled.params.values() and 7 in compiled.params.values()

    async def test_a_key_cannot_reach_a_knowledge_base_not_linked_to_its_agent(self):
        db = AsyncMock()
        db.scalar.return_value = None
        key = MagicMock(tenant_id=TENANT, agent_id=AGENT)
        with patch.object(AgentApiAuthMiddleware, "authenticate_request", AsyncMock(return_value=key)):
            with pytest.raises(HTTPException) as err:
                await knowledge_tenant("knowledge:read")(_request("7"), "Bearer sk_live_abc", db)
        assert err.value.status_code == 404

    async def test_a_key_without_the_permission_is_refused(self):
        deny = AsyncMock(side_effect=HTTPException(403, "API key does not have required permission: knowledge:write"))
        with patch.object(AgentApiAuthMiddleware, "authenticate_request", deny):
            with pytest.raises(HTTPException) as err:
                await knowledge_tenant("knowledge:write")(_request("7"), "Bearer sk_live_abc", AsyncMock())
        assert err.value.status_code == 403

    async def test_a_non_numeric_knowledge_base_id_is_not_found(self):
        key = MagicMock(tenant_id=TENANT, agent_id=AGENT)
        with patch.object(AgentApiAuthMiddleware, "authenticate_request", AsyncMock(return_value=key)):
            with pytest.raises(HTTPException) as err:
                await knowledge_tenant("knowledge:read")(_request("abc"), "Bearer sk_live_abc", AsyncMock())
        assert err.value.status_code == 404

    def test_the_module_exposes_no_other_way_around_the_link_check(self):
        assert hasattr(auth, "knowledge_tenant")


@pytest.fixture
def db():
    session = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def client(db):
    app = FastAPI()
    app.include_router(kb_api.router)
    app.dependency_overrides[get_async_db] = lambda: db
    seen = []

    async def authenticate(_request, required_permission=None):
        seen.append(required_permission)
        return MagicMock(tenant_id=TENANT, agent_id=AGENT)

    with patch.object(AgentApiAuthMiddleware, "authenticate_request", authenticate):
        test_client = TestClient(app)
        test_client.permissions_seen = seen
        yield test_client


def _kb(**kw):
    kb = MagicMock(id=3, description=None, total_documents=2, total_chunks=40, status=KnowledgeBaseStatus.ACTIVE)
    kb.name = "FAQ"
    for key, value in kw.items():
        setattr(kb, key, value)
    return kb


class TestKnowledgeApi:
    URL = f"/api/v1/public/agents/{AGENT}/knowledge-bases"

    def test_only_the_keys_own_agent_is_reachable(self, client, db):
        response = client.get(f"/api/v1/public/agents/{uuid4()}/knowledge-bases")
        assert response.status_code == 403
        assert client.post(f"/api/v1/public/agents/{uuid4()}/knowledge-bases", json={"name": "x"}).status_code == 403

    def test_list_returns_linked_knowledge_bases(self, client, db):
        db.scalar.return_value = MagicMock(id=AGENT)
        result = MagicMock()
        result.scalars.return_value.all.return_value = [_kb()]
        db.execute.return_value = result
        body = client.get(self.URL).json()
        assert body == [
            {"id": 3, "name": "FAQ", "description": None, "document_count": 2, "total_chunks": 40, "is_active": True}
        ]
        assert client.permissions_seen == ["knowledge:read"]
        compiled = db.execute.call_args[0][0].compile()
        assert TENANT in compiled.params.values() and AGENT in compiled.params.values()

    def test_create_uses_defaults_links_the_agent_and_returns_no_config(self, client, db):
        db.scalar.side_effect = [MagicMock(id=AGENT), _kb(name="Policies")]
        with (
            patch.object(kb_api, "PlanRestrictionService") as restrictions,
            patch.object(kb_api, "create_knowledge_base", AsyncMock(return_value=MagicMock(id=3))) as create,
        ):
            restrictions.return_value.enforce_knowledge_base_limit = AsyncMock()
            response = client.post(self.URL, json={"name": "Policies"})

        assert response.status_code == 201
        assert set(response.json()) == {"id", "name", "description", "document_count", "total_chunks", "is_active"}
        request, tenant_id, _ = create.await_args.args
        assert request.name == "Policies" and tenant_id == TENANT
        linked = db.add.call_args.args[0]
        assert linked.agent_id == AGENT and linked.knowledge_base_id == 3
        assert client.permissions_seen == ["knowledge:write"]

    def test_plan_limit_is_enforced(self, client, db):
        db.scalar.return_value = MagicMock(id=AGENT)
        with patch.object(kb_api, "PlanRestrictionService") as restrictions:
            restrictions.return_value.enforce_knowledge_base_limit = AsyncMock(
                side_effect=kb_api.PlanRestrictionError("Knowledge base limit reached")
            )
            response = client.post(self.URL, json={"name": "Another"})
        assert response.status_code == 403 and "limit" in response.json()["detail"]
