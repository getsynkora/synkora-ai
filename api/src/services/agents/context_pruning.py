"""
Context Pruning for Tool Results

Prunes old tool results from conversation history to reduce token usage.
This prevents context bloat when agents make many tool calls.

Strategy:
1. Keep recent tool results intact (last N results)
2. Trim large older results to head + tail
3. Optionally summarize very old results
"""

import json
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Prefix present in all summarised tool results.
# Used by the dedup-cache eviction check in function_calling.py so that
# a summarised entry is evicted (triggering a fresh tool call next time).
RESULT_PRUNED_MARKER = "[pruned: "


@dataclass
class PruningSettings:
    """Configuration for context pruning."""

    enabled: bool = True
    keep_last_results: int = 3  # Always keep last N tool results intact
    max_result_chars: int = 5000  # Trim results larger than this
    head_chars: int = 1500  # Keep first N chars when trimming
    tail_chars: int = 1500  # Keep last N chars when trimming
    max_total_tool_chars: int = 400000  # Max total chars for all tool results combined
    prune_error_results: bool = True  # Replace old error results with compact summaries
    use_meaningful_summaries: bool = True  # Replace pruned results with informative 1-liners
    # Tool name patterns whose results must never be reduced to a 1-liner.
    # These tools return actual data (rows, file contents) the LLM may need
    # to reference later, so they are trimmed head+tail instead of summarised.
    protect_data_tools: tuple[str, ...] = (
        "internal_execute_",
        "internal_query_",
        "internal_read_",
        "internal_fetch_",
        "internal_list_",
        "internal_search_",
        "internal_database_",
        "internal_supabase_",
        "internal_csv_",
        "internal_sql_",
        "internal_db_",
        "internal_select_",
    )


@dataclass
class PruningStats:
    """Statistics from pruning operation."""

    original_messages: int = 0
    pruned_messages: int = 0
    tool_results_count: int = 0
    tool_results_pruned: int = 0
    data_bearing_pruned: int = 0  # pruned results from data-bearing tools (quality signal)
    original_chars: int = 0
    pruned_chars: int = 0
    chars_saved: int = 0
    estimated_tokens_saved: int = 0


def _get_content_length(content: Any) -> int:
    """Get the character length of message content."""
    if isinstance(content, str):
        return len(content)
    elif isinstance(content, dict):
        return len(json.dumps(content))
    elif isinstance(content, list):
        return sum(_get_content_length(item) for item in content)
    return len(str(content))


def _get_content_as_string(content: Any) -> str:
    """Convert content to string for manipulation."""
    if isinstance(content, str):
        return content
    elif isinstance(content, (dict, list)):
        return json.dumps(content, indent=2)
    return str(content)


def _trim_content(content: str, settings: PruningSettings) -> str:
    """
    Trim large content to head + tail.

    Keeps the first N chars and last N chars, with an indicator in between.
    """
    if len(content) <= settings.max_result_chars:
        return content

    head = content[: settings.head_chars]
    tail = content[-settings.tail_chars :]
    trimmed_chars = len(content) - settings.head_chars - settings.tail_chars

    return f"{head}\n\n[... {trimmed_chars:,} characters trimmed for context efficiency ...]\n\n{tail}"


def _create_summary_placeholder(tool_name: str, original_length: int) -> str:
    """Create a summary placeholder for very old tool results."""
    return f"[Previous {tool_name} result: {original_length:,} chars - cleared for context efficiency]"


def _is_tool_result_message(msg: dict) -> bool:
    """Check if a message is a tool result."""
    return msg.get("role") == "tool"


def _is_error_result(content: Any) -> bool:
    """Check if content represents an error result."""
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
            return isinstance(parsed, dict) and "error" in parsed
        except (json.JSONDecodeError, TypeError):
            return "error" in content.lower()[:100]
    elif isinstance(content, dict):
        return "error" in content
    return False


