"""Agent monetisation purchase endpoints.

Provides two routers:
  router       — auth-required: credit-based subscription purchase
  public_router — no auth: Stripe guest checkout + token retrieval
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.redis import get_redis_async
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.models.agent import Agent
from src.services.billing.agent_user_subscription_service import AgentUserSubscriptionService

logger = logging.getLogger(__name__)

router = APIRouter()  # Mounted at /api/v1/agents
public_router = APIRouter()  # Mounted at /api/public


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SubscribeRequest(BaseModel):
    pricing_id: UUID
    tier: str
    discount_code: str | None = None


class GuestCheckoutRequest(BaseModel):
    pricing_id: UUID
    tier: str
    guest_email: EmailStr
    success_url: str
    cancel_url: str


# ---------------------------------------------------------------------------
# Auth-required: credit-based subscription
# ---------------------------------------------------------------------------


@router.post("/{agent_slug}/purchase-access")
async def subscribe_with_credits(
    agent_slug: str,
    body: SubscribeRequest,
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Subscribe to a paid agent using platform credits."""
    agent_result = await db.execute(select(Agent).where(Agent.slug == agent_slug))
    agent = agent_result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    try:
        sub = await AgentUserSubscriptionService.subscribe_account_user(
            agent_id=agent.id,
            pricing_id=body.pricing_id,
            subscriber_tenant_id=tenant_id,
            tier=body.tier,
            db=db,
            discount_code=body.discount_code,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {
        "subscription": {
            "id": str(sub.id),
            "pricing_tier": sub.pricing_tier,
            "status": sub.status,
            "started_at": sub.started_at.isoformat(),
            "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
        }
    }


# ---------------------------------------------------------------------------
# Public: Stripe guest checkout
# ---------------------------------------------------------------------------


@public_router.post("/api/public/agents/{agent_slug}/checkout")
async def create_guest_checkout(
    agent_slug: str,
    body: GuestCheckoutRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """Create a Stripe Checkout session for guest agent access."""
    agent_result = await db.execute(select(Agent).where(Agent.slug == agent_slug))
    agent = agent_result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    try:
        checkout_url = await AgentUserSubscriptionService.create_stripe_checkout_session(
            agent_id=agent.id,
            pricing_id=body.pricing_id,
            tier=body.tier,
            guest_email=body.guest_email,
            success_url=body.success_url,
            cancel_url=body.cancel_url,
            db=db,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Stripe checkout session creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe is not configured or unavailable",
        )

    return {"checkout_url": checkout_url}


@public_router.get("/api/public/agents/checkout/token")
async def get_guest_token(session_id: str):
    """Retrieve the one-time guest access token after Stripe checkout completes.

    Called by the frontend when the user lands on success_url.
    The token is consumed on first read (getdel) and expires after 10 minutes.
    """
    try:
        redis = get_redis_async()
        raw_token = await redis.getdel(f"agent_token:{session_id}")
    except Exception as e:
        logger.error(f"Redis error retrieving guest token: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Token service unavailable",
        )

    if raw_token is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found or already retrieved. Please complete checkout again.",
        )

    return {"agent_access_token": raw_token}
