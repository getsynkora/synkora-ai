---
sidebar_position: 3
---

# Configuration

Synkora configuration is split by service. The most important files are:

- `api/.env`
- `web/.env.local`
- `docker-compose.yml`

## Backend Configuration

Start from:

```bash
cp api/.env.example api/.env
```

The backend configuration covers:

- database and Redis connectivity
- JWT and encryption secrets
- storage provider configuration
- vector/search providers
- LLM provider keys
- OAuth and SSO configuration
- billing and payment providers
- observability integrations

## Frontend Configuration

Start from:

```bash
cp web/.env.example web/.env.local
```

Typical frontend values:

- `NEXT_PUBLIC_API_URL`
- `NEXT_PUBLIC_APP_URL`
- optional analytics or Sentry settings

## Minimum Configuration For Local Development

For a working local environment, the practical minimum is:

- valid backend secrets
- a reachable PostgreSQL and Redis setup
- one LLM provider key

Everything else can be added incrementally.

## Recommended Configuration Layers

### Core platform

- app environment
- URLs and ports
- secrets
- database
- Redis

### AI providers

- OpenAI
- Anthropic
- Google
- any additional LiteLLM-backed providers you use

### Retrieval and storage

- PostgreSQL + pgvector
- Qdrant / Pinecone / Elasticsearch if used
- S3 / MinIO object storage

### Integrations

- OAuth apps
- Slack / WhatsApp / Teams / Telegram credentials
- widget identity settings
- Okta SSO

### Observability and billing

- Langfuse
- Sentry
- Stripe or Paddle, depending on your deployment

## Configuration Strategy

- Keep secrets out of version control
- Prefer one environment file per service
- Treat payment, OAuth, and SSO config as environment-specific
- Start with the smallest set of providers you actually need

## Related Pages

- [Authentication](/docs/getting-started/authentication)
- [Production Deployment](/docs/guides/deployment/production)
