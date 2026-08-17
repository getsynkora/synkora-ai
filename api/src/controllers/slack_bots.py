"""Slack Bot API controller."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_async_db
from ..middleware.auth_middleware import get_current_account, get_current_tenant_id
from ..models import Account
from ..services.slack.slack_bot_manager import SlackBotManager

router = APIRouter(prefix="/slack-bots", tags=["slack-bots"])


# Request/Response Models
class SlackBotCreate(BaseModel):
    """Request model for creating a Slack bot."""

    agent_id: UUID
    bot_name: str = Field(..., min_length=1, max_length=255)
    slack_app_id: str = Field(..., min_length=1)
    slack_bot_token: str = Field(..., description="Bot user OAuth token (xoxb-*)")
    slack_app_token: str | None = Field(None, description="App-level token for Socket Mode (xapp-*)")
    slack_workspace_id: str | None = Field(None, description="Auto-detected on first connection")
    slack_workspace_name: str | None = None
    connection_mode: str = Field(default="socket", description="Connection mode: 'socket' or 'event'")
    signing_secret: str | None = Field(None, description="Signing secret for Event Mode verification")
    allow_external_shared_channels: bool = Field(
        default=False,
        description="If False (default), bot refuses to respond in Slack Connect / externally-shared channels",
    )


class SlackBotUpdate(BaseModel):
    """Request model for updating a Slack bot."""

    bot_name: str | None = Field(None, min_length=1, max_length=255)
    slack_bot_token: str | None = Field(None, description="Bot user OAuth token (xoxb-*)")
    slack_app_token: str | None = Field(None, description="App-level token for Socket Mode (xapp-*)")
    signing_secret: str | None = Field(None, description="Signing secret for Event Mode verification")
    is_active: bool | None = None
    allow_external_shared_channels: bool | None = None


class SlackBotResponse(BaseModel):
    """Response model for Slack bot."""

    id: str
    agent_id: str
    tenant_id: str
    bot_name: str
    slack_app_id: str
    slack_workspace_id: str | None
    slack_workspace_name: str | None
    is_active: bool
    allow_external_shared_channels: bool
    connection_status: str
    connection_mode: str
    webhook_url: str | None
    last_connected_at: str | None
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


class SlackBotStatusResponse(BaseModel):
    """Response model for Slack bot status."""

    bot_id: str
    bot_name: str
    agent_id: str
    agent_name: str | None
    workspace_id: str | None
    workspace_name: str | None
    is_active: bool
    connection_status: str
    connection_mode: str
    webhook_url: str | None
    is_running: bool
    assigned_worker: str | None
    worker_healthy: bool | None
    last_connected_at: str | None
    created_at: str
    updated_at: str


# Endpoints
@router.post("", response_model=SlackBotResponse, status_code=status.HTTP_201_CREATED)
async def create_slack_bot(
    bot_data: SlackBotCreate,
    current_account: Account = Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Create a new Slack bot configuration."""
    manager = SlackBotManager(db)

    try:
        slack_bot = await manager.create_bot(
            agent_id=bot_data.agent_id,
            tenant_id=tenant_id,
            bot_name=bot_data.bot_name,
            slack_app_id=bot_data.slack_app_id,
            slack_bot_token=bot_data.slack_bot_token,
            slack_app_token=bot_data.slack_app_token,
            slack_workspace_id=bot_data.slack_workspace_id,
            slack_workspace_name=bot_data.slack_workspace_name,
            connection_mode=bot_data.connection_mode,
            signing_secret=bot_data.signing_secret,
            created_by=current_account.id,
            allow_external_shared_channels=bot_data.allow_external_shared_channels,
        )

        return SlackBotResponse(
            id=str(slack_bot.id),
            agent_id=str(slack_bot.agent_id),
            tenant_id=str(slack_bot.tenant_id),
            bot_name=slack_bot.bot_name,
            slack_app_id=slack_bot.slack_app_id,
            slack_workspace_id=slack_bot.slack_workspace_id,
            slack_workspace_name=slack_bot.slack_workspace_name,
            is_active=slack_bot.is_active,
            allow_external_shared_channels=slack_bot.allow_external_shared_channels,
            connection_status=slack_bot.connection_status,
            connection_mode=slack_bot.connection_mode,
            webhook_url=slack_bot.webhook_url,
            last_connected_at=slack_bot.last_connected_at.isoformat() if slack_bot.last_connected_at else None,
            created_at=slack_bot.created_at.isoformat(),
            updated_at=slack_bot.updated_at.isoformat(),
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to create Slack bot: {str(e)}")


@router.get("", response_model=list[SlackBotResponse])
async def list_slack_bots(
    agent_id: UUID | None = None,
    is_active: bool | None = None,
    current_account: Account = Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """List all Slack bots for the current tenant."""
    manager = SlackBotManager(db)

    bots = await manager.list_bots(tenant_id=tenant_id, agent_id=agent_id, is_active=is_active)

    return [
        SlackBotResponse(
            id=str(bot.id),
            agent_id=str(bot.agent_id),
            tenant_id=str(bot.tenant_id),
            bot_name=bot.bot_name,
            slack_app_id=bot.slack_app_id,
            slack_workspace_id=bot.slack_workspace_id,
            slack_workspace_name=bot.slack_workspace_name,
            is_active=bot.is_active,
            allow_external_shared_channels=bot.allow_external_shared_channels,
            connection_status=bot.connection_status,
            connection_mode=bot.connection_mode,
            webhook_url=bot.webhook_url,
            last_connected_at=bot.last_connected_at.isoformat() if bot.last_connected_at else None,
            created_at=bot.created_at.isoformat(),
            updated_at=bot.updated_at.isoformat(),
        )
        for bot in bots
    ]


@router.get("/{bot_id}", response_model=SlackBotResponse)
async def get_slack_bot(
    bot_id: UUID,
    current_account: Account = Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Get a specific Slack bot by ID."""
    manager = SlackBotManager(db)

    bot = await manager.get_bot(bot_id)
    if not bot or bot.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slack bot not found")

    return SlackBotResponse(
        id=str(bot.id),
        agent_id=str(bot.agent_id),
        tenant_id=str(bot.tenant_id),
        bot_name=bot.bot_name,
        slack_app_id=bot.slack_app_id,
        slack_workspace_id=bot.slack_workspace_id,
        slack_workspace_name=bot.slack_workspace_name,
        is_active=bot.is_active,
        allow_external_shared_channels=bot.allow_external_shared_channels,
        connection_status=bot.connection_status,
        connection_mode=bot.connection_mode,
        webhook_url=bot.webhook_url,
        last_connected_at=bot.last_connected_at.isoformat() if bot.last_connected_at else None,
        created_at=bot.created_at.isoformat(),
        updated_at=bot.updated_at.isoformat(),
    )


@router.put("/{bot_id}", response_model=SlackBotResponse)
async def update_slack_bot(
    bot_id: UUID,
    bot_data: SlackBotUpdate,
    current_account: Account = Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Update a Slack bot configuration."""
    manager = SlackBotManager(db)

    # Verify ownership
    bot = await manager.get_bot(bot_id)
    if not bot or bot.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slack bot not found")

    try:
        updated_bot = await manager.update_bot(
            bot_id=bot_id,
            bot_name=bot_data.bot_name,
            slack_bot_token=bot_data.slack_bot_token,
            slack_app_token=bot_data.slack_app_token,
            signing_secret=bot_data.signing_secret,
            is_active=bot_data.is_active,
            allow_external_shared_channels=bot_data.allow_external_shared_channels,
        )

        return SlackBotResponse(
            id=str(updated_bot.id),
            agent_id=str(updated_bot.agent_id),
            tenant_id=str(updated_bot.tenant_id),
            bot_name=updated_bot.bot_name,
            slack_app_id=updated_bot.slack_app_id,
            slack_workspace_id=updated_bot.slack_workspace_id,
            slack_workspace_name=updated_bot.slack_workspace_name,
            is_active=updated_bot.is_active,
            allow_external_shared_channels=updated_bot.allow_external_shared_channels,
            connection_status=updated_bot.connection_status,
            connection_mode=updated_bot.connection_mode,
            webhook_url=updated_bot.webhook_url,
            last_connected_at=updated_bot.last_connected_at.isoformat() if updated_bot.last_connected_at else None,
            created_at=updated_bot.created_at.isoformat(),
            updated_at=updated_bot.updated_at.isoformat(),
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to update Slack bot: {str(e)}")


@router.delete("/{bot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_slack_bot(
    bot_id: UUID,
    current_account: Account = Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Delete a Slack bot."""
    manager = SlackBotManager(db)

    # Verify ownership
    bot = await manager.get_bot(bot_id)
    if not bot or bot.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slack bot not found")

    success = await manager.delete_bot(bot_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to delete Slack bot")


@router.post("/{bot_id}/start", response_model=dict)
async def start_slack_bot(
    bot_id: UUID,
    current_account: Account = Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Start a Slack bot."""
    manager = SlackBotManager(db)

    # Verify ownership
    bot = await manager.get_bot(bot_id)
    if not bot or bot.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slack bot not found")

    success = await manager.start_bot(bot_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to start Slack bot")

    return {"message": "Slack bot started successfully", "bot_id": str(bot_id)}


@router.post("/{bot_id}/stop", response_model=dict)
async def stop_slack_bot(
    bot_id: UUID,
    current_account: Account = Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Stop a running Slack bot."""
    manager = SlackBotManager(db)

    # Verify ownership
    bot = await manager.get_bot(bot_id)
    if not bot or bot.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slack bot not found")

    success = await manager.stop_bot(bot_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to stop Slack bot")

    return {"message": "Slack bot stopped successfully", "bot_id": str(bot_id)}


@router.post("/{bot_id}/restart", response_model=dict)
async def restart_slack_bot(
    bot_id: UUID,
    current_account: Account = Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Restart a Slack bot."""
    manager = SlackBotManager(db)

    # Verify ownership
    bot = await manager.get_bot(bot_id)
    if not bot or bot.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slack bot not found")

    success = await manager.restart_bot(bot_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to restart Slack bot")

    return {"message": "Slack bot restarted successfully", "bot_id": str(bot_id)}


@router.get("/{bot_id}/status", response_model=SlackBotStatusResponse)
async def get_slack_bot_status(
    bot_id: UUID,
    current_account: Account = Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Get detailed status of a Slack bot."""
    manager = SlackBotManager(db)

    # Verify ownership
    bot = await manager.get_bot(bot_id)
    if not bot or bot.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slack bot not found")

    status_info = await manager.get_bot_status(bot_id)

    if "error" in status_info:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=status_info["error"])

    return SlackBotStatusResponse(**status_info)
