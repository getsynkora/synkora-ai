"""CreatorProfile model — public creator/developer profile."""

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, relationship

from .base import BaseModel


class CreatorProfile(BaseModel):
    """Public creator/developer profile (one per tenant)."""

    __tablename__ = "creator_profiles"

    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Tenant this creator profile belongs to (one per tenant)",
    )

    username = Column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
        comment="Globally unique username / public URL segment",
    )

    display_name = Column(
        String(255),
        nullable=True,
        comment="Public display name",
    )

    bio = Column(
        Text,
        nullable=True,
        comment="Creator biography",
    )

    avatar_url = Column(
        String(500),
        nullable=True,
        comment="Avatar image URL",
    )

    banner_image_url = Column(
        String(500),
        nullable=True,
        comment="Banner/cover image URL",
    )

    website_url = Column(
        String(500),
        nullable=True,
        comment="Personal or company website URL",
    )

    twitter_url = Column(
        String(500),
        nullable=True,
        comment="Twitter/X profile URL",
    )

    linkedin_url = Column(
        String(500),
        nullable=True,
        comment="LinkedIn profile URL",
    )

    github_url = Column(
        String(500),
        nullable=True,
        comment="GitHub profile URL",
    )

    stripe_account_id = Column(
        String(255),
        nullable=True,
        comment="Stripe Connect account ID for payouts",
    )

    stripe_onboarding_complete = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether Stripe Connect onboarding is complete",
    )

    is_public = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether the creator profile is publicly visible",
    )

    total_earnings_credits = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Cumulative earnings in platform credits",
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="creator_profile",
    )
