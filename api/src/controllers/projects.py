"""
Projects Controller

API endpoints for managing lightweight projects.
Projects group agents and provide shared context.
"""

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id
from src.services.roles.project_service import ProjectService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["projects"])


# Request/Response Models


class CreateProjectRequest(BaseModel):
    """Request model for creating a project."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    status: str = Field(default="active", pattern="^(active|on_hold|completed|archived)$")
    knowledge_base_id: str | None = None
    external_project_ref: dict[str, str] | None = None
    project_settings: dict[str, Any] | None = None


class UpdateProjectRequest(BaseModel):
    """Request model for updating a project."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = Field(None, pattern="^(active|on_hold|completed|archived)$")
    knowledge_base_id: str | None = None
    external_project_ref: dict[str, str] | None = None
    project_settings: dict[str, Any] | None = None


class AddAgentRequest(BaseModel):
    """Request model for adding an agent to a project."""

    agent_id: str


class UpdateContextRequest(BaseModel):
    """Request model for updating project context."""

    context: dict[str, Any]


class SetContextValueRequest(BaseModel):
    """Request model for setting a single context value."""

    key: str
    value: Any


class AgentSummary(BaseModel):
    """Summary of an agent in a project."""

    id: str
    name: str
    agent_name: str  # Added for frontend compatibility
    type: str
    role_id: str | None
    human_contact_id: str | None


class ProjectResponse(BaseModel):
    """Response model for a project."""

    id: str
    name: str
    description: str | None
    status: str
    knowledge_base_id: str | None
    external_project_ref: dict[str, str] | None
    shared_context: dict[str, Any] | None
    project_settings: dict[str, Any] | None
    created_at: str
    updated_at: str


class ProjectWithAgentsResponse(ProjectResponse):
    """Response model for a project with agents."""

    agents: list[AgentSummary]


# Endpoints


