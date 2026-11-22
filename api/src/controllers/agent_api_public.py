"""
Public Agent API Controller - External API for agent interactions with Advanced Security.

CRITICAL: All chat interactions are protected with prompt injection scanning.
"""

import hashlib
import hmac
import json
import logging
import uuid as uuid_lib
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
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
    ChatResponse,
    ConversationInfo,
    ConversationListResponse,
    CreateConversationRequest,
    MessageFeedbackRequest,
)
from src.services.security.advanced_prompt_scanner import advanced_prompt_scanner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/public", tags=["Public Agent API"])


MAX_ATTACHMENTS = 5
MAX_ATTACHMENT_TEXT = 100_000


class _SecurityBlocked(Exception):
    def __init__(self, scan_result: dict):
        self.scan_result = scan_result


@dataclass
class _PreparedChat:
    agent_name: str
    message: str
    tenant_id: UUID
    conversation_id: str
    history: list
    attachments: list[dict] | None
    scan_result: dict


def _conversation_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Conversation not found")


def _owned_by(conversation: Conversation, external_user_id: str | None) -> bool:
    """A conversation belongs to the end user it was created for (or to nobody, when none was given)."""
    return conversation.external_user_id == external_user_id


async def _load_agent(db: AsyncSession, api_key: AgentApiKey, agent_id: UUID) -> Agent:
    result = await db.execute(select(Agent).where(Agent.id == agent_id, Agent.tenant_id == api_key.tenant_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if api_key.agent_id and api_key.agent_id != agent_id:
        raise HTTPException(status_code=403, detail="API key not authorized for this agent")
    return agent


async def _load_conversation(
    db: AsyncSession, agent_id: UUID, conversation_id: UUID, external_user_id: str | None = None, strict: bool = False
) -> Conversation:
    """
    Load a conversation of this agent. With ``external_user_id`` the conversation must belong to that
    end user. ``strict`` also requires a match when no id is given, so a chat can never continue
    another user's conversation by leaving the id out.
    """
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.agent_id == agent_id)
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise _conversation_not_found()
    if (strict or external_user_id is not None) and not _owned_by(conversation, external_user_id):
        raise _conversation_not_found()
    return conversation


async def _precheck_billing(db: AsyncSession, api_key: AgentApiKey, agent: Agent, conversation_id: UUID | None):
    """Same subscription, allowance and credit checks the dashboard chat applies, as an HTTP 402."""
    from src.services.billing import ChatBillingService

    config = next((c for c in (agent.llm_configs or []) if c.is_default and c.enabled), None)
    model_name = config.model_name if config else (agent.llm_config or {}).get("model_name", "")
    result = await ChatBillingService(db).validate_chat_request(
        tenant_id=api_key.tenant_id,
        model_name=model_name,
        conversation_id=conversation_id,
        quota_pool=agent.quota_pool,
    )
    if not result.is_valid:
        raise HTTPException(
            status_code=402,
            detail={
                "error_code": result.error.error_code.value,
                "message": result.error.message,
                "details": result.error.details or {},
            },
        )


ATTACHMENT_FIELDS = (
    "file_id",
    "file_name",
    "file_type",
    "file_size",
    "file_url",
    "download_url",
    "thumbnail_url",
    "uploaded_at",
    "extracted_text",
)


def _attachment_signature(attachment: dict, tenant_id: UUID, conversation_id: UUID) -> str:
    """
    Server-side proof that this exact attachment, every field that reaches the model, was produced by an upload
    to this conversation. The signed text is a canonical JSON object, so fields cannot shift into each other,
    and a fixed label keeps the key from being reused for anything else.
    """
    payload = json.dumps(
        {
            "tenant": str(tenant_id),
            "conversation": str(conversation_id),
            **{field: attachment.get(field) for field in ATTACHMENT_FIELDS},
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    label = b"synkora.attachment.v1|"
    return hmac.new(settings.secret_key.encode(), label + payload.encode(), hashlib.sha256).hexdigest()


def _validate_attachments(attachments: list[dict] | None, tenant_id: UUID, conversation_id: UUID | None):
    """Accept only files returned by the attachments endpoint for this conversation, unchanged."""
    if not attachments:
        return None
    if conversation_id is None:
        raise HTTPException(status_code=400, detail="Attachments need a conversation_id: create a conversation first")
    if len(attachments) > MAX_ATTACHMENTS:
        raise HTTPException(status_code=400, detail=f"At most {MAX_ATTACHMENTS} attachments per message")
    clean = []
    for attachment in attachments:
        given = str(attachment.get("signature") or "")
        expected = _attachment_signature(attachment, tenant_id, conversation_id)
        if not hmac.compare_digest(given, expected):
            raise HTTPException(
                status_code=400, detail="Attachment was not uploaded to this conversation or was changed"
            )
        item = {field: attachment.get(field) for field in ATTACHMENT_FIELDS}
        item["extracted_text"] = str(attachment.get("extracted_text") or "")[:MAX_ATTACHMENT_TEXT]
        clean.append(item)
    return clean


async def _prepare_chat(
    agent_id: UUID, request: ChatRequest, http_request: Request, api_key: AgentApiKey, db: AsyncSession
) -> _PreparedChat:
    """Everything both chat endpoints do before the agent runs."""
    agent = await _load_agent(db, api_key, agent_id)

    client_ip = http_request.client.host if http_request.client else "unknown"
    user_agent = http_request.headers.get("User-Agent", "unknown")
    scan_result = await advanced_prompt_scanner.scan_comprehensive_async(
        text=request.message, user_id=f"api_key_{api_key.id}", ip_address=client_ip, context="agent_api_chat"
    )
    if not scan_result["is_safe"]:
        logger.warning(
            f"SECURITY: Prompt injection blocked in Agent API chat. "
            f"Agent: {agent.agent_name}, API Key: {api_key.id}, "
            f"Risk Score: {scan_result['risk_score']}, "
            f"Threat Level: {scan_result['threat_level']}, "
            f"IP: {client_ip}, User-Agent: {user_agent[:100]}"
        )
        raise _SecurityBlocked(scan_result)

    conversation = None
    if request.conversation_id:
        conversation = await _load_conversation(
            db, agent_id, request.conversation_id, request.external_user_id, strict=True
        )

    await _precheck_billing(db, api_key, agent, request.conversation_id)
    attachments = _validate_attachments(request.attachments, api_key.tenant_id, request.conversation_id)

    if conversation is None:
        conversation = Conversation(
            agent_id=agent_id,
            name=f"API Chat - {datetime.now(UTC).strftime('%Y-%m-%d %H:%M')}",
            source="api",
            external_user_id=request.external_user_id,
            external_org_id=request.external_org_id,
            external_user_name=request.external_user_name,
            external_user_email=request.external_user_email,
        )
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)

    from src.services.conversation_service import ConversationService

    history = await ConversationService.get_conversation_history_cached(
        db=db, conversation_id=conversation.id, limit=30
    )
    return _PreparedChat(
        agent_name=agent.agent_name,
        message=request.message,
        tenant_id=api_key.tenant_id,
        conversation_id=str(conversation.id),
        history=history,
        attachments=attachments,
        scan_result=scan_result,
    )


def _agent_events(prepared: _PreparedChat, language: str | None):
    from src.controllers.agents.chat import chat_stream_service

    return chat_stream_service.stream_agent_response(
        agent_name=prepared.agent_name,
        message=prepared.message,
        conversation_history=prepared.history,
        conversation_id=prepared.conversation_id,
        attachments=prepared.attachments,
        llm_config_id=None,
        db=None,
        tenant_id=prepared.tenant_id,
        language=language,
    )


def _conversation_info(conversation: Conversation, message_count: int) -> ConversationInfo:
    return ConversationInfo(
        id=conversation.id,
        agent_id=conversation.agent_id,
        name=conversation.name,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=message_count,
        external_user_id=conversation.external_user_id,
        external_org_id=conversation.external_org_id,
        external_user_name=conversation.external_user_name,
    )


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

    Pass ``external_user_id`` (and optionally org, name, email) to tie the conversation to your own end
    user; continuing a conversation then requires the same ``external_user_id``.

    Errors before the stream starts are HTTP errors (402 with an ``error_code`` when the plan's
    allowance is used up). The conversation id is returned in the ``X-Conversation-Id`` header.

    Requires permission: chat
    """
    try:
        prepared = await _prepare_chat(agent_id, request, http_request, api_key, db)
    except _SecurityBlocked as blocked:
        scan_result = blocked.scan_result

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

    await db.close()

    return StreamingResponse(
        _agent_events(prepared, request.language),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Security-Status": "validated",
            "X-Risk-Score": str(prepared.scan_result["risk_score"]),
            "X-Conversation-Id": prepared.conversation_id,
        },
    )


@router.post("/agents/{agent_id}/chat", response_model=ChatResponse)
async def chat_with_agent(
    agent_id: UUID,
    request: ChatRequest,
    http_request: Request,
    api_key: AgentApiKey = Depends(require_permission("chat")),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Send a message and get the complete reply in one response (no streaming).

    Same request, identity and error rules as the streaming endpoint. A reply that fails
    (for example the allowance ran out while it was starting) is an HTTP error with an ``error_code``.

    Requires permission: chat
    """
    try:
        prepared = await _prepare_chat(agent_id, request, http_request, api_key, db)
    except _SecurityBlocked as blocked:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "SECURITY_VIOLATION",
                "message": "Message blocked due to security policy violations. Please rephrase your request.",
                "details": {"risk_score": blocked.scan_result["risk_score"]},
            },
        ) from blocked

    await db.close()

    content: list[str] = []
    sources: list[dict] = []
    metadata: dict = {}
    async for raw in _agent_events(prepared, request.language):
        for line in str(raw).splitlines():
            if not line.startswith("data: "):
                continue
            try:
                event = json.loads(line[6:])
            except ValueError:
                continue
            kind = event.get("type")
            if kind == "chunk":
                content.append(event.get("content", ""))
            elif kind == "error":
                code = event.get("error_code") or event.get("error_type") or "AGENT_ERROR"
                raise HTTPException(
                    status_code=402
                    if code in ("QUOTA_EXCEEDED", "QUOTA_NOT_ASSIGNED", "INSUFFICIENT_CREDITS")
                    else 502,
                    detail={
                        "error_code": code,
                        "message": event.get("error") or event.get("content") or "The agent could not reply",
                        "details": event.get("details") or {},
                    },
                )
            elif kind == "done":
                sources = event.get("sources") or []
                metadata = event.get("metadata") or {}

    return ChatResponse(
        conversation_id=UUID(prepared.conversation_id), message="".join(content), sources=sources, metadata=metadata
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
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    external_user_id: str | None = None,
    external_org_id: str | None = None,
    api_key: AgentApiKey = Depends(require_permission("read")),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List conversations for a specific agent, newest first.

    Filter with ``external_user_id`` or ``external_org_id`` to show one of your end users (or one
    organisation) only their own conversations.

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
    conditions = [
        Conversation.agent_id == agent_id,
        Conversation.agent_id == api_key.agent_id,  # SECURITY: caller scope — key must own this agent
    ]
    if external_user_id is not None:
        conditions.append(Conversation.external_user_id == external_user_id)
    if external_org_id is not None:
        conditions.append(Conversation.external_org_id == external_org_id)

    result = await db.execute(
        select(Conversation).where(*conditions).order_by(Conversation.updated_at.desc()).limit(limit).offset(offset)
    )
    conversations = result.scalars().all()

    # Get total count
    count_result = await db.execute(select(func.count(Conversation.id)).where(*conditions))
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

    conversation_list = [_conversation_info(conv, counts_by_conv.get(conv.id, 0)) for conv in conversations]

    return ConversationListResponse(conversations=conversation_list, total=total)


@router.get("/agents/{agent_id}/conversations/{conversation_id}")
async def get_conversation(
    agent_id: UUID,
    conversation_id: UUID,
    message_limit: int = Query(200, ge=1, le=1000),
    message_offset: int = Query(0, ge=0),
    external_user_id: str | None = None,
    api_key: AgentApiKey = Depends(require_permission("read")),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get a specific conversation with its messages.

    With ``external_user_id`` the conversation must belong to that end user, otherwise it is not found.

    Requires permission: read
    """
    # Check if API key is scoped to a specific agent
    if api_key.agent_id and api_key.agent_id != agent_id:
        raise HTTPException(status_code=403, detail="API key not authorized for this agent")

    conversation = await _load_conversation(db, agent_id, conversation_id, external_user_id)

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
        "external_user_id": conversation.external_user_id,
        "external_org_id": conversation.external_org_id,
        "messages": [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at,
                "feedback": (msg.message_metadata or {}).get("feedback"),
            }
            for msg in messages
        ],
    }


@router.delete("/agents/{agent_id}/conversations/{conversation_id}")
async def delete_conversation(
    agent_id: UUID,
    conversation_id: UUID,
    external_user_id: str | None = None,
    api_key: AgentApiKey = Depends(require_permission("write")),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Delete a conversation. With ``external_user_id`` it must belong to that end user.

    Requires permission: write
    """
    # Check if API key is scoped to a specific agent
    if api_key.agent_id and api_key.agent_id != agent_id:
        raise HTTPException(status_code=403, detail="API key not authorized for this agent")

    conversation = await _load_conversation(db, agent_id, conversation_id, external_user_id)

    # Delete conversation (cascade will delete messages)
    await db.delete(conversation)
    await db.commit()

    return {"message": "Conversation deleted successfully"}


@router.post("/agents/{agent_id}/conversations", response_model=ConversationInfo, status_code=201)
async def create_conversation(
    agent_id: UUID,
    request: CreateConversationRequest,
    api_key: AgentApiKey = Depends(require_permission("write")),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Start a conversation without sending a message, for example before uploading an attachment.

    Requires permission: write
    """
    await _load_agent(db, api_key, agent_id)
    conversation = Conversation(
        agent_id=agent_id,
        name=request.name or "New Conversation",
        source="api",
        external_user_id=request.external_user_id,
        external_org_id=request.external_org_id,
        external_user_name=request.external_user_name,
        external_user_email=request.external_user_email,
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return _conversation_info(conversation, 0)


@router.post("/agents/{agent_id}/conversations/{conversation_id}/attachments")
async def upload_attachment(
    agent_id: UUID,
    conversation_id: UUID,
    file: UploadFile = File(...),
    external_user_id: str | None = Form(None),
    api_key: AgentApiKey = Depends(require_permission("write")),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Upload a file (up to 10 MB) to a conversation. Pass the returned object in the ``attachments`` list of
    the next chat message.

    Requires permission: write
    """
    from src.services.chat import AttachmentService
    from src.services.security.upload_limits import read_bounded_upload

    await _load_agent(db, api_key, agent_id)
    conversation = await _load_conversation(db, agent_id, conversation_id, external_user_id, strict=True)
    content = await read_bounded_upload(file, 10 * 1024 * 1024)
    attachment = await AttachmentService().upload_attachment(
        file_content=content,
        filename=file.filename,
        content_type=file.content_type,
        tenant_id=api_key.tenant_id,
        conversation_id=conversation.id,
    )
    signature = _attachment_signature(attachment, api_key.tenant_id, conversation.id)
    return {"attachment": {**attachment, "signature": signature}}


@router.put("/agents/{agent_id}/conversations/{conversation_id}/messages/{message_id}/feedback")
async def set_message_feedback(
    agent_id: UUID,
    conversation_id: UUID,
    message_id: UUID,
    request: MessageFeedbackRequest,
    api_key: AgentApiKey = Depends(require_permission("write")),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Record thumbs up or down (and an optional comment) on a message. ``rating: null`` clears it.

    Requires permission: write
    """
    if api_key.agent_id and api_key.agent_id != agent_id:
        raise HTTPException(status_code=403, detail="API key not authorized for this agent")
    await _load_agent(db, api_key, agent_id)
    await _load_conversation(db, agent_id, conversation_id, request.external_user_id)

    result = await db.execute(
        select(Message).where(Message.id == message_id, Message.conversation_id == conversation_id)
    )
    message = result.scalar_one_or_none()
    if message is None:
        raise HTTPException(status_code=404, detail="Message not found")

    metadata = dict(message.message_metadata or {})
    if request.rating is None:
        metadata.pop("feedback", None)
    else:
        metadata["feedback"] = {
            "rating": request.rating,
            "comment": request.comment,
            "at": datetime.now(UTC).isoformat(),
        }
    message.message_metadata = metadata  # a new dict, so the change is saved
    await db.commit()
    return {"message_id": message.id, "feedback": metadata.get("feedback")}