def _strip_base64_from_content(content: Any) -> tuple[Any, int]:
    """
    Strip base64-encoded data from content to reduce token usage.

    Looks for common base64 patterns in tool results (screenshots, images, etc.)
    and replaces them with placeholders.

    Returns:
        Tuple of (stripped_content, bytes_saved)
    """
    import re

    bytes_saved = 0

    if isinstance(content, str):
        # Try to parse as JSON first
        try:
            parsed = json.loads(content)
            stripped, saved = _strip_base64_from_content(parsed)
            return json.dumps(stripped, indent=2), saved
        except (json.JSONDecodeError, TypeError):
            # Check for raw base64 patterns (long alphanumeric strings)
            # Base64 pattern: at least 1000 chars of base64 characters
            base64_pattern = r'"(?:screenshot|image|data|content|base64)":\s*"([A-Za-z0-9+/=]{1000,})"'
            matches = list(re.finditer(base64_pattern, content))

            if matches:
                result = content
                for match in reversed(matches):  # Process in reverse to maintain positions
                    full_match = match.group(0)
                    base64_data = match.group(1)
                    key_name = re.match(r'"(\w+)"', full_match).group(1)
                    size_kb = len(base64_data) * 3 / 4 / 1024  # Approximate decoded size

                    replacement = f'"{key_name}": "[BASE64_REMOVED: ~{size_kb:.1f}KB - use image_url instead]"'
                    result = result[: match.start()] + replacement + result[match.end() :]
                    bytes_saved += len(base64_data)

                return result, bytes_saved

            return content, 0

    elif isinstance(content, dict):
        result = {}
        for key, value in content.items():
            # Check for base64 fields by name
            if key.lower() in ("screenshot", "image", "image_data", "base64", "data") and isinstance(value, str):
                if len(value) > 1000 and _looks_like_base64(value):
                    size_kb = len(value) * 3 / 4 / 1024
                    result[key] = f"[BASE64_REMOVED: ~{size_kb:.1f}KB - use image_url instead]"
                    bytes_saved += len(value)
                    continue

            # Recursively process nested content
            if isinstance(value, (dict, list)):
                stripped, saved = _strip_base64_from_content(value)
                result[key] = stripped
                bytes_saved += saved
            else:
                result[key] = value

        return result, bytes_saved

    elif isinstance(content, list):
        result = []
        for item in content:
            stripped, saved = _strip_base64_from_content(item)
            result.append(stripped)
            bytes_saved += saved
        return result, bytes_saved

    return content, 0


def _looks_like_base64(s: str) -> bool:
    """Check if a string looks like base64-encoded data."""
    import re

    if len(s) < 100:
        return False

    # Check if string contains only base64 characters
    # Allow some flexibility (newlines, spaces are sometimes present)
    clean = s.replace("\n", "").replace(" ", "").replace("\r", "")

    # Base64 uses A-Z, a-z, 0-9, +, /, and = for padding
    if not re.match(r"^[A-Za-z0-9+/=]+$", clean[:1000]):  # Check first 1000 chars
        return False

    # Check if length is roughly right for base64 (multiple of 4)
    # Allow some flexibility
    return True


def _is_data_bearing_tool(tool_name: str, settings: PruningSettings) -> bool:
    """Return True if this tool returns data the LLM may need verbatim (e.g. SQL rows, file contents)."""
    lower = tool_name.lower()
    return any(lower.startswith(prefix) for prefix in settings.protect_data_tools)


def _get_tool_name_for_result(msg: dict, messages: list[dict], index: int) -> str:
    """
    Resolve the tool name for a tool-result message.

    First checks the message's own ``name`` field (set by some providers),
    then walks backwards through the conversation to find the assistant
    tool_call whose ID matches ``msg["tool_call_id"]``.
    """
    tool_name = msg.get("name", "")
    if tool_name:
        return tool_name

    tool_call_id = msg.get("tool_call_id")
    if tool_call_id:
        for prev_msg in reversed(messages[:index]):
            if prev_msg.get("role") == "assistant" and prev_msg.get("tool_calls"):
                for tc in prev_msg["tool_calls"]:
                    if tc.get("id") == tool_call_id:
                        name = tc.get("function", {}).get("name", "")
                        if name:
                            return name

    return "tool"


