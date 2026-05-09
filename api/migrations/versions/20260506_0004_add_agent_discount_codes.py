"""add agent_discount_codes table for promotional pricing

Revision ID: 20260506_0004
Revises: 20260506_0003
Create Date: 2026-05-06

Creates the agent_discount_codes table that allows agent creators to issue
promotional discount codes tied to a specific pricing tier. Supports both
percentage-based and flat-credit discounts with optional usage caps and
validity windows.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

# revision identifiers, used by Alembic.
revision = "20260506_0004"
down_revision = "20260506_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # Create enum type for discount kind.
    discount_type = pg.ENUM(
        "PERCENTAGE",
        "FLAT_CREDITS",
        name="discounttype",
    )
    discount_type.create(bind, checkfirst=True)

    if not bind.dialect.has_table(bind, "agent_discount_codes"):
        op.create_table(
            "agent_discount_codes",
            sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("NOW()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("NOW()"),
            ),
            sa.Column("agent_pricing_id", pg.UUID(as_uuid=True), nullable=False),
            sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False),
            sa.Column("code", sa.String(50), nullable=False),
            sa.Column(
                "discount_type",
                pg.ENUM(
                    "PERCENTAGE",
                    "FLAT_CREDITS",
                    name="discounttype",
                    create_type=False,
                ),
                nullable=False,
            ),
            sa.Column("discount_value", sa.Numeric(10, 2), nullable=False),
            sa.Column("max_uses", sa.Integer(), nullable=True),
            sa.Column(
                "used_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
            sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
            sa.ForeignKeyConstraint(
                ["agent_pricing_id"], ["agent_pricing.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "agent_pricing_id",
                "code",
                name="uq_discount_code_pricing_code",
            ),
        )

        op.create_index(
            "ix_agent_discount_codes_code",
            "agent_discount_codes",
            ["code"],
        )
        op.create_index(
            "ix_agent_discount_codes_tenant_id",
            "agent_discount_codes",
            ["tenant_id"],
        )
        op.create_index(
            "ix_agent_discount_codes_agent_pricing_id",
            "agent_discount_codes",
            ["agent_pricing_id"],
        )


def downgrade() -> None:
    op.drop_index("ix_agent_discount_codes_agent_pricing_id", table_name="agent_discount_codes")
    op.drop_index("ix_agent_discount_codes_tenant_id", table_name="agent_discount_codes")
    op.drop_index("ix_agent_discount_codes_code", table_name="agent_discount_codes")
    op.drop_table("agent_discount_codes")

    discount_type = pg.ENUM(
        "PERCENTAGE",
        "FLAT_CREDITS",
        name="discounttype",
    )
    discount_type.drop(op.get_bind(), checkfirst=True)
