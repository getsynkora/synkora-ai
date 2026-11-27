"""Plans hidden from the pricing page but still settable through the API (subscription_plans.is_public)."""

import sqlalchemy as sa
from alembic import op

revision = "20261127_0001"
down_revision = "20261125_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "subscription_plans",
        sa.Column(
            "is_public",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
            comment="Shown on the pricing page; off for plans only set through the API by another billing system",
        ),
    )


def downgrade():
    op.drop_column("subscription_plans", "is_public")
