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
    # Guarded with existence checks: an earlier, incomplete deploy attempt
    # created recall_webhook_receipts out-of-band (outside Alembic's tracked
    # history) before failing on an unrelated connection issue, leaving this
    # revision partially applied. Idempotent checks let `upgrade head` finish
    # cleanly from that state, and are harmless against a clean database too.
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "auth_version" not in {c["name"] for c in inspector.get_columns("accounts")}:
        op.add_column("accounts", sa.Column("auth_version", sa.Integer(), nullable=False, server_default="0"))

    if "recall_webhook_receipts" not in inspector.get_table_names():
        op.create_table(
            "recall_webhook_receipts",
            sa.Column("event_key", sa.String(64), primary_key=True),
            sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    existing_indexes = {ix["name"] for ix in sa.inspect(bind).get_indexes("recall_webhook_receipts")}
    if "ix_recall_webhook_receipts_processed_at" not in existing_indexes:
        op.create_index("ix_recall_webhook_receipts_processed_at", "recall_webhook_receipts", ["processed_at"])


def downgrade() -> None:
    op.drop_table("recall_webhook_receipts")
    op.drop_column("accounts", "auth_version")
