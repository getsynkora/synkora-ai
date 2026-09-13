"""
User OAuth Token Model.

Stores per-user OAuth tokens for different OAuth apps.
This allows each user to connect their own account to an OAuth app,
rather than sharing a single token at the OAuthApp level.

SECURITY: access_token and refresh_token are stored encrypted at rest via
Fernet (from src.services.agents.security).  They are exposed via Python
properties that transparently encrypt on write and decrypt on read.  The
raw ``_access_token_enc`` / ``_refresh_token_enc`` columns must never be
read directly — always go through the properties.
"""

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import BaseModel


class UserOAuthToken(BaseModel):
    """Per-user OAuth token storage."""

    __tablename__ = "user_oauth_tokens"

    # Foreign keys
    account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User account that owns this token",
    )
    oauth_app_id = Column(
        Integer,
        ForeignKey("oauth_apps.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="OAuth app configuration this token belongs to",
    )

    # Encrypted token storage — do NOT access these columns directly.
    # Use the access_token / refresh_token properties instead.
    _access_token_enc = Column("access_token", Text, nullable=False, comment="Fernet-encrypted access token")
    _refresh_token_enc = Column(
        "refresh_token", Text, nullable=True, comment="Fernet-encrypted refresh token (if provided by provider)"
    )
    token_expires_at = Column(DateTime(timezone=True), nullable=True, comment="Token expiration timestamp")
    provider_config = Column(JSON, nullable=True, comment="Destination settings bound to this personal OAuth token")

    # ------------------------------------------------------------------
    # Encrypted property accessors
    # ------------------------------------------------------------------

    @property
    def access_token(self) -> str | None:
        """Return the decrypted access token."""
        if not self._access_token_enc:
            return None
        try:
            from src.services.agents.security import decrypt_value  # noqa: PLC0415

            return decrypt_value(self._access_token_enc)
        except Exception:
            # If decryption fails (e.g. key rotation), return None rather than
            # leaking the ciphertext.
            return None

    @access_token.setter
    def access_token(self, value: str | None) -> None:
        """Encrypt and store the access token."""
        if value is None:
            self._access_token_enc = None  # type: ignore[assignment]
            return
        try:
            from src.services.agents.security import encrypt_value  # noqa: PLC0415

            self._access_token_enc = encrypt_value(value)
        except Exception as exc:
            raise RuntimeError("Failed to encrypt access_token — check ENCRYPTION_KEY configuration") from exc

    @property
    def refresh_token(self) -> str | None:
        """Return the decrypted refresh token."""
        if not self._refresh_token_enc:
            return None
        try:
            from src.services.agents.security import decrypt_value  # noqa: PLC0415

            return decrypt_value(self._refresh_token_enc)
        except Exception:
            return None

    @refresh_token.setter
    def refresh_token(self, value: str | None) -> None:
        """Encrypt and store the refresh token."""
        if value is None:
            self._refresh_token_enc = None  # type: ignore[assignment]
            return
        try:
            from src.services.agents.security import encrypt_value  # noqa: PLC0415

            self._refresh_token_enc = encrypt_value(value)
        except Exception as exc:
            raise RuntimeError("Failed to encrypt refresh_token — check ENCRYPTION_KEY configuration") from exc

    # Provider user info (for display purposes)
    provider_user_id = Column(String(255), nullable=True, comment="User ID from the OAuth provider")
    provider_email = Column(String(255), nullable=True, comment="Email from the OAuth provider")
    provider_username = Column(
        String(255), nullable=True, comment="Username from the OAuth provider (e.g., GitHub login)"
    )
    provider_display_name = Column(String(255), nullable=True, comment="Display name from the OAuth provider")
    scopes = Column(Text, nullable=True, comment="Comma-separated list of authorized scopes")

    # Relationships
    account = relationship("Account", backref="oauth_tokens")
    oauth_app = relationship("OAuthApp", backref="user_tokens")

    __table_args__ = (UniqueConstraint("account_id", "oauth_app_id", name="uq_user_oauth_app"),)

    def __repr__(self):
        return f"<UserOAuthToken user:{self.account_id} app:{self.oauth_app_id}>"

    def to_dict(self, include_token_status=True):
        """
        Convert to dictionary (excluding sensitive data).

        Args:
            include_token_status: If True, include token presence status
        """
        data = {
            "id": str(self.id),
            "account_id": str(self.account_id),
            "oauth_app_id": self.oauth_app_id,
            "provider_user_id": self.provider_user_id,
            "provider_email": self.provider_email,
            "provider_username": self.provider_username,
            "provider_display_name": self.provider_display_name,
            "scopes": self.scopes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

        if include_token_status:
            data["has_access_token"] = bool(self.access_token)
            data["has_refresh_token"] = bool(self.refresh_token)
            data["token_expires_at"] = self.token_expires_at.isoformat() if self.token_expires_at else None

        return data
