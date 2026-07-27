"""
OAuth App Model.

Stores OAuth application credentials for different providers.
This allows multi-tenant SaaS where each tenant can have their own OAuth apps.
Supports multiple accounts per provider (e.g., multiple Gmail or Slack accounts).

Platform-level OAuth apps (tenant_id=None, is_platform_app=True) are provided by
Synkora and can be used by any tenant without setting up their own OAuth credentials.
"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from ..core.database import Base


class OAuthApp(Base):
    """OAuth Application configuration."""

    __tablename__ = "oauth_apps"

    id = Column(Integer, primary_key=True, index=True)
    # tenant_id is nullable for platform-level OAuth apps
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    provider = Column(String(50), nullable=False, index=True)  # github, gmail, slack, gitlab, zoom, etc.
    app_name = Column(String(255), nullable=False)

    # Platform app flag - True for Synkora-provided OAuth apps that any tenant can use
    is_platform_app = Column(Boolean, default=False, nullable=False, index=True)

    # Authentication method: 'oauth', 'api_token', or 'github_app'
    auth_method = Column(String(20), nullable=False, default="oauth")

    # OAuth credentials (used when auth_method = 'oauth')
    client_id = Column(String(255), nullable=True)  # Made nullable for API token method
    client_secret = Column(Text, nullable=True)  # Made nullable for API token method, Encrypted
    redirect_uri = Column(String(500), nullable=True)  # Made nullable for API token method
    scopes = Column(JSON, nullable=True)  # List of scopes

    # API Token credentials (used when auth_method = 'api_token')
    api_token = Column(Text, nullable=True)  # Encrypted API token

    # OAuth tokens (encrypted, used when auth_method = 'oauth')
    access_token = Column(Text, nullable=True)  # Encrypted access token
    refresh_token = Column(Text, nullable=True)  # Encrypted refresh token
    token_expires_at = Column(DateTime, nullable=True)  # Token expiration time

    # Status flags
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)  # Default app for this provider+tenant

    # Tagging for internal tools
    tags = Column(JSON, nullable=True, default=list)  # List of tags for categorization
    is_internal_tool = Column(Boolean, default=False)  # Mark as internal tool integration

    # Metadata
    description = Column(Text, nullable=True)
    config = Column(JSON, nullable=True)  # Additional provider-specific config

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    tenant = relationship("Tenant", back_populates="oauth_apps")

    def __repr__(self):
        return f"<OAuthApp {self.provider}:{self.app_name} (tenant:{self.tenant_id})>"

    def to_dict(self, include_tokens=False):
        """
        Convert to dictionary (excluding sensitive data by default).

        Args:
            include_tokens: If True, include token status (but not actual tokens)
        """
        data = {
            "id": self.id,
            "tenant_id": str(self.tenant_id) if self.tenant_id else None,
            "provider": self.provider,
            "app_name": self.app_name,
            "auth_method": self.auth_method,
            "redirect_uri": self.redirect_uri,
            "scopes": self.scopes,
            "is_active": self.is_active,
            "is_default": self.is_default,
            "is_platform_app": self.is_platform_app,
            "tags": self.tags or [],
            "is_internal_tool": self.is_internal_tool,
            "description": self.description,
            "config": self.config,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

        if include_tokens:
            if self.auth_method == "oauth":
                data["has_access_token"] = bool(self.access_token)
                data["has_refresh_token"] = bool(self.refresh_token)
                data["token_expires_at"] = self.token_expires_at.isoformat() if self.token_expires_at else None
            elif self.auth_method in ("api_token", "basic_auth"):
                data["has_api_token"] = bool(self.api_token)
            elif self.auth_method == "github_app":
                data["has_private_key"] = bool(self.client_secret)
                data["app_id"] = self.client_id

        return data
