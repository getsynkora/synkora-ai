from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.controllers import agent_api_account as account
from src.core.database import get_async_db
from src.middleware.agent_api_auth import AgentApiAuthMiddleware
from src.models.subscription_plan import PlanTier
from src.services.agent_api.api_key_service import AgentApiKeyService
from src.services.billing.quota_service import PoolStatus

TENANT = uuid4()
START = datetime(2026, 11, 1, tzinfo=UTC)
END = datetime(2026, 12, 1, tzinfo=UTC)


def _plan(**overrides):
    plan = MagicMock()
    plan.id = uuid4()
    plan.name = "Growth"
    plan.tier = PlanTier.STARTER
    plan.description = "Example"
    plan.price_monthly = Decimal("299.00")
    plan.price_yearly = Decimal("2868.00")
    plan.credits_monthly = 0
    plan.credits_rollover = False
    plan.quota_pools = [{"key": "assistant", "label": "Assistant messages", "limit": 2500}]
    plan.features = {"support_level": "email"}
    for column in account._LIMIT_COLUMNS:
        setattr(plan, column, None)
    plan.max_agents = 5
    for key, value in overrides.items():
        setattr(plan, key, value)
    return plan


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(account.router)
    app.dependency_overrides[get_async_db] = lambda: AsyncMock()
    return TestClient(app)


@pytest.fixture
def auth():
    """Stand-in for API key auth that records which permission each route asks for."""
    key = MagicMock(tenant_id=TENANT)
    seen: list[str] = []

    async def authenticate(_request, required_permission=None):
        seen.append(required_permission)
        return key

    with patch.object(
        AgentApiAuthMiddleware,
        "authenticate_request",
        authenticate,
    ):
        yield seen


class TestSerializePlan:
    def test_includes_price_pools_limits_and_features(self):
        info = account.serialize_plan(_plan())
        assert info.name == "Growth"
        assert info.tier == "STARTER"
        assert info.price_monthly == 299.0 and info.price_yearly == 2868.0
        assert info.quota_pools[0].model_dump() == {"key": "assistant", "label": "Assistant messages", "limit": 2500}
        assert info.limits["max_agents"] == 5
        assert info.limits["max_team_members"] is None  # null means unlimited
        assert info.features == {"support_level": "email"}

    def test_plan_without_pools_or_yearly_price(self):
        info = account.serialize_plan(_plan(quota_pools=None, price_yearly=None, features=None))
        assert info.quota_pools == []
        assert info.price_yearly is None
        assert info.features == {}


