---
sidebar_position: 1
---

# Architecture Overview

Synkora is a full-stack monorepo. The same codebase contains the public site, docs, blog, dashboard, API, background workers, and supporting runtime services.

At a high level, the platform splits into four operating planes:

- a **frontend control plane** in `web/`
- an **API and runtime plane** in `api/`
- an **async execution plane** built on Celery and dedicated bot workers
- a **data plane** built around PostgreSQL, Redis, object storage, and retrieval backends

## Production Deployment HLD

![Synkora production deployment high-level architecture diagram.](/images/docs/architecture/production-deployment-hld.svg)

This view is the production-shaped diagram:

- AWS ALB-style ingress from the Helm chart
- horizontally scaled web and API tiers
- Redis as the shared coordination layer
- PgBouncer in front of PostgreSQL for the production Kubernetes path referenced in the repo
- dedicated Celery worker groups plus beat and bot worker
- internal `synkora-ml`, `synkora-scraper`, and `synkora-sandbox` services
- managed-style external services for PostgreSQL, S3-compatible object storage, vector databases, Elasticsearch, Langfuse, and multiple LLM providers

The repo also supports local/self-hosted equivalents for many of these services, but this is the higher-level production topology.

## System Diagram

![Synkora high-level system architecture diagram.](/images/docs/architecture/system-hld.svg)

## Major Runtime Components

| Layer | Implementation | Main Role |
| --- | --- | --- |
| Frontend | Next.js app in `web/` | Dashboard, public site, blog, docs, share pages, agent management UI |
| API | FastAPI app in `api/src/app.py` | Auth, agent APIs, chat flows, integrations, admin and public endpoints |
| Realtime | WebSocket manager in `api/src/core/websocket.py` | Streaming and cross-pod message delivery |
| Background work | Celery app in `api/src/celery_app.py` | Long-running jobs, ingestion, notifications, billing, scheduled work |
| Bot execution | `api/src/bot_worker` | Dedicated long-lived messaging bot workloads |
| System of record | PostgreSQL with `pgvector` | Tenants, users, agents, conversations, billing, configuration |
| Coordination | Redis | Cache, pub/sub, rate limiting, token revocation state, Celery broker |
| Retrieval and search | PostgreSQL `pgvector`, Qdrant, Pinecone, Elasticsearch | Knowledge retrieval and search workloads |
| File storage | MinIO or S3-compatible storage | Uploaded files, binary assets, document storage |
| Supporting services | Langfuse, `synkora-ml`, `synkora-scraper` | Observability, embeddings/reranking, scraping/browser automation |

## Repo Shape

| Path | Purpose |
| --- | --- |
| `web/app` | Next.js routes for auth, dashboard, docs, blog, and public pages |
| `web/components` | Domain UI for agents, chat, widgets, billing, integrations, public site |
| `web/lib` | API client, auth helpers, stores, types, shared utilities |
| `api/src/controllers` | HTTP route handlers |
| `api/src/services` | Business logic and integration orchestration |
| `api/src/models` | SQLAlchemy models |
| `api/src/schemas` | Pydantic request and response schemas |
| `api/src/tasks` | Celery task modules |
| `services/` | Supporting runtime services such as ML and scraping |

## Current Tech Stack

| Area | Current Stack |
| --- | --- |
| Frontend | Next `16.2.6`, React `19`, Tailwind CSS `3.4.14`, Zustand, React Query, Axios, React Hook Form, Zod |
| Backend | Python `>=3.11,<3.13`, FastAPI, Uvicorn, Gunicorn, SQLAlchemy 2, Alembic, LiteLLM |
| Async and messaging | Celery, Redis, Flower, dedicated bot worker services |
| Data | PostgreSQL, `pgvector`, Redis, Elasticsearch, Qdrant, Pinecone |
| Integrations | OpenAI, Anthropic, Google GenAI, FastMCP, Slack, Telegram, Stripe, Firebase, ElevenLabs, SendGrid |
| Observability | Langfuse, Sentry, Prometheus metrics |
| Delivery | Docker Compose, Kubernetes, S3 or MinIO-compatible object storage |

## How The Pieces Fit Together

1. The Next.js app acts as the operator-facing control plane and also serves public product pages, `/blog`, and `/docs`.
2. The FastAPI backend owns authenticated APIs, public APIs, chat runtime, and tenant-aware business logic.
3. Redis coordinates rate limiting, caching, token state, Celery, and distributed WebSocket delivery.
4. PostgreSQL stores the durable product state.
5. Celery and bot workers handle slow or scheduled work outside the request path.
6. Retrieval, storage, and observability services support knowledge-heavy and production workloads.

The rest of the architecture pages break these parts down in more detail.
