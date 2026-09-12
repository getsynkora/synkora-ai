"""
Activity Log Model

Database model for comprehensive audit trail of user actions.
"""

from enum import StrEnum

from sqlalchemy import Column, ForeignKey, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from .base import BaseModel


class ActivityType(StrEnum):
    """Activity type categories."""

    AUTH = "AUTH"  # Login, logout, password change
    ACCOUNT = "ACCOUNT"  # Profile updates, settings changes
    TENANT = "TENANT"  # Tenant creation, updates
    TEAM = "TEAM"  # Team member invitations, role changes
    AGENT = "AGENT"  # Agent creation, updates, deletion
    CONVERSATION = "CONVERSATION"  # Chat interactions
    RESOURCE = "RESOURCE"  # Resource access, modifications
    SECURITY = "SECURITY"  # Security events, permission changes
    SYSTEM = "SYSTEM"  # System-level events


class ActivityLog(BaseModel):
    """
    Activity log model for comprehensive audit trail.

    Tracks all significant user actions for security, compliance,
    and debugging purposes.
    """

    __tablename__ = "activity_logs"

    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Tenant ID (null for platform-level activities)",
    )

    account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Account ID of user who performed the action",
    )

    activity_type = Column(
        SQLEnum(ActivityType),
        nullable=False,
        index=True,
        comment="Type of activity",
    )

    action = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Specific action performed (e.g., 'login', 'create_agent', 'update_role')",
    )

    resource_type = Column(
        String(50),
        nullable=True,
        index=True,
        comment="Type of resource affected (e.g., 'agent', 'user', 'tenant')",
    )

    resource_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="ID of the affected resource",
    )

    description = Column(
        Text,
        nullable=True,
        comment="Human-readable description of the activity",
    )

    activity_metadata = Column(
        JSONB,
        nullable=True,
        comment="Additional context and details about the activity",
    )

    ip_address = Column(
        String(45),
        nullable=True,
        comment="IP address of the user (supports IPv6)",
    )

    user_agent = Column(
        Text,
        nullable=True,
        comment="User agent string from the request",
    )

    status = Column(
        String(20),
        nullable=False,
        default="success",
        comment="Status of the activity (success, failure, pending)",
    )

    error_message = Column(
        Text,
        nullable=True,
        comment="Error message if activity failed",
    )

    entry_hash = Column(
        String(64),
        nullable=True,  # nullable for backwards compatibility with old rows
        index=True,
        comment="SHA-256 HMAC of this entry chained with the previous entry hash",
    )

    # Relationships
    tenant = relationship("Tenant")
    account = relationship("Account")

    def __repr__(self) -> str:
        """String representation."""
        return f"<ActivityLog(id={self.id}, action={self.action}, account_id={self.account_id})>"

    @staticmethod
    def compute_hash(
        entry_id: str,
        action: str,
        account_id: str | None,
        tenant_id: str | None,
        activity_type: str,
        created_at: str,
        prev_hash: str,
        secret_key: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        description: str | None = None,
        activity_metadata: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        status: str = "success",
        error_message: str | None = None,
    ) -> str:
        """
        Compute HMAC-SHA256 for this log entry chained with the previous entry.

        The chain ensures any tampering (modification or deletion of entries)
        is detectable by re-computing and comparing hashes.
        """
        import hashlib
        import hmac as _hmac
        import json

        if not secret_key or len(secret_key) < 32:
            raise ValueError("A strong audit signing key is required")
        payload = json.dumps(
            {
                "version": 2,
                "entry_id": str(entry_id),
                "action": action,
                "account_id": str(account_id) if account_id else None,
                "tenant_id": str(tenant_id) if tenant_id else None,
                "activity_type": str(activity_type),
                "created_at": created_at,
                "prev_hash": prev_hash,
                "resource_type": resource_type,
                "resource_id": str(resource_id) if resource_id else None,
                "description": description,
                "activity_metadata": activity_metadata or {},
                "ip_address": ip_address,
                "user_agent": user_agent,
                "status": status,
                "error_message": error_message,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return _hmac.new(
            secret_key.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

    @classmethod
    def log_activity(
        cls,
        action: str,
        activity_type: ActivityType,
        account_id: str | None = None,
        tenant_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        description: str | None = None,
        activity_metadata: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        status: str = "success",
        error_message: str | None = None,
    ) -> "ActivityLog":
        """
        Create a new activity log entry.

        Args:
            action: Specific action performed
            activity_type: Type of activity
            account_id: Account ID (optional)
            tenant_id: Tenant ID (optional)
            resource_type: Type of resource (optional)
            resource_id: Resource ID (optional)
            description: Human-readable description (optional)
            metadata: Additional context (optional)
            ip_address: User's IP address (optional)
            user_agent: User agent string (optional)
            status: Activity status (default: success)
            error_message: Error message if failed (optional)

        Returns:
            ActivityLog: New activity log instance
        """
        return cls(
            action=action,
            activity_type=activity_type,
            account_id=account_id,
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            description=description,
            activity_metadata=activity_metadata,
            ip_address=ip_address,
            user_agent=user_agent,
            status=status,
            error_message=error_message,
        )
