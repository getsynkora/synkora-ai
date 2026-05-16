"""Add brain_event_rules table

Revision ID: 20260512_0006
Revises: 20260512_0005
Create Date: 2026-05-12
"""

from alembic import op

revision = "20260512_0006"
down_revision = "20260512_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS brain_event_rules (
            id UUID DEFAULT gen_random_uuid() NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            domain_id UUID REFERENCES brain_domains(id) ON DELETE SET NULL,
            name VARCHAR(200) NOT NULL,
            event_type VARCHAR(120) NOT NULL,
            trigger_config JSONB NOT NULL DEFAULT '{}',
            delivery_config JSONB NOT NULL DEFAULT '[]',
            is_active BOOLEAN NOT NULL DEFAULT true,
            CONSTRAINT brain_event_rules_pkey PRIMARY KEY (id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_brain_event_rules_tenant_id ON brain_event_rules (tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_brain_event_rules_domain_id ON brain_event_rules (domain_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_brain_event_rules_event_type ON brain_event_rules (event_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_brain_event_rules_is_active ON brain_event_rules (is_active)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_brain_event_rules_is_active")
    op.execute("DROP INDEX IF EXISTS ix_brain_event_rules_event_type")
    op.execute("DROP INDEX IF EXISTS ix_brain_event_rules_domain_id")
    op.execute("DROP INDEX IF EXISTS ix_brain_event_rules_tenant_id")
    op.execute("DROP TABLE IF EXISTS brain_event_rules")
