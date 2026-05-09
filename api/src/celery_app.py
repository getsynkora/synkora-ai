"""
Celery application configuration for scheduled tasks
"""

import json
import logging
from datetime import UTC, datetime

import sentry_sdk
from celery import Celery
from celery.schedules import crontab
from celery.signals import task_failure, task_retry
from prometheus_client import Counter
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

from src.config.settings import settings

# Initialize Sentry for Celery workers if configured
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment or settings.app_env,
        integrations=[
            CeleryIntegration(),
            LoggingIntegration(
                level=logging.INFO,
                event_level=logging.ERROR,
            ),
        ],
        traces_sample_rate=1.0 if settings.app_debug else 0.1,
        send_default_pii=False,  # Don't send PII by default
    )
    logging.info("Sentry initialized for Celery workers")

# Create Celery app
celery_app = Celery(
    "synkora",
    broker=settings.celery_broker_url_str,
    backend=settings.celery_result_backend_str,
    include=[
        "src.tasks.scheduled_tasks",
        "src.tasks.database_tasks",
        "src.tasks.notification_tasks",
        "src.tasks.agent_tasks",  # Webhook event processing
        "src.tasks.email_tasks",  # Email sending
        "src.tasks.billing_tasks",  # Credit deduction and reconciliation
        "src.tasks.workspace_tasks",  # Workspace cleanup
        "src.tasks.data_source_tasks",  # Data source ingestion
        "src.tasks.document_tasks",  # Document processing
        "src.tasks.file_tasks",  # File handling
        "src.tasks.load_testing_tasks",  # Load test execution
        "src.tasks.followup_reminder_task",  # Follow-up reminders
        "src.tasks.knowledge_compiler_task",  # Knowledge wiki compilation
        "src.tasks.kb_tasks",  # Knowledge base document processing
        "src.tasks.company_brain_tasks",  # Company brain ingestion and sync
        "src.tasks.digest_tasks",  # Daily digest generation for all data sources
        "src.tasks.a2a_tasks",  # A2A protocol async task execution
        "src.tasks.batch_poll_task",  # LLM batch API polling
        "src.tasks.gdpr_tasks",  # GDPR Article 15 export + Article 17 erasure
        "src.tasks.retention_tasks",  # Data retention policy enforcement
        "src.tasks.payout_tasks",  # Agent subscription expiry and creator payouts
    ],
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour
    task_soft_time_limit=3300,  # 55 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    # K8s reliability: Acknowledge tasks only after completion
    # Ensures tasks are requeued if worker crashes/pod terminates
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Queue routing - default queue must match worker's -Q flag
    task_default_queue="default",
    task_routes={
        # Email tasks to email queue
        "send_email_task": {"queue": "email"},
        "send_verification_email_task": {"queue": "email"},
        "send_welcome_email_task": {"queue": "email"},
        "send_password_reset_email_task": {"queue": "email"},
        "send_bulk_emails_task": {"queue": "email"},
        "send_team_invitation_email_task": {"queue": "email"},
        # Notification tasks to notifications queue
        "send_bulk_notifications_task": {"queue": "notifications"},
        "send_in_app_notification_task": {"queue": "notifications"},
        "send_slack_notification_task": {"queue": "notifications"},
        "send_teams_notification_task": {"queue": "notifications"},
        "send_webhook_notification_task": {"queue": "notifications"},
        "send_whatsapp_notification_task": {"queue": "notifications"},
        "send_task_notification": {"queue": "notifications"},
        # Agent tasks to agents queue
        "execute_spawn_agent_task": {"queue": "agents"},
        "process_webhook_event": {"queue": "agents"},
        # Scheduled task execution goes to default queue so it doesn't block
        # spawn_agent / webhook tasks on the agents queue.
        # tasks.check_scheduled_tasks (beat dispatcher) → default queue.
        "tasks.execute_scheduled_task": {"queue": "default"},
        "tasks.execute_a2a_task": {"queue": "agents"},
        "tasks.poll_llm_batches": {"queue": "agents"},
        # Knowledge compilation to agents queue
        "tasks.compile_knowledge_wikis": {"queue": "agents"},
        "tasks.compile_single_knowledge_wiki": {"queue": "agents"},
        "tasks.embed_wiki_documents": {"queue": "agents"},
        # Digest tasks to agents queue (LLM-heavy)
        "tasks.generate_all_daily_digests": {"queue": "agents"},
        "tasks.generate_data_source_digest": {"queue": "agents"},
        # Billing tasks to billing queue
        "billing.flush_usage_analytics": {"queue": "billing"},
        "billing.deduct_credits_async": {"queue": "billing"},
        "billing.reconcile_credits_daily": {"queue": "billing"},
    },
    beat_schedule={
        # Check for due scheduled tasks every minute
        "check-scheduled-tasks-every-minute": {
            "task": "tasks.check_scheduled_tasks",
            "schedule": 60.0,  # Every 60 seconds
        },
        # Clean up old task executions daily at midnight
        "cleanup-old-executions-daily": {
            "task": "tasks.cleanup_old_executions",
            "schedule": crontab(hour=0, minute=0),
            "args": (30,),  # Keep 30 days of history
        },
        # Flush buffered usage counters from Redis to DB every hour
        "flush-usage-analytics": {
            "task": "billing.flush_usage_analytics",
            "schedule": crontab(minute=0),
        },
        # Daily credit reconciliation at 2 AM
        "reconcile-credits-daily": {
            "task": "billing.reconcile_credits_daily",
            "schedule": crontab(hour=2, minute=0),
        },
        # Clean up expired workspaces every 6 hours
        "cleanup-expired-workspaces": {
            "task": "tasks.cleanup_expired_workspaces",
            "schedule": crontab(minute=0, hour="*/6"),  # Every 6 hours
            "args": (24,),  # 24-hour TTL
        },
        # Compile knowledge wikis daily at 3 AM
        "compile-knowledge-wikis-daily": {
            "task": "tasks.compile_knowledge_wikis",
            "schedule": crontab(hour=3, minute=0),
        },
        # Recover webhook events stuck in 'processing' (worker killed mid-task) every 15 minutes
        "cleanup-stale-webhook-events": {
            "task": "tasks.cleanup_stale_webhook_events",
            "schedule": crontab(minute="*/15"),  # Every 15 minutes
            "args": (30,),  # 30-minute stale threshold
        },
        # Generate daily digests for all active data sources at 11 PM UTC
        "generate-daily-digests": {
            "task": "tasks.generate_all_daily_digests",
            "schedule": crontab(hour=23, minute=0),
        },
        # Poll pending LLM batch jobs every 30 minutes
        "poll-llm-batches": {
            "task": "tasks.poll_llm_batches",
            "schedule": crontab(minute="*/30"),
        },
        # Purge audit logs older than AUDIT_LOG_RETENTION_DAYS (default 365) daily at 1 AM
        "cleanup-audit-logs": {
            "task": "tasks.cleanup_audit_logs",
            "schedule": crontab(hour=1, minute=0),
        },
        # Disable dormant (inactive) accounts every Sunday at 2 AM UTC
        "disable-dormant-accounts-weekly": {
            "task": "tasks.disable_dormant_accounts",
            "schedule": crontab(hour=2, minute=0, day_of_week=0),  # 0 = Sunday
        },
        # Data retention: delete old conversations weekly on Sunday at 3 AM UTC
        "cleanup-old-conversations-weekly": {
            "task": "tasks.cleanup_old_conversations",
            "schedule": crontab(hour=3, minute=0, day_of_week=0),
        },
        # Data retention: delete old/orphaned messages weekly on Sunday at 3:30 AM UTC
        "cleanup-old-messages-weekly": {
            "task": "tasks.cleanup_old_messages",
            "schedule": crontab(hour=3, minute=30, day_of_week=0),
        },
        # Data retention: delete old uploaded files weekly on Sunday at 4 AM UTC
        "cleanup-old-files-weekly": {
            "task": "tasks.cleanup_old_files",
            "schedule": crontab(hour=4, minute=0, day_of_week=0),
        },
        # Expire stale agent access subscriptions every hour
        "expire-agent-subscriptions-hourly": {
            "task": "billing.expire_agent_subscriptions",
            "schedule": crontab(minute=0),
        },
        # Process creator payouts on the 1st of each month at 2 AM UTC
        "process-monthly-creator-payouts": {
            "task": "billing.process_monthly_payouts",
            "schedule": crontab(hour=2, minute=0, day_of_month=1),
        },
    },
)

