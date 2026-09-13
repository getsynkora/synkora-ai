"""
Scheduled tasks controller
"""

import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.services.scheduler.scheduler_service import SchedulerService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scheduled-tasks", tags=["scheduled-tasks"])


# Pydantic models for request/response
class ScheduledTaskCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    task_type: str = Field(..., pattern="^(database_query|chart_generation|followup_reminder|agent_task)$")
    interval_seconds: int = Field(..., gt=0, description="Interval in seconds between executions")
    database_connection_id: int | None = None  # Optional for agent tasks
    query: str | None = None  # Optional for agent tasks
    config: dict[str, Any] | None = None  # Generic config for agent tasks
    chart_config: dict[str, Any] | None = None  # Chart config for chart_generation tasks
    is_active: bool = True


class ScheduledTaskUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    task_type: str | None = Field(None, pattern="^(database_query|chart_generation|followup_reminder|agent_task)$")
    interval_seconds: int | None = Field(None, gt=0)
    database_connection_id: int | None = None
    query: str | None = None
    config: dict[str, Any] | None = None
    chart_config: dict[str, Any] | None = None
    is_active: bool | None = None


class ScheduledTaskResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None
    task_type: str
    schedule_type: str
    cron_expression: str | None = None
    interval_seconds: int | None = None
    database_connection_id: int | None = None
    query: str | None = None
    config: dict[str, Any]
    is_active: bool
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    last_run_status: str | None = None
    created_at: datetime
    updated_at: datetime
    created_by: uuid.UUID

    model_config = ConfigDict(from_attributes=True)


class TaskExecutionResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    status: str
    started_at: datetime
    completed_at: datetime | None
    result: dict[str, Any] | None
    error_message: str | None
    execution_time_seconds: float | None

    model_config = ConfigDict(from_attributes=True)


class CronValidationRequest(BaseModel):
    cron_expression: str


class CronValidationResponse(BaseModel):
    is_valid: bool
    error: str | None = None
    next_run: str | None = None
    preview: list[str] | None = None
    description: str | None = None


@router.post("", response_model=ScheduledTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_scheduled_task(
    task_data: ScheduledTaskCreate,
    db: AsyncSession = Depends(get_async_db),
    current_account=Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    """Create a new scheduled task with interval-based scheduling"""
    try:
        scheduler_service = SchedulerService(db)

        # Validate required fields based on task type
        if task_data.task_type in ["database_query", "chart_generation"]:
            if not task_data.database_connection_id:
                raise ValueError("database_connection_id is required for database_query and chart_generation tasks")
            if not task_data.query:
                raise ValueError("query is required for database_query and chart_generation tasks")
        if task_data.task_type in ["agent_task", "followup_reminder"]:
            config = task_data.config or {}
            if not config.get("agent_id"):
                raise ValueError("agent_id is required in config for agent_task and followup_reminder tasks")

        # Merge config and chart_config for the task
        merged_config = task_data.config or {}
        if task_data.chart_config:
            merged_config["chart_config"] = task_data.chart_config
        if task_data.database_connection_id:
            merged_config["database_connection_id"] = task_data.database_connection_id
        if task_data.query:
            merged_config["query"] = task_data.query

        # Use create_agent_task for interval-based scheduling
        task = await scheduler_service.create_agent_task(
            tenant_id=tenant_id,
            name=task_data.name,
            task_type=task_data.task_type,
            interval_seconds=task_data.interval_seconds,
            created_by=current_account.id,
            config=merged_config,
            description=task_data.description,
            is_active=task_data.is_active,
        )

        return task

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating scheduled task: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create scheduled task")


@router.get("")
async def list_scheduled_tasks(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_db),
    current_account=Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    """List all scheduled tasks for the current tenant"""
    try:
        from src.models.followup import FollowupItem

        scheduler_service = SchedulerService(db)
        tasks = await scheduler_service.list_tasks(tenant_id=tenant_id, skip=skip, limit=limit)

        # Enrich tasks with followup status if applicable
        result = []
        for task in tasks:
            task_dict = {
                "id": str(task.id),
                "tenant_id": str(task.tenant_id),
                "name": task.name,
                "description": task.description,
                "task_type": task.task_type,
                "schedule_type": task.schedule_type,
                "cron_expression": task.cron_expression,
                "interval_seconds": task.interval_seconds,
                "database_connection_id": task.config.get("database_connection_id"),
                "query": task.config.get("query"),
                "config": task.config,
                "is_active": task.is_active,
                "last_run_at": task.last_run_at.isoformat() if task.last_run_at else None,
                "next_run_at": task.next_run_at.isoformat() if task.next_run_at else None,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None,
                "created_by": str(task.created_by),
                "last_run_status": None,
            }

            # For followup_reminder tasks, get the status from the followup item
            if task.task_type == "followup_reminder" and task.config.get("followup_item_id"):
                try:
                    followup_result = await db.execute(
                        select(FollowupItem).filter(
                            FollowupItem.id == task.config["followup_item_id"],
                            FollowupItem.tenant_id == tenant_id,
                            FollowupItem.agent_id == task.config.get("agent_id"),
                        )
                    )
                    followup_item = followup_result.scalar_one_or_none()

                    if followup_item:
                        task_dict["last_run_status"] = followup_item.status
                except Exception as e:
                    logger.warning(f"Error fetching followup item status: {str(e)}")
            else:
                # For other task types, get status from the latest execution
                if task.executions and len(task.executions) > 0:
                    latest_execution = max(task.executions, key=lambda e: e.started_at)
                    task_dict["last_run_status"] = latest_execution.status

            result.append(task_dict)

        return result

    except Exception as e:
        logger.error(f"Error listing scheduled tasks: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list scheduled tasks")


@router.get("/{task_id}", response_model=ScheduledTaskResponse)
async def get_scheduled_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db),
    current_account=Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    """Get a scheduled task by ID"""
    try:
        scheduler_service = SchedulerService(db)
        # SECURITY: Scope query to tenant to prevent cross-tenant existence leaks
        task = await scheduler_service.get_task(task_id, tenant_id=tenant_id)

        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scheduled task not found")

        return task

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting scheduled task: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get scheduled task")


@router.put("/{task_id}", response_model=ScheduledTaskResponse)
async def update_scheduled_task(
    task_id: uuid.UUID,
    task_data: ScheduledTaskUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_account=Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    """Update a scheduled task"""
    try:
        scheduler_service = SchedulerService(db)

        # SECURITY: Scope query to tenant — returns uniform 404 for wrong tenant
        task = await scheduler_service.get_task(task_id, tenant_id=tenant_id)
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scheduled task not found")

        # Update task
        update_data = task_data.model_dump(exclude_unset=True)
        updated_task = await scheduler_service.update_task(task_id, tenant_id=tenant_id, **update_data)

        return updated_task

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating scheduled task: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update scheduled task")


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scheduled_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db),
    current_account=Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    """Delete a scheduled task"""
    try:
        scheduler_service = SchedulerService(db)

        # SECURITY: Scope query to tenant — returns uniform 404 for wrong tenant
        task = await scheduler_service.get_task(task_id, tenant_id=tenant_id)
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scheduled task not found")

        await scheduler_service.delete_task(task_id, tenant_id=tenant_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting scheduled task: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete scheduled task")


@router.post("/{task_id}/execute", status_code=status.HTTP_202_ACCEPTED)
async def execute_scheduled_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db),
    current_account=Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    """Execute a scheduled task immediately"""
    try:
        scheduler_service = SchedulerService(db)

        # SECURITY: Scope query to tenant — returns uniform 404 for wrong tenant
        task = await scheduler_service.get_task(task_id, tenant_id=tenant_id)
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scheduled task not found")

        # Execute task asynchronously
        scheduler_service.execute_task_async(task_id)

        return {"message": "Task execution queued"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing scheduled task: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to execute scheduled task"
        )


@router.post("/{task_id}/toggle", response_model=ScheduledTaskResponse)
async def toggle_scheduled_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db),
    current_account=Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    """Toggle a scheduled task's active status"""
    try:
        scheduler_service = SchedulerService(db)

        # SECURITY: Scope query to tenant — returns uniform 404 for wrong tenant
        task = await scheduler_service.get_task(task_id, tenant_id=tenant_id)
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scheduled task not found")

        updated_task = await scheduler_service.toggle_task(task_id, tenant_id=tenant_id)
        return updated_task

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling scheduled task: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to toggle scheduled task")


