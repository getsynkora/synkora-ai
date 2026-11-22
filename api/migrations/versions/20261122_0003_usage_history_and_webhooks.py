"""Agent id on usage events (per-agent usage history), announced-threshold state and outbound webhook endpoints."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261122_0003"
down_revision = "20261122_0002"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    usage_columns = {c["name"] for c in inspector.get_columns("quota_usage")}
    if "notified_percent" not in usage_columns:
        op.add_column("quota_usage", sa.Column("notified_percent", sa.Integer(), nullable=False, server_default="0"))

    event_columns = {c["name"] for c in inspector.get_columns("quota_usage_events")}
    if "agent_id" not in event_columns:
        op.add_column("quota_usage_events", sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(
            "fk_quota_usage_events_agent_id", "quota_usage_events", "agents", ["agent_id"], ["id"], ondelete="SET NULL"
        )
    existing_indexes = {i["name"] for i in inspector.get_indexes("quota_usage_events")}
    if "ix_quota_usage_events_tenant_created" not in existing_indexes:
        op.create_index("ix_quota_usage_events_tenant_created", "quota_usage_events", ["tenant_id", "created_at"])

    if "webhook_endpoints" not in inspector.get_table_names():
        op.create_table(
            "webhook_endpoints",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("url", sa.String(length=2048), nullable=False),
            sa.Column("description", sa.String(length=255), nullable=True),
            sa.Column("secret", sa.Text(), nullable=False),
            sa.Column("events", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_webhook_endpoints_tenant_id", "webhook_endpoints", ["tenant_id"])


def downgrade():
    op.drop_column("quota_usage", "notified_percent")
    op.drop_table("webhook_endpoints")
    op.drop_index("ix_quota_usage_events_tenant_created", table_name="quota_usage_events")
    op.drop_constraint("fk_quota_usage_events_agent_id", "quota_usage_events", type_="foreignkey")
    op.drop_column("quota_usage_events", "agent_id")
