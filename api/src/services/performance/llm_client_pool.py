"""
LLM client connection pool.

Pools LLM client instances by provider to avoid connection overhead
when multiple agents use the same provider.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PooledLLMClient:
    """Wrapper for a pooled LLM client."""

    client: Any
    provider: str
    model: str
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    use_count: int = 0

    def mark_used(self):
        """Mark client as used."""
        self.last_used = time.time()
        self.use_count += 1


class LLMClientPool:
    """
    Pool for LLM client instances.

    Maintains client instances per provider to avoid repeated initialization.
    LLM clients are stateless and can be safely shared across requests.

    Features:
    - Caches clients by provider + API key hash
    - Thread-safe operations
    - Automatic cleanup of stale clients
    """

    DEFAULT_MAX_CLIENTS = 20
    DEFAULT_MAX_AGE = 3600  # 1 hour

    def __init__(
        self,
        max_clients: int = DEFAULT_MAX_CLIENTS,
        max_age: int = DEFAULT_MAX_AGE,
    ):
        """
        Initialize the LLM client pool.

        Args:
            max_clients: Maximum number of cached clients
            max_age: Maximum age of a cached client in seconds
        """
        self.max_clients = max_clients
        self.max_age = max_age

        self._clients: dict[str, PooledLLMClient] = {}
        self._lock = threading.RLock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
        }

        logger.info(f"LLM client pool initialized: max_clients={max_clients}, max_age={max_age}s")

    def _get_client_key(self, provider: str, api_key: str, model: str, api_base: str | None = None) -> str:
        """Generate a unique key for a client configuration."""
        # Hash the API key for security
        key_hash = hash(api_key) if api_key else "no_key"
        base_hash = hash(api_base) if api_base else "default"
        return f"{provider}:{key_hash}:{model}:{base_hash}"

    def _cleanup_stale_clients(self):
        """Remove stale clients from the pool."""
        now = time.time()
        stale_keys = []

        for key, client in self._clients.items():
            if now - client.created_at > self.max_age:
                stale_keys.append(key)

        for key in stale_keys:
            del self._clients[key]
            self._stats["evictions"] += 1
            logger.debug(f"Evicted stale LLM client: {key}")

    def _ensure_capacity(self):
        """Ensure pool doesn't exceed max size by evicting least recently used."""
        if len(self._clients) < self.max_clients:
            return

        # Find least recently used client
        lru_key = min(self._clients.keys(), key=lambda k: self._clients[k].last_used)
        del self._clients[lru_key]
        self._stats["evictions"] += 1
        logger.debug(f"Evicted LRU LLM client: {lru_key}")

    def get_client(
        self,
        provider: str,
        api_key: str,
        model: str,
        api_base: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        top_p: float = 1.0,
        additional_params: dict[str, Any] | None = None,
        observability_config: dict[str, Any] | None = None,
    ):
        """
        Get or create an LLM client.

        Args:
            provider: LLM provider name (openai, anthropic, google, litellm)
            api_key: API key for the provider
            model: Model name
            api_base: Optional custom API base URL
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            top_p: Top-p sampling parameter
            additional_params: Additional provider-specific parameters
            observability_config: Observability configuration

        Returns:
            MultiProviderLLMClient instance
        """
        client_key = self._get_client_key(provider, api_key, model, api_base)

        with self._lock:
            # Check for existing client
            if client_key in self._clients:
                pooled = self._clients[client_key]
                now = time.time()

                # Check if still valid
                if now - pooled.created_at <= self.max_age:
                    pooled.mark_used()
                    self._stats["hits"] += 1
                    logger.debug(f"LLM client pool hit for {provider}/{model}")
                    return pooled.client
                else:
                    # Stale, remove it
                    del self._clients[client_key]

            # Create new client
            self._stats["misses"] += 1
            self._cleanup_stale_clients()
            self._ensure_capacity()

            from src.services.agents.config import ModelConfig
            from src.services.agents.llm_client import MultiProviderLLMClient

            config = ModelConfig(
                provider=provider,
                model_name=model,
                api_key=api_key,
                api_base=api_base,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                additional_params=additional_params,
            )

            client = MultiProviderLLMClient(config, observability_config)

            # Cache the client
            self._clients[client_key] = PooledLLMClient(
                client=client,
                provider=provider,
                model=model,
            )

            logger.debug(f"Created new LLM client for {provider}/{model}")
            return client

    def get_stats(self) -> dict[str, Any]:
        """Get pool statistics."""
        with self._lock:
            return {
                **self._stats,
                "active_clients": len(self._clients),
                "max_clients": self.max_clients,
            }

    def evict_by_model(self, provider: str, model: str) -> int:
        """Evict all pool entries for a given provider/model.

        Called after an LLM config update so the next request creates a fresh
        client with the updated settings (temperature, max_tokens, etc.).
        """
        with self._lock:
            keys_to_remove = [
                k for k in self._clients if self._clients[k].provider == provider and self._clients[k].model == model
            ]
            for k in keys_to_remove:
                del self._clients[k]
                self._stats["evictions"] += 1
            if keys_to_remove:
                logger.info(f"Evicted {len(keys_to_remove)} pool entries for {provider}/{model}")
            return len(keys_to_remove)

    def clear(self):
        """Clear all cached clients."""
        with self._lock:
            self._clients.clear()
            logger.info("Cleared LLM client pool")


# Global pool instance
_llm_client_pool: LLMClientPool | None = None
_pool_lock = threading.Lock()


def get_llm_client_pool() -> LLMClientPool:
    """
    Get the global LLM client pool.

    Returns:
        LLMClientPool instance
    """
    global _llm_client_pool

    if _llm_client_pool is None:
        with _pool_lock:
            if _llm_client_pool is None:
                _llm_client_pool = LLMClientPool()

    return _llm_client_pool


def close_llm_client_pool():
    """Close the global LLM client pool."""
    global _llm_client_pool

    with _pool_lock:
        if _llm_client_pool:
            _llm_client_pool.clear()
            _llm_client_pool = None
