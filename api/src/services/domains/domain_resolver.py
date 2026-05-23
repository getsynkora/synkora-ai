"""
Domain Resolution Service

Resolves incoming requests to the appropriate agent based on domain/subdomain.
Handles both custom domains and platform subdomains.
"""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.agent_domain import AgentDomain
from src.models.tenant_portal import TenantPortal

logger = logging.getLogger(__name__)


class DomainResolver:
    """Service for resolving domains to agents and their configurations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def resolve_agent_from_domain(self, domain: str) -> Agent | None:
        """
        Resolve agent from custom domain or subdomain

        Args:
            domain: The domain to resolve (e.g., 'chat.example.com' or 'product-owner.synkora.ai')

        Returns:
            Agent object if found, None otherwise
        """
        try:
            # First, check if it's a custom domain
            agent = await self._resolve_custom_domain(domain)
            if agent:
                return agent

            # If not found, check if it's a platform subdomain
            agent = await self._resolve_subdomain(domain)
            if agent:
                return agent

            logger.warning(f"No agent found for domain: {domain}")
            return None

        except Exception as e:
            logger.error(f"Error resolving domain {domain}: {str(e)}")
            return None

    async def resolve_agent_by_slug(self, agent_slug: str) -> Agent | None:
        """
        Resolve agent by slug directly (for URL-based routing)

        Args:
            agent_slug: The slug to resolve (e.g., 'product-owner-agent')

        Returns:
            Agent object if found, None otherwise
        """
        try:
            stmt = select(Agent).where(Agent.slug == agent_slug, Agent.status == "ACTIVE")

            result = await self.db.execute(stmt)
            agent = result.scalar_one_or_none()

            if agent:
                logger.info(f"Resolved slug {agent_slug} to agent {agent.slug}")

            return agent

        except Exception as e:
            logger.error(f"Error resolving slug {agent_slug}: {str(e)}")
            return None

    async def _resolve_custom_domain(self, domain: str) -> Agent | None:
        """
        Resolve agent from custom domain

        Args:
            domain: Custom domain (e.g., 'chat.example.com')

        Returns:
            Agent object if found, None otherwise
        """
        try:
            # Query for verified custom domain
            stmt = (
                select(Agent)
                .join(AgentDomain, Agent.id == AgentDomain.agent_id)
                .where(
                    AgentDomain.domain == domain,
                    AgentDomain.is_verified,
                    AgentDomain.status == "active",
                    Agent.status == "ACTIVE",
                )
            )

            result = await self.db.execute(stmt)
            agent = result.scalar_one_or_none()

            if agent:
                logger.info(f"Resolved custom domain {domain} to agent {agent.agent_name}")

            return agent

        except Exception as e:
            logger.error(f"Error resolving custom domain {domain}: {str(e)}")
            return None

    async def _resolve_subdomain(self, domain: str) -> Agent | None:
        """
        Resolve agent from platform subdomain

        Args:
            domain: Full domain (e.g., 'product-owner.synkora.ai')

        Returns:
            Agent object if found, None otherwise
        """
        try:
            # Extract subdomain from domain
            # Expected format: {subdomain}.synkora.ai or {subdomain}.synkora.ai
            parts = domain.split(".")

            if len(parts) < 2:
                return None

            subdomain = parts[0]

            # First try to find by subdomain in agent_domains table
            stmt = (
                select(Agent)
                .join(AgentDomain, Agent.id == AgentDomain.agent_id)
                .where(AgentDomain.subdomain == subdomain, AgentDomain.status == "active", Agent.status == "ACTIVE")
            )

            result = await self.db.execute(stmt)
            agent = result.scalar_one_or_none()

            if agent:
                logger.info(f"Resolved subdomain {subdomain} to agent {agent.agent_name}")
                return agent

            return None

        except Exception as e:
            logger.error(f"Error resolving subdomain from {domain}: {str(e)}")
            return None

    async def get_chat_config(self, agent_id: str, domain: str | None = None) -> dict[str, Any]:
        """
        Get chat page configuration for the agent and domain

        Args:
            agent_id: Agent ID
            domain: Optional domain to get specific configuration

        Returns:
            Dictionary containing chat page configuration
        """
        try:
            # Get agent
            stmt = select(Agent).where(Agent.id == agent_id)
            result = await self.db.execute(stmt)
            agent = result.scalar_one_or_none()

            if not agent:
                logger.warning(f"Agent not found: {agent_id}")
                return self._get_default_config()

            # If domain is provided, get domain-specific configuration
            if domain:
                domain_config = await self._get_domain_config(agent_id, domain)
                if domain_config:
                    return domain_config

            # Return default agent configuration
            return self._get_agent_default_config(agent)

        except Exception as e:
            logger.error(f"Error getting chat config for agent {agent_id}: {str(e)}")
            return self._get_default_config()

    async def _get_domain_config(self, agent_id: str, domain: str) -> dict[str, Any] | None:
        """
        Get domain-specific chat configuration

        Args:
            agent_id: Agent ID
            domain: Domain name

        Returns:
            Configuration dictionary if found, None otherwise
        """
        try:
            # Try exact domain match first
            stmt = select(AgentDomain).where(
                AgentDomain.agent_id == agent_id,
                AgentDomain.domain == domain,
                AgentDomain.is_verified,
                AgentDomain.status == "active",
            )

            result = await self.db.execute(stmt)
            agent_domain = result.scalar_one_or_none()

            if agent_domain and agent_domain.chat_page_config:
                logger.info(f"Found domain-specific config for {domain}")
                return agent_domain.chat_page_config

            # Try subdomain match
            parts = domain.split(".")
            if len(parts) > 0:
                subdomain = parts[0]
                stmt = select(AgentDomain).where(
                    AgentDomain.agent_id == agent_id, AgentDomain.subdomain == subdomain, AgentDomain.status == "active"
                )

                result = await self.db.execute(stmt)
                agent_domain = result.scalar_one_or_none()

                if agent_domain and agent_domain.chat_page_config:
                    logger.info(f"Found subdomain-specific config for {subdomain}")
                    return agent_domain.chat_page_config

            return None

        except Exception as e:
            logger.error(f"Error getting domain config for {domain}: {str(e)}")
            return None

    def _get_agent_default_config(self, agent: Agent) -> dict[str, Any]:
        """
        Get default configuration from agent

        Args:
            agent: Agent object

        Returns:
            Default configuration dictionary
        """
        return {
            "page_title": agent.agent_name,
            "logo_url": agent.avatar or "",
            "favicon_url": "",
            "primary_color": "#3B82F6",
            "secondary_color": "#60A5FA",
            "background_color": "#FFFFFF",
            "text_color": "#1F2937",
            "chat_bubble_color": "#DBEAFE",
            "user_message_color": "#3B82F6",
            "bot_message_color": "#F3F4F6",
            "welcome_message": f"Welcome! I'm {agent.agent_name}. How can I help you today?",
            "description": agent.description or "",
            "footer_text": "Powered by Synkora",
            "custom_css": "",
            "show_branding": True,
            "enable_file_upload": True,
            "enable_voice_input": False,
            "meta_title": agent.agent_name,
            "meta_description": agent.description or "",
            "meta_keywords": "",
        }

    def _get_default_config(self) -> dict[str, Any]:
        """
        Get fallback default configuration

        Returns:
            Default configuration dictionary
        """
        return {
            "page_title": "AI Chat Assistant",
            "logo_url": "",
            "favicon_url": "",
            "primary_color": "#3B82F6",
            "secondary_color": "#60A5FA",
            "background_color": "#FFFFFF",
            "text_color": "#1F2937",
            "chat_bubble_color": "#DBEAFE",
            "user_message_color": "#3B82F6",
            "bot_message_color": "#F3F4F6",
            "welcome_message": "Welcome! How can I help you today?",
            "description": "Chat with our AI assistant",
            "footer_text": "Powered by Synkora",
            "custom_css": "",
            "show_branding": True,
            "enable_file_upload": True,
            "enable_voice_input": False,
            "meta_title": "AI Chat Assistant",
            "meta_description": "Get instant help from our AI-powered assistant",
            "meta_keywords": "",
        }

    async def resolve_portal_from_domain(self, domain: str) -> TenantPortal | None:
        """
        Resolve a TenantPortal by custom domain (Host header).

        Allows portal endpoints to work via custom domain without a slug in the URL.
        Returns None if the domain is not mapped to any active portal.

        Args:
            domain: The incoming hostname (e.g. 'ai.acmecorp.com')

        Returns:
            TenantPortal if found and enabled, None otherwise
        """
        try:
            result = await self.db.execute(
                select(TenantPortal).where(
                    TenantPortal.portal_domain == domain,
                    TenantPortal.portal_enabled.is_(True),
                )
            )
            portal = result.scalar_one_or_none()
            if portal:
                logger.info(f"Resolved portal domain {domain} to tenant {portal.tenant_id}")
            return portal
        except Exception as e:
            logger.error(f"Error resolving portal domain {domain}: {e}")
            return None

    async def resolve_portal_tenant_id(self, domain: str) -> UUID | None:
        """
        Return the tenant_id for a given portal custom domain, or None.

        Convenience wrapper used by middleware to inject tenant context
        for custom-domain portal requests.
        """
        portal = await self.resolve_portal_from_domain(domain)
        return portal.tenant_id if portal else None

    async def is_domain_available(self, domain: str) -> bool:
        """
        Check if a domain is available for registration

        Args:
            domain: Domain to check

        Returns:
            True if available, False otherwise
        """
        try:
            stmt = select(AgentDomain).where(AgentDomain.domain == domain)

            result = await self.db.execute(stmt)
            existing_domain = result.scalar_one_or_none()

            return existing_domain is None

        except Exception as e:
            logger.error(f"Error checking domain availability for {domain}: {str(e)}")
            return False
