"""
Scheduler service for managing scheduled tasks
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from croniter import croniter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.scheduled_task import ScheduledTask, TaskExecution
from src.services.scheduler.cron_validator import CronValidator
from src.services.scheduler.task_executor import TaskExecutor
from src.tasks.scheduled_tasks import execute_scheduled_task

logger = logging.getLogger(__name__)


class SchedulerService:
    """Service for managing scheduled tasks"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.task_executor = TaskExecutor(db)
        self.cron_validator = CronValidator()

    async def _validate_references(self, tenant_id: uuid.UUID, task_type: str, config: dict) -> None:
        """Validate JSON resource references before persisting a task."""
        from pydantic import BaseModel, ConfigDict

        from src.models.agent import Agent
        from src.models.database_connection import DatabaseConnection
        from src.models.followup import FollowupItem

        class FollowupConfig(BaseModel):
            model_config = ConfigDict(extra="allow")
            agent_id: uuid.UUID
            followup_item_id: uuid.UUID

        if task_type == "followup_reminder":
            references = FollowupConfig.model_validate(config)
            followup = await self.db.scalar(
                select(FollowupItem.id).where(
                    FollowupItem.id == references.followup_item_id,
                    FollowupItem.agent_id == references.agent_id,
                    FollowupItem.tenant_id == tenant_id,
                )
            )
            if followup is None:
                raise ValueError("Follow-up is unavailable in this tenant")
        if task_type in {"agent_task", "autonomous_agent", "followup_reminder"} or config.get("agent_id"):
            agent_id = uuid.UUID(str(config.get("agent_id", "")))
            agent = await self.db.scalar(select(Agent.id).where(Agent.id == agent_id, Agent.tenant_id == tenant_id))
            if agent is None:
                raise ValueError("Agent is unavailable in this tenant")
        if task_type in {"database_query", "chart_generation"} or config.get("database_connection_id"):
            try:
                database_connection_id = uuid.UUID(str(config.get("database_connection_id", "")))
            except ValueError as e:
                raise ValueError("Database connection is unavailable in this tenant") from e
            connection = await self.db.scalar(
                select(DatabaseConnection.id).where(
                    DatabaseConnection.id == database_connection_id,
                    DatabaseConnection.tenant_id == tenant_id,
                )
            )
            if connection is None:
                raise ValueError("Database connection is unavailable in this tenant")

    async def create_task(
        self,
        tenant_id: uuid.UUID,
        name: str,
        task_type: str,
        schedule: str,
        created_by: uuid.UUID,
        database_connection_id: int | None = None,
        query: str | None = None,
        description: str | None = None,
        chart_config: dict[str, Any] | None = None,
        is_active: bool = True,
    ) -> ScheduledTask:
        """
        Create a new scheduled task

        Args:
            tenant_id: ID of the tenant
            name: Name of the task
            task_type: Type of task (database_query, chart_generation, followup_reminder, agent_task)
            schedule: Cron expression for scheduling
            created_by: ID of the user creating the task
            database_connection_id: ID of the database connection (optional for agent tasks)
            query: SQL query to execute (optional for agent tasks)
            description: Optional description
            chart_config: Optional chart/task configuration
            is_active: Whether the task is active

        Returns:
            Created ScheduledTask
        """
        # Validate cron expression
        validation = self.cron_validator.validate(schedule)
        if not validation.get("is_valid"):
            raise ValueError(f"Invalid cron expression: {validation.get('error')}")

        # Create task config
        task_config = chart_config or {}
        if database_connection_id is not None:
            task_config["database_connection_id"] = database_connection_id
        if query is not None:
            task_config["query"] = query

        await self._validate_references(tenant_id, task_type, task_config)

        task = ScheduledTask(
            tenant_id=tenant_id,
            name=name,
            description=description,
            task_type=task_type,
            schedule_type="cron",
            cron_expression=schedule,
            config=task_config,
            is_active=is_active,
            created_by=created_by,
            # Set last_run_at to now so the task does NOT fire immediately on first
            # Beat check — it will wait until the next actual cron occurrence.
            last_run_at=datetime.now(UTC),
        )

        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)

        logger.info(f"Created scheduled task {task.id}: {name}")

        return task

    async def create_agent_task(
        self,
        tenant_id: uuid.UUID,
        name: str,
        task_type: str,
        interval_seconds: int,
        created_by: uuid.UUID,
        config: dict[str, Any] | None = None,
        description: str | None = None,
        is_active: bool = True,
    ) -> ScheduledTask:
        """
        Create a scheduled task for agents using interval-based scheduling.

        Args:
            tenant_id: ID of the tenant
            name: Name of the task
            task_type: Type of task (e.g., 'followup_reminder', 'agent_task')
            interval_seconds: Interval in seconds between task executions
            created_by: ID of the user/agent creating the task
            config: Task configuration dictionary
            description: Optional description
            is_active: Whether the task is active

        Returns:
            Created ScheduledTask
        """
        task_config = config or {}

        await self._validate_references(tenant_id, task_type, task_config)

        task = ScheduledTask(
            tenant_id=tenant_id,
            name=name,
            description=description,
            task_type=task_type,
            schedule_type="interval",
            interval_seconds=interval_seconds,
            config=task_config,
            is_active=is_active,
            created_by=created_by,
            # Set last_run_at to now so the first run waits a full interval,
            # not immediately on the next Beat check.
            last_run_at=datetime.now(UTC),
        )

        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)

        logger.info(f"Created scheduled task {task.id}: {name} (every {interval_seconds}s)")

        return task

    async def update_task(self, task_id: uuid.UUID, tenant_id: uuid.UUID, **kwargs) -> ScheduledTask:
        """
        Update a scheduled task

        Args:
            task_id: ID of the task to update
            tenant_id: Tenant ID for access control
            **kwargs: Fields to update

        Returns:
            Updated ScheduledTask
        """
        result = await self.db.execute(
            select(ScheduledTask).filter(ScheduledTask.id == task_id, ScheduledTask.tenant_id == tenant_id)
        )
        task = result.scalar_one_or_none()

        if not task:
            raise ValueError(f"Task {task_id} not found")

        # Validate cron expression if schedule is being updated
        if "schedule" in kwargs:
            validation = self.cron_validator.validate(kwargs["schedule"])
            if not validation.get("is_valid"):
                raise ValueError(f"Invalid cron expression: {validation.get('error')}")
            kwargs["cron_expression"] = kwargs.pop("schedule")

        if "chart_config" in kwargs:
            kwargs["config"] = kwargs.pop("chart_config")

        if "query" in kwargs:
            kwargs["config"] = kwargs.get("config", {})
            kwargs["config"]["query"] = kwargs.pop("query")

        if "database_connection_id" in kwargs:
            kwargs["config"] = dict(kwargs.get("config", task.config) or {})
            kwargs["config"]["database_connection_id"] = kwargs.pop("database_connection_id")
        await self._validate_references(
            task.tenant_id, kwargs.get("task_type", task.task_type), kwargs.get("config", task.config) or {}
        )

        # Update fields
        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)

        task.updated_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(task)

        logger.info(f"Updated scheduled task {task_id}")

        return task

    async def delete_task(self, task_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        """
        Delete a scheduled task

        Args:
            task_id: ID of the task to delete
            tenant_id: Tenant ID for access control
        """
        result = await self.db.execute(
            select(ScheduledTask).filter(ScheduledTask.id == task_id, ScheduledTask.tenant_id == tenant_id)
        )
        task = result.scalar_one_or_none()

        if not task:
            raise ValueError(f"Task {task_id} not found")

        await self.db.delete(task)
        await self.db.commit()

        logger.info(f"Deleted scheduled task {task_id}")

    async def get_task(self, task_id: uuid.UUID, tenant_id: uuid.UUID | None = None) -> ScheduledTask | None:
        """
        Get a scheduled task by ID, optionally scoped to a tenant.

        Args:
            task_id: ID of the task
            tenant_id: Optional tenant ID for access control

        Returns:
            ScheduledTask or None
        """
        stmt = select(ScheduledTask).filter(ScheduledTask.id == task_id)
        if tenant_id is not None:
            stmt = stmt.filter(ScheduledTask.tenant_id == tenant_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_tasks(self, tenant_id: uuid.UUID, skip: int = 0, limit: int = 100) -> list[ScheduledTask]:
        """
        List scheduled tasks for a tenant

        Args:
            tenant_id: ID of the tenant
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of ScheduledTask
        """
        from sqlalchemy.orm import selectinload

        result = await self.db.execute(
            select(ScheduledTask)
            .options(selectinload(ScheduledTask.executions))
            .filter(ScheduledTask.tenant_id == tenant_id)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_due_tasks(self) -> list[ScheduledTask]:
        """
        Get tasks that are due to run

        Returns:
            List of ScheduledTask that are due
        """

        now = datetime.now(UTC)

        # Get all active tasks
        result = await self.db.execute(select(ScheduledTask).filter(ScheduledTask.is_active))
        tasks = list(result.scalars().all())

        due_tasks = []

        for task in tasks:
            try:
                # Check if task is due
                if self._is_task_due(task, now):
                    due_tasks.append(task)
            except Exception as e:
                logger.error(f"Error checking if task {task.id} is due: {str(e)}")

        return due_tasks

    def _is_task_due(self, task: ScheduledTask, now: datetime) -> bool:
        """
        Check if a task is due to run based on interval or cron scheduling.

        Args:
            task: The scheduled task
            now: Current datetime (timezone-aware)

        Returns:
            True if task is due, False otherwise
        """
        from datetime import timedelta

        # Handle cron-based scheduling
        if task.schedule_type == "cron" and task.cron_expression:
            return self._is_cron_task_due(task, now)

        # Handle interval-based scheduling
        if not task.interval_seconds:
            logger.warning(f"Task {task.id} has no interval_seconds or cron_expression configured")
            return False

        # If task has never run, it's due
        if not task.last_run_at:
            return True

        # Ensure last_run_at is timezone-aware for comparison
        last_run = task.last_run_at
        if last_run.tzinfo is None:
            last_run = last_run.replace(tzinfo=UTC)

        # Check if interval has passed since last run
        next_run = last_run + timedelta(seconds=task.interval_seconds)
        return next_run <= now

    def _is_cron_task_due(self, task: ScheduledTask, now: datetime) -> bool:
        """
        Check if a cron-based task is due to run.

        Args:
            task: The scheduled task with cron_expression
            now: Current datetime (timezone-aware)

        Returns:
            True if task is due, False otherwise
        """

        try:
            # If task has never run, it's due to run now
            if not task.last_run_at:
                return True

            # Ensure last_run_at is timezone-aware
            last_run = task.last_run_at
            if last_run.tzinfo is None:
                last_run = last_run.replace(tzinfo=UTC)

            # Get the next scheduled run time after the last run
            cron = croniter(task.cron_expression, last_run)
            next_run = cron.get_next(datetime)

            # Ensure next_run is timezone-aware
            if next_run.tzinfo is None:
                next_run = next_run.replace(tzinfo=UTC)

            # Task is due if we're past the next scheduled time
            return next_run <= now

        except Exception as e:
            logger.error(f"Error checking cron task {task.id}: {str(e)}")
            return False

    async def execute_task(self, task_id: uuid.UUID) -> dict[str, Any]:
        """
        Execute a scheduled task

        Args:
            task_id: ID of the task to execute

        Returns:
            Dict containing execution results
        """
        return await self.task_executor.execute_task(task_id)

    def execute_task_async(self, task_id: uuid.UUID) -> None:
        """
        Execute a scheduled task asynchronously using Celery

        Args:
            task_id: ID of the task to execute
        """
        execute_scheduled_task.delay(str(task_id))
        logger.info(f"Queued task {task_id} for async execution")

    async def get_task_executions(self, task_id: uuid.UUID, skip: int = 0, limit: int = 100) -> list[TaskExecution]:
        """
        Get execution history for a task

        Args:
            task_id: ID of the task
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of TaskExecution
        """
        result = await self.db.execute(
            select(TaskExecution)
            .filter(TaskExecution.task_id == task_id)
            .order_by(TaskExecution.started_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_execution(self, execution_id: uuid.UUID) -> TaskExecution | None:
        """
        Get a task execution by ID

        Args:
            execution_id: ID of the execution

        Returns:
            TaskExecution or None
        """
        result = await self.db.execute(select(TaskExecution).filter(TaskExecution.id == execution_id))
        return result.scalar_one_or_none()

    def validate_cron(self, cron_expression: str) -> dict[str, Any]:
        """
        Validate a cron expression

        Args:
            cron_expression: The cron expression to validate

        Returns:
            Dict containing validation results
        """
        return self.cron_validator.validate(cron_expression)

    async def get_next_run_time(self, task_id: uuid.UUID) -> datetime | None:
        """
        Get the next scheduled run time for a task based on interval scheduling.

        Args:
            task_id: ID of the task

        Returns:
            Next run datetime or None
        """
        task = await self.get_task(task_id)

        if not task or not task.is_active or not task.interval_seconds:
            return None

        try:
            from datetime import timedelta

            base_time = task.last_run_at or datetime.now(UTC)
            return base_time + timedelta(seconds=task.interval_seconds)
        except Exception as e:
            logger.error(f"Error getting next run time for task {task_id}: {str(e)}")
            return None

    async def toggle_task(self, task_id: uuid.UUID, tenant_id: uuid.UUID) -> ScheduledTask:
        """
        Toggle a task's active status

        Args:
            task_id: ID of the task
            tenant_id: Tenant ID for access control

        Returns:
            Updated ScheduledTask
        """
        task = await self.get_task(task_id, tenant_id=tenant_id)

        if not task:
            raise ValueError(f"Task {task_id} not found")

        task.is_active = not task.is_active
        task.updated_at = datetime.now(UTC)

        await self.db.commit()
        await self.db.refresh(task)

        logger.info(f"Toggled task {task_id} active status to {task.is_active}")

        return task
