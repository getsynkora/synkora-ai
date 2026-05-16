"""
Widget authentication middleware.

Validates widget API keys and enforces rate limiting for widget requests.
"""

import hmac
import logging
import time

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.models.agent_widget import AgentWidget
from src.services.agents.security import decrypt_value

logger = logging.getLogger(__name__)


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

        Args:
            api_key: Widget API key to validate
            db: Async database session

        Returns:
            AgentWidget if valid, None otherwise
        """
        if not api_key:
            return None

        # Check for valid prefixes
        valid_prefixes = ("swk_", "widget_")
        if not api_key.startswith(valid_prefixes):
            return None

        key_prefix = api_key[:20] if len(api_key) >= 20 else api_key

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

        # Extract domain from origin (remove protocol and port)
        domain = origin.replace("http://", "").replace("https://", "").split(":")[0]

        # Check if domain matches any allowed domain (support wildcards)
        for allowed_domain in widget.allowed_domains:
            if allowed_domain == "*":
                return True
            if allowed_domain.startswith("*."):
                # Wildcard subdomain matching
                base_domain = allowed_domain[2:]
                if domain.endswith(base_domain):
                    return True
            elif domain == allowed_domain:
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
        widget_id = str(widget.id)
        rate_limit_key = f"widget:rate_limit:{widget_id}"
        current_time = time.time()

        redis_client = _get_redis_rate_limiter()

        # Use Redis sorted set for sliding window rate limiting
        hour_ago = current_time - 3600

        # Remove old entries
        redis_client.zremrangebyscore(rate_limit_key, 0, hour_ago)

        # Get current count
        current_count = redis_client.zcard(rate_limit_key)

        if current_count >= widget.rate_limit:
            return False

        # Add current request with timestamp as score
        redis_client.zadd(rate_limit_key, {str(current_time): current_time})

        # Set expiry on the key (1 hour + buffer)
        redis_client.expire(rate_limit_key, 3660)

        return True

    @staticmethod
    async def check_rate_limit_async(widget: AgentWidget) -> bool:
        """
        Async variant of check_rate_limit for request handlers.

        Keeps the same sliding-window semantics without blocking the FastAPI
        event loop on Redis network I/O.
        """
        widget_id = str(widget.id)
        rate_limit_key = f"widget:rate_limit:{widget_id}"
        current_time = time.time()

        redis_client = await _get_async_redis_rate_limiter()

        hour_ago = current_time - 3600
        pipe = redis_client.pipeline()
        pipe.zremrangebyscore(rate_limit_key, 0, hour_ago)
        pipe.zcard(rate_limit_key)
        results = await pipe.execute()
        current_count = int(results[1] or 0)

        if current_count >= widget.rate_limit:
            return False

        pipe = redis_client.pipeline()
        pipe.zadd(rate_limit_key, {str(current_time): current_time})
        pipe.expire(rate_limit_key, 3660)
        await pipe.execute()

        return True

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
