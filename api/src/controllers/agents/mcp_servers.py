"""
Agent API endpoints.

Provides REST API endpoints for managing and executing Google Agent SDK agents.
"""

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.controllers.agents.models import AgentResponse, AttachMCPServerRequest
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id
from src.models.agent import Agent
from src.services.agents.agent_manager import AgentManager

logger = logging.getLogger(__name__)

# Create router
agents_mcp_servers_router = APIRouter()

# Global agent manager instance
agent_manager = AgentManager()

# Agent-MCP Server Management Endpoints


@agents_mcp_servers_router.post("/{agent_id}/mcp-servers", response_model=AgentResponse)
async def attach_mcp_server(
    agent_id: str,
    request: AttachMCPServerRequest,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Attach an MCP server to an agent.

    Args:
        agent_id: UUID of the agent
        request: MCP server attachment request
        tenant_id: Tenant ID from JWT token
        db: Database session

    Returns:
        Success confirmation
    """
    try:
        from src.models.agent_mcp_server import AgentMCPServer
        from src.models.mcp_server import MCPServer

        # Convert string to UUID
        try:
            agent_uuid = uuid.UUID(agent_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid agent ID format")

        # SECURITY: Verify agent exists AND belongs to current tenant (prevents IDOR)
        result = await db.execute(select(Agent).filter(Agent.id == agent_uuid, Agent.tenant_id == tenant_id))
        agent = result.scalar_one_or_none()
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent with ID '{agent_id}' not found")

        # Convert mcp_server_id string to UUID
        try:
            mcp_server_uuid = uuid.UUID(request.mcp_server_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid MCP server ID format")

        # SECURITY: Verify MCP server exists AND belongs to current tenant (prevents IDOR)
        result = await db.execute(
            select(MCPServer).filter(MCPServer.id == mcp_server_uuid, MCPServer.tenant_id == tenant_id)
        )
        mcp_server = result.scalar_one_or_none()
        if not mcp_server:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"MCP server with ID '{request.mcp_server_id}' not found"
            )

        # Check if already attached
        result = await db.execute(
            select(AgentMCPServer).filter(
                AgentMCPServer.agent_id == agent_uuid, AgentMCPServer.mcp_server_id == mcp_server_uuid
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing association
            existing.mcp_config = request.mcp_config or {}
            existing.is_active = True
            message = f"MCP server '{mcp_server.name}' updated for agent"
        else:
            # Create new association
            agent_mcp = AgentMCPServer(
                agent_id=agent_uuid, mcp_server_id=mcp_server_uuid, mcp_config=request.mcp_config or {}, is_active=True
            )
            db.add(agent_mcp)
            message = f"MCP server '{mcp_server.name}' attached to agent"

        await db.commit()

        # Evict the cached client so next request reconnects with the updated server list.
        try:
            from src.services.mcp import mcp_client_manager

            await mcp_client_manager.close_agent_client(agent_uuid)
        except Exception:
            pass

        return AgentResponse(
            success=True,
            message=message,
            data={
                "agent_id": str(agent_uuid),
                "mcp_server_id": str(mcp_server_uuid),
                "mcp_server_name": mcp_server.name,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to attach MCP server: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to attach MCP server")


@agents_mcp_servers_router.get("/{agent_id}/mcp-servers", response_model=AgentResponse)
async def list_agent_mcp_servers(
    agent_id: str,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List all MCP servers attached to an agent.

    Args:
        agent_id: UUID of the agent
        tenant_id: Tenant ID from JWT token
        db: Database session

    Returns:
        List of attached MCP servers
    """
    try:
        from src.models.agent_mcp_server import AgentMCPServer

        # Convert string to UUID
        try:
            agent_uuid = uuid.UUID(agent_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid agent ID format")

        # SECURITY: Single OR query to prevent timing attacks
        # Checks: (agent belongs to tenant) OR (agent is public)
        from sqlalchemy import or_

        result = await db.execute(
            select(Agent).filter(Agent.id == agent_uuid, or_(Agent.tenant_id == tenant_id, Agent.is_public.is_(True)))
        )
        agent = result.scalar_one_or_none()
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent with ID '{agent_id}' not found")

        # Get all MCP servers for this agent (eager-load mcp_server to avoid lazy-load in async)
        result = await db.execute(
            select(AgentMCPServer)
            .filter(AgentMCPServer.agent_id == agent_uuid)
            .options(selectinload(AgentMCPServer.mcp_server))
        )
        agent_mcps = result.scalars().all()

        mcp_list = []
        for agent_mcp in agent_mcps:
            mcp = agent_mcp.mcp_server
            mcp_list.append(
                {
                    "id": mcp.id,
                    "name": mcp.name,
                    "description": mcp.description,
                    "url": mcp.url,
                    "auth_type": mcp.auth_type,
                    "is_active": agent_mcp.is_active,
                    "mcp_config": agent_mcp.mcp_config,
                    "created_at": agent_mcp.created_at.isoformat(),
                    "updated_at": agent_mcp.updated_at.isoformat(),
                }
            )

        return AgentResponse(
            success=True, message=f"Found {len(mcp_list)} MCP servers for agent", data={"mcp_servers": mcp_list}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list agent MCP servers: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list MCP servers")


@agents_mcp_servers_router.put("/{agent_id}/mcp-servers/{mcp_server_id}/config", response_model=AgentResponse)
async def update_mcp_config(
    agent_id: str,
    mcp_server_id: str,
    config: dict[str, Any],
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Update MCP configuration for an agent-MCP server association.

    Args:
        agent_id: UUID of the agent
        mcp_server_id: UUID of the MCP server
        config: New MCP configuration
        tenant_id: Tenant ID from JWT token
        db: Database session

    Returns:
        Success confirmation
    """
    try:
        from src.models.agent_mcp_server import AgentMCPServer

        # Convert agent_id string to UUID
        try:
            agent_uuid = uuid.UUID(agent_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid agent ID format")

        # SECURITY: Verify agent exists AND belongs to current tenant (prevents IDOR)
        result = await db.execute(select(Agent).filter(Agent.id == agent_uuid, Agent.tenant_id == tenant_id))
        agent = result.scalar_one_or_none()
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent with ID '{agent_id}' not found")

        # Convert mcp_server_id string to UUID
        try:
            mcp_server_uuid = uuid.UUID(mcp_server_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid MCP server ID format")

        # Find the association
        result = await db.execute(
            select(AgentMCPServer).filter(
                AgentMCPServer.agent_id == agent_uuid, AgentMCPServer.mcp_server_id == mcp_server_uuid
            )
        )
        agent_mcp = result.scalar_one_or_none()

        if not agent_mcp:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP server not attached to this agent")

        # Update configuration - use tool names as-is (no prefix)
        agent_mcp.mcp_config = config
        await db.commit()

        # Invalidate the in-memory tool discovery cache so the next chat picks up
        # the updated enabled_tools list without waiting for a reconnect.
        try:
            from src.services.mcp import mcp_client_manager

            mcp_client_manager.invalidate_tools_cache(agent_uuid)
        except Exception:
            pass

        # Return the config as-is
        response_config = config.copy()

        return AgentResponse(
            success=True, message="MCP configuration updated successfully", data={"mcp_config": response_config}
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update MCP config: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update configuration")


@agents_mcp_servers_router.delete("/{agent_id}/mcp-servers/{mcp_server_id}", response_model=AgentResponse)
async def detach_mcp_server(
    agent_id: str,
    mcp_server_id: str,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Detach an MCP server from an agent.

    Args:
        agent_id: UUID of the agent
        mcp_server_id: UUID of the MCP server
        tenant_id: Tenant ID from JWT token
        db: Database session

    Returns:
        Deletion confirmation
    """
    try:
        from src.models.agent_mcp_server import AgentMCPServer

        # Convert agent_id string to UUID
        try:
            agent_uuid = uuid.UUID(agent_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid agent ID format")

        # SECURITY: Verify agent exists AND belongs to current tenant (prevents IDOR)
        result = await db.execute(select(Agent).filter(Agent.id == agent_uuid, Agent.tenant_id == tenant_id))
        agent = result.scalar_one_or_none()
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent with ID '{agent_id}' not found")

        # Convert mcp_server_id string to UUID
        try:
            mcp_server_uuid = uuid.UUID(mcp_server_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid MCP server ID format")

        # Find and delete the association (eager-load mcp_server to read name without lazy load)
        result = await db.execute(
            select(AgentMCPServer)
            .filter(AgentMCPServer.agent_id == agent_uuid, AgentMCPServer.mcp_server_id == mcp_server_uuid)
            .options(selectinload(AgentMCPServer.mcp_server))
        )
        agent_mcp = result.scalar_one_or_none()

        if not agent_mcp:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP server not attached to this agent")

        mcp_name = agent_mcp.mcp_server.name
        await db.delete(agent_mcp)
        await db.commit()

        # Evict the cached client so next request reconnects without the removed server.
        try:
            from src.services.mcp import mcp_client_manager

            await mcp_client_manager.close_agent_client(agent_uuid)
        except Exception:
            pass

        return AgentResponse(success=True, message=f"MCP server '{mcp_name}' detached from agent")

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to detach MCP server: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to detach MCP server")


@agents_mcp_servers_router.get("/{agent_id}/mcp-servers/{mcp_server_id}/tools", response_model=AgentResponse)
async def list_mcp_server_tools(
    agent_id: str,
    mcp_server_id: str,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List available tools from an MCP server attached to an agent.

    Args:
        agent_id: UUID of the agent
        mcp_server_id: UUID of the MCP server
        tenant_id: Tenant ID from JWT token
        db: Database session

    Returns:
        List of available tools
    """
    try:
        from src.models.agent_mcp_server import AgentMCPServer

        # Convert agent_id string to UUID
        try:
            agent_uuid = uuid.UUID(agent_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid agent ID format")

        # SECURITY: Verify agent exists AND belongs to current tenant (prevents IDOR)
        result = await db.execute(select(Agent).filter(Agent.id == agent_uuid, Agent.tenant_id == tenant_id))
        agent = result.scalar_one_or_none()
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent with ID '{agent_id}' not found")

        # Convert mcp_server_id string to UUID
        try:
            mcp_server_uuid = uuid.UUID(mcp_server_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid MCP server ID format")

        # Find the association (eager-load mcp_server to avoid lazy load in async)
        result = await db.execute(
            select(AgentMCPServer)
            .filter(AgentMCPServer.agent_id == agent_uuid, AgentMCPServer.mcp_server_id == mcp_server_uuid)
            .options(selectinload(AgentMCPServer.mcp_server))
        )
        agent_mcp = result.scalar_one_or_none()

        if not agent_mcp:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP server not attached to this agent")

        # Get MCP client and discover tools
        try:
            # Create a dedicated MCP client for just this server
            # This ensures we only get tools from this specific server
            from src.services.mcp.mcp_client import MCPClient

            single_server_client = MCPClient(servers=[agent_mcp.mcp_server], timeout=30, max_retries=3)

            # Connect to the server
            await single_server_client.connect()

            # Discover tools from this specific server
            tools = await single_server_client.discover_tools(force_refresh=True)

            # Disconnect after getting tools
            await single_server_client.disconnect()

            # Convert Tool objects to dicts for JSON serialization
            tools_list = []
            for tool in tools:
                # Convert Tool object to dict if needed
                if hasattr(tool, "model_dump"):
                    tool_dict = tool.model_dump()
                elif hasattr(tool, "dict"):
                    tool_dict = tool.dict()
                elif isinstance(tool, dict):
                    tool_dict = tool
                else:
                    tool_dict = {
                        "name": getattr(tool, "name", ""),
                        "description": getattr(tool, "description", ""),
                        "inputSchema": getattr(tool, "inputSchema", {}),
                    }

                tools_list.append(tool_dict)

            return AgentResponse(
                success=True,
                message=f"Found {len(tools_list)} tools from MCP server '{agent_mcp.mcp_server.name}'",
                data={"mcp_server_name": agent_mcp.mcp_server.name, "tools": tools_list},
            )

        except Exception as e:
            logger.error(f"Failed to discover tools from MCP server: {e}")
            # Return a response with empty tools instead of 500 error
            # This allows the frontend to handle the error gracefully
            return AgentResponse(
                success=False,
                message=f"Failed to connect to MCP server '{agent_mcp.mcp_server.name}': {str(e)}",
                data={"mcp_server_name": agent_mcp.mcp_server.name, "tools": [], "error": str(e)},
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list MCP server tools: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list MCP server tools")
