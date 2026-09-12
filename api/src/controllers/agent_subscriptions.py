"""Agent subscription endpoints — let emails subscribe to scheduled agent reports."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.models.agent import Agent
from src.models.agent_subscription import AgentSubscription

logger = logging.getLogger(__name__)

router = APIRouter()  # Auth-required routes (prefixed with /api/v1/agents)
public_router = APIRouter()  # Public routes (no prefix)


# --- Schemas ---


class SubscribeRequest(BaseModel):
    email: EmailStr


class SubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: UUID
    email: str
    is_active: bool


# --- Auth-required endpoints ---


@router.patch("/{agent_id}/subscriptions/toggle")
async def toggle_subscriptions(
    agent_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """Toggle allow_subscriptions on/off for an agent (owner only)."""
    result = await db.execute(select(Agent).filter(Agent.id == agent_id, Agent.tenant_id == tenant_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    agent.allow_subscriptions = not agent.allow_subscriptions
    await db.commit()
    await db.refresh(agent)

    logger.info(f"Agent {agent_id} allow_subscriptions set to {agent.allow_subscriptions}")
    return {"agent_id": str(agent_id), "allow_subscriptions": agent.allow_subscriptions}


@router.get("/{agent_id}/subscribers")
async def list_subscribers(
    agent_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: int = Depends(get_current_tenant_id),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List subscribers for an agent (owner only, paginated)."""
    result = await db.execute(select(Agent).filter(Agent.id == agent_id, Agent.tenant_id == tenant_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    from sqlalchemy import func

    count_result = await db.execute(
        select(func.count(AgentSubscription.id)).filter(AgentSubscription.agent_id == agent_id)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(AgentSubscription)
        .filter(AgentSubscription.agent_id == agent_id)
        .order_by(AgentSubscription.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    subs = result.scalars().all()
    return {
        "items": [SubscriptionResponse.model_validate(s) for s in subs],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.delete("/{agent_id}/subscribers/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscriber(
    agent_id: UUID,
    subscription_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """Remove a subscriber (owner only)."""
    result = await db.execute(select(Agent).filter(Agent.id == agent_id, Agent.tenant_id == tenant_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    result = await db.execute(
        select(AgentSubscription).filter(
            AgentSubscription.id == subscription_id, AgentSubscription.agent_id == agent_id
        )
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")

    await db.delete(sub)
    await db.commit()
    logger.info(f"Deleted subscription {subscription_id} for agent {agent_id}")


# --- Public endpoints ---


@public_router.post("/api/v1/agents/{agent_id}/subscribe", status_code=status.HTTP_201_CREATED)
async def subscribe(
    agent_id: UUID,
    body: SubscribeRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """Subscribe an email address to an agent's scheduled reports (public)."""
    result = await db.execute(select(Agent).filter(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    if not agent.allow_subscriptions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Subscriptions are disabled for this agent")

    # Check for existing subscription
    result = await db.execute(
        select(AgentSubscription).filter(AgentSubscription.agent_id == agent_id, AgentSubscription.email == body.email)
    )
    existing = result.scalar_one_or_none()

    if existing:
        if existing.is_active:
            return {"message": "Already subscribed"}
        # Re-activate
        existing.is_active = True
        await db.commit()
        return {"message": "Subscription reactivated"}

    sub = AgentSubscription(agent_id=agent_id, email=body.email)
    db.add(sub)
    await db.commit()
    logger.info(f"New subscription: {body.email} -> agent {agent_id}")
    return {"message": "Subscribed successfully"}


@public_router.get("/unsubscribe", response_class=HTMLResponse)
async def unsubscribe(token: str, db: AsyncSession = Depends(get_async_db)):
    """Unsubscribe via token link (public). Sets is_active=False."""
    try:
        token_uuid = UUID(token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")

    result = await db.execute(select(AgentSubscription).filter(AgentSubscription.unsubscribe_token == token_uuid))
    sub = result.scalar_one_or_none()

    if not sub:
        return HTMLResponse(
            content="<html><body><p>Subscription not found.</p></body></html>",
            status_code=404,
        )

    sub.is_active = False
    await db.commit()
    logger.info(f"Unsubscribed {sub.email} from agent {sub.agent_id} via token")

    return HTMLResponse(
        content=(
            "<html><body style='font-family:sans-serif;max-width:480px;margin:60px auto;text-align:center'>"
            "<h2>Unsubscribed</h2>"
            f"<p>You have been unsubscribed from agent reports for <strong>{sub.email}</strong>.</p>"
            "</body></html>"
        )
    )
