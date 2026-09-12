"""Tests for MCP servers controller."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from src.controllers.mcp_servers import router
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id


def setup_db_execute_mock(mock_db, return_value, return_list=False):
    """Helper to mock async db.execute() pattern."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = return_value
    if return_list:
        mock_result.scalars.return_value.all.return_value = return_value if return_value else []
    else:
        mock_result.scalars.return_value.all.return_value = [return_value] if return_value else []
    mock_result.scalars.return_value.first.return_value = return_value
    mock_db.execute = AsyncMock(return_value=mock_result)
    return mock_result


@pytest.fixture
def mock_db_session():
    db = AsyncMock()
    db.add = MagicMock()
    db.delete = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.fixture
def client(mock_db_session):
    app = FastAPI()
    app.include_router(router)

    _tenant_id = uuid.uuid4()

    # Mock dependencies
    async def mock_db():
        yield mock_db_session

    def mock_tenant_id():
        return _tenant_id

    app.dependency_overrides[get_async_db] = mock_db
    app.dependency_overrides[get_current_tenant_id] = mock_tenant_id

    return TestClient(app), mock_db_session


def _create_mock_mcp_server(server_id, tenant_id, **kwargs):
    """Helper to create mock MCP server."""
    mock_server = MagicMock()
    mock_server.id = server_id
    mock_server.tenant_id = tenant_id
    mock_server.name = kwargs.get("name", "Test MCP Server")
    mock_server.url = kwargs.get("url", "http://localhost:8080")
    mock_server.description = kwargs.get("description", "Test server")
    mock_server.transport_type = kwargs.get("transport_type", "http")
    mock_server.command = kwargs.get("command")
    mock_server.args = kwargs.get("args", [])
    mock_server.env_vars = kwargs.get("env_vars", {})
    mock_server.server_type = kwargs.get("server_type", "http")
    mock_server.auth_type = kwargs.get("auth_type", "none")
    mock_server.auth_config = kwargs.get("auth_config", {})
    mock_server.headers = kwargs.get("headers", {})
    mock_server.capabilities = kwargs.get("capabilities", {})
    mock_server.server_metadata = kwargs.get("server_metadata", {})
    mock_server.status = kwargs.get("status", "ACTIVE")
    mock_server.created_at = datetime.now(UTC)
    mock_server.updated_at = datetime.now(UTC)

    mock_server.to_dict = MagicMock(
        return_value={
            "id": str(server_id),
            "tenant_id": str(tenant_id),
            "name": mock_server.name,
            "url": mock_server.url,
            "description": mock_server.description,
            "transport_type": mock_server.transport_type,
            "command": mock_server.command,
            "args": mock_server.args,
            "env_vars": mock_server.env_vars,
            "server_type": mock_server.server_type,
            "auth_type": mock_server.auth_type,
            "auth_config": mock_server.auth_config,
            "headers": mock_server.headers,
            "capabilities": mock_server.capabilities,
            "server_metadata": mock_server.server_metadata,
            "status": mock_server.status,
        }
    )
    return mock_server


class TestListMCPServers:
    """Tests for listing MCP servers."""

    def test_list_servers_success(self, client):
        """Test listing all MCP servers."""
        test_client, mock_db = client

        server_id = uuid.uuid4()
        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
        mock_server = _create_mock_mcp_server(server_id, tenant_id)

        setup_db_execute_mock(mock_db, [mock_server], return_list=True)

        response = test_client.get("/api/v1/mcp/servers")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "servers" in data["data"]

    def test_list_servers_filter_by_status(self, client):
        """Test listing servers filtered by status."""
        test_client, mock_db = client

        setup_db_execute_mock(mock_db, [], return_list=True)

        response = test_client.get("/api/v1/mcp/servers?status=ACTIVE")

        assert response.status_code == status.HTTP_200_OK

    def test_list_servers_empty(self, client):
        """Test listing when no servers exist."""
        test_client, mock_db = client

        setup_db_execute_mock(mock_db, [], return_list=True)

        response = test_client.get("/api/v1/mcp/servers")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"]["total"] == 0


