"""
Account API - plan and usage for external platforms.

Lets another product (for example a customer portal) show a tenant's plan, what the plan
includes, and how much of it has been used, using the same API keys as the Public Agent API.

Authentication: ``Authorization: Bearer <agent api key>`` with the ``billing:read`` permission (``billing:manage`` to
set the plan of a tenant billed in another system). All data is for the key's own tenant; there is no way to ask about
or change another tenant.
"""

import logging
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.agent_api_auth import require_permission
from src.models.agent_api_key import AgentApiKey
from src.models.quota_usage import QuotaUsageEvent
from src.models.subscription_plan import SubscriptionPlan
from src.models.tenant import Tenant
from src.services.activity.api_audit import audit_api_action
from src.services.agent_api.api_key_service import is_platform_key
from src.services.billing.credit_service import CreditService
from src.services.billing.plan_restriction_service import PlanRestrictionService
from src.services.billing.quota_service import QuotaService
from src.services.billing.subscription_service import SubscriptionService
from src.services.tenant_provisioning_service import ProvisioningError, TenantProvisioningService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/public/account", tags=["Account API"])

# Plan columns that cap a resource. ``null`` means unlimited.
_LIMIT_COLUMNS = (
    "max_agents",
    "max_team_members",
    "max_knowledge_bases",
    "max_data_sources",
    "max_custom_tools",
    "max_database_connections",
    "max_mcp_servers",
    "max_scheduled_tasks",
    "max_widgets",
    "max_slack_bots",
    "max_api_keys",
    "max_api_calls_per_month",
)


class QuotaPoolInfo(BaseModel):
    key: str
    label: str
    limit: int


class PlanInfo(BaseModel):
    id: str
    name: str
    tier: str
    description: str | None
    price_monthly: float
    price_yearly: float | None
    credits_monthly: int
    credits_rollover: bool
    quota_pools: list[QuotaPoolInfo]
    limits: dict[str, int | None]
    features: dict[str, Any]


class SubscriptionInfo(BaseModel):
    status: str
    billing_cycle: str | None
    current_period_start: datetime | None
    current_period_end: datetime | None
    trial_end: datetime | None
    cancel_at_period_end: bool
    cancelled_at: datetime | None
    auto_renew: bool | None


class CurrentPlanResponse(BaseModel):
    plan: PlanInfo | None
    subscription: SubscriptionInfo | None


class SubscriptionRequest(BaseModel):
    plan: str | None = Field(None, description="Plan name or id to move the customer to")
    status: str | None = Field(None, description="ACTIVE, TRIAL, SUSPENDED, CANCELLED or EXPIRED")
    billing_cycle: str | None = Field(None, description="MONTHLY or YEARLY")
    period_start: datetime | None = None
    period_end: datetime | None = Field(None, description="A new period starts every message pool at zero")
    cancel_at_period_end: bool | None = None
    renew: bool = Field(False, description="Start a new 30-day period now and reset allowances")


class PoolUsage(BaseModel):
    key: str
    label: str
    limit: int
    used: int
    remaining: int
    period_start: datetime
    period_end: datetime


class CreditsUsage(BaseModel):
    total: int
    used: int
    available: int
    last_reset_at: datetime | None


class ResourceUsage(BaseModel):
    current: int
    limit: int | None
    unlimited: bool


class UsageResponse(BaseModel):
    # "quota_pools" when the plan meters messages per pool, "credits" when it uses a shared balance
    metering: str
    period_start: datetime | None
    period_end: datetime | None
    pools: list[PoolUsage]
    credits: CreditsUsage | None
    resources: dict[str, ResourceUsage]


