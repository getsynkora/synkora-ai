"""Slack Socket Mode service for handling real-time events."""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.slack_bot import SlackBot
from ...services.agents.agent_manager import AgentManager
from ...services.agents.security import decrypt_value
from .slack_message_handler import SlackMessageHandler

logger = logging.getLogger(__name__)

# Fallback prompts when agent has no suggestion_prompts configured
_DEFAULT_SUGGESTED_PROMPTS = [
    {"title": "What can you do?", "message": "What are your capabilities?"},
    {"title": "Summarize recent messages", "message": "Summarize the last 20 messages in this channel"},
    {"title": "Help me draft a message", "message": "Help me write a professional message to my team about..."},
]


class SlackSocketService:
    """Service for managing Slack Socket Mode connections and events."""

    # Class-level storage for active handlers (shared across all instances)
    _active_handlers: dict[str, AsyncSocketModeHandler] = {}

    def __init__(self, db_session: AsyncSession, agent_manager: AgentManager | None = None):
        self.db_session = db_session
        # OPTIMIZATION: Allow passing a shared AgentManager to avoid re-creation overhead
        self.agent_manager = agent_manager or AgentManager()

    @property
    def active_handlers(self) -> dict[str, AsyncSocketModeHandler]:
        """Access the shared active_handlers dictionary."""
        return SlackSocketService._active_handlers

    async def start_bot(self, slack_bot: SlackBot) -> bool:
        """
        Start a Slack bot with Socket Mode connection.

        Args:
            slack_bot: SlackBot instance to start

        Returns:
            bool: True if started successfully
        """
        try:
            # Decrypt tokens
            bot_token = decrypt_value(slack_bot.slack_bot_token)
            app_token = decrypt_value(slack_bot.slack_app_token)

            # Create Slack app
            app = AsyncApp(token=bot_token)

            # Auto-detect workspace info and this bot's own Slack user id (for @-mention
            # support) if not already set — backfills bots created before that field existed.
            if not slack_bot.slack_workspace_id or not slack_bot.slack_bot_user_id:
                try:
                    client = AsyncWebClient(token=bot_token)
                    auth_response = await client.auth_test()
                    slack_bot.slack_workspace_id = auth_response["team_id"]
                    slack_bot.slack_workspace_name = auth_response["team"]
                    slack_bot.slack_bot_user_id = auth_response.get("user_id")
                    logger.info(
                        f"Auto-detected workspace: {slack_bot.slack_workspace_name} ({slack_bot.slack_workspace_id}), "
                        f"bot_user_id: {slack_bot.slack_bot_user_id}"
                    )
                except Exception as e:
                    logger.warning(f"Failed to auto-detect workspace/bot user info: {str(e)}")

            # Register event handlers
            self._register_event_handlers(app, slack_bot)

            # Create Socket Mode handler
            handler = AsyncSocketModeHandler(app, app_token)

            # Start the handler in background
            asyncio.create_task(handler.start_async())

            # Store handler reference
            self.active_handlers[str(slack_bot.id)] = handler

            # Update bot status
            slack_bot.connection_status = "connected"
            slack_bot.last_connected_at = datetime.now(UTC)
            await self.db_session.commit()

            logger.info(f"Started Slack bot {slack_bot.bot_name} (ID: {slack_bot.id})")
            return True

        except Exception as e:
            logger.error(f"Failed to start Slack bot {slack_bot.id}: {str(e)}")
            slack_bot.connection_status = "error"
            await self.db_session.commit()
            return False

    async def stop_bot(self, slack_bot_id: UUID) -> bool:
        """
        Stop a running Slack bot.

        Args:
            slack_bot_id: ID of the bot to stop

        Returns:
            bool: True if stopped successfully
        """
        try:
            bot_id_str = str(slack_bot_id)

            if bot_id_str in self.active_handlers:
                handler = self.active_handlers[bot_id_str]
                await handler.close_async()
                del self.active_handlers[bot_id_str]

                logger.info(f"Stopped Slack bot {slack_bot_id}")
            else:
                logger.info(f"Slack bot {slack_bot_id} was not running in active handlers")

            # Update bot status regardless of whether it was in active_handlers
            slack_bot = await self.db_session.get(SlackBot, slack_bot_id)
            if slack_bot:
                slack_bot.connection_status = "disconnected"
                await self.db_session.commit()

            # Always return True - stopping an already-stopped bot is not an error
            return True

        except Exception as e:
            logger.error(f"Failed to stop Slack bot {slack_bot_id}: {str(e)}")
            return False

    def _register_event_handlers(self, app: AsyncApp, slack_bot: SlackBot):
        """Register event handlers for the Slack app."""

        @app.event("app_mention")
        async def handle_app_mention(event, say, client):
            """Handle @mentions of the bot."""
            await self._handle_message(
                slack_bot=slack_bot,
                channel_id=event["channel"],
                user_id=event["user"],
                text=event["text"],
                message_ts=event.get("ts"),
                thread_ts=event.get("thread_ts"),
                say=say,
                client=client,
            )

        @app.event("message")
        async def handle_message(event, say, client):
            """Handle DMs; channel messages are handled via app_mention."""
            subtype = event.get("subtype")
            if subtype == "bot_message" or event.get("bot_id"):
                return
            if subtype in ("message_changed", "message_deleted", "channel_join", "channel_leave"):
                return

            channel_id = event.get("channel", "")
            channel_type = event.get("channel_type")
            is_dm = channel_type == "im" or channel_id.startswith("D")

            if is_dm:
                logger.info(f"Received DM in channel {channel_id} from user {event.get('user')}")
                await self._handle_message(
                    slack_bot=slack_bot,
                    channel_id=channel_id,
                    user_id=event["user"],
                    text=event.get("text", ""),
                    message_ts=event.get("ts"),
                    thread_ts=event.get("thread_ts"),
                    say=say,
                    client=client,
                )

        @app.event("app_home_opened")
        async def handle_app_home_opened(event, client):
            """Render the App Home tab when a user opens it."""
            await self._handle_app_home_opened(slack_bot=slack_bot, event=event, client=client)

        @app.event("assistant_thread_started")
        async def handle_assistant_thread_started(event, client):
            """Inject suggested prompts when the AI assistant panel is opened."""
            await self._handle_assistant_thread_started(slack_bot=slack_bot, event=event, client=client)

        @app.event("assistant_thread_context_changed")
        async def handle_assistant_thread_context_changed(event, client):
            """Acknowledge context changes from the assistant panel (no action needed)."""

        @app.action("hitl_approve")
        async def handle_hitl_approve(ack, body, client):
            await ack()
            await self._handle_hitl_button(body, decision="approved")

        @app.action("hitl_reject")
        async def handle_hitl_reject(ack, body, client):
            await ack()
            await self._handle_hitl_button(body, decision="rejected")

    async def _handle_hitl_button(self, body: dict, decision: str) -> None:
        """Handle an Approve/Reject button click on a HITL approval message."""
        from ...core.database import get_async_session_factory
        from ...services.human_approval_service import HumanApprovalService

        try:
            approval_id = body["actions"][0]["value"]
            slack_user_id = body["user"]["id"]
            response_url = body.get("response_url")
        except (KeyError, IndexError):
            logger.warning("Malformed HITL button interaction payload")
            return

        async with get_async_session_factory()() as db:
            service = HumanApprovalService(db)
            result = await service.respond_to_approval(
                approval_id, decision, feedback_text=None, db=db, responded_by=slack_user_id
            )

        if result.get("already_handled") and response_url:
            responded_by = result.get("responded_by")
            note = (
                f"This request was already handled by <@{responded_by}>."
                if responded_by
                else "This request was already handled."
            )
            await HumanApprovalService.post_slack_ephemeral(response_url, note)

    async def _handle_message(
        self,
        slack_bot: SlackBot,
        channel_id: str,
        user_id: str,
        text: str,
        message_ts: str | None,
        thread_ts: str | None,
        say,
        client: AsyncWebClient,
    ) -> None:
        """Delegate message handling to the shared SlackMessageHandler."""
        handler = SlackMessageHandler(self.db_session, self.agent_manager)
        await handler.handle_message(
            slack_bot=slack_bot,
            channel_id=channel_id,
            user_id=user_id,
            text=text,
            message_ts=message_ts,
            thread_ts=thread_ts,
            client=client,
            say=say,
        )

    async def _handle_app_home_opened(self, slack_bot: SlackBot, event: dict, client: AsyncWebClient) -> None:
        """Publish the App Home tab view when a user opens it."""
        user_id = event.get("user")
        if not user_id:
            return
        try:
            from ...models.agent import Agent

            agent = await self.db_session.get(Agent, slack_bot.agent_id)
            agent_name = agent.agent_name if agent else slack_bot.bot_name
            agent_desc = (agent.description or "").strip() if agent else ""

            blocks: list[dict] = [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": f"Welcome to {agent_name}"},
                },
            ]
            if agent_desc:
                blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": agent_desc}})
            blocks += [
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            "*How to use:*\n"
                            "• DM me directly to start a private conversation\n"
                            "• @mention me in any channel to get help in context\n"
                            "• Open the AI assistant panel (bolt icon) for a focused chat"
                        ),
                    },
                },
            ]

            # Show suggestion prompts if the agent has them configured
            if agent and agent.suggestion_prompts:
                prompt_lines = "\n".join(
                    f"• *{p.get('title', '')}*" + (f" — _{p.get('description', '')}_" if p.get("description") else "")
                    for p in agent.suggestion_prompts[:5]
                    if p.get("title")
                )
                if prompt_lines:
                    blocks += [
                        {"type": "divider"},
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": f"*Try asking:*\n{prompt_lines}"},
                        },
                    ]

            await client.views_publish(
                user_id=user_id,
                view={"type": "home", "blocks": blocks},
            )
            logger.info(f"Published App Home for user {user_id}, bot {slack_bot.id}")
        except Exception as e:
            logger.warning(f"Failed to publish App Home for user {user_id}: {e}")

    async def _handle_assistant_thread_started(self, slack_bot: SlackBot, event: dict, client: AsyncWebClient) -> None:
        """Set suggested prompts in the Slack AI assistant panel."""
        thread = event.get("assistant_thread", {})
        channel_id = thread.get("channel_id")
        thread_ts = thread.get("thread_ts")
        if not channel_id or not thread_ts:
            return
        try:
            from ...models.agent import Agent

            agent = await self.db_session.get(Agent, slack_bot.agent_id)

            prompts = _DEFAULT_SUGGESTED_PROMPTS
            if agent and agent.suggestion_prompts:
                built = [
                    {
                        "title": p.get("title", ""),
                        "message": p.get("prompt") or p.get("description") or p.get("title", ""),
                    }
                    for p in agent.suggestion_prompts[:4]
                    if p.get("title")
                ]
                if built:
                    prompts = built

            await client.assistant_threads_setSuggestedPrompts(
                channel_id=channel_id,
                thread_ts=thread_ts,
                prompts=prompts,
            )
            logger.info(f"Set {len(prompts)} suggested prompts for assistant thread {thread_ts}")
        except Exception as e:
            logger.warning(f"Failed to set assistant suggested prompts: {e}")

    async def get_bot_status(self, slack_bot_id: UUID) -> dict[str, Any]:
        """Get status of a Slack bot."""
        bot_id_str = str(slack_bot_id)
        is_running = bot_id_str in self.active_handlers

        slack_bot = await self.db_session.get(SlackBot, slack_bot_id)

        return {
            "bot_id": str(slack_bot_id),
            "is_running": is_running,
            "connection_status": slack_bot.connection_status if slack_bot else "unknown",
            "last_connected_at": slack_bot.last_connected_at.isoformat()
            if slack_bot and slack_bot.last_connected_at
            else None,
        }
