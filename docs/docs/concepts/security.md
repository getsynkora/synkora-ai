---
sidebar_position: 7
---

# Security

Synkora is built as a platform product, so security is part of the architecture, not a post-processing step.

## Security Areas Covered by the Platform

- authentication and session control
- tenant isolation
- role-based authorization
- encrypted storage for secrets and tokens
- rate limiting
- security headers and CSP
- input sanitization
- token blacklisting and versioning
- SSO support

## Secret Handling

Treat the following as sensitive at all times:

- JWT and encryption secrets
- provider API keys
- OAuth client secrets
- widget identity secrets
- payment provider credentials

## Widget and Extension Security

Public-facing surfaces have their own security models:

- widgets use scoped widget keys and optional `userHash` verification
- the Chrome extension authenticates with PKCE and extension-scoped storage

## Operational Advice

- rotate credentials on a schedule
- scope permissions narrowly
- separate staging and production credentials
- audit which tools can trigger external actions

## Related Pages

- [Authentication](/docs/getting-started/authentication)
- [API Keys](/docs/guides/auth/api-keys)
- [Security and Reliability Architecture](/docs/architecture/security-and-reliability)
