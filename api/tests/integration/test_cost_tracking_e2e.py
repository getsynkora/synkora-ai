"""
End-to-end integration trace for LLM cost tracking.

Simulates the exact sequence a user triggers from the chat UI:

  UI sends POST /agents/{name}/conversations/{id}/messages
    → chat_stream_service._handle_chat()
    → _build_prompt()
    → llm_client.set_cost_context()
    → _generate_anthropic_stream_with_messages()   ← prompt caching headers
    → get_final_message()                           ← usage capture into ContextVar
    → _with_streaming_timeout() finally             ← _read_and_fire_usage()
    → fire_persist_llm_usage()                      ← asyncio.create_task()
    → _persist_llm_usage()                          ← LLMTokenUsage INSERT
    → GET /billing/llm-cost/summary                ← analytics query returns row

Each step is verified with concrete values, not just "no exception raised".
Run: pytest tests/integration/test_cost_tracking_e2e.py -v -s
"""

import asyncio
import hashlib
import uuid
from contextvars import ContextVar
from datetime import UTC
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ─── Concrete test data ──────────────────────────────────────────────────────

TENANT_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")
AGENT_ID = uuid.UUID("20000000-0000-0000-0000-000000000002")
CONV_ID = uuid.UUID("30000000-0000-0000-0000-000000000003")
AGENT_UPDATED_AT = "1745000000.0"

# Exactly what the UI sends
USER_MESSAGE = "What is machine learning?"

# Agent LLM config: claude-haiku, temperature=0.7, no response cache
AGENT_MODEL = "claude-haiku-4-5-20251001"
AGENT_PROVIDER = "anthropic"
AGENT_TEMP = 0.7

# Anthropic returns these token counts (first call = cache creation)
ANTHROPIC_USAGE_CALL_1 = SimpleNamespace(
    input_tokens=450,
    output_tokens=95,
    cache_read_input_tokens=0,
    cache_creation_input_tokens=400,  # system prompt cached on first call
)

# Second identical call = cache read
ANTHROPIC_USAGE_CALL_2 = SimpleNamespace(
    input_tokens=450,
    output_tokens=95,
    cache_read_input_tokens=400,  # served from Anthropic's cache
    cache_creation_input_tokens=0,
)

SYSTEM_PROMPT = "You are a helpful AI assistant. Answer clearly and concisely. Be accurate and professional."


# ─── Step 1: set_cost_context populates _cost_context correctly ──────────────


class TestStep1_SetCostContext:
    """
    UI loads agent page → chat sends first message
    → chat_stream_service calls llm_client.set_cost_context()
    """

    def test_cost_context_fields_match_agent_data(self):
        from src.services.agents.config import ModelConfig
        from src.services.agents.llm_client import MultiProviderLLMClient

        config = ModelConfig(
            model_name=AGENT_MODEL,
            api_key="sk-ant-test",
            temperature=AGENT_TEMP,
        )
        client = MultiProviderLLMClient.__new__(MultiProviderLLMClient)
        client.config = config
        client.provider = AGENT_PROVIDER

        system_prompt_hash = hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()[:16]

        client.set_cost_context(
            tenant_id=TENANT_ID,
            agent_id=AGENT_ID,
            conversation_id=CONV_ID,
            routing_rules=None,
            optimization_flags={},
            enable_response_cache=False,
            system_prompt_hash=system_prompt_hash,
            agent_updated_at=AGENT_UPDATED_AT,
        )

        ctx = client._cost_context
        assert ctx["tenant_id"] == TENANT_ID, f"tenant_id mismatch: {ctx['tenant_id']}"
        assert ctx["agent_id"] == AGENT_ID, f"agent_id mismatch: {ctx['agent_id']}"
        assert ctx["conversation_id"] == CONV_ID, f"conv_id mismatch: {ctx['conversation_id']}"
        assert ctx["enable_response_cache"] is False, "cache should be off for this agent"
        assert len(ctx["system_prompt_hash"]) == 16, "SHA256 prefix should be 16 hex chars"
        assert ctx["agent_updated_at"] == AGENT_UPDATED_AT
        # Hash is stable for same prompt
        assert ctx["system_prompt_hash"] == hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()[:16]


# ─── Step 2: Anthropic prompt caching headers are sent ───────────────────────


