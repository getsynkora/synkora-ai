---
sidebar_position: 7
---

# Rate Limits

Synkora applies rate limiting because it is a multi-tenant platform with public and semi-public surfaces.

## Why It Exists

- protect the API from abuse
- preserve fair tenant behavior
- shield expensive model and tool paths
- protect public surfaces such as widgets and bots

## Client Advice

- back off and retry rather than hot-looping
- distinguish user-facing retries from backend batch workflows
- monitor which surfaces hit limits first
