"""
Integration tests for MCP Server management endpoints.

Tests CRUD operations for MCP (Model Context Protocol) servers.
"""

import uuid

import pytest
import pytest_asyncio
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture
async def auth_headers(async_client: AsyncClient, async_db_session: AsyncSession):
    """Create authenticated user and return headers with tenant info."""
    from src.models import Account, AccountStatus

    email = f"mcp_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecureTestPass123!"

    response = await async_client.post(
        "/console/api/auth/register",
        json={
            "email": email,
            "password": password,
            "name": "MCP Test User",
            "tenant_name": "MCP Test Org",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED

    result = await async_db_session.execute(select(Account).filter_by(email=email))
    account = result.scalar_one_or_none()
    account.status = AccountStatus.ACTIVE
    await async_db_session.commit()

    login_response = await async_client.post(
        "/console/api/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == status.HTTP_200_OK
    token = login_response.json()["data"]["access_token"]

    return {"Authorization": f"Bearer {token}"}


class TestMCPServersCRUDIntegration:
    """Test MCP Servers CRUD operations."""

    @pytest.mark.asyncio
    async def test_mcp_server_full_lifecycle(self, async_client: AsyncClient, auth_headers):
        """Test complete MCP server lifecycle: create -> get -> update -> delete."""
        server_name = f"TestMCPServer_{uuid.uuid4().hex[:8]}"

        # 1. Create MCP Server (HTTP type)
        create_response = await async_client.post(
            "/api/v1/mcp/servers",
            json={
                "name": server_name,
                "url": "https://mcp.example.com/api",
                "description": "Test MCP server for integration tests",
                "transport_type": "http",
                "server_type": "http",
                "auth_type": "none",
                "capabilities": {"tools": True, "prompts": True},
            },
            headers=auth_headers,
        )

        assert create_response.status_code == status.HTTP_200_OK
        create_data = create_response.json()
        assert create_data["success"] is True
        assert create_data["data"]["name"] == server_name
        server_id = create_data["data"]["id"]

        # 2. Get MCP Server
        get_response = await async_client.get(f"/api/v1/mcp/servers/{server_id}", headers=auth_headers)
        assert get_response.status_code == status.HTTP_200_OK
        get_data = get_response.json()
        assert get_data["success"] is True
        assert get_data["data"]["name"] == server_name
        assert get_data["data"]["transport_type"] == "http"

        # 3. List MCP Servers
        list_response = await async_client.get("/api/v1/mcp/servers", headers=auth_headers)
        assert list_response.status_code == status.HTTP_200_OK
        list_data = list_response.json()
        assert list_data["success"] is True
        server_ids = [s["id"] for s in list_data["data"]["servers"]]
        assert server_id in server_ids

        # 4. Update MCP Server
        update_response = await async_client.put(
            f"/api/v1/mcp/servers/{server_id}",
            json={
                "name": f"{server_name}_updated",
                "description": "Updated description",
            },
            headers=auth_headers,
        )
        assert update_response.status_code == status.HTTP_200_OK
        update_data = update_response.json()
        assert update_data["success"] is True
        assert update_data["data"]["name"] == f"{server_name}_updated"

        # 5. Delete MCP Server
        delete_response = await async_client.delete(f"/api/v1/mcp/servers/{server_id}", headers=auth_headers)
        assert delete_response.status_code in [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT]

        # Verify deletion
        verify_response = await async_client.get(f"/api/v1/mcp/servers/{server_id}", headers=auth_headers)
        assert verify_response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_create_stdio_mcp_server_is_rejected(self, async_client: AsyncClient, auth_headers):
        """stdio (command-based) MCP servers can no longer be created via the tenant
        API — SECURITY: tenant-supplied commands must not execute in the API
        process. Deploy them in an isolated runner behind an HTTP endpoint instead."""
        server_name = f"StdioMCPServer_{uuid.uuid4().hex[:8]}"

        response = await async_client.post(
            "/api/v1/mcp/servers",
            json={
                "name": server_name,
                "description": "Stdio MCP server",
                "transport_type": "stdio",
                "command": "npx",
                "args": ["-y", "@anthropics/mcp-server-example"],
                "env_vars": {"DEBUG": "true"},
                "server_type": "stdio",
                "auth_type": "none",
            },
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "isolated runner" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_stdio_server_without_command_fails(self, async_client: AsyncClient, auth_headers):
        """Test that creating stdio server without command fails."""
        response = await async_client.post(
            "/api/v1/mcp/servers",
            json={
                "name": f"NoCommandServer_{uuid.uuid4().hex[:8]}",
                "description": "Missing command",
                "transport_type": "stdio",
                # Missing 'command' field
                "server_type": "stdio",
                "auth_type": "none",
            },
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_create_http_server_without_url_fails(self, async_client: AsyncClient, auth_headers):
        """Test that creating http server without URL fails."""
        response = await async_client.post(
            "/api/v1/mcp/servers",
            json={
                "name": f"NoUrlServer_{uuid.uuid4().hex[:8]}",
                "description": "Missing URL",
                "transport_type": "http",
                # Missing 'url' field
                "server_type": "http",
                "auth_type": "none",
            },
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_get_nonexistent_server(self, async_client: AsyncClient, auth_headers):
        """Test getting a nonexistent server returns 404."""
        fake_id = str(uuid.uuid4())
        response = await async_client.get(f"/api/v1/mcp/servers/{fake_id}", headers=auth_headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_server_invalid_id(self, async_client: AsyncClient, auth_headers):
        """Test getting server with invalid ID format returns 400."""
        response = await async_client.get("/api/v1/mcp/servers/invalid-uuid-format", headers=auth_headers)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_list_servers_by_status(self, async_client: AsyncClient, auth_headers):
        """Test listing servers filtered by status."""
        # Create an active server
        create_response = await async_client.post(
            "/api/v1/mcp/servers",
            json={
                "name": f"ActiveServer_{uuid.uuid4().hex[:8]}",
                "url": "https://active.example.com",
                "description": "Active server",
                "transport_type": "http",
                "server_type": "http",
                "auth_type": "none",
            },
            headers=auth_headers,
        )
        assert create_response.status_code == status.HTTP_200_OK

        # List with status filter
        list_response = await async_client.get("/api/v1/mcp/servers?status=active", headers=auth_headers)
        assert list_response.status_code == status.HTTP_200_OK
        list_data = list_response.json()
        assert list_data["success"] is True

    @pytest.mark.asyncio
    async def test_create_server_with_auth(self, async_client: AsyncClient, auth_headers):
        """Test creating server with authentication config."""
        server_name = f"AuthServer_{uuid.uuid4().hex[:8]}"

        response = await async_client.post(
            "/api/v1/mcp/servers",
            json={
                "name": server_name,
                "url": "https://auth.example.com",
                "description": "Server with auth",
                "transport_type": "http",
                "server_type": "http",
                "auth_type": "bearer",
                "auth_config": {"token": "test-bearer-token"},
                "headers": {"X-Custom-Header": "custom-value"},
            },
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"]["auth_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_update_server_status(self, async_client: AsyncClient, auth_headers):
        """Test updating server status."""
        # Create server
        create_response = await async_client.post(
            "/api/v1/mcp/servers",
            json={
                "name": f"StatusServer_{uuid.uuid4().hex[:8]}",
                "url": "https://status.example.com",
                "description": "Status test server",
                "transport_type": "http",
                "server_type": "http",
                "auth_type": "none",
            },
            headers=auth_headers,
        )
        server_id = create_response.json()["data"]["id"]

        # Update status to inactive
        update_response = await async_client.put(
            f"/api/v1/mcp/servers/{server_id}",
            json={"status": "inactive"},
            headers=auth_headers,
        )

        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.json()["data"]["status"] == "inactive"

    @pytest.mark.asyncio
    async def test_update_server_transport_type_to_stdio_is_rejected(self, async_client: AsyncClient, auth_headers):
        """Updating an existing server to stdio transport is blocked for the same
        reason creating one is — SECURITY: no tenant-supplied command execution
        in the API process."""
        # Create HTTP server
        create_response = await async_client.post(
            "/api/v1/mcp/servers",
            json={
                "name": f"TransportServer_{uuid.uuid4().hex[:8]}",
                "url": "https://transport.example.com",
                "description": "Transport test server",
                "transport_type": "http",
                "server_type": "http",
                "auth_type": "none",
            },
            headers=auth_headers,
        )
        server_id = create_response.json()["data"]["id"]

        # Attempt to update to stdio
        update_response = await async_client.put(
            f"/api/v1/mcp/servers/{server_id}",
            json={
                "transport_type": "stdio",
                "command": "node",
                "args": ["server.js"],
            },
            headers=auth_headers,
        )

        assert update_response.status_code == status.HTTP_400_BAD_REQUEST
        assert "isolated runner" in update_response.json()["detail"]
