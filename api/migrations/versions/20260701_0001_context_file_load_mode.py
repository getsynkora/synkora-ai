"""add context file load_mode, description, drop extracted_text

Revision ID: 95b0831fc354
Revises: 20260627_0001
Create Date: 2026-07-01 06:41:13.264220+00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "95b0831fc354"
down_revision = "20260627_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add new columns
    op.add_column(
        "agent_context_files",
        sa.Column(
            "load_mode",
            sa.String(20),
            nullable=False,
            server_default="always",
            comment="always | on_demand",
        ),
    )
    op.add_column(
        "agent_context_files",
        sa.Column(
            "description",
            sa.String(500),
            nullable=True,
            comment="Short description shown to LLM in manifest",
        ),
    )

    # 2. Backfill description from first 200 chars of extracted_text
    op.execute(
        """
        UPDATE agent_context_files
        SET description = LEFT(extracted_text, 200)
        WHERE extracted_text IS NOT NULL AND description IS NULL
        """
    )

    # 3. Drop extracted_text
    op.drop_column("agent_context_files", "extracted_text")


def downgrade() -> None:
    op.add_column(
        "agent_context_files",
        sa.Column("extracted_text", sa.Text(), nullable=True),
    )
    op.drop_column("agent_context_files", "description")
    op.drop_column("agent_context_files", "load_mode")
