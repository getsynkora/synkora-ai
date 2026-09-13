"""
Agent API endpoints.

Provides REST API endpoints for managing and executing Google Agent SDK agents.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.controllers.agents.models import AgentResponse
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id, require_role
from src.models import AccountRole
from src.models.agent import Agent
from src.services.agents.agent_manager import AgentManager

logger = logging.getLogger(__name__)

# Create router
agents_custom_tools_router = APIRouter()

# Global agent manager instance
agent_manager = AgentManager()


# Custom Tool Operations Management Endpoints


@agents_custom_tools_router.get("/{agent_id}/custom-tools/{custom_tool_id}/operations", response_model=AgentResponse)
async def list_custom_tool_operations(
    agent_id: str,
    custom_tool_id: str,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List all operations from a custom tool and show which are enabled for the agent.

    Args:
        agent_id: UUID of the agent
        custom_tool_id: UUID of the custom tool
        db: Database session

    Returns:
        List of operations with enabled status
    """
    try:
        from src.models.agent_tool import AgentTool
        from src.models.custom_tool import CustomTool
        from src.services.custom_tools import OpenAPIParser

        # Convert string to UUID
        try:
            agent_uuid = uuid.UUID(agent_id)
            custom_tool_uuid = uuid.UUID(custom_tool_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ID format")

        # SECURITY: Verify agent exists AND belongs to current tenant (prevents IDOR)
        result = await db.execute(select(Agent).filter(Agent.id == agent_uuid, Agent.tenant_id == tenant_id))
        agent = result.scalar_one_or_none()
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent with ID '{agent_id}' not found")

        # SECURITY: Verify custom tool belongs to current tenant (prevents IDOR)
        result = await db.execute(
            select(CustomTool).filter(CustomTool.id == custom_tool_uuid, CustomTool.tenant_id == tenant_id)
        )
        custom_tool = result.scalar_one_or_none()

        if not custom_tool:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Custom tool with ID '{custom_tool_id}' not found"
            )

        # Parse OpenAPI schema to get operations
        parser = OpenAPIParser(schema=custom_tool.openapi_schema, server_url=custom_tool.server_url)
        operations = parser.get_available_operations()

        # Get enabled operations for this agent
        result = await db.execute(
            select(AgentTool).filter(AgentTool.agent_id == agent_uuid, AgentTool.custom_tool_id == custom_tool_uuid)
        )
        enabled_operations = result.scalars().all()

        enabled_operation_ids = {tool.operation_id for tool in enabled_operations}

        # Build response with enabled status
        operations_list = []
        for op in operations:
            operations_list.append(
                {
                    "operation_id": op["operation_id"],
                    "method": op["method"],
                    "path": op["path"],
                    "summary": op.get("summary", ""),
                    "description": op.get("description", ""),
                    "parameters": op.get("parameters", []),
                    "enabled": op["operation_id"] in enabled_operation_ids,
                }
            )

        return AgentResponse(
            success=True,
            message=f"Found {len(operations_list)} operations",
            data={
                "custom_tool_id": str(custom_tool_uuid),
                "custom_tool_name": custom_tool.name,
                "operations": operations_list,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list custom tool operations: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list operations")


@agents_custom_tools_router.post(
    "/{agent_id}/custom-tools/{custom_tool_id}/operations/{operation_id}",
    response_model=AgentResponse,
    dependencies=[Depends(require_role(AccountRole.ADMIN))],
)
async def enable_custom_tool_operation(
    agent_id: str,
    custom_tool_id: str,
    operation_id: str,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Enable a specific operation from a custom tool for an agent.

    Args:
        agent_id: UUID of the agent
        custom_tool_id: UUID of the custom tool
        operation_id: Operation ID from OpenAPI schema
        db: Database session

    Returns:
        Success confirmation
    """
    try:
        from src.models.agent_tool import AgentTool
        from src.models.custom_tool import CustomTool

        # Convert string to UUID
        try:
            agent_uuid = uuid.UUID(agent_id)
            custom_tool_uuid = uuid.UUID(custom_tool_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ID format")

        # SECURITY: Verify agent exists AND belongs to current tenant (prevents IDOR)
        result = await db.execute(select(Agent).filter(Agent.id == agent_uuid, Agent.tenant_id == tenant_id))
        agent = result.scalar_one_or_none()
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent with ID '{agent_id}' not found")

        # SECURITY: Verify custom tool belongs to current tenant (prevents IDOR)
        result = await db.execute(
            select(CustomTool).filter(CustomTool.id == custom_tool_uuid, CustomTool.tenant_id == tenant_id)
        )
        custom_tool = result.scalar_one_or_none()

        if not custom_tool:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Custom tool with ID '{custom_tool_id}' not found"
            )

        # Check if operation already enabled
        result = await db.execute(
            select(AgentTool).filter(
                AgentTool.agent_id == agent_uuid,
                AgentTool.custom_tool_id == custom_tool_uuid,
                AgentTool.operation_id == operation_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            return AgentResponse(
                success=True, message=f"Operation '{operation_id}' already enabled", data={"operation_id": operation_id}
            )

        # Generate unique tool name: customtoolname_operationid
        tool_name = f"{custom_tool.name.lower().replace(' ', '_')}_{operation_id}"

        # Create agent tool entry
        agent_tool = AgentTool(
            agent_id=agent_uuid,
            tool_name=tool_name,
            custom_tool_id=custom_tool_uuid,
            operation_id=operation_id,
            config={},
            enabled=True,
        )

        db.add(agent_tool)
        await db.commit()

        return AgentResponse(
            success=True,
            message=f"Operation '{operation_id}' enabled successfully",
            data={"operation_id": operation_id, "tool_name": tool_name},
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to enable custom tool operation: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to enable operation")


@agents_custom_tools_router.delete(
    "/{agent_id}/custom-tools/{custom_tool_id}/operations/{operation_id}",
    response_model=AgentResponse,
    dependencies=[Depends(require_role(AccountRole.ADMIN))],
)
async def disable_custom_tool_operation(
    agent_id: str,
    custom_tool_id: str,
    operation_id: str,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Disable a specific operation from a custom tool for an agent.

    Args:
        agent_id: UUID of the agent
        custom_tool_id: UUID of the custom tool
        operation_id: Operation ID from OpenAPI schema
        db: Database session

    Returns:
        Deletion confirmation
    """
    try:
        from src.models.agent_tool import AgentTool

        # Convert string to UUID
        try:
            agent_uuid = uuid.UUID(agent_id)
            custom_tool_uuid = uuid.UUID(custom_tool_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ID format")

        # SECURITY: Verify agent exists AND belongs to current tenant (prevents IDOR)
        result = await db.execute(select(Agent).filter(Agent.id == agent_uuid, Agent.tenant_id == tenant_id))
        agent = result.scalar_one_or_none()
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent with ID '{agent_id}' not found")

        # Find and delete the agent tool entry
        result = await db.execute(
            select(AgentTool).filter(
                AgentTool.agent_id == agent_uuid,
                AgentTool.custom_tool_id == custom_tool_uuid,
                AgentTool.operation_id == operation_id,
            )
        )
        agent_tool = result.scalar_one_or_none()

        if not agent_tool:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Operation '{operation_id}' not enabled for this agent"
            )

        await db.delete(agent_tool)
        await db.commit()

        return AgentResponse(success=True, message=f"Operation '{operation_id}' disabled successfully")

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to disable custom tool operation: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to disable operation")
