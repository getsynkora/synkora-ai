"""
TenantPortal Model

Stores white-label portal configuration for a tenant.
Each tenant can have at most one portal (unique on tenant_id).
"""

from sqlalchemy import Boolean, Column, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from src.models.base import BaseModel


class TenantPortal(BaseModel):
    """
    White-label portal configuration for a tenant.

    Controls the public-facing branded portal that tenant customers see,
    independent of the Synkora platform itself.
    """

    __tablename__ = "tenant_portals"

    __table_args__ = (UniqueConstraint("tenant_id", name="uq_tenant_portal_tenant"),)

    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Owning tenant (one portal per tenant)",
    )

    portal_enabled = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether the portal is publicly accessible",
    )

    subdomain = Column(
        String(100),
        nullable=True,
        unique=True,
        index=True,
        comment="Auto-generated subdomain slug (e.g. 'acmecorp')",
    )

    portal_domain = Column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
        comment="Optional custom domain (e.g. 'ai.acmecorp.com')",
    )

    branding_config = Column(
        JSONB,
        nullable=True,
        comment=(
            "Branding configuration: logo_url, favicon_url, primary_color, "
            "secondary_color, font_family, site_title, tagline, footer_text, "
            "social_links {twitter, linkedin, github, website}"
        ),
    )

    featured_agent_slugs = Column(
        JSONB,
        nullable=True,
        comment="Ordered list of agent slugs to feature on the portal home page",
    )

    seo_config = Column(
        JSONB,
        nullable=True,
        comment="SEO configuration: meta_description, og_image_url",
    )

    def __repr__(self) -> str:
        return f"<TenantPortal(tenant_id={self.tenant_id}, subdomain={self.subdomain!r})>"
