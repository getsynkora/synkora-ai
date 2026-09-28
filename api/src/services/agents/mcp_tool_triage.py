"""
TypeSafe-based MCP tool pre-filtering.

After MCP tools are loaded in chat_stream_service.py, this module scores each tool
for relevance to the current query before the LLM sees the tool list. Extends the
same JEV tool-filtering posture from jev_router.py to the per-agent MCP tool set.

Fail-open contract: any error (missing client, timeout, API error) returns all
tool_names unchanged. The caller never gets a worse result than without filtering.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

MAX_MCP_TOOL_QUESTIONS = 50
MCP_TRIAGE_TIMEOUT = 5.0
_MAX_DESC_CHARS = 200
_MAX_QUERY_CHARS = 500
_MAX_PURPOSE_CHARS = 600


def _build_questions(tool_names: list[str], registry: Any) -> dict[str, dict[str, Any]]:
    """One noul question per tool, capped at MAX_MCP_TOOL_QUESTIONS."""
    questions: dict[str, dict[str, Any]] = {}
    for name in tool_names[:MAX_MCP_TOOL_QUESTIONS]:
        tool = registry.get_tool(name)
        desc = ((tool or {}).get("description") or "")[:_MAX_DESC_CHARS]
        questions[f"tool_{name}"] = {
            "type": "noul",
            "question": (
                f"Is the tool '{name}' needed to answer this query? "
                f"Tool description: {desc}"
            ),
        }
    return questions


def _build_state(query: str, agent: Any, history: list[dict] | None) -> dict[str, Any]:
    history_summary = ""
    if history:
        history_summary = " | ".join(
            f"{m.get('role', '?')}: {str(m.get('content', ''))[:100]}" for m in history[-5:]
        )
    return {
        "agent_purpose": (getattr(agent, "description", "") or "General purpose agent")[:_MAX_PURPOSE_CHARS],
        "query": query[:_MAX_QUERY_CHARS],
        "recent_history": history_summary,
    }


def _extract_answer(answer: Any) -> str:
    """Normalize a noul answer dict to a plain lowercase string."""
    if isinstance(answer, dict):
        # TypeSafe noul returns {"answer": "yes"/"no"/"unclear", "noul": 0.8, ...}
        return str(answer.get("answer") or "").lower()
    return str(answer).lower()


async def filter_mcp_tools(
    *,
    client: Any | None,
    tool_names: list[str],
    registry: Any,
    query: str,
    agent: Any,
    history: list[dict] | None = None,
    threshold: str = "yes",
    timeout: float = MCP_TRIAGE_TIMEOUT,
) -> list[str]:
    """
    Return the subset of ``tool_names`` relevant for the current query.

    Tools beyond MAX_MCP_TOOL_QUESTIONS always pass through (same rule as
    jev_router._MAX_TOOL_QUESTIONS). Fails open on any error.

    Args:
        client:     TypeSafeClient instance (from shared_state["_jev_client"]).
        tool_names: MCP tool names loaded for this agent this turn.
        registry:   ADKToolRegistry with get_tool(name) -> dict.
        query:      The user's current message.
        agent:      Agent ORM instance (needs .description).
        history:    Recent conversation history (optional).
        threshold:  "yes" -> strict (only "yes" passes);
                    "unclear" -> permissive ("yes" or "unclear" pass).
        timeout:    Seconds before failing open.

    Returns:
        Filtered list of tool names.
    """
    if not tool_names or client is None:
        return tool_names

    within_cap = tool_names[:MAX_MCP_TOOL_QUESTIONS]
    beyond_cap = tool_names[MAX_MCP_TOOL_QUESTIONS:]

    questions = _build_questions(within_cap, registry)
    if not questions:
        return tool_names

    state = _build_state(query, agent, history)

    try:
        result = await asyncio.wait_for(
            client.evaluate(state=state, questions=questions),
            timeout=timeout,
        )
    except TimeoutError:
        logger.warning("[mcp-tool-triage] timeout — all %d MCP tools pass through", len(tool_names))
        return tool_names
    except Exception as exc:
        logger.warning("[mcp-tool-triage] raised: %s — all MCP tools pass through", exc)
        return tool_names

    if not isinstance(result, dict) or "error" in result:
        logger.warning("[mcp-tool-triage] API error — all MCP tools pass through")
        return tool_names

    answers = result.get("answers") or {}
    allowed: list[str] = []
    for name in within_cap:
        # Missing answer → empty string → does not match "yes"/"unclear" → excluded
        answer_val = _extract_answer(answers.get(f"tool_{name}") or "")
        if threshold == "unclear":
            if answer_val in ("yes", "unclear"):
                allowed.append(name)
        else:
            if answer_val == "yes":
                allowed.append(name)

    logger.debug(
        "[mcp-tool-triage] %d / %d MCP tools approved (threshold=%s)",
        len(allowed),
        len(within_cap),
        threshold,
    )
    return allowed + beyond_cap
