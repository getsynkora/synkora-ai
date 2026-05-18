---
sidebar_position: 6
---

# Webhooks

Webhooks let Synkora push platform events into your external systems.

## Typical Use Cases

- mirror agent activity into internal systems
- trigger downstream workflows
- notify operational tooling
- record billing or usage events externally

## Design Advice

- verify signatures where supported
- make receivers idempotent
- handle retries and out-of-order delivery safely
- log every failed webhook delivery path
