"""
Conversation Service

Service for managing chat conversations and sessions.
"""

import logging
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.conversation import Conversation, ConversationStatus
from src.models.message import Message
from src.services.cache.conversation_cache_service import get_conversation_cache

logger = logging.getLogger(__name__)


class ConversationService:
    """Service for managing conversations."""

    @staticmethod
    async def create_conversation(
        db: AsyncSession,
        app_id: UUID,
        agent_id: UUID | None = None,
        account_id: UUID | None = None,
        session_id: str | None = None,
        name: str = "New Conversation",
        source: str = "web",
    ) -> Conversation:
        """
        Create a new conversation.

        Args:
            db: Async database session
            app_id: App ID
            agent_id: Agent ID (optional)
            account_id: Account ID (optional)
            session_id: Session ID for tracking (optional)
            name: Conversation name
            source: Channel that created the conversation (web/flutter/widget/whatsapp/slack/chrome)

        Returns:
            Created conversation
        """
        conversation = Conversation(
            app_id=None,  # app_id is now nullable
            agent_id=agent_id,
            account_id=account_id,
            session_id=session_id,
            name=name,
            status=ConversationStatus.ACTIVE,
            source=source,
        )
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
        logger.info(f"Created conversation {conversation.id} for agent {agent_id}")
        return conversation

    @staticmethod
    async def get_conversation(
        db: AsyncSession,
        conversation_id: UUID,
        include_messages: bool = False,
    ) -> Conversation | None:
        """
        Get a conversation by ID.

        Args:
            db: Async database session
            conversation_id: Conversation ID
            include_messages: Whether to include messages

        Returns:
            Conversation or None
        """
        query = select(Conversation).where(Conversation.id == conversation_id)

        if include_messages:
            query = query.options(selectinload(Conversation.messages))

        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_agent_conversations(
        db: AsyncSession,
        agent_id: UUID,
        account_id: UUID | None = None,
        limit: int = 50,
    ) -> list[Conversation]:
        """
        Get conversations for an agent.

        Args:
            db: Async database session
            agent_id: Agent ID
            account_id: Account ID to filter by (optional)
            limit: Maximum number of conversations to return

        Returns:
            List of conversations
        """
        conditions = [
            Conversation.agent_id == agent_id,
            Conversation.status == ConversationStatus.ACTIVE,
        ]

        if account_id:
            conditions.append(Conversation.account_id == account_id)

        query = select(Conversation).where(and_(*conditions)).order_by(Conversation.updated_at.desc()).limit(limit)

        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_conversation_by_session(
        db: AsyncSession,
        session_id: str,
        agent_id: UUID | None = None,
    ) -> Conversation | None:
        """
        Get a conversation by session ID.

        Args:
            db: Async database session
            session_id: Session ID
            agent_id: Agent ID to filter by (optional)

        Returns:
            Conversation or None
        """
        conditions = [Conversation.session_id == session_id]

        if agent_id:
            conditions.append(Conversation.agent_id == agent_id)

        query = select(Conversation).where(and_(*conditions))
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def update_conversation(
        db: AsyncSession,
        conversation_id: UUID,
        name: str | None = None,
        summary: str | None = None,
        status: ConversationStatus | None = None,
    ) -> Conversation | None:
        """
        Update a conversation.

        Args:
            db: Async database session
            conversation_id: Conversation ID
            name: New name (optional)
            summary: New summary (optional)
            status: New status (optional)

        Returns:
            Updated conversation or None
        """
        conversation = await ConversationService.get_conversation(db, conversation_id)
        if not conversation:
            return None

        if name is not None:
            conversation.name = name
        if summary is not None:
            conversation.summary = summary
        if status is not None:
            conversation.status = status

        await db.commit()
        await db.refresh(conversation)
        logger.info(f"Updated conversation {conversation_id}")
        return conversation

    @staticmethod
    async def delete_conversation(
        db: AsyncSession,
        conversation_id: UUID,
        soft_delete: bool = True,
    ) -> bool:
        """
        Delete a conversation.

        Args:
            db: Async database session
            conversation_id: Conversation ID
            soft_delete: Whether to soft delete (mark as deleted) or hard delete

        Returns:
            True if deleted, False if not found
        """
        conversation = await ConversationService.get_conversation(db, conversation_id)
        if not conversation:
            return False

        if soft_delete:
            conversation.status = ConversationStatus.DELETED
            await db.commit()
        else:
            await db.delete(conversation)
            await db.commit()

        logger.info(f"Deleted conversation {conversation_id} (soft={soft_delete})")
        return True

    @staticmethod
    async def get_conversation_messages(
        db: AsyncSession,
        conversation_id: UUID,
        limit: int | None = None,
    ) -> list[Message]:
        """
        Get messages for a conversation.

        Args:
            db: Async database session
            conversation_id: Conversation ID
            limit: Maximum number of messages to return (optional)

        Returns:
            List of messages
        """
        query = select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.asc())

        if limit:
            query = query.limit(limit)

        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_conversation_history_cached(
        db: AsyncSession,
        conversation_id: UUID,
        limit: int = 20,
    ) -> list[dict]:
        """
        Get conversation history with caching support.

        First tries to get from cache, falls back to database.

        Args:
            db: Database session
            conversation_id: Conversation ID
            limit: Maximum number of messages to return

        Returns:
            List of message dicts with 'role' and 'content' keys
        """
        cache_service = get_conversation_cache()
        conversation_id_str = str(conversation_id)

        # Try cache first
        cached_messages = await cache_service.get_conversation_history(conversation_id=conversation_id_str, limit=limit)

        if cached_messages is not None:
            logger.debug(f"Using cached history for conversation {conversation_id}")
            return cached_messages

        # Cache miss - load from database
        logger.debug(f"Cache miss - loading history from DB for conversation {conversation_id}")
        db_messages = await ConversationService.get_conversation_messages(
            db=db, conversation_id=conversation_id, limit=limit
        )

        # Convert to simple dict format — normalize role to lowercase so it matches
        # the "user" / "assistant" filter in _build_prompt (MessageRole enum uses uppercase)
        messages = []
        for msg in db_messages:
            role = (msg.role.value if hasattr(msg.role, "value") else str(msg.role)).lower()
            entry: dict = {"role": role, "content": msg.content}
            # DeepSeek reasoning models require reasoning_content to be echoed back
            # in subsequent turns. Include it when stored in message metadata.
            if role == "assistant" and msg.message_metadata:
                rc = msg.message_metadata.get("reasoning_content")
                if rc:
                    entry["reasoning_content"] = rc
            messages.append(entry)

        # Cache for future requests
        if messages:
            await cache_service.set_conversation_history(conversation_id=conversation_id_str, messages=messages)

        return messages

    @staticmethod
    async def invalidate_conversation_cache(conversation_id: UUID) -> None:
        """
        Invalidate all cache entries for a conversation.

        Args:
            conversation_id: Conversation ID
        """
        cache_service = get_conversation_cache()
        await cache_service.invalidate(str(conversation_id))
        logger.info(f"Invalidated cache for conversation {conversation_id}")
