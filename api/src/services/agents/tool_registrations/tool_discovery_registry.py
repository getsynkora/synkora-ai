"""
Tool Discovery Registry

Registers the tool discovery meta-tool that allows LLM to search for
additional tools on-demand.

This tool should ALWAYS be included in the tool list sent to LLM,
providing a safety net when initial filtering might miss relevant tools.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# This tool name should always be included in filtered tool lists
ALWAYS_INCLUDE_TOOLS = [
    "internal_search_available_tools",
    "internal_list_tool_categories",
]

_MAX_JEV_DISCOVERY_TOOLS = 50


async def jev_discover_tools(
    query: str,
    candidate_tools: list[dict[str, Any]],
    typesafe_client: Any,
    threshold: str = "yes",
) -> list[dict[str, Any]]:
    """
    Use JEV (TypeSafe) to semantically discover which candidate tools are relevant to a query.

    Replaces keyword-based relevance scoring with a single parallel JEV noul call.

    Args:
        query:           The user query / capability description.
        candidate_tools: List of {\"name\": str, \"description\": str} dicts (≤50).
        typesafe_client: Initialized TypeSafeClient instance.
        threshold:       \"yes\" (strict) or \"unclear\" (permissive).

    Returns:
        Subset of candidate_tools that JEV approved.
        Falls back to returning all candidates on any API error.
    """
    if not candidate_tools:
        return []

    # Cap at _MAX_JEV_DISCOVERY_TOOLS; caller pre-filters if pool is larger
    tools = candidate_tools[:_MAX_JEV_DISCOVERY_TOOLS]

    questions: dict[str, dict[str, Any]] = {}
    for tool in tools:
        name = tool.get("name", "")
        desc = (tool.get("description") or "")[:200]
        questions[f"tool_{name}"] = {
            "type": "noul",
            "question": (f"Is the tool '{name}' ({desc}) needed to answer this query: {query[:200]}?"),
        }

    try:
        result = await typesafe_client.evaluate(
            state=query,
            questions=questions,
        )

        if "error" in result:
            logger.warning("[jev-discover] JEV returned error: %s — returning all candidates", result["error"])
            return list(candidate_tools)

        answers = result.get("answers", {})
        approved: list[dict[str, Any]] = []
        for tool in tools:
            name = tool.get("name", "")
            key = f"tool_{name}"
            if key not in answers:
                # Not answered → include (permissive unknown)
                approved.append(tool)
                continue
            ans = answers[key]
            answer_val = (
                str(ans.get("answer") or ans.get("choice") or "").lower() if isinstance(ans, dict) else str(ans).lower()
            )
            if threshold == "unclear":
                if answer_val in ("yes", "unclear"):
                    approved.append(tool)
            else:
                if answer_val == "yes":
                    approved.append(tool)

        logger.debug(
            "[jev-discover] %d / %d tools approved (threshold=%s)",
            len(approved),
            len(tools),
            threshold,
        )
        return approved

    except Exception as exc:
        logger.warning("[jev-discover] JEV call failed: %s — returning all candidates", exc)
        return list(candidate_tools)


def register_tool_discovery_tools(registry):
    """
    Register tool discovery tools with the ADK tool registry.

    Args:
        registry: ADKToolRegistry instance
    """
    from src.services.agents.internal_tools.tool_discovery_tools import (
        internal_list_tool_categories,
        internal_search_available_tools,
    )

    # Wrapper for search_available_tools
    async def internal_search_available_tools_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_search_available_tools(
            query=kwargs.get("query", ""),
            limit=kwargs.get("limit", 10),
            runtime_context=runtime_context,
            config=config,
        )

    # Wrapper for list_tool_categories
    async def internal_list_tool_categories_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_list_tool_categories(
            runtime_context=runtime_context,
            config=config,
        )

    # Register search_available_tools
    registry.register_tool(
        name="internal_search_available_tools",
        description=(
            "IMPORTANT: Before telling the user you cannot do something, ALWAYS use this tool first "
            "to search for capabilities you might be missing. "
            "Describe what you need (e.g., 'schedule daily tasks at specific time', 'send email notifications', "
            "'youtube transcripts', 'slack messaging') and this will return matching tools you can use. "
            "Many capabilities like email, scheduling, messaging, and integrations are available but may not "
            "be in your initial tool set. Search before saying you can't do something."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Description of the capability you need (e.g., 'schedule daily tasks', 'search youtube')",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of tools to return (default 10)",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
        function=internal_search_available_tools_wrapper,
    )

    # Register list_tool_categories
    registry.register_tool(
        name="internal_list_tool_categories",
        description=(
            "List available tool categories to understand what capabilities exist. "
            "Use this to explore available integrations before searching for specific tools."
        ),
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
        function=internal_list_tool_categories_wrapper,
    )

    logger.info("Registered 2 tool discovery tools (always included)")
