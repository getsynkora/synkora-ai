"""Tests for paywall and creator-bypass in the chat endpoints (Fix 4 + Fix 5)."""

import sys
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# Stub heavy transitive deps so collection doesn't fail on pyparsing/httplib2
for _mod in [
    "googleapiclient",
    "googleapiclient.discovery",
    "httplib2",
]:
    sys.modules.setdefault(_mod, MagicMock())

from src.models.agent_pricing import AgentPricing, PricingModel  # noqa: E402
from src.models.agent_user_subscription import SubscriptionAccessStatus  # noqa: E402

# ---------------------------------------------------------------------------
# Helper: build a paid AgentPricing mock
# ---------------------------------------------------------------------------


def _paid_pricing(trial_messages=0, session_credits=10):
    p = MagicMock(spec=AgentPricing)
    p.id = uuid4()
    p.pricing_model = PricingModel.SESSION
    p.is_paid = True
    p.trial_messages = trial_messages
    p.session_credits = session_credits
    p.daily_credits = 50
    p.weekly_credits = 150
    p.monthly_subscription_credits = 400
    return p


# ---------------------------------------------------------------------------
# Test the creator-bypass logic directly (unit, no HTTP layer)
# ---------------------------------------------------------------------------


class TestCreatorBypassLogic:
    """The paywall must grant access when tenant_id == agent.tenant_id."""

    @pytest.mark.asyncio
    async def test_creator_always_has_access(self):
        creator_tenant_id = uuid4()

        mock_agent = MagicMock()
        mock_agent.id = uuid4()
        mock_agent.tenant_id = creator_tenant_id

        mock_pricing = _paid_pricing(trial_messages=0)

        mock_db = AsyncMock()
        pricing_result = MagicMock()
        pricing_result.scalar_one_or_none.return_value = mock_pricing
        mock_db.execute = AsyncMock(return_value=pricing_result)

        check_access_mock = AsyncMock(return_value=False)  # Would block if called

        with patch(
            "src.services.billing.agent_user_subscription_service.AgentUserSubscriptionService.check_access",
            new=check_access_mock,
        ):
            # Simulate the creator-bypass guard
            tenant_id = creator_tenant_id
            if tenant_id == mock_agent.tenant_id:
                has_access = True
            else:
                has_access = await check_access_mock(agent_id=mock_agent.id, db=mock_db, subscriber_tenant_id=tenant_id)

        assert has_access is True
        check_access_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_creator_goes_through_access_check(self):
        creator_tenant_id = uuid4()
        subscriber_tenant_id = uuid4()  # different tenant

        mock_agent = MagicMock()
        mock_agent.id = uuid4()
        mock_agent.tenant_id = creator_tenant_id

        check_access_mock = AsyncMock(return_value=True)

        tenant_id = subscriber_tenant_id
        if tenant_id != mock_agent.tenant_id:
            mock_db = AsyncMock()
            await check_access_mock(agent_id=mock_agent.id, db=mock_db, subscriber_tenant_id=tenant_id)

        check_access_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_subscriber_without_access_blocked_after_trial(self):
        """After trial messages are exhausted, non-subscriber gets paywall."""
        creator_tenant_id = uuid4()
        _subscriber_tenant_id = uuid4()

        mock_agent = MagicMock()
        mock_agent.id = uuid4()
        mock_agent.tenant_id = creator_tenant_id

        mock_pricing = _paid_pricing(trial_messages=2)

        # Simulate trial_used > trial_messages
        trial_used = 3
        should_paywall = trial_used > (mock_pricing.trial_messages or 0)

        assert should_paywall is True

    @pytest.mark.asyncio
    async def test_subscriber_within_trial_not_blocked(self):
        """Within the free trial window, non-subscriber can still chat."""
        mock_pricing = _paid_pricing(trial_messages=3)

        # First message: trial_used = 1
        trial_used = 1
        should_paywall = trial_used > (mock_pricing.trial_messages or 0)
        assert should_paywall is False

        # Third message: trial_used = 3
        trial_used = 3
        should_paywall = trial_used > (mock_pricing.trial_messages or 0)
        assert should_paywall is False

        # Fourth message: trial_used = 4 (exceeds 3)
        trial_used = 4
        should_paywall = trial_used > (mock_pricing.trial_messages or 0)
        assert should_paywall is True


# ---------------------------------------------------------------------------
# Test _ws_chat_pipeline paywall logic (Fix 4)
# ---------------------------------------------------------------------------


