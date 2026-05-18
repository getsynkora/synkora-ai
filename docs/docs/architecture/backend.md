---
sidebar_position: 2
---

# Backend Architecture

The backend lives in `api/` and is built as a FastAPI application with async request handling, tenant-aware auth, Redis-backed coordination, and Celery workers for off-path execution.

## Backend Flow Diagram

![Synkora backend high-level architecture diagram.](/images/docs/architecture/backend-hld.svg)

## Main Entry Points

| File | Responsibility |
| --- | --- |
| `api/src/app.py` | Builds the FastAPI app, applies middleware, manages startup and shutdown lifecycle |
| `api/src/router_registry.py` | Registers routers declaratively instead of keeping a long list of imports in `app.py` |
| `api/src/celery_app.py` | Configures queues, beat schedules, worker reliability, Sentry, and DLQ behavior |

## Directory Layout

| Path | Responsibility |
| --- | --- |
| `api/src/controllers` | HTTP boundaries and route handlers |
| `api/src/controllers/agents` | Agent runtime, chat, tools, outputs, autonomous mode, lens, webhooks, compute |
| `api/src/controllers/console` | Console and admin-style routes, including auth and SSO flows |
| `api/src/controllers/oauth` | OAuth provider flows |
| `api/src/controllers/service_api` | Service-oriented APIs |
| `api/src/controllers/web` | Public web-facing API routes |
| `api/src/services` | Business logic and orchestration across domains |
| `api/src/models` | SQLAlchemy ORM models |
| `api/src/schemas` | Pydantic schemas |
| `api/src/middleware` | Security headers, CORS, rate limiting, auth helpers |
| `api/src/core` | Database setup, WebSocket infrastructure, error handling, model provider plumbing |
| `api/src/tasks` | Background job implementations |
| `api/src/bot_worker` | Dedicated worker process for long-lived bot workloads |

## Request Lifecycle

Most backend requests follow this path:

1. `app.py` applies request-size limits, security headers, dynamic CORS, and rate limiting.
2. Auth dependencies decode the JWT once per request, then check token revocation and token version in Redis.
3. Tenant and role context are derived from the token for tenant-aware routes.
4. Controllers validate input and shape the HTTP response.
5. Services run the business logic.
6. Models and database sessions handle durable state.
7. Long-running work is pushed to Celery instead of blocking the request.

That is the default shape for the backend even though individual domains add their own provider calls or async jobs on top of it.

## Runtime Behavior On Startup

The API lifespan in `api/src/app.py` does more than start the web server:

- pre-warms the async PostgreSQL connection pool
- clears stale Redis conversation locks left by previous processes
- initializes encryption for sensitive values
- starts the Redis subscriber for distributed WebSocket delivery
- starts the Redis subscriber for distributed cache invalidation
- configures WebSocket room authorization

On shutdown it stops those subscribers cleanly so Kubernetes-style restarts are safer.

## Backend Service Domains

The backend is organized by business capability rather than by one large generic service layer. Current service areas include:

- agents, chat, outputs, and autonomous workflows
- knowledge bases, knowledge autopilot, and company brain ingestion
- custom tools, MCP, webhooks, and compute
- billing, subscriptions, roles, permissions, and teams
- OAuth, SSO, Slack, Telegram, WhatsApp, and other integrations
- storage, email, search, observability, and performance tooling

This structure is visible in `api/src/services/*`.

## Database Access Model

The backend uses two database modes:

- **async SQLAlchemy + asyncpg** for FastAPI request paths
- **sync SQLAlchemy + psycopg2** for sync code paths and some worker use cases

`api/src/core/database.py` also creates fresh async session factories for Celery tasks when a new event loop is required.

## Reliability and Security Patterns

The current backend includes:

- Redis-backed distributed rate limiting
- token blacklisting and token version checks
- per-request tenant resolution
- request body size limits
- Redis-backed distributed WebSocket delivery
- Redis-backed cross-pod cache invalidation
- Celery dead-letter queue tracking in Redis
- Prometheus counters for task failures

## Current Backend Stack

| Area | Current Stack |
| --- | --- |
| Language | Python `>=3.11,<3.13` |
| Web framework | FastAPI |
| Servers | Uvicorn, Gunicorn |
| ORM | SQLAlchemy 2 |
| Migrations | Alembic |
| Validation | Pydantic v2 and `pydantic-settings` |
| Queueing | Celery, Redis, Flower |
| LLM orchestration | LiteLLM, OpenAI, Anthropic, Google GenAI |
| Realtime | FastAPI WebSockets + Redis pub/sub |
| Observability | Langfuse, Sentry, Prometheus |

If you need the data layer details next, continue to [Database Architecture](/docs/architecture/database).