@router.get("/{task_id}/executions", response_model=list[TaskExecutionResponse])
async def get_task_executions(
    task_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_db),
    current_account=Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    """Get execution history for a scheduled task"""
    try:
        scheduler_service = SchedulerService(db)

        # SECURITY: Scope query to tenant — returns uniform 404 for wrong tenant
        task = await scheduler_service.get_task(task_id, tenant_id=tenant_id)
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scheduled task not found")

        executions = await scheduler_service.get_task_executions(task_id=task_id, skip=skip, limit=limit)

        return executions

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task executions: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get task executions")


@router.post("/executions/{execution_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_task_execution(
    execution_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db),
    current_account=Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    """Cancel a running task execution by revoking the Celery task."""
    from datetime import UTC, datetime

    from sqlalchemy import select

    from src.celery_app import celery_app
    from src.models.scheduled_task import TaskExecution, TaskStatus

    result = await db.execute(select(TaskExecution).filter(TaskExecution.id == execution_id))
    execution = result.scalar_one_or_none()

    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")

    # Verify tenant ownership via the parent task
    from src.models.scheduled_task import ScheduledTask

    task_result = await db.execute(select(ScheduledTask).filter(ScheduledTask.id == execution.task_id))
    task = task_result.scalar_one_or_none()
    if not task or task.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scheduled task not found")

    if execution.status not in (TaskStatus.RUNNING, TaskStatus.PENDING):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel execution in '{execution.status}' state",
        )

    # Revoke the Celery task (terminate=True sends SIGTERM to the worker process)
    if execution.celery_task_id:
        celery_app.control.revoke(execution.celery_task_id, terminate=True, signal="SIGTERM")
        logger.info(f"Revoked Celery task {execution.celery_task_id} for execution {execution_id}")

    execution.status = TaskStatus.CANCELLED
    execution.completed_at = datetime.now(UTC)
    execution.error_message = "Cancelled by user"
    await db.commit()

    return {"execution_id": str(execution_id), "status": "cancelled"}


@router.post("/validate-cron", response_model=CronValidationResponse)
async def validate_cron_expression(
    request: CronValidationRequest,
    db: AsyncSession = Depends(get_async_db),
    current_account=Depends(get_current_account),
):
    """Validate a cron expression"""
    try:
        scheduler_service = SchedulerService(db)
        result = scheduler_service.validate_cron(request.cron_expression)
        return result

    except Exception as e:
        logger.warning(f"Error validating cron expression: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to validate cron expression"
        )
