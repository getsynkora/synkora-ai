"""AgentPublicProfile model — public landing page data for an agent."""

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, relationship

from .base import BaseModel


class AgentPublicProfile(BaseModel):
    """Public landing page data for an agent."""

    __tablename__ = "agent_public_profiles"

    agent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Agent this profile belongs to",
    )

    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Creator tenant ID",
    )

    slug = Column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Globally unique URL slug",
    )

    tagline = Column(
        String(255),
        nullable=True,
        comment="Short tagline shown on the landing page",
    )

    long_description = Column(
        Text,
        nullable=True,
        comment="Markdown long description",
    )

    hero_image_url = Column(
        String(500),
        nullable=True,
        comment="Hero/banner image URL",
    )

    preview_video_url = Column(
        String(500),
        nullable=True,
        comment="Preview video URL",
    )

    gallery_images = Column(
        JSONB,
        nullable=True,
        comment="Gallery images: [{url, caption, order}]",
    )

    example_conversations = Column(
        JSONB,
        nullable=True,
        comment="Example conversations: [{title, messages:[{role,content}]}]",
    )

    creator_bio = Column(
        Text,
        nullable=True,
        comment="Creator biography text",
    )

    creator_display_name = Column(
        String(255),
        nullable=True,
        comment="Creator display name shown on the page",
    )

    seo_title = Column(
        String(255),
        nullable=True,
        comment="SEO meta title",
    )

    seo_description = Column(
        String(500),
        nullable=True,
        comment="SEO meta description",
    )

    og_image_url = Column(
        String(500),
        nullable=True,
        comment="Open Graph image URL",
    )

    cta_label = Column(
        String(100),
        nullable=True,
        default="Try it free",
        comment="Call-to-action button label",
    )

    accent_color = Column(
        String(20),
        nullable=True,
        comment="Hex or CSS accent color for the page",
    )

    is_published = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether the public profile is live",
    )

    view_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total page view count",
    )

    # Relationships
    agent: Mapped["Agent"] = relationship(
        "Agent",
        back_populates="public_profile",
    )

    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="public_profiles",
    )
