"""Cooldown timestamps on webhook endpoints (test pings and switching back on)."""

import sqlalchemy as sa
from alembic import op

revision = "20261123_0001"
down_revision = "20261122_0003"
branch_labels = None
depends_on = None


def upgrade():
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("webhook_endpoints")}
    for name in ("last_tested_at", "last_reactivated_at"):
        if name not in columns:
            op.add_column("webhook_endpoints", sa.Column(name, sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("webhook_endpoints", "last_reactivated_at")
    op.drop_column("webhook_endpoints", "last_tested_at")
