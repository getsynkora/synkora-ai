"""Slack Bot models for agent integration with Socket Mode support."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base


class SlackBot(Base):
    """Slack Bot configuration model with Socket Mode support."""

    __tablename__ = "slack_bots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)

    # Slack App Configuration
    bot_name = Column(String(255), nullable=False)
    slack_app_id = Column(String(255), nullable=False)
    slack_bot_token = Column(Text, nullable=False, comment="Encrypted bot token (xoxb-*)")
    slack_app_token = Column(Text, nullable=True, comment="Encrypted app-level token for Socket Mode (xapp-*)")

    # Connection Mode (socket or event)
    connection_mode = Column(String(20), default="socket", nullable=False, comment="Connection mode: socket or event")
    signing_secret = Column(Text, nullable=True, comment="Encrypted signing secret for Event Mode")
    webhook_url = Column(Text, nullable=True, comment="Auto-generated webhook URL for Event Mode")

    # Workspace Information (auto-detected on first connection)
    slack_workspace_id = Column(String(255), nullable=True)
    slack_workspace_name = Column(String(255), nullable=True)

    # Ownership — account that created/connected this bot (used to resolve OAuth tokens for scheduled runs)
    created_by = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    allow_external_shared_channels = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="If False (default), bot refuses to respond in Slack Connect / externally-shared channels",
    )
    connection_status = Column(
        String(50), default="disconnected", nullable=False, comment="connected, disconnected, error"
    )
    last_connected_at = Column(DateTime, nullable=True)

    # Worker Assignment (for scalable worker pool)
    assigned_worker_id = Column(String(255), nullable=True, comment="ID of the worker managing this bot")
    worker_connected_at = Column(DateTime, nullable=True, comment="When the worker established the connection")

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    agent = relationship("Agent", back_populates="slack_bots")
    tenant = relationship("Tenant")
    conversations = relationship("SlackConversation", back_populates="slack_bot", cascade="all, delete-orphan")

    @property
    def is_socket_mode(self) -> bool:
        """Check if the bot uses Socket Mode."""
        return self.connection_mode == "socket"

    @property
    def is_event_mode(self) -> bool:
        """Check if the bot uses Event Mode (HTTP webhooks)."""
        return self.connection_mode == "event"

    def __repr__(self):
        return f"<SlackBot {self.bot_name} (workspace: {self.slack_workspace_name}, status: {self.connection_status}, mode: {self.connection_mode})>"


class SlackConversation(Base):
    """Mapping between Slack threads and agent conversations."""

    __tablename__ = "slack_conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slack_bot_id = Column(UUID(as_uuid=True), ForeignKey("slack_bots.id", ondelete="CASCADE"), nullable=False)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)

    # Slack Thread Information
    slack_channel_id = Column(String(255), nullable=False)
    slack_user_id = Column(String(255), nullable=False)
    slack_thread_ts = Column(String(255), nullable=True, comment="Thread timestamp for threaded conversations")

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    slack_bot = relationship("SlackBot", back_populates="conversations")
    conversation = relationship("Conversation")

    def __repr__(self):
        return f"<SlackConversation channel={self.slack_channel_id} user={self.slack_user_id}>"
