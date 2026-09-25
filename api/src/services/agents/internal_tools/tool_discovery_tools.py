"""
Tool Discovery Tools

Meta-tool that allows the LLM to search and discover available tools on-demand.
This provides a safety net when initial tool filtering might miss relevant tools.

The LLM can call this tool to find additional capabilities it needs to complete a task.
"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def _normalize_text(text: str) -> str:
    """Normalize text for matching."""
    return re.sub(r"[^\w\s]", " ", text.lower())


def _calculate_relevance_score(query: str, tool_name: str, tool_description: str) -> float:
    """
    Calculate relevance score between query and tool.

    Returns a score from 0.0 to 1.0 where higher = more relevant.
    """
    query_lower = _normalize_text(query)
    query_words = set(query_lower.split())

    # Check tool name
    name_words = tool_name.replace("internal_", "").replace("_", " ").lower()
    name_word_set = set(name_words.split())

    # Check description
    desc_lower = _normalize_text(tool_description)
    desc_words = set(desc_lower.split())

    score = 0.0

    # Exact word matches in name (high weight)
    name_matches = len(query_words & name_word_set)
    score += name_matches * 0.3

    # Exact word matches in description (medium weight)
    desc_matches = len(query_words & desc_words)
    score += min(desc_matches * 0.1, 0.5)  # Cap at 0.5

    # Substring matches in name
    for word in query_words:
        if len(word) > 3 and word in name_words:
            score += 0.2

    # Substring matches in description
    for word in query_words:
        if len(word) > 3 and word in desc_lower:
            score += 0.05

    return min(score, 1.0)


async def internal_search_available_tools(
    query: str,
    limit: int = 10,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Search for available tools that match a query.

    Use this tool when you need capabilities that aren't in your current tool set.
    Describe what you need to do, and this will return matching tools.

    Args:
        query: Description of the capability you need (e.g., "schedule recurring tasks",
               "send slack messages", "search youtube videos")
        limit: Maximum number of tools to return (default 10)

    Returns:
        List of matching tools with their names and descriptions
    """
    try:
        if not query:
            return {
                "success": False,
                "error": "Query is required. Describe what capability you need.",
            }

        # Get all available tools from runtime context
        all_tools = []
        if runtime_context and hasattr(runtime_context, "all_available_tools"):
            all_tools = runtime_context.all_available_tools
        elif config and "_all_available_tools" in config:
            all_tools = config["_all_available_tools"]

        if not all_tools:
            return {
                "success": False,
                "error": "No tool registry available. Contact support.",
            }

        # Exclude the discovery tool itself from candidates
        candidates = [t for t in all_tools if t.get("name") != "internal_search_available_tools"]

        # JEV semantic discovery: use TypeSafe when a jev_client is available in this context.
        # Require shared_state to be a real dict (not a MagicMock from tests that don't set it).
        jev_client = None
        if runtime_context and isinstance(getattr(runtime_context, "shared_state", None), dict):
            jev_client = runtime_context.shared_state.get("_jev_client")
        if jev_client is None and isinstance(config, dict):
            jev_client = config.get("_jev_client")

        if jev_client:
            from src.services.agents.tool_registrations.tool_discovery_registry import jev_discover_tools

            # Cap candidates at 50; send the rest as-is (permissive unknown)
            _MAX_CANDIDATES = 50
            to_ask = candidates[:_MAX_CANDIDATES]
            overflow = candidates[_MAX_CANDIDATES:]
            jev_results = await jev_discover_tools(
                query=query,
                candidate_tools=to_ask,
                typesafe_client=jev_client,
            )
            top_tools_raw = (jev_results + overflow)[:limit]
            results = [
                {
                    "name": t.get("name"),
                    "description": (t.get("description") or "")[:200],
                    "relevance": 1.0,  # JEV doesn't produce a numeric score
                }
                for t in top_tools_raw
            ]
            if not results:
                return {
                    "success": True,
                    "message": f"No tools found matching '{query}'.",
                    "tools": [],
                    "count": 0,
                }
            return {
                "success": True,
                "tools": results,
                "count": len(results),
                "query": query,
                "message": f"Found {len(results)} tools matching your query. You can now use these tools by name.",
            }

        # Keyword-based fallback (original behaviour)
        scored_tools: list[tuple[dict, float]] = []
        for tool in candidates:
            tool_name = tool.get("name", "")
            tool_description = tool.get("description", "")
            score = _calculate_relevance_score(query, tool_name, tool_description)
            if score > 0.1:  # Minimum threshold
                scored_tools.append((tool, score))

        # Sort by score descending
        scored_tools.sort(key=lambda x: x[1], reverse=True)

        # Take top N
        top_tools = scored_tools[:limit]

        if not top_tools:
            return {
                "success": True,
                "message": f"No tools found matching '{query}'. Try different keywords.",
                "tools": [],
                "count": 0,
            }

        # Format results
        results = []
        for tool, score in top_tools:
            results.append(
                {
                    "name": tool.get("name"),
                    "description": tool.get("description", "")[:200],  # Truncate long descriptions
                    "relevance": round(score, 2),
                }
            )

        return {
            "success": True,
            "tools": results,
            "count": len(results),
            "query": query,
            "message": f"Found {len(results)} tools matching your query. You can now use these tools by name.",
        }

    except Exception as e:
        logger.error(f"Error searching tools: {e}")
        return {"success": False, "error": str(e)}


async def internal_list_tool_categories(
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    List available tool categories to help discover capabilities.

    Use this to understand what types of tools are available before searching.

    Returns:
        List of tool categories with example tools
    """
    try:
        # Get all available tools from runtime context
        all_tools = []
        if runtime_context and hasattr(runtime_context, "all_available_tools"):
            all_tools = runtime_context.all_available_tools
        elif config and "_all_available_tools" in config:
            all_tools = config["_all_available_tools"]

        if not all_tools:
            return {
                "success": False,
                "error": "No tool registry available.",
            }

        # Group tools by category (extract from tool name prefix)
        categories: dict[str, list[str]] = {}
        for tool in all_tools:
            tool_name = tool.get("name", "")

            # Extract category from tool name
            # e.g., "internal_slack_send_message" -> "slack"
            # e.g., "internal_hackernews_get_top_stories" -> "hackernews"
            parts = tool_name.replace("internal_", "").split("_")
            if parts:
                category = parts[0]
                # Skip generic prefixes
                if category in ("get", "list", "create", "update", "delete", "search"):
                    category = parts[1] if len(parts) > 1 else "general"

                if category not in categories:
                    categories[category] = []
                categories[category].append(tool_name)

        # Format results
        results = []
        for category, tools in sorted(categories.items()):
            results.append(
                {
                    "category": category,
                    "tool_count": len(tools),
                    "example_tools": tools[:3],  # Show up to 3 examples
                }
            )

        return {
            "success": True,
            "categories": results,
            "total_categories": len(results),
            "total_tools": len(all_tools),
            "message": "Use search_available_tools with keywords from these categories to find specific tools.",
        }

    except Exception as e:
        logger.error(f"Error listing tool categories: {e}")
        return {"success": False, "error": str(e)}