# Optional: Configure result backend settings
if settings.celery_result_backend:
    import os as _os

    celery_app.conf.update(
        result_expires=3600,  # Results expire after 1 hour
        result_backend_transport_options={
            # Use same env var as get_redis() for consistency
            "master_name": _os.getenv("REDIS_MASTER_NAME", "mymaster"),
            "visibility_timeout": 3600,
        },
    )

# Sentinel requires master_name in broker_transport_options.
# sentinel_kwargs passes the sentinel auth password separately from the Redis
# master password embedded in the sentinel:// URL — both are required when
# the sentinel process itself has requirepass set.
if settings.celery_broker_url_str.startswith("sentinel://"):
    import os as _os

    _sentinel_pwd = _os.getenv("REDIS_SENTINEL_PASSWORD", "")
    celery_app.conf.update(
        broker_transport_options={
            "master_name": _os.getenv("REDIS_MASTER_NAME", "mymaster"),
            "sentinel_kwargs": {"password": _sentinel_pwd},
        },
        result_backend_transport_options={
            "master_name": _os.getenv("REDIS_MASTER_NAME", "mymaster"),
            "sentinel_kwargs": {"password": _sentinel_pwd},
            "visibility_timeout": 3600,
        },
    )


# Prometheus counter for Celery task failures (labelled by task name)
CELERY_TASK_FAILURES = Counter(
    "celery_task_failures_total",
    "Total number of Celery task failures after all retries exhausted",
    ["task_name"],
)

