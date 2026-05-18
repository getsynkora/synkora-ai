---
sidebar_position: 3
---

# Production Deployment

Production Synkora is a platform rollout, not just an app deployment.

## Core Production Concerns

- secret management
- stable persistent storage
- database backup and recovery
- Redis durability strategy
- observability and alerting
- worker isolation
- payment and billing correctness
- tenant isolation and auth posture

## Recommended Production Posture

- managed PostgreSQL where possible
- managed Redis where possible
- S3-compatible object storage
- external TLS termination
- Langfuse and Sentry configured before heavy usage

## Before Go-Live

- validate backup and restore paths
- confirm LLM provider key ownership
- review widget and API key exposure
- test billing and usage tracking
- test retries, failed jobs, and worker restart behavior

## Surfaces To Review Explicitly

- widget authentication
- messaging bot credentials
- OAuth redirects
- extension auth flow
- tenant and role boundaries
