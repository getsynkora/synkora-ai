"""Human Handoff API endpoints."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id
from src.models.agent import Agent
from src.models.conversation import Conversation
from src.models.message import Message, MessageRole, MessageStatus

logger = logging.getLogger(__name__)

router = APIRouter()


class HandoffReplyBody(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)


async def _get_conversation_for_tenant(
    conversation_id: uuid.UUID,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> Conversation:
    """Load conversation and verify it belongs to tenant via agent."""
    result = await db.execute(select(Conversation).filter(Conversation.id == conversation_id))
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    # Verify tenant ownership via agent
    if conv.agent_id:
        agent_result = await db.execute(select(Agent).filter(Agent.id == conv.agent_id, Agent.tenant_id == tenant_id))
        if not agent_result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    return conv


@router.post("/conversations/{conversation_id}/handoff/reply", status_code=status.HTTP_200_OK)
async def handoff_reply(
    conversation_id: uuid.UUID,
    body: HandoffReplyBody,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Send an operator reply to a handed-off conversation."""
    conv = await _get_conversation_for_tenant(conversation_id, tenant_id, db)

    if conv.handoff_status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conversation is not in an active handoff",
        )

    msg = Message(
        conversation_id=conversation_id,
        role=MessageRole.OPERATOR,
        content=body.message,
        status=MessageStatus.COMPLETED,
        message_metadata={"source": "operator_handoff"},
    )
    db.add(msg)
    conv.increment_message_count()
    await db.commit()
    await db.refresh(msg)

    # Broadcast operator message via WebSocket so the widget/Flutter gets it in real time
    try:
        from src.core.websocket import connection_manager

        await connection_manager.broadcast(
            {
                "type": "operator_message",
                "data": {
                    "conversation_id": str(conversation_id),
                    "message_id": str(msg.id),
                    "content": body.message,
                    "created_at": msg.created_at.isoformat() if msg.created_at else None,
                },
            }
        )
    except Exception as exc:
        logger.warning(f"Failed to broadcast operator message: {exc}")

    return {"id": str(msg.id), "content": body.message, "role": "operator"}


@router.post("/conversations/{conversation_id}/handoff/resolve", status_code=status.HTTP_200_OK)
async def handoff_resolve(
    conversation_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """End an active handoff — AI resumes the conversation."""
    conv = await _get_conversation_for_tenant(conversation_id, tenant_id, db)

    if conv.handoff_status not in ("active", "resolved"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conversation is not in a handoff",
        )

    conv.handoff_status = "resolved"

    # Save AI resumption message so it appears in the user's chat
    resume_msg = Message(
        conversation_id=conversation_id,
        role=MessageRole.ASSISTANT,
        content="I'm back! The support agent has resolved your request. How can I continue helping you?",
        status=MessageStatus.COMPLETED,
        message_metadata={"source": "handoff_resolved"},
    )
    db.add(resume_msg)
    conv.increment_message_count()
    await db.commit()
    await db.refresh(resume_msg)

    # Broadcast handoff_resolved and the resume message via WebSocket
    try:
        from src.core.websocket import connection_manager

        await connection_manager.broadcast(
            {
                "type": "handoff_resolved",
                "data": {
                    "conversation_id": str(conversation_id),
                    "resume_message": {
                        "id": str(resume_msg.id),
                        "role": "assistant",
                        "content": resume_msg.content,
                        "created_at": resume_msg.created_at.isoformat() if resume_msg.created_at else None,
                    },
                },
            }
        )
    except Exception as exc:
        logger.warning(f"Failed to broadcast handoff_resolved: {exc}")

    return {"status": "resolved", "conversation_id": str(conversation_id)}


@router.get("/conversations/handoffs", status_code=status.HTTP_200_OK)
async def list_active_handoffs(
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """List all active handoffs for the tenant (conversations with handoff_status='active')."""
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Conversation)
        .join(Agent, Agent.id == Conversation.agent_id)
        .filter(
            Agent.tenant_id == tenant_id,
            Conversation.handoff_status == "active",
        )
        .options(selectinload(Conversation.messages))
        .order_by(Conversation.handoff_at.desc().nullslast())
        .limit(50)
    )
    convs = result.scalars().all()

    return [
        {
            "id": str(c.id),
            "agent_id": str(c.agent_id) if c.agent_id else None,
            "name": c.name,
            "handoff_status": c.handoff_status,
            "handoff_at": c.handoff_at.isoformat() if c.handoff_at else None,
            "handoff_summary": c.handoff_summary,
            "source": c.source,
            "external_user_name": c.external_user_name,
            "external_user_email": c.external_user_email,
            "message_count": c.message_count,
            "last_activity_at": c.last_activity_at.isoformat() if c.last_activity_at else None,
        }
        for c in convs
    ]
