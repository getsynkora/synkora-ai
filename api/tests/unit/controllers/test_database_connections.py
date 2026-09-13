"""Tests for database connections controller."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from src.controllers.database_connections import router
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.models.database_connection import DatabaseConnectionType


@pytest.fixture
def mock_db_session():
    db = AsyncMock()
    db.add = MagicMock()  # add is sync, not async
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.flush = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.fixture
def client(mock_db_session):
    app = FastAPI()
    app.include_router(router)

    # Mock dependencies
    async def mock_db():
        yield mock_db_session

    app.dependency_overrides[get_async_db] = mock_db

    # Mock current account
    mock_account = MagicMock()
    mock_account.id = uuid.uuid4()
    app.dependency_overrides[get_current_account] = lambda: mock_account

    # Mock tenant ID
    tenant_id = uuid.uuid4()
    app.dependency_overrides[get_current_tenant_id] = lambda: tenant_id

    return TestClient(app), tenant_id, mock_account, mock_db_session


def _create_mock_connection(conn_id, tenant_id, **kwargs):
    """Helper to create mock database connection."""
    mock_conn = MagicMock()
    mock_conn.id = conn_id
    mock_conn.tenant_id = tenant_id
    mock_conn.name = kwargs.get("name", "Test Connection")
    mock_conn.database_type = kwargs.get("database_type", DatabaseConnectionType.POSTGRESQL)
    mock_conn.host = kwargs.get("host", "localhost")
    mock_conn.port = kwargs.get("port", 5432)
    mock_conn.database_name = kwargs.get("database_name", "testdb")
    mock_conn.username = kwargs.get("username", "testuser")
    mock_conn.database_path = kwargs.get("database_path")
    mock_conn.connection_params = kwargs.get("connection_params", {})
    mock_conn.get_safe_connection_params.return_value = kwargs.get("connection_params", {})
    mock_conn.status = kwargs.get("status", "active")
    mock_conn.created_at = datetime.now(UTC)
    mock_conn.updated_at = datetime.now(UTC)
    return mock_conn


class TestCreateDatabaseConnection:
    """Tests for creating database connections."""

    def test_create_postgresql_connection_success(self, client):
        """Test successful PostgreSQL connection creation."""
        test_client, tenant_id, mock_account, mock_db = client

        conn_id = uuid.uuid4()

        def mock_add(conn):
            conn.id = conn_id
            conn.created_at = datetime.now(UTC)
            conn.updated_at = datetime.now(UTC)
            conn.status = "pending"

        mock_db.add.side_effect = mock_add

        with patch("src.controllers.database_connections.PostgreSQLConnector") as mock_connector_cls:
            mock_connector = mock_connector_cls.return_value
            mock_connector.test_connection = AsyncMock(return_value={"success": True})

            response = test_client.post(
                "/api/v1/database-connections",
                json={
                    "name": "Test PostgreSQL",
                    "type": "POSTGRESQL",
                    "host": "localhost",
                    "port": 5432,
                    "database": "testdb",
                    "username": "testuser",
                    "password": "testpass",
                },
            )

            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["name"] == "Test PostgreSQL"

    def test_create_sqlite_connection_success(self, client):
        """Test successful SQLite connection creation."""
        test_client, tenant_id, mock_account, mock_db = client

        conn_id = uuid.uuid4()

        def mock_add(conn):
            conn.id = conn_id
            conn.created_at = datetime.now(UTC)
            conn.updated_at = datetime.now(UTC)
            conn.status = "pending"

        mock_db.add.side_effect = mock_add

        with patch("src.controllers.database_connections.SQLiteConnector") as mock_connector_cls:
            mock_connector = mock_connector_cls.return_value
            mock_connector.test_connection = AsyncMock(return_value={"success": True})

            response = test_client.post(
                "/api/v1/database-connections",
                json={"name": "Test SQLite", "type": "SQLITE", "database_path": "/path/to/db.sqlite"},
            )

            assert response.status_code == status.HTTP_201_CREATED

    def test_create_postgresql_missing_credentials(self, client):
        """Test PostgreSQL creation without required credentials."""
        test_client, tenant_id, mock_account, mock_db = client

        response = test_client.post(
            "/api/v1/database-connections",
            json={"name": "Test PostgreSQL", "type": "POSTGRESQL", "host": "localhost", "port": 5432},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_sqlite_missing_path(self, client):
        """Test SQLite creation without database path."""
        test_client, tenant_id, mock_account, mock_db = client

        response = test_client.post("/api/v1/database-connections", json={"name": "Test SQLite", "type": "SQLITE"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestListDatabaseConnections:
    """Tests for listing database connections."""

    def test_list_connections_success(self, client):
        """Test listing all database connections."""
        test_client, tenant_id, mock_account, mock_db = client

        conn_id = uuid.uuid4()
        mock_conn = _create_mock_connection(conn_id, tenant_id)

        # Endpoint is paginated: one query for the total count, one for the page.
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1
        mock_result.scalars.return_value.all.return_value = [mock_conn]
        mock_db.execute.return_value = mock_result

        response = test_client.get("/api/v1/database-connections")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data["items"], list)
        assert data["total"] == 1
        assert len(data["items"]) == 1

    def test_list_connections_empty(self, client):
        """Test listing when no connections exist."""
        test_client, tenant_id, mock_account, mock_db = client

        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        response = test_client.get("/api/v1/database-connections")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0


class TestGetDatabaseConnection:
    """Tests for getting a specific database connection."""

    def test_get_connection_success(self, client):
        """Test getting a specific connection."""
        test_client, tenant_id, mock_account, mock_db = client

        conn_id = uuid.uuid4()
        mock_conn = _create_mock_connection(conn_id, tenant_id)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_conn
        mock_db.execute.return_value = mock_result

        response = test_client.get(f"/api/v1/database-connections/{conn_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == str(conn_id)

    def test_get_connection_not_found(self, client):
        """Test getting non-existent connection."""
        test_client, tenant_id, mock_account, mock_db = client

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        response = test_client.get(f"/api/v1/database-connections/{uuid.uuid4()}")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestUpdateDatabaseConnection:
    """Tests for updating database connections."""

    def test_update_connection_success(self, client):
        """Test updating a connection."""
        test_client, tenant_id, mock_account, mock_db = client

        conn_id = uuid.uuid4()
        mock_conn = _create_mock_connection(conn_id, tenant_id)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_conn
        mock_db.execute.return_value = mock_result

        response = test_client.put(f"/api/v1/database-connections/{conn_id}", json={"name": "Updated Connection"})

        assert response.status_code == status.HTTP_200_OK
        mock_db.commit.assert_called()

    def test_update_connection_not_found(self, client):
        """Test updating non-existent connection."""
        test_client, tenant_id, mock_account, mock_db = client

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        response = test_client.put(f"/api/v1/database-connections/{uuid.uuid4()}", json={"name": "Updated"})

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestDeleteDatabaseConnection:
    """Tests for deleting database connections."""

    def test_delete_connection_success(self, client):
        """Test deleting a connection."""
        test_client, tenant_id, mock_account, mock_db = client

        conn_id = uuid.uuid4()
        mock_conn = _create_mock_connection(conn_id, tenant_id)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_conn
        mock_db.execute.return_value = mock_result

        response = test_client.delete(f"/api/v1/database-connections/{conn_id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        mock_db.delete.assert_called_once()

    def test_delete_connection_not_found(self, client):
        """Test deleting non-existent connection."""
        test_client, tenant_id, mock_account, mock_db = client

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        response = test_client.delete(f"/api/v1/database-connections/{uuid.uuid4()}")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestTestDatabaseConnection:
    """Tests for testing database connections."""

    def test_test_new_connection_success(self, client):
        """Test testing a new connection configuration."""
        test_client, tenant_id, mock_account, mock_db = client

        with patch("src.controllers.database_connections.PostgreSQLConnector") as mock_connector_cls:
            mock_connector = mock_connector_cls.return_value
            mock_connector.test_connection = AsyncMock(return_value={"success": True, "message": "Connected"})

            response = test_client.post(
                "/api/v1/database-connections/test",
                json={
                    "name": "Test",
                    "type": "POSTGRESQL",
                    "host": "localhost",
                    "port": 5432,
                    "database": "testdb",
                    "username": "testuser",
                    "password": "testpass",
                },
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True

    def test_test_new_connection_failed(self, client):
        """Test testing a connection that fails."""
        test_client, tenant_id, mock_account, mock_db = client

        with patch("src.controllers.database_connections.PostgreSQLConnector") as mock_connector_cls:
            mock_connector = mock_connector_cls.return_value
            mock_connector.test_connection = AsyncMock(side_effect=Exception("Connection refused"))

            response = test_client.post(
                "/api/v1/database-connections/test",
                json={
                    "name": "Test",
                    "type": "POSTGRESQL",
                    "host": "localhost",
                    "port": 5432,
                    "database": "testdb",
                    "username": "testuser",
                    "password": "wrongpass",
                },
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is False

    def test_test_existing_connection_success(self, client):
        """Test testing an existing connection."""
        test_client, tenant_id, mock_account, mock_db = client

        conn_id = uuid.uuid4()
        mock_conn = _create_mock_connection(conn_id, tenant_id)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_conn
        mock_db.execute.return_value = mock_result

        with patch("src.controllers.database_connections.PostgreSQLConnector") as mock_connector_cls:
            mock_connector = mock_connector_cls.return_value
            mock_connector.test_connection = AsyncMock(
                return_value={"success": True, "message": "Connection successful"}
            )

            response = test_client.post(f"/api/v1/database-connections/{conn_id}/test")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True

    def test_test_existing_connection_not_found(self, client):
        """Test testing non-existent connection."""
        test_client, tenant_id, mock_account, mock_db = client

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        response = test_client.post(f"/api/v1/database-connections/{uuid.uuid4()}/test")

        assert response.status_code == status.HTTP_404_NOT_FOUND
