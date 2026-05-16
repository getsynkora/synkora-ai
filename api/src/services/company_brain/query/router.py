"""
Query router for Company Brain.

Classifies the incoming query into a routing intent using a cheap LLM.
The domain names and descriptions come from the tenant's BrainDomain rows
(Redis-cached, 5 min TTL) — completely generic, no hardcoded domain names.

If the tenant has no domains configured, the router falls back to source-type
classification using the heuristic defaults.

Intent schema:
  {
    "intent":        "recent" | "historical" | "deep_doc" | "code" | "entity" | "cross_source",
    "domains":       ["slug1", "slug2"],   // empty = all active domains
    "source_types":  ["slack", "github"],  // used when no domains configured
    "time_range":    {"from": "ISO", "to": "ISO"} | null,
    "entities":      ["alice", "payments-api"],
    "use_pageindex": bool,
    "tiers":         ["hot"] | ["hot", "warm"]
  }

Cost: ~$0.0001 per query with claude-haiku.
Fallback: safe default intent on any failure.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class QueryIntent:
    intent: str = "cross_source"
    domains: list[str] = field(default_factory=list)  # domain slugs, empty = all
    source_types: list[str] = field(default_factory=list)  # fallback when no domains
    time_from: str | None = None
    time_to: str | None = None
    entities: list[str] = field(default_factory=list)
    use_pageindex: bool = False
    tiers: list[str] = field(default_factory=lambda: ["hot"])


_SYSTEM_PROMPT_TEMPLATE = """You are a query classifier for a Company Brain (enterprise knowledge hub).
The company has defined the following knowledge domains:

{domain_context}

Classify the user query and return a JSON object with these fields:

intent: one of
  "recent"       — asking about something that happened recently (last 7 days)
  "historical"   — asking about something from the distant past
  "deep_doc"     — asking for detailed information from long documents
  "code"         — asking about code, PRs, commits, or technical implementation
  "entity"       — asking about a specific person, team, or project
  "cross_source" — general question spanning multiple sources (default)

domains: array of domain slugs from the list above that are relevant.
  Empty array = search all domains.

time_from: ISO-8601 date string if query implies a time window start, else null.
time_to:   ISO-8601 date string if query implies a time window end, else null.

entities: array of named entities (people, projects, repos, teams) mentioned.

use_pageindex: true only if intent=deep_doc.

tiers: ["hot"] for recent, ["hot","warm"] for historical queries.

Respond with ONLY valid JSON, no markdown, no explanation."""

_SYSTEM_PROMPT_NO_DOMAINS = """You are a query classifier for a Company Brain (enterprise knowledge hub).
Classify the user query and return a JSON object with these fields:

intent: one of "recent" | "historical" | "deep_doc" | "code" | "entity" | "cross_source"

source_types: array from: slack, github, gitlab, jira, clickup, notion, confluence,
  gmail, google_drive, linear. Empty = all sources.

time_from / time_to: ISO-8601 or null.
entities: named entities mentioned.
use_pageindex: true only if intent=deep_doc.
tiers: ["hot"] for recent, ["hot","warm"] for historical.

Respond with ONLY valid JSON."""


async def classify_query(
    query: str,
    tenant_id: str | None = None,
    db: Any | None = None,
) -> QueryIntent:
    """
    Classify a query into a routing intent.

    If tenant_id + db are provided, loads the tenant's domain config to give
    the LLM domain-aware context. Falls back to heuristics on any error.
    """
    from src.config.settings import get_settings

    settings = get_settings()
    model = getattr(settings, "company_brain_query_router_model", "claude-haiku-4-5-20251001")
    enable_pageindex = getattr(settings, "company_brain_enable_pageindex", False)

    # Load tenant domains if available
    domains: list[dict] = []
    if tenant_id and db:
        try:
            from src.services.company_brain.domain_service import get_domains_cached

            domains = await get_domains_cached(tenant_id, db)
        except Exception as exc:
            logger.warning("Failed to load tenant domains for query routing: %s", exc)

    system_prompt = _build_system_prompt(domains)

    try:
        import litellm

        response = await litellm.acompletion(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            max_tokens=300,
            temperature=0,
        )
        raw = response.choices[0].message.content or "{}"
        data: dict[str, Any] = json.loads(raw)

        use_pi = bool(data.get("use_pageindex")) and enable_pageindex
        tiers = data.get("tiers") or ["hot"]
        if not isinstance(tiers, list):
            tiers = ["hot"]

        return QueryIntent(
            intent=data.get("intent", "cross_source"),
            domains=data.get("domains") or [],
            source_types=data.get("source_types") or [],
            time_from=data.get("time_from"),
            time_to=data.get("time_to"),
            entities=data.get("entities") or [],
            use_pageindex=use_pi,
            tiers=tiers,
        )

    except Exception as exc:
        logger.warning("Query classification failed (%s): returning default intent", exc)
        return _default_intent(query)


def _build_system_prompt(domains: list[dict]) -> str:
    if not domains:
        return _SYSTEM_PROMPT_NO_DOMAINS

    domain_lines = []
    for d in domains:
        desc = f" — {d['description']}" if d.get("description") else ""
        domain_lines.append(f"  - {d['slug']}{desc}")

    domain_context = "\n".join(domain_lines)
    return _SYSTEM_PROMPT_TEMPLATE.format(domain_context=domain_context)


def _default_intent(query: str) -> QueryIntent:
    """Safe heuristic fallback when LLM classification fails."""
    q = query.lower()
    recent_signals = ["today", "this week", "recently", "just now", "latest", "yesterday"]
    historical_signals = ["last year", "months ago", "when did", "history of", "originally"]
    code_signals = ["pr ", "pull request", "commit", "branch", "merge", "code", "function", "bug"]

    tiers = ["hot", "warm"] if any(s in q for s in historical_signals) else ["hot"]

    return QueryIntent(
        intent=(
            "recent"
            if any(s in q for s in recent_signals)
            else "code"
            if any(s in q for s in code_signals)
            else "cross_source"
        ),
        tiers=tiers,
    )
