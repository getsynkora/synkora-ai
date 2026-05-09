"""AgentDiscountCode — promotional discount codes for agent pricing."""

from enum import StrEnum

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, relationship

from .base import BaseModel


class DiscountType(StrEnum):
    """Type of discount applied by a code."""

    PERCENTAGE = "PERCENTAGE"
    FLAT_CREDITS = "FLAT_CREDITS"


class AgentDiscountCode(BaseModel):
    """Promotional discount code associated with an agent pricing record."""

    __tablename__ = "agent_discount_codes"
    __table_args__ = (UniqueConstraint("agent_pricing_id", "code", name="uq_discount_code_pricing_code"),)

    agent_pricing_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_pricing.id", ondelete="CASCADE"),
        nullable=False,
        comment="Pricing record this code applies to",
    )

    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        comment="Creator's tenant ID",
    )

    code = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Discount code string entered by subscribers",
    )

    discount_type = Column(
        SQLEnum(DiscountType),
        nullable=False,
        comment="Whether the discount is a percentage or flat credit amount",
    )

    discount_value = Column(
        Numeric(10, 2),
        nullable=False,
        comment="Discount amount (percent 0-100 or flat credit value)",
    )

    max_uses = Column(
        Integer,
        nullable=True,
        comment="Maximum number of redemptions (null = unlimited)",
    )

    used_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of times this code has been redeemed",
    )

    valid_from = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Earliest date/time the code is valid",
    )

    valid_until = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Expiry date/time of the code (null = no expiry)",
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether the code is currently active",
    )

    # Relationships
    agent_pricing: Mapped["AgentPricing"] = relationship(
        "AgentPricing",
        back_populates="discount_codes",
    )

    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
    )
