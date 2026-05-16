"""Agent user subscription endpoints — manage paid chat/email access."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.models.agent import Agent
from src.models.agent_user_subscription import AgentUserSubscription, SubscriptionAccessStatus
from src.services.billing.agent_user_subscription_service import AgentUserSubscriptionService

logger = logging.getLogger(__name__)

router = APIRouter()  # Auth: prefix /api/v1


class CancelSubscriptionRequest(BaseModel):
    pass


@router.get("/my/agent-subscriptions")
async def list_my_subscriptions(
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """List all agent subscriptions for the current user."""
    result = await db.execute(
        select(AgentUserSubscription)
        .where(AgentUserSubscription.subscriber_tenant_id == tenant_id)
        .order_by(AgentUserSubscription.created_at.desc())
        .limit(100)
    )
    subs = result.scalars().all()
    return {"subscriptions": [s.__dict__ for s in subs]}


@router.delete("/my/agent-subscriptions/{sub_id}")
async def cancel_my_subscription(
    sub_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Cancel an active agent subscription."""
    try:
        sub = await AgentUserSubscriptionService.cancel_subscription(
            sub_id=sub_id,
            db=db,
            subscriber_tenant_id=tenant_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"cancelled": True, "subscription_id": str(sub.id)}


@router.get("/agents/{agent_slug}/paid-subscribers")
async def list_agent_paid_subscribers(
    agent_slug: str,
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """List subscribers for an agent (owner only)."""
    agent_result = await db.execute(select(Agent).where(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
    agent = agent_result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    result = await db.execute(
        select(AgentUserSubscription)
        .where(
            AgentUserSubscription.agent_id == agent.id,
            AgentUserSubscription.status == SubscriptionAccessStatus.ACTIVE,
        )
        .order_by(AgentUserSubscription.created_at.desc())
        .limit(500)
    )
    subs = result.scalars().all()

    # Mask guest tokens for privacy
    return {
        "subscribers": [
            {
                "id": str(s.id),
                "pricing_tier": s.pricing_tier,
                "status": s.status,
                "started_at": s.started_at,
                "expires_at": s.expires_at,
                "is_guest": s.subscriber_tenant_id is None,
                "guest_email": s.guest_email,
            }
            for s in subs
        ]
    }
