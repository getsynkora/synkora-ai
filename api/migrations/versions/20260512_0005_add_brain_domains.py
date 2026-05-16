"""Add brain_domains table and brain_domain_id/custom_connector_config to data_sources

Revision ID: 20260512_0005
Revises: 20260512_0001
Create Date: 2026-05-12

Changes:
  - brain_domains table: tenant-configurable Company Brain domains
  - data_sources.brain_domain_id: optional FK to brain_domains
  - data_sources.custom_connector_config: JSON for CUSTOM type connectors
"""

from alembic import op
import sqlalchemy as sa

revision = "20260512_0005"
down_revision = "20260512_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- brain_domains (idempotent) ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS brain_domains (
            id UUID DEFAULT gen_random_uuid() NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR(120) NOT NULL,
            slug VARCHAR(80) NOT NULL,
            description TEXT,
            rerank_weight FLOAT NOT NULL DEFAULT 1.0,
            is_active BOOLEAN NOT NULL DEFAULT true,
            CONSTRAINT brain_domains_pkey PRIMARY KEY (id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_brain_domains_tenant_id ON brain_domains (tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_brain_domains_slug ON brain_domains (slug)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_brain_domains_is_active ON brain_domains (is_active)")
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_brain_domain_tenant_slug'
            ) THEN
                ALTER TABLE brain_domains
                    ADD CONSTRAINT uq_brain_domain_tenant_slug UNIQUE (tenant_id, slug);
            END IF;
        END$$
    """)

    # --- data_sources additions (idempotent) ---
    op.execute("""
        ALTER TABLE data_sources
            ADD COLUMN IF NOT EXISTS brain_domain_id UUID
                REFERENCES brain_domains(id) ON DELETE SET NULL
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_data_sources_brain_domain_id ON data_sources (brain_domain_id)")
    op.execute("""
        ALTER TABLE data_sources
            ADD COLUMN IF NOT EXISTS custom_connector_config JSONB NOT NULL DEFAULT '{}'
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE data_sources DROP COLUMN IF EXISTS custom_connector_config")
    op.execute("DROP INDEX IF EXISTS ix_data_sources_brain_domain_id")
    op.execute("ALTER TABLE data_sources DROP COLUMN IF EXISTS brain_domain_id")
    op.execute("DROP TABLE IF EXISTS brain_domains")
