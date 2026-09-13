"""
Agent Roles Controller

API endpoints for managing agent role templates (PM, QA, BA, etc.).
"""

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id
from src.models import AgentRoleType
from src.services.roles.agent_role_service import AgentRoleService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent-roles", tags=["agent-roles"])


# Request/Response Models


class CreateRoleRequest(BaseModel):
    """Request model for creating a role."""

    role_type: str = Field(..., description="Role type (use 'custom' for custom roles)")
    role_name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    system_prompt_template: str = Field(..., min_length=1)
    suggested_tools: list[str] | None = None
    default_capabilities: dict[str, Any] | None = None


class UpdateRoleRequest(BaseModel):
    """Request model for updating a role."""

    role_name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    system_prompt_template: str | None = None
    suggested_tools: list[str] | None = None
    default_capabilities: dict[str, Any] | None = None


class RoleResponse(BaseModel):
    """Response model for a role."""

    id: str
    role_type: str
    role_name: str
    description: str | None
    system_prompt_template: str
    suggested_tools: list[str] | None
    default_capabilities: dict[str, Any] | None
    is_system_template: bool
    created_at: str
    updated_at: str


class CloneRoleRequest(BaseModel):
    """Request model for cloning a role."""

    new_name: str = Field(..., min_length=1, max_length=255)


# Endpoints


@router.get("", response_model=list[RoleResponse])
async def list_roles(
    include_system: bool = Query(True, description="Include system templates"),
    role_type: str | None = Query(None, description="Filter by role type"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """List all available agent roles."""
    try:
        service = AgentRoleService(db)
        roles = await service.list_roles(tenant_id=tenant_id, include_system=include_system, role_type=role_type)

        return [
            RoleResponse(
                id=str(role.id),
                role_type=role.role_type,
                role_name=role.role_name,
                description=role.description,
                system_prompt_template=role.system_prompt_template,
                suggested_tools=role.suggested_tools,
                default_capabilities=role.default_capabilities,
                is_system_template=role.is_system_template,
                created_at=role.created_at.isoformat() if role.created_at else None,
                updated_at=role.updated_at.isoformat() if role.updated_at else None,
            )
            for role in roles
        ]
    except Exception as e:
        logger.error(f"Error listing roles: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/types")
async def list_role_types():
    """List available role types."""
    return {
        "success": True,
        "data": [{"value": rt.value, "label": rt.value.replace("_", " ").title()} for rt in AgentRoleType],
    }


@router.post("", response_model=RoleResponse, status_code=201)
async def create_role(
    request: CreateRoleRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Create a new custom role."""
    try:
        service = AgentRoleService(db)

        role = await service.create_role(
            tenant_id=tenant_id,
            role_type=request.role_type,
            role_name=request.role_name,
            description=request.description,
            system_prompt_template=request.system_prompt_template,
            suggested_tools=request.suggested_tools,
            default_capabilities=request.default_capabilities,
            is_system_template=False,
        )

        return RoleResponse(
            id=str(role.id),
            role_type=role.role_type,
            role_name=role.role_name,
            description=role.description,
            system_prompt_template=role.system_prompt_template,
            suggested_tools=role.suggested_tools,
            default_capabilities=role.default_capabilities,
            is_system_template=role.is_system_template,
            created_at=role.created_at.isoformat() if role.created_at else None,
            updated_at=role.updated_at.isoformat() if role.updated_at else None,
        )
    except Exception as e:
        logger.error(f"Error creating role: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: str, tenant_id: UUID = Depends(get_current_tenant_id), db: AsyncSession = Depends(get_async_db)
):
    """Get a specific role."""
    try:
        service = AgentRoleService(db)
        # SECURITY: Pass tenant_id to filter in the query itself (prevents cross-tenant reads)
        role = await service.get_role(UUID(role_id), tenant_id=tenant_id)

        if not role:
            raise HTTPException(status_code=404, detail="Role not found")

        return RoleResponse(
            id=str(role.id),
            role_type=role.role_type,
            role_name=role.role_name,
            description=role.description,
            system_prompt_template=role.system_prompt_template,
            suggested_tools=role.suggested_tools,
            default_capabilities=role.default_capabilities,
            is_system_template=role.is_system_template,
            created_at=role.created_at.isoformat() if role.created_at else None,
            updated_at=role.updated_at.isoformat() if role.updated_at else None,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid role ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting role: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: str,
    request: UpdateRoleRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Update a custom role. System templates cannot be modified."""
    try:
        service = AgentRoleService(db)

        update_data = request.model_dump(exclude_unset=True)
        role = await service.update_role(role_id=UUID(role_id), tenant_id=tenant_id, **update_data)

        if not role:
            raise HTTPException(
                status_code=404, detail="Role not found or cannot be modified (system templates are read-only)"
            )

        return RoleResponse(
            id=str(role.id),
            role_type=role.role_type,
            role_name=role.role_name,
            description=role.description,
            system_prompt_template=role.system_prompt_template,
            suggested_tools=role.suggested_tools,
            default_capabilities=role.default_capabilities,
            is_system_template=role.is_system_template,
            created_at=role.created_at.isoformat() if role.created_at else None,
            updated_at=role.updated_at.isoformat() if role.updated_at else None,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid role ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating role: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{role_id}", status_code=204)
async def delete_role(
    role_id: str, tenant_id: UUID = Depends(get_current_tenant_id), db: AsyncSession = Depends(get_async_db)
):
    """Delete a custom role. System templates cannot be deleted."""
    try:
        service = AgentRoleService(db)

        success = await service.delete_role(role_id=UUID(role_id), tenant_id=tenant_id)

        if not success:
            raise HTTPException(
                status_code=404, detail="Role not found or cannot be deleted (system templates are read-only)"
            )

        return None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid role ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting role: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{role_id}/clone", response_model=RoleResponse, status_code=201)
async def clone_role(
    role_id: str,
    request: CloneRoleRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Clone an existing role (including system templates) to create a custom version."""
    try:
        service = AgentRoleService(db)

        role = await service.clone_role(role_id=UUID(role_id), tenant_id=tenant_id, new_name=request.new_name)

        if not role:
            raise HTTPException(status_code=404, detail="Source role not found")

        return RoleResponse(
            id=str(role.id),
            role_type=role.role_type,
            role_name=role.role_name,
            description=role.description,
            system_prompt_template=role.system_prompt_template,
            suggested_tools=role.suggested_tools,
            default_capabilities=role.default_capabilities,
            is_system_template=role.is_system_template,
            created_at=role.created_at.isoformat() if role.created_at else None,
            updated_at=role.updated_at.isoformat() if role.updated_at else None,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid role ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cloning role: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/seed", status_code=201)
async def seed_system_roles(tenant_id: UUID = Depends(get_current_tenant_id), db: AsyncSession = Depends(get_async_db)):
    """
    Seed default system role templates.

    This endpoint creates the default role templates if they don't exist.
    Usually called during system initialization.
    """
    try:
        service = AgentRoleService(db)
        roles = await service.seed_system_roles(system_tenant_id=tenant_id)

        return {
            "success": True,
            "message": f"Seeded {len(roles)} system role templates",
            "data": {
                "roles": [
                    {"id": str(role.id), "role_type": role.role_type, "role_name": role.role_name} for role in roles
                ]
            },
        }
    except Exception as e:
        logger.error(f"Error seeding roles: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")
