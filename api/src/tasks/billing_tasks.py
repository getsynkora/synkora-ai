"""
Billing-related Celery tasks for async credit deduction.

Handles asynchronous credit deduction and usage tracking without
impacting real-time chat performance.
"""

import logging
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

from src.core.database import get_db
from src.models.credit_transaction import ActionType
from src.services.billing.credit_service import CreditService

logger = logging.getLogger(__name__)


class BillingTaskError(Exception):
    """Base exception for billing task errors."""

    pass


class RetryableBillingError(BillingTaskError):
    """Error that should trigger a retry."""

    pass


class PermanentBillingError(BillingTaskError):
    """Error that should not be retried."""

    pass


@shared_task(
    name="billing.deduct_credits_async",
    bind=True,
    max_retries=3,  # Retry up to 3 times for transient failures
    default_retry_delay=60,  # 60 seconds between retries
    retry_backoff=True,  # Exponential backoff
    retry_backoff_max=300,  # Max 5 minutes between retries
    retry_jitter=True,  # Add randomness to prevent thundering herd
    time_limit=30,  # 30 second timeout
    soft_time_limit=25,
    queue="billing",  # Dedicated billing queue
    acks_late=True,  # Only acknowledge after successful processing
)
def deduct_credits_async(self, tenant_id: str, user_id: str | None, agent_id: str, action_type: str, metadata: dict):
    """
    Asynchronously deduct credits after an action is completed.

    This task runs in the background and does not block the chat response.
    Uses idempotency to prevent duplicate deductions.

    Args:
        tenant_id: Tenant UUID as string
        user_id: User UUID as string (optional)
        agent_id: Agent UUID as string
        action_type: Action type string (e.g., "CHAT_MESSAGE_GPT4")
        metadata: Additional metadata including conversation_id, message_id, etc.
    """
    import asyncio

    async def _deduct_credits():
        from src.core.database import create_celery_async_session

        # Convert string UUIDs back to UUID objects
        tenant_uuid = UUID(tenant_id)
        agent_uuid = UUID(agent_id)
        user_uuid = UUID(user_id) if user_id else None

        # Convert action_type string to enum
        try:
            action_enum = ActionType[action_type]
        except KeyError:
            # Invalid action type is a permanent error - don't retry
            logger.error(
                f"Invalid action type: '{action_type}' (type: {type(action_type)}). "
                f"Available types: {[e.name for e in ActionType]}"
            )
            # Store failed deduction for reconciliation
            _store_failed_deduction(
                tenant_id=tenant_id,
                user_id=user_id,
                agent_id=agent_id,
                action_type=action_type,
                metadata=metadata,
                error=f"Invalid action type: {action_type}",
                task_id=self.request.id,
            )
            return None

        async_session_factory = create_celery_async_session()
        async with async_session_factory() as db:
            try:
                # Initialize credit service
                credit_service = CreditService(db)

                # Deduct credits with idempotency check
                transaction = await credit_service.deduct_credits_idempotent(
                    tenant_id=tenant_uuid,
                    user_id=user_uuid,
                    agent_id=agent_uuid,
                    action_type=action_enum,
                    metadata=metadata,
                )

                if transaction:
                    logger.info(
                        f"✅ Credits deducted asynchronously: "
                        f"tenant={tenant_id}, action={action_type}, "
                        f"amount={abs(transaction.amount)}"
                    )
                else:
                    logger.info(
                        f"ℹ️ Credit deduction skipped (already processed): tenant={tenant_id}, action={action_type}"
                    )

                return transaction
            except Exception:
                await db.rollback()
                raise

    try:
        asyncio.run(_deduct_credits())
    except Exception as e:
        error_msg = str(e)
        logger.error(
            f"❌ Failed to deduct credits asynchronously: {e}",
            exc_info=True,
            extra={
                "tenant_id": tenant_id,
                "agent_id": agent_id,
                "action_type": action_type,
                "metadata": metadata,
                "task_id": self.request.id,
                "retry_count": self.request.retries,
            },
        )

        # Determine if this is a retryable error
        is_retryable = _is_retryable_error(e)

        if is_retryable and self.request.retries < self.max_retries:
            # Retry with exponential backoff
            try:
                raise self.retry(exc=e)
            except MaxRetriesExceededError:
                # Max retries exceeded - store for reconciliation
                _store_failed_deduction(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    agent_id=agent_id,
                    action_type=action_type,
                    metadata=metadata,
                    error=f"Max retries exceeded: {error_msg}",
                    task_id=self.request.id,
                )
        else:
            # Permanent error or max retries - store for reconciliation
            _store_failed_deduction(
                tenant_id=tenant_id,
                user_id=user_id,
                agent_id=agent_id,
                action_type=action_type,
                metadata=metadata,
                error=error_msg,
                task_id=self.request.id,
            )


