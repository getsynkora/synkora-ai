"""
Project Service

Service for managing lightweight projects.
Projects group agents and provide shared context without built-in task management.
Task management uses existing Jira/ClickUp/GitHub integrations.
"""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.models import Agent, KnowledgeBase, Project, ProjectAgent, ProjectStatus

logger = logging.getLogger(__name__)


class ProjectService:
    """Service for managing projects and project-agent associations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _validate_knowledge_base(self, knowledge_base_id: int | None, tenant_id: UUID) -> None:
        if knowledge_base_id is None:
            return
        result = await self.db.execute(
            select(KnowledgeBase.id).where(KnowledgeBase.id == knowledge_base_id, KnowledgeBase.tenant_id == tenant_id)
        )
        if result.scalar_one_or_none() is None:
            raise ValueError("Knowledge base not found")

    async def create_project(
        self,
        tenant_id: UUID,
        name: str,
        description: str | None = None,
        status: str = ProjectStatus.ACTIVE.value,
        knowledge_base_id: int | None = None,
        external_project_ref: dict[str, str] | None = None,
        project_settings: dict[str, Any] | None = None,
    ) -> Project:
        """
        Create a new project.

        Args:
            tenant_id: Tenant identifier
            name: Project name
            description: Project description
            status: Project status
            knowledge_base_id: Optional shared knowledge base
            external_project_ref: External PM tool references
            project_settings: Project-specific settings

        Returns:
            Created Project instance
        """
        await self._validate_knowledge_base(knowledge_base_id, tenant_id)
        project = Project(
            tenant_id=tenant_id,
            name=name,
            description=description,
            status=status,
            knowledge_base_id=knowledge_base_id,
            external_project_ref=external_project_ref or {},
            shared_context={},
            project_settings=project_settings or {},
        )

        self.db.add(project)
        await self.db.commit()
        await self.db.refresh(project)

        logger.info(f"Created project: {name} (id={project.id})")
        return project

    async def get_project(self, project_id: UUID, tenant_id: UUID | None = None) -> Project | None:
        """Get a project by ID, optionally scoped to a tenant."""
        stmt = select(Project).filter(Project.id == project_id)
        if tenant_id is not None:
            stmt = stmt.filter(Project.tenant_id == tenant_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_project_with_agents(self, project_id: UUID, tenant_id: UUID | None = None) -> dict[str, Any] | None:
        """
        Get a project with its associated agents.

        Args:
            project_id: Project ID
            tenant_id: Optional tenant ID for access control

        Returns:
            Dictionary with project data and agents list
        """
        # Eager load agents and their associated agent details to prevent N+1 queries
        stmt = (
            select(Project)
            .options(joinedload(Project.agents).joinedload(ProjectAgent.agent))
            .filter(Project.id == project_id)
        )
        if tenant_id is not None:
            stmt = stmt.filter(Project.tenant_id == tenant_id)
        result = await self.db.execute(stmt)
        project = result.unique().scalar_one_or_none()
        if not project:
            return None

        agents = [
            {
                "id": str(pa.agent.id),
                "name": pa.agent.agent_name,
                "type": pa.agent.agent_type,
                "role_id": str(pa.agent.role_id) if pa.agent.role_id else None,
                "human_contact_id": str(pa.agent.human_contact_id) if pa.agent.human_contact_id else None,
            }
            for pa in project.agents
            if pa.agent
        ]

        return {"project": project.to_dict(), "agents": agents}

    async def list_projects(
        self, tenant_id: UUID, status: str | None = None, search: str | None = None
    ) -> list[Project]:
        """
        List projects for a tenant.

        Args:
            tenant_id: Tenant identifier
            status: Optional status filter
            search: Optional search string

        Returns:
            List of Project instances
        """
        # Eager load agents and their associated agent details to prevent N+1 queries
        stmt = (
            select(Project)
            .options(joinedload(Project.agents).joinedload(ProjectAgent.agent))
            .filter(Project.tenant_id == tenant_id)
        )

        if status:
            stmt = stmt.filter(Project.status == status)

        if search:
            search_pattern = f"%{search}%"
            stmt = stmt.filter((Project.name.ilike(search_pattern)) | (Project.description.ilike(search_pattern)))

        stmt = stmt.order_by(Project.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.unique().scalars().all())

    async def update_project(self, project_id: UUID, tenant_id: UUID, **kwargs) -> Project | None:
        """
        Update a project.

        Args:
            project_id: Project ID to update
            tenant_id: Tenant ID for validation
            **kwargs: Fields to update

        Returns:
            Updated Project or None if not found
        """
        result = await self.db.execute(
            select(Project).filter(and_(Project.id == project_id, Project.tenant_id == tenant_id))
        )
        project = result.scalar_one_or_none()

        if not project:
            logger.warning(f"Project not found or access denied: {project_id}")
            return None

        if "knowledge_base_id" in kwargs:
            await self._validate_knowledge_base(kwargs["knowledge_base_id"], tenant_id)

        # Update allowed fields
        allowed_fields = {
            "name",
            "description",
            "status",
            "knowledge_base_id",
            "external_project_ref",
            "project_settings",
        }

        for key, value in kwargs.items():
            if key in allowed_fields:
                setattr(project, key, value)

        await self.db.commit()
        await self.db.refresh(project)

        logger.info(f"Updated project: {project_id}")
        return project

    async def delete_project(self, project_id: UUID, tenant_id: UUID) -> bool:
        """
        Delete a project.

        Args:
            project_id: Project ID to delete
            tenant_id: Tenant ID for validation

        Returns:
            True if deleted, False otherwise
        """
        result = await self.db.execute(
            select(Project).filter(and_(Project.id == project_id, Project.tenant_id == tenant_id))
        )
        project = result.scalar_one_or_none()

        if not project:
            logger.warning(f"Project not found or access denied: {project_id}")
            return False

        await self.db.delete(project)
        await self.db.commit()

        logger.info(f"Deleted project: {project_id}")
        return True

    async def archive_project(self, project_id: UUID, tenant_id: UUID) -> Project | None:
        """Archive a project instead of deleting."""
        return await self.update_project(project_id, tenant_id, status=ProjectStatus.ARCHIVED.value)

    # Shared Context Management

    async def get_context(self, project_id: UUID, tenant_id: UUID | None = None) -> dict[str, Any] | None:
        """
        Get shared context for a project.

        Args:
            project_id: Project ID
            tenant_id: Optional tenant ID for access control

        Returns:
            Shared context dictionary or None if project not found
        """
        project = await self.get_project(project_id, tenant_id=tenant_id)
        if not project:
            return None
        return project.shared_context or {}

    async def update_context(self, project_id: UUID, tenant_id: UUID, context: dict[str, Any]) -> Project | None:
        """
        Replace shared context for a project.

        Args:
            project_id: Project ID
            tenant_id: Tenant ID for validation
            context: New context dictionary

        Returns:
            Updated Project or None
        """
        result = await self.db.execute(
            select(Project).filter(and_(Project.id == project_id, Project.tenant_id == tenant_id))
        )
        project = result.scalar_one_or_none()

        if not project:
            return None

        project.shared_context = context
        await self.db.commit()
        await self.db.refresh(project)

        logger.info(f"Updated context for project: {project_id}")
        return project

    async def set_context_value(self, project_id: UUID, tenant_id: UUID, key: str, value: Any) -> Project | None:
        """
        Set a single value in shared context.

        Args:
            project_id: Project ID
            tenant_id: Tenant ID for validation
            key: Context key
            value: Value to set

        Returns:
            Updated Project or None
        """
        result = await self.db.execute(
            select(Project).filter(and_(Project.id == project_id, Project.tenant_id == tenant_id))
        )
        project = result.scalar_one_or_none()

        if not project:
            return None

        if project.shared_context is None:
            project.shared_context = {}

        project.shared_context[key] = value

        # Mark as modified for SQLAlchemy
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(project, "shared_context")

        await self.db.commit()
        await self.db.refresh(project)

        logger.debug(f"Set context key '{key}' for project: {project_id}")
        return project

    async def delete_context_key(self, project_id: UUID, tenant_id: UUID, key: str) -> Project | None:
        """
        Delete a key from shared context.

        Args:
            project_id: Project ID
            tenant_id: Tenant ID for validation
            key: Context key to delete

        Returns:
            Updated Project or None
        """
        result = await self.db.execute(
            select(Project).filter(and_(Project.id == project_id, Project.tenant_id == tenant_id))
        )
        project = result.scalar_one_or_none()

        if not project or not project.shared_context:
            return project

        if key in project.shared_context:
            del project.shared_context[key]

            from sqlalchemy.orm.attributes import flag_modified

            flag_modified(project, "shared_context")

            await self.db.commit()
            await self.db.refresh(project)

        return project

    # Project-Agent Management

    async def add_agent_to_project(self, project_id: UUID, agent_id: UUID, tenant_id: UUID) -> ProjectAgent | None:
        """
        Add an agent to a project.

        Args:
            project_id: Project ID
            agent_id: Agent ID to add
            tenant_id: Tenant ID for validation

        Returns:
            Created ProjectAgent association or None
        """
        # Validate project belongs to tenant
        result = await self.db.execute(
            select(Project).filter(and_(Project.id == project_id, Project.tenant_id == tenant_id))
        )
        project = result.scalar_one_or_none()

        if not project:
            logger.warning(f"Project not found or access denied: {project_id}")
            return None

        # Validate agent belongs to tenant
        result = await self.db.execute(select(Agent).filter(and_(Agent.id == agent_id, Agent.tenant_id == tenant_id)))
        agent = result.scalar_one_or_none()

        if not agent:
            logger.warning(f"Agent not found or access denied: {agent_id}")
            return None

        # Check if already linked
        result = await self.db.execute(
            select(ProjectAgent).filter(and_(ProjectAgent.project_id == project_id, ProjectAgent.agent_id == agent_id))
        )
        existing = result.scalar_one_or_none()

        if existing:
            logger.debug(f"Agent {agent_id} already in project {project_id}")
            return existing

        # Create association
        project_agent = ProjectAgent(project_id=project_id, agent_id=agent_id)

        self.db.add(project_agent)
        await self.db.commit()
        await self.db.refresh(project_agent)

        logger.info(f"Added agent {agent_id} to project {project_id}")
        return project_agent

    async def remove_agent_from_project(self, project_id: UUID, agent_id: UUID, tenant_id: UUID) -> bool:
        """
        Remove an agent from a project.

        Args:
            project_id: Project ID
            agent_id: Agent ID to remove
            tenant_id: Tenant ID for validation

        Returns:
            True if removed, False otherwise
        """
        # Validate project belongs to tenant
        result = await self.db.execute(
            select(Project).filter(and_(Project.id == project_id, Project.tenant_id == tenant_id))
        )
        project = result.scalar_one_or_none()

        if not project:
            return False

        # Find and delete association
        result = await self.db.execute(
            select(ProjectAgent).filter(and_(ProjectAgent.project_id == project_id, ProjectAgent.agent_id == agent_id))
        )
        project_agent = result.scalar_one_or_none()

        if not project_agent:
            return False

        await self.db.delete(project_agent)
        await self.db.commit()

        logger.info(f"Removed agent {agent_id} from project {project_id}")
        return True

    async def get_project_agents(self, project_id: UUID, tenant_id: UUID | None = None) -> list[Agent]:
        """
        Get all agents for a project.

        Args:
            project_id: Project ID
            tenant_id: Optional tenant ID for access control

        Returns:
            List of Agent instances
        """
        # Eager load agents to prevent N+1 queries
        stmt = (
            select(Project)
            .options(joinedload(Project.agents).joinedload(ProjectAgent.agent))
            .filter(Project.id == project_id)
        )
        if tenant_id is not None:
            stmt = stmt.filter(Project.tenant_id == tenant_id)
        result = await self.db.execute(stmt)
        project = result.unique().scalar_one_or_none()
        if not project:
            return []

        return [pa.agent for pa in project.agents if pa.agent]

    async def get_agent_projects(self, agent_id: UUID) -> list[Project]:
        """
        Get all projects an agent is part of.

        Args:
            agent_id: Agent ID

        Returns:
            List of Project instances
        """
        # Eager load projects to prevent N+1 queries
        result = await self.db.execute(
            select(ProjectAgent).options(joinedload(ProjectAgent.project)).filter(ProjectAgent.agent_id == agent_id)
        )
        project_agents = list(result.unique().scalars().all())

        return [pa.project for pa in project_agents if pa.project]
