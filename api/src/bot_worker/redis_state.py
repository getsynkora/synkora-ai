"""Redis state management for bot worker coordination.

This module manages distributed state in Redis for:
- Worker registration and heartbeats
- Bot-to-worker assignments
- Event streaming for bot lifecycle events
- Worker commands via pub/sub
"""

import json
import logging
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import redis

logger = logging.getLogger(__name__)


class BotType(StrEnum):
    """Bot platform types."""

    SLACK = "slack"
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"


class BotEventType(StrEnum):
    """Bot lifecycle event types."""

    ACTIVATE = "activate"
    DEACTIVATE = "deactivate"
    RESTART = "restart"


@dataclass
class BotEvent:
    """Bot lifecycle event."""

    event_type: BotEventType
    bot_id: str
    bot_type: BotType
    timestamp: float
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, str | float]:
        """Convert to dict for Redis XADD (values must be str/int/float/bytes)."""
        return {
            "type": self.event_type.value,
            "bot_id": self.bot_id,
            "bot_type": self.bot_type.value,
            "timestamp": self.timestamp,
            "metadata": json.dumps(self.metadata or {}),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BotEvent":
        metadata_raw = data.get("metadata", "{}")
        if isinstance(metadata_raw, bytes):
            metadata_raw = metadata_raw.decode("utf-8")
        metadata = json.loads(metadata_raw) if isinstance(metadata_raw, str) else metadata_raw
        return cls(
            event_type=BotEventType(data["type"] if isinstance(data["type"], str) else data["type"].decode("utf-8")),
            bot_id=data["bot_id"] if isinstance(data["bot_id"], str) else data["bot_id"].decode("utf-8"),
            bot_type=BotType(
                data["bot_type"] if isinstance(data["bot_type"], str) else data["bot_type"].decode("utf-8")
            ),
            timestamp=float(data["timestamp"]),
            metadata=metadata,
        )


@dataclass
class WorkerInfo:
    """Worker metadata."""

    worker_id: str
    capacity: int
    active_bots: int
    started_at: float
    last_heartbeat: float
    host: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "capacity": self.capacity,
            "active_bots": self.active_bots,
            "started_at": self.started_at,
            "last_heartbeat": self.last_heartbeat,
            "host": self.host,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "WorkerInfo | None":
        """Create WorkerInfo from dict. Returns None if required fields are missing."""
        # Check for required fields
        required_fields = ["worker_id", "capacity", "active_bots", "started_at", "last_heartbeat"]
        if not all(field in data for field in required_fields):
            return None

        return cls(
            worker_id=data["worker_id"],
            capacity=int(data["capacity"]),
            active_bots=int(data["active_bots"]),
            started_at=float(data["started_at"]),
            last_heartbeat=float(data["last_heartbeat"]),
            host=data.get("host"),
        )


class BotRedisState:
    """Redis state manager for bot worker coordination."""

    # Redis key prefixes
    KEY_WORKER_INFO = "bot_worker:info:"  # Hash: worker metadata
    KEY_WORKER_HEARTBEATS = "bot_worker:heartbeats"  # Sorted set: worker_id -> timestamp
    KEY_BOT_ASSIGNMENTS = "bot_worker:assignments"  # Hash: bot_id -> worker_id
    KEY_BOT_EVENTS = "bot_worker:events"  # Stream: bot lifecycle events
    KEY_WORKER_COMMANDS = "bot_worker:commands:"  # Pub/sub: commands to specific worker
    KEY_BOT_CLAIM_LOCK = "bot_worker:claim_lock:"  # String w/ TTL: bot_id -> claiming worker_id

    def __init__(self, redis_client: redis.Redis):
        """Initialize with a Redis client.

        Args:
            redis_client: Connected Redis client instance
        """
        self.redis = redis_client

    # ==================== Worker Management ====================

    def register_worker(self, worker_id: str, capacity: int, host: str | None = None) -> None:
        """Register a new worker in Redis.

        Args:
            worker_id: Unique worker identifier
            capacity: Maximum bots this worker can handle
            host: Optional hostname/IP of the worker
        """
        now = time.time()

        # Store worker info
        worker_info = {
            "worker_id": worker_id,
            "capacity": str(capacity),
            "active_bots": "0",
            "started_at": str(now),
            "last_heartbeat": str(now),
            "host": host or "",
        }
        self.redis.hset(f"{self.KEY_WORKER_INFO}{worker_id}", mapping=worker_info)

        # Add to heartbeat sorted set
        self.redis.zadd(self.KEY_WORKER_HEARTBEATS, {worker_id: now})

        logger.info(f"Registered worker {worker_id} with capacity {capacity}")

    def unregister_worker(self, worker_id: str) -> None:
        """Remove a worker from Redis.

        Args:
            worker_id: Worker to remove
        """
        # Remove worker info
        self.redis.delete(f"{self.KEY_WORKER_INFO}{worker_id}")

        # Remove from heartbeat set
        self.redis.zrem(self.KEY_WORKER_HEARTBEATS, worker_id)

        logger.info(f"Unregistered worker {worker_id}")

    def send_heartbeat(self, worker_id: str, active_bots: int) -> None:
        """Send a heartbeat for a worker.

        Args:
            worker_id: Worker sending the heartbeat
            active_bots: Current number of active bots on this worker
        """
        now = time.time()

        # Update heartbeat timestamp
        self.redis.zadd(self.KEY_WORKER_HEARTBEATS, {worker_id: now})

        # Update worker info
        self.redis.hset(
            f"{self.KEY_WORKER_INFO}{worker_id}",
            mapping={"last_heartbeat": str(now), "active_bots": str(active_bots)},
        )

    def get_worker_info(self, worker_id: str) -> WorkerInfo | None:
        """Get information about a specific worker.

        Args:
            worker_id: Worker to look up

        Returns:
            WorkerInfo if found, None otherwise
        """
        data = self.redis.hgetall(f"{self.KEY_WORKER_INFO}{worker_id}")
        if not data:
            return None
        # Add worker_id to data since it's stored in the key, not the hash values
        data["worker_id"] = worker_id
        return WorkerInfo.from_dict(data)

    def get_all_workers(self) -> list[WorkerInfo]:
        """Get information about all registered workers.

        Returns:
            List of WorkerInfo for all workers
        """
        # Get all worker IDs from heartbeat set
        worker_ids = self.redis.zrange(self.KEY_WORKER_HEARTBEATS, 0, -1)

        workers = []
        for worker_id in worker_ids:
            info = self.get_worker_info(worker_id)
            if info:
                workers.append(info)

        return workers

    def get_healthy_workers(self, timeout: int = 30) -> list[str]:
        """Get worker IDs that have sent a heartbeat within the timeout period.

        Args:
            timeout: Maximum seconds since last heartbeat to be considered healthy

        Returns:
            List of healthy worker IDs
        """
        cutoff = time.time() - timeout
        return self.redis.zrangebyscore(self.KEY_WORKER_HEARTBEATS, cutoff, "+inf")

    def get_dead_workers(self, timeout: int = 30) -> list[str]:
        """Get worker IDs that haven't sent a heartbeat within the timeout period.

        Args:
            timeout: Maximum seconds since last heartbeat

        Returns:
            List of dead worker IDs
        """
        cutoff = time.time() - timeout
        return self.redis.zrangebyscore(self.KEY_WORKER_HEARTBEATS, "-inf", cutoff)

    # ==================== Bot Assignment Management ====================

    def try_claim_bot_lock(self, bot_id: str, worker_id: str, ttl_seconds: int = 30) -> bool:
        """Atomically claim the right to start a bot.

        assign_bot() is a plain HSET (last-write-wins) with no compare-and-swap,
        so two workers independently deciding "this bot looks orphaned, I'll
        start it" can both pass that check and both start duplicate connections
        (visible as Telegram's "Conflict: terminated by other getUpdates
        request", and silently for Slack Socket Mode, which doesn't error on
        duplicate connections the same way). This lock closes that race: only
        the worker that wins the atomic SET NX may proceed to _start_bot().

        The TTL is a safety net, not the primary release mechanism — release_bot_lock()
        should be called once assign_bot() has recorded ownership (success or
        failure), but if the claiming worker dies before that, the lock still
        expires on its own instead of permanently blocking reassignment.

        Returns:
            True if this worker won the claim, False if another worker holds it.
        """
        key = f"{self.KEY_BOT_CLAIM_LOCK}{bot_id}"
        return bool(self.redis.set(key, worker_id, nx=True, ex=ttl_seconds))

    def release_bot_lock(self, bot_id: str) -> None:
        """Release a claim lock acquired via try_claim_bot_lock()."""
        self.redis.delete(f"{self.KEY_BOT_CLAIM_LOCK}{bot_id}")

    def assign_bot(self, bot_id: str, worker_id: str, bot_type: BotType) -> None:
        """Assign a bot to a worker.

        Args:
            bot_id: Bot to assign
            worker_id: Worker to assign to
            bot_type: Type of bot (slack/telegram)
        """
        # Store assignment with bot type
        self.redis.hset(
            self.KEY_BOT_ASSIGNMENTS,
            bot_id,
            json.dumps({"worker_id": worker_id, "bot_type": bot_type.value}),
        )
        logger.debug(f"Assigned bot {bot_id} ({bot_type.value}) to worker {worker_id}")

    def unassign_bot(self, bot_id: str) -> None:
        """Remove a bot assignment.

        Args:
            bot_id: Bot to unassign
        """
        self.redis.hdel(self.KEY_BOT_ASSIGNMENTS, bot_id)
        logger.debug(f"Unassigned bot {bot_id}")

    def get_bot_assignment(self, bot_id: str) -> tuple[str, BotType] | None:
        """Get the worker assigned to a bot.

        Args:
            bot_id: Bot to look up

        Returns:
            Tuple of (worker_id, bot_type) if assigned, None otherwise
        """
        data = self.redis.hget(self.KEY_BOT_ASSIGNMENTS, bot_id)
        if not data:
            return None

        parsed = json.loads(data)
        return parsed["worker_id"], BotType(parsed["bot_type"])

    def get_bots_for_worker(self, worker_id: str) -> list[tuple[str, BotType]]:
        """Get all bots assigned to a specific worker.

        Args:
            worker_id: Worker to look up

        Returns:
            List of (bot_id, bot_type) tuples
        """
        all_assignments = self.redis.hgetall(self.KEY_BOT_ASSIGNMENTS)
        result = []

        for bot_id, data in all_assignments.items():
            parsed = json.loads(data)
            if parsed["worker_id"] == worker_id:
                result.append((bot_id, BotType(parsed["bot_type"])))

        return result

    def get_all_assigned_bot_ids(self) -> list[str]:
        """Get all bot IDs that have assignments.

        Returns:
            List of bot IDs
        """
        return list(self.redis.hkeys(self.KEY_BOT_ASSIGNMENTS))

    # ==================== Event Streaming ====================

    def publish_bot_event(self, event: BotEvent) -> str:
        """Publish a bot lifecycle event to the stream.

        Args:
            event: Event to publish

        Returns:
            Stream message ID
        """
        return self.redis.xadd(self.KEY_BOT_EVENTS, event.to_dict())

    def read_bot_events(
        self, last_id: str = "0", count: int = 100, block: int | None = None
    ) -> list[tuple[str, BotEvent]]:
        """Read bot events from the stream.

        Args:
            last_id: Start reading after this message ID
            count: Maximum number of events to read
            block: Milliseconds to block waiting for new events (None = don't block)

        Returns:
            List of (message_id, BotEvent) tuples
        """
        result = self.redis.xread({self.KEY_BOT_EVENTS: last_id}, count=count, block=block)

        events = []
        if result:
            for _stream_name, messages in result:
                for msg_id, data in messages:
                    try:
                        events.append((msg_id, BotEvent.from_dict(data)))
                    except Exception as e:
                        logger.warning(f"Failed to parse event {msg_id}: {e}")

        return events

    def get_latest_event_id(self) -> str:
        """Return the ID of the most-recent event in the stream, or '0' if empty."""
        result = self.redis.xrevrange(self.KEY_BOT_EVENTS, "+", "-", count=1)
        if result:
            msg_id, _ = result[0]
            return msg_id if isinstance(msg_id, str) else msg_id.decode()
        return "0"

    def trim_bot_events(self, max_len: int = 10000) -> None:
        """Trim the event stream to prevent unbounded growth.

        Args:
            max_len: Maximum number of events to keep
        """
        self.redis.xtrim(self.KEY_BOT_EVENTS, maxlen=max_len, approximate=True)

    # ==================== Worker Commands (Pub/Sub) ====================

    def send_worker_command(self, worker_id: str, command: dict[str, Any]) -> int:
        """Send a command to a specific worker.

        Args:
            worker_id: Target worker
            command: Command data (should include 'action' key)

        Returns:
            Number of subscribers that received the message
        """
        channel = f"{self.KEY_WORKER_COMMANDS}{worker_id}"
        return self.redis.publish(channel, json.dumps(command))

    def subscribe_to_commands(self, worker_id: str) -> redis.client.PubSub:
        """Subscribe to commands for a specific worker.

        Args:
            worker_id: Worker to subscribe for

        Returns:
            PubSub object for receiving messages
        """
        pubsub = self.redis.pubsub()
        pubsub.subscribe(f"{self.KEY_WORKER_COMMANDS}{worker_id}")
        return pubsub

    # ==================== Utility Methods ====================

    def clear_all_state(self) -> None:
        """Clear all bot worker state from Redis.

        WARNING: This will disrupt all running workers!
        """
        # Get all keys matching our prefix
        keys = self.redis.keys("bot_worker:*")
        if keys:
            self.redis.delete(*keys)
        logger.warning("Cleared all bot worker state from Redis")
