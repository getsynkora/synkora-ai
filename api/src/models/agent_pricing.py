"""
Agent Pricing model.

This module defines the agent pricing model for agent monetization.
"""

from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Boolean, Column, ForeignKey, Integer, Numeric, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, relationship

from .base import BaseModel


class PricingModel(StrEnum):
    """Agent pricing models."""

    FREE = "FREE"
    PER_USE = "PER_USE"
    SUBSCRIPTION = "SUBSCRIPTION"
    SESSION = "SESSION"  # single conversation (chat access)
    DAILY = "DAILY"  # 24hr access
    WEEKLY = "WEEKLY"  # 7-day access
    MONTHLY = "MONTHLY"  # 30-day rolling


class AgentPricing(BaseModel):
    """
    Agent Pricing model.

    Defines monetization settings for agents.
    """

    __tablename__ = "agent_pricing"

    agent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Agent ID",
    )

    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Creator tenant ID",
    )

    pricing_model = Column(
        SQLEnum(PricingModel),
        nullable=False,
        default=PricingModel.FREE,
        index=True,
        comment="Pricing model type",
    )

    credits_per_use = Column(
        Integer,
        nullable=True,
        comment="Credits charged per use (for PER_USE model)",
    )

    monthly_subscription_credits = Column(
        Integer,
        nullable=True,
        comment="Monthly subscription cost in credits",
    )

    revenue_share_percentage = Column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("70.00"),
        comment="Creator revenue share percentage (e.g., 70.00 for 70%)",
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether pricing is active",
    )

    total_uses = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total number of uses",
    )

    total_revenue_credits = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total revenue earned in credits",
    )

    session_credits = Column(Integer, nullable=True, comment="Credits for single session access")
    daily_credits = Column(Integer, nullable=True, comment="Credits for 24hr access")
    weekly_credits = Column(Integer, nullable=True, comment="Credits for 7-day access")
    trial_messages = Column(Integer, nullable=True, default=0, comment="Free messages before paywall")

    email_subscription_model = Column(
        String(20),
        nullable=False,
        default="FREE",
        comment="Email subscription pricing model: FREE, ONE_TIME, MONTHLY",
    )
    email_subscription_price_cents = Column(Integer, nullable=True, comment="Email subscription price in cents")
    email_subscription_trial_emails = Column(
        Integer, nullable=True, default=0, comment="Free emails before email paywall"
    )

    # Relationships
    agent: Mapped["Agent"] = relationship(
        "Agent",
        back_populates="pricing",
    )

    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="agent_pricing",
    )

    revenue_records: Mapped[list["AgentRevenue"]] = relationship(
        "AgentRevenue",
        back_populates="agent_pricing",
        order_by="AgentRevenue.created_at.desc()",
    )

    discount_codes: Mapped[list["AgentDiscountCode"]] = relationship(
        "AgentDiscountCode",
        back_populates="agent_pricing",
        cascade="all, delete-orphan",
    )

    user_subscriptions: Mapped[list["AgentUserSubscription"]] = relationship(
        "AgentUserSubscription",
        back_populates="agent_pricing",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<AgentPricing(id={self.id}, agent_id={self.agent_id}, model={self.pricing_model})>"

    @property
    def is_free(self) -> bool:
        """Check if agent is free to use."""
        return self.pricing_model == PricingModel.FREE

    @property
    def is_paid(self) -> bool:
        """Check if agent requires payment."""
        return self.pricing_model in (
            PricingModel.PER_USE,
            PricingModel.SUBSCRIPTION,
            PricingModel.SESSION,
            PricingModel.DAILY,
            PricingModel.WEEKLY,
            PricingModel.MONTHLY,
        )

    def calculate_creator_revenue(self, amount: int) -> int:
        """Calculate creator's share of revenue."""
        return int(amount * float(self.revenue_share_percentage) / 100)

    def calculate_platform_revenue(self, amount: int) -> int:
        """Calculate platform's share of revenue."""
        return amount - self.calculate_creator_revenue(amount)
