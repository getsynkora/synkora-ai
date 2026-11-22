"""
Account API - plan and usage for external platforms.

Lets another product (for example a customer portal) show a tenant's plan, what the plan
includes, and how much of it has been used, using the same API keys as the Public Agent API.

Authentication: ``Authorization: Bearer <agent api key>`` with the ``billing:read`` permission.
All data is for the key's own tenant; there is no way to ask about another tenant.
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.agent_api_auth import require_permission
from src.models.agent_api_key import AgentApiKey
from src.models.subscription_plan import SubscriptionPlan
from src.services.billing.credit_service import CreditService
from src.services.billing.plan_restriction_service import PlanRestrictionService
from src.services.billing.quota_service import QuotaService
from src.services.billing.subscription_service import SubscriptionService

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
    restrictions = PlanRestrictionService(db)
    plan = await restrictions.get_tenant_plan(api_key.tenant_id)
    subscription = await restrictions.get_tenant_subscription(api_key.tenant_id)
    return CurrentPlanResponse(
        plan=serialize_plan(plan) if plan else None,
        subscription=_serialize_subscription(subscription) if subscription else None,
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
    pool_statuses = await QuotaService(db).list_pool_statuses(api_key.tenant_id)

    credits: CreditsUsage | None = None
    if not pool_statuses:
        balance = await CreditService(db).get_balance(api_key.tenant_id)
        credits = CreditsUsage(
            total=balance.total_credits if balance else 0,
            used=balance.used_credits if balance else 0,
            available=balance.available_credits if balance else 0,
            last_reset_at=balance.last_reset_at if balance else None,
        )

    stats = await PlanRestrictionService(db).get_usage_stats(api_key.tenant_id)

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
