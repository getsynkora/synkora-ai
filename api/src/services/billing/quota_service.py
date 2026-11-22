"""
Quota Service - generic per-pool message metering.

A subscription plan may define named quota pools in ``SubscriptionPlan.quota_pools``::

    [{"key": "support", "label": "Support messages", "limit": 2500}, ...]

Each agent draws from one pool (``Agent.quota_pool``, default ``"default"``). Usage is
counted per billing period, so a new period starts every pool at zero with no reset job.
Pool keys are free-form slugs; nothing here is specific to an industry.

If the tenant's plan has no pools, the service reports "not metered" and callers fall back to the
shared credit balance. If the plan has pools but none matches the agent, the agent is "unassigned":
that is a configuration problem, reported as such instead of silently falling back to credits.
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
from src.services.outbound_webhooks import EVENT_USAGE_THRESHOLD, USAGE_THRESHOLDS, emit_event

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
    UNASSIGNED = "unassigned"  # plan has pools but none matches this agent; nothing was counted


class ReserveResult(StrEnum):
    """Outcome of reserving one unit before work starts."""

    NOT_METERED = "not_metered"  # plan has no matching pool; caller should use credits
    RESERVED = "reserved"  # unit taken; release it if the work does not complete
    DUPLICATE = "duplicate"  # this key already holds a unit
    EXHAUSTED = "exhausted"  # pool is full; nothing was taken
    UNASSIGNED = "unassigned"  # plan has pools but none matches this agent; nothing was taken
    INACTIVE = "inactive"  # the tenant's subscription is suspended, cancelled or expired; nothing was taken


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

    async def _has_inactive_subscription(self, tenant_id: uuid.UUID) -> bool:
        """True when the tenant's most recent subscription is suspended, cancelled or expired."""
        status = await self.db.scalar(
            select(TenantSubscription.status)
            .where(TenantSubscription.tenant_id == tenant_id)
            .order_by(TenantSubscription.created_at.desc())
            .limit(1)
        )
        return status in (SubscriptionStatus.SUSPENDED, SubscriptionStatus.CANCELLED, SubscriptionStatus.EXPIRED)

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

    def unassigned_pools(self, plan: SubscriptionPlan, pool_key: str | None) -> list[str] | None:
        """The plan's pool keys when it has pools but none matches ``pool_key``; otherwise None."""
        pools = plan.quota_pools or []
        if pools and self._find_pool(pools, pool_key) is None:
            return [p["key"] for p in pools]
        return None

    async def unassigned_pool_keys(self, tenant_id: uuid.UUID, pool_key: str | None) -> list[str] | None:
        """For the pre-check: the pools the tenant's plan offers if this agent matches none of them."""
        active = await self._active_plan(tenant_id)
        return self.unassigned_pools(active[1], pool_key) if active else None

    @staticmethod
    def _status(pool: dict, used: int, period: tuple[datetime, datetime]) -> PoolStatus:
        return PoolStatus(
            key=pool["key"],
            label=pool.get("label") or pool["key"],
            limit=int(pool["limit"]),
            used=int(used or 0),
            period_start=period[0],
            period_end=period[1],
        )

    async def get_pool_status(self, tenant_id: uuid.UUID, pool_key: str | None) -> PoolStatus | None:
        """Return the pool's usage this period, or None if the plan does not meter this pool."""
        active = await self._active_plan(tenant_id)
        if not active:
            return None
        subscription, plan = active
        pool = self._find_pool(plan.quota_pools, pool_key)
        if pool is None:
            return None

        period = self._period(subscription)
        used = await self.db.scalar(
            select(QuotaUsage.used).where(
                QuotaUsage.tenant_id == tenant_id,
                QuotaUsage.pool_key == pool["key"],
                QuotaUsage.period_start == period[0],
            )
        )
        return self._status(pool, used, period)

    async def list_pool_statuses(self, tenant_id: uuid.UUID) -> list[PoolStatus]:
        """All pools on the tenant's plan with this period's usage (empty if the plan has none)."""
        active = await self._active_plan(tenant_id)
        if not active:
            return []
        subscription, plan = active
        pools = plan.quota_pools or []
        if not pools:
            return []

        period = self._period(subscription)
        rows = await self.db.execute(
            select(QuotaUsage.pool_key, QuotaUsage.used).where(
                QuotaUsage.tenant_id == tenant_id, QuotaUsage.period_start == period[0]
            )
        )
        used_by_pool = {row[0]: row[1] for row in rows.all()}
        return [self._status(pool, used_by_pool.get(pool["key"], 0), period) for pool in pools]

    async def _notify_thresholds(self, tenant_id: uuid.UUID, pool: dict, period_start: datetime, used: int) -> None:
        """
        Queue a ``usage.threshold`` event the first time each of 80% and 100% is reached in a period.

        The highest level already announced is stored on the counter row, so retries, released units and
        overshoot never repeat an alert. Marking is a conditional UPDATE, so concurrent messages announce once.
        """
        limit = int(pool["limit"])
        if limit <= 0:
            return
        announced: list[int] = []
        for percent in USAGE_THRESHOLDS:
            if used * 100 < percent * limit:
                continue
            marked = await self.db.execute(
                update(QuotaUsage)
                .where(
                    QuotaUsage.tenant_id == tenant_id,
                    QuotaUsage.pool_key == pool["key"],
                    QuotaUsage.period_start == period_start,
                    QuotaUsage.notified_percent < percent,
                )
                .values(notified_percent=percent)
                .returning(QuotaUsage.id)
            )
            if marked.first() is not None:
                announced.append(percent)
        if not announced:
            return
        await self.db.commit()
        for percent in announced:
            await emit_event(
                self.db,
                tenant_id,
                EVENT_USAGE_THRESHOLD,
                {
                    "pool": pool["key"],
                    "label": pool.get("label") or pool["key"],
                    "threshold_percent": percent,
                    "used": used,
                    "limit": limit,
                },
            )

    async def consume(
        self,
        tenant_id: uuid.UUID,
        pool_key: str | None,
        idempotency_key: str,
        amount: int = 1,
        agent_id: uuid.UUID | None = None,
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
            return ConsumeResult.UNASSIGNED if plan.quota_pools else ConsumeResult.NOT_METERED

        period_start, _ = self._period(subscription)
        key = pool["key"]

        inserted = await self.db.execute(
            pg_insert(QuotaUsageEvent)
            .values(
                idempotency_key=idempotency_key,
                tenant_id=tenant_id,
                pool_key=key,
                agent_id=agent_id,
                period_start=period_start,
                amount=amount,
            )
            .on_conflict_do_nothing(index_elements=["idempotency_key"])
            .returning(QuotaUsageEvent.id)
        )
        if inserted.scalar_one_or_none() is None:
            # Nothing was written. No session rollback: it would expire every object the caller has loaded in this
            # session, and their next attribute read would fail outside the async context (MissingGreenlet).
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
        await self._notify_thresholds(tenant_id, pool, period_start, used_now)

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
        agent_id: uuid.UUID | None = None,
    ) -> ReserveResult:
        """
        Take ``amount`` units before the work starts, never going past the pool's limit.

        The increment is a single conditional UPDATE (``used + amount <= limit``), so
        concurrent requests are serialised by the row lock and the limit holds exactly.
        Call ``release`` with the same key if the work does not complete.
        """
        active = await self._active_plan(tenant_id)
        if not active:
            # Every chat path reserves here, including bots, widgets and the scheduler that run no pre-check, so a
            # suspended, cancelled or expired subscription is refused here rather than served on credits.
            return (
                ReserveResult.INACTIVE
                if await self._has_inactive_subscription(tenant_id)
                else ReserveResult.NOT_METERED
            )
        subscription, plan = active
        pool = self._find_pool(plan.quota_pools, pool_key)
        if pool is None:
            return ReserveResult.UNASSIGNED if plan.quota_pools else ReserveResult.NOT_METERED

        period_start, _ = self._period(subscription)
        key = pool["key"]
        limit = int(pool["limit"])

        # A savepoint, not a session rollback, undoes the event row when the pool is full: a session rollback expires
        # every object the caller has loaded (the agent, the conversation), and their next attribute read fails.
        savepoint = await self.db.begin_nested()
        inserted = await self.db.execute(
            pg_insert(QuotaUsageEvent)
            .values(
                idempotency_key=idempotency_key,
                tenant_id=tenant_id,
                pool_key=key,
                agent_id=agent_id,
                period_start=period_start,
                amount=amount,
            )
            .on_conflict_do_nothing(index_elements=["idempotency_key"])
            .returning(QuotaUsageEvent.id)
        )
        if inserted.scalar_one_or_none() is None:
            await savepoint.rollback()  # nothing was written
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
        used_now = taken.scalar_one_or_none()
        if used_now is None:
            await savepoint.rollback()  # discards the event row inserted above
            return ReserveResult.EXHAUSTED

        await savepoint.commit()
        await self.db.commit()
        await self._notify_thresholds(tenant_id, pool, period_start, used_now)
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
            return False  # nothing was deleted; no session rollback (it would expire the caller's loaded objects)
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
