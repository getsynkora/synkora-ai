"""
WebSocket manager for real-time communication.
"""

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from fastapi import WebSocket
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# Type alias for authorization callback
RoomAuthorizationCallback = Callable[[str, UUID, UUID], Awaitable[bool]]


# Connection limits - configurable via environment variables
MAX_CONNECTIONS_PER_USER = int(os.getenv("WS_MAX_CONNECTIONS_PER_USER", "10"))
MAX_TOTAL_CONNECTIONS = int(os.getenv("WS_MAX_TOTAL_CONNECTIONS", "10000"))
MAX_CONNECTIONS_PER_TENANT = int(os.getenv("WS_MAX_CONNECTIONS_PER_TENANT", "500"))


class WebSocketMessage(BaseModel):
    """WebSocket message structure."""

    type: str
    data: dict[str, Any]
    conversation_id: str | None = None
    message_id: str | None = None


class ConnectionLimitExceeded(Exception):
    """Exception raised when connection limits are exceeded."""

    def __init__(self, message: str, limit_type: str):
        self.message = message
        self.limit_type = limit_type
        super().__init__(message)


class RoomAuthorizationError(Exception):
    """Exception raised when a user is not authorized to access a room."""

    def __init__(self, message: str, room_id: str, user_id: UUID):
        self.message = message
        self.room_id = room_id
        self.user_id = user_id
        super().__init__(message)


