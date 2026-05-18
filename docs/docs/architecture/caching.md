---
sidebar_position: 5
---

# Caching and Coordination

Redis in Synkora is both a cache and a coordination layer. It is used for agent data caching, cross-pod messaging, rate limiting, auth state, and Celery.

## Redis Roles In The Current Stack

- agent configuration cache
- knowledge-base and context-file cache
- agent list cache
- distributed cache invalidation via pub/sub
- distributed WebSocket delivery
- rate limiting
- token blacklist and token-version state
- Celery broker and optional result backend

## Agent Cache Behavior

`api/src/services/cache/agent_cache_service.py` is the clearest example of how Redis is used as a product-level cache.

It currently caches:

- agent configs
- agent tools
- attached knowledge bases
- context files
- paginated agent lists

Key implementation details:

- agent config keys are tenant-scoped to avoid cross-tenant cache hits
- default TTL is `300` seconds
- paginated agent list cache uses a shorter `60` second TTL
- invalidations are broadcast on `cache:invalidation:agent`
- each pod ignores invalidation messages that it published itself

## Distributed Cache Invalidation

`app.py` starts the cache invalidation subscriber during API startup. That matters when multiple API pods are running.

The flow is:

1. One pod updates agent state.
2. That pod invalidates its Redis cache keys.
3. It publishes an invalidation message.
4. Other pods receive the message and invalidate their own cached copies.

This keeps cached agent state from drifting across pods.

## Coordination, Not Just Speed

Redis is also used outside classic caching:

- `auth_middleware.py` checks token blacklist and token version through Redis
- `core/websocket.py` uses Redis pub/sub for cross-pod realtime delivery
- `celery_app.py` uses Redis as broker and optional result backend

So Redis is part of the control plane, not just a performance optimization.

## Design Rule

Redis improves latency and coordination, but it is not the durable source of truth. Durable state still belongs in PostgreSQL and object storage.
