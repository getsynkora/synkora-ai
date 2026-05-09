"""AgentSubscription model — email subscribers for scheduled agent reports."""

import uuid

from sqlalchemy import Boolean, Column, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.models.base import BaseModel


class AgentSubscription(BaseModel):
    """Email subscription to an agent's scheduled task output."""

    __tablename__ = "agent_subscriptions"
    __table_args__ = (UniqueConstraint("agent_id", "email", name="uq_agent_subscription_agent_email"),)

    agent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    email = Column(String(255), nullable=False)

    unsubscribe_token = Column(
        UUID(as_uuid=True),
        unique=True,
        nullable=False,
        default=uuid.uuid4,
    )

    is_active = Column(Boolean, nullable=False, default=True)

    paid_subscription_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_user_subscriptions.id", ondelete="SET NULL"),
        nullable=True,
        comment="FK to AgentUserSubscription if this email sub requires payment. NULL = free subscription.",
    )

    # Relationship
    agent = relationship("Agent", back_populates="subscriptions")

    def __repr__(self) -> str:
        return f"<AgentSubscription(id={self.id}, agent_id={self.agent_id}, email='{self.email}')>"
