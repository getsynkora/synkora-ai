"""Add analysis_jobs table for background query jobs

Revision ID: 20260610_0001
Revises: 20260606_0001
Create Date: 2026-06-10
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260610_0001"
down_revision = "20260606_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analysis_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("job_type", sa.String(10), nullable=False, server_default="read"),
        sa.Column("source_type", sa.String(50), nullable=True),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("query", sa.Text, nullable=True),
        sa.Column("analysis_spec", postgresql.JSONB, nullable=True,
                  server_default=sa.text("'{}'")),
        sa.Column("result_summary", postgresql.JSONB, nullable=True),
        sa.Column("write_log", postgresql.JSONB, nullable=True),
        sa.Column("rows_processed", sa.Integer, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )
    op.create_index("ix_analysis_jobs_tenant_id", "analysis_jobs", ["tenant_id"])
    op.create_index("ix_analysis_jobs_conversation_id", "analysis_jobs", ["conversation_id"])
    op.create_index(
        "ix_analysis_jobs_status_active",
        "analysis_jobs",
        ["status"],
        postgresql_where=sa.text("status IN ('pending', 'running')"),
    )


def downgrade() -> None:
    op.drop_index("ix_analysis_jobs_status_active", table_name="analysis_jobs")
    op.drop_index("ix_analysis_jobs_conversation_id", table_name="analysis_jobs")
    op.drop_index("ix_analysis_jobs_tenant_id", table_name="analysis_jobs")
    op.drop_table("analysis_jobs")
