"""Add unique constraint on documents(knowledge_base_id, external_id)

Revision ID: 20260606_0001
Revises: 20260602_0003_add_external_user_email_phone
Create Date: 2026-06-06
"""

from alembic import op

revision = "20260606_0001"
down_revision = "20260602_0003_add_external_user_email_phone"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove any duplicate rows before adding the constraint, keeping the most
    # recently updated record for each (knowledge_base_id, external_id) pair.
    op.execute("""
        DELETE FROM documents
        WHERE id NOT IN (
            SELECT DISTINCT ON (knowledge_base_id, external_id) id
            FROM documents
            WHERE knowledge_base_id IS NOT NULL
              AND external_id IS NOT NULL
            ORDER BY knowledge_base_id, external_id, updated_at DESC NULLS LAST
        )
        AND knowledge_base_id IS NOT NULL
        AND external_id IS NOT NULL
    """)

    op.create_index(
        "uq_documents_kb_external_id",
        "documents",
        ["knowledge_base_id", "external_id"],
        unique=True,
        postgresql_where="knowledge_base_id IS NOT NULL AND external_id IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_index("uq_documents_kb_external_id", table_name="documents")