def _is_retryable_error(error: Exception) -> bool:
    """Determine if an error should trigger a retry."""
    error_str = str(error).lower()

    # Database connection errors are retryable
    retryable_patterns = [
        "connection",
        "timeout",
        "temporarily unavailable",
        "too many connections",
        "deadlock",
        "lock wait timeout",
        "could not connect",
        "connection refused",
        "connection reset",
    ]

    # Permanent errors should not be retried
    permanent_patterns = [
        "invalid",
        "not found",
        "does not exist",
        "permission denied",
        "insufficient credits",
        "duplicate key",
    ]

    for pattern in permanent_patterns:
        if pattern in error_str:
            return False

    for pattern in retryable_patterns:
        if pattern in error_str:
            return True

    # Default to retrying for unknown errors
    return True


def _store_failed_deduction(
    tenant_id: str,
    user_id: str | None,
    agent_id: str,
    action_type: str,
    metadata: dict,
    error: str,
    task_id: str,
) -> None:
    """Store failed deduction for later reconciliation."""
    try:
        from src.config.redis import get_redis

        redis = get_redis()
        if redis:
            # Store failed deduction in Redis sorted set for reconciliation
            failed_data = {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "agent_id": agent_id,
                "action_type": action_type,
                "metadata": metadata,
                "error": error[:500],  # Truncate error message
                "task_id": task_id,
                "failed_at": datetime.now(UTC).isoformat(),
            }
            import json

            redis.zadd(
                "billing:failed_deductions",
                {json.dumps(failed_data): datetime.now(UTC).timestamp()},
            )
            logger.info(f"📝 Stored failed deduction for reconciliation: task_id={task_id}")
    except Exception as e:
        logger.error(f"Failed to store failed deduction in Redis: {e}")


@shared_task(
    name="billing.reconcile_credits_daily",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    time_limit=600,  # 10 minute timeout
    soft_time_limit=540,
    queue="billing",
)
def reconcile_credits_daily(self):
    """
    Daily reconciliation job to find and fix credit discrepancies.

    Compares messages sent vs. credit transactions to identify:
    - Messages without credit deductions
    - Duplicate credit deductions
    - Failed deductions stored in Redis
    - Credit balance discrepancies
    """
    db = None
    reconciliation_report = {
        "started_at": datetime.now(UTC).isoformat(),
        "failed_deductions_processed": 0,
        "failed_deductions_retried": 0,
        "failed_deductions_expired": 0,
        "discrepancies_found": 0,
        "errors": [],
    }

    try:
        db = next(get_db())

        # 1. Process failed deductions from Redis
        failed_processed = _process_failed_deductions(db)
        reconciliation_report["failed_deductions_processed"] = failed_processed["processed"]
        reconciliation_report["failed_deductions_retried"] = failed_processed["retried"]
        reconciliation_report["failed_deductions_expired"] = failed_processed["expired"]

        # 2. Find messages from last 24 hours without credit transactions
        discrepancies = _find_missing_deductions(db)
        reconciliation_report["discrepancies_found"] = len(discrepancies)

        # 3. Retry missing deductions
        for discrepancy in discrepancies:
            try:
                deduct_credits_async.delay(
                    tenant_id=str(discrepancy["tenant_id"]),
                    user_id=str(discrepancy["user_id"]) if discrepancy.get("user_id") else None,
                    agent_id=str(discrepancy["agent_id"]),
                    action_type=discrepancy["action_type"],
                    metadata={
                        "message_id": str(discrepancy["message_id"]),
                        "conversation_id": str(discrepancy["conversation_id"]),
                        "reconciliation": True,
                        "original_created_at": discrepancy["created_at"],
                    },
                )
            except Exception as e:
                reconciliation_report["errors"].append(f"Failed to retry deduction: {e}")

        reconciliation_report["completed_at"] = datetime.now(UTC).isoformat()
        reconciliation_report["status"] = "success"

        logger.info(
            f"✅ Daily credit reconciliation completed: "
            f"processed={failed_processed['processed']}, "
            f"retried={failed_processed['retried']}, "
            f"discrepancies={len(discrepancies)}"
        )

        # Store report in Redis for monitoring
        _store_reconciliation_report(reconciliation_report)

    except Exception as e:
        reconciliation_report["status"] = "failed"
        reconciliation_report["errors"].append(str(e))
        _store_reconciliation_report(reconciliation_report)

        logger.error(f"❌ Credit reconciliation failed: {e}", exc_info=True)
        raise self.retry(exc=e)

    finally:
        if db:
            db.close()


