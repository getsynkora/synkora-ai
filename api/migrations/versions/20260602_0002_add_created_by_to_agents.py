"""Add created_by to agents table.

Revision ID: 20260602_0002
Revises: 20260602_0001
Create Date: 2026-06-02
"""

from alembic import op
import sqlalchemy as sa

revision = "20260602_0002"
down_revision = "20260602_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column(
            "created_by",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="SET NULL"),
            nullable=True,
            comment="Account that created this agent",
        ),
    )
    op.create_index("ix_agents_created_by", "agents", ["created_by"])


def downgrade() -> None:
    op.drop_index("ix_agents_created_by", table_name="agents")
    op.drop_column("agents", "created_by")
