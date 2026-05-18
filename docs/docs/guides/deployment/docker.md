---
sidebar_position: 1
---

# Deploy with Docker Compose

Docker Compose is the default way to run Synkora locally and a practical way to run it in smaller self-hosted environments.

## What Compose Gives You

- web app
- API
- PostgreSQL
- Redis
- vector/search services
- workers and scheduler
- ML and scraper services
- observability components

## Basic Flow

```bash
cp api/.env.example api/.env
cp web/.env.example web/.env.local

docker compose up -d
docker compose exec api alembic upgrade head
docker compose exec api python create_super_admin.py
docker compose exec api python seed_platform_config.py
```

## When To Use Compose

- local development
- evaluation environments
- smaller self-hosted deployments
- pre-production integration environments

## Operational Advice

- monitor memory usage closely
- keep environment files explicit and versioned outside git
- use named volumes carefully when resetting environments
