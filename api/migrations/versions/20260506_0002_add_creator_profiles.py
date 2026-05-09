"""add creator_profiles table for marketplace creator pages

Revision ID: 20260506_0002
Revises: 20260506_0001
Create Date: 2026-05-06

Creates the creator_profiles table that stores public-facing profile information
for agent creators, including social links, Stripe connect details, and earnings
tracking.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

# revision identifiers, used by Alembic.
revision = "20260506_0002"
down_revision = "20260506_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    if not bind.dialect.has_table(bind, "creator_profiles"):
        op.create_table(
            "creator_profiles",
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
                "tenant_id",
                pg.UUID(as_uuid=True),
                nullable=False,
            ),
            sa.Column("username", sa.String(50), nullable=False),
            sa.Column("display_name", sa.String(255), nullable=True),
            sa.Column("bio", sa.Text(), nullable=True),
            sa.Column("avatar_url", sa.String(500), nullable=True),
            sa.Column("banner_image_url", sa.String(500), nullable=True),
            sa.Column("website_url", sa.String(500), nullable=True),
            sa.Column("twitter_url", sa.String(500), nullable=True),
            sa.Column("linkedin_url", sa.String(500), nullable=True),
            sa.Column("github_url", sa.String(500), nullable=True),
            sa.Column("stripe_account_id", sa.String(255), nullable=True),
            sa.Column(
                "stripe_onboarding_complete",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column(
                "is_public",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
            sa.Column(
                "total_earnings_credits",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", name="uq_creator_profile_tenant"),
            sa.UniqueConstraint("username", name="uq_creator_profile_username"),
        )

        op.create_index(
            "ix_creator_profiles_tenant_id",
            "creator_profiles",
            ["tenant_id"],
        )
        op.create_index(
            "ix_creator_profiles_username",
            "creator_profiles",
            ["username"],
        )


def downgrade() -> None:
    op.drop_index("ix_creator_profiles_username", table_name="creator_profiles")
    op.drop_index("ix_creator_profiles_tenant_id", table_name="creator_profiles")
    op.drop_table("creator_profiles")
