"""
Widget API endpoints.

Provides REST API endpoints for managing agent widgets (embedded chat interfaces).
"""

import hmac
import json
import logging
import secrets
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

# Import SessionLocal to create independent sessions for streams
from src.config.settings import get_settings
from src.controllers.agents.index import convert_s3_uri_to_presigned_url
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id
from src.middleware.widget_auth import WidgetAuthMiddleware
from src.models.agent import Agent
from src.models.agent_widget import AgentWidget, WidgetAnalytics
from src.models.conversation import Conversation, ConversationStatus
from src.models.message import Message
from src.models.widget_agent_route import WidgetAgentRoute
from src.services.security.advanced_prompt_scanner import advanced_prompt_scanner

logger = logging.getLogger(__name__)

# Create router
widgets_router = APIRouter()


# Request/Response Models
class CreateWidgetRequest(BaseModel):
    """Request model for creating a widget."""

    agent_id: str = Field(..., description="UUID of the agent")
    widget_name: str = Field(..., description="Human-readable name for the widget")
    allowed_domains: list[str] | None = Field(
        None, description="List of domains allowed to embed this widget (null = all domains)"
    )
    theme_config: dict[str, Any] | None = Field(
        None, description="JSON configuration for widget appearance and behavior"
    )
    rate_limit: int = Field(100, description="Maximum requests per hour")


class UpdateWidgetRequest(BaseModel):
    """Request model for updating a widget."""

    widget_name: str | None = Field(None, description="Human-readable name for the widget")
    allowed_domains: list[str] | None = Field(None, description="List of domains allowed to embed this widget")
    theme_config: dict[str, Any] | None = Field(None, description="JSON configuration for widget appearance")
    rate_limit: int | None = Field(None, description="Maximum requests per hour")
    is_active: bool | None = Field(None, description="Whether the widget is active")
    identity_verification_required: bool | None = Field(None, description="Require HMAC identity verification")
    enable_agent_routing: bool | None = Field(None, description="Enable org-based agent routing")
    mobile_allowed: bool | None = Field(None, description="Allow Flutter/mobile SDK requests without Origin header")


class WidgetResponse(BaseModel):
    """Response model for widget operations."""

    success: bool
    message: str
    data: dict[str, Any] = Field(default_factory=dict)


