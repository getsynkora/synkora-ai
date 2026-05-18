---
sidebar_position: 1
---

# API Overview

Synkora exposes a large API surface because it is a platform, not a single chat endpoint.

## Main API Areas

- agents
- conversations and streaming chat
- knowledge bases and documents
- widgets
- messaging bot integrations
- OAuth and identity flows
- billing and usage
- monitoring and operational endpoints

## Best Starting Point

For exact schemas and live request models, use the OpenAPI docs from a running instance:

```text
http://localhost:5001/docs
```

This documentation focuses on the **shape of the platform** and how to think about the APIs, not on duplicating every generated schema by hand.

## Authentication Patterns

Depending on the surface, calls may use:

- dashboard/session auth
- bearer tokens
- agent API keys
- widget API keys
- OAuth flows

## Streaming

Interactive chat paths are streaming-first. When building API clients, assume incremental delivery is the normal mode for end-user experiences.

## Related Pages

- [Agents API](/docs/api-reference/agents/index)
- [Knowledge Bases API](/docs/api-reference/knowledge-bases/index)
- [Billing and Usage API](/docs/api-reference/billing/usage)
