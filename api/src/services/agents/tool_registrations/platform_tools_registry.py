"""
Platform Engineer Tools Registry

Registers platform management tools with the ADK tool registry.
These tools allow the platform engineer agent to operate the platform:
create agents, list agents, check integration status.

Follows the same pattern as github_repo_tools_registry.py.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register_platform_tools(registry) -> None:
    """
    Register all platform engineer tools with the ADK tool registry.

    Args:
        registry: ADKToolRegistry instance
    """
    from src.services.agents.internal_tools.platform_tools import (
        platform_check_integration,
        platform_create_agent,
        platform_create_slack_bot,
        platform_create_telegram_bot,
        platform_delete_agent_channel,
        platform_get_available_tools,
        platform_list_agent_channels,
        platform_list_agents,
        platform_update_agent,
    )

    # --- Wrappers that inject runtime_context from config ---

    async def platform_list_agents_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await platform_list_agents(runtime_context=runtime_context)

    async def platform_get_available_tools_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await platform_get_available_tools(runtime_context=runtime_context)

    async def platform_check_integration_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await platform_check_integration(
            provider=kwargs.get("provider", ""),
            runtime_context=runtime_context,
        )

    async def platform_create_agent_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await platform_create_agent(
            name=kwargs.get("name", ""),
            description=kwargs.get("description", ""),
            system_prompt=kwargs.get("system_prompt", ""),
            agent_type=kwargs.get("agent_type", "LLM"),
            llm_provider=kwargs.get("llm_provider", "openai"),
            llm_model=kwargs.get("llm_model", "gpt-4o"),
            api_key=kwargs.get("api_key", ""),
            tools_list=kwargs.get("tools_list"),
            category=kwargs.get("category"),
            tags=kwargs.get("tags"),
            image_llm_provider=kwargs.get("image_llm_provider"),
            image_llm_model=kwargs.get("image_llm_model"),
            runtime_context=runtime_context,
        )

    async def platform_update_agent_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await platform_update_agent(
            agent_name=kwargs.get("agent_name", ""),
            description=kwargs.get("description"),
            system_prompt=kwargs.get("system_prompt"),
            status=kwargs.get("status"),
            tools_list=kwargs.get("tools_list"),
            image_llm_provider=kwargs.get("image_llm_provider"),
            image_llm_model=kwargs.get("image_llm_model"),
            runtime_context=runtime_context,
        )

    # --- Tool registrations ---

    registry.register_tool(
        name="platform_list_agents",
        description="List all AI agents for the current tenant. Returns agent names, descriptions, status, and tool counts.",
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
        function=platform_list_agents_wrapper,
    )

    registry.register_tool(
        name="platform_get_available_tools",
        description=(
            "Get all tool categories available on this platform, with descriptions and OAuth requirements. "
            "Use this to understand what capabilities agents can have and which integrations are needed."
        ),
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
        function=platform_get_available_tools_wrapper,
    )

    registry.register_tool(
        name="platform_check_integration",
        description=(
            "Check whether the current user has connected a specific OAuth integration. "
            "Always call this before designing an agent that requires an integration (github, slack, gmail, etc.)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "provider": {
                    "type": "string",
                    "description": (
                        "Integration provider name, e.g. 'github', 'gitlab', 'slack', 'gmail', "
                        "'google_calendar', 'google_drive', 'jira', 'zoom', 'twitter', 'linkedin'"
                    ),
                }
            },
            "required": ["provider"],
        },
        function=platform_check_integration_wrapper,
    )

    registry.register_tool(
        name="platform_create_agent",
        description=(
            "Create a new AI agent for the current tenant. "
            "IMPORTANT: Before calling this tool you MUST first output the marker: "
            '__ACTION__{"type":"create_agent","config":{...}}__ACTION__ '
            "and wait for the user to confirm. Only call this tool after the user "
            "sends __CONFIRMED__ in their reply. "
            "The 'config' object in the marker must include: "
            "name, description, system_prompt, and optionally tools_list, image_llm_provider, image_llm_model."
        ),
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Human-readable agent name (will be slugified)"},
                "description": {"type": "string", "description": "Short description of what the agent does"},
                "system_prompt": {"type": "string", "description": "The agent's system instructions"},
                "agent_type": {
                    "type": "string",
                    "enum": ["LLM", "research", "code"],
                    "description": "Agent type (default: LLM)",
                    "default": "LLM",
                },
                "llm_provider": {
                    "type": "string",
                    "enum": ["openai", "anthropic", "google", "groq"],
                    "description": "LLM provider (default: openai)",
                    "default": "openai",
                },
                "llm_model": {
                    "type": "string",
                    "description": "Model identifier, e.g. gpt-4o, claude-3-5-sonnet-20241022, gemini-2.0-flash-exp",
                    "default": "gpt-4o",
                },
                "api_key": {
                    "type": "string",
                    "description": "Provider API key (stored encrypted). Leave empty to use platform default.",
                    "default": "",
                },
                "tools_list": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of tool category names to enable (from platform_get_available_tools)",
                },
                "image_llm_provider": {
                    "type": "string",
                    "description": "Optional provider for image generation agents, e.g. openai or google.",
                },
                "image_llm_model": {
                    "type": "string",
                    "description": "Optional image model, e.g. gpt-image-2 or imagen-3.0-generate-002.",
                },
                "category": {"type": "string", "description": "Agent category for organization"},
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of tags for discovery",
                },
            },
            "required": ["name", "description", "system_prompt"],
        },
        function=platform_create_agent_wrapper,
        tool_category="action",
    )

    registry.register_tool(
        name="platform_update_agent",
        description=(
            "Update an existing agent's description, system prompt, status, or tools. "
            "Use tools_list to add tool capabilities to an existing agent — pass the same "
            "tool category names used in platform_create_agent (e.g. browser_tools, scheduler_tools). "
            "Only updates fields that are explicitly provided."
        ),
        parameters={
            "type": "object",
            "properties": {
                "agent_name": {"type": "string", "description": "The agent's name/slug to update"},
                "description": {"type": "string", "description": "New description (optional)"},
                "system_prompt": {"type": "string", "description": "New system prompt (optional)"},
                "status": {
                    "type": "string",
                    "enum": ["ACTIVE", "INACTIVE"],
                    "description": "New status (optional)",
                },
                "tools_list": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Tool category names to enable on the agent (optional). "
                        "Adds tools without removing existing ones. "
                        "Use the same names as platform_create_agent: "
                        "browser_tools, scheduler_tools, email_tools, gmail_tools, "
                        "file_tools, storage_tools, command_tools, database_tools, image_generation, "
                        "elasticsearch_tools, data_analysis_tools, document_tools, "
                        "github_tools, gitlab_tools, slack_tools, jira_tools, "
                        "clickup_tools, zoom_tools, google_calendar_tools, "
                        "google_drive_tools, twitter_tools, linkedin_tools, "
                        "youtube_tools, news_tools."
                    ),
                },
                "image_llm_provider": {
                    "type": "string",
                    "description": "Optional provider for the agent's image generation config.",
                },
                "image_llm_model": {
                    "type": "string",
                    "description": "Optional image model to assign, e.g. gpt-image-2.",
                },
            },
            "required": ["agent_name"],
        },
        function=platform_update_agent_wrapper,
        tool_category="action",
    )

    async def platform_create_slack_bot_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await platform_create_slack_bot(
            agent_name=kwargs.get("agent_name", ""),
            bot_name=kwargs.get("bot_name", ""),
            bot_token=kwargs.get("bot_token", ""),
            connection_mode=kwargs.get("connection_mode", "socket"),
            app_token=kwargs.get("app_token"),
            signing_secret=kwargs.get("signing_secret"),
            app_id=kwargs.get("app_id", ""),
            runtime_context=runtime_context,
        )

    async def platform_create_telegram_bot_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await platform_create_telegram_bot(
            agent_name=kwargs.get("agent_name", ""),
            bot_name=kwargs.get("bot_name", ""),
            bot_token=kwargs.get("bot_token", ""),
            runtime_context=runtime_context,
        )

    async def platform_list_agent_channels_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await platform_list_agent_channels(
            agent_name=kwargs.get("agent_name", ""),
            runtime_context=runtime_context,
        )

    async def platform_delete_agent_channel_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await platform_delete_agent_channel(
            channel=kwargs.get("channel", ""),
            bot_id=kwargs.get("bot_id", ""),
            runtime_context=runtime_context,
        )

    registry.register_tool(
        name="platform_create_slack_bot",
        description=(
            "Create a Slack bot for an agent and connect it to a Slack workspace. "
            "Can target any agent by name, or 'platform_engineer_agent' to connect the PE itself. "
            "Guide the user to create a Slack app at api.slack.com/apps, enable Socket Mode, "
            "then collect the Bot Token (xoxb-...) and App Token (xapp-...) before calling this. "
            "For Event Mode, collect the Signing Secret instead of the App Token."
        ),
        parameters={
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "description": "Slug name of the target agent, or 'platform_engineer_agent'",
                },
                "bot_name": {"type": "string", "description": "Display name for the Slack bot"},
                "bot_token": {"type": "string", "description": "Bot user OAuth token from Slack (xoxb-...)"},
                "connection_mode": {
                    "type": "string",
                    "enum": ["socket", "event"],
                    "description": "Connection mode: 'socket' (recommended, needs app_token) or 'event' (needs signing_secret)",
                    "default": "socket",
                },
                "app_token": {"type": "string", "description": "App-level token for Socket Mode (xapp-...)"},
                "signing_secret": {"type": "string", "description": "Signing secret for Event Mode"},
                "app_id": {"type": "string", "description": "Slack App ID from app settings (optional)"},
            },
            "required": ["agent_name", "bot_name", "bot_token"],
        },
        function=platform_create_slack_bot_wrapper,
        tool_category="action",
    )

    registry.register_tool(
        name="platform_create_telegram_bot",
        description=(
            "Create a Telegram bot for an agent. "
            "Can target any agent by name, or 'platform_engineer_agent' to connect the PE itself. "
            "Guide the user to message @BotFather on Telegram, type /newbot, follow the prompts, "
            "then paste the bot token here before calling this tool."
        ),
        parameters={
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "description": "Slug name of the target agent, or 'platform_engineer_agent'",
                },
                "bot_name": {"type": "string", "description": "Display name for the Telegram bot"},
                "bot_token": {"type": "string", "description": "Bot token from @BotFather (format: 123456:ABC-...)"},
            },
            "required": ["agent_name", "bot_name", "bot_token"],
        },
        function=platform_create_telegram_bot_wrapper,
        tool_category="action",
    )

    registry.register_tool(
        name="platform_list_agent_channels",
        description=(
            "List all Slack and Telegram bots connected to a given agent. "
            "Use this to check which channels an agent is available on, or to find bot_ids before disconnecting."
        ),
        parameters={
            "type": "object",
            "properties": {
                "agent_name": {"type": "string", "description": "Slug name of the agent to inspect"},
            },
            "required": ["agent_name"],
        },
        function=platform_list_agent_channels_wrapper,
    )

    registry.register_tool(
        name="platform_delete_agent_channel",
        description=(
            "Disconnect a Slack or Telegram bot from an agent (soft-delete). "
            "Call platform_list_agent_channels first to get the bot_id."
        ),
        parameters={
            "type": "object",
            "properties": {
                "channel": {
                    "type": "string",
                    "enum": ["slack", "telegram"],
                    "description": "Which channel type to disconnect",
                },
                "bot_id": {"type": "string", "description": "UUID of the bot to disconnect"},
            },
            "required": ["channel", "bot_id"],
        },
        function=platform_delete_agent_channel_wrapper,
        tool_category="action",
    )

    logger.info("Registered 9 platform engineer tools")
