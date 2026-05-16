"""Telegram Bot REST API endpoints."""

import logging
import time
from collections import defaultdict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.models import Account
from src.models.agent import Agent
from src.models.telegram_bot import TelegramBot
from src.services.telegram.telegram_bot_manager import TelegramBotManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telegram-bots", tags=["telegram-bots"])
public_router = APIRouter()  # Public routes for webhook (no auth)


# =====================
# Webhook Rate Limiter
# =====================


class TelegramWebhookRateLimiter:
    """Rate limiter for Telegram webhook endpoints."""

    def __init__(self, requests_per_minute: int = 60, requests_per_hour: int = 1000):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.minute_window: dict[str, list[float]] = defaultdict(list)
        self.hour_window: dict[str, list[float]] = defaultdict(list)
        self._last_cleanup = time.time()

    def is_rate_limited(self, key: str) -> tuple[bool, str]:
        """Check if a bot is rate limited."""
        current_time = time.time()
        self._cleanup_if_needed(current_time)

        minute_requests = [t for t in self.minute_window[key] if current_time - t < 60]
        if len(minute_requests) >= self.requests_per_minute:
            return True, f"Rate limit exceeded: {self.requests_per_minute} requests per minute"

        hour_requests = [t for t in self.hour_window[key] if current_time - t < 3600]
        if len(hour_requests) >= self.requests_per_hour:
            return True, f"Rate limit exceeded: {self.requests_per_hour} requests per hour"

        return False, ""

    def record_request(self, key: str) -> None:
        """Record a request for rate limiting."""
        current_time = time.time()
        self.minute_window[key].append(current_time)
        self.hour_window[key].append(current_time)

    def _cleanup_if_needed(self, current_time: float) -> None:
        """Clean up old entries periodically."""
        if current_time - self._last_cleanup < 300:
            return

        self._last_cleanup = current_time

        for key in list(self.minute_window.keys()):
            self.minute_window[key] = [t for t in self.minute_window[key] if current_time - t < 60]
            if not self.minute_window[key]:
                del self.minute_window[key]

        for key in list(self.hour_window.keys()):
            self.hour_window[key] = [t for t in self.hour_window[key] if current_time - t < 3600]
            if not self.hour_window[key]:
                del self.hour_window[key]


telegram_webhook_rate_limiter = TelegramWebhookRateLimiter()


# =====================
# Request/Response Models
# =====================


class CreateTelegramBotRequest(BaseModel):
    """Request model for creating a Telegram bot."""

    agent_id: str = Field(..., description="ID of the agent to connect")
    bot_name: str = Field(..., min_length=1, max_length=255, description="Display name for the bot")
    bot_token: str = Field(..., min_length=40, description="Bot token from BotFather")
    use_webhook: bool = Field(default=False, description="Use webhook instead of long polling")
    webhook_url: str | None = Field(default=None, description="Webhook URL if use_webhook is true")
    webhook_secret: str | None = Field(default=None, description="Secret for webhook validation")


class UpdateTelegramBotRequest(BaseModel):
    """Request model for updating a Telegram bot."""

    bot_name: str | None = Field(default=None, min_length=1, max_length=255)
    bot_token: str | None = Field(default=None, min_length=40)
    use_webhook: bool | None = Field(default=None)
    webhook_url: str | None = Field(default=None)
    webhook_secret: str | None = Field(default=None)
    is_active: bool | None = Field(default=None)


class ValidateTokenRequest(BaseModel):
    """Request model for validating a bot token."""

    bot_token: str = Field(..., min_length=40, description="Bot token to validate")


class TelegramBotResponse(BaseModel):
    """Response model for Telegram bot."""

    id: str
    agent_id: str
    bot_name: str
    bot_username: str | None
    telegram_bot_id: int | None
    use_webhook: bool
    is_active: bool
    connection_status: str
    last_connected_at: str | None
    last_error: str | None
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


class TelegramBotStatusResponse(BaseModel):
    """Response model for bot status."""

    bot_id: str
    bot_name: str
    bot_username: str | None
    telegram_bot_id: int | None
    agent_id: str
    agent_name: str | None
    use_webhook: bool
    is_active: bool
    connection_status: str
    is_running: bool
    last_connected_at: str | None
    last_error: str | None
    created_at: str
    updated_at: str


# =====================
# Helper Functions
# =====================


def _bot_to_response(bot) -> TelegramBotResponse:
    """Convert TelegramBot model to response."""
    return TelegramBotResponse(
        id=str(bot.id),
        agent_id=str(bot.agent_id),
        bot_name=bot.bot_name,
        bot_username=bot.bot_username,
        telegram_bot_id=bot.telegram_bot_id,
        use_webhook=bot.use_webhook,
        is_active=bot.is_active,
        connection_status=bot.connection_status,
        last_connected_at=bot.last_connected_at.isoformat() if bot.last_connected_at else None,
        last_error=bot.last_error,
        created_at=bot.created_at.isoformat(),
        updated_at=bot.updated_at.isoformat(),
    )