class TestEndpoints:
    def test_plan_requires_billing_read_and_uses_the_keys_tenant(self, client, auth):
        subscription = MagicMock(
            status="ACTIVE",
            billing_cycle="MONTHLY",
            current_period_start=START,
            current_period_end=END,
            trial_end=None,
            cancel_at_period_end=True,
            cancelled_at=None,
            auto_renew=True,
        )
        with patch.object(account, "PlanRestrictionService") as service:
            service.return_value.get_tenant_plan = AsyncMock(return_value=_plan())
            service.return_value.get_tenant_subscription = AsyncMock(return_value=subscription)
            response = client.get("/api/v1/public/account/plan")

        assert response.status_code == 200
        body = response.json()
        assert body["plan"]["name"] == "Growth"
        assert body["subscription"]["status"] == "ACTIVE"
        assert body["subscription"]["auto_renew"] is True
        assert body["subscription"]["cancel_at_period_end"] is True
        assert auth == ["billing:read"]
        service.return_value.get_tenant_plan.assert_awaited_once_with(TENANT)

    def test_plan_for_tenant_without_subscription(self, client, auth):
        with patch.object(account, "PlanRestrictionService") as service:
            service.return_value.get_tenant_plan = AsyncMock(return_value=_plan())
            service.return_value.get_tenant_subscription = AsyncMock(return_value=None)
            body = client.get("/api/v1/public/account/plan").json()
        assert body["subscription"] is None
        assert body["plan"] is not None

    def test_usage_for_a_plan_with_message_pools(self, client, auth):
        pool = PoolStatus("assistant", "Assistant messages", 2500, 900, START, END)
        stats = {"usage": {"agents": {"current": 2, "limit": 5, "unlimited": False}}}
        with (
            patch.object(account, "QuotaService") as quota,
            patch.object(account, "PlanRestrictionService") as restrictions,
        ):
            quota.return_value.list_pool_statuses = AsyncMock(return_value=[pool])
            restrictions.return_value.get_usage_stats = AsyncMock(return_value=stats)
            body = client.get("/api/v1/public/account/usage").json()

        assert auth == ["billing:read"]
        assert body["metering"] == "quota_pools"
        assert body["credits"] is None
        assert body["pools"][0]["used"] == 900 and body["pools"][0]["remaining"] == 1600
        assert body["period_end"].startswith("2026-12-01")
        assert body["resources"]["agents"] == {"current": 2, "limit": 5, "unlimited": False}
        quota.return_value.list_pool_statuses.assert_awaited_once_with(TENANT)

    def test_usage_for_a_plan_with_shared_credits(self, client, auth):
        balance = MagicMock(total_credits=3000, used_credits=120, available_credits=2880, last_reset_at=START)
        with (
            patch.object(account, "QuotaService") as quota,
            patch.object(account, "CreditService") as credit,
            patch.object(account, "PlanRestrictionService") as restrictions,
        ):
            quota.return_value.list_pool_statuses = AsyncMock(return_value=[])
            credit.return_value.get_balance = AsyncMock(return_value=balance)
            restrictions.return_value.get_usage_stats = AsyncMock(return_value={"usage": {}})
            body = client.get("/api/v1/public/account/usage").json()

        assert body["metering"] == "credits"
        assert body["pools"] == []
        assert body["credits"] == {
            "total": 3000,
            "used": 120,
            "available": 2880,
            "last_reset_at": body["credits"]["last_reset_at"],
        }

    def test_plans_lists_every_available_plan(self, client, auth):
        with patch.object(account, "SubscriptionService") as service:
            service.return_value.get_available_plans = AsyncMock(
                return_value=[_plan(name="Growth"), _plan(name="Scale", price_monthly=Decimal("990"))]
            )
            body = client.get("/api/v1/public/account/plans").json()
        assert [p["name"] for p in body] == ["Growth", "Scale"]
        assert body[1]["price_monthly"] == 990.0
        assert auth == ["billing:read"]

    def test_key_without_permission_is_rejected(self, client):
        async def deny(_request, required_permission=None):
            raise HTTPException(
                status_code=403, detail=f"API key does not have required permission: {required_permission}"
            )

        with patch.object(AgentApiAuthMiddleware, "authenticate_request", deny):
            for path in ("plan", "usage", "plans"):
                response = client.get(f"/api/v1/public/account/{path}")
                assert response.status_code == 403
                assert "billing:read" in response.json()["detail"]


class TestBillingReadPermission:
    @pytest.mark.parametrize(
        ("permissions", "allowed"),
        [
            (["chat"], False),
            (["agent:chat", "agent:read"], False),
            (["billing:read"], True),
            (["*"], False),  # scoped permissions must be listed explicitly
        ],
    )
    def test_only_an_explicit_billing_read_grants_access(self, permissions, allowed):
        key = MagicMock(permissions=permissions)
        assert AgentApiKeyService.check_permission(key, "billing:read") is allowed

    @pytest.mark.parametrize(
        ("permissions", "required", "allowed"),
        [
            # Scoped permissions never satisfy the plain verbs used by the conversation endpoints
            (["billing:read"], "read", False),
            (["knowledge:write"], "write", False),
            (["handoff:write"], "write", False),
            (["webhooks:manage"], "manage", False),
            (["tenants:manage"], "manage", False),
            # Their own exact permission still works
            (["knowledge:write"], "knowledge:write", True),
            (["billing:read"], "billing:read", True),
            # Legacy namespaced style is unchanged
            (["agent:chat"], "chat", True),
            (["agent:read"], "read", True),
            (["chat"], "chat", True),
            (["*"], "write", True),
            # Reproduces the escalation: "*" or a look-alike must never satisfy a scoped permission
            (["*"], "tenants:manage", False),
            (["foo:tenants:manage"], "tenants:manage", False),
            (["agent:tenants:manage"], "tenants:manage", False),
            (["*"], "webhooks:manage", False),
            (["*"], "knowledge:write", False),
            (["x:billing:read"], "read", False),
            (["a:b:read"], "read", False),
            (["tenants:manage"], "tenants:manage", True),
        ],
    )
    def test_scoped_permissions_do_not_grant_plain_verbs(self, permissions, required, allowed):
        assert AgentApiKeyService.check_permission(MagicMock(permissions=permissions), required) is allowed


