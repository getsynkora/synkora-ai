"""Keep personal OAuth destinations with their tokens.

Revision ID: 20260909_0002
Revises: 20260909_0001
"""

import sqlalchemy as sa
from alembic import op

revision = "20260909_0002"
down_revision = "20260909_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing shared settings cannot safely be attributed to a personal token.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "provider_config" not in {c["name"] for c in inspector.get_columns("user_oauth_tokens")}:
        op.add_column("user_oauth_tokens", sa.Column("provider_config", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("user_oauth_tokens", "provider_config")
