"""add responded_by to agent_approval_requests

Revision ID: 20260813_0002
Revises: 20260813_0001
Create Date: 2026-08-13

Adds a responded_by column to agent_approval_requests to record which
Slack user (or other channel identity) approved/rejected a HITL request
via an interactive button click.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260813_0002"
down_revision = "20260813_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_approval_requests",
        sa.Column("responded_by", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_approval_requests", "responded_by")
