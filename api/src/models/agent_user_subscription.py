"""AgentUserSubscription — paid chat/email access subscription for an agent.

NOTE: This is distinct from AgentSubscription (email notification subscribers).
This model tracks PAID ACCESS — who has paid to chat with or receive emails
from a monetised agent.
"""

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, relationship

from .base import BaseModel


class SubscriptionAccessStatus(StrEnum):
    """Access status for a paid agent subscription."""

    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class AgentUserSubscription(BaseModel):
    """Paid access subscription granting a user the right to chat with or receive emails from an agent."""

    __tablename__ = "agent_user_subscriptions"
    __table_args__ = (
        Index("ix_agent_user_sub_agent_tenant", "agent_id", "subscriber_tenant_id"),
        Index("ix_agent_user_sub_tenant_status", "subscriber_tenant_id", "status"),
    )

    agent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        comment="Agent being subscribed to",
    )

    agent_pricing_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_pricing.id", ondelete="CASCADE"),
        nullable=False,
        comment="Pricing record at time of purchase",
    )

    subscriber_tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True,
        comment="Tenant of the subscriber (null for guest checkouts)",
    )

    guest_email = Column(
        String(255),
        nullable=True,
        comment="Email address for guest (non-account) subscribers",
    )

    guest_token_hash = Column(
        String(64),
        nullable=True,
        unique=True,
        comment="SHA-256 hash of the browser cookie token for guest access",
    )

    stripe_subscription_id = Column(
        String(255),
        nullable=True,
        comment="Stripe subscription ID",
    )

    stripe_customer_id = Column(
        String(255),
        nullable=True,
        comment="Stripe customer ID",
    )

    pricing_tier = Column(
        String(30),
        nullable=False,
        comment="Tier purchased: SESSION|DAILY|WEEKLY|MONTHLY|EMAIL_ONE_TIME|EMAIL_MONTHLY",
    )

    amount_cents = Column(
        Integer,
        nullable=False,
        comment="Price paid in cents at time of purchase",
    )

    status = Column(
        SQLEnum(SubscriptionAccessStatus),
        nullable=False,
        default=SubscriptionAccessStatus.ACTIVE,
        comment="Current access status",
    )

    started_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        comment="When access began",
    )

    expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When access expires (null = no expiry)",
    )

    cancelled_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the subscription was cancelled",
    )

    # Relationships
    agent: Mapped["Agent"] = relationship(
        "Agent",
    )

    agent_pricing: Mapped["AgentPricing"] = relationship(
        "AgentPricing",
        back_populates="user_subscriptions",
    )

    subscriber_tenant: Mapped["Tenant"] = relationship(
        "Tenant",
    )
