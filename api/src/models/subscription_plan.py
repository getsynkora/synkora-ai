"""
Subscription Plan model.

This module defines the subscription plan model for the credit-based pricing system.
"""

from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Boolean, Column, Integer, Numeric, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import true as sa_true
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, relationship

from .base import BaseModel


class PlanTier(StrEnum):
    """Subscription plan tiers."""

    FREE = "FREE"
    HOBBY = "HOBBY"
    STARTER = "STARTER"
    PROFESSIONAL = "PROFESSIONAL"
    ENTERPRISE = "ENTERPRISE"


class SubscriptionPlan(BaseModel):
    """
    Subscription Plan model.

    Defines the available subscription plans with pricing and credit allocations.
    """

    __tablename__ = "subscription_plans"

    name = Column(
        String(100),
        nullable=False,
        unique=True,
        comment="Plan name (e.g., Free, Starter, Professional, Enterprise)",
    )

    tier = Column(
        SQLEnum(PlanTier),
        nullable=False,
        default=PlanTier.FREE,
        index=True,
        comment="Plan tier for categorization",
    )

    description = Column(
        Text,
        nullable=True,
        comment="Plan description and features",
    )

    price_monthly = Column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Monthly subscription price in USD",
    )

    price_yearly = Column(
        Numeric(10, 2),
        nullable=True,
        comment="Yearly subscription price in USD (discounted)",
    )

    credits_monthly = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Monthly credit allocation",
    )

    credits_rollover = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether unused credits roll over to next month",
    )

    max_agents = Column(
        Integer,
        nullable=True,
        comment="Maximum number of agents allowed (null = unlimited)",
    )

    max_team_members = Column(
        Integer,
        nullable=True,
        comment="Maximum number of team members allowed (null = unlimited)",
    )

    max_api_calls_per_month = Column(
        Integer,
        nullable=True,
        comment="Maximum API calls per month (null = unlimited)",
    )

    max_knowledge_bases = Column(
        Integer,
        nullable=True,
        comment="Maximum number of knowledge bases (null = unlimited)",
    )

    max_data_sources = Column(
        Integer,
        nullable=True,
        comment="Maximum number of data sources (null = unlimited)",
    )

    max_custom_tools = Column(
        Integer,
        nullable=True,
        comment="Maximum number of custom tools (null = unlimited)",
    )

    max_database_connections = Column(
        Integer,
        nullable=True,
        comment="Maximum number of database connections (null = unlimited)",
    )

    max_mcp_servers = Column(
        Integer,
        nullable=True,
        comment="Maximum number of MCP servers (null = unlimited)",
    )

    max_scheduled_tasks = Column(
        Integer,
        nullable=True,
        comment="Maximum number of scheduled tasks (null = unlimited)",
    )

    max_widgets = Column(
        Integer,
        nullable=True,
        comment="Maximum number of widgets (null = unlimited)",
    )

    max_slack_bots = Column(
        Integer,
        nullable=True,
        comment="Maximum number of Slack bots (null = unlimited)",
    )

    max_api_keys = Column(
        Integer,
        nullable=True,
        comment="Maximum number of API keys (null = unlimited)",
    )

    features = Column(
        JSONB,
        nullable=True,
        comment="JSON object of plan features and limits",
    )

    quota_pools = Column(
        JSONB,
        nullable=True,
        comment=(
            "Per-pool monthly message quotas: [{'key': slug, 'label': display name, 'limit': int}]. "
            "Null = plan uses the shared credit balance instead."
        ),
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether plan is currently available for subscription",
    )

    is_public = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default=sa_true(),
        comment="Shown on the pricing page; off for plans only set through the API by another billing system",
    )

    stripe_product_id = Column(
        String(255),
        nullable=True,
        comment="Stripe Product ID for this plan",
    )

    stripe_price_id = Column(
        String(255),
        nullable=True,
        comment="Stripe Price ID for monthly subscription",
    )

    paddle_product_id = Column(
        String(255),
        nullable=True,
        comment="Paddle Product ID for this plan",
    )

    paddle_price_id = Column(
        String(255),
        nullable=True,
        comment="Paddle Price ID for monthly subscription",
    )

    # Relationships
    subscriptions: Mapped[list["TenantSubscription"]] = relationship(
        "TenantSubscription",
        back_populates="plan",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<SubscriptionPlan(id={self.id}, name={self.name}, tier={self.tier})>"

    @property
    def yearly_discount_percentage(self) -> float | None:
        """Calculate yearly discount percentage."""
        if not self.price_yearly or self.price_monthly == 0:
            return None
        monthly_total = float(self.price_monthly) * 12
        yearly_price = float(self.price_yearly)
        return ((monthly_total - yearly_price) / monthly_total) * 100