def _extract_result_summary(tool_name: str, content: Any) -> str:
    """
    Build a compact, informative 1-line summary of a tool result.

    Extracts the most meaningful fact (row count, error message, item count,
    created ID, etc.) so the LLM retains enough context for follow-up
    questions without keeping the full payload.

    All summaries are prefixed with RESULT_PRUNED_MARKER so the dedup-cache
    eviction logic in function_calling.py can detect them.
    """
    # Parse JSON string content
    data = content
    if isinstance(content, str):
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            preview = content[:120].replace("\n", " ").strip()
            return f"{RESULT_PRUNED_MARKER}{tool_name}: {preview}]"

    # List at top level
    if isinstance(data, list):
        return f"{RESULT_PRUNED_MARKER}{tool_name}: returned {len(data)} items]"

    if not isinstance(data, dict):
        return f"{RESULT_PRUNED_MARKER}{tool_name}: completed]"

    # --- Error cases ---
    if data.get("error"):
        error_msg = str(data["error"])[:120].replace("\n", " ").strip()
        return f"{RESULT_PRUNED_MARKER}{tool_name} failed: {error_msg}]"

    if data.get("success") is False:
        return f"{RESULT_PRUNED_MARKER}{tool_name}: failed]"

    # --- Success cases: extract most informative fact ---
    if "row_count" in data:
        return f"{RESULT_PRUNED_MARKER}{tool_name}: returned {data['row_count']} rows]"

    if "rows" in data and isinstance(data["rows"], list):
        return f"{RESULT_PRUNED_MARKER}{tool_name}: returned {len(data['rows'])} rows]"

    if "messages" in data and isinstance(data["messages"], list):
        return f"{RESULT_PRUNED_MARKER}{tool_name}: returned {len(data['messages'])} messages]"

    if "files" in data and isinstance(data["files"], list):
        return f"{RESULT_PRUNED_MARKER}{tool_name}: listed {len(data['files'])} files]"

    if "items" in data and isinstance(data["items"], list):
        return f"{RESULT_PRUNED_MARKER}{tool_name}: returned {len(data['items'])} items]"

    if "number" in data:
        return f"{RESULT_PRUNED_MARKER}{tool_name}: #{data['number']}]"

    if "id" in data:
        return f"{RESULT_PRUNED_MARKER}{tool_name}: id={data['id']}]"

    if "url" in data:
        url_preview = str(data["url"])[:80]
        return f"{RESULT_PRUNED_MARKER}{tool_name}: url={url_preview}]"

    if "content" in data and isinstance(data["content"], str):
        preview = data["content"][:80].replace("\n", " ").strip()
        return f"{RESULT_PRUNED_MARKER}{tool_name}: content='{preview}']"

    if data.get("success") is True:
        return f"{RESULT_PRUNED_MARKER}{tool_name}: succeeded]"

    if data.get("ok") is True:
        return f"{RESULT_PRUNED_MARKER}{tool_name}: ok]"

    # Generic fallback: list top-level keys
    top_keys = list(data.keys())[:5]
    return f"{RESULT_PRUNED_MARKER}{tool_name}: completed — keys={top_keys}]"


