"""
Database Connections Controller.

Handles HTTP requests for managing database connections.
"""

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.core.errors import safe_error_message
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.models import Account
from src.models.database_connection import DatabaseConnection, DatabaseConnectionType
from src.schemas.base import StrictModel
from src.services.database import (
    BigQueryConnector,
    ClickHouseConnector,
    DatabricksConnector,
    DatadogConnector,
    DockerConnector,
    DuckDBConnector,
    ElasticsearchConnector,
    MongoDBConnector,
    MySQLConnector,
    PostgreSQLConnector,
    SnowflakeConnector,
    SQLiteConnector,
    SQLServerConnector,
    SupabaseConnector,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/database-connections", tags=["database-connections"])


async def _audit_log(
    db: AsyncSession,
    account_id: UUID,
    tenant_id: UUID,
    action: str,
    resource_type: str,
    resource_id: UUID | None = None,
    metadata: dict | None = None,
) -> None:
    """Fire-and-forget audit log — never raises, never blocks the main response."""
    try:
        from src.services.activity.activity_log_service import ActivityLogService

        ActivityLogService.queue_activity(
            tenant_id=tenant_id,
            account_id=account_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=metadata or {},
        )
    except Exception:
        pass  # Audit logging must never break the main flow


def _make_connector(db_type: DatabaseConnectionType, connection: "DatabaseConnection"):
    """Return the right connector instance for *db_type*, or None if unsupported."""
    match db_type:
        case DatabaseConnectionType.POSTGRESQL:
            return PostgreSQLConnector(database_connection=connection)
        case DatabaseConnectionType.SUPABASE:
            return SupabaseConnector(database_connection=connection)
        case DatabaseConnectionType.MYSQL:
            return MySQLConnector(database_connection=connection)
        case DatabaseConnectionType.MONGODB:
            return MongoDBConnector(database_connection=connection)
        case DatabaseConnectionType.SQLITE:
            return SQLiteConnector(database_path=connection.database_path)
        case DatabaseConnectionType.ELASTICSEARCH:
            return ElasticsearchConnector(database_connection=connection)
        case DatabaseConnectionType.BIGQUERY:
            return BigQueryConnector(database_connection=connection)
        case DatabaseConnectionType.SNOWFLAKE:
            return SnowflakeConnector(database_connection=connection)
        case DatabaseConnectionType.SQLSERVER:
            return SQLServerConnector(database_connection=connection)
        case DatabaseConnectionType.CLICKHOUSE:
            return ClickHouseConnector(database_connection=connection)
        case DatabaseConnectionType.DUCKDB:
            return DuckDBConnector(database_connection=connection)
        case DatabaseConnectionType.DATADOG:
            return DatadogConnector(database_connection=connection)
        case DatabaseConnectionType.DATABRICKS:
            return DatabricksConnector(database_connection=connection)
        case DatabaseConnectionType.DOCKER:
            return DockerConnector(database_connection=connection)
        case _:
            return None


# Request/Response Models
class DatabaseConnectionCreate(StrictModel):
    """Request model for creating a database connection."""

    name: str = Field(..., min_length=1, max_length=255)
    type: DatabaseConnectionType
    host: str | None = None
    port: int | None = Field(None, ge=1, lt=65536)
    database: str | None = None
    username: str | None = None
    password: str | None = None
    database_path: str | None = None
    connection_params: dict[str, Any] | None = None

    @field_validator("host", "database", "username", "password")
    @classmethod
    def validate_non_sqlite_fields(cls, v, info):
        """Validate that non-SQLite fields are provided for non-SQLite connections."""
        # This will be checked in the endpoint logic
        return v

    @field_validator("database_path")
    @classmethod
    def validate_sqlite_path(cls, v, info):
        """Validate that database_path is provided for SQLite connections."""
        # This will be checked in the endpoint logic
        return v


class DatabaseConnectionUpdate(StrictModel):
    """Request model for updating a database connection."""

    name: str | None = Field(None, min_length=1, max_length=255)
    host: str | None = None
    port: int | None = Field(None, ge=1, lt=65536)
    database: str | None = None
    username: str | None = None
    password: str | None = None
    database_path: str | None = None
    connection_params: dict[str, Any] | None = None
    status: str | None = Field(None, pattern="^(active|pending|error|inactive)$")


class DatabaseConnectionResponse(BaseModel):
    """Response model for database connection."""

    id: str
    tenant_id: str
    name: str
    type: str
    host: str | None
    port: int | None
    database: str | None
    username: str | None
    database_path: str | None
    connection_params: dict[str, Any] | None
    status: str
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


class ConnectionTestResponse(BaseModel):
    """Response model for connection test."""

    success: bool
    message: str
    details: dict[str, Any] | None = None


@router.post("", response_model=DatabaseConnectionResponse, status_code=status.HTTP_201_CREATED)
async def create_database_connection(
    connection_data: DatabaseConnectionCreate,
    db: AsyncSession = Depends(get_async_db),
    current_account: Account = Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
) -> DatabaseConnectionResponse:
    """
    Create a new database connection.

    Args:
        connection_data: Database connection details
        db: Database session
        current_account: Authenticated user
        tenant_id: Current tenant ID

    Returns:
        Created database connection
    """
    try:
        # Validate required fields based on database type
        if connection_data.type == DatabaseConnectionType.SQLITE:
            if not connection_data.database_path:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="database_path is required for SQLite connections"
                )
        elif connection_data.type == DatabaseConnectionType.DUCKDB:
            # DuckDB is in-process — no host/port needed.
            # database_path may be ':memory:' (default) or a file path.
            pass  # all configurations valid; connector defaults to :memory:
        elif connection_data.type == DatabaseConnectionType.DATADOG:
            if not connection_data.password:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="API key (password) is required for Datadog"
                )
            if not connection_data.username:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Application key (username) is required for Datadog"
                )
            if not connection_data.host:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Site (host) is required for Datadog"
                )
        elif connection_data.type == DatabaseConnectionType.DATABRICKS:
            if not connection_data.host:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Server hostname (host) is required for Databricks"
                )
            if not connection_data.database_path:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="HTTP path (database_path) is required for Databricks",
                )
            if not connection_data.password:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Access token (password) is required for Databricks"
                )
        elif connection_data.type == DatabaseConnectionType.BIGQUERY:
            if not connection_data.connection_params or not connection_data.connection_params.get(
                "service_account_json"
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="connection_params.service_account_json is required for BigQuery",
                )
        elif connection_data.type == DatabaseConnectionType.DOCKER:
            if not connection_data.host:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Docker host is required")
        elif connection_data.type == DatabaseConnectionType.SUPABASE:
            if not connection_data.host or not connection_data.username or not connection_data.password:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Project URL (host), Anon Key (username) and Service Role Key (password) are required for Supabase",
                )
        else:
            if not connection_data.host or not connection_data.port:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="host and port are required for non-SQLite connections",
                )
            # For Elasticsearch, credentials are optional (only needed if security is enabled)
            # For PostgreSQL/MySQL/MongoDB, credentials are required
            if connection_data.type != DatabaseConnectionType.ELASTICSEARCH:
                if not connection_data.database:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="database is required for non-SQLite connections",
                    )
                if not connection_data.username or not connection_data.password:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="username and password are required for non-SQLite connections",
                    )

        # Create database connection
        connection = DatabaseConnection(
            tenant_id=tenant_id,
            name=connection_data.name,
            database_type=connection_data.type,
            host=connection_data.host or "",
            port=connection_data.port or 0,
            database_name=connection_data.database or "",
            username=connection_data.username or "",
            database_path=connection_data.database_path,
        )
        connection.connection_params = connection_data.connection_params or {}

        # Set encrypted password if provided
        if connection_data.password:
            connection.set_password(connection_data.password)

        # Set initial status
        connection.status = "pending"

        db.add(connection)
        await db.commit()
        await db.refresh(connection)

        logger.info(f"Created database connection: {connection.id}")
        await _audit_log(
            db,
            current_account.id,
            tenant_id,
            "create",
            "database_connection",
            resource_id=connection.id,
            metadata={"name": connection.name, "type": str(connection.database_type)},
        )

        # Automatically test the connection and update status
        try:
            connector = _make_connector(connection.database_type, connection)
            if connector is not None:
                test_result = await connector.test_connection()
            else:
                test_result = {"success": False}

            # Update status based on test result
            if test_result.get("success"):
                connection.status = "active"
            else:
                connection.status = "error"

            await db.commit()
            await db.refresh(connection)

        except Exception as e:
            logger.warning(f"Auto-test failed for connection {connection.id}: {e}")
            # Keep status as "pending" if auto-test fails

        return DatabaseConnectionResponse(
            id=str(connection.id),
            tenant_id=str(connection.tenant_id),
            name=connection.name,
            type=connection.database_type.value
            if isinstance(connection.database_type, DatabaseConnectionType)
            else connection.database_type,
            host=connection.host if connection.host else None,
            port=connection.port if connection.port else None,
            database=connection.database_name if connection.database_name else None,
            username=connection.username if connection.username else None,
            database_path=connection.database_path,
            connection_params=connection.get_safe_connection_params(),
            status=connection.status,
            created_at=connection.created_at.isoformat(),
            updated_at=connection.updated_at.isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating database connection: {e}", exc_info=True)
        await db.rollback()
        # SECURITY: Don't expose internal error details
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=safe_error_message(e, "Failed to create database connection", include_type=True),
        )


