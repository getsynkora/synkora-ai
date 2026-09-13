"""Durable reset revocation and transactional Recall event receipts.

Revision ID: 20260909_0001
Revises: 20260824_0001
"""

import sqlalchemy as sa
from alembic import op

revision = "20260909_0001"
down_revision = "20260824_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("auth_version", sa.Integer(), nullable=False, server_default="0"))
    op.create_table(
        "recall_webhook_receipts",
        sa.Column("event_key", sa.String(64), primary_key=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_recall_webhook_receipts_processed_at", "recall_webhook_receipts", ["processed_at"])


def downgrade() -> None:
    op.drop_table("recall_webhook_receipts")
    op.drop_column("accounts", "auth_version")
