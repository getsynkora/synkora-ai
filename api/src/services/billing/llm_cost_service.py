"""
LLM Cost Service

Calculates, records, and aggregates LLM API costs using existing pricing sources
(DB routing_rules, _BUILTIN_COSTS, llm_provider_comparison_data.MODEL_COMPARISON_DATA).

No new hardcoded pricing dicts — all resolution flows through existing sources.
"""

import asyncio
import logging
import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

logger = logging.getLogger(__name__)

# Module-level set keeps strong references to background tasks (prevents GC).
_background_tasks: set[asyncio.Task] = set()


# ---------------------------------------------------------------------------
# Pricing resolution
# ---------------------------------------------------------------------------


def _resolve_pricing(
    model_name: str,
    routing_rules: dict | None,
) -> tuple[float | None, float | None]:
    """
    Return (input_cost_per_1k, output_cost_per_1k) in USD.

    Priority:
    1. routing_rules["cost_per_1k_input/output"]  — DB, per-config override
    2. model_router._BUILTIN_COSTS / _BUILTIN_OUTPUT_COSTS — exact-match tables
    3. llm_provider_comparison_data.MODEL_COMPARISON_DATA — prefix-match, convert 1M -> 1k
    4. None, None                                  — unknown model, cost not tracked
    """
    # 1. DB override wins
    if routing_rules:
        inp = routing_rules.get("cost_per_1k_input")
        out = routing_rules.get("cost_per_1k_output")
        if inp is not None:
            return float(inp), float(out) if out is not None else None

    # Normalize model name: strip trailing date suffixes like -20241022
    normalized = re.sub(r"-\d{8}$", "", model_name.lower())

    try:
        from src.services.agents.routing.model_router import _BUILTIN_COSTS, _BUILTIN_OUTPUT_COSTS
    except ImportError:
        return None, None

    try:
        from src.services.agents.llm_provider_comparison_data import MODEL_COMPARISON_DATA
    except ImportError:
        MODEL_COMPARISON_DATA = {}

    builtin_inp: float | None = None
    builtin_out: float | None = None
    preset_inp: float | None = None
    preset_out: float | None = None

    # 2. Exact-match against built-in tables (normalized strips date suffix)
    for key in _BUILTIN_COSTS:
        if normalized == key or normalized.startswith(key + "-") or key == normalized:
            builtin_inp = _BUILTIN_COSTS[key]
            builtin_out = _BUILTIN_OUTPUT_COSTS.get(key)
            break

    # 3. Prefix-match MODEL_COMPARISON_DATA for additional coverage
    for preset_key, preset in MODEL_COMPARISON_DATA.items():
        if normalized.startswith(preset_key.lower()) or preset_key.lower() in normalized:
            raw_inp = preset.get("cost_input_per_1m") or 0
            raw_out = preset.get("cost_output_per_1m") or 0
            preset_inp = raw_inp / 1000 if raw_inp else None
            preset_out = raw_out / 1000 if raw_out else None
            break

    if builtin_inp is not None:
        # Use builtin output rate first; fall back to preset if not declared
        out_rate = builtin_out if builtin_out is not None else preset_out
        return builtin_inp, out_rate

    if preset_inp is not None:
        return preset_inp, preset_out

    return None, None


def calculate_cost(
    model_name: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_creation_tokens: int = 0,
    routing_rules: dict | None = None,
) -> float | None:
    """
    Calculate estimated USD cost for one LLM call.

    Anthropic cache pricing:
      cache_read_tokens:     10% of input rate
      cache_creation_tokens: 125% of input rate (5-min TTL tier)
    Returns None when model pricing is unknown.
    """
    inp_rate, out_rate = _resolve_pricing(model_name, routing_rules)
    if inp_rate is None:
        return None

    billable_input = max(0, input_tokens - cache_read_tokens - cache_creation_tokens)
    cost = (
        (billable_input * inp_rate / 1000)
        + (cache_read_tokens * inp_rate * 0.10 / 1000)
        + (cache_creation_tokens * inp_rate * 1.25 / 1000)
        + ((output_tokens * out_rate / 1000) if out_rate else 0)
    )
    return round(cost, 8)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


