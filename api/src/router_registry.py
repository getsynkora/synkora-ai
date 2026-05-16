"""
Declarative router registry for API routes.

This module provides a data-driven approach to router registration,
replacing 50+ import statements with a single configuration list.

Usage:
    from src.router_registry import register_all_routers
    register_all_routers(app)
"""

import importlib
import logging
from dataclasses import dataclass, field

from fastapi import FastAPI

logger = logging.getLogger(__name__)


@dataclass
class RouteConfig:
    """Configuration for a single router registration."""

    module: str  # e.g., "src.controllers.agents"
    attribute: str = "router"  # e.g., "router", "public_router", "agents_router"
    prefix: str = ""  # e.g., "/api/v1/agents"
    tags: list[str] = field(default_factory=list)  # e.g., ["agents"]


# Registry of all routes in the application
# Order matters for route matching (more specific routes should come first)
ROUTER_REGISTRY: list[RouteConfig] = [
    # ===== Legacy Console Routes (backwards compatibility) =====
    RouteConfig(
        module="src.controllers.console",
        attribute="console_router",
        prefix="/console/api",
        tags=["console"],
    ),
    RouteConfig(
        module="src.controllers.files",
        attribute="files_router",
        prefix="/console/api/files",
        tags=["files"],
    ),
    # ===== V1 API Routes =====
    RouteConfig(
        module="src.controllers.console.apps",
        attribute="router",
        prefix="/api/v1/apps",
        tags=["apps"],
    ),
    RouteConfig(
        module="src.controllers.files",
        attribute="files_router",
        prefix="/api/v1/files",
        tags=["files"],
    ),
    RouteConfig(
        module="src.controllers.service_api",
        attribute="service_router",
        prefix="/v1",
        tags=["service"],
    ),
    RouteConfig(
        module="src.controllers.web",
        attribute="web_router",
        prefix="/api",
        tags=["web"],
    ),
    # ===== Agents =====
    RouteConfig(
        module="src.controllers.agents",
        attribute="agents_router",
        prefix="/api/v1/agents",
        tags=["agents"],
    ),
    RouteConfig(
        module="src.controllers.agents.chat_config",
        attribute="router",
        prefix="/api/v1",
        tags=["chat-config"],
    ),
    RouteConfig(
        module="src.controllers.agents.sub_agents",
        attribute="router",
        prefix="/api/v1",
        tags=["sub-agents"],
    ),
    RouteConfig(
        module="src.controllers.agents.database_connections",
        attribute="router",
        prefix="/api/v1/agents",
        tags=["agent-database-connections"],
    ),
    RouteConfig(
        module="src.controllers.agents.webhooks",
        attribute="router",
        prefix="/api/v1/agents",
        tags=["webhooks"],
    ),
    RouteConfig(
        module="src.controllers.agents.webhooks",
        attribute="public_router",
        prefix="",
        tags=["webhooks-public"],
    ),
    RouteConfig(
        module="src.controllers.agents.outputs",
        attribute="router",
        prefix="/api/v1/agents",
        tags=["agent-outputs"],
    ),
    RouteConfig(
        module="src.controllers.agents.autonomous_agents",
        attribute="router",
        prefix="/api/v1/agents",
        tags=["autonomous-agents"],
    ),
    RouteConfig(
        module="src.controllers.agents.agent_lens",
        attribute="router",
        prefix="/api/v1/agents",
        tags=["agent-lens"],
    ),
    RouteConfig(
        module="src.controllers.agents.conversation_shares",
        attribute="conversation_shares_router",
        prefix="/api/v1/agents",
        tags=["conversation-shares"],
    ),
    RouteConfig(
        module="src.controllers.agents.share_public",
        attribute="share_public_router",
        prefix="",
        tags=["share-public"],
    ),
    RouteConfig(
        module="src.controllers.agents.compute",
        attribute="router",
        prefix="/api/v1/agents",
        tags=["agent-compute"],
    ),
    RouteConfig(
        module="src.controllers.tenant_compute_config",
        attribute="router",
        prefix="/api/v1",
        tags=["compute"],
    ),
    RouteConfig(
        module="src.controllers.agents.live_lab",
        attribute="router",
        prefix="/api/v1",
        tags=["live-lab"],
    ),
    RouteConfig(
        module="src.controllers.agents.war_room",
        attribute="router",
        prefix="/api/v1",
        tags=["war-room"],
    ),
    RouteConfig(
        module="src.controllers.agents.war_room",
        attribute="public_router",
        prefix="",
        tags=["war-room-public"],
    ),
    RouteConfig(
        module="src.controllers.knowledge_autopilot",
        attribute="router",
        prefix="/api/v1",
        tags=["knowledge-autopilot"],
    ),
    RouteConfig(
        module="src.controllers.rate_my_life",
        attribute="router",
        prefix="/api/v1",
        tags=["rate-my-life"],
    ),
    RouteConfig(
        module="src.controllers.agent_subscriptions",
        attribute="router",
        prefix="/api/v1/agents",
        tags=["subscriptions"],
    ),
    RouteConfig(
        module="src.controllers.agent_subscriptions",
        attribute="public_router",
        prefix="",
        tags=["subscriptions-public"],
    ),
    RouteConfig(
        module="src.controllers.agents.llm_configs",
        attribute="providers_router",
        prefix="",
        tags=["llm-providers"],
    ),
    # ===== Email Templates =====
    RouteConfig(
        module="src.controllers.email_templates",
        attribute="router",
        prefix="/api/v1",
        tags=["email-templates"],
    ),
    # ===== MCP Server Host (expose agents as MCP servers) =====
    RouteConfig(
        module="src.controllers.agents.mcp_server_host",
        attribute="mcp_host_router",
        prefix="/api/mcp",
        tags=["MCP Server"],
    ),
    # ===== A2A Protocol (expose agents via Google A2A) =====
    RouteConfig(
        module="src.controllers.agents.a2a",
        attribute="a2a_router",
        prefix="/api/a2a",
        tags=["A2A"],
    ),
    # ===== MCP & Tools =====
    RouteConfig(
        module="src.controllers.mcp_servers",
        attribute="router",
        prefix="",
        tags=["mcp"],
    ),
    RouteConfig(
        module="src.controllers.agents.mcp_servers",
        attribute="agents_mcp_servers_router",
        prefix="/api/v1/agents",
        tags=["agent-mcp-servers"],
    ),
    RouteConfig(
        module="src.controllers.tools",
        attribute="router",
        prefix="/api/v1",
        tags=["tools"],
    ),
    RouteConfig(
        module="src.controllers.custom_tools",
        attribute="router",
        prefix="/api/v1",
        tags=[],
    ),
    # ===== OAuth & Auth =====
    RouteConfig(
        module="src.controllers.oauth",
        attribute="router",
        prefix="",
        tags=["oauth"],
    ),
    RouteConfig(
        module="src.controllers.social_auth",
        attribute="router",
        prefix="",
        tags=["social-auth"],
    ),
    RouteConfig(
        module="src.controllers.social_auth_config",
        attribute="router",
        prefix="",
        tags=[],
    ),
    RouteConfig(
        module="src.controllers.okta_sso",
        attribute="router",
        prefix="",
        tags=["okta-sso"],
    ),
    # ===== SAML 2.0 SSO =====
    RouteConfig(
        module="src.controllers.console.saml_sso",
        attribute="saml_router",
        prefix="",
        tags=["saml-sso"],
    ),
    # ===== SCIM 2.0 User Provisioning =====
    RouteConfig(
        module="src.controllers.scim",
        attribute="scim_router",
        prefix="",
        tags=["scim"],
    ),
    # ===== Company Brain =====
    RouteConfig(
        module="src.controllers.brain_domains",
        attribute="router",
        prefix="/api/v1",
        tags=["company-brain"],
    ),
    # ===== Knowledge Bases & Data =====
    RouteConfig(
        module="src.controllers.knowledge_bases",
        attribute="router",
        prefix="/api/v1",
        tags=[],
    ),
    RouteConfig(
        module="src.controllers.data_sources",
        attribute="router",
        prefix="/api/v1",
        tags=[],
    ),
    RouteConfig(
        module="src.controllers.documents",
        attribute="router",
        prefix="",
        tags=["documents"],
    ),
    RouteConfig(
        module="src.controllers.data_analysis",
        attribute="router",
        prefix="",
        tags=["data-analysis"],
    ),
    RouteConfig(
        module="src.controllers.database_connections",
        attribute="router",
        prefix="",
        tags=["database-connections"],
    ),
    # ===== Widgets =====
    RouteConfig(
        module="src.controllers.widgets",
        attribute="widgets_router",
        prefix="/api/v1",
        tags=["widgets"],
    ),
    # ===== Bot Integrations =====
    RouteConfig(
        module="src.controllers.slack_bots",
        attribute="router",
        prefix="/api/v1",
        tags=["slack-bots"],
    ),
    RouteConfig(
        module="src.controllers.slack_webhooks",
        attribute="public_router",
        prefix="",
        tags=["slack-webhooks"],
    ),
    RouteConfig(
        module="src.controllers.telegram_bots",
        attribute="router",
        prefix="/api/v1",
        tags=["telegram-bots"],
    ),
    RouteConfig(
        module="src.controllers.telegram_bots",
        attribute="public_router",
        prefix="",
        tags=["telegram-webhooks"],
    ),
    RouteConfig(
        module="src.controllers.whatsapp_bots",
        attribute="whatsapp_router",
        prefix="/api/v1",
        tags=["whatsapp-bots"],
    ),
    RouteConfig(
        module="src.controllers.teams_bots",
        attribute="teams_router",
        prefix="/api/v1",
        tags=["teams-bots"],
    ),
    RouteConfig(
        module="src.controllers.bot_workers",
        attribute="router",
        prefix="",
        tags=["bot-workers"],
    ),
    # ===== Webhooks =====
    RouteConfig(
        module="src.controllers.recall_webhooks",
        attribute="public_router",
        prefix="",
        tags=["recall-webhooks"],
    ),
    # ===== Voice =====
    RouteConfig(
        module="src.controllers.voice",
        attribute="voice_router",
        prefix="/api/v1/voice",
        tags=["voice"],
    ),
    # ===== App Store & Charts =====
    RouteConfig(
        module="src.controllers.app_store_sources",
        attribute="router",
        prefix="/api/v1",
        tags=[],
    ),
    RouteConfig(
        module="src.controllers.charts",
        attribute="router",
        prefix="/api/v1",
        tags=[],
    ),
    # ===== Tasks & Scheduling =====
    RouteConfig(
        module="src.controllers.scheduled_tasks",
        attribute="router",
        prefix="/api/v1",
        tags=[],
    ),
    # ===== User & Team Management =====
    RouteConfig(
        module="src.controllers.profiles",
        attribute="router",
        prefix="/api/v1",
        tags=[],
    ),
    RouteConfig(
        module="src.controllers.teams",
        attribute="router",
        prefix="/api/v1",
        tags=[],
    ),
    RouteConfig(
        module="src.controllers.permissions",
        attribute="router",
        prefix="/api/v1",
        tags=[],
    ),
    RouteConfig(
        module="src.controllers.activity_logs",
        attribute="router",
        prefix="/api/v1",
        tags=[],
    ),
    # ===== API Keys & Domains =====
    RouteConfig(
        module="src.controllers.agent_api_keys",
        attribute="router",
        prefix="",
        tags=["agent-api-keys"],
    ),
    RouteConfig(
        module="src.controllers.agent_api_public",
        attribute="router",
        prefix="",
        tags=["agent-api-public"],
    ),
    RouteConfig(
        module="src.controllers.agent_domains",
        attribute="router",
        prefix="",
        tags=["agent-domains"],
    ),
    RouteConfig(
        module="src.controllers.agent_domains",
        attribute="public_router",
        prefix="",
        tags=["domain-resolution"],
    ),
    # ===== Public =====
    RouteConfig(
        module="src.controllers.contact",
        attribute="router",
        prefix="",
        tags=["contact"],
    ),
    # ===== Platform & Billing =====
    RouteConfig(
        module="src.controllers.platform_agent",
        attribute="router",
        prefix="/api/v1/platform-agent",
        tags=["platform-agent"],
    ),
    RouteConfig(
        module="src.controllers.platform_settings",
        attribute="router",
        prefix="/api/v1",
        tags=[],
    ),
    RouteConfig(
        module="src.controllers.billing",
        attribute="router",
        prefix="",
        tags=[],
    ),
    RouteConfig(
        module="src.controllers.usage_stats",
        attribute="router",
        prefix="/api/v1",
        tags=[],
    ),
    RouteConfig(
        module="src.controllers.integration_configs",
        attribute="router",
        prefix="",
        tags=[],
    ),
    # ===== Roles & Projects =====
    RouteConfig(
        module="src.controllers.agent_roles",
        attribute="router",
        prefix="/api/v1",
        tags=["agent-roles"],
    ),
    RouteConfig(
        module="src.controllers.human_contacts",
        attribute="router",
        prefix="/api/v1",
        tags=["human-contacts"],
    ),
    RouteConfig(
        module="src.controllers.projects",
        attribute="router",
        prefix="/api/v1",
        tags=["projects"],
    ),
    RouteConfig(
        module="src.controllers.escalations",
        attribute="router",
        prefix="/api/v1",
        tags=["escalations"],
    ),
    # ===== KB Webhooks (real-time data source ingestion) =====
    RouteConfig(
        module="src.controllers.kb_webhooks",
        attribute="public_router",
        prefix="",
        tags=["kb-webhooks"],
    ),
    # ===== Load Testing =====
    RouteConfig(
        module="src.controllers.load_tests",
        attribute="router",
        prefix="/api/v1",
        tags=["load-tests"],
    ),
    RouteConfig(
        module="src.controllers.test_runs",
        attribute="router",
        prefix="/api/v1",
        tags=["test-runs"],
    ),
    RouteConfig(
        module="src.controllers.proxy_configs",
        attribute="router",
        prefix="/api/v1",
        tags=["proxy"],
    ),
    RouteConfig(
        module="src.controllers.monitoring_integrations",
        attribute="router",
        prefix="/api/v1",
        tags=["monitoring"],
    ),
    RouteConfig(
        module="src.controllers.llm_proxy",
        attribute="router",
        prefix="",
        tags=["llm-proxy"],
    ),
    # ===== Agent Landing Pages =====
    RouteConfig(
        module="src.controllers.agents.landing_page",
        attribute="router",
        prefix="/api/v1/agents",
        tags=["landing-pages"],
    ),
    RouteConfig(
        module="src.controllers.agents.landing_page",
        attribute="public_router",
        prefix="",
        tags=["landing-pages"],
    ),
    RouteConfig(
        module="src.controllers.agents.landing_page",
        attribute="webhook_router",
        prefix="",
        tags=["webhooks"],
    ),
    # ===== Agent Public Profiles =====
    RouteConfig(
        module="src.controllers.agents.agent_public_profile",
        attribute="public_router",
        prefix="",
        tags=["agent-public-profiles"],
    ),
    # ===== Creator Profiles =====
    RouteConfig(
        module="src.controllers.creators",
        attribute="router",
        prefix="",
        tags=["creators"],
    ),
    RouteConfig(
        module="src.controllers.creators",
        attribute="public_router",
        prefix="",
        tags=["creators"],
    ),
    # ===== Discount Codes =====
    RouteConfig(
        module="src.controllers.agents.discount_codes",
        attribute="router",
        prefix="/api/v1/agents",
        tags=["discount-codes"],
    ),
    RouteConfig(
        module="src.controllers.agents.discount_codes",
        attribute="public_router",
        prefix="",
        tags=["discount-codes"],
    ),
    # ===== Agent User Subscriptions =====
    RouteConfig(
        module="src.controllers.agent_user_subscriptions",
        attribute="router",
        prefix="/api/v1",
        tags=["agent-subscriptions"],
    ),
    # ===== Agent Monetization (purchase endpoints) =====
    RouteConfig(
        module="src.controllers.agents.monetization",
        attribute="router",
        prefix="/api/v1/agents",
        tags=["agent-monetization"],
    ),
    RouteConfig(
        module="src.controllers.agents.monetization",
        attribute="public_router",
        prefix="",
        tags=["agent-monetization"],
    ),
    # ===== Newsletter Templates =====
    RouteConfig(
        module="src.controllers.newsletter_templates",
        attribute="router",
        prefix="/api",
        tags=["newsletter-templates"],
    ),
]


def register_all_routers(app: FastAPI) -> None:
    """
    Register all routers from the registry.

    Args:
        app: FastAPI application instance
    """
    registered_count = 0

    for config in ROUTER_REGISTRY:
        try:
            # Import the module
            module = importlib.import_module(config.module)

            # Get the router attribute
            router = getattr(module, config.attribute)

            # Build include_router kwargs
            kwargs = {}
            if config.prefix:
                kwargs["prefix"] = config.prefix
            if config.tags:
                kwargs["tags"] = config.tags

            # Register the router
            app.include_router(router, **kwargs)
            registered_count += 1

            logger.debug(f"Registered router: {config.module}.{config.attribute} -> {config.prefix or '/'}")

        except ImportError as e:
            logger.error(f"Failed to import module {config.module}: {e}")
            raise
        except AttributeError as e:
            logger.error(f"Module {config.module} has no attribute {config.attribute}: {e}")
            raise

    logger.info(f"Registered {registered_count} routers from registry")
