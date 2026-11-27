"""Tests for billing controller."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from src.controllers.billing import router
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id


@pytest.fixture
def mock_credit_service():
    with patch("src.controllers.billing.CreditService") as mock:
        mock.return_value = AsyncMock()
        yield mock


@pytest.fixture
def mock_subscription_service():
    with patch("src.controllers.billing.SubscriptionService") as mock:
        mock.return_value = AsyncMock()
        yield mock


@pytest.fixture
def mock_usage_service():
    with patch("src.controllers.billing.UsageTrackingService") as mock:
        mock.return_value = AsyncMock()
        yield mock


@pytest.fixture
def mock_stripe_service():
    with patch("src.controllers.billing.StripeService") as mock:
        mock_instance = AsyncMock()  # All StripeService methods are async
        mock.create = AsyncMock(return_value=mock_instance)  # factory method is async
        mock.return_value = mock_instance  # for backwards compatibility
        yield mock


@pytest.fixture
def mock_db_session():
    mock_db = AsyncMock()
    mock_db.add = MagicMock()  # add is synchronous
    return mock_db


@pytest.fixture
def client(mock_credit_service, mock_subscription_service, mock_usage_service, mock_stripe_service, mock_db_session):
    app = FastAPI()
    app.include_router(router)

    # Mock dependencies
    async def mock_db():
        yield mock_db_session

    app.dependency_overrides[get_async_db] = mock_db

    # Mock tenant ID
    tenant_id = uuid.uuid4()
    app.dependency_overrides[get_current_tenant_id] = lambda: tenant_id

    return (
        TestClient(app),
        tenant_id,
        {
            "credit": mock_credit_service,
            "subscription": mock_subscription_service,
            "usage": mock_usage_service,
            "stripe": mock_stripe_service,
        },
        mock_db_session,
    )


class TestCreditBalanceEndpoints:
    """Tests for credit balance endpoints."""

    def test_get_credit_balance_success(self, client):
        """Test getting credit balance successfully."""
        test_client, tenant_id, mocks, _ = client
        mock_credit = mocks["credit"].return_value

        # Mock balance
        mock_balance = MagicMock()
        mock_balance.tenant_id = tenant_id
        mock_balance.total_credits = 1000
        mock_balance.used_credits = 200
        mock_balance.available_credits = 800
        mock_balance.last_reset_at = datetime.now(UTC)

        mock_credit.get_balance.return_value = mock_balance

        response = test_client.get("/api/v1/billing/credits/balance")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_credits"] == 1000
        assert data["used_credits"] == 200
        assert data["available_credits"] == 800

    def test_get_credit_balance_new_tenant(self, client):
        """Test getting credit balance for new tenant without balance."""
        test_client, tenant_id, mocks, _ = client
        mock_credit = mocks["credit"].return_value

        mock_credit.get_balance.return_value = None

        response = test_client.get("/api/v1/billing/credits/balance")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_credits"] == 0
        assert data["used_credits"] == 0
        assert data["available_credits"] == 0

    def test_get_credit_transactions(self, client):
        """Test getting credit transaction history."""
        test_client, tenant_id, mocks, _ = client
        mock_credit = mocks["credit"].return_value

        # Mock transactions
        mock_transaction = MagicMock()
        mock_transaction.id = uuid.uuid4()
        mock_transaction.tenant_id = tenant_id
        mock_transaction.transaction_type = "usage"
        mock_transaction.amount = -10
        mock_transaction.balance_after = 990
        mock_transaction.reference_type = "chat"
        mock_transaction.description = "Agent chat interaction"
        mock_transaction.created_at = datetime.now(UTC)

        mock_credit.get_transaction_history.return_value = [mock_transaction]

        response = test_client.get("/api/v1/billing/credits/transactions")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["transaction_type"] == "usage"
        assert data[0]["credits_amount"] == -10


class TestSubscriptionEndpoints:
    """Tests for subscription endpoints."""

    def test_get_active_subscription(self, client):
        """Test getting active subscription."""
        test_client, tenant_id, mocks, _ = client
        mock_subscription = mocks["subscription"].return_value

        # Mock subscription
        mock_sub = MagicMock()
        mock_sub.id = uuid.uuid4()
        mock_sub.plan_id = uuid.uuid4()
        mock_sub.plan.name = "Pro Plan"
        mock_sub.status = "active"
        mock_sub.current_period_start = datetime.now(UTC)
        mock_sub.current_period_end = datetime.now(UTC)
        mock_sub.cancelled_at = None

        mock_subscription.get_subscription_by_tenant = AsyncMock(return_value=mock_sub)

        response = test_client.get("/api/v1/billing/subscription")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["plan_name"] == "Pro Plan"
        assert data["status"] == "active"

    def test_get_subscription_none(self, client):
        """Test getting subscription when none exists."""
        test_client, tenant_id, mocks, _ = client
        mock_subscription = mocks["subscription"].return_value

        mock_subscription.get_subscription_by_tenant = AsyncMock(return_value=None)

        response = test_client.get("/api/v1/billing/subscription")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() is None

    def test_get_subscription_plans(self, client):
        """Test getting available subscription plans."""
        test_client, tenant_id, mocks, _ = client
        mock_subscription = mocks["subscription"].return_value

        # Mock plans
        mock_plan = MagicMock()
        mock_plan.id = uuid.uuid4()
        mock_plan.name = "Pro Plan"
        mock_plan.description = "Professional tier"
        mock_plan.price_monthly = 29.99
        mock_plan.price_yearly = 299.99
        mock_plan.credits_monthly = 5000
        mock_plan.max_agents = 10
        mock_plan.max_team_members = 5
        mock_plan.features = {"advanced_analytics": True}
        mock_plan.is_active = True

        mock_subscription.get_available_plans = AsyncMock(return_value=[mock_plan])

        with patch("src.controllers.billing.get_redis_async", return_value=None):
            response = test_client.get("/api/v1/billing/plans")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Pro Plan"
        assert data[0]["price_monthly"] == 29.99
        mock_subscription.get_available_plans.assert_awaited_once_with(public_only=True)

    def test_cancel_subscription(self, client):
        """Test cancelling subscription."""
        test_client, tenant_id, mocks, _ = client
        mock_subscription = mocks["subscription"].return_value

        mock_sub = MagicMock()
        mock_sub.id = uuid.uuid4()

        mock_subscription.get_tenant_subscription.return_value = mock_sub
        mock_subscription.cancel_subscription.return_value = mock_sub

        response = test_client.post("/api/v1/billing/subscription/cancel")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "cancelled"

    def test_cancel_subscription_not_found(self, client):
        """Test cancelling subscription when none exists."""
        test_client, tenant_id, mocks, _ = client
        mock_subscription = mocks["subscription"].return_value

        mock_subscription.get_tenant_subscription.return_value = None

        response = test_client.post("/api/v1/billing/subscription/cancel")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestUsageEndpoints:
    """Tests for usage analytics endpoints."""

    def test_get_usage_summary(self, client):
        """Test getting usage summary."""
        test_client, tenant_id, mocks, _ = client
        mock_usage = mocks["usage"].return_value

        mock_summary = {
            "period": {"start": "2024-01-01", "end": "2024-01-31"},
            "total_interactions": 150,
            "total_credits_used": 300,
            "breakdown": {"chat": 100, "api": 50},
        }

        mock_usage.get_usage_summary = AsyncMock(return_value=mock_summary)

        response = test_client.get("/api/v1/billing/usage/summary")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_interactions"] == 150
        assert data["total_credits_used"] == 300

    def test_get_usage_trends(self, client):
        """Test getting usage trends."""
        test_client, tenant_id, mocks, _ = client
        mock_usage = mocks["usage"].return_value

        mock_trend = [
            {"date": "2024-01-01", "interactions": 10, "credits": 20},
            {"date": "2024-01-02", "interactions": 15, "credits": 30},
        ]

        mock_usage.get_daily_usage_trend = AsyncMock(return_value=mock_trend)

        response = test_client.get("/api/v1/billing/usage/trends?days=30")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "trend" in data
        assert len(data["trend"]) == 2

    def test_get_usage_by_agent(self, client):
        """Test getting usage breakdown by agent."""
        test_client, tenant_id, mocks, _ = client
        mock_usage = mocks["usage"].return_value

        mock_breakdown = [
            {"agent_id": str(uuid.uuid4()), "agent_name": "Support Bot", "interactions": 100},
            {"agent_id": str(uuid.uuid4()), "agent_name": "Sales Bot", "interactions": 50},
        ]

        mock_usage.get_agent_usage_breakdown = AsyncMock(return_value=mock_breakdown)

        response = test_client.get("/api/v1/billing/usage/by-agent")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "breakdown" in data

    def test_get_peak_usage_times(self, client):
        """Test getting peak usage times."""
        test_client, tenant_id, mocks, _ = client
        mock_usage = mocks["usage"].return_value

        mock_peak_times = {
            "peak_hour": 14,
            "peak_day": "Monday",
            "hourly_distribution": {str(i): i * 10 for i in range(24)},
        }

        mock_usage.get_peak_usage_times = AsyncMock(return_value=mock_peak_times)

        response = test_client.get("/api/v1/billing/usage/peak-times")

        assert response.status_code == status.HTTP_200_OK


class TestPaymentMethodEndpoints:
    """Tests for payment method management endpoints."""

    def test_list_payment_methods(self, client):
        """Test listing payment methods."""
        test_client, tenant_id, mocks, mock_db = client
        mock_stripe = mocks["stripe"].return_value

        mock_payment_methods = [{"id": "pm_123", "card": {"brand": "visa", "last4": "4242"}, "is_default": True}]

        mock_stripe.list_payment_methods = AsyncMock(return_value=mock_payment_methods)

        # Mock tenant with stripe customer ID
        mock_tenant = MagicMock()
        mock_tenant.metadata = {"stripe_customer_id": "cus_123"}
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_tenant
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = test_client.get("/api/v1/billing/payment-methods")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "payment_methods" in data

    def test_create_setup_intent(self, client):
        """Test creating setup intent for payment method."""
        test_client, tenant_id, mocks, mock_db = client
        mock_stripe = mocks["stripe"].return_value

        mock_setup_intent = {"client_secret": "seti_xxx_secret_xxx", "setup_intent_id": "seti_xxx"}

        mock_stripe.get_or_create_customer = AsyncMock(return_value="cus_123")
        mock_stripe.create_setup_intent = AsyncMock(return_value=mock_setup_intent)

        # Mock tenant
        mock_tenant = MagicMock()
        mock_tenant.id = tenant_id
        mock_tenant.email = "test@example.com"
        mock_tenant.name = "Test Tenant"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_tenant
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = test_client.post("/api/v1/billing/payment-methods/setup-intent")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "client_secret" in data

    def test_delete_payment_method(self, client):
        """Test deleting a payment method."""
        test_client, tenant_id, mocks, mock_db = client
        mock_stripe = mocks["stripe"].return_value

        mock_stripe.detach_payment_method = AsyncMock(return_value=True)

        response = test_client.delete("/api/v1/billing/payment-methods/pm_123")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