class TestUsageHistory:
    def _rows(self, rows):
        result = MagicMock()
        result.all.return_value = rows
        return result

    async def test_groups_messages_by_day_pool_and_agent(self):
        agent = uuid4()
        db = AsyncMock()
        db.execute.return_value = self._rows(
            [
                (datetime(2026, 11, 3, tzinfo=UTC), "assistant", agent, 7),
                (datetime(2026, 11, 3, tzinfo=UTC), "operations", None, 2),
                (datetime(2026, 11, 4, tzinfo=UTC), "assistant", agent, 5),
            ]
        )
        history = await account.build_usage_history(db, TENANT, 30)

        assert history.total == 14
        assert [(p.date.isoformat(), p.pool_key, p.messages) for p in history.series] == [
            ("2026-11-03", "assistant", 7),
            ("2026-11-03", "operations", 2),
            ("2026-11-04", "assistant", 5),
        ]
        assert history.series[0].agent_id == str(agent) and history.series[1].agent_id is None
        assert (history.to_date - history.from_date).days == 29

    async def test_only_this_tenants_events_in_the_window_are_read(self):
        db = AsyncMock()
        db.execute.return_value = self._rows([])
        await account.build_usage_history(db, TENANT, 7)
        compiled = db.execute.call_args[0][0].compile()
        assert TENANT in compiled.params.values()
        assert "quota_usage_events" in str(compiled) and "created_at" in str(compiled)

    async def test_days_are_bucketed_in_utc_whatever_the_database_time_zone_is(self):
        """Reproduces daily buckets shifting when the database session is not in UTC."""
        db = AsyncMock()
        db.execute.return_value = self._rows([])
        await account.build_usage_history(db, TENANT, 7)
        sql = str(db.execute.call_args[0][0].compile(compile_kwargs={"literal_binds": True}))
        assert "timezone('UTC'" in sql and "date_trunc('day'" in sql

    def test_endpoint_returns_the_history_and_needs_billing_read(self, client, auth):
        empty = account.UsageHistoryResponse(from_date=START.date(), to_date=END.date(), total=0, series=[])
        with patch.object(account, "build_usage_history", AsyncMock(return_value=empty)) as build:
            response = client.get("/api/v1/public/account/usage/history?days=14")
        assert response.status_code == 200 and auth == ["billing:read"]
        build.assert_awaited_once()
        assert build.await_args.args[1:] == (TENANT, 14)

    @pytest.mark.parametrize("days", [0, 93, -1])
    def test_days_must_be_between_1_and_92(self, client, auth, days):
        assert client.get(f"/api/v1/public/account/usage/history?days={days}").status_code == 422


