"""
Output Sanitizer for Agent Responses

CRITICAL: Enterprise-grade output validation to prevent information leakage.
Sanitizes agent responses before sending to users to prevent:
- API key/token leakage
- PII exposure
- Internal system information disclosure
- Sensitive credential exposure
"""

import hashlib
import logging
import re
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SanitizationAction(Enum):
    """Actions to take when sensitive data is detected"""

    REDACT = "redact"  # Replace with [REDACTED]
    MASK = "mask"  # Partial masking (e.g., sk-***xyz)
    REMOVE = "remove"  # Remove entirely
    BLOCK = "block"  # Block entire response


@dataclass
class SanitizationResult:
    """Result of sanitization scan"""

    is_safe: bool
    sanitized_content: str
    detections: list[dict]
    action_taken: str
    original_hash: str


class OutputSanitizer:
    """
    Multi-layer output sanitizer for agent responses.

    Sanitization Layers:
    1. Credential detection (API keys, passwords, tokens)
    2. PII detection (emails, phones, SSNs, credit cards)
    3. System path detection (internal file paths)
    4. Database query detection (SQL with sensitive data)
    5. Error message sanitization (stack traces, internal errors)
    """

    # Allowlist patterns - content matching these patterns should NOT be sanitized
    # These are legitimate outputs that may contain paths or credentials-like strings
    ALLOWLIST_PATTERNS = [
        # S3/MinIO presigned URLs - contain paths and signature parameters that look sensitive
        # but are actually legitimate browser-accessible URLs
        r"https?://[^\s]+\?[^\s]*X-Amz-Algorithm=[^\s]*X-Amz-Signature=[^\s]*",
        # CloudFront signed URLs
        r"https?://[^\s]+\?[^\s]*Signature=[^\s]*&Key-Pair-Id=[^\s]*",
        # Azure SAS URLs
        r"https?://[^\s]+\?[^\s]*sig=[^\s]*&se=[^\s]*&sv=[^\s]*",
        # GCS signed URLs
        r"https?://storage\.googleapis\.com/[^\s]+\?[^\s]*Signature=[^\s]*",
    ]

    # Layer 1: Credential patterns
    CREDENTIAL_PATTERNS = {
        "api_key_generic": {
            "pattern": r"(?i)(?:api[_-]?key|apikey|api[_-]?token)[\s]*[:=][\s]*['\"]?([a-zA-Z0-9_\-]{20,})['\"]?",
            "action": SanitizationAction.REDACT,
            "severity": "CRITICAL",
        },
        "openai_key": {"pattern": r"sk-[a-zA-Z0-9]{48}", "action": SanitizationAction.REDACT, "severity": "CRITICAL"},
        "openai_key_proj": {
            "pattern": r"sk-proj-[a-zA-Z0-9_\-]{80,}",
            "action": SanitizationAction.REDACT,
            "severity": "CRITICAL",
        },
        "anthropic_key": {
            "pattern": r"sk-ant-[a-zA-Z0-9\-]{90,}",
            "action": SanitizationAction.REDACT,
            "severity": "CRITICAL",
        },
        "aws_key": {"pattern": r"AKIA[0-9A-Z]{16}", "action": SanitizationAction.REDACT, "severity": "CRITICAL"},
        "aws_secret": {
            "pattern": r"(?i)aws[_-]?secret[_-]?access[_-]?key[\s]*[:=][\s]*['\"]?([a-zA-Z0-9/+=]{40})['\"]?",
            "action": SanitizationAction.REDACT,
            "severity": "CRITICAL",
        },
        "github_token": {
            "pattern": r"gh[ps]_[a-zA-Z0-9]{36}",
            "action": SanitizationAction.REDACT,
            "severity": "CRITICAL",
        },
        "github_fine_grained": {
            "pattern": r"github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59}",
            "action": SanitizationAction.REDACT,
            "severity": "CRITICAL",
        },
        "google_api_key": {
            "pattern": r"AIza[0-9A-Za-z\-_]{35}",
            "action": SanitizationAction.REDACT,
            "severity": "CRITICAL",
        },
        "stripe_key": {
            "pattern": r"(?:sk|pk)_(?:live|test)_[a-zA-Z0-9]{24,}",
            "action": SanitizationAction.REDACT,
            "severity": "CRITICAL",
        },
        "slack_token": {
            "pattern": r"xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24,32}",
            "action": SanitizationAction.REDACT,
            "severity": "CRITICAL",
        },
        "slack_webhook": {
            "pattern": r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[a-zA-Z0-9]+",
            "action": SanitizationAction.REDACT,
            "severity": "CRITICAL",
        },
        "discord_webhook": {
            "pattern": r"https://discord(?:app)?\.com/api/webhooks/[0-9]+/[a-zA-Z0-9_\-]+",
            "action": SanitizationAction.REDACT,
            "severity": "CRITICAL",
        },
        "jwt_token": {
            "pattern": r"eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*",
            "action": SanitizationAction.REDACT,
            "severity": "HIGH",
        },
        "password_field": {
            "pattern": r"(?i)(?:password|passwd|pwd)[\s]*[:=][\s]*['\"]?([^\s'\"]{8,})['\"]?",
            "action": SanitizationAction.REDACT,
            "severity": "CRITICAL",
        },
        "bearer_token": {
            "pattern": r"(?i)bearer[\s]+([a-zA-Z0-9_\-\.=]+)",
            "action": SanitizationAction.REDACT,
            "severity": "HIGH",
        },
        "private_key": {
            "pattern": r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
            "action": SanitizationAction.BLOCK,
            "severity": "CRITICAL",
        },
        "sendgrid_key": {
            "pattern": r"SG\.[a-zA-Z0-9_\-]{22}\.[a-zA-Z0-9_\-]{43}",
            "action": SanitizationAction.REDACT,
            "severity": "CRITICAL",
        },
        "twilio_key": {"pattern": r"SK[a-f0-9]{32}", "action": SanitizationAction.REDACT, "severity": "CRITICAL"},
        "mailchimp_key": {
            "pattern": r"[a-f0-9]{32}-us[0-9]{1,2}",
            "action": SanitizationAction.REDACT,
            "severity": "CRITICAL",
        },
    }

    # Layer 2: PII patterns
    # NOTE: email addresses are intentionally excluded here. They are user-configured
    # values (e.g. report recipients) that agents legitimately reference in their
    # responses. Masking them here causes the masked value to persist in conversation
    # history, breaking subsequent runs that try to use the address. Email PII in
    # tool *results* is handled separately by PIIRedactor with proper token restoration.
    PII_PATTERNS = {
        "phone_us": {
            "pattern": r"\b(\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b",
            "action": SanitizationAction.MASK,
            "severity": "MEDIUM",
        },
        "ssn": {"pattern": r"\b\d{3}-\d{2}-\d{4}\b", "action": SanitizationAction.REDACT, "severity": "HIGH"},
        "credit_card": {"pattern": r"\b(?:\d[ -]*?){13,16}\b", "action": SanitizationAction.REDACT, "severity": "HIGH"},
        "ip_address": {
            "pattern": r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b",
            "action": SanitizationAction.MASK,
            "severity": "LOW",
        },
    }

    # Layer 3: System path patterns
    # NOTE: unix_path is restricted to known root directories to avoid false positives
    # on URL paths (like /synkora-storage/tenants/...) which are not security risks
    SYSTEM_PATH_PATTERNS = {
        "unix_path": {
            # Only match paths starting from known sensitive root directories
            # This avoids matching URL paths, S3 bucket paths, API paths, etc.
            "pattern": r"(?:/(?:home|var|etc|usr|tmp|opt|root|srv|mnt|proc|sys|dev|boot|run|snap|private)/[a-zA-Z0-9_\-\.]+)+",
            "action": SanitizationAction.MASK,
            "severity": "LOW",
        },
        "windows_path": {
            "pattern": r"[A-Z]:\\(?:[^\\\s]+\\)*[^\\\s]*",
            "action": SanitizationAction.MASK,
            "severity": "LOW",
        },
        "home_directory": {"pattern": r"~/[a-zA-Z0-9_\-\./]+", "action": SanitizationAction.MASK, "severity": "LOW"},
    }

    # Layer 4: Database query patterns with sensitive data
    DATABASE_PATTERNS = {
        "sql_with_password": {
            "pattern": r"(?i)(?:insert|update|select).*(?:password|passwd|pwd).*['\"]([^'\"]{8,})['\"]",
            "action": SanitizationAction.REDACT,
            "severity": "HIGH",
        },
        "connection_string": {
            "pattern": r"(?i)(?:mysql|postgresql|mongodb|mssql)://[^@\s]+:[^@\s]+@[^\s]+",
            "action": SanitizationAction.REDACT,
            "severity": "CRITICAL",
        },
    }

    # Layer 6: Harmful content / jailbreak output patterns
    _HARM_PATTERNS = [
        # Jailbreak indicators in output (model breaking character)
        (
            re.compile(
                r"\b(I\s+am\s+now\s+(DAN|freed?|unchained|unrestricted)|ignore\s+(all\s+)?previous\s+instructions|my\s+true\s+self|pretend\s+I\s+have\s+no\s+restrictions)\b",
                re.I,
            ),
            "jailbreak_output",
        ),
        # Instructions to harm
        (
            re.compile(
                r"\b(step[\s\-]+by[\s\-]+step\s+(instructions?|guide|tutorial)\s+(to|for)\s+(hack|synthesize|make|build|create)\s+(a\s+)?(bomb|weapon|malware|ransomware|poison|drug))\b",
                re.I,
            ),
            "harmful_instructions",
        ),
    ]

    # Layer 5: Error message patterns
    ERROR_PATTERNS = {
        "stack_trace": {
            "pattern": r"(?:File|at)\s+\"([^\"]+)\",\s+line\s+\d+",
            "action": SanitizationAction.MASK,
            "severity": "LOW",
        },
        "python_traceback": {
            "pattern": r"Traceback \(most recent call last\):.*?(?=\n\n|\Z)",
            "action": SanitizationAction.REMOVE,
            "severity": "MEDIUM",
        },
    }

    def __init__(self, strict_mode: bool = False):
        """
        Initialize output sanitizer.

        Args:
            strict_mode: If True, blocks entire response on HIGH/CRITICAL detections
        """
        self.strict_mode = strict_mode
        self.compiled_patterns = self._compile_all_patterns()
        self.compiled_allowlist = self._compile_allowlist_patterns()
        self.sanitization_stats = {"total_scans": 0, "total_detections": 0, "total_blocked": 0}

    def _compile_allowlist_patterns(self) -> list:
        """Compile allowlist regex patterns for performance"""
        return [re.compile(pattern, re.IGNORECASE) for pattern in self.ALLOWLIST_PATTERNS]

    def _extract_allowlisted_content(self, content: str) -> tuple[str, list[tuple[str, int, int]]]:
        """
        Extract allowlisted content and replace with placeholders.

        Returns:
            Tuple of (content_with_placeholders, list of (original_content, start, end))
        """
        extracted = []
        modified_content = content

        for pattern in self.compiled_allowlist:
            matches = list(pattern.finditer(modified_content))
            # Process in reverse order to maintain positions
            for match in reversed(matches):
                original = match.group(0)
                placeholder = f"__ALLOWLIST_{len(extracted)}__"
                extracted.insert(0, (original, match.start(), match.end()))
                modified_content = modified_content[: match.start()] + placeholder + modified_content[match.end() :]

        return modified_content, extracted

    def _restore_allowlisted_content(self, content: str, extracted: list[tuple[str, int, int]]) -> str:
        """Restore allowlisted content from placeholders."""
        result = content
        for i, (original, _, _) in enumerate(extracted):
            placeholder = f"__ALLOWLIST_{i}__"
            result = result.replace(placeholder, original)
        return result

    def _compile_all_patterns(self) -> dict:
        """Compile all regex patterns for performance"""
        compiled = {}

        pattern_groups = {
            "credentials": self.CREDENTIAL_PATTERNS,
            "pii": self.PII_PATTERNS,
            "system_paths": self.SYSTEM_PATH_PATTERNS,
            "database": self.DATABASE_PATTERNS,
            "errors": self.ERROR_PATTERNS,
        }

        for group_name, patterns in pattern_groups.items():
            compiled[group_name] = {}
            for pattern_name, config in patterns.items():
                compiled[group_name][pattern_name] = {
                    "regex": re.compile(config["pattern"], re.MULTILINE | re.DOTALL),
                    "action": config["action"],
                    "severity": config["severity"],
                }

        return compiled

    def check_harmful_content(self, text: str) -> dict:
        """Check output for harmful content patterns (jailbreak indicators, harmful instructions)."""
        for pattern, category in self._HARM_PATTERNS:
            if pattern.search(text):
                return {"is_harmful": True, "category": category}
        return {"is_harmful": False}

    def sanitize(self, content: str, context: str | None = None) -> SanitizationResult:
        """
        Sanitize output content before sending to user.

        Args:
            content: Response content to sanitize
            context: Optional context for logging

        Returns:
            SanitizationResult with sanitized content and detection info
        """
        if not content or not content.strip():
            return self._safe_result(content)

        self.sanitization_stats["total_scans"] += 1

        # Create hash of original content for audit trail
        original_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

        # Harm check: detect jailbreak output or harmful instructions before any other processing
        harm_result = self.check_harmful_content(content)
        if harm_result["is_harmful"]:
            logger.warning(
                "Harmful content detected in LLM output - Category: %s, Context: %s, Hash: %s",
                harm_result["category"],
                context,
                original_hash,
            )
            self.sanitization_stats["total_blocked"] += 1
            return SanitizationResult(
                is_safe=False,
                sanitized_content="[Content blocked by safety filter]",
                detections=[{"type": f"harm:{harm_result['category']}", "severity": "CRITICAL", "action": "block"}],
                action_taken="BLOCKED",
                original_hash=original_hash,
            )

        # Step 1: Extract allowlisted content (e.g., S3 presigned URLs) and replace
        # with placeholders so they don't get caught by sanitization patterns
        sanitized, allowlisted = self._extract_allowlisted_content(content)

        if allowlisted:
            logger.debug(f"Allowlisted {len(allowlisted)} items from sanitization (context: {context})")

        detections = []
        should_block = False

        # Scan all pattern groups (on content with placeholders)
        for group_name, patterns in self.compiled_patterns.items():
            for pattern_name, config in patterns.items():
                matches = config["regex"].finditer(sanitized)

                for match in matches:
                    # Skip matches that are inside allowlist placeholders
                    matched_text = match.group(0)
                    if "__ALLOWLIST_" in matched_text:
                        continue

                    detection = {
                        "type": f"{group_name}:{pattern_name}",
                        "severity": config["severity"],
                        "action": config["action"].value,
                        "matched_text": matched_text[:50] + "..." if len(matched_text) > 50 else matched_text,
                        "position": match.span(),
                    }
                    detections.append(detection)
                    self.sanitization_stats["total_detections"] += 1

                    # Debug log for non-critical detections to help diagnose false positives
                    if config["severity"] in ["LOW", "MEDIUM"]:
                        logger.debug(
                            f"Sanitization detected: pattern={group_name}:{pattern_name}, "
                            f"severity={config['severity']}, matched='{matched_text[:30]}...'"
                        )

                    # Apply sanitization action
                    if config["action"] == SanitizationAction.REDACT:
                        sanitized = self._redact_match(sanitized, match)
                    elif config["action"] == SanitizationAction.MASK:
                        sanitized = self._mask_match(sanitized, match)
                    elif config["action"] == SanitizationAction.REMOVE:
                        sanitized = self._remove_match(sanitized, match)
                    elif config["action"] == SanitizationAction.BLOCK:
                        should_block = True

                    # Check if should block in strict mode
                    if self.strict_mode and config["severity"] in ["HIGH", "CRITICAL"]:
                        should_block = True

                    # Log critical detections
                    if config["severity"] == "CRITICAL":
                        logger.critical(
                            f"CRITICAL: Sensitive data detected in output - "
                            f"Type: {group_name}:{pattern_name}, "
                            f"Context: {context}, "
                            f"Hash: {original_hash}"
                        )

        # Step 2: Restore allowlisted content from placeholders
        sanitized = self._restore_allowlisted_content(sanitized, allowlisted)

        # Determine final result
        if should_block:
            self.sanitization_stats["total_blocked"] += 1
            return SanitizationResult(
                is_safe=False,
                sanitized_content="[RESPONSE BLOCKED: Sensitive information detected]",
                detections=detections,
                action_taken="BLOCKED",
                original_hash=original_hash,
            )
        elif detections:
            return SanitizationResult(
                is_safe=True,
                sanitized_content=sanitized,
                detections=detections,
                action_taken="SANITIZED",
                original_hash=original_hash,
            )
        else:
            return SanitizationResult(
                is_safe=True,
                sanitized_content=content,
                detections=[],
                action_taken="PASSED",
                original_hash=original_hash,
            )

    def _redact_match(self, text: str, match: re.Match) -> str:
        """Redact sensitive match with [REDACTED]"""
        matched_text = match.group(0)
        return text.replace(matched_text, "[REDACTED]", 1)

    def _mask_match(self, text: str, match: re.Match) -> str:
        """Mask sensitive match partially"""
        matched_text = match.group(0)
        if len(matched_text) <= 4:
            masked = "****"
        else:
            # Show first 2 and last 2 chars
            masked = matched_text[:2] + "***" + matched_text[-2:]
        return text.replace(matched_text, masked, 1)

    def _remove_match(self, text: str, match: re.Match) -> str:
        """Remove sensitive match entirely"""
        matched_text = match.group(0)
        return text.replace(matched_text, "", 1)

    def _safe_result(self, content: str) -> SanitizationResult:
        """Return safe result for empty/valid content"""
        return SanitizationResult(
            is_safe=True, sanitized_content=content, detections=[], action_taken="PASSED", original_hash=""
        )

    def get_stats(self) -> dict:
        """Get sanitization statistics"""
        return {
            **self.sanitization_stats,
            "detection_rate": (
                self.sanitization_stats["total_detections"] / self.sanitization_stats["total_scans"]
                if self.sanitization_stats["total_scans"] > 0
                else 0
            ),
            "block_rate": (
                self.sanitization_stats["total_blocked"] / self.sanitization_stats["total_scans"]
                if self.sanitization_stats["total_scans"] > 0
                else 0
            ),
        }


# Global instance — strict_mode enabled in production so HIGH/CRITICAL detections
# block the entire response rather than just redacting/masking inline.
import os as _os

_strict_mode = _os.getenv("APP_ENV", "development") == "production"
output_sanitizer = OutputSanitizer(strict_mode=_strict_mode)
