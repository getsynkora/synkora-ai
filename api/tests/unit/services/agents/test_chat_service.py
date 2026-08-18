"""
Unit tests for ChatService.

Focused on the conversation-cache append behavior for user messages,
specifically the page_context (widget page-context-awareness feature)
propagation from message_metadata into the incrementally-cached message.
"""

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from src.services.agents import chat_service as chat_service_module
from src.services.agents.chat_service import ChatService


async def _drain_bg_cache_tasks() -> None:
    """Await any fire-and-forget cache-append tasks scheduled by ChatService."""
    pending = list(chat_service_module._bg_cache_tasks)
    if pending:
        await asyncio.gather(*pending)


class TestSaveUserMessageCacheAppend:
    """Test that save_user_message's incremental cache append preserves page_context."""

    async def test_cache_append_includes_page_context_from_metadata(self):
        mock_db = AsyncMock(spec=AsyncSession)
        conversation_id = uuid.uuid4()

        mock_conversation = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_conversation
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_cache = AsyncMock()
        mock_cache.append_message = AsyncMock(return_value=True)

        with patch(
            "src.services.agents.chat_service.get_conversation_cache",
            return_value=mock_cache,
        ):
            await ChatService.save_user_message(
                conversation_id=conversation_id,
                message="Second message, still page1",
                db=mock_db,
                metadata={"page_context": {"url": "http://test.local/page1", "title": "Test Page 1"}},
            )
            await _drain_bg_cache_tasks()

        mock_cache.append_message.assert_called_once()
        _, kwargs = mock_cache.append_message.call_args
        assert kwargs["message"]["page_context"] == {"url": "http://test.local/page1", "title": "Test Page 1"}

    async def test_cache_append_omits_page_context_when_absent(self):
        mock_db = AsyncMock(spec=AsyncSession)
        conversation_id = uuid.uuid4()

        mock_conversation = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_conversation
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_cache = AsyncMock()
        mock_cache.append_message = AsyncMock(return_value=True)

        with patch(
            "src.services.agents.chat_service.get_conversation_cache",
            return_value=mock_cache,
        ):
            await ChatService.save_user_message(
                conversation_id=conversation_id,
                message="Hello, what can you help with?",
                db=mock_db,
                metadata=None,
            )
            await _drain_bg_cache_tasks()

        mock_cache.append_message.assert_called_once()
        _, kwargs = mock_cache.append_message.call_args
        assert "page_context" not in kwargs["message"]
