"""Add external_user_email and external_user_phone to conversations.

Revision ID: 20260602_0003
Revises: 20260602_0002
Create Date: 2026-06-02
"""

from alembic import op
import sqlalchemy as sa

revision = "20260602_0003"
down_revision = "20260602_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("external_user_email", sa.String(255), nullable=True))
    op.add_column("conversations", sa.Column("external_user_phone", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("conversations", "external_user_phone")
    op.drop_column("conversations", "external_user_email")
