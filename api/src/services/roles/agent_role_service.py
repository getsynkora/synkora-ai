"""
Agent Role Service

Service for managing agent role templates (PM, QA, BA, etc.).
Handles CRUD operations and seeding of system default roles.
"""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import AgentRole, AgentRoleType

logger = logging.getLogger(__name__)


# Default system role templates
DEFAULT_ROLE_TEMPLATES = [
    {
        "role_type": AgentRoleType.PROJECT_MANAGER.value,
        "role_name": "Project Manager",
        "description": "Coordinates project activities, tracks timelines, manages risks, and facilitates communication between stakeholders.",
        "system_prompt_template": """You are a Project Manager AI assistant for the project "{project_name}".

Project Description: {project_description}

Your human counterpart is {human_name}. You should escalate to them when:
- Critical decisions need human approval
- There are significant risks or blockers
- Timeline changes require stakeholder communication
- Budget implications need review

Your responsibilities:
- Track project progress and milestones
- Identify risks and dependencies
- Coordinate between team members
- Prepare status updates and reports
- Flag blockers and issues early

Always maintain a professional, organized approach. Focus on clarity, deadlines, and stakeholder alignment.""",
        "suggested_tools": [
            "jira_list_issues",
            "jira_create_issue",
            "jira_update_issue",
            "slack_send_message",
            "slack_list_channels",
            "calendar_list_events",
            "email_send",
        ],
        "default_capabilities": {
            "can_create_tasks": True,
            "can_assign_tasks": True,
            "can_update_status": True,
            "can_send_notifications": True,
        },
    },
    {
        "role_type": AgentRoleType.PRODUCT_OWNER.value,
        "role_name": "Product Owner",
        "description": "Manages product backlog, defines user stories, prioritizes features, and ensures alignment with business goals.",
        "system_prompt_template": """You are a Product Owner AI assistant for the project "{project_name}".

Project Description: {project_description}

Your human counterpart is {human_name}. Escalate to them for:
- Major feature prioritization decisions
- Scope changes or new requirements
- Stakeholder conflicts on priorities
- Release planning decisions

Your responsibilities:
- Maintain and prioritize the product backlog
- Write and refine user stories with acceptance criteria
- Clarify requirements for the development team
- Ensure delivered features meet business needs
- Gather and synthesize stakeholder feedback

Focus on value delivery, user needs, and clear requirements.""",
        "suggested_tools": [
            "jira_list_issues",
            "jira_create_issue",
            "jira_update_issue",
            "clickup_list_tasks",
            "confluence_create_page",
            "slack_send_message",
        ],
        "default_capabilities": {
            "can_create_stories": True,
            "can_prioritize_backlog": True,
            "can_define_acceptance_criteria": True,
        },
    },
    {
        "role_type": AgentRoleType.QA_ENGINEER.value,
        "role_name": "QA Engineer",
        "description": "Plans testing strategies, reviews quality, identifies bugs, and ensures software meets quality standards.",
        "system_prompt_template": """You are a QA Engineer AI assistant for the project "{project_name}".

Project Description: {project_description}

Your human counterpart is {human_name}. Escalate to them for:
- Critical or security-related bugs
- Test strategy decisions for complex features
- Quality gate decisions before releases
- Uncertain bug severity classifications

Your responsibilities:
- Plan and document test cases
- Review code changes for quality concerns
- Track and triage bugs
- Ensure test coverage for new features
- Monitor regression test results
- Validate fixes and verify bug resolutions

Be thorough, detail-oriented, and advocate for quality.""",
        "suggested_tools": [
            "jira_list_issues",
            "jira_create_issue",
            "github_list_pull_requests",
            "github_get_pull_request",
            "github_create_issue",
        ],
        "default_capabilities": {"can_create_bugs": True, "can_update_test_status": True, "can_review_code": True},
    },
    {
        "role_type": AgentRoleType.CODE_REVIEWER.value,
        "role_name": "Code Reviewer",
        "description": "Reviews code for quality, security, best practices, and maintainability. Provides constructive feedback.",
        "system_prompt_template": """You are a Code Reviewer AI assistant for the project "{project_name}".

Project Description: {project_description}

Your human counterpart is {human_name}. Escalate to them for:
- Security vulnerabilities or concerns
- Architectural decisions with significant impact
- Code that requires domain expertise review
- Disagreements on implementation approach

Your responsibilities:
- Review pull requests for code quality
- Check for security vulnerabilities
- Ensure adherence to coding standards
- Suggest performance improvements
- Verify proper error handling
- Check for maintainability and readability

Be constructive, specific, and educational in your feedback.""",
        "suggested_tools": [
            "github_list_pull_requests",
            "github_get_pull_request",
            "github_create_review",
            "github_add_comment",
        ],
        "default_capabilities": {"can_review_code": True, "can_approve_prs": False, "can_request_changes": True},
    },
    {
        "role_type": AgentRoleType.BUSINESS_ANALYST.value,
        "role_name": "Business Analyst",
        "description": "Gathers requirements, analyzes business processes, creates documentation, and bridges technical and business teams.",
        "system_prompt_template": """You are a Business Analyst AI assistant for the project "{project_name}".

Project Description: {project_description}

Your human counterpart is {human_name}. Escalate to them for:
- Complex business rule interpretations
- Stakeholder interviews and meetings
- Process change recommendations
- Conflicting requirements from different stakeholders

Your responsibilities:
- Gather and document business requirements
- Analyze current and future business processes
- Create process flows and documentation
- Translate business needs into technical requirements
- Facilitate understanding between stakeholders and technical teams
- Track requirement changes and their impacts

Be analytical, thorough in documentation, and focused on business value.""",
        "suggested_tools": [
            "confluence_create_page",
            "confluence_search",
            "jira_create_issue",
            "slack_send_message",
            "google_docs_create",
        ],
        "default_capabilities": {
            "can_create_documentation": True,
            "can_update_requirements": True,
            "can_create_diagrams": True,
        },
    },
    {
        "role_type": AgentRoleType.SCRUM_MASTER.value,
        "role_name": "Scrum Master",
        "description": "Facilitates Scrum ceremonies, removes impediments, coaches the team on Agile practices, and protects team focus.",
        "system_prompt_template": """You are a Scrum Master AI assistant for the project "{project_name}".

Project Description: {project_description}

Your human counterpart is {human_name}. Escalate to them for:
- Team conflicts requiring mediation
- Organizational impediments beyond team control
- Process changes affecting multiple teams
- Stakeholder management issues

Your responsibilities:
- Facilitate sprint planning, reviews, and retrospectives
- Track sprint progress and velocity
- Remove impediments blocking the team
- Coach team on Agile best practices
- Shield the team from external distractions
- Promote continuous improvement

Be servant-leader focused, process-oriented, and team-protective.""",
        "suggested_tools": [
            "jira_list_issues",
            "jira_get_sprint",
            "slack_send_message",
            "slack_list_channels",
            "calendar_create_event",
        ],
        "default_capabilities": {
            "can_manage_sprints": True,
            "can_track_velocity": True,
            "can_facilitate_ceremonies": True,
        },
    },
    {
        "role_type": AgentRoleType.TECH_LEAD.value,
        "role_name": "Tech Lead",
        "description": "Provides technical guidance, makes architecture decisions, mentors developers, and ensures technical excellence.",
        "system_prompt_template": """You are a Tech Lead AI assistant for the project "{project_name}".

Project Description: {project_description}

Your human counterpart is {human_name}. Escalate to them for:
- Major architectural decisions
- Technology stack changes
- Security architecture concerns
- Performance issues requiring infrastructure changes
- Technical debt prioritization

Your responsibilities:
- Guide technical architecture and design
- Review and approve technical approaches
- Mentor team members on best practices
- Manage technical debt
- Ensure code quality standards
- Make technology recommendations

Be technically thorough, mentor-focused, and pragmatic about trade-offs.""",
        "suggested_tools": [
            "github_list_pull_requests",
            "github_get_pull_request",
            "github_create_review",
            "jira_list_issues",
            "confluence_create_page",
        ],
        "default_capabilities": {
            "can_approve_architecture": True,
            "can_review_code": True,
            "can_manage_tech_debt": True,
        },
    },
]


