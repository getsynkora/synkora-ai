"""Redact PII and secrets from LLM traces before sending to Langfuse."""
from __future__ import annotations
import os
import re

# Enabled by default; set LANGFUSE_REDACT_TRACES=false to disable
_ENABLED = os.getenv("LANGFUSE_REDACT_TRACES", "true").lower() not in ("false", "0", "no")

# Patterns: (compiled_regex, replacement_string)
_PATTERNS: list[tuple[re.Pattern, str]] = [
    # AWS keys
    (re.compile(r"(?<![A-Z0-9])(AKIA|ASIA|AROA)[A-Z0-9]{16}(?![A-Z0-9])"), "[AWS_KEY]"),
    # GitHub tokens
    (re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,}"), "[GITHUB_TOKEN]"),
    # Generic API keys: sk-... / sk_live_... / pk_...
    (re.compile(r"\b(sk|pk)[-_](live|test|prod)?[-_]?[A-Za-z0-9]{20,}\b"), "[API_KEY]"),
    # Bearer tokens in text
    (re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.I), "Bearer [REDACTED]"),
    # Credit card numbers (simplified Luhn-format patterns)
    (re.compile(r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\b"), "[CARD_NUMBER]"),
    # SSN
    (re.compile(r"\b\d{3}[- ]\d{2}[- ]\d{4}\b"), "[SSN]"),
    # Private keys
    (re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----.*?-----END \1PRIVATE KEY-----", re.S), "[PRIVATE_KEY]"),
]


def redact(text: str) -> str:
    """Redact known PII/secret patterns from a string. No-op if redaction disabled."""
    if not _ENABLED or not isinstance(text, str):
        return text
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def redact_messages(messages: list[dict]) -> list[dict]:
    """Redact PII from a list of {role, content} message dicts."""
    if not _ENABLED:
        return messages
    return [
        {**msg, "content": redact(msg["content"]) if isinstance(msg.get("content"), str) else msg.get("content")}
        for msg in messages
    ]
