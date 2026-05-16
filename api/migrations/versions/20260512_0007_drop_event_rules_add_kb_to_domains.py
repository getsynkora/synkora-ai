"""Drop brain_event_rules, add knowledge_base_id to brain_domains

Revision ID: 20260512_0007
Revises: 20260512_0006
Create Date: 2026-05-12

Changes:
  - Drop brain_event_rules table (feature removed — agents handle events natively)
  - brain_domains.knowledge_base_id: FK to knowledge_bases — links a domain to the KB
    that IS its storage layer. Query routing now resolves domain → KB → data sources.
"""

from alembic import op

revision = "20260512_0007"
down_revision = "20260512_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop event rules (feature removed)
    op.execute("DROP TABLE IF EXISTS brain_event_rules CASCADE")

    # Link each domain to its Knowledge Base
    op.execute("""
        ALTER TABLE brain_domains
            ADD COLUMN IF NOT EXISTS knowledge_base_id INTEGER
                REFERENCES knowledge_bases(id) ON DELETE SET NULL
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_brain_domains_knowledge_base_id "
        "ON brain_domains (knowledge_base_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_brain_domains_knowledge_base_id")
    op.execute("ALTER TABLE brain_domains DROP COLUMN IF EXISTS knowledge_base_id")
    # Note: brain_event_rules is not restored in downgrade — use 20260512_0006 directly if needed
