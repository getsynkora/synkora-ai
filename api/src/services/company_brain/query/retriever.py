"""
Multi-domain parallel retriever for Company Brain.

Flow:
  1. Resolve domains from QueryIntent (loads tenant's BrainDomain rows via cache)
  2. For each active domain, resolve its knowledge_base_ids from DataSource rows
  3. Fan out searches in parallel across all domains (asyncio.gather)
  4. Weight results by domain.rerank_weight before returning to assembler

When a tenant has no domains configured, falls back to the legacy source_type
fan-out behaviour so existing deployments keep working without migration.

Concurrency limit: max 8 parallel domain searches to protect the search backend.
"""

import asyncio
import logging
from typing import Any

from src.services.company_brain.search.base import SearchFilter, SearchResult
from src.services.company_brain.search.factory import get_search_backend

from .router import QueryIntent

logger = logging.getLogger(__name__)

_DEFAULT_PER_DOMAIN_LIMIT = 10
_MAX_PARALLEL_DOMAINS = 8  # semaphore cap — protects backend at 100-agent load


async def retrieve(
    tenant_id: str,
    query: str,
    intent: QueryIntent,
    limit: int = 20,
    db: Any | None = None,
) -> list[SearchResult]:
    """
    Parallel domain fan-out retrieval.

    Args:
        tenant_id:  Scopes all searches to this tenant.
        query:      User's natural language query.
        intent:     Routing intent from the query router.
        limit:      Total results to return after merging.
        db:         Async DB session — needed to resolve domain → KB mappings.

    Returns:
        List of SearchResult sorted by weighted score (descending), capped at limit.
    """
    # --- Domain-aware path (tenant has domains configured) ---
    if db is not None:
        try:
            from src.services.company_brain.domain_service import (
                get_domain_source_types,
                get_domains_cached,
            )

            all_domains = await get_domains_cached(tenant_id, db)
            active_domains = [d for d in all_domains if d["is_active"]]

            if active_domains:
                # Filter to requested domains if intent specified any
                if intent.domains:
                    slug_set = set(intent.domains)
                    target_domains = [d for d in active_domains if d["slug"] in slug_set]
                else:
                    target_domains = active_domains

                if target_domains:
                    return await _fan_out_by_domain(
                        tenant_id=tenant_id,
                        query=query,
                        intent=intent,
                        domains=target_domains,
                        limit=limit,
                        db=db,
                        get_source_types_fn=get_domain_source_types,
                    )
        except Exception as exc:
            logger.warning("Domain-aware retrieval failed, falling back to source_type mode: %s", exc)

    # --- Legacy source-type path (no domains, or domain load failed) ---
    return await _fan_out_by_source_type(tenant_id, query, intent, limit)


# ---------------------------------------------------------------------------
# Domain fan-out
# ---------------------------------------------------------------------------


async def _fan_out_by_domain(
    tenant_id: str,
    query: str,
    intent: QueryIntent,
    domains: list[dict],
    limit: int,
    db: Any,
    get_source_types_fn: Any,
) -> list[SearchResult]:
    """Search each domain in parallel, weight results, merge and sort."""
    semaphore = asyncio.Semaphore(_MAX_PARALLEL_DOMAINS)
    per_domain = max(_DEFAULT_PER_DOMAIN_LIMIT, limit)

    async def search_domain(domain: dict) -> tuple[list[SearchResult], float]:
        async with semaphore:
            source_types = await get_source_types_fn(domain["id"], tenant_id, db)
            if not source_types:
                # Domain exists but has no active data sources yet
                return [], 1.0

            filters = SearchFilter(
                source_types=source_types,
                time_from=intent.time_from,
                time_to=intent.time_to,
                storage_tiers=intent.tiers,
            )
            results = await _search_with_filter(tenant_id, query, filters, per_domain)
            return results, domain.get("rerank_weight", 1.0)

    raw = await asyncio.gather(
        *[search_domain(d) for d in domains],
        return_exceptions=True,
    )

    all_results: list[SearchResult] = []
    for domain, outcome in zip(domains, raw, strict=False):
        if isinstance(outcome, Exception):
            logger.warning("Domain search failed for '%s': %s", domain["slug"], outcome)
            continue
        results, weight = outcome
        # Apply domain weight to each result score
        for r in results:
            r.score = r.score * weight
        all_results.extend(results)

    all_results.sort(key=lambda r: r.score, reverse=True)
    return all_results[:limit]


# ---------------------------------------------------------------------------
# Legacy source-type fan-out (unchanged behaviour for undomained deployments)
# ---------------------------------------------------------------------------


async def _fan_out_by_source_type(
    tenant_id: str,
    query: str,
    intent: QueryIntent,
    limit: int,
) -> list[SearchResult]:
    source_types = intent.source_types or _all_source_types()
    filters = SearchFilter(
        source_types=source_types,
        time_from=intent.time_from,
        time_to=intent.time_to,
        storage_tiers=intent.tiers,
    )

    if len(source_types) <= 1:
        return await _search_with_filter(tenant_id, query, filters, limit)

    per_source = max(_DEFAULT_PER_DOMAIN_LIMIT, limit)
    semaphore = asyncio.Semaphore(_MAX_PARALLEL_DOMAINS)

    async def search_one(source_type: str) -> list[SearchResult]:
        async with semaphore:
            f = SearchFilter(
                source_types=[source_type],
                time_from=intent.time_from,
                time_to=intent.time_to,
                storage_tiers=intent.tiers,
            )
            return await _search_with_filter(tenant_id, query, f, per_source)

    outcomes = await asyncio.gather(*[search_one(s) for s in source_types], return_exceptions=True)
    all_results: list[SearchResult] = []
    for source_type, outcome in zip(source_types, outcomes, strict=False):
        if isinstance(outcome, Exception):
            logger.warning("Source search failed for '%s': %s", source_type, outcome)
        else:
            all_results.extend(outcome)

    if intent.use_pageindex:
        all_results.extend(await _fetch_pageindex(tenant_id, query, intent))

    all_results.sort(key=lambda r: r.score, reverse=True)
    return all_results[:limit]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


async def _search_with_filter(
    tenant_id: str,
    query: str,
    filters: SearchFilter,
    limit: int,
    knowledge_base_id: str | None = None,
) -> list[SearchResult]:
    try:
        backend = get_search_backend()
        resp = await backend.search(
            tenant_id=tenant_id, knowledge_base_id=knowledge_base_id, query=query, filters=filters, limit=limit
        )
        return resp.results
    except Exception as exc:
        logger.warning("Search failed (filters=%s): %s", filters.source_types, exc)
        return []


async def _fetch_pageindex(
    tenant_id: str,
    query: str,
    intent: QueryIntent,
) -> list[SearchResult]:
    """Placeholder for deep-doc PageIndex traversal."""
    logger.debug("PageIndex routing requested but not yet implemented — skipping")
    return []


def _all_source_types() -> list[str]:
    return [
        "slack",
        "github",
        "gitlab",
        "jira",
        "clickup",
        "notion",
        "confluence",
        "gmail",
        "google_drive",
        "linear",
    ]