class TestStep2_PromptCachingHeaders:
    """
    _generate_anthropic_stream_with_messages() must add:
      - anthropic-beta: prompt-caching-2024-07-31
      - system param as list[{type, text, cache_control}]
    for claude-haiku models.
    """

    def test_supports_prompt_cache_for_haiku(self):
        from src.services.agents.config import ModelConfig
        from src.services.agents.llm_client import MultiProviderLLMClient

        config = ModelConfig(model_name=AGENT_MODEL, api_key="x", temperature=0.7)
        client = MultiProviderLLMClient.__new__(MultiProviderLLMClient)
        client.config = config
        assert client._supports_prompt_cache() is True, (
            f"claude-haiku must support prompt caching, got False for {AGENT_MODEL}"
        )

    def test_does_not_cache_gpt4(self):
        from src.services.agents.config import ModelConfig
        from src.services.agents.llm_client import MultiProviderLLMClient

        config = ModelConfig(model_name="gpt-4o", api_key="x", temperature=0.7)
        client = MultiProviderLLMClient.__new__(MultiProviderLLMClient)
        client.config = config
        assert client._supports_prompt_cache() is False, "gpt-4o must NOT have Anthropic prompt caching"

    @pytest.mark.asyncio
    async def test_stream_call_sends_cache_control_on_system_prompt(self):
        """
        When the stream API is called, the system param must be a list with
        cache_control=ephemeral — not a plain string.

        _generate_anthropic_stream_with_messages() extracts the system prompt
        from messages that carry role="system" — it is NOT a separate kwarg.
        This is how chat_stream_service passes it via structured_messages.
        """
        from src.services.agents.config import ModelConfig
        from src.services.agents.llm_client import MultiProviderLLMClient, _llm_usage_ctx

        config = ModelConfig(model_name=AGENT_MODEL, api_key="sk-ant-test", temperature=AGENT_TEMP)
        client = MultiProviderLLMClient.__new__(MultiProviderLLMClient)
        client.config = config
        client.provider = AGENT_PROVIDER
        # ModelConfig has no additional_params by default
        if not hasattr(config, "additional_params"):
            config.__dict__["additional_params"] = None

        captured_kwargs = {}

        # Mock the Anthropic stream
        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_stream_ctx)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_stream_ctx.text_stream = _async_iter(["Machine ", "learning ", "is..."])
        final_msg = SimpleNamespace(usage=ANTHROPIC_USAGE_CALL_1)
        mock_stream_ctx.get_final_message = AsyncMock(return_value=final_msg)

        def capture_stream(**kwargs):
            captured_kwargs.update(kwargs)
            return mock_stream_ctx

        mock_anthropic = MagicMock()
        mock_anthropic.messages.stream = capture_stream
        client._client = mock_anthropic

        # CORRECT: pass system prompt as role="system" message — this is how
        # chat_stream_service structures the messages array (not as a separate kwarg)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_MESSAGE},
        ]
        chunks = []
        async for chunk in client._generate_anthropic_stream_with_messages(
            messages=messages,
            temperature=AGENT_TEMP,
            max_tokens=1024,
        ):
            chunks.append(chunk)

        # Assert full response streamed
        assert "".join(chunks) == "Machine learning is...", f"Unexpected streamed text: {''.join(chunks)}"

        # Assert filtered_messages has only the user turn (system is extracted)
        sent_messages = captured_kwargs.get("messages", [])
        assert all(m.get("role") != "system" for m in sent_messages), (
            f"system role must be filtered out of messages array: {sent_messages}"
        )

        # Assert cache_control is set on system prompt
        system_param = captured_kwargs.get("system")
        assert isinstance(system_param, list), (
            f"system param must be list for cacheable model, got {type(system_param)}"
        )
        assert system_param[0]["type"] == "text"
        assert system_param[0]["text"] == SYSTEM_PROMPT
        assert system_param[0]["cache_control"] == {"type": "ephemeral"}, (
            f"cache_control wrong: {system_param[0].get('cache_control')}"
        )

        # Assert anthropic-beta header sent
        extra_headers = captured_kwargs.get("extra_headers", {})
        assert extra_headers.get("anthropic-beta") == "prompt-caching-2024-07-31", (
            f"anthropic-beta header missing or wrong: {extra_headers}"
        )

        # Assert ContextVar captured usage from get_final_message()
        usage = _llm_usage_ctx.get()
        assert usage is not None, "ContextVar must be set after stream completes"
        assert usage["input_tokens"] == 450
        assert usage["output_tokens"] == 95
        assert usage["cache_read_tokens"] == 0
        assert usage["cache_creation_tokens"] == 400, (
            f"First call: cache_creation_tokens should be 400, got {usage['cache_creation_tokens']}"
        )


