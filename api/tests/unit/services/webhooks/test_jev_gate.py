"""Unit tests for the webhook Jev gate."""

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.webhooks import jev_gate
from src.services.webhooks.jev_gate import (
    ANSWER_KEY,
    JevGateConfig,
    build_state,
    decide,
    evaluate_event,
)
from src.services.webhooks.webhook_processor import WebhookProcessor

PARSED = {"event_type": "issue_comment.created", "data": {"body": "LGTM", "author": "ci-bot"}}


def _cfg(**overrides):
    raw = {"enabled": True, **overrides}
    cfg = JevGateConfig.from_webhook_config({"jev_gate": raw})
    assert cfg is not None
    return cfg


def _client(noul=None, *, result=None):
    client = MagicMock()
    payload = result if result is not None else {"answers": {ANSWER_KEY: {"type": "noul", "noul": noul}}}
    client.evaluate = AsyncMock(return_value=payload)
    return client


async def _evaluate(cfg, client, parsed=PARSED, **kwargs):
    return await evaluate_event(
        cfg=cfg,
        client=client,
        agent_name="pr-reviewer",
        description="Reviews pull requests",
        provider="github",
        parsed_data=parsed,
        **kwargs,
    )


class TestConfigParsing:
    @pytest.mark.parametrize("config", [None, {}, {"jev_gate": None}, {"jev_gate": {"enabled": False}}])
    def test_disabled_returns_none(self, config):
        assert JevGateConfig.from_webhook_config(config) is None

    @pytest.mark.parametrize("enabled", ["true", 1, "yes"])
    def test_enabled_must_be_literal_true(self, enabled):
        assert JevGateConfig.from_webhook_config({"jev_gate": {"enabled": enabled}}) is None

    def test_defaults_to_shadow_mode(self):
        cfg = _cfg()
        assert cfg.mode == "shadow"
        assert cfg.min_actionable == jev_gate.DEFAULT_MIN_ACTIONABLE

    def test_unknown_mode_falls_back_to_shadow(self):
        assert _cfg(mode="destroy").mode == "shadow"

    def test_enforce_mode_is_kept(self):
        assert _cfg(mode="enforce").mode == "enforce"

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            (0.3, 0.3),
            (0.9, 0.5),
            (-1, 0.0),
            ("bad", jev_gate.DEFAULT_MIN_ACTIONABLE),
            (None, jev_gate.DEFAULT_MIN_ACTIONABLE),
        ],
    )
    def test_threshold_is_clamped(self, raw, expected):
        assert _cfg(min_actionable=raw).min_actionable == expected

    def test_instructions_trimmed_and_capped(self):
        cfg = _cfg(instructions="  " + "x" * 5000 + "  ")
        assert len(cfg.instructions) == 1000

    def test_non_string_instructions_ignored(self):
        assert _cfg(instructions=123).instructions == ""


class TestDecide:
    def test_at_or_above_threshold_runs(self):
        assert decide(_cfg(mode="enforce"), 0.2)[0] == "run"
        assert decide(_cfg(mode="enforce"), 0.9)[0] == "run"

    def test_below_threshold_skips_in_enforce(self):
        action, reason = decide(_cfg(mode="enforce"), 0.05)
        assert action == "skip"
        assert "0.05" in reason

    def test_below_threshold_only_reports_in_shadow(self):
        action, reason = decide(_cfg(mode="shadow"), 0.05)
        assert action == "run"
        assert "would skip" in reason


class TestBuildState:
    def test_uses_description_and_instructions(self):
        state = build_state(
            agent_name="a",
            description="Reviews PRs",
            cfg=_cfg(instructions="Ignore bots"),
            provider="github",
            parsed_data=PARSED,
        )
        assert state["agent_purpose"] == "Reviews PRs"
        assert state["instructions"] == "Ignore bots"
        assert state["event_type"] == "issue_comment.created"
        assert "LGTM" in state["event"]

    def test_falls_back_to_agent_name(self):
        state = build_state(agent_name="pr-bot", description=None, cfg=_cfg(), provider="github", parsed_data=PARSED)
        assert state["agent_purpose"] == "pr-bot"
        assert "instructions" not in state

    def test_large_events_are_truncated(self):
        big = {"event_type": "push", "data": {"body": "x" * 50_000}}
        state = build_state(agent_name="a", description="d", cfg=_cfg(), provider="github", parsed_data=big)
        assert len(state["event"]) == 6000

    def test_unserialisable_data_does_not_raise(self):
        weird = {"event_type": "x", "data": {"obj": object()}}
        state = build_state(agent_name="a", description="d", cfg=_cfg(), provider="github", parsed_data=weird)
        assert isinstance(state["event"], str)


