"""Microsoft Teams Bot Framework webhook service."""

import json
import logging
from datetime import UTC, datetime
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.agent import Agent
from ...models.conversation import Conversation, ConversationStatus
from ...models.message import Message
from ...models.teams_bot import TeamsBot, TeamsConversation
from ...services.agents.security import decrypt_value

logger = logging.getLogger(__name__)


class TeamsWebhookService:
    """Service for handling Microsoft Teams webhooks and sending messages."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def handle_activity(self, bot_id: UUID, activity: dict):
        """
        Handle incoming Teams activity.

        Args:
            bot_id: Teams bot ID
            activity: Activity payload from Teams Bot Framework
        """
        try:
            bot = await self.db_session.get(TeamsBot, bot_id)
            if not bot or not bot.is_active:
                logger.warning(f"Teams bot {bot_id} not found or inactive")
                return

            activity_type = activity.get("type")

            if activity_type == "message":
                await self._handle_message(bot, activity)
            elif activity_type == "conversationUpdate":
                await self._handle_conversation_update(bot, activity)
            else:
                logger.debug(f"Ignoring Teams activity type: {activity_type}")

        except Exception as e:
            logger.error(f"Error handling Teams activity: {str(e)}")
            await self.db_session.rollback()

    async def _handle_message(self, bot: TeamsBot, activity: dict):
        """
        Handle Teams message activity.

        Args:
            bot: TeamsBot instance
            activity: Message activity data
        """
        try:
            text = activity.get("text", "").strip()
            if not text:
                return

            # Feedback: intercept 👍/👎 as per-message satisfaction signal
            _stripped = text.strip()
            if _stripped in ("👍", "👎", ":thumbsup:", ":thumbsdown:", "+1", "-1"):
                try:
                    from sqlalchemy import select

                    from ...models.message import Message
                    from ...services.eval.feedback_service import record_feedback

                    _msg_result = await self.db_session.execute(
                        select(Message).filter(Message.role == "assistant").order_by(Message.created_at.desc()).limit(1)
                    )
                    _last_msg = _msg_result.scalar_one_or_none()
                    if _last_msg:
                        _rating = 1 if _stripped in ("👍", ":thumbsup:", "+1") else -1
                        record_feedback(
                            message_id=str(_last_msg.id),
                            agent_id=bot.agent_id,
                            tenant_id=bot.tenant_id,
                            channel="teams",
                            rating=_rating,
                        )
                except Exception as _fb_err:
                    logger.debug("Teams feedback intercept failed: %s", _fb_err)
                return

            from_user = activity.get("from", {})
            user_id = from_user.get("id")
            user_name = from_user.get("name", user_id)

            conversation_ref = activity.get("conversation", {})
            conversation_id = conversation_ref.get("id")

            service_url = activity.get("serviceUrl")
            activity_id = activity.get("id")

            # Get or create conversation
            conversation = await self._get_or_create_conversation(bot, conversation_id, user_id)

            # Block AI while a human operator is handling this conversation
            if getattr(conversation, "handoff_status", None) == "active":
                await self._send_message(
                    bot,
                    service_url,
                    conversation_id,
                    "A human support agent is currently handling your request. They will respond shortly.",
                    activity_id,
                )
                return

            # Save user message
            user_message = Message(
                conversation_id=conversation.id,
                role="user",
                content=text,
                message_metadata={
                    "teams_activity_id": activity_id,
                    "teams_user_id": user_id,
                    "teams_user_name": user_name,
                },
            )
            self.db_session.add(user_message)
            conversation.increment_message_count()
            await self.db_session.commit()

            # Send typing indicator
            await self._send_typing(bot, service_url, conversation_id)

            # Get agent response
            from ...controllers.agents.chat import stream_agent_response
            from ...services.conversation_service import ConversationService

            agent = await self.db_session.get(Agent, bot.agent_id)
            if not agent:
                logger.error(f"Agent {bot.agent_id} not found for Teams bot {bot.id}")
                return

            # Load conversation history with caching support
            conversation_history = await ConversationService.get_conversation_history_cached(
                db=self.db_session,
                conversation_id=conversation.id,
                limit=30,  # Keep recent messages for context
            )
            logger.info(f"Loaded {len(conversation_history)} messages from Teams conversation history")

            # Collect streamed response
            response_chunks = []
            async for event_data in stream_agent_response(
                agent_name=agent.slug or agent.agent_name,
                message=text,
                conversation_history=conversation_history,  # Pass loaded history for memory
                conversation_id=str(conversation.id),
                attachments=None,
                db=self.db_session,
            ):
                if event_data.startswith("data: "):
                    try:
                        event_json = json.loads(event_data[6:])
                        if event_json.get("type") == "chunk":
                            response_chunks.append(event_json.get("content", ""))
                    except Exception:
                        pass

            agent_response = "".join(response_chunks)

            # Send Teams message
            await self._send_message(bot, service_url, conversation_id, agent_response, activity_id)

            # Save assistant message
            assistant_message = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=agent_response,
            )
            self.db_session.add(assistant_message)
            conversation.increment_message_count()
            bot.last_message_at = datetime.now(UTC)
            await self.db_session.commit()

            logger.info(f"Processed Teams message from {user_name} for bot {bot.id}")

        except Exception as e:
            logger.error(f"Error processing Teams message: {str(e)}")
            await self.db_session.rollback()

    async def _handle_conversation_update(self, bot: TeamsBot, activity: dict):
        """
        Handle Teams conversation update (e.g., bot added to channel).

        Args:
            bot: TeamsBot instance
            activity: Conversation update activity
        """
        members_added = activity.get("membersAdded", [])
        bot_was_added = any(member.get("id") == bot.bot_id for member in members_added)

        if bot_was_added:
            logger.info(f"Teams bot {bot.id} was added to a conversation")
            # Optionally send welcome message
            conversation_ref = activity.get("conversation", {})
            conversation_id = conversation_ref.get("id")
            service_url = activity.get("serviceUrl")

            if bot.welcome_message:
                await self._send_message(bot, service_url, conversation_id, bot.welcome_message)

    async def _get_or_create_conversation(
        self, bot: TeamsBot, teams_conversation_id: str, user_id: str
    ) -> Conversation:
        """
        Get or create conversation mapping.

        Args:
            bot: TeamsBot instance
            teams_conversation_id: Teams conversation ID
            user_id: Teams user ID

        Returns:
            Conversation instance
        """
        stmt = select(TeamsConversation).where(
            TeamsConversation.teams_bot_id == bot.id,
            TeamsConversation.teams_conversation_id == teams_conversation_id,
            TeamsConversation.teams_user_id == user_id,
        )
        result = await self.db_session.execute(stmt)
        teams_conv = result.scalar_one_or_none()

        if teams_conv:
            return await self.db_session.get(Conversation, teams_conv.conversation_id)

        # Create new conversation
        conversation = Conversation(
            agent_id=bot.agent_id, name=f"Teams conversation with {user_id}", status=ConversationStatus.ACTIVE
        )
        self.db_session.add(conversation)
        await self.db_session.commit()
        await self.db_session.refresh(conversation)

        teams_conv = TeamsConversation(
            teams_bot_id=bot.id,
            conversation_id=conversation.id,
            teams_conversation_id=teams_conversation_id,
            teams_user_id=user_id,
        )
        self.db_session.add(teams_conv)
        await self.db_session.commit()

        return conversation

    async def _send_message(
        self, bot: TeamsBot, service_url: str, conversation_id: str, text: str, reply_to_id: str | None = None
    ):
        """
        Send Teams message via Bot Framework API.

        Args:
            bot: TeamsBot instance
            service_url: Teams service URL
            conversation_id: Teams conversation ID
            text: Message text
            reply_to_id: Activity ID to reply to (optional)
        """
        try:
            access_token = await self._get_bot_token(bot)

            url = f"{service_url}/v3/conversations/{conversation_id}/activities"
            if reply_to_id:
                url = f"{service_url}/v3/conversations/{conversation_id}/activities/{reply_to_id}"

            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

            payload = {"type": "message", "text": text}

            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload, timeout=30.0)
                response.raise_for_status()

            logger.info(f"Sent Teams message to conversation {conversation_id}")

        except Exception as e:
            logger.error(f"Failed to send Teams message: {str(e)}")
            raise

    async def _send_typing(self, bot: TeamsBot, service_url: str, conversation_id: str):
        """
        Send typing indicator to Teams.

        Args:
            bot: TeamsBot instance
            service_url: Teams service URL
            conversation_id: Teams conversation ID
        """
        try:
            access_token = await self._get_bot_token(bot)

            url = f"{service_url}/v3/conversations/{conversation_id}/activities"
            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

            payload = {"type": "typing"}

            async with httpx.AsyncClient() as client:
                await client.post(url, headers=headers, json=payload, timeout=10.0)

        except Exception as e:
            logger.debug(f"Failed to send Teams typing indicator: {str(e)}")

    async def _get_bot_token(self, bot: TeamsBot) -> str:
        """
        Get Bot Framework access token.

        Args:
            bot: TeamsBot instance

        Returns:
            Access token string
        """
        app_id = bot.app_id
        app_password = decrypt_value(bot.app_password)

        url = "https://login.microsoftonline.com/botframework.com/oauth2/v2.0/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": app_id,
            "client_secret": app_password,
            "scope": "https://api.botframework.com/.default",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=data, timeout=10.0)
            response.raise_for_status()
            token_data = response.json()
            return token_data["access_token"]
