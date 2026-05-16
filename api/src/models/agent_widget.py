"""
Agent Widget model for embedded HTML widget integration.

This module defines the database model for agent widgets that can be
embedded in external websites via JavaScript.
"""

import secrets
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship

from src.models.base import BaseModel, TenantMixin

if TYPE_CHECKING:
    pass


class AgentWidget(BaseModel, TenantMixin):
    """
    Agent Widget model for embedded HTML widget integration.

    Attributes:
        agent_id: UUID of the agent this widget exposes
        widget_name: Human-readable name for the widget
        api_key: Unique API key for widget authentication
        allowed_domains: List of domains allowed to embed this widget
        theme_config: JSON configuration for widget appearance
        rate_limit: Maximum requests per hour (default: 100)
        is_active: Whether the widget is currently active
        tenant_id: Tenant identifier for multi-tenancy
    """

    __tablename__ = "agent_widgets"

    agent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Agent this widget exposes",
    )

    widget_name = Column(
        String(255),
        nullable=False,
        comment="Human-readable name for the widget",
    )

    api_key = Column(
        Text,
        nullable=False,
        comment="SECURITY: Encrypted API key for widget authentication",
    )

    key_prefix = Column(
        String(32),
        unique=True,
        nullable=True,
        index=True,
        comment="First 16 chars of API key for identification/lookup",
    )

    allowed_domains = Column(
        ARRAY(Text),
        nullable=True,
        comment="List of domains allowed to embed this widget (null = all domains)",
    )

    theme_config = Column(
        JSONB,
        nullable=True,
        comment="JSON configuration for widget appearance and behavior",
    )

    rate_limit = Column(
        Integer,
        nullable=False,
        default=100,
        comment="Maximum requests per hour",
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether the widget is currently active",
    )

    identity_secret = Column(
        Text,
        nullable=True,
        comment="SECURITY: Encrypted HMAC secret for verifying user identity",
    )

    identity_verification_required = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="When True, user context + valid HMAC required on every chat request",
    )

    enable_agent_routing = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="When True, resolve agent from widget_agent_routes table based on org_id",
    )

    mobile_allowed = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="When True, Origin header check is skipped — allows Flutter/mobile SDK access",
    )

    fcm_server_key = Column(
        Text,
        nullable=True,
        comment="SECURITY: Encrypted FCM Server Key for sending push notifications to mobile users",
    )

    # Relationships
    agent = relationship("Agent", back_populates="widgets")
    routes = relationship("WidgetAgentRoute", back_populates="widget", cascade="all, delete-orphan")

    @staticmethod
    def generate_api_key() -> tuple[str, str, str]:
        """
        Generate a secure random API key.

        SECURITY: Returns plain key (for user), encrypted key (for storage),
        and key prefix (for lookup).

        Returns:
            Tuple of (plain_key, encrypted_key, key_prefix)
        """
        from src.services.agents.security import encrypt_value

        plain_key = f"swk_{secrets.token_urlsafe(48)}"
        encrypted_key = encrypt_value(plain_key)
        key_prefix = plain_key[:20]  # e.g., "swk_abc123..."

        return plain_key, encrypted_key, key_prefix

    def to_dict(self, exclude: set[str] | None = None) -> dict:
        """
        Convert model instance to dictionary.

        Args:
            exclude: Set of field names to exclude from output

        Returns:
            dict: Model data as dictionary
        """
        data = super().to_dict(exclude=exclude)

        # Convert allowed_domains list to proper format
        if data.get("allowed_domains") is None:
            data["allowed_domains"] = []

        # Ensure theme_config is a dict
        if data.get("theme_config") is None:
            data["theme_config"] = {}

        return data

    def __repr__(self) -> str:
        """String representation of model instance."""
        return f"<AgentWidget(id={self.id}, name={self.widget_name}, agent_id={self.agent_id})>"


class WidgetAnalytics(BaseModel):
    """
    Widget Analytics model for tracking widget usage.

    Attributes:
        widget_id: UUID of the widget
        session_id: Unique session identifier
        messages_count: Number of messages in this session
        domain: Domain where the widget was embedded
        user_agent: Browser user agent string
    """

    __tablename__ = "widget_analytics"

    widget_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_widgets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Widget this analytics record belongs to",
    )

    session_id = Column(
        String(255),
        nullable=False,
        index=True,
        comment="Unique session identifier",
    )

    messages_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of messages in this session",
    )

    domain = Column(
        String(255),
        nullable=True,
        index=True,
        comment="Domain where the widget was embedded",
    )

    user_agent = Column(
        Text,
        nullable=True,
        comment="Browser user agent string",
    )

    # Relationships
    widget = relationship("AgentWidget")

    def __repr__(self) -> str:
        """String representation of model instance."""
        return f"<WidgetAnalytics(id={self.id}, widget_id={self.widget_id}, session={self.session_id})>"