class TestEvaluateEvent:
    @pytest.mark.asyncio
    async def test_confident_no_skips_in_enforce(self):
        decision = await _evaluate(_cfg(mode="enforce"), _client(0.03))
        assert decision.action == "skip"
        assert decision.actionable == 0.03
        assert decision.latency_ms is not None

    @pytest.mark.asyncio
    async def test_confident_no_runs_in_shadow(self):
        decision = await _evaluate(_cfg(mode="shadow"), _client(0.03))
        assert decision.action == "run"
        assert decision.actionable == 0.03

    @pytest.mark.asyncio
    async def test_unsure_runs_even_in_enforce(self):
        decision = await _evaluate(_cfg(mode="enforce"), _client(0.45))
        assert decision.action == "run"

    @pytest.mark.asyncio
    async def test_sends_one_noul_question_with_untrusted_warning(self):
        client = _client(0.9)
        await _evaluate(_cfg(), client)
        kwargs = client.evaluate.call_args.kwargs
        assert list(kwargs["questions"]) == [ANSWER_KEY]
        assert kwargs["questions"][ANSWER_KEY]["type"] == "noul"
        assert "untrusted" in kwargs["questions"][ANSWER_KEY]["question"]

    @pytest.mark.asyncio
    async def test_no_client_fails_open(self):
        decision = await _evaluate(_cfg(mode="enforce"), None)
        assert decision.action == "run"
        assert decision.reason == "no_typesafe_credentials"
        assert decision.actionable is None

    @pytest.mark.asyncio
    async def test_api_error_fails_open(self):
        decision = await _evaluate(_cfg(mode="enforce"), _client(result={"error": "boom", "answers": {}}))
        assert decision.action == "run"
        assert decision.reason == "api_error"

    @pytest.mark.asyncio
    async def test_exception_fails_open(self):
        client = MagicMock()
        client.evaluate = AsyncMock(side_effect=RuntimeError("network"))
        decision = await _evaluate(_cfg(mode="enforce"), client)
        assert decision.action == "run"
        assert decision.reason == "error"

    @pytest.mark.asyncio
    async def test_timeout_fails_open(self):
        client = MagicMock()

        async def slow(**_):
            await asyncio.sleep(1)

        client.evaluate = slow
        decision = await _evaluate(_cfg(mode="enforce"), client, timeout=0.01)
        assert decision.action == "run"
        assert decision.reason == "timeout"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "result",
        [
            {"answers": {}},
            {"answers": {ANSWER_KEY: "no"}},
            {"answers": {ANSWER_KEY: {"noul": "0.0"}}},
            {"answers": {ANSWER_KEY: {"noul": 1.5}}},
            {"answers": {ANSWER_KEY: {"noul": -0.1}}},
            {"answers": {ANSWER_KEY: {"noul": True}}},
            {"answers": {ANSWER_KEY: {"noul": None}}},
            {},
        ],
    )
    async def test_malformed_answer_fails_open(self, result):
        decision = await _evaluate(_cfg(mode="enforce"), _client(result=result))
        assert decision.action == "run"
        assert decision.reason == "malformed_answer"

    @pytest.mark.asyncio
    async def test_to_dict_is_json_friendly(self):
        decision = await _evaluate(_cfg(mode="enforce"), _client(0.03))
        assert set(decision.to_dict()) == {"action", "mode", "actionable", "reason", "latency_ms"}


