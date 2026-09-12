from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.models import MCPServer
from src.services.mcp.mcp_client import MCPClient, MCPClientManager, MCPConnectionError, MCPToolExecutionError


class TestMCPClient:
    @pytest.fixture
    def mock_server(self):
        server = MagicMock(spec=MCPServer)
        server.name = "test-server"
        server.url = "http://localhost:8000"
        server.transport_type = "http"
        server.auth_type = "none"
        server.auth_config = {}
        server.headers = {}
        server.env_vars = {}
        server.args = []
        server.command = None
        return server

    @pytest.fixture
    def mock_fastmcp_client(self):
        with patch("src.services.mcp.mcp_client.Client") as MockClient:
            client_instance = MockClient.return_value
            client_instance.__aenter__ = AsyncMock(return_value=client_instance)
            client_instance.__aexit__ = AsyncMock()
            client_instance.ping = AsyncMock()
            client_instance.list_tools = AsyncMock(return_value=[])
            client_instance.call_tool = AsyncMock(return_value="result")
            yield MockClient

    @pytest.mark.asyncio
    async def test_connect_http_success(self, mock_server, mock_fastmcp_client):
        client = MCPClient([mock_server])
        await client.connect()

        mock_fastmcp_client.assert_called_once()
        # Verify StreamableHttpTransport was created implicitly by passing args to Client or explicitly
        # The implementation calls self._create_transport then passes it to Client

        assert client._client is not None

    @pytest.mark.asyncio
    async def test_connect_stdio_rejected(self, mock_server, mock_fastmcp_client):
        mock_server.transport_type = "stdio"
        mock_server.command = "python"
        mock_server.args = ["script.py"]

        client = MCPClient([mock_server])
        with pytest.raises(MCPConnectionError):
            await client.connect()
        mock_fastmcp_client.assert_not_called()

    @pytest.mark.asyncio
    async def test_connect_failure(self, mock_server, mock_fastmcp_client):
        mock_fastmcp_client.return_value.__aenter__.side_effect = Exception("Connection failed")

        client = MCPClient([mock_server])
        with pytest.raises(MCPConnectionError):
            await client.connect()

    @pytest.mark.asyncio
    async def test_discover_tools(self, mock_server, mock_fastmcp_client):
        client = MCPClient([mock_server])
        await client.connect()

        mock_tools = [{"name": "tool1", "description": "desc"}]
        client._client.list_tools.return_value = mock_tools

        tools = await client.discover_tools()
        assert tools == mock_tools
        assert client._tools_cache["all"] == mock_tools

    @pytest.mark.asyncio
    async def test_execute_tool_success(self, mock_server, mock_fastmcp_client):
        client = MCPClient([mock_server])
        await client.connect()

        client._client.call_tool.return_value = {"result": "success"}

        result = await client.execute_tool("tool1", {"arg": "val"})
        assert result == {"result": "success"}
        client._client.call_tool.assert_called_with(name="tool1", arguments={"arg": "val"})

    @pytest.mark.asyncio
    async def test_execute_tool_failure_is_not_replayed(self, mock_server, mock_fastmcp_client):
        client = MCPClient([mock_server], max_retries=2)
        await client.connect()

        client._client.call_tool.side_effect = Exception("Fail")

        with pytest.raises(MCPToolExecutionError):
            await client.execute_tool("tool1", {})

        assert client._client.call_tool.call_count == 1


class TestMCPClientManager:
    @pytest.fixture
    def manager(self):
        return MCPClientManager()

    @pytest.fixture
    def mock_db(self):
        server = SimpleNamespace(
            id=uuid4(),
            tenant_id=uuid4(),
            name="server1",
            url="https://tools.example.com/mcp",
            status="ACTIVE",
            transport_type="http",
            command=None,
            args=[],
            env_vars={},
            auth_type="none",
            auth_config={},
            headers={},
        )
        association = SimpleNamespace(mcp_server=server, mcp_config={})
        result = MagicMock()
        result.scalars.return_value.all.return_value = [association]
        db = AsyncMock()
        db.execute.return_value = result
        return db

    @pytest.mark.asyncio
    async def test_get_agent_client_create_new(self, manager, mock_db):
        with patch("src.services.mcp.mcp_client.MCPClient") as MockMCPClient:
            mock_instance = MockMCPClient.return_value
            mock_instance.connect = AsyncMock()

            client = await manager.get_agent_client("agent-id", mock_db)

            assert client == mock_instance
            assert "agent-id" in manager._clients
            mock_instance.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_agent_client_cached(self, manager, mock_db):
        with patch("src.services.mcp.mcp_client.MCPClient") as factory:
            factory.return_value.connect = AsyncMock()
            factory.return_value._retired = False
            first = await manager.get_agent_client("agent-id", mock_db)
            second = await manager.get_agent_client("agent-id", mock_db)
        assert second is first
        assert mock_db.execute.await_count == 2  # Reconcile revocation even on a warm client.
        factory.return_value.connect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_agent_client(self, manager):
        mock_client = MagicMock()
        mock_client.disconnect = AsyncMock()
        manager._clients["agent-id"] = mock_client

        await manager.close_agent_client("agent-id")

        mock_client.disconnect.assert_called_once()
        assert "agent-id" not in manager._clients
