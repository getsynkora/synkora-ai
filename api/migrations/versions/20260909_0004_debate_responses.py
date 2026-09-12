"""Keep authenticated external submissions separate from executor message snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "20260909_0004"
down_revision = "20260909_0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("debate_sessions", sa.Column("external_responses", sa.JSON(), nullable=False, server_default="{}"))


def downgrade():
    op.drop_column("debate_sessions", "external_responses")