@router.get("", response_model=list[DatabaseConnectionResponse])
async def list_database_connections(
    db: AsyncSession = Depends(get_async_db),
    current_account: Account = Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
) -> list[DatabaseConnectionResponse]:
    """
    List all database connections for the current tenant.

    Args:
        db: Database session
        current_account: Authenticated user
        tenant_id: Current tenant ID

    Returns:
        List of database connections
    """
    try:
        stmt = (
            select(DatabaseConnection)
            .where(DatabaseConnection.tenant_id == tenant_id)
            .order_by(DatabaseConnection.created_at.desc())
        )

        result = await db.execute(stmt)
        connections = result.scalars().all()

        return [
            DatabaseConnectionResponse(
                id=str(conn.id),
                tenant_id=str(conn.tenant_id),
                name=conn.name,
                type=conn.database_type.value
                if isinstance(conn.database_type, DatabaseConnectionType)
                else conn.database_type,
                host=conn.host if conn.host else None,
                port=conn.port if conn.port else None,
                database=conn.database_name if conn.database_name else None,
                username=conn.username if conn.username else None,
                database_path=conn.database_path,
                connection_params=conn.get_safe_connection_params(),
                status=conn.status,
                created_at=conn.created_at.isoformat(),
                updated_at=conn.updated_at.isoformat(),
            )
            for conn in connections
        ]

    except Exception as e:
        logger.error(f"Error listing database connections: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=safe_error_message(e, "Failed to list database connections", include_type=True),
        )


