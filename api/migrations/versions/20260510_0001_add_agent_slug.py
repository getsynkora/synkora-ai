"""add agent slug

Revision ID: 20260510_0001
Revises:
Create Date: 2026-05-10 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260510_0001"
down_revision = "20260506_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("slug", sa.String(255), nullable=True))
    op.create_unique_constraint("uq_agent_slug", "agents", ["slug"])
    op.create_index("ix_agents_slug", "agents", ["slug"])


def downgrade() -> None:
    op.drop_index("ix_agents_slug", table_name="agents")
    op.drop_constraint("uq_agent_slug", "agents", type_="unique")
    op.drop_column("agents", "slug")
