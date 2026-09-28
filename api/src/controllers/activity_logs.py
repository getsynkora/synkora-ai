"""
Activity logs controller
"""

import csv
import io
import json
import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.models.tenant import AccountRole
from src.services.activity.activity_log_service import ActivityLogService
from src.services.audit_chain_service import verify_chain

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/activity-logs", tags=["activity-logs"])


# Pydantic models for request/response
class ActivityLogResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID | None
    account_id: uuid.UUID | None
    action: str
    resource_type: str | None = None
    resource_id: uuid.UUID | None = None
    description: str | None = None
    activity_metadata: dict | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    status: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ActivityLogStats(BaseModel):
    total_activities: int
    unique_users: int
    top_actions: list[dict]
    recent_activities: list[ActivityLogResponse]


@router.get("", response_model=list[ActivityLogResponse])
async def list_activity_logs(
    account_id: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    start_date: datetime | None = Query(None, description="Filter logs from this date"),
    end_date: datetime | None = Query(None, description="Filter logs until this date"),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_db),
    current_account=Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    """List activity logs for the current tenant"""
    try:
        activity_service = ActivityLogService(db)

        # Check if user has permission to view activity logs
        # Only owners and admins can view all logs
        from src.services.team.team_service import TeamService

        team_service = TeamService(db)
        current_member = await team_service.get_team_member(tenant_id, str(current_account.id))

        if not current_member:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

        # Regular members can only see their own logs
        if current_member["role"] not in [AccountRole.OWNER.value, AccountRole.ADMIN.value]:
            account_id = str(current_account.id)

        logs = await activity_service.list_logs(
            tenant_id=tenant_id,
            account_id=account_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            start_date=start_date,
            end_date=end_date,
            skip=skip,
            limit=limit,
        )

        return logs

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing activity logs: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list activity logs")


@router.get("/export")
async def export_activity_logs(
    format: str = Query("json", pattern="^(csv|json)$", description="Export format: csv or json"),
    account_id: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    start_date: datetime | None = Query(None, description="Filter logs from this date"),
    end_date: datetime | None = Query(None, description="Filter logs until this date"),
    limit: int = Query(1000, ge=1, le=10000, description="Max records to export (up to 10000)"),
    db: AsyncSession = Depends(get_async_db),
    current_account=Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    """Export audit logs as CSV or JSON with chain integrity header."""
    try:
        from src.services.team.team_service import TeamService

        team_service = TeamService(db)
        current_member = await team_service.get_team_member(tenant_id, str(current_account.id))

        if not current_member or current_member["role"] not in [AccountRole.OWNER.value, AccountRole.ADMIN.value]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only owners and admins can export audit logs",
            )

        activity_service = ActivityLogService(db)
        logs = await activity_service.list_logs(
            tenant_id=tenant_id,
            account_id=account_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            start_date=start_date,
            end_date=end_date,
            skip=0,
            limit=limit,
        )

        chain_result = await verify_chain(db, tenant_id, limit=min(limit, 1000))
        chain_valid = chain_result.get("valid", False)

        today = datetime.now(UTC).strftime("%Y-%m-%d")
        extra_headers = {"X-Audit-Chain-Valid": str(chain_valid).lower()}

        if format == "csv":
            output = io.StringIO()
            fieldnames = [
                "id",
                "action",
                "resource_type",
                "resource_id",
                "description",
                "ip_address",
                "user_agent",
                "status",
                "account_id",
                "created_at",
            ]
            writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for log in logs:
                writer.writerow(
                    {
                        "id": str(log.id) if log.id else "",
                        "action": log.action or "",
                        "resource_type": log.resource_type or "",
                        "resource_id": str(log.resource_id) if log.resource_id else "",
                        "description": log.description or "",
                        "ip_address": log.ip_address or "",
                        "user_agent": log.user_agent or "",
                        "status": log.status or "",
                        "account_id": str(log.account_id) if log.account_id else "",
                        "created_at": log.created_at.isoformat() if log.created_at else "",
                    }
                )
            csv_content = output.getvalue()
            extra_headers["Content-Disposition"] = f'attachment; filename="audit-logs-{today}.csv"'
            return Response(
                content=csv_content,
                media_type="text/csv",
                headers=extra_headers,
            )

        # JSON format
        def _serialize(log) -> dict:
            return {
                "id": str(log.id) if log.id else None,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": str(log.resource_id) if log.resource_id else None,
                "description": log.description,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "status": log.status,
                "account_id": str(log.account_id) if log.account_id else None,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }

        json_content = json.dumps([_serialize(log) for log in logs], default=str)
        extra_headers["Content-Disposition"] = f'attachment; filename="audit-logs-{today}.json"'
        return Response(
            content=json_content,
            media_type="application/json",
            headers=extra_headers,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting activity logs: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to export activity logs")


@router.get("/stats", response_model=ActivityLogStats)
async def get_activity_stats(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: AsyncSession = Depends(get_async_db),
    current_account=Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    """Get activity statistics for the current tenant"""
    try:
        activity_service = ActivityLogService(db)

        # Check if user has permission to view stats
        from src.services.team.team_service import TeamService

        team_service = TeamService(db)
        current_member = await team_service.get_team_member(tenant_id, str(current_account.id))

        if not current_member or current_member["role"] not in [AccountRole.OWNER.value, AccountRole.ADMIN.value]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions to view activity statistics"
            )

        stats = await activity_service.get_stats(tenant_id, days)

        return stats

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting activity stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get activity statistics"
        )


@router.get("/{log_id}", response_model=ActivityLogResponse)
async def get_activity_log(
    log_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_account=Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    """Get a specific activity log"""
    try:
        activity_service = ActivityLogService(db)
        log = await activity_service.get_log(log_id)

        if not log:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity log not found")

        # Check tenant access
        if str(log.tenant_id) != str(tenant_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

        # Check if user has permission to view this log
        from src.services.team.team_service import TeamService

        team_service = TeamService(db)
        current_member = await team_service.get_team_member(tenant_id, str(current_account.id))

        if not current_member:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

        # Regular members can only see their own logs
        if current_member["role"] not in [AccountRole.OWNER.value, AccountRole.ADMIN.value]:
            if str(log.account_id) != str(current_account.id):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

        return log

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting activity log: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get activity log")


@router.get("/me/recent", response_model=list[ActivityLogResponse])
async def get_my_recent_activities(
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
    current_account=Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    """Get recent activities for the current user"""
    try:
        activity_service = ActivityLogService(db)
        logs = await activity_service.list_logs(
            tenant_id=tenant_id, account_id=str(current_account.id), skip=0, limit=limit
        )

        return logs

    except Exception as e:
        logger.error(f"Error getting recent activities: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get recent activities")


@router.delete("/cleanup", status_code=status.HTTP_204_NO_CONTENT)
async def cleanup_old_logs(
    days: int = Query(90, ge=30, le=365, description="Delete logs older than this many days"),
    db: AsyncSession = Depends(get_async_db),
    current_account=Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    """Clean up old activity logs"""
    try:
        # Check if user has permission to cleanup logs
        from src.services.team.team_service import TeamService

        team_service = TeamService(db)
        current_member = await team_service.get_team_member(tenant_id, str(current_account.id))

        if not current_member or current_member["role"] != AccountRole.OWNER.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Only tenant owners can cleanup activity logs"
            )

        activity_service = ActivityLogService(db)
        await activity_service.cleanup_old_logs(tenant_id, days)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cleaning up logs: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to cleanup activity logs")
