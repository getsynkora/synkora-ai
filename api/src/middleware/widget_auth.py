"""
Widget authentication middleware.

Validates widget API keys and enforces rate limiting for widget requests.
"""

import hmac
import json
import logging
import types
import uuid
from urllib.parse import urlsplit

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.models.agent_widget import AgentWidget
from src.services.agents.security import decrypt_value

logger = logging.getLogger(__name__)

# ── API key Redis cache ────────────────────────────────────────────────────────
# Validated widget data is cached for 5 minutes to eliminate the DB query +
# Fernet decrypt on every single widget request.  The encrypted api_key and
# identity_secret stay encrypted in the cache — no plaintext secrets at rest.
# Cache entries are invalidated on every write (update / delete / key-regen).
_WIDGET_KEY_CACHE_TTL = 300  # seconds


def _widget_cache_key(key_prefix: str) -> str:
    return f"widget:auth:pfx:{key_prefix}"


async def _get_cached_widget(key_prefix: str):
    """Return a SimpleNamespace mimicking AgentWidget from Redis, or None on miss/error."""
    try:
        from src.config.redis import get_redis_async

        redis = get_redis_async()
        if not redis:
            return None
        raw = await redis.get(_widget_cache_key(key_prefix))
        if not raw:
            return None
        data = json.loads(raw)
        # Restore UUID fields
        data["id"] = uuid.UUID(data["id"])
        data["agent_id"] = uuid.UUID(data["agent_id"])
        data["tenant_id"] = uuid.UUID(data["tenant_id"])
        return types.SimpleNamespace(**data)
    except Exception:
        return None


async def _cache_widget(widget) -> None:
    """Serialize widget to Redis cache.  Failures are silently ignored."""
    try:
        from src.config.redis import get_redis_async

        redis = get_redis_async()
        if not redis:
            return
        data = {
            "id": str(widget.id),
            "agent_id": str(widget.agent_id),
            "tenant_id": str(widget.tenant_id),
            "api_key": widget.api_key,
            "key_prefix": widget.key_prefix,
            "widget_name": getattr(widget, "widget_name", None),
            "allowed_domains": widget.allowed_domains,
            "theme_config": getattr(widget, "theme_config", None),
            "rate_limit": widget.rate_limit,
            "is_active": widget.is_active,
            "identity_verification_required": widget.identity_verification_required,
            "mobile_allowed": getattr(widget, "mobile_allowed", False),
            "enable_agent_routing": widget.enable_agent_routing,
            "identity_secret": widget.identity_secret,
            "fcm_server_key": getattr(widget, "fcm_server_key", None),
        }
        await redis.setex(_widget_cache_key(widget.key_prefix), _WIDGET_KEY_CACHE_TTL, json.dumps(data))
    except Exception:
        pass


async def invalidate_widget_cache(key_prefix: str) -> None:
    """Delete a widget's cache entry.  Call this on every write to the widget."""
    try:
        from src.config.redis import get_redis_async

        redis = get_redis_async()
        if redis:
            await redis.delete(_widget_cache_key(key_prefix))
    except Exception:
        pass


# One atomic operation across all workers; distinct request IDs avoid timestamp collisions.
WIDGET_RATE_LIMIT_SCRIPT = """
local timestamp = redis.call('TIME')
local now = tonumber(timestamp[1]) + tonumber(timestamp[2]) / 1000000
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - 3600)
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[1]) then return 0 end
redis.call('ZADD', KEYS[1], now, ARGV[2])
redis.call('EXPIRE', KEYS[1], 3660)
return 1
"""


def _get_redis_rate_limiter():
    """
    Get Redis client for rate limiting.

    SECURITY: Redis is required for rate limiting - no fallback.
    Raises exception if Redis is unavailable.
    """
    try:
        from src.config.redis import get_redis

        redis = get_redis()
        if redis is None:
            raise RuntimeError("Redis connection returned None")
        return redis
    except Exception as e:
        logger.warning(f"SECURITY: Redis unavailable for widget rate limiting: {e}")
        raise RuntimeError("Rate limiting service temporarily unavailable. Please try again later.")


async def _get_async_redis_rate_limiter():
    """
    Get async Redis client for rate limiting.

    SECURITY: Redis is required for rate limiting - no fallback.
    Raises exception if Redis is unavailable.
    """
    try:
        from src.config.redis import get_redis_async

        redis = get_redis_async()
        if redis is None:
            raise RuntimeError("Redis connection returned None")
        return redis
    except Exception as e:
        logger.warning(f"SECURITY: Redis unavailable for widget rate limiting: {e}")
        raise RuntimeError("Rate limiting service temporarily unavailable. Please try again later.")


