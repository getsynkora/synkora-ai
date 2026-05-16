"""
Agent Model

Database model for storing AI agent configurations.
"""

import logging

from sqlalchemy import JSON, Boolean, Column, ForeignKey, Integer, String, Text, UniqueConstraint, select

logger = logging.getLogger(__name__)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, relationship

from src.models.base import BaseModel, StatusMixin, TenantMixin


class Agent(BaseModel, StatusMixin, TenantMixin):
    """
    Agent model for storing agent configurations.

    Attributes:
        agent_name: Unique name for the agent
        agent_type: Type of agent (llm, research, code, etc.)
        description: Agent description
        system_prompt: System prompt for the agent
        llm_config: LLM configuration (provider, model, etc.)
        tools_config: Tools configuration
        agent_metadata: Additional metadata
        execution_count: Number of times agent has been executed
        success_count: Number of successful executions
        status: Agent status (active, inactive, error)
        tenant_id: Tenant identifier for multi-tenancy
    """

    __tablename__ = "agents"

    __table_args__ = (UniqueConstraint("agent_name", "tenant_id", name="uq_agent_name_tenant"),)

    agent_name = Column(String(255), nullable=False, index=True, comment="Unique agent name per tenant")

    slug = Column(String(255), nullable=True, unique=True, index=True, comment="Globally unique slug for URL routing")

    agent_type = Column(String(50), nullable=False, default="LLM", comment="Agent type (llm, research, code)")

    description = Column(Text, nullable=True, comment="Agent description")

    system_prompt = Column(Text, nullable=True, comment="System prompt for the agent")

    llm_config = Column(JSON, nullable=False, comment="LLM configuration (provider, model, api_key, etc.)")

    tools_config = Column(JSON, nullable=True, comment="Tools configuration")

    agent_metadata = Column(JSON, nullable=True, comment="Additional agent metadata")

    observability_config = Column(
        JSON, nullable=True, comment="Observability configuration (Langfuse tracing, sampling rate, etc.)"
    )

    suggestion_prompts = Column(
        JSON,
        nullable=True,
        comment="Suggestion prompts for chat interface (array of objects with title, description, icon, prompt)",
    )

    voice_enabled = Column(
        Boolean, nullable=False, default=False, comment="Whether voice chat is enabled for this agent"
    )

    voice_config = Column(JSON, nullable=True, comment="Voice configuration (STT/TTS providers, voice settings, etc.)")

    is_public = Column(
        Boolean, nullable=False, default=False, comment="Whether agent is publicly visible in marketplace"
    )

    allow_subscriptions = Column(
        Boolean, nullable=False, default=False, comment="Whether external emails can subscribe to this agent's output"
    )

    likes_count = Column(Integer, nullable=False, default=0, comment="Number of likes")

    dislikes_count = Column(Integer, nullable=False, default=0, comment="Number of dislikes")

    avatar = Column(String(255), nullable=True, comment="URL to agent avatar")

    usage_count = Column(Integer, nullable=False, default=0, comment="Number of times agent has been used")

    category = Column(String(100), nullable=True, comment="Agent category (e.g., Support, Engineering, Sales)")

    tags = Column(ARRAY(String), nullable=True, comment="Agent tags for filtering and search")

    execution_count = Column(Integer, nullable=False, default=0, comment="Number of executions")

    success_count = Column(Integer, nullable=False, default=0, comment="Number of successful executions")

    # Role-based agent fields
    role_id = Column(
        UUID,
        ForeignKey("agent_roles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Reference to agent role template",
    )

    human_contact_id = Column(
        UUID,
        ForeignKey("human_contacts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Reference to linked human contact for escalation",
    )

    # Multi-agent support fields
    parent_agent_id = Column(
        UUID,
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Parent agent ID for multi-agent hierarchy",
    )

    allow_transfer = Column(
        Boolean, nullable=False, default=False, comment="Whether this agent can transfer to other agents"
    )

    transfer_scope = Column(
        String(50), nullable=False, default="sub_agents", comment="Transfer scope: sub_agents, siblings, or parent"
    )

    output_key = Column(
        String(255), nullable=True, comment="State key where this agent's output is automatically saved"
    )

    autonomous_enabled = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether this agent has an active autonomous schedule",
    )

    # Model routing
    routing_mode = Column(
        String(30),
        nullable=False,
        default="fixed",
        comment="Model routing mode: fixed | round_robin | cost_opt | intent | latency_opt",
    )

    routing_config = Column(
        JSON,
        nullable=True,
        comment="Routing configuration: quality_floor, max_cost_per_1k, etc.",
    )

    # Execution backend
    execution_backend = Column(
        String(30),
        nullable=False,
        server_default="celery",
        comment="Execution backend: celery | lambda | cloud_run",
    )

    # Email template assignment
    email_template_id = Column(
        UUID,
        ForeignKey("email_templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Assigned email template used by internal_send_email and internal_render_newsletter",
    )

    # ADK-style workflow agent fields
    workflow_type = Column(
        String(50),
        nullable=True,
        comment="Workflow type: sequential, loop, parallel, custom (null for regular LLM agents)",
    )

    workflow_config = Column(
        JSON,
        nullable=True,
        comment="""Workflow-specific configuration:
        - loop: {max_iterations: 5, exit_tool: "exit_loop"}
        - parallel: {merge_strategy: "combine", wait_for_all: true}
        - sequential: {stop_on_error: true, pass_state: true}
        - custom: {custom_executor_class: "MyCustomExecutor"}
        """,
    )

    # Relationships
    # NOTE: Using lazy="select" (default lazy loading) for most relationships to avoid
    # 20+ queries per agent fetch. Use selectinload() explicitly in queries where needed.
    # Previously all relationships used lazy="selectin" which caused severe N+1 performance issues.
    tools = relationship("AgentTool", back_populates="agent", cascade="all, delete-orphan", lazy="select")

    knowledge_bases = relationship(
        "AgentKnowledgeBase", back_populates="agent", cascade="all, delete-orphan", lazy="select"
    )

    mcp_servers = relationship("AgentMCPServer", back_populates="agent", cascade="all, delete-orphan", lazy="select")

    context_files = relationship(
        "AgentContextFile",
        back_populates="agent",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="AgentContextFile.display_order",
    )

    conversations = relationship("Conversation", back_populates="agent", cascade="all, delete-orphan", lazy="select")

    widgets = relationship("AgentWidget", back_populates="agent", cascade="all, delete-orphan", lazy="select")

    slack_bots = relationship("SlackBot", back_populates="agent", cascade="all, delete-orphan", lazy="select")

    charts = relationship("Chart", back_populates="agent", cascade="all, delete-orphan", lazy="select")

    domains = relationship("AgentDomain", back_populates="agent", cascade="all, delete-orphan", lazy="select")

    api_keys = relationship("AgentApiKey", back_populates="agent", cascade="all, delete-orphan", lazy="select")

    pricing = relationship(
        "AgentPricing", back_populates="agent", uselist=False, cascade="all, delete-orphan", lazy="select"
    )

    email_template = relationship(
        "EmailTemplate",
        back_populates="agents",
        foreign_keys=[email_template_id],
        lazy="select",
    )

    usage_analytics = relationship(
        "UsageAnalytics", back_populates="agent", cascade="all, delete-orphan", lazy="select"
    )

    # LLM configs needed frequently - use selectin for better performance
    llm_configs = relationship(
        "AgentLLMConfig",
        back_populates="agent",
        cascade="all, delete-orphan",
        lazy="selectin",  # Keep eager loading for frequently accessed config
        order_by="AgentLLMConfig.display_order",
    )

    whatsapp_bots = relationship("WhatsAppBot", back_populates="agent", cascade="all, delete-orphan", lazy="select")

    teams_bots = relationship("TeamsBot", back_populates="agent", cascade="all, delete-orphan", lazy="select")

    telegram_bots = relationship("TelegramBot", back_populates="agent", cascade="all, delete-orphan", lazy="select")

    # Role-based agent relationships
    role = relationship("AgentRole", foreign_keys=[role_id], lazy="select")

    human_contact = relationship("HumanContact", foreign_keys=[human_contact_id], lazy="select")

    # Multi-agent relationships
    parent_agent = relationship(
        "Agent", remote_side="Agent.id", backref="direct_sub_agents", foreign_keys=[parent_agent_id]
    )

    # Compute assignment (1:1 optional)
    compute = relationship(
        "AgentCompute",
        back_populates="agent",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="select",
    )

    # Followup relationships
    followup_items = relationship("FollowupItem", back_populates="agent", cascade="all, delete-orphan", lazy="select")

    followup_config = relationship(
        "FollowupConfig", back_populates="agent", uselist=False, cascade="all, delete-orphan", lazy="select"
    )

    subscriptions = relationship(
        "AgentSubscription", back_populates="agent", cascade="all, delete-orphan", lazy="select"
    )

    public_profile: Mapped["AgentPublicProfile"] = relationship(
        "AgentPublicProfile",
        back_populates="agent",
        uselist=False,
        lazy="select",
    )

    def __repr__(self) -> str:
        """String representation of agent."""
        return f"<Agent(id={self.id}, name='{self.agent_name}', type='{self.agent_type}')>"

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.execution_count == 0:
            return 0.0
        return (self.success_count / self.execution_count) * 100

    def to_dict(self, exclude: set[str] | None = None) -> dict:
        """
        Convert to dictionary, excluding sensitive data by default.

        Args:
            exclude: Additional fields to exclude

        Returns:
            Dictionary representation of the agent
        """
        exclude = exclude or set()
        # Exclude API key from llm_config by default
        data = super().to_dict(exclude=exclude)

        # Remove API key from llm_config if present
        if "llm_config" in data and isinstance(data["llm_config"], dict):
            llm_config = data["llm_config"].copy()
            llm_config.pop("api_key", None)
            data["llm_config"] = llm_config

        # Add computed fields
        data["success_rate"] = self.success_rate

        return data

    def to_dict_with_secrets(self) -> dict:
        """
        Convert to dictionary including sensitive data.
        Use with caution - only for authorized operations.

        Returns:
            Full dictionary including secrets
        """
        data = super().to_dict(exclude=set())
        data["success_rate"] = self.success_rate
        return data

    async def get_sub_agents(self, db: AsyncSession, active_only: bool = True) -> list["Agent"]:
        """
        Get configured sub-agents through junction table.

        Args:
            db: Database session
            active_only: Only return active sub-agents

        Returns:
            List of sub-agent instances
        """
        from src.models.agent_sub_agent import AgentSubAgent

        stmt = (
            select(Agent)
            .join(AgentSubAgent, AgentSubAgent.sub_agent_id == Agent.id)
            .filter(AgentSubAgent.parent_agent_id == self.id)
            .filter(Agent.tenant_id == self.tenant_id)
        )

        if active_only:
            stmt = stmt.filter(AgentSubAgent.is_active)

        stmt = stmt.order_by(AgentSubAgent.execution_order)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def find_agent_by_name(self, name: str, db: AsyncSession) -> "Agent | None":
        """
        Find agent by name in accessible scope based on transfer_scope.

        Args:
            name: Agent name to find
            db: Database session

        Returns:
            Agent instance if found and accessible, None otherwise
        """
        if self.transfer_scope == "sub_agents":
            # Can only transfer to sub-agents
            sub_agents = await self.get_sub_agents(db)
            return next((a for a in sub_agents if a.agent_name == name), None)

        elif self.transfer_scope == "siblings":
            # Can transfer to siblings (same parent)
            if self.parent_agent_id:
                result = await db.execute(
                    select(Agent).filter(Agent.id == self.parent_agent_id, Agent.tenant_id == self.tenant_id)
                )
                parent = result.scalar_one_or_none()
                if parent:
                    siblings = await parent.get_sub_agents(db)
                    return next((a for a in siblings if a.agent_name == name), None)

        elif self.transfer_scope == "parent":
            # Can transfer to parent or siblings
            if self.parent_agent_id:
                result = await db.execute(
                    select(Agent).filter(Agent.id == self.parent_agent_id, Agent.tenant_id == self.tenant_id)
                )
                parent = result.scalar_one_or_none()
                if parent and parent.agent_name == name:
                    return parent
                if parent:
                    siblings = await parent.get_sub_agents(db)
                    return next((a for a in siblings if a.agent_name == name), None)

        return None

    async def get_root_agent(self, db: AsyncSession) -> "Agent":
        """
        Get root agent in hierarchy. Uses iterative traversal with cycle detection.
        Max depth: 10 levels.
        """
        MAX_DEPTH = 10
        visited: set = {self.id}
        current = self
        depth = 0

        while current.parent_agent_id and depth < MAX_DEPTH:
            if current.parent_agent_id in visited:
                # Circular reference detected — return current node
                logger.warning(f"Circular agent hierarchy detected at agent {current.id}, breaking traversal")
                break
            visited.add(current.parent_agent_id)
            result = await db.execute(
                select(Agent).filter(Agent.id == current.parent_agent_id, Agent.tenant_id == self.tenant_id)
            )
            parent = result.scalar_one_or_none()
            if parent is None:
                break
            current = parent
            depth += 1

        return current