class WidgetUserContext(BaseModel):
    """User identity context sent from SaaS platform."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., max_length=255, description="SaaS platform's user ID")
    name: str | None = None
    email: str | None = None
    org_id: str | None = Field(None, alias="orgId", description="SaaS platform's org/workspace ID")
    org_name: str | None = Field(None, alias="orgName")


class WidgetAgentRouteSchema(BaseModel):
    """Single org → agent route mapping."""

    external_org_id: str = Field(..., max_length=255)
    agent_id: uuid.UUID


def generate_api_key() -> tuple[str, str, str]:
    """Generate a secure API key. Returns (plain_key, encrypted_key, key_prefix)."""
    from src.services.agents.security import encrypt_value

    plain_key = f"widget_{secrets.token_urlsafe(32)}"
    encrypted_key = encrypt_value(plain_key)
    key_prefix = plain_key[:20]
    return plain_key, encrypted_key, key_prefix


@widgets_router.post("/widgets", response_model=WidgetResponse, status_code=status.HTTP_201_CREATED)
async def create_widget(
    request: CreateWidgetRequest,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    try:
        try:
            agent_uuid = uuid.UUID(request.agent_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid agent ID format")

        result = await db.execute(select(Agent).filter(Agent.id == agent_uuid, Agent.tenant_id == tenant_id))
        agent = result.scalar_one_or_none()
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent with ID '{request.agent_id}' not found"
            )

        plain_key, encrypted_key, key_prefix = generate_api_key()

        # Generate HMAC identity secret (returned plaintext once, stored encrypted)
        from src.services.agents.security import encrypt_value

        plain_secret = secrets.token_urlsafe(32)
        encrypted_secret = encrypt_value(plain_secret)

        widget = AgentWidget(
            agent_id=agent_uuid,
            tenant_id=agent.tenant_id,
            widget_name=request.widget_name,
            api_key=encrypted_key,
            key_prefix=key_prefix,
            allowed_domains=request.allowed_domains,
            theme_config=request.theme_config or {},
            rate_limit=request.rate_limit,
            is_active=True,
            identity_secret=encrypted_secret,
            identity_verification_required=False,
            enable_agent_routing=False,
        )

        db.add(widget)
        await db.commit()
        await db.refresh(widget)

        return WidgetResponse(
            success=True,
            message=f"Widget '{request.widget_name}' created successfully",
            data={
                "widget_id": str(widget.id),
                "widget_name": widget.widget_name,
                "api_key": plain_key,
                "identity_secret": plain_secret,
                "agent_id": str(widget.agent_id),
                "agent_name": agent.agent_name,
                "allowed_domains": widget.allowed_domains,
                "theme_config": widget.theme_config,
                "rate_limit": widget.rate_limit,
                "is_active": widget.is_active,
                "identity_verification_required": widget.identity_verification_required,
                "enable_agent_routing": widget.enable_agent_routing,
                "created_at": widget.created_at.isoformat(),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create widget: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create widget")


@widgets_router.get("/widgets", response_model=WidgetResponse)
async def list_widgets(
    agent_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    try:
        if agent_id:
            try:
                agent_uuid = uuid.UUID(agent_id)
                result = await db.execute(select(Agent).filter(Agent.id == agent_uuid, Agent.tenant_id == tenant_id))
                agent = result.scalar_one_or_none()
                if not agent:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent with ID '{agent_id}' not found"
                    )
                stmt = (
                    select(AgentWidget)
                    .options(joinedload(AgentWidget.agent))
                    .filter(AgentWidget.agent_id == agent_uuid, AgentWidget.tenant_id == tenant_id)
                )
            except ValueError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid agent ID format")
        else:
            stmt = select(AgentWidget).options(joinedload(AgentWidget.agent)).filter(AgentWidget.tenant_id == tenant_id)

        # Get total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await db.execute(count_stmt)
        total_count = count_result.scalar() or 0

        # Get paginated results
        result = await db.execute(stmt.limit(limit).offset(offset))
        widgets = result.scalars().unique().all()

        widgets_list = []
        for widget in widgets:
            widgets_list.append(
                {
                    "widget_id": str(widget.id),
                    "widget_name": widget.widget_name,
                    "agent_id": str(widget.agent_id),
                    "agent_name": widget.agent.agent_name,
                    "allowed_domains": widget.allowed_domains,
                    "rate_limit": widget.rate_limit,
                    "is_active": widget.is_active,
                    "created_at": widget.created_at.isoformat(),
                    "updated_at": widget.updated_at.isoformat(),
                }
            )

        return WidgetResponse(
            success=True,
            message=f"Found {len(widgets_list)} widgets",
            data={"widgets": widgets_list, "total": total_count, "limit": limit, "offset": offset},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list widgets: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list widgets")


# Widget Public Config Endpoint
@widgets_router.get("/widgets/config")
async def get_widget_config(http_request: Request, db: AsyncSession = Depends(get_async_db)):
    """
    Public endpoint to fetch widget + agent configuration.
    Authenticated via X-Widget-API-Key header.
    Returns agent name, avatar, description, suggestion prompts, and theme config
    so the embedded widget can render itself correctly without hardcoded values.
    """
    try:
        api_key = http_request.headers.get("X-Widget-API-Key")
        if not api_key:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Widget API key is required")

        widget = await WidgetAuthMiddleware.validate_api_key(api_key, db)
        if not widget:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or inactive widget API key")

        result = await db.execute(
            select(Agent).filter(
                Agent.id == widget.agent_id,
                Agent.tenant_id == widget.tenant_id,
            )
        )
        agent = result.scalar_one_or_none()
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

        theme = widget.theme_config or {}

        pre_chat = theme.get("pre_chat_form") or {}
        return {
            "widget_id": str(widget.id),
            "widget_name": widget.widget_name,
            "agent_name": agent.agent_name,
            "agent_description": agent.description or "",
            "agent_avatar": convert_s3_uri_to_presigned_url(agent.avatar or ""),
            "suggestion_prompts": agent.suggestion_prompts or [],
            "theme": {
                "primary_color": theme.get("chat_primary_color") or theme.get("primaryColor") or "",
                "welcome_message": theme.get("chat_welcome_message") or "",
                "placeholder": theme.get("chat_placeholder") or "",
                "title": theme.get("chat_title") or "",
                "privacy_policy_url": theme.get("privacy_policy_url") or "",
                "privacy_policy_text": theme.get("privacy_policy_text") or "",
                # branding_text can be a string or False to hide the bar entirely
                "branding_text": theme.get("branding_text"),
                "branding_url": theme.get("branding_url") or "",
            },
            "pre_chat_form": {
                "enabled": bool(pre_chat.get("enabled", False)),
                "show_name": bool(pre_chat.get("show_name", True)),
                "show_email": bool(pre_chat.get("show_email", True)),
                "show_phone": bool(pre_chat.get("show_phone", False)),
                "skippable": bool(pre_chat.get("skippable", True)),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get widget config: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get widget config")


@widgets_router.get("/widgets/chat/history")
async def get_widget_chat_history(
    http_request: Request,
    session_id: str | None = None,
    external_user_id: str | None = None,
    conversation_id: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_async_db),
):
    try:
        api_key = http_request.headers.get("X-Widget-API-Key")
        if not api_key:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Widget API key is required")

        widget = await WidgetAuthMiddleware.validate_api_key(api_key, db)
        if not widget:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or inactive widget API key")

        if not session_id and not external_user_id and not conversation_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either session_id, external_user_id, or conversation_id is required",
            )

        # Collect all agent IDs this widget can route to (default + all routed agents)
        # SECURITY: all routed agents must belong to the same tenant as the widget
        routes_result = await db.execute(select(WidgetAgentRoute).filter(WidgetAgentRoute.widget_id == widget.id))
        routed_agent_ids = {r.agent_id for r in routes_result.scalars().all()}
        routed_agent_ids.add(widget.agent_id)

        # Verify all agent IDs belong to the widget's tenant
        agents_result = await db.execute(
            select(Agent.id).filter(
                Agent.id.in_(routed_agent_ids),
                Agent.tenant_id == widget.tenant_id,
            )
        )
        valid_agent_ids = [row[0] for row in agents_result.all()]
        if not valid_agent_ids:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

        # Scope by conversation_id (direct lookup), external_user_id, or session_id
        if conversation_id:
            try:
                conv_uuid = uuid.UUID(conversation_id)
            except ValueError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid conversation_id format")
            conversation_result = await db.execute(
                select(Conversation).filter(
                    Conversation.id == conv_uuid,
                    Conversation.agent_id.in_(valid_agent_ids),
                )
            )
        elif external_user_id:
            conversation_result = await db.execute(
                select(Conversation)
                .filter(
                    Conversation.agent_id.in_(valid_agent_ids),
                    Conversation.external_user_id == external_user_id,
                    Conversation.status == ConversationStatus.ACTIVE,
                )
                .order_by(Conversation.updated_at.desc())
                .limit(1)
            )
        else:
            conversation_result = await db.execute(
                select(Conversation).filter(
                    Conversation.agent_id.in_(valid_agent_ids),
                    Conversation.session_id == session_id,
                )
            )
        conversation = conversation_result.scalar_one_or_none()

        identifier = external_user_id or session_id
        if not conversation:
            return WidgetResponse(
                success=True, message="No chat history found", data={"identifier": identifier, "messages": []}
            )

        messages_result = await db.execute(
            select(Message)
            .filter(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        messages = messages_result.scalars().all()

        messages_list = []
        for msg in reversed(messages):
            messages_list.append(
                {
                    "id": str(msg.id),
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat() if msg.created_at else None,
                }
            )

        return WidgetResponse(
            success=True,
            message=f"Found {len(messages_list)} messages",
            data={
                "identifier": identifier,
                "conversation_id": str(conversation.id),
                "messages": messages_list,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get chat history: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get chat history")


# NOTE: /widgets/sessions and /widgets/sessions/{id}/close MUST be defined before
# /widgets/{widget_id} so FastAPI doesn't swallow them as widget_id="sessions".


@widgets_router.get("/widgets/sessions")
async def list_widget_sessions(
    http_request: Request,
    page: int = 1,
    page_size: int = 20,
    session_status: str | None = None,
    db: AsyncSession = Depends(get_async_db),
):
    """
    List sessions for an identified widget user.
    Authenticated via X-Widget-API-Key header. Requires user context (external_user_id).
    """
    from datetime import UTC, datetime

    from sqlalchemy import or_

    api_key = http_request.headers.get("X-Widget-API-Key")
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Widget API key is required")

    widget = await WidgetAuthMiddleware.validate_api_key(api_key, db)
    if not widget:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or inactive widget API key")

    external_user_id = http_request.headers.get("X-Widget-User-Id")
    if not external_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Widget-User-Id header is required to list sessions",
        )

    # Build base filter: conversations for this user on this agent
    stmt = (
        select(Conversation)
        .filter(
            Conversation.agent_id == widget.agent_id,
            Conversation.external_user_id == external_user_id,
            Conversation.deleted_at.is_(None),
        )
        .order_by(Conversation.last_activity_at.desc().nullslast())
    )

    if session_status == "active":
        stmt = stmt.filter(Conversation.status == ConversationStatus.ACTIVE, Conversation.closed_at.is_(None))
    elif session_status == "closed":
        stmt = stmt.filter(or_(Conversation.status != ConversationStatus.ACTIVE, Conversation.closed_at.isnot(None)))

    offset = (page - 1) * page_size
    result = await db.execute(stmt.offset(offset).limit(page_size))
    conversations = result.scalars().all()

    from src.models.message import Message

    sessions = []
    for conv in conversations:
        first_msg_result = await db.execute(
            select(Message)
            .filter(Message.conversation_id == conv.id, Message.role == "USER")
            .order_by(Message.created_at.asc())
            .limit(1)
        )
        first_msg = first_msg_result.scalar_one_or_none()

        # Skip conversations with no user messages (empty sessions)
        if not first_msg:
            continue

        first_message_preview = first_msg.content[:80] if first_msg.content else None

        is_closed = conv.closed_at is not None or conv.status != ConversationStatus.ACTIVE
        sessions.append(
            {
                "id": str(conv.id),
                "first_message": first_message_preview,
                "last_activity_at": (
                    conv.last_activity_at.isoformat() if conv.last_activity_at else conv.created_at.isoformat()
                ),
                "status": "closed" if is_closed else "active",
                "created_at": conv.created_at.isoformat(),
            }
        )

    return WidgetResponse(
        success=True,
        message=f"Found {len(sessions)} sessions",
        data={"sessions": sessions, "page": page, "page_size": page_size},
    )


@widgets_router.post("/widgets/sessions/{session_id}/close")
async def close_widget_session(
    session_id: str,
    http_request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Close a widget session. Sets closed_at and archives the conversation.
    Accepts either X-Widget-API-Key (widget/Flutter clients) or Bearer token (dashboard admins).
    """
    from datetime import UTC, datetime

    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid session ID format")

    api_key = http_request.headers.get("X-Widget-API-Key")
    bearer = http_request.headers.get("Authorization", "")

    if api_key:
        # Widget/Flutter client path — verify API key and scope to widget's agent
        widget = await WidgetAuthMiddleware.validate_api_key(api_key, db)
        if not widget:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or inactive widget API key")

        external_user_id = http_request.headers.get("X-Widget-User-Id")
        filters = [
            Conversation.id == session_uuid,
            Conversation.agent_id == widget.agent_id,
            Conversation.deleted_at.is_(None),
        ]
        if external_user_id:
            filters.append(Conversation.external_user_id == external_user_id)

    elif bearer.startswith("Bearer "):
        # Dashboard admin path — verify JWT and scope to tenant
        from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
        from src.models.tenant import TenantAccountJoin

        token = bearer[7:]
        try:
            from src.services.auth_service import AuthService

            payload = AuthService.decode_token(token)
            tenant_id = uuid.UUID(payload["tenant_id"])
            account_id = uuid.UUID(payload["sub"])
        except Exception:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        # Verify membership and admin/owner role
        membership = await db.execute(
            select(TenantAccountJoin).filter(
                TenantAccountJoin.tenant_id == tenant_id,
                TenantAccountJoin.account_id == account_id,
            )
        )
        join = membership.scalar_one_or_none()
        if not join or not join.is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

        # Scope conversation to tenant via agent join
        from src.models.agent import Agent as AgentModel

        filters = [
            Conversation.id == session_uuid,
            Conversation.deleted_at.is_(None),
            AgentModel.tenant_id == tenant_id,
        ]
        # Rewrite to use join below
        result = await db.execute(
            select(Conversation).join(AgentModel, Conversation.agent_id == AgentModel.id).filter(*filters)
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

        conversation.closed_at = datetime.now(UTC)
        conversation.status = ConversationStatus.ARCHIVED
        await db.commit()
        return WidgetResponse(success=True, message="Session closed", data={"id": session_id})

    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    result = await db.execute(select(Conversation).filter(*filters))
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    conversation.closed_at = datetime.now(UTC)
    conversation.status = ConversationStatus.ARCHIVED
    await db.commit()

    return WidgetResponse(success=True, message="Session closed", data={"id": session_id})


@widgets_router.get("/widgets/{widget_id}", response_model=WidgetResponse)
async def get_widget(
    widget_id: str,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    try:
        try:
            widget_uuid = uuid.UUID(widget_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid widget ID format")

        # Eager load agent to prevent N+1 query
        result = await db.execute(
            select(AgentWidget)
            .options(joinedload(AgentWidget.agent))
            .filter(AgentWidget.id == widget_uuid, AgentWidget.tenant_id == tenant_id)
        )
        widget = result.scalar_one_or_none()

        if not widget:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Widget with ID '{widget_id}' not found")

        return WidgetResponse(
            success=True,
            message="Widget details retrieved",
            data={
                "widget_id": str(widget.id),
                "widget_name": widget.widget_name,
                "api_key": widget.api_key,
                "agent_id": str(widget.agent_id),
                "agent_name": widget.agent.agent_name,
                "allowed_domains": widget.allowed_domains,
                "theme_config": widget.theme_config,
                "rate_limit": widget.rate_limit,
                "is_active": widget.is_active,
                "identity_verification_required": widget.identity_verification_required,
                "enable_agent_routing": widget.enable_agent_routing,
                "created_at": widget.created_at.isoformat(),
                "updated_at": widget.updated_at.isoformat(),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get widget: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get widget details")


@widgets_router.put("/widgets/{widget_id}", response_model=WidgetResponse)
async def update_widget(
    widget_id: str,
    request: UpdateWidgetRequest,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    try:
        try:
            widget_uuid = uuid.UUID(widget_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid widget ID format")

        result = await db.execute(
            select(AgentWidget).filter(AgentWidget.id == widget_uuid, AgentWidget.tenant_id == tenant_id)
        )
        widget = result.scalar_one_or_none()

        if not widget:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Widget with ID '{widget_id}' not found")

        if request.widget_name is not None:
            widget.widget_name = request.widget_name
        if request.allowed_domains is not None:
            widget.allowed_domains = request.allowed_domains
        if request.theme_config is not None:
            widget.theme_config = request.theme_config
        if request.rate_limit is not None:
            widget.rate_limit = request.rate_limit
        if request.is_active is not None:
            widget.is_active = request.is_active
        if request.identity_verification_required is not None:
            widget.identity_verification_required = request.identity_verification_required
        if request.enable_agent_routing is not None:
            widget.enable_agent_routing = request.enable_agent_routing
        if request.mobile_allowed is not None:
            widget.mobile_allowed = request.mobile_allowed

        await db.commit()
        await db.refresh(widget)

        return WidgetResponse(
            success=True,
            message=f"Widget '{widget.widget_name}' updated successfully",
            data={
                "widget_id": str(widget.id),
                "widget_name": widget.widget_name,
                "allowed_domains": widget.allowed_domains,
                "theme_config": widget.theme_config,
                "rate_limit": widget.rate_limit,
                "is_active": widget.is_active,
                "identity_verification_required": widget.identity_verification_required,
                "enable_agent_routing": widget.enable_agent_routing,
                "updated_at": widget.updated_at.isoformat(),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update widget: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update widget")


@widgets_router.delete("/widgets/{widget_id}", response_model=WidgetResponse)
async def delete_widget(
    widget_id: str,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    try:
        try:
            widget_uuid = uuid.UUID(widget_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid widget ID format")

        result = await db.execute(
            select(AgentWidget).filter(AgentWidget.id == widget_uuid, AgentWidget.tenant_id == tenant_id)
        )
        widget = result.scalar_one_or_none()

        if not widget:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Widget with ID '{widget_id}' not found")

        widget_name = widget.widget_name
        await db.delete(widget)
        await db.commit()

        return WidgetResponse(success=True, message=f"Widget '{widget_name}' deleted successfully")

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete widget: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete widget")


@widgets_router.post("/widgets/{widget_id}/regenerate-key", response_model=WidgetResponse)
async def regenerate_api_key(
    widget_id: str,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    try:
        try:
            widget_uuid = uuid.UUID(widget_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid widget ID format")

        result = await db.execute(
            select(AgentWidget).filter(AgentWidget.id == widget_uuid, AgentWidget.tenant_id == tenant_id)
        )
        widget = result.scalar_one_or_none()

        if not widget:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Widget with ID '{widget_id}' not found")

        plain_key, encrypted_key, key_prefix = generate_api_key()
        widget.api_key = encrypted_key
        widget.key_prefix = key_prefix
        await db.commit()
        await db.refresh(widget)

        return WidgetResponse(
            success=True,
            message="API key regenerated successfully",
            data={"widget_id": str(widget.id), "api_key": plain_key},
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to regenerate API key: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to regenerate API key")


@widgets_router.post("/widgets/{widget_id}/regenerate-identity-secret", response_model=WidgetResponse)
async def regenerate_identity_secret(
    widget_id: str,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Regenerate the HMAC identity secret. Returns the new plaintext secret once."""
    try:
        try:
            widget_uuid = uuid.UUID(widget_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid widget ID format")

        result = await db.execute(
            select(AgentWidget).filter(AgentWidget.id == widget_uuid, AgentWidget.tenant_id == tenant_id)
        )
        widget = result.scalar_one_or_none()
        if not widget:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Widget with ID '{widget_id}' not found")

        from src.services.agents.security import encrypt_value

        plain_secret = secrets.token_urlsafe(32)
        widget.identity_secret = encrypt_value(plain_secret)
        await db.commit()

        return WidgetResponse(
            success=True,
            message="Identity secret regenerated successfully",
            data={"widget_id": str(widget.id), "identity_secret": plain_secret},
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to regenerate identity secret: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to regenerate secret")


@widgets_router.get("/widgets/{widget_id}/routes", response_model=WidgetResponse)
async def list_widget_routes(
    widget_id: str,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """List all org→agent routes for this widget."""
    try:
        try:
            widget_uuid = uuid.UUID(widget_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid widget ID format")

        result = await db.execute(
            select(AgentWidget).filter(AgentWidget.id == widget_uuid, AgentWidget.tenant_id == tenant_id)
        )
        widget = result.scalar_one_or_none()
        if not widget:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Widget with ID '{widget_id}' not found")

        routes_result = await db.execute(select(WidgetAgentRoute).filter(WidgetAgentRoute.widget_id == widget_uuid))
        routes = routes_result.scalars().all()

        return WidgetResponse(
            success=True,
            message=f"Found {len(routes)} routes",
            data={
                "widget_id": widget_id,
                "routes": [
                    {
                        "external_org_id": r.external_org_id,
                        "agent_id": str(r.agent_id),
                        "created_at": r.created_at.isoformat(),
                    }
                    for r in routes
                ],
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list routes: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list routes")


@widgets_router.put("/widgets/{widget_id}/routes", response_model=WidgetResponse)
async def set_widget_routes(
    widget_id: str,
    routes: list[WidgetAgentRouteSchema],
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Bulk-replace all org→agent routes for this widget."""
    try:
        try:
            widget_uuid = uuid.UUID(widget_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid widget ID format")

        result = await db.execute(
            select(AgentWidget).filter(AgentWidget.id == widget_uuid, AgentWidget.tenant_id == tenant_id)
        )
        widget = result.scalar_one_or_none()
        if not widget:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Widget with ID '{widget_id}' not found")

        # Validate all agent IDs belong to the same tenant
        for route in routes:
            agent_result = await db.execute(
                select(Agent).filter(Agent.id == route.agent_id, Agent.tenant_id == tenant_id)
            )
            if not agent_result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Agent {route.agent_id} not found or belongs to a different tenant",
                )

        # Delete existing routes with a single statement (avoids flush/ordering issues)
        await db.execute(delete(WidgetAgentRoute).where(WidgetAgentRoute.widget_id == widget_uuid))

        # Insert new routes
        for route in routes:
            db.add(
                WidgetAgentRoute(
                    widget_id=widget_uuid,
                    external_org_id=route.external_org_id,
                    agent_id=route.agent_id,
                )
            )

        await db.commit()

        return WidgetResponse(
            success=True,
            message=f"Set {len(routes)} routes",
            data={"widget_id": widget_id, "route_count": len(routes)},
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to set routes: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to set routes")


@widgets_router.delete("/widgets/{widget_id}/routes/{external_org_id}", response_model=WidgetResponse)
async def delete_widget_route(
    widget_id: str,
    external_org_id: str,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Remove a single org→agent route."""
    try:
        try:
            widget_uuid = uuid.UUID(widget_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid widget ID format")

        result = await db.execute(
            select(AgentWidget).filter(AgentWidget.id == widget_uuid, AgentWidget.tenant_id == tenant_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Widget with ID '{widget_id}' not found")

        route_result = await db.execute(
            select(WidgetAgentRoute).filter(
                WidgetAgentRoute.widget_id == widget_uuid,
                WidgetAgentRoute.external_org_id == external_org_id,
            )
        )
        route = route_result.scalar_one_or_none()
        if not route:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")

        await db.delete(route)
        await db.commit()

        return WidgetResponse(success=True, message=f"Route for org '{external_org_id}' deleted")

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete route: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete route")


@widgets_router.get("/widgets/{widget_id}/embed-code", response_model=WidgetResponse)
async def get_embed_code(
    widget_id: str,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    try:
        try:
            widget_uuid = uuid.UUID(widget_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid widget ID format")

        result = await db.execute(
            select(AgentWidget).filter(AgentWidget.id == widget_uuid, AgentWidget.tenant_id == tenant_id)
        )
        widget = result.scalar_one_or_none()

        if not widget:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Widget with ID '{widget_id}' not found")

        settings = get_settings()
        widget_js_url = settings.widget_js_url
        public_api_url = settings.public_api_url

        # Decrypt API key for embed code display (keys may be stored encrypted)
        from src.services.agents.security import decrypt_value

        try:
            display_api_key = decrypt_value(widget.api_key)
        except Exception:
            display_api_key = widget.api_key  # already plain (legacy)

        embed_code = f"""<!-- Synkora Agent Widget -->
<div id="synkora-widget-{widget_id}"></div>
<script src="{widget_js_url}"></script>
<script>
  SynkoraWidget.init({{
    widgetId: '{widget_id}',
    apiKey: '{display_api_key}',
    containerId: 'synkora-widget-{widget_id}',
    apiUrl: '{public_api_url}'
  }});
</script>"""

        return WidgetResponse(
            success=True, message="Embed code generated", data={"widget_id": str(widget.id), "embed_code": embed_code}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate embed code: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate embed code")


@widgets_router.get("/widgets/{widget_id}/analytics", response_model=WidgetResponse)
async def get_widget_analytics(
    widget_id: str,
    limit: int = 100,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    try:
        try:
            widget_uuid = uuid.UUID(widget_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid widget ID format")

        result = await db.execute(
            select(AgentWidget).filter(AgentWidget.id == widget_uuid, AgentWidget.tenant_id == tenant_id)
        )
        widget = result.scalar_one_or_none()

        if not widget:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Widget with ID '{widget_id}' not found")

        analytics_result = await db.execute(
            select(WidgetAnalytics)
            .filter(WidgetAnalytics.widget_id == widget_uuid)
            .order_by(WidgetAnalytics.created_at.desc())
            .limit(limit)
        )
        analytics = analytics_result.scalars().all()

        analytics_list = []
        for record in analytics:
            analytics_list.append(
                {
                    "session_id": record.session_id,
                    "messages_count": record.messages_count,
                    "domain": record.domain,
                    "user_agent": record.user_agent,
                    "created_at": record.created_at.isoformat(),
                }
            )

        total_sessions = len({a.session_id for a in analytics})
        total_messages = sum(a.messages_count for a in analytics)
        unique_domains = len({a.domain for a in analytics if a.domain})

        return WidgetResponse(
            success=True,
            message=f"Found {len(analytics_list)} analytics records",
            data={
                "widget_id": str(widget.id),
                "widget_name": widget.widget_name,
                "analytics": analytics_list,
                "summary": {
                    "total_sessions": total_sessions,
                    "total_messages": total_messages,
                    "unique_domains": unique_domains,
                },
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get widget analytics: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get analytics")


_PAGE_CONTEXT_MAX_BYTES = 500


def _cap_page_context(page_context: dict[str, Any] | None) -> dict[str, Any] | None:
    """Enforce a size cap and JSON-serializability check on host-supplied page_context.

    Returns None (and logs a warning) if page_context is oversized or not JSON-serializable,
    so a misbehaving host app can't bloat prompts or crash serialization downstream.
    """
    if page_context is None:
        return None
    try:
        serialized = json.dumps(page_context)
    except (TypeError, ValueError) as e:
        logger.warning(f"Discarding non-JSON-serializable page_context: {e}")
        return None
    if len(serialized.encode("utf-8")) > _PAGE_CONTEXT_MAX_BYTES:
        logger.warning(
            f"Discarding oversized page_context ({len(serialized.encode('utf-8'))} bytes > "
            f"{_PAGE_CONTEXT_MAX_BYTES} byte cap)"
        )
        return None
    return page_context


# Widget Chat Endpoints
class WidgetChatRequest(BaseModel):
    """Request model for widget chat."""

    message: str = Field(..., description="User message")
    session_id: str | None = Field(None, description="Session ID for conversation continuity")
    conversation_id: str | None = Field(None, description="Conversation ID if continuing existing chat")
    user: WidgetUserContext | None = Field(None, description="Identified user context from SaaS platform")
    user_hash: str | None = Field(None, description="HMAC-SHA256(identity_secret, user.id) for identity verification")
    source: str | None = Field(None, description="Channel source: flutter | widget | chrome (defaults to widget)")
    force_new: bool = Field(
        False, description="When true, always create a new conversation instead of resuming the latest active one"
    )
    # Pre-chat form collected fields (optional, passed on first message)
    user_email: str | None = Field(None, description="Email collected from pre-chat form")
    user_phone: str | None = Field(None, description="Phone collected from pre-chat form")
    page_context: dict[str, Any] | None = Field(
        None, description="Host-app-supplied context describing what the end user is currently looking at"
    )


class PushRegisterRequest(BaseModel):
    """Request model for registering an FCM push token."""

    fcm_token: str = Field(..., description="FCM device token")
    platform: str = Field(..., description="Platform: android | ios | web")
    conversation_id: str | None = Field(None, description="Active conversation ID to link to this token")
    user_id: str | None = Field(None, description="App-side user identifier for per-user push targeting")


@widgets_router.post("/widgets/push/register")
async def register_push_token(
    request: PushRegisterRequest, http_request: Request, db: AsyncSession = Depends(get_async_db)
):
    """
    Register an FCM device token for push notifications.
    Safe to call on every app launch — upserts on (widget_id, fcm_token).
    """
    import uuid as uuid_mod

    from src.models.widget_push_subscription import WidgetPushSubscription

    api_key = http_request.headers.get("X-Widget-API-Key")
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Widget API key is required")

    widget = await WidgetAuthMiddleware.validate_api_key(api_key, db)
    if not widget:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or inactive widget API key")

    if request.platform not in ("android", "ios", "web"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="platform must be android, ios, or web")

    conversation_uuid = None
    if request.conversation_id:
        try:
            conversation_uuid = uuid_mod.UUID(request.conversation_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid conversation_id format")

    # Upsert: find existing by (widget_id, fcm_token) and update, or create new
    result = await db.execute(
        select(WidgetPushSubscription).filter(
            WidgetPushSubscription.widget_id == widget.id,
            WidgetPushSubscription.fcm_token == request.fcm_token,
        )
    )
    sub = result.scalar_one_or_none()

    if sub:
        sub.platform = request.platform
        if conversation_uuid:
            sub.conversation_id = conversation_uuid
        if request.user_id is not None:
            sub.external_user_id = request.user_id
    else:
        sub = WidgetPushSubscription(
            widget_id=widget.id,
            tenant_id=widget.tenant_id,
            conversation_id=conversation_uuid,
            fcm_token=request.fcm_token,
            platform=request.platform,
            external_user_id=request.user_id,
        )
        db.add(sub)

    await db.commit()

    # Subscribe token to FCM topics for bulk/user-targeted sends (fire-and-forget)
    widget_topic_id = str(widget.id).replace("-", "")
    _fire_subscribe_to_topics(request.fcm_token, widget_topic_id, request.user_id, widget)

    return {"registered": True}


def _fire_subscribe_to_topics(fcm_token: str, widget_topic_id: str, user_id: str | None, widget: Any) -> None:
    """
    Subscribe the FCM token to topics in a background thread (fire-and-forget).
    Topics:
      synkora_w_{widget_topic_id}                    — all subscribers for this widget (bulk send)
      synkora_w_{widget_topic_id}_u_{safe_user_id}   — per-user targeting (when user_id provided)
    Failure is silent — topic subscription is best-effort.
    """
    import re
    import threading

    def _subscribe() -> None:
        try:
            import firebase_admin
            from firebase_admin import credentials, messaging
            from src.utils.encryption import decrypt_value

            if not widget.fcm_server_key:
                return

            try:
                fcm_key = decrypt_value(widget.fcm_server_key)
            except Exception:
                fcm_key = widget.fcm_server_key

            app_name = f"synkora_{abs(hash(fcm_key))}"
            try:
                app = firebase_admin.get_app(app_name)
            except ValueError:
                cred = credentials.Certificate(fcm_key)
                app = firebase_admin.initialize_app(cred, name=app_name)

            # Subscribe to widget-wide topic
            bulk_topic = f"synkora_w_{widget_topic_id}"
            messaging.subscribe_to_topic([fcm_token], bulk_topic, app=app)

            # Subscribe to per-user topic if user_id provided
            if user_id:
                safe_uid = re.sub(r"[^a-zA-Z0-9_-]", "_", user_id)[:100]
                user_topic = f"synkora_w_{widget_topic_id}_u_{safe_uid}"
                messaging.subscribe_to_topic([fcm_token], user_topic, app=app)

        except Exception as e:
            logger.warning(f"FCM topic subscription failed (non-critical): {e}")

    threading.Thread(target=_subscribe, daemon=True).start()


@widgets_router.post("/widgets/chat")
async def widget_chat(request: WidgetChatRequest, http_request: Request, db: AsyncSession = Depends(get_async_db)):
    """
    Send a message to the agent via widget with advanced prompt injection protection.
    """
    try:
        # Get API key from header
        api_key = http_request.headers.get("X-Widget-API-Key")
        if not api_key:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Widget API key is required")

        # Validate API key and get widget
        widget = await WidgetAuthMiddleware.validate_api_key(api_key, db)
        if not widget:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or inactive widget API key")

        # Enforce size/serializability cap on host-supplied page_context before it's used anywhere
        page_context = _cap_page_context(request.page_context)

        # Validate domain — skip check for mobile SDK requests (no Origin header) when mobile_allowed=True
        origin = http_request.headers.get("Origin") or http_request.headers.get("Referer")
        is_mobile_request = not origin
        if not (is_mobile_request and getattr(widget, "mobile_allowed", False)):
            if not WidgetAuthMiddleware.validate_domain(widget, origin):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Domain not allowed for this widget")

        # Check rate limit
        if not await WidgetAuthMiddleware.check_rate_limit_async(widget):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded for this widget"
            )

        # ── HMAC identity verification ────────────────────────────────────────────
        if widget.identity_verification_required:
            if not request.user or not request.user_hash:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Identity verification required: user context and user_hash must be provided",
                )
            if not widget.identity_secret:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Widget identity secret not configured"
                )
            try:
                from src.services.agents.security import decrypt_value

                plain_secret = decrypt_value(widget.identity_secret)
                expected = hmac.new(plain_secret.encode(), request.user.id.encode(), "sha256").hexdigest()
                if not hmac.compare_digest(expected, request.user_hash):
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid identity hash")
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"HMAC verification error for widget {widget.id}: {e}")
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Identity verification failed")

        # ── Widget user JWT for MCP servers ───────────────────────────────────────
        # Generate a short-lived signed JWT encoding the verified user context so
        # that MCP tools can forward it as an Authorization Bearer token.  The JWT
        # is only generated when a user context is present AND the widget has an
        # identity_secret (which doubles as the signing key).
        _mcp_user_token: str | None = None
        if request.user and widget.identity_secret:
            try:
                import time

                import jwt as _jwt

                from src.services.agents.security import decrypt_value

                _secret = decrypt_value(widget.identity_secret)
                _now = int(time.time())
                _payload = {
                    "user_id": request.user.id,
                    "organization_id": request.user.org_id,
                    "iat": _now,
                    "exp": _now + 300,  # 5-minute lifetime
                    "widget_id": str(widget.id),
                    "name": request.user.name,
                    "email": request.user.email,
                    "org_name": request.user.org_name,
                }
                _mcp_user_token = _jwt.encode(_payload, _secret, algorithm="HS256")
            except Exception as _jwt_err:
                logger.warning(f"Could not generate MCP user JWT for widget {widget.id}: {_jwt_err}")

        # ── Agent routing ─────────────────────────────────────────────────────────
        resolved_agent_id = widget.agent_id
        if widget.enable_agent_routing and request.user and request.user.org_id:
            route_result = await db.execute(
                select(WidgetAgentRoute).filter(
                    WidgetAgentRoute.widget_id == widget.id,
                    WidgetAgentRoute.external_org_id == request.user.org_id,
                )
            )
            route = route_result.scalar_one_or_none()
            if route:
                resolved_agent_id = route.agent_id

        # Get agent - SECURITY: Verify agent belongs to the same tenant as the widget
        result = await db.execute(
            select(Agent).filter(
                Agent.id == resolved_agent_id,
                Agent.tenant_id == widget.tenant_id,  # Prevent cross-tenant access
            )
        )
        agent = result.scalar_one_or_none()
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

        # Eager load any necessary agent data here if needed to avoid lazy loading in thread

        # Scan message
        client_ip = http_request.client.host if http_request.client else "unknown"
        http_request.headers.get("User-Agent", "unknown")

        scan_result = await advanced_prompt_scanner.scan_comprehensive_async(
            text=request.message, user_id=f"widget_{widget.id}", ip_address=client_ip, context="widget_chat"
        )

        # Block if threat detected
        if not scan_result["is_safe"]:
            logger.warning(
                f"SECURITY: Prompt injection blocked. Widget: {widget.id}, Risk: {scan_result['risk_score']}"
            )

            async def generate_security_block():
                security_response = {
                    "type": "error",
                    "content": "Your message has been blocked due to security policy violations.",
                    "error_type": "security_violation",
                    "violation_id": f"WVI_{uuid.uuid4().hex[:8]}",
                }
                yield f"data: {json.dumps(security_response)}\n\n"

            return StreamingResponse(
                generate_security_block(), media_type="text/event-stream", headers={"X-Security-Status": "blocked"}
            )

        # ── Conversation find-or-create ───────────────────────────────────────────
        # If conversation_id is supplied, verify ownership then use it.
        # Otherwise always create a new conversation — callers that want to resume
        # must pass conversation_id explicitly (Flutter does this via _conversationId tracking).
        resolved_conversation_id = request.conversation_id
        _widget_source = request.source if request.source in ("flutter", "widget", "chrome") else "widget"

        if request.user:
            if resolved_conversation_id:
                # Verify this conversation belongs to this user
                ownership_result = await db.execute(
                    select(Conversation).filter(
                        Conversation.id == uuid.UUID(resolved_conversation_id),
                        Conversation.agent_id == agent.id,
                        Conversation.external_user_id == request.user.id,
                    )
                )
                if not ownership_result.scalar_one_or_none():
                    resolved_conversation_id = None  # Strip invalid/spoofed ID

            if not resolved_conversation_id:
                # Always create a new conversation for this user
                new_conv = Conversation(
                    agent_id=agent.id,
                    external_user_id=request.user.id,
                    external_org_id=request.user.org_id,
                    external_user_name=request.user.name,
                    external_user_email=request.user_email,
                    external_user_phone=request.user_phone,
                    session_id=f"eu_{request.user.id}_{uuid.uuid4().hex[:8]}",
                    name=request.message[:60].strip()
                    if request.message
                    else f"Chat with {request.user.name or request.user.id}",
                    status=ConversationStatus.ACTIVE,
                    source=_widget_source,
                )
                db.add(new_conv)
                try:
                    await db.commit()
                    await db.refresh(new_conv)
                    resolved_conversation_id = str(new_conv.id)
                except Exception as e:
                    await db.rollback()
                    logger.warning(f"Could not create conversation for user {request.user.id}: {e}")

        else:
            # Anonymous session — industry standard: persist conversation by session_id so
            # the dashboard can review all widget conversations, not just identified-user ones.
            _anon_session_id = request.session_id

            if resolved_conversation_id:
                # Verify the supplied conversation_id belongs to this agent (anonymous = no account_id)
                anon_check = await db.execute(
                    select(Conversation).filter(
                        Conversation.id == uuid.UUID(resolved_conversation_id),
                        Conversation.agent_id == agent.id,
                        Conversation.account_id.is_(None),
                    )
                )
                if not anon_check.scalar_one_or_none():
                    resolved_conversation_id = None  # Strip invalid/spoofed ID

            if not resolved_conversation_id and _anon_session_id and not request.force_new:
                # Try to resume the most recent active conversation for this session
                resume_result = await db.execute(
                    select(Conversation)
                    .filter(
                        Conversation.agent_id == agent.id,
                        Conversation.session_id == _anon_session_id,
                        Conversation.status == ConversationStatus.ACTIVE,
                        Conversation.account_id.is_(None),
                    )
                    .order_by(Conversation.updated_at.desc())
                    .limit(1)
                )
                existing_conv = resume_result.scalar_one_or_none()
                if existing_conv:
                    resolved_conversation_id = str(existing_conv.id)

            if not resolved_conversation_id:
                # Create a new anonymous conversation tracked by session_id
                anon_conv = Conversation(
                    agent_id=agent.id,
                    session_id=_anon_session_id or str(uuid.uuid4()),
                    name=request.message[:60].strip() if request.message else "Anonymous Chat",
                    status=ConversationStatus.ACTIVE,
                    source=_widget_source,
                )
                db.add(anon_conv)
                try:
                    await db.commit()
                    await db.refresh(anon_conv)
                    resolved_conversation_id = str(anon_conv.id)
                except Exception as e:
                    await db.rollback()
                    logger.warning(f"Could not create anonymous conversation: {e}")

        # Generate session ID if not provided
        session_id = request.session_id or str(uuid.uuid4())

        # Track analytics
        origin = http_request.headers.get("Origin") or http_request.headers.get("Referer")
        domain = None
        if origin:
            domain = origin.replace("http://", "").replace("https://", "").split(":")[0]

        analytics_result = await db.execute(
            select(WidgetAnalytics).filter(
                WidgetAnalytics.widget_id == widget.id, WidgetAnalytics.session_id == session_id
            )
        )
        analytics = analytics_result.scalar_one_or_none()

        if analytics:
            analytics.messages_count += 1
        else:
            analytics = WidgetAnalytics(
                widget_id=widget.id,
                session_id=session_id,
                messages_count=1,
                domain=domain,
                user_agent=http_request.headers.get("User-Agent", "unknown"),
            )
            db.add(analytics)

        try:
            await db.commit()
        except Exception as e:
            logger.warning(f"Failed to commit analytics: {e}")
            await db.rollback()

        # Import the stream services
        from src.services.agents.agent_loader_service import AgentLoaderService
        from src.services.agents.agent_manager import AgentManager
        from src.services.agents.chat_service import ChatService
        from src.services.agents.chat_stream_service import ChatStreamService
        from src.services.conversation_service import ConversationService

        # Load conversation history if conversation_id is resolved
        conversation_history = None
        if resolved_conversation_id:
            try:
                conversation_uuid = uuid.UUID(resolved_conversation_id)
                conversation_history = await ConversationService.get_conversation_history_cached(
                    db=db,
                    conversation_id=conversation_uuid,
                    limit=30,  # Keep recent messages for context
                )
                logger.info(f"📝 Loaded {len(conversation_history)} messages from widget conversation history")
            except (ValueError, Exception) as e:
                logger.warning(f"Could not load conversation history: {e}")

        # Block AI while a human operator is handling this conversation
        if resolved_conversation_id:
            try:
                _hc_result = await db.execute(
                    select(Conversation).filter(Conversation.id == uuid.UUID(resolved_conversation_id))
                )
                _hc = _hc_result.scalar_one_or_none()
                if _hc and _hc.handoff_status == "active":
                    # Save the user message so the operator can see it in the thread
                    from src.models.message import Message as _Msg
                    from src.models.message import MessageRole as _MR
                    from src.models.message import MessageStatus as _MS

                    _user_msg = _Msg(
                        conversation_id=uuid.UUID(resolved_conversation_id),
                        role=_MR.USER,
                        content=request.message,
                        status=_MS.COMPLETED,
                        message_metadata={"source": "widget"},
                    )
                    db.add(_user_msg)
                    _hc.increment_message_count()
                    await db.commit()
                    # Broadcast so operator inbox sees the new message in real time
                    try:
                        from src.core.websocket import connection_manager as _cm

                        await _cm.broadcast(
                            {
                                "type": "handoff_user_message",
                                "data": {
                                    "conversation_id": resolved_conversation_id,
                                    "content": request.message,
                                },
                            }
                        )
                    except Exception:
                        pass
                    await db.close()
                    _wait_msg = "Your message has been received. A human support agent is currently handling your request — they'll respond shortly."
                    _cid = resolved_conversation_id

                    async def _handoff_stream():
                        yield f"data: {json.dumps({'type': 'chunk', 'content': _wait_msg})}\n\n"
                        yield f"data: {json.dumps({'type': 'done', 'content': '', 'conversation_id': _cid})}\n\n"

                    return StreamingResponse(_handoff_stream(), media_type="text/event-stream")
            except Exception as _he:
                logger.warning(f"Handoff status check failed: {_he}")

        # Initialize the chat stream service
        agent_manager = AgentManager()
        chat_stream_service = ChatStreamService(
            agent_loader=AgentLoaderService(agent_manager), chat_service=ChatService()
        )

        agent_slug = agent.slug or agent.agent_name
        _widget_id = str(widget.id)
        _agent_name = agent.agent_name

        # Release request DB resources before the long SSE stream. The stream
        # service opens short sessions for its own DB work.
        await db.close()

        # Build the raw stream
        _widget_shared_state: dict[str, Any] = {}
        if _mcp_user_token:
            _widget_shared_state["mcp_user_token"] = _mcp_user_token
        raw_stream = chat_stream_service.stream_agent_response(
            agent_slug,
            request.message,
            conversation_history,
            resolved_conversation_id,
            None,  # attachments
            None,  # llm_config_id
            db=None,
            shared_state=_widget_shared_state if _widget_shared_state else None,
            page_context=page_context,
        )

        # Wrap stream to fire FCM push after done event

        async def stream_with_fcm():
            import json as _json

            conv_id = resolved_conversation_id
            reply_chunks: list[str] = []
            async for chunk in raw_stream:
                try:
                    data_str = chunk.replace("data: ", "").strip()
                    if data_str:
                        parsed = _json.loads(data_str)
                        if parsed.get("type") == "done":
                            # Inject conversation_id into done event metadata so the
                            # widget can persist chat history for identified users.
                            if conv_id and not parsed.get("metadata", {}).get("conversation_id"):
                                parsed.setdefault("metadata", {})["conversation_id"] = conv_id
                                chunk = "data: " + _json.dumps(parsed) + "\n\n"
                        elif parsed.get("type") == "chunk":
                            reply_chunks.append(parsed.get("content", ""))
                except Exception:
                    pass
                yield chunk
            # Stream exhausted — fire FCM push (fire-and-forget)
            if conv_id:
                try:
                    from src.tasks.notification_tasks import send_fcm_push_task

                    preview = "".join(reply_chunks)[:100]
                    send_fcm_push_task.delay(
                        widget_id=_widget_id,
                        conversation_id=conv_id,
                        agent_name=_agent_name,
                        reply_preview=preview,
                    )
                except Exception as _fcm_err:
                    logger.warning(f"FCM push dispatch failed (non-critical): {_fcm_err}")

        return StreamingResponse(
            stream_with_fcm(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "X-Security-Status": "validated",
                "X-Risk-Score": str(scan_result["risk_score"]),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process widget chat: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to process chat message")


class WidgetApprovalRespondBody(BaseModel):
    decision: str = Field(..., pattern=r"^(approved|rejected|feedback)$")
    feedback_text: str | None = None


@widgets_router.post("/widgets/chat/approvals/{approval_id}/respond")
async def widget_respond_approval(
    approval_id: uuid.UUID,
    body: WidgetApprovalRespondBody,
    http_request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Allow a widget user to respond to a pending HITL approval request.
    Auth: X-Widget-API-Key header (same as /widgets/chat).
    """
    api_key = http_request.headers.get("X-Widget-API-Key")
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Widget API key is required")

    widget = await WidgetAuthMiddleware.validate_api_key(api_key, db)
    if not widget:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid widget API key")

    try:
        import hashlib
        import json as _json
        from datetime import UTC, datetime

        from src.models.agent_approval import AgentApprovalRequest, ApprovalStatus
        from src.services.human_approval_service import HumanApprovalService

        result = await db.execute(select(AgentApprovalRequest).filter(AgentApprovalRequest.id == approval_id))
        approval = result.scalar_one_or_none()
        if not approval:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found")
        if approval.status != ApprovalStatus.PENDING:
            return {"status": approval.status.value}

        if datetime.now(UTC) > approval.expires_at:
            approval.status = ApprovalStatus.EXPIRED
            await db.commit()
            return {"status": "expired"}

        if body.decision == "approved":
            approval.status = ApprovalStatus.APPROVED
            approval.responded_at = datetime.now(UTC)
            await db.commit()

            # Store one-time Redis execution token
            from src.config.redis import get_redis_async

            redis = get_redis_async()
            args_hash = hashlib.sha256(_json.dumps(approval.tool_args, sort_keys=True).encode()).hexdigest()
            conversation_id = str(approval.conversation_id) if approval.conversation_id else ""
            token_key = f"approval_token:chat:{conversation_id}:{approval.tool_name}:{args_hash}"
            await redis.set(token_key, "1", ex=600)

        elif body.decision == "rejected":
            approval.status = ApprovalStatus.REJECTED
            approval.responded_at = datetime.now(UTC)
            await db.commit()
        elif body.decision == "feedback" and body.feedback_text:
            approval.status = ApprovalStatus.REJECTED
            approval.responded_at = datetime.now(UTC)
            await db.commit()

        return {"status": body.decision, "approval_id": str(approval_id)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Widget approval respond error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to process approval")