# Global Dead-Letter Queue handlers for failed tasks
DLQ_KEY = "celery:dlq"
DLQ_MAX_ENTRIES = 10000  # Limit DLQ size to prevent unbounded growth


@task_failure.connect
def handle_task_failure(sender, task_id, exception, args, kwargs, traceback, einfo, **kw):
    """
    Global handler for all failed tasks after max retries exhausted.
    Stores failed task info in Redis sorted set for monitoring and replay.
    """
    try:
        from src.config.redis import get_redis

        redis = get_redis()
        if not redis:
            logging.error(f"DLQ: Redis unavailable, cannot store failed task {task_id}")
            return

        task_name = sender.name if sender else "unknown"

        # Increment Prometheus failure counter (safe — labels are deduplicated)
        try:
            CELERY_TASK_FAILURES.labels(task_name=task_name).inc()
        except Exception as _prom_err:
            logging.debug("Prometheus counter update failed: %s", _prom_err)
        failed_at = datetime.now(UTC)

        # Build failure record
        failed_data = {
            "task_id": task_id,
            "task_name": task_name,
            "args": _safe_serialize(args),
            "kwargs": _safe_serialize(kwargs),
            "exception_type": type(exception).__name__,
            "exception_message": str(exception)[:500],
            "traceback": str(einfo)[:2000] if einfo else None,
            "failed_at": failed_at.isoformat(),
        }

        # Store in sorted set (score = timestamp for ordering) and trim atomically
        pipe = redis.pipeline()
        pipe.zadd(DLQ_KEY, {json.dumps(failed_data): failed_at.timestamp()})
        pipe.zremrangebyrank(DLQ_KEY, 0, -(DLQ_MAX_ENTRIES + 1))  # Keep only newest DLQ_MAX_ENTRIES
        pipe.execute()

        logging.warning(f"DLQ: Stored failed task {task_name} (id={task_id}): {type(exception).__name__}")

    except Exception as e:
        # Don't let DLQ failures break task processing
        logging.error(f"DLQ: Error storing failed task {task_id}: {e}")


@task_retry.connect
def handle_task_retry(sender, request, reason, einfo, **kw):
    """Log task retries for monitoring and alerting."""
    task_name = sender.name if sender else "unknown"
    retry_count = request.retries if request else 0

    logging.warning(
        f"Celery task retry: {task_name} (id={request.id if request else 'unknown'}, "
        f"attempt={retry_count + 1}): {reason}"
    )


def _safe_serialize(obj):
    """Safely serialize args/kwargs for storage, handling non-JSON-serializable types."""
    try:
        # Test if it's JSON serializable
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        # Fall back to string representation
        return str(obj)[:1000]