def prune_tool_results(
    messages: list[dict[str, Any]], settings: PruningSettings | None = None
) -> tuple[list[dict[str, Any]], PruningStats]:
    """
    Prune old tool results from conversation history.

    Args:
        messages: List of conversation messages in OpenAI format
        settings: Pruning configuration

    Returns:
        Tuple of (pruned messages, pruning statistics)
    """
    if settings is None:
        settings = PruningSettings()

    stats = PruningStats(
        original_messages=len(messages), original_chars=sum(_get_content_length(m.get("content", "")) for m in messages)
    )

    if not settings.enabled:
        stats.pruned_messages = stats.original_messages
        stats.pruned_chars = stats.original_chars
        return messages, stats

    # FIRST PASS: Strip base64 content from ALL tool results (regardless of count)
    # This prevents context bloat from screenshots/images even with few tool calls
    total_base64_saved = 0
    messages_with_stripped_base64 = []
    for msg in messages:
        if _is_tool_result_message(msg):
            content = msg.get("content", "")
            stripped_content, saved = _strip_base64_from_content(content)
            if saved > 0:
                total_base64_saved += saved
                messages_with_stripped_base64.append({**msg, "content": stripped_content})
            else:
                messages_with_stripped_base64.append(msg)
        else:
            messages_with_stripped_base64.append(msg)

    if total_base64_saved > 0:
        logger.info(
            f"Context pruning: Stripped {total_base64_saved:,} chars of base64 data "
            f"(~{total_base64_saved // 4:,} tokens) from tool results"
        )

    messages = messages_with_stripped_base64

    # Recalculate original chars after base64 stripping
    stats.original_chars = sum(_get_content_length(m.get("content", "")) for m in messages)

    # Find all tool result message indices
    tool_indices = [i for i, m in enumerate(messages) if _is_tool_result_message(m)]

    stats.tool_results_count = len(tool_indices)

    if len(tool_indices) <= settings.keep_last_results:
        # Not enough tool results to prune
        stats.pruned_messages = len(messages)
        stats.pruned_chars = stats.original_chars
        stats.chars_saved = total_base64_saved
        stats.estimated_tokens_saved = total_base64_saved // 4
        if total_base64_saved > 0:
            logger.debug(f"Context pruning: Only {len(tool_indices)} tool results, but stripped base64 data")
        else:
            logger.debug(f"Context pruning: Only {len(tool_indices)} tool results, no pruning needed")
        return messages, stats

    # Indices of tool results to potentially prune (all except last N)
    prune_candidates = set(tool_indices[: -settings.keep_last_results])

    # Create new message list with pruned content
    pruned_messages = []
    total_tool_chars = 0

    for i, msg in enumerate(messages):
        if i not in prune_candidates:
            # Keep message as-is
            pruned_messages.append(msg)
            if _is_tool_result_message(msg):
                total_tool_chars += _get_content_length(msg.get("content", ""))
            continue

        # This is an old tool result - consider pruning
        content = msg.get("content", "")
        content_str = _get_content_as_string(content)
        original_length = len(content_str)
        is_error = _is_error_result(content)

        # Old error results: always replace with a compact summary so they stop
        # accumulating tokens across every subsequent turn.
        if is_error and settings.prune_error_results:
            tool_name = _get_tool_name_for_result(msg, messages, i)
            summary = _extract_result_summary(tool_name, content)
            pruned_messages.append({**msg, "content": summary})
            total_tool_chars += len(summary)
            stats.tool_results_pruned += 1
            logger.debug(
                f"Context pruning: Replaced error result ({original_length:,} chars) with summary for {tool_name}"
            )
            continue

        # Non-error results: keep errors with old flag behaviour intact
        if is_error and not settings.prune_error_results:
            pruned_messages.append(msg)
            total_tool_chars += original_length
            continue

        # Check if we need to prune based on size
        if original_length > settings.max_result_chars:
            tool_name = _get_tool_name_for_result(msg, messages, i)
            is_data = _is_data_bearing_tool(tool_name, settings)

            if is_data:
                # Data-bearing tools (SELECT, read_csv, fetch, etc.): always keep
                # head+tail so the LLM still sees actual row/file data, not just
                # a count.  Never reduce to a 1-liner — that destroys the data.
                trimmed_content = _trim_content(content_str, settings)
                pruned_msg = {**msg, "content": trimmed_content}
                total_tool_chars += len(trimmed_content)
                stats.data_bearing_pruned += 1
                logger.debug(
                    f"Context pruning: Trimmed data-bearing tool result from "
                    f"{original_length:,} chars (head+tail preserved) for {tool_name}"
                )
            elif settings.use_meaningful_summaries:
                # Non-data tools: replace with informative 1-liner
                try:
                    summary = _extract_result_summary(tool_name, content)
                except Exception:
                    summary = _create_summary_placeholder(tool_name, original_length)
                pruned_msg = {**msg, "content": summary}
                total_tool_chars += len(summary)
                logger.debug(
                    f"Context pruning: Replaced tool result ({original_length:,} chars) with summary for {tool_name}"
                )
            else:
                # Legacy behaviour: keep head + tail
                trimmed_content = _trim_content(content_str, settings)
                pruned_msg = {**msg, "content": trimmed_content}
                total_tool_chars += len(trimmed_content)
                logger.debug(f"Context pruning: Trimmed tool result from {original_length:,} chars for {tool_name}")

            pruned_messages.append(pruned_msg)
            stats.tool_results_pruned += 1
        else:
            # Small results: keep as-is
            pruned_messages.append(msg)
            total_tool_chars += original_length

    # If total tool chars still exceeds limit, do aggressive pruning
    if total_tool_chars > settings.max_total_tool_chars:
        logger.info(
            f"Context pruning: Total tool chars ({total_tool_chars:,}) exceeds limit "
            f"({settings.max_total_tool_chars:,}), doing aggressive pruning"
        )
        pruned_messages = _aggressive_prune(pruned_messages, settings, stats)

    # Calculate final stats
    stats.pruned_messages = len(pruned_messages)
    stats.pruned_chars = sum(_get_content_length(m.get("content", "")) for m in pruned_messages)
    stats.chars_saved = stats.original_chars - stats.pruned_chars
    stats.estimated_tokens_saved = stats.chars_saved // 4  # ~4 chars per token

    if stats.chars_saved > 0:
        logger.info(
            f"Context pruning: Saved {stats.chars_saved:,} chars (~{stats.estimated_tokens_saved:,} tokens) "
            f"by pruning {stats.tool_results_pruned} tool results"
        )

    return pruned_messages, stats


