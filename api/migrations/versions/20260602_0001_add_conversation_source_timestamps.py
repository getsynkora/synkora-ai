"""Add source, closed_at, last_activity_at to conversations

Revision ID: 20260602_0001
Revises: 20260522_0002
Create Date: 2026-06-02

Adds three columns to conversations:
  source          — channel that created the conversation (web/flutter/widget/whatsapp/slack/chrome)
  closed_at       — set when session is manually or automatically closed
  last_activity_at — updated on every message; used by Flutter inactivity timer
"""

import sqlalchemy as sa
from alembic import op

revision = "20260602_0001"
down_revision = "20260522_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("source", sa.String(20), nullable=True, server_default="web"),
    )
    op.add_column(
        "conversations",
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "conversations",
        sa.Column(
            "last_activity_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_conversations_source", "conversations", ["source"])


def downgrade() -> None:
    op.drop_index("ix_conversations_source", table_name="conversations")
    op.drop_column("conversations", "last_activity_at")
    op.drop_column("conversations", "closed_at")
    op.drop_column("conversations", "source")