@router.get("/{connection_id}", response_model=DatabaseConnectionResponse)
async def get_database_connection(
    connection_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_account: Account = Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
) -> DatabaseConnectionResponse:
    """
    Get a specific database connection.

    Args:
        connection_id: Database connection ID
        db: Database session
        current_account: Authenticated user
        tenant_id: Current tenant ID

    Returns:
        Database connection details
    """
    try:
        stmt = select(DatabaseConnection).where(
            DatabaseConnection.id == connection_id, DatabaseConnection.tenant_id == tenant_id
        )

        result = await db.execute(stmt)
        connection = result.scalar_one_or_none()

        if not connection:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database connection not found")

        return DatabaseConnectionResponse(
            id=str(connection.id),
            tenant_id=str(connection.tenant_id),
            name=connection.name,
            type=connection.database_type.value
            if isinstance(connection.database_type, DatabaseConnectionType)
            else connection.database_type,
            host=connection.host if connection.host else None,
            port=connection.port if connection.port else None,
            database=connection.database_name if connection.database_name else None,
            username=connection.username if connection.username else None,
            database_path=connection.database_path,
            connection_params=connection.get_safe_connection_params(),
            status=connection.status,
            created_at=connection.created_at.isoformat(),
            updated_at=connection.updated_at.isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting database connection: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=safe_error_message(e, "Failed to get database connection", include_type=True),
        )