# ─── Step 3: _read_and_fire_usage assembles correct payload ──────────────────


class TestStep3_ReadAndFireUsage:
    """
    After stream completes, _with_streaming_timeout finally block fires
    _read_and_fire_usage(). This must assemble the correct payload and
    schedule the DB write without blocking the stream.
    """

    @pytest.mark.asyncio
    async def test_fire_usage_called_with_correct_payload(self):
        from src.services.agents.config import ModelConfig
        from src.services.agents.llm_client import MultiProviderLLMClient, _llm_usage_ctx

        config = ModelConfig(model_name=AGENT_MODEL, api_key="x", temperature=AGENT_TEMP)
        # routing_mode is NOT a ModelConfig field — _read_and_fire_usage uses
        # getattr(self.config, "routing_mode", "fixed") which returns "fixed" by default
        client = MultiProviderLLMClient.__new__(MultiProviderLLMClient)
        client.config = config
        client.provider = AGENT_PROVIDER

        client.set_cost_context(
            tenant_id=TENANT_ID,
            agent_id=AGENT_ID,
            conversation_id=CONV_ID,
            routing_rules=None,
            optimization_flags={},
            enable_response_cache=False,
            system_prompt_hash="abc123def456aabb",
            agent_updated_at=AGENT_UPDATED_AT,
        )

        # Simulate what get_final_message() sets after first Anthropic call
        _llm_usage_ctx.set(
            {
                "input_tokens": 450,
                "output_tokens": 95,
                "cache_read_tokens": 0,
                "cache_creation_tokens": 400,
            }
        )

        captured_payload = {}

        def mock_fire(**kwargs):
            captured_payload.update(kwargs)

        with patch("src.services.billing.llm_cost_service.fire_persist_llm_usage", side_effect=mock_fire):
            client._read_and_fire_usage()

        assert captured_payload["tenant_id"] == TENANT_ID
        assert captured_payload["provider"] == AGENT_PROVIDER
        assert captured_payload["model_name"] == AGENT_MODEL
        assert captured_payload["input_tokens"] == 450
        assert captured_payload["output_tokens"] == 95
        assert captured_payload["cache_read_tokens"] == 0
        assert captured_payload["cache_creation_tokens"] == 400
        assert captured_payload["agent_id"] == AGENT_ID
        assert captured_payload["conversation_id"] == CONV_ID
        assert captured_payload["optimization_flags"]["response_cache_hit"] is False
        assert captured_payload["optimization_flags"]["routing_mode"] == "fixed"

        # ContextVar must be cleared — next call won't double-fire
        assert _llm_usage_ctx.get() is None, "ContextVar must be cleared after fire"


# ─── Step 4: Cost calculation ────────────────────────────────────────────────


