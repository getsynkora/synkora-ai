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
from typing import Any
from uuid import UUID

from fastmcp import Client
from fastmcp.client.transports import StdioTransport, StreamableHttpTransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import AgentMCPServer, MCPServer

logger = logging.getLogger(__name__)


def _describe_bearer_token(token: str) -> str:
    """Best-effort, no-verify decode of a bearer token's claims for diagnostics.

    Never logs the raw token — only whether it looks like a JWT and, if so,
    its non-sensitive claims (everything except any value under "email").
    """
    try:
        import jwt as _jwt

        claims = _jwt.decode(token, options={"verify_signature": False})
        safe_claims = {k: v for k, v in claims.items() if k != "email"}
        return f"JWT claims={safe_claims}"
    except Exception:
        return f"opaque token (len={len(token)})"


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
        headers = {"Accept": "application/json", "User-Agent": "synkora-mcp-client"}

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

        return headers

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
            # Stdio transport for local MCP servers
            if not server.command:
                raise ValueError(f"Command required for stdio transport: {server.name}")

            # Build environment variables
            env = dict(os.environ)  # Start with current environment
            if server.env_vars:
                env.update(server.env_vars)

            logger.info(f"Creating stdio transport for {server.name}")
            logger.info(f"Command: {server.command}")
            logger.info(f"Args: {server.args}")
            logger.info(f"Env vars: {list(server.env_vars.keys()) if server.env_vars else []}")

            # Create stdio transport
            return StdioTransport(command=server.command, args=server.args or [], env=env)
        else:
            # HTTP/SSE transport (existing)
            if not server.url:
                raise ValueError(f"URL required for HTTP transport: {server.name}")

            headers = self._build_headers(server)

            # Extract auth token if present for Bearer auth
            auth = None
            if "Authorization" in headers:
                auth_header = headers.pop("Authorization")
                if auth_header.startswith("Bearer "):
                    auth = auth_header[7:]  # Remove "Bearer " prefix

            logger.info(f"Creating HTTP transport for {server.name}")
            logger.info(f"URL: {server.url}")
            logger.info(f"Auth: {_describe_bearer_token(auth) if auth else 'none'}")

            return StreamableHttpTransport(server.url, headers=headers, auth=auth)

    async def connect(self) -> None:
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
                # Multiple servers mode - use config-based approach
                # Note: For mixed transports, we need to handle each type appropriately
                mcp_config = {"mcpServers": {}}

                for name, server in self.servers.items():
                    transport_type = getattr(server, "transport_type", "http")

                    if transport_type == "stdio":
                        # For stdio, we need to provide command configuration
                        env = dict(os.environ)
                        if server.env_vars:
                            env.update(server.env_vars)

                        mcp_config["mcpServers"][name] = {
                            "command": server.command,
                            "args": server.args or [],
                            "env": env,
                        }
                    else:
                        # For HTTP, use URL-based config
                        headers = self._build_headers(server)

                        # Extract auth token if present
                        auth = None
                        if "Authorization" in headers:
                            auth_header = headers.pop("Authorization")
                            if auth_header.startswith("Bearer "):
                                auth = auth_header[7:]

                        mcp_config["mcpServers"][name] = {"url": server.url, "headers": headers, "auth": auth}

                # Create client with multi-server config
                logger.info(f"Creating MCP client with {len(self.servers)} servers")
                self._client_context = Client(mcp_config)

            # Enter the context manager
            self._client = await self._client_context.__aenter__()

            # Test connection with ping
            try:
                await self._client.ping()
                logger.info(f"Connected to {len(self.servers)} MCP server(s)")
            except Exception as e:
                logger.warning(f"Ping failed but connection established: {str(e)}")

        except Exception as e:
            # httpx.HTTPStatusError only puts a generic "401 Unauthorized" summary in
            # str(e) — the server's actual rejection reason is in the response body.
            response = getattr(e, "response", None)
            if response is not None:
                try:
                    logger.error(f"MCP server response body: {response.text[:1000]}")
                except Exception:
                    pass
            logger.error(f"Failed to connect to MCP servers: {str(e)}")
            raise MCPConnectionError(f"Failed to connect to MCP servers: {str(e)}")

    async def disconnect(self) -> None:
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

        if cache_key in self._tools_cache and not force_refresh:
            return self._tools_cache[cache_key]

        if not self._client:
            raise MCPConnectionError("Not connected to MCP servers")

        try:
            logger.info("Discovering tools from MCP servers")

            # FastMCP Client handles tool discovery automatically
            tools = await self._client.list_tools()
            logger.debug(f"MCP tools discovered: {tools}")
            # Note: When multiple servers are configured, tool filtering by server
            # should be handled at a higher level (e.g., in adk_tools.py) using
            # the enabled_tools configuration rather than name prefixes

            self._tools_cache[cache_key] = tools
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

        # Log the request details
        logger.info("=== MCP Tool Execution Request ===")
        logger.info(f"Tool: {tool_name}")
        logger.info(f"Server: {server_name}")
        logger.info(f"Arguments: {json.dumps(arguments, indent=2)}")

        # Log server configuration
        if server_name and server_name in self.servers:
            server = self.servers[server_name]
            logger.info(f"Server URL: {server.url}")
            logger.info(f"Auth Type: {server.auth_type}")
            logger.info(f"Has auth_config: {bool(server.auth_config)}")
            if server.auth_config:
                # Log auth config without exposing full token
                auth_keys = list(server.auth_config.keys())
                logger.info(f"Auth config keys: {auth_keys}")
                if "token" in server.auth_config:
                    token = server.auth_config["token"]
                    logger.info(f"Token present: Yes (length: {len(token)})")

        # Per-call timeout (seconds). Keeps slow MCP tools from consuming the
        # entire outer task budget and killing the whole agent run.
        _TOOL_TIMEOUT = 120

        # Execute with retries
        last_error = None
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Attempt {attempt + 1}/{self.max_retries}: Calling FastMCP client.call_tool()")

                # FastMCP Client handles session management and tool execution
                result = await asyncio.wait_for(
                    self._client.call_tool(name=tool_name, arguments=arguments),
                    timeout=_TOOL_TIMEOUT,
                )

                logger.info("=== MCP Tool Execution Response ===")
                logger.info("Success: True")
                logger.info(f"Result type: {type(result)}")
                logger.info(f"Result: {json.dumps(result, indent=2) if isinstance(result, dict) else str(result)}")

                return result

            except asyncio.CancelledError:
                # Outer task was cancelled (e.g. parent wait_for fired) — do not retry,
                # just propagate so the caller can handle it cleanly.
                raise

            except Exception as e:
                last_error = e
                error_msg = str(e)

                # Auth errors will never succeed on retry — fail fast
                _auth_keywords = ("authentication", "unauthorized", "401", "forbidden", "403", "jwt", "token")
                if any(kw in error_msg.lower() for kw in _auth_keywords):
                    logger.warning(f"MCP auth error for tool {tool_name} (not retrying): {error_msg}")
                    break

                logger.error("=== MCP Tool Execution Error ===")
                logger.error(f"Attempt: {attempt + 1}/{self.max_retries}")
                logger.error(f"Error type: {type(e).__name__}")
                logger.error(f"Error message: {error_msg}")
                logger.error("Error details:", exc_info=True)

                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    await asyncio.sleep(2**attempt)
                    logger.warning(f"Retrying after {2**attempt} seconds...")

        raise MCPToolExecutionError(
            f"Failed to execute tool {tool_name} after {self.max_retries} attempts: {str(last_error)}"
        )

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
        """Initialize MCP client manager."""
        self._clients: dict[UUID, MCPClient] = {}

    async def get_agent_client(self, agent_id: UUID, db: AsyncSession) -> MCPClient | None:
        """
        Get or create an MCP client for an agent with all its servers.

        Args:
            agent_id: Agent ID
            db: Async database session

        Returns:
            MCP client instance or None if no servers configured
        """
        if agent_id in self._clients:
            return self._clients[agent_id]

        # Get agent's MCP server associations
        from sqlalchemy.orm import selectinload

        result = await db.execute(
            select(AgentMCPServer)
            .options(selectinload(AgentMCPServer.mcp_server))
            .filter(AgentMCPServer.agent_id == agent_id, AgentMCPServer.is_active)
        )
        associations = list(result.scalars().all())

        if not associations:
            return None

        # Collect all servers for this agent
        servers = [assoc.mcp_server for assoc in associations]

        try:
            # Create single client for all servers
            client = MCPClient(servers=servers, timeout=30, max_retries=3)

            await client.connect()
            self._clients[agent_id] = client

            return client

        except Exception as e:
            logger.error(f"Failed to create MCP client for agent {agent_id}: {str(e)}")
            return None

    async def close_agent_client(self, agent_id: UUID) -> None:
        """
        Close MCP client for a specific agent.

        Args:
            agent_id: Agent ID
        """
        if agent_id in self._clients:
            try:
                await self._clients[agent_id].disconnect()
            except Exception as e:
                logger.error(f"Error closing MCP client for agent {agent_id}: {str(e)}")
            finally:
                del self._clients[agent_id]

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
        associations = list(result.scalars().all())

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
