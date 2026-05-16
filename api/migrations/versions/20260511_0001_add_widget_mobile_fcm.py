"""add widget mobile_allowed, fcm_server_key, widget_push_subscriptions

Revision ID: 20260511_0001
Revises: 20260510_0004
Create Date: 2026-05-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "20260511_0001"
down_revision = "20260510_0004"
branch_labels = None
depends_on = None


def _column_exists(conn, table, column):
    result = conn.execute(
        sa.text("SELECT 1 FROM information_schema.columns WHERE table_name=:t AND column_name=:c"),
        {"t": table, "c": column},
    )
    return result.fetchone() is not None


def _table_exists(conn, table):
    result = conn.execute(
        sa.text("SELECT 1 FROM information_schema.tables WHERE table_name=:t"),
        {"t": table},
    )
    return result.fetchone() is not None


def _index_exists(conn, index):
    result = conn.execute(
        sa.text("SELECT 1 FROM pg_indexes WHERE indexname=:i"),
        {"i": index},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    conn = op.get_bind()

    # Add mobile_allowed to agent_widgets (idempotent)
    if not _column_exists(conn, "agent_widgets", "mobile_allowed"):
        op.add_column(
            "agent_widgets",
            sa.Column("mobile_allowed", sa.Boolean(), nullable=False, server_default="false"),
        )

    # Add fcm_server_key to agent_widgets (idempotent)
    if not _column_exists(conn, "agent_widgets", "fcm_server_key"):
        op.add_column(
            "agent_widgets",
            sa.Column("fcm_server_key", sa.Text(), nullable=True),
        )

    # Create widget_push_subscriptions table (idempotent)
    if not _table_exists(conn, "widget_push_subscriptions"):
        op.create_table(
            "widget_push_subscriptions",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("widget_id", UUID(as_uuid=True), nullable=False),
            sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
            sa.Column("conversation_id", UUID(as_uuid=True), nullable=True),
            sa.Column("fcm_token", sa.Text(), nullable=False),
            sa.Column("platform", sa.String(20), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )

    if not _index_exists(conn, "ix_push_sub_widget_token"):
        op.create_index("ix_push_sub_widget_token", "widget_push_subscriptions", ["widget_id", "fcm_token"])

    if not _index_exists(conn, "ix_push_sub_widget_conv"):
        op.create_index("ix_push_sub_widget_conv", "widget_push_subscriptions", ["widget_id", "conversation_id"])


def downgrade() -> None:
    op.drop_index("ix_push_sub_widget_conv", table_name="widget_push_subscriptions")
    op.drop_index("ix_push_sub_widget_token", table_name="widget_push_subscriptions")
    op.drop_table("widget_push_subscriptions")
    op.drop_column("agent_widgets", "fcm_server_key")
    op.drop_column("agent_widgets", "mobile_allowed")
