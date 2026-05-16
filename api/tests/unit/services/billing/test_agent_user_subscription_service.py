"""Unit tests for AgentUserSubscriptionService."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent_pricing import AgentPricing, PricingModel
from src.models.agent_user_subscription import AgentUserSubscription, SubscriptionAccessStatus
from src.services.billing.agent_user_subscription_service import (
    AgentUserSubscriptionService,
    _hash_token,
)


@pytest.fixture
def mock_db():
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.add = MagicMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def mock_pricing():
    p = MagicMock(spec=AgentPricing)
    p.id = uuid4()
    p.tenant_id = uuid4()
    p.pricing_model = PricingModel.SUBSCRIPTION
    p.session_credits = 10
    p.daily_credits = 50
    p.weekly_credits = 150
    p.monthly_subscription_credits = 400
    p.revenue_share_percentage = Decimal("70.00")
    p.calculate_creator_revenue = lambda amount: int(amount * 0.70)
    p.calculate_platform_revenue = lambda amount: amount - int(amount * 0.70)
    return p


# ---------------------------------------------------------------------------
# check_access
# ---------------------------------------------------------------------------


class TestCheckAccess:
    @pytest.mark.asyncio
    async def test_returns_false_when_no_identifiers(self, mock_db):
        result = await AgentUserSubscriptionService.check_access(agent_id=uuid4(), db=mock_db)
        assert result is False
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_true_for_active_non_expired_sub(self, mock_db):
        mock_sub = MagicMock(spec=AgentUserSubscription)
        mock_sub.expires_at = datetime.now(UTC) + timedelta(hours=1)

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = mock_sub
        mock_db.execute.return_value = result_mock

        result = await AgentUserSubscriptionService.check_access(
            agent_id=uuid4(), db=mock_db, subscriber_tenant_id=uuid4()
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_and_marks_expired_when_past_expiry(self, mock_db):
        mock_sub = MagicMock(spec=AgentUserSubscription)
        mock_sub.expires_at = datetime.now(UTC) - timedelta(seconds=1)

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = mock_sub
        mock_db.execute.return_value = result_mock

        result = await AgentUserSubscriptionService.check_access(
            agent_id=uuid4(), db=mock_db, subscriber_tenant_id=uuid4()
        )
        assert result is False
        assert mock_sub.status == SubscriptionAccessStatus.EXPIRED
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_false_when_no_subscription_found(self, mock_db):
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = result_mock

        result = await AgentUserSubscriptionService.check_access(
            agent_id=uuid4(), db=mock_db, subscriber_tenant_id=uuid4()
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_for_no_expiry_sub(self, mock_db):
        mock_sub = MagicMock(spec=AgentUserSubscription)
        mock_sub.expires_at = None  # No expiry = permanent access

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = mock_sub
        mock_db.execute.return_value = result_mock

        result = await AgentUserSubscriptionService.check_access(
            agent_id=uuid4(), db=mock_db, subscriber_tenant_id=uuid4()
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_uses_hashed_token_for_guest_lookup(self, mock_db):
        raw_token = "my_raw_token"
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = result_mock

        await AgentUserSubscriptionService.check_access(agent_id=uuid4(), db=mock_db, guest_token=raw_token)

        # The query must use the hashed token, not the raw one
        call_args = str(mock_db.execute.call_args)
        assert raw_token not in call_args


# ---------------------------------------------------------------------------
# subscribe_account_user
# ---------------------------------------------------------------------------


class TestSubscribeAccountUser:
    @pytest.mark.asyncio
    async def test_deducts_credits_and_creates_subscription(self, mock_db, mock_pricing):
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = mock_pricing
        mock_db.execute.return_value = result_mock

        mock_credit_service = AsyncMock()
        mock_credit_service.deduct_credits = AsyncMock()

        with (
            patch(
                "src.services.billing.agent_user_subscription_service.CreditService",
                return_value=mock_credit_service,
            ),
            patch(
                "src.services.billing.agent_user_subscription_service.DiscountCodeService.validate_code",
                new=AsyncMock(return_value=None),
            ),
        ):
            await AgentUserSubscriptionService.subscribe_account_user(
                agent_id=uuid4(),
                pricing_id=mock_pricing.id,
                subscriber_tenant_id=uuid4(),
                tier="SESSION",
                db=mock_db,
            )

        mock_credit_service.deduct_credits.assert_called_once()
        call_kwargs = mock_credit_service.deduct_credits.call_args.kwargs
        assert call_kwargs["amount"] == 10  # session_credits

        mock_db.add.assert_called()  # revenue + subscription
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_value_error_for_unconfigured_tier(self, mock_db, mock_pricing):
        mock_pricing.daily_credits = None  # DAILY not configured

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = mock_pricing
        mock_db.execute.return_value = result_mock

        with pytest.raises(ValueError, match="No credit cost configured for tier 'DAILY'"):
            await AgentUserSubscriptionService.subscribe_account_user(
                agent_id=uuid4(),
                pricing_id=mock_pricing.id,
                subscriber_tenant_id=uuid4(),
                tier="DAILY",
                db=mock_db,
            )

    @pytest.mark.asyncio
    async def test_raises_value_error_when_pricing_not_found(self, mock_db):
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = result_mock

        with pytest.raises(ValueError, match="not found"):
            await AgentUserSubscriptionService.subscribe_account_user(
                agent_id=uuid4(),
                pricing_id=uuid4(),
                subscriber_tenant_id=uuid4(),
                tier="SESSION",
                db=mock_db,
            )

    @pytest.mark.asyncio
    async def test_applies_discount_code_when_provided(self, mock_db, mock_pricing):
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = mock_pricing
        mock_db.execute.return_value = result_mock

        mock_discount = MagicMock()
        mock_discount.id = uuid4()

        mock_credit_service = AsyncMock()
        mock_credit_service.deduct_credits = AsyncMock()

        with (
            patch(
                "src.services.billing.agent_user_subscription_service.CreditService",
                return_value=mock_credit_service,
            ),
            patch(
                "src.services.billing.agent_user_subscription_service.DiscountCodeService.validate_code",
                new=AsyncMock(return_value=mock_discount),
            ),
            patch(
                "src.services.billing.agent_user_subscription_service.DiscountCodeService.apply_and_consume",
                new=AsyncMock(return_value=8),  # 20% off 10 = 8
            ) as mock_apply,
        ):
            await AgentUserSubscriptionService.subscribe_account_user(
                agent_id=uuid4(),
                pricing_id=mock_pricing.id,
                subscriber_tenant_id=uuid4(),
                tier="SESSION",
                db=mock_db,
                discount_code="SAVE20",
            )

        mock_apply.assert_called_once_with(mock_discount.id, 10, mock_db)
        # Should deduct the discounted amount
        call_kwargs = mock_credit_service.deduct_credits.call_args.kwargs
        assert call_kwargs["amount"] == 8

    @pytest.mark.asyncio
    async def test_session_tier_expires_in_2_hours(self, mock_db, mock_pricing):
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = mock_pricing
        mock_db.execute.return_value = result_mock

        mock_credit_service = AsyncMock()
        mock_credit_service.deduct_credits = AsyncMock()

        with (
            patch(
                "src.services.billing.agent_user_subscription_service.CreditService",
                return_value=mock_credit_service,
            ),
            patch(
                "src.services.billing.agent_user_subscription_service.DiscountCodeService.validate_code",
                new=AsyncMock(return_value=None),
            ),
        ):
            await AgentUserSubscriptionService.subscribe_account_user(
                agent_id=uuid4(),
                pricing_id=mock_pricing.id,
                subscriber_tenant_id=uuid4(),
                tier="SESSION",
                db=mock_db,
            )

        add_calls = mock_db.add.call_args_list
        # Find the subscription add call (AgentUserSubscription, not AgentRevenue)
        from src.models.agent_user_subscription import AgentUserSubscription

        sub_add = next(call for call in add_calls if isinstance(call.args[0], AgentUserSubscription))
        created_sub = sub_add.args[0]
        assert created_sub.pricing_tier == "SESSION"
        # expires_at should be roughly 2 hours from now
        delta = created_sub.expires_at - created_sub.started_at
        assert timedelta(hours=1, minutes=55) < delta < timedelta(hours=2, minutes=5)

    @pytest.mark.asyncio
    async def test_records_creator_revenue(self, mock_db, mock_pricing):
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = mock_pricing
        mock_db.execute.return_value = result_mock

        mock_credit_service = AsyncMock()
        mock_credit_service.deduct_credits = AsyncMock()

        with (
            patch(
                "src.services.billing.agent_user_subscription_service.CreditService",
                return_value=mock_credit_service,
            ),
            patch(
                "src.services.billing.agent_user_subscription_service.DiscountCodeService.validate_code",
                new=AsyncMock(return_value=None),
            ),
        ):
            await AgentUserSubscriptionService.subscribe_account_user(
                agent_id=uuid4(),
                pricing_id=mock_pricing.id,
                subscriber_tenant_id=uuid4(),
                tier="SESSION",
                db=mock_db,
            )

        # Should add both AgentRevenue and AgentUserSubscription
        assert mock_db.add.call_count == 2


# ---------------------------------------------------------------------------
# create_stripe_checkout_session: type tag
# ---------------------------------------------------------------------------


class TestStripeCheckoutMetadata:
    @pytest.mark.asyncio
    async def test_metadata_includes_type_agent_access(self, mock_db, mock_pricing):
        """Stripe session metadata must include type=agent_access for webhook routing."""
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = mock_pricing
        mock_db.execute.return_value = result_mock

        captured_metadata = {}

        def fake_session_create(**kwargs):
            captured_metadata.update(kwargs.get("metadata", {}))
            session = MagicMock()
            session.__getitem__ = lambda self, key: "https://checkout.stripe.com/fake" if key == "url" else None
            return session

        with patch("src.services.billing.agent_user_subscription_service.stripe") as mock_stripe:
            mock_stripe.checkout.Session.create.side_effect = fake_session_create

            await AgentUserSubscriptionService.create_stripe_checkout_session(
                agent_id=uuid4(),
                pricing_id=mock_pricing.id,
                tier="SESSION",
                guest_email="guest@example.com",
                success_url="https://app.example.com/success",
                cancel_url="https://app.example.com/cancel",
                db=mock_db,
            )

        assert captured_metadata.get("type") == "agent_access"
        assert "agent_id" in captured_metadata
        assert "pricing_id" in captured_metadata
        assert "tier" in captured_metadata
        assert "guest_email" in captured_metadata


# ---------------------------------------------------------------------------
# fulfill_guest_subscription
# ---------------------------------------------------------------------------


class TestFulfillGuestSubscription:
    @pytest.mark.asyncio
    async def test_creates_active_subscription_and_returns_token(self, mock_db, mock_pricing):
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = mock_pricing
        mock_db.execute.return_value = result_mock

        fake_session = {
            "metadata": {
                "agent_id": str(uuid4()),
                "pricing_id": str(mock_pricing.id),
                "tier": "DAILY",
                "guest_email": "guest@example.com",
                "amount_cents": "50",
            },
            "customer": "cus_test123",
        }

        with patch("src.services.billing.agent_user_subscription_service.stripe") as mock_stripe:
            mock_stripe.checkout.Session.retrieve.return_value = fake_session

            raw_token, guest_email = await AgentUserSubscriptionService.fulfill_guest_subscription(
                stripe_session_id="cs_test_abc", db=mock_db
            )

        assert isinstance(raw_token, str)
        assert len(raw_token) > 10
        assert guest_email == "guest@example.com"

        # Subscription must be added
        mock_db.add.assert_called_once()
        sub = mock_db.add.call_args.args[0]
        assert sub.status == SubscriptionAccessStatus.ACTIVE
        assert sub.guest_token_hash is not None
        assert sub.guest_token_hash != raw_token  # must be hashed
        assert sub.guest_token_hash == _hash_token(raw_token)
