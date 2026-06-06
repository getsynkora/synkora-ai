"""Bot Worker configuration."""

import os
import uuid

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotWorkerConfig(BaseSettings):
    """Configuration for bot worker processes."""

    # Worker identification
    worker_id: str = Field(
        default_factory=lambda: os.environ.get("WORKER_ID", f"worker-{uuid.uuid4().hex[:12]}"),
        description="Unique identifier for this worker instance",
    )

    # Capacity settings
    worker_capacity: int = Field(
        default=1000,
        description="Maximum number of bots this worker can handle",
        ge=1,
        le=10000,
    )

    # Heartbeat settings
    heartbeat_interval: int = Field(
        default=10,
        description="Interval between heartbeats in seconds",
        ge=1,
        le=60,
    )

    heartbeat_timeout: int = Field(
        default=30,
        description="Consider worker dead after this many seconds without heartbeat",
        ge=10,
        le=300,
    )

    # Health server
    health_port: int = Field(
        default=8080,
        description="Port for health check HTTP server",
    )

    # Startup behavior
    startup_jitter_max: float = Field(
        default=5.0,
        description="Maximum random delay (seconds) when starting bots to avoid thundering herd",
    )

    # Consistent hash settings
    hash_replicas: int = Field(
        default=100,
        description="Number of virtual nodes per worker in consistent hash ring",
    )

    # Graceful shutdown
    shutdown_timeout: int = Field(
        default=30,
        description="Maximum time to wait for graceful shutdown in seconds",
    )

    model_config = SettingsConfigDict(env_prefix="BOT_WORKER_")
