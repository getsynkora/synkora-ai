"""
Context-Aware Tool Filtering

Filters tools based on message content to reduce the number of tools sent to the LLM.
This improves response latency and reduces token costs by only sending relevant tools.

Strategy:
1. Extract keywords and intent from user message
2. Match against tool keywords and descriptions
3. Use semantic embeddings for better matching (optional)
4. Score and rank tools by relevance (hybrid: keyword + embedding)
5. Expand categories to include all related tools
6. Return top N most relevant tools (or fallback to all if unclear intent)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.services.agents.tool_embedding_service import ToolEmbeddingService

from src.services.agents.tool_filter_data import (
    ACTION_VERB_PATTERN,
    MULTI_STEP_INDICATORS,
    SERVICE_INDICATORS,
    TOOL_CATEGORIES,
    TOOL_CATEGORIES_V2,
    TOOL_KEYWORDS,
)

logger = logging.getLogger(__name__)


class TaskComplexity(Enum):
    """Task complexity levels that determine tool limits."""

    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


# Dynamic tool limits based on task complexity
# Keep these large enough for multi-step work, but low enough that tool schemas
# do not dominate prompt cost on every turn.
COMPLEXITY_TOOL_LIMITS = {
    TaskComplexity.SIMPLE: 20,
    TaskComplexity.MODERATE: 30,
    TaskComplexity.COMPLEX: 45,
}

# Tools that should ALWAYS be included regardless of filtering
# These meta-tools allow LLM to discover additional tools on-demand
ALWAYS_INCLUDE_TOOLS = [
    "internal_search_available_tools",
    "internal_list_tool_categories",
    # Context file on-demand loading — always available so LLM can load skills/context when needed
    "internal_load_context_file",
    # Multi-agent orchestration tools — always available so agents can spawn
    # sub-agents and track tasks without needing spawn_agent in tools_config.
    "spawn_agent",
    "check_task",
    "list_background_tasks",
    # Human handoff — always available so any agent can escalate to a human
    # without requiring explicit tool configuration per agent.
    "handoff_to_human",
]


@dataclass
class ToolFilterConfig:
    """Configuration for tool filtering."""

    min_tools: int = 10  # Always include at least N tools
    max_tools: int = 20  # Base cap (overridden by complexity for more tools)
    fallback_to_all: bool = False  # Prefer top-N shortlist plus discovery tools
    min_score_threshold: float = 1.0  # Require at least one real lexical/semantic signal

    # Hybrid scoring weights (keyword vs embedding)
    # Set embedding_weight to 0 to disable embedding-based search
    keyword_weight: float = 0.6  # Weight for keyword-based scoring
    embedding_weight: float = 0.4  # Weight for embedding-based scoring
    embedding_score_threshold: float = 0.2  # Lower threshold for embedding similarity


def _normalize_text(text: str) -> str:
    """Normalize text for matching - lowercase and remove punctuation."""
    return re.sub(r"[^\w\s]", " ", text.lower())


def _extract_keywords_from_message(message: str) -> set[str]:
    """Extract meaningful keywords from user message."""
    normalized = _normalize_text(message)
    words = set(normalized.split())

    # Add bigrams for better matching (e.g., "pull request", "direct message")
    word_list = normalized.split()
    bigrams = {f"{word_list[i]} {word_list[i + 1]}" for i in range(len(word_list) - 1)}

    return words | bigrams


def _detect_task_complexity(message: str) -> TaskComplexity:
    """
    Detect if message requires multiple tool categories (multi-step task).

    This determines how many tools should be included in the filtered set:
    - SIMPLE: Single service, basic query → 20 tools max
    - MODERATE: Two services or multi-step indicator → 30 tools max
    - COMPLEX: Three+ services or complex workflow → 45 tools max
    """
    message_lower = message.lower()

    # Count how many distinct services are mentioned
    service_count = sum(1 for s in SERVICE_INDICATORS if s in message_lower)

    # Check for multi-step workflow indicators
    has_multi_step = any(ind in message_lower for ind in MULTI_STEP_INDICATORS)

    # Count action verbs (suggests multiple operations)
    action_verbs = len(ACTION_VERB_PATTERN.findall(message_lower))

    # Determine complexity level
    if service_count >= 3 or (has_multi_step and service_count >= 2) or action_verbs >= 3:
        return TaskComplexity.COMPLEX
    elif service_count >= 2 or has_multi_step or action_verbs >= 2:
        return TaskComplexity.MODERATE
    return TaskComplexity.SIMPLE


def _expand_categories(message: str, initial_tool_names: set[str], available_tool_names: set[str]) -> set[str]:
    """
    Include all tools from detected categories.

    When we detect that a user's message relates to a category (e.g., scheduler),
    we include ALL tools from that category, not just the ones that scored well.
    This ensures multi-step tasks have access to all needed tools.

    Args:
        message: User's message
        initial_tool_names: Tool names from initial keyword scoring
        available_tool_names: All available tool names (to filter unavailable tools)

    Returns:
        Expanded set of tool names including full category tools
    """
    message_lower = message.lower()
    expanded = set(initial_tool_names)
    matched_categories: list[str] = []

    for category, config in TOOL_CATEGORIES_V2.items():
        # Check if any category keyword matches
        if any(kw in message_lower for kw in config["keywords"]):
            matched_categories.append(category)
            # Add all tools from this category (if available)
            for tool in config["tools"]:
                if tool in available_tool_names:
                    expanded.add(tool)
            # Add companion tools that are commonly needed with this category
            for tool in config.get("always_include_with", []):
                if tool in available_tool_names:
                    expanded.add(tool)

    if matched_categories:
        logger.debug(f"Category expansion matched: {matched_categories}")

    return expanded


def _matches_pattern(tool_name: str, pattern: str) -> bool:
    """Check if tool name matches a glob-like pattern."""
    if pattern == "*":
        return True
    if "*" not in pattern:
        return tool_name == pattern

    # Convert glob to regex
    regex_pattern = pattern.replace("*", ".*")
    return bool(re.match(f"^{regex_pattern}$", tool_name))


def _score_tool(tool_name: str, tool_description: str, message_keywords: set[str], message_lower: str) -> float:
    """
    Score a tool based on relevance to the message.

    Returns a score from 0.0 to 10.0 where higher = more relevant.
    """
    score = 0.0

    # 1. Check if tool name appears directly in message (highest weight)
    tool_words = tool_name.replace("internal_", "").replace("_", " ").lower()
    for word in tool_words.split():
        if len(word) > 3 and word in message_lower:
            score += 3.0

    # 2. Check keyword mappings (high weight)
    tool_keywords = TOOL_KEYWORDS.get(tool_name, [])
    for keyword in tool_keywords:
        if keyword in message_lower:
            score += 2.5
        # Partial match for compound words
        elif any(keyword in kw for kw in message_keywords if len(kw) > 3):
            score += 1.0

    # 3. Check if any message keyword appears in tool description (medium weight)
    description_lower = tool_description.lower()
    for keyword in message_keywords:
        if len(keyword) > 3 and keyword in description_lower:
            score += 1.0

    # 4. Category bonus - if message intent matches tool category
    for category, patterns in TOOL_CATEGORIES.items():
        for pattern in patterns:
            if _matches_pattern(tool_name, pattern):
                # Check if category-related words are in message
                category_words = category.replace("_", " ").split()
                if any(cw in message_lower for cw in category_words):
                    score += 1.5
                break

    return min(score, 10.0)  # Cap at 10


def _get_embedding_scores(
    message: str,
    tool_names: list[str],
    config: ToolFilterConfig,
) -> dict[str, float]:
    """
    Get embedding similarity scores for tools using the ToolEmbeddingService.

    Returns a dict mapping tool_name -> similarity_score (0-1).
    Returns empty dict if embeddings are disabled or not initialized.
    """
    if config.embedding_weight <= 0:
        return {}

    try:
        from src.services.agents.tool_embedding_service import get_tool_embedding_service

        embedding_service = get_tool_embedding_service()
        if not embedding_service.is_initialized():
            return {}

        # Get similar tools with scores
        similar_tools = embedding_service.find_similar_tools(
            query=message,
            limit=len(tool_names),  # Get scores for all tools
            score_threshold=config.embedding_score_threshold,
        )

        return dict(similar_tools)

    except ImportError:
        logger.debug("Tool embedding service not available")
        return {}
    except Exception as e:
        logger.warning(f"Error getting embedding scores: {e}")
        return {}


def _compute_hybrid_score(
    keyword_score: float,
    embedding_score: float,
    config: ToolFilterConfig,
) -> float:
    """
    Compute hybrid score combining keyword and embedding scores.

    Uses weighted average based on config.keyword_weight and config.embedding_weight.
    If embedding_score is 0 (not found), falls back to keyword_score only.
    """
    if embedding_score <= 0:
        # No embedding match, use keyword score only
        return keyword_score

    # Normalize keyword score to 0-1 range (it's capped at 10)
    normalized_keyword = keyword_score / 10.0

    # Weighted average
    total_weight = config.keyword_weight + config.embedding_weight
    hybrid = (config.keyword_weight * normalized_keyword + config.embedding_weight * embedding_score) / total_weight

    # Scale back to 0-10 range for consistency with existing threshold logic
    return hybrid * 10.0


def filter_tools_by_message(
    message: str,
    available_tools: list[dict],
    config: ToolFilterConfig | None = None,
    embedding_service: ToolEmbeddingService | None = None,
) -> list[dict]:
    """
    Filter tools based on message content with hybrid scoring and category expansion.

    This improved filter:
    1. Detects task complexity to set dynamic tool limits
    2. Scores tools by keyword relevance
    3. Enhances scores with semantic embeddings (if available)
    4. Expands categories to include all related tools for multi-step tasks

    Args:
        message: User's message
        available_tools: List of tool definitions [{"name": str, "description": str, ...}]
        config: Filtering configuration
        embedding_service: Optional embedding service (if not provided, uses global singleton)

    Returns:
        Filtered list of tools most relevant to the message
    """
    if config is None:
        config = ToolFilterConfig()

    if not message or not available_tools:
        return available_tools

    # Step 1: Detect task complexity and set dynamic max_tools
    complexity = _detect_task_complexity(message)
    dynamic_max = COMPLEXITY_TOOL_LIMITS[complexity]
    effective_max_tools = max(config.max_tools, dynamic_max)

    # If the available set already fits under the effective cap, filtering only
    # adds regression risk without meaningfully reducing prompt cost.
    if len(available_tools) <= effective_max_tools:
        logger.debug(f"Tool filter: {len(available_tools)} tools fit under cap {effective_max_tools}, skipping filter")
        return available_tools

    message_lower = _normalize_text(message)
    message_keywords = _extract_keywords_from_message(message)

    # Step 2: Get embedding scores (if enabled)
    tool_names = [t.get("name", "") for t in available_tools]
    embedding_scores = _get_embedding_scores(message, tool_names, config)
    using_embeddings = len(embedding_scores) > 0

    # Step 3: Score each tool with hybrid scoring (keyword + embedding)
    tool_scores: list[tuple[dict, float]] = []
    for tool in available_tools:
        tool_name = tool.get("name", "")
        tool_description = tool.get("description", "")

        # Get keyword score
        keyword_score = _score_tool(tool_name, tool_description, message_keywords, message_lower)

        # Get embedding score (0 if not found)
        embedding_score = embedding_scores.get(tool_name, 0.0)

        # Compute hybrid score
        if using_embeddings:
            final_score = _compute_hybrid_score(keyword_score, embedding_score, config)
        else:
            final_score = keyword_score

        tool_scores.append((tool, final_score))

    # Sort by score descending
    tool_scores.sort(key=lambda x: x[1], reverse=True)

    # Get tools above threshold
    matched_tools = [tool for tool, score in tool_scores if score >= config.min_score_threshold]

    # Log scoring for debugging
    if logger.isEnabledFor(logging.DEBUG):
        top_5 = tool_scores[:5]
        logger.debug(f"Tool filter top scores: {[(t['name'], s) for t, s in top_5]}")

    # Handle edge cases - fall back if not enough tools matched
    if len(matched_tools) < config.min_tools:
        if config.fallback_to_all:
            logger.info(
                f"Tool filter: Only {len(matched_tools)} tools matched (below min {config.min_tools}), "
                f"falling back to all {len(available_tools)} tools"
            )
            return available_tools
        else:
            # Take top N even if below threshold
            matched_tools = [tool for tool, _ in tool_scores[: config.min_tools]]

    # Step 4: Category expansion - include all tools from matched categories
    # This ensures multi-step tasks have access to all needed tools
    available_tool_names = {t.get("name", "") for t in available_tools}
    matched_tool_names = {t.get("name", "") for t in matched_tools}
    expanded_tool_names = _expand_categories(message, matched_tool_names, available_tool_names)

    # Build expanded tool list while preserving score ordering
    # First add originally matched tools (in score order), then category-expanded tools
    expanded_tools = list(matched_tools)
    expanded_names_set = {t.get("name", "") for t in expanded_tools}

    for tool in available_tools:
        tool_name = tool.get("name", "")
        if tool_name in expanded_tool_names and tool_name not in expanded_names_set:
            expanded_tools.append(tool)
            expanded_names_set.add(tool_name)

    # Apply dynamic max limit
    if len(expanded_tools) > effective_max_tools:
        expanded_tools = expanded_tools[:effective_max_tools]

    # Step 5: Always include discovery tools (meta-tools for on-demand tool loading)
    # These allow LLM to search for additional tools if initial filtering missed something
    expanded_names_set = {t.get("name", "") for t in expanded_tools}
    always_include_added = 0
    for tool in available_tools:
        tool_name = tool.get("name", "")
        if tool_name in ALWAYS_INCLUDE_TOOLS and tool_name not in expanded_names_set:
            expanded_tools.append(tool)
            expanded_names_set.add(tool_name)
            always_include_added += 1

    # Enhanced logging
    category_added = len(expanded_tools) - len(matched_tools) - always_include_added
    embedding_status = "enabled" if using_embeddings else "disabled"
    logger.info(
        f"Tool filter: complexity={complexity.value}, embeddings={embedding_status}, "
        f"{len(available_tools)} → {len(expanded_tools)} tools "
        f"(scored={len(matched_tools)}, category_added={category_added}, "
        f"always_include={always_include_added}, max={effective_max_tools}) "
        f"(message: '{message[:50]}...')"
    )

    return expanded_tools


def filter_tool_names_by_message(
    message: str, available_tool_names: list[str], tool_registry, config: ToolFilterConfig | None = None
) -> list[str]:
    """
    Filter tool names based on message content.

    Convenience function that works with tool names instead of full definitions.

    Args:
        message: User's message
        available_tool_names: List of tool names
        tool_registry: The ADKToolRegistry instance
        config: Filtering configuration

    Returns:
        Filtered list of tool names
    """
    if config is None:
        config = ToolFilterConfig()

    if not message or not available_tool_names:
        return available_tool_names

    # Get full tool definitions for scoring
    all_tools = tool_registry.list_tools()
    available_tools = [t for t in all_tools if t["name"] in available_tool_names]

    # Filter using full definitions
    filtered_tools = filter_tools_by_message(message, available_tools, config)

    # Return just the names
    return [t["name"] for t in filtered_tools]
