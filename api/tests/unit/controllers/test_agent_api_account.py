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
            (["*"], True),
        ],
    )
    def test_only_billing_read_or_wildcard_grants_access(self, permissions, allowed):
        key = MagicMock(permissions=permissions)
        assert AgentApiKeyService.check_permission(key, "billing:read") is allowed
