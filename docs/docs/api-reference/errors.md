---
sidebar_position: 8
---

# Errors

API errors in Synkora usually come from one of five categories:

- authentication failures
- authorization or tenant-boundary failures
- validation errors
- integration/provider failures
- platform/runtime failures

## How To Handle Them

- log the request context
- separate user-facing messages from operator/debug detail
- retry only where the failure mode is clearly transient
- treat auth and permission failures as configuration issues first, not transport errors
