"""
Agent API Key model for programmatic agent access.

This module defines the database model for API keys that allow external
applications to interact with agents programmatically via REST API.
"""

import secrets
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship

from src.models.base import BaseModel, TenantMixin

if TYPE_CHECKING:
    pass


class AgentApiKey(BaseModel, TenantMixin):
    """
    Agent API Key model for programmatic agent access.

    Attributes:
        agent_id: UUID of the agent this API key provides access to
        key_name: Human-readable name for the API key
        api_key: Unique API key for authentication (hashed)
        key_prefix: First 8 characters of the key for identification
        permissions: List of allowed operations (e.g., ['chat', 'execute'])
        rate_limit_per_minute: Maximum requests per minute
        rate_limit_per_hour: Maximum requests per hour
        rate_limit_per_day: Maximum requests per day
        allowed_ips: List of IP addresses allowed to use this key
        allowed_origins: List of CORS origins allowed to use this key
        expires_at: Optional expiration timestamp for the key
        last_used_at: Timestamp of last successful use
        is_active: Whether the API key is currently active
        metadata: Additional metadata (e.g., created_by, purpose)
        tenant_id: Tenant identifier for multi-tenancy
    """

    __tablename__ = "agent_api_keys"

    agent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Agent this API key provides access to; null for a platform key (tenant-level, platform APIs only)",
    )

    key_name = Column(
        String(255),
        nullable=False,
        comment="Human-readable name for the API key",
    )

    api_key = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Hashed API key for authentication",
    )

    key_prefix = Column(
        String(20),
        nullable=False,
        index=True,
        comment="First characters of the key for identification (e.g., sk_live_abc123...)",
    )

    permissions = Column(
        ARRAY(String),
        nullable=False,
        default=["chat"],
        comment="List of allowed operations (e.g., ['chat', 'execute', 'stream', 'mcp_server', 'a2a'])",
    )

    rate_limit_per_minute = Column(
        Integer,
        nullable=False,
        default=60,
        comment="Maximum requests per minute (0 = unlimited)",
    )

    rate_limit_per_hour = Column(
        Integer,
        nullable=False,
        default=1000,
        comment="Maximum requests per hour (0 = unlimited)",
    )

    rate_limit_per_day = Column(
        Integer,
        nullable=False,
        default=10000,
        comment="Maximum requests per day (0 = unlimited)",
    )

    allowed_ips = Column(
        ARRAY(Text),
        nullable=True,
        comment="List of IP addresses allowed to use this key (null = all IPs)",
    )

    allowed_origins = Column(
        ARRAY(Text),
        nullable=True,
        comment="List of CORS origins allowed to use this key (null = all origins)",
    )

    expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Optional expiration timestamp for the key",
    )

    last_used_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of last successful use",
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether the API key is currently active",
    )

    key_metadata = Column(
        JSONB,
        nullable=True,
        comment="Additional metadata (e.g., created_by, purpose, environment)",
    )

    # Relationships
    agent = relationship("Agent", back_populates="api_keys")
    usage_records = relationship("AgentApiUsage", back_populates="api_key", cascade="all, delete-orphan", lazy="select")

    @staticmethod
    def generate_api_key() -> tuple[str, str]:
        """
        Generate a secure random API key with Stripe-like format.

        Returns:
            tuple[str, str]: (full_key, key_prefix) where full_key is the complete
                           key to show to user once, and key_prefix is for identification
        """
        # Generate random token (48 bytes = 64 characters in base64)
        token = secrets.token_urlsafe(48)
        full_key = f"sk_live_{token}"
        key_prefix = full_key[:20]  # e.g., "sk_live_abc123..."
        return full_key, key_prefix

    @property
    def is_expired(self) -> bool:
        """Check if the API key has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(UTC) > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if the API key is valid (active and not expired)."""
        return self.is_active and not self.is_expired

    def update_last_used(self) -> None:
        """Update the last_used_at timestamp."""
        self.last_used_at = datetime.now(UTC)

    def to_dict(self, exclude: set[str] | None = None) -> dict:
        """
        Convert model instance to dictionary.

        Args:
            exclude: Set of field names to exclude from output

        Returns:
            dict: Model data as dictionary
        """
        # Always exclude the full API key from serialization
        exclude = exclude or set()
        exclude.add("api_key")

        data = super().to_dict(exclude=exclude)

        # Convert arrays to proper format
        if data.get("permissions") is None:
            data["permissions"] = ["chat"]
        if data.get("allowed_ips") is None:
            data["allowed_ips"] = []
        if data.get("allowed_origins") is None:
            data["allowed_origins"] = []

        # Ensure key_metadata is a dict
        if data.get("key_metadata") is None:
            data["key_metadata"] = {}

        # Add computed properties
        data["is_expired"] = self.is_expired
        data["is_valid"] = self.is_valid

        return data

    def __repr__(self) -> str:
        """String representation of model instance."""
        return f"<AgentApiKey(id={self.id}, name={self.key_name}, prefix={self.key_prefix})>"
