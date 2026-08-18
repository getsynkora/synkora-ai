"""
Unit tests for Conversation Service.

Tests conversation CRUD operations and caching.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.conversation import ConversationStatus
from src.services.conversation_service import ConversationService


class TestCreateConversation:
    """Test conversation creation."""

    async def test_create_conversation_basic(self):
        """Test basic conversation creation."""
        mock_db = AsyncMock(spec=AsyncSession)
        agent_id = uuid.uuid4()
        account_id = uuid.uuid4()

        # Mock the conversation that would be created
        mock_conversation = MagicMock()
        mock_conversation.id = uuid.uuid4()
        mock_conversation.agent_id = agent_id
        mock_conversation.account_id = account_id
        mock_conversation.name = "New Conversation"
        mock_conversation.status = ConversationStatus.ACTIVE

        # Configure db.refresh to update the conversation
        def set_id(conv):
            conv.id = mock_conversation.id

        mock_db.refresh.side_effect = set_id

        await ConversationService.create_conversation(
            db=mock_db,
            app_id=uuid.uuid4(),
            agent_id=agent_id,
            account_id=account_id,
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    async def test_create_conversation_with_session_id(self):
        """Test conversation creation with session ID."""
        mock_db = AsyncMock(spec=AsyncSession)

        await ConversationService.create_conversation(
            db=mock_db,
            app_id=uuid.uuid4(),
            agent_id=uuid.uuid4(),
            session_id="session_123",
            name="Chat Session",
        )

        # Verify add was called with a conversation
        call_args = mock_db.add.call_args[0][0]
        assert call_args.session_id == "session_123"
        assert call_args.name == "Chat Session"

    async def test_create_conversation_without_optional_params(self):
        """Test conversation creation without optional parameters."""
        mock_db = AsyncMock(spec=AsyncSession)

        await ConversationService.create_conversation(
            db=mock_db,
            app_id=uuid.uuid4(),
        )

        call_args = mock_db.add.call_args[0][0]
        assert call_args.agent_id is None
        assert call_args.account_id is None


class TestGetConversation:
    """Test getting a conversation."""

    async def test_get_conversation_found(self):
        """Test getting an existing conversation."""
        mock_db = AsyncMock(spec=AsyncSession)
        conversation_id = uuid.uuid4()

        mock_conversation = MagicMock()
        mock_conversation.id = conversation_id

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_conversation
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await ConversationService.get_conversation(mock_db, conversation_id)

        assert result == mock_conversation
        mock_db.execute.assert_called_once()

    async def test_get_conversation_not_found(self):
        """Test getting a non-existent conversation."""
        mock_db = AsyncMock(spec=AsyncSession)
        conversation_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await ConversationService.get_conversation(mock_db, conversation_id)

        assert result is None

    async def test_get_conversation_with_messages(self):
        """Test getting a conversation with messages included."""
        mock_db = AsyncMock(spec=AsyncSession)
        conversation_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        await ConversationService.get_conversation(mock_db, conversation_id, include_messages=True)

        # Verify execute was called (with options for loading messages)
        mock_db.execute.assert_called_once()


class TestGetAgentConversations:
    """Test getting conversations for an agent."""

    async def test_get_agent_conversations(self):
        """Test getting agent conversations."""
        mock_db = AsyncMock(spec=AsyncSession)
        agent_id = uuid.uuid4()

        mock_conversations = [MagicMock(), MagicMock()]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_conversations
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await ConversationService.get_agent_conversations(mock_db, agent_id)

        assert len(result) == 2
        mock_db.execute.assert_called_once()

    async def test_get_agent_conversations_with_account_filter(self):
        """Test getting agent conversations filtered by account."""
        mock_db = AsyncMock(spec=AsyncSession)
        agent_id = uuid.uuid4()
        account_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        await ConversationService.get_agent_conversations(mock_db, agent_id, account_id=account_id)

        mock_db.execute.assert_called_once()

    async def test_get_agent_conversations_with_limit(self):
        """Test getting agent conversations with custom limit."""
        mock_db = AsyncMock(spec=AsyncSession)
        agent_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        await ConversationService.get_agent_conversations(mock_db, agent_id, limit=10)

        mock_db.execute.assert_called_once()


class TestGetConversationBySession:
    """Test getting a conversation by session ID."""

    async def test_get_by_session_found(self):
        """Test getting conversation by session ID when found."""
        mock_db = AsyncMock(spec=AsyncSession)
        session_id = "session_123"

        mock_conversation = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_conversation
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await ConversationService.get_conversation_by_session(mock_db, session_id)

        assert result == mock_conversation

    async def test_get_by_session_not_found(self):
        """Test getting conversation by session ID when not found."""
        mock_db = AsyncMock(spec=AsyncSession)
        session_id = "nonexistent_session"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await ConversationService.get_conversation_by_session(mock_db, session_id)

        assert result is None

    async def test_get_by_session_with_agent_filter(self):
        """Test getting conversation by session with agent filter."""
        mock_db = AsyncMock(spec=AsyncSession)
        session_id = "session_123"
        agent_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        await ConversationService.get_conversation_by_session(mock_db, session_id, agent_id=agent_id)

        mock_db.execute.assert_called_once()


class TestUpdateConversation:
    """Test conversation updates."""

    async def test_update_conversation_name(self):
        """Test updating conversation name."""
        mock_db = AsyncMock(spec=AsyncSession)
        conversation_id = uuid.uuid4()

        mock_conversation = MagicMock()
        mock_conversation.id = conversation_id

        with patch.object(
            ConversationService, "get_conversation", new_callable=AsyncMock, return_value=mock_conversation
        ):
            await ConversationService.update_conversation(mock_db, conversation_id, name="Updated Name")

            assert mock_conversation.name == "Updated Name"
            mock_db.commit.assert_called_once()

    async def test_update_conversation_summary(self):
        """Test updating conversation summary."""
        mock_db = AsyncMock(spec=AsyncSession)
        conversation_id = uuid.uuid4()

        mock_conversation = MagicMock()

        with patch.object(
            ConversationService, "get_conversation", new_callable=AsyncMock, return_value=mock_conversation
        ):
            await ConversationService.update_conversation(mock_db, conversation_id, summary="New summary")

            assert mock_conversation.summary == "New summary"

    async def test_update_conversation_status(self):
        """Test updating conversation status."""
        mock_db = AsyncMock(spec=AsyncSession)
        conversation_id = uuid.uuid4()

        mock_conversation = MagicMock()

        with patch.object(
            ConversationService, "get_conversation", new_callable=AsyncMock, return_value=mock_conversation
        ):
            await ConversationService.update_conversation(mock_db, conversation_id, status=ConversationStatus.ARCHIVED)

            assert mock_conversation.status == ConversationStatus.ARCHIVED

    async def test_update_conversation_not_found(self):
        """Test updating non-existent conversation."""
        mock_db = AsyncMock(spec=AsyncSession)
        conversation_id = uuid.uuid4()

        with patch.object(ConversationService, "get_conversation", new_callable=AsyncMock, return_value=None):
            result = await ConversationService.update_conversation(mock_db, conversation_id, name="New Name")

            assert result is None
            mock_db.commit.assert_not_called()


class TestDeleteConversation:
    """Test conversation deletion."""

    async def test_soft_delete_conversation(self):
        """Test soft deleting a conversation."""
        mock_db = AsyncMock(spec=AsyncSession)
        conversation_id = uuid.uuid4()

        mock_conversation = MagicMock()

        with patch.object(
            ConversationService, "get_conversation", new_callable=AsyncMock, return_value=mock_conversation
        ):
            result = await ConversationService.delete_conversation(mock_db, conversation_id, soft_delete=True)

            assert result is True
            assert mock_conversation.status == ConversationStatus.DELETED
            mock_db.commit.assert_called_once()

    async def test_hard_delete_conversation(self):
        """Test hard deleting a conversation."""
        mock_db = AsyncMock(spec=AsyncSession)
        conversation_id = uuid.uuid4()

        mock_conversation = MagicMock()

        with patch.object(
            ConversationService, "get_conversation", new_callable=AsyncMock, return_value=mock_conversation
        ):
            result = await ConversationService.delete_conversation(mock_db, conversation_id, soft_delete=False)

            assert result is True
            mock_db.delete.assert_called_once_with(mock_conversation)
            mock_db.commit.assert_called_once()

    async def test_delete_conversation_not_found(self):
        """Test deleting non-existent conversation."""
        mock_db = AsyncMock(spec=AsyncSession)
        conversation_id = uuid.uuid4()

        with patch.object(ConversationService, "get_conversation", new_callable=AsyncMock, return_value=None):
            result = await ConversationService.delete_conversation(mock_db, conversation_id)

            assert result is False
            mock_db.commit.assert_not_called()


class TestGetConversationMessages:
    """Test getting conversation messages."""

    async def test_get_messages(self):
        """Test getting conversation messages."""
        mock_db = AsyncMock(spec=AsyncSession)
        conversation_id = uuid.uuid4()

        mock_messages = [MagicMock(), MagicMock(), MagicMock()]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_messages
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await ConversationService.get_conversation_messages(mock_db, conversation_id)

        assert len(result) == 3

    async def test_get_messages_with_limit(self):
        """Test getting messages with limit."""
        mock_db = AsyncMock(spec=AsyncSession)
        conversation_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        await ConversationService.get_conversation_messages(mock_db, conversation_id, limit=10)

        mock_db.execute.assert_called_once()

    async def test_get_messages_empty(self):
        """Test getting messages when none exist."""
        mock_db = AsyncMock(spec=AsyncSession)
        conversation_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await ConversationService.get_conversation_messages(mock_db, conversation_id)

        assert result == []


class TestGetConversationHistoryCached:
    """Test cached conversation history retrieval."""

    async def test_get_history_from_cache(self):
        """Test getting history from cache."""
        mock_db = AsyncMock(spec=AsyncSession)
        conversation_id = uuid.uuid4()

        cached_messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        mock_cache = AsyncMock()
        mock_cache.get_conversation_history = AsyncMock(return_value=cached_messages)

        with patch(
            "src.services.conversation_service.get_conversation_cache",
            return_value=mock_cache,
        ):
            result = await ConversationService.get_conversation_history_cached(mock_db, conversation_id)

            assert result == cached_messages
            mock_cache.get_conversation_history.assert_called_once()

    async def test_get_history_cache_miss(self):
        """Test getting history when cache misses."""
        mock_db = AsyncMock(spec=AsyncSession)
        conversation_id = uuid.uuid4()

        mock_messages = [MagicMock(), MagicMock()]
        mock_messages[0].role.value = "user"
        mock_messages[0].content = "Hello"
        mock_messages[1].role.value = "assistant"
        mock_messages[1].content = "Hi!"

        mock_cache = AsyncMock()
        mock_cache.get_conversation_history = AsyncMock(return_value=None)
        mock_cache.set_conversation_history = AsyncMock()

        with (
            patch(
                "src.services.conversation_service.get_conversation_cache",
                return_value=mock_cache,
            ),
            patch.object(
                ConversationService,
                "get_conversation_messages",
                new_callable=AsyncMock,
                return_value=mock_messages,
            ),
        ):
            result = await ConversationService.get_conversation_history_cached(mock_db, conversation_id)

            assert len(result) == 2
            assert result[0]["role"] == "user"
            mock_cache.set_conversation_history.assert_called_once()

    async def test_get_history_cache_miss_includes_page_context_on_user_turn(self):
        """Test page_context in message_metadata is folded into the user-turn history entry."""
        mock_db = AsyncMock(spec=AsyncSession)
        conversation_id = uuid.uuid4()

        user_msg = MagicMock()
        user_msg.role.value = "user"
        user_msg.content = "what's their plan?"
        user_msg.message_metadata = {"page_context": {"entity_id": "usr_123"}}

        assistant_msg = MagicMock()
        assistant_msg.role.value = "assistant"
        assistant_msg.content = "They're on the Pro plan."
        assistant_msg.message_metadata = None

        mock_cache = AsyncMock()
        mock_cache.get_conversation_history = AsyncMock(return_value=None)
        mock_cache.set_conversation_history = AsyncMock()

        with (
            patch(
                "src.services.conversation_service.get_conversation_cache",
                return_value=mock_cache,
            ),
            patch.object(
                ConversationService,
                "get_conversation_messages",
                new_callable=AsyncMock,
                return_value=[user_msg, assistant_msg],
            ),
        ):
            result = await ConversationService.get_conversation_history_cached(mock_db, conversation_id)

        assert result[0]["page_context"] == {"entity_id": "usr_123"}
        assert "page_context" not in result[1]

    async def test_get_history_cache_miss_omits_page_context_when_absent(self):
        """Test user turns without page_context in metadata get no page_context key."""
        mock_db = AsyncMock(spec=AsyncSession)
        conversation_id = uuid.uuid4()

        user_msg = MagicMock()
        user_msg.role.value = "user"
        user_msg.content = "hello"
        user_msg.message_metadata = None

        mock_cache = AsyncMock()
        mock_cache.get_conversation_history = AsyncMock(return_value=None)
        mock_cache.set_conversation_history = AsyncMock()

        with (
            patch(
                "src.services.conversation_service.get_conversation_cache",
                return_value=mock_cache,
            ),
            patch.object(
                ConversationService,
                "get_conversation_messages",
                new_callable=AsyncMock,
                return_value=[user_msg],
            ),
        ):
            result = await ConversationService.get_conversation_history_cached(mock_db, conversation_id)

        assert "page_context" not in result[0]


class TestInvalidateConversationCache:
    """Test cache invalidation."""

    async def test_invalidate_cache(self):
        """Test invalidating conversation cache."""
        conversation_id = uuid.uuid4()

        mock_cache = AsyncMock()
        mock_cache.invalidate = AsyncMock()

        with patch(
            "src.services.conversation_service.get_conversation_cache",
            return_value=mock_cache,
        ):
            await ConversationService.invalidate_conversation_cache(conversation_id)

            mock_cache.invalidate.assert_called_once_with(str(conversation_id))