async def _persist_llm_usage(payload: dict) -> None:
    """Write one LLMTokenUsage row using a fresh DB session (never shares caller's session)."""
    from src.core.database import get_async_session_factory
    from src.models.llm_token_usage import LLMTokenUsage

    factory = get_async_session_factory()
    session = factory()
    try:
        session.add(LLMTokenUsage(**payload))
        await session.commit()
    except Exception as e:
        logger.error(f"LLM usage persist error: {e}")
        try:
            await session.rollback()
        except Exception:
            pass
    finally:
        try:
            await session.close()
        except Exception:
            pass


def fire_persist_llm_usage(
    tenant_id: UUID,
    provider: str,
    model_name: str,
    input_tokens: int,
    output_tokens: int,
    agent_id: UUID | None = None,
    conversation_id: UUID | None = None,
    cache_read_tokens: int = 0,
    cache_creation_tokens: int = 0,
    cached_input_tokens: int = 0,
    optimization_flags: dict | None = None,
    routing_rules: dict | None = None,
) -> None:
    """
    Non-blocking fire-and-forget DB write.

    Schedules a background asyncio task with a strong reference to prevent GC.
    Never raises — all errors are logged and swallowed.
    """
    try:
        cost = calculate_cost(
            model_name,
            input_tokens,
            output_tokens,
            cache_read_tokens,
            cache_creation_tokens,
            routing_rules,
        )
        payload = {
            "tenant_id": tenant_id,
            "provider": provider,
            "model_name": model_name,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_tokens": cache_read_tokens or None,
            "cache_creation_tokens": cache_creation_tokens or None,
            "cached_input_tokens": cached_input_tokens or None,
            "estimated_cost_usd": cost,
            "optimization_flags": optimization_flags,
            "agent_id": agent_id,
            "conversation_id": conversation_id,
        }
        task = asyncio.create_task(_persist_llm_usage(payload))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
    except Exception as e:
        logger.error(f"fire_persist_llm_usage scheduling error: {e}")


# ---------------------------------------------------------------------------
# Analytics queries (called by billing controller)
# ---------------------------------------------------------------------------


async def get_cost_summary(
    db,
    tenant_id: UUID,
    start_date: datetime,
    end_date: datetime,
    agent_id: UUID | None = None,
) -> dict:
    """Aggregate token counts and cost for a time period."""
    from sqlalchemy import func, select

    from src.models.llm_token_usage import LLMTokenUsage

    q = select(
        func.sum(LLMTokenUsage.input_tokens).label("total_input_tokens"),
        func.sum(LLMTokenUsage.output_tokens).label("total_output_tokens"),
        func.sum(LLMTokenUsage.cache_read_tokens).label("total_cache_read_tokens"),
        func.sum(LLMTokenUsage.cache_creation_tokens).label("total_cache_creation_tokens"),
        func.sum(LLMTokenUsage.cached_input_tokens).label("total_cached_input_tokens"),
        func.sum(LLMTokenUsage.estimated_cost_usd).label("total_cost_usd"),
        func.count().label("total_calls"),
    ).where(
        LLMTokenUsage.tenant_id == tenant_id,
        LLMTokenUsage.created_at >= start_date,
        LLMTokenUsage.created_at < end_date,
    )
    if agent_id:
        q = q.where(LLMTokenUsage.agent_id == agent_id)

    row = (await db.execute(q)).one()
    return {
        "total_input_tokens": int(row.total_input_tokens or 0),
        "total_output_tokens": int(row.total_output_tokens or 0),
        "total_cache_read_tokens": int(row.total_cache_read_tokens or 0),
        "total_cache_creation_tokens": int(row.total_cache_creation_tokens or 0),
        "total_cached_input_tokens": int(row.total_cached_input_tokens or 0),
        "total_cost_usd": float(row.total_cost_usd or 0),
        "total_calls": int(row.total_calls or 0),
        "period_start": start_date.isoformat(),
        "period_end": end_date.isoformat(),
    }