@router.get("", response_model=list[ProjectWithAgentsResponse])
async def list_projects(
    status: str | None = Query(None, description="Filter by status"),
    search: str | None = Query(None, description="Search by name or description"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """List all projects with their agents."""
    try:
        service = ProjectService(db)
        projects = await service.list_projects(tenant_id=tenant_id, status=status, search=search)

        return [
            ProjectWithAgentsResponse(
                id=str(project.id),
                name=project.name,
                description=project.description,
                status=project.status,
                knowledge_base_id=str(project.knowledge_base_id) if project.knowledge_base_id else None,
                external_project_ref=project.external_project_ref,
                shared_context=project.shared_context,
                project_settings=project.project_settings,
                created_at=project.created_at.isoformat() if project.created_at else None,
                updated_at=project.updated_at.isoformat() if project.updated_at else None,
                agents=[
                    AgentSummary(
                        id=str(pa.agent.id),
                        name=pa.agent.agent_name,
                        agent_name=pa.agent.agent_name,
                        type=pa.agent.agent_type,
                        role_id=str(pa.agent.role_id) if pa.agent.role_id else None,
                        human_contact_id=str(pa.agent.human_contact_id) if pa.agent.human_contact_id else None,
                    )
                    for pa in project.agents
                    if pa.agent
                ],
            )
            for project in projects
        ]
    except Exception as e:
        logger.error(f"Error listing projects: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    request: CreateProjectRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Create a new project."""
    try:
        service = ProjectService(db)

        project = await service.create_project(
            tenant_id=tenant_id,
            name=request.name,
            description=request.description,
            status=request.status,
            knowledge_base_id=int(request.knowledge_base_id) if request.knowledge_base_id else None,
            external_project_ref=request.external_project_ref,
            project_settings=request.project_settings,
        )

        return ProjectResponse(
            id=str(project.id),
            name=project.name,
            description=project.description,
            status=project.status,
            knowledge_base_id=str(project.knowledge_base_id) if project.knowledge_base_id else None,
            external_project_ref=project.external_project_ref,
            shared_context=project.shared_context,
            project_settings=project.project_settings,
            created_at=project.created_at.isoformat() if project.created_at else None,
            updated_at=project.updated_at.isoformat() if project.updated_at else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error creating project: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{project_id}", response_model=ProjectWithAgentsResponse)
async def get_project(
    project_id: str, tenant_id: UUID = Depends(get_current_tenant_id), db: AsyncSession = Depends(get_async_db)
):
    """Get a project with its agents."""
    try:
        service = ProjectService(db)
        # SECURITY: Pass tenant_id into the query to prevent cross-tenant reads
        result = await service.get_project_with_agents(UUID(project_id), tenant_id=tenant_id)

        if not result:
            raise HTTPException(status_code=404, detail="Project not found")

        project_data = result["project"]

        return ProjectWithAgentsResponse(
            id=project_data["id"],
            name=project_data["name"],
            description=project_data.get("description"),
            status=project_data["status"],
            knowledge_base_id=project_data.get("knowledge_base_id"),
            external_project_ref=project_data.get("external_project_ref"),
            shared_context=project_data.get("shared_context"),
            project_settings=project_data.get("project_settings"),
            created_at=project_data.get("created_at"),
            updated_at=project_data.get("updated_at"),
            agents=[
                AgentSummary(
                    id=agent["id"],
                    name=agent["name"],
                    agent_name=agent["name"],
                    type=agent["type"],
                    role_id=agent.get("role_id"),
                    human_contact_id=agent.get("human_contact_id"),
                )
                for agent in result["agents"]
            ],
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting project: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    request: UpdateProjectRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Update a project."""
    try:
        service = ProjectService(db)

        update_data = request.model_dump(exclude_unset=True)

        # Convert knowledge_base_id to int if present
        if "knowledge_base_id" in update_data and update_data["knowledge_base_id"]:
            update_data["knowledge_base_id"] = int(update_data["knowledge_base_id"])

        project = await service.update_project(project_id=UUID(project_id), tenant_id=tenant_id, **update_data)

        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        return ProjectResponse(
            id=str(project.id),
            name=project.name,
            description=project.description,
            status=project.status,
            knowledge_base_id=str(project.knowledge_base_id) if project.knowledge_base_id else None,
            external_project_ref=project.external_project_ref,
            shared_context=project.shared_context,
            project_settings=project.project_settings,
            created_at=project.created_at.isoformat() if project.created_at else None,
            updated_at=project.updated_at.isoformat() if project.updated_at else None,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating project: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: str, tenant_id: UUID = Depends(get_current_tenant_id), db: AsyncSession = Depends(get_async_db)
):
    """Delete a project."""
    try:
        service = ProjectService(db)

        success = await service.delete_project(project_id=UUID(project_id), tenant_id=tenant_id)

        if not success:
            raise HTTPException(status_code=404, detail="Project not found")

        return None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting project: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


# Shared Context Endpoints


@router.get("/{project_id}/context")
async def get_project_context(
    project_id: str, tenant_id: UUID = Depends(get_current_tenant_id), db: AsyncSession = Depends(get_async_db)
):
    """Get shared context for a project."""
    try:
        service = ProjectService(db)
        # SECURITY: Pass tenant_id into the query to prevent cross-tenant reads
        project = await service.get_project(UUID(project_id), tenant_id=tenant_id)

        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        return {"success": True, "data": {"project_id": str(project.id), "context": project.shared_context or {}}}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting context: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{project_id}/context")
async def update_project_context(
    project_id: str,
    request: UpdateContextRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Replace shared context for a project."""
    try:
        service = ProjectService(db)

        project = await service.update_context(
            project_id=UUID(project_id), tenant_id=tenant_id, context=request.context
        )

        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        return {"success": True, "data": {"project_id": str(project.id), "context": project.shared_context}}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating context: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{project_id}/context")
async def set_context_value(
    project_id: str,
    request: SetContextValueRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Set a single value in shared context."""
    try:
        service = ProjectService(db)

        project = await service.set_context_value(
            project_id=UUID(project_id), tenant_id=tenant_id, key=request.key, value=request.value
        )

        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        return {"success": True, "data": {"project_id": str(project.id), "key": request.key, "value": request.value}}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting context value: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{project_id}/context/{key}")
async def delete_context_key(
    project_id: str,
    key: str,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Delete a key from shared context."""
    try:
        service = ProjectService(db)

        project = await service.delete_context_key(project_id=UUID(project_id), tenant_id=tenant_id, key=key)

        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        return {"success": True, "message": f"Key '{key}' deleted from context"}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting context key: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


# Project-Agent Management


@router.post("/{project_id}/agents", status_code=201)
async def add_agent_to_project(
    project_id: str,
    request: AddAgentRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Add an agent to a project."""
    try:
        service = ProjectService(db)

        project_agent = await service.add_agent_to_project(
            project_id=UUID(project_id), agent_id=UUID(request.agent_id), tenant_id=tenant_id
        )

        if not project_agent:
            raise HTTPException(status_code=404, detail="Project or agent not found")

        return {
            "success": True,
            "message": "Agent added to project",
            "data": {"project_id": str(project_agent.project_id), "agent_id": str(project_agent.agent_id)},
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding agent to project: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{project_id}/agents/{agent_id}", status_code=204)
async def remove_agent_from_project(
    project_id: str,
    agent_id: str,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Remove an agent from a project."""
    try:
        service = ProjectService(db)

        success = await service.remove_agent_from_project(
            project_id=UUID(project_id), agent_id=UUID(agent_id), tenant_id=tenant_id
        )

        if not success:
            raise HTTPException(status_code=404, detail="Project-agent association not found")

        return None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing agent from project: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{project_id}/agents", response_model=list[AgentSummary])
async def get_project_agents(
    project_id: str, tenant_id: UUID = Depends(get_current_tenant_id), db: AsyncSession = Depends(get_async_db)
):
    """Get all agents for a project."""
    try:
        service = ProjectService(db)

        # SECURITY: Pass tenant_id into the query to prevent cross-tenant reads
        project = await service.get_project(UUID(project_id), tenant_id=tenant_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        agents = await service.get_project_agents(UUID(project_id), tenant_id=tenant_id)

        return [
            AgentSummary(
                id=str(agent.id),
                name=agent.agent_name,
                agent_name=agent.agent_name,
                type=agent.agent_type,
                role_id=str(agent.role_id) if agent.role_id else None,
                human_contact_id=str(agent.human_contact_id) if agent.human_contact_id else None,
            )
            for agent in agents
        ]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting project agents: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
