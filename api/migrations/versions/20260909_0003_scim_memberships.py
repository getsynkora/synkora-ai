"""Keep SCIM lifecycle and profile changes tenant-local."""

import sqlalchemy as sa
from alembic import op

revision = "20260909_0003"
down_revision = "20260909_0002"
branch_labels = None
depends_on = None


def upgrade():
    # Guarded with existence checks: an earlier, incomplete deploy attempt
    # created this table out-of-band (outside Alembic's tracked history)
    # before failing on an unrelated connection issue, leaving this revision
    # partially applied — the table and its unique constraint exist, but not
    # the check constraint or index. Idempotent checks let `upgrade head`
    # finish cleanly from that state, and are harmless against a clean
    # database too.
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "scim_memberships" not in inspector.get_table_names():
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
    else:
        # src/core/database.py's naming convention ("ck":
        # "%(table_name)s_%(constraint_name)s_check") rewrites even an
        # explicitly-named CheckConstraint, so the name actually landing in
        # Postgres from the op.create_table() branch above is
        # "scim_memberships_ck_scim_membership_role_check", not the literal
        # "ck_scim_membership_role" — confirmed against both a fresh local
        # migration run and production's already-partially-applied table.
        existing_constraints = {c["name"] for c in inspector.get_check_constraints("scim_memberships")}
        if "scim_memberships_ck_scim_membership_role_check" not in existing_constraints:
            op.create_check_constraint(
                "ck_scim_membership_role", "scim_memberships", "role IN ('NORMAL', 'EDITOR', 'ADMIN', 'OWNER')"
            )

    existing_indexes = {ix["name"] for ix in sa.inspect(bind).get_indexes("scim_memberships")}
    if "ix_scim_memberships_tenant_id" not in existing_indexes:
        op.create_index("ix_scim_memberships_tenant_id", "scim_memberships", ["tenant_id"])


def downgrade():
    op.drop_table("scim_memberships")