@router.put("/{connection_id}", response_model=DatabaseConnectionResponse)
async def update_database_connection(
    connection_id: UUID,
    connection_data: DatabaseConnectionUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_account: Account = Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
) -> DatabaseConnectionResponse:
    """
    Update a database connection.

    Args:
        connection_id: Database connection ID
        connection_data: Updated connection details
        db: Database session
        current_account: Authenticated user
        tenant_id: Current tenant ID

    Returns:
        Updated database connection
    """
    try:
        stmt = select(DatabaseConnection).where(
            DatabaseConnection.id == connection_id, DatabaseConnection.tenant_id == tenant_id
        )

        result = await db.execute(stmt)
        connection = result.scalar_one_or_none()

        if not connection:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database connection not found")

        # Update fields
        if connection_data.name is not None:
            connection.name = connection_data.name
        if connection_data.host is not None:
            connection.host = connection_data.host
        if connection_data.port is not None:
            connection.port = connection_data.port
        if connection_data.database is not None:
            connection.database_name = connection_data.database
        if connection_data.username is not None:
            connection.username = connection_data.username
        if connection_data.password is not None:
            connection.set_password(connection_data.password)
        if connection_data.database_path is not None:
            connection.database_path = connection_data.database_path
        if connection_data.connection_params is not None:
            # Merge: keep existing sensitive values unless caller explicitly replaces them
            existing = connection.connection_params  # decrypted via property getter
            connection.connection_params = {**existing, **connection_data.connection_params}

        # Update status if provided, otherwise reset to pending if connection details changed
        if connection_data.status is not None:
            connection.status = connection_data.status
        elif any(
            [
                connection_data.host,
                connection_data.port,
                connection_data.database,
                connection_data.username,
                connection_data.password,
                connection_data.database_path,
            ]
        ):
            connection.status = "pending"

        await db.commit()
        await db.refresh(connection)

        logger.info(f"Updated database connection: {connection.id}")
        await _audit_log(
            db,
            current_account.id,
            tenant_id,
            "update",
            "database_connection",
            resource_id=connection.id,
            metadata={"name": connection.name},
        )

        return DatabaseConnectionResponse(
            id=str(connection.id),
            tenant_id=str(connection.tenant_id),
            name=connection.name,
            type=connection.database_type.value
            if isinstance(connection.database_type, DatabaseConnectionType)
            else connection.database_type,
            host=connection.host if connection.host else None,
            port=connection.port if connection.port else None,
            database=connection.database_name if connection.database_name else None,
            username=connection.username if connection.username else None,
            database_path=connection.database_path,
            connection_params=connection.get_safe_connection_params(),
            status=connection.status,
            created_at=connection.created_at.isoformat(),
            updated_at=connection.updated_at.isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating database connection: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=safe_error_message(e, "Failed to update database connection", include_type=True),
        )