def serialize_plan(plan: SubscriptionPlan) -> PlanInfo:
    """Full public description of a plan: price, allowances, limits and features."""
    return PlanInfo(
        id=str(plan.id),
        name=plan.name,
        tier=plan.tier.value if hasattr(plan.tier, "value") else str(plan.tier),
        description=plan.description,
        price_monthly=float(plan.price_monthly or 0),
        price_yearly=float(plan.price_yearly) if plan.price_yearly is not None else None,
        credits_monthly=plan.credits_monthly or 0,
        credits_rollover=bool(plan.credits_rollover),
        quota_pools=[
            QuotaPoolInfo(key=p["key"], label=p.get("label") or p["key"], limit=int(p["limit"]))
            for p in (plan.quota_pools or [])
        ],
        limits={column: getattr(plan, column, None) for column in _LIMIT_COLUMNS},
        features=plan.features or {},
    )


def _serialize_subscription(subscription: Any) -> SubscriptionInfo:
    def _text(value: Any) -> str | None:
        return None if value is None else getattr(value, "value", str(value))

    return SubscriptionInfo(
        status=_text(subscription.status) or "UNKNOWN",
        billing_cycle=_text(subscription.billing_cycle),
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        trial_end=subscription.trial_end,
        cancel_at_period_end=bool(subscription.cancel_at_period_end),
        cancelled_at=subscription.cancelled_at,
        auto_renew=subscription.auto_renew,
    )


async def build_plan_response(db: AsyncSession, tenant_id: UUID) -> CurrentPlanResponse:
    """A tenant's current plan and subscription. No subscription means the Free plan, with ``subscription: null``."""
    restrictions = PlanRestrictionService(db)
    plan = await restrictions.get_tenant_plan(tenant_id)
    subscription = await restrictions.get_tenant_subscription(tenant_id)
    return CurrentPlanResponse(
        plan=serialize_plan(plan) if plan else None,
        subscription=_serialize_subscription(subscription) if subscription else None,
    )


@router.get("/plan", response_model=CurrentPlanResponse)
async def get_current_plan(
    api_key: AgentApiKey = Depends(require_permission("billing:read")),
    db: AsyncSession = Depends(get_async_db),
):
    """
    The tenant's current plan and subscription.

    A tenant with no active subscription is shown on the Free plan with ``subscription: null``.
    Requires permission: billing:read
    """
    return await build_plan_response(db, api_key.tenant_id)


