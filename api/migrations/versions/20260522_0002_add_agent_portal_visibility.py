"""Add portal_visibility column to agents table

Revision ID: 20260522_0002
Revises: 20260522_0001
Create Date: 2026-05-22

Adds portal_visibility to control per-agent visibility on the tenant's
white-label portal. Defaults to 'hidden' so no existing agents are
accidentally exposed.

Values:
  hidden       — not shown on portal public pages (default, safe)
  public       — visible to anonymous visitors; chat requires login
  members_only — visible only to logged-in portal users
"""

import sqlalchemy as sa
from alembic import op

revision = "20260522_0002"
down_revision = "20260522_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # Check if column already exists (idempotent)
    inspector = sa.inspect(bind)
    cols = [c["name"] for c in inspector.get_columns("agents")]
    if "portal_visibility" not in cols:
        op.add_column(
            "agents",
            sa.Column(
                "portal_visibility",
                sa.String(20),
                nullable=False,
                server_default="hidden",
                comment="Portal visibility: hidden | public | members_only",
            ),
        )
        op.create_index("ix_agent_portal_visibility", "agents", ["tenant_id", "portal_visibility"])


def downgrade() -> None:
    op.drop_index("ix_agent_portal_visibility", table_name="agents")
    op.drop_column("agents", "portal_visibility")