@router.post("/test", response_model=ConnectionTestResponse)
async def test_database_connection(
    connection_data: DatabaseConnectionCreate,
    db: AsyncSession = Depends(get_async_db),
    current_account: Account = Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
) -> ConnectionTestResponse:
    """
    Test a database connection without saving it.

    Args:
        connection_data: Database connection details to test
        db: Database session
        current_account: Authenticated user
        tenant_id: Current tenant ID

    Returns:
        Connection test result
    """
    try:
        # Validate required fields per connector type
        if connection_data.type == DatabaseConnectionType.SQLITE:
            if not connection_data.database_path:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="database_path is required for SQLite connections",
                )
        elif connection_data.type == DatabaseConnectionType.BIGQUERY:
            # BigQuery uses service_account_json in connection_params, not host/port
            if not connection_data.connection_params or not connection_data.connection_params.get(
                "service_account_json"
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="connection_params.service_account_json is required for BigQuery",
                )
        elif connection_data.type == DatabaseConnectionType.DATADOG:
            if not connection_data.password:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="API key (password) is required for Datadog"
                )
            if not connection_data.host:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Site (host) is required for Datadog"
                )
        elif connection_data.type == DatabaseConnectionType.DATABRICKS:
            if not connection_data.host:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Server hostname (host) is required for Databricks"
                )
            if not connection_data.database_path:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="HTTP path (database_path) is required for Databricks",
                )
            if not connection_data.password:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Access token (password) is required for Databricks"
                )
        elif connection_data.type == DatabaseConnectionType.DOCKER:
            if not connection_data.host:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Docker host is required")
        elif connection_data.type == DatabaseConnectionType.SUPABASE:
            if not connection_data.host or not connection_data.username or not connection_data.password:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Project URL (host), Anon Key (username) and Service Role Key (password) are required for Supabase",
                )
        elif connection_data.type != DatabaseConnectionType.ELASTICSEARCH:
            if not connection_data.host or not connection_data.port:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="host and port are required for this connection type",
                )

        # Build a transient DatabaseConnection for testing (never persisted)
        temp_connection = DatabaseConnection(
            tenant_id=tenant_id,
            name="temp_test",
            database_type=connection_data.type,
            host=connection_data.host or "",
            port=connection_data.port or 0,
            database_name=connection_data.database or "",
            username=connection_data.username or "",
            database_path=connection_data.database_path,
        )
        temp_connection.connection_params = connection_data.connection_params or {}
        if connection_data.password:
            temp_connection.set_password(connection_data.password)

        connector = _make_connector(connection_data.type, temp_connection)
        if connector is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported database type: {connection_data.type}",
            )

        test_result = await connector.test_connection()
        if not test_result.get("success"):
            raise Exception(test_result.get("message", "Connection test failed"))

        return ConnectionTestResponse(
            success=True, message="Connection successful", details={"type": connection_data.type.value}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing database connection: {e}", exc_info=True)
        error_str = str(e).lower()
        if "authentication" in error_str or "password" in error_str:
            category = "authentication_failed"
        elif "timeout" in error_str or "timed out" in error_str:
            category = "connection_timeout"
        elif "refused" in error_str or "unreachable" in error_str:
            category = "host_unreachable"
        else:
            category = "connection_failed"
        return ConnectionTestResponse(
            success=False,
            message=f"Connection failed: {category}",
            details={"error_code": category},
        )


@router.post("/{connection_id}/test", response_model=ConnectionTestResponse)
async def test_existing_database_connection(
    connection_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_account: Account = Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
) -> ConnectionTestResponse:
    """
    Test an existing database connection.

    Args:
        connection_id: Database connection ID
        db: Database session
        current_account: Authenticated user
        tenant_id: Current tenant ID

    Returns:
        Connection test result
    """
    try:
        stmt = select(DatabaseConnection).where(
            DatabaseConnection.id == connection_id, DatabaseConnection.tenant_id == tenant_id
        )

        result = await db.execute(stmt)
        connection = result.scalar_one_or_none()

        if not connection:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database connection not found")

        # Test the connection based on type
        connector = _make_connector(connection.database_type, connection)
        if connector is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported database type: {connection.database_type}",
            )
        test_result = await connector.test_connection()

        # Update connection status based on test result
        if test_result["success"]:
            connection.status = "active"
        else:
            connection.status = "error"

        await db.commit()

        return ConnectionTestResponse(
            success=test_result["success"], message=test_result["message"], details=test_result.get("details")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing database connection: {e}", exc_info=True)
        error_str = str(e).lower()
        if "authentication" in error_str or "password" in error_str:
            category = "authentication_failed"
        elif "timeout" in error_str or "timed out" in error_str:
            category = "connection_timeout"
        elif "refused" in error_str or "unreachable" in error_str:
            category = "host_unreachable"
        else:
            category = "connection_failed"
        return ConnectionTestResponse(
            success=False,
            message=f"Connection test failed: {category}",
            details={"error_code": category},
        )


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_database_connection(
    connection_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_account: Account = Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
) -> None:
    """
    Delete a database connection.

    Args:
        connection_id: Database connection ID
        db: Database session
        current_account: Authenticated user
        tenant_id: Current tenant ID
    """
    try:
        stmt = select(DatabaseConnection).where(
            DatabaseConnection.id == connection_id, DatabaseConnection.tenant_id == tenant_id
        )

        result = await db.execute(stmt)
        connection = result.scalar_one_or_none()

        if not connection:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database connection not found")

        await db.delete(connection)
        await db.commit()

        logger.info(f"Deleted database connection: {connection_id}")
        await _audit_log(
            db,
            current_account.id,
            tenant_id,
            "delete",
            "database_connection",
            resource_id=connection_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting database connection: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=safe_error_message(e, "Failed to delete database connection", include_type=True),
        )
