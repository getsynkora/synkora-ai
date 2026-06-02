"""
Billing API Controllers
Handles subscription management, credit operations, and billing analytics
"""

import json
from datetime import UTC, date, datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.redis import get_redis_async
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id
from src.models.agent_pricing import PricingModel
from src.models.credit_topup import CreditTopup
from src.models.tenant import Account, AccountRole, Tenant, TenantAccountJoin
from src.services.billing import (
    CreditService,
    PaddleService,
    StripeService,
    SubscriptionService,
    UsageTrackingService,
)
from src.services.integrations.integration_config_service import IntegrationConfigService
from src.utils.config_helper import get_app_base_url

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


# ---------------------------------------------------------------------------
# Agent Pricing routes (used by the dashboard billing/agent-pricing page)
# ---------------------------------------------------------------------------


class AgentPricingUpsertRequest(BaseModel):
    agent_id: UUID
    pricing_model: PricingModel = PricingModel.FREE
    credits_per_use: int | None = None
    session_credits: int | None = None
    daily_credits: int | None = None
    weekly_credits: int | None = None
    monthly_subscription_credits: int | None = None
    trial_messages: int | None = None
    revenue_share_percentage: float | None = None
    email_subscription_model: str | None = None
    email_subscription_price_cents: int | None = None
    email_subscription_trial_emails: int | None = None


def _clean_dict(obj) -> dict:
    """Return obj.__dict__ without SQLAlchemy internal state."""
    return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}


_CREDIT_VALUE_USD = 0.02  # 1 credit = $0.02 (matches AgentPricingService.CREDIT_VALUE_USD)