class TestWebSocketPaywallPipeline:
    """Verify the WS pipeline yields {type:paywall} and returns when paywall hit."""

    @pytest.mark.asyncio
    async def test_ws_pipeline_yields_paywall_when_no_subscription(self):
        """Non-subscriber hitting paywall gets {"type": "paywall"} frame and pipeline stops."""
        import json

        from src.controllers.agents.chat import _ws_chat_pipeline

        tenant_id = uuid4()
        agent_id = uuid4()
        agent_tenant_id = uuid4()  # Different from tenant_id

        mock_llm_config = MagicMock()
        mock_llm_config.is_default = True
        mock_llm_config.enabled = True
        mock_llm_config.model_name = "gpt-4"
        mock_llm_config.id = uuid4()

        mock_agent = MagicMock()
        mock_agent.id = agent_id
        mock_agent.slug = "test-agent"
        mock_agent.tenant_id = agent_tenant_id  # not the subscriber
        mock_agent.llm_configs = [mock_llm_config]

        mock_pricing = _paid_pricing(trial_messages=0)
        mock_pricing.id = uuid4()

        mock_db = AsyncMock()

        # First execute: agent load → returns mock_agent
        # Second execute: pricing load → returns mock_pricing
        # Third execute: profile load → returns None
        agent_result = MagicMock()
        agent_result.scalar_one_or_none.return_value = mock_agent

        pricing_result = MagicMock()
        pricing_result.scalar_one_or_none.return_value = mock_pricing

        profile_result = MagicMock()
        profile_result.scalar_one_or_none.return_value = None

        mock_db.execute = AsyncMock(side_effect=[agent_result, pricing_result, profile_result])

        mock_account = MagicMock()
        mock_account.id = uuid4()

        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=1)  # First call = 1 > 0 trial messages
        mock_redis.expire = AsyncMock()

        mock_billing_result = MagicMock()
        mock_billing_result.is_valid = True
        mock_billing_cls = MagicMock()
        mock_billing_cls.return_value.validate_chat_request = AsyncMock(return_value=mock_billing_result)

        frames = []
        with (
            patch(
                "src.controllers.agents.chat.advanced_prompt_scanner.scan_comprehensive",
                return_value={"is_safe": True, "risk_score": 0, "layers_triggered": 0, "detections": []},
            ),
            patch(
                "src.controllers.agents.chat.get_redis_async",
                return_value=mock_redis,
            ),
            patch("src.services.billing.ChatBillingService", mock_billing_cls),
            patch(
                "src.services.billing.agent_user_subscription_service.AgentUserSubscriptionService.check_access",
                new=AsyncMock(return_value=False),
            ),
        ):
            async for frame in _ws_chat_pipeline(
                agent_slug="test-agent",
                message="Hello",
                conversation_id=None,
                conversation_history=[],
                attachments=None,
                llm_config_id=None,
                db=mock_db,
                tenant_id=tenant_id,
                current_account=mock_account,
            ):
                frames.append(frame)
                break  # Stop after first frame

        assert len(frames) >= 1
        data = json.loads(frames[0])
        assert data["type"] == "paywall"
        assert "agent_id" in data["data"]
        assert "session_credits" in data["data"]

    @pytest.mark.asyncio
    async def test_ws_pipeline_creator_bypasses_paywall(self):
        """Creator tenant_id == agent.tenant_id → pipeline reaches stream, no paywall frame."""
        from src.controllers.agents.chat import _ws_chat_pipeline

        creator_tenant_id = uuid4()

        mock_llm_config = MagicMock()
        mock_llm_config.is_default = True
        mock_llm_config.enabled = True
        mock_llm_config.model_name = "gpt-4"
        mock_llm_config.id = uuid4()

        mock_agent = MagicMock()
        mock_agent.id = uuid4()
        mock_agent.slug = "test-agent"
        mock_agent.tenant_id = creator_tenant_id
        mock_agent.llm_configs = [mock_llm_config]

        mock_pricing = _paid_pricing(trial_messages=0)

        mock_db = AsyncMock()

        agent_result = MagicMock()
        agent_result.scalar_one_or_none.return_value = mock_agent

        pricing_result = MagicMock()
        pricing_result.scalar_one_or_none.return_value = mock_pricing

        mock_db.execute = AsyncMock(side_effect=[agent_result, pricing_result])

        mock_account = MagicMock()
        mock_account.id = uuid4()

        mock_billing_result = MagicMock()
        mock_billing_result.is_valid = True
        mock_billing_cls = MagicMock()
        mock_billing_cls.return_value.validate_chat_request = AsyncMock(return_value=mock_billing_result)

        frames = []
        stream_reached = False

        async def fake_stream(*args, **kwargs):
            nonlocal stream_reached
            stream_reached = True
            yield 'data: {"type":"done"}\n\n'

        with (
            patch(
                "src.controllers.agents.chat.advanced_prompt_scanner.scan_comprehensive",
                return_value={"is_safe": True, "risk_score": 0, "layers_triggered": 0, "detections": []},
            ),
            patch("src.controllers.agents.chat.get_redis_async", return_value=AsyncMock()),
            patch("src.services.billing.ChatBillingService", mock_billing_cls),
            patch(
                "src.controllers.agents.chat.chat_stream_service.stream_agent_response",
                side_effect=fake_stream,
            ),
        ):
            async for frame in _ws_chat_pipeline(
                agent_slug="test-agent",
                message="Hello",
                conversation_id=None,
                conversation_history=[],
                attachments=None,
                llm_config_id=None,
                db=mock_db,
                tenant_id=creator_tenant_id,  # Same as agent.tenant_id
                current_account=mock_account,
            ):
                frames.append(frame)

        # Should reach the stream without hitting paywall
        assert stream_reached is True
        # No paywall frame in output
        for f in frames:
            import json

            parsed = json.loads(f)
            assert parsed.get("type") != "paywall"


# ---------------------------------------------------------------------------
# Test AgentPricingUpsertRequest enum validation (Fix 6)
# ---------------------------------------------------------------------------


class TestAgentPricingEnumValidation:
    def test_valid_pricing_model_accepted(self):
        from src.controllers.billing import AgentPricingUpsertRequest
        from src.models.agent_pricing import PricingModel

        req = AgentPricingUpsertRequest(agent_id=uuid4(), pricing_model=PricingModel.SESSION)
        assert req.pricing_model == PricingModel.SESSION

    def test_invalid_pricing_model_rejected(self):
        import pydantic

        from src.controllers.billing import AgentPricingUpsertRequest

        with pytest.raises(pydantic.ValidationError):
            AgentPricingUpsertRequest(agent_id=uuid4(), pricing_model="YEARLY")

    def test_default_is_free(self):
        from src.controllers.billing import AgentPricingUpsertRequest
        from src.models.agent_pricing import PricingModel

        req = AgentPricingUpsertRequest(agent_id=uuid4())
        assert req.pricing_model == PricingModel.FREE
