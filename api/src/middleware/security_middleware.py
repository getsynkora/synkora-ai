"""
Enterprise Security Middleware

CRITICAL: This middleware implements mandatory enterprise security controls
as required by the enterprise security policy deployed via JAMF MDM.

NOTE: All middleware classes use pure ASGI pattern instead of BaseHTTPMiddleware
to avoid TaskGroup cancellation issues with async database sessions.
"""

import json
import logging
import re
import secrets

from fastapi import status
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware:
    """
    Pure ASGI middleware that implements mandatory enterprise security headers.
    CRITICAL: These headers are required by enterprise policy.

    Uses pure ASGI pattern to avoid BaseHTTPMiddleware TaskGroup cancellation issues.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Generate nonce for CSP
        nonce = secrets.token_urlsafe(16)

        # Store nonce in scope for access by the application
        scope["state"] = scope.get("state", {})
        scope["state"]["csp_nonce"] = nonce

        # Security headers to add to response
        security_headers = {
            # Content Security Policy - CRITICAL for XSS protection
            b"content-security-policy": (
                f"default-src 'self'; "
                f"script-src 'self' 'nonce-{nonce}' 'strict-dynamic'; "
                f"style-src 'self' 'unsafe-inline'; "
                f"img-src 'self' data: https:; "
                f"font-src 'self'; "
                f"connect-src 'self'; "
                f"media-src 'self'; "
                f"object-src 'none'; "
                f"base-uri 'self'; "
                f"form-action 'self'; "
                f"frame-ancestors 'none'"
            ).encode(),
            # X-Frame-Options - Prevent clickjacking (belt-and-suspenders alongside CSP)
            b"x-frame-options": b"DENY",
            # X-Content-Type-Options - Prevent MIME type sniffing
            b"x-content-type-options": b"nosniff",
            # NOTE: X-XSS-Protection intentionally omitted — deprecated and can introduce
            # XSS vulnerabilities in some browsers. CSP above provides XSS protection.
            # Referrer Policy - Control referrer information
            b"referrer-policy": b"strict-origin-when-cross-origin",
            # Permissions Policy - Control browser features
            b"permissions-policy": b"geolocation=(), microphone=(self), camera=(), payment=(), usb=(), magnetometer=(), gyroscope=(), speaker=()",
            # NOTE: cache-control intentionally omitted from global headers.
            # Setting no-store on every response (including health checks, public configs,
            # metrics) breaks CDN/reverse proxy caching. Auth controllers set their own
            # cache-control where needed.
            # NOTE: HSTS intentionally omitted from the API backend. HSTS is a browser
            # directive for HTML pages — browsers ignore it on API (JSON) responses.
            # HSTS belongs on the frontend Next.js server only.
            # Cross-Origin isolation headers — prevent Spectre/Meltdown side-channel leaks
            # and restrict cross-origin resource sharing at the browser level.
            b"cross-origin-opener-policy": b"same-origin",
            b"cross-origin-embedder-policy": b"require-corp",
            b"cross-origin-resource-policy": b"same-site",
            # Server header — generic value to avoid leaking tech stack details
            b"server": b"web",
        }

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                # Get existing headers and add security headers
                headers = list(message.get("headers", []))
                for header_name, header_value in security_headers.items():
                    headers.append((header_name, header_value))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)


class InputSanitizationMiddleware:
    """
    Pure ASGI Input Sanitization Middleware.
    CRITICAL: Protects against XSS attacks but delegates prompt injection to advanced scanner.

    Uses pure ASGI pattern to avoid BaseHTTPMiddleware TaskGroup cancellation issues.

    SECURITY: Comprehensive XSS pattern list covering:
    - Script injection tags
    - Event handler attributes (including HTML5)
    - JavaScript URI schemes
    - Data URI schemes
    - SVG-based XSS vectors
    - Expression/behavior CSS
    """

    # XSS patterns - comprehensive list including HTML5 event handlers
    XSS_PATTERNS = [
        # Script tags and execution contexts
        r"<script[^>]*>",  # Script tag opening
        r"</script>",  # Script tag closing (for detection)
        r"<svg[^>]*onload",  # SVG onload attacks
        r"<svg[^>]*>.*?<script",  # SVG with embedded script
        r"<img[^>]*onerror",  # Image error handler XSS
        r"<body[^>]*onload",  # Body onload
        r"<input[^>]*onfocus",  # Input focus handler
        r"<marquee[^>]*onstart",  # Marquee start handler
        r"<source[^>]*onerror",  # Source error handler
        # Dangerous embedding tags — no legitimate use in AI chat or API JSON payloads.
        # NOTE: <video>, <audio>, <link>, <meta>, <form>, <style> are intentionally
        # omitted here. Their dangerous variants (event handlers, javascript: URIs,
        # CSS expressions) are already covered by the on*= and URI-scheme patterns
        # below. Blocking the bare tags causes false positives when users paste HTML
        # code snippets or AI responses contain HTML examples.
        r"<iframe[^>]*>",  # Iframe injection
        r"<object[^>]*>",  # Object injection
        r"<embed[^>]*>",  # Embed injection
        r"<base[^>]*>",  # Base tag hijacking (changes all relative URLs on page)
        # URI scheme attacks
        r"javascript\s*:",  # JavaScript URI (with optional whitespace bypass)
        r"vbscript\s*:",  # VBScript URI
        r"data\s*:\s*text/html",  # Data URI with HTML
        r"data\s*:\s*application/javascript",  # Data URI with JS
        # Event handlers - comprehensive HTML5 list
        # SECURITY: Pattern matches on* attributes with flexible whitespace
        r"on(abort|afterprint|animationcancel|animationend|animationiteration|animationstart)\s*=",
        r"on(auxclick|beforeinput|beforeprint|beforeunload|blur|canplay|canplaythrough)\s*=",
        r"on(change|click|close|contextmenu|copy|cuechange|cut|dblclick|drag|dragend)\s*=",
        r"on(dragenter|dragexit|dragleave|dragover|dragstart|drop|durationchange)\s*=",
        r"on(emptied|ended|error|focus|focusin|focusout|formdata|gotpointercapture)\s*=",
        r"on(hashchange|input|invalid|keydown|keypress|keyup|languagechange|load)\s*=",
        r"on(loadeddata|loadedmetadata|loadend|loadstart|lostpointercapture|message)\s*=",
        r"on(messageerror|mousedown|mouseenter|mouseleave|mousemove|mouseout|mouseover)\s*=",
        r"on(mouseup|mousewheel|offline|online|pagehide|pageshow|paste|pause|play)\s*=",
        r"on(playing|pointercancel|pointerdown|pointerenter|pointerleave|pointerlockchange)\s*=",
        r"on(pointerlockerror|pointermove|pointerout|pointerover|pointerup|popstate)\s*=",
        r"on(progress|ratechange|readystatechange|rejectionhandled|reset|resize|scroll)\s*=",
        r"on(securitypolicyviolation|seeked|seeking|select|selectionchange|selectstart)\s*=",
        r"on(show|slotchange|stalled|storage|submit|suspend|timeupdate|toggle|touchcancel)\s*=",
        r"on(touchend|touchmove|touchstart|transitioncancel|transitionend|transitionrun)\s*=",
        r"on(transitionstart|unhandledrejection|unload|volumechange|waiting|webkitanimationend)\s*=",
        r"on(webkitanimationiteration|webkitanimationstart|webkittransitionend|wheel)\s*=",
        # Catch-all for any on* handler (backup pattern)
        r"\bon[a-z]{2,}\s*=",  # Matches on followed by 2+ lowercase letters
        # CSS-based attacks
        r"expression\s*\(",  # CSS expression (IE)
        r"behavior\s*:",  # CSS behavior (IE)
        r"binding\s*:",  # Mozilla binding
        r"-moz-binding\s*:",  # Mozilla binding
        r"@import",  # CSS import
        # HTML5 specific dangerous attributes
        r"srcdoc\s*=",  # Iframe srcdoc attribute
        r"formaction\s*=",  # Form action override
        r"xlink:href\s*=",  # SVG xlink
    ]

    # All patterns compiled once into a single alternation regex.
    # One re.search() call replaces 60+ per-pattern calls on every request.
    _XSS_RE: re.Pattern = re.compile("|".join(XSS_PATTERNS), re.IGNORECASE)

    # Only scan the first 64 KB of the body. XSS payloads in JSON fields are
    # always tiny; no attack hides past 64 KB of legitimate content. The app
    # still receives the full unmodified body — only the scan window is capped.
    _SCAN_LIMIT: int = 65_536

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")

        # Only process POST, PUT, PATCH requests with JSON content
        if method not in {"POST", "PUT", "PATCH"}:
            await self.app(scope, receive, send)
            return

        # Check content-type header
        headers = dict(scope.get("headers", []))
        content_type = headers.get(b"content-type", b"").decode()

        if "application/json" not in content_type:
            await self.app(scope, receive, send)
            return

        # Collect body chunks only up to _SCAN_LIMIT bytes.
        # For large payloads (e.g. 50 MB uploads) we must NOT buffer the entire
        # body — that would cause a huge memory spike. We buffer only enough to
        # scan for XSS, then replay those messages and fall through to the real
        # receive callable for any remaining chunks.
        scan_chunks: list[bytes] = []
        scan_total = 0
        buffered_messages: list[Message] = []
        body_done = False

        while not body_done and scan_total < self._SCAN_LIMIT:
            message = await receive()
            buffered_messages.append(message)
            if message["type"] == "http.request":
                body = message.get("body", b"")
                if body:
                    scan_chunks.append(body)
                    scan_total += len(body)
                if not message.get("more_body", False):
                    body_done = True

        scan_data = b"".join(scan_chunks)

        if scan_data:
            try:
                body_str = scan_data.decode("utf-8", errors="ignore")

                # Scan only top-level string values from the parsed JSON body.
                # Nested structures (e.g. conversation_history, messages arrays)
                # are skipped — they contain prior AI-generated content that may
                # legitimately include HTML/code examples and should not be
                # re-scanned as user input. Falls back to raw body scan if the
                # body is not a JSON object (e.g. raw string or array).
                strings_to_scan = self._extract_scannable_strings(body_str)

                # Check for XSS (prompt injection is handled by the advanced scanner)
                xss_found = any(self._contains_xss(s) for s in strings_to_scan)
                if xss_found:
                    client = scope.get("client")
                    client_ip = client[0] if client else "unknown"
                    logger.warning(f"XSS attempt detected from {client_ip}")
                    response = JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={
                            "error": "Input validation failed",
                            "detail": "Content contains script injection attempts",
                        },
                    )
                    await response(scope, receive, send)
                    return
            except Exception as e:
                logger.error(f"Error during input sanitization: {e}")
                # Continue processing to avoid breaking legitimate requests

        # Replay already-buffered messages first, then fall through to the real
        # receive for any remaining body chunks (critical for large payloads).
        msg_index = 0

        async def receive_replayed() -> Message:
            nonlocal msg_index
            if msg_index < len(buffered_messages):
                msg = buffered_messages[msg_index]
                msg_index += 1
                return msg
            return await receive()

        await self.app(scope, receive_replayed, send)

    # Fields that legitimately contain technical/HTML content written by users or
    # platform operators (agent system prompts, descriptions, email templates, etc.).
    # Scanning these causes false positives — e.g. a system prompt that says
    # "handle @import rules" or references onload= in documentation.
    _SKIP_XSS_FIELDS: frozenset[str] = frozenset(
        {
            "system_prompt",
            "instructions",
            "prompt",
            "description",
            "content",
            "body",
            "template",
            "html",
            "welcome_message",
            "placeholder",
            "footer_text",
            "subject",
            "preheader",
        }
    )

    def _extract_scannable_strings(self, body_str: str) -> list[str]:
        """Return the string values that should be scanned for XSS.

        For a JSON object body, only top-level string values are returned,
        excluding known content fields (system_prompt, description, etc.) that
        legitimately contain HTML/code and would cause false positives.
        Nested arrays and objects (e.g. conversation_history) are skipped
        because they contain prior AI-generated or pre-validated content, not
        raw user input.  If the body is not a JSON object, the raw string is
        returned so the existing behaviour is preserved for non-standard bodies.
        """
        try:
            data = json.loads(body_str)
            if isinstance(data, dict):
                return [v for k, v in data.items() if isinstance(v, str) and k not in self._SKIP_XSS_FIELDS]
            if isinstance(data, str):
                return [data]
        except (json.JSONDecodeError, ValueError):
            pass
        # Non-JSON or root-level array: fall back to scanning the raw body.
        return [body_str]

    def _contains_xss(self, content: str) -> bool:
        """Check content against the compiled XSS pattern."""
        return self._XSS_RE.search(content) is not None
