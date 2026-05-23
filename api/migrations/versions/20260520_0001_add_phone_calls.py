"""Add phone calls tables and phone_config to agents

Revision ID: 20260520_0001
Revises: 20260516_0001
Create Date: 2026-05-20

Changes:
  - Create phone_numbers table
  - Create phone_calls table
  - Create phone_provider_credentials table
  - Add phone_config JSON column to agents table
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSON, UUID

revision = '20260520_0001'
down_revision = '20260516_0001'
branch_labels = None
depends_on = None


def _table_exists(bind, table_name: str) -> bool:
    return bool(
        bind.execute(
            sa.text("SELECT 1 FROM information_schema.tables WHERE table_name=:t"),
            {"t": table_name},
        ).fetchone()
    )


def _index_exists(bind, index_name: str) -> bool:
    return bool(
        bind.execute(
            sa.text("SELECT 1 FROM pg_indexes WHERE indexname=:i"),
            {"i": index_name},
        ).fetchone()
    )


def upgrade() -> None:
    bind = op.get_bind()

    # --- phone_provider_credentials ---
    if not _table_exists(bind, 'phone_provider_credentials'):
        op.create_table(
            'phone_provider_credentials',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
            sa.Column('provider', sa.String(50), nullable=False),
            sa.Column('credentials_encrypted', sa.Text, nullable=False),
            sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        )
    if not _index_exists(bind, 'ix_phone_provider_credentials_tenant_id'):
        op.create_index('ix_phone_provider_credentials_tenant_id', 'phone_provider_credentials', ['tenant_id'])

    # --- phone_numbers ---
    if not _table_exists(bind, 'phone_numbers'):
        op.create_table(
            'phone_numbers',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
            sa.Column('agent_id', UUID(as_uuid=True), sa.ForeignKey('agents.id', ondelete='CASCADE'), nullable=False),
            sa.Column('provider', sa.String(50), nullable=False, server_default='vapi'),
            sa.Column('phone_number', sa.String(20), nullable=False),
            sa.Column('is_provisioned', sa.Boolean, nullable=False, server_default='false'),
            sa.Column('provider_number_id', sa.String(255), nullable=True),
            sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        )
    if not _index_exists(bind, 'ix_phone_numbers_tenant_id_agent_id'):
        op.create_index('ix_phone_numbers_tenant_id_agent_id', 'phone_numbers', ['tenant_id', 'agent_id'])

    # --- phone_calls ---
    if not _table_exists(bind, 'phone_calls'):
        op.create_table(
            'phone_calls',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
            sa.Column('agent_id', UUID(as_uuid=True), sa.ForeignKey('agents.id', ondelete='CASCADE'), nullable=False),
            sa.Column('phone_number_id', UUID(as_uuid=True), sa.ForeignKey('phone_numbers.id', ondelete='SET NULL'), nullable=True),
            sa.Column('conversation_id', UUID(as_uuid=True), sa.ForeignKey('conversations.id', ondelete='SET NULL'), nullable=True),
            sa.Column('provider', sa.String(50), nullable=False, server_default='vapi'),
            sa.Column('provider_call_id', sa.String(255), nullable=False),
            sa.Column('caller_number', sa.String(20), nullable=True),
            sa.Column('status', sa.String(20), nullable=False, server_default='ringing'),
            sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('answered_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('duration_seconds', sa.Integer, nullable=True),
            sa.Column('recording_url', sa.Text, nullable=True),
            sa.Column('cost_cents', sa.Integer, nullable=True),
            sa.Column('call_metadata', JSON, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        )
    if not _index_exists(bind, 'ix_phone_calls_tenant_agent_started'):
        op.create_index('ix_phone_calls_tenant_agent_started', 'phone_calls', ['tenant_id', 'agent_id', 'started_at'])
    if not _index_exists(bind, 'ix_phone_calls_provider_call_id'):
        op.create_index('ix_phone_calls_provider_call_id', 'phone_calls', ['provider_call_id'])

    # --- phone_config on agents ---
    existing = bind.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='agents' AND column_name='phone_config'"
        )
    ).fetchone()
    if not existing:
        op.add_column('agents', sa.Column('phone_config', JSON, nullable=True))


def downgrade() -> None:
    op.drop_table('phone_calls')
    op.drop_table('phone_numbers')
    op.drop_table('phone_provider_credentials')
    bind = op.get_bind()
    existing = bind.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='agents' AND column_name='phone_config'"
        )
    ).fetchone()
    if existing:
        op.drop_column('agents', 'phone_config')
