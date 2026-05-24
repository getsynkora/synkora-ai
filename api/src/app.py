"""
FastAPI application factory.

Creates and configures the FastAPI application instance.
"""


import logging
import os
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.types import ASGIApp, Receive, Scope, Send

from src.config import settings
from src.core.database import get_async_db, init_db
from src.core.errors import APIError
from src.middleware.cors_middleware import DynamicCORSMiddleware
from src.middleware.rate_limit_middleware import RateLimitMiddleware
from src.middleware.security_middleware import SecurityHeadersMiddleware

# SECURITY: Maximum request body size (10MB default, configurable)
MAX_REQUEST_BODY_SIZE = getattr(settings, "max_request_body_size", 10 * 1024 * 1024)

# SECURITY: Paths that allow larger uploads (e.g., file uploads)
LARGE_UPLOAD_PATHS = [
    "/console/api/files/upload",
    "/api/v1/files/upload",
    "/api/v1/knowledge-bases/",
    "/api/v1/data-analysis/",
]


class RequestSizeLimitMiddleware:
    """
    SECURITY: Pure ASGI middleware to limit request body size.

    Prevents DoS attacks via extremely large request bodies.
    Pure ASGI implementation avoids BaseHTTPMiddleware task cancellation issues.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Determine max size based on path
        path = scope.get("path", "")
        max_size = MAX_REQUEST_BODY_SIZE
        for allowed_path in LARGE_UPLOAD_PATHS:
            if path.startswith(allowed_path):
                max_size = 50 * 1024 * 1024  # 50MB for file uploads
                break

        # Check Content-Length header
        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length", b"").decode()

        if content_length:
            try:
                size = int(content_length)
                if size > max_size:
                    client = scope.get("client", ("unknown", 0))
                    logging.warning(
                        f"Request body too large: {size} bytes (max: {max_size}) "
                        f"from {client[0] if client else 'unknown'}"
                    )
                    response = JSONResponse(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        content={
                            "error": "Request body too large",
                            "detail": f"Maximum request size is {max_size // (1024 * 1024)}MB",
                            "max_size_bytes": max_size,
                        },
                    )
                    await response(scope, receive, send)
                    return
            except ValueError:
                pass

        await self.app(scope, receive, send)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    """
    Application lifespan manager.

    Handles startup and shutdown events with proper resource cleanup for K8s.
    """
    import asyncio

    # Track background tasks for cleanup
    background_tasks: list[asyncio.Task] = []

    # Startup
    logging.info("Starting up Synkora API...")

    # Only call init_db() in dev/test - production should use Alembic migrations
    if settings.is_development or settings.app_env == "test":
        init_db()
        logging.info("Database tables created (dev/test mode)")
    else:
        logging.info("Skipping init_db() in production - use Alembic migrations")

    # Pre-warm the async connection pool so the first API requests aren't slow.
    # asyncpg connections are created lazily; without this, the first few requests
    # pay the full connection-establishment cost (TCP + protocol handshake + server_settings).
    try:
        from sqlalchemy import text

        from src.core.database import get_async_session_factory

        _factory = get_async_session_factory()
        async with _factory() as _warmup_session:
            await _warmup_session.execute(text("SELECT 1"))
        logging.info("Async DB connection pool pre-warmed")
    except Exception as e:
        logging.warning(f"Failed to pre-warm async DB pool: {e}")

    # Clear stale conversation lane Redis locks left by a previous process/restart.
    # In-process asyncio locks are reset on restart, so any Redis keys still present
    # are orphaned and would block new requests for up to the full TTL (15 min).
    try:
        from src.config.redis import get_redis_async

        _redis = get_redis_async()
        _stale_keys = await _redis.keys("conversation_lane:*")
        if _stale_keys:
            await _redis.delete(*_stale_keys)
            logging.info(f"Cleared {len(_stale_keys)} stale conversation lane lock(s) from Redis")
    except Exception as e:
        logging.warning(f"Failed to clear stale conversation lane locks: {e}")

    # Set up Elasticsearch index/ILM for agent session tracing
    try:
        from src.services.agents.agent_trace_setup import setup_agent_trace

        await setup_agent_trace()
    except Exception as e:
        logging.warning(f"Agent trace ES setup failed (non-critical): {e}")

    # SECURITY: Fail fast if AUDIT_CHAIN_SECRET is missing in production.
    # Without this secret, audit log entries cannot be HMAC-chained and
    # tamper detection is completely disabled.
    if settings.is_production and not settings.audit_chain_secret:
        raise RuntimeError(
            "AUDIT_CHAIN_SECRET must be set in production. "
            "Audit log tamper detection is disabled — refusing to start. "
            'Generate with: python -c "import secrets; print(secrets.token_hex(32))"'
        )

    # SECURITY: Fail fast if Redis is not using TLS in production.
    # Unencrypted Redis exposes session tokens and rate-limit state on the wire.
    _redis_url_str = str(settings.redis_url) if settings.redis_url else ""
    _allow_insecure_redis = os.environ.get("ALLOW_INSECURE_REDIS", "false").lower() == "true"
    if (
        settings.is_production
        and _redis_url_str
        and not _redis_url_str.startswith("rediss://")
        and not _allow_insecure_redis
    ):
        raise RuntimeError(
            f"Redis connection is NOT using TLS in production "
            f"(URL scheme: '{_redis_url_str.split('://')[0]}://'). "
            "Use rediss:// to encrypt Redis traffic. "
            "Set ALLOW_INSECURE_REDIS=true to suppress this check only when Redis is on an isolated private network."
        )

    # Initialize encryption key for security module
    from src.services.agents.security import set_encryption_key

    set_encryption_key(settings.encryption_key.encode())
    logging.info("Encryption key initialized for security module")

    # Disable LiteLLM debug logging
    import litellm

    litellm.suppress_debug_info = True
    litellm.set_verbose = False
    logging.getLogger("LiteLLM").setLevel(logging.WARNING)
    logging.getLogger("LiteLLM Router").setLevel(logging.WARNING)
    logging.getLogger("LiteLLM Proxy").setLevel(logging.WARNING)
    logging.info("LiteLLM debug logging disabled")

    # NOTE: Telegram bots are managed by the dedicated bot-worker service.
    # They must NOT be started here — running long-lived bot polling loops
    # inside the web-server process competes with request handling for the
    # event loop and prevents clean horizontal scaling.

    # Start WebSocket Redis subscriber for cross-pod messaging (K8s multi-pod support)
    try:
        from src.core.websocket import connection_manager

        if hasattr(connection_manager, "start_redis_subscriber"):
            await connection_manager.start_redis_subscriber()
            logging.info("WebSocket Redis subscriber started for cross-pod messaging")
    except Exception as e:
        logging.warning(f"Failed to start WebSocket Redis subscriber: {e}")

    # SECURITY: Configure WebSocket room authorization
    try:
        from src.services.websocket_auth_service import setup_websocket_authorization

        setup_websocket_authorization()
        logging.info("WebSocket room authorization configured")
    except Exception as e:
        logging.error(f"Failed to configure WebSocket authorization: {e}")

    # Start cache invalidation subscriber for distributed cache (K8s multi-pod support)
    try:
        from src.services.cache.agent_cache_service import get_agent_cache

        agent_cache = get_agent_cache()
        await agent_cache.start_invalidation_subscriber()
        logging.info("Cache invalidation subscriber started for cross-pod cache sync")
    except Exception as e:
        logging.warning(f"Failed to start cache invalidation subscriber: {e}")

    yield

    # Shutdown - Clean up all resources for graceful K8s termination
    logging.info("Shutting down Synkora API...")

    # Cancel background tasks with timeout
    for task in background_tasks:
        if not task.done():
            task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=5.0)
            except (TimeoutError, asyncio.CancelledError):
                pass

    # Stop cache invalidation subscriber
    try:
        from src.services.cache.agent_cache_service import get_agent_cache

        agent_cache = get_agent_cache()
        await agent_cache.stop_invalidation_subscriber()
        logging.info("Cache invalidation subscriber stopped")
    except Exception as e:
        logging.debug(f"Cache invalidation subscriber cleanup skipped: {e}")

    # Stop WebSocket Redis subscriber
    try:
        from src.core.websocket import connection_manager

        if hasattr(connection_manager, "stop_redis_subscriber"):
            await connection_manager.stop_redis_subscriber()
            logging.info("WebSocket Redis subscriber stopped")
    except Exception as e:
        logging.debug(f"WebSocket Redis subscriber cleanup skipped: {e}")

    # Close database connection pools (both sync and async)
    try:
        from src.core.database import close_async_db, close_db

        # Close async engine first (used by FastAPI)
        await close_async_db()
        logging.info("Async database connection pool closed")

        # Close sync engine (used by Celery tasks)
        close_db()
        logging.info("Sync database connection pool closed")
    except Exception as e:
        logging.error(f"Error closing database pool: {e}")

    # Close Redis connections (sync + async)
    try:
        from src.config.redis import close_redis, close_redis_async

        close_redis()
        await close_redis_async()
        logging.info("Redis connections closed")
    except Exception as e:
        logging.error(f"Error closing Redis connection: {e}")

    # Close vector DB connection pool
    try:
        from src.services.performance.connection_pool import close_vector_db_pool

        close_vector_db_pool()
        logging.info("Vector DB connection pool closed")
    except Exception as e:
        logging.debug(f"Vector DB pool cleanup skipped: {e}")

    # Close HTTP client pools
    try:
        from src.services.oauth.http_client import close_http_clients

        await close_http_clients()
        logging.info("HTTP client pools closed")
    except Exception as e:
        logging.debug(f"HTTP client cleanup skipped: {e}")

    # Close LLM client pool
    try:
        from src.services.performance.llm_client_pool import close_llm_client_pool

        close_llm_client_pool()
        logging.info("LLM client pool closed")
    except Exception as e:
        logging.debug(f"LLM client pool cleanup skipped: {e}")

    logging.info("Synkora API shutdown complete")


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.

    Returns:
        Configured FastAPI application
    """
    # Initialize Sentry if configured
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.sentry_environment or settings.app_env,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
                LoggingIntegration(
                    level=logging.INFO,
                    event_level=logging.ERROR,
                ),
            ],
            traces_sample_rate=1.0 if settings.app_debug else 0.1,
            profiles_sample_rate=1.0 if settings.app_debug else 0.1,
            send_default_pii=False,  # Don't send PII by default
        )
        logging.info("Sentry initialized for error tracking")

    # SECURITY: Hide OpenAPI schema in production regardless of APP_DEBUG setting.
    # A developer may set APP_DEBUG=true in production for verbose logging — the schema
    # must remain hidden to avoid exposing endpoint details to attackers.
    _expose_docs = not settings.is_production
    app = FastAPI(
        title="Synkora API",
        description="Production-ready LLM application platform API",
        version="1.0.0",
        docs_url="/api/v1/docs" if _expose_docs else None,
        redoc_url="/api/v1/redoc" if _expose_docs else None,
        openapi_url="/api/v1/openapi.json" if _expose_docs else None,
        lifespan=lifespan,
    )

    # Configure dynamic CORS middleware
    # Supports both dashboard and widget requests with domain validation
    # SECURITY: Use configured origins from environment, not wildcard
    cors_origins = settings.cors_origins
    # Only fall back to localhost defaults in development mode.
    # In staging/production with no origins configured, leave it empty so
    # cross-origin requests are rejected rather than silently allowed.
    if not cors_origins or cors_origins == ["*"]:
        if settings.is_development:
            cors_origins = [
                "http://localhost:3000",
                "http://localhost:3001",
                "http://localhost:3005",
                "http://127.0.0.1:3000",
                "http://127.0.0.1:3001",
                "http://127.0.0.1:3005",
            ]
        else:
            # Production/staging: require explicit CORS_ORIGINS env var.
            # Log a warning so operators know they need to configure this.
            logging.warning(
                "CORS_ORIGINS is not configured. All cross-origin requests will be blocked. "
                "Set CORS_ORIGINS=https://your-frontend-domain in your environment."
            )
            cors_origins = []

    app.add_middleware(
        DynamicCORSMiddleware,
        dashboard_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        # Enumerate headers explicitly instead of wildcard alongside named header.
        # Wildcard ("*") already covers everything; listing X-CSRF-Token next to it
        # is contradictory and implies enforcement that doesn't exist.
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-Widget-API-Key", "X-API-Key"],
        expose_headers=["Content-Type", "Authorization"],
        max_age=600,
    )

    # Prometheus labeled HTTP metrics (method/endpoint/status_code)
    from src.services.performance.metrics import PrometheusMiddleware

    app.add_middleware(PrometheusMiddleware)

    # SECURITY: Add security headers middleware (CSP, X-Frame-Options, etc.)
    app.add_middleware(SecurityHeadersMiddleware)

    # SECURITY: Add XSS input sanitization middleware
    from src.middleware.security_middleware import InputSanitizationMiddleware

    app.add_middleware(InputSanitizationMiddleware)

    # SECURITY: Add request size limit middleware (first defense against large payloads)
    app.add_middleware(RequestSizeLimitMiddleware)

    # Add rate limiting middleware (before other middleware)
    # Protects against abuse and ensures fair resource usage
    app.add_middleware(
        RateLimitMiddleware,
        enabled=settings.rate_limit_enabled,
        default_requests=100,
        default_window=60,
    )

    # Add plan restriction middleware
    # Enforces subscription plan limits on resource creation
    from src.middleware.plan_restriction_middleware import PlanRestrictionMiddleware

    app.add_middleware(PlanRestrictionMiddleware)

    # Register error handlers
    register_error_handlers(app)

    # Register routers
    register_routers(app)

    # Setup logging
    setup_logging()

    return app


