"""
File Security Service

CRITICAL: Implements mandatory file security controls per enterprise policy.
Provides secure file upload validation, virus scanning, and content analysis.
"""

import hashlib
import logging
import mimetypes
import os
import re
from pathlib import Path

import magic

logger = logging.getLogger(__name__)


class ScannerUnavailableError(RuntimeError):
    """Raised when the virus scanner cannot be reached.

    Callers should translate this into an HTTP 503 response so that
    file uploads are never silently passed without a scan.
    """


class FileSecurityService:
    """
    Comprehensive file security validation service.
    CRITICAL: All file uploads must pass these security checks.
    """

    # File type allowlists by category (magic number validation)
    ALLOWED_FILE_SIGNATURES = {
        # Images
        "image/jpeg": [b"\xff\xd8\xff"],
        "image/png": [b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a"],
        "image/gif": [b"GIF87a", b"GIF89a"],
        "image/webp": [b"RIFF", b"WEBP"],
        "image/bmp": [b"BM"],
        "image/tiff": [b"\x49\x49\x2a\x00", b"\x4d\x4d\x00\x2a"],
        # Documents
        "application/pdf": [b"%PDF-"],
        "text/plain": [],  # Text files are validated separately
        "text/markdown": [],
        "text/x-markdown": [],
        "text/html": [],
        "text/csv": [],
        "application/json": [],
        # Microsoft Office (new format)
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [b"PK\x03\x04"],
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [b"PK\x03\x04"],
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": [b"PK\x03\x04"],
        # Microsoft Office (legacy)
        "application/msword": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"],
        "application/vnd.ms-excel": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"],
        "application/vnd.ms-powerpoint": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"],
        # Archives (limited support)
        "application/zip": [b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"],
    }

    # Maximum file sizes by type (in bytes)
    MAX_FILE_SIZES = {
        "avatar": 5 * 1024 * 1024,  # 5MB for avatars
        "document": 25 * 1024 * 1024,  # 25MB for documents
        "image": 10 * 1024 * 1024,  # 10MB for images
        "default": 50 * 1024 * 1024,  # 50MB default
    }

    # Dangerous file extensions (always blocked)
    DANGEROUS_EXTENSIONS = {
        ".exe",
        ".scr",
        ".bat",
        ".cmd",
        ".com",
        ".pif",
        ".scf",
        ".vbs",
        ".js",
        ".jse",
        ".ws",
        ".wsf",
        ".wsc",
        ".wsh",
        ".ps1",
        ".ps1xml",
        ".ps2",
        ".ps2xml",
        ".psc1",
        ".psc2",
        ".msh",
        ".msh1",
        ".msh2",
        ".mshxml",
        ".msh1xml",
        ".msh2xml",
        ".application",
        ".gadget",
        ".msi",
        ".msp",
        ".mst",
        ".jar",
        ".hta",
        ".cpl",
        ".inf",
        ".reg",
        ".url",
        ".vbe",
        ".jnlp",
        ".app",
        ".deb",
        ".pkg",
        ".dmg",
        ".action",
        ".bin",
    }

    # Malicious content patterns
    MALICIOUS_PATTERNS = [
        # Script injections
        rb"<script[^>]*>",
        rb"javascript:",
        rb"vbscript:",
        rb"data:text/html",
        # Executable signatures
        rb"MZ\x90\x00",  # PE executable
        rb"\x7fELF",  # ELF executable
        rb"\xca\xfe\xba\xbe",  # Mach-O
        # Macro indicators
        rb"Microsoft Office Word Document",
        rb"Microsoft Excel",
        rb"macros",
        rb"VBA",
        # Shell commands
        rb"#!/bin/",
        rb"#!/usr/bin/",
        rb"powershell",
        rb"cmd.exe",
    ]

    def __init__(self):
        """Initialize file security service"""
        try:
            self.mime = magic.Magic(mime=True)
            self.file_type = magic.Magic()
        except Exception as e:
            logger.warning(f"Could not initialize python-magic: {e}")
            self.mime = None
            self.file_type = None

    def validate_file(
        self, file_content: bytes, filename: str, category: str = "default", max_size_override: int | None = None
    ) -> dict[str, bool | str | list[str]]:
        """
        Comprehensive file validation.

        Args:
            file_content: Raw file content
            filename: Original filename
            category: File category (avatar, document, etc.)
            max_size_override: Override default size limit

        Returns:
            Validation result dictionary
        """
        result = {
            "is_valid": True,
            "mime_type": None,
            "detected_type": None,
            "file_hash": None,
            "warnings": [],
            "errors": [],
            "metadata": {},
        }

        try:
            # 1. Basic validation
            if not file_content:
                result["is_valid"] = False
                result["errors"].append("File is empty")
                return result

            # 2. File size validation
            max_size = max_size_override or self.MAX_FILE_SIZES.get(category, self.MAX_FILE_SIZES["default"])
            if len(file_content) > max_size:
                result["is_valid"] = False
                result["errors"].append(f"File size ({len(file_content)} bytes) exceeds limit ({max_size} bytes)")
                return result

            # 3. Extension validation
            file_extension = Path(filename).suffix.lower()
            if file_extension in self.DANGEROUS_EXTENSIONS:
                result["is_valid"] = False
                result["errors"].append(f"Dangerous file extension: {file_extension}")
                return result

            # 4. MIME type detection
            detected_mime = None
            detected_type = None

            if self.mime and self.file_type:
                try:
                    detected_mime = self.mime.from_buffer(file_content)
                    detected_type = self.file_type.from_buffer(file_content)
                    result["mime_type"] = detected_mime
                    result["detected_type"] = detected_type
                except Exception as e:
                    result["warnings"].append(f"MIME detection failed: {str(e)}")
            else:
                detected_mime, _ = mimetypes.guess_type(filename)
                result["mime_type"] = detected_mime
                result["warnings"].append("Using fallback MIME detection")

            # 5. Magic number validation
            if detected_mime and not self._validate_file_signature(file_content, detected_mime):
                result["is_valid"] = False
                result["errors"].append(f"File signature doesn't match MIME type: {detected_mime}")
                return result

            # 6. Content scanning for malicious patterns
            malicious_patterns = self._scan_malicious_content(file_content)
            if malicious_patterns:
                result["is_valid"] = False
                result["errors"].append("Malicious content detected")
                return result

            # 7. Generate file hash for deduplication/tracking
            result["file_hash"] = hashlib.sha256(file_content).hexdigest()

            # 8. Category-specific validation
            category_validation = self._validate_category_specific(file_content, filename, category, detected_mime)
            if not category_validation["is_valid"]:
                result["is_valid"] = False
                result["errors"].extend(category_validation["errors"])
                return result

            result["warnings"].extend(category_validation.get("warnings", []))
            result["metadata"].update(category_validation.get("metadata", {}))

            logger.info(f"File validation passed: {filename} ({detected_mime})")

        except Exception as e:
            logger.warning(f"File validation error: {str(e)}")
            result["is_valid"] = False
            result["errors"].append(f"Validation error: {str(e)}")

        return result

    # MIME types that python-magic commonly reports for plain-text files whose
    # content resembles a programming language.  These are all UTF-8 text and
    # have no fixed magic bytes, so signature checking is meaningless for them.
    _TEXT_EQUIVALENT_MIMES = frozenset({
        "application/javascript",
        "application/x-javascript",
        "text/javascript",
        "application/x-python",
        "application/x-python-code",
        "application/x-sh",
        "application/x-shellscript",
        "application/x-ruby",
        "application/x-perl",
        "application/x-php",
        "application/x-httpd-php",
        "application/x-typescript",
        "application/x-sql",
        "application/x-yaml",
        "application/x-toml",
    })

    def _validate_file_signature(self, content: bytes, mime_type: str) -> bool:
        """Validate file magic numbers/signatures"""
        # All text/* types are valid — python-magic detects .md/.txt content as
        # text/x-script.python, text/html, text/x-c, etc. depending on content.
        # Text files have no fixed magic bytes so signature checking is not meaningful.
        if mime_type.startswith("text/"):
            return True

        # python-magic often misidentifies plain-text files that contain code
        # (e.g. a .md skill file with JS examples) as application/javascript or
        # similar.  These are all text content — no magic-byte check applies.
        if mime_type in self._TEXT_EQUIVALENT_MIMES:
            return True

        if mime_type not in self.ALLOWED_FILE_SIGNATURES:
            return False

        signatures = self.ALLOWED_FILE_SIGNATURES[mime_type]

        # Types registered with no signatures have no magic bytes to check
        if not signatures:
            return True

        # Check if file starts with any of the allowed signatures
        for signature in signatures:
            if content.startswith(signature):
                return True

        return False

    def _scan_malicious_content(self, content: bytes) -> list[str]:
        """Scan file content for malicious patterns"""
        detected_patterns = []

        for pattern in self.MALICIOUS_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                detected_patterns.append("malicious_pattern")

        return detected_patterns

    def _validate_category_specific(self, content: bytes, filename: str, category: str, mime_type: str | None) -> dict:
        """Category-specific validation rules"""
        result = {"is_valid": True, "errors": [], "warnings": [], "metadata": {}}

        if category == "avatar":
            # Avatar must be an image
            if not mime_type or not mime_type.startswith("image/"):
                result["is_valid"] = False
                result["errors"].append("Avatar must be an image file")
                return result

        elif category == "document":
            # Validate document types
            allowed_doc_types = [
                "application/pdf",
                "text/plain",
                "text/csv",
                "application/json",
                "application/msword",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ]

            if mime_type and mime_type not in allowed_doc_types:
                result["warnings"].append(f"Document type {mime_type} may not be supported")

        return result

    def sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename to prevent path traversal and other attacks.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename
        """
        if not filename:
            return "unnamed_file"

        # Remove path components
        filename = os.path.basename(filename)

        # Remove or replace dangerous characters
        # Keep only alphanumeric, dots, hyphens, and underscores
        sanitized = re.sub(r"[^a-zA-Z0-9._-]", "_", filename)

        # Remove leading dots (hidden files)
        sanitized = sanitized.lstrip(".")

        # Ensure filename isn't empty after sanitization
        if not sanitized:
            sanitized = "unnamed_file"

        # Limit filename length
        if len(sanitized) > 255:
            name, ext = os.path.splitext(sanitized)
            sanitized = name[: 255 - len(ext)] + ext

        return sanitized

    def scan_for_viruses(self, file_path: str) -> dict[str, bool | str]:
        """
        Scan a file for viruses using ClamAV (via pyclamd).

        Args:
            file_path: Path to file to scan

        Returns:
            Scan result dictionary with keys:
              - is_clean (bool): True if no threat detected
              - scanner (str): "clamav" | "none" | "error"
              - threat (str, optional): threat name when is_clean=False
              - message (str, optional): additional context

        Raises:
            ScannerUnavailableError: when the scanner process cannot be reached
              (ImportError or connection failure).  Callers must propagate this
              as an HTTP 503 — never silently skip scanning in production.
        """
        try:
            import pyclamd

            cd = pyclamd.ClamdUnixSocket()
            result = cd.scan_file(file_path)
            if result is None:
                return {"is_clean": True, "scanner": "clamav"}
            return {"is_clean": False, "scanner": "clamav", "threat": str(result)}
        except ImportError:
            logger.warning(
                "pyclamd not installed — virus scanning is unavailable. Install pyclamd and ClamAV for production use."
            )
            raise ScannerUnavailableError(
                "Virus scanner (pyclamd) is not installed. File scanning service unavailable."
            )
        except Exception as e:
            # Covers pyclamd.ConnectionError and any other runtime failures.
            logger.error(f"Virus scan failed — scanner unreachable: {e}")
            raise ScannerUnavailableError(f"Virus scanner could not be reached: {type(e).__name__}") from e

    def quarantine_file(self, file_content: bytes, reason: str) -> str:
        """
        Quarantine malicious files for analysis.

        Args:
            file_content: File content to quarantine
            reason: Reason for quarantine

        Returns:
            Quarantine ID
        """
        try:
            quarantine_id = hashlib.sha256(file_content).hexdigest()[:16]

            # Create quarantine directory if it doesn't exist
            quarantine_dir = Path("/tmp/synkora_quarantine")
            quarantine_dir.mkdir(exist_ok=True)

            # Write quarantined file
            quarantine_file = quarantine_dir / f"{quarantine_id}.quarantined"
            with open(quarantine_file, "wb") as f:
                f.write(file_content)

            # Write metadata
            metadata_file = quarantine_dir / f"{quarantine_id}.metadata"
            with open(metadata_file, "w") as f:
                f.write(f"Quarantine Reason: {reason}\n")
                f.write(f"Timestamp: {os.path.getctime(quarantine_file)}\n")
                f.write(f"Size: {len(file_content)} bytes\n")
                f.write(f"Hash: {hashlib.sha256(file_content).hexdigest()}\n")

            logger.warning(f"File quarantined: {quarantine_id} - {reason}")
            return quarantine_id

        except Exception as e:
            logger.error(f"Failed to quarantine file: {str(e)}")
            return ""


class PromptInjectionScanner:
    """
    CRITICAL: Specialized scanner for prompt injection attacks.
    Protects against LLM manipulation and jailbreaking attempts.
    """

    # Advanced prompt injection patterns
    INJECTION_PATTERNS = [
        # Direct instruction overrides
        r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions?|commands?|prompts?)",
        r"disregard\s+(?:the\s+)?(?:above|previous|prior)\s+(?:instructions?|text|prompt)",
        r"forget\s+(?:all\s+)?(?:previous|prior)\s+(?:instructions?|context|conversation)",
        # System message injection
        r"system\s*:\s*.*(?:ignore|override|disregard)",
        r"<\|system\|>.*?<\|/system\|>",
        r"\[SYSTEM\].*?\[/SYSTEM\]",
        # Role manipulation
        r"(?:act|behave|pretend)\s+(?:as|like)\s+(?:if\s+)?(?:you\s+are|you're)\s+(?:not\s+)?(?:an?\s+)?(?:AI|assistant|bot|system)",
        r"you\s+are\s+now\s+(?:a\s+)?(?!an?\s+(?:AI\s+)?assistant)[\w\s]+",
        r"roleplay\s+as\s+(?:a\s+)?(?!an?\s+(?:AI\s+)?assistant)[\w\s]+",
        # Jailbreak attempts
        r"developer\s+mode",
        r"jailbreak",
        r"unlimited\s+(?:mode|power)",
        r"break\s+(?:out\s+of\s+)?(?:character|role)",
        # Prompt leakage attempts
        r"(?:show|tell|reveal|display)\s+me\s+your\s+(?:system\s+)?(?:prompt|instructions)",
        r"what\s+(?:are|were)\s+your\s+(?:initial\s+)?(?:instructions|prompt)",
        # Context manipulation
        r"\\n\\n(?:Human|User|Person):",
        r"\\n\\n(?:Assistant|AI|Bot):",
        r"<\|(?:human|user|assistant|ai)\|>",
    ]

    # Severity levels for detected patterns
    SEVERITY_LEVELS = {
        "low": ["roleplay", "pretend"],
        "medium": ["ignore", "disregard", "forget"],
        "high": ["system:", "jailbreak", "override"],
        "critical": ["developer mode", "break character", "show prompt"],
    }

    def scan_text(self, text: str) -> dict[str, bool | list[dict] | int]:
        """
        Scan text for prompt injection attempts.

        Args:
            text: Text to scan

        Returns:
            Scan results with detections and severity
        """
        if not text:
            return {"is_safe": True, "detections": [], "risk_score": 0}

        detections = []
        risk_score = 0

        text_lower = text.lower()

        for pattern in self.INJECTION_PATTERNS:
            matches = re.finditer(pattern, text_lower, re.IGNORECASE | re.MULTILINE)

            for match in matches:
                detection = {
                    "pattern": pattern[:50] + "..." if len(pattern) > 50 else pattern,
                    "match": match.group(0),
                    "position": match.span(),
                    "severity": self._get_severity(match.group(0)),
                    "context": text[max(0, match.start() - 50) : match.end() + 50],
                }

                detections.append(detection)
                risk_score += self._get_risk_points(detection["severity"])

        is_safe = risk_score < 50  # Threshold for blocking

        if not is_safe:
            logger.warning(f"Prompt injection detected - Risk Score: {risk_score}")

        return {
            "is_safe": is_safe,
            "detections": detections,
            "risk_score": risk_score,
            "recommendation": self._get_recommendation(risk_score),
        }

    def _get_severity(self, match_text: str) -> str:
        """Determine severity of detected pattern"""
        match_lower = match_text.lower()

        for severity, keywords in self.SEVERITY_LEVELS.items():
            if any(keyword in match_lower for keyword in keywords):
                return severity

        return "medium"  # Default severity

    def _get_risk_points(self, severity: str) -> int:
        """Get risk points for severity level"""
        points = {"low": 10, "medium": 25, "high": 50, "critical": 100}
        return points.get(severity, 25)

    def _get_recommendation(self, risk_score: int) -> str:
        """Get recommendation based on risk score"""
        if risk_score >= 100:
            return "BLOCK - Critical prompt injection detected"
        elif risk_score >= 50:
            return "WARN - High risk prompt injection detected"
        elif risk_score >= 25:
            return "MONITOR - Potential prompt injection detected"
        else:
            return "ALLOW - Low risk content"


# Global instances
file_security = FileSecurityService()
prompt_scanner = PromptInjectionScanner()
