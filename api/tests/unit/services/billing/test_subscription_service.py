from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.subscription_plan import PlanTier, SubscriptionPlan
from src.models.tenant_subscription import SubscriptionStatus, TenantSubscription
from src.services.billing.subscription_service import UNCAPPED_ROLLOVER, SubscriptionService


class TestSubscriptionService:
    @pytest.fixture
    def mock_db(self):
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.fixture
    def service(self, mock_db):
        return SubscriptionService(mock_db)

    @pytest.fixture
    def mock_plan(self):
        plan = MagicMock(spec=SubscriptionPlan)
        plan.id = uuid4()
        plan.name = "Pro Plan"
        plan.tier = PlanTier.PROFESSIONAL  # Use PROFESSIONAL instead of PRO
        plan.price_monthly = 29.0
        plan.credits_monthly = 1000
        plan.is_active = True
        return plan

    @pytest.fixture
    def mock_subscription(self, mock_plan):
        sub = MagicMock(spec=TenantSubscription)
        sub.id = uuid4()
        sub.tenant_id = uuid4()
        sub.plan_id = mock_plan.id
        sub.status = SubscriptionStatus.ACTIVE
        sub.cancel_at_period_end = False
        sub.current_period_start = datetime.now(UTC)
        sub.current_period_end = datetime.now(UTC) + timedelta(days=30)
        return sub

    async def test_get_plan(self, service, mock_db, mock_plan):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_plan
        mock_db.execute.return_value = mock_result

        result = await service.get_plan(mock_plan.id)
        assert result == mock_plan
        mock_db.execute.assert_called_once()

    async def test_get_plan_by_tier(self, service, mock_db, mock_plan):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_plan
        mock_db.execute.return_value = mock_result

        result = await service.get_plan_by_tier(PlanTier.PROFESSIONAL)
        assert result == mock_plan
        mock_db.execute.assert_called_once()

    async def test_list_active_plans(self, service, mock_db):
        mock_plans = [MagicMock(spec=SubscriptionPlan), MagicMock(spec=SubscriptionPlan)]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_plans
        mock_db.execute.return_value = mock_result

        result = await service.list_active_plans()
        assert len(result) == 2
        mock_db.execute.assert_called_once()

    async def test_list_active_plans_for_the_pricing_page_leaves_out_hidden_plans(self, service, mock_db):
        mock_db.execute.return_value = MagicMock()

        def where_clause():
            return str(mock_db.execute.call_args[0][0]).split("WHERE", 1)[1]

        await service.list_active_plans(public_only=True)
        assert "subscription_plans.is_public" in where_clause()

        await service.list_active_plans()
        assert "subscription_plans.is_public" not in where_clause()

    async def test_get_tenant_subscription(self, service, mock_db, mock_subscription):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_subscription
        mock_db.execute.return_value = mock_result

        result = await service.get_tenant_subscription(mock_subscription.tenant_id)
        assert result == mock_subscription
        mock_db.execute.assert_called_once()

    async def test_create_subscription_success(self, service, mock_db, mock_plan):
        tenant_id = uuid4()

        with (
            patch.object(service, "get_plan", AsyncMock(return_value=mock_plan)),
            patch.object(service, "get_tenant_subscription", AsyncMock(return_value=None)),
        ):
            # Mock the credit service
            service.credit_service = AsyncMock()
            service.credit_service.add_credits = AsyncMock()

            sub = await service.create_subscription(tenant_id, mock_plan.id)

            assert sub.tenant_id == tenant_id
            assert sub.plan_id == mock_plan.id
            assert sub.status == SubscriptionStatus.ACTIVE

            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            service.credit_service.add_credits.assert_called_once()

    async def test_create_subscription_cancel_existing(self, service, mock_db, mock_plan, mock_subscription):
        tenant_id = uuid4()

        with (
            patch.object(service, "get_plan", AsyncMock(return_value=mock_plan)),
            patch.object(service, "get_tenant_subscription", AsyncMock(return_value=mock_subscription)),
        ):
            # Mock the credit service
            service.credit_service = AsyncMock()
            service.credit_service.add_credits = AsyncMock()

            await service.create_subscription(tenant_id, mock_plan.id)

            assert mock_subscription.status == SubscriptionStatus.CANCELLED
            assert mock_subscription.cancelled_at is not None

    async def test_create_subscription_plan_not_found(self, service, mock_db):
        with patch.object(service, "get_plan", AsyncMock(return_value=None)):
            with pytest.raises(ValueError, match="Plan .* not found"):
                await service.create_subscription(uuid4(), uuid4())

    async def test_renew_subscription_success(self, service, mock_db, mock_plan, mock_subscription):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_subscription
        mock_db.execute.return_value = mock_result

        with patch.object(service, "get_plan", AsyncMock(return_value=mock_plan)):
            # Mock credit service
            service.credit_service = AsyncMock()
            service.credit_service.apply_monthly_rollover = AsyncMock()
            service.credit_service.add_credits = AsyncMock()
            mock_plan.credits_rollover = True
            mock_plan.features = {"max_rollover_credits": 30000}

            renewed_sub = await service.renew_subscription(mock_subscription.id)

            assert renewed_sub.current_period_end > datetime.now(UTC) + timedelta(days=29)
            # Old balance is reduced to what may roll over, then exactly one month's grant is added
            service.credit_service.apply_monthly_rollover.assert_called_once_with(
                tenant_id=mock_subscription.tenant_id,
                new_credits=0,
                max_rollover=30000,
                credits_rollover=True,
            )
            service.credit_service.add_credits.assert_called_once()
            mock_db.commit.assert_called_once()

    async def test_renew_subscription_without_rollover_expires_unused_credits(
        self, service, mock_db, mock_plan, mock_subscription
    ):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_subscription
        mock_db.execute.return_value = mock_result

        with patch.object(service, "get_plan", AsyncMock(return_value=mock_plan)):
            service.credit_service = AsyncMock()
            mock_plan.credits_rollover = False
            mock_plan.features = {"max_rollover_credits": 30000}

            await service.renew_subscription(mock_subscription.id)

            kwargs = service.credit_service.apply_monthly_rollover.call_args.kwargs
            assert kwargs["credits_rollover"] is False

    async def test_renew_subscription_skips_credit_grant_for_quota_pool_plans(
        self, service, mock_db, mock_plan, mock_subscription
    ):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_subscription
        mock_db.execute.return_value = mock_result

        with patch.object(service, "get_plan", AsyncMock(return_value=mock_plan)):
            service.credit_service = AsyncMock()
            mock_plan.credits_monthly = 0
            mock_plan.credits_rollover = False
            mock_plan.features = None

            await service.renew_subscription(mock_subscription.id)

            service.credit_service.add_credits.assert_not_called()

    async def test_rollover_plan_without_a_configured_cap_keeps_its_credits(
        self, service, mock_db, mock_plan, mock_subscription
    ):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_subscription
        mock_db.execute.return_value = mock_result

        with patch.object(service, "get_plan", AsyncMock(return_value=mock_plan)):
            service.credit_service = AsyncMock()
            mock_plan.credits_rollover = True
            mock_plan.features = {}

            await service.renew_subscription(mock_subscription.id)

        kwargs = service.credit_service.apply_monthly_rollover.call_args.kwargs
        assert kwargs["max_rollover"] == UNCAPPED_ROLLOVER
        assert kwargs["credits_rollover"] is True

    async def test_an_explicit_cap_of_zero_keeps_nothing(self, service, mock_db, mock_plan, mock_subscription):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_subscription
        mock_db.execute.return_value = mock_result

        with patch.object(service, "get_plan", AsyncMock(return_value=mock_plan)):
            service.credit_service = AsyncMock()
            mock_plan.credits_rollover = True
            mock_plan.features = {"max_rollover_credits": 0}

            await service.renew_subscription(mock_subscription.id)

        assert service.credit_service.apply_monthly_rollover.call_args.kwargs["max_rollover"] == 0

    async def test_renew_subscription_ends_it_when_cancel_at_period_end_is_set(
        self, service, mock_db, mock_plan, mock_subscription
    ):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_subscription
        mock_db.execute.return_value = mock_result
        mock_subscription.cancel_at_period_end = True

        with patch.object(service, "get_plan", AsyncMock(return_value=mock_plan)):
            service.credit_service = AsyncMock()

            result = await service.renew_subscription(mock_subscription.id)

        assert result.status == SubscriptionStatus.CANCELLED
        assert result.cancelled_at is not None
        # No new period and no new credits for a subscription the tenant asked to end
        service.credit_service.apply_monthly_rollover.assert_not_called()
        service.credit_service.add_credits.assert_not_called()

    async def test_renew_subscription_not_found(self, service, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(ValueError, match="Subscription .* not found"):
            await service.renew_subscription(uuid4())

    async def test_cancel_subscription_immediate(self, service, mock_db, mock_subscription):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_subscription
        mock_db.execute.return_value = mock_result

        await service.cancel_subscription(mock_subscription.id, immediate=True)

        assert mock_subscription.status == SubscriptionStatus.CANCELLED
        assert mock_subscription.cancelled_at is not None
        mock_db.commit.assert_called_once()

    async def test_cancel_subscription_period_end(self, service, mock_db, mock_subscription):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_subscription
        mock_db.execute.return_value = mock_result

        await service.cancel_subscription(mock_subscription.id, immediate=False)

        assert mock_subscription.cancel_at_period_end is True
        mock_db.commit.assert_called_once()

    async def test_upgrade_subscription_success(self, service, mock_db, mock_subscription, mock_plan):
        new_plan_id = uuid4()
        new_plan = MagicMock(spec=SubscriptionPlan)
        new_plan.id = new_plan_id
        new_plan.name = "Enterprise"
        new_plan.credits_monthly = 2000

        with (
            patch.object(service, "get_tenant_subscription", AsyncMock(return_value=mock_subscription)),
            patch.object(service, "get_plan", AsyncMock(side_effect=[new_plan, mock_plan])),
        ):  # Calls get_plan(new), then get_plan(old)
            service.credit_service = AsyncMock()
            service.credit_service.add_credits = AsyncMock()

            updated_sub = await service.upgrade_subscription(mock_subscription.tenant_id, new_plan_id)

            assert updated_sub.plan_id == new_plan_id
            service.credit_service.add_credits.assert_called_once()  # Prorated credits
            mock_db.commit.assert_called_once()

    async def test_a_downgrade_takes_back_the_prorated_credits(self, service, mock_db, mock_subscription, mock_plan):
        """Reproduces switching plans back and forth minting credits: upgrades added, downgrades never removed."""
        low = MagicMock(spec=SubscriptionPlan, id=uuid4(), credits_monthly=1000)
        low.name = "Low"
        high = MagicMock(spec=SubscriptionPlan, id=uuid4(), credits_monthly=30000)
        mock_subscription.current_period_end = datetime.now(UTC) + timedelta(days=29, hours=12)
        service.credit_service = AsyncMock()
        service.credit_service.get_balance = AsyncMock(return_value=MagicMock(available_credits=50_000))
        with (
            patch.object(service, "get_tenant_subscription", AsyncMock(return_value=mock_subscription)),
            patch.object(service, "get_plan", AsyncMock(side_effect=[low, high])),
        ):
            await service.upgrade_subscription(mock_subscription.tenant_id, low.id)

        amount = service.credit_service.add_credits.await_args.kwargs["amount"]
        expected_take_back = int((30000 / 30 - 1000 / 30) * 29)  # 29 whole days left in the period
        assert amount == -expected_take_back

    async def test_a_downgrade_never_takes_more_than_is_unused(self, service, mock_db, mock_subscription):
        low = MagicMock(spec=SubscriptionPlan, id=uuid4(), credits_monthly=1000)
        low.name = "Low"
        high = MagicMock(spec=SubscriptionPlan, id=uuid4(), credits_monthly=30000)
        mock_subscription.current_period_end = datetime.now(UTC) + timedelta(days=29, hours=12)
        service.credit_service = AsyncMock()
        service.credit_service.get_balance = AsyncMock(return_value=MagicMock(available_credits=500))
        with (
            patch.object(service, "get_tenant_subscription", AsyncMock(return_value=mock_subscription)),
            patch.object(service, "get_plan", AsyncMock(side_effect=[low, high])),
        ):
            await service.upgrade_subscription(mock_subscription.tenant_id, low.id)
        assert service.credit_service.add_credits.await_args.kwargs["amount"] == -500

    async def test_upgrade_subscription_no_active(self, service):
        with patch.object(service, "get_tenant_subscription", AsyncMock(return_value=None)):
            with pytest.raises(ValueError, match="No active subscription"):
                await service.upgrade_subscription(uuid4(), uuid4())

    async def test_get_subscription_history(self, service, mock_db):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [MagicMock(), MagicMock()]
        mock_db.execute.return_value = mock_result

        history = await service.get_subscription_history(uuid4())
        assert len(history) == 2
        mock_db.execute.assert_called_once()

    async def test_get_subscription_by_tenant_async(self, service, mock_subscription):
        with patch.object(service, "get_tenant_subscription", AsyncMock(return_value=mock_subscription)):
            result = await service.get_subscription_by_tenant(uuid4())
            assert result == mock_subscription
