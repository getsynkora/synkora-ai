"""add video_generation_jobs table

Revision ID: 20260619_0001
Revises: 20260611_0001_add_handoff_fields
Create Date: 2026-06-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260619_0001"
down_revision = "20260611_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "video_generation_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "running", "completed", "failed", name="video_job_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("prompt", sa.Text, nullable=False),
        sa.Column("duration", sa.Integer, nullable=False, server_default="5"),
        sa.Column("external_task_id", sa.String(255), nullable=True),
        sa.Column("video_url", sa.Text, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_video_generation_jobs_tenant_id", "video_generation_jobs", ["tenant_id"])
    op.create_index("ix_video_generation_jobs_conversation_id", "video_generation_jobs", ["conversation_id"])


def downgrade() -> None:
    op.drop_table("video_generation_jobs")
    op.execute("DROP TYPE IF EXISTS video_job_status")
