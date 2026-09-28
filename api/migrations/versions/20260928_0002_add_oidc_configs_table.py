"""Add oidc_configs table for generic OIDC SSO support."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260928_0002"
down_revision = "20260928_0001"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    tables = sa.inspect(bind).get_table_names()
    if "oidc_configs" not in tables:
        op.create_table(
            "oidc_configs",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "tenant_id",
                postgresql.UUID(as_uuid=True),
                nullable=False,
                comment="Owning tenant — one OIDC config per tenant",
            ),
            sa.Column(
                "provider_name",
                sa.String(100),
                nullable=False,
                comment="Display name, e.g. 'Ping Identity', 'Azure AD'",
            ),
            sa.Column(
                "client_id",
                sa.String(500),
                nullable=False,
                comment="OAuth2 client ID from IdP",
            ),
            sa.Column(
                "client_secret",
                sa.Text(),
                nullable=False,
                comment="OAuth2 client secret (stored encrypted)",
            ),
            sa.Column(
                "discovery_url",
                sa.String(500),
                nullable=True,
                comment="OIDC discovery URL (.well-known/openid-configuration). If set, other endpoints are auto-discovered.",
            ),
            sa.Column(
                "authorization_endpoint",
                sa.String(500),
                nullable=True,
                comment="Authorization endpoint (manual override)",
            ),
            sa.Column(
                "token_endpoint",
                sa.String(500),
                nullable=True,
                comment="Token endpoint (manual override)",
            ),
            sa.Column(
                "userinfo_endpoint",
                sa.String(500),
                nullable=True,
                comment="UserInfo endpoint (manual override)",
            ),
            sa.Column(
                "jwks_uri",
                sa.String(500),
                nullable=True,
                comment="JWKS URI for token verification (manual override)",
            ),
            sa.Column(
                "email_claim",
                sa.String(100),
                nullable=False,
                server_default="email",
                comment="JWT claim for user email",
            ),
            sa.Column(
                "name_claim",
                sa.String(100),
                nullable=False,
                server_default="name",
                comment="JWT claim for user display name",
            ),
            sa.Column(
                "is_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
                comment="Whether OIDC SSO is enabled for this tenant",
            ),
            sa.Column(
                "auto_provision",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
                comment="Auto-create accounts on first SSO login (JIT provisioning)",
            ),
            sa.Column(
                "scopes",
                sa.String(500),
                nullable=False,
                server_default="openid email profile",
                comment="Space-separated OAuth2 scopes to request",
            ),
            sa.ForeignKeyConstraint(
                ["tenant_id"],
                ["tenants.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id"),
        )
        op.create_index(
            "oidc_configs_tenant_id_idx",
            "oidc_configs",
            ["tenant_id"],
            unique=False,
        )


def downgrade():
    bind = op.get_bind()
    tables = sa.inspect(bind).get_table_names()
    if "oidc_configs" in tables:
        op.drop_index("oidc_configs_tenant_id_idx", table_name="oidc_configs")
        op.drop_table("oidc_configs")
