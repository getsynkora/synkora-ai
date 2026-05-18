---
sidebar_position: 7
---

# Streaming and Realtime

Synkora’s realtime layer is implemented in `api/src/core/websocket.py`. It supports live chat-style experiences across the dashboard and other realtime surfaces without assuming a single API process.

## What The WebSocket Layer Supports

The base `ConnectionManager` handles:

- multiple WebSocket connections per user
- room-based messaging
- user-targeted messaging
- global broadcast
- per-user, per-tenant, and global connection limits
- room authorization callbacks

## Default Connection Limits

The current defaults are:

- `10` connections per user
- `500` connections per tenant
- `10,000` total connections

These are environment-configurable, but those are the built-in defaults in the code today.

## Distributed Delivery Across Pods

`DistributedConnectionManager` extends the base connection manager and uses Redis pub/sub for cross-pod delivery.

Current channel layout:

- `ws:broadcast:all`
- `ws:broadcast:user:*`
- `ws:broadcast:room:*`

When a message is sent:

1. it is delivered to local connections
2. it is published to Redis
3. other pods receive it and fan it out to their own local connections

Each message includes `source_pod` so the origin pod does not echo the message back to itself.

## Operational Behavior

The distributed subscriber is started in `api/src/app.py` during application startup.

Implementation details that matter in production:

- pub/sub uses a dedicated Redis connection with no socket timeout
- the listener reconnects with exponential backoff
- room and user patterns are subscribed with `psubscribe`
- if Redis pub/sub cannot start, the manager falls back to local-only mode

## Where This Matters

This architecture is what lets Synkora support interactive surfaces such as:

- dashboard chat
- widget and embedded chat experiences
- public-facing agent sessions
- operator views that expect live state

Streaming is not just a UI improvement here. It is part of the platform runtime design.