class ConnectionManager:
    """
    Manages WebSocket connections for real-time communication.

    Supports:
    - Multiple connections per user (with limits)
    - Room-based messaging (conversations)
    - Broadcast to all connections
    - User-specific messaging
    - Connection limits per user, tenant, and global
    """

    def __init__(
        self,
        max_connections_per_user: int = MAX_CONNECTIONS_PER_USER,
        max_total_connections: int = MAX_TOTAL_CONNECTIONS,
        max_connections_per_tenant: int = MAX_CONNECTIONS_PER_TENANT,
        room_authorization_callback: RoomAuthorizationCallback | None = None,
    ):
        """Initialize connection manager with limits."""
        # Lock for thread-safe connection management (prevents race conditions)
        self._connection_lock = asyncio.Lock()

        # Active connections: {user_id: {websocket1, websocket2, ...}}
        self.active_connections: dict[UUID, set[WebSocket]] = {}

        # Room subscriptions: {room_id: {user_id1, user_id2, ...}}
        self.rooms: dict[str, set[UUID]] = {}

        # Connection metadata: {websocket: {user_id, tenant_id, ...}}
        self.connection_metadata: dict[WebSocket, dict[str, Any]] = {}

        # Tenant connection tracking: {tenant_id: connection_count}
        self.tenant_connections: dict[UUID, int] = {}

        # Connection limits
        self.max_connections_per_user = max_connections_per_user
        self.max_total_connections = max_total_connections
        self.max_connections_per_tenant = max_connections_per_tenant

        # Authorization callback for room access
        self._room_authorization_callback = room_authorization_callback

    def _check_connection_limits(self, user_id: UUID, tenant_id: UUID) -> None:
        """
        Check if connection limits would be exceeded.

        Raises:
            ConnectionLimitExceeded: If any limit would be exceeded
        """
        # Check global connection limit
        total_connections = self.get_connection_count()
        if total_connections >= self.max_total_connections:
            logger.warning(f"Global connection limit reached: {total_connections}/{self.max_total_connections}")
            raise ConnectionLimitExceeded(
                f"Server connection limit reached ({self.max_total_connections})",
                "global",
            )

        # Check per-user connection limit
        user_connections = len(self.active_connections.get(user_id, set()))
        if user_connections >= self.max_connections_per_user:
            logger.warning(
                f"User connection limit reached: user={user_id}, "
                f"connections={user_connections}/{self.max_connections_per_user}"
            )
            raise ConnectionLimitExceeded(
                f"Too many connections for user ({self.max_connections_per_user})",
                "user",
            )

        # Check per-tenant connection limit
        tenant_connections = self.tenant_connections.get(tenant_id, 0)
        if tenant_connections >= self.max_connections_per_tenant:
            logger.warning(
                f"Tenant connection limit reached: tenant={tenant_id}, "
                f"connections={tenant_connections}/{self.max_connections_per_tenant}"
            )
            raise ConnectionLimitExceeded(
                f"Too many connections for tenant ({self.max_connections_per_tenant})",
                "tenant",
            )

    async def connect(
        self,
        websocket: WebSocket,
        user_id: UUID,
        tenant_id: UUID,
    ) -> None:
        """
        Accept and register a new WebSocket connection.

        Uses a lock to prevent race conditions when checking and updating
        connection limits under high concurrency.

        Args:
            websocket: WebSocket connection
            user_id: User ID
            tenant_id: Tenant ID

        Raises:
            ConnectionLimitExceeded: If connection limits are exceeded
        """
        # Use lock to prevent race condition between limit check and registration
        async with self._connection_lock:
            # Check limits before accepting
            self._check_connection_limits(user_id, tenant_id)

            await websocket.accept()

            # Add to active connections (inside lock to prevent race condition)
            if user_id not in self.active_connections:
                self.active_connections[user_id] = set()
            self.active_connections[user_id].add(websocket)

            # Track tenant connections
            if tenant_id not in self.tenant_connections:
                self.tenant_connections[tenant_id] = 0
            self.tenant_connections[tenant_id] += 1

            # Store metadata
            self.connection_metadata[websocket] = {
                "user_id": user_id,
                "tenant_id": tenant_id,
            }

            logger.debug(
                f"WebSocket connected: user={user_id}, tenant={tenant_id}, "
                f"user_connections={len(self.active_connections[user_id])}, "
                f"tenant_connections={self.tenant_connections[tenant_id]}, "
                f"total_connections={self.get_connection_count()}"
            )

        # Send connection confirmation
        await self.send_personal_message(
            {
                "type": "connection",
                "data": {
                    "status": "connected",
                    "user_id": str(user_id),
                },
            },
            websocket,
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """
        Remove a WebSocket connection.

        Args:
            websocket: WebSocket connection to remove
        """
        # Get metadata
        metadata = self.connection_metadata.get(websocket)
        if not metadata:
            return

        user_id = metadata["user_id"]
        tenant_id = metadata.get("tenant_id")

        # Remove from active connections
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

        # Decrement tenant connection count
        if tenant_id and tenant_id in self.tenant_connections:
            self.tenant_connections[tenant_id] -= 1
            if self.tenant_connections[tenant_id] <= 0:
                del self.tenant_connections[tenant_id]

        # Remove from all rooms
        for room_users in self.rooms.values():
            room_users.discard(user_id)

        # Remove metadata
        del self.connection_metadata[websocket]

        logger.debug(
            f"WebSocket disconnected: user={user_id}, tenant={tenant_id}, "
            f"total_connections={self.get_connection_count()}"
        )

    async def send_personal_message(
        self,
        message: dict[str, Any],
        websocket: WebSocket,
    ) -> None:
        """
        Send message to a specific WebSocket connection.

        Args:
            message: Message to send
            websocket: Target WebSocket connection
        """
        try:
            await websocket.send_json(message)
        except Exception:
            # Connection might be closed
            self.disconnect(websocket)

    async def send_to_user(
        self,
        message: dict[str, Any],
        user_id: UUID,
    ) -> None:
        """
        Send message to all connections of a specific user.

        Args:
            message: Message to send
            user_id: Target user ID
        """
        if user_id not in self.active_connections:
            return

        # Send to all user's connections
        disconnected = []
        for websocket in self.active_connections[user_id]:
            try:
                await websocket.send_json(message)
            except Exception:
                disconnected.append(websocket)

        # Clean up disconnected websockets
        for websocket in disconnected:
            self.disconnect(websocket)

    async def broadcast(
        self,
        message: dict[str, Any],
        exclude: set[UUID] | None = None,
    ) -> None:
        """
        Broadcast message to all connected users.

        Args:
            message: Message to broadcast
            exclude: Set of user IDs to exclude from broadcast
        """
        exclude = exclude or set()

        for user_id in list(self.active_connections.keys()):
            if user_id not in exclude:
                await self.send_to_user(message, user_id)

    def set_room_authorization_callback(self, callback: RoomAuthorizationCallback) -> None:
        """
        Set the authorization callback for room access.

        Args:
            callback: Async function that takes (room_id, user_id, tenant_id)
                     and returns True if access is allowed
        """
        self._room_authorization_callback = callback

    def get_user_tenant_id(self, user_id: UUID) -> UUID | None:
        """
        Get tenant_id for a connected user.

        Args:
            user_id: User ID to look up

        Returns:
            Tenant ID if user is connected, None otherwise
        """
        if user_id not in self.active_connections:
            return None

        # Get tenant_id from any of the user's connections
        for websocket in self.active_connections[user_id]:
            metadata = self.connection_metadata.get(websocket)
            if metadata and "tenant_id" in metadata:
                return metadata["tenant_id"]
        return None

    async def join_room(self, room_id: str, user_id: UUID, skip_authorization: bool = False) -> None:
        """
        Add user to a room (e.g., conversation) after authorization check.

        Args:
            room_id: Room identifier
            user_id: User ID to add
            skip_authorization: Skip authorization check (use with caution,
                               only for internal operations)

        Raises:
            RoomAuthorizationError: If user is not authorized to join the room
        """
        # SECURITY: Check authorization before allowing room join
        if not skip_authorization and self._room_authorization_callback:
            tenant_id = self.get_user_tenant_id(user_id)
            if tenant_id is None:
                logger.warning(f"User {user_id} attempted to join room {room_id} but is not connected")
                raise RoomAuthorizationError(
                    "User must be connected to join a room",
                    room_id,
                    user_id,
                )

            try:
                is_authorized = await self._room_authorization_callback(room_id, user_id, tenant_id)
            except Exception as e:
                logger.error(f"Authorization check failed for user {user_id} joining room {room_id}: {e}")
                raise RoomAuthorizationError(
                    "Authorization check failed",
                    room_id,
                    user_id,
                )

            if not is_authorized:
                logger.warning(f"Unauthorized room access attempt: user={user_id}, room={room_id}, tenant={tenant_id}")
                raise RoomAuthorizationError(
                    f"User is not authorized to access room {room_id}",
                    room_id,
                    user_id,
                )

        if room_id not in self.rooms:
            self.rooms[room_id] = set()
        self.rooms[room_id].add(user_id)
        logger.debug(f"User {user_id} joined room {room_id}")

    def leave_room(self, room_id: str, user_id: UUID) -> None:
        """
        Remove user from a room.

        Args:
            room_id: Room identifier
            user_id: User ID to remove
        """
        if room_id in self.rooms:
            self.rooms[room_id].discard(user_id)
            if not self.rooms[room_id]:
                del self.rooms[room_id]

    def is_user_in_room(self, room_id: str, user_id: UUID) -> bool:
        """
        Check if a user is currently in a room.

        Args:
            room_id: Room identifier
            user_id: User ID to check

        Returns:
            True if user is in the room, False otherwise
        """
        return room_id in self.rooms and user_id in self.rooms[room_id]

    async def send_to_room(
        self,
        room_id: str,
        message: dict[str, Any],
        exclude: set[UUID] | None = None,
        sender_user_id: UUID | None = None,
    ) -> None:
        """
        Send message to all users in a room.

        SECURITY: Only sends to users who have been authorized to join the room.
        If sender_user_id is provided, verifies the sender is a member of the room.

        Args:
            room_id: Room identifier
            message: Message to send
            exclude: Set of user IDs to exclude
            sender_user_id: Optional sender ID for authorization verification
        """
        if room_id not in self.rooms:
            logger.debug(f"Attempted to send to non-existent room: {room_id}")
            return

        # SECURITY: Verify sender is a member of the room if provided
        if sender_user_id is not None and not self.is_user_in_room(room_id, sender_user_id):
            logger.warning(f"User {sender_user_id} attempted to send to room {room_id} without being a member")
            return

        exclude = exclude or set()

        for user_id in self.rooms[room_id]:
            if user_id not in exclude:
                await self.send_to_user(message, user_id)

    async def stream_message(
        self,
        conversation_id: str,
        message_id: str,
        content_chunk: str,
        user_id: UUID,
        is_final: bool = False,
    ) -> None:
        """
        Stream message content in real-time.

        Args:
            conversation_id: Conversation ID
            message_id: Message ID
            content_chunk: Content chunk to stream
            user_id: Target user ID
            is_final: Whether this is the final chunk
        """
        message = {
            "type": "message_stream",
            "data": {
                "conversation_id": conversation_id,
                "message_id": message_id,
                "content": content_chunk,
                "is_final": is_final,
            },
        }

        await self.send_to_user(message, user_id)

    async def send_typing_indicator(
        self,
        conversation_id: str,
        user_id: UUID,
        is_typing: bool = True,
    ) -> None:
        """
        Send typing indicator to conversation participants.

        Args:
            conversation_id: Conversation ID
            user_id: User who is typing
            is_typing: Whether user is typing
        """
        message = {
            "type": "typing",
            "data": {
                "conversation_id": conversation_id,
                "user_id": str(user_id),
                "is_typing": is_typing,
            },
        }

        # Send to all users in the conversation room except the sender
        await self.send_to_room(
            f"conversation:{conversation_id}",
            message,
            exclude={user_id},
        )

    async def send_error(
        self,
        error: str,
        websocket: WebSocket,
        error_code: str | None = None,
    ) -> None:
        """
        Send error message to a WebSocket connection.

        Args:
            error: Error message
            websocket: Target WebSocket connection
            error_code: Optional error code
        """
        message = {
            "type": "error",
            "data": {
                "error": error,
                "code": error_code,
            },
        }

        await self.send_personal_message(message, websocket)

    def get_user_count(self) -> int:
        """Get number of connected users."""
        return len(self.active_connections)

    def get_connection_count(self) -> int:
        """Get total number of WebSocket connections."""
        return sum(len(connections) for connections in self.active_connections.values())

    def is_user_connected(self, user_id: UUID) -> bool:
        """Check if user has any active connections."""
        return user_id in self.active_connections and len(self.active_connections[user_id]) > 0

    def get_connection_stats(self) -> dict:
        """Get detailed connection statistics for monitoring."""
        return {
            "total_connections": self.get_connection_count(),
            "total_users": self.get_user_count(),
            "total_tenants": len(self.tenant_connections),
            "total_rooms": len(self.rooms),
            "limits": {
                "max_per_user": self.max_connections_per_user,
                "max_per_tenant": self.max_connections_per_tenant,
                "max_total": self.max_total_connections,
            },
            "utilization": {
                "total_percent": (self.get_connection_count() / self.max_total_connections) * 100
                if self.max_total_connections > 0
                else 0,
            },
        }

    def get_tenant_connection_count(self, tenant_id: UUID) -> int:
        """Get connection count for a specific tenant."""
        return self.tenant_connections.get(tenant_id, 0)


class DistributedConnectionManager(ConnectionManager):
    """
    Distributed WebSocket connection manager with Redis pub/sub support.

    Extends ConnectionManager to support multi-pod Kubernetes deployments
    by using Redis pub/sub for cross-pod message delivery.
    """

    CHANNEL_PREFIX = "ws:broadcast:"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._redis_pubsub = None
        self._pubsub_redis = None
        self._subscriber_task = None
        self._pod_id = os.getenv("POD_NAME", os.getenv("HOSTNAME", "unknown"))

    async def _make_pubsub_client(self):
        """
        Create a dedicated Redis client for pub/sub with no socket timeout.

        Pub/sub holds the connection open waiting for messages indefinitely.
        Reusing the shared async client (which has socket_timeout=5s) causes
        the listener to raise TimeoutError every 5 seconds of silence.
        """
        import os

        import redis.asyncio as aioredis

        from src.config.settings import settings

        sentinel_hosts = os.getenv("REDIS_SENTINEL_HOSTS")
        master_name = os.getenv("REDIS_MASTER_NAME", "mymaster")

        if sentinel_hosts:
            from redis.asyncio.sentinel import Sentinel as AsyncSentinel

            from src.config.redis import _parse_sentinel_hosts

            hosts = _parse_sentinel_hosts(sentinel_hosts)
            sentinel = AsyncSentinel(hosts)
            return sentinel.master_for(
                master_name,
                password=os.getenv("REDIS_PASSWORD"),
                decode_responses=True,
                socket_timeout=None,  # no timeout for pub/sub reads
                socket_connect_timeout=5.0,
            )
        else:
            redis_url = str(settings.redis_url)
            return aioredis.from_url(
                redis_url,
                decode_responses=True,
                socket_timeout=None,  # no timeout for pub/sub reads
                socket_connect_timeout=5.0,
            )

    async def start_redis_subscriber(self) -> None:
        """Start Redis pub/sub subscriber for cross-pod messaging."""
        try:
            self._pubsub_redis = await self._make_pubsub_client()
            self._redis_pubsub = self._pubsub_redis.pubsub()

            # Exact-match channel for global broadcasts.
            await self._redis_pubsub.subscribe(f"{self.CHANNEL_PREFIX}all")
            # Pattern subscriptions for per-user and per-room channels.
            # subscribe() does NOT support glob patterns — only psubscribe() does.
            await self._redis_pubsub.psubscribe(f"{self.CHANNEL_PREFIX}user:*")
            await self._redis_pubsub.psubscribe(f"{self.CHANNEL_PREFIX}room:*")

            logger.info(f"WebSocket Redis pub/sub started on pod {self._pod_id}")

            # Start background listener
            self._subscriber_task = asyncio.create_task(self._listen_for_messages())
        except Exception as e:
            logger.warning(f"Failed to start Redis pub/sub for WebSocket: {e}. Running in local mode.")

    async def stop_redis_subscriber(self) -> None:
        """Stop Redis pub/sub subscriber."""
        if self._subscriber_task:
            self._subscriber_task.cancel()
            try:
                await self._subscriber_task
            except asyncio.CancelledError:
                pass

        if self._redis_pubsub:
            await self._redis_pubsub.unsubscribe()
            await self._redis_pubsub.punsubscribe()
            await self._redis_pubsub.aclose()

        if hasattr(self, "_pubsub_redis") and self._pubsub_redis:
            await self._pubsub_redis.aclose()

        logger.info("WebSocket Redis pub/sub stopped")

    async def _listen_for_messages(self) -> None:
        """
        Background task to listen for Redis pub/sub messages.

        Reconnects automatically on transient errors (network blips, Redis
        restarts) with exponential backoff up to 60 seconds.
        """
        import json

        backoff = 1.0
        while True:
            try:
                async for message in self._redis_pubsub.listen():
                    backoff = 1.0  # reset on successful receive
                    if message["type"] in ("message", "pmessage"):
                        try:
                            data = json.loads(message["data"])

                            # Skip messages from this pod
                            if data.get("source_pod") == self._pod_id:
                                continue

                            channel = message.get("channel", message.get("pattern", ""))
                            await self._handle_distributed_message(channel, data)
                        except json.JSONDecodeError:
                            continue
                        except Exception as e:
                            logger.error(f"Error handling distributed WebSocket message: {e}")
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.warning(f"Redis pub/sub listener error: {e}. Reconnecting in {backoff:.0f}s...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)

                # Re-subscribe on reconnect
                try:
                    await self._redis_pubsub.subscribe(f"{self.CHANNEL_PREFIX}all")
                    await self._redis_pubsub.psubscribe(f"{self.CHANNEL_PREFIX}user:*")
                    await self._redis_pubsub.psubscribe(f"{self.CHANNEL_PREFIX}room:*")
                except Exception:
                    pass  # will retry on next loop iteration

    async def _handle_distributed_message(self, channel: str, data: dict) -> None:
        """Handle incoming message from another pod."""
        from uuid import UUID

        msg_type = data.get("type")
        payload = data.get("payload")

        if msg_type == "room":
            room_id = data.get("room_id")
            if room_id:
                # Reconstruct the exclude set so the sender is not echoed back
                # from this pod. The exclude list was serialised as strings when
                # published; convert back to UUIDs.
                exclude_strs = data.get("exclude", [])
                exclude = {UUID(u) for u in exclude_strs} if exclude_strs else None
                # Cross-pod room messages skip sender_user_id check (already
                # verified on the origin pod).
                await super().send_to_room(room_id, payload, exclude=exclude)
        elif msg_type == "user":
            user_id = data.get("user_id")
            if user_id:
                await super().send_to_user(payload, UUID(user_id))
        elif msg_type == "broadcast":
            exclude_strs = data.get("exclude", [])
            exclude = {UUID(u) for u in exclude_strs} if exclude_strs else None
            await super().broadcast(payload, exclude=exclude)

    async def _publish_to_redis(self, channel: str, data: dict) -> None:
        """Publish message to Redis for other pods."""
        import json

        try:
            from src.config.redis import get_redis_async

            # Use the async Redis client — calling the sync client inside an async
            # method blocks the event loop on every WebSocket message send.
            redis = get_redis_async()
            data["source_pod"] = self._pod_id
            await redis.publish(channel, json.dumps(data))
        except Exception as e:
            logger.debug(f"Failed to publish to Redis: {e}")

    async def send_to_room(
        self,
        room_id: str,
        message: dict[str, Any],
        exclude: set[UUID] | None = None,
        sender_user_id: UUID | None = None,
    ) -> None:
        """Send message to room, including cross-pod delivery."""
        # Send to local connections (includes authorization check)
        await super().send_to_room(room_id, message, exclude, sender_user_id)

        # Publish to Redis for other pods
        await self._publish_to_redis(
            f"{self.CHANNEL_PREFIX}room:{room_id}",
            {
                "type": "room",
                "room_id": room_id,
                "payload": message,
                "exclude": [str(u) for u in (exclude or set())],
            },
        )

    async def send_to_user(
        self,
        message: dict[str, Any],
        user_id: UUID,
    ) -> None:
        """Send message to user, including cross-pod delivery."""
        # Send to local connections
        await super().send_to_user(message, user_id)

        # Publish to Redis for other pods
        await self._publish_to_redis(
            f"{self.CHANNEL_PREFIX}user:{user_id}",
            {
                "type": "user",
                "user_id": str(user_id),
                "payload": message,
            },
        )

    async def broadcast(
        self,
        message: dict[str, Any],
        exclude: set[UUID] | None = None,
    ) -> None:
        """Broadcast message to all users, including cross-pod delivery."""
        # Send to local connections
        await super().broadcast(message, exclude)

        # Publish to Redis for other pods
        await self._publish_to_redis(
            f"{self.CHANNEL_PREFIX}all",
            {
                "type": "broadcast",
                "payload": message,
                "exclude": [str(u) for u in (exclude or set())],
            },
        )


# Import asyncio for the distributed manager

# Global connection manager instance - use distributed version for K8s
# Falls back to local-only mode if Redis is unavailable
connection_manager = DistributedConnectionManager()
