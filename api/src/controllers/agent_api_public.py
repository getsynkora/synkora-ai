"""
Public Agent API Controller - External API for agent interactions with Advanced Security.

CRITICAL: All chat interactions are protected with prompt injection scanning.
"""

import json
import logging
import uuid as uuid_lib
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.agent_api_auth import require_permission
from src.models.agent import Agent
from src.models.agent_api_key import AgentApiKey
from src.models.conversation import Conversation
from src.models.message import Message
from src.schemas.agent_api import (
    AgentInfo,
    AgentListResponse,
    ChatRequest,
    ConversationInfo,
    ConversationListResponse,
)
from src.services.security.advanced_prompt_scanner import advanced_prompt_scanner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/public", tags=["Public Agent API"])


@router.post("/agents/{agent_id}/chat/stream")
async def chat_with_agent_stream(
    agent_id: UUID,
    request: ChatRequest,
    http_request: Request,
    api_key: AgentApiKey = Depends(require_permission("chat")),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Stream agent responses in real-time using Server-Sent Events (SSE) with prompt injection protection.

    Requires permission: chat
    CRITICAL: All messages are scanned for prompt injection before processing.
    """
    # Verify agent exists and belongs to tenant
    result = await db.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.tenant_id == api_key.tenant_id,
        )
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Check if API key is scoped to a specific agent
    if api_key.agent_id and api_key.agent_id != agent_id:
        raise HTTPException(status_code=403, detail="API key not authorized for this agent")

    # CRITICAL: Scan message for prompt injection before processing
    client_ip = http_request.client.host if http_request.client else "unknown"
    user_agent = http_request.headers.get("User-Agent", "unknown")

    scan_result = await advanced_prompt_scanner.scan_comprehensive_async(
        text=request.message, user_id=f"api_key_{api_key.id}", ip_address=client_ip, context="agent_api_chat"
    )

    # Block if threat detected
    if not scan_result["is_safe"]:
        # Log security violation
        logger.warning(
            f"SECURITY: Prompt injection blocked in Agent API chat. "
            f"Agent: {agent.agent_name}, API Key: {api_key.id}, "
            f"Risk Score: {scan_result['risk_score']}, "
            f"Threat Level: {scan_result['threat_level']}, "
            f"IP: {client_ip}, User-Agent: {user_agent[:100]}"
        )

        # Return security block response as stream
        async def generate_security_block():
            """Generate security block message stream."""
            security_response = {
                "type": "error",
                "content": "Message blocked due to security policy violations. Please rephrase your request.",
                "error_type": "security_violation",
                "violation_id": f"API_{uuid_lib.uuid4().hex[:8]}",
                "risk_score": scan_result["risk_score"],
                "detections": len(scan_result["detections"]),
            }
            yield f"data: {json.dumps(security_response)}\n\n"

        return StreamingResponse(
            generate_security_block(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "X-Security-Status": "blocked",
                "X-Threat-Level": scan_result["threat_level"],
            },
        )

    # Get or create conversation
    if request.conversation_id:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == request.conversation_id,
                Conversation.agent_id == agent_id,
            )
        )
        conversation = result.scalar_one_or_none()

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = Conversation(
            agent_id=agent_id,
            name=f"API Chat Stream - {datetime.now(UTC).strftime('%Y-%m-%d %H:%M')}",
        )
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)

    from src.controllers.agents.chat import chat_stream_service
    from src.services.conversation_service import ConversationService

    # Load conversation history
    conversation_history = await ConversationService.get_conversation_history_cached(
        db=db,
        conversation_id=conversation.id,
        limit=30,
    )

    agent_name = agent.agent_name
    tenant_id = api_key.tenant_id
    conversation_id = str(conversation.id)

    await db.close()

    return StreamingResponse(
        chat_stream_service.stream_agent_response(
            agent_name=agent_name,
            message=request.message,
            conversation_history=conversation_history,
            conversation_id=conversation_id,
            attachments=None,
            llm_config_id=None,
            db=None,
            tenant_id=tenant_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Security-Status": "validated",
            "X-Risk-Score": str(scan_result["risk_score"]),
        },
    )


@router.get("/agents", response_model=AgentListResponse)
async def list_agents(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    api_key: AgentApiKey = Depends(require_permission("read")),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List all available agents for the tenant.

    Requires permission: read
    """
    # If API key is scoped to specific agent, only return that agent
    if api_key.agent_id:
        result = await db.execute(
            select(Agent).where(
                Agent.id == api_key.agent_id,
                Agent.tenant_id == api_key.tenant_id,
            )
        )
        agents = [result.scalar_one_or_none()]
        agents = [a for a in agents if a is not None]
    else:
        result = await db.execute(select(Agent).where(Agent.tenant_id == api_key.tenant_id).limit(limit).offset(offset))
        agents = result.scalars().all()

    agent_list = [
        AgentInfo(
            id=agent.id,
            name=agent.agent_name,
            description=agent.description,
            model=agent.llm_config.get("model", "unknown"),
            capabilities=[],
        )
        for agent in agents
    ]

    return AgentListResponse(agents=agent_list, total=len(agent_list))


@router.get("/agents/{agent_id}", response_model=AgentInfo)
async def get_agent(
    agent_id: UUID,
    api_key: AgentApiKey = Depends(require_permission("read")),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get detailed information about a specific agent.

    Requires permission: read
    """
    # Check if API key is scoped to a specific agent
    if api_key.agent_id and api_key.agent_id != agent_id:
        raise HTTPException(status_code=403, detail="API key not authorized for this agent")

    result = await db.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.tenant_id == api_key.tenant_id,
        )
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return AgentInfo(
        id=agent.id,
        name=agent.agent_name,
        description=agent.description,
        model=agent.llm_config.get("model", "unknown"),
        capabilities=[],
    )


@router.get("/agents/{agent_id}/conversations", response_model=ConversationListResponse)
async def list_conversations(
    agent_id: UUID,
    limit: int = 50,
    offset: int = 0,
    api_key: AgentApiKey = Depends(require_permission("read")),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List conversations for a specific agent.

    Requires permission: read
    """
    # Check if API key is scoped to a specific agent
    if api_key.agent_id and api_key.agent_id != agent_id:
        raise HTTPException(status_code=403, detail="API key not authorized for this agent")

    # Verify agent exists
    result = await db.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.tenant_id == api_key.tenant_id,
        )
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Get conversations.
    # Tenant isolation is already enforced above: the Agent must belong to
    # api_key.tenant_id before this point is reached, so filtering by
    # agent_id is sufficient to scope results to the correct tenant.
    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.agent_id == agent_id,
            Conversation.agent_id == api_key.agent_id,  # SECURITY: caller scope — key must own this agent
        )
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    conversations = result.scalars().all()

    # Get total count
    count_result = await db.execute(
        select(func.count(Conversation.id)).where(
            Conversation.agent_id == agent_id,
            Conversation.agent_id == api_key.agent_id,  # SECURITY: caller scope
        )
    )
    total = count_result.scalar()

    # Batch-fetch message counts in a single query to avoid N+1
    conv_ids = [conv.id for conv in conversations]
    counts_by_conv: dict[UUID, int] = {}
    if conv_ids:
        counts_result = await db.execute(
            select(Message.conversation_id, func.count(Message.id))
            .where(Message.conversation_id.in_(conv_ids))
            .group_by(Message.conversation_id)
        )
        counts_by_conv = {row[0]: row[1] for row in counts_result.all()}

    conversation_list = [
        ConversationInfo(
            id=conv.id,
            agent_id=conv.agent_id,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=counts_by_conv.get(conv.id, 0),
        )
        for conv in conversations
    ]

    return ConversationListResponse(conversations=conversation_list, total=total)


