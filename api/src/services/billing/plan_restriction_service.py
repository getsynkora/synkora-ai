"""
Plan Restriction Service - Enforces subscription plan limits
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.agent_api_key import AgentApiKey
from src.models.agent_user import AgentUser
from src.models.agent_widget import AgentWidget
from src.models.conversation import Conversation
from src.models.custom_tool import CustomTool
from src.models.data_source import DataSource
from src.models.database_connection import DatabaseConnection
from src.models.knowledge_base import KnowledgeBase
from src.models.mcp_server import MCPServer
from src.models.message import Message
from src.models.scheduled_task import ScheduledTask
from src.models.slack_bot import SlackBot
from src.models.subscription_plan import PlanTier, SubscriptionPlan
from src.models.tenant import TenantAccountJoin
from src.models.tenant_subscription import SubscriptionStatus, TenantSubscription


class PlanRestrictionError(Exception):
    """Raised when a plan restriction is violated"""

    pass


class SubscriptionExpiredError(PlanRestrictionError):
    """Raised when subscription has expired"""

    pass


class SubscriptionCancelledError(PlanRestrictionError):
    """Raised when subscription has been cancelled"""

    pass


class SubscriptionSuspendedError(PlanRestrictionError):
    """Raised when subscription has been suspended"""

    pass


class ConversationLimitExceededError(PlanRestrictionError):
    """Raised when conversation limit is exceeded"""

    pass


class MessageLimitExceededError(PlanRestrictionError):
    """Raised when message limit per conversation is exceeded"""

    pass


class PlanRestrictionService:
    """Service for checking and enforcing subscription plan restrictions"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_tenant_subscription(self, tenant_id: UUID) -> TenantSubscription | None:
        """Get the tenant's subscription record (any status)"""
        result = await self.db.execute(
            select(TenantSubscription)
            .where(TenantSubscription.tenant_id == tenant_id)
            .order_by(TenantSubscription.created_at.desc())
        )
        return result.scalar_one_or_none()

    async def check_subscription_validity(self, tenant_id: UUID) -> None:
        """
        Check if tenant has a valid subscription.
        Raises specific errors for expired, cancelled, or suspended subscriptions.
        """
        subscription = await self.get_tenant_subscription(tenant_id)

        if not subscription:
            # No subscription record - will use FREE plan, which is valid
            return

        # Check subscription status
        if subscription.status == SubscriptionStatus.EXPIRED:
            raise SubscriptionExpiredError(
                "Your subscription has expired. Please renew your subscription to continue using this feature."
            )

        if subscription.status == SubscriptionStatus.CANCELLED:
            raise SubscriptionCancelledError(
                "Your subscription has been cancelled. Please resubscribe to continue using this feature."
            )

        if subscription.status == SubscriptionStatus.SUSPENDED:
            raise SubscriptionSuspendedError(
                "Your subscription has been suspended. Please contact support or update your payment method."
            )

        # Check if subscription period has ended (status may not have been updated yet)
        if subscription.current_period_end:
            now = datetime.now(UTC)
            # Handle both timezone-aware and naive datetimes
            period_end = subscription.current_period_end
            if period_end.tzinfo is None:
                period_end = period_end.replace(tzinfo=UTC)

            if now > period_end:
                raise SubscriptionExpiredError(
                    "Your subscription period has ended. Please renew your subscription to continue using this feature."
                )

    async def get_tenant_plan(self, tenant_id: UUID) -> SubscriptionPlan | None:
        """Get the active subscription plan for a tenant"""
        # First try to get active or trial subscription
        result = await self.db.execute(
            select(SubscriptionPlan)
            .join(TenantSubscription)
            .where(TenantSubscription.tenant_id == tenant_id)
            .where(TenantSubscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]))
        )
        plan = result.scalar_one_or_none()

        # If no active/trial subscription, fall back to FREE plan
        if not plan:
            result = await self.db.execute(
                select(SubscriptionPlan).where(SubscriptionPlan.tier == PlanTier.FREE).where(SubscriptionPlan.is_active)
            )
            plan = result.scalar_one_or_none()

        return plan

    async def get_plan_features(self, tenant_id: UUID) -> dict:
        """Get all plan features and limits for a tenant

        Uses column-based limits from the SubscriptionPlan model,
        with features JSON for boolean feature flags.
        """
        plan = await self.get_tenant_plan(tenant_id)

        if not plan:
            # This should rarely happen, but provide safe defaults (most restrictive)
            return {
                "max_agents": 0,
                "max_team_members": 0,
                "max_knowledge_bases": 0,
                "max_mcp_servers": 0,
                "max_custom_tools": 0,
                "max_database_connections": 0,
                "max_data_sources": 0,
                "max_scheduled_tasks": 0,
                "max_widgets": 0,
                "max_slack_bots": 0,
                "max_api_calls_per_month": 0,
                "credits_monthly": 0,
                "credits_rollover": False,
                "features": {},
            }

        # Get feature flags from JSON (for boolean flags)
        features = plan.features or {}

        # Return column-based limits (NOT from features JSON)
        return {
            # Column-based numeric limits
            "max_agents": plan.max_agents,
            "max_team_members": plan.max_team_members,
            "max_knowledge_bases": plan.max_knowledge_bases,
            "max_mcp_servers": plan.max_mcp_servers,
            "max_custom_tools": plan.max_custom_tools,
            "max_database_connections": plan.max_database_connections,
            "max_data_sources": plan.max_data_sources,
            "max_scheduled_tasks": plan.max_scheduled_tasks,
            "max_widgets": plan.max_widgets,
            "max_slack_bots": plan.max_slack_bots,
            "max_api_calls_per_month": plan.max_api_calls_per_month,
            # Credit info
            "credits_monthly": plan.credits_monthly,
            "credits_rollover": plan.credits_rollover,
            # Overage settings from features JSON
            "overage_allowed": features.get("overage_allowed", False),
            "overage_rate_per_credit": features.get("overage_rate_per_credit", 0),
            "grace_period_days": features.get("grace_period_days", 0),
            "max_rollover_credits": features.get("max_rollover_credits", 0),
            # Boolean feature flags from JSON
            "features": {
                "advanced_analytics": features.get("advanced_analytics", False),
                "custom_domains": features.get("custom_domains", False),
                "priority_support": features.get("priority_support", False),
                "white_label": features.get("white_label", False),
                "sso": features.get("sso", False),
                "audit_logs": features.get("audit_logs", False),
                "api_access": features.get("api_access", False),
                "webhooks": features.get("webhooks", False),
                "custom_integrations": features.get("custom_integrations", False),
                "advanced_security": features.get("advanced_security", False),
                "dedicated_support": features.get("dedicated_support", False),
                "sla_guarantee": features.get("sla_guarantee", False),
                # Additional feature flags for middleware enforcement
                "mcp_servers": features.get("mcp_servers", False),
                "knowledge_bases": features.get("knowledge_bases", False),
                "custom_tools": features.get("custom_tools", False),
                "platform_engineer_agent": features.get("platform_engineer_agent", False),
                # Serverless execution backends (Cloud Run, Lambda) — gated to Professional+
                "serverless_execution": features.get("serverless_execution", False),
            },
        }

    async def check_agent_limit(self, tenant_id: UUID) -> bool:
        """Check if tenant can create more agents"""
        plan = await self.get_tenant_plan(tenant_id)

        if not plan or plan.max_agents is None:
            # Unlimited agents
            return True

        # Count current agents
        result = await self.db.execute(select(func.count(Agent.id)).where(Agent.tenant_id == tenant_id))
        current_count = result.scalar()

        return current_count < plan.max_agents

    async def check_team_member_limit(self, tenant_id: UUID) -> bool:
        """Check if tenant can add more team members"""
        plan = await self.get_tenant_plan(tenant_id)

        if not plan or plan.max_team_members is None:
            # Unlimited team members
            return True

        # Count current team members
        result = await self.db.execute(
            select(func.count(TenantAccountJoin.id)).where(TenantAccountJoin.tenant_id == tenant_id)
        )
        current_count = result.scalar()

        return current_count < plan.max_team_members

    async def check_knowledge_base_limit(self, tenant_id: UUID) -> bool:
        """Check if tenant can create more knowledge bases"""
        plan = await self.get_tenant_plan(tenant_id)

        if not plan or plan.max_knowledge_bases is None:
            # Unlimited knowledge bases
            return True

        # Count current knowledge bases
        result = await self.db.execute(select(func.count(KnowledgeBase.id)).where(KnowledgeBase.tenant_id == tenant_id))
        current_count = result.scalar()

        return current_count < plan.max_knowledge_bases

    async def check_mcp_server_limit(self, tenant_id: UUID) -> bool:
        """Check if tenant can create more MCP servers"""
        plan = await self.get_tenant_plan(tenant_id)

        if not plan or plan.max_mcp_servers is None:
            # Unlimited MCP servers
            return True

        # Count current MCP servers
        result = await self.db.execute(select(func.count(MCPServer.id)).where(MCPServer.tenant_id == tenant_id))
        current_count = result.scalar()

        return current_count < plan.max_mcp_servers

    async def check_custom_tool_limit(self, tenant_id: UUID) -> bool:
        """Check if tenant can create more custom tools"""
        plan = await self.get_tenant_plan(tenant_id)

        if not plan or plan.max_custom_tools is None:
            # Unlimited custom tools
            return True

        # Count current custom tools
        result = await self.db.execute(select(func.count(CustomTool.id)).where(CustomTool.tenant_id == tenant_id))
        current_count = result.scalar()

        return current_count < plan.max_custom_tools

    async def check_database_connection_limit(self, tenant_id: UUID) -> bool:
        """Check if tenant can create more database connections"""
        plan = await self.get_tenant_plan(tenant_id)

        if not plan or plan.max_database_connections is None:
            # Unlimited database connections
            return True

        # Count current database connections
        result = await self.db.execute(
            select(func.count(DatabaseConnection.id)).where(DatabaseConnection.tenant_id == tenant_id)
        )
        current_count = result.scalar()

        return current_count < plan.max_database_connections

    async def check_data_source_limit(self, tenant_id: UUID) -> bool:
        """Check if tenant can create more data sources"""
        plan = await self.get_tenant_plan(tenant_id)

        if not plan or plan.max_data_sources is None:
            # Unlimited data sources
            return True

        # Count current data sources
        result = await self.db.execute(select(func.count(DataSource.id)).where(DataSource.tenant_id == tenant_id))
        current_count = result.scalar()

        return current_count < plan.max_data_sources

    async def check_scheduled_task_limit(self, tenant_id: UUID) -> bool:
        """Check if tenant can create more scheduled tasks"""
        plan = await self.get_tenant_plan(tenant_id)

        if not plan or plan.max_scheduled_tasks is None:
            # Unlimited scheduled tasks
            return True

        # Count current scheduled tasks
        result = await self.db.execute(select(func.count(ScheduledTask.id)).where(ScheduledTask.tenant_id == tenant_id))
        current_count = result.scalar()

        return current_count < plan.max_scheduled_tasks

    async def check_widget_limit(self, tenant_id: UUID) -> bool:
        """Check if tenant can create more widgets"""
        plan = await self.get_tenant_plan(tenant_id)

        if not plan or plan.max_widgets is None:
            # Unlimited widgets
            return True

        # Count current widgets
        result = await self.db.execute(select(func.count(AgentWidget.id)).where(AgentWidget.tenant_id == tenant_id))
        current_count = result.scalar()

        return current_count < plan.max_widgets

    async def check_slack_bot_limit(self, tenant_id: UUID) -> bool:
        """Check if tenant can create more slack bots"""
        plan = await self.get_tenant_plan(tenant_id)

        if not plan or plan.max_slack_bots is None:
            # Unlimited slack bots
            return True

        # Count current slack bots
        result = await self.db.execute(select(func.count(SlackBot.id)).where(SlackBot.tenant_id == tenant_id))
        current_count = result.scalar()

        return current_count < plan.max_slack_bots

    async def check_feature_access(self, tenant_id: UUID, feature_name: str) -> bool:
        """Check if tenant has access to a specific feature"""
        features = await self.get_plan_features(tenant_id)
        return features.get("features", {}).get(feature_name, False)

    async def enforce_agent_limit(self, tenant_id: UUID):
        """Enforce agent creation limit"""
        if not await self.check_agent_limit(tenant_id):
            plan = await self.get_tenant_plan(tenant_id)
            max_agents = plan.max_agents if plan and plan.max_agents is not None else "unlimited"
            raise PlanRestrictionError(
                f"Agent limit reached. Your plan allows {max_agents} agents. "
                f"Please upgrade your plan to create more agents."
            )

    async def enforce_team_member_limit(self, tenant_id: UUID):
        """Enforce team member limit"""
        if not await self.check_team_member_limit(tenant_id):
            plan = await self.get_tenant_plan(tenant_id)
            max_members = plan.max_team_members if plan and plan.max_team_members is not None else "unlimited"
            raise PlanRestrictionError(
                f"Team member limit reached. Your plan allows {max_members} team members. "
                f"Please upgrade your plan to add more team members."
            )

    async def enforce_knowledge_base_limit(self, tenant_id: UUID):
        """Enforce knowledge base creation limit"""
        if not await self.check_knowledge_base_limit(tenant_id):
            plan = await self.get_tenant_plan(tenant_id)
            max_kb = plan.max_knowledge_bases if plan else 0
            raise PlanRestrictionError(
                f"Knowledge base limit reached. Your plan allows {max_kb} knowledge bases. "
                f"Please upgrade your plan to create more knowledge bases."
            )

    async def enforce_mcp_server_limit(self, tenant_id: UUID):
        """Enforce MCP server creation limit"""
        if not await self.check_mcp_server_limit(tenant_id):
            plan = await self.get_tenant_plan(tenant_id)
            max_mcp = plan.max_mcp_servers if plan else 0
            raise PlanRestrictionError(
                f"MCP server limit reached. Your plan allows {max_mcp} MCP servers. "
                f"Please upgrade your plan to create more MCP servers."
            )

    async def enforce_custom_tool_limit(self, tenant_id: UUID):
        """Enforce custom tool creation limit"""
        if not await self.check_custom_tool_limit(tenant_id):
            plan = await self.get_tenant_plan(tenant_id)
            max_tools = plan.max_custom_tools if plan else 0
            raise PlanRestrictionError(
                f"Custom tool limit reached. Your plan allows {max_tools} custom tools. "
                f"Please upgrade your plan to create more custom tools."
            )

    async def enforce_database_connection_limit(self, tenant_id: UUID):
        """Enforce database connection creation limit"""
        if not await self.check_database_connection_limit(tenant_id):
            plan = await self.get_tenant_plan(tenant_id)
            max_db = plan.max_database_connections if plan else 0
            raise PlanRestrictionError(
                f"Database connection limit reached. Your plan allows {max_db} database connections. "
                f"Please upgrade your plan to create more database connections."
            )

    async def enforce_data_source_limit(self, tenant_id: UUID):
        """Enforce data source creation limit"""
        if not await self.check_data_source_limit(tenant_id):
            plan = await self.get_tenant_plan(tenant_id)
            max_ds = plan.max_data_sources if plan else 0
            raise PlanRestrictionError(
                f"Data source limit reached. Your plan allows {max_ds} data sources. "
                f"Please upgrade your plan to create more data sources."
            )

    async def enforce_scheduled_task_limit(self, tenant_id: UUID):
        """Enforce scheduled task creation limit"""
        if not await self.check_scheduled_task_limit(tenant_id):
            plan = await self.get_tenant_plan(tenant_id)
            max_tasks = plan.max_scheduled_tasks if plan else 0
            raise PlanRestrictionError(
                f"Scheduled task limit reached. Your plan allows {max_tasks} scheduled tasks. "
                f"Please upgrade your plan to create more scheduled tasks."
            )

    async def enforce_widget_limit(self, tenant_id: UUID):
        """Enforce widget creation limit"""
        if not await self.check_widget_limit(tenant_id):
            plan = await self.get_tenant_plan(tenant_id)
            max_widgets = plan.max_widgets if plan else 0
            raise PlanRestrictionError(
                f"Widget limit reached. Your plan allows {max_widgets} widgets. "
                f"Please upgrade your plan to create more widgets."
            )

    async def enforce_slack_bot_limit(self, tenant_id: UUID):
        """Enforce slack bot creation limit"""
        if not await self.check_slack_bot_limit(tenant_id):
            plan = await self.get_tenant_plan(tenant_id)
            max_bots = plan.max_slack_bots if plan else 0
            raise PlanRestrictionError(
                f"Slack bot limit reached. Your plan allows {max_bots} slack bots. "
                f"Please upgrade your plan to create more slack bots."
            )

    async def check_api_key_limit(self, tenant_id: UUID) -> bool:
        """Check if tenant can create more API keys"""
        plan = await self.get_tenant_plan(tenant_id)

        if not plan or plan.max_api_keys is None:
            # Unlimited API keys
            return True

        # Count current API keys
        result = await self.db.execute(select(func.count(AgentApiKey.id)).where(AgentApiKey.tenant_id == tenant_id))
        current_count = result.scalar()

        return current_count < plan.max_api_keys

    async def enforce_api_key_limit(self, tenant_id: UUID):
        """Enforce API key creation limit"""
        if not await self.check_api_key_limit(tenant_id):
            plan = await self.get_tenant_plan(tenant_id)
            max_keys = plan.max_api_keys if plan else 0
            raise PlanRestrictionError(
                f"API key limit reached. Your plan allows {max_keys} API keys. "
                f"Please upgrade your plan to create more API keys."
            )

    async def enforce_feature_access(self, tenant_id: UUID, feature_name: str, feature_label: str = None):
        """Enforce feature access"""
        if not await self.check_feature_access(tenant_id, feature_name):
            label = feature_label or feature_name.replace("_", " ").title()
            raise PlanRestrictionError(
                f"{label} is not available in your current plan. Please upgrade your plan to access this feature."
            )

    async def get_conversation_limit(self, tenant_id: UUID) -> int | None:
        """Get max conversations limit from plan features.

        Returns:
            Limit as int, None for unlimited, or -1 for unlimited (from features JSON)
        """
        plan = await self.get_tenant_plan(tenant_id)
        if not plan:
            return 50  # Default for no plan

        features = plan.features or {}
        limit = features.get("max_conversations", 50)

        # -1 means unlimited in the features JSON
        if limit == -1:
            return None
        return limit

    async def get_message_limit(self, tenant_id: UUID) -> int | None:
        """Get max messages per conversation limit from plan features.

        Returns:
            Limit as int, None for unlimited, or -1 for unlimited (from features JSON)
        """
        plan = await self.get_tenant_plan(tenant_id)
        if not plan:
            return 100  # Default for no plan

        features = plan.features or {}
        limit = features.get("max_messages_per_conversation", 100)

        # -1 means unlimited in the features JSON
        if limit == -1:
            return None
        return limit

    async def check_conversation_limit(self, tenant_id: UUID, account_id: UUID) -> bool:
        """Check if account can create more conversations.

        Args:
            tenant_id: Tenant UUID
            account_id: Account UUID (user)

        Returns:
            True if can create more, False if limit reached
        """
        limit = await self.get_conversation_limit(tenant_id)

        # None means unlimited
        if limit is None:
            return True

        # Count current conversations for this user
        result = await self.db.execute(
            select(func.count(Conversation.id)).where(
                Conversation.account_id == account_id,
                Conversation.deleted_at.is_(None),  # Exclude soft-deleted
            )
        )
        current_count = result.scalar() or 0

        return current_count < limit

    async def check_message_limit(self, tenant_id: UUID, conversation_id: UUID) -> bool:
        """Check if conversation can have more messages.

        Args:
            tenant_id: Tenant UUID
            conversation_id: Conversation UUID

        Returns:
            True if can add more messages, False if limit reached
        """
        limit = await self.get_message_limit(tenant_id)

        # None means unlimited
        if limit is None:
            return True

        # Count current messages in conversation
        result = await self.db.execute(select(func.count(Message.id)).where(Message.conversation_id == conversation_id))
        current_count = result.scalar() or 0

        return current_count < limit

    async def enforce_conversation_limit(self, tenant_id: UUID, account_id: UUID):
        """Enforce conversation creation limit.

        Raises:
            ConversationLimitExceededError: If limit reached
        """
        if not await self.check_conversation_limit(tenant_id, account_id):
            limit = await self.get_conversation_limit(tenant_id)
            raise ConversationLimitExceededError(
                f"Conversation limit reached. Your plan allows {limit} conversations. "
                f"Please upgrade your plan to create more conversations or delete old ones."
            )

    async def enforce_message_limit(self, tenant_id: UUID, conversation_id: UUID):
        """Enforce message limit per conversation.

        Raises:
            MessageLimitExceededError: If limit reached
        """
        if not await self.check_message_limit(tenant_id, conversation_id):
            limit = await self.get_message_limit(tenant_id)
            raise MessageLimitExceededError(
                f"Message limit reached. Your plan allows {limit} messages per conversation. "
                f"Please upgrade your plan or start a new conversation."
            )

    async def get_usage_stats(self, tenant_id: UUID) -> dict:
        """Get current usage statistics for a tenant"""
        plan = await self.get_tenant_plan(tenant_id)
        plan_features = await self.get_plan_features(tenant_id)

        # Count current usage
        agents_result = await self.db.execute(select(func.count(Agent.id)).where(Agent.tenant_id == tenant_id))
        agents_count = agents_result.scalar()

        team_members_result = await self.db.execute(
            select(func.count(TenantAccountJoin.id)).where(TenantAccountJoin.tenant_id == tenant_id)
        )
        team_members_count = team_members_result.scalar()

        kb_result = await self.db.execute(
            select(func.count(KnowledgeBase.id)).where(KnowledgeBase.tenant_id == tenant_id)
        )
        knowledge_bases_count = kb_result.scalar()

        mcp_result = await self.db.execute(select(func.count(MCPServer.id)).where(MCPServer.tenant_id == tenant_id))
        mcp_servers_count = mcp_result.scalar()

        tools_result = await self.db.execute(select(func.count(CustomTool.id)).where(CustomTool.tenant_id == tenant_id))
        custom_tools_count = tools_result.scalar()

        db_result = await self.db.execute(
            select(func.count(DatabaseConnection.id)).where(DatabaseConnection.tenant_id == tenant_id)
        )
        database_connections_count = db_result.scalar()

        ds_result = await self.db.execute(select(func.count(DataSource.id)).where(DataSource.tenant_id == tenant_id))
        data_sources_count = ds_result.scalar()

        tasks_result = await self.db.execute(
            select(func.count(ScheduledTask.id)).where(ScheduledTask.tenant_id == tenant_id)
        )
        scheduled_tasks_count = tasks_result.scalar()

        widgets_result = await self.db.execute(
            select(func.count(AgentWidget.id)).where(AgentWidget.tenant_id == tenant_id)
        )
        widgets_count = widgets_result.scalar()

        bots_result = await self.db.execute(select(func.count(SlackBot.id)).where(SlackBot.tenant_id == tenant_id))
        slack_bots_count = bots_result.scalar()

        return {
            "plan_name": plan.name if plan else "Free",
            "plan_tier": plan.tier.value if plan else "FREE",
            "credits_monthly": plan.credits_monthly if plan else 0,
            "credits_rollover": plan.credits_rollover if plan else False,
            "overage_allowed": plan_features.get("overage_allowed", False),
            "overage_rate_per_credit": plan_features.get("overage_rate_per_credit", 0),
            "grace_period_days": plan_features.get("grace_period_days", 0),
            "usage": {
                "agents": {
                    "current": agents_count,
                    "limit": plan.max_agents if plan else 0,
                    "unlimited": plan.max_agents is None if plan else False,
                },
                "team_members": {
                    "current": team_members_count,
                    "limit": plan.max_team_members if plan else 0,
                    "unlimited": plan.max_team_members is None if plan else False,
                },
                "knowledge_bases": {
                    "current": knowledge_bases_count,
                    "limit": plan.max_knowledge_bases if plan else 0,
                    "unlimited": plan.max_knowledge_bases is None if plan else False,
                },
                "mcp_servers": {
                    "current": mcp_servers_count,
                    "limit": plan.max_mcp_servers if plan else 0,
                    "unlimited": plan.max_mcp_servers is None if plan else False,
                },
                "custom_tools": {
                    "current": custom_tools_count,
                    "limit": plan.max_custom_tools if plan else 0,
                    "unlimited": plan.max_custom_tools is None if plan else False,
                },
                "database_connections": {
                    "current": database_connections_count,
                    "limit": plan.max_database_connections if plan else 0,
                    "unlimited": plan.max_database_connections is None if plan else False,
                },
                "data_sources": {
                    "current": data_sources_count,
                    "limit": plan.max_data_sources if plan else 0,
                    "unlimited": plan.max_data_sources is None if plan else False,
                },
                "scheduled_tasks": {
                    "current": scheduled_tasks_count,
                    "limit": plan.max_scheduled_tasks if plan else 0,
                    "unlimited": plan.max_scheduled_tasks is None if plan else False,
                },
                "widgets": {
                    "current": widgets_count,
                    "limit": plan.max_widgets if plan else 0,
                    "unlimited": plan.max_widgets is None if plan else False,
                },
                "slack_bots": {
                    "current": slack_bots_count,
                    "limit": plan.max_slack_bots if plan else 0,
                    "unlimited": plan.max_slack_bots is None if plan else False,
                },
                "api_calls_per_month": {
                    "current": 0,  # API call tracking not yet implemented
                    "limit": plan.max_api_calls_per_month if plan else 0,
                    "unlimited": plan.max_api_calls_per_month is None if plan else False,
                },
            },
            "features": plan_features.get("features", {}),
        }
