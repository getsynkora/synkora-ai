---
sidebar_position: 2
---

# Installation

Synkora can be installed in three practical ways:

1. **Interactive installer** for quickest setup
2. **Docker Compose** for explicit local control
3. **Split local development** for hacking on API or web services directly

## Hardware Expectations

Synkora is not a tiny demo stack. A normal local environment includes Redis, PostgreSQL, Qdrant, Elasticsearch, ML services, Playwright-based scraping, Langfuse, and multiple workers.

| | Minimum | Recommended |
|---|---|---|
| RAM | 16 GB | 32 GB |
| CPU | 4 cores | 8+ cores |
| Disk | 40 GB | 100 GB |

If you under-size the machine, Elasticsearch and the ML service are the first places you will feel it.

## Required Software

- Docker Engine 24+
- Docker Compose v2
- `openssl`

Optional for local development:

- Node.js 20+
- pnpm 8+
- Python 3.11+
- `uv`

## Option 1: Installer

Use this when you want the fastest path to a working Synkora environment.

```bash
curl -fsSL https://raw.githubusercontent.com/getsynkora/synkora-ai/main/get.sh | bash
```

## Option 2: Docker Compose

Use this when you want to inspect or control the environment yourself.

```bash
cp api/.env.example api/.env
cp web/.env.example web/.env.local
docker compose up -d
```

Then run migrations and seed platform data:

```bash
docker compose exec api alembic upgrade head
docker compose exec api python create_super_admin.py
docker compose exec api python seed_platform_config.py
```

## Option 3: Local Development

Use this when you are contributing to the repo and want faster iteration on specific services.

Backend:

```bash
cd api
uv sync
cp .env.example .env
alembic upgrade head
uvicorn src.app:app --reload --host 0.0.0.0 --port 5001
```

Frontend:

```bash
cd web
pnpm install
cp .env.example .env.local
pnpm dev
```

## Choosing the Right Path

- Use the **installer** for evaluation or first-time setup
- Use **Docker Compose** for regular local product work
- Use **local development mode** when actively changing backend or frontend code
