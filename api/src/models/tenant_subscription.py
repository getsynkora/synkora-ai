"""
Tenant Subscription model.

This module defines the tenant subscription model for tracking active subscriptions.
"""

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, false
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, relationship

from .base import BaseModel


class BillingCycle(StrEnum):
    """Billing cycle options."""

    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"


class SubscriptionStatus(StrEnum):
    """Subscription status values."""

    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    SUSPENDED = "SUSPENDED"
    TRIAL = "TRIAL"


class TenantSubscription(BaseModel):
    """
    Tenant Subscription model.

    Tracks active subscriptions for tenants with billing and renewal information.
    """

    __tablename__ = "tenant_subscriptions"

    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Tenant ID",
    )

    plan_id = Column(
        UUID(as_uuid=True),
        ForeignKey("subscription_plans.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Subscription plan ID",
    )

    status = Column(
        SQLEnum(SubscriptionStatus),
        nullable=False,
        default=SubscriptionStatus.TRIAL,
        index=True,
        comment="Current subscription status",
    )

    billing_cycle = Column(
        SQLEnum(BillingCycle),
        nullable=False,
        default=BillingCycle.MONTHLY,
        comment="Billing cycle (monthly or yearly)",
    )

    current_period_start = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Start date of current billing period",
    )

    current_period_end = Column(
        DateTime(timezone=True),
        nullable=False,
        comment="End date of current billing period",
    )

    trial_end = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Trial period end date (if applicable)",
    )

    cancelled_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when subscription was cancelled",
    )

    payment_provider = Column(
        String(20),
        nullable=False,
        default="stripe",
        index=True,
        comment="Payment provider: 'stripe' or 'paddle'",
    )

    stripe_subscription_id = Column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
        comment="Stripe subscription ID for payment tracking",
    )

    stripe_customer_id = Column(
        String(255),
        nullable=True,
        index=True,
        comment="Stripe customer ID",
    )

    paddle_subscription_id = Column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
        comment="Paddle subscription ID for payment tracking",
    )

    paddle_customer_id = Column(
        String(255),
        nullable=True,
        index=True,
        comment="Paddle customer ID",
    )

    cancel_at_period_end = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        comment="Subscription ends at the end of the current period instead of renewing",
    )

    auto_renew = Column(
        String(10),
        nullable=False,
        default="true",
        comment="Whether subscription auto-renews (stored as string)",
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="subscriptions",
    )

    plan: Mapped["SubscriptionPlan"] = relationship(
        "SubscriptionPlan",
        back_populates="subscriptions",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<TenantSubscription(id={self.id}, tenant_id={self.tenant_id}, status={self.status})>"

    @property
    def is_active(self) -> bool:
        """Check if subscription is currently active."""
        return self.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL)

    @property
    def is_trial(self) -> bool:
        """Check if subscription is in trial period."""
        return self.status == SubscriptionStatus.TRIAL

    @property
    def days_until_renewal(self) -> int | None:
        """Calculate days until next renewal."""
        if not self.current_period_end:
            return None
        delta = self.current_period_end - datetime.now(UTC)
        return max(0, delta.days)
