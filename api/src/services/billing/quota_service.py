"""
Quota Service - generic per-pool message metering.

A subscription plan may define named quota pools in ``SubscriptionPlan.quota_pools``::

    [{"key": "support", "label": "Support messages", "limit": 2500}, ...]

Each agent draws from one pool (``Agent.quota_pool``, default ``"default"``). Usage is
counted per billing period, so a new period starts every pool at zero with no reset job.
Pool keys are free-form slugs; nothing here is specific to an industry.

If the tenant's plan has no pools, or has no pool matching the agent, the service reports
"not metered" and callers fall back to the shared credit balance.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.quota_usage import QuotaUsage, QuotaUsageEvent
from src.models.subscription_plan import SubscriptionPlan
from src.models.tenant_subscription import SubscriptionStatus, TenantSubscription

logger = logging.getLogger(__name__)

DEFAULT_POOL_KEY = "default"


@dataclass
class PoolStatus:
    """Usage of one quota pool in the current billing period."""

    key: str
    label: str
    limit: int
    used: int
    period_start: datetime
    period_end: datetime

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)

    @property
    def exhausted(self) -> bool:
        return self.used >= self.limit


class ConsumeResult(StrEnum):
    """Outcome of consuming one unit from a pool."""

    NOT_METERED = "not_metered"  # plan has no matching pool; caller should use credits
    CONSUMED = "consumed"
    DUPLICATE = "duplicate"  # idempotency key already counted
    OVER_LIMIT = "over_limit"  # counted, but pool is now past its limit


class ReserveResult(StrEnum):
    """Outcome of reserving one unit before work starts."""

    NOT_METERED = "not_metered"  # plan has no matching pool; caller should use credits
    RESERVED = "reserved"  # unit taken; release it if the work does not complete
    DUPLICATE = "duplicate"  # this key already holds a unit
    EXHAUSTED = "exhausted"  # pool is full; nothing was taken


class QuotaService:
    """Reads plan quota pools and records usage against them."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _active_plan(self, tenant_id: uuid.UUID) -> tuple[TenantSubscription, SubscriptionPlan] | None:
        result = await self.db.execute(
            select(TenantSubscription, SubscriptionPlan)
            .join(SubscriptionPlan, SubscriptionPlan.id == TenantSubscription.plan_id)
            .where(
                TenantSubscription.tenant_id == tenant_id,
                TenantSubscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]),
            )
            .order_by(TenantSubscription.created_at.desc())
            .limit(1)
        )
        row = result.first()
        return (row[0], row[1]) if row else None

    @staticmethod
    def _period(subscription: TenantSubscription) -> tuple[datetime, datetime]:
        start = subscription.current_period_start
        end = subscription.current_period_end
        if start is None:
            now = datetime.now(UTC)
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if end is None:
            end = start + timedelta(days=31)
        return start, end

    @staticmethod
    def _find_pool(pools: list[dict] | None, pool_key: str | None) -> dict | None:
        if not pools:
            return None
        wanted = pool_key or DEFAULT_POOL_KEY
        for pool in pools:
            if pool.get("key") == wanted:
                return pool
        return None

    async def get_pool_status(self, tenant_id: uuid.UUID, pool_key: str | None) -> PoolStatus | None:
        """Return the pool's usage this period, or None if the plan does not meter this pool."""
        active = await self._active_plan(tenant_id)
        if not active:
            return None
        subscription, plan = active
        pool = self._find_pool(plan.quota_pools, pool_key)
        if pool is None:
            return None

        period_start, period_end = self._period(subscription)
        used = await self.db.scalar(
            select(QuotaUsage.used).where(
                QuotaUsage.tenant_id == tenant_id,
                QuotaUsage.pool_key == pool["key"],
                QuotaUsage.period_start == period_start,
            )
        )
        return PoolStatus(
            key=pool["key"],
            label=pool.get("label") or pool["key"],
            limit=int(pool["limit"]),
            used=int(used or 0),
            period_start=period_start,
            period_end=period_end,
        )

    async def list_pool_statuses(self, tenant_id: uuid.UUID) -> list[PoolStatus]:
        """All pools on the tenant's plan with this period's usage (empty if the plan has none)."""
        active = await self._active_plan(tenant_id)
        if not active:
            return []
        _, plan = active
        statuses = []
        for pool in plan.quota_pools or []:
            status = await self.get_pool_status(tenant_id, pool["key"])
            if status:
                statuses.append(status)
        return statuses

    async def consume(
        self,
        tenant_id: uuid.UUID,
        pool_key: str | None,
        idempotency_key: str,
        amount: int = 1,
    ) -> ConsumeResult:
        """
        Count ``amount`` units against the pool, once per ``idempotency_key``.

        The counter row is locked while it is updated so concurrent messages cannot lose
        increments. The true count is stored even past the limit, so overshoot is visible.
        """
        active = await self._active_plan(tenant_id)
        if not active:
            return ConsumeResult.NOT_METERED
        subscription, plan = active
        pool = self._find_pool(plan.quota_pools, pool_key)
        if pool is None:
            return ConsumeResult.NOT_METERED

        period_start, _ = self._period(subscription)
        key = pool["key"]

        inserted = await self.db.execute(
            pg_insert(QuotaUsageEvent)
            .values(
                idempotency_key=idempotency_key,
                tenant_id=tenant_id,
                pool_key=key,
                period_start=period_start,
                amount=amount,
            )
            .on_conflict_do_nothing(index_elements=["idempotency_key"])
            .returning(QuotaUsageEvent.id)
        )
        if inserted.scalar_one_or_none() is None:
            await self.db.rollback()
            return ConsumeResult.DUPLICATE

        await self.db.execute(
            pg_insert(QuotaUsage)
            .values(tenant_id=tenant_id, pool_key=key, period_start=period_start, used=0)
            .on_conflict_do_nothing(constraint="uq_quota_usage_period")
        )
        counter = (
            await self.db.execute(
                select(QuotaUsage)
                .where(
                    QuotaUsage.tenant_id == tenant_id,
                    QuotaUsage.pool_key == key,
                    QuotaUsage.period_start == period_start,
                )
                .with_for_update()
            )
        ).scalar_one()
        counter.used = (counter.used or 0) + amount
        used_now = counter.used
        await self.db.commit()

        limit = int(pool["limit"])
        if used_now > limit:
            logger.warning("Quota pool %s over limit for tenant %s: used=%s limit=%s", key, tenant_id, used_now, limit)
            return ConsumeResult.OVER_LIMIT
        return ConsumeResult.CONSUMED

    async def reserve(
        self,
        tenant_id: uuid.UUID,
        pool_key: str | None,
        idempotency_key: str,
        amount: int = 1,
    ) -> ReserveResult:
        """
        Take ``amount`` units before the work starts, never going past the pool's limit.

        The increment is a single conditional UPDATE (``used + amount <= limit``), so
        concurrent requests are serialised by the row lock and the limit holds exactly.
        Call ``release`` with the same key if the work does not complete.
        """
        active = await self._active_plan(tenant_id)
        if not active:
            return ReserveResult.NOT_METERED
        subscription, plan = active
        pool = self._find_pool(plan.quota_pools, pool_key)
        if pool is None:
            return ReserveResult.NOT_METERED

        period_start, _ = self._period(subscription)
        key = pool["key"]
        limit = int(pool["limit"])

        inserted = await self.db.execute(
            pg_insert(QuotaUsageEvent)
            .values(
                idempotency_key=idempotency_key,
                tenant_id=tenant_id,
                pool_key=key,
                period_start=period_start,
                amount=amount,
            )
            .on_conflict_do_nothing(index_elements=["idempotency_key"])
            .returning(QuotaUsageEvent.id)
        )
        if inserted.scalar_one_or_none() is None:
            await self.db.rollback()
            return ReserveResult.DUPLICATE

        await self.db.execute(
            pg_insert(QuotaUsage)
            .values(tenant_id=tenant_id, pool_key=key, period_start=period_start, used=0)
            .on_conflict_do_nothing(constraint="uq_quota_usage_period")
        )
        taken = await self.db.execute(
            update(QuotaUsage)
            .where(
                QuotaUsage.tenant_id == tenant_id,
                QuotaUsage.pool_key == key,
                QuotaUsage.period_start == period_start,
                QuotaUsage.used + amount <= limit,
            )
            .values(used=QuotaUsage.used + amount)
            .returning(QuotaUsage.used)
        )
        if taken.scalar_one_or_none() is None:
            await self.db.rollback()  # also discards the event row inserted above
            return ReserveResult.EXHAUSTED

        await self.db.commit()
        return ReserveResult.RESERVED

    async def release(self, tenant_id: uuid.UUID, idempotency_key: str) -> bool:
        """Give back a reserved or consumed unit (the work failed). Returns False if the key is unknown."""
        deleted = await self.db.execute(
            delete(QuotaUsageEvent)
            .where(QuotaUsageEvent.idempotency_key == idempotency_key, QuotaUsageEvent.tenant_id == tenant_id)
            .returning(QuotaUsageEvent.pool_key, QuotaUsageEvent.period_start, QuotaUsageEvent.amount)
        )
        row = deleted.first()
        if row is None:
            await self.db.rollback()
            return False
        pool_key, period_start, amount = row
        await self.db.execute(
            update(QuotaUsage)
            .where(
                QuotaUsage.tenant_id == tenant_id,
                QuotaUsage.pool_key == pool_key,
                QuotaUsage.period_start == period_start,
            )
            .values(used=func.greatest(QuotaUsage.used - amount, 0))
        )
        await self.db.commit()
        return True
