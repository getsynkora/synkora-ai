"""
Agent caching service using Redis for high-performance agent data retrieval.

Supports distributed cache invalidation via Redis pub/sub for K8s multi-pod deployments.

Caches:
- Agent configurations
- Agent tools
- Knowledge base metadata
- Context files
"""

import asyncio
import json
import logging
import os
from datetime import timedelta

logger = logging.getLogger(__name__)

# Redis pub/sub channel for distributed cache invalidation
CACHE_INVALIDATION_CHANNEL = "cache:invalidation:agent"


class AgentCacheService:
    """
    Service for caching agent-related data in Redis.

    Supports distributed cache invalidation via Redis pub/sub for K8s multi-pod deployments.
    When cache is invalidated on one pod, all other pods are notified via pub/sub.
    """

    def __init__(self, redis_client=None):
        """
        Initialize the cache service.

        Args:
            redis_client: Async Redis client instance (optional, will use global if not provided)
        """
        self.redis = redis_client
        self.default_ttl = 300  # 5 minutes default TTL
        self._pod_id = os.getenv("HOSTNAME", os.getenv("POD_NAME", f"pod-{os.getpid()}"))
        self._subscriber_task: asyncio.Task | None = None
        self._pubsub = None

    def _get_redis(self):
        """Get async Redis client, fallback to import if not provided."""
        if self.redis:
            return self.redis

        try:
            from src.config.redis import get_redis_async

            return get_redis_async()
        except Exception as e:
            logger.warning(f"Redis not available: {e}")
            return None

    def _build_key(self, prefix: str, identifier: str) -> str:
        """Build cache key with prefix."""
        return f"agent_cache:{prefix}:{identifier}"

    def _agent_config_key(self, slug: str, tenant_id: str = "") -> str:
        """Build tenant-scoped cache key for agent config."""
        identifier = f"{tenant_id}:{slug}" if tenant_id else slug
        return self._build_key("config", identifier)

    async def get_agent_config(self, slug: str, tenant_id: str = "") -> dict | None:
        """
        Get cached agent configuration.

        Args:
            slug: Globally unique agent slug
            tenant_id: Tenant ID — must be provided to prevent cross-tenant cache hits

        Returns:
            Cached agent config or None
        """
        redis = self._get_redis()
        if not redis:
            return None

        try:
            key = self._agent_config_key(slug, tenant_id)
            cached_data = await redis.get(key)

            if cached_data:
                logger.info(f"Cache HIT: Agent config for '{slug}' (tenant={tenant_id or 'unscoped'})")
                return json.loads(cached_data)

            logger.info(f"Cache MISS: Agent config for '{slug}' (tenant={tenant_id or 'unscoped'})")
            return None
        except Exception as e:
            logger.error(f"Error getting cached agent config: {e}")
            return None

    async def set_agent_config(self, slug: str, config: dict, tenant_id: str = "", ttl: int = None) -> bool:
        """
        Cache agent configuration.

        Args:
            slug: Globally unique agent slug
            config: Agent configuration dict
            tenant_id: Tenant ID — must be provided to prevent cross-tenant cache pollution
            ttl: Time to live in seconds (default: 5 minutes)

        Returns:
            True if cached successfully
        """
        redis = self._get_redis()
        if not redis:
            return False

        try:
            key = self._agent_config_key(slug, tenant_id)
            ttl = ttl or self.default_ttl

            await redis.setex(key, timedelta(seconds=ttl), json.dumps(config))

            logger.info(f"Cached agent config for '{slug}' (tenant={tenant_id or 'unscoped'}, TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.error(f"Error caching agent config: {e}")
            return False

    async def get_agent_tools(self, agent_id: str) -> list | None:
        """Get cached agent tools."""
        redis = self._get_redis()
        if not redis:
            return None

        try:
            key = self._build_key("tools", agent_id)
            cached_data = await redis.get(key)

            if cached_data:
                logger.info(f"Cache HIT: Agent tools for ID '{agent_id}'")
                return json.loads(cached_data)

            return None
        except Exception as e:
            logger.error(f"Error getting cached agent tools: {e}")
            return None

    async def set_agent_tools(self, agent_id: str, tools: list, ttl: int = None) -> bool:
        """Cache agent tools."""
        redis = self._get_redis()
        if not redis:
            return False

        try:
            key = self._build_key("tools", agent_id)
            ttl = ttl or self.default_ttl

            await redis.setex(key, timedelta(seconds=ttl), json.dumps(tools))

            logger.info(f"Cached {len(tools)} tools for agent ID '{agent_id}' (TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.error(f"Error caching agent tools: {e}")
            return False

    async def get_agents_list(self, tenant_id: str, page: int = 1, page_size: int = 10) -> dict | None:
        """
        Get cached agents list for a tenant.

        Args:
            tenant_id: Tenant ID
            page: Page number
            page_size: Number of items per page

        Returns:
            Cached agents list response or None
        """
        redis = self._get_redis()
        if not redis:
            return None

        try:
            key = self._build_key("list", f"{tenant_id}:{page}:{page_size}")
            cached_data = await redis.get(key)

            if cached_data:
                logger.info(f"Cache HIT: Agents list for tenant '{tenant_id}' (page={page})")
                return json.loads(cached_data)

            logger.debug(f"Cache MISS: Agents list for tenant '{tenant_id}' (page={page})")
            return None
        except Exception as e:
            logger.error(f"Error getting cached agents list: {e}")
            return None

    async def set_agents_list(
        self, tenant_id: str, data: dict, page: int = 1, page_size: int = 10, ttl: int = None
    ) -> bool:
        """
        Cache agents list for a tenant.

        Args:
            tenant_id: Tenant ID
            data: Agents list response data
            page: Page number
            page_size: Number of items per page
            ttl: Time to live in seconds (default: 60 seconds for list data)

        Returns:
            True if cached successfully
        """
        redis = self._get_redis()
        if not redis:
            return False

        try:
            key = self._build_key("list", f"{tenant_id}:{page}:{page_size}")
            # Shorter TTL for list data (60s) since it changes more frequently
            ttl = ttl or 60

            await redis.setex(key, timedelta(seconds=ttl), json.dumps(data))

            logger.info(f"Cached agents list for tenant '{tenant_id}' (page={page}, TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.error(f"Error caching agents list: {e}")
            return False

    async def invalidate_agents_list(self, tenant_id: str, broadcast: bool = True):
        """
        Invalidate all cached agents list pages for a tenant.

        Args:
            tenant_id: Tenant ID
            broadcast: Whether to broadcast invalidation to other pods
        """
        redis = self._get_redis()
        if not redis:
            return

        try:
            # Delete all list cache keys for this tenant using SCAN (non-blocking, O(1) per call)
            pattern = self._build_key("list", f"{tenant_id}:*")
            keys = [key async for key in redis.scan_iter(pattern)]

            if keys:
                await redis.delete(*keys)
                logger.info(f"Invalidated {len(keys)} agents list cache entries for tenant '{tenant_id}'")

            # Broadcast invalidation to other pods
            if broadcast:
                await self._publish_list_invalidation(tenant_id)

        except Exception as e:
            logger.error(f"Error invalidating agents list cache: {e}")

    async def _publish_list_invalidation(self, tenant_id: str):
        """Publish agents list cache invalidation via Redis pub/sub."""
        redis = self._get_redis()
        if not redis:
            return

        try:
            message = json.dumps(
                {
                    "type": "agents_list_cache_invalidation",
                    "tenant_id": tenant_id,
                    "source_pod": self._pod_id,
                }
            )
            await redis.publish(CACHE_INVALIDATION_CHANNEL, message)
            logger.debug(f"Published agents list cache invalidation for tenant {tenant_id}")
        except Exception as e:
            logger.warning(f"Failed to publish list cache invalidation: {e}")

    async def get_knowledge_bases(self, agent_id: str) -> list | None:
        """Get cached knowledge bases for an agent."""
        redis = self._get_redis()
        if not redis:
            return None

        try:
            key = self._build_key("kbs", agent_id)
            cached_data = await redis.get(key)

            if cached_data:
                logger.info(f"Cache HIT: Knowledge bases for agent ID '{agent_id}'")
                return json.loads(cached_data)

            return None
        except Exception as e:
            logger.error(f"Error getting cached knowledge bases: {e}")
            return None

    async def set_knowledge_bases(self, agent_id: str, kbs: list, ttl: int = None) -> bool:
        """Cache knowledge bases for an agent."""
        redis = self._get_redis()
        if not redis:
            return False

        try:
            key = self._build_key("kbs", agent_id)
            ttl = ttl or self.default_ttl

            await redis.setex(key, timedelta(seconds=ttl), json.dumps(kbs))

            logger.info(f"Cached {len(kbs)} knowledge bases for agent ID '{agent_id}' (TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.error(f"Error caching knowledge bases: {e}")
            return False

    async def get_context_files(self, agent_id: str) -> list | None:
        """Get cached context files for an agent."""
        redis = self._get_redis()
        if not redis:
            return None

        try:
            key = self._build_key("context_files", agent_id)
            cached_data = await redis.get(key)

            if cached_data:
                logger.info(f"Cache HIT: Context files for agent ID '{agent_id}'")
                return json.loads(cached_data)

            return None
        except Exception as e:
            logger.error(f"Error getting cached context files: {e}")
            return None

    async def set_context_files(self, agent_id: str, context_files: list, ttl: int = None) -> bool:
        """Cache context files for an agent."""
        redis = self._get_redis()
        if not redis:
            return False

        try:
            key = self._build_key("context_files", agent_id)
            ttl = ttl or self.default_ttl

            await redis.setex(key, timedelta(seconds=ttl), json.dumps(context_files))

            logger.info(f"Cached {len(context_files)} context files for agent ID '{agent_id}' (TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.error(f"Error caching context files: {e}")
            return False

    CONTENT_CACHE_TTL = 86400  # 24 hours — content never changes after upload

    async def get_context_file_content(self, file_id: str) -> str | None:
        """Get cached extracted text for a single context file."""
        redis = self._get_redis()
        if not redis:
            return None
        try:
            key = self._build_key("context_file_content", file_id)
            cached = await redis.get(key)
            if cached:
                logger.info(f"Cache HIT: context_file_content:{file_id}")
                return json.loads(cached)
            return None
        except Exception as e:
            logger.error(f"Error getting context file content cache: {e}")
            return None

    async def set_context_file_content(self, file_id: str, content: str) -> bool:
        """Cache extracted text for a single context file (24h TTL)."""
        redis = self._get_redis()
        if not redis:
            return False
        try:
            key = self._build_key("context_file_content", file_id)
            await redis.setex(key, timedelta(seconds=self.CONTENT_CACHE_TTL), json.dumps(content))
            logger.info(f"Cached context_file_content:{file_id} (TTL: {self.CONTENT_CACHE_TTL}s)")
            return True
        except Exception as e:
            logger.error(f"Error caching context file content: {e}")
            return False

    async def invalidate_context_file_content(self, file_id: str) -> None:
        """Delete per-file content cache on file deletion."""
        redis = self._get_redis()
        if not redis:
            return
        try:
            key = self._build_key("context_file_content", file_id)
            await redis.delete(key)
            logger.info(f"Invalidated context_file_content:{file_id}")
        except Exception as e:
            logger.error(f"Error invalidating context file content: {e}")

    async def invalidate_agent(
        self,
        slug: str = None,
        agent_id: str = None,
        tenant_id: str = "",
        broadcast: bool = True,
    ):
        """
        Invalidate all cached data for an agent.

        When broadcast=True (default), also publishes invalidation message via Redis pub/sub
        to notify all other pods in K8s cluster to invalidate their local caches.

        Args:
            slug: Agent slug (for config cache)
            agent_id: Agent ID (for tools, KBs cache)
            tenant_id: Tenant ID — required to correctly target the tenant-scoped config key
            broadcast: Whether to broadcast invalidation to other pods (default: True)
        """
        redis = self._get_redis()
        if not redis:
            return

        try:
            keys_to_delete = []

            if slug:
                keys_to_delete.append(self._agent_config_key(slug, tenant_id))
                # Also invalidate the routing LLM-configs cache (keyed by slug)
                keys_to_delete.append(self._build_key("llm_configs", slug))

            if agent_id:
                keys_to_delete.append(self._build_key("tools", agent_id))
                keys_to_delete.append(self._build_key("kbs", agent_id))
                keys_to_delete.append(self._build_key("context_files", agent_id))

            if keys_to_delete:
                await redis.delete(*keys_to_delete)
                logger.info(f"Invalidated cache for agent (slug={slug}, id={agent_id})")

            # Broadcast invalidation to other pods via pub/sub
            if broadcast:
                await self._publish_invalidation(slug, agent_id)

        except Exception as e:
            logger.error(f"Error invalidating agent cache: {e}")

    async def _publish_invalidation(self, slug: str = None, agent_id: str = None):
        """
        Publish cache invalidation message via Redis pub/sub.

        This notifies all other pods to invalidate their local caches.
        """
        redis = self._get_redis()
        if not redis:
            return

        try:
            message = json.dumps(
                {
                    "type": "agent_cache_invalidation",
                    "agent_slug": slug,
                    "agent_id": agent_id,
                    "source_pod": self._pod_id,
                }
            )
            await redis.publish(CACHE_INVALIDATION_CHANNEL, message)
            logger.debug(f"Published cache invalidation: agent_slug={slug}, agent_id={agent_id}")
        except Exception as e:
            logger.warning(f"Failed to publish cache invalidation: {e}")

    async def start_invalidation_subscriber(self):
        """
        Start Redis pub/sub subscriber for distributed cache invalidation.

        Call this during application startup to enable cross-pod cache invalidation.
        """
        redis = self._get_redis()
        if not redis:
            logger.warning("Redis not available, distributed cache invalidation disabled")
            return

        try:
            self._pubsub = redis.pubsub()
            await self._pubsub.subscribe(CACHE_INVALIDATION_CHANNEL)
            self._subscriber_task = asyncio.create_task(self._listen_for_invalidations())
            logger.info(f"Started cache invalidation subscriber on pod {self._pod_id}")
        except Exception as e:
            logger.error(f"Failed to start cache invalidation subscriber: {e}")

    async def stop_invalidation_subscriber(self):
        """Stop Redis pub/sub subscriber."""
        if self._subscriber_task:
            self._subscriber_task.cancel()
            try:
                await self._subscriber_task
            except asyncio.CancelledError:
                pass
            self._subscriber_task = None

        if self._pubsub:
            try:
                await self._pubsub.unsubscribe()
                await self._pubsub.aclose()
            except Exception as e:
                logger.warning(f"Error closing pubsub: {e}")
            self._pubsub = None

        logger.info("Stopped cache invalidation subscriber")

    async def _listen_for_invalidations(self):
        """Listen for cache invalidation messages from other pods.

        Uses get_message() polling instead of listen() so that idle-connection
        timeouts (TCP keepalive drops, Redis server timeout, firewall rules) trigger
        a reconnect rather than permanently killing the subscriber.
        """
        _RECONNECT_DELAY = 5  # seconds to wait before re-subscribing after an error

        while True:
            try:
                # Poll every second; get_message returns None when there is nothing to read.
                # ignore_subscribe_messages=True suppresses the confirmation messages that
                # Redis sends when (re)subscribing so we only handle real payloads.
                while True:
                    message = await self._pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if message and message["type"] == "message":
                        try:
                            data = json.loads(message["data"])

                            # Skip messages we published ourselves
                            if data.get("source_pod") == self._pod_id:
                                continue

                            invalidation_type = data.get("type", "agent_cache_invalidation")

                            if invalidation_type == "agents_list_cache_invalidation":
                                tenant_id = data.get("tenant_id")
                                logger.info(
                                    f"Received agents list cache invalidation from pod {data.get('source_pod')}: "
                                    f"tenant_id={tenant_id}"
                                )
                                await self.invalidate_agents_list(
                                    tenant_id=tenant_id,
                                    broadcast=False,
                                )
                            else:
                                agent_slug = data.get("agent_slug")
                                agent_id = data.get("agent_id")
                                logger.info(
                                    f"Received cache invalidation from pod {data.get('source_pod')}: "
                                    f"agent_slug={agent_slug}, agent_id={agent_id}"
                                )
                                await self.invalidate_agent(
                                    slug=agent_slug,
                                    agent_id=agent_id,
                                    broadcast=False,
                                )
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid cache invalidation message: {message['data']}")

                    # Yield to the event loop between polls to avoid busy-waiting
                    await asyncio.sleep(0.01)

            except asyncio.CancelledError:
                logger.debug("Cache invalidation subscriber cancelled")
                raise
            except Exception as e:
                # Connection dropped (TCP timeout, Redis restart, network blip, etc.).
                # Log at WARNING — this is expected on idle connections — then reconnect.
                logger.warning(f"Cache invalidation listener disconnected ({e}); reconnecting in {_RECONNECT_DELAY}s")
                await asyncio.sleep(_RECONNECT_DELAY)
                await self._reconnect_pubsub()

    async def _reconnect_pubsub(self):
        """Re-create the pubsub connection after a disconnect."""
        try:
            if self._pubsub:
                try:
                    await self._pubsub.unsubscribe()
                    await self._pubsub.aclose()
                except Exception:
                    pass
                self._pubsub = None

            redis = self._get_redis()
            if not redis:
                logger.warning("Redis unavailable during pubsub reconnect; will retry on next error")
                return

            self._pubsub = redis.pubsub()
            await self._pubsub.subscribe(CACHE_INVALIDATION_CHANNEL)
            logger.info(f"Re-subscribed to cache invalidation channel on pod {self._pod_id}")
        except Exception as e:
            logger.warning(f"Pubsub reconnect failed: {e}")


# Global cache service instance
_cache_service = None


def get_agent_cache() -> AgentCacheService:
    """Get global agent cache service instance."""
    global _cache_service

    if _cache_service is None:
        _cache_service = AgentCacheService()

    return _cache_service
