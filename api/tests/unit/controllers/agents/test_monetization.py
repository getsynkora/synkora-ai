"""Unit tests for agent monetisation purchase endpoints."""

import sys
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

# Stub out the heavy transitive deps before importing the module under test
for _mod in [
    "googleapiclient",
    "googleapiclient.discovery",
    "httplib2",
]:
    sys.modules.setdefault(_mod, MagicMock())

from src.controllers.agents.monetization import (  # noqa: E402
    GuestCheckoutRequest,
    SubscribeRequest,
    create_guest_checkout,
    get_guest_token,
    subscribe_with_credits,
)
from src.models.agent_user_subscription import AgentUserSubscription, SubscriptionAccessStatus


@pytest.fixture
def mock_db():
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.id = uuid4()
    agent.slug = "test-agent"
    agent.tenant_id = uuid4()
    return agent


def _mock_db_with_agent(mock_db, agent):
    result = MagicMock()
    result.scalar_one_or_none.return_value = agent
    mock_db.execute.return_value = result
    return mock_db


def _mock_db_no_agent(mock_db):
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = result
    return mock_db


# ---------------------------------------------------------------------------
# subscribe_with_credits
# ---------------------------------------------------------------------------


class TestSubscribeWithCredits:
    @pytest.mark.asyncio
    async def test_returns_subscription_on_success(self, mock_db, mock_agent):
        _mock_db_with_agent(mock_db, mock_agent)

        mock_sub = MagicMock(spec=AgentUserSubscription)
        mock_sub.id = uuid4()
        mock_sub.pricing_tier = "SESSION"
        mock_sub.status = SubscriptionAccessStatus.ACTIVE
        mock_sub.started_at = MagicMock()
        mock_sub.started_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"
        mock_sub.expires_at = MagicMock()
        mock_sub.expires_at.isoformat.return_value = "2026-01-01T02:00:00+00:00"

        with patch(
            "src.controllers.agents.monetization.AgentUserSubscriptionService.subscribe_account_user",
            new=AsyncMock(return_value=mock_sub),
        ):
            body = SubscribeRequest(pricing_id=uuid4(), tier="SESSION")
            result = await subscribe_with_credits(
                agent_slug="test-agent",
                body=body,
                db=mock_db,
                account=MagicMock(),
                tenant_id=uuid4(),
            )

        assert result["subscription"]["pricing_tier"] == "SESSION"
        assert result["subscription"]["status"] == SubscriptionAccessStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_raises_404_when_agent_not_found(self, mock_db):
        _mock_db_no_agent(mock_db)

        body = SubscribeRequest(pricing_id=uuid4(), tier="SESSION")
        with pytest.raises(HTTPException) as exc_info:
            await subscribe_with_credits(
                agent_slug="ghost-agent",
                body=body,
                db=mock_db,
                account=MagicMock(),
                tenant_id=uuid4(),
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_raises_400_on_value_error(self, mock_db, mock_agent):
        _mock_db_with_agent(mock_db, mock_agent)

        with patch(
            "src.controllers.agents.monetization.AgentUserSubscriptionService.subscribe_account_user",
            new=AsyncMock(side_effect=ValueError("Insufficient credits")),
        ):
            body = SubscribeRequest(pricing_id=uuid4(), tier="SESSION")
            with pytest.raises(HTTPException) as exc_info:
                await subscribe_with_credits(
                    agent_slug="test-agent",
                    body=body,
                    db=mock_db,
                    account=MagicMock(),
                    tenant_id=uuid4(),
                )
            assert exc_info.value.status_code == 400
            assert "Insufficient credits" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_passes_discount_code_to_service(self, mock_db, mock_agent):
        _mock_db_with_agent(mock_db, mock_agent)

        mock_sub = MagicMock(spec=AgentUserSubscription)
        mock_sub.id = uuid4()
        mock_sub.pricing_tier = "DAILY"
        mock_sub.status = SubscriptionAccessStatus.ACTIVE
        mock_sub.started_at = MagicMock()
        mock_sub.started_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"
        mock_sub.expires_at = None

        subscribe_mock = AsyncMock(return_value=mock_sub)
        with patch(
            "src.controllers.agents.monetization.AgentUserSubscriptionService.subscribe_account_user",
            new=subscribe_mock,
        ):
            body = SubscribeRequest(pricing_id=uuid4(), tier="DAILY", discount_code="SAVE20")
            await subscribe_with_credits(
                agent_slug="test-agent",
                body=body,
                db=mock_db,
                account=MagicMock(),
                tenant_id=uuid4(),
            )

        _, kwargs = subscribe_mock.call_args
        assert kwargs["discount_code"] == "SAVE20"


# ---------------------------------------------------------------------------
# create_guest_checkout
# ---------------------------------------------------------------------------


class TestCreateGuestCheckout:
    @pytest.mark.asyncio
    async def test_returns_checkout_url(self, mock_db, mock_agent):
        _mock_db_with_agent(mock_db, mock_agent)

        with patch(
            "src.controllers.agents.monetization.AgentUserSubscriptionService.create_stripe_checkout_session",
            new=AsyncMock(return_value="https://checkout.stripe.com/pay/abc123"),
        ):
            body = GuestCheckoutRequest(
                pricing_id=uuid4(),
                tier="MONTHLY",
                guest_email="guest@example.com",
                success_url="https://app.example.com/success",
                cancel_url="https://app.example.com/cancel",
            )
            result = await create_guest_checkout(agent_slug="test-agent", body=body, db=mock_db)

        assert result["checkout_url"] == "https://checkout.stripe.com/pay/abc123"

    @pytest.mark.asyncio
    async def test_raises_404_when_agent_not_found(self, mock_db):
        _mock_db_no_agent(mock_db)

        body = GuestCheckoutRequest(
            pricing_id=uuid4(),
            tier="SESSION",
            guest_email="g@example.com",
            success_url="https://s.example.com",
            cancel_url="https://c.example.com",
        )
        with pytest.raises(HTTPException) as exc_info:
            await create_guest_checkout(agent_slug="ghost", body=body, db=mock_db)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_raises_503_when_stripe_unavailable(self, mock_db, mock_agent):
        _mock_db_with_agent(mock_db, mock_agent)

        with patch(
            "src.controllers.agents.monetization.AgentUserSubscriptionService.create_stripe_checkout_session",
            new=AsyncMock(side_effect=Exception("Stripe not configured")),
        ):
            body = GuestCheckoutRequest(
                pricing_id=uuid4(),
                tier="SESSION",
                guest_email="g@example.com",
                success_url="https://s.example.com",
                cancel_url="https://c.example.com",
            )
            with pytest.raises(HTTPException) as exc_info:
                await create_guest_checkout(agent_slug="test-agent", body=body, db=mock_db)
            assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_raises_400_on_value_error(self, mock_db, mock_agent):
        _mock_db_with_agent(mock_db, mock_agent)

        with patch(
            "src.controllers.agents.monetization.AgentUserSubscriptionService.create_stripe_checkout_session",
            new=AsyncMock(side_effect=ValueError("No price configured for tier 'DAILY'")),
        ):
            body = GuestCheckoutRequest(
                pricing_id=uuid4(),
                tier="DAILY",
                guest_email="g@example.com",
                success_url="https://s.example.com",
                cancel_url="https://c.example.com",
            )
            with pytest.raises(HTTPException) as exc_info:
                await create_guest_checkout(agent_slug="test-agent", body=body, db=mock_db)
            assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# get_guest_token
# ---------------------------------------------------------------------------


class TestGetGuestToken:
    @pytest.mark.asyncio
    async def test_returns_token_and_deletes_from_redis(self):
        session_id = "cs_test_abc123"
        raw_token = "tok_supersecret"

        mock_redis = AsyncMock()
        mock_redis.getdel = AsyncMock(return_value=raw_token)

        with patch("src.controllers.agents.monetization.get_redis_async", return_value=mock_redis):
            result = await get_guest_token(session_id=session_id)

        assert result["agent_access_token"] == raw_token
        mock_redis.getdel.assert_called_once_with(f"agent_token:{session_id}")

    @pytest.mark.asyncio
    async def test_raises_404_when_token_not_found(self):
        mock_redis = AsyncMock()
        mock_redis.getdel = AsyncMock(return_value=None)

        with patch("src.controllers.agents.monetization.get_redis_async", return_value=mock_redis):
            with pytest.raises(HTTPException) as exc_info:
                await get_guest_token(session_id="cs_expired")
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_raises_503_on_redis_error(self):
        mock_redis = AsyncMock()
        mock_redis.getdel = AsyncMock(side_effect=Exception("Redis unavailable"))

        with patch("src.controllers.agents.monetization.get_redis_async", return_value=mock_redis):
            with pytest.raises(HTTPException) as exc_info:
                await get_guest_token(session_id="cs_any")
        assert exc_info.value.status_code == 503
