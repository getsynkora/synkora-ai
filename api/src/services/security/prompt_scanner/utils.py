"""Utility helpers for prompt scanner normalization and span mapping."""

from __future__ import annotations

import hashlib
import re
import unicodedata

BIDI_CONTROL_CHARS = "\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\u200f\u200e"
ZERO_WIDTH_CHARS = ["\u200b", "\u200c", "\u200d", "\ufeff"]


def normalize_text(text: str, max_chars: int | None = None) -> str:
    """Normalize text for consistent matching."""
    text = unicodedata.normalize("NFKC", text)
    for char in BIDI_CONTROL_CHARS:
        text = text.replace(char, "")
    if max_chars is not None:
        text = text[:max_chars]
    normalized = re.sub(r"\s+", " ", text.strip())
    normalized = decode_obfuscations(normalized)
    return normalized.lower()


def decode_obfuscations(text: str) -> str:
    """Decode common obfuscation techniques."""
    import html
    import urllib.parse

    decoded = text
    try:
        decoded = html.unescape(decoded)
    except Exception:
        pass

    try:
        decoded = urllib.parse.unquote(decoded)
    except Exception:
        pass

    for char in ZERO_WIDTH_CHARS:
        decoded = decoded.replace(char, "")

    return decoded


def extract_context(text: str, start: int, end: int, context_size: int = 100) -> str:
    """Extract surrounding context for a matched span."""
    context_start = max(0, start - context_size)
    context_end = min(len(text), end + context_size)
    snippet = text[context_start:context_end]
    if context_start > 0:
        snippet = "..." + snippet
    if context_end < len(text):
        snippet = snippet + "..."
    return snippet


def locate_text_span(original_text: str, matched_text: str, fallback: tuple[int, int] | None = None) -> tuple[int, int]:
    """Map a normalized or phrase match back to the original text span."""
    snippet = matched_text.strip()
    if not snippet:
        return fallback or (0, 0)

    flexible_pattern = re.escape(snippet).replace(r"\ ", r"\s+")
    resolved = re.search(flexible_pattern, original_text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
    if resolved:
        return resolved.span()

    lowered_text = original_text.lower()
    lowered_snippet = snippet.lower()
    position = lowered_text.find(lowered_snippet)
    if position >= 0:
        return position, position + len(snippet)

    if fallback is None:
        return 0, min(len(original_text), len(snippet))

    start, end = fallback
    start = max(0, min(start, len(original_text)))
    end = max(start, min(end, len(original_text)))
    return start, end


def hash_text(text: str) -> str:
    """Create a short stable hash for logging and metrics."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]
