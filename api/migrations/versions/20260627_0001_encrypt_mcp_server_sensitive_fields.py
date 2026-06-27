"""encrypt mcp_server sensitive fields at rest

Revision ID: 20260627_0001
Revises: 20260619_0001
Create Date: 2026-06-27

Changes auth_config, env_vars, and headers columns in mcp_servers from JSON to TEXT
so they can store Fernet-encrypted payloads ("enc:<token>").

Existing rows with plaintext JSON are left as-is; the MCPServer model property
getters transparently handle both formats (enc: prefix = encrypted, plain JSON = legacy).
Rows are re-encrypted the next time they are written.

Downgrade: converts columns back to JSON; any rows that have already been encrypted
(enc: prefix) will be set to NULL since the cipher text is not valid JSON.
"""

import sqlalchemy as sa
from alembic import op

revision = "20260627_0001"
down_revision = "20260619_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Cast existing JSON values to TEXT.  PostgreSQL allows direct JSON → TEXT cast
    # via the ::TEXT operator, which produces standard JSON-formatted strings that
    # the backwards-compat path in MCPServer's property getters can parse.
    op.alter_column(
        "mcp_servers",
        "auth_config",
        existing_type=sa.JSON(),
        type_=sa.Text(),
        existing_nullable=True,
        postgresql_using="auth_config::TEXT",
    )
    op.alter_column(
        "mcp_servers",
        "env_vars",
        existing_type=sa.JSON(),
        type_=sa.Text(),
        existing_nullable=True,
        postgresql_using="env_vars::TEXT",
    )
    op.alter_column(
        "mcp_servers",
        "headers",
        existing_type=sa.JSON(),
        type_=sa.Text(),
        existing_nullable=True,
        postgresql_using="headers::TEXT",
    )


def downgrade() -> None:
    # Encrypted values (enc: prefix) cannot be cast back to JSON — they are nulled.
    # Plaintext JSON rows (legacy, not yet re-encrypted) are preserved.
    op.alter_column(
        "mcp_servers",
        "auth_config",
        existing_type=sa.Text(),
        type_=sa.JSON(),
        existing_nullable=True,
        postgresql_using="CASE WHEN auth_config LIKE 'enc:%' THEN NULL ELSE auth_config::JSON END",
    )
    op.alter_column(
        "mcp_servers",
        "env_vars",
        existing_type=sa.Text(),
        type_=sa.JSON(),
        existing_nullable=True,
        postgresql_using="CASE WHEN env_vars LIKE 'enc:%' THEN NULL ELSE env_vars::JSON END",
    )
    op.alter_column(
        "mcp_servers",
        "headers",
        existing_type=sa.Text(),
        type_=sa.JSON(),
        existing_nullable=True,
        postgresql_using="CASE WHEN headers LIKE 'enc:%' THEN NULL ELSE headers::JSON END",
    )
