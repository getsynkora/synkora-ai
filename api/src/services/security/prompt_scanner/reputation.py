"""Reputation storage abstractions for the prompt scanner."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass(slots=True)
class RedisBackedReputationStore:
    """Redis-backed reputation repository with atomic updates and a local mirror."""

    ttl_seconds: int
    cache: dict[str, dict[str, int]] = field(default_factory=dict)
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)

    @staticmethod
    def _redis_key(key: str) -> str:
        return f"reputation:{key}"

    def _require_redis(self):
        from src.config.redis import get_redis

        redis = get_redis()
        if not redis:
            raise RuntimeError("Redis is required for prompt scanner reputation storage")
        return redis

    async def _require_redis_async(self):
        from src.config.redis import get_redis_async

        redis = get_redis_async()
        if not redis:
            raise RuntimeError("Redis is required for prompt scanner reputation storage")
        return redis

    def _update_local_mirror(self, key: str, violations: int) -> None:
        with self._lock:
            if violations > 0:
                self.cache[key] = {"score": 0, "violations": violations}
            else:
                self.cache.pop(key, None)

    def get_violations(self, key: str) -> int:
        """Fetch violation count from Redis."""
        redis = self._require_redis()
        raw = redis.get(self._redis_key(key))
        violations = int(raw) if raw is not None else 0
        self._update_local_mirror(key, violations)
        return violations

    async def get_violations_async(self, key: str) -> int:
        """Async fetch of violation count from Redis."""
        redis = await self._require_redis_async()
        raw = await redis.get(self._redis_key(key))
        violations = int(raw) if raw is not None else 0
        self._update_local_mirror(key, violations)
        return violations

    def set_violations(self, key: str, violations: int) -> None:
        """Persist the current violation count exactly."""
        redis = self._require_redis()
        pipe = redis.pipeline()
        if violations > 0:
            pipe.setex(self._redis_key(key), self.ttl_seconds, violations)
        else:
            pipe.delete(self._redis_key(key))
        pipe.execute()
        self._update_local_mirror(key, violations)

    async def set_violations_async(self, key: str, violations: int) -> None:
        """Persist the current violation count asynchronously."""
        redis = await self._require_redis_async()
        if violations > 0:
            await redis.setex(self._redis_key(key), self.ttl_seconds, violations)
        else:
            await redis.delete(self._redis_key(key))
        self._update_local_mirror(key, violations)

    def increment_violations(self, key: str, amount: int = 1) -> int:
        """Atomically increment the current violation count."""
        redis = self._require_redis()
        pipe = redis.pipeline()
        pipe.incrby(self._redis_key(key), amount)
        pipe.expire(self._redis_key(key), self.ttl_seconds)
        new_value = int(pipe.execute()[0])
        self._update_local_mirror(key, new_value)
        return new_value

    async def increment_violations_async(self, key: str, amount: int = 1) -> int:
        """Atomically increment the current violation count asynchronously."""
        redis = await self._require_redis_async()
        pipe = redis.pipeline()
        pipe.incrby(self._redis_key(key), amount)
        pipe.expire(self._redis_key(key), self.ttl_seconds)
        new_value = int((await pipe.execute())[0])
        self._update_local_mirror(key, new_value)
        return new_value
