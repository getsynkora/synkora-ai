"""add slack_bot_id to data_sources

Revision ID: 20260817_0001
Revises: 20260813_0002
Create Date: 2026-08-17

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260817_0001"
down_revision = "20260813_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = bind.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='data_sources' AND column_name='slack_bot_id'"
        )
    ).fetchone()
    if not existing:
        op.add_column(
            "data_sources",
            sa.Column(
                "slack_bot_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("slack_bots.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )


def downgrade() -> None:
    pass
