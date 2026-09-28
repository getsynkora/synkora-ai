"""Generic OIDC SSO configuration per tenant."""

from sqlalchemy import Boolean, Column, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID

from .base import BaseModel


class OIDCConfig(BaseModel):
    """
    Generic OIDC IdP configuration for a tenant.

    One record per tenant (enforced by unique constraint on tenant_id).
    Supports auto-discovery via /.well-known/openid-configuration or
    manual endpoint configuration.
    """

    __tablename__ = "oidc_configs"

    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Owning tenant — one OIDC config per tenant",
    )

    # Provider identity
    provider_name = Column(
        String(100),
        nullable=False,
        comment="Display name, e.g. 'Ping Identity', 'Azure AD'",
    )

    # OAuth2 credentials
    client_id = Column(
        String(500),
        nullable=False,
        comment="OAuth2 client ID from IdP",
    )
    client_secret = Column(
        Text,
        nullable=False,
        comment="OAuth2 client secret (stored encrypted)",
    )

    # Discovery or manual endpoints
    discovery_url = Column(
        String(500),
        nullable=True,
        comment="OIDC discovery URL (.well-known/openid-configuration). If set, other endpoints are auto-discovered.",
    )
    authorization_endpoint = Column(
        String(500),
        nullable=True,
        comment="Authorization endpoint (manual override)",
    )
    token_endpoint = Column(
        String(500),
        nullable=True,
        comment="Token endpoint (manual override)",
    )
    userinfo_endpoint = Column(
        String(500),
        nullable=True,
        comment="UserInfo endpoint (manual override)",
    )
    jwks_uri = Column(
        String(500),
        nullable=True,
        comment="JWKS URI for token verification (manual override)",
    )

    # Attribute mapping
    email_claim = Column(
        String(100),
        nullable=False,
        default="email",
        comment="JWT claim for user email",
    )
    name_claim = Column(
        String(100),
        nullable=False,
        default="name",
        comment="JWT claim for user display name",
    )

    # Behaviour
    is_enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether OIDC SSO is enabled for this tenant",
    )
    auto_provision = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Auto-create accounts on first SSO login (JIT provisioning)",
    )

    # Scopes to request
    scopes = Column(
        String(500),
        nullable=False,
        default="openid email profile",
        comment="Space-separated OAuth2 scopes to request",
    )