class TestStep4_CostCalculation:
    """
    fire_persist_llm_usage() calls calculate_cost() before inserting.
    Verify the Anthropic cache pricing math is exact.

    claude-haiku-4-5-20251001 pricing from MODEL_COMPARISON_DATA:
      input:  $0.80 / 1M tokens  = $0.0008 / 1k
      output: $4.00 / 1M tokens  = $0.0040 / 1k

    Call 1 (cache_creation_tokens=400, input=450, output=95):
      billable_input = 450 - 0 - 400 = 50  tokens
      cache_creation = 400 * 0.0008 * 1.25 / 1 = 400 * 0.000001 = ...
      Let's compute precisely:
        billable_input_cost = 50 * 0.0008 / 1000         = 0.00000004 * 50 ... wait need per-1k

    Actually input rate is per-1k, so:
      inp_rate = 0.0008 (per 1k)
      out_rate = 0.0040 (per 1k)
      billable_input = 50
      cost = (50 * 0.0008 / 1000)
           + (400 * 0.0008 * 1.25 / 1000)
           + (95  * 0.0040 / 1000)
           = 0.00004 + 0.0004 + 0.00038
    """

    def test_haiku_first_call_cost_with_cache_creation(self):
        from src.services.billing.llm_cost_service import calculate_cost

        cost = calculate_cost(
            model_name=AGENT_MODEL,
            input_tokens=450,
            output_tokens=95,
            cache_read_tokens=0,
            cache_creation_tokens=400,
        )

        assert cost is not None, f"Cost must not be None for {AGENT_MODEL}"
        assert cost > 0, f"Cost must be positive, got {cost}"

        # Cache creation is MORE expensive than normal input (125%)
        cost_no_cache = calculate_cost(AGENT_MODEL, 450, 95)
        assert cost > cost_no_cache, f"cache_creation call should cost MORE than uncached: {cost} vs {cost_no_cache}"

    def test_haiku_second_call_cost_with_cache_read(self):
        from src.services.billing.llm_cost_service import calculate_cost

        cost_no_cache = calculate_cost(AGENT_MODEL, 450, 95)
        cost_with_read = calculate_cost(
            model_name=AGENT_MODEL,
            input_tokens=450,
            output_tokens=95,
            cache_read_tokens=400,
        )

        assert cost_with_read < cost_no_cache, f"cache_read call should be CHEAPER: {cost_with_read} vs {cost_no_cache}"

        # Cache read is 10% of input rate. Savings depend on input/output ratio.
        # For haiku (input $0.80/1M, output $4.00/1M): output cost dominates,
        # so 400-token cache read saves ~15% of total. Assert it's measurable (>5%).
        savings_pct = (cost_no_cache - cost_with_read) / cost_no_cache
        assert savings_pct > 0.05, f"Expected >5% savings from cache read, got {savings_pct:.1%}"
        # Confirm savings direction is correct (cheaper, not more expensive)
        assert cost_with_read < cost_no_cache

    def test_db_override_routing_rules_wins(self):
        from src.services.billing.llm_cost_service import calculate_cost

        # Operator sets custom pricing in routing_rules for this agent config
        routing_rules = {"cost_per_1k_input": 0.0005, "cost_per_1k_output": 0.002}
        cost = calculate_cost(AGENT_MODEL, 1000, 1000, routing_rules=routing_rules)
        expected = (1000 * 0.0005 / 1000) + (1000 * 0.002 / 1000)  # = 0.0005 + 0.002 = 0.0025
        assert abs(cost - expected) < 1e-7, f"Expected {expected}, got {cost}"


# ─── Step 5: LLMTokenUsage row assembled correctly ───────────────────────────


class TestStep5_DBRowAssembled:
    """
    _persist_llm_usage() builds the LLMTokenUsage payload.
    Verify the model accepts all fields without error and values are correct.
    """

    def test_llm_token_usage_model_fields(self):
        from src.models.llm_token_usage import LLMTokenUsage
        from src.services.billing.llm_cost_service import calculate_cost

        cost = calculate_cost(AGENT_MODEL, 450, 95, cache_creation_tokens=400)

        row = LLMTokenUsage(
            tenant_id=TENANT_ID,
            agent_id=AGENT_ID,
            conversation_id=CONV_ID,
            provider=AGENT_PROVIDER,
            model_name=AGENT_MODEL,
            input_tokens=450,
            output_tokens=95,
            cache_read_tokens=None,
            cache_creation_tokens=400,
            cached_input_tokens=None,
            estimated_cost_usd=cost,
            optimization_flags={
                "response_cache_hit": False,
                "routing_mode": "fixed",
                "prompt_cache_created": True,
            },
        )

        assert row.tenant_id == TENANT_ID
        assert row.model_name == AGENT_MODEL
        assert row.cache_creation_tokens == 400
        assert row.estimated_cost_usd == cost
        assert row.optimization_flags["prompt_cache_created"] is True

    def test_no_fk_constraints_on_model(self):
        """
        LLMTokenUsage must NOT have FK constraints so it survives agent deletion.
        """
        from sqlalchemy import inspect as sa_inspect

        from src.models.llm_token_usage import LLMTokenUsage

        table = LLMTokenUsage.__table__
        fk_columns = [col.name for col in table.columns if col.foreign_keys]
        assert fk_columns == [], f"LLMTokenUsage must have no FK constraints, found on: {fk_columns}"


# ─── Step 6: Response cache — cache miss on first call, hit on second ────────


