"""extend agent_pricing with session/time-based tiers and email subscription fields

Revision ID: 20260506_0005
Revises: 20260506_0004
Create Date: 2026-05-06

Extends the existing agent_pricing table with columns for session-based, daily,
and weekly credit allocations, trial message limits, and email subscription
pricing. Also adds SESSION/DAILY/WEEKLY/MONTHLY values to the pricingmodel
enum and links agent_subscriptions to agent_user_subscriptions via a new
paid_subscription_id foreign key.

Note: PostgreSQL does not support removing enum values; the four new
pricingmodel values cannot be rolled back in the downgrade step.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

# revision identifiers, used by Alembic.
revision = "20260506_0005"
down_revision = "20260506_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Extend the pricingmodel enum with time-based billing intervals.
    #    IF NOT EXISTS is used so re-running the migration is safe.
    # ------------------------------------------------------------------
    op.execute("ALTER TYPE pricingmodel ADD VALUE IF NOT EXISTS 'SESSION'")
    op.execute("ALTER TYPE pricingmodel ADD VALUE IF NOT EXISTS 'DAILY'")
    op.execute("ALTER TYPE pricingmodel ADD VALUE IF NOT EXISTS 'WEEKLY'")
    op.execute("ALTER TYPE pricingmodel ADD VALUE IF NOT EXISTS 'MONTHLY'")

    # ------------------------------------------------------------------
    # 2. Add new columns to agent_pricing.
    # ------------------------------------------------------------------
    op.add_column(
        "agent_pricing",
        sa.Column("session_credits", sa.Integer(), nullable=True),
    )
    op.add_column(
        "agent_pricing",
        sa.Column("daily_credits", sa.Integer(), nullable=True),
    )
    op.add_column(
        "agent_pricing",
        sa.Column("weekly_credits", sa.Integer(), nullable=True),
    )
    op.add_column(
        "agent_pricing",
        sa.Column(
            "trial_messages",
            sa.Integer(),
            nullable=True,
            server_default="0",
        ),
    )
    op.add_column(
        "agent_pricing",
        sa.Column(
            "email_subscription_model",
            sa.String(20),
            nullable=False,
            server_default="FREE",
        ),
    )
    op.add_column(
        "agent_pricing",
        sa.Column("email_subscription_price_cents", sa.Integer(), nullable=True),
    )
    op.add_column(
        "agent_pricing",
        sa.Column(
            "email_subscription_trial_emails",
            sa.Integer(),
            nullable=True,
            server_default="0",
        ),
    )

    # ------------------------------------------------------------------
    # 3. Link agent_subscriptions to agent_user_subscriptions so a
    #    platform subscription record knows which paid access it granted.
    # ------------------------------------------------------------------
    op.add_column(
        "agent_subscriptions",
        sa.Column("paid_subscription_id", pg.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_agent_subscription_paid_sub",
        "agent_subscriptions",
        "agent_user_subscriptions",
        ["paid_subscription_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # ------------------------------------------------------------------
    # Reverse in LIFO order.
    # Note: the four new pricingmodel enum values (SESSION, DAILY,
    # WEEKLY, MONTHLY) CANNOT be removed in PostgreSQL. This is a known
    # limitation — document and leave them in place.
    # ------------------------------------------------------------------
    op.drop_constraint(
        "fk_agent_subscription_paid_sub",
        "agent_subscriptions",
        type_="foreignkey",
    )
    op.drop_column("agent_subscriptions", "paid_subscription_id")

    op.drop_column("agent_pricing", "email_subscription_trial_emails")
    op.drop_column("agent_pricing", "email_subscription_price_cents")
    op.drop_column("agent_pricing", "email_subscription_model")
    op.drop_column("agent_pricing", "trial_messages")
    op.drop_column("agent_pricing", "weekly_credits")
    op.drop_column("agent_pricing", "daily_credits")
    op.drop_column("agent_pricing", "session_credits")
