"""add ingestion_mode to knowledge_bases

Revision ID: 20260817_0002
Revises: 20260817_0001
Create Date: 2026-08-17

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260817_0002"
down_revision = "20260817_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    existing_type = bind.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = 'ingestionmode'")
    ).fetchone()
    if not existing_type:
        op.execute("CREATE TYPE ingestionmode AS ENUM ('standard', 'advanced')")

    existing_column = bind.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='knowledge_bases' AND column_name='ingestion_mode'"
        )
    ).fetchone()
    if not existing_column:
        op.add_column(
            "knowledge_bases",
            sa.Column(
                "ingestion_mode",
                sa.Enum("standard", "advanced", name="ingestionmode"),
                nullable=False,
                server_default="standard",
            ),
        )


def downgrade() -> None:
    pass
