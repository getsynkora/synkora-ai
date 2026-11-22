"""Add generic quota pools: plan quotas, agent pool key, usage tables."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261121_0001"
down_revision = "20260928_0002"
branch_labels = None
depends_on = None


def _columns(bind, table):
    return {c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade():
    bind = op.get_bind()

    if "quota_pools" not in _columns(bind, "subscription_plans"):
        op.add_column("subscription_plans", sa.Column("quota_pools", postgresql.JSONB(), nullable=True))
    if "quota_pool" not in _columns(bind, "agents"):
        op.add_column("agents", sa.Column("quota_pool", sa.String(length=64), nullable=True))

    tables = sa.inspect(bind).get_table_names()
    if "quota_usage" not in tables:
        op.create_table(
            "quota_usage",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("pool_key", sa.String(length=64), nullable=False),
            sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used", sa.Integer(), nullable=False, server_default="0"),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "pool_key", "period_start", name="uq_quota_usage_period"),
        )
        op.create_index("ix_quota_usage_tenant_id", "quota_usage", ["tenant_id"])
    if "quota_usage_events" not in tables:
        op.create_table(
            "quota_usage_events",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("idempotency_key", sa.String(length=255), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("pool_key", sa.String(length=64), nullable=False),
            sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
            sa.Column("amount", sa.Integer(), nullable=False, server_default="1"),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("idempotency_key"),
        )
        op.create_index("ix_quota_usage_events_tenant_id", "quota_usage_events", ["tenant_id"])


def downgrade():
    op.drop_table("quota_usage_events")
    op.drop_table("quota_usage")
    op.drop_column("agents", "quota_pool")
    op.drop_column("subscription_plans", "quota_pools")
