"""
Payout Tasks

Celery tasks for agent subscription expiry and creator payouts.
"""

import logging
from datetime import UTC, datetime

from celery import shared_task
from sqlalchemy import select

logger = logging.getLogger(__name__)


@shared_task(name="billing.expire_agent_subscriptions", queue="billing")
def expire_agent_subscriptions() -> dict:
    """Mark expired agent_user_subscriptions as EXPIRED. Runs hourly."""
    import asyncio

    from src.core.database import get_db_session

    async def _run():
        async with get_db_session() as db:
            from src.services.billing.agent_user_subscription_service import AgentUserSubscriptionService

            count = await AgentUserSubscriptionService.expire_stale_subscriptions(db)
            logger.info(f"Expired {count} stale agent subscriptions")
            return count

    count = asyncio.run(_run())
    return {"expired_count": count}


@shared_task(name="billing.process_monthly_payouts", queue="billing")
def process_monthly_payouts() -> dict:
    """Process creator payouts for the previous month. Runs 1st of month at 2 AM UTC."""
    import asyncio

    from src.core.database import get_db_session

    async def _run():
        async with get_db_session() as db:
            from src.models.agent_revenue import AgentRevenue, RevenueStatus
            from src.services.billing.revenue_service import RevenueService

            # Fetch all pending revenue records
            result = await db.execute(select(AgentRevenue).where(AgentRevenue.status == RevenueStatus.PENDING))
            pending = result.scalars().all()

            processed = 0
            failed = 0
            revenue_service = RevenueService(db)

            for record in pending:
                try:
                    await revenue_service.process_payout(record.id)
                    processed += 1
                except Exception as e:
                    logger.error(f"Payout failed for revenue {record.id}: {e}")
                    record.mark_as_failed(str(e)[:255])
                    failed += 1

            await db.commit()
            logger.info(f"Monthly payouts: {processed} processed, {failed} failed")
            return {"processed": processed, "failed": failed}

    result = asyncio.run(_run())
    return result
