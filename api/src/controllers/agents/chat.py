"""
Agent API endpoints with Advanced Security Protection.

Provides REST API endpoints for managing and executing Google Agent SDK agents.
CRITICAL: All chat interactions are protected with prompt injection scanning.
"""

import asyncio
import hashlib
import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.controllers.agents.models import AgentResponse, ChatRequest
from src.core.database import get_async_db, get_async_session_factory
from src.helpers.chat_helpers import validate_conversation_id
from src.helpers.streaming_helpers import generate_security_block_stream
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.models import AccountStatus
from src.models.tenant import Account
from src.services import AuthService
from src.services.agents.agent_loader_service import AgentLoaderService
from src.services.agents.agent_manager import AgentManager
from src.services.agents.chat_service import ChatService
from src.services.agents.chat_stream_service import ChatStreamService
from src.services.security.advanced_prompt_scanner import advanced_prompt_scanner
from src.services.security.token_blacklist import ACCOUNT_TOKENS_PREFIX, TOKEN_BLACKLIST_PREFIX

logger = logging.getLogger(__name__)

# Create router
agents_chat_router = APIRouter()

# Global service instances
agent_manager = AgentManager()
agent_loader = AgentLoaderService(agent_manager)
chat_service = ChatService()
chat_stream_service = ChatStreamService(
    agent_loader=agent_loader,
    chat_service=chat_service,
)


