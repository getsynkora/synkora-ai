"""add slack_bot_user_id to slack_bots

Revision ID: 20260824_0001
Revises: 20260817_0002
Create Date: 2026-08-24

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260824_0001"
down_revision = "20260817_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = bind.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='slack_bots' AND column_name='slack_bot_user_id'"
        )
    ).fetchone()
    if not existing:
        op.add_column(
            "slack_bots",
            sa.Column("slack_bot_user_id", sa.String(255), nullable=True),
        )


def downgrade() -> None:
    pass
