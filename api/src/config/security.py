"""Security configuration."""

import os
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


def get_encryption_key() -> str:
    """Get the encryption key from environment variables."""
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        raise ValueError("ENCRYPTION_KEY environment variable is not set")
    return key


class SecurityConfig(BaseSettings):
    """Security configuration settings."""

    secret_key: str = Field(
        ...,
        description=(
            "Secret key used for session signing and CSRF protection. "
            'Must be a long random string. Generate with: python -c "import secrets; print(secrets.token_hex(32))"'
        ),
    )

    jwt_secret_key: str = Field(
        ...,
        description=(
            "Secret key used exclusively for signing JWT access and refresh tokens. "
            "Separate from secret_key so token signing keys can be rotated independently. "
            'Generate with: python -c "import secrets; print(secrets.token_hex(32))"'
        ),
    )

    jwt_access_token_expires: int = Field(
        default=900,
        description="Access token expiration in seconds (default: 15 minutes)",
    )

    jwt_refresh_token_expires: int = Field(
        default=2592000,
        description="Refresh token expiration in seconds (default: 30 days)",
    )

    jwt_algorithm: Literal["HS256", "HS384", "HS512", "RS256", "RS384", "RS512", "ES256"] = Field(
        default="HS256",
        description="JWT signing algorithm (HS256 recommended for single-service; RS256 for multi-service)",
    )

    jwt_issuer: str = Field(
        default="synkora-api",
        description=(
            "JWT 'iss' (issuer) claim. Override when running multiple isolated instances "
            "or integrating with external JWT validators."
        ),
    )

    jwt_audience: str = Field(
        default="synkora-app",
        description=(
            "JWT 'aud' (audience) claim. Override to match your deployment. "
            "Must match between the API that issues tokens and any service that validates them."
        ),
    )

    jwt_max_session_age_hours: int = Field(
        default=12,
        description=(
            "Absolute maximum session lifetime in hours. "
            "Even with valid refresh tokens, a session cannot exceed this age. "
            "Configurable via JWT_MAX_SESSION_AGE_HOURS env var."
        ),
    )

    cookie_domain: str | None = Field(
        default=None,
        description=(
            "Domain attribute for auth cookies. None = current domain only (recommended). "
            "Set to '.example.com' (leading dot) to share cookies across subdomains."
        ),
    )

    mobile_oauth_redirect_scheme: str = Field(
        default="synkora",
        description=(
            "Custom URL scheme the native mobile app registers to receive social login "
            "callbacks (e.g. 'synkora' for 'synkora://auth-callback'). Social login "
            "redirect_url values using this scheme bypass the same-host open-redirect "
            "check, since the mobile app (not a browser) is the one receiving them."
        ),
    )

    encryption_key: str = Field(
        ...,
        description=(
            "Fernet encryption key for encrypting sensitive data at rest (OAuth tokens, API keys). "
            "Must be a URL-safe base64-encoded 32-byte key. "
            'Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        ),
    )

    require_2fa_for_admin: bool = Field(
        default=False,
        description=(
            "When True, OWNER and ADMIN accounts must have 2FA enabled to log in. "
            "Enable in production via REQUIRE_2FA_FOR_ADMIN=true. "
            "Disabled by default so tests and fresh deployments are not locked out."
        ),
    )

    audit_chain_secret: str = Field(
        default="",
        description=(
            "HMAC secret used to chain audit log entries for tamper detection. "
            "If empty, audit log entries will not be chained and tampering cannot be detected. "
            "MUST be set in production. "
            'Generate with: python -c "import secrets; print(secrets.token_hex(32))"'
        ),
    )

    @field_validator("secret_key", "jwt_secret_key")
    @classmethod
    def validate_key_entropy(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("Key must be at least 32 characters")
        if v.lower().startswith("your-") or v in ("change-me", "changeme", "secret"):
            raise ValueError("Default placeholder key detected — set a real secret key")
        return v

    @field_validator("encryption_key")
    @classmethod
    def validate_encryption_key(cls, v: str) -> str:
        # Fernet keys are URL-safe base64-encoded 32 bytes → 44 characters
        if len(v) < 43:
            raise ValueError(
                "ENCRYPTION_KEY must be a valid Fernet key (~44 base64 chars). "
                'Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
            )
        if v.lower().startswith("your-") or v in ("change-me", "changeme"):
            raise ValueError("Default placeholder ENCRYPTION_KEY detected — generate a real Fernet key")
        return v


class RateLimitConfig(BaseSettings):
    """Rate limiting configuration."""

    rate_limit_enabled: bool = Field(
        default=True,
        description="Enable rate limiting",
    )

    rate_limit_per_minute: int = Field(
        default=60,
        description="Requests per minute",
    )

    rate_limit_per_hour: int = Field(
        default=1000,
        description="Requests per hour",
    )


class LoggingConfig(BaseSettings):
    """Logging configuration."""

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level",
    )

    log_format: Literal["json", "text"] = Field(
        default="json",
        description="Log format",
    )
