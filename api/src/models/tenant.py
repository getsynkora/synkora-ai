"""
Tenant and Account models.

This module defines the multi-tenancy models for organizations (tenants)
and user accounts with role-based access control.
"""

from enum import StrEnum

from sqlalchemy import JSON, Column, ForeignKey, String, UniqueConstraint
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, relationship

from .base import BaseModel, StatusMixin


class TenantPlan(StrEnum):
    """Tenant subscription plans."""

    FREE = "FREE"
    BASIC = "BASIC"
    PRO = "PRO"
    ENTERPRISE = "ENTERPRISE"


class TenantStatus(StrEnum):
    """Tenant status values."""

    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DELETED = "DELETED"


class TenantType(StrEnum):
    """Tenant type values."""

    PLATFORM = "PLATFORM"
    EXTERNAL = "EXTERNAL"


class AccountRole(StrEnum):
    """User roles within a tenant."""

    OWNER = "OWNER"
    ADMIN = "ADMIN"
    EDITOR = "EDITOR"
    NORMAL = "NORMAL"


class AccountStatus(StrEnum):
    """Account status values."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"
    DELETED = "DELETED"


class Tenant(BaseModel, StatusMixin):
    """
    Tenant (Organization) model.

    Represents an organization/workspace that contains users and resources.
    Implements multi-tenancy for data isolation.
    """

    __tablename__ = "tenants"

    name = Column(
        String(255),
        nullable=False,
        comment="Tenant name",
    )

    plan = Column(
        SQLEnum(TenantPlan),
        nullable=False,
        default=TenantPlan.FREE,
        comment="Subscription plan",
    )

    tenant_type = Column(
        SQLEnum(TenantType),
        nullable=False,
        default=TenantType.EXTERNAL,
        comment="Tenant type: PLATFORM for platform tenant, EXTERNAL for customer tenants",
    )

    # Domain for automatic user assignment
    domain = Column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
        comment="Email domain for auto-assigning users (e.g., synkora.ai)",
    )

    # Admin-enforced 2FA for all tenant members
    mfa_required = Column(
        String(10),
        nullable=False,
        default="false",
        comment="Whether 2FA is required for all members of this tenant (stored as string)",
    )

    # Whether to auto-assign new users with matching email domain
    auto_assign_domain_users = Column(
        String(10),
        nullable=False,
        default="false",
        comment="Whether to auto-assign users with matching email domain (stored as string)",
    )

    # Platform OAuth app preferences
    disabled_platform_oauth_providers = Column(
        JSON,
        nullable=True,
        default=list,
        comment="List of platform OAuth providers disabled for this tenant (e.g., ['github', 'slack'])",
    )

    # Relationships
    members: Mapped[list["TenantAccountJoin"]] = relationship(
        "TenantAccountJoin",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    apps: Mapped[list["App"]] = relationship(
        "App",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    datasets: Mapped[list["Dataset"]] = relationship(
        "Dataset",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    data_sources: Mapped[list["DataSource"]] = relationship(
        "DataSource",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    knowledge_bases: Mapped[list["KnowledgeBase"]] = relationship(
        "KnowledgeBase",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    oauth_apps: Mapped[list["OAuthApp"]] = relationship(
        "OAuthApp",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    custom_tools: Mapped[list["CustomTool"]] = relationship(
        "CustomTool",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    charts: Mapped[list["Chart"]] = relationship(
        "Chart",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    database_connections: Mapped[list["DatabaseConnection"]] = relationship(
        "DatabaseConnection",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    scheduled_tasks: Mapped[list["ScheduledTask"]] = relationship(
        "ScheduledTask",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    subscriptions: Mapped[list["TenantSubscription"]] = relationship(
        "TenantSubscription",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    credit_balance: Mapped["CreditBalance"] = relationship(
        "CreditBalance",
        back_populates="tenant",
        uselist=False,
        cascade="all, delete-orphan",
    )
    credit_transactions: Mapped[list["CreditTransaction"]] = relationship(
        "CreditTransaction",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    credit_topups: Mapped[list["CreditTopup"]] = relationship(
        "CreditTopup",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    usage_analytics: Mapped[list["UsageAnalytics"]] = relationship(
        "UsageAnalytics",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    agent_pricing: Mapped[list["AgentPricing"]] = relationship(
        "AgentPricing",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    agent_revenues: Mapped[list["AgentRevenue"]] = relationship(
        "AgentRevenue",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    files: Mapped[list["UploadFile"]] = relationship(
        "UploadFile",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    followup_items: Mapped[list["FollowupItem"]] = relationship(
        "FollowupItem",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    followup_configs: Mapped[list["FollowupConfig"]] = relationship(
        "FollowupConfig",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

    creator_profile: Mapped["CreatorProfile"] = relationship(
        "CreatorProfile",
        back_populates="tenant",
        uselist=False,
        lazy="select",
    )

    public_profiles: Mapped[list["AgentPublicProfile"]] = relationship(
        "AgentPublicProfile",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<Tenant(id={self.id}, name={self.name}, plan={self.plan})>"


class Account(BaseModel, StatusMixin):
    """
    User account model.

    Represents a user who can belong to multiple tenants with different roles.
    """

    __tablename__ = "accounts"

    name = Column(
        String(255),
        nullable=False,
        comment="User full name",
    )

    email = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="User email address",
    )

    password_hash = Column(
        String(255),
        nullable=True,
        comment="Hashed password (null for OAuth users)",
    )

    interface_language = Column(
        String(10),
        nullable=False,
        default="en-US",
        comment="Preferred UI language",
    )

    timezone = Column(
        String(50),
        nullable=False,
        default="UTC",
        comment="User timezone",
    )

    # Profile fields
    avatar_url = Column(
        String(500),
        nullable=True,
        comment="Profile avatar URL",
    )

    phone = Column(
        String(20),
        nullable=True,
        comment="Phone number",
    )

    bio = Column(
        String(500),
        nullable=True,
        comment="User biography/description",
    )

    company = Column(
        String(255),
        nullable=True,
        comment="Company name",
    )

    job_title = Column(
        String(100),
        nullable=True,
        comment="Job title/position",
    )

    location = Column(
        String(100),
        nullable=True,
        comment="Location (city, country)",
    )

    website = Column(
        String(255),
        nullable=True,
        comment="Personal or company website",
    )

    # Security fields
    two_factor_enabled = Column(
        String(10),
        nullable=False,
        default="false",
        comment="Whether 2FA is enabled (stored as string for compatibility)",
    )

    two_factor_secret = Column(
        String(255),
        nullable=True,
        comment="2FA secret key (encrypted)",
    )

    two_factor_backup_codes = Column(
        JSON,
        nullable=True,
        comment="Hashed 2FA backup/recovery codes (SHA-256); each consumed on use",
    )

    last_login_at = Column(
        String(50),
        nullable=True,
        comment="Last login timestamp",
    )

    last_login_ip = Column(
        String(45),
        nullable=True,
        comment="Last login IP address (supports IPv6)",
    )

    # Social auth fields
    auth_provider = Column(
        String(20),
        nullable=False,
        default="local",
        comment="Authentication provider: local, google, github, microsoft, apple, okta",
    )

    provider_user_id = Column(
        String(255),
        nullable=True,
        comment="User ID from OAuth provider",
    )

    provider_metadata = Column(
        String(2000),
        nullable=True,
        comment="JSON string of additional provider data",
    )

    okta_tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("okta_tenants.id", ondelete="SET NULL"),
        nullable=True,
        comment="Okta tenant ID for SSO users",
    )

    # Platform admin flag
    is_platform_admin = Column(
        String(10),
        nullable=False,
        default="false",
        comment="Whether user is a platform administrator (stored as string)",
    )

    # Notification preferences
    notification_preferences = Column(
        String(1000),
        nullable=True,
        comment="JSON string of notification preferences",
    )

    # Password reset fields
    reset_token = Column(
        String(255),
        nullable=True,
        index=True,
        comment="Password reset token",
    )

    reset_token_expires_at = Column(
        String(50),
        nullable=True,
        comment="Password reset token expiration timestamp",
    )

    # Email verification fields
    email_verification_token = Column(
        String(255),
        nullable=True,
        index=True,
        comment="Email verification token",
    )

    email_verification_sent_at = Column(
        String(50),
        nullable=True,
        comment="Email verification sent timestamp",
    )

    # Relationships
    tenant_memberships = relationship(
        "TenantAccountJoin",
        foreign_keys="[TenantAccountJoin.account_id]",
        back_populates="account",
        cascade="all, delete-orphan",
    )
    created_apps = relationship(
        "App",
        foreign_keys="App.created_by",
        back_populates="creator",
    )
    updated_apps = relationship(
        "App",
        foreign_keys="App.updated_by",
        back_populates="updater",
    )
    conversations = relationship(
        "Conversation",
        back_populates="account",
    )
    linked_providers: Mapped[list["AccountProvider"]] = relationship(
        "AccountProvider",
        back_populates="account",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<Account(id={self.id}, email={self.email})>"

    def to_dict(self, exclude: set[str] | None = None) -> dict:
        """Convert to dict, always excluding password_hash."""
        exclude = exclude or set()
        exclude.add("password_hash")
        return super().to_dict(exclude=exclude)


class TenantAccountJoin(BaseModel):
    """
    Association table for tenant-account many-to-many relationship.

    Links users to tenants with specific roles.
    """

    __tablename__ = "tenant_account_joins"

    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Tenant ID",
    )

    account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Account ID",
    )

    role = Column(
        SQLEnum(AccountRole),
        nullable=False,
        default=AccountRole.NORMAL,
        comment="User role in tenant",
    )

    # Invitation tracking
    invited_by = Column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
        comment="Account ID of user who sent the invitation",
    )

    joined_at = Column(
        String(50),
        nullable=True,
        comment="Timestamp when user joined the tenant",
    )

    # Custom permissions (JSON string for tenant-specific permission overrides)
    custom_permissions = Column(
        String(2000),
        nullable=True,
        comment="JSON string of custom permission overrides for this user in this tenant",
    )

    # Role-based permissions
    role_id = Column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Role ID for granular permission control",
    )

    # Relationships
    tenant = relationship("Tenant", back_populates="members")
    account = relationship(
        "Account",
        foreign_keys=[account_id],
        back_populates="tenant_memberships",
    )
    assigned_role = relationship(
        "Role",
        foreign_keys=[role_id],
    )

    # Constraints
    __table_args__ = (UniqueConstraint("tenant_id", "account_id", name="uq_tenant_account"),)

    def __repr__(self) -> str:
        """String representation."""
        return f"<TenantAccountJoin(tenant_id={self.tenant_id}, account_id={self.account_id}, role={self.role})>"

    @property
    def is_owner(self) -> bool:
        """Check if user is owner."""
        return self.role == AccountRole.OWNER

    @property
    def is_admin(self) -> bool:
        """Check if user is admin or owner."""
        return self.role in (AccountRole.OWNER, AccountRole.ADMIN)

    @property
    def can_edit(self) -> bool:
        """Check if user can edit resources."""
        return self.role in (AccountRole.OWNER, AccountRole.ADMIN, AccountRole.EDITOR)
