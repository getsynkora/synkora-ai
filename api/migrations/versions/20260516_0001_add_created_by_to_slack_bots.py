"""Add created_by to slack_bots

Revision ID: 20260516_0001
Revises: 20260512_0007
Create Date: 2026-05-16

Changes:
  - slack_bots.created_by: nullable FK to accounts.id (SET NULL on delete)
    Column was added to the SQLAlchemy model but the migration was missing.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '20260516_0001'
down_revision = '20260512_0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = bind.execute(
        sa.text("SELECT column_name FROM information_schema.columns WHERE table_name='slack_bots' AND column_name='created_by'")
    ).fetchone()
    if not existing:
        op.add_column(
            'slack_bots',
            sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('accounts.id', ondelete='SET NULL'), nullable=True),
        )


def downgrade() -> None:
    # column is owned by 20260408_0001 — no-op here
    pass
