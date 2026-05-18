---
sidebar_position: 6
---

# Background Jobs

Synkora moves slow, scheduled, or operationally isolated work out of the API request path and into Celery workers plus dedicated bot-worker processes.

## Core Runtime Pieces

| Component | Source | Responsibility |
| --- | --- | --- |
| Celery app | `api/src/celery_app.py` | Worker configuration, queues, schedules, retry and failure behavior |
| Task modules | `api/src/tasks/*` | Actual job implementations |
| Celery Beat | configured in `celery_app.py` | Periodic job scheduling |
| Bot worker | `api/src/bot_worker` | Long-lived messaging bot execution |

## Current Queue Layout

`api/src/celery_app.py` currently routes work into named queues so one workload does not starve another.

| Queue | Examples of Work |
| --- | --- |
| `default` | general scheduled task dispatch and cleanup work |
| `email` | verification, welcome, password reset, bulk email |
| `notifications` | in-app, Slack, Teams, webhook, WhatsApp notifications |
| `agents` | spawn-agent tasks, webhook processing, LLM batch polling, knowledge compilation, digest generation |
| `billing` | usage analytics flush, credit deduction, reconciliation, subscription expiry, payouts |
| `company_brain` | stream consumption, sync, batching, entity extraction, tier migration |

## Scheduled Work Configured Today

The current beat schedule includes jobs such as:

- scheduled task checks every minute
- execution cleanup at midnight
- usage analytics flush every hour
- daily credit reconciliation
- workspace cleanup every 6 hours
- knowledge wiki compilation daily
- stale webhook cleanup every 15 minutes
- daily digest generation
- pending LLM batch polling every 30 minutes
- audit-log cleanup
- Company Brain stream consumption and sync jobs
- dormant account cleanup
- weekly data-retention cleanup for conversations, messages, and files
- hourly subscription expiry
- monthly creator payout processing

## Reliability Controls

The current worker configuration includes a few important safeguards:

- `task_acks_late=True`
- `task_reject_on_worker_lost=True`
- `worker_prefetch_multiplier=1`
- `worker_max_tasks_per_child=1000`
- hard and soft task time limits

These settings reduce the chance that a crashed worker silently loses important work.

## Failure Tracking

`celery_app.py` also wires in:

- Sentry for worker exceptions
- a Prometheus counter for task failures
- a Redis-backed dead-letter queue at `celery:dlq`

The DLQ stores failure payloads for monitoring and possible replay instead of letting failed jobs disappear.

## Practical Guidance

If you are operating Synkora at scale:

- scale queues independently
- watch task failures, not only API health
- keep messaging bots out of the API process
- treat retries and replay as part of normal operations
