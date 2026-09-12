from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.subscription_plan import PlanTier, SubscriptionPlan
from src.services.billing.plan_restriction_service import PlanRestrictionError, PlanRestrictionService


class TestPlanRestrictionService:
    @pytest.fixture
    def mock_db(self):
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.scalar = AsyncMock()
        return session

    @pytest.fixture
    def service(self, mock_db):
        return PlanRestrictionService(mock_db)

    @pytest.fixture
    def mock_plan(self):
        plan = MagicMock(spec=SubscriptionPlan)
        plan.id = uuid4()
        plan.name = "Starter"
        plan.tier = PlanTier.STARTER
        # Column-based limits (the new approach)
        plan.max_agents = 5
        plan.max_team_members = 2
        plan.max_knowledge_bases = 1
        plan.max_mcp_servers = 1
        plan.max_custom_tools = 5
        plan.max_database_connections = 1
        plan.max_data_sources = 2
        plan.max_scheduled_tasks = 5
        plan.max_widgets = 1
        plan.max_slack_bots = 1
        plan.max_api_calls_per_month = 5000
        plan.credits_monthly = 1500
        plan.credits_rollover = False
        # Feature flags (boolean flags and overage settings)
        plan.features = {
            "advanced_analytics": True,
            "api_access": True,
            "webhooks": True,
            "overage_allowed": True,
            "overage_rate_per_credit": 0.02,
            "grace_period_days": 7,
        }
        return plan

    async def test_get_tenant_plan_active(self, service, mock_db, mock_plan):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_plan
        mock_db.execute.return_value = mock_result

        result = await service.get_tenant_plan(uuid4())
        assert result == mock_plan
        # Should call execute once (found active subscription)
        mock_db.execute.assert_called_once()

    async def test_get_tenant_plan_fallback_free(self, service, mock_db, mock_plan):
        tenant_id = uuid4()
        free_plan = MagicMock(spec=SubscriptionPlan)
        free_plan.tier = PlanTier.FREE

        # First call returns None (no active sub), second call returns Free plan
        mock_active_result = MagicMock()
        mock_active_result.scalar_one_or_none.return_value = None

        mock_free_result = MagicMock()
        mock_free_result.scalar_one_or_none.return_value = free_plan

        mock_db.execute.side_effect = [mock_active_result, mock_free_result]

        result = await service.get_tenant_plan(tenant_id)
        assert result == free_plan
        assert mock_db.execute.call_count == 2

    async def test_get_plan_features(self, service, mock_plan):
        with patch.object(service, "get_tenant_plan", new_callable=AsyncMock) as mock_get_plan:
            mock_get_plan.return_value = mock_plan
            features = await service.get_plan_features(uuid4())

            assert features["max_agents"] == 5
            assert features["max_team_members"] == 2
            assert features["max_knowledge_bases"] == 1
            assert features["features"]["advanced_analytics"] is True

    async def test_get_plan_features_no_plan(self, service):
        with patch.object(service, "get_tenant_plan", new_callable=AsyncMock) as mock_get_plan:
            mock_get_plan.return_value = None
            features = await service.get_plan_features(uuid4())
            assert features["max_agents"] == 0

    async def test_check_agent_limit_under(self, service, mock_db, mock_plan):
        with patch.object(service, "get_tenant_plan", new_callable=AsyncMock) as mock_get_plan:
            mock_get_plan.return_value = mock_plan
            # Mock current count
            mock_result = MagicMock()
            mock_result.scalar.return_value = 3
            mock_db.execute.return_value = mock_result

            result = await service.check_agent_limit(uuid4())
            assert result is True

    async def test_check_agent_limit_over(self, service, mock_db, mock_plan):
        with patch.object(service, "get_tenant_plan", new_callable=AsyncMock) as mock_get_plan:
            mock_get_plan.return_value = mock_plan
            mock_result = MagicMock()
            mock_result.scalar.return_value = 5
            mock_db.execute.return_value = mock_result

            result = await service.check_agent_limit(uuid4())
            assert result is False  # 5 < 5 is False

    async def test_check_agent_limit_unlimited(self, service, mock_db, mock_plan):
        mock_plan.max_agents = None
        with patch.object(service, "get_tenant_plan", new_callable=AsyncMock) as mock_get_plan:
            mock_get_plan.return_value = mock_plan
            result = await service.check_agent_limit(uuid4())
            assert result is True
            mock_db.execute.assert_not_called()

    async def test_enforce_agent_limit_success(self, service):
        with patch.object(service, "check_agent_limit", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = True
            await service.enforce_agent_limit(uuid4())

    async def test_enforce_agent_limit_failure(self, service, mock_plan):
        with (
            patch.object(service, "check_agent_limit", new_callable=AsyncMock) as mock_check,
            patch.object(service, "get_tenant_plan", new_callable=AsyncMock) as mock_get_plan,
        ):
            mock_check.return_value = False
            mock_get_plan.return_value = mock_plan
            with pytest.raises(PlanRestrictionError, match="Agent limit reached"):
                await service.enforce_agent_limit(uuid4())

    async def test_check_knowledge_base_limit(self, service, mock_db, mock_plan):
        with patch.object(service, "get_tenant_plan", new_callable=AsyncMock) as mock_get_plan:
            mock_get_plan.return_value = mock_plan
            mock_result = MagicMock()
            mock_result.scalar.return_value = 0
            mock_db.execute.return_value = mock_result

            result = await service.check_knowledge_base_limit(uuid4())
            assert result is True  # 0 < 1

    async def test_check_knowledge_base_limit_unlimited(self, service, mock_db, mock_plan):
        mock_plan.max_knowledge_bases = None  # Column-based limit
        with patch.object(service, "get_tenant_plan", new_callable=AsyncMock) as mock_get_plan:
            mock_get_plan.return_value = mock_plan
            result = await service.check_knowledge_base_limit(uuid4())
            assert result is True

    async def test_check_feature_access(self, service, mock_plan):
        with patch.object(service, "get_tenant_plan", new_callable=AsyncMock) as mock_get_plan:
            mock_get_plan.return_value = mock_plan
            result_analytics = await service.check_feature_access(uuid4(), "advanced_analytics")
            result_unknown = await service.check_feature_access(uuid4(), "unknown_feature")
            assert result_analytics is True
            assert result_unknown is False

    async def test_enforce_feature_access_failure(self, service):
        with patch.object(service, "check_feature_access", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = False
            with pytest.raises(PlanRestrictionError, match="Advanced Analytics is not available"):
                await service.enforce_feature_access(uuid4(), "advanced_analytics")

    async def test_get_usage_stats(self, service, mock_db, mock_plan):
        with (
            patch.object(service, "get_tenant_plan", new_callable=AsyncMock) as mock_get_plan,
            patch.object(service, "get_plan_features", new_callable=AsyncMock) as mock_get_features,
        ):
            mock_get_plan.return_value = mock_plan
            mock_get_features.return_value = {
                "overage_allowed": True,
                "overage_rate_per_credit": 0.02,
                "grace_period_days": 7,
                "features": {"advanced_analytics": True},
            }

            # get_usage_stats runs a single query with one scalar subquery per
            # resource, returning one row with a labeled column per resource.
            mock_row = MagicMock()
            mock_row.agents = 1
            mock_row.team_members = 1
            mock_row.knowledge_bases = 1
            mock_row.mcp_servers = 1
            mock_row.custom_tools = 1
            mock_row.database_connections = 1
            mock_row.data_sources = 1
            mock_row.scheduled_tasks = 1
            mock_row.widgets = 1
            mock_row.slack_bots = 1
            mock_result = MagicMock()
            mock_result.one.return_value = mock_row
            mock_db.execute.return_value = mock_result

            stats = await service.get_usage_stats(uuid4())

            assert stats["plan_name"] == "Starter"
            assert stats["plan_tier"] == "STARTER"
            assert stats["credits_monthly"] == 1500
            assert stats["credits_rollover"] is False
            assert stats["overage_allowed"] is True
            assert stats["usage"]["agents"]["current"] == 1
            assert stats["usage"]["agents"]["limit"] == 5
            assert stats["usage"]["knowledge_bases"]["limit"] == 1
            assert stats["usage"]["api_calls_per_month"]["limit"] == 5000
