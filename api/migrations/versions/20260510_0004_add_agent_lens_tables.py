"""add agent_lens_alerts table (tool call logs moved to Elasticsearch)

Revision ID: 20260510_0004
Revises: 20260510_0003
Create Date: 2026-05-10
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "20260510_0004"
down_revision = "20260510_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    if not bind.dialect.has_table(bind, "agent_lens_alerts"):
        op.create_table(
            "agent_lens_alerts",
            sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False),
            sa.Column("agent_id", pg.UUID(as_uuid=True), nullable=False, index=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("metric", sa.String(50), nullable=False),
            sa.Column("condition", sa.String(10), nullable=False),
            sa.Column("threshold", sa.Numeric(14, 4), nullable=False),
            sa.Column("window_minutes", sa.Integer, nullable=False, server_default="60"),
            sa.Column("notify_method", sa.String(20), nullable=False, server_default="email"),
            sa.Column("notify_config", pg.JSONB, nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
            sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index(
            "ix_lens_alert_tenant_agent",
            "agent_lens_alerts",
            ["tenant_id", "agent_id"],
        )


def downgrade() -> None:
    op.drop_index("ix_lens_alert_tenant_agent", table_name="agent_lens_alerts")
    op.drop_table("agent_lens_alerts")