def register_error_handlers(app: FastAPI) -> None:
    """
    Register error handlers for the application.

    Args:
        app: FastAPI application
    """

    @app.exception_handler(APIError)
    async def handle_api_error(request, exc: APIError):  # noqa: ARG001
        """Handle custom API errors."""
        return JSONResponse(
            status_code=exc.code,
            content=exc.to_dict(),
        )

    @app.exception_handler(ValueError)
    async def handle_value_error(request, exc: ValueError):  # noqa: ARG001
        """Handle ValueError exceptions with sanitized messages in production."""
        # Don't expose internal error details in production
        message = str(exc) if not settings.is_production else "Invalid input"
        if settings.is_production:
            logging.warning(f"ValueError: {exc}")

        return JSONResponse(
            status_code=400,
            content={
                "code": "value_error",
                "message": message,
                "status": 400,
            },
        )

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request, exc: HTTPException):  # noqa: ARG001
        """Handle HTTPException with sanitized error messages in production."""
        # For 5xx errors, hide internal details in production
        if exc.status_code >= 500 and settings.is_production:
            detail = "An internal server error occurred"
            logging.error(f"HTTPException {exc.status_code}: {exc.detail}", exc_info=True)
        else:
            detail = exc.detail

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": detail,
            },
        )

    @app.exception_handler(Exception)
    async def handle_generic_exception(request, exc: Exception):  # noqa: ARG001
        """Handle unexpected exceptions."""
        logging.error(f"Unhandled exception: {exc}", exc_info=True)

        # Capture exception to Sentry if configured
        if settings.sentry_dsn:
            sentry_sdk.capture_exception(exc)

        # Don't expose internal errors in production
        message = "An internal error occurred" if settings.is_production else str(exc)

        return JSONResponse(
            status_code=500,
            content={
                "code": "internal_error",
                "message": message,
                "status": 500,
            },
        )


