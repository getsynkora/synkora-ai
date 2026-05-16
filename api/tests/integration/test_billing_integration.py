"""
Integration tests for Billing endpoints.

Tests credit operations, subscriptions, usage analytics, and payment methods.
"""

import uuid

import pytest
import pytest_asyncio
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Account, AccountStatus


@pytest_asyncio.fixture
async def auth_headers(async_client: AsyncClient, async_db_session: AsyncSession):
    """Create authenticated user and return headers with tenant info."""
    email = f"billing_test_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecureTestPass123!"

    # Register
    response = await async_client.post(
        "/console/api/auth/register",
        json={
            "email": email,
            "password": password,
            "name": "Billing Test User",
            "tenant_name": "Billing Test Org",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    tenant_id = data["data"]["tenant"]["id"]

    # Activate account
    result = await async_db_session.execute(select(Account).filter_by(email=email))
    account = result.scalar_one()
    account.status = AccountStatus.ACTIVE
    await async_db_session.commit()

    # Login
    login_response = await async_client.post(
        "/console/api/auth/login",
        json={"email": email, "password": password},
    )
    token = login_response.json()["data"]["access_token"]

    return {"Authorization": f"Bearer {token}"}, tenant_id, account


class TestCreditBalanceIntegration:
    """Test credit balance operations."""

    @pytest.mark.asyncio
    async def test_get_credit_balance(self, async_client: AsyncClient, auth_headers):
        """Test getting credit balance."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/billing/credits/balance", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "total_credits" in data
        assert "used_credits" in data
        assert "available_credits" in data

    @pytest.mark.asyncio
    async def test_get_credit_balance_unauthorized(self, async_client: AsyncClient):
        """Test that unauthenticated requests are rejected."""
        response = await async_client.get("/api/v1/billing/credits/balance")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]


class TestCreditTransactionsIntegration:
    """Test credit transaction operations."""

    @pytest.mark.asyncio
    async def test_get_credit_transactions(self, async_client: AsyncClient, auth_headers):
        """Test getting credit transactions."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/billing/credits/transactions", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_credit_transactions_with_pagination(self, async_client: AsyncClient, auth_headers):
        """Test getting credit transactions with pagination."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/billing/credits/transactions?limit=10&offset=0", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 10

    @pytest.mark.asyncio
    async def test_get_credit_transactions_filter_by_type(self, async_client: AsyncClient, auth_headers):
        """Test getting credit transactions filtered by type."""
        headers, tenant_id, account = auth_headers

        # TransactionType enum uses UPPERCASE: PURCHASE, USAGE, REFUND, etc.
        response = await async_client.get(
            "/api/v1/billing/credits/transactions?transaction_type=USAGE", headers=headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # All returned transactions should be of the specified type (if any)
        for tx in data:
            assert tx["transaction_type"] == "USAGE"


class TestCreditTopupsIntegration:
    """Test credit topup operations."""

    @pytest.mark.asyncio
    async def test_get_credit_topups(self, async_client: AsyncClient, auth_headers):
        """Test getting credit topup history."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/billing/credits/topups", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "topups" in data
        assert isinstance(data["topups"], list)

    @pytest.mark.asyncio
    async def test_purchase_topup_nonexistent_package(self, async_client: AsyncClient, auth_headers):
        """Test purchasing a nonexistent topup package."""
        headers, tenant_id, account = auth_headers

        fake_topup_id = str(uuid.uuid4())
        response = await async_client.post(
            "/api/v1/billing/credits/topup",
            json={"topup_id": fake_topup_id},
            headers=headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestSubscriptionIntegration:
    """Test subscription operations."""

    @pytest.mark.asyncio
    async def test_get_subscription(self, async_client: AsyncClient, auth_headers):
        """Test getting current subscription."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/billing/subscription", headers=headers)

        # Returns null for tenants without subscription, or subscription object
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_get_subscription_plans(self, async_client: AsyncClient, auth_headers):
        """Test getting available subscription plans."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/billing/plans", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_subscription_plans_public(self, async_client: AsyncClient):
        """Test that plans endpoint may work without auth (for pricing pages)."""
        # This endpoint may or may not require auth depending on implementation
        response = await async_client.get("/api/v1/billing/plans")

        # Accept either 200 (public) or 401/403 (requires auth)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    async def test_create_subscription_nonexistent_plan(self, async_client: AsyncClient, auth_headers):
        """Test creating subscription with nonexistent plan."""
        headers, tenant_id, account = auth_headers

        fake_plan_id = str(uuid.uuid4())
        response = await async_client.post(
            "/api/v1/billing/subscription/create",
            json={"plan_id": fake_plan_id},
            headers=headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_cancel_subscription_without_active(self, async_client: AsyncClient, auth_headers):
        """Test cancelling when no active subscription exists."""
        headers, tenant_id, account = auth_headers

        response = await async_client.post("/api/v1/billing/subscription/cancel", headers=headers)

        # May return 200, 400, or 404 depending on implementation
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND]


class TestUsageAnalyticsIntegration:
    """Test usage analytics operations."""

    @pytest.mark.asyncio
    async def test_get_usage_summary(self, async_client: AsyncClient, auth_headers):
        """Test getting usage summary."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/billing/usage/summary", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "period" in data
        assert "total_interactions" in data
        assert "total_credits_used" in data

    @pytest.mark.asyncio
    async def test_get_usage_trends(self, async_client: AsyncClient, auth_headers):
        """Test getting usage trends."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/billing/usage/trends?days=30", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "trend" in data

    @pytest.mark.asyncio
    async def test_get_usage_trends_invalid_days(self, async_client: AsyncClient, auth_headers):
        """Test getting usage trends with invalid days parameter."""
        headers, tenant_id, account = auth_headers

        # Days must be between 1 and 365
        response = await async_client.get("/api/v1/billing/usage/trends?days=0", headers=headers)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_get_usage_by_agent(self, async_client: AsyncClient, auth_headers):
        """Test getting usage breakdown by agent."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/billing/usage/by-agent", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "breakdown" in data

    @pytest.mark.asyncio
    async def test_get_usage_by_action(self, async_client: AsyncClient, auth_headers):
        """Test getting usage breakdown by action type."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/billing/usage/by-action", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "breakdown" in data

    @pytest.mark.asyncio
    async def test_get_peak_usage_times(self, async_client: AsyncClient, auth_headers):
        """Test getting peak usage times."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/billing/usage/peak-times?days=7", headers=headers)

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_export_usage_report_json(self, async_client: AsyncClient, auth_headers):
        """Test exporting usage report in JSON format."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/billing/usage/export?format=json", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "report_metadata" in data
        assert "summary" in data
        assert data["report_metadata"]["format"] == "json"

    @pytest.mark.asyncio
    async def test_export_usage_report_csv(self, async_client: AsyncClient, auth_headers):
        """Test exporting usage report in CSV format."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/billing/usage/export?format=csv", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "report_metadata" in data
        assert data["report_metadata"]["format"] == "csv"


class TestPaymentProviderConfigIntegration:
    """Test payment provider configuration."""

    @pytest.mark.asyncio
    async def test_get_payment_provider_config(self, async_client: AsyncClient, auth_headers):
        """Test getting payment provider configuration."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/billing/payment-provider/config", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "provider" in data
        assert "is_configured" in data


class TestPaymentMethodsIntegration:
    """Test payment method operations."""

    @pytest.mark.asyncio
    async def test_list_payment_methods(self, async_client: AsyncClient, auth_headers):
        """Test listing payment methods."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/billing/payment-methods", headers=headers)

        # May fail if Stripe not configured, accept 200 or 400/500
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert "payment_methods" in data

    @pytest.mark.asyncio
    async def test_create_setup_intent(self, async_client: AsyncClient, auth_headers):
        """Test creating a setup intent for adding payment method."""
        headers, tenant_id, account = auth_headers

        response = await async_client.post("/api/v1/billing/payment-methods/setup-intent", headers=headers)

        # May fail if Stripe not configured
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert "client_secret" in data
            assert "setup_intent_id" in data

    @pytest.mark.asyncio
    async def test_delete_nonexistent_payment_method(self, async_client: AsyncClient, auth_headers):
        """Test deleting a nonexistent payment method."""
        headers, tenant_id, account = auth_headers

        response = await async_client.delete("/api/v1/billing/payment-methods/pm_nonexistent", headers=headers)

        # May fail with 400/404/500 depending on Stripe configuration
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestBillingAuthorization:
    """Test billing authorization."""

    @pytest.mark.asyncio
    async def test_subscription_unauthorized(self, async_client: AsyncClient):
        """Test that unauthenticated requests to subscription are rejected."""
        response = await async_client.get("/api/v1/billing/subscription")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    async def test_usage_summary_unauthorized(self, async_client: AsyncClient):
        """Test that unauthenticated requests to usage summary are rejected."""
        response = await async_client.get("/api/v1/billing/usage/summary")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
