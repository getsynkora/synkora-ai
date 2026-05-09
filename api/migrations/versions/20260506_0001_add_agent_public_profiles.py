"""add agent_public_profiles table for marketplace listings

Revision ID: 20260506_0001
Revises: 20260430_0099
Create Date: 2026-05-06

Creates the agent_public_profiles table that stores public-facing marketplace
metadata for agents, including SEO fields, gallery images, example conversations,
creator info, and CTA customisation.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

# revision identifiers, used by Alembic.
revision = "20260506_0001"
down_revision = "20260430_0099"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    if not bind.dialect.has_table(bind, "agent_public_profiles"):
        op.create_table(
            "agent_public_profiles",
            sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, nullable=False),
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
            sa.Column(
                "agent_id",
                pg.UUID(as_uuid=True),
                nullable=False,
            ),
            sa.Column(
                "tenant_id",
                pg.UUID(as_uuid=True),
                nullable=False,
            ),
            sa.Column("slug", sa.String(100), nullable=False),
            sa.Column("tagline", sa.String(255), nullable=True),
            sa.Column("long_description", sa.Text(), nullable=True),
            sa.Column("hero_image_url", sa.String(500), nullable=True),
            sa.Column("preview_video_url", sa.String(500), nullable=True),
            sa.Column("gallery_images", pg.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("example_conversations", pg.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("creator_bio", sa.Text(), nullable=True),
            sa.Column("creator_display_name", sa.String(255), nullable=True),
            sa.Column("seo_title", sa.String(255), nullable=True),
            sa.Column("seo_description", sa.String(500), nullable=True),
            sa.Column("og_image_url", sa.String(500), nullable=True),
            sa.Column("cta_label", sa.String(100), nullable=True, server_default="Try it free"),
            sa.Column("accent_color", sa.String(20), nullable=True),
            sa.Column(
                "is_published",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column(
                "view_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("agent_id", name="uq_agent_public_profile_agent"),
            sa.UniqueConstraint("slug", name="uq_agent_public_profile_slug"),
        )

        op.create_index(
            "ix_agent_public_profiles_slug",
            "agent_public_profiles",
            ["slug"],
        )
        op.create_index(
            "ix_agent_public_profiles_tenant_id",
            "agent_public_profiles",
            ["tenant_id"],
        )


def downgrade() -> None:
    op.drop_index("ix_agent_public_profiles_tenant_id", table_name="agent_public_profiles")
    op.drop_index("ix_agent_public_profiles_slug", table_name="agent_public_profiles")
    op.drop_table("agent_public_profiles")
