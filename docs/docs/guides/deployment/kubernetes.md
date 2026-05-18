---
sidebar_position: 2
---

# Deploy with Kubernetes

Use Kubernetes when you need Synkora as a durable multi-service platform instead of a single-box deployment.

## Best Fit

Kubernetes is the right choice when you need:

- horizontal scaling
- managed secrets and config
- controlled rollouts
- production-grade health checks and restarts
- workload separation across web, API, workers, and supporting services

## Repo Assets

The repo includes Kubernetes resources and Helm charts under:

- `helm/`
- `k8s/`

## Rollout Model

Treat these as separate workload groups:

- web frontend
- API
- Celery workers
- scheduler
- bot workers
- supporting infrastructure

## Advice

- externalize managed services where possible
- isolate resource-heavy services like search and ML
- validate Redis and database connectivity in readiness checks
- do not scale chat/API traffic without also reviewing workers and retrieval backends
