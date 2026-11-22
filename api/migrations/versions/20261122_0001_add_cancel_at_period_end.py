"""Add tenant_subscriptions.cancel_at_period_end.

The flag was set on the model but never stored, so a cancel-at-period-end request was
forgotten. Existing rows default to false: earlier requests were never recorded.
"""

import sqlalchemy as sa
from alembic import op

revision = "20261122_0001"
down_revision = "20261121_0001"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {c["name"] for c in sa.inspect(bind).get_columns("tenant_subscriptions")}
    if "cancel_at_period_end" not in columns:
        op.add_column(
            "tenant_subscriptions",
            sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade():
    op.drop_column("tenant_subscriptions", "cancel_at_period_end")
