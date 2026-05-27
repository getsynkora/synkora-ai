"""
Dynamic CORS middleware for widget support.

Handles CORS for both dashboard and widget requests with domain validation.

NOTE: Uses pure ASGI pattern instead of BaseHTTPMiddleware to avoid
TaskGroup cancellation issues with async database sessions.
"""

import hashlib
import logging
import os

from starlette.requests import Request as StarletteRequest
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.core.database import get_async_session_factory

logger = logging.getLogger(__name__)


class DynamicCORSMiddleware:
    """
    Pure ASGI Dynamic CORS middleware that validates origins based on widget configuration.

    For widget requests (identified by X-Widget-API-Key header), validates the
    origin against the widget's allowed_domains list. For other requests, allows
    configured dashboard origins.

    Uses pure ASGI pattern to avoid BaseHTTPMiddleware TaskGroup cancellation issues.
    """

    # How long (seconds) a widget CORS decision is cached in Redis.
    # Browser preflights are already cached for max_age=600 s, so the server
    # only re-validates after the browser cache expires.  60 s is short enough
    # that domain changes on a widget propagate quickly.
    _WIDGET_CORS_CACHE_TTL = 60

    def __init__(
        self,
        app: ASGIApp,
        dashboard_origins: list[str] | None = None,
        allow_credentials: bool = True,
        allow_methods: list[str] | None = None,
        allow_headers: list[str] | None = None,
        expose_headers: list[str] | None = None,
        max_age: int = 600,
    ):
        """
        Initialize CORS middleware.

        Args:
            app: ASGI application
            dashboard_origins: List of allowed origins for dashboard requests
            allow_credentials: Whether to allow credentials
            allow_methods: List of allowed HTTP methods
            allow_headers: List of allowed headers
            expose_headers: List of headers to expose
            max_age: Max age for preflight cache
        """
        self.app = app
        if not dashboard_origins or dashboard_origins == ["*"]:
            if os.getenv("APP_ENV", "development") == "production":
                raise RuntimeError(
                    "CORS_ORIGINS must be explicitly set in production — refusing wildcard + credentials"
                )
            self.dashboard_origins = ["*"]  # Only allow wildcard in dev/test
        else:
            self.dashboard_origins = dashboard_origins
        self.allow_credentials = allow_credentials
        self.allow_methods = allow_methods or ["*"]
        self.allow_headers = allow_headers or ["*"]
        self.expose_headers = expose_headers or []
        self.max_age = max_age

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Create a request object for header access
        request = StarletteRequest(scope, receive, send)
        origin = request.headers.get("origin")
        method = scope.get("method", "GET")

        # Handle preflight requests
        if method == "OPTIONS":
            response = await self._handle_preflight(request, origin)
            await response(scope, receive, send)
            return

        # Process request with CORS headers added to response
        if origin:
            allowed_origin = await self._get_allowed_origin(request, origin)
            if allowed_origin:
                # Add CORS headers to response
                cors_headers = self._build_cors_headers(allowed_origin)

                async def send_with_cors(message: Message) -> None:
                    if message["type"] == "http.response.start":
                        headers = list(message.get("headers", []))
                        for header_name, header_value in cors_headers:
                            headers.append((header_name, header_value))
                        message = {**message, "headers": headers}
                    await send(message)

                await self.app(scope, receive, send_with_cors)
                return

        # No CORS headers needed
        await self.app(scope, receive, send)

    async def _handle_preflight(self, request: StarletteRequest, origin: str | None) -> Response:
        """
        Handle CORS preflight requests.

        Args:
            request: Preflight request
            origin: Request origin

        Returns:
            Preflight response with CORS headers
        """
        # Widget preflights don't carry the API key value — the browser only declares
        # it intends to send X-Widget-API-Key via Access-Control-Request-Headers.
        # Allow the preflight from any origin; the real API key validation happens
        # on the subsequent actual request.
        requested_headers = request.headers.get("access-control-request-headers", "")
        if origin and "x-widget-api-key" in requested_headers.lower():
            allowed_origin = origin
        else:
            allowed_origin = await self._get_allowed_origin(request, origin) if origin else None

        if not allowed_origin:
            # Origin not allowed
            return Response(status_code=403, content="Origin not allowed")

        # Create preflight response
        response = Response(status_code=200)
        self._add_cors_headers(response, allowed_origin)

        # Add preflight-specific headers
        response.headers["Access-Control-Max-Age"] = str(self.max_age)

        # Handle requested method
        requested_method = request.headers.get("access-control-request-method")
        if requested_method:
            if "*" in self.allow_methods or requested_method in self.allow_methods:
                response.headers["Access-Control-Allow-Methods"] = ", ".join(self.allow_methods)
            else:
                return Response(status_code=403, content="Method not allowed")

        # Handle requested headers
        requested_headers = request.headers.get("access-control-request-headers")
        if requested_headers:
            if "*" in self.allow_headers:
                response.headers["Access-Control-Allow-Headers"] = requested_headers
            else:
                response.headers["Access-Control-Allow-Headers"] = ", ".join(self.allow_headers)

        return response

    async def _get_allowed_origin(self, request: StarletteRequest, origin: str) -> str | None:
        """
        Determine if origin is allowed for this request.

        Args:
            request: Incoming request
            origin: Request origin

        Returns:
            Allowed origin or None if not allowed
        """
        # Check if this is a widget request
        api_key = request.headers.get("x-widget-api-key")

        if api_key:
            # Widget request - validate against widget's allowed domains
            return await self._validate_widget_origin(api_key, origin)

        # Chrome extensions send origin: chrome-extension://<id>. They enforce
        # their own security via host_permissions and Bearer tokens — allow them.
        if origin.startswith("chrome-extension://"):
            return origin

        # Dashboard request - validate against dashboard origins
        return self._validate_dashboard_origin(origin)

    async def _validate_widget_origin(self, api_key: str, origin: str) -> str | None:
        """
        Validate origin against widget's allowed domains.

        Uses the same decrypted key lookup as WidgetAuthMiddleware to correctly
        handle encrypted API keys stored in the database.

        PERFORMANCE: Results are cached in Redis for _WIDGET_CORS_CACHE_TTL seconds
        so repeated cross-origin requests from the same widget+origin pair do not
        hit the database on every preflight or request.  Redis failure falls through
        to a normal DB lookup (safe degradation — no requests are incorrectly blocked).

        Cache key: cors:widget:<sha256(api_key)[:16]>:<sha256(origin)[:16]>
        Cache value: allowed origin string, or "" for denied.

        Args:
            api_key: Widget API key
            origin: Request origin

        Returns:
            Origin if allowed, None otherwise
        """
        # Build a short, privacy-safe cache key.  We hash the api_key so raw
        # credentials are never written to Redis.
        key_hash = hashlib.sha256(api_key.encode(), usedforsecurity=False).hexdigest()[:16]
        origin_hash = hashlib.sha256(origin.encode(), usedforsecurity=False).hexdigest()[:16]
        cache_key = f"cors:widget:{key_hash}:{origin_hash}"

        # --- Redis cache check ---
        try:
            from src.config.redis import get_redis_async

            aio_redis = get_redis_async()
            cached = await aio_redis.get(cache_key)
            if cached is not None:
                # "" stored → previously denied; any other string → allowed origin
                return cached if cached else None
        except Exception as exc:
            logger.warning("Redis unavailable for CORS widget cache lookup, falling back to DB: %s", exc)

        # --- DB lookup (cache miss or Redis unavailable) ---
        result: str | None = None
        try:
            # Import here to avoid circular imports at module load time
            from src.middleware.widget_auth import WidgetAuthMiddleware

            async with get_async_session_factory()() as db:
                widget = await WidgetAuthMiddleware.validate_api_key(api_key, db)

            if not widget:
                logger.warning("Widget not found for API key (length: %d)", len(api_key))
                result = None
            elif not widget.allowed_domains or "*" in widget.allowed_domains:
                # No domain restrictions — allow all origins
                result = origin
            else:
                origin_host = self._extract_host(origin)
                for allowed_domain in widget.allowed_domains:
                    if self._match_domain(origin_host, allowed_domain):
                        result = origin
                        break
                if result is None:
                    logger.warning(f"Origin {origin} not allowed for widget {widget.id}")

        except Exception as e:
            logger.warning(f"Error validating widget origin: {e}")
            return None

        # --- Store result in Redis cache ---
        try:
            from src.config.redis import get_redis_async

            aio_redis = get_redis_async()
            # Store "" for denied so we can distinguish a cached deny from a cache miss
            await aio_redis.setex(cache_key, self._WIDGET_CORS_CACHE_TTL, result if result is not None else "")
        except Exception as exc:
            logger.warning("Failed to cache CORS widget result in Redis: %s", exc)

        return result

    def _validate_dashboard_origin(self, origin: str) -> str | None:
        """
        Validate origin against dashboard allowed origins.

        Args:
            origin: Request origin

        Returns:
            Origin if allowed, None otherwise.
            Returns the literal string "*" when a wildcard is configured —
            callers must NOT send credentials with a wildcard response.
        """
        # Explicit wildcard — return "*" (not the reflected origin).
        # SECURITY: reflecting the origin with credentials=true bypasses the
        # browser's CORS credential protection. Always return the literal "*"
        # so browsers enforce the no-credentials rule.
        if "*" in self.dashboard_origins:
            return "*"

        # Check exact match
        if origin in self.dashboard_origins:
            return origin

        # Check wildcard patterns
        origin_host = self._extract_host(origin)
        for allowed_origin in self.dashboard_origins:
            allowed_host = self._extract_host(allowed_origin)
            if self._match_domain(origin_host, allowed_host):
                return origin

        return None

    def _extract_host(self, url: str) -> str:
        """
        Extract host (with port) from URL.

        Args:
            url: Full URL or host

        Returns:
            Host:port portion (port included when present)
        """
        if "://" in url:
            return url.split("://")[1].split("/")[0]
        return url.split("/")[0]

    def _match_domain(self, origin_host: str, allowed_domain: str) -> bool:
        """
        Check if origin matches allowed domain pattern.

        Compares both with and without port so that storing "localhost:3005"
        or "localhost" both match an origin of "localhost:3005".
        Supports wildcard patterns like *.example.com

        Args:
            origin_host: Origin host (may include port, e.g. "localhost:3005")
            allowed_domain: Allowed domain pattern

        Returns:
            True if matches, False otherwise
        """
        # Bare hostname without port (for fallback comparisons)
        origin_bare = origin_host.split(":")[0]
        allowed_bare = allowed_domain.split(":")[0] if not allowed_domain.startswith("*.") else allowed_domain

        # Exact match (with or without port)
        if origin_host == allowed_domain or origin_bare == allowed_bare:
            return True

        # Wildcard match (*.example.com)
        if allowed_domain.startswith("*."):
            domain_suffix = allowed_domain[2:]  # Remove *.
            return origin_bare.endswith(f".{domain_suffix}") or origin_bare == domain_suffix

        return False

    def _build_cors_headers(self, origin: str) -> list[tuple[bytes, bytes]]:
        """
        Build CORS headers as a list of tuples for pure ASGI middleware.

        Args:
            origin: Allowed origin (use "*" only when credentials must NOT be sent)

        Returns:
            List of (header_name, header_value) tuples
        """
        headers: list[tuple[bytes, bytes]] = [
            (b"access-control-allow-origin", origin.encode()),
        ]

        # SECURITY: ACAO=* and ACAC=true is forbidden by the CORS spec and
        # bypassed by reflecting the origin. Never send credentials with a wildcard.
        if self.allow_credentials and origin != "*":
            headers.append((b"access-control-allow-credentials", b"true"))

        if self.expose_headers:
            headers.append((b"access-control-expose-headers", ", ".join(self.expose_headers).encode()))

        return headers

    def _add_cors_headers(self, response: Response, origin: str) -> None:
        """
        Add CORS headers to a Response object (used for preflight responses).

        Args:
            response: Response object
            origin: Allowed origin
        """
        response.headers["Access-Control-Allow-Origin"] = origin

        # SECURITY: never send credentials with a wildcard origin
        if self.allow_credentials and origin != "*":
            response.headers["Access-Control-Allow-Credentials"] = "true"

        if self.expose_headers:
            response.headers["Access-Control-Expose-Headers"] = ", ".join(self.expose_headers)
