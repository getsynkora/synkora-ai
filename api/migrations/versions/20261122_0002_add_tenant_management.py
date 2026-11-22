"""Let a tenant create and manage customer tenants through the API."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261122_0002"
down_revision = "20261122_0001"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {c["name"] for c in sa.inspect(bind).get_columns("tenants")}

    if "can_manage_tenants" not in columns:
        op.add_column(
            "tenants",
            sa.Column("can_manage_tenants", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if "managed_by_tenant_id" not in columns:
        op.add_column("tenants", sa.Column("managed_by_tenant_id", postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(
            "fk_tenants_managed_by_tenant_id", "tenants", "tenants", ["managed_by_tenant_id"], ["id"], ondelete="SET NULL"
        )
        op.create_index("ix_tenants_managed_by_tenant_id", "tenants", ["managed_by_tenant_id"])
    if "external_ref" not in columns:
        op.add_column("tenants", sa.Column("external_ref", sa.String(length=255), nullable=True))
        op.create_index("ix_tenants_external_ref", "tenants", ["external_ref"])
        op.create_unique_constraint(
            "uq_tenant_managed_external_ref", "tenants", ["managed_by_tenant_id", "external_ref"]
        )


def downgrade():
    op.drop_constraint("uq_tenant_managed_external_ref", "tenants", type_="unique")
    op.drop_index("ix_tenants_external_ref", table_name="tenants")
    op.drop_index("ix_tenants_managed_by_tenant_id", table_name="tenants")
    op.drop_constraint("fk_tenants_managed_by_tenant_id", "tenants", type_="foreignkey")
    op.drop_column("tenants", "external_ref")
    op.drop_column("tenants", "managed_by_tenant_id")
    op.drop_column("tenants", "can_manage_tenants")
