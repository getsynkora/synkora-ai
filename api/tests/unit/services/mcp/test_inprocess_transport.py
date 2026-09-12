"""Real FastMCP protocol tests using in-memory servers, no external endpoints."""

import asyncio
from types import SimpleNamespace

import pytest
from fastmcp import FastMCP
from fastmcp.client.transports import FastMCPTransport

from src.services.mcp.mcp_client import MCPClient


@pytest.mark.asyncio
async def test_multi_server_discovery_routing_and_lifecycle():
    first = FastMCP("first")
    second = FastMCP("second")

    @first.tool
    def lookup() -> str:
        return "first server"

    @second.tool(name="lookup")
    def lookup_second() -> str:
        return "second server"

    servers = {"a": first, "a_b": second}
    client = MCPClient([SimpleNamespace(name=name) for name in servers])
    client._create_transport = lambda server: FastMCPTransport(servers[server.name])

    async with client:
        first_tools = await client.discover_tools("a")
        second_tools = await client.discover_tools("a_b")
        assert [tool.name for tool in first_tools] == ["a_lookup"]
        assert [tool.name for tool in second_tools] == ["a_b_lookup"]
        first_result, second_result = await asyncio.gather(
            client.execute_tool("a_lookup", {}, "a"),
            client.execute_tool("a_b_lookup", {}, "a_b"),
        )
        assert first_result.content[0].text == "first server"
        assert second_result.content[0].text == "second server"
    assert client._client is None
    assert client._owner_task.done()
