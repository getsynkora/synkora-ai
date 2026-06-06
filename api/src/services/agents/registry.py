"""
Agent runtime registry for managing in-process agent instances.

The registry is intentionally process-local. Redis synchronization mirrors
runtime presence metadata per pod, but executable agent instances remain local
to the worker that constructed them.
"""

import asyncio
import logging
import os
from collections import OrderedDict
from typing import Any

from src.services.agents.base_agent import BaseAgent
from src.services.agents.config import AgentConfig

logger = logging.getLogger(__name__)

DEFAULT_RUNTIME_ID = "__default__"


def _resolve_registry_capacity() -> int:
    """Resolve the bounded runtime-cache size."""
    raw = os.getenv("AGENT_REGISTRY_MAX_AGENTS", "256")
    try:
        capacity = int(raw)
    except ValueError:
        logger.warning("Invalid AGENT_REGISTRY_MAX_AGENTS '%s', using 256", raw)
        return 256
    return max(1, capacity)


def _get_redis_registry():
    """Lazy import to avoid circular dependencies."""
    try:
        from src.services.agents.redis_registry import get_redis_registry

        return get_redis_registry()
    except Exception as e:
        logger.warning(f"Redis registry not available: {e}")
        return None


class AgentRegistry:
    """
    Registry for managing agent instances.

    Provides a centralized location for agent registration, discovery,
    and lifecycle management across the application.

    Keys are ``(tenant_id, agent_name)`` tuples so that agents with the
    same name belonging to different tenants never collide in the
    in-memory store.
    """

    def __init__(self, max_agents: int | None = None):
        """Initialize the agent registry."""
        self.max_agents = max_agents or _resolve_registry_capacity()
        # Key: (tenant_id, agent_name, runtime_id)
        self._agents: OrderedDict[tuple[str, str, str], BaseAgent] = OrderedDict()
        self._configs: OrderedDict[tuple[str, str, str], AgentConfig] = OrderedDict()
        logger.info("Agent registry initialized (max_agents=%s)", self.max_agents)

    @staticmethod
    def _normalize_runtime_id(runtime_id: str | None) -> str:
        return runtime_id or DEFAULT_RUNTIME_ID

    @classmethod
    def _key(cls, tenant_id: str, agent_name: str, runtime_id: str | None = None) -> tuple[str, str, str]:
        """Build a registry key from tenant_id, agent_name, and runtime_id."""
        return (str(tenant_id), agent_name, cls._normalize_runtime_id(runtime_id))

    def _matching_keys(self, agent_name: str, tenant_id: str) -> list[tuple[str, str, str]]:
        tenant = str(tenant_id)
        return [key for key in self._agents if key[0] == tenant and key[1] == agent_name]

    def _touch(self, key: tuple[str, str, str]) -> None:
        self._agents.move_to_end(key)
        self._configs.move_to_end(key)

    def _evict_lru_if_needed(self) -> None:
        while len(self._agents) > self.max_agents:
            key, _agent = self._agents.popitem(last=False)
            self._configs.pop(key, None)
            tenant_id, agent_name, runtime_id = key
            redis_registry = _get_redis_registry()
            if redis_registry:
                try:
                    loop = asyncio.get_running_loop()
                    loop.run_in_executor(
                        None,
                        lambda r=redis_registry, t=tenant_id, n=agent_name, ri=runtime_id: r.unregister_runtime(
                            tenant_id=t, agent_name=n, runtime_id=ri
                        ),
                    )
                except RuntimeError:
                    # No running event loop (e.g. sync test context) — call directly.
                    try:
                        redis_registry.unregister_runtime(tenant_id=tenant_id, agent_name=agent_name, runtime_id=runtime_id)
                    except Exception as exc:
                        logger.warning("Failed to unregister evicted runtime from Redis: %s", exc)
            logger.info(
                "Evicted least-recently-used agent runtime '%s' (tenant=%s, runtime=%s)",
                agent_name,
                tenant_id,
                runtime_id,
            )

    def register(self, agent: BaseAgent, tenant_id: str = "", runtime_id: str | None = None) -> None:
        """
        Register an agent instance.

        Args:
            agent: Agent instance to register
            tenant_id: Tenant identifier (scopes the registry key)

        Raises:
            ValueError: If agent with same name already exists for this tenant
        """
        normalized_runtime_id = self._normalize_runtime_id(runtime_id)
        key = self._key(tenant_id, agent.config.name, normalized_runtime_id)
        if key in self._agents:
            raise ValueError(
                f"Agent '{agent.config.name}' is already registered for tenant '{tenant_id}' runtime '{normalized_runtime_id}'"
            )

        self._agents[key] = agent
        self._configs[key] = agent.config
        self._touch(key)
        self._evict_lru_if_needed()

        # Sync runtime presence metadata to Redis for cross-pod visibility.
        redis_registry = _get_redis_registry()
        if redis_registry:
            try:
                config_dict = {
                    "name": agent.config.name,
                    "description": agent.config.description,
                    "system_prompt": agent.config.system_prompt,
                }
                redis_registry.register_runtime(
                    tenant_id=str(tenant_id),
                    agent_name=agent.config.name,
                    runtime_id=normalized_runtime_id,
                    config=config_dict,
                    metadata={"type": agent.__class__.__name__},
                )
            except Exception as e:
                logger.warning(f"Failed to sync agent to Redis: {e}")

        logger.info(
            "Registered agent runtime: %s (tenant=%s, runtime=%s)",
            agent.config.name,
            tenant_id,
            normalized_runtime_id,
        )

    def unregister(self, agent_name: str, tenant_id: str = "", runtime_id: str | None = None) -> None:
        """
        Unregister one runtime or all runtimes for an agent/tenant.

        Args:
            agent_name: Name of the agent to unregister
            tenant_id: Tenant identifier

        Raises:
            KeyError: If agent not found
        """
        if runtime_id is None:
            keys_to_remove = self._matching_keys(agent_name, tenant_id)
        else:
            key = self._key(tenant_id, agent_name, runtime_id)
            keys_to_remove = [key] if key in self._agents else []

        if not keys_to_remove:
            raise KeyError(f"Agent '{agent_name}' not found in registry for tenant '{tenant_id}'")

        redis_registry = _get_redis_registry()

        for key in keys_to_remove:
            _, _, removed_runtime_id = key
            del self._agents[key]
            del self._configs[key]
            if redis_registry:
                try:
                    redis_registry.unregister_runtime(
                        tenant_id=str(tenant_id),
                        agent_name=agent_name,
                        runtime_id=removed_runtime_id,
                    )
                except Exception as exc:
                    logger.warning("Failed to unregister agent runtime from Redis: %s", exc)

        logger.info(
            "Unregistered agent runtimes: %s (tenant=%s, count=%s)",
            agent_name,
            tenant_id,
            len(keys_to_remove),
        )

    def get(self, agent_name: str, tenant_id: str = "", runtime_id: str | None = None) -> BaseAgent | None:
        """
        Get an agent runtime by name scoped to a tenant.

        Args:
            agent_name: Name of the agent
            tenant_id: Tenant identifier

        Returns:
            Agent instance or None if not found
        """
        key = self._key(tenant_id, agent_name, runtime_id)
        agent = self._agents.get(key)
        if agent:
            self._touch(key)
        return agent

    def get_config(self, agent_name: str, tenant_id: str = "", runtime_id: str | None = None) -> AgentConfig | None:
        """
        Get agent configuration by name scoped to a tenant.

        Args:
            agent_name: Name of the agent
            tenant_id: Tenant identifier

        Returns:
            Agent configuration or None if not found
        """
        key = self._key(tenant_id, agent_name, runtime_id)
        config = self._configs.get(key)
        if config:
            self._touch(key)
        return config

    def contains(self, agent_name: str, tenant_id: str = "", runtime_id: str | None = None) -> bool:
        """Check if any runtime, or a specific runtime, is registered for a tenant."""
        if runtime_id is None:
            return any(key[0] == str(tenant_id) and key[1] == agent_name for key in self._agents)
        return self._key(tenant_id, agent_name, runtime_id) in self._agents

    def list_agents(self) -> list[str]:
        """
        List all registered agent names (across all tenants).

        Returns:
            List of agent names
        """
        return sorted({name for (_tid, name, _rid) in self._agents.keys()})

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """
        Get statistics for all registered agents.

        Returns:
            Dictionary mapping agent names to their statistics
        """
        result: dict[str, dict[str, Any]] = {}
        for (tenant_id, name, runtime_id), agent in self._agents.items():
            if tenant_id:
                label = f"{tenant_id}:{name}" if runtime_id == DEFAULT_RUNTIME_ID else f"{tenant_id}:{name}:{runtime_id}"
            else:
                label = name if runtime_id == DEFAULT_RUNTIME_ID else f"{name}:{runtime_id}"
            result[label] = agent.get_stats()
        return result

    def reset_all(self) -> None:
        """Reset all registered agents."""
        for agent in self._agents.values():
            agent.reset()
        logger.info("Reset all agents in registry")

    def clear(self) -> None:
        """Clear all agents from registry."""
        redis_registry = _get_redis_registry()
        if redis_registry:
            for tenant_id, agent_name, runtime_id in list(self._agents.keys()):
                try:
                    redis_registry.unregister_runtime(
                        tenant_id=tenant_id,
                        agent_name=agent_name,
                        runtime_id=runtime_id,
                    )
                except Exception as exc:
                    logger.warning("Failed to unregister agent runtime during clear: %s", exc)
        self._agents.clear()
        self._configs.clear()
        logger.info("Cleared agent registry")

    def __len__(self) -> int:
        """Get number of registered agents."""
        return len(self._agents)

    def __contains__(self, agent_name: str) -> bool:
        """
        Backward-compatible __contains__ check without tenant scope.

        Prefer ``registry.contains(agent_name, tenant_id)`` for accurate
        tenant-scoped lookups.
        """
        return any(name == agent_name for (_tid, name, _rid) in self._agents)

    def __repr__(self) -> str:
        """String representation."""
        return f"<AgentRegistry agents={len(self._agents)} max_agents={self.max_agents}>"


# Global registry instance
_global_registry: AgentRegistry | None = None


def get_registry() -> AgentRegistry:
    """
    Get the global agent registry instance.

    Returns:
        Global agent registry
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = AgentRegistry()
    return _global_registry