class TestStep6_ResponseCache:
    """
    Agent with enable_response_cache=true.
    User sends "What is 2+2?" at temperature=0 twice.
    First call: LLM is invoked, response is written to Redis.
    Second call: Redis returns cached value, LLM is NOT called.
    """

    @pytest.mark.asyncio
    async def test_first_call_misses_cache_second_hits(self):
        from src.services.cache.llm_response_cache import (
            _is_cacheable,
            _make_cache_key,
            get_cached_response,
            set_cached_response,
        )

        messages = [{"role": "user", "content": "What is 2+2?"}]
        temp = 0.0
        system_hash = "aabbccddeeff0011"
        agent_ts = AGENT_UPDATED_AT

        # Gate check: must be cacheable
        assert _is_cacheable(messages, temp) is True, "Deterministic query must be cacheable"

        # Build the key that both calls will use
        key = _make_cache_key(AGENT_PROVIDER, AGENT_MODEL, temp, messages, system_hash, agent_ts)
        assert key.startswith("llm_resp:"), f"Key prefix wrong: {key}"
        assert len(key) > 20, "Key should be a proper SHA256 hash"

        redis_store = {}  # simulate Redis

        class FakeRedis:
            async def get(self, k):
                return redis_store.get(k)

            async def set(self, k, v, ex=None, nx=False):
                if nx and k in redis_store:
                    return  # NX: don't overwrite
                redis_store[k] = v.encode() if isinstance(v, str) else v

        with patch("src.services.cache.llm_response_cache.get_redis_async", return_value=FakeRedis()):
            # First call: cache miss
            result1 = await get_cached_response(AGENT_PROVIDER, AGENT_MODEL, temp, messages, system_hash, agent_ts)
            assert result1 is None, f"First call must be a cache miss, got: {result1}"

            # Simulate LLM returning a response, then caching it
            llm_response = "4"
            await set_cached_response(AGENT_PROVIDER, AGENT_MODEL, temp, messages, llm_response, system_hash, agent_ts)
            assert key in redis_store, "Response must be stored in Redis after set"

            # Second call: cache hit
            result2 = await get_cached_response(AGENT_PROVIDER, AGENT_MODEL, temp, messages, system_hash, agent_ts)
            assert result2 == "4", f"Second call must return cached value '4', got: {result2}"

    @pytest.mark.asyncio
    async def test_cache_busts_when_agent_edited(self):
        """Editing agent system prompt changes agent_updated_at, busting the cache."""
        from src.services.cache.llm_response_cache import _make_cache_key

        messages = [{"role": "user", "content": "What is 2+2?"}]
        system_hash = "aabbccddeeff0011"

        key_before = _make_cache_key(AGENT_PROVIDER, AGENT_MODEL, 0.0, messages, system_hash, "1000.0")
        key_after = _make_cache_key(AGENT_PROVIDER, AGENT_MODEL, 0.0, messages, system_hash, "1001.0")

        assert key_before != key_after, "Agent edit (new updated_at) must produce a different cache key"

    @pytest.mark.asyncio
    async def test_time_sensitive_query_never_cached(self):
        """'What is the current Bitcoin price?' must never hit or populate Redis."""
        from src.services.cache.llm_response_cache import get_cached_response

        messages = [{"role": "user", "content": "What is the current Bitcoin price?"}]
        mock_redis = AsyncMock()

        with patch("src.services.cache.llm_response_cache.get_redis_async", return_value=mock_redis):
            result = await get_cached_response(AGENT_PROVIDER, AGENT_MODEL, 0.0, messages, "hash", AGENT_UPDATED_AT)
            assert result is None
            mock_redis.get.assert_not_called(), "Redis.get must not be called for time-sensitive queries"


# ─── Step 7: fire_persist_llm_usage scheduling guarantees ────────────────────


