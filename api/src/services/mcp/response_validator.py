"""Validate MCP tool responses for prompt injection and oversized payloads."""
from __future__ import annotations
import logging
import re

logger = logging.getLogger(__name__)

# Hard limits
MAX_RESPONSE_CHARS = 50_000   # 50K chars per tool response
MAX_RESPONSE_ITEMS = 100      # max items in a list response

# Prompt injection patterns in tool responses (simplified — LLM will also scan)
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.I),
    re.compile(r"you\s+are\s+now\s+(a\s+)?", re.I),
    re.compile(r"system\s*:\s*(ignore|forget|disregard)", re.I),
    re.compile(r"<\s*/?system\s*>", re.I),
    re.compile(r"\[INST\]|\[/INST\]|\[SYS\]|\[/SYS\]", re.I),
    re.compile(r"###\s*(Human|Assistant|System)\s*:", re.I),
]

def validate_mcp_response(tool_name: str, result: object) -> object:
    """
    Validate and sanitize an MCP tool response.

    - Truncates oversized string results
    - Logs (but does NOT block) prompt injection patterns — the LLM
      is already sandboxed; blocking would cause false positives on
      legitimate technical content.
    - Returns the (possibly truncated) result unchanged in structure.
    """
    if isinstance(result, str):
        if len(result) > MAX_RESPONSE_CHARS:
            logger.warning("MCP tool %r response truncated (%d → %d chars)", tool_name, len(result), MAX_RESPONSE_CHARS)
            result = result[:MAX_RESPONSE_CHARS] + "\n[... truncated by security policy ...]"
        _check_injection(tool_name, result)
    elif isinstance(result, list):
        if len(result) > MAX_RESPONSE_ITEMS:
            logger.warning("MCP tool %r response list truncated (%d → %d items)", tool_name, len(result), MAX_RESPONSE_ITEMS)
            result = result[:MAX_RESPONSE_ITEMS]
        for item in result:
            if isinstance(item, str):
                _check_injection(tool_name, item)
    elif isinstance(result, dict):
        text = str(result)
        if len(text) > MAX_RESPONSE_CHARS:
            logger.warning("MCP tool %r response dict too large (%d chars)", tool_name, len(text))
        _check_injection(tool_name, text[:MAX_RESPONSE_CHARS])
    return result


def _check_injection(tool_name: str, text: str) -> None:
    for pat in _INJECTION_PATTERNS:
        if pat.search(text):
            logger.warning(
                "MCP tool %r response contains possible prompt injection pattern: %r",
                tool_name, pat.pattern,
            )
            break  # one warning per response is enough
