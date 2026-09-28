"""
Secret and PII scanner for user-provided content.

Scans chat messages for accidentally-pasted secrets (API keys, tokens,
credentials) and PII (SSNs, credit card numbers). Operates at ingest time --
before the content is stored in the database.

Policy:
- REDACT mode (default): Replace matched content with a placeholder and log a warning.
- ALERT mode: Store as-is but log the detection for SIEM forwarding.
- BLOCK mode: Reject the message entirely (use sparingly -- high false-positive risk).

Enabled by default. Disable per-deployment via SECRETS_SCANNER_ENABLED=false.
Mode controlled by SECRETS_SCANNER_MODE=redact|alert|block (default: alert).
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from enum import StrEnum

logger = logging.getLogger(__name__)

_ENABLED = os.getenv("SECRETS_SCANNER_ENABLED", "true").lower() not in ("false", "0", "no")
_MODE = os.getenv("SECRETS_SCANNER_MODE", "alert").lower()


class ScanMode(StrEnum):
    REDACT = "redact"
    ALERT = "alert"
    BLOCK = "block"


@dataclass
class ScanResult:
    has_findings: bool
    findings: list[str]  # list of finding type names
    content: str  # original or redacted content
    blocked: bool = False


# ---------------------------------------------------------------------------
# Pattern registry -- (name, compiled_regex, replacement)
# ---------------------------------------------------------------------------
_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    # AWS Access Key IDs
    (
        "aws_access_key",
        re.compile(r"(?<![A-Z0-9])(AKIA|ASIA|AROA|AIDA)[A-Z0-9]{16}(?![A-Z0-9])"),
        "[AWS_ACCESS_KEY]",
    ),
    # AWS Secret Access Keys (40-char base64)
    (
        "aws_secret_key",
        re.compile(r"(?<![A-Za-z0-9/+=])[A-Za-z0-9/+=]{40}(?![A-Za-z0-9/+=])"),
        "[AWS_SECRET_KEY]",
    ),
    # GitHub personal access tokens
    (
        "github_token",
        re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,255}"),
        "[GITHUB_TOKEN]",
    ),
    # GitHub fine-grained PATs
    (
        "github_fine_grained",
        re.compile(r"github_pat_[A-Za-z0-9_]{82,}"),
        "[GITHUB_TOKEN]",
    ),
    # Slack tokens
    (
        "slack_token",
        re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,200}"),
        "[SLACK_TOKEN]",
    ),
    # Generic API/secret keys: sk-..., sk_live_..., pk_...
    (
        "generic_api_key",
        re.compile(r"\b(sk|pk|rk|ak)[-_](live|test|prod|secret)?[-_]?[A-Za-z0-9]{20,100}\b"),
        "[API_KEY]",
    ),
    # Stripe keys
    (
        "stripe_key",
        re.compile(r"(sk|rk)_(live|test)_[A-Za-z0-9]{24,}"),
        "[STRIPE_KEY]",
    ),
    # Private keys (PEM blocks)
    (
        "private_key",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        "[PRIVATE_KEY_HEADER]",
    ),
    # SSNs
    (
        "ssn",
        re.compile(r"\b\d{3}[- ]\d{2}[- ]\d{4}\b"),
        "[SSN]",
    ),
    # Credit card numbers (Visa, Mastercard, Amex -- simplified Luhn prefix check)
    (
        "credit_card",
        re.compile(
            r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b"
        ),
        "[CARD_NUMBER]",
    ),
    # Password in JSON/form context: "password": "value"
    (
        "password_in_json",
        re.compile(r'"password"\s*:\s*"[^"]{8,}"', re.I),
        '"password": "[REDACTED]"',
    ),
    # Connection strings with credentials
    (
        "connection_string",
        re.compile(r"(?:postgresql|mysql|mongodb|redis)://[^:]+:[^@]+@"),
        "[DB_CONN_STRING]",
    ),
    # Bearer tokens
    (
        "bearer_token",
        re.compile(r"\bBearer\s+[A-Za-z0-9\-._~+/]+=*", re.I),
        "Bearer [REDACTED]",
    ),
]

# AWS secret key is high false-positive risk -- only flag if near an AWS key ID in the text
_HIGH_FP_PATTERNS = {"aws_secret_key"}

_AWS_KEY_ID_RE = re.compile(r"(AKIA|ASIA|AROA|AIDA)[A-Z0-9]{16}")


def scan(content: str, agent_id: str | None = None) -> ScanResult:
    """
    Scan content for secrets and PII.

    Returns ScanResult with findings and (if mode=redact) redacted content.
    Never raises -- exceptions return an empty ScanResult to fail open.
    """
    if not _ENABLED or not content or not isinstance(content, str):
        return ScanResult(has_findings=False, findings=[], content=content)

    try:
        return _scan_impl(content, agent_id)
    except Exception as exc:
        logger.warning("Secret scanner failed (fail-open): %s", exc)
        return ScanResult(has_findings=False, findings=[], content=content)


def _scan_impl(content: str, agent_id: str | None) -> ScanResult:
    findings: list[str] = []
    redacted = content
    mode = ScanMode(_MODE) if _MODE in ScanMode.__members__.values() else ScanMode.ALERT

    for name, pattern, replacement in _PATTERNS:
        # High FP patterns: only flag if AWS key ID is nearby
        if name in _HIGH_FP_PATTERNS:
            if not _AWS_KEY_ID_RE.search(content):
                continue

        if pattern.search(redacted if mode == ScanMode.REDACT else content):
            findings.append(name)
            if mode == ScanMode.REDACT:
                redacted = pattern.sub(replacement, redacted)

    if findings:
        logger.warning(
            "Secret/PII detected in message content (agent=%s, mode=%s, findings=%s)",
            agent_id,
            mode.value,
            findings,
        )
        if mode == ScanMode.BLOCK:
            return ScanResult(has_findings=True, findings=findings, content=content, blocked=True)

    return ScanResult(
        has_findings=bool(findings),
        findings=findings,
        content=redacted if mode == ScanMode.REDACT else content,
    )
