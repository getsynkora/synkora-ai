"""Human Handoff API — full lifecycle management.

Endpoints:
    GET  /conversations/handoffs                         list handoffs (filterable, paginated)
    GET  /conversations/{id}/handoff                     single handoff detail + full messages
    POST /conversations/{id}/handoff/reply               operator sends message to customer
    POST /conversations/{id}/handoff/resolve             resolve / hand back to AI
    POST /conversations/{id}/handoff/reopen              reopen a resolved handoff
    POST /conversations/{id}/handoff/assign              assign to operator (sets metadata)
    GET  /conversations/{id}/messages                    full message history for a conversation
"""

import logging
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id
from src.models.agent import Agent
from src.models.conversation import Conversation
from src.models.message import Message, MessageRole, MessageStatus

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Pydantic bodies
# ---------------------------------------------------------------------------


class HandoffReplyBody(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)


class HandoffAssignBody(BaseModel):
    operator_id: str = Field(..., min_length=1, max_length=255)
    operator_name: str | None = Field(None, max_length=255)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_conversation_for_tenant(
    conversation_id: uuid.UUID,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> Conversation:
    """Load conversation and verify it belongs to the tenant via its agent."""
    result = await db.execute(select(Conversation).filter(Conversation.id == conversation_id))
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    if not conv.agent_id:
        # Conversations without an agent cannot be scoped to a tenant — deny access.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    agent_result = await db.execute(select(Agent).filter(Agent.id == conv.agent_id, Agent.tenant_id == tenant_id))
    if not agent_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    return conv


def _serialize_message(m: Message) -> dict:
    return {
        "id": str(m.id),
        "role": m.role.value if hasattr(m.role, "value") else str(m.role),
        "content": m.content or "",
        "status": m.status.value if hasattr(m.status, "value") else str(m.status),
        "metadata": m.message_metadata or {},
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


def _serialize_conversation(c: Conversation, messages: list[Message] | None = None) -> dict:
    data: dict = {
        "id": str(c.id),
        "agent_id": str(c.agent_id) if c.agent_id else None,
        "name": c.name,
        "handoff_status": c.handoff_status,
        "handoff_at": c.handoff_at.isoformat() if c.handoff_at else None,
        "handoff_summary": c.handoff_summary,
        "source": c.source,
        "external_user_id": c.external_user_id,
        "external_user_name": c.external_user_name,
        "external_user_email": c.external_user_email,
        "external_user_phone": c.external_user_phone,
        "message_count": c.message_count,
        "last_activity_at": c.last_activity_at.isoformat() if c.last_activity_at else None,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }
    if messages is not None:
        data["messages"] = [_serialize_message(m) for m in messages]
    return data


async def _broadcast(event_type: str, payload: dict) -> None:
    try:
        from src.core.websocket import connection_manager

        await connection_manager.broadcast({"type": event_type, "data": payload})
    except Exception as exc:
        logger.warning("WebSocket broadcast failed (%s): %s", event_type, exc)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/conversations/handoffs", status_code=status.HTTP_200_OK)
async def list_handoffs(
    handoff_status: Literal["active", "resolved", "all"] = Query("active", alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List handoffs for the tenant.

    Query params:
        status:    active | resolved | all  (default: active)
        page:      page number (default: 1)
        page_size: results per page (default: 20, max: 100)
    """
    base_q = select(Conversation).join(Agent, Agent.id == Conversation.agent_id).filter(Agent.tenant_id == tenant_id)

    if handoff_status != "all":
        base_q = base_q.filter(Conversation.handoff_status == handoff_status)
    else:
        base_q = base_q.filter(Conversation.handoff_status.in_(["active", "resolved"]))

    # Total count
    count_result = await db.execute(select(func.count()).select_from(base_q.subquery()))
    total = count_result.scalar_one()

    # Paginated data with recent messages included
    offset = (page - 1) * page_size
    result = await db.execute(
        base_q.options(selectinload(Conversation.messages))
        .order_by(Conversation.handoff_at.desc().nullslast())
        .offset(offset)
        .limit(page_size)
    )
    convs = result.scalars().all()

    items = []
    for c in convs:
        # Include last 10 messages inline so callers can preview the conversation
        sorted_msgs = sorted(c.messages or [], key=lambda m: m.created_at or 0)
        items.append(_serialize_conversation(c, messages=sorted_msgs[-10:]))

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, -(-total // page_size)),  # ceiling division
    }


@router.get("/conversations/{conversation_id}/handoff", status_code=status.HTTP_200_OK)
async def get_handoff_detail(
    conversation_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get full detail for a single handoff conversation, including all messages.
    """
    result = await db.execute(
        select(Conversation).options(selectinload(Conversation.messages)).filter(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    # Tenant check
    if not conv.agent_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    agent_result = await db.execute(select(Agent).filter(Agent.id == conv.agent_id, Agent.tenant_id == tenant_id))
    if not agent_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    if conv.handoff_status == "none":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This conversation has not been handed off",
        )

    sorted_msgs = sorted(conv.messages or [], key=lambda m: m.created_at or 0)
    return _serialize_conversation(conv, messages=sorted_msgs)


@router.get("/conversations/{conversation_id}/messages", status_code=status.HTTP_200_OK)
async def get_conversation_messages(
    conversation_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get paginated message history for any conversation (not just handoffs).
    Useful for operators reviewing the full chat before responding.
    """
    conv = await _get_conversation_for_tenant(conversation_id, tenant_id, db)

    count_result = await db.execute(select(func.count()).where(Message.conversation_id == conv.id))
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    msg_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at.asc())
        .offset(offset)
        .limit(page_size)
    )
    messages = msg_result.scalars().all()

    return {
        "conversation_id": str(conv.id),
        "handoff_status": conv.handoff_status,
        "external_user_name": conv.external_user_name,
        "external_user_email": conv.external_user_email,
        "messages": [_serialize_message(m) for m in messages],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, -(-total // page_size)),
    }


@router.post("/conversations/{conversation_id}/handoff/reply", status_code=status.HTTP_200_OK)
async def handoff_reply(
    conversation_id: uuid.UUID,
    body: HandoffReplyBody,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Send an operator message into a handed-off conversation.
    The message is persisted and broadcast via WebSocket so the widget / Flutter
    client receives it in real time.
    """
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

    await _broadcast(
        "operator_message",
        {
            "conversation_id": str(conversation_id),
            "message_id": str(msg.id),
            "content": body.message,
            "role": "operator",
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        },
    )

    return _serialize_message(msg)


@router.post("/conversations/{conversation_id}/handoff/resolve", status_code=status.HTTP_200_OK)
async def handoff_resolve(
    conversation_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Resolve an active handoff — marks it resolved and resumes AI handling.
    A system message is added so the customer sees the transition.
    """
    conv = await _get_conversation_for_tenant(conversation_id, tenant_id, db)

    if conv.handoff_status not in ("active", "resolved"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conversation is not in a handoff",
        )

    conv.handoff_status = "resolved"

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

    await _broadcast(
        "handoff_resolved",
        {
            "conversation_id": str(conversation_id),
            "resume_message": _serialize_message(resume_msg),
        },
    )

    return {"status": "resolved", "conversation_id": str(conversation_id)}


@router.post("/conversations/{conversation_id}/handoff/reopen", status_code=status.HTTP_200_OK)
async def handoff_reopen(
    conversation_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Reopen a resolved handoff back to active.
    Useful when a customer replies after resolution and the operator wants to
    take back control before letting the AI respond.
    """
    conv = await _get_conversation_for_tenant(conversation_id, tenant_id, db)

    if conv.handoff_status != "resolved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only resolved handoffs can be reopened",
        )

    from datetime import UTC, datetime

    conv.handoff_status = "active"
    conv.handoff_at = datetime.now(UTC)

    reopen_msg = Message(
        conversation_id=conversation_id,
        role=MessageRole.OPERATOR,
        content="The support agent has rejoined the conversation.",
        status=MessageStatus.COMPLETED,
        message_metadata={"source": "handoff_reopened"},
    )
    db.add(reopen_msg)
    conv.increment_message_count()
    await db.commit()
    await db.refresh(reopen_msg)

    await _broadcast(
        "handoff_reopened",
        {
            "conversation_id": str(conversation_id),
            "message": _serialize_message(reopen_msg),
        },
    )

    return {"status": "active", "conversation_id": str(conversation_id)}


@router.post("/conversations/{conversation_id}/handoff/assign", status_code=status.HTTP_200_OK)
async def handoff_assign(
    conversation_id: uuid.UUID,
    body: HandoffAssignBody,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Assign a handoff conversation to a specific operator.
    Stores operator info in the conversation metadata and broadcasts the assignment.
    """
    conv = await _get_conversation_for_tenant(conversation_id, tenant_id, db)

    if conv.handoff_status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only active handoffs can be assigned",
        )

    # Record assignment as a system message so it is visible in the history
    label = body.operator_name or body.operator_id
    assign_msg = Message(
        conversation_id=conversation_id,
        role=MessageRole.OPERATOR,
        content=f"Conversation assigned to {label}.",
        status=MessageStatus.COMPLETED,
        message_metadata={
            "source": "handoff_assigned",
            "operator_id": body.operator_id,
            "operator_name": body.operator_name,
        },
    )
    db.add(assign_msg)
    conv.increment_message_count()
    await db.commit()
    await db.refresh(assign_msg)

    await _broadcast(
        "handoff_assigned",
        {
            "conversation_id": str(conversation_id),
            "operator_id": body.operator_id,
            "operator_name": body.operator_name,
        },
    )

    return {
        "conversation_id": str(conversation_id),
        "assigned_operator_id": body.operator_id,
        "assigned_operator_name": body.operator_name,
    }
