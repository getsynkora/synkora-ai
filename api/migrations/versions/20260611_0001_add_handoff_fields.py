"""Add handoff fields to conversations and update agent_approval_requests

Revision ID: 20260611_0001
Revises: 20260610_0001
Create Date: 2026-06-11
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260611_0001"
down_revision = "20260610_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add handoff columns to conversations
    op.add_column("conversations", sa.Column("handoff_status", sa.String(20), nullable=False, server_default="none"))
    op.add_column("conversations", sa.Column("handoff_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("conversations", sa.Column("handoff_summary", sa.Text(), nullable=True))

    # Make task_id nullable on agent_approval_requests
    op.alter_column(
        "agent_approval_requests",
        "task_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )

    # Add conversation_id column to agent_approval_requests
    op.add_column(
        "agent_approval_requests",
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # Add composite index for the new conversation_id + status lookup
    op.create_index(
        "ix_approval_conversation_status",
        "agent_approval_requests",
        ["conversation_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_approval_conversation_status", table_name="agent_approval_requests")
    op.drop_column("agent_approval_requests", "conversation_id")
    op.alter_column(
        "agent_approval_requests",
        "task_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    op.drop_column("conversations", "handoff_summary")
    op.drop_column("conversations", "handoff_at")
    op.drop_column("conversations", "handoff_status")
