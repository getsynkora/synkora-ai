"""Unit tests for the Slack bot incoming message gate."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.slack.slack_bot_gate import (
    ANSWER_KEY,
    DEFAULT_MIN_ACTIONABLE,
    DEFAULT_MODE,
    GATE_TIMEOUT_SECONDS,
    MODE_ENFORCE,
    MODE_SHADOW,
    SlackBotGateConfig,
    SlackBotGateDecision,
    evaluate_slack_message,
)


def _cfg(mode: str = MODE_SHADOW, threshold: float = DEFAULT_MIN_ACTIONABLE) -> SlackBotGateConfig:
    return SlackBotGateConfig(mode=mode, min_actionable=threshold)


def _client(noul: float | None = None, *, result: dict | None = None) -> MagicMock:
    client = MagicMock()
    payload = result if result is not None else {"answers": {ANSWER_KEY: {"type": "noul", "noul": noul}}}
    client.evaluate = AsyncMock(return_value=payload)
    return client


async def _eval(cfg, client, *, text="Hey bot, can you help with the outage?", agent_name="ops-bot", description="Monitors infrastructure"):
    return await evaluate_slack_message(
        cfg=cfg,
        client=client,
        text=text,
        agent_name=agent_name,
        description=description,
    )


class TestConfigParsing:
    def test_from_tools_config_none_returns_default(self):
        cfg = SlackBotGateConfig.from_agent_tools_config(None)
        assert cfg.mode == MODE_SHADOW
        assert cfg.min_actionable == DEFAULT_MIN_ACTIONABLE

    def test_from_tools_config_missing_key_returns_default(self):
        cfg = SlackBotGateConfig.from_agent_tools_config({"other_key": {}})
        assert cfg.mode == MODE_SHADOW

    def test_from_tools_config_enforce_mode(self):
        cfg = SlackBotGateConfig.from_agent_tools_config({"slack_bot_gate": {"mode": "enforce"}})
        assert cfg.mode == MODE_ENFORCE

    def test_from_tools_config_threshold_clamped(self):
        cfg = SlackBotGateConfig.from_agent_tools_config({"slack_bot_gate": {"threshold": 0.9}})
        assert cfg.min_actionable == 0.5  # _MAX_MIN_ACTIONABLE

    def test_from_tools_config_unknown_mode_falls_back_to_shadow(self):
        cfg = SlackBotGateConfig.from_agent_tools_config({"slack_bot_gate": {"mode": "destroy"}})
        assert cfg.mode == MODE_SHADOW


class TestFailOpen:
    @pytest.mark.asyncio
    async def test_none_client_returns_run(self):
        decision = await _eval(_cfg(), None)
        assert decision.action == "run"
        assert decision.reason == "no_typesafe_credentials"

    @pytest.mark.asyncio
    async def test_timeout_returns_run(self):
        client = MagicMock()
        client.evaluate = AsyncMock(side_effect=asyncio.TimeoutError())
        decision = await _eval(_cfg(), client, text="Help me!")
        assert decision.action == "run"
        assert decision.reason == "timeout"

    @pytest.mark.asyncio
    async def test_api_error_returns_run(self):
        client = _client(result={"error": "internal_server_error"})
        decision = await _eval(_cfg(), client)
        assert decision.action == "run"
        assert decision.reason == "api_error"

    @pytest.mark.asyncio
    async def test_malformed_answer_returns_run(self):
        client = _client(result={"answers": {ANSWER_KEY: {"noul": "bad"}}})
        decision = await _eval(_cfg(), client)
        assert decision.action == "run"
        assert decision.reason == "malformed_answer"

    @pytest.mark.asyncio
    async def test_exception_returns_run(self):
        client = MagicMock()
        client.evaluate = AsyncMock(side_effect=RuntimeError("boom"))
        decision = await _eval(_cfg(), client)
        assert decision.action == "run"
        assert decision.reason == "error"


class TestShadowMode:
    @pytest.mark.asyncio
    async def test_shadow_below_threshold_still_runs(self):
        """Shadow mode: scores below threshold log a would-skip but still return run."""
        cfg = _cfg(mode=MODE_SHADOW, threshold=0.5)
        client = _client(noul=0.1)
        decision = await _eval(cfg, client)
        assert decision.action == "run"
        assert "shadow" in decision.reason
        assert decision.actionable == pytest.approx(0.1, abs=0.001)

    @pytest.mark.asyncio
    async def test_shadow_above_threshold_runs(self):
        cfg = _cfg(mode=MODE_SHADOW, threshold=0.25)
        client = _client(noul=0.8)
        decision = await _eval(cfg, client)
        assert decision.action == "run"
        assert decision.actionable == pytest.approx(0.8, abs=0.001)


class TestEnforceMode:
    @pytest.mark.asyncio
    async def test_enforce_below_threshold_skips(self):
        cfg = _cfg(mode=MODE_ENFORCE, threshold=0.25)
        client = _client(noul=0.1)
        decision = await _eval(cfg, client)
        assert decision.action == "skip"

    @pytest.mark.asyncio
    async def test_enforce_above_threshold_runs(self):
        cfg = _cfg(mode=MODE_ENFORCE, threshold=0.25)
        client = _client(noul=0.9)
        decision = await _eval(cfg, client)
        assert decision.action == "run"

    @pytest.mark.asyncio
    async def test_enforce_at_threshold_runs(self):
        """Exactly at threshold → run (not skip)."""
        cfg = _cfg(mode=MODE_ENFORCE, threshold=0.25)
        client = _client(noul=0.25)
        decision = await _eval(cfg, client)
        assert decision.action == "run"


class TestDecisionShape:
    @pytest.mark.asyncio
    async def test_decision_to_dict_has_expected_keys(self):
        cfg = _cfg()
        client = _client(noul=0.7)
        decision = await _eval(cfg, client)
        d = decision.to_dict()
        assert set(d.keys()) == {"action", "mode", "actionable", "reason", "latency_ms"}

    @pytest.mark.asyncio
    async def test_latency_ms_is_non_negative(self):
        cfg = _cfg()
        client = _client(noul=0.5)
        decision = await _eval(cfg, client)
        assert isinstance(decision.latency_ms, int)
        assert decision.latency_ms >= 0
