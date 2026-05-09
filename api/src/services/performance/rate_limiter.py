"""
Rate limiting service.

Provides token bucket and sliding window rate limiting
with Redis backend for distributed rate limiting.
"""

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    remaining: int
    reset_time: float
    retry_after: float | None = None

    def to_headers(self) -> dict[str, str]:
        """Convert to HTTP headers."""
        headers = {
            "X-RateLimit-Remaining": str(self.remaining),
            "X-RateLimit-Reset": str(int(self.reset_time)),
        }
        if self.retry_after:
            headers["Retry-After"] = str(int(self.retry_after))
        return headers


class RateLimiter:
    """
    Rate limiter with Redis backend for distributed limiting.

    Implements a sliding window algorithm for accurate rate limiting
    across multiple application instances.

    Features:
    - Sliding window rate limiting
    - Redis backend for distributed operation
    - Configurable limits per key pattern
    - Fails open when Redis is unavailable (allows requests, logs warning)
    """

    DEFAULT_REQUESTS = 100
    DEFAULT_WINDOW = 60  # seconds

    def __init__(
        self,
        redis_client=None,
        default_requests: int = DEFAULT_REQUESTS,
        default_window: int = DEFAULT_WINDOW,
    ):
        """
        Initialize the rate limiter.

        Args:
            redis_client: Redis client (optional, will get from global)
            default_requests: Default max requests per window
            default_window: Default window size in seconds
        """
        self._redis = redis_client
        self.default_requests = default_requests
        self.default_window = default_window

        # Custom limits per key pattern
        self._custom_limits: dict[str, tuple[int, int]] = {}

        logger.info(f"Rate limiter initialized: default={default_requests} requests/{default_window}s")

    def _get_redis(self):
        """Get async Redis client."""
        if self._redis:
            return self._redis

        try:
            from src.config.redis import get_redis_async

            return get_redis_async()
        except Exception as e:
            logger.warning(f"Redis not available for rate limiting: {e}")
            return None

    def set_limit(self, key_pattern: str, requests: int, window: int):
        """
        Set custom rate limit for a key pattern.

        Args:
            key_pattern: Key pattern (e.g., "api:*", "chat:*")
            requests: Max requests per window
            window: Window size in seconds
        """
        self._custom_limits[key_pattern] = (requests, window)
        logger.info(f"Set rate limit for '{key_pattern}': {requests} requests/{window}s")

    def _get_limit(self, key: str) -> tuple[int, int]:
        """Get rate limit for a key."""
        # Check custom limits
        for pattern, limit in self._custom_limits.items():
            if key.startswith(pattern.rstrip("*")):
                return limit

        return (self.default_requests, self.default_window)

    async def _check_redis(self, key: str, max_requests: int, window: int) -> RateLimitResult:
        """Check rate limit using async Redis — non-blocking, safe to call from ASGI middleware."""
        redis = self._get_redis()
        if not redis:
            logger.warning("Redis unavailable for rate limiting — allowing request (fail open)")
            return RateLimitResult(allowed=True, remaining=max_requests, reset_time=time.time() + window)

        now = time.time()
        window_start = now - window

        try:
            pipe = redis.pipeline()

            # Remove old entries
            pipe.zremrangebyscore(key, 0, window_start)
            # Add current request
            pipe.zadd(key, {str(now): now})
            # Count requests in window
            pipe.zcard(key)
            # Set expiry
            pipe.expire(key, window)

            results = await pipe.execute()
            request_count = results[2]

            if request_count <= max_requests:
                return RateLimitResult(
                    allowed=True,
                    remaining=max_requests - request_count,
                    reset_time=now + window,
                )
            else:
                # Get oldest request time for retry calculation
                oldest = await redis.zrange(key, 0, 0, withscores=True)
                retry_after = (oldest[0][1] + window - now) if oldest else window

                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    reset_time=now + window,
                    retry_after=retry_after,
                )

        except Exception as e:
            logger.warning(f"Redis rate limit check failed: {e} — allowing request (fail open)")
            return RateLimitResult(allowed=True, remaining=max_requests, reset_time=time.time() + window)

    async def check(
        self,
        key: str,
        max_requests: int | None = None,
        window: int | None = None,
    ) -> RateLimitResult:
        """
        Check if a request should be rate limited.

        Args:
            key: Rate limit key (e.g., "user:123", "ip:1.2.3.4")
            max_requests: Optional override for max requests
            window: Optional override for window size

        Returns:
            RateLimitResult with allowed status and headers
        """
        limit_requests, limit_window = self._get_limit(key)
        max_requests = max_requests or limit_requests
        window = window or limit_window

        return await self._check_redis(f"ratelimit:{key}", max_requests, window)

    async def is_allowed(
        self,
        key: str,
        max_requests: int | None = None,
        window: int | None = None,
    ) -> bool:
        """
        Simple check if request is allowed.

        Args:
            key: Rate limit key
            max_requests: Optional override for max requests
            window: Optional override for window size

        Returns:
            True if allowed, False if rate limited
        """
        return (await self.check(key, max_requests, window)).allowed

    async def reset(self, key: str):
        """Reset rate limit for a key."""
        redis = self._get_redis()
        full_key = f"ratelimit:{key}"

        if redis:
            try:
                await redis.delete(full_key)
            except Exception as e:
                logger.warning(f"Failed to reset rate limit in Redis: {e}")

        logger.debug(f"Reset rate limit for: {key}")

    async def get_status(self, key: str) -> dict[str, Any]:
        """
        Get current rate limit status for a key.

        Args:
            key: Rate limit key

        Returns:
            Dictionary with current status
        """
        max_requests, window = self._get_limit(key)
        result = await self.check(key, max_requests=max_requests + 1, window=window)

        return {
            "key": key,
            "max_requests": max_requests,
            "window_seconds": window,
            "remaining": result.remaining,
            "reset_time": result.reset_time,
        }


# Global rate limiter instance
_rate_limiter: RateLimiter | None = None
_limiter_lock = threading.Lock()


def get_rate_limiter() -> RateLimiter:
    """
    Get the global rate limiter.

    Returns:
        RateLimiter instance
    """
    global _rate_limiter

    if _rate_limiter is None:
        with _limiter_lock:
            if _rate_limiter is None:
                _rate_limiter = RateLimiter()

    return _rate_limiter


def configure_rate_limiter(
    default_requests: int = RateLimiter.DEFAULT_REQUESTS,
    default_window: int = RateLimiter.DEFAULT_WINDOW,
    custom_limits: dict[str, tuple[int, int]] | None = None,
):
    """
    Configure the global rate limiter.

    Args:
        default_requests: Default max requests per window
        default_window: Default window size in seconds
        custom_limits: Custom limits per key pattern
    """
    global _rate_limiter

    with _limiter_lock:
        _rate_limiter = RateLimiter(
            default_requests=default_requests,
            default_window=default_window,
        )

        if custom_limits:
            for pattern, (requests, window) in custom_limits.items():
                _rate_limiter.set_limit(pattern, requests, window)
