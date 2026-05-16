"""
Agent Output Configuration API endpoints.

This controller provides CRUD operations for managing agent output configurations
and viewing delivery logs.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.models import Agent, AgentOutputConfig, AgentOutputDelivery, OAuthApp, OutputProvider
from src.models.slack_bot import SlackBot
from src.services.agent_output_service import AgentOutputService

router = APIRouter()
logger = logging.getLogger(__name__)


# ==================== Schemas ====================


class OutputConfigBase(BaseModel):
    """Base schema for output configuration."""

    name: str = Field(..., description="User-friendly name for this output")
    description: str | None = Field(None, description="Optional description")
    provider: OutputProvider = Field(..., description="Output provider type")
    oauth_app_id: int | None = Field(None, description="OAuth app ID (for Slack/Email)")
    slack_bot_id: str | None = Field(None, description="Slack bot UUID (alternative to oauth_app_id for Slack)")
    config: dict = Field(..., description="Provider-specific configuration")
    conditions: dict | None = Field(None, description="Conditional routing rules")
    output_template: str | None = Field(None, description="Jinja2 template for formatting")
    is_enabled: bool = Field(True, description="Whether this output is enabled")
    send_on_webhook_trigger: bool = Field(True, description="Send when webhook triggers agent")
    send_on_chat_completion: bool = Field(False, description="Send when chat completes")
    retry_on_failure: bool = Field(True, description="Retry failed deliveries")
    max_retries: int = Field(3, ge=0, le=10, description="Maximum retry attempts")


class OutputConfigCreate(OutputConfigBase):
    """Schema for creating output configuration."""

    pass


class OutputConfigUpdate(BaseModel):
    """Schema for updating output configuration."""

    name: str | None = None
    description: str | None = None
    oauth_app_id: int | None = None
    slack_bot_id: str | None = None
    config: dict | None = None
    conditions: dict | None = None
    output_template: str | None = None
    is_enabled: bool | None = None
    send_on_webhook_trigger: bool | None = None
    send_on_chat_completion: bool | None = None
    retry_on_failure: bool | None = None
    max_retries: int | None = Field(None, ge=0, le=10)


class OutputConfigResponse(OutputConfigBase):
    """Schema for output configuration response."""

    id: str
    agent_id: str
    tenant_id: str
    created_at: str
    updated_at: str
    stats: dict | None = None

    model_config = ConfigDict(from_attributes=True)


class DeliveryResponse(BaseModel):
    """Schema for delivery response."""

    id: str
    output_config_id: str
    agent_id: str
    webhook_event_id: str | None
    status: str
    provider: str
    formatted_output: str | None
    attempt_count: int
    error_message: str | None
    provider_message_id: str | None
    created_at: str
    delivered_at: str | None

    model_config = ConfigDict(from_attributes=True)


# ==================== Endpoints ====================


@router.get("/{agent_id}/outputs", response_model=list[OutputConfigResponse])
async def list_output_configs(
    agent_id: str,
    include_stats: bool = False,
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """
    List all output configurations for an agent.

    Args:
        agent_id: Agent ID (UUID string or agent name)
        include_stats: Include delivery statistics
        db: Database session
        account: Current authenticated account
        tenant_id: Current tenant ID

    Returns:
        List of output configurations
    """
    # Try to parse as UUID first, otherwise treat as agent name
    try:
        agent_uuid = UUID(agent_id)
        result = await db.execute(select(Agent).filter(Agent.id == agent_uuid, Agent.tenant_id == tenant_id))
        agent = result.scalar_one_or_none()
    except ValueError:
        # Not a UUID, treat as agent slug
        result = await db.execute(select(Agent).filter(Agent.slug == agent_id, Agent.tenant_id == tenant_id))
        agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    # Get output configs — eager-load deliveries only when stats are requested
    q = select(AgentOutputConfig).filter(AgentOutputConfig.agent_id == agent.id)
    if include_stats:
        q = q.options(selectinload(AgentOutputConfig.deliveries))
    result = await db.execute(q)
    configs = result.scalars().all()

    return [config.to_dict(include_stats=include_stats) for config in configs]


@router.post("/{agent_id}/outputs", response_model=OutputConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_output_config(
    agent_id: str,
    data: OutputConfigCreate,
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """
    Create a new output configuration for an agent.

    Args:
        agent_id: Agent ID (UUID string or agent name)
        data: Output configuration data
        db: Database session
        account: Current authenticated account
        tenant_id: Current tenant ID

    Returns:
        Created output configuration
    """
    # Try to parse as UUID first, otherwise treat as agent name
    try:
        agent_uuid = UUID(agent_id)
        result = await db.execute(select(Agent).filter(Agent.id == agent_uuid, Agent.tenant_id == tenant_id))
        agent = result.scalar_one_or_none()
    except ValueError:
        # Not a UUID, treat as agent slug
        result = await db.execute(select(Agent).filter(Agent.slug == agent_id, Agent.tenant_id == tenant_id))
        agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    # Verify OAuth app if provided
    if data.oauth_app_id:
        result = await db.execute(
            select(OAuthApp).filter(OAuthApp.id == data.oauth_app_id, OAuthApp.tenant_id == tenant_id)
        )
        oauth_app = result.scalar_one_or_none()

        if not oauth_app:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OAuth app not found")

        # Verify provider matches
        expected_provider = oauth_app.provider.lower()
        if data.provider.value not in [expected_provider, "slack"] or (
            data.provider.value == "slack" and expected_provider != "slack"
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"OAuth app provider '{oauth_app.provider}' doesn't match output provider '{data.provider.value}'",
            )

    # Verify Slack bot if provided
    slack_bot_uuid = None
    if data.slack_bot_id:
        try:
            slack_bot_uuid = UUID(data.slack_bot_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid slack_bot_id format")
        result = await db.execute(
            select(SlackBot).filter(SlackBot.id == slack_bot_uuid, SlackBot.tenant_id == tenant_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slack bot not found")

    # Create output config — exclude slack_bot_id from model_dump since it's stored as UUID
    config_data = data.model_dump(exclude={"slack_bot_id"})
    config = AgentOutputConfig(agent_id=agent_id, tenant_id=tenant_id, slack_bot_id=slack_bot_uuid, **config_data)

    db.add(config)
    await db.commit()
    await db.refresh(config)

    logger.info(f"Created output config {config.id} for agent {agent_id}")

    return config.to_dict()


@router.get("/{agent_id}/outputs/{output_id}", response_model=OutputConfigResponse)
async def get_output_config(
    agent_id: UUID,
    output_id: UUID,
    include_stats: bool = False,
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """
    Get a specific output configuration.

    Args:
        agent_id: Agent UUID
        output_id: Output configuration UUID
        include_stats: Include delivery statistics
        db: Database session
        current_user: Current authenticated user

    Returns:
        Output configuration
    """
    q = select(AgentOutputConfig).filter(
        AgentOutputConfig.id == output_id,
        AgentOutputConfig.agent_id == agent_id,
        AgentOutputConfig.tenant_id == tenant_id,
    )
    if include_stats:
        q = q.options(selectinload(AgentOutputConfig.deliveries))
    result = await db.execute(q)
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Output configuration not found")

    return config.to_dict(include_stats=include_stats)


@router.patch("/{agent_id}/outputs/{output_id}", response_model=OutputConfigResponse)
async def update_output_config(
    agent_id: UUID,
    output_id: UUID,
    data: OutputConfigUpdate,
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """
    Update an output configuration.

    Args:
        agent_id: Agent UUID
        output_id: Output configuration UUID
        data: Update data
        db: Database session
        current_user: Current authenticated user

    Returns:
        Updated output configuration
    """
    result = await db.execute(
        select(AgentOutputConfig).filter(
            AgentOutputConfig.id == output_id,
            AgentOutputConfig.agent_id == agent_id,
            AgentOutputConfig.tenant_id == tenant_id,
        )
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Output configuration not found")

    # Update fields
    update_data = data.model_dump(exclude_unset=True, exclude={"slack_bot_id"})
    for field, value in update_data.items():
        setattr(config, field, value)

    # Handle slack_bot_id separately to ensure UUID conversion
    if "slack_bot_id" in data.model_fields_set:
        raw = data.slack_bot_id
        if raw is not None:
            try:
                config.slack_bot_id = UUID(raw)
            except ValueError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid slack_bot_id format")
        else:
            config.slack_bot_id = None

    await db.commit()
    await db.refresh(config)

    logger.info(f"Updated output config {output_id}")

    return config.to_dict()


@router.delete("/{agent_id}/outputs/{output_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_output_config(
    agent_id: UUID,
    output_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """
    Delete an output configuration.

    Args:
        agent_id: Agent UUID
        output_id: Output configuration UUID
        db: Database session
        current_user: Current authenticated user
    """
    result = await db.execute(
        select(AgentOutputConfig).filter(
            AgentOutputConfig.id == output_id,
            AgentOutputConfig.agent_id == agent_id,
            AgentOutputConfig.tenant_id == tenant_id,
        )
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Output configuration not found")

    await db.delete(config)
    await db.commit()

    logger.info(f"Deleted output config {output_id}")


@router.get("/{agent_id}/outputs/{output_id}/deliveries", response_model=list[DeliveryResponse])
async def list_deliveries(
    agent_id: UUID,
    output_id: UUID,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """
    List delivery attempts for an output configuration.

    Args:
        agent_id: Agent UUID
        output_id: Output configuration UUID
        limit: Maximum number of results
        offset: Pagination offset
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of delivery records
    """
    # Verify output config exists and user has access
    result = await db.execute(
        select(AgentOutputConfig).filter(
            AgentOutputConfig.id == output_id,
            AgentOutputConfig.agent_id == agent_id,
            AgentOutputConfig.tenant_id == tenant_id,
        )
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Output configuration not found")

    # Get deliveries
    result = await db.execute(
        select(AgentOutputDelivery)
        .filter(AgentOutputDelivery.output_config_id == output_id)
        .order_by(AgentOutputDelivery.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    deliveries = result.scalars().all()

    return [delivery.to_dict() for delivery in deliveries]


@router.post("/{agent_id}/outputs/{output_id}/deliveries/{delivery_id}/retry", response_model=DeliveryResponse)
async def retry_delivery(
    agent_id: UUID,
    output_id: UUID,
    delivery_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """
    Retry a failed delivery.

    Args:
        agent_id: Agent UUID
        output_id: Output configuration UUID
        delivery_id: Delivery UUID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Updated delivery record
    """
    # Verify access
    result = await db.execute(
        select(AgentOutputConfig).filter(
            AgentOutputConfig.id == output_id,
            AgentOutputConfig.agent_id == agent_id,
            AgentOutputConfig.tenant_id == tenant_id,
        )
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Output configuration not found")

    # Retry delivery
    try:
        service = AgentOutputService(db)
        delivery = await service.retry_failed_delivery(delivery_id)
        return delivery.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
