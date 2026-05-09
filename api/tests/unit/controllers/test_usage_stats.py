"""Tests for usage stats controller."""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from src.controllers.usage_stats import router
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id


@pytest.fixture
def mock_db_session():
    return AsyncMock()


@pytest.fixture
def mock_account():
    account = MagicMock()
    account.id = uuid.uuid4()
    account.email = "test@example.com"
    return account


@pytest.fixture
def client(mock_db_session, mock_account):
    app = FastAPI()
    app.include_router(router)

    tenant_id = uuid.uuid4()

    async def mock_db():
        yield mock_db_session

    app.dependency_overrides[get_async_db] = mock_db
    app.dependency_overrides[get_current_tenant_id] = lambda: tenant_id
    app.dependency_overrides[get_current_account] = lambda: mock_account

    return TestClient(app), tenant_id, mock_account, mock_db_session


class TestGetUsageStats:
    """Tests for getting usage statistics."""

    def test_get_usage_stats_success(self, client):
        """Test successfully getting usage stats."""
        test_client, tenant_id, mock_account, mock_db = client

        with (
            patch("src.controllers.usage_stats.PlanRestrictionService") as mock_plan_service,
            patch("src.controllers.usage_stats.CreditService") as mock_credit_service,
        ):
            # Mock plan
            mock_plan = MagicMock()
            mock_plan.name = "Pro Plan"
            mock_plan.tier = "pro"
            mock_plan.max_agents = 10
            mock_plan.max_team_members = 5
            mock_plan.max_api_calls_per_month = 10000
            mock_plan.max_knowledge_bases = 5
            mock_plan.max_data_sources = 10
            mock_plan.max_custom_tools = 20
            mock_plan.max_database_connections = 5
            mock_plan.max_mcp_servers = 3
            mock_plan.max_scheduled_tasks = 10
            mock_plan.max_widgets = 5
            mock_plan.max_slack_bots = 2
            mock_plan.features = {"feature1": True}

            mock_plan_instance = mock_plan_service.return_value
            mock_plan_instance.get_usage_stats = AsyncMock(
                return_value={
                    "plan_name": "Pro Plan",
                    "plan_tier": "pro",
                    "usage": {
                        "agents": {"current": 3, "limit": 10},
                        "team_members": {"current": 2, "limit": 5},
                    },
                }
            )
            mock_plan_instance.get_tenant_plan = AsyncMock(return_value=mock_plan)

            mock_credit_instance = mock_credit_service.return_value
            mock_credit_instance.get_balance = AsyncMock(return_value=Decimal("100.50"))

            response = test_client.get("/usage-stats")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["plan_name"] == "Pro Plan"
        assert data["plan_tier"] == "pro"
        assert data["current_usage"]["agents"] == 3
        assert data["current_usage"]["team_members"] == 2
        assert data["current_usage"]["api_calls_this_month"] == 0
        assert data["limits"]["max_agents"] == 10
        assert float(data["credit_balance"]) == 100.50

    def test_get_usage_stats_zero_limits(self, client):
        """Test usage stats with zero limits (unlimited plan)."""
        test_client, tenant_id, mock_account, mock_db = client

        with (
            patch("src.controllers.usage_stats.PlanRestrictionService") as mock_plan_service,
            patch("src.controllers.usage_stats.CreditService") as mock_credit_service,
        ):
            mock_plan = MagicMock()
            mock_plan.name = "Enterprise"
            mock_plan.tier = "enterprise"
            mock_plan.max_agents = 0  # Unlimited
            mock_plan.max_team_members = 0
            mock_plan.max_api_calls_per_month = 0
            mock_plan.max_knowledge_bases = 0
            mock_plan.max_data_sources = 0
            mock_plan.max_custom_tools = 0
            mock_plan.max_database_connections = 0
            mock_plan.max_mcp_servers = 0
            mock_plan.max_scheduled_tasks = 0
            mock_plan.max_widgets = 0
            mock_plan.max_slack_bots = 0
            mock_plan.features = {}

            mock_plan_instance = mock_plan_service.return_value
            mock_plan_instance.get_usage_stats = AsyncMock(
                return_value={
                    "plan_name": "Enterprise",
                    "plan_tier": "enterprise",
                    "usage": {
                        "agents": {"current": 100, "limit": 0},
                        "team_members": {"current": 50, "limit": 0},
                    },
                }
            )
            mock_plan_instance.get_tenant_plan = AsyncMock(return_value=mock_plan)

            mock_credit_instance = mock_credit_service.return_value
            mock_credit_instance.get_balance = AsyncMock(return_value=None)

            response = test_client.get("/usage-stats")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Zero limits should result in 0% usage
        assert data["usage_percentage"]["agents"] == 0
        assert data["usage_percentage"]["team_members"] == 0
        assert data["usage_percentage"]["api_calls"] == 0

    def test_get_usage_stats_error(self, client):
        """Test error handling when getting usage stats."""
        test_client, tenant_id, mock_account, mock_db = client

        with patch("src.controllers.usage_stats.PlanRestrictionService") as mock_plan_service:
            mock_plan_instance = mock_plan_service.return_value
            mock_plan_instance.get_usage_stats = AsyncMock(side_effect=Exception("Database error"))

            response = test_client.get("/usage-stats")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
