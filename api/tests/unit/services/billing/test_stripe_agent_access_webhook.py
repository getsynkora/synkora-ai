"""Tests for Stripe webhook handling of agent_access checkout sessions (Fix 2B)."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.billing.stripe_service import StripeService


@pytest.fixture
def mock_db():
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.add = MagicMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
async def stripe_service(mock_db):
    """Build a StripeService with all Stripe+integration deps mocked."""
    mock_config = MagicMock()
    mock_config.id = uuid4()
    mock_config.is_active = True
    mock_config.config_data = b"enc"

    mock_int_svc = MagicMock()
    mock_int_svc.get_active_config = AsyncMock(return_value=mock_config)
    mock_int_svc._decrypt_config.return_value = {
        "credentials": {"secret_key": "sk_test", "webhook_secret": "whsec_test"},
        "settings": {"publishable_key": "pk_test"},
    }

    with (
        patch(
            "src.services.billing.stripe_service.IntegrationConfigService",
            return_value=mock_int_svc,
        ),
        patch("src.services.billing.stripe_service.stripe"),
    ):
        svc = await StripeService.create(mock_db)
    return svc


class TestHandleCheckoutAgentAccess:
    @pytest.mark.asyncio
    async def test_agent_access_session_calls_fulfill_and_stores_token(self, stripe_service):
        session = {
            "id": "cs_test_agent_abc",
            "metadata": {"type": "agent_access"},
        }

        raw_token = "raw_tok_supersecret"
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock()

        with (
            patch(
                "src.services.billing.stripe_service.AgentUserSubscriptionService.fulfill_guest_subscription",
                new=AsyncMock(return_value=(raw_token, "guest@example.com")),
            ) as mock_fulfill,
            patch(
                "src.services.billing.stripe_service.get_redis_async",
                return_value=mock_redis,
            ),
        ):
            result = await stripe_service._handle_checkout_session_completed(session)

        assert result is True
        mock_fulfill.assert_called_once_with("cs_test_agent_abc", stripe_service.db)
        mock_redis.setex.assert_called_once_with("agent_token:cs_test_agent_abc", 600, raw_token)

    @pytest.mark.asyncio
    async def test_agent_access_failure_returns_false(self, stripe_service):
        session = {
            "id": "cs_test_fail",
            "metadata": {"type": "agent_access"},
        }

        with (
            patch(
                "src.services.billing.stripe_service.AgentUserSubscriptionService.fulfill_guest_subscription",
                new=AsyncMock(side_effect=Exception("DB error")),
            ),
            patch("src.services.billing.stripe_service.get_redis_async"),
        ):
            result = await stripe_service._handle_checkout_session_completed(session)

        assert result is False

    @pytest.mark.asyncio
    async def test_redis_failure_does_not_prevent_success(self, stripe_service):
        """If Redis is unavailable, the subscription is still created — token just can't be retrieved."""
        session = {
            "id": "cs_test_redis_fail",
            "metadata": {"type": "agent_access"},
        }

        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock(side_effect=Exception("Redis down"))

        with (
            patch(
                "src.services.billing.stripe_service.AgentUserSubscriptionService.fulfill_guest_subscription",
                new=AsyncMock(return_value=("tok_abc", "g@example.com")),
            ),
            patch(
                "src.services.billing.stripe_service.get_redis_async",
                return_value=mock_redis,
            ),
        ):
            result = await stripe_service._handle_checkout_session_completed(session)

        # fulfill was called and succeeded; Redis failure is non-fatal
        assert result is True

    @pytest.mark.asyncio
    async def test_unrecognised_type_still_returns_true(self, stripe_service):
        """Unknown event types must not raise — return True (idempotent)."""
        session = {
            "id": "cs_unknown",
            "metadata": {"type": "future_event_type"},
        }
        result = await stripe_service._handle_checkout_session_completed(session)
        assert result is True

    @pytest.mark.asyncio
    async def test_topup_session_still_handled_correctly(self, stripe_service, mock_db):
        """Ensure we didn't break the pre-existing topup branch."""
        topup_id = str(uuid4())
        session = {
            "id": "cs_topup",
            "metadata": {
                "type": "credit_topup",
                "topup_id": topup_id,
                "credits_amount": "100",
                "tenant_id": str(uuid4()),
            },
        }

        mock_topup = MagicMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = mock_topup
        stripe_service.db.execute.return_value = result_mock

        mock_credit_svc = AsyncMock()
        mock_credit_svc.add_credits = AsyncMock()
        stripe_service.credit_service = mock_credit_svc

        result = await stripe_service._handle_checkout_session_completed(session)

        assert result is True
        mock_credit_svc.add_credits.assert_called_once()
