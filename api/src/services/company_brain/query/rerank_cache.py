"""
Redis rerank cache for Company Brain.

Problem: At 100 concurrent agents, each agent independently runs the full
retrieve → assemble pipeline. The backend can't sustain this (melts at ~10).

Solution: Cache assembled results by (tenant_id, query_hash, filter_hash) with
a 60s TTL. At 100 agents, 99% of queries hit cache after the first miss.

Cache key:
  brain:rc:{tenant_id}:{md5(query + canonical_filter_str)}

The assembled dict (context, citations, token_count, result_count) is stored
as JSON. Results are re-hydrated on hit.

TTL is configurable via COMPANY_BRAIN_RERANK_CACHE_TTL (default: 60s).
Set to 0 to disable caching entirely.
"""

import hashlib
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

_CACHE_KEY_PREFIX = "brain:rc"


def _cache_key(tenant_id: str, query: str, filter_repr: str) -> str:
    digest = hashlib.md5(f"{query}|{filter_repr}".encode()).hexdigest()
    return f"{_CACHE_KEY_PREFIX}:{tenant_id}:{digest}"


def _filter_repr(intent_dict: dict[str, Any]) -> str:
    """Stable string representation of the parts of intent that affect results."""
    parts = {
        "domains": sorted(intent_dict.get("domains") or []),
        "source_types": sorted(intent_dict.get("source_types") or []),
        "tiers": sorted(intent_dict.get("tiers") or ["hot"]),
        "time_from": intent_dict.get("time_from"),
        "time_to": intent_dict.get("time_to"),
    }
    return json.dumps(parts, sort_keys=True)


def _cache_ttl() -> int:
    try:
        from src.config.settings import get_settings

        return getattr(get_settings(), "company_brain_rerank_cache_ttl", 60)
    except Exception:
        return 60


async def get_cached(
    tenant_id: str,
    query: str,
    intent_dict: dict[str, Any],
) -> dict[str, Any] | None:
    """Return cached assembled result or None on miss/error."""
    ttl = _cache_ttl()
    if ttl <= 0:
        return None
    try:
        from src.config.redis import get_redis_async

        redis = get_redis_async()
        key = _cache_key(tenant_id, query, _filter_repr(intent_dict))
        raw = await redis.get(key)
        if raw:
            logger.debug("Brain rerank cache HIT key=%s", key)
            return json.loads(raw)
    except Exception as exc:
        logger.debug("Brain rerank cache read error (%s) — cache miss", exc)
    return None


async def set_cached(
    tenant_id: str,
    query: str,
    intent_dict: dict[str, Any],
    assembled: dict[str, Any],
) -> None:
    """Store assembled result in cache. Silently skips on error."""
    ttl = _cache_ttl()
    if ttl <= 0:
        return
    try:
        from src.config.redis import get_redis_async

        redis = get_redis_async()
        key = _cache_key(tenant_id, query, _filter_repr(intent_dict))
        await redis.setex(key, ttl, json.dumps(assembled, default=str))
        logger.debug("Brain rerank cache SET key=%s ttl=%ds", key, ttl)
    except Exception as exc:
        logger.debug("Brain rerank cache write error (%s) — skipping", exc)