class TestRequestedPermissions:
    """The dashboard and key API can no longer create or edit a key into a tenant-management key."""

    @pytest.mark.parametrize(
        "permissions",
        [["tenants:manage"], ["x:tenants:manage"], ["tenants:read"], ["Tenants:Manage"], ["a:b:c"], ["chat\n"],
         ["with space"], [""], ["x" * 41], [f"p{i}" for i in range(21)]],
    )  # fmt: skip
    def test_operator_only_or_malformed_permissions_are_refused(self, permissions):
        from pydantic import ValidationError

        from src.schemas.agent_api import CreateApiKeyRequest, UpdateApiKeyRequest

        with pytest.raises(ValidationError):
            CreateApiKeyRequest(key_name="k", agent_id=uuid4(), permissions=permissions)
        with pytest.raises(ValidationError):
            UpdateApiKeyRequest(permissions=permissions)

    @pytest.mark.parametrize(
        "permissions",
        [["chat"], ["agent:chat", "agent:read"], ["*"], ["billing:read", "webhooks:manage"], ["handoff:write"],
         ["knowledge:read", "knowledge:write"], ["mcp_server", "a2a", "conversations"]],
    )  # fmt: skip
    def test_normal_permissions_are_accepted(self, permissions):
        from src.schemas.agent_api import CreateApiKeyRequest, UpdateApiKeyRequest

        assert CreateApiKeyRequest(key_name="k", agent_id=uuid4(), permissions=permissions).permissions == permissions
        assert UpdateApiKeyRequest(permissions=permissions).permissions == permissions
        assert UpdateApiKeyRequest().permissions is None


class TestSetSubscription:
    """A tenant billed in another system reports its plan with its own platform key."""

    def _put(self, client, tenant, key=None, body=None):
        key = key or MagicMock(tenant_id=TENANT, agent_id=None)

        async def authenticate(_request, required_permission=None):
            assert required_permission == "billing:manage"
            return key

        db = AsyncMock()
        db.get.return_value = tenant
        client.app.dependency_overrides[get_async_db] = lambda: db
        with (
            patch.object(AgentApiAuthMiddleware, "authenticate_request", authenticate),
            patch.object(account, "TenantProvisioningService") as service,
            patch.object(account, "build_plan_response", AsyncMock(return_value={"plan": None, "subscription": None})),
            patch.object(account, "audit_api_action") as audit,
        ):
            service.return_value.set_subscription = AsyncMock()
            response = client.put("/api/v1/public/account/subscription", json=body or {"plan": "Growth"})
        return response, service, audit

    def test_a_tenant_billed_elsewhere_can_set_its_plan(self, client):
        tenant = MagicMock(id=TENANT, external_billing=True)
        response, service, audit = self._put(client, tenant, body={"plan": "Growth", "billing_cycle": "MONTHLY"})
        assert response.status_code == 200
        kwargs = service.return_value.set_subscription.call_args.kwargs
        assert kwargs["plan"] == "Growth" and kwargs["billing_cycle"] == "MONTHLY"
        assert service.return_value.set_subscription.call_args.args == (tenant,)
        assert audit.call_args.args[2] == "account.subscription_changed"

    def test_a_tenant_billed_in_synkora_cannot_set_its_own_plan(self, client):
        response, service, _ = self._put(client, MagicMock(id=TENANT, external_billing=False))
        assert response.status_code == 403
        service.return_value.set_subscription.assert_not_called()

    def test_an_agent_key_cannot_set_the_plan(self, client):
        key = MagicMock(tenant_id=TENANT, agent_id=uuid4())
        response, service, _ = self._put(client, MagicMock(id=TENANT, external_billing=True), key=key)
        assert response.status_code == 403
        service.return_value.set_subscription.assert_not_called()

    def test_a_bad_request_is_reported_with_its_status(self, client):
        from src.services.tenant_provisioning_service import ProvisioningError

        tenant = MagicMock(id=TENANT, external_billing=True)
        key = MagicMock(tenant_id=TENANT, agent_id=None)

        async def authenticate(_request, required_permission=None):
            return key

        db = AsyncMock()
        db.get.return_value = tenant
        client.app.dependency_overrides[get_async_db] = lambda: db
        with (
            patch.object(AgentApiAuthMiddleware, "authenticate_request", authenticate),
            patch.object(account, "TenantProvisioningService") as service,
        ):
            service.return_value.set_subscription = AsyncMock(side_effect=ProvisioningError("Plan not found", 404))
            response = client.put("/api/v1/public/account/subscription", json={"plan": "Nope"})
        assert response.status_code == 404
        assert response.json()["detail"] == "Plan not found"
