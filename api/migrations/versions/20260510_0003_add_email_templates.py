"""add email_templates table and agents.email_template_id

Revision ID: 20260510_0003
Revises: 20260510_0001
Create Date: 2026-05-10
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "20260510_0003"
down_revision = "20260510_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # Create enum type
    template_type = pg.ENUM(
        "BUILTIN",
        "CUSTOM_HTML",
        "SENDGRID",
        "MAILCHIMP",
        "BREVO",
        name="emailtemplatetype",
    )
    template_type.create(bind, checkfirst=True)

    if not bind.dialect.has_table(bind, "email_templates"):
        op.create_table(
            "email_templates",
            sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
            sa.Column("tenant_id", pg.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("description", sa.String(500), nullable=True),
            sa.Column("template_type", pg.ENUM("BUILTIN", "CUSTOM_HTML", "SENDGRID", "MAILCHIMP", "BREVO", name="emailtemplatetype", create_type=False), nullable=False, server_default="BUILTIN"),
            sa.Column("builtin_name", sa.String(50), nullable=True),
            sa.Column("html_content", sa.Text, nullable=True),
            sa.Column("external_provider", sa.String(50), nullable=True),
            sa.Column("external_template_id", sa.String(200), nullable=True),
            sa.Column("external_config", pg.JSONB, nullable=True),
            sa.Column("preview_html", sa.Text, nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        )
        op.create_index("ix_email_templates_tenant_id", "email_templates", ["tenant_id"])
        op.create_index("ix_email_templates_template_type", "email_templates", ["template_type"])
        op.create_index("ix_email_templates_is_active", "email_templates", ["is_active"])

    # Add email_template_id FK to agents
    result = bind.execute(
        sa.text("SELECT column_name FROM information_schema.columns WHERE table_name='agents' AND column_name='email_template_id'")
    )
    if not result.fetchone():
        op.add_column("agents", sa.Column("email_template_id", pg.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(
            "fk_agents_email_template_id",
            "agents",
            "email_templates",
            ["email_template_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_agents_email_template_id", "agents", ["email_template_id"])


def downgrade() -> None:
    op.drop_index("ix_agents_email_template_id", table_name="agents")
    op.drop_constraint("fk_agents_email_template_id", "agents", type_="foreignkey")
    op.drop_column("agents", "email_template_id")

    op.drop_index("ix_email_templates_is_active", table_name="email_templates")
    op.drop_index("ix_email_templates_template_type", table_name="email_templates")
    op.drop_index("ix_email_templates_tenant_id", table_name="email_templates")
    op.drop_table("email_templates")

    bind = op.get_bind()
    pg.ENUM(name="emailtemplatetype").drop(bind, checkfirst=True)
