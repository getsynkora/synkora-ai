"""Add performance indexes for conversations and activity_logs."""

from alembic import op

revision = "20260911_0001"
down_revision = "20260909_0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_conversations_session_id", "conversations", ["session_id"])
    op.create_index(
        "ix_conversations_agent_status_updated",
        "conversations",
        ["agent_id", "status", "updated_at"],
    )


def downgrade():
    op.drop_index("ix_conversations_agent_status_updated", table_name="conversations")
    op.drop_index("ix_conversations_session_id", table_name="conversations")
