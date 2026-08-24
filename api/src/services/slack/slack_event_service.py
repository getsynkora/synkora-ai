"""Slack Event Mode service for handling HTTP webhook events."""

import logging
from typing import Any

from slack_sdk.web.async_client import AsyncWebClient
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.slack_bot import SlackBot
from ...services.agents.agent_manager import AgentManager
from ...services.agents.security import decrypt_value
from ...services.webhooks.signature_verifier import SignatureVerifier
from .slack_message_handler import SlackMessageHandler

logger = logging.getLogger(__name__)


class SlackEventService:
    """Service for handling Slack Event Mode (HTTP webhook) events.

    This service processes incoming webhook requests from Slack's Event API,
    verifies signatures, and delegates message handling to the shared handler.
    """

    def __init__(self, db_session: AsyncSession, agent_manager: AgentManager | None = None):
        """Initialize the event service.

        Args:
            db_session: SQLAlchemy async database session
            agent_manager: Optional shared AgentManager instance
        """
        self.db_session = db_session
        self.agent_manager = agent_manager or AgentManager()
        self.message_handler = SlackMessageHandler(db_session, self.agent_manager)

    def verify_request(
        self,
        slack_bot: SlackBot,
        payload: bytes,
        timestamp: str,
        signature: str,
    ) -> bool:
        """Verify the webhook request signature.

        Args:
            slack_bot: SlackBot instance with signing_secret
            payload: Raw request body bytes
            timestamp: X-Slack-Request-Timestamp header
            signature: X-Slack-Signature header

        Returns:
            True if signature is valid
        """
        if not slack_bot.signing_secret:
            logger.error(f"Slack bot {slack_bot.id} has no signing secret configured")
            return False

        try:
            decrypted_secret = decrypt_value(slack_bot.signing_secret)
            return SignatureVerifier.verify_slack(
                timestamp=timestamp,
                signature_header=signature,
                payload=payload,
                secret=decrypted_secret,
            )
        except Exception as e:
            logger.error(f"Error verifying Slack signature: {e}")
            return False

    async def handle_url_verification(self, payload: dict[str, Any]) -> dict[str, str]:
        """Handle Slack URL verification challenge.

        Args:
            payload: Parsed JSON payload with 'challenge' field

        Returns:
            Dict with challenge response
        """
        challenge = payload.get("challenge", "")
        logger.info("Slack URL verification challenge received")
        return {"challenge": challenge}

    async def process_event(self, slack_bot: SlackBot, payload: dict[str, Any]) -> dict[str, str]:
        """Process a Slack event.

        Args:
            slack_bot: SlackBot instance
            payload: Parsed JSON event payload

        Returns:
            Dict with status response
        """
        event = payload.get("event", {})
        event_type = event.get("type", "")

        logger.info(f"Processing Slack event: {event_type} for bot {slack_bot.id}")

        # Handle different event types
        if event_type == "app_mention":
            await self._handle_app_mention(slack_bot, event, payload)
        elif event_type == "message":
            await self._handle_message_event(slack_bot, event, payload)
        elif event_type == "app_home_opened":
            await self._handle_app_home_opened(slack_bot, event)
        elif event_type == "assistant_thread_started":
            await self._handle_assistant_thread_started(slack_bot, event)
        elif event_type == "assistant_thread_context_changed":
            pass  # Acknowledge only
        else:
            logger.info(f"Unhandled event type: {event_type}")

        return {"status": "ok"}

    async def _handle_app_mention(self, slack_bot: SlackBot, event: dict[str, Any], payload: dict[str, Any]) -> None:
        """Handle @mention of the bot in a channel.

        Args:
            slack_bot: SlackBot instance
            event: Event data
            payload: Full event payload
        """
        channel_id = event.get("channel", "")
        user_id = event.get("user", "")
        text = event.get("text", "")
        message_ts = event.get("ts")
        thread_ts = event.get("thread_ts")

        if not channel_id or not user_id:
            logger.warning("Missing channel_id or user_id in app_mention event")
            return

        # Create Slack client
        client = await self._get_slack_client(slack_bot)

        # Delegate to shared message handler
        await self.message_handler.handle_message(
            slack_bot=slack_bot,
            channel_id=channel_id,
            user_id=user_id,
            text=text,
            message_ts=message_ts,
            thread_ts=thread_ts,
            client=client,
            say=None,  # Event mode uses client.chat_postMessage
            is_bot_sender=bool(event.get("bot_id")),
        )

    async def _handle_message_event(self, slack_bot: SlackBot, event: dict[str, Any], payload: dict[str, Any]) -> None:
        """Handle direct messages and channel messages.

        Args:
            slack_bot: SlackBot instance
            event: Event data
            payload: Full event payload
        """
        # Ignore bot messages and message subtypes
        subtype = event.get("subtype")
        if subtype == "bot_message" or event.get("bot_id"):
            return

        if subtype in ("message_changed", "message_deleted", "channel_join", "channel_leave"):
            return

        channel_id = event.get("channel", "")
        channel_type = event.get("channel_type")
        user_id = event.get("user", "")
        text = event.get("text", "")
        message_ts = event.get("ts")
        thread_ts = event.get("thread_ts")

        # Check if this is a DM
        is_dm = channel_type == "im" or channel_id.startswith("D")

        if not is_dm:
            # For channel messages, only respond to @mentions (handled by app_mention event)
            return

        if not channel_id or not user_id:
            logger.warning("Missing channel_id or user_id in message event")
            return

        logger.info(f"Received DM in channel {channel_id} from user {user_id}")

        # Create Slack client
        client = await self._get_slack_client(slack_bot)

        # Delegate to shared message handler
        await self.message_handler.handle_message(
            slack_bot=slack_bot,
            channel_id=channel_id,
            user_id=user_id,
            text=text,
            message_ts=message_ts,
            thread_ts=thread_ts,
            client=client,
            say=None,  # Event mode uses client.chat_postMessage
        )

    async def _handle_app_home_opened(self, slack_bot: SlackBot, event: dict[str, Any]) -> None:
        """Publish the App Home tab view when a user opens it."""
        user_id = event.get("user")
        if not user_id:
            return
        client = await self._get_slack_client(slack_bot)
        try:
            from ...models.agent import Agent

            agent = await self.db_session.get(Agent, slack_bot.agent_id)
            agent_name = agent.agent_name if agent else slack_bot.bot_name
            agent_desc = (agent.description or "").strip() if agent else ""

            blocks: list[dict] = [
                {"type": "header", "text": {"type": "plain_text", "text": f"Welcome to {agent_name}"}},
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
            if agent and agent.suggestion_prompts:
                prompt_lines = "\n".join(
                    f"• *{p.get('title', '')}*" + (f" — _{p.get('description', '')}_" if p.get("description") else "")
                    for p in agent.suggestion_prompts[:5]
                    if p.get("title")
                )
                if prompt_lines:
                    blocks += [
                        {"type": "divider"},
                        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Try asking:*\n{prompt_lines}"}},
                    ]

            await client.views_publish(user_id=user_id, view={"type": "home", "blocks": blocks})
            logger.info(f"Published App Home for user {user_id}, bot {slack_bot.id}")
        except Exception as e:
            logger.warning(f"Failed to publish App Home for user {user_id}: {e}")

    async def _handle_assistant_thread_started(self, slack_bot: SlackBot, event: dict[str, Any]) -> None:
        """Set suggested prompts in the Slack AI assistant panel."""
        thread = event.get("assistant_thread", {})
        channel_id = thread.get("channel_id")
        thread_ts = thread.get("thread_ts")
        if not channel_id or not thread_ts:
            return
        client = await self._get_slack_client(slack_bot)
        try:
            from ...models.agent import Agent

            agent = await self.db_session.get(Agent, slack_bot.agent_id)
            default_prompts = [
                {"title": "What can you do?", "message": "What are your capabilities?"},
                {"title": "Summarize recent messages", "message": "Summarize the last 20 messages in this channel"},
                {
                    "title": "Help me draft a message",
                    "message": "Help me write a professional message to my team about...",
                },
            ]
            prompts = default_prompts
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

    async def process_interaction(self, slack_bot: SlackBot, payload: dict[str, Any]) -> dict[str, str]:
        """Process a Slack interactive component payload (e.g. button click).

        Args:
            slack_bot: SlackBot instance
            payload: Parsed interaction payload (from the form-encoded `payload` field)

        Returns:
            Dict with status response
        """
        from ...services.human_approval_service import HumanApprovalService

        interaction_type = payload.get("type", "")
        if interaction_type != "block_actions":
            logger.info(f"Unhandled Slack interaction type: {interaction_type}")
            return {"status": "ok"}

        actions = payload.get("actions") or []
        if not actions:
            logger.warning("block_actions payload had no actions")
            return {"status": "ok"}

        action_id = actions[0].get("action_id", "")
        approval_id = actions[0].get("value", "")
        slack_user_id = (payload.get("user") or {}).get("id", "")
        response_url = payload.get("response_url")

        if action_id not in ("hitl_approve", "hitl_reject") or not approval_id:
            logger.info(f"Unhandled Slack block action_id: {action_id}")
            return {"status": "ok"}

        decision = "approved" if action_id == "hitl_approve" else "rejected"

        result = await HumanApprovalService(self.db_session).respond_to_approval(
            approval_id, decision, feedback_text=None, db=self.db_session, responded_by=slack_user_id
        )

        if result.get("already_handled") and response_url:
            responded_by = result.get("responded_by")
            note = (
                f"This request was already handled by <@{responded_by}>."
                if responded_by
                else "This request was already handled."
            )
            await HumanApprovalService.post_slack_ephemeral(response_url, note)

        return {"status": "ok"}

    async def _get_slack_client(self, slack_bot: SlackBot) -> AsyncWebClient:
        """Create Slack web client for the bot.

        Args:
            slack_bot: SlackBot instance

        Returns:
            Configured AsyncWebClient
        """
        bot_token = decrypt_value(slack_bot.slack_bot_token)
        return AsyncWebClient(token=bot_token)
