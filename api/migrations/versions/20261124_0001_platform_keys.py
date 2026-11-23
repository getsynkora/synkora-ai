"""Platform keys: tenant-level API keys that belong to no agent (agent_api_keys.agent_id may be null)."""

import sqlalchemy as sa
from alembic import op

revision = "20261124_0001"
down_revision = "20261123_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "agent_api_keys", "agent_id", existing_type=sa.dialects.postgresql.UUID(as_uuid=True), nullable=True
    )


def downgrade():
    # Platform keys have no agent and cannot exist with the column NOT NULL again
    op.execute("DELETE FROM agent_api_keys WHERE agent_id IS NULL")
    op.alter_column(
        "agent_api_keys", "agent_id", existing_type=sa.dialects.postgresql.UUID(as_uuid=True), nullable=False
    )