@router.put("/subscription", response_model=CurrentPlanResponse)
async def set_subscription(
    body: SubscriptionRequest,
    request: Request,
    api_key: AgentApiKey = Depends(require_permission("billing:manage")),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Set this tenant's plan, status or billing period, for a tenant whose plan is paid for in your own system.

    Report each payment: the plan bought, a renewal (``renew: true`` or a new period, which starts every message
    pool at zero), or a stop (``status: SUSPENDED``). Only works once a platform administrator has set the tenant to
    external billing; otherwise any tenant could put itself on any plan.
    Requires permission: billing:manage
    """
    if not is_platform_key(api_key):
        raise HTTPException(status_code=403, detail="Only a platform key can set the plan")
    tenant = await db.get(Tenant, api_key.tenant_id)
    if tenant is None or not tenant.external_billing:
        raise HTTPException(
            status_code=403,
            detail="This workspace's plan is paid for in Synkora. Ask a platform administrator to allow external billing.",
        )
    try:
        await TenantProvisioningService(db, tenant).set_subscription(tenant, **body.model_dump())
    except ProvisioningError as err:
        raise HTTPException(status_code=err.status_code, detail=str(err)) from err
    audit_api_action(
        api_key,
        request,
        "account.subscription_changed",
        "tenant",
        resource_id=tenant.id,
        details=body.model_dump(exclude_none=True, mode="json"),
    )
    return await build_plan_response(db, tenant.id)


async def build_usage_response(db: AsyncSession, tenant_id: UUID) -> UsageResponse:
    """Usage in the tenant's current billing period: message pools or credits, plus resource counts."""
    pool_statuses = await QuotaService(db).list_pool_statuses(tenant_id)

    credits: CreditsUsage | None = None
    if not pool_statuses:
        balance = await CreditService(db).get_balance(tenant_id)
        credits = CreditsUsage(
            total=balance.total_credits if balance else 0,
            used=balance.used_credits if balance else 0,
            available=balance.available_credits if balance else 0,
            last_reset_at=balance.last_reset_at if balance else None,
        )

    stats = await PlanRestrictionService(db).get_usage_stats(tenant_id)

    return UsageResponse(
        metering="quota_pools" if pool_statuses else "credits",
        period_start=pool_statuses[0].period_start if pool_statuses else None,
        period_end=pool_statuses[0].period_end if pool_statuses else None,
        pools=[
            PoolUsage(
                key=s.key,
                label=s.label,
                limit=s.limit,
                used=s.used,
                remaining=s.remaining,
                period_start=s.period_start,
                period_end=s.period_end,
            )
            for s in pool_statuses
        ],
        credits=credits,
        resources={name: ResourceUsage(**values) for name, values in (stats.get("usage") or {}).items()},
    )


@router.get("/usage", response_model=UsageResponse)
async def get_usage(
    api_key: AgentApiKey = Depends(require_permission("billing:read")),
    db: AsyncSession = Depends(get_async_db),
):
    """
    How much of the plan has been used in the current billing period.

    - ``pools``: per-pool message usage, for plans that include message allowances.
    - ``credits``: the shared credit balance, for plans that do not use pools.
    - ``resources``: counts against plan limits (agents, team members, knowledge bases, ...).

    Requires permission: billing:read
    """
    return await build_usage_response(db, api_key.tenant_id)


class UsageHistoryPoint(BaseModel):
    date: date
    pool_key: str
    agent_id: str | None
    messages: int


class UsageHistoryResponse(BaseModel):
    from_date: date
    to_date: date
    total: int
    # One row per day, pool and agent. Days with no messages have no row.
    series: list[UsageHistoryPoint]


async def build_usage_history(db: AsyncSession, tenant_id: UUID, days: int) -> UsageHistoryResponse:
    """Messages counted against message pools, per day, pool and agent, for the last ``days`` days."""
    today = datetime.now(UTC).date()
    since = datetime.combine(today - timedelta(days=days - 1), time.min, tzinfo=UTC)
    # Bucket by UTC day whatever time zone the database session uses
    day = func.date_trunc("day", func.timezone("UTC", QuotaUsageEvent.created_at))
    rows = await db.execute(
        select(day, QuotaUsageEvent.pool_key, QuotaUsageEvent.agent_id, func.sum(QuotaUsageEvent.amount))
        .where(QuotaUsageEvent.tenant_id == tenant_id, QuotaUsageEvent.created_at >= since)
        .group_by(day, QuotaUsageEvent.pool_key, QuotaUsageEvent.agent_id)
        .order_by(day, QuotaUsageEvent.pool_key)
    )
    series = [
        UsageHistoryPoint(
            date=row[0].date(), pool_key=row[1], agent_id=str(row[2]) if row[2] else None, messages=int(row[3] or 0)
        )
        for row in rows.all()
    ]
    return UsageHistoryResponse(
        from_date=since.date(), to_date=today, total=sum(p.messages for p in series), series=series
    )


@router.get("/usage/history", response_model=UsageHistoryResponse)
async def get_usage_history(
    days: int = Query(30, ge=1, le=92, description="How many days back, including today"),
    api_key: AgentApiKey = Depends(require_permission("billing:read")),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Messages per day, pool and agent, for charts. Only plans that meter messages per pool record history.

    Requires permission: billing:read
    """
    return await build_usage_history(db, api_key.tenant_id, days)


@router.get("/plans", response_model=list[PlanInfo])
async def list_plans(
    api_key: AgentApiKey = Depends(require_permission("billing:read")),  # noqa: ARG001
    db: AsyncSession = Depends(get_async_db),
):
    """
    Every plan currently on offer, with price, message allowances, limits and features.

    Use it to show upgrade options next to the tenant's current plan.
    Requires permission: billing:read
    """
    plans = await SubscriptionService(db).get_available_plans()
    return [serialize_plan(plan) for plan in plans]
