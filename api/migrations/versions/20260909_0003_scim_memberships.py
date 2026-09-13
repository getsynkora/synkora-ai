"""Keep SCIM lifecycle and profile changes tenant-local."""

import sqlalchemy as sa
from alembic import op

revision = "20260909_0003"
down_revision = "20260909_0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "scim_memberships",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("membership_attributes", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "account_id", name="uq_scim_membership"),
        sa.CheckConstraint("role IN ('NORMAL', 'EDITOR', 'ADMIN', 'OWNER')", name="ck_scim_membership_role"),
    )
    op.create_index("ix_scim_memberships_tenant_id", "scim_memberships", ["tenant_id"])


def downgrade():
    op.drop_table("scim_memberships")