@router.get("/agents/{agent_id}/pricing")
async def get_billing_agent_pricing(
    agent_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Get pricing configuration for an agent (by UUID)."""
    from src.services.billing.agent_pricing_service import AgentPricingService

    pricing = await AgentPricingService.get_agent_pricing(agent_id, db)
    if pricing is None:
        return {"pricing": None}
    return {"pricing": _clean_dict(pricing)}


@router.put("/agents/{agent_id}/pricing")
async def upsert_billing_agent_pricing(
    agent_id: UUID,
    body: AgentPricingUpsertRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Create or update pricing configuration for an agent."""
    from sqlalchemy import select as _select

    from src.models.agent import Agent
    from src.models.agent_pricing import AgentPricing, PricingModel

    # Verify agent belongs to this tenant
    result = await db.execute(_select(Agent).where(Agent.id == agent_id, Agent.tenant_id == tenant_id))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    pricing_result = await db.execute(_select(AgentPricing).where(AgentPricing.agent_id == agent_id))
    pricing = pricing_result.scalar_one_or_none()

    # Fields to update — always apply all fields sent by the client so that
    # switching pricing model clears stale tier-specific values.
    updateable = {
        "pricing_model": body.pricing_model,
        "credits_per_use": body.credits_per_use,
        "session_credits": body.session_credits,
        "daily_credits": body.daily_credits,
        "weekly_credits": body.weekly_credits,
        "monthly_subscription_credits": body.monthly_subscription_credits,
        "trial_messages": body.trial_messages,
        "revenue_share_percentage": body.revenue_share_percentage,
        "email_subscription_model": body.email_subscription_model,
        "email_subscription_price_cents": body.email_subscription_price_cents,
        "email_subscription_trial_emails": body.email_subscription_trial_emails,
    }

    if pricing is None:
        pricing = AgentPricing(
            agent_id=agent_id,
            tenant_id=tenant_id,
            is_active=True,
            **{k: v for k, v in updateable.items() if v is not None},
        )
        db.add(pricing)
    else:
        for k, v in updateable.items():
            if v is not None:
                setattr(pricing, k, v)

    await db.commit()
    await db.refresh(pricing)
    return {"pricing": _clean_dict(pricing)}


@router.get("/agents/{agent_id}/revenue")
async def get_billing_agent_revenue(
    agent_id: UUID,
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Get revenue records for an agent."""
    from sqlalchemy import select as _select

    from src.models.agent_pricing import AgentPricing
    from src.models.agent_revenue import AgentRevenue

    result = await db.execute(
        _select(AgentRevenue)
        .join(AgentPricing, AgentPricing.id == AgentRevenue.agent_pricing_id)
        .where(AgentPricing.agent_id == agent_id)
        .order_by(AgentRevenue.created_at.desc())
        .limit(100)
    )
    records = result.scalars().all()

    def _serialize_revenue(r: AgentRevenue) -> dict:
        d = _clean_dict(r)
        credits_used = int(d.get("total_credits") or 0)
        creator_credits = int(d.pop("creator_credits", 0) or 0)
        platform_credits = int(d.pop("platform_credits", 0) or 0)
        d.pop("total_credits", None)
        d["credits_used"] = credits_used
        d["revenue_amount"] = round(credits_used * _CREDIT_VALUE_USD, 2)
        d["creator_earnings"] = round(creator_credits * _CREDIT_VALUE_USD, 2)
        d["platform_fee"] = round(platform_credits * _CREDIT_VALUE_USD, 2)
        d["status"] = str(d.get("status") or "PENDING").lower()
        d["payout_date"] = None  # stored as payout_reference (not a date)
        return d

    return {"revenue": [_serialize_revenue(r) for r in records]}


@router.get("/agents/{agent_id}/earnings")
async def get_billing_agent_earnings(
    agent_id: UUID,
    period: str = Query("monthly", pattern="^(daily|weekly|monthly|yearly)$"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Get earnings summary for an agent."""
    from datetime import UTC, datetime, timedelta

    from src.services.billing.agent_pricing_service import AgentPricingService

    _period_days = {"daily": 1, "weekly": 7, "monthly": 30, "yearly": 365}
    end_date = datetime.now(UTC)
    start_date = end_date - timedelta(days=_period_days.get(period, 30))
    earnings = await AgentPricingService.get_agent_earnings(agent_id, start_date=start_date, end_date=end_date, db=db)
    return {"earnings": earnings}


async def _get_tenant_owner_email(db: AsyncSession, tenant_id: UUID) -> str | None:
    """Fetch the email of the tenant owner account."""
    result = await db.execute(
        select(Account.email)
        .join(TenantAccountJoin, TenantAccountJoin.account_id == Account.id)
        .where(TenantAccountJoin.tenant_id == tenant_id, TenantAccountJoin.role == AccountRole.OWNER)
        .limit(1)
    )
    return result.scalar_one_or_none()


# Pydantic Schemas
class CreditBalanceResponse(BaseModel):
    tenant_id: UUID
    total_credits: int
    used_credits: int
    available_credits: int
    last_reset_at: datetime | None


class CreditTransactionResponse(BaseModel):
    id: UUID
    tenant_id: UUID | None = None
    user_id: UUID | None = None
    agent_id: UUID | None = None
    transaction_type: str
    credits_amount: int  # Frontend expects credits_amount, not amount
    balance_before: int | None = None
    balance_after: int
    action_type: str | None = None
    description: str | None
    created_at: datetime


class SubscriptionResponse(BaseModel):
    id: UUID
    plan_id: UUID
    plan_name: str
    status: str
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool


class SubscriptionPlanResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    price_monthly: float
    price_yearly: float | None
    credits_monthly: int
    max_agents: int | None
    max_team_members: int | None
    features: dict
    is_active: bool


class UsageSummaryResponse(BaseModel):
    period: dict
    total_interactions: int
    total_credits_used: int
    breakdown: dict


class TopUpRequest(BaseModel):
    topup_id: str
    payment_provider: str | None = None  # "stripe" or "paddle"


class CreateSubscriptionRequest(BaseModel):
    plan_id: UUID
    payment_provider: str = "stripe"  # "stripe" or "paddle"


class UpgradeSubscriptionRequest(BaseModel):
    plan_id: UUID
    payment_provider: str | None = None  # Use existing provider if not specified


class PaymentProviderConfigResponse(BaseModel):
    provider: str
    client_token: str | None
    environment: str | None
    is_configured: bool


# Credit Balance Endpoints
@router.get("/credits/balance", response_model=CreditBalanceResponse)
async def get_credit_balance(
    tenant_id: UUID = Depends(get_current_tenant_id), db: AsyncSession = Depends(get_async_db)
):
    """Get current credit balance for tenant"""
    cache_key = f"billing:balance:{tenant_id}"
    try:
        redis = get_redis_async()
        if redis:
            cached = await redis.get(cache_key)
            if cached:
                return CreditBalanceResponse(**json.loads(cached))
    except Exception:
        pass

    credit_service = CreditService(db)
    balance = await credit_service.get_balance(tenant_id)

    if not balance:
        result = CreditBalanceResponse(
            tenant_id=tenant_id, total_credits=0, used_credits=0, available_credits=0, last_reset_at=None
        )
    else:
        result = CreditBalanceResponse(
            tenant_id=balance.tenant_id,
            total_credits=balance.total_credits,
            used_credits=balance.used_credits,
            available_credits=balance.available_credits,
            last_reset_at=balance.last_reset_at,
        )

    try:
        redis = get_redis_async()
        if redis:
            await redis.setex(cache_key, 120, result.model_dump_json())
    except Exception:
        pass

    return result


@router.get("/credits/transactions", response_model=list[CreditTransactionResponse])
async def get_credit_transactions(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    transaction_type: str | None = None,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Get credit transaction history"""
    credit_service = CreditService(db)

    filters = {}
    if transaction_type:
        filters["transaction_type"] = transaction_type

    transactions = await credit_service.get_transaction_history(
        tenant_id=tenant_id, filters=filters, limit=limit, offset=offset
    )

    return [
        CreditTransactionResponse(
            id=t.id,
            tenant_id=t.tenant_id,
            transaction_type=t.transaction_type.value
            if hasattr(t.transaction_type, "value")
            else str(t.transaction_type),
            credits_amount=t.amount,  # Map 'amount' to 'credits_amount' for frontend
            balance_after=t.balance_after,
            action_type=t.reference_type,  # Use reference_type as action_type
            description=t.description,
            created_at=t.created_at,
        )
        for t in transactions
    ]


@router.get("/credits/topups")
async def get_credit_topups(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Get credit topup history"""
    query = (
        select(CreditTopup)
        .where(CreditTopup.tenant_id == tenant_id)
        .order_by(CreditTopup.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    result = await db.execute(query)
    topups = result.scalars().all()

    return {
        "topups": [
            {
                "id": str(t.id),
                "amount": t.amount,
                "credits": t.credits,
                "status": t.status,
                "created_at": t.created_at.isoformat(),
            }
            for t in topups
        ]
    }


@router.post("/credits/topup")
async def purchase_credit_topup(
    request: TopUpRequest, tenant_id: UUID = Depends(get_current_tenant_id), db: AsyncSession = Depends(get_async_db)
):
    """Purchase additional credits via Stripe or Paddle Checkout"""
    # Get topup details
    result = await db.execute(select(CreditTopup).filter(CreditTopup.id == UUID(request.topup_id)))
    topup = result.scalar_one_or_none()
    if not topup:
        raise HTTPException(status_code=404, detail="Credit topup package not found")

    # Get tenant
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    base_url = await get_app_base_url(db, tenant_id)
    cancel_url = f"{base_url}/billing?canceled=true"

    if request.payment_provider == "paddle":
        # Use Paddle for checkout
        try:
            paddle_service = await PaddleService.create(db)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Paddle appends transaction_id automatically
        paddle_success_url = f"{base_url}/billing?provider=paddle&type=topup"

        # Get or create Paddle customer
        customer_id = await paddle_service.get_or_create_customer(
            tenant_id=tenant_id,
            email=await _get_tenant_owner_email(db, tenant_id) or f"tenant-{tenant_id}@placeholder.invalid",
            name=tenant.name if tenant else None,
        )

        checkout_result = await paddle_service.create_topup_checkout(
            tenant_id=tenant_id,
            topup_id=UUID(request.topup_id),
            credits_amount=topup.credits_amount,
            price_cents=int(topup.price * 100),
            customer_id=customer_id,
            success_url=paddle_success_url,
            cancel_url=cancel_url,
        )

        return {
            "checkout_url": checkout_result["checkout_url"],
            "session_id": checkout_result["transaction_id"],
            "provider": "paddle",
        }
    else:
        # Use Stripe for checkout (default)
        try:
            stripe_service = await StripeService.create(db)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Stripe uses {CHECKOUT_SESSION_ID} placeholder
        stripe_success_url = f"{base_url}/billing?session_id={{CHECKOUT_SESSION_ID}}"

        # Get or create Stripe customer
        customer_id = await stripe_service.get_or_create_customer(
            tenant_id=tenant_id,
            email=await _get_tenant_owner_email(db, tenant_id) or f"tenant-{tenant_id}@placeholder.invalid",
            name=tenant.name if tenant else None,
        )

        checkout_session = await stripe_service.create_topup_checkout_session(
            tenant_id=tenant_id,
            topup_id=UUID(request.topup_id),
            credits_amount=topup.credits_amount,
            price_cents=int(topup.price * 100),
            customer_id=customer_id,
            success_url=stripe_success_url,
            cancel_url=cancel_url,
        )

        return {
            "checkout_url": checkout_session["checkout_url"],
            "session_id": checkout_session["session_id"],
            "provider": "stripe",
        }


# Subscription Endpoints
@router.get("/subscription", response_model=Optional[SubscriptionResponse])
async def get_active_subscription(
    tenant_id: UUID = Depends(get_current_tenant_id), db: AsyncSession = Depends(get_async_db)
):
    """Get active subscription for tenant"""
    cache_key = f"billing:subscription:{tenant_id}"
    try:
        redis = get_redis_async()
        if redis:
            cached = await redis.get(cache_key)
            if cached:
                data = json.loads(cached)
                return SubscriptionResponse(**data) if data else None
    except Exception:
        pass

    subscription_service = SubscriptionService(db)
    subscription = await subscription_service.get_subscription_by_tenant(tenant_id)

    if not subscription:
        try:
            redis = get_redis_async()
            if redis:
                await redis.setex(cache_key, 120, "null")
        except Exception:
            pass
        return None

    result = SubscriptionResponse(
        id=subscription.id,
        plan_id=subscription.plan_id,
        plan_name=subscription.plan.name,
        status=subscription.status,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        cancel_at_period_end=subscription.cancelled_at is not None,
    )

    try:
        redis = get_redis_async()
        if redis:
            await redis.setex(cache_key, 120, result.model_dump_json())
    except Exception:
        pass

    return result


@router.get("/plans", response_model=list[SubscriptionPlanResponse])
async def get_subscription_plans(db: AsyncSession = Depends(get_async_db)):
    """Get all available subscription plans"""
    cache_key = "billing:plans"
    try:
        redis = get_redis_async()
        if redis:
            cached = await redis.get(cache_key)
            if cached:
                return [SubscriptionPlanResponse(**p) for p in json.loads(cached)]
    except Exception:
        pass

    subscription_service = SubscriptionService(db)
    plans = await subscription_service.get_available_plans()

    result = [
        SubscriptionPlanResponse(
            id=plan.id,
            name=plan.name,
            description=plan.description,
            price_monthly=float(plan.price_monthly),
            price_yearly=float(plan.price_yearly) if plan.price_yearly else None,
            credits_monthly=plan.credits_monthly,
            max_agents=plan.max_agents,
            max_team_members=plan.max_team_members,
            features=plan.features or {},
            is_active=plan.is_active,
        )
        for plan in plans
    ]

    try:
        redis = get_redis_async()
        if redis:
            await redis.setex(cache_key, 3600, json.dumps([p.model_dump() for p in result], default=str))
    except Exception:
        pass

    return result


@router.post("/subscription/create")
async def create_subscription(
    request: CreateSubscriptionRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Create a new subscription via Stripe or Paddle Checkout"""
    subscription_service = SubscriptionService(db)

    # Get plan details
    plan = await subscription_service.get_plan(request.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found")

    # Get tenant
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    base_url = await get_app_base_url(db, tenant_id)
    cancel_url = f"{base_url}/billing?canceled=true"

    if request.payment_provider == "paddle":
        # Use Paddle for checkout
        try:
            paddle_service = await PaddleService.create(db)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Paddle appends transaction_id automatically, no placeholder needed
        paddle_success_url = f"{base_url}/billing?provider=paddle"

        # Get or create Paddle customer
        customer_id = await paddle_service.get_or_create_customer(
            tenant_id=tenant_id,
            email=await _get_tenant_owner_email(db, tenant_id) or f"tenant-{tenant_id}@placeholder.invalid",
            name=tenant.name if tenant else None,
        )

        # Check for Paddle price ID
        price_id = plan.paddle_price_id if hasattr(plan, "paddle_price_id") else None
        if not price_id:
            raise HTTPException(status_code=400, detail="Plan does not have a Paddle price ID configured")

        checkout_session = await paddle_service.create_subscription_checkout_session(
            customer_id=customer_id,
            price_id=price_id,
            success_url=paddle_success_url,
            cancel_url=cancel_url,
            metadata={"tenant_id": str(tenant_id), "plan_id": str(request.plan_id), "type": "subscription"},
        )

        return {
            "checkout_url": checkout_session["checkout_url"],
            "session_id": checkout_session["session_id"],
            "provider": "paddle",
        }
    else:
        # Use Stripe for checkout (default)
        try:
            stripe_service = await StripeService.create(db)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Stripe uses {CHECKOUT_SESSION_ID} placeholder which it replaces
        stripe_success_url = f"{base_url}/billing?session_id={{CHECKOUT_SESSION_ID}}"

        # Get or create Stripe customer
        customer_id = await stripe_service.get_or_create_customer(
            tenant_id=tenant_id,
            email=await _get_tenant_owner_email(db, tenant_id) or f"tenant-{tenant_id}@placeholder.invalid",
            name=tenant.name if tenant else None,
        )

        # Check for Stripe price ID
        price_id = plan.stripe_price_id if hasattr(plan, "stripe_price_id") else None
        if not price_id:
            raise HTTPException(status_code=400, detail="Plan does not have a Stripe price ID configured")

        checkout_session = await stripe_service.create_subscription_checkout_session(
            customer_id=customer_id,
            price_id=price_id,
            success_url=stripe_success_url,
            cancel_url=cancel_url,
            metadata={"tenant_id": str(tenant_id), "plan_id": str(request.plan_id), "type": "subscription"},
        )

        return {
            "checkout_url": checkout_session["checkout_url"],
            "session_id": checkout_session["session_id"],
            "provider": "stripe",
        }


@router.post("/subscription/upgrade")
async def upgrade_subscription(
    request: UpgradeSubscriptionRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Upgrade to a different subscription plan via Stripe or Paddle Checkout"""
    subscription_service = SubscriptionService(db)

    # Get new plan details
    new_plan = await subscription_service.get_plan(request.plan_id)
    if not new_plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found")

    # Get tenant
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    base_url = await get_app_base_url(db, tenant_id)
    cancel_url = f"{base_url}/billing?canceled=true"

    if request.payment_provider == "paddle":
        # Use Paddle for checkout
        try:
            paddle_service = await PaddleService.create(db)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Paddle appends transaction_id automatically, no placeholder needed
        paddle_success_url = f"{base_url}/billing?provider=paddle"

        # Get or create Paddle customer
        customer_id = await paddle_service.get_or_create_customer(
            tenant_id=tenant_id,
            email=await _get_tenant_owner_email(db, tenant_id) or f"tenant-{tenant_id}@placeholder.invalid",
            name=tenant.name if tenant else None,
        )

        # Check for Paddle price ID
        price_id = new_plan.paddle_price_id if hasattr(new_plan, "paddle_price_id") else None
        if not price_id:
            raise HTTPException(status_code=400, detail="Plan does not have a Paddle price ID configured")

        try:
            checkout_session = await paddle_service.create_subscription_checkout_session(
                customer_id=customer_id,
                price_id=price_id,
                success_url=paddle_success_url,
                cancel_url=cancel_url,
                metadata={"tenant_id": str(tenant_id), "plan_id": str(request.plan_id), "type": "subscription_upgrade"},
            )
        except Exception as e:
            error_msg = str(e)
            if "400" in error_msg or "Paddle API error" in error_msg:
                raise HTTPException(status_code=400, detail=error_msg)
            raise HTTPException(status_code=503, detail=f"Payment provider error: {error_msg}")

        return {
            "checkout_url": checkout_session["checkout_url"],
            "session_id": checkout_session["session_id"],
            "provider": "paddle",
        }
    else:
        # Use Stripe for checkout (default)
        try:
            stripe_service = await StripeService.create(db)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Stripe uses {CHECKOUT_SESSION_ID} placeholder which it replaces
        stripe_success_url = f"{base_url}/billing?session_id={{CHECKOUT_SESSION_ID}}"

        # Get or create Stripe customer
        customer_id = await stripe_service.get_or_create_customer(
            tenant_id=tenant_id,
            email=await _get_tenant_owner_email(db, tenant_id) or f"tenant-{tenant_id}@placeholder.invalid",
            name=tenant.name if tenant else None,
        )

        price_id = new_plan.stripe_price_id if hasattr(new_plan, "stripe_price_id") else None
        if not price_id:
            raise HTTPException(status_code=400, detail="Plan does not have a Stripe price ID configured")

        checkout_session = await stripe_service.create_subscription_checkout_session(
            customer_id=customer_id,
            price_id=price_id,
            success_url=stripe_success_url,
            cancel_url=cancel_url,
            metadata={"tenant_id": str(tenant_id), "plan_id": str(request.plan_id), "type": "subscription_upgrade"},
        )

        return {
            "checkout_url": checkout_session["checkout_url"],
            "session_id": checkout_session["session_id"],
            "provider": "stripe",
        }


@router.post("/subscription/cancel")
async def cancel_subscription(
    immediate: bool = False, tenant_id: UUID = Depends(get_current_tenant_id), db: AsyncSession = Depends(get_async_db)
):
    """Cancel subscription with the payment provider and locally"""
    subscription_service = SubscriptionService(db)

    # Get the active subscription first
    subscription = await subscription_service.get_tenant_subscription(tenant_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="No active subscription found")

    # Cancel with the payment provider
    payment_provider = getattr(subscription, "payment_provider", None)

    if payment_provider == "paddle" and subscription.paddle_subscription_id:
        try:
            paddle_service = await PaddleService.create(db)
            effective_from = "immediately" if immediate else "next_billing_period"
            await paddle_service.cancel_subscription(subscription.paddle_subscription_id, effective_from=effective_from)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to cancel Paddle subscription: {str(e)}")
    elif subscription.stripe_subscription_id:
        try:
            stripe_service = await StripeService.create(db)
            await stripe_service.cancel_subscription(subscription.stripe_subscription_id, immediate=immediate)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to cancel Stripe subscription: {str(e)}")

    # Update local subscription status
    await subscription_service.cancel_subscription(subscription_id=subscription.id, immediate=immediate)

    return {"status": "cancelled", "immediate": immediate}


@router.post("/subscription/verify-checkout")
async def verify_checkout_session(
    session_id: str = Query(..., description="Stripe checkout session ID"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Verify a Stripe checkout session and create subscription if needed.
    This is useful when webhooks aren't configured or there's a delay.
    """
    stripe_service = await StripeService.create(db)

    try:
        success = await stripe_service.verify_checkout_session(session_id)
        if success:
            return {"status": "success", "message": "Checkout session verified and subscription created"}
        else:
            return {"status": "pending", "message": "Checkout session not yet completed"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


async def _invalidate_billing_cache_for_tenant(tenant_id: str) -> None:
    """Invalidate per-tenant billing cache keys."""
    try:
        redis = get_redis_async()
        if redis:
            await redis.delete(f"billing:subscription:{tenant_id}")
            await redis.delete(f"billing:balance:{tenant_id}")
    except Exception:
        pass


async def _invalidate_billing_cache_from_event(obj: dict) -> None:
    """Invalidate billing cache from a Stripe webhook object."""
    tenant_id = (obj.get("metadata") or {}).get("tenant_id")
    if tenant_id:
        await _invalidate_billing_cache_for_tenant(tenant_id)


async def _invalidate_billing_cache_from_paddle_event(data: dict) -> None:
    """Invalidate billing cache from a Paddle webhook data object."""
    tenant_id = (data.get("custom_data") or {}).get("tenant_id")
    if tenant_id:
        await _invalidate_billing_cache_for_tenant(tenant_id)


# Stripe Webhook
@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_async_db)):
    """Handle Stripe webhook events"""
    stripe_service = await StripeService.create(db)

    # Get webhook secret from integration config
    webhook_secret = await stripe_service._get_stripe_webhook_secret()
    if not webhook_secret:
        raise HTTPException(status_code=500, detail="Webhook secret not configured in integration configs")

    # Get request body and signature
    payload = await request.body()
    signature = request.headers.get("stripe-signature")

    if not signature:
        raise HTTPException(status_code=400, detail="Missing stripe-signature header")

    try:
        # Verify and construct event
        event = stripe_service.construct_webhook_event(
            payload=payload, signature=signature, webhook_secret=webhook_secret
        )

        # Handle the event
        success = await stripe_service.handle_webhook_event(event)

        if success:
            # Invalidate subscription/balance caches for affected tenant
            await _invalidate_billing_cache_from_event(event.get("data", {}).get("object", {}))
            return {"status": "success"}
        else:
            raise HTTPException(status_code=500, detail="Failed to handle webhook event")

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Paddle Webhook
@router.post("/webhook/paddle")
async def paddle_webhook(request: Request, db: AsyncSession = Depends(get_async_db)):
    """Handle Paddle webhook events"""
    import json

    try:
        paddle_service = await PaddleService.create(db)
    except ValueError:
        # Paddle not configured, return 200 to acknowledge receipt
        return {"status": "skipped", "message": "Paddle not configured"}

    # Get webhook secret
    webhook_secret = paddle_service._get_paddle_webhook_secret()

    # Get request body and signature
    payload = await request.body()
    signature = request.headers.get("paddle-signature", "")

    # Verify signature if webhook secret is configured
    if webhook_secret and signature:
        if not paddle_service.verify_webhook_signature(payload, signature):
            raise HTTPException(status_code=400, detail="Invalid webhook signature")

    try:
        # Parse the event
        event_data = json.loads(payload)
        event_type = event_data.get("event_type", "")
        data = event_data.get("data", {})

        # Handle the event
        success = await paddle_service.handle_webhook_event(event_type, data)

        if success:
            # Invalidate subscription/balance caches for affected tenant
            await _invalidate_billing_cache_from_paddle_event(data)
            return {"status": "success"}
        else:
            raise HTTPException(status_code=500, detail="Failed to handle webhook event")

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Payment Provider Configuration Endpoint
@router.get("/payment-provider/config", response_model=PaymentProviderConfigResponse)
async def get_payment_provider_config(db: AsyncSession = Depends(get_async_db)):
    """Get active payment provider configuration for frontend"""
    integration_service = IntegrationConfigService(db)

    # Check for Paddle first (preferred for MoR)
    paddle_config = await integration_service.get_active_config(None, "payment", "paddle")
    if paddle_config:
        config_data = integration_service._decrypt_config(paddle_config.config_data)
        credentials = config_data.get("credentials", {})
        settings = config_data.get("settings", {})
        return PaymentProviderConfigResponse(
            provider="paddle",
            client_token=credentials.get("client_side_token"),
            environment=settings.get("environment", "sandbox"),
            is_configured=True,
        )

    # Fall back to Stripe
    stripe_config = await integration_service.get_active_config(None, "payment", "stripe")
    if stripe_config:
        config_data = integration_service._decrypt_config(stripe_config.config_data)
        settings = config_data.get("settings", {})
        return PaymentProviderConfigResponse(
            provider="stripe",
            client_token=settings.get("publishable_key"),
            environment="live" if settings.get("publishable_key", "").startswith("pk_live") else "test",
            is_configured=True,
        )

    return PaymentProviderConfigResponse(
        provider="none",
        client_token=None,
        environment=None,
        is_configured=False,
    )


# Payment Method Management Endpoints


@router.post("/payment-methods/setup-intent")
async def create_setup_intent(
    tenant_id: UUID = Depends(get_current_tenant_id), db: AsyncSession = Depends(get_async_db)
):
    """Create a setup intent for adding payment method"""
    stripe_service = await StripeService.create(db)

    # Get or create Stripe customer
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Get or create customer
    customer_id = await stripe_service.get_or_create_customer(
        tenant_id=tenant_id,
        email=await _get_tenant_owner_email(db, tenant_id) or f"tenant-{tenant_id}@placeholder.invalid",
        name=tenant.name if tenant else None,
    )

    # Create setup intent
    setup_intent = await stripe_service.create_setup_intent(customer_id)

    return {"client_secret": setup_intent["client_secret"], "setup_intent_id": setup_intent["setup_intent_id"]}


@router.get("/payment-methods")
async def list_payment_methods(
    tenant_id: UUID = Depends(get_current_tenant_id), db: AsyncSession = Depends(get_async_db)
):
    """List saved payment methods"""
    stripe_service = await StripeService.create(db)

    # Get tenant
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Get customer ID from metadata
    if not tenant.metadata or "stripe_customer_id" not in tenant.metadata:
        return {"payment_methods": []}

    customer_id = tenant.metadata["stripe_customer_id"]

    # List payment methods
    payment_methods = await stripe_service.list_payment_methods(customer_id)

    return {"payment_methods": payment_methods}


@router.delete("/payment-methods/{payment_method_id}")
async def delete_payment_method(
    payment_method_id: str, tenant_id: UUID = Depends(get_current_tenant_id), db: AsyncSession = Depends(get_async_db)
):
    """Delete a payment method"""
    stripe_service = await StripeService.create(db)

    # Detach payment method
    success = await stripe_service.detach_payment_method(payment_method_id)

    return {"success": success}


@router.post("/payment-methods/{payment_method_id}/set-default")
async def set_default_payment_method(
    payment_method_id: str, tenant_id: UUID = Depends(get_current_tenant_id), db: AsyncSession = Depends(get_async_db)
):
    """Set default payment method"""
    stripe_service = await StripeService.create(db)

    # Get tenant
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Get customer ID
    if not tenant.metadata or "stripe_customer_id" not in tenant.metadata:
        raise HTTPException(status_code=400, detail="No Stripe customer found")

    customer_id = tenant.metadata["stripe_customer_id"]

    # Set default payment method
    success = await stripe_service.set_default_payment_method(customer_id, payment_method_id)

    return {"success": success}


# Usage Analytics Endpoints
@router.get("/usage/summary", response_model=UsageSummaryResponse)
async def get_usage_summary(
    start_date: date | None = None,
    end_date: date | None = None,
    agent_id: UUID | None = None,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Get usage summary for a period"""
    usage_service = UsageTrackingService(db)

    summary = await usage_service.get_usage_summary(
        tenant_id=tenant_id, start_date=start_date, end_date=end_date, agent_id=agent_id
    )

    return UsageSummaryResponse(**summary)


@router.get("/usage/trends")
async def get_usage_trends(
    days: int = Query(30, ge=1, le=365),
    agent_id: UUID | None = None,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Get daily usage trend"""
    usage_service = UsageTrackingService(db)

    trend = await usage_service.get_daily_usage_trend(tenant_id=tenant_id, days=days, agent_id=agent_id)

    return {"trend": trend}


@router.get("/usage/by-agent")
async def get_usage_by_agent(
    start_date: date | None = None,
    end_date: date | None = None,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Get usage breakdown by agent"""
    usage_service = UsageTrackingService(db)

    breakdown = await usage_service.get_agent_usage_breakdown(
        tenant_id=tenant_id, start_date=start_date, end_date=end_date
    )

    return {"breakdown": breakdown}


@router.get("/usage/by-action")
async def get_usage_by_action(
    start_date: date | None = None,
    end_date: date | None = None,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Get usage breakdown by action type"""
    usage_service = UsageTrackingService(db)

    breakdown = await usage_service.get_action_type_breakdown(
        tenant_id=tenant_id, start_date=start_date, end_date=end_date
    )

    return {"breakdown": breakdown}


@router.get("/usage/peak-times")
async def get_peak_usage_times(
    days: int = Query(7, ge=1, le=30),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Get peak usage times"""
    usage_service = UsageTrackingService(db)

    peak_times = await usage_service.get_peak_usage_times(tenant_id=tenant_id, days=days)

    return peak_times


@router.get("/usage/export")
async def export_usage_report(
    start_date: date | None = None,
    end_date: date | None = None,
    format: str = Query("json", pattern="^(json|csv)$"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Export usage report"""
    usage_service = UsageTrackingService(db)

    report = await usage_service.export_usage_report(
        tenant_id=tenant_id, start_date=start_date, end_date=end_date, format=format
    )

    return report


# ---------------------------------------------------------------------------
# LLM Cost Analytics Endpoints
# ---------------------------------------------------------------------------


def _parse_period(period: str) -> tuple[datetime, datetime]:
    """Parse a period string like '7d', '30d', '90d' into (start, end) UTC datetimes."""
    now = datetime.now(UTC)
    mapping = {"1d": 1, "7d": 7, "30d": 30, "90d": 90}
    days = mapping.get(period, 7)
    return now - timedelta(days=days), now


@router.get("/llm-cost/summary")
async def get_llm_cost_summary(
    period: str = Query("7d", pattern="^(1d|7d|30d|90d)$"),
    agent_id: UUID | None = None,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Total token counts and estimated cost for a time period."""
    from src.services.billing.llm_cost_service import get_cost_summary

    start, end = _parse_period(period)
    return await get_cost_summary(db, tenant_id, start, end, agent_id=agent_id)


@router.get("/llm-cost/by-model")
async def get_llm_cost_by_model(
    period: str = Query("7d", pattern="^(1d|7d|30d|90d)$"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Cost breakdown grouped by provider and model."""
    from src.services.billing.llm_cost_service import get_cost_by_model

    start, end = _parse_period(period)
    return await get_cost_by_model(db, tenant_id, start, end)


@router.get("/llm-cost/savings")
async def get_llm_cost_savings(
    period: str = Query("7d", pattern="^(1d|7d|30d|90d)$"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Savings estimate: cached token counts, response cache hits, batch calls."""
    from src.services.billing.llm_cost_service import get_savings_estimate

    start, end = _parse_period(period)
    return await get_savings_estimate(db, tenant_id, start, end)