class TestProcessorIntegration:
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock(spec=AsyncSession)
        empty = MagicMock()
        empty.scalar_one_or_none.return_value = None
        empty.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=empty)
        return db

    @pytest.fixture
    def processor(self, mock_db):
        return WebhookProcessor(mock_db)

    @pytest.fixture
    def webhook(self):
        wh = MagicMock()
        wh.id = uuid.uuid4()
        wh.agent_id = uuid.uuid4()
        wh.provider = "github"
        wh.secret = None
        wh.is_active = True
        wh.event_types = None
        wh.config = {"verify_signature": False}
        wh.success_count = 0
        wh.failure_count = 0
        return wh

    def _patches(self, gate_decision):
        return (
            patch.object(WebhookProcessor, "evaluate_jev_gate", AsyncMock(return_value=gate_decision)),
            patch.object(WebhookProcessor, "trigger_agent_execution", AsyncMock(return_value="task-1")),
            patch(
                "src.services.webhooks.webhook_processor.ProviderParser.parse_github",
                return_value=dict(PARSED),
            ),
        )

    async def _run(self, processor, webhook):
        return await processor.process_webhook(
            webhook=webhook,
            payload=b"{}",
            payload_dict={},
            headers={"x-github-event": "issue_comment", "x-github-delivery": "d-1"},
        )

    @pytest.mark.asyncio
    async def test_skip_records_event_and_does_not_trigger_agent(self, processor, webhook):
        decision = jev_gate.JevGateDecision(action="skip", mode="enforce", actionable=0.02, reason="r")
        gate_p, trigger_p, parse_p = self._patches(decision)
        with gate_p, trigger_p as trigger, parse_p:
            result = await self._run(processor, webhook)

        assert result["status"] == "skipped"
        assert result["message"] == "Skipped by Jev gate"
        trigger.assert_not_awaited()
        assert webhook.success_count == 0
        event = processor.db.add.call_args.args[0]
        assert event.status == "skipped"
        assert event.processing_completed_at is not None
        assert event.parsed_data["jev_gate"]["actionable"] == 0.02
        # Replay protection still works for skipped deliveries.
        assert event.event_id == "d-1"

    @pytest.mark.asyncio
    async def test_run_triggers_agent_with_unmodified_parsed_data(self, processor, webhook):
        decision = jev_gate.JevGateDecision(action="run", mode="shadow", actionable=0.02, reason="shadow")
        gate_p, trigger_p, parse_p = self._patches(decision)
        with gate_p, trigger_p as trigger, parse_p:
            result = await self._run(processor, webhook)

        assert result["status"] == "success"
        trigger.assert_awaited_once()
        sent = trigger.await_args.kwargs["parsed_data"]
        assert "jev_gate" not in sent  # the agent never sees the verdict
        event = processor.db.add.call_args.args[0]
        assert event.status == "pending"
        assert event.parsed_data["jev_gate"]["mode"] == "shadow"

    @pytest.mark.asyncio
    async def test_gate_disabled_adds_nothing(self, processor, webhook):
        gate_p, trigger_p, parse_p = self._patches(None)
        with gate_p, trigger_p, parse_p:
            result = await self._run(processor, webhook)

        assert result["status"] == "success"
        event = processor.db.add.call_args.args[0]
        assert "jev_gate" not in event.parsed_data

    @pytest.mark.asyncio
    async def test_evaluate_gate_returns_none_when_disabled(self, processor, webhook):
        assert await processor.evaluate_jev_gate(webhook, dict(PARSED)) is None
        processor.db.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_evaluate_gate_fails_open_when_agent_missing(self, processor, webhook):
        webhook.config = {"jev_gate": {"enabled": True, "mode": "enforce"}}
        decision = await processor.evaluate_jev_gate(webhook, dict(PARSED))
        assert decision.action == "run"
        assert decision.reason == "agent_not_found"

    @pytest.mark.asyncio
    async def test_evaluate_gate_fails_open_on_unexpected_error(self, processor, webhook):
        webhook.config = {"jev_gate": {"enabled": True, "mode": "enforce"}}
        processor.db.execute = AsyncMock(side_effect=RuntimeError("db down"))
        decision = await processor.evaluate_jev_gate(webhook, dict(PARSED))
        assert decision.action == "run"
        assert decision.reason == "error"

    @pytest.mark.asyncio
    async def test_evaluate_gate_end_to_end_skip(self, processor, webhook):
        webhook.config = {"jev_gate": {"enabled": True, "mode": "enforce"}}
        agent = MagicMock()
        agent.tenant_id = uuid.uuid4()
        agent.agent_name = "pr-reviewer"
        agent.description = "Reviews pull requests"
        found = MagicMock()
        found.scalar_one_or_none.return_value = agent
        processor.db.execute = AsyncMock(return_value=found)

        with patch(
            "src.services.agents.context_relevance_pruner.resolve_typesafe_client_for_pruning",
            AsyncMock(return_value=_client(0.02)),
        ):
            decision = await processor.evaluate_jev_gate(webhook, dict(PARSED))

        assert decision.action == "skip"
        assert decision.actionable == 0.02