# Endpoints
@agents_chat_router.post("/chat/upload-attachment", response_model=AgentResponse)
async def upload_chat_attachment(
    file: UploadFile = File(...),
    conversation_id: str = Form(...),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Upload a file attachment for chat.

    Args:
        file: File to upload
        conversation_id: Conversation ID
        tenant_id: Tenant ID
        db: Async database session

    Returns:
        Attachment metadata
    """
    try:
        from src.models.agent import Agent
        from src.models.conversation import Conversation
        from src.services.chat import AttachmentService

        # Validate conversation ID using helper
        conversation_uuid = validate_conversation_id(conversation_id)
        if not conversation_uuid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid conversation ID format")

        # Verify conversation exists
        result = await db.execute(select(Conversation).filter(Conversation.id == conversation_uuid))
        conversation = result.scalar_one_or_none()

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Conversation with ID '{conversation_id}' not found"
            )

        # SECURITY: Verify the conversation belongs to current tenant (prevents IDOR)
        # Must verify via agent since conversations don't have direct tenant_id
        if not conversation.agent_id:
            # SECURITY: Reject conversations without an agent - cannot verify tenant ownership
            logger.warning(f"IDOR attempt: Conversation {conversation_id} has no agent_id for tenant verification")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Conversation with ID '{conversation_id}' not found"
            )

        # Verify agent belongs to current tenant
        agent_result = await db.execute(
            select(Agent).filter(Agent.id == conversation.agent_id, Agent.tenant_id == tenant_id)
        )
        agent = agent_result.scalar_one_or_none()
        if not agent:
            logger.warning(
                f"IDOR attempt: Tenant {tenant_id} tried to access conversation {conversation_id} "
                f"belonging to agent {conversation.agent_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Conversation with ID '{conversation_id}' not found"
            )

        # Initialize attachment service
        attachment_service = AttachmentService()

        # Read file content
        file_content = await file.read()

        # Upload attachment
        attachment = await attachment_service.upload_attachment(
            file_content=file_content,
            filename=file.filename,
            content_type=file.content_type,
            tenant_id=tenant_id,
            conversation_id=conversation_uuid,
        )

        return AgentResponse(
            success=True, message=f"File '{file.filename}' uploaded successfully", data={"attachment": attachment}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload chat attachment: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to upload attachment")


@agents_chat_router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_async_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_account: Account = Depends(get_current_account),
):
    """
    Chat with an agent using Server-Sent Events streaming with prompt injection protection.

    Args:
        request: Chat request
        http_request: FastAPI request object for security context
        db: Async database session
        tenant_id: Tenant ID from auth

    Returns:
        StreamingResponse with SSE or security block
    """
    # CRITICAL: Scan message for prompt injection before processing
    client_ip = http_request.client.host if http_request.client else "unknown"
    user_agent = http_request.headers.get("User-Agent", "unknown")

    scan_result = advanced_prompt_scanner.scan_comprehensive(
        text=request.message, user_id=f"tenant_{tenant_id}", ip_address=client_ip, context="agent_chat_stream"
    )

    # Block if threat detected
    if not scan_result["is_safe"]:
        # Log security violation — expected user-input event, not a server error
        logger.warning(
            f"SECURITY: Prompt injection blocked in agent chat stream. "
            f"Agent: {request.agent_name}, Tenant: {tenant_id}, "
            f"Risk Score: {scan_result['risk_score']}, "
            f"Threat Level: {scan_result['threat_level']}, "
            f"IP: {client_ip}, User-Agent: {user_agent[:100]}"
        )

        return StreamingResponse(
            generate_security_block_stream(
                details={
                    "threat_level": scan_result["threat_level"],
                    "risk_score": scan_result["risk_score"],
                    "detections": len(scan_result["detections"]),
                }
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "X-Security-Status": "blocked",
                "X-Threat-Level": scan_result["threat_level"],
                "X-Risk-Score": str(scan_result["risk_score"]),
            },
        )

    # Message is safe - proceed with normal chat flow

    # HITL: Check if this chat message is an approval reply for a pending action
    try:
        import json as _json_mod

        from src.config.redis import get_redis_async
        from src.services.human_approval_service import HumanApprovalService

        _redis = get_redis_async()
        _conv_id = request.conversation_id or ""
        _hitl_key = f"hitl:chat:{request.agent_name}:{_conv_id}"
        _approval_id_str = await _redis.get(_hitl_key)
        if _approval_id_str:
            _approval_svc = HumanApprovalService(db)
            _decision = _approval_svc.parse_reply(request.message)
            if _decision != "unclear":
                _result = await _approval_svc.handle_reply(uuid.UUID(_approval_id_str), request.message, db)
                if _result == "approved":
                    _reply = "Great! Proceeding with the action now."
                elif _result in ("rejected", "feedback"):
                    _reply = (
                        "Understood. Action cancelled."
                        if _result == "rejected"
                        else "Got it! I'll revise and ask again shortly."
                    )
                elif _result == "expired":
                    _reply = "This approval request has expired. The next scheduled run will ask again."
                else:
                    _reply = "Action status updated."

                await _redis.delete(_hitl_key)

                async def _approval_stream():
                    yield f"data: {_json_mod.dumps({'type': 'chunk', 'content': _reply})}\n\n"
                    yield 'data: {"type":"done"}\n\n'

                return StreamingResponse(
                    _approval_stream(),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no",
                    },
                )
            # else: unclear — fall through to normal agent handling
    except Exception as _hitl_err:
        logger.warning(f"HITL chat intercept error: {_hitl_err}")

    # BILLING: Validate billing requirements before processing chat
    try:
        from sqlalchemy import or_

        from src.helpers.chat_helpers import validate_conversation_id
        from src.models.agent import Agent
        from src.services.billing import ChatBillingService

        # Get agent to determine model for credit cost calculation
        agent_result = await db.execute(
            select(Agent).filter(
                Agent.agent_name == request.agent_name,
                or_(Agent.tenant_id == tenant_id, Agent.is_public.is_(True)),
            )
        )
        db_agent = agent_result.scalar_one_or_none()

        if db_agent:
            # Get model from agent's llm_configs relationship
            llm_config = None
            if request.llm_config_id:
                # Find specific config by ID
                try:
                    llm_config_uuid = uuid.UUID(request.llm_config_id)
                    llm_config = next(
                        (c for c in db_agent.llm_configs if c.id == llm_config_uuid and c.enabled),
                        None,
                    )
                except ValueError:
                    pass
            else:
                # Find default config
                llm_config = next(
                    (c for c in db_agent.llm_configs if c.is_default and c.enabled),
                    None,
                )

            if not llm_config or not llm_config.model_name:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "No LLM configuration",
                        "message": "This agent has no LLM configuration. Please configure an LLM model for the agent.",
                        "error_code": "NO_LLM_CONFIG",
                    },
                )

            # Parse conversation_id if provided
            conversation_uuid = None
            if request.conversation_id:
                conversation_uuid = validate_conversation_id(request.conversation_id)

            # Validate all billing requirements
            billing_service = ChatBillingService(db)
            billing_result = await billing_service.validate_chat_request(
                tenant_id=tenant_id,
                model_name=llm_config.model_name,
                conversation_id=conversation_uuid,
            )

            if not billing_result.is_valid:
                logger.warning(
                    f"Billing validation failed for chat: tenant={tenant_id}, "
                    f"error_code={billing_result.error.error_code}"
                )
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail={
                        "error": billing_result.error.error_code.value,
                        "message": billing_result.error.message,
                        "error_code": billing_result.error.error_code.value,
                        **(billing_result.error.details or {}),
                    },
                )
    except HTTPException:
        raise
    except Exception as e:
        # Log but don't block chat if billing validation fails (fail open for non-critical errors)
        logger.warning(f"Billing validation failed, allowing chat to proceed: {e}")

    # AGENT PAYWALL: Check paid agent access (creator monetization, separate from platform billing)
    try:
        import json as _json_paywall

        from sqlalchemy import or_

        from src.config.redis import get_redis_async
        from src.models.agent import Agent
        from src.models.agent_pricing import AgentPricing
        from src.services.billing.agent_user_subscription_service import AgentUserSubscriptionService

        _agent_paywall_result = await db.execute(
            select(Agent).filter(
                Agent.agent_name == request.agent_name,
                or_(Agent.tenant_id == tenant_id, Agent.is_public.is_(True)),
            )
        )
        _agent_for_paywall = _agent_paywall_result.scalar_one_or_none()

        if _agent_for_paywall:
            _pricing_result = await db.execute(
                select(AgentPricing).filter(AgentPricing.agent_id == _agent_for_paywall.id)
            )
            _pricing = _pricing_result.scalar_one_or_none()

            if _pricing and _pricing.is_paid:
                # Creator monetization gate: check if this user has an active subscription
                _guest_token = http_request.cookies.get("agent_access_token")
                _has_access = await AgentUserSubscriptionService.check_access(
                    agent_id=_agent_for_paywall.id,
                    db=db,
                    subscriber_tenant_id=tenant_id,
                    guest_token=_guest_token,
                )

                if not _has_access:
                    # Check trial message budget via Redis
                    _visitor_key = str(tenant_id) or _guest_token or client_ip
                    _redis_paywall = get_redis_async()
                    _trial_key = f"trial:{_agent_for_paywall.id}:{_visitor_key}"
                    _trial_used = await _redis_paywall.incr(_trial_key)
                    await _redis_paywall.expire(_trial_key, 86400)

                    if _trial_used > (_pricing.trial_messages or 0):
                        # Load public profile slug for frontend redirect
                        from src.models.agent_public_profile import AgentPublicProfile

                        _profile_result = await db.execute(
                            select(AgentPublicProfile).filter(
                                AgentPublicProfile.agent_id == _agent_for_paywall.id,
                                AgentPublicProfile.is_published.is_(True),
                            )
                        )
                        _profile = _profile_result.scalar_one_or_none()
                        _slug = _profile.slug if _profile else None

                        _paywall_data = {
                            "agent_id": str(_agent_for_paywall.id),
                            "pricing_id": str(_pricing.id),
                            "slug": _slug,
                            "trial_messages": _pricing.trial_messages or 0,
                            "session_credits": _pricing.session_credits,
                            "daily_credits": _pricing.daily_credits,
                            "weekly_credits": _pricing.weekly_credits,
                            "monthly_credits": _pricing.monthly_subscription_credits,
                        }

                        async def _paywall_stream():
                            yield f"data: {_json_paywall.dumps({'type': 'paywall', 'data': _paywall_data})}\n\n"

                        return StreamingResponse(
                            _paywall_stream(),
                            media_type="text/event-stream",
                            headers={
                                "Cache-Control": "no-cache",
                                "Connection": "keep-alive",
                                "X-Accel-Buffering": "no",
                            },
                        )
    except Exception as _paywall_err:
        logger.warning(f"Agent paywall check failed, allowing chat to proceed: {_paywall_err}")

    # SECURITY: Pass tenant_id to verify conversation ownership
    return StreamingResponse(
        chat_stream_service.stream_agent_response(
            request.agent_name,
            request.message,
            request.conversation_history,
            request.conversation_id,
            request.attachments,
            request.llm_config_id,
            db,
            user_id=str(current_account.id),
            tenant_id=tenant_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Security-Status": "validated",
            "X-Risk-Score": str(scan_result["risk_score"]),
            "X-Scan-ID": f"CHAT_SC_{uuid.uuid4().hex[:8]}",
            "X-Layers-Triggered": str(scan_result["layers_triggered"]),
            "X-AI-Generated": "true",
        },
    )


# ---------------------------------------------------------------------------
# WebSocket chat endpoint
# ---------------------------------------------------------------------------


async def _ws_chat_pipeline(
    agent_name: str,
    message: str,
    conversation_id: str | None,
    conversation_history: list[dict[str, str]],
    attachments: list[dict[str, Any]] | None,
    llm_config_id: str | None,
    db: AsyncSession,
    tenant_id: uuid.UUID,
    current_account: Account,
) -> AsyncGenerator[str, None]:
    """
    Full chat pipeline for WebSocket transport.

    Runs the same pre-flight checks as the SSE endpoint (injection scan → HITL →
    billing) and then streams the agent response.  Yields raw JSON strings — the
    SSE ``data: `` framing is stripped so the WebSocket handler can send them
    directly as text frames.

    Error conditions yield ``{"type":"error", ...}`` frames instead of raising
    HTTP exceptions, because WebSocket has no concept of HTTP status codes.
    """
    import json as _json

    from src.config.redis import get_redis_async

    # ── Prompt injection scan ────────────────────────────────────────────────
    scan_result = advanced_prompt_scanner.scan_comprehensive(
        text=message,
        user_id=f"tenant_{tenant_id}",
        ip_address="ws",
        context="agent_chat_ws",
    )
    if not scan_result["is_safe"]:
        logger.warning(
            "SECURITY: Prompt injection blocked in WS chat. Agent: %s, Tenant: %s, Risk: %s",
            agent_name,
            tenant_id,
            scan_result["risk_score"],
        )
        yield _json.dumps(
            {
                "type": "error",
                "error": "Message blocked by security policy",
                "error_type": "security_violation",
                "risk_score": scan_result["risk_score"],
            }
        )
        return

    # ── HITL approval intercept ──────────────────────────────────────────────
    try:
        from src.services.human_approval_service import HumanApprovalService

        _redis = get_redis_async()
        _hitl_key = f"hitl:chat:{agent_name}:{conversation_id or ''}"
        _approval_id_str = await _redis.get(_hitl_key)
        if _approval_id_str:
            _approval_svc = HumanApprovalService(db)
            _decision = _approval_svc.parse_reply(message)
            if _decision != "unclear":
                _result = await _approval_svc.handle_reply(uuid.UUID(_approval_id_str), message, db)
                _reply_map = {
                    "approved": "Great! Proceeding with the action now.",
                    "rejected": "Understood. Action cancelled.",
                    "feedback": "Got it! I'll revise and ask again shortly.",
                    "expired": "This approval request has expired. The next scheduled run will ask again.",
                }
                await _redis.delete(_hitl_key)
                yield _json.dumps({"type": "chunk", "content": _reply_map.get(_result, "Action status updated.")})
                yield _json.dumps({"type": "done"})
                return
    except Exception as _hitl_err:
        logger.warning("HITL WS intercept error: %s", _hitl_err)

    # ── Billing validation ───────────────────────────────────────────────────
    try:
        from sqlalchemy import or_

        from src.models.agent import Agent
        from src.services.billing import ChatBillingService

        agent_result = await db.execute(
            select(Agent).filter(
                Agent.agent_name == agent_name,
                or_(Agent.tenant_id == tenant_id, Agent.is_public.is_(True)),
            )
        )
        db_agent = agent_result.scalar_one_or_none()

        if db_agent:
            llm_config = None
            if llm_config_id:
                try:
                    _cfg_uuid = uuid.UUID(llm_config_id)
                    llm_config = next(
                        (c for c in db_agent.llm_configs if c.id == _cfg_uuid and c.enabled),
                        None,
                    )
                except ValueError:
                    pass
            else:
                llm_config = next(
                    (c for c in db_agent.llm_configs if c.is_default and c.enabled),
                    None,
                )

            if not llm_config or not llm_config.model_name:
                yield _json.dumps(
                    {
                        "type": "error",
                        "error": "No LLM configuration. Please configure an LLM model for the agent.",
                        "error_code": "NO_LLM_CONFIG",
                    }
                )
                return

            conversation_uuid = validate_conversation_id(conversation_id) if conversation_id else None
            billing_service = ChatBillingService(db)
            billing_result = await billing_service.validate_chat_request(
                tenant_id=tenant_id,
                model_name=llm_config.model_name,
                conversation_id=conversation_uuid,
            )
            if not billing_result.is_valid:
                yield _json.dumps(
                    {
                        "type": "error",
                        "error": billing_result.error.message,
                        "error_code": billing_result.error.error_code.value,
                    }
                )
                return
    except Exception as _billing_err:
        # Fail open for non-critical billing errors (same behaviour as SSE endpoint)
        logger.warning("WS billing validation error: %s", _billing_err)

    # ── Stream agent response ────────────────────────────────────────────────
    async for sse_frame in chat_stream_service.stream_agent_response(
        agent_name=agent_name,
        message=message,
        conversation_history=conversation_history,
        conversation_id=conversation_id,
        attachments=attachments,
        llm_config_id=llm_config_id,
        db=db,
        user_id=str(current_account.id),
        tenant_id=tenant_id,
    ):
        # sse_frame = "data: {...}\n\n" — strip SSE framing for WebSocket
        json_str = sse_frame.removeprefix("data: ").rstrip("\n")
        if json_str:
            yield json_str


@agents_chat_router.websocket("/chat/ws")
async def chat_websocket(websocket: WebSocket) -> None:
    """
    Persistent WebSocket endpoint for agent chat.

    Authentication (first frame only — token never appears in URL or logs):

        client  →  {"type": "auth", "token": "<access_token>"}
        server  →  {"type": "auth_ok"}
                   OR closes with code 1008 on failure

    Chat (repeatable, sequential — one in-flight stream at a time):

        client  →  {
                     "type": "chat",
                     "agent_name": "my-agent",
                     "message": "Hello",
                     "conversation_id": "<uuid or null>",
                     "conversation_history": [...],
                     "attachments": [...],
                     "llm_config_id": "<uuid or null>"
                   }
        server  →  stream of JSON frames identical to SSE events:
                   {"type": "start", ...}
                   {"type": "chunk", "content": "..."}
                   {"type": "tool_status", ...}
                   {"type": "done", "sources": [...], "metadata": {...}}
                   {"type": "error", "error": "...", "error_code": "..."}

    A fresh database session is opened for every chat message so that
    a long-lived connection does not hold a pool slot idle between turns.
    """
    from src.config.redis import get_redis_async

    await websocket.accept()

    # ── 1. Auth handshake (5 s window) ───────────────────────────────────────
    try:
        auth_frame: dict = await asyncio.wait_for(websocket.receive_json(), timeout=5.0)
    except (TimeoutError, Exception):
        await websocket.close(code=1008, reason="Auth timeout")
        return

    if auth_frame.get("type") != "auth":
        await websocket.close(code=1008, reason="First frame must be {type: auth}")
        return

    token: str = auth_frame.get("token", "")
    try:
        payload = AuthService.decode_token(token)
        account_id = uuid.UUID(payload["sub"])
        tenant_id = uuid.UUID(payload["tenant_id"])
        token_version: int = int(payload.get("ver", 0))
    except Exception:
        await websocket.send_json({"type": "auth_error", "message": "Invalid token"})
        await websocket.close(code=1008)
        return

    # Redis revocation check — same logic as _check_token_revocation in auth_middleware
    try:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        aio_redis = get_redis_async()
        pipe = aio_redis.pipeline()
        pipe.exists(f"{TOKEN_BLACKLIST_PREFIX}{token_hash}")
        pipe.get(f"{ACCOUNT_TOKENS_PREFIX}{account_id}:version")
        results = await pipe.execute()
        is_blacklisted = bool(results[0])
        current_version = int(results[1]) if results[1] else 0
    except Exception as exc:
        logger.warning("WS Redis auth check failed: %s", exc)
        await websocket.send_json({"type": "auth_error", "message": "Auth service unavailable"})
        await websocket.close(code=1008)
        return

    if is_blacklisted or token_version < current_version:
        await websocket.send_json({"type": "auth_error", "message": "Token revoked"})
        await websocket.close(code=1008)
        return

    # Load account (separate short-lived session — auth only)
    async with get_async_session_factory()() as auth_db:
        result = await auth_db.execute(select(Account).filter_by(id=account_id))
        current_account = result.scalar_one_or_none()

    if not current_account or current_account.status != AccountStatus.ACTIVE:
        await websocket.send_json({"type": "auth_error", "message": "Account not found or inactive"})
        await websocket.close(code=1008)
        return

    await websocket.send_json({"type": "auth_ok"})
    logger.debug("WS authenticated: account=%s tenant=%s", account_id, tenant_id)

    # ── 2. Message loop ──────────────────────────────────────────────────────
    while True:
        try:
            frame: dict = await websocket.receive_json()
        except WebSocketDisconnect:
            break
        except Exception as exc:
            logger.debug("WS receive error: %s", exc)
            break

        if frame.get("type") != "chat":
            continue

        agent_name: str = frame.get("agent_name", "")
        message: str = frame.get("message", "")

        if not agent_name or not message:
            await websocket.send_json({"type": "error", "error": "agent_name and message are required"})
            continue

        if len(message) > 32000:
            await websocket.send_json({"type": "error", "error": "Message exceeds maximum length of 32000 characters"})
            continue

        conversation_id: str | None = frame.get("conversation_id")
        conversation_history: list = frame.get("conversation_history") or []
        attachments: list | None = frame.get("attachments")
        llm_config_id: str | None = frame.get("llm_config_id")

        # Fresh DB session per message — avoids holding a pool slot idle between turns
        async with get_async_session_factory()() as msg_db:
            try:
                async for json_str in _ws_chat_pipeline(
                    agent_name=agent_name,
                    message=message,
                    conversation_id=conversation_id,
                    conversation_history=conversation_history,
                    attachments=attachments,
                    llm_config_id=llm_config_id,
                    db=msg_db,
                    tenant_id=tenant_id,
                    current_account=current_account,
                ):
                    await websocket.send_text(json_str)
            except WebSocketDisconnect:
                return
            except Exception as exc:
                logger.error("WS stream error: %s", exc, exc_info=True)
                try:
                    await websocket.send_json({"type": "error", "error": "Stream failed"})
                except Exception:
                    return