class WidgetAuthMiddleware:
    """Middleware for widget authentication and rate limiting."""

    @staticmethod
    async def validate_api_key(api_key: str, db: AsyncSession) -> AgentWidget | None:
        """
        Validate widget API key.

        SECURITY: Uses constant-time comparison to prevent timing attacks.
        SECURITY: API keys are stored encrypted and decrypted for comparison.
        SECURITY FIX: Uses key prefix index to prevent N+1 query DoS attacks.
        PERF: Validated widget data is cached in Redis for 5 minutes.

        Args:
            api_key: Widget API key to validate
            db: Async database session

        Returns:
            AgentWidget (or SimpleNamespace with same attributes) if valid, None otherwise
        """
        if not api_key:
            return None

        # Check for valid prefixes
        valid_prefixes = ("swk_", "widget_")
        if not api_key.startswith(valid_prefixes):
            return None

        key_prefix = api_key[:20] if len(api_key) >= 20 else api_key

        # Fast path: Redis cache hit → skip DB query entirely
        cached = await _get_cached_widget(key_prefix)
        if cached is not None:
            try:
                stored_key = decrypt_value(cached.api_key)
                if hmac.compare_digest(stored_key.encode(), api_key.encode()):
                    return cached
            except Exception:
                pass
            # Cache entry present but key didn't match (e.g. stale after regen) → fall through

        # Slow path: DB lookup + populate cache on success
        result = await db.execute(
            select(AgentWidget)
            .filter(
                AgentWidget.is_active == True,  # noqa: E712
                AgentWidget.key_prefix == key_prefix,
            )
            .limit(10)
        )
        candidate_widgets = result.scalars().all()

        matched_widget = None
        for widget in candidate_widgets:
            try:
                stored_key = decrypt_value(widget.api_key)
                if hmac.compare_digest(stored_key.encode(), api_key.encode()):
                    matched_widget = widget
                    break
            except Exception:
                try:
                    if hmac.compare_digest(widget.api_key.encode(), api_key.encode()):
                        matched_widget = widget
                        break
                except Exception:
                    pass
                continue

        if matched_widget is not None:
            await _cache_widget(matched_widget)

        return matched_widget

    @staticmethod
    def validate_domain(widget: AgentWidget, origin: str | None) -> bool:
        """
        Validate request origin against widget's allowed domains.

        Args:
            widget: Widget configuration
            origin: Request origin header

        Returns:
            True if domain is allowed, False otherwise
        """
        # If no domain restrictions, allow all
        if not widget.allowed_domains:
            return True

        # If no origin provided, reject
        if not origin:
            return False

        try:
            parsed = urlsplit(origin)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
                return False
            # Accessing port also rejects malformed/non-numeric ports.
            _ = parsed.port
            domain = parsed.hostname.rstrip(".").encode("idna").decode("ascii").lower()
        except (ValueError, UnicodeError):
            return False

        for allowed_domain in widget.allowed_domains:
            if allowed_domain == "*":
                return True
            wildcard = allowed_domain.startswith("*.")
            candidate = allowed_domain[2:] if wildcard else allowed_domain
            try:
                candidate = candidate.rstrip(".").encode("idna").decode("ascii").lower()
            except UnicodeError:
                continue
            if wildcard:
                if domain.endswith("." + candidate):
                    return True
            elif domain == candidate:
                return True

        return False

    @staticmethod
    def check_rate_limit(widget: AgentWidget) -> bool:
        """
        Check if widget has exceeded rate limit.

        SECURITY: Uses Redis for distributed rate limiting. No fallback -
        if Redis is unavailable, the request will fail safely.

        Args:
            widget: Widget configuration

        Returns:
            True if within rate limit, False if exceeded

        Raises:
            RuntimeError: If Redis is unavailable
        """
        redis_client = _get_redis_rate_limiter()
        return bool(
            redis_client.eval(
                WIDGET_RATE_LIMIT_SCRIPT, 1, f"widget:rate_limit:{widget.id}", widget.rate_limit, uuid.uuid4().hex
            )
        )

    @staticmethod
    async def check_rate_limit_async(widget: AgentWidget) -> bool:
        """
        Async variant of check_rate_limit for request handlers.

        Keeps the same sliding-window semantics without blocking the FastAPI
        event loop on Redis network I/O.
        """
        redis_client = await _get_async_redis_rate_limiter()
        return bool(
            await redis_client.eval(
                WIDGET_RATE_LIMIT_SCRIPT, 1, f"widget:rate_limit:{widget.id}", widget.rate_limit, uuid.uuid4().hex
            )
        )

    @staticmethod
    async def authenticate_widget_request(request: Request) -> AgentWidget:
        """
        Authenticate widget request.

        Args:
            request: FastAPI request object

        Returns:
            Authenticated widget

        Raises:
            HTTPException: If authentication fails
        """
        # Get API key from header
        api_key = request.headers.get("X-Widget-API-Key")
        if not api_key:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Widget API key is required")

        # Get database session
        async for db in get_async_db():
            try:
                # Validate API key
                widget = await WidgetAuthMiddleware.validate_api_key(api_key, db)
                if not widget:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or inactive widget API key"
                    )

                # Validate domain
                origin = request.headers.get("Origin") or request.headers.get("Referer")
                if not WidgetAuthMiddleware.validate_domain(widget, origin):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN, detail="Domain not allowed for this widget"
                    )

                # Check rate limit
                if not await WidgetAuthMiddleware.check_rate_limit_async(widget):
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded for this widget"
                    )

                return widget
            finally:
                await db.close()


def get_widget_from_request(request: Request) -> AgentWidget:
    """
    Dependency to get authenticated widget from request.

    Args:
        request: FastAPI request object

    Returns:
        Authenticated widget
    """
    # This will be set by the middleware
    if not hasattr(request.state, "widget"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Widget authentication required")
    return request.state.widget
