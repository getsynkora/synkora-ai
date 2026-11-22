"""
Real-database checks for the quota counter (idempotency, period rollover, concurrency).

Requires the test Postgres (see CLAUDE.md, port 5433).
"""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.models.quota_usage import QuotaUsage
from src.models.subscription_plan import PlanTier, SubscriptionPlan
from src.models.tenant_subscription import BillingCycle, SubscriptionStatus, TenantSubscription
from src.services.billing.quota_service import ConsumeResult, QuotaService, ReserveResult

pytestmark = pytest.mark.integration


async def _subscribe(db: AsyncSession, tenant_id, limit: int, period_start: datetime):
    plan = SubscriptionPlan(
        name=f"quota-plan-{uuid4().hex[:8]}",
        tier=PlanTier.STARTER,
        price_monthly=10,
        credits_monthly=0,
        quota_pools=[{"key": "support", "label": "Support messages", "limit": limit}],
    )
    db.add(plan)
    await db.flush()
    sub = TenantSubscription(
        tenant_id=tenant_id,
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE,
        billing_cycle=BillingCycle.MONTHLY,
        current_period_start=period_start,
        current_period_end=period_start + timedelta(days=30),
    )
    db.add(sub)
    await db.commit()
    return sub


async def test_same_message_counts_once(async_db_session, async_tenant):
    start = datetime.now(UTC).replace(microsecond=0)
    await _subscribe(async_db_session, async_tenant.id, 10, start)
    service = QuotaService(async_db_session)

    first = await service.consume(async_tenant.id, "support", "msg_a")
    second = await service.consume(async_tenant.id, "support", "msg_a")

    assert first == ConsumeResult.CONSUMED
    assert second == ConsumeResult.DUPLICATE
    status = await service.get_pool_status(async_tenant.id, "support")
    assert status.used == 1


async def test_pool_exhausts_then_new_period_starts_at_zero(async_db_session, async_tenant):
    start = datetime.now(UTC).replace(microsecond=0)
    sub = await _subscribe(async_db_session, async_tenant.id, 2, start)
    service = QuotaService(async_db_session)

    await service.consume(async_tenant.id, "support", "msg_1")
    await service.consume(async_tenant.id, "support", "msg_2")
    assert (await service.get_pool_status(async_tenant.id, "support")).exhausted
    assert await service.consume(async_tenant.id, "support", "msg_3") == ConsumeResult.OVER_LIMIT

    sub.current_period_start = start + timedelta(days=30)
    sub.current_period_end = start + timedelta(days=60)
    await async_db_session.commit()
    assert (await service.get_pool_status(async_tenant.id, "support")).used == 0


async def test_concurrent_messages_do_not_lose_counts(async_engine, async_db_session, async_tenant):
    start = datetime.now(UTC).replace(microsecond=0)
    await _subscribe(async_db_session, async_tenant.id, 100, start)
    factory = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

    async def one(i: int):
        async with factory() as db:
            return await QuotaService(db).consume(async_tenant.id, "support", f"msg_c{i}")

    results = await asyncio.gather(*[one(i) for i in range(20)])
    assert all(r == ConsumeResult.CONSUMED for r in results)
    used = await async_db_session.scalar(select(QuotaUsage.used).where(QuotaUsage.tenant_id == async_tenant.id))
    assert used == 20


async def test_reservations_never_exceed_the_limit_under_concurrency(async_engine, async_db_session, async_tenant):
    start = datetime.now(UTC).replace(microsecond=0)
    await _subscribe(async_db_session, async_tenant.id, 5, start)
    factory = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

    async def one(i: int):
        async with factory() as db:
            return await QuotaService(db).reserve(async_tenant.id, "support", f"msg_r{i}")

    results = await asyncio.gather(*[one(i) for i in range(20)])
    assert results.count(ReserveResult.RESERVED) == 5
    assert results.count(ReserveResult.EXHAUSTED) == 15
    status = await QuotaService(async_db_session).get_pool_status(async_tenant.id, "support")
    assert status.used == 5


async def test_release_frees_a_unit_and_consume_after_reserve_does_not_double_count(async_db_session, async_tenant):
    start = datetime.now(UTC).replace(microsecond=0)
    await _subscribe(async_db_session, async_tenant.id, 1, start)
    service = QuotaService(async_db_session)

    assert await service.reserve(async_tenant.id, "support", "msg_x") == ReserveResult.RESERVED
    assert await service.reserve(async_tenant.id, "support", "msg_y") == ReserveResult.EXHAUSTED
    # the deduction task counts under the same key after the reply: no second unit
    assert await service.consume(async_tenant.id, "support", "msg_x") == ConsumeResult.DUPLICATE

    assert await service.release(async_tenant.id, "msg_x") is True
    assert (await service.get_pool_status(async_tenant.id, "support")).used == 0
    assert await service.reserve(async_tenant.id, "support", "msg_y") == ReserveResult.RESERVED
