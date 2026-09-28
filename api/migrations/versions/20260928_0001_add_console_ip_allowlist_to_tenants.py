"""Add console_ip_allowlist column to tenants table."""

import sqlalchemy as sa
from alembic import op

revision = "20260928_0001"
down_revision = "20260911_0001"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("tenants")}
    if "console_ip_allowlist" not in cols:
        op.add_column(
            "tenants",
            sa.Column(
                "console_ip_allowlist",
                sa.JSON(),
                nullable=True,
                comment="List of IP addresses/CIDR ranges allowed to access the console. Null = all IPs allowed.",
            ),
        )


def downgrade():
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("tenants")}
    if "console_ip_allowlist" in cols:
        op.drop_column("tenants", "console_ip_allowlist")
