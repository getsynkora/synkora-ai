---
sidebar_position: 1
---

# API Keys

Synkora supports multiple key types because the platform has multiple trust boundaries.

## Common Key Types

- dashboard/session auth for human users
- agent API keys for agent-specific API access
- widget API keys for website embeds
- provider keys for LLM vendors

## Guidance

- use the narrowest key type available
- never reuse widget keys as backend integration keys
- separate staging and production credentials
- rotate keys on a schedule

## Good Operational Pattern

- one owner for each key
- one purpose per key
- one environment per key

If you cannot tell which system owns a key, the key lifecycle is already too loose.