def register_routers(app: FastAPI) -> None:
    """
    Register API routers.

    Uses the declarative router registry for cleaner configuration.
    See src/router_registry.py for the full list of routes.

    Args:
        app: FastAPI application
    """
    from src.router_registry import register_all_routers

    # Register all routers from the declarative registry
    register_all_routers(app)

    # Health check endpoints for Kubernetes
    @app.get("/health", tags=["health"])
    async def health_check():
        """Basic health check endpoint."""
        return {"status": "healthy", "version": settings.app_version}

    @app.get("/live", tags=["health"])
    async def liveness_probe():
        """
        Kubernetes liveness probe.

        Returns 200 if the application is running.
        Used by K8s to determine if the pod should be restarted.
        """
        return {"status": "alive"}

    @app.get("/ready", tags=["health"])
    async def readiness_probe(db: AsyncSession = Depends(get_async_db)):
        """
        Kubernetes readiness probe.

        Checks database and Redis connectivity.
        Used by K8s to determine if the pod should receive traffic.
        """
        from sqlalchemy import text

        health_status = {"status": "ready", "checks": {}}

        # Check database connectivity
        try:
            await db.execute(text("SELECT 1"))
            health_status["checks"]["database"] = "ok"
        except Exception as e:
            health_status["status"] = "not_ready"
            health_status["checks"]["database"] = "error"
            logging.error(f"Readiness probe database check failed: {e}")

        # Check Redis connectivity (async — must not block the event loop)
        try:
            from src.config.redis import get_redis_async

            await get_redis_async().ping()
            health_status["checks"]["redis"] = "ok"
        except Exception as e:
            health_status["status"] = "not_ready"
            health_status["checks"]["redis"] = "error"
            logging.error(f"Readiness probe Redis check failed: {e}")

        if health_status["status"] != "ready":
            raise HTTPException(status_code=503, detail=health_status)

        return health_status

    # Prometheus metrics endpoint
    @app.get("/metrics", tags=["monitoring"])
    async def prometheus_metrics(request: Request):
        """
        Prometheus metrics endpoint.

        SECURITY: Protected by METRICS_AUTH_TOKEN when configured.
        Set METRICS_AUTH_TOKEN in your environment for production deployments.
        Prometheus scrapers should pass: Authorization: Bearer <token>
        """
        metrics_token = settings.metrics_auth_token
        if metrics_token:
            auth_header = request.headers.get("Authorization", "")
            if auth_header != f"Bearer {metrics_token}":
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Metrics access requires a valid bearer token."},
                )
        elif settings.is_production:
            # No token configured in production — deny access to prevent data leakage.
            # Set METRICS_AUTH_TOKEN in your environment to enable Prometheus scraping.
            return JSONResponse(
                status_code=403,
                content={"detail": "Metrics endpoint requires METRICS_AUTH_TOKEN to be configured in production."},
            )

        from src.services.performance.metrics import get_metrics_collector

        collector = get_metrics_collector()
        return PlainTextResponse(
            content=collector.to_prometheus_format(),
            media_type="text/plain; charset=utf-8",
        )

    # Performance stats endpoint
    @app.get("/api/v1/stats/performance", tags=["monitoring"])
    async def performance_stats(request: Request):
        """
        Get performance statistics.

        SECURITY: Protected by METRICS_AUTH_TOKEN when configured.
        """
        metrics_token = settings.metrics_auth_token
        if metrics_token:
            auth_header = request.headers.get("Authorization", "")
            if auth_header != f"Bearer {metrics_token}":
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Performance stats access requires a valid bearer token."},
                )
        elif settings.is_production:
            return JSONResponse(
                status_code=403,
                content={"detail": "Stats endpoint requires METRICS_AUTH_TOKEN to be configured in production."},
            )

        import math

        from src.services.performance.circuit_breaker import get_all_circuit_breaker_stats
        from src.services.performance.connection_pool import get_vector_db_pool
        from src.services.performance.llm_client_pool import get_llm_client_pool
        from src.services.performance.metrics import get_metrics_collector
        from src.services.performance.rate_limiter import get_rate_limiter

        def sanitize_floats(obj):
            """Recursively sanitize float values that are not JSON compliant."""
            if isinstance(obj, dict):
                return {k: sanitize_floats(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [sanitize_floats(item) for item in obj]
            elif isinstance(obj, float):
                if math.isnan(obj):
                    return None
                elif math.isinf(obj):
                    return None if obj < 0 else 9999999999
                return obj
            return obj

        stats = {
            "metrics": get_metrics_collector().collect_all(),
            "circuit_breakers": get_all_circuit_breaker_stats(),
            "rate_limiter": await get_rate_limiter().get_status("global"),
            "vector_db_pool": get_vector_db_pool().get_stats(),
            "llm_client_pool": get_llm_client_pool().get_stats(),
        }

        return sanitize_floats(stats)


class ConnectionTerminationFilter(logging.Filter):
    """
    Filter out noisy connection termination errors from SQLAlchemy.

    These errors occur when requests are cancelled (e.g., client disconnect)
    and are not actual failures - just SQLAlchemy unable to gracefully close
    connections in a cancelled async context.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        # Skip "Exception terminating connection" errors
        if "terminating connection" in msg.lower() or "exception terminating connection" in msg.lower():
            return False
        return True


def setup_logging() -> None:
    """Setup application logging."""
    log_level = logging.DEBUG if settings.app_debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
    )

    # Suppress noisy connection termination errors from SQLAlchemy async pool
    # These happen when requests are cancelled and are not actual failures
    conn_filter = ConnectionTerminationFilter()

    # Add filter to root logger to catch all connection termination errors
    logging.getLogger().addFilter(conn_filter)

    # Also add to specific SQLAlchemy loggers
    logging.getLogger("sqlalchemy.pool").addFilter(conn_filter)
    logging.getLogger("sqlalchemy.pool.base").addFilter(conn_filter)

    # Reduce noise from Slack SDK (PING/PONG and queue messages)
    logging.getLogger("slack_sdk").setLevel(logging.WARNING)
    logging.getLogger("slack_sdk.socket_mode").setLevel(logging.WARNING)
    logging.getLogger("slack_sdk.socket_mode.aiohttp").setLevel(logging.WARNING)
    logging.getLogger("slack_sdk.socket_mode.builtin").setLevel(logging.WARNING)
    logging.getLogger("slack_sdk.web.async_client").setLevel(logging.WARNING)
    logging.getLogger("slack_sdk.web.base_client").setLevel(logging.WARNING)
