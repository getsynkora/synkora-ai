"""Slack Bot Manager for managing bot lifecycle and operations."""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.redis import get_redis
from ...models.agent import Agent
from ...models.slack_bot import SlackBot
from ...services.agents.security import encrypt_value
from ...services.bot_worker.bot_deployment_service import BotDeploymentService

logger = logging.getLogger(__name__)


class SlackBotManager:
    """Manager for Slack bot operations."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        # Use bot deployment service for worker pool architecture
        redis_client = get_redis()
        self.deployment_service = BotDeploymentService(db_session, redis_client)

    async def create_bot(
        self,
        agent_id: UUID,
        tenant_id: UUID,
        bot_name: str,
        slack_app_id: str,
        slack_bot_token: str,
        slack_app_token: str | None = None,
        slack_workspace_id: str | None = None,
        slack_workspace_name: str | None = None,
        connection_mode: str = "socket",
        signing_secret: str | None = None,
        created_by: UUID | None = None,
        allow_external_shared_channels: bool = False,
    ) -> SlackBot:
        """
        Create a new Slack bot configuration.

        Args:
            agent_id: ID of the agent to connect
            tenant_id: ID of the tenant
            bot_name: Name of the bot
            slack_app_id: Slack app ID
            slack_bot_token: Bot user OAuth token (xoxb-*)
            slack_app_token: App-level token for Socket Mode (xapp-*). Required for socket mode.
            slack_workspace_id: Slack workspace ID (optional, auto-detected)
            slack_workspace_name: Slack workspace name (optional)
            connection_mode: Connection mode - "socket" or "event" (default: "socket")
            signing_secret: Signing secret for Event Mode verification. Required for event mode.

        Returns:
            SlackBot: Created bot instance
        """
        try:
            # Validate connection mode and required fields
            if connection_mode not in ("socket", "event"):
                raise ValueError(f"Invalid connection mode: {connection_mode}. Must be 'socket' or 'event'.")

            if connection_mode == "socket" and not slack_app_token:
                raise ValueError("App-level token (slack_app_token) is required for Socket Mode")

            if connection_mode == "event" and not signing_secret:
                raise ValueError("Signing secret is required for Event Mode")

            # Encrypt tokens
            encrypted_bot_token = encrypt_value(slack_bot_token)
            encrypted_app_token = encrypt_value(slack_app_token) if slack_app_token else None
            encrypted_signing_secret = encrypt_value(signing_secret) if signing_secret else None

            # Create bot (webhook URL will be set after creation for event mode)
            # Event Mode bots are "connected" immediately since they use webhooks
            slack_bot = SlackBot(
                agent_id=agent_id,
                tenant_id=tenant_id,
                bot_name=bot_name,
                slack_app_id=slack_app_id,
                slack_bot_token=encrypted_bot_token,
                slack_app_token=encrypted_app_token,
                slack_workspace_id=slack_workspace_id,
                slack_workspace_name=slack_workspace_name,
                connection_mode=connection_mode,
                signing_secret=encrypted_signing_secret,
                is_active=True,
                allow_external_shared_channels=allow_external_shared_channels,
                connection_status="connected" if connection_mode == "event" else "disconnected",
                created_by=created_by,
            )

            self.db_session.add(slack_bot)
            await self.db_session.commit()
            await self.db_session.refresh(slack_bot)

            # Generate webhook URL for event mode after we have the bot ID
            if connection_mode == "event":
                slack_bot.webhook_url = self._generate_webhook_url(slack_bot.id)
                await self.db_session.commit()
                await self.db_session.refresh(slack_bot)

            logger.info(f"Created Slack bot {bot_name} (ID: {slack_bot.id}, mode: {connection_mode})")
            return slack_bot

        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Failed to create Slack bot: {str(e)}")
            raise

    def _generate_webhook_url(self, bot_id: UUID) -> str:
        """Generate the webhook URL for Event Mode.

        Args:
            bot_id: Bot ID

        Returns:
            Webhook URL string
        """
        import os

        from ...config import settings

        # Priority: APP_BASE_URL env var → webhook_base_url setting → fallback
        base_url = (
            os.getenv("APP_BASE_URL")
            or getattr(settings, "webhook_base_url", None)
            or getattr(settings, "api_base_url", None)
        )
        if not base_url:
            # Last resort: construct from host/port (will be wrong in production
            # if APP_BASE_URL is not set — ensure that env var is configured)
            host = getattr(settings, "api_host", "localhost")
            port = getattr(settings, "api_port", 5001)
            protocol = "https" if getattr(settings, "is_production", False) else "http"
            base_url = f"{protocol}://{host}:{port}"

        return f"{base_url.rstrip('/')}/api/webhooks/slack/{bot_id}/events"

    async def update_bot(
        self,
        bot_id: UUID,
        bot_name: str | None = None,
        slack_bot_token: str | None = None,
        slack_app_token: str | None = None,
        signing_secret: str | None = None,
        is_active: bool | None = None,
        allow_external_shared_channels: bool | None = None,
    ) -> SlackBot:
        """
        Update Slack bot configuration.

        Args:
            bot_id: ID of the bot to update
            bot_name: New bot name (optional)
            slack_bot_token: New bot token (optional)
            slack_app_token: New app token (optional, for Socket Mode)
            signing_secret: New signing secret (optional, for Event Mode)
            is_active: New active status (optional)

        Returns:
            SlackBot: Updated bot instance
        """
        try:
            slack_bot = await self.db_session.get(SlackBot, bot_id)
            if not slack_bot:
                raise ValueError(f"Slack bot {bot_id} not found")

            # Track if bot was running before update
            was_running = slack_bot.connection_status == "connected"
            tokens_updated = slack_bot_token is not None or slack_app_token is not None or signing_secret is not None

            # Stop bot if it's running and tokens are being updated (Socket Mode only)
            if tokens_updated and was_running and slack_bot.is_socket_mode:
                logger.info(f"Stopping bot {bot_id} for token update")
                await self.deployment_service.deactivate_slack_bot(bot_id)
                import asyncio

                await asyncio.sleep(1)

            # Update fields
            if bot_name is not None:
                slack_bot.bot_name = bot_name

            if slack_bot_token is not None:
                slack_bot.slack_bot_token = encrypt_value(slack_bot_token)

            if slack_app_token is not None:
                slack_bot.slack_app_token = encrypt_value(slack_app_token)

            if signing_secret is not None:
                slack_bot.signing_secret = encrypt_value(signing_secret)

            if is_active is not None:
                slack_bot.is_active = is_active
                # Stop bot if deactivated (Socket Mode only)
                if not is_active and slack_bot.connection_status == "connected" and slack_bot.is_socket_mode:
                    await self.deployment_service.deactivate_slack_bot(bot_id)

            if allow_external_shared_channels is not None:
                slack_bot.allow_external_shared_channels = allow_external_shared_channels

            slack_bot.updated_at = datetime.utcnow()
            await self.db_session.commit()
            await self.db_session.refresh(slack_bot)

            # Restart bot if it was running and tokens were updated (Socket Mode only)
            if tokens_updated and was_running and slack_bot.is_active and slack_bot.is_socket_mode:
                logger.info(f"Restarting bot {bot_id} with new tokens")
                import asyncio

                await asyncio.sleep(1)
                await self.start_bot(bot_id)

            logger.info(f"Updated Slack bot {bot_id}")
            return slack_bot

        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Failed to update Slack bot {bot_id}: {str(e)}")
            raise

    async def delete_bot(self, bot_id: UUID) -> bool:
        """
        Delete a Slack bot (soft delete).

        Args:
            bot_id: ID of the bot to delete

        Returns:
            bool: True if deleted successfully
        """
        try:
            slack_bot = await self.db_session.get(SlackBot, bot_id)
            if not slack_bot:
                return False

            # Stop bot if running - force stop to ensure cleanup
            logger.info(f"Stopping bot {bot_id} before deletion")
            await self.deployment_service.deactivate_slack_bot(bot_id)

            # Wait for clean shutdown
            import asyncio

            await asyncio.sleep(1)

            # Soft delete
            slack_bot.deleted_at = datetime.utcnow()
            slack_bot.is_active = False
            slack_bot.connection_status = "disconnected"

            await self.db_session.commit()

            logger.info(f"Deleted Slack bot {bot_id}")
            return True

        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Failed to delete Slack bot {bot_id}: {str(e)}")
            return False

    async def get_bot(self, bot_id: UUID) -> SlackBot | None:
        """Get a Slack bot by ID."""
        return await self.db_session.get(SlackBot, bot_id)

    async def list_bots(
        self, tenant_id: UUID | None = None, agent_id: UUID | None = None, is_active: bool | None = None
    ) -> list[SlackBot]:
        """
        List Slack bots with optional filters.

        Args:
            tenant_id: Filter by tenant ID (optional)
            agent_id: Filter by agent ID (optional)
            is_active: Filter by active status (optional)

        Returns:
            List[SlackBot]: List of bots
        """
        stmt = select(SlackBot).where(SlackBot.deleted_at.is_(None))

        if tenant_id:
            stmt = stmt.where(SlackBot.tenant_id == tenant_id)

        if agent_id:
            stmt = stmt.where(SlackBot.agent_id == agent_id)

        if is_active is not None:
            stmt = stmt.where(SlackBot.is_active == is_active)

        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())

    async def start_bot(self, bot_id: UUID) -> bool:
        """
        Start a Slack bot.

        For Socket Mode: Activates via the worker pool.
        For Event Mode: Marks as connected (no worker needed, webhook handles events).

        Args:
            bot_id: ID of the bot to start

        Returns:
            bool: True if activation was successful
        """
        try:
            slack_bot = await self.db_session.get(SlackBot, bot_id)
            if not slack_bot:
                raise ValueError(f"Slack bot {bot_id} not found")

            # Handle based on connection mode
            if slack_bot.is_event_mode:
                # Event Mode: No worker needed, just mark as connected
                slack_bot.is_active = True
                slack_bot.connection_status = "connected"
                slack_bot.last_connected_at = datetime.utcnow()

                # Generate webhook URL if not already set
                if not slack_bot.webhook_url:
                    slack_bot.webhook_url = self._generate_webhook_url(bot_id)

                await self.db_session.commit()
                logger.info(f"Event Mode Slack bot {bot_id} marked as connected")
                return True
            else:
                # Socket Mode: Activate via worker pool
                result = await self.deployment_service.activate_slack_bot(bot_id)

                if result.get("success"):
                    logger.info(
                        f"Activation request sent for Slack bot {bot_id}, assigned to worker {result.get('assigned_worker')}"
                    )
                    return True
                else:
                    logger.error(f"Failed to activate Slack bot {bot_id}: {result.get('error')}")
                    return False

        except Exception as e:
            logger.error(f"Error starting Slack bot {bot_id}: {str(e)}")
            return False

    async def stop_bot(self, bot_id: UUID) -> bool:
        """
        Stop a running Slack bot.

        For Socket Mode: Deactivates via the worker pool.
        For Event Mode: Marks as disconnected (no worker to stop).

        Args:
            bot_id: ID of the bot to stop

        Returns:
            bool: True if deactivation was successful
        """
        try:
            slack_bot = await self.db_session.get(SlackBot, bot_id)
            if not slack_bot:
                raise ValueError(f"Slack bot {bot_id} not found")

            if slack_bot.is_event_mode:
                # Event Mode: Just mark as disconnected
                slack_bot.connection_status = "disconnected"
                await self.db_session.commit()
                logger.info(f"Event Mode Slack bot {bot_id} marked as disconnected")
                return True
            else:
                # Socket Mode: Deactivate via worker pool
                result = await self.deployment_service.deactivate_slack_bot(bot_id)
                return result.get("success", False)
        except Exception as e:
            logger.error(f"Error stopping Slack bot {bot_id}: {str(e)}")
            return False

    async def restart_bot(self, bot_id: UUID) -> bool:
        """
        Restart a Slack bot.

        For Socket Mode: Restarts via the worker pool.
        For Event Mode: Just refreshes the connection status.

        Args:
            bot_id: ID of the bot to restart

        Returns:
            bool: True if restart was successful
        """
        try:
            slack_bot = await self.db_session.get(SlackBot, bot_id)
            if not slack_bot:
                raise ValueError(f"Slack bot {bot_id} not found")

            if slack_bot.is_event_mode:
                # Event Mode: Just refresh connection status
                slack_bot.connection_status = "connected"
                slack_bot.last_connected_at = datetime.utcnow()
                await self.db_session.commit()
                logger.info(f"Event Mode Slack bot {bot_id} restarted (refreshed status)")
                return True
            else:
                # Socket Mode: Restart via worker pool
                from ...bot_worker.redis_state import BotType

                result = self.deployment_service.restart_bot(str(bot_id), BotType.SLACK)
                return result.get("success", False)
        except Exception as e:
            logger.error(f"Error restarting Slack bot {bot_id}: {str(e)}")
            return False

    async def get_bot_status(self, bot_id: UUID) -> dict[str, Any]:
        """
        Get detailed status of a Slack bot.

        Args:
            bot_id: ID of the bot

        Returns:
            Dict: Bot status information
        """
        slack_bot = await self.db_session.get(SlackBot, bot_id)
        if not slack_bot:
            return {"error": "Bot not found"}

        # Get deployment status from worker pool (only for Socket Mode)
        deployment_status = {}
        if slack_bot.is_socket_mode:
            deployment_status = self.deployment_service.get_bot_status(str(bot_id))

        # Get agent info
        agent = await self.db_session.get(Agent, slack_bot.agent_id)

        # For Event Mode, bots are always "running" when active (no worker needed)
        if slack_bot.is_event_mode:
            is_running = slack_bot.is_active
            # Event Mode bots are always "connected" when active
            connection_status = "connected" if slack_bot.is_active else "disconnected"
        else:
            is_running = deployment_status.get("is_deployed", False)
            connection_status = slack_bot.connection_status

        return {
            "bot_id": str(slack_bot.id),
            "bot_name": slack_bot.bot_name,
            "agent_id": str(slack_bot.agent_id),
            "agent_name": agent.agent_name if agent else None,
            "workspace_id": slack_bot.slack_workspace_id,
            "workspace_name": slack_bot.slack_workspace_name,
            "is_active": slack_bot.is_active,
            "connection_status": connection_status,
            "connection_mode": slack_bot.connection_mode,
            "webhook_url": slack_bot.webhook_url if slack_bot.is_event_mode else None,
            "is_running": is_running,
            "assigned_worker": deployment_status.get("assigned_worker") if slack_bot.is_socket_mode else None,
            "worker_healthy": deployment_status.get("worker_healthy") if slack_bot.is_socket_mode else None,
            "last_connected_at": slack_bot.last_connected_at.isoformat() if slack_bot.last_connected_at else None,
            "created_at": slack_bot.created_at.isoformat(),
            "updated_at": slack_bot.updated_at.isoformat(),
        }

    async def start_all_active_bots(self, tenant_id: UUID | None = None) -> dict[str, int]:
        """
        Start all active bots, optionally filtered by tenant.

        Args:
            tenant_id: Filter by tenant ID (optional)

        Returns:
            Dict: Statistics about started bots
        """
        bots = await self.list_bots(tenant_id=tenant_id, is_active=True)

        started = 0
        failed = 0

        for bot in bots:
            if bot.connection_status != "connected":
                success = await self.start_bot(bot.id)
                if success:
                    started += 1
                else:
                    failed += 1

        logger.info(f"Started {started} bots, {failed} failed")

        return {
            "total": len(bots),
            "started": started,
            "failed": failed,
            "already_running": len(bots) - started - failed,
        }
