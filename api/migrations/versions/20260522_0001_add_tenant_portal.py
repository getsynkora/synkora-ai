"""Add tenant_portals table for white-label portal configuration

Revision ID: 20260522_0001
Revises: 20260520_0001
Create Date: 2026-05-22

Creates the tenant_portals table that stores per-tenant branding,
subdomain/custom-domain config, and portal enable/disable toggle.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "20260522_0001"
down_revision = "20260520_0001"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name: str) -> bool:
    return bool(bind.dialect.has_table(bind, table_name))


def upgrade() -> None:
    bind = op.get_bind()

    if not _table_exists(bind, "tenant_portals"):
        op.create_table(
            "tenant_portals",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "tenant_id",
                UUID(as_uuid=True),
                sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("portal_enabled", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("subdomain", sa.String(100), nullable=True, unique=True),
            sa.Column("portal_domain", sa.String(255), nullable=True, unique=True),
            sa.Column("branding_config", JSONB, nullable=True),
            sa.Column("featured_agent_slugs", JSONB, nullable=True),
            sa.Column("seo_config", JSONB, nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("NOW()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("NOW()"),
            ),
            sa.UniqueConstraint("tenant_id", name="uq_tenant_portal_tenant"),
        )

        op.create_index("ix_tenant_portal_subdomain", "tenant_portals", ["subdomain"])
        op.create_index("ix_tenant_portal_domain", "tenant_portals", ["portal_domain"])


def downgrade() -> None:
    op.drop_index("ix_tenant_portal_domain", table_name="tenant_portals")
    op.drop_index("ix_tenant_portal_subdomain", table_name="tenant_portals")
    op.drop_table("tenant_portals")
