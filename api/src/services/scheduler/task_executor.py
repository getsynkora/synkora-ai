"""
Task executor for running scheduled tasks
"""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.database_connection import DatabaseConnection, DatabaseConnectionType
from src.models.scheduled_task import ScheduledTask, TaskExecution, TaskStatus
from src.services.charts.chart_service import ChartService
from src.services.database import ElasticsearchConnector, PostgreSQLConnector
from src.tasks.notification_tasks import send_task_notification

logger = logging.getLogger(__name__)


def _run_query_sync(db_connection: DatabaseConnection, query: str, task_id: Any) -> dict[str, Any]:
    """Run a database query synchronously (called via run_in_executor from async context)."""
    if db_connection.database_type == DatabaseConnectionType.POSTGRESQL:
        connector = PostgreSQLConnector(db_connection)
    elif db_connection.database_type == DatabaseConnectionType.ELASTICSEARCH:
        connector = ElasticsearchConnector(db_connection)
    else:
        raise ValueError(f"Unsupported database type: {db_connection.database_type}")

    async def _run():
        await connector.connect()
        try:
            results = await connector.execute_query(query)
            logger.info(f"Query executed successfully for task {task_id}")
            return {"success": True, "data": results, "row_count": len(results) if isinstance(results, list) else 0}
        except Exception as e:
            logger.error(f"Error executing query for task {task_id}: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e), "data": None, "row_count": 0}
        finally:
            await connector.disconnect()

    return asyncio.run(_run())


class TaskExecutor:
    """Executes scheduled tasks"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.chart_service = ChartService(db)

    async def execute_task(self, task_id: int) -> dict[str, Any]:
        """
        Execute a scheduled task

        Args:
            task_id: ID of the task to execute

        Returns:
            Dict containing execution results
        """
        try:
            # Get the task
            result = await self.db.execute(select(ScheduledTask).filter(ScheduledTask.id == task_id))
            task = result.scalar_one_or_none()

            if not task:
                raise ValueError(f"Task {task_id} not found")

            if not task.is_active:
                logger.info(f"Task {task_id} is not active, skipping execution")
                return {"status": "skipped", "reason": "Task is not active"}

            # Create execution record
            execution = TaskExecution(task_id=task.id, status=TaskStatus.RUNNING, started_at=datetime.now(UTC))
            self.db.add(execution)
            await self.db.commit()

            try:
                # Execute based on task type
                if task.task_type == "database_query":
                    task_result = await self._execute_database_query(task, execution)
                elif task.task_type == "chart_generation":
                    task_result = await self._execute_chart_generation(task, execution)
                else:
                    raise ValueError(f"Unknown task type: {task.task_type}")

                # Update execution record
                execution.status = TaskStatus.COMPLETED
                execution.completed_at = datetime.now(UTC)
                execution.result = task_result

                # Update task last run
                task.last_run_at = datetime.now(UTC)
                task.last_run_status = TaskStatus.COMPLETED

                await self.db.commit()

                # Send notifications if configured
                if task.notifications:
                    send_task_notification.delay(execution.id)

                logger.info(f"Task {task_id} executed successfully")

                return {"status": "success", "execution_id": execution.id, "result": task_result}

            except Exception as e:
                # Update execution record with error
                execution.status = TaskStatus.FAILED
                execution.completed_at = datetime.now(UTC)
                execution.error_message = str(e)

                # Update task last run
                task.last_run_at = datetime.now(UTC)
                task.last_run_status = TaskStatus.FAILED

                await self.db.commit()

                # Send error notifications
                if task.notifications:
                    send_task_notification.delay(execution.id)

                logger.error(f"Task {task_id} execution failed: {str(e)}")
                raise

        except Exception as e:
            logger.error(f"Error executing task {task_id}: {str(e)}")
            raise

    async def _execute_database_query(self, task: ScheduledTask, execution: TaskExecution) -> dict[str, Any]:
        """
        Execute a database query task

        Args:
            task: The scheduled task
            execution: The task execution record

        Returns:
            Dict containing query results
        """
        # Get database connection
        result = await self.db.execute(
            select(DatabaseConnection).filter(
                DatabaseConnection.id == task.database_connection_id, DatabaseConnection.tenant_id == task.tenant_id
            )
        )
        db_connection = result.scalar_one_or_none()

        if not db_connection:
            raise ValueError(f"Database connection {task.database_connection_id} not found")

        # Execute query in thread pool — connectors are synchronous
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _run_query_sync, db_connection, task.query, task.id)

    async def _execute_chart_generation(self, task: ScheduledTask, execution: TaskExecution) -> dict[str, Any]:
        """
        Execute a chart generation task

        Args:
            task: The scheduled task
            execution: The task execution record

        Returns:
            Dict containing chart generation results
        """
        # First execute the query
        query_result = await self._execute_database_query(task, execution)

        if not query_result.get("success"):
            raise ValueError("Query execution failed")

        # Generate chart from query results
        chart_spec = await self.chart_service.generate_chart_spec(
            data=query_result.get("data", []),
            chart_type=task.chart_config.get("type", "bar"),
            title=task.chart_config.get("title", task.name),
            x_axis=task.chart_config.get("x_axis"),
            y_axis=task.chart_config.get("y_axis"),
        )

        # Save chart
        chart = await self.chart_service.save_chart(
            tenant_id=task.tenant_id,
            name=f"{task.name} - {datetime.now(UTC).isoformat()}",
            chart_type=task.chart_config.get("type", "bar"),
            chart_spec=chart_spec,
            query=task.query,
            database_connection_id=task.database_connection_id,
        )

        return {"success": True, "chart_id": chart.id, "query_result": query_result}
