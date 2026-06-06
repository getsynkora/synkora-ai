"""Activity logging service."""

import asyncio
import inspect
import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_async_session_factory
from ...models import ActivityLog

logger = logging.getLogger(__name__)

# Strong refs prevent GC before background tasks complete.
_siem_bg_tasks: set[asyncio.Task] = set()
_audit_bg_tasks: set[asyncio.Task] = set()


async def _resolve_sync_or_async(value: Any) -> Any:
    """Handle SQLAlchemy result accessors and AsyncMock-based test doubles uniformly."""
    if inspect.isawaitable(value):
        return await value
    return value


def _finalize_background_task(task: asyncio.Task, task_set: set[asyncio.Task], label: str) -> None:
    """Drop task refs and log unexpected background failures."""
    task_set.discard(task)
    try:
        exc = task.exception()
    except asyncio.CancelledError:
        return

    if exc is not None:
        logger.exception("Background %s task failed", label, exc_info=exc)


class ActivityLogService:
    """Service for logging and retrieving user activities."""

    def __init__(self, db: AsyncSession):
        """Initialize the activity log service.

        Args:
            db: Async database session
        """
        self.db = db

    async def _prepare_log_entry(
        self,
        tenant_id: UUID | None,
        account_id: UUID,
        action: str,
        resource_type: str,
        resource_id: UUID | None = None,
        details: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> ActivityLog:
        """Create an audit entry inside the current transaction."""
        # Import ActivityType here to avoid circular imports if any
        from ...models.activity_log import ActivityType

        # Map basic actions to ActivityType if possible, or default to SYSTEM/RESOURCE
        # This logic might need to be more sophisticated based on resource_type
        activity_type = ActivityType.SYSTEM

        if resource_type == "agent":
            activity_type = ActivityType.AGENT
        elif resource_type == "conversation":
            activity_type = ActivityType.CONVERSATION
        elif resource_type == "team_member":
            activity_type = ActivityType.TEAM
        elif action in ["login", "logout"]:
            activity_type = ActivityType.AUTH

        log_entry = ActivityLog(
            tenant_id=tenant_id,
            account_id=account_id,
            action=action,
            activity_type=activity_type,
            resource_type=resource_type,
            resource_id=resource_id,
            activity_metadata=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=datetime.now(UTC),
        )

        self.db.add(log_entry)
        # Flush so the ORM assigns the PK (UUID) before we compute the chain hash
        await self.db.flush()

        # Compute HMAC chain hash — fetch the previous entry's hash for this tenant
        try:
            prev_result = await self.db.execute(
                select(ActivityLog.entry_hash)
                .where(ActivityLog.tenant_id == tenant_id)
                .where(ActivityLog.id != log_entry.id)
                .order_by(ActivityLog.created_at.desc())
                .limit(1)
            )
            prev_hash = await _resolve_sync_or_async(prev_result.scalar())
            prev_hash = prev_hash or ("0" * 64)  # Genesis hash for first entry

            # Prefer AUDIT_CHAIN_SECRET; fall back to SECRET_KEY so existing
            # deployments that have not yet set AUDIT_CHAIN_SECRET still get chain hashes.
            secret_key = os.getenv("AUDIT_CHAIN_SECRET") or os.getenv("SECRET_KEY", "")
            log_entry.entry_hash = ActivityLog.compute_hash(
                entry_id=str(log_entry.id),
                action=log_entry.action,
                account_id=str(log_entry.account_id) if log_entry.account_id else None,
                tenant_id=str(log_entry.tenant_id) if log_entry.tenant_id else None,
                activity_type=str(log_entry.activity_type),
                created_at=log_entry.created_at.isoformat() if log_entry.created_at else "",
                prev_hash=prev_hash,
                secret_key=secret_key,
            )
        except Exception:
            pass  # Hash computation failure must not block the audit write

        return log_entry

    async def log_activity(
        self,
        tenant_id: UUID | None,
        account_id: UUID,
        action: str,
        resource_type: str,
        resource_id: UUID | None = None,
        details: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        *,
        commit: bool = True,
        refresh: bool = False,
        forward_to_siem: bool | None = None,
    ) -> ActivityLog:
        """Log a user activity, optionally committing within this call."""
        log_entry = await self._prepare_log_entry(
            tenant_id=tenant_id,
            account_id=account_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if commit:
            await self.db.commit()
            if refresh:
                await self.db.refresh(log_entry)

        if forward_to_siem is None:
            forward_to_siem = commit
        if forward_to_siem:
            self._schedule_siem_forwarding(log_entry)

        return log_entry

    @staticmethod
    def _schedule_siem_forwarding(log_entry: ActivityLog) -> None:
        """Fire-and-forget SIEM forwarding — never blocks the audit write."""
        try:
            from .siem_service import get_siem_service

            siem_event = {
                "timestamp": log_entry.created_at.isoformat() if log_entry.created_at else None,
                "event_type": str(log_entry.activity_type) if log_entry.activity_type else "audit",
                "tenant_id": str(log_entry.tenant_id) if log_entry.tenant_id else None,
                "account_id": str(log_entry.account_id) if log_entry.account_id else None,
                "action": log_entry.action,
                "resource_type": log_entry.resource_type,
                "resource_id": str(log_entry.resource_id) if log_entry.resource_id else None,
                "ip": log_entry.ip_address,
                "metadata": log_entry.activity_metadata or {},
            }
            task = asyncio.create_task(get_siem_service().stream_event(siem_event))
            _siem_bg_tasks.add(task)
            task.add_done_callback(lambda completed: _finalize_background_task(completed, _siem_bg_tasks, "SIEM"))
        except Exception:
            pass  # SIEM forwarding failure must never affect the audit write

    @classmethod
    def queue_activity(
        cls,
        *,
        tenant_id: UUID | None,
        account_id: UUID,
        action: str,
        resource_type: str,
        resource_id: UUID | None = None,
        details: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Persist an audit event using a background task and an isolated DB session."""

        async def _runner() -> None:
            session_factory = get_async_session_factory()
            async with session_factory() as db:
                service = cls(db)
                await service.log_activity(
                    tenant_id=tenant_id,
                    account_id=account_id,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    details=details,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    commit=True,
                    refresh=False,
                )

        task = asyncio.create_task(_runner())
        _audit_bg_tasks.add(task)
        task.add_done_callback(lambda completed: _finalize_background_task(completed, _audit_bg_tasks, "audit"))

    async def list_logs(
        self,
        tenant_id: UUID,
        account_id: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ActivityLog]:
        """List activity logs for a tenant.

        Args:
            tenant_id: Tenant ID
            account_id: Filter by account ID
            action: Filter by action
            resource_type: Filter by resource type
            resource_id: Filter by resource ID
            start_date: Filter logs from this date
            end_date: Filter logs until this date
            skip: Number of entries to skip
            limit: Maximum number of entries to return

        Returns:
            List of activity log entries
        """
        conditions = [ActivityLog.tenant_id == tenant_id]

        if start_date:
            conditions.append(ActivityLog.created_at >= start_date)
        if end_date:
            conditions.append(ActivityLog.created_at <= end_date)
        if account_id:
            conditions.append(ActivityLog.account_id == account_id)
        if resource_type:
            conditions.append(ActivityLog.resource_type == resource_type)
        if resource_id:
            conditions.append(ActivityLog.resource_id == resource_id)
        if action:
            conditions.append(ActivityLog.action == action)

        stmt = (
            select(ActivityLog)
            .filter(and_(*conditions))
            .order_by(desc(ActivityLog.created_at))
            .limit(limit)
            .offset(skip)
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_user_activities(
        self, account_id: UUID, limit: int = 100, offset: int = 0, tenant_id: UUID | None = None
    ) -> list[ActivityLog]:
        """Get activity logs for a specific user.

        Args:
            account_id: Account ID
            limit: Maximum number of entries to return
            offset: Number of entries to skip
            tenant_id: Filter by tenant ID

        Returns:
            List of activity log entries
        """
        conditions = [ActivityLog.account_id == account_id]

        if tenant_id:
            conditions.append(ActivityLog.tenant_id == tenant_id)

        stmt = (
            select(ActivityLog)
            .filter(and_(*conditions))
            .order_by(desc(ActivityLog.created_at))
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_resource_activities(
        self, resource_type: str, resource_id: UUID, limit: int = 100, offset: int = 0
    ) -> list[ActivityLog]:
        """Get activity logs for a specific resource.

        Args:
            resource_type: Type of resource
            resource_id: Resource ID
            limit: Maximum number of entries to return
            offset: Number of entries to skip

        Returns:
            List of activity log entries
        """
        stmt = (
            select(ActivityLog)
            .filter(and_(ActivityLog.resource_type == resource_type, ActivityLog.resource_id == resource_id))
            .order_by(desc(ActivityLog.created_at))
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_security_events(
        self, tenant_id: UUID | None = None, limit: int = 100, offset: int = 0
    ) -> list[ActivityLog]:
        """Get security-related activity logs.

        Security events include: login, logout, password_change, 2fa_enable,
        2fa_disable, permission_change, role_change, etc.

        Args:
            tenant_id: Filter by tenant ID (None for all tenants)
            limit: Maximum number of entries to return
            offset: Number of entries to skip

        Returns:
            List of security-related activity log entries
        """
        security_actions = [
            "login",
            "logout",
            "login_failed",
            "password_change",
            "password_reset",
            "2fa_enable",
            "2fa_disable",
            "permission_change",
            "role_change",
            "api_key_create",
            "api_key_delete",
        ]

        conditions = [ActivityLog.action.in_(security_actions)]

        if tenant_id:
            conditions.append(ActivityLog.tenant_id == tenant_id)

        stmt = (
            select(ActivityLog)
            .filter(and_(*conditions))
            .order_by(desc(ActivityLog.created_at))
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_activities(
        self,
        tenant_id: UUID | None = None,
        account_id: UUID | None = None,
        resource_type: str | None = None,
        action: str | None = None,
    ) -> int:
        """Count activity logs matching the given filters.

        Args:
            tenant_id: Filter by tenant ID
            account_id: Filter by account ID
            resource_type: Filter by resource type
            action: Filter by action

        Returns:
            Count of matching activity logs
        """
        conditions = []

        if tenant_id:
            conditions.append(ActivityLog.tenant_id == tenant_id)
        if account_id:
            conditions.append(ActivityLog.account_id == account_id)
        if resource_type:
            conditions.append(ActivityLog.resource_type == resource_type)
        if action:
            conditions.append(ActivityLog.action == action)

        stmt = select(func.count(ActivityLog.id))

        if conditions:
            stmt = stmt.filter(and_(*conditions))

        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def delete_old_logs(self, days: int = 90, tenant_id: UUID | None = None) -> int:
        """Delete activity logs older than the specified number of days.

        Args:
            days: Number of days to retain logs
            tenant_id: Filter by tenant ID (None for all tenants)

        Returns:
            Number of logs deleted
        """
        cutoff_date = datetime.now(UTC) - timedelta(days=days)

        conditions = [ActivityLog.created_at < cutoff_date]

        if tenant_id:
            conditions.append(ActivityLog.tenant_id == tenant_id)

        stmt = select(ActivityLog).filter(and_(*conditions))
        result = await self.db.execute(stmt)
        logs_to_delete = result.scalars().all()

        count = len(logs_to_delete)

        for log in logs_to_delete:
            await self.db.delete(log)

        await self.db.commit()

        return count
