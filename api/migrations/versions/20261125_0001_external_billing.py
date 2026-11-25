"""Tenants whose plan is paid for in another system and set through the API (tenants.external_billing)."""

import sqlalchemy as sa
from alembic import op

revision = "20261125_0001"
down_revision = "20261124_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "tenants",
        sa.Column(
            "external_billing",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment="Plan is paid for outside Synkora and set through the API (enabled by a platform operator)",
        ),
    )


def downgrade():
    op.drop_column("tenants", "external_billing")
