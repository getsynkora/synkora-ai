"""add agent_user_subscriptions table for paid agent access

Revision ID: 20260506_0003
Revises: 20260506_0002
Create Date: 2026-05-06

Creates the agent_user_subscriptions table that tracks paid subscriptions
(Stripe or credit-based) granting users access to premium agents. Supports
both authenticated tenant subscribers and unauthenticated guest subscribers
identified by a hashed token.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

# revision identifiers, used by Alembic.
revision = "20260506_0003"
down_revision = "20260506_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # Create enum type for subscription status.
    subscription_access_status = pg.ENUM(
        "ACTIVE",
        "CANCELLED",
        "EXPIRED",
        name="subscriptionaccessstatus",
    )
    subscription_access_status.create(bind, checkfirst=True)

    if not bind.dialect.has_table(bind, "agent_user_subscriptions"):
        op.create_table(
            "agent_user_subscriptions",
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
            sa.Column("agent_id", pg.UUID(as_uuid=True), nullable=False),
            sa.Column("agent_pricing_id", pg.UUID(as_uuid=True), nullable=False),
            sa.Column("subscriber_tenant_id", pg.UUID(as_uuid=True), nullable=True),
            sa.Column("guest_email", sa.String(255), nullable=True),
            sa.Column("guest_token_hash", sa.String(64), nullable=True),
            sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
            sa.Column("stripe_customer_id", sa.String(255), nullable=True),
            sa.Column("pricing_tier", sa.String(30), nullable=False),
            sa.Column("amount_cents", sa.Integer(), nullable=False),
            sa.Column(
                "status",
                pg.ENUM(
                    "ACTIVE",
                    "CANCELLED",
                    "EXPIRED",
                    name="subscriptionaccessstatus",
                    create_type=False,
                ),
                nullable=False,
                server_default="ACTIVE",
            ),
            sa.Column(
                "started_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("NOW()"),
            ),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["agent_pricing_id"], ["agent_pricing.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["subscriber_tenant_id"], ["tenants.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "guest_token_hash", name="uq_agent_user_sub_guest_token"
            ),
        )

        op.create_index(
            "ix_agent_user_sub_agent_tenant",
            "agent_user_subscriptions",
            ["agent_id", "subscriber_tenant_id"],
        )
        op.create_index(
            "ix_agent_user_sub_tenant_status",
            "agent_user_subscriptions",
            ["subscriber_tenant_id", "status"],
        )
        op.create_index(
            "ix_agent_user_sub_agent_pricing_id",
            "agent_user_subscriptions",
            ["agent_pricing_id"],
        )


def downgrade() -> None:
    op.drop_index("ix_agent_user_sub_agent_pricing_id", table_name="agent_user_subscriptions")
    op.drop_index("ix_agent_user_sub_tenant_status", table_name="agent_user_subscriptions")
    op.drop_index("ix_agent_user_sub_agent_tenant", table_name="agent_user_subscriptions")
    op.drop_table("agent_user_subscriptions")

    subscription_access_status = pg.ENUM(
        "ACTIVE",
        "CANCELLED",
        "EXPIRED",
        name="subscriptionaccessstatus",
    )
    subscription_access_status.drop(op.get_bind(), checkfirst=True)
