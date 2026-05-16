"""
Conversation Cache Service.

Redis cache for conversation history with smart invalidation.
Provides fast retrieval of recent messages and conversation metadata.
"""

import json
import logging
from datetime import timedelta
from inspect import isawaitable
from typing import Any

logger = logging.getLogger(__name__)


class ConversationCacheService:
    """Redis cache for conversation history."""

    CACHE_TTL = 7200  # 2 hours (increased from 30 minutes for better memory retention)
    SUMMARY_TTL = 86400  # 24 hours for summaries (they're expensive to regenerate)
    MAX_CACHED_MESSAGES = 50  # Cache last 50 messages

    # Cache key prefixes
    KEY_PREFIX_HISTORY = "conv_history"
    KEY_PREFIX_SUMMARY = "conv_summary"
    KEY_PREFIX_META = "conv_meta"

    def __init__(self, redis_client=None):
        """
        Initialize the conversation cache service.

        Args:
            redis_client: Redis client instance (optional, will use global if not provided)
        """
        self.redis = redis_client

    def _get_redis(self):
        """Get Redis client, fallback to import if not provided."""
        if self.redis:
            return self.redis

        try:
            from src.config.redis import get_redis_async

            return get_redis_async()
        except Exception as e:
            logger.warning(f"Redis not available: {e}")
            return None

    async def _redis_call(self, redis, method_name: str, *args):
        """Call sync test clients and async production clients without blocking async code."""
        result = getattr(redis, method_name)(*args)
        if isawaitable(result):
            return await result
        return result

    def _build_key(self, prefix: str, conversation_id: str) -> str:
        """Build cache key with prefix."""
        return f"{prefix}:{conversation_id}"

    async def get_conversation_history(self, conversation_id: str, limit: int = 20) -> list[dict[str, Any]] | None:
        """
        Get cached conversation history.

        Args:
            conversation_id: Conversation ID
            limit: Maximum number of messages to return

        Returns:
            List of message dicts or None if not cached
        """
        redis = self._get_redis()
        if not redis:
            return None

        try:
            key = self._build_key(self.KEY_PREFIX_HISTORY, conversation_id)
            cached_data = await self._redis_call(redis, "get", key)

            if cached_data:
                messages = json.loads(cached_data)
                logger.info(f"✅ Cache HIT: Conversation history for '{conversation_id}' ({len(messages)} messages)")
                # Return last N messages
                return messages[-limit:] if len(messages) > limit else messages

            logger.debug(f"❌ Cache MISS: Conversation history for '{conversation_id}'")
            return None
        except Exception as e:
            logger.error(f"Error getting cached conversation history: {e}")
            return None

    async def set_conversation_history(
        self, conversation_id: str, messages: list[dict[str, Any]], ttl: int | None = None
    ) -> bool:
        """
        Cache conversation history.

        Args:
            conversation_id: Conversation ID
            messages: List of message dicts with 'role' and 'content' keys
            ttl: Time to live in seconds (default: 30 minutes)

        Returns:
            True if cached successfully
        """
        redis = self._get_redis()
        if not redis:
            return False

        try:
            key = self._build_key(self.KEY_PREFIX_HISTORY, conversation_id)
            ttl = ttl or self.CACHE_TTL

            # Only cache last MAX_CACHED_MESSAGES messages
            cached_messages = messages[-self.MAX_CACHED_MESSAGES :]

            # Serialize messages (convert any non-serializable fields)
            serializable_messages = self._serialize_messages(cached_messages)

            await self._redis_call(redis, "setex", key, timedelta(seconds=ttl), json.dumps(serializable_messages))

            logger.info(
                f"✅ Cached conversation history for '{conversation_id}' "
                f"({len(serializable_messages)} messages, TTL: {ttl}s)"
            )
            return True
        except Exception as e:
            logger.error(f"Error caching conversation history: {e}")
            return False

    async def append_message(self, conversation_id: str, message: dict[str, Any]) -> bool:
        """
        Append new message to cache (efficient incremental update).

        Args:
            conversation_id: Conversation ID
            message: Message dict with 'role' and 'content' keys

        Returns:
            True if appended successfully
        """
        redis = self._get_redis()
        if not redis:
            return False

        try:
            key = self._build_key(self.KEY_PREFIX_HISTORY, conversation_id)

            # Get existing messages
            cached_data = await self._redis_call(redis, "get", key)
            if cached_data:
                messages = json.loads(cached_data)
            else:
                messages = []

            # Append new message
            serialized_message = self._serialize_message(message)
            messages.append(serialized_message)

            # Trim to max cached messages
            if len(messages) > self.MAX_CACHED_MESSAGES:
                messages = messages[-self.MAX_CACHED_MESSAGES :]

            # Save back with refreshed TTL
            await self._redis_call(redis, "setex", key, timedelta(seconds=self.CACHE_TTL), json.dumps(messages))

            logger.debug(f"Appended message to conversation '{conversation_id}' cache (total: {len(messages)})")
            return True
        except Exception as e:
            logger.error(f"Error appending message to cache: {e}")
            return False

    async def get_conversation_summary(self, conversation_id: str) -> str | None:
        """
        Get cached conversation summary.

        Args:
            conversation_id: Conversation ID

        Returns:
            Summary text or None if not cached
        """
        redis = self._get_redis()
        if not redis:
            return None

        try:
            key = self._build_key(self.KEY_PREFIX_SUMMARY, conversation_id)
            summary = await self._redis_call(redis, "get", key)

            if summary:
                logger.info(f"✅ Cache HIT: Conversation summary for '{conversation_id}'")
                return summary.decode() if isinstance(summary, bytes) else summary

            return None
        except Exception as e:
            logger.error(f"Error getting cached conversation summary: {e}")
            return None

    async def set_conversation_summary(self, conversation_id: str, summary: str, ttl: int | None = None) -> bool:
        """
        Cache conversation summary.

        Args:
            conversation_id: Conversation ID
            summary: Summary text
            ttl: Time to live in seconds (default: 24 hours for summaries)

        Returns:
            True if cached successfully
        """
        redis = self._get_redis()
        if not redis:
            return False

        try:
            key = self._build_key(self.KEY_PREFIX_SUMMARY, conversation_id)
            ttl = ttl or self.SUMMARY_TTL  # Use longer TTL for summaries

            await self._redis_call(redis, "setex", key, timedelta(seconds=ttl), summary)

            logger.info(f"✅ Cached conversation summary for '{conversation_id}' ({len(summary)} chars, TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.error(f"Error caching conversation summary: {e}")
            return False

    async def get_conversation_metadata(self, conversation_id: str) -> dict[str, Any] | None:
        """
        Get cached conversation metadata.

        Args:
            conversation_id: Conversation ID

        Returns:
            Metadata dict or None if not cached
        """
        redis = self._get_redis()
        if not redis:
            return None

        try:
            key = self._build_key(self.KEY_PREFIX_META, conversation_id)
            cached_data = await self._redis_call(redis, "get", key)

            if cached_data:
                return json.loads(cached_data)

            return None
        except Exception as e:
            logger.error(f"Error getting cached conversation metadata: {e}")
            return None

    async def set_conversation_metadata(
        self, conversation_id: str, metadata: dict[str, Any], ttl: int | None = None
    ) -> bool:
        """
        Cache conversation metadata.

        Metadata includes:
        - total_messages: Total message count
        - total_tokens: Estimated total tokens
        - last_summary_at: Timestamp of last summarization
        - last_message_position: Position of last cached message

        Args:
            conversation_id: Conversation ID
            metadata: Metadata dict
            ttl: Time to live in seconds (default: 30 minutes)

        Returns:
            True if cached successfully
        """
        redis = self._get_redis()
        if not redis:
            return False

        try:
            key = self._build_key(self.KEY_PREFIX_META, conversation_id)
            ttl = ttl or self.CACHE_TTL

            await self._redis_call(redis, "setex", key, timedelta(seconds=ttl), json.dumps(metadata))

            logger.debug(f"Cached conversation metadata for '{conversation_id}'")
            return True
        except Exception as e:
            logger.error(f"Error caching conversation metadata: {e}")
            return False

    async def update_metadata_field(self, conversation_id: str, field: str, value: Any) -> bool:
        """
        Update a single metadata field.

        Args:
            conversation_id: Conversation ID
            field: Field name to update
            value: New value

        Returns:
            True if updated successfully
        """
        redis = self._get_redis()
        if not redis:
            return False

        try:
            metadata = await self.get_conversation_metadata(conversation_id)
            if metadata is None:
                metadata = {}

            metadata[field] = value
            return await self.set_conversation_metadata(conversation_id, metadata)
        except Exception as e:
            logger.error(f"Error updating metadata field: {e}")
            return False

    async def invalidate(self, conversation_id: str) -> None:
        """
        Invalidate all cache entries for a conversation.

        Args:
            conversation_id: Conversation ID
        """
        redis = self._get_redis()
        if not redis:
            return

        try:
            keys_to_delete = [
                self._build_key(self.KEY_PREFIX_HISTORY, conversation_id),
                self._build_key(self.KEY_PREFIX_SUMMARY, conversation_id),
                self._build_key(self.KEY_PREFIX_META, conversation_id),
            ]

            await self._redis_call(redis, "delete", *keys_to_delete)
            logger.info(f"✅ Invalidated cache for conversation '{conversation_id}'")
        except Exception as e:
            logger.error(f"Error invalidating conversation cache: {e}")

    async def invalidate_history_only(self, conversation_id: str) -> None:
        """
        Invalidate only the history cache (keep summary and metadata).

        Args:
            conversation_id: Conversation ID
        """
        redis = self._get_redis()
        if not redis:
            return

        try:
            key = self._build_key(self.KEY_PREFIX_HISTORY, conversation_id)
            await self._redis_call(redis, "delete", key)
            logger.debug(f"Invalidated history cache for conversation '{conversation_id}'")
        except Exception as e:
            logger.error(f"Error invalidating history cache: {e}")

    def _serialize_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Serialize messages for JSON storage."""
        return [self._serialize_message(msg) for msg in messages]

    def _serialize_message(self, message: dict[str, Any]) -> dict[str, Any]:
        """
        Serialize a single message for JSON storage.

        Handles UUID and datetime conversion.
        """
        serialized = {}
        for key, value in message.items():
            if hasattr(value, "hex"):  # UUID
                serialized[key] = str(value)
            elif hasattr(value, "isoformat"):  # datetime
                serialized[key] = value.isoformat()
            elif isinstance(value, dict):
                serialized[key] = self._serialize_message(value)
            elif isinstance(value, list):
                serialized[key] = [self._serialize_message(item) if isinstance(item, dict) else item for item in value]
            else:
                serialized[key] = value
        return serialized


# Global cache service instance
_conversation_cache_service = None


def get_conversation_cache() -> ConversationCacheService:
    """Get global conversation cache service instance."""
    global _conversation_cache_service

    if _conversation_cache_service is None:
        _conversation_cache_service = ConversationCacheService()

    return _conversation_cache_service