def _aggressive_prune(
    messages: list[dict[str, Any]], settings: PruningSettings, stats: PruningStats
) -> list[dict[str, Any]]:
    """
    Aggressively prune when total chars still exceed limit.

    Replaces old tool results with short summaries.
    """
    # Find tool results (excluding last N)
    tool_indices = [i for i, m in enumerate(messages) if _is_tool_result_message(m)]

    if len(tool_indices) <= settings.keep_last_results:
        return messages

    # Replace older results with placeholders
    prune_indices = set(tool_indices[: -settings.keep_last_results])
    pruned_messages = []

    for i, msg in enumerate(messages):
        if i not in prune_indices:
            pruned_messages.append(msg)
            continue

        # Replace with compact summary (or head+tail for data-bearing tools)
        content = msg.get("content", "")
        original_length = _get_content_length(content)
        tool_name = _get_tool_name_for_result(msg, messages, i)
        is_data = _is_data_bearing_tool(tool_name, settings)

        if is_data:
            content_str = _get_content_as_string(content)
            placeholder = _trim_content(content_str, settings)
            stats.data_bearing_pruned += 1
        else:
            try:
                placeholder = _extract_result_summary(tool_name, content)
            except Exception:
                placeholder = _create_summary_placeholder(tool_name, original_length)

        pruned_msg = {**msg, "content": placeholder}
        pruned_messages.append(pruned_msg)
        stats.tool_results_pruned += 1

    return pruned_messages


def estimate_context_usage(
    messages: list[dict[str, Any]], system_prompt: str = "", tools: list[dict] | None = None
) -> dict[str, int]:
    """
    Estimate context usage in characters and tokens.

    Args:
        messages: Conversation messages
        system_prompt: System prompt text
        tools: List of tool definitions

    Returns:
        Dictionary with usage estimates
    """
    message_chars = sum(_get_content_length(m.get("content", "")) for m in messages)
    system_chars = len(system_prompt)
    tools_chars = len(json.dumps(tools)) if tools else 0

    total_chars = message_chars + system_chars + tools_chars

    # Tool results specifically
    tool_result_chars = sum(_get_content_length(m.get("content", "")) for m in messages if _is_tool_result_message(m))

    return {
        "message_chars": message_chars,
        "system_prompt_chars": system_chars,
        "tools_definition_chars": tools_chars,
        "tool_results_chars": tool_result_chars,
        "total_chars": total_chars,
        "estimated_tokens": total_chars // 4,
        "tool_results_percentage": round(tool_result_chars / total_chars * 100, 1) if total_chars > 0 else 0,
    }


def should_prune(
    messages: list[dict[str, Any]], context_window_tokens: int = 128000, threshold_percentage: float = 0.3
) -> bool:
    """
    Check if pruning should be triggered.

    Args:
        messages: Conversation messages
        context_window_tokens: Model's context window size
        threshold_percentage: Trigger pruning at this % of context

    Returns:
        True if pruning should be triggered
    """
    usage = estimate_context_usage(messages)
    estimated_tokens = usage["estimated_tokens"]
    threshold_tokens = int(context_window_tokens * threshold_percentage)

    return estimated_tokens > threshold_tokens