def _process_failed_deductions(db) -> dict:
    """Process failed deductions stored in Redis."""
    result = {"processed": 0, "retried": 0, "expired": 0}

    try:
        import json

        from src.config.redis import get_redis

        redis = get_redis()
        if not redis:
            return result

        # Get failed deductions older than 1 hour (give original task time to complete)
        one_hour_ago = datetime.now(UTC) - timedelta(hours=1)
        seven_days_ago = datetime.now(UTC) - timedelta(days=7)

        # Get all failed deductions
        failed_items = redis.zrangebyscore(
            "billing:failed_deductions",
            min=seven_days_ago.timestamp(),
            max=one_hour_ago.timestamp(),
        )

        for item in failed_items:
            result["processed"] += 1
            try:
                data = json.loads(item)
                failed_at = datetime.fromisoformat(data["failed_at"])

                # If older than 7 days, just remove (expired)
                if failed_at < seven_days_ago:
                    result["expired"] += 1
                    redis.zrem("billing:failed_deductions", item)
                    continue

                # Retry the deduction
                deduct_credits_async.delay(
                    tenant_id=data["tenant_id"],
                    user_id=data.get("user_id"),
                    agent_id=data["agent_id"],
                    action_type=data["action_type"],
                    metadata={**data.get("metadata", {}), "reconciliation_retry": True},
                )
                result["retried"] += 1

                # Remove from failed set
                redis.zrem("billing:failed_deductions", item)

            except Exception as e:
                logger.warning(f"Failed to process failed deduction: {e}")

    except Exception as e:
        logger.error(f"Error processing failed deductions: {e}")

    return result


def _find_missing_deductions(db) -> list:
    """Find messages from last 24 hours without corresponding credit transactions."""
    from sqlalchemy import text

    discrepancies = []

    try:
        # Query for messages without credit transactions
        # This is a simplified query - adjust based on your actual schema
        query = text("""
            SELECT DISTINCT
                m.id as message_id,
                m.conversation_id,
                c.agent_id,
                c.account_id as user_id,
                a.tenant_id,
                m.created_at
            FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            JOIN agents a ON c.agent_id = a.id
            WHERE m.role = 'ASSISTANT'
            AND m.status = 'COMPLETED'
            AND m.created_at > NOW() - INTERVAL '24 hours'
            AND m.created_at < NOW() - INTERVAL '1 hour'
            AND NOT EXISTS (
                SELECT 1 FROM credit_transactions ct
                WHERE ct.transaction_metadata::jsonb->>'message_id' = m.id::text
            )
            LIMIT 100
        """)

        result = db.execute(query)
        for row in result:
            discrepancies.append(
                {
                    "message_id": row.message_id,
                    "conversation_id": row.conversation_id,
                    "agent_id": row.agent_id,
                    "user_id": row.user_id,
                    "tenant_id": row.tenant_id,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "action_type": "CHAT_MESSAGE",  # Default action type
                }
            )

    except Exception as e:
        logger.error(f"Error finding missing deductions: {e}")

    return discrepancies