class TestGetMCPServer:
    """Tests for getting a specific MCP server."""

    def test_get_server_success(self, client):
        """Test getting a specific server."""
        test_client, mock_db = client

        server_id = uuid.uuid4()
        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
        mock_server = _create_mock_mcp_server(server_id, tenant_id)

        setup_db_execute_mock(mock_db, mock_server)

        response = test_client.get(f"/api/v1/mcp/servers/{server_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True

    def test_get_server_not_found(self, client):
        """Test getting non-existent server."""
        test_client, mock_db = client

        setup_db_execute_mock(mock_db, None)

        response = test_client.get(f"/api/v1/mcp/servers/{uuid.uuid4()}")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_server_invalid_id(self, client):
        """Test getting server with invalid ID."""
        test_client, mock_db = client

        response = test_client.get("/api/v1/mcp/servers/invalid-id")

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestCreateMCPServer:
    """Tests for creating MCP servers."""

    def test_create_http_server_success(self, client):
        """Test creating an HTTP MCP server."""
        test_client, mock_db = client

        server_id = uuid.uuid4()
        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
        mock_server = _create_mock_mcp_server(server_id, tenant_id)

        # Return the mock server after refresh
        def mock_add(server):
            server.id = server_id
            server.to_dict = mock_server.to_dict

        mock_db.add.side_effect = mock_add

        response = test_client.post(
            "/api/v1/mcp/servers",
            json={
                "name": "Test Server",
                "url": "http://localhost:8080",
                "description": "Test MCP server",
                "transport_type": "http",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True

    def test_create_stdio_server_rejected(self, client):
        """Test creating a stdio MCP server."""
        test_client, mock_db = client

        server_id = uuid.uuid4()
        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
        mock_server = _create_mock_mcp_server(
            server_id, tenant_id, transport_type="stdio", command="/usr/bin/mcp-server"
        )

        def mock_add(server):
            server.id = server_id
            server.to_dict = mock_server.to_dict

        mock_db.add.side_effect = mock_add

        response = test_client.post(
            "/api/v1/mcp/servers",
            json={
                "name": "Stdio Server",
                "description": "Test stdio server",
                "transport_type": "stdio",
                "command": "/usr/bin/mcp-server",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        mock_db.add.assert_not_called()

    def test_create_http_server_missing_url(self, client):
        """Test creating HTTP server without URL."""
        test_client, mock_db = client

        response = test_client.post(
            "/api/v1/mcp/servers", json={"name": "Test Server", "description": "Test", "transport_type": "http"}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_stdio_server_missing_command(self, client):
        """Test creating stdio server without command."""
        test_client, mock_db = client

        response = test_client.post(
            "/api/v1/mcp/servers", json={"name": "Test Server", "description": "Test", "transport_type": "stdio"}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_server_invalid_transport_type(self, client):
        """Test creating server with invalid transport type."""
        test_client, mock_db = client

        response = test_client.post(
            "/api/v1/mcp/servers", json={"name": "Test Server", "description": "Test", "transport_type": "invalid"}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestUpdateMCPServer:
    """Tests for updating MCP servers."""

    def test_update_server_success(self, client):
        """Test updating a server."""
        test_client, mock_db = client

        server_id = uuid.uuid4()
        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
        mock_server = _create_mock_mcp_server(server_id, tenant_id)

        setup_db_execute_mock(mock_db, mock_server)

        response = test_client.put(f"/api/v1/mcp/servers/{server_id}", json={"name": "Updated Server Name"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True

    def test_update_server_not_found(self, client):
        """Test updating non-existent server."""
        test_client, mock_db = client

        setup_db_execute_mock(mock_db, None)

        response = test_client.put(f"/api/v1/mcp/servers/{uuid.uuid4()}", json={"name": "Updated"})

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_server_change_transport_type(self, client):
        """Test changing server transport type with validation."""
        test_client, mock_db = client

        server_id = uuid.uuid4()
        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
        mock_server = _create_mock_mcp_server(server_id, tenant_id, transport_type="http")

        setup_db_execute_mock(mock_db, mock_server)

        # Try to change to stdio without command
        response = test_client.put(f"/api/v1/mcp/servers/{server_id}", json={"transport_type": "stdio"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestDeleteMCPServer:
    """Tests for deleting MCP servers."""

    def test_delete_server_success(self, client):
        """Test deleting a server."""
        test_client, mock_db = client

        server_id = uuid.uuid4()
        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
        mock_server = _create_mock_mcp_server(server_id, tenant_id)

        setup_db_execute_mock(mock_db, mock_server)

        response = test_client.delete(f"/api/v1/mcp/servers/{server_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True

    def test_delete_server_not_found(self, client):
        """Test deleting non-existent server."""
        test_client, mock_db = client

        setup_db_execute_mock(mock_db, None)

        response = test_client.delete(f"/api/v1/mcp/servers/{uuid.uuid4()}")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestTestMCPServer:
    """Tests for testing MCP server connections."""

    def test_test_server_success(self, client):
        """Test testing a server connection."""
        test_client, mock_db = client

        server_id = uuid.uuid4()
        tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
        mock_server = _create_mock_mcp_server(server_id, tenant_id)

        setup_db_execute_mock(mock_db, mock_server)

        with patch("src.services.mcp.mcp_client.MCPClient") as factory:
            factory.return_value.__aenter__ = AsyncMock(return_value=factory.return_value)
            factory.return_value.__aexit__ = AsyncMock()
            factory.return_value.discover_tools = AsyncMock(return_value=[])
            response = test_client.post(f"/api/v1/mcp/servers/{server_id}/test")
            factory.return_value.discover_tools.assert_awaited_once()

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "connected"

    def test_test_server_not_found(self, client):
        """Test testing non-existent server."""
        test_client, mock_db = client

        setup_db_execute_mock(mock_db, None)

        response = test_client.post(f"/api/v1/mcp/servers/{uuid.uuid4()}/test")

        assert response.status_code == status.HTTP_404_NOT_FOUND
