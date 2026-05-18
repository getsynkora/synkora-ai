---
sidebar_position: 1
---

# Quick Start

The fastest way to get Synkora running is the interactive installer. It handles prerequisite checks, environment generation, service startup, migrations, and initial seeding.

## Recommended Path

```bash
curl -fsSL https://raw.githubusercontent.com/getsynkora/synkora-ai/main/get.sh | bash
```

By default, this installs into `~/synkora-ai`.

To choose a custom directory:

```bash
curl -fsSL https://raw.githubusercontent.com/getsynkora/synkora-ai/main/get.sh | \
  SYNKORA_INSTALL_DIR=~/my-synkora bash
```

For non-interactive installs:

```bash
curl -fsSL https://raw.githubusercontent.com/getsynkora/synkora-ai/main/get.sh | \
  SYNKORA_ADMIN_EMAIL=admin@example.com \
  SYNKORA_ADMIN_PASSWORD=change-me-now \
  SYNKORA_LLM_PROVIDER=openai \
  SYNKORA_LLM_API_KEY=sk-... \
  bash -s -- --non-interactive
```

## What the Installer Does

1. Checks machine resources and port conflicts
2. Verifies Docker, Docker Compose, Node.js, pnpm, and `openssl`
3. Generates `.env` files and secrets
4. Starts the full Docker stack
5. Runs migrations and seeds platform data
6. Creates the initial admin user

## Manual Docker Compose Setup

If you prefer to bring the stack up yourself:

```bash
cp api/.env.example api/.env
cp web/.env.example web/.env.local

docker compose up -d

docker compose exec api alembic upgrade head
docker compose exec api python create_super_admin.py
docker compose exec api python seed_platform_config.py
```

## Default Local URLs

- Web app: `http://localhost:3005`
- API: `http://localhost:5001`
- OpenAPI docs: `http://localhost:5001/docs`
- Langfuse: `http://localhost:3001`
- MinIO console: `http://localhost:9001`

## What To Do Next

- [Installation](/docs/getting-started/installation)
- [Configuration](/docs/getting-started/configuration)
- [Create Your First Agent](/docs/getting-started/first-agent)