@shared_task(
    name="billing.flush_usage_analytics",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    time_limit=300,  # 5 minutes — generous for large key counts
    soft_time_limit=270,
    queue="billing",
    acks_late=True,
)
def flush_usage_analytics(self):
    """
    Flush buffered usage counters from Redis to the database.

    Scheduled every hour by Celery beat. For each buffered
    usage:{tenant}:{agent}:{metric}:{date} key the task:

      1. Atomically reads the hash and deletes the key (pipeline).
      2. Upserts the accumulated delta into usage_analytics using
         UPDATE … WHERE …; INSERT if rowcount == 0 — no unique constraint needed.

    A Redis lock prevents concurrent flushes if beat fires while a previous
    run is still in progress.
    """
    import asyncio

    async def _flush() -> int:
        from src.config.redis import get_redis
        from src.core.database import create_celery_async_session
        from src.services.billing.usage_tracking_service import USAGE_REDIS_PREFIX

        redis = get_redis()
        if not redis:
            logger.warning("Redis unavailable, skipping usage analytics flush")
            return 0

        # Prevent concurrent flushes — TTL slightly less than the hourly beat interval
        lock = redis.lock("billing:usage_flush_lock", timeout=3540)
        if not lock.acquire(blocking=False):
            logger.info("Usage analytics flush already in progress, skipping this run")
            return 0

        try:
            keys = list(redis.scan_iter(f"{USAGE_REDIS_PREFIX}*", count=500))
            if not keys:
                return 0

            # Atomically read + delete every key in one pipeline round-trip.
            # Results layout: [hgetall_0, del_0, hgetall_1, del_1, ...]
            pipe = redis.pipeline()
            for key in keys:
                pipe.hgetall(key)
                pipe.delete(key)
            results = pipe.execute()

            entries = []
            for i, key in enumerate(keys):
                raw = results[i * 2]
                if not raw:
                    continue  # Already consumed by a concurrent worker

                # redis-py may return bytes or str keys depending on connection config
                def _int(val) -> int:
                    return int(val) if val else 0

                count = _int(raw.get(b"count") or raw.get("count"))
                credits = _int(raw.get(b"credits") or raw.get("credits"))
                if count == 0 and credits == 0:
                    continue

                try:
                    key_str = key.decode() if isinstance(key, bytes) else key
                    # Format: usage:{tenant_id}:{agent_id_or_none}:{metric_type}:{YYYY-MM-DD}
                    _, tenant_id_str, agent_id_str, metric_type, date_str = key_str.split(":", 4)
                    entries.append(
                        {
                            "tenant_id": UUID(tenant_id_str),
                            "agent_id": UUID(agent_id_str) if agent_id_str != "none" else None,
                            "metric_type": metric_type,
                            "date": date.fromisoformat(date_str),
                            "count": count,
                            "credits": credits,
                        }
                    )
                except Exception as parse_err:
                    logger.warning(f"Skipping unparseable usage key '{key}': {parse_err}")

            if not entries:
                return 0

            async_session_factory = create_celery_async_session()
            async with async_session_factory() as db:
                try:
                    await _upsert_usage_entries(db, entries)
                    await db.commit()
                    logger.info(f"Flushed {len(entries)} usage counter(s) to DB")
                    return len(entries)
                except Exception:
                    await db.rollback()
                    raise

        finally:
            try:
                lock.release()
            except Exception:
                pass

    try:
        return asyncio.run(_flush())
    except Exception as e:
        logger.error(f"Usage analytics flush failed: {e}", exc_info=True)
        raise self.retry(exc=e)


async def _upsert_usage_entries(db, entries: list[dict]) -> None:
    """
    Write accumulated usage deltas to usage_analytics.

    Uses UPDATE-then-INSERT so no unique constraint is required.
    All entries are committed in the caller's transaction.
    """
    from sqlalchemy import update

    from src.models.usage_analytics import UsageAnalytics

    now = datetime.now(UTC)

    for entry in entries:
        result = await db.execute(
            update(UsageAnalytics)
            .where(
                UsageAnalytics.tenant_id == entry["tenant_id"],
                UsageAnalytics.agent_id == entry["agent_id"],
                UsageAnalytics.date == entry["date"],
                UsageAnalytics.metric_type == entry["metric_type"],
            )
            .values(
                total_count=UsageAnalytics.total_count + entry["count"],
                credits_consumed=UsageAnalytics.credits_consumed + entry["credits"],
                updated_at=now,
            )
        )

        if result.rowcount == 0:
            # Row does not exist yet — create it
            db.add(
                UsageAnalytics(
                    tenant_id=entry["tenant_id"],
                    agent_id=entry["agent_id"],
                    date=entry["date"],
                    metric_type=entry["metric_type"],
                    total_count=entry["count"],
                    credits_consumed=entry["credits"],
                )
            )


def _store_reconciliation_report(report: dict) -> None:
    """Store reconciliation report in Redis for monitoring."""
    try:
        import json

        from src.config.redis import get_redis

        redis = get_redis()
        if redis:
            # Store report with timestamp key
            key = f"billing:reconciliation:{datetime.now(UTC).strftime('%Y-%m-%d')}"
            redis.set(key, json.dumps(report), ex=86400 * 30)  # Keep for 30 days
    except Exception as e:
        logger.warning(f"Failed to store reconciliation report: {e}")
