"""
Chat Service.

Handles chat operations including message saving, conversation management,
and post-chat actions like credit deduction and stat updates.
"""

import asyncio
import logging
import uuid
from typing import Any

# Strong references prevent GC before background cache tasks complete.
# The event loop only keeps weak refs; without this set tasks can be
# silently collected mid-execution under GC pressure.
_bg_cache_tasks: set[asyncio.Task] = set()

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.helpers.chat_helpers import build_message_metadata
from src.models.agent import Agent
from src.models.conversation import Conversation
from src.models.message import Message, MessageRole, MessageStatus
from src.services.billing.credit_utils import get_chat_action_type
from src.services.cache.conversation_cache_service import get_conversation_cache
from src.tasks.billing_tasks import deduct_credits_async

logger = logging.getLogger(__name__)


class ChatService:
    """Service for chat operations."""

    @staticmethod
    async def save_user_message(
        conversation_id: uuid.UUID,
        message: str,
        db: AsyncSession,
        attachments: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Message | None:
        """
        Save user message to conversation.

        Args:
            conversation_id: Conversation UUID
            message: User message content
            db: Database session
            metadata: Optional channel-specific metadata (e.g. Slack user/channel/thread info)

        Returns:
            Saved Message object or None if failed
        """
        try:
            # Use conversation.message_count instead of count() query for O(1) performance
            result = await db.execute(select(Conversation).filter(Conversation.id == conversation_id))
            conversation = result.scalar_one_or_none()
            if not conversation:
                logger.error(f"Conversation {conversation_id} not found")
                return None

            user_message = Message(
                conversation_id=conversation_id,
                role=MessageRole.USER,
                content=message,
                message_metadata=metadata or {},
                attachments=attachments,
                status=MessageStatus.COMPLETED,
            )

            db.add(user_message)
            conversation.increment_message_count()
            await db.commit()
            await db.refresh(user_message)

            # Append to conversation cache. Include page_context so history replay
            # (ConversationService.get_conversation_history_cached) sees it on a
            # cache HIT, not just on the cache-miss DB-load path.
            page_context = (metadata or {}).get("page_context")
            ChatService._append_message_to_cache(
                conversation_id=str(conversation_id), role="user", content=message, page_context=page_context
            )

            logger.info(f"Saved user message to conversation {conversation_id}")
            return user_message

        except Exception as e:
            logger.error(f"Failed to save user message: {e}")
            await db.rollback()
            return None

    @staticmethod
    async def save_assistant_message(
        conversation_id: uuid.UUID,
        content: str,
        sources: list[dict[str, Any]] | None = None,
        charts: list[dict[str, Any]] | None = None,
        diagrams: list[dict[str, Any]] | None = None,
        infographics: list[dict[str, Any]] | None = None,
        generated_images: list[dict[str, Any]] | None = None,
        forms: list[dict[str, Any]] | None = None,
        fleet_cards: list[dict[str, Any]] | None = None,
        workflow_type: str | None = None,
        execution_log: list[dict[str, Any]] | None = None,
        workflow_state: dict[str, Any] | None = None,
        timing: dict[str, float] | None = None,
        usage: dict[str, int] | None = None,
        reasoning_content: str | None = None,
        db: AsyncSession | None = None,
    ) -> Message | None:
        """
        Save assistant message to conversation.

        Args:
            conversation_id: Conversation UUID
            content: Assistant response content
            sources: Retrieved RAG sources
            charts: Chart data
            workflow_type: Workflow type if workflow agent
            execution_log: Workflow execution log
            workflow_state: Workflow state
            timing: Timing metrics (duration, time_to_first_token)
            usage: Token usage (input_tokens, output_tokens, total_tokens)
            db: Database session

        Returns:
            Saved Message object or None if failed
        """
        try:
            # Use conversation.message_count instead of count() query for O(1) performance
            result = await db.execute(select(Conversation).filter(Conversation.id == conversation_id))
            conversation = result.scalar_one_or_none()
            if not conversation:
                logger.error(f"Conversation {conversation_id} not found")
                return None

            metadata = build_message_metadata(
                sources=sources,
                charts=charts,
                diagrams=diagrams,
                infographics=infographics,
                generated_images=generated_images,
                forms=forms,
                fleet_cards=fleet_cards,
                workflow_type=workflow_type,
                execution_log=execution_log,
                workflow_state=workflow_state,
                timing=timing,
                usage=usage,
            )
            if reasoning_content:
                metadata["reasoning_content"] = reasoning_content

            assistant_message = Message(
                conversation_id=conversation_id,
                role=MessageRole.ASSISTANT,
                content=content,
                message_metadata=metadata,
                status=MessageStatus.COMPLETED,
            )

            db.add(assistant_message)
            conversation.increment_message_count()
            await db.commit()
            await db.refresh(assistant_message)
            # Refresh conversation so message_count is re-loaded as a Python int,
            # not an expired/lazy attribute (avoids greenlet_spawn in async context)
            await db.refresh(conversation)

            # Append to conversation cache
            ChatService._append_message_to_cache(
                conversation_id=str(conversation_id),
                role="assistant",
                content=content,
                reasoning_content=reasoning_content,
            )

            # Update conversation metadata cache
            if usage:
                ChatService._update_conversation_metadata_cache(
                    conversation_id=str(conversation_id),
                    total_messages=conversation.message_count,
                    total_tokens=usage.get("total_tokens", 0),
                )

            logger.info(f"Saved assistant message to conversation {conversation_id}")
            return assistant_message

        except Exception as e:
            logger.error(f"Failed to save assistant message: {e}")
            await db.rollback()
            return None

    @staticmethod
    def _append_message_to_cache(
        conversation_id: str,
        role: str,
        content: str,
        reasoning_content: str | None = None,
        page_context: dict[str, Any] | None = None,
    ) -> None:
        """
        Append a message to the conversation cache.

        Args:
            conversation_id: Conversation ID string
            role: Message role (user/assistant)
            content: Message content
            reasoning_content: DeepSeek reasoning_content to echo back on subsequent turns
            page_context: Host-supplied page context (widget page-context-awareness feature),
                mirrored from message_metadata so cached history stays consistent with the
                DB-load extraction in ConversationService.get_conversation_history_cached
        """
        try:
            cache_service = get_conversation_cache()
            message: dict = {"role": role, "content": content}
            if reasoning_content:
                message["reasoning_content"] = reasoning_content
            if page_context:
                message["page_context"] = page_context
            # Run cache update in background; store a strong ref so GC
            # cannot collect the task before it completes.
            task = asyncio.create_task(cache_service.append_message(conversation_id=conversation_id, message=message))
            _bg_cache_tasks.add(task)
            task.add_done_callback(_bg_cache_tasks.discard)
        except Exception as e:
            # Don't fail message save if cache update fails
            logger.warning(f"Failed to append message to cache: {e}")

    @staticmethod
    def _update_conversation_metadata_cache(conversation_id: str, total_messages: int, total_tokens: int) -> None:
        """
        Update conversation metadata in cache.

        Args:
            conversation_id: Conversation ID string
            total_messages: Total message count
            total_tokens: Total token count
        """
        try:
            import time

            cache_service = get_conversation_cache()
            # Run cache update in background; store a strong ref so GC
            # cannot collect the task before it completes.
            task = asyncio.create_task(
                cache_service.set_conversation_metadata(
                    conversation_id=conversation_id,
                    metadata={
                        "total_messages": total_messages,
                        "total_tokens": total_tokens,
                        "last_updated": time.time(),
                    },
                )
            )
            _bg_cache_tasks.add(task)
            task.add_done_callback(_bg_cache_tasks.discard)
        except Exception as e:
            logger.warning(f"Failed to update conversation metadata cache: {e}")

    @staticmethod
    async def update_agent_stats(agent: Agent, success: bool, db: AsyncSession) -> None:
        """
        Update agent execution statistics.

        Args:
            agent: Agent instance (may be detached from session)
            success: Whether execution was successful
            db: Database session
        """
        try:
            values: dict = {"execution_count": Agent.execution_count + 1}
            if success:
                values["success_count"] = Agent.success_count + 1

            await db.execute(update(Agent).where(Agent.id == agent.id).values(**values))
            await db.commit()

            logger.info(f"Updated agent stats for agent_id={agent.id}")

        except Exception as e:
            logger.error(f"Failed to update agent stats: {e}")
            await db.rollback()

    @staticmethod
    def queue_credit_deduction(
        tenant_id: uuid.UUID,
        agent_id: uuid.UUID,
        conversation_id: uuid.UUID,
        message_id: uuid.UUID,
        agent_name: str,
        model: str,
        content: str,
    ) -> None:
        """
        Queue async credit deduction task.

        Args:
            tenant_id: Tenant ID
            agent_id: Agent ID
            conversation_id: Conversation ID
            message_id: Message ID
            agent_name: Agent name
            model: LLM model used
            content: Message content
        """
        try:
            action_type = get_chat_action_type(model)

            deduct_credits_async.delay(
                tenant_id=str(tenant_id),
                user_id=None,
                agent_id=str(agent_id),
                action_type=action_type.name,
                metadata={
                    "conversation_id": str(conversation_id),
                    "message_id": str(message_id),
                    "agent_name": agent_name,
                    "model": model,
                    "message_length": len(content),
                },
            )

            logger.info(f"Queued credit deduction for conversation {conversation_id}")

        except Exception as e:
            logger.error(f"Failed to queue credit deduction: {e}")

    @staticmethod
    async def mark_message_failed(message: Message, error: str, db: AsyncSession) -> None:
        """
        Mark message as failed with error.

        Args:
            message: Message object
            error: Error message
            db: Database session
        """
        try:
            await db.execute(
                update(Message).where(Message.id == message.id).values(status=MessageStatus.FAILED, error=error)
            )
            await db.commit()

            logger.info(f"Marked message {message.id} as failed")

        except Exception as e:
            logger.error(f"Failed to update message status: {e}")
            await db.rollback()
