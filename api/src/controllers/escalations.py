"""
Escalations Controller

API endpoints for managing human escalations.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id
from src.models import EscalationPriority, EscalationReason, EscalationStatus
from src.services.roles.human_escalation_service import HumanEscalationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/escalations", tags=["escalations"])


# Request/Response Models


class ResolveEscalationRequest(BaseModel):
    """Request model for resolving an escalation."""

    response: str = Field(..., min_length=1)
    resolution_notes: str | None = None


class CreateEscalationRequest(BaseModel):
    """Request model for creating an escalation (for testing/admin purposes)."""

    project_id: str
    from_agent_id: str
    to_human_id: str
    reason: str = Field(
        ...,
        pattern="^(uncertainty|approval_needed|complex_decision|blocker|review_required|customer_request|security_concern|budget_approval)$",
    )
    subject: str = Field(..., min_length=1, max_length=500)
    message: str = Field(..., min_length=1)
    context_summary: str | None = None
    priority: str = Field(default="medium", pattern="^(low|medium|high|urgent)$")
    conversation_id: str | None = None
    expires_in_hours: int | None = Field(default=24, ge=1, le=168)
    auto_notify: bool = True


class EscalationResponse(BaseModel):
    """Response model for an escalation."""

    id: str
    project_id: str
    conversation_id: str | None
    from_agent_id: str | None
    to_human_id: str | None
    reason: str
    priority: str
    subject: str
    message: str
    context_summary: str | None
    status: str
    notification_channels: dict | None
    notification_sent_at: str | None
    human_response: str | None
    resolved_at: str | None
    expires_at: str | None
    created_at: str
    updated_at: str
    # Related info
    from_agent_name: str | None
    to_human_name: str | None
    project_name: str | None


# Endpoints


@router.get("", response_model=list[EscalationResponse])
async def list_escalations(
    status: str | None = Query(None, description="Filter by status"),
    project_id: str | None = Query(None, description="Filter by project"),
    human_id: str | None = Query(None, description="Filter by human contact"),
    agent_id: str | None = Query(None, description="Filter by agent"),
    include_expired: bool = Query(False, description="Include expired escalations"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """List escalations with filters."""
    try:
        service = HumanEscalationService(db)
        escalations = await service.list_escalations(
            tenant_id=tenant_id,
            status=status,
            project_id=UUID(project_id) if project_id else None,
            human_id=UUID(human_id) if human_id else None,
            agent_id=UUID(agent_id) if agent_id else None,
            include_expired=include_expired,
        )

        return [
            EscalationResponse(
                id=str(e.id),
                project_id=str(e.project_id),
                conversation_id=str(e.conversation_id) if e.conversation_id else None,
                from_agent_id=str(e.from_agent_id) if e.from_agent_id else None,
                to_human_id=str(e.to_human_id) if e.to_human_id else None,
                reason=e.reason,
                priority=e.priority,
                subject=e.subject,
                message=e.message,
                context_summary=e.context_summary,
                status=e.status,
                notification_channels=e.notification_channels,
                notification_sent_at=e.notification_sent_at.isoformat() if e.notification_sent_at else None,
                human_response=e.human_response,
                resolved_at=e.resolved_at.isoformat() if e.resolved_at else None,
                expires_at=e.expires_at.isoformat() if e.expires_at else None,
                created_at=e.created_at.isoformat() if e.created_at else None,
                updated_at=e.updated_at.isoformat() if e.updated_at else None,
                from_agent_name=e.from_agent.agent_name if e.from_agent else None,
                to_human_name=e.to_human.name if e.to_human else None,
                project_name=e.project.name if e.project else None,
            )
            for e in escalations
        ]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format")
    except Exception as e:
        logger.error(f"Error listing escalations: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/statuses")
async def list_escalation_statuses():
    """List available escalation statuses."""
    return {
        "success": True,
        "data": [{"value": s.value, "label": s.value.replace("_", " ").title()} for s in EscalationStatus],
    }


@router.get("/reasons")
async def list_escalation_reasons():
    """List available escalation reasons."""
    return {
        "success": True,
        "data": [{"value": r.value, "label": r.value.replace("_", " ").title()} for r in EscalationReason],
    }


@router.get("/priorities")
async def list_escalation_priorities():
    """List available escalation priorities."""
    return {"success": True, "data": [{"value": p.value, "label": p.value.title()} for p in EscalationPriority]}


@router.get("/{escalation_id}", response_model=EscalationResponse)
async def get_escalation(
    escalation_id: str, tenant_id: UUID = Depends(get_current_tenant_id), db: AsyncSession = Depends(get_async_db)
):
    """Get a specific escalation."""
    try:
        service = HumanEscalationService(db)
        e = await service.get_escalation(UUID(escalation_id))

        if not e or e.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="Escalation not found")

        return EscalationResponse(
            id=str(e.id),
            project_id=str(e.project_id),
            conversation_id=str(e.conversation_id) if e.conversation_id else None,
            from_agent_id=str(e.from_agent_id) if e.from_agent_id else None,
            to_human_id=str(e.to_human_id) if e.to_human_id else None,
            reason=e.reason,
            priority=e.priority,
            subject=e.subject,
            message=e.message,
            context_summary=e.context_summary,
            status=e.status,
            notification_channels=e.notification_channels,
            notification_sent_at=e.notification_sent_at.isoformat() if e.notification_sent_at else None,
            human_response=e.human_response,
            resolved_at=e.resolved_at.isoformat() if e.resolved_at else None,
            expires_at=e.expires_at.isoformat() if e.expires_at else None,
            created_at=e.created_at.isoformat() if e.created_at else None,
            updated_at=e.updated_at.isoformat() if e.updated_at else None,
            from_agent_name=e.from_agent.agent_name if e.from_agent else None,
            to_human_name=e.to_human.name if e.to_human else None,
            project_name=e.project.name if e.project else None,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid escalation ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting escalation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{escalation_id}/resolve", response_model=EscalationResponse)
async def resolve_escalation(
    escalation_id: str,
    request: ResolveEscalationRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Resolve an escalation with human response."""
    try:
        service = HumanEscalationService(db)

        e = await service.resolve_escalation(
            escalation_id=UUID(escalation_id),
            tenant_id=tenant_id,
            response=request.response,
            resolution_notes=request.resolution_notes,
        )

        if not e:
            raise HTTPException(status_code=404, detail="Escalation not found")

        return EscalationResponse(
            id=str(e.id),
            project_id=str(e.project_id),
            conversation_id=str(e.conversation_id) if e.conversation_id else None,
            from_agent_id=str(e.from_agent_id) if e.from_agent_id else None,
            to_human_id=str(e.to_human_id) if e.to_human_id else None,
            reason=e.reason,
            priority=e.priority,
            subject=e.subject,
            message=e.message,
            context_summary=e.context_summary,
            status=e.status,
            notification_channels=e.notification_channels,
            notification_sent_at=e.notification_sent_at.isoformat() if e.notification_sent_at else None,
            human_response=e.human_response,
            resolved_at=e.resolved_at.isoformat() if e.resolved_at else None,
            expires_at=e.expires_at.isoformat() if e.expires_at else None,
            created_at=e.created_at.isoformat() if e.created_at else None,
            updated_at=e.updated_at.isoformat() if e.updated_at else None,
            from_agent_name=e.from_agent.agent_name if e.from_agent else None,
            to_human_name=e.to_human.name if e.to_human else None,
            project_name=e.project.name if e.project else None,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid escalation ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving escalation: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{escalation_id}/in-progress", response_model=EscalationResponse)
async def mark_in_progress(
    escalation_id: str, tenant_id: UUID = Depends(get_current_tenant_id), db: AsyncSession = Depends(get_async_db)
):
    """Mark an escalation as in progress."""
    try:
        service = HumanEscalationService(db)

        e = await service.mark_in_progress(escalation_id=UUID(escalation_id), tenant_id=tenant_id)

        if not e:
            raise HTTPException(status_code=404, detail="Escalation not found")

        return EscalationResponse(
            id=str(e.id),
            project_id=str(e.project_id),
            conversation_id=str(e.conversation_id) if e.conversation_id else None,
            from_agent_id=str(e.from_agent_id) if e.from_agent_id else None,
            to_human_id=str(e.to_human_id) if e.to_human_id else None,
            reason=e.reason,
            priority=e.priority,
            subject=e.subject,
            message=e.message,
            context_summary=e.context_summary,
            status=e.status,
            notification_channels=e.notification_channels,
            notification_sent_at=e.notification_sent_at.isoformat() if e.notification_sent_at else None,
            human_response=e.human_response,
            resolved_at=e.resolved_at.isoformat() if e.resolved_at else None,
            expires_at=e.expires_at.isoformat() if e.expires_at else None,
            created_at=e.created_at.isoformat() if e.created_at else None,
            updated_at=e.updated_at.isoformat() if e.updated_at else None,
            from_agent_name=e.from_agent.agent_name if e.from_agent else None,
            to_human_name=e.to_human.name if e.to_human else None,
            project_name=e.project.name if e.project else None,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid escalation ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking escalation in progress: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{escalation_id}/notify")
async def resend_notification(
    escalation_id: str, tenant_id: UUID = Depends(get_current_tenant_id), db: AsyncSession = Depends(get_async_db)
):
    """Resend notification for an escalation."""
    try:
        service = HumanEscalationService(db)

        result = await service.notify_human(escalation_id=UUID(escalation_id), tenant_id=tenant_id)

        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to send notification"))

        return {"success": True, "message": "Notification sent", "data": result.get("channels", {})}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid escalation ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("")
async def create_escalation(
    request: CreateEscalationRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Create an escalation manually (for testing/admin purposes).

    Normally, escalations are created by agents using the escalate_to_human tool.
    """
    try:
        service = HumanEscalationService(db)

        e = await service.create_escalation(
            tenant_id=tenant_id,
            project_id=UUID(request.project_id),
            from_agent_id=UUID(request.from_agent_id),
            to_human_id=UUID(request.to_human_id),
            reason=request.reason,
            subject=request.subject,
            message=request.message,
            context_summary=request.context_summary,
            priority=request.priority,
            conversation_id=UUID(request.conversation_id) if request.conversation_id else None,
            expires_in_hours=request.expires_in_hours,
            auto_notify=request.auto_notify,
        )

        return {
            "success": True,
            "data": {"id": str(e.id), "status": e.status, "notification_channels": e.notification_channels},
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error creating escalation: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/expire-old")
async def expire_old_escalations(
    tenant_id: UUID = Depends(get_current_tenant_id), db: AsyncSession = Depends(get_async_db)
):
    """
    Mark old escalations as expired.

    This is typically called by a scheduled job.
    """
    try:
        service = HumanEscalationService(db)
        count = await service.expire_old_escalations(tenant_id=tenant_id)

        return {"success": True, "message": f"Expired {count} escalations"}
    except Exception as e:
        logger.error(f"Error expiring escalations: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/pending/human/{human_id}", response_model=list[EscalationResponse])
async def get_pending_for_human(
    human_id: str, tenant_id: UUID = Depends(get_current_tenant_id), db: AsyncSession = Depends(get_async_db)
):
    """Get all pending escalations for a specific human contact."""
    try:
        service = HumanEscalationService(db)
        escalations = await service.get_pending_escalations(UUID(human_id))

        # Filter by tenant
        escalations = [e for e in escalations if e.tenant_id == tenant_id]

        return [
            EscalationResponse(
                id=str(e.id),
                project_id=str(e.project_id),
                conversation_id=str(e.conversation_id) if e.conversation_id else None,
                from_agent_id=str(e.from_agent_id) if e.from_agent_id else None,
                to_human_id=str(e.to_human_id) if e.to_human_id else None,
                reason=e.reason,
                priority=e.priority,
                subject=e.subject,
                message=e.message,
                context_summary=e.context_summary,
                status=e.status,
                notification_channels=e.notification_channels,
                notification_sent_at=e.notification_sent_at.isoformat() if e.notification_sent_at else None,
                human_response=e.human_response,
                resolved_at=e.resolved_at.isoformat() if e.resolved_at else None,
                expires_at=e.expires_at.isoformat() if e.expires_at else None,
                created_at=e.created_at.isoformat() if e.created_at else None,
                updated_at=e.updated_at.isoformat() if e.updated_at else None,
                from_agent_name=e.from_agent.agent_name if e.from_agent else None,
                to_human_name=e.to_human.name if e.to_human else None,
                project_name=e.project.name if e.project else None,
            )
            for e in escalations
        ]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid human ID format")
    except Exception as e:
        logger.error(f"Error getting pending escalations: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