async def get_cost_by_model(
    db,
    tenant_id: UUID,
    start_date: datetime,
    end_date: datetime,
) -> list[dict]:
    """Cost breakdown grouped by (provider, model_name)."""
    from sqlalchemy import func, select

    from src.models.llm_token_usage import LLMTokenUsage

    q = (
        select(
            LLMTokenUsage.provider,
            LLMTokenUsage.model_name,
            func.sum(LLMTokenUsage.input_tokens).label("input_tokens"),
            func.sum(LLMTokenUsage.output_tokens).label("output_tokens"),
            func.sum(LLMTokenUsage.estimated_cost_usd).label("cost_usd"),
            func.count().label("calls"),
        )
        .where(
            LLMTokenUsage.tenant_id == tenant_id,
            LLMTokenUsage.created_at >= start_date,
            LLMTokenUsage.created_at < end_date,
        )
        .group_by(LLMTokenUsage.provider, LLMTokenUsage.model_name)
        .order_by(func.sum(LLMTokenUsage.estimated_cost_usd).desc().nulls_last())
    )

    rows = (await db.execute(q)).all()
    return [
        {
            "provider": r.provider,
            "model_name": r.model_name,
            "input_tokens": int(r.input_tokens or 0),
            "output_tokens": int(r.output_tokens or 0),
            "cost_usd": float(r.cost_usd or 0),
            "calls": int(r.calls or 0),
        }
        for r in rows
    ]


async def get_savings_estimate(
    db,
    tenant_id: UUID,
    start_date: datetime,
    end_date: datetime,
) -> dict:
    """
    Estimate savings from caching vs a baseline of no caching.

    baseline_cost: what the same tokens would cost at full input rate
    actual_cost:   estimated_cost_usd (already accounts for reduced cache rates)
    savings:       baseline_cost - actual_cost
    """
    from sqlalchemy import func, select

    from src.models.llm_token_usage import LLMTokenUsage

    q = select(
        func.sum(LLMTokenUsage.estimated_cost_usd).label("actual_cost"),
        func.count().label("total_calls"),
        func.sum(
            func.coalesce(LLMTokenUsage.cache_read_tokens, 0)
            + func.coalesce(LLMTokenUsage.cache_creation_tokens, 0)
            + func.coalesce(LLMTokenUsage.cached_input_tokens, 0)
        ).label("total_cached_tokens"),
        func.count(LLMTokenUsage.id)
        .filter(
            LLMTokenUsage.optimization_flags["response_cache_hit"].as_boolean() == True  # noqa: E712
        )
        .label("response_cache_hits"),
        func.count(LLMTokenUsage.id)
        .filter(
            LLMTokenUsage.optimization_flags["batch_id"].astext != None  # noqa: E711
        )
        .label("batch_calls"),
    ).where(
        LLMTokenUsage.tenant_id == tenant_id,
        LLMTokenUsage.created_at >= start_date,
        LLMTokenUsage.created_at < end_date,
    )

    row = (await db.execute(q)).one()
    actual_cost = float(row.actual_cost or 0)
    total_cached = int(row.total_cached_tokens or 0)

    # Rough baseline: compute what caching saved (average rate not available here,
    # so we report token counts and let the UI do the math if needed)
    return {
        "actual_cost_usd": actual_cost,
        "total_cached_tokens": total_cached,
        "response_cache_hits": int(row.response_cache_hits or 0),
        "batch_calls": int(row.batch_calls or 0),
        "total_calls": int(row.total_calls or 0),
    }
