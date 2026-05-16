"""add external_user_id to widget_push_subscriptions for per-user topic targeting

Revision ID: 20260512_0001
Revises: 20260511_0001
Create Date: 2026-05-12
"""

from alembic import op
import sqlalchemy as sa

revision = "20260512_0001"
down_revision = "20260511_0001"
branch_labels = None
depends_on = None


def _column_exists(conn, table, column):
    result = conn.execute(
        sa.text("SELECT 1 FROM information_schema.columns WHERE table_name=:t AND column_name=:c"),
        {"t": table, "c": column},
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

    if not _column_exists(conn, "widget_push_subscriptions", "external_user_id"):
        op.add_column(
            "widget_push_subscriptions",
            sa.Column("external_user_id", sa.String(255), nullable=True),
        )

    if not _index_exists(conn, "ix_push_sub_widget_user"):
        op.create_index(
            "ix_push_sub_widget_user",
            "widget_push_subscriptions",
            ["widget_id", "external_user_id"],
        )


def downgrade() -> None:
    op.drop_index("ix_push_sub_widget_user", table_name="widget_push_subscriptions")
    op.drop_column("widget_push_subscriptions", "external_user_id")