# =====================
# API Endpoints
# =====================


@router.post("", response_model=TelegramBotResponse)
async def create_telegram_bot(
    request: CreateTelegramBotRequest,
    db: AsyncSession = Depends(get_async_db),
    current_account: Account = Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """
    Create a new Telegram bot configuration.

    The bot token is obtained from BotFather (@BotFather) on Telegram.
    """
    try:
        # Validate agent exists and belongs to tenant
        result = await db.execute(select(Agent).filter(Agent.id == request.agent_id, Agent.tenant_id == tenant_id))
        agent = result.scalar_one_or_none()

        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        manager = TelegramBotManager(db)
        bot = await manager.create_bot(
            agent_id=UUID(request.agent_id),
            tenant_id=tenant_id,
            bot_name=request.bot_name,
            bot_token=request.bot_token,
            use_webhook=request.use_webhook,
            webhook_url=request.webhook_url,
            webhook_secret=request.webhook_secret,
            created_by=current_account.id,
        )

        return _bot_to_response(bot)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating Telegram bot: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create Telegram bot")


@router.post("/validate-token")
async def validate_telegram_token(
    request: ValidateTokenRequest,
    db: AsyncSession = Depends(get_async_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """
    Validate a Telegram bot token before creating a bot.

    Returns bot information if the token is valid.
    """
    try:
        manager = TelegramBotManager(db)
        result = await manager.validate_token(request.bot_token)

        if result["success"]:
            return {"valid": True, "message": result["message"], "bot_info": result["details"]}
        else:
            return {"valid": False, "message": result["message"], "bot_info": {}}

    except Exception as e:
        logger.warning(f"Error validating Telegram token: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to validate token")


@router.get("", response_model=list[TelegramBotResponse])
async def list_telegram_bots(
    agent_id: str | None = Query(default=None, description="Filter by agent ID"),
    is_active: bool | None = Query(default=None, description="Filter by active status"),
    db: AsyncSession = Depends(get_async_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """List all Telegram bots for the current tenant."""
    try:
        manager = TelegramBotManager(db)
        bots = await manager.list_bots(
            tenant_id=tenant_id, agent_id=UUID(agent_id) if agent_id else None, is_active=is_active
        )

        return [_bot_to_response(bot) for bot in bots]

    except Exception as e:
        logger.error(f"Error listing Telegram bots: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list Telegram bots")


@router.get("/{bot_id}", response_model=TelegramBotResponse)
async def get_telegram_bot(
    bot_id: str, db: AsyncSession = Depends(get_async_db), tenant_id: UUID = Depends(get_current_tenant_id)
):
    """Get a specific Telegram bot by ID."""
    try:
        manager = TelegramBotManager(db)
        bot = await manager.get_bot(UUID(bot_id))

        if not bot or bot.tenant_id != tenant_id or bot.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Telegram bot not found")

        return _bot_to_response(bot)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Telegram bot: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get Telegram bot")


@router.put("/{bot_id}", response_model=TelegramBotResponse)
async def update_telegram_bot(
    bot_id: str,
    request: UpdateTelegramBotRequest,
    db: AsyncSession = Depends(get_async_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Update a Telegram bot configuration."""
    try:
        # Check bot exists and belongs to tenant
        manager = TelegramBotManager(db)
        bot = await manager.get_bot(UUID(bot_id))

        if not bot or bot.tenant_id != tenant_id or bot.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Telegram bot not found")

        # Update bot
        updated_bot = await manager.update_bot(
            bot_id=UUID(bot_id),
            bot_name=request.bot_name,
            bot_token=request.bot_token,
            use_webhook=request.use_webhook,
            webhook_url=request.webhook_url,
            webhook_secret=request.webhook_secret,
            is_active=request.is_active,
        )

        return _bot_to_response(updated_bot)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating Telegram bot: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update Telegram bot")


@router.delete("/{bot_id}")
async def delete_telegram_bot(
    bot_id: str, db: AsyncSession = Depends(get_async_db), tenant_id: UUID = Depends(get_current_tenant_id)
):
    """Delete a Telegram bot (soft delete)."""
    try:
        # Check bot exists and belongs to tenant
        manager = TelegramBotManager(db)
        bot = await manager.get_bot(UUID(bot_id))

        if not bot or bot.tenant_id != tenant_id or bot.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Telegram bot not found")

        success = await manager.delete_bot(UUID(bot_id))

        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete bot")

        return {"message": "Telegram bot deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting Telegram bot: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete Telegram bot")


@router.post("/{bot_id}/start")
async def start_telegram_bot(
    bot_id: str, db: AsyncSession = Depends(get_async_db), tenant_id: UUID = Depends(get_current_tenant_id)
):
    """
    Start a Telegram bot.

    For polling mode (use_webhook=false): Begins long polling for messages.
    For webhook mode (use_webhook=true): Registers webhook URL with Telegram.
    """
    try:
        from src.config import settings

        # Check bot exists and belongs to tenant
        manager = TelegramBotManager(db)
        bot = await manager.get_bot(UUID(bot_id))

        if not bot or bot.tenant_id != tenant_id or bot.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Telegram bot not found")

        # For webhook mode, require webhook_base_url
        if bot.use_webhook and not settings.webhook_base_url:
            raise HTTPException(
                status_code=400, detail="WEBHOOK_BASE_URL environment variable is required for webhook mode"
            )

        success = await manager.start_bot(UUID(bot_id), webhook_base_url=settings.webhook_base_url)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to start bot")

        mode = "webhook" if bot.use_webhook else "polling"
        return {"message": f"Telegram bot started successfully ({mode} mode)", "connection_status": "connected"}

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error starting Telegram bot: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to start Telegram bot")


@router.post("/{bot_id}/stop")
async def stop_telegram_bot(
    bot_id: str, db: AsyncSession = Depends(get_async_db), tenant_id: UUID = Depends(get_current_tenant_id)
):
    """Stop a running Telegram bot."""
    try:
        # Check bot exists and belongs to tenant
        manager = TelegramBotManager(db)
        bot = await manager.get_bot(UUID(bot_id))

        if not bot or bot.tenant_id != tenant_id or bot.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Telegram bot not found")

        success = await manager.stop_bot(UUID(bot_id))

        if not success:
            raise HTTPException(status_code=500, detail="Failed to stop bot")

        return {"message": "Telegram bot stopped successfully", "connection_status": "disconnected"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping Telegram bot: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to stop Telegram bot")


@router.post("/{bot_id}/restart")
async def restart_telegram_bot(
    bot_id: str, db: AsyncSession = Depends(get_async_db), tenant_id: UUID = Depends(get_current_tenant_id)
):
    """Restart a Telegram bot."""
    try:
        # Check bot exists and belongs to tenant
        manager = TelegramBotManager(db)
        bot = await manager.get_bot(UUID(bot_id))

        if not bot or bot.tenant_id != tenant_id or bot.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Telegram bot not found")

        success = await manager.restart_bot(UUID(bot_id))

        if not success:
            raise HTTPException(status_code=500, detail="Failed to restart bot")

        return {"message": "Telegram bot restarted successfully", "connection_status": "connected"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error restarting Telegram bot: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to restart Telegram bot")


@router.get("/{bot_id}/status", response_model=TelegramBotStatusResponse)
async def get_telegram_bot_status(
    bot_id: str, db: AsyncSession = Depends(get_async_db), tenant_id: UUID = Depends(get_current_tenant_id)
):
    """Get detailed status of a Telegram bot."""
    try:
        # Check bot exists and belongs to tenant
        manager = TelegramBotManager(db)
        bot = await manager.get_bot(UUID(bot_id))

        if not bot or bot.tenant_id != tenant_id or bot.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Telegram bot not found")

        status = await manager.get_bot_status(UUID(bot_id))

        if "error" in status:
            raise HTTPException(status_code=404, detail=status["error"])

        return TelegramBotStatusResponse(**status)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Telegram bot status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get bot status")


# =====================
# Public Webhook Endpoint
# =====================


@public_router.post("/api/webhooks/telegram/{bot_id}")
async def receive_telegram_webhook(bot_id: str, request: Request, db: AsyncSession = Depends(get_async_db)):
    """
    Receive and process Telegram webhook updates.

    This is a public endpoint that Telegram calls when updates are received.
    No authentication required - verification is done via X-Telegram-Bot-Api-Secret-Token header.
    """
    # Rate limiting
    is_limited, limit_reason = telegram_webhook_rate_limiter.is_rate_limited(bot_id)
    if is_limited:
        logger.warning(f"Rate limit exceeded for Telegram bot: {bot_id[:10]}...")
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=limit_reason)

    telegram_webhook_rate_limiter.record_request(bot_id)

    # Find bot
    try:
        bot_uuid = UUID(bot_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid bot ID")

    result = await db.execute(
        select(TelegramBot).filter(
            TelegramBot.id == bot_uuid,
            TelegramBot.deleted_at.is_(None),
        )
    )
    telegram_bot = result.scalar_one_or_none()

    if not telegram_bot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot not found")

    if not telegram_bot.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bot is inactive")

    if not telegram_bot.use_webhook:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bot is not configured for webhooks")

    # Verify secret token
    from src.services.telegram.telegram_webhook_service import TelegramWebhookService

    webhook_service = TelegramWebhookService(db)
    secret_token = request.headers.get("x-telegram-bot-api-secret-token")

    if not webhook_service.verify_webhook_secret(telegram_bot, secret_token):
        logger.warning(f"Invalid webhook secret for bot {bot_id}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid secret token")

    # Parse request body
    try:
        update_data = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse webhook body: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body")

    # Process update - returns quickly, processing happens in background
    result = await webhook_service.process_update(telegram_bot, update_data)

    # Always return 200 OK to Telegram to acknowledge receipt
    return {"ok": True, **result}