class AgentRoleService:
    """Service for managing agent role templates."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_role(
        self,
        tenant_id: UUID,
        role_type: str,
        role_name: str,
        description: str,
        system_prompt_template: str,
        suggested_tools: list[str] | None = None,
        default_capabilities: dict[str, Any] | None = None,
        is_system_template: bool = False,
    ) -> AgentRole:
        """
        Create a new agent role.

        Args:
            tenant_id: Tenant identifier
            role_type: Type of role (from AgentRoleType enum)
            role_name: Human-readable role name
            description: Role description
            system_prompt_template: System prompt template with placeholders
            suggested_tools: List of suggested tool names
            default_capabilities: Default capabilities for this role
            is_system_template: Whether this is a system template

        Returns:
            Created AgentRole instance
        """
        role = AgentRole(
            tenant_id=tenant_id,
            role_type=role_type,
            role_name=role_name,
            description=description,
            system_prompt_template=system_prompt_template,
            suggested_tools=suggested_tools or [],
            default_capabilities=default_capabilities or {},
            is_system_template=is_system_template,
        )

        self.db.add(role)
        await self.db.commit()
        await self.db.refresh(role)

        logger.info(f"Created agent role: {role_name} (type={role_type})")
        return role

    async def get_role(self, role_id: UUID, tenant_id: UUID | None = None) -> AgentRole | None:
        """Get a role by ID, optionally scoped to a tenant (or system templates)."""
        if tenant_id is not None:
            # SECURITY: Only return if the role belongs to the tenant or is a system template
            result = await self.db.execute(
                select(AgentRole).filter(
                    AgentRole.id == role_id,
                    or_(AgentRole.tenant_id == tenant_id, AgentRole.is_system_template),
                )
            )
        else:
            result = await self.db.execute(select(AgentRole).filter(AgentRole.id == role_id))
        return result.scalar_one_or_none()

    async def get_role_by_type(self, tenant_id: UUID, role_type: str) -> AgentRole | None:
        """
        Get a role by type for a tenant.
        Falls back to system template if tenant-specific not found.
        """
        # First try tenant-specific
        result = await self.db.execute(
            select(AgentRole).filter(and_(AgentRole.tenant_id == tenant_id, AgentRole.role_type == role_type))
        )
        role = result.scalar_one_or_none()

        if role:
            return role

        # Fall back to system template
        result = await self.db.execute(
            select(AgentRole).filter(and_(AgentRole.is_system_template, AgentRole.role_type == role_type))
        )
        return result.scalar_one_or_none()

    async def list_roles(
        self, tenant_id: UUID, include_system: bool = True, role_type: str | None = None
    ) -> list[AgentRole]:
        """
        List roles for a tenant.

        Args:
            tenant_id: Tenant identifier
            include_system: Whether to include system templates
            role_type: Optional filter by role type

        Returns:
            List of AgentRole instances
        """
        if include_system:
            stmt = select(AgentRole).filter(or_(AgentRole.tenant_id == tenant_id, AgentRole.is_system_template))
        else:
            stmt = select(AgentRole).filter(AgentRole.tenant_id == tenant_id)

        if role_type:
            stmt = stmt.filter(AgentRole.role_type == role_type)

        stmt = stmt.order_by(AgentRole.role_name)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_role(self, role_id: UUID, tenant_id: UUID, **kwargs) -> AgentRole | None:
        """
        Update a role.

        Note: System templates cannot be modified.

        Args:
            role_id: Role ID to update
            tenant_id: Tenant ID for validation
            **kwargs: Fields to update

        Returns:
            Updated AgentRole or None if not found/not allowed
        """
        result = await self.db.execute(
            select(AgentRole).filter(and_(AgentRole.id == role_id, AgentRole.tenant_id == tenant_id))
        )
        role = result.scalar_one_or_none()

        if not role:
            logger.warning(f"Role not found or access denied: {role_id}")
            return None

        if role.is_system_template:
            logger.warning(f"Cannot modify system template: {role_id}")
            return None

        # Update allowed fields
        allowed_fields = {
            "role_name",
            "description",
            "system_prompt_template",
            "suggested_tools",
            "default_capabilities",
        }

        for key, value in kwargs.items():
            if key in allowed_fields and value is not None:
                setattr(role, key, value)

        await self.db.commit()
        await self.db.refresh(role)

        logger.info(f"Updated role: {role_id}")
        return role

    async def delete_role(self, role_id: UUID, tenant_id: UUID) -> bool:
        """
        Delete a role.

        Note: System templates cannot be deleted.

        Args:
            role_id: Role ID to delete
            tenant_id: Tenant ID for validation

        Returns:
            True if deleted, False otherwise
        """
        result = await self.db.execute(
            select(AgentRole).filter(and_(AgentRole.id == role_id, AgentRole.tenant_id == tenant_id))
        )
        role = result.scalar_one_or_none()

        if not role:
            logger.warning(f"Role not found or access denied: {role_id}")
            return False

        if role.is_system_template:
            logger.warning(f"Cannot delete system template: {role_id}")
            return False

        await self.db.delete(role)
        await self.db.commit()

        logger.info(f"Deleted role: {role_id}")
        return True

    async def seed_system_roles(self, system_tenant_id: UUID) -> list[AgentRole]:
        """
        Seed default system role templates.

        This should be called during system initialization.
        Creates templates if they don't exist.

        Args:
            system_tenant_id: System tenant ID for templates

        Returns:
            List of created/existing system roles
        """
        roles = []

        for template in DEFAULT_ROLE_TEMPLATES:
            # Check if already exists
            result = await self.db.execute(
                select(AgentRole).filter(
                    and_(AgentRole.is_system_template, AgentRole.role_type == template["role_type"])
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                roles.append(existing)
                logger.debug(f"System role already exists: {template['role_name']}")
                continue

            # Create new system role
            role = AgentRole(
                tenant_id=system_tenant_id,
                role_type=template["role_type"],
                role_name=template["role_name"],
                description=template["description"],
                system_prompt_template=template["system_prompt_template"],
                suggested_tools=template["suggested_tools"],
                default_capabilities=template["default_capabilities"],
                is_system_template=True,
            )

            self.db.add(role)
            roles.append(role)
            logger.info(f"Created system role: {template['role_name']}")

        await self.db.commit()

        # Refresh all roles
        for role in roles:
            await self.db.refresh(role)

        return roles

    async def clone_role(self, role_id: UUID, tenant_id: UUID, new_name: str) -> AgentRole | None:
        """
        Clone an existing role (including system templates).

        Args:
            role_id: Source role ID
            tenant_id: Tenant ID for the new role
            new_name: Name for the cloned role

        Returns:
            New AgentRole instance or None if source not found
        """
        source = await self.get_role(role_id, tenant_id=tenant_id)
        if not source:
            return None

        return await self.create_role(
            tenant_id=tenant_id,
            role_type=AgentRoleType.CUSTOM.value,
            role_name=new_name,
            description=source.description,
            system_prompt_template=source.system_prompt_template,
            suggested_tools=source.suggested_tools.copy() if source.suggested_tools else [],
            default_capabilities=source.default_capabilities.copy() if source.default_capabilities else {},
            is_system_template=False,
        )