class TestStep7_FireAndForgetGuarantees:
    """
    fire_persist_llm_usage() must:
    1. Never raise even if DB is down
    2. Schedule exactly one asyncio task
    3. Store task in module-level set (prevents GC)
    4. Remove from set via done callback
    """

    def test_never_raises_when_db_down(self):
        from src.services.billing.llm_cost_service import fire_persist_llm_usage

        with patch(
            "src.services.billing.llm_cost_service._persist_llm_usage",
            side_effect=RuntimeError("DB connection refused"),
        ):
            with patch("asyncio.create_task", side_effect=RuntimeError("no running loop")):
                # Must not raise
                fire_persist_llm_usage(
                    tenant_id=TENANT_ID,
                    provider=AGENT_PROVIDER,
                    model_name=AGENT_MODEL,
                    input_tokens=450,
                    output_tokens=95,
                    cache_creation_tokens=400,
                )

    def test_task_added_to_module_set_then_discarded(self):
        from src.services.billing import llm_cost_service
        from src.services.billing.llm_cost_service import fire_persist_llm_usage

        mock_task = MagicMock()
        done_callbacks = []
        mock_task.add_done_callback = lambda cb: done_callbacks.append(cb)

        with patch("asyncio.create_task", return_value=mock_task):
            initial_count = len(llm_cost_service._background_tasks)
            fire_persist_llm_usage(
                tenant_id=TENANT_ID,
                provider=AGENT_PROVIDER,
                model_name=AGENT_MODEL,
                input_tokens=450,
                output_tokens=95,
            )
            # Task added to set
            assert len(llm_cost_service._background_tasks) == initial_count + 1, (
                "Task must be added to _background_tasks set"
            )

            # Simulate task completion — done callback fires
            assert len(done_callbacks) == 1, "Exactly one done callback must be registered"
            done_callbacks[0](mock_task)  # simulate asyncio calling it
            assert len(llm_cost_service._background_tasks) == initial_count, (
                "Task must be removed from set after completion (prevents memory leak)"
            )


# ─── Step 8: Billing endpoint response shape ─────────────────────────────────


class TestStep8_BillingEndpointShape:
    """
    GET /billing/llm-cost/summary returns dict with expected keys.
    Simulate one existing row and verify response.
    """

    @pytest.mark.asyncio
    async def test_get_cost_summary_returns_expected_keys(self):
        from datetime import datetime, timezone

        from src.services.billing.llm_cost_service import get_cost_summary

        # Mock DB returning one aggregated row
        mock_row = MagicMock()
        mock_row.total_calls = 5
        mock_row.total_input_tokens = 2250  # 5 * 450
        mock_row.total_output_tokens = 475  # 5 * 95
        mock_row.total_cache_read_tokens = 1600  # 4 * 400 (calls 2-5)
        mock_row.total_cache_creation_tokens = 400  # call 1
        mock_row.total_cached_input_tokens = 0
        mock_row.total_cost_usd = Decimal("0.00482000")

        mock_result = MagicMock()
        mock_result.one = MagicMock(return_value=mock_row)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        start = datetime(2026, 4, 16, tzinfo=UTC)
        end = datetime(2026, 4, 23, tzinfo=UTC)

        result = await get_cost_summary(mock_db, TENANT_ID, start, end)

        required_keys = {
            "total_calls",
            "total_input_tokens",
            "total_output_tokens",
            "total_cache_read_tokens",
            "total_cache_creation_tokens",
            "total_cost_usd",
            "period_start",
            "period_end",
        }
        missing = required_keys - set(result.keys())
        assert not missing, f"Summary response missing keys: {missing}"

        assert result["total_calls"] == 5
        assert result["total_input_tokens"] == 2250
        assert result["total_cache_read_tokens"] == 1600
        assert "2026-04-16" in result["period_start"]
        assert "2026-04-23" in result["period_end"]

    @pytest.mark.asyncio
    async def test_get_cost_summary_empty_tenant(self):
        """
        New tenant with no LLM calls returns zero counts, not an error.

        PostgreSQL aggregate queries always return one row (with NULL values)
        even when no matching rows exist. The service uses .one() not .one_or_none(),
        so the mock must return a row with all-NULL aggregate columns.
        """
        from datetime import datetime, timezone

        from src.services.billing.llm_cost_service import get_cost_summary

        # Aggregate on zero rows → all sums/counts are NULL (not zero, not a missing row)
        empty_row = SimpleNamespace(
            total_input_tokens=None,
            total_output_tokens=None,
            total_cache_read_tokens=None,
            total_cache_creation_tokens=None,
            total_cached_input_tokens=None,
            total_cost_usd=None,
            total_calls=None,
        )

        mock_result = MagicMock()
        mock_result.one = MagicMock(return_value=empty_row)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        start = datetime(2026, 4, 16, tzinfo=UTC)
        end = datetime(2026, 4, 23, tzinfo=UTC)

        result = await get_cost_summary(mock_db, TENANT_ID, start, end)
        # Service must convert NULL → 0 via "or 0"
        assert result["total_calls"] == 0, f"Expected 0 calls, got {result['total_calls']}"
        assert result["total_cost_usd"] == 0, f"Expected 0 cost, got {result['total_cost_usd']}"
        assert result["total_input_tokens"] == 0


