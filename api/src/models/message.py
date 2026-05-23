"""
Message model for managing conversation messages.

A Message represents a single message in a conversation (user or assistant).
"""

import enum
from uuid import UUID

from sqlalchemy import JSON, Enum, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin


class MessageRole(enum.StrEnum):
    """Message role."""

    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"

    @classmethod
    def _missing_(cls, value: object) -> "MessageRole | None":
        if isinstance(value, str):
            for member in cls:
                if member.value == value.upper():
                    return member
        return None


class MessageStatus(enum.StrEnum):
    """Message status."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Message(Base, UUIDMixin, TimestampMixin):
    """
    Message model representing a conversation message.

    Attributes:
        conversation_id: Foreign key to conversation
        role: Message role (user, assistant, system)
        content: Message content
        metadata: Additional metadata (JSON)
        status: Message status
        error: Error message if failed
        token_count: Number of tokens used
        position: Message position in conversation
    """

    __tablename__ = "messages"
    __table_args__ = (
        # Composite index for efficient message retrieval by conversation ordered by created_at
        # This covers the common query: SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at
        Index("ix_messages_conversation_created_at", "conversation_id", "created_at"),
    )

    # Foreign keys
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey("conversations.id"), nullable=False, index=True)

    # Message info
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole, native_enum=False, length=50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Status
    status: Mapped[MessageStatus] = mapped_column(
        Enum(MessageStatus, native_enum=False, length=50),
        nullable=False,
        default=MessageStatus.COMPLETED,
    )
    error: Mapped[str | None] = mapped_column(Text)

    # Metrics
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Attachments (file uploads in chat)
    attachments: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Relationships
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")
    charts: Mapped[list["Chart"]] = relationship("Chart", back_populates="message", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        """String representation."""
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<Message {self.role.value}: {preview}>"

    def to_dict(self) -> dict:
        """
        Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "id": str(self.id),
            "conversation_id": str(self.conversation_id),
            "role": self.role.value,
            "content": self.content,
            "metadata": self.message_metadata,
            "attachments": self.attachments,
            "status": self.status.value,
            "error": self.error,
            "token_count": self.token_count,
            "position": self.position,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def is_user_message(self) -> bool:
        """Check if message is from user."""
        return self.role == MessageRole.USER

    def is_assistant_message(self) -> bool:
        """Check if message is from assistant."""
        return self.role == MessageRole.ASSISTANT

    def is_completed(self) -> bool:
        """Check if message is completed."""
        return self.status == MessageStatus.COMPLETED
