"""
MCP Client Service using FastMCP

Handles communication with Model Context Protocol (MCP) servers using FastMCP library.
Supports multiple servers with a single client instance and proper authentication.
Supports both HTTP and stdio transports.
"""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

import httpx
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import AgentMCPServer, MCPServer

logger = logging.getLogger(__name__)


def _describe_bearer_token(token: str) -> str:
    """Describe authentication without decoding or logging identity claims."""
    return "bearer token present" if token else "none"


class MCPClientError(Exception):
    """Base exception for MCP client errors."""

    pass


class MCPConnectionError(MCPClientError):
    """Raised when connection to MCP server fails."""

    pass


class MCPAuthenticationError(MCPClientError):
    """Raised when authentication with MCP server fails."""

    pass


class MCPToolExecutionError(MCPClientError):
    """Raised when tool execution fails."""

    pass


class MCPClient:
    """
    Client for communicating with MCP servers using FastMCP.

    FastMCP provides:
    - Single client instance for multiple servers
    - Automatic session management via context manager
    - Built-in authentication support via headers
    - Tool discovery and execution
    - Error handling and retries
    - Compatible with Google ADK
    """

    def __init__(self, servers: list[MCPServer], timeout: int = 30, max_retries: int = 3):
        """
        Initialize MCP client using FastMCP with multiple servers.

        Args:
            servers: List of MCP server configurations
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.servers = {server.name: server for server in servers}
        self.timeout = timeout
        self.max_retries = max_retries
        self._client_context = None
        self._client: Client | None = None
        self._tools_cache: dict[str, list[dict[str, Any]]] = {}
        self._tools_cache_times: dict[str, float] = {}
        self.config_revision = ""
        self._owner_task = None
        self._connect_lock = asyncio.Lock()
        self._close_requested = asyncio.Event()
        self._idle = asyncio.Event()
        self._idle.set()
        self._active = 0
        self._retired = False

    async def connect(self) -> None:
        async with self._connect_lock:
            if self._retired:
                raise MCPConnectionError("MCP connection is retired; acquire a current connection")
            if self._client is not None:
                return
            await self._connect_owned()

    async def _connect_owned(self) -> None:
        """Keep transport context entry/exit in the same owning task."""
        ready = asyncio.get_running_loop().create_future()

        async def own_connection():
            try:
                await self._open_connection()
                ready.set_result(None)
                await self._close_requested.wait()
                await self._idle.wait()
            except BaseException as exc:
                if not ready.done():
                    ready.set_exception(exc)
            finally:
                await self._close_connection()

        self._owner_task = asyncio.create_task(own_connection())
        try:
            await asyncio.wait_for(asyncio.shield(ready), self.timeout)
        except BaseException:
            self._owner_task.cancel()
            await asyncio.gather(self._owner_task, return_exceptions=True)
            # Consume an exception published during cancellation to avoid orphan warnings.
            if ready.done() and not ready.cancelled():
                ready.exception()
            raise

    async def disconnect(self) -> None:
        self._retired = True
        self._close_requested.set()
        if self._owner_task:
            await asyncio.shield(self._owner_task)
        else:
            await self._close_connection()

    @asynccontextmanager
    async def _operation(self):
        if self._retired:
            raise MCPConnectionError("MCP configuration changed; acquire a current connection")
        self._active += 1
        self._idle.clear()
        try:
            yield
        finally:
            self._active -= 1
            if not self._active:
                self._idle.set()

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()

    def _build_headers(self, server: MCPServer) -> dict[str, str]:
        """
        Build authentication headers for the server.

        Args:
            server: MCP server configuration

        Returns:
            Dictionary of headers
        """
        headers = httpx.Headers({"Accept": "application/json", "User-Agent": "synkora-mcp-client"})

        # Add custom headers from server config
        if server.headers:
            headers.update(server.headers)

        # Add authentication headers
        if server.auth_config:
            auth_type = server.auth_type.lower()

            if auth_type == "bearer":
                token = server.auth_config.get("token")
                if token:
                    headers["Authorization"] = f"Bearer {token}"

            elif auth_type == "api_key":
                api_key = server.auth_config.get("api_key")
                header_name = server.auth_config.get("header_name", "X-API-Key")
                if api_key:
                    headers[header_name] = api_key

        return dict(headers)

    def _create_transport(self, server: MCPServer):
        """
        Create appropriate transport based on server configuration.

        Args:
            server: MCP server configuration

        Returns:
            Transport instance (StreamableHttpTransport or StdioTransport)

        Raises:
            ValueError: If configuration is invalid
        """
        transport_type = getattr(server, "transport_type", "http")

        if transport_type == "stdio":
            raise MCPConnectionError(
                "Command-based MCP servers cannot run inside the API. "
                "Deploy the server in an isolated runner and configure its HTTP endpoint."
            )
        else:
            # HTTP/SSE transport (existing)
            if not server.url:
                raise ValueError(f"URL required for HTTP transport: {server.name}")

            headers = httpx.Headers(self._build_headers(server))

            # Extract auth token if present for Bearer auth
            auth = None
            if "Authorization" in headers:
                auth_header = headers.pop("Authorization")
                if auth_header.startswith("Bearer "):
                    auth = auth_header[7:]  # Remove "Bearer " prefix

            logger.info(f"Creating HTTP transport for {server.name}")
            logger.info(f"URL: {server.url}")
            logger.info(f"Auth: {_describe_bearer_token(auth) if auth else 'none'}")

            from src.services.mcp.http_transport import mcp_http_client_factory

            return StreamableHttpTransport(
                server.url,
                headers=dict(headers),
                auth=auth,
                httpx_client_factory=mcp_http_client_factory(server.url),
            )

    async def _open_connection(self) -> None:
        """
        Connect to all MCP servers using FastMCP Client.

        Supports both HTTP and stdio transports. For multiple servers,
        FastMCP uses a config-based approach where each server is
        identified by a unique name.

        Raises:
            MCPConnectionError: If connection fails
            MCPAuthenticationError: If authentication fails
        """
        try:
            if len(self.servers) == 1:
                # Single server mode - create transport based on type
                server = list(self.servers.values())[0]
                transport = self._create_transport(server)

                transport_type = getattr(server, "transport_type", "http")
                logger.info(f"Creating MCP client for {server.name} ({transport_type})")
                self._client_context = Client(transport)
            else:
                # Use the same guarded transport for every server; raw config URLs
                # would bypass the HTTP factory used in the single-server path.
                from fastmcp import FastMCP

                composite = FastMCP("Synkora MCP Router")
                for name, server in self.servers.items():
                    transport = self._create_transport(server)
                    proxy = FastMCP.as_proxy(Client(transport))
                    composite.mount(proxy, name)
                self._client_context = Client(composite)

            # Enter the context manager
            self._client = await self._client_context.__aenter__()

            # Test connection with ping
            try:
                await self._client.ping()
                logger.info(f"Connected to {len(self.servers)} MCP server(s)")
            except Exception as e:
                logger.warning(f"Ping failed but connection established: {str(e)}")

        except Exception as e:
            logger.warning("MCP connection failed (%s)", type(e).__name__)
            raise MCPConnectionError("MCP connection failed") from e

    async def _close_connection(self) -> None:
        """Disconnect from all MCP servers."""
        if self._client_context:
            try:
                await self._client_context.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Error closing MCP client: {str(e)}")
            finally:
                self._client = None
                self._client_context = None
                logger.info("Disconnected from MCP servers")

    async def discover_tools(self, server_name: str | None = None, force_refresh: bool = False) -> list[dict[str, Any]]:
        """
        Discover available tools from MCP server(s).

        Args:
            server_name: Optional server name to filter tools (for multi-server setup)
            force_refresh: Force refresh of tools cache

        Returns:
            List of tool definitions

        Raises:
            MCPConnectionError: If discovery fails
        """
        cache_key = server_name or "all"
        now = asyncio.get_running_loop().time()

        if (
            cache_key in self._tools_cache
            and not force_refresh
            and now - self._tools_cache_times.get(cache_key, 0) < 300
        ):
            return self._tools_cache[cache_key]

        if not self._client:
            raise MCPConnectionError("Not connected to MCP servers")

        try:
            logger.info("Discovering tools from MCP servers")

            # FastMCP Client handles tool discovery automatically
            async with self._operation():
                tools = await self._client.list_tools()
            logger.debug(f"MCP tools discovered: {tools}")
            # Note: When multiple servers are configured, tool filtering by server
            # should be handled at a higher level (e.g., in adk_tools.py) using
            # the enabled_tools configuration rather than name prefixes

            if server_name and len(self.servers) > 1:

                def owner(tool):
                    name = tool.name if hasattr(tool, "name") else tool.get("name", "")
                    matches = [server for server in self.servers if name.startswith(f"{server}_")]
                    return max(matches, key=len) if matches else None

                tools = [tool for tool in tools if owner(tool) == server_name]
            self._tools_cache[cache_key] = tools
            self._tools_cache_times[cache_key] = now
            logger.info(f"Discovered {len(tools)} tools")

            return tools

        except Exception as e:
            logger.error(f"Error discovering tools: {str(e)}")
            raise MCPConnectionError(f"Failed to discover tools: {str(e)}")

    async def execute_tool(
        self, tool_name: str, arguments: dict[str, Any], server_name: str | None = None
    ) -> dict[str, Any]:
        """
        Execute a tool on an MCP server.

        Args:
            tool_name: Name of the tool to execute (use the tool name as-is from MCP server)
            arguments: Tool arguments
            server_name: Optional server name (for logging purposes only)

        Returns:
            Tool execution result

        Raises:
            MCPToolExecutionError: If tool execution fails
        """
        if not self._client:
            raise MCPConnectionError("Not connected to MCP servers")

        logger.info("Executing MCP tool %s on server %s", tool_name, server_name)

        # Per-call timeout (seconds). Keeps slow MCP tools from consuming the
        # entire outer task budget and killing the whole agent run.
        _TOOL_TIMEOUT = 120

        # A transport failure does not prove a remote write failed. Never replay here.
        try:
            async with self._operation():
                return await asyncio.wait_for(
                    self._client.call_tool(name=tool_name, arguments=arguments), timeout=_TOOL_TIMEOUT
                )
        except Exception as exc:
            logger.warning("MCP tool %s failed (%s)", tool_name, type(exc).__name__)
            raise MCPToolExecutionError(f"MCP tool {tool_name} failed; completion may be unknown") from exc

    async def get_tool_schema(self, tool_name: str, server_name: str | None = None) -> dict[str, Any] | None:
        """
        Get the schema for a specific tool.

        Args:
            tool_name: Name of the tool (use the tool name as-is from MCP server)
            server_name: Optional server name (for filtering, not used currently)

        Returns:
            Tool schema or None if not found
        """
        tools = await self.discover_tools(server_name=server_name)

        for tool in tools:
            if tool.get("name") == tool_name:
                return tool
        return None


class MCPClientManager:
    """
    Manager for MCP client instances.

    Handles:
    - Creating and caching MCP clients per agent
    - Loading agent MCP server configurations
    - Managing client lifecycle
    - Supporting multiple servers per agent with a single client
    """

    def __init__(self):
        from weakref import WeakValueDictionary

        self._clients: dict[UUID, MCPClient] = {}
        self._locks = WeakValueDictionary()
        self._last_used = {}
        self.max_clients = max(1, int(os.getenv("MCP_MAX_CACHED_CLIENTS", "128")))
        self.idle_seconds = max(1, int(os.getenv("MCP_CLIENT_IDLE_SECONDS", "300")))

    async def get_agent_client(self, agent_id: UUID, db: AsyncSession) -> MCPClient | None:
        """Single-flight acquisition reconciled against authoritative configuration."""
        import hashlib
        import time

        from sqlalchemy.orm import selectinload

        lock = self._locks.setdefault(agent_id, asyncio.Lock())
        async with lock:
            result = await db.execute(
                select(AgentMCPServer)
                .options(selectinload(AgentMCPServer.mcp_server))
                .filter(AgentMCPServer.agent_id == agent_id, AgentMCPServer.is_active)
                .execution_options(populate_existing=True)
            )
            associations = [a for a in result.scalars().all() if a.mcp_server.status == "ACTIVE"]
            if not associations:
                await self.close_agent_client(agent_id)
                return None

            servers = [a.mcp_server for a in associations]
            revision_data = sorted(
                [
                    {
                        "id": str(server.id),
                        "tenant": str(server.tenant_id),
                        "name": server.name,
                        "url": server.url,
                        "transport": server.transport_type,
                        "command": server.command,
                        "args": server.args,
                        "env": server.env_vars,
                        "auth_type": server.auth_type,
                        "auth": server.auth_config,
                        "headers": server.headers,
                        "binding": assoc.mcp_config,
                    }
                    for assoc, server in zip(associations, servers, strict=True)
                ],
                key=lambda value: value["id"],
            )
            revision = hashlib.sha256(json.dumps(revision_data, sort_keys=True).encode()).hexdigest()
            now = time.monotonic()
            cached = self._clients.get(agent_id)
            if cached is not None and cached.config_revision == revision and not cached._retired:
                self._last_used[agent_id] = now
                return cached
            await self.close_agent_client(agent_id)

            # Retire only idle entries. Never interrupt a running remote operation.
            for key in sorted(self._clients, key=lambda key: self._last_used.get(key, 0)):
                candidate = self._clients.get(key)
                if (
                    candidate is not None
                    and candidate._client is not None
                    and not candidate._active
                    and (
                        len(self._clients) >= self.max_clients or now - self._last_used.get(key, 0) >= self.idle_seconds
                    )
                ):
                    await self.close_agent_client(key)
            if len(self._clients) >= self.max_clients:
                raise MCPConnectionError("MCP connection capacity reached; try again later")

            client = MCPClient(servers=servers, timeout=30)
            client.config_revision = revision
            # Reserve capacity before awaiting connection to bound concurrent cold starts.
            self._clients[agent_id] = client
            self._last_used[agent_id] = now
            try:
                await client.connect()
                return client
            except BaseException:
                self._clients.pop(agent_id, None)
                self._last_used.pop(agent_id, None)
                raise

    async def close_agent_client(self, agent_id: UUID) -> None:
        """
        Close MCP client for a specific agent.

        Args:
            agent_id: Agent ID
        """
        client = self._clients.pop(agent_id, None)
        self._last_used.pop(agent_id, None)
        if client is not None:
            await client.disconnect()

    def invalidate_tools_cache(self, agent_id: UUID) -> None:
        """
        Clear the in-memory tool discovery cache for an agent's MCP client.

        Causes the next discover_tools() call to re-query the MCP server,
        picking up any newly added or removed tools without disconnecting.
        """
        if agent_id in self._clients:
            self._clients[agent_id]._tools_cache.clear()
            logger.info(f"Cleared MCP tools cache for agent {agent_id}")

    async def get_agent_client_with_user_token(
        self, agent_id: UUID, db: AsyncSession, user_token: str
    ) -> MCPClient | None:
        """
        Create a fresh, non-cached MCP client for a single request, injecting a
        per-request Bearer token that overrides the static auth_config token.

        Used when a widget user's identity JWT needs to be forwarded to the MCP
        server so it can extract user context from the Authorization header.

        The client is NOT stored in the cache — callers must call disconnect()
        themselves (or use it as an async context manager).

        Args:
            agent_id: Agent ID
            db: Async database session
            user_token: Short-lived JWT to use as Bearer token (overrides static config)

        Returns:
            Connected MCP client or None if no servers configured
        """
        from sqlalchemy.orm import selectinload

        result = await db.execute(
            select(AgentMCPServer)
            .options(selectinload(AgentMCPServer.mcp_server))
            .filter(AgentMCPServer.agent_id == agent_id, AgentMCPServer.is_active)
        )
        associations = [a for a in result.scalars().all() if a.mcp_server.status == "ACTIVE"]

        if not associations:
            return None

        # Build patched server list — override Bearer token with the per-request JWT.
        # Use SimpleNamespace instead of copying the SQLAlchemy model to avoid
        # corrupting shared _sa_instance_state.
        import types

        patched_servers: list[Any] = []
        for assoc in associations:
            server = assoc.mcp_server
            transport_type = getattr(server, "transport_type", "http")
            if transport_type != "http":
                # stdio transport doesn't use HTTP headers; pass through unchanged
                patched_servers.append(server)
                continue

            patched_servers.append(
                types.SimpleNamespace(
                    name=server.name,
                    url=server.url,
                    auth_type="bearer",
                    auth_config={**(server.auth_config or {}), "token": user_token},
                    headers=server.headers,
                    transport_type="http",
                )
            )

        try:
            client = MCPClient(servers=patched_servers, timeout=30, max_retries=3)
            await client.connect()
            return client
        except Exception as e:
            logger.error(f"Failed to create per-request MCP client for agent {agent_id}: {e}")
            return None

    async def close_all(self) -> None:
        """Close all MCP clients."""
        for agent_id in list(self._clients.keys()):
            await self.close_agent_client(agent_id)


# Global MCP client manager instance
mcp_client_manager = MCPClientManager()
