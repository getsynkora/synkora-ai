"""add allow_external_shared_channels to slack_bots

Revision ID: 20260813_0001
Revises: 95b0831fc354
Create Date: 2026-08-13

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260813_0001"
down_revision = "95b0831fc354"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = bind.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='slack_bots' AND column_name='allow_external_shared_channels'"
        )
    ).fetchone()
    if not existing:
        op.add_column(
            "slack_bots",
            sa.Column(
                "allow_external_shared_channels",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade() -> None:
    pass
