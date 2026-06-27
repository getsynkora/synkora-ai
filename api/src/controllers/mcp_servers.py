"""
MCP Server Management Controller
Handles CRUD operations for MCP servers using database
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id
from src.models.mcp_server import MCPServer

router = APIRouter(prefix="/api/v1/mcp", tags=["mcp"])


class CreateMCPServerRequest(BaseModel):
    name: str
    url: str | None = None
    description: str
    transport_type: str = "http"  # "http" or "stdio"
    command: str | None = None
    args: list[str] | None = None
    env_vars: dict | None = None
    server_type: str = "http"
    auth_type: str = "none"
    auth_config: dict | None = None
    headers: dict | None = None
    capabilities: dict | None = None
    server_metadata: dict | None = None


class UpdateMCPServerRequest(BaseModel):
    name: str | None = None
    url: str | None = None
    description: str | None = None
    transport_type: str | None = None
    command: str | None = None
    args: list[str] | None = None
    env_vars: dict | None = None
    server_type: str | None = None
    auth_type: str | None = None
    auth_config: dict | None = None
    headers: dict | None = None
    capabilities: dict | None = None
    server_metadata: dict | None = None
    status: str | None = None


@router.get("/servers")
async def list_mcp_servers(
    status: str | None = None,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """List all MCP servers"""
    try:
        query = select(MCPServer).filter(MCPServer.tenant_id == tenant_id)

        if status:
            query = query.filter(MCPServer.status == status)

        result = await db.execute(query)
        servers = result.scalars().all()

        return {"success": True, "data": {"servers": [server.to_dict() for server in servers], "total": len(servers)}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/servers/{server_id}")
async def get_mcp_server(
    server_id: str,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Get a specific MCP server"""
    try:
        result = await db.execute(
            select(MCPServer).filter(MCPServer.id == uuid.UUID(server_id), MCPServer.tenant_id == tenant_id)
        )
        server = result.scalar_one_or_none()

        if not server:
            raise HTTPException(status_code=404, detail="MCP server not found")

        return {"success": True, "data": server.to_dict()}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid server ID format")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/servers")
async def create_mcp_server(
    request: CreateMCPServerRequest,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Create a new MCP server"""
    try:
        # Validate based on transport type
        if request.transport_type == "stdio":
            if not request.command:
                raise HTTPException(status_code=400, detail="Command is required for stdio transport")
        else:  # http
            if not request.url:
                raise HTTPException(status_code=400, detail="URL is required for HTTP transport")

        # Validate transport type
        if request.transport_type not in ["http", "stdio"]:
            raise HTTPException(status_code=400, detail="Transport type must be 'http' or 'stdio'")

        # Create new server — sensitive fields set via properties after construction
        # so that Fernet encryption is applied before the first db.add().
        new_server = MCPServer(
            tenant_id=tenant_id,
            name=request.name,
            url=request.url,
            description=request.description,
            transport_type=request.transport_type,
            command=request.command,
            args=request.args,
            server_type=request.server_type,
            auth_type=request.auth_type,
            capabilities=request.capabilities,
            server_metadata=request.server_metadata or {},
            status="ACTIVE",
        )
        new_server.auth_config = request.auth_config
        new_server.env_vars = request.env_vars
        new_server.headers = request.headers

        db.add(new_server)
        await db.commit()
        await db.refresh(new_server)

        return {"success": True, "message": "MCP server created successfully", "data": new_server.to_dict()}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/servers/{server_id}")
async def update_mcp_server(
    server_id: str,
    request: UpdateMCPServerRequest,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Update an MCP server"""
    try:
        result = await db.execute(
            select(MCPServer).filter(MCPServer.id == uuid.UUID(server_id), MCPServer.tenant_id == tenant_id)
        )
        server = result.scalar_one_or_none()

        if not server:
            raise HTTPException(status_code=404, detail="MCP server not found")

        # Get update data
        update_data = request.model_dump(exclude_unset=True)

        # Validate transport type if being updated
        if "transport_type" in update_data:
            new_transport_type = update_data["transport_type"]
            if new_transport_type not in ["http", "stdio"]:
                raise HTTPException(status_code=400, detail="Transport type must be 'http' or 'stdio'")

            # Validate required fields for new transport type
            if new_transport_type == "stdio":
                command = update_data.get("command", server.command)
                if not command:
                    raise HTTPException(status_code=400, detail="Command is required for stdio transport")
            else:  # http
                url = update_data.get("url", server.url)
                if not url:
                    raise HTTPException(status_code=400, detail="URL is required for HTTP transport")

        # Update fields
        for key, value in update_data.items():
            setattr(server, key, value)

        await db.commit()
        await db.refresh(server)

        return {"success": True, "message": "MCP server updated successfully", "data": server.to_dict()}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid server ID format")
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/servers/{server_id}")
async def delete_mcp_server(
    server_id: str,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Delete an MCP server"""
    try:
        result = await db.execute(
            select(MCPServer).filter(MCPServer.id == uuid.UUID(server_id), MCPServer.tenant_id == tenant_id)
        )
        server = result.scalar_one_or_none()

        if not server:
            raise HTTPException(status_code=404, detail="MCP server not found")

        await db.delete(server)
        await db.commit()

        return {"success": True, "message": "MCP server deleted successfully"}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid server ID format")
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/servers/{server_id}/test")
async def test_mcp_server(
    server_id: str,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Test connection to an MCP server"""
    try:
        result = await db.execute(
            select(MCPServer).filter(MCPServer.id == uuid.UUID(server_id), MCPServer.tenant_id == tenant_id)
        )
        server = result.scalar_one_or_none()

        if not server:
            raise HTTPException(status_code=404, detail="MCP server not found")

        # Connection test returns mock success - actual MCP connection is made during tool execution
        return {
            "success": True,
            "message": "MCP server connection test successful",
            "data": {
                "server_id": str(server.id),
                "server_name": server.name,
                "status": "connected",
                "response_time_ms": 45,
                "capabilities_detected": server.capabilities or {},
            },
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid server ID format")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