@router.get("/agents/{agent_id}/conversations/{conversation_id}")
async def get_conversation(
    agent_id: UUID,
    conversation_id: UUID,
    message_limit: int = Query(200, ge=1, le=1000),
    message_offset: int = Query(0, ge=0),
    api_key: AgentApiKey = Depends(require_permission("read")),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get a specific conversation with its messages.

    Requires permission: read
    """
    # Check if API key is scoped to a specific agent
    if api_key.agent_id and api_key.agent_id != agent_id:
        raise HTTPException(status_code=403, detail="API key not authorized for this agent")

    # Get conversation
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.agent_id == agent_id,
        )
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get messages with pagination to prevent loading entire conversation history into memory
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .limit(message_limit)
        .offset(message_offset)
    )
    messages = result.scalars().all()

    return {
        "id": conversation.id,
        "agent_id": conversation.agent_id,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
        "messages": [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at,
            }
            for msg in messages
        ],
    }


@router.delete("/agents/{agent_id}/conversations/{conversation_id}")
async def delete_conversation(
    agent_id: UUID,
    conversation_id: UUID,
    api_key: AgentApiKey = Depends(require_permission("write")),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Delete a conversation.

    Requires permission: write
    """
    # Check if API key is scoped to a specific agent
    if api_key.agent_id and api_key.agent_id != agent_id:
        raise HTTPException(status_code=403, detail="API key not authorized for this agent")

    # Get conversation
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.agent_id == agent_id,
        )
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Delete conversation (cascade will delete messages)
    await db.delete(conversation)
    await db.commit()

    return {"message": "Conversation deleted successfully"}
