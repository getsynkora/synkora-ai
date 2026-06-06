"""
Redis-backed agent registry for horizontal scaling.

Provides distributed agent state management using Redis,
enabling multiple application instances to share agent configurations.
"""

import json
import logging
import os
import threading
from typing import Any

logger = logging.getLogger(__name__)


class RedisAgentRegistry:
    """
    Redis-backed agent registry for distributed operation.

    Stores agent metadata in Redis to enable:
    - Horizontal scaling across multiple instances
    - Persistence across restarts
    - Shared state for multi-instance deployments

    Note: Agent instances are still created in-memory per process,
    but metadata and configurations are shared via Redis.
    """

    KEY_PREFIX = "agent_registry"
    AGENT_SET_KEY = f"{KEY_PREFIX}:agents"
    RUNTIME_SET_KEY = f"{KEY_PREFIX}:runtimes"
    CONFIG_PREFIX = f"{KEY_PREFIX}:config"
    STATS_PREFIX = f"{KEY_PREFIX}:stats"
    DEFAULT_TTL = 86400  # 24 hours

    def __init__(self, redis_client=None, ttl: int = DEFAULT_TTL):
        """
        Initialize the Redis-backed registry.

        Args:
            redis_client: Redis client (optional, will get from global)
            ttl: TTL for registry entries in seconds
        """
        self._redis = redis_client
        self._ttl = ttl
        self._local_cache: dict[str, Any] = {}
        self._lock = threading.RLock()
        self._pod_id = os.getenv("HOSTNAME", os.getenv("POD_NAME", f"pod-{os.getpid()}"))

        logger.info(f"Redis agent registry initialized with TTL={ttl}s")

    def _get_redis(self):
        """Get Redis client."""
        if self._redis:
            return self._redis

        try:
            from src.config.redis import get_redis

            return get_redis()
        except Exception as e:
            logger.warning(f"Redis not available: {e}")
            return None

    def _config_key(self, agent_name: str) -> str:
        """Get Redis key for agent config."""
        return f"{self.CONFIG_PREFIX}:{agent_name}"

    def _runtime_key(self, tenant_id: str, agent_name: str, runtime_id: str) -> str:
        """Stable runtime identifier for one agent runtime on this pod."""
        return f"{self._pod_id}:{tenant_id}:{agent_name}:{runtime_id}"

    def _pod_runtime_set_key(self) -> str:
        return f"{self.KEY_PREFIX}:pod:{self._pod_id}:runtimes"

    def _stats_key(self, agent_name: str) -> str:
        """Get Redis key for agent stats."""
        return f"{self.STATS_PREFIX}:{agent_name}"

    def register_runtime(
        self,
        tenant_id: str,
        agent_name: str,
        runtime_id: str,
        config: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Register one in-process runtime instance for this pod."""
        redis = self._get_redis()
        if not redis:
            return False

        runtime_key = self._runtime_key(tenant_id, agent_name, runtime_id)
        try:
            safe_config = self._sanitize_config(config)
            data = {
                "pod_id": self._pod_id,
                "tenant_id": tenant_id,
                "agent_name": agent_name,
                "runtime_id": runtime_id,
                "config": safe_config,
                "metadata": metadata or {},
            }
            pipe = redis.pipeline()
            pipe.sadd(self.RUNTIME_SET_KEY, runtime_key)
            pipe.sadd(self._pod_runtime_set_key(), runtime_key)
            pipe.setex(self._config_key(runtime_key), self._ttl, json.dumps(data))
            pipe.execute()
            return True
        except Exception as e:
            logger.error(f"Failed to register agent runtime in Redis: {e}")
            return False

    def unregister_runtime(self, tenant_id: str, agent_name: str, runtime_id: str | None = None) -> bool:
        """Unregister one runtime, or all runtimes for an agent on this pod."""
        redis = self._get_redis()
        if not redis:
            return False

        try:
            runtime_keys = set(redis.smembers(self._pod_runtime_set_key()) or [])
            prefix = self._runtime_key(tenant_id, agent_name, "")
            keys_to_remove = [
                key
                for key in runtime_keys
                if key.startswith(prefix) and (runtime_id is None or key.endswith(f":{runtime_id}"))
            ]
            if not keys_to_remove:
                return False

            pipe = redis.pipeline()
            for key in keys_to_remove:
                pipe.srem(self.RUNTIME_SET_KEY, key)
                pipe.srem(self._pod_runtime_set_key(), key)
                pipe.delete(self._config_key(key))
                pipe.delete(self._stats_key(key))
            pipe.execute()
            return True
        except Exception as e:
            logger.error(f"Failed to unregister agent runtime from Redis: {e}")
            return False

    def register_config(
        self,
        agent_name: str,
        config: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        Register agent configuration in Redis.

        Args:
            agent_name: Name of the agent
            config: Agent configuration dictionary
            metadata: Optional additional metadata

        Returns:
            True if registered successfully
        """
        redis = self._get_redis()
        if not redis:
            logger.warning("Redis unavailable, config not persisted")
            return False

        try:
            # Prepare data (exclude sensitive fields from config)
            safe_config = self._sanitize_config(config)
            data = {
                "name": agent_name,
                "config": safe_config,
                "metadata": metadata or {},
            }

            # Store in Redis
            pipe = redis.pipeline()
            pipe.sadd(self.AGENT_SET_KEY, agent_name)
            pipe.setex(self._config_key(agent_name), self._ttl, json.dumps(data))
            pipe.execute()

            logger.info(f"Registered agent config in Redis: {agent_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to register agent in Redis: {e}")
            return False

    def _sanitize_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Remove sensitive fields from config for storage."""
        safe_config = config.copy()

        # Remove API keys and other sensitive data
        sensitive_keys = ["api_key", "password", "token", "secret"]
        for key in sensitive_keys:
            if key in safe_config:
                safe_config[key] = "[REDACTED]"

            # Also check nested dicts like llm_config
            if isinstance(safe_config.get("llm_config"), dict):
                llm_config = safe_config["llm_config"].copy()
                for sk in sensitive_keys:
                    if sk in llm_config:
                        llm_config[sk] = "[REDACTED]"
                safe_config["llm_config"] = llm_config

        return safe_config

    def unregister(self, agent_name: str) -> bool:
        """
        Remove agent from Redis registry.

        Args:
            agent_name: Name of the agent

        Returns:
            True if removed successfully
        """
        redis = self._get_redis()
        if not redis:
            return False

        try:
            pipe = redis.pipeline()
            pipe.srem(self.AGENT_SET_KEY, agent_name)
            pipe.delete(self._config_key(agent_name))
            pipe.delete(self._stats_key(agent_name))
            pipe.execute()

            logger.info(f"Unregistered agent from Redis: {agent_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to unregister agent from Redis: {e}")
            return False

    def get_config(self, agent_name: str) -> dict[str, Any] | None:
        """
        Get agent configuration from Redis.

        Args:
            agent_name: Name of the agent

        Returns:
            Agent configuration or None if not found
        """
        redis = self._get_redis()
        if not redis:
            return None

        try:
            data = redis.get(self._config_key(agent_name))
            if data:
                return json.loads(data)
            return None

        except Exception as e:
            logger.error(f"Failed to get agent config from Redis: {e}")
            return None

    def list_agents(self) -> list[str]:
        """
        List all registered agent names.

        Returns:
            List of agent names
        """
        redis = self._get_redis()
        if not redis:
            return []

        try:
            agents = redis.smembers(self.AGENT_SET_KEY)
            return list(agents) if agents else []

        except Exception as e:
            logger.error(f"Failed to list agents from Redis: {e}")
            return []

    def exists(self, agent_name: str) -> bool:
        """
        Check if agent is registered in Redis.

        Args:
            agent_name: Name of the agent

        Returns:
            True if agent exists
        """
        redis = self._get_redis()
        if not redis:
            return False

        try:
            return redis.sismember(self.AGENT_SET_KEY, agent_name)

        except Exception as e:
            logger.error(f"Failed to check agent existence in Redis: {e}")
            return False

    def update_stats(
        self,
        agent_name: str,
        stats: dict[str, Any],
    ) -> bool:
        """
        Update agent statistics in Redis.

        Args:
            agent_name: Name of the agent
            stats: Statistics to update

        Returns:
            True if updated successfully
        """
        redis = self._get_redis()
        if not redis:
            return False

        try:
            # Use HINCRBY for numeric stats for atomic updates
            key = self._stats_key(agent_name)

            pipe = redis.pipeline()
            for stat_name, value in stats.items():
                if isinstance(value, (int, float)):
                    pipe.hincrbyfloat(key, stat_name, value)
                else:
                    pipe.hset(key, stat_name, json.dumps(value))
            pipe.expire(key, self._ttl)
            pipe.execute()

            return True

        except Exception as e:
            logger.error(f"Failed to update agent stats in Redis: {e}")
            return False

    def get_stats(self, agent_name: str) -> dict[str, Any]:
        """
        Get agent statistics from Redis.

        Args:
            agent_name: Name of the agent

        Returns:
            Statistics dictionary
        """
        redis = self._get_redis()
        if not redis:
            return {}

        try:
            data = redis.hgetall(self._stats_key(agent_name))
            if not data:
                return {}

            # Parse values
            result = {}
            for key, value in data.items():
                try:
                    result[key] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    result[key] = value

            return result

        except Exception as e:
            logger.error(f"Failed to get agent stats from Redis: {e}")
            return {}

    def refresh_ttl(self, agent_name: str) -> bool:
        """
        Refresh TTL for an agent's data.

        Args:
            agent_name: Name of the agent

        Returns:
            True if refreshed successfully
        """
        redis = self._get_redis()
        if not redis:
            return False

        try:
            pipe = redis.pipeline()
            pipe.expire(self._config_key(agent_name), self._ttl)
            pipe.expire(self._stats_key(agent_name), self._ttl)
            pipe.execute()
            return True

        except Exception as e:
            logger.error(f"Failed to refresh TTL for agent: {e}")
            return False

    def clear(self) -> bool:
        """
        Clear all agents from Redis registry.

        Returns:
            True if cleared successfully
        """
        redis = self._get_redis()
        if not redis:
            return False

        try:
            # Get all agent names
            agents = self.list_agents()

            # Delete all keys
            pipe = redis.pipeline()
            for agent_name in agents:
                pipe.delete(self._config_key(agent_name))
                pipe.delete(self._stats_key(agent_name))
            pipe.delete(self.AGENT_SET_KEY)
            pipe.execute()

            logger.info("Cleared Redis agent registry")
            return True

        except Exception as e:
            logger.error(f"Failed to clear Redis registry: {e}")
            return False


# Global instance
_redis_registry: RedisAgentRegistry | None = None
_registry_lock = threading.Lock()


def get_redis_registry() -> RedisAgentRegistry:
    """
    Get the global Redis agent registry.

    Returns:
        RedisAgentRegistry instance
    """
    global _redis_registry

    if _redis_registry is None:
        with _registry_lock:
            if _redis_registry is None:
                _redis_registry = RedisAgentRegistry()

    return _redis_registry
