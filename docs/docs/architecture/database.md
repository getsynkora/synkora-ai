---
sidebar_position: 4
---

# Data and Search Architecture

Synkora separates durable product state from retrieval-oriented data. PostgreSQL is the system of record. Vector databases, search engines, Redis, and object storage support specific runtime jobs around retrieval, caching, and files.

## Data Plane Diagram

![Synkora data and search high-level architecture diagram.](/images/docs/architecture/data-hld.svg)

## What Lives Where

| Store | Role in Synkora | Typical Data |
| --- | --- | --- |
| PostgreSQL | System of record | tenants, accounts, agents, conversations, billing, integrations, settings |
| PostgreSQL + `pgvector` | Relational data plus vector similarity | embeddings and vector search tied to relational records |
| Redis | Coordination and ephemeral runtime state | cache entries, pub/sub, rate-limit state, token state, Celery broker data |
| Elasticsearch | Search and analytics support | knowledge/search workloads, session tracing used by Lens-related flows |
| Qdrant / Pinecone | External vector retrieval backends | knowledge-base embeddings when those providers are selected |
| MinIO / S3 | Object storage | uploaded files, avatars, documents, generated assets |

## Database Access Pattern

`api/src/core/database.py` sets up two access paths:

- a **sync SQLAlchemy engine** for sync workloads and legacy paths
- an **async SQLAlchemy engine** for FastAPI request handling

Important implementation details:

- SQLAlchemy 2 style configuration
- Alembic migrations for schema changes
- `asyncpg` for async database connections
- `psycopg2` for sync connections
- `statement_timeout` set to `30s`
- pooled connections in normal environments
- `NullPool` in tests

## Modeling Pattern

Most durable models inherit common mixins from `api/src/models/base.py`:

- `UUIDMixin`
- `TimestampMixin`
- `TenantMixin`
- `SoftDeleteMixin`
- `StatusMixin`

That gives the platform a consistent baseline for:

- UUID primary keys
- audit timestamps
- tenant-scoped records
- soft deletion
- status tracking

## Performance Patterns

The current backend architecture intentionally treats the relational layer as the durable truth and optimizes around that:

- `tenant_id`, `status`, and key lookup columns are indexed
- lazy loading is the default for many relationships
- `selectinload` and `joinedload` are used where relationship data is needed
- async session factories are created lazily so they bind to the correct event loop

## Practical Rule

Use PostgreSQL for truth, consistency, and multi-tenant state.

Use vector databases, search engines, Redis, and object storage as specialized supporting systems for:

- retrieval
- search
- performance
- file handling

That split keeps Synkora from turning the vector layer into the product database.
