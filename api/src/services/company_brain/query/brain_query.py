"""
Unified Company Brain query entrypoint.

Call this from agents, tools, and the chat pipeline:

    from src.services.company_brain.query.brain_query import query_brain

    result = await query_brain(
        tenant_id="...",
        query="What are the latest trading anomalies?",
        limit=20,
        db=db,         # AsyncSession — needed for domain resolution
    )
    # result = {"context": str, "citations": [...], "token_count": int, "result_count": int}

Pipeline:
  1. Classify query → QueryIntent (tenant-domain-aware LLM router)
  2. Check rerank cache (60s TTL) — return immediately on hit
  3. Retrieve: parallel fan-out by domain → KnowledgeBase searches
  4. Assemble: RRF rerank + dedup + token-budget trim + citations
  5. Write to rerank cache
  6. Return assembled context
"""

import dataclasses
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def query_brain(
    tenant_id: str,
    query: str,
    limit: int = 20,
    db: Any | None = None,
    domains: list[str] | None = None,  # override: restrict to these domain slugs
    tiers: list[str] | None = None,  # override: ["hot"] | ["hot", "warm"]
    max_tokens: int | None = None,
) -> dict[str, Any]:
    """
    Full Company Brain query pipeline with caching.

    Returns:
        {
          "context":      str,           # formatted context block ready for LLM prompt
          "citations":    list[dict],    # source citations for frontend display
          "token_count":  int,
          "result_count": int,
          "cache_hit":    bool,
        }
    """
    from src.services.company_brain.query.assembler import assemble
    from src.services.company_brain.query.rerank_cache import get_cached, set_cached
    from src.services.company_brain.query.retriever import retrieve
    from src.services.company_brain.query.router import classify_query

    # 1. Classify
    intent = await classify_query(query=query, tenant_id=tenant_id, db=db)

    # Apply caller overrides
    if domains:
        intent.domains = domains
    if tiers:
        intent.tiers = tiers

    intent_dict = dataclasses.asdict(intent)

    # 2. Cache check
    cached = await get_cached(tenant_id, query, intent_dict)
    if cached is not None:
        cached["cache_hit"] = True
        return cached

    # 3. Retrieve
    results = await retrieve(
        tenant_id=tenant_id,
        query=query,
        intent=intent,
        limit=limit,
        db=db,
    )

    # 4. Assemble
    assembled = assemble(results=results, query=query, max_tokens=max_tokens)

    # 5. Cache the assembled result
    await set_cached(tenant_id, query, intent_dict, assembled)

    assembled["cache_hit"] = False
    return assembled