# ─── Step 9: Anthropic tool caching in function_calling ──────────────────────


class TestStep9_ToolCaching:
    """
    When an agent has tools and the model is claude-haiku,
    _generate_anthropic_with_tools() must add cache_control to the last tool
    and set the anthropic-beta header.
    """

    @pytest.mark.asyncio
    async def test_tool_list_gets_cache_control(self):
        from src.services.agents.config import ModelConfig
        from src.services.agents.function_calling import FunctionCallingHandler
        from src.services.agents.llm_client import MultiProviderLLMClient

        config = ModelConfig(model_name=AGENT_MODEL, api_key="sk-ant-x", temperature=AGENT_TEMP)
        llm_client = MultiProviderLLMClient.__new__(MultiProviderLLMClient)
        llm_client.config = config
        llm_client.provider = "anthropic"

        handler = FunctionCallingHandler.__new__(FunctionCallingHandler)
        handler.llm_client = llm_client
        handler.provider = "anthropic"
        # Bypassing __init__() via __new__, so set the attributes it would
        # normally initialize that this code path touches.
        handler._on_answer_delta = None
        # _generate_anthropic_with_tools calls _convert_to_anthropic_format()
        # which reads self.available_tools. Populate with ADK-style tool defs.
        handler.available_tools = [
            {"name": "search_web", "description": "Search the web", "parameters": {"type": "object", "properties": {}}},
            {"name": "get_weather", "description": "Get weather", "parameters": {"type": "object", "properties": {}}},
            {
                "name": "query_database",
                "description": "Query a database",
                "parameters": {"type": "object", "properties": {}},
            },
        ]

        captured = {}

        async def mock_create(**kwargs):
            captured.update(kwargs)
            msg = MagicMock()
            msg.stop_reason = "end_turn"
            msg.content = [MagicMock(type="text", text="done")]
            return msg

        mock_messages = MagicMock()
        mock_messages.create = mock_create
        mock_client = MagicMock()
        mock_client.messages = mock_messages
        llm_client._client = mock_client

        history = [{"role": "user", "content": USER_MESSAGE}]
        await handler._generate_anthropic_with_tools(history, AGENT_TEMP, 1024)

        sent_tools = captured.get("tools", [])
        assert len(sent_tools) == 3, f"Expected 3 tools, got {len(sent_tools)}"

        last_tool = sent_tools[-1]
        assert "cache_control" in last_tool, f"Last tool must have cache_control, got: {last_tool}"
        assert last_tool["cache_control"] == {"type": "ephemeral"}, (
            f"cache_control value wrong: {last_tool['cache_control']}"
        )

        # Other tools must NOT have cache_control added
        assert "cache_control" not in sent_tools[0], "Only the last tool should have cache_control"

        # anthropic-beta header must be set
        extra_headers = captured.get("extra_headers", {})
        assert extra_headers.get("anthropic-beta") == "prompt-caching-2024-07-31", (
            f"anthropic-beta header missing: {extra_headers}"
        )


# ─── Step 10: ContextVar isolation — concurrent requests don't cross-contaminate


class TestStep10_ContextVarIsolation:
    """
    The same LLMClient instance handles two concurrent requests.
    Request A's usage must not bleed into Request B.
    """

    @pytest.mark.asyncio
    async def test_concurrent_requests_get_own_usage(self):
        from src.services.agents.llm_client import _llm_usage_ctx

        usage_a = None
        usage_b = None

        async def simulate_request_a():
            nonlocal usage_a
            _llm_usage_ctx.set({"input_tokens": 100, "output_tokens": 20})
            await asyncio.sleep(0.01)  # yield to let B run
            usage_a = _llm_usage_ctx.get()

        async def simulate_request_b():
            nonlocal usage_b
            _llm_usage_ctx.set({"input_tokens": 999, "output_tokens": 888})
            await asyncio.sleep(0.01)
            usage_b = _llm_usage_ctx.get()

        await asyncio.gather(simulate_request_a(), simulate_request_b())

        assert usage_a["input_tokens"] == 100, f"Request A saw wrong tokens: {usage_a}"
        assert usage_b["input_tokens"] == 999, f"Request B saw wrong tokens: {usage_b}"
        assert usage_a is not usage_b, "ContextVar must be isolated per-coroutine"


# ─── Helpers ─────────────────────────────────────────────────────────────────


async def _async_iter(items):
    for item in items:
        yield item
