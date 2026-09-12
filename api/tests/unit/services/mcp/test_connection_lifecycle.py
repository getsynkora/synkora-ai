import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.services.mcp.mcp_client import MCPClient, MCPClientManager


def configured_db():
    server = SimpleNamespace(
        id=uuid4(),
        tenant_id=uuid4(),
        name="tools",
        url="https://tools.example.com/mcp",
        status="ACTIVE",
        transport_type="http",
        command=None,
        args=[],
        env_vars={},
        auth_type="bearer",
        auth_config={"token": "old"},
        headers={},
    )
    result = MagicMock()
    result.scalars.return_value.all.return_value = [SimpleNamespace(mcp_server=server, mcp_config={})]
    return server, SimpleNamespace(execute=AsyncMock(return_value=result))


class FakeClient:
    created = []

    def __init__(self, **_kwargs):
        self._client = object()
        self._active = 0
        self._retired = False
        self.config_revision = ""
        self.disconnect = AsyncMock(side_effect=self.retire)
        self.created.append(self)

    async def connect(self):
        await asyncio.sleep(0)

    async def retire(self):
        self._retired = True


@pytest.mark.asyncio
async def test_concurrent_cold_acquisition_connects_once():
    _, db = configured_db()
    manager = MCPClientManager()
    with patch("src.services.mcp.mcp_client.MCPClient", FakeClient):
        clients = await asyncio.gather(*(manager.get_agent_client("agent", db) for _ in range(20)))
    assert all(client is clients[0] for client in clients)
    assert len(manager._clients) == 1


@pytest.mark.asyncio
async def test_credential_rotation_and_disable_reconcile_without_pubsub():
    server, db = configured_db()
    manager = MCPClientManager()
    with patch("src.services.mcp.mcp_client.MCPClient", FakeClient):
        old = await manager.get_agent_client("agent", db)
        server.auth_config = {"token": "rotated"}
        new = await manager.get_agent_client("agent", db)
        assert new is not old
        assert new.config_revision != old.config_revision
        old.disconnect.assert_awaited_once()
        server.status = "INACTIVE"
        assert await manager.get_agent_client("agent", db) is None
        new.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_pool_evicts_idle_entry_at_bound():
    _, db = configured_db()
    manager = MCPClientManager()
    manager.max_clients = 1
    with patch("src.services.mcp.mcp_client.MCPClient", FakeClient):
        old = await manager.get_agent_client("one", db)
        new = await manager.get_agent_client("two", db)
    assert list(manager._clients) == ["two"]
    assert new is not old
    old.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_transport_owner_closes_after_inflight_operation():
    client = MCPClient([])
    entered = asyncio.Event()
    release = asyncio.Event()
    owner_tasks = []

    async def tool(**_kwargs):
        entered.set()
        await release.wait()
        return "done"

    async def opened():
        owner_tasks.append(asyncio.current_task())
        client._client = SimpleNamespace(call_tool=tool)

    async def closed():
        owner_tasks.append(asyncio.current_task())

    client._open_connection = opened
    client._close_connection = closed
    await client.connect()
    operation = asyncio.create_task(client.execute_tool("write", {}))
    await entered.wait()
    closing = asyncio.create_task(client.disconnect())
    await asyncio.sleep(0)
    assert not closing.done()
    release.set()
    assert await operation == "done"
    await closing
    assert len(owner_tasks) == 2
    assert owner_tasks[0] is owner_tasks[1]


@pytest.mark.asyncio
async def test_direct_concurrent_connect_has_one_owner():
    client = MCPClient([])

    async def opened():
        await asyncio.sleep(0)
        client._client = object()

    client._open_connection = AsyncMock(side_effect=opened)
    client._close_connection = AsyncMock()
    await asyncio.gather(*(client.connect() for _ in range(10)))
    client._open_connection.assert_awaited_once()
    await client.disconnect()
    client._close_connection.assert_awaited_once()
