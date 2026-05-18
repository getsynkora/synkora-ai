---
sidebar_position: 8
---

# Multi-Tenant Architecture

Multi-tenancy in Synkora is enforced in the data model, the auth layer, cache keys, and realtime limits. It is not only a UI grouping concept.

## Data Model Enforcement

`api/src/models/base.py` defines `TenantMixin`, which adds an indexed `tenant_id` column to tenant-scoped models.

That pattern is used across many platform records, including areas such as:

- agent-related records
- human contacts
- MCP servers
- knowledge and wiki records
- integration and security records

## Auth And Request Context

`api/src/middleware/auth_middleware.py` extracts tenant context from the JWT payload after the request passes token validation.

The current auth flow does this:

1. extract bearer token
2. decode JWT
3. check Redis-backed token blacklist and token version
4. load the account from the database
5. resolve `tenant_id` and role for downstream dependencies

That means tenant-scoped routes are tied to validated auth state, not just to a request parameter.

## Where Tenant Context Shows Up Operationally

Tenant isolation affects more than database queries:

- cache keys include tenant context where it matters, such as agent config caching
- WebSocket connection counts are tracked per tenant
- room authorization receives `tenant_id`
- billing and subscription events can be attributed to the correct workspace
- SSO and enterprise identity flows are tenant-scoped

## Why The Pattern Matters

Synkora supports many workspaces from one platform runtime. To do that safely, tenant boundaries have to exist in:

- persistence
- auth
- caching
- realtime delivery
- billing and integrations

That is why multi-tenancy is an architecture concern here, not just a dashboard feature.
