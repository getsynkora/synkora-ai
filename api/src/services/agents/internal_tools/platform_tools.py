"""
Platform Engineer Agent Tools

Provides tools that allow the platform engineer agent to operate the platform:
create agents, list agents, check integration status, get available tools.

Phase 1: Agents
Phase 2 (future): Knowledge bases, data sources
Phase 3 (future): Integrations, MCP servers, billing
"""

import logging
from typing import Any
from uuid import uuid4

from sqlalchemy import select

logger = logging.getLogger(__name__)

IMAGE_GENERATION_CATEGORY = "image_generation"

IMAGE_PROVIDER_DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-image-2",
    "litellm": "gpt-image-2",
    "azure_openai": "gpt-image-2",
    "google": "imagen-3.0-generate-002",
    "gemini": "imagen-3.0-generate-002",
    "xai": "grok-2-image",
    "grok": "grok-2-image",
    "x-ai": "grok-2-image",
    "x_ai": "grok-2-image",
}

TOOL_CATEGORY_ALIASES: dict[str, str] = {
    "web_search": "browser_tools",
    "browser": "browser_tools",
    "send_email": "email_tools",
    "email": "email_tools",
    "storage": "storage_tools",
    "s3": "storage_tools",
    "generate_image": IMAGE_GENERATION_CATEGORY,
    "internal_generate_image": IMAGE_GENERATION_CATEGORY,
}


def normalize_tool_categories(tools_list: list[str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()

    for raw_name in tools_list or []:
        tool_name = TOOL_CATEGORY_ALIASES.get(raw_name, raw_name)
        if tool_name not in seen:
            seen.add(tool_name)
            normalized.append(tool_name)

    return normalized


def resolve_image_generation_config(
    tools_list: list[str] | None = None,
    image_llm_provider: str | None = None,
    image_llm_model: str | None = None,
    fallback_provider: str | None = None,
) -> dict[str, str] | None:
    wants_image_generation = (
        IMAGE_GENERATION_CATEGORY in (tools_list or []) or bool(image_llm_provider) or bool(image_llm_model)
    )
    if not wants_image_generation:
        return None

    provider = (image_llm_provider or fallback_provider or "openai").strip().lower()
    model = (image_llm_model or IMAGE_PROVIDER_DEFAULT_MODELS.get(provider) or "gpt-image-2").strip()
    return {"provider": provider, "model": model}


async def upsert_image_generation_llm_config(
    *,
    db_session: Any,
    agent: Any,
    tenant_id: Any,
    encrypted_api_key: str,
    api_base: str | None,
    additional_params: dict[str, Any] | None,
    provider: str,
    model_name: str,
) -> None:
    from sqlalchemy.orm.attributes import flag_modified

    from src.models.agent_llm_config import AgentLLMConfig

    metadata = dict(agent.agent_metadata or {})
    existing_config_id = metadata.get("image_generation_llm_config_id")
    existing_cfg = None

    if existing_config_id:
        existing_cfg = (
            await db_session.execute(
                select(AgentLLMConfig).where(
                    AgentLLMConfig.id == existing_config_id,
                    AgentLLMConfig.agent_id == agent.id,
                    AgentLLMConfig.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()

    if existing_cfg:
        existing_cfg.name = "Image Generation"
        existing_cfg.provider = provider
        existing_cfg.model_name = model_name
        existing_cfg.api_key = encrypted_api_key
        existing_cfg.api_base = api_base
        existing_cfg.additional_params = additional_params or {}
        existing_cfg.enabled = True
        image_cfg = existing_cfg
    else:
        image_cfg = AgentLLMConfig(
            id=uuid4(),
            agent_id=agent.id,
            tenant_id=tenant_id,
            name="Image Generation",
            provider=provider,
            model_name=model_name,
            api_key=encrypted_api_key,
            api_base=api_base,
            temperature=0.7,
            max_tokens=None,
            top_p=None,
            additional_params=additional_params or {},
            is_default=False,
            display_order=1,
            enabled=True,
        )
        db_session.add(image_cfg)
        await db_session.flush()

    metadata["image_generation_llm_config_id"] = str(image_cfg.id)
    agent.agent_metadata = metadata
    flag_modified(agent, "agent_metadata")


# All tool categories available on the platform with OAuth requirements
PLATFORM_TOOL_CATALOG = {
    "browser_tools": {
        "description": (
            "Full Playwright browser automation: navigate pages, take screenshots, click buttons, "
            "fill forms, extract structured data, handle dialogs, manage cookies/storage. "
            "Use this when you need screenshots, JS-rendered pages, or interactive browser sessions."
        ),
        "requires_oauth": [],
    },
    "scheduler_tools": {
        "description": (
            "Schedule the agent to run automatically. Supports cron expressions (specific time daily/weekly) "
            "and interval-based scheduling. The agent will self-schedule using internal_create_cron_scheduled_task "
            "or internal_create_scheduled_task. Timezone-aware: cron times are written in user's local time."
        ),
        "requires_oauth": [],
    },
    "email_tools": {
        "description": "Send emails via SMTP (no OAuth needed — uses platform SMTP config)",
        "requires_oauth": [],
    },
    "push_notification_tools": {
        "description": "Send FCM push notifications to mobile users who have the synkora_push Flutter package installed. Use for proactive alerts, task completion notifications, and reports. Requires FCM server key configured in widget settings.",
        "requires_oauth": [],
    },
    "newsletter_tools": {
        "description": "Render 'The Signal' newsletter from structured JSON into production-quality HTML with PDF and share image generation",
        "requires_oauth": [],
    },
    "file_tools": {
        "description": "Read, write, and edit files in the agent workspace",
        "requires_oauth": [],
    },
    "command_tools": {
        "description": "Run shell commands (git, npm, pip, bash, etc.) in a sandboxed environment",
        "requires_oauth": [],
    },
    "database_tools": {
        "description": "Query attached database connections (PostgreSQL, MySQL, SQLite, etc.)",
        "requires_oauth": [],
    },
    "elasticsearch_tools": {
        "description": "Search and index documents in Elasticsearch",
        "requires_oauth": [],
    },
    "data_analysis_tools": {
        "description": "Analyze datasets, run statistical analysis, and generate charts/reports",
        "requires_oauth": [],
    },
    "image_generation": {
        "description": (
            "Generate AI images from text prompts for avatars, illustrations, marketing creatives, and branded visuals. "
            "Supports OpenAI gpt-image-2, Google Imagen 3, and Grok image models."
        ),
        "requires_oauth": [],
    },
    "storage_tools": {
        "description": "Upload and retrieve files from S3/MinIO storage",
        "requires_oauth": [],
    },
    "news_tools": {
        "description": "Search latest news articles (NewsAPI and HackerNews). NewsAPI requires an API key integration.",
        "requires_oauth": [],
        "requires_integration": ["newsapi"],
    },
    "openweather_tools": {
        "description": (
            "Current weather and hourly forecast (up to 48h) for any lat/lng via OpenWeatherMap. "
            "Requires an OpenWeather API key integration. Prefer this over browser_tools for any "
            "agent that needs weather data — it returns structured temperature/precipitation/wind "
            "data instead of scraping a weather website."
        ),
        "requires_oauth": ["openweather"],
        "requires_integration": ["openweather"],
    },
    "openmeteo_tools": {
        "description": (
            "Current weather and hourly forecast (up to 48h) for any lat/lng via Open-Meteo — free, "
            "no API key required. Use this as the default weather tool when OpenWeather is not "
            "configured. Prefer this over browser_tools for any agent that needs weather data."
        ),
        "requires_oauth": [],
    },
    "micromobility_event_tools": {
        "description": (
            "Event impact analysis, network health, parking compliance, battery degradation, and "
            "ranger performance for a micromobility fleet. Requires a micromobility API integration."
        ),
        "requires_oauth": ["micromobility"],
        "requires_integration": ["micromobility"],
    },
    "document_tools": {
        "description": "Parse and extract text from PDFs, Word docs, Excel files",
        "requires_oauth": [],
    },
    "kb_ingest_tools": {
        "description": (
            "Crawl any public URL and save it to a knowledge base, or add manual how-to guides and "
            "reference content directly to a knowledge base for future agent retrieval."
        ),
        "requires_oauth": [],
    },
    "github_tools": {
        "description": "Full GitHub: search repos, read/create issues, open PRs, manage branches and commits",
        "requires_oauth": ["github"],
    },
    "gitlab_tools": {
        "description": "Manage GitLab repos, issues, and merge requests",
        "requires_oauth": ["gitlab"],
    },
    "gmail_tools": {
        "description": "Read, send, search, and manage Gmail messages and labels",
        "requires_oauth": ["gmail"],
    },
    "google_calendar_tools": {
        "description": "Create, update, query, and delete Google Calendar events",
        "requires_oauth": ["google_calendar"],
    },
    "google_drive_tools": {
        "description": "Read, upload, search, and manage Google Drive files and folders",
        "requires_oauth": ["google_drive"],
    },
    "slack_tools": {
        "description": "Send messages to channels/users, read channel history, manage Slack workspaces",
        "requires_oauth": ["slack"],
    },
    "jira_tools": {
        "description": "Create and manage Jira issues, transitions, sprints, and projects",
        "requires_oauth": ["jira"],
    },
    "zoom_tools": {
        "description": "Schedule Zoom meetings and access recordings",
        "requires_oauth": ["zoom"],
    },
    "twitter_tools": {
        "description": "Post tweets, search Twitter/X, and manage engagement",
        "requires_oauth": ["twitter"],
    },
    "linkedin_tools": {
        "description": "Post to LinkedIn and search professional content",
        "requires_oauth": ["linkedin"],
    },
    "youtube_tools": {
        "description": "Search YouTube videos, fetch transcripts, and get channel info",
        "requires_oauth": [],
    },
    "clickup_tools": {
        "description": "Create and manage ClickUp tasks and projects",
        "requires_oauth": ["clickup"],
    },
    "spawn_agent_tool": {
        "description": "Spawn another agent as a sub-task (multi-agent orchestration)",
        "requires_oauth": [],
    },
    "tutorial_tools": {
        "description": "Generate a tutorial from a public GitHub repo: fetch files, identify abstractions, analyze relationships, and write ordered chapters",
        "requires_oauth": [],
    },
    "contract_tools": {
        "description": "Analyze contracts and generate risk/summary reports",
        "requires_oauth": [],
    },
    "followup_tools": {
        "description": "Track, escalate, and send follow-up messages (including searching Slack mentions). Requires a Slack integration for the Slack-related actions.",
        "requires_oauth": ["slack"],
    },
    "zendesk_tools": {
        "description": "Search, create, update, and comment on Zendesk support tickets",
        "requires_oauth": ["zendesk"],
    },
    "zoho_crm_tools": {
        "description": "Search, create, update, and annotate Zoho CRM records",
        "requires_oauth": ["zoho_crm"],
    },
    "events_tools": {
        "description": "Discover local events (concerts, sports, attendance-based impact scores) via PredictHQ or Ticketmaster",
        "requires_oauth": ["predicthq"],
    },
    "mapbox_tools": {
        "description": "Generate static maps and turn-by-turn directions via Mapbox",
        "requires_oauth": ["mapbox"],
    },
    "blog_site_tools": {
        "description": "Generate a blog site and deploy it to GitHub Pages. Requires a GitHub integration for deployment.",
        "requires_oauth": ["github"],
    },
    "role_tools": {
        "description": (
            "Multi-agent project roles: get project info/context, escalate to a human contact, "
            "check escalation status, and list project agents/roles"
        ),
        "requires_oauth": [],
    },
    "onepassword_tools": {
        "description": "Read, create, update, and archive 1Password items and secrets; generate secure passwords",
        "requires_oauth": ["onepassword"],
    },
    "diagram_tools": {
        "description": "Generate diagrams (flowcharts, architecture diagrams, etc.)",
        "requires_oauth": [],
    },
    "infographic_tools": {
        "description": "Generate infographics, including Slack-formatted infographics",
        "requires_oauth": [],
    },
    "video_tools": {
        "description": (
            "Scrape a website for video content, and generate AI video via Kling or Minimax. "
            "Video generation requires a Kling or Minimax API integration."
        ),
        "requires_oauth": ["kling"],
    },
    "recall_tools": {
        "description": "Send a bot to record and transcribe meetings, and summarize the recording. Requires a Recall.ai integration.",
        "requires_oauth": ["recall"],
    },
    "speckit_tools": {
        "description": "Spec-driven development workflow: specify, plan, break into tasks, and commit",
        "requires_oauth": [],
    },
}


async def platform_list_agents(runtime_context: Any = None) -> dict:
    """
    List all agents for the current tenant.

    Returns a summary of each agent including name, description, status,
    agent type, and tool count.
    """
    if not runtime_context or not runtime_context.tenant_id:
        return {"error": "No tenant context available"}

    try:
        from src.models.agent import Agent

        db = runtime_context.db_session
        result = await db.execute(
            select(Agent)
            .where(Agent.tenant_id == runtime_context.tenant_id)
            .order_by(Agent.created_at.desc())
            .limit(100)
        )
        all_agents = result.scalars().all()
        # Filter out platform-level agents in Python to avoid JSON operator complexity
        agents = [a for a in all_agents if not (a.agent_metadata or {}).get("is_platform_agent")]

        agent_list = []
        for a in agents:
            tool_count = len(a.tools_config) if isinstance(a.tools_config, list) else 0
            agent_list.append(
                {
                    "name": a.agent_name,
                    "description": a.description,
                    "status": a.status,
                    "agent_type": a.agent_type,
                    "tool_count": tool_count,
                    "is_public": a.is_public,
                    "category": a.category,
                    "tags": a.tags or [],
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
            )

        return {"agents": agent_list, "count": len(agent_list)}

    except Exception as e:
        logger.exception("Error listing agents")
        return {"error": str(e)}


async def platform_get_available_tools(runtime_context: Any = None) -> dict:
    """
    Return all tool categories available on this platform with their
    descriptions and integration requirements.
    """
    return {
        "tool_categories": PLATFORM_TOOL_CATALOG,
        "note": (
            "Tools with non-empty 'requires_oauth' need the user to connect a personal OAuth integration. "
            "Tools with non-empty 'requires_integration' need a platform API-key integration configured in "
            "Settings → Integrations. Use platform_check_integration(provider) to verify both types."
        ),
    }


async def platform_check_integration(provider: str, runtime_context: Any = None) -> dict:
    """
    Check whether a specific integration is available for use.

    Checks two sources in order:
    1. Personal OAuth token (UserOAuthToken) — for OAuth flows (github, slack, gmail, etc.)
    2. Platform/tenant API-key OAuth app (OAuthApp.api_token) — for API-key integrations (newsapi, etc.)

    Args:
        provider: Integration provider name (e.g. 'github', 'slack', 'gmail', 'newsapi')

    Returns:
        dict with keys: connected (bool), auth_method, provider_email, provider_username
    """
    if not runtime_context or not runtime_context.tenant_id:
        return {"connected": False, "auth_method": None, "provider_email": None, "provider_username": None}

    try:
        from sqlalchemy import func, or_

        from src.models.oauth_app import OAuthApp
        from src.models.user_oauth_token import UserOAuthToken

        db = runtime_context.db_session

        # 1. Check personal OAuth token
        if runtime_context.user_id:
            result = await db.execute(
                select(UserOAuthToken.provider_email, UserOAuthToken.provider_username)
                .join(OAuthApp, OAuthApp.id == UserOAuthToken.oauth_app_id)
                .where(UserOAuthToken.account_id == runtime_context.user_id)
                .where(func.lower(OAuthApp.provider) == provider.lower())
                .limit(1)
            )
            row = result.first()
            if row:
                return {
                    "connected": True,
                    "auth_method": "oauth",
                    "provider_email": row.provider_email,
                    "provider_username": row.provider_username,
                }

        # 2. Check tenant clone with company-wide OAuth token (access_token on OAuthApp row)
        result = await db.execute(
            select(OAuthApp)
            .where(
                OAuthApp.tenant_id == runtime_context.tenant_id,
                func.lower(OAuthApp.provider) == provider.lower(),
                OAuthApp.is_active.is_(True),
                OAuthApp.access_token.isnot(None),
            )
            .limit(1)
        )
        clone_app = result.scalar_one_or_none()
        if clone_app:
            return {
                "connected": True,
                "auth_method": "oauth",
                "provider_email": None,
                "provider_username": clone_app.app_name,
                "scope": "company",
            }

        # 3. Check platform/tenant API-key OAuth app
        result = await db.execute(
            select(OAuthApp)
            .where(
                or_(
                    OAuthApp.tenant_id == runtime_context.tenant_id,
                    OAuthApp.is_platform_app.is_(True),
                ),
                func.lower(OAuthApp.provider) == provider.lower(),
                OAuthApp.is_active.is_(True),
                OAuthApp.api_token.isnot(None),
            )
            .limit(1)
        )
        api_app = result.scalar_one_or_none()
        if api_app:
            return {
                "connected": True,
                "auth_method": "api_token",
                "provider_email": None,
                "provider_username": api_app.app_name,
            }

        # 4. Check GitHub App (tenant clone or platform app) — no stored token, credentials are App ID + Private Key
        result = await db.execute(
            select(OAuthApp)
            .where(
                or_(
                    OAuthApp.tenant_id == runtime_context.tenant_id,
                    OAuthApp.is_platform_app.is_(True),
                ),
                func.lower(OAuthApp.provider) == provider.lower(),
                OAuthApp.is_active.is_(True),
                OAuthApp.auth_method == "github_app",
                OAuthApp.client_id.isnot(None),
                OAuthApp.client_secret.isnot(None),
            )
            .limit(1)
        )
        github_app = result.scalar_one_or_none()
        if github_app:
            return {
                "connected": True,
                "auth_method": "github_app",
                "provider_email": None,
                "provider_username": github_app.app_name,
            }

        # Note: Slack can also be satisfied per-agent by a dedicated SlackBot (Socket Mode
        # bot/app token) instead of an OAuth app — see _resolve_slack_bot_id. That check is
        # intentionally NOT done here because this function has no agent context yet (it's
        # called before the target agent exists): a SlackBot is a credential dedicated to
        # one specific agent and must never be reported as "connected" for a different one.

        return {"connected": False, "auth_method": None, "provider_email": None, "provider_username": None}

    except Exception as e:
        logger.exception("Error checking integration")
        return {"error": str(e), "connected": False}


async def platform_create_agent(
    name: str,
    description: str,
    system_prompt: str,
    agent_type: str = "LLM",
    llm_provider: str = "openai",
    llm_model: str = "gpt-4o",
    api_key: str = "",
    tools_list: list[str] | None = None,
    category: str | None = None,
    tags: list[str] | None = None,
    image_llm_provider: str | None = None,
    image_llm_model: str | None = None,
    knowledge_base_ids: list[int] | None = None,
    runtime_context: Any = None,
) -> dict:
    """
    Create a new AI agent for the current tenant.

    IMPORTANT: Before calling this tool, you MUST output the marker:
    __ACTION__{"type":"create_agent","config":{...}}__ACTION__
    and wait for the user to confirm. Only call this tool after the user
    sends __CONFIRMED__ in their next message.

    Args:
        name: Agent name (will be slugified for storage)
        description: Short description of what the agent does
        system_prompt: The agent's system instructions
        agent_type: One of LLM, research, code (default: LLM)
        llm_provider: LLM provider name (openai, anthropic, google, groq, deepseek)
        llm_model: Model identifier (e.g. gpt-4o, claude-3-5-sonnet-20241022)
        api_key: Provider API key (stored encrypted)
        tools_list: List of tool category names to enable
        category: Agent category for organization
        tags: List of tags for discovery

    Returns:
        dict with success, agent_name, agent_id, message
    """
    if not runtime_context or not runtime_context.tenant_id:
        return {"success": False, "message": "No tenant context available"}

    try:
        from src.models.agent import Agent
        from src.models.agent_llm_config import AgentLLMConfig
        from src.services.agents.security import encrypt_value
        from src.services.billing.plan_restriction_service import PlanRestrictionError, PlanRestrictionService

        db = runtime_context.db_session
        tenant_id = runtime_context.tenant_id
        normalized_tools_list = normalize_tool_categories(tools_list)

        # Check plan limit before creating
        restriction_service = PlanRestrictionService(db)
        try:
            await restriction_service.enforce_agent_limit(tenant_id)
        except PlanRestrictionError as e:
            return {"success": False, "message": str(e)}

        # Slugify agent name
        import re

        agent_name_slug = re.sub(r"[^a-z0-9_-]", "_", name.lower().strip()).strip("_")
        if not agent_name_slug:
            agent_name_slug = "agent"

        # Check uniqueness within tenant
        existing = await db.execute(
            select(Agent).where(
                Agent.tenant_id == tenant_id,
                Agent.agent_name == agent_name_slug,
            )
        )
        if existing.scalar_one_or_none():
            # Append a short suffix
            agent_name_slug = f"{agent_name_slug}_{uuid4().hex[:4]}"

        # Inherit full LLM config from PE's per-tenant config when no api_key supplied
        llm_temperature: float = 0.7
        llm_max_tokens: int = 4096
        llm_top_p: float = 1.0
        llm_api_base: str | None = None
        llm_additional_params: dict = {}

        if not api_key:
            from uuid import UUID as _UUID

            from src.models.agent_llm_config import AgentLLMConfig as _LLMCfg

            _platform_tenant_id = _UUID("00000000-0000-0000-0000-000000000000")
            _pe_agent = (
                await db.execute(
                    select(Agent).where(
                        Agent.agent_name == "platform_engineer_agent",
                        Agent.tenant_id == _platform_tenant_id,
                    )
                )
            ).scalar_one_or_none()
            if _pe_agent:
                _pe_cfg = (
                    await db.execute(
                        select(_LLMCfg)
                        .where(
                            _LLMCfg.agent_id == _pe_agent.id,
                            _LLMCfg.tenant_id == tenant_id,
                        )
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if _pe_cfg and _pe_cfg.api_key:
                    llm_provider = _pe_cfg.provider
                    llm_model = _pe_cfg.model_name
                    encrypted_key = _pe_cfg.api_key  # already encrypted
                    llm_api_base = _pe_cfg.api_base
                    llm_temperature = _pe_cfg.temperature if _pe_cfg.temperature is not None else 0.7
                    llm_max_tokens = _pe_cfg.max_tokens if _pe_cfg.max_tokens is not None else 4096
                    llm_top_p = _pe_cfg.top_p if _pe_cfg.top_p is not None else 1.0
                    llm_additional_params = _pe_cfg.additional_params or {}
                    logger.info(f"platform_create_agent: inherited LLM config from PE ({llm_provider}/{llm_model})")
                else:
                    encrypted_key = ""
            else:
                encrypted_key = ""
        else:
            encrypted_key = encrypt_value(api_key)

        # Build llm_config
        llm_config_data = {
            "provider": llm_provider,
            "model_name": llm_model,
            "temperature": llm_temperature,
            "max_tokens": llm_max_tokens,
            "api_key": encrypted_key,
            "api_base": llm_api_base,
        }

        # Build tools_config from tools_list
        tools_config: list[dict] = []
        if normalized_tools_list:
            for tool_name in normalized_tools_list:
                tools_config.append({"name": tool_name, "enabled": True, "config": {}})

        agent = Agent(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_name=agent_name_slug,
            agent_type=agent_type,
            description=description,
            system_prompt=system_prompt,
            llm_config=llm_config_data,
            tools_config=tools_config,
            agent_metadata={},
            status="ACTIVE",
            is_public=False,
            category=category,
            tags=tags or [],
            execution_count=0,
            success_count=0,
        )
        db.add(agent)
        await db.flush()

        # Create default AgentLLMConfig row
        llm_cfg = AgentLLMConfig(
            id=uuid4(),
            agent_id=agent.id,
            tenant_id=tenant_id,
            name=f"Primary {llm_model}",
            provider=llm_provider,
            model_name=llm_model,
            api_key=encrypted_key,
            api_base=llm_api_base,
            temperature=llm_temperature,
            max_tokens=llm_max_tokens,
            top_p=llm_top_p,
            additional_params=llm_additional_params,
            is_default=True,
            display_order=0,
            enabled=True,
        )
        db.add(llm_cfg)
        await db.flush()

        image_config = resolve_image_generation_config(
            tools_list=normalized_tools_list,
            image_llm_provider=image_llm_provider,
            image_llm_model=image_llm_model,
            fallback_provider=llm_provider,
        )
        if image_config:
            await upsert_image_generation_llm_config(
                db_session=db,
                agent=agent,
                tenant_id=tenant_id,
                encrypted_api_key=encrypted_key,
                api_base=llm_api_base,
                additional_params=llm_additional_params,
                provider=image_config["provider"],
                model_name=image_config["model"],
            )

        # Enable AgentTool records from tool categories (direct pattern match, not capability groups)
        if normalized_tools_list:
            import fnmatch

            from src.models.agent_tool import AgentTool
            from src.services.agents.adk_tools import tool_registry

            available_tool_names = [t["name"] for t in tool_registry.list_tools()]
            # Map tool_name → (oauth_app_id, slack_bot_id) to avoid duplicate rows with conflicting app ids
            tool_to_creds: dict[str, tuple[Any, Any]] = {}

            for cat in normalized_tools_list:
                patterns = TOOL_CATEGORY_TO_PATTERNS.get(cat, [])
                cat_tools = [t for t in available_tool_names if any(fnmatch.fnmatch(t, p) for p in patterns)]
                if not cat_tools:
                    continue

                oauth_app_id = None
                slack_bot_id = None
                oauth_providers = (PLATFORM_TOOL_CATALOG.get(cat) or {}).get("requires_oauth") or []
                if oauth_providers:
                    oauth_app_id = await _resolve_oauth_app_id(
                        db=db,
                        provider=oauth_providers[0],
                        tenant_id=tenant_id,
                        user_id=runtime_context.user_id if runtime_context else None,
                    )
                    # An already-connected SlackBot is a valid, independent credential source
                    # for Slack tools — fall back to it when no Slack OAuth app is configured.
                    if oauth_app_id is None and oauth_providers[0] == "slack":
                        slack_bot_id = await _resolve_slack_bot_id(db, tenant_id, agent.id)

                for tool_name in cat_tools:
                    if tool_name not in tool_to_creds:
                        tool_to_creds[tool_name] = (oauth_app_id, slack_bot_id)

            for tool_name, (oauth_app_id, slack_bot_id) in tool_to_creds.items():
                db.add(
                    AgentTool(
                        agent_id=agent.id,
                        tool_name=tool_name,
                        config={},
                        enabled=True,
                        oauth_app_id=oauth_app_id,
                        slack_bot_id=slack_bot_id,
                    )
                )

        await db.commit()

        # Attach knowledge bases if provided
        kb_results: list[str] = []
        if knowledge_base_ids:
            from src.models.agent_knowledge_base import AgentKnowledgeBase
            from src.models.knowledge_base import KnowledgeBase

            for kb_id in knowledge_base_ids:
                try:
                    kb = (
                        await db.execute(
                            select(KnowledgeBase).where(
                                KnowledgeBase.id == kb_id,
                                KnowledgeBase.tenant_id == tenant_id,
                            )
                        )
                    ).scalar_one_or_none()
                    if kb:
                        db.add(
                            AgentKnowledgeBase(
                                agent_id=agent.id,
                                knowledge_base_id=kb_id,
                                retrieval_config={},
                                is_active=True,
                            )
                        )
                        kb_results.append(kb.name)
                        logger.info(
                            f"platform_create_agent: attached KB '{kb.name}' (id={kb_id}) to agent '{agent_name_slug}'"
                        )
                    else:
                        logger.warning(
                            f"platform_create_agent: KB id={kb_id} not found for tenant {tenant_id}, skipping"
                        )
                except Exception as kb_err:
                    logger.warning(f"platform_create_agent: failed to attach KB id={kb_id}: {kb_err}")
            if kb_results:
                await db.commit()

        attached_msg = f" Knowledge bases attached: {', '.join(kb_results)}." if kb_results else ""
        return {
            "success": True,
            "agent_name": agent_name_slug,
            "agent_id": str(agent.id),
            "message": f"Agent '{agent_name_slug}' created successfully.{attached_msg}",
            "knowledge_bases_attached": kb_results,
        }

    except Exception as e:
        logger.exception("Error creating agent")
        try:
            await runtime_context.db_session.rollback()
        except Exception:
            pass
        return {"success": False, "message": str(e)}


# Maps platform tool category names → capability IDs (kept for backwards compat, not used for tool expansion)
TOOL_CATEGORY_TO_CAPABILITY_ID: dict[str, str] = {
    "browser_tools": "browser-web",
    "scheduler_tools": "scheduling",
    "email_tools": "email",
    "gmail_tools": "email",
    "file_tools": "files-storage",
    "storage_tools": "files-storage",
    "google_drive_tools": "files-storage",
    "command_tools": "system-commands",
    "database_tools": "database-analytics",
    "elasticsearch_tools": "database-analytics",
    "data_analysis_tools": "database-analytics",
    "image_generation": "image-generation",
    "document_tools": "documents",
    "kb_ingest_tools": "knowledge-base",
    "github_tools": "code-github",
    "gitlab_tools": "code-github",
    "slack_tools": "communication",
    "jira_tools": "project-mgmt",
    "clickup_tools": "project-mgmt",
    "zoom_tools": "meetings-calendar",
    "google_calendar_tools": "meetings-calendar",
    "twitter_tools": "social-media",
    "linkedin_tools": "social-media",
    "youtube_tools": "social-media",
    "news_tools": "social-media",
    "spawn_agent_tool": "multi-agent",
    "newsletter_tools": "email",
}

# Direct per-category tool patterns — used for precise tool expansion.
# Each category maps only to the tools it specifically provides, preventing
# broad capability groups from enabling unrelated tools (e.g. news_tools
# should not enable twitter/linkedin/youtube).
TOOL_CATEGORY_TO_PATTERNS: dict[str, list[str]] = {
    "browser_tools": [
        "internal_browser_*",
        "internal_navigate_*",
        "internal_screenshot_*",
        "internal_extract_*",
        "internal_scrape_*",
        "internal_web_*",
        "web_search",
        "navigate_to_url",
        "extract_links",
        "extract_structured_data",
        "check_element_exists",
    ],
    "scheduler_tools": [
        "internal_create_scheduled_task",
        "internal_create_cron_scheduled_task",
        "internal_list_scheduled_tasks",
        "internal_delete_scheduled_task",
        "internal_toggle_scheduled_task",
        "internal_schedule_*",
    ],
    "email_tools": [
        "internal_send_email",
        "internal_send_bulk_emails",
        "internal_test_email_connection",
        "internal_email_*",
    ],
    "gmail_tools": ["internal_gmail_*", "internal_read_email*", "internal_search_email*"],
    "push_notification_tools": ["internal_send_push_notification"],
    "newsletter_tools": ["internal_render_newsletter"],
    "file_tools": [
        "internal_read_file",
        "internal_write_file",
        "internal_edit_file",
        "internal_search_files",
        "internal_get_file_info",
        "internal_move_file",
        "internal_create_directory",
        "internal_list_directory",
        "internal_directory_tree",
        "internal_glob",
        "internal_grep",
        "internal_read_*_file",
    ],
    "storage_tools": ["internal_s3_*", "internal_storage_*"],
    "google_drive_tools": [
        "internal_google_drive_*",
        "internal_google_docs_*",
        "internal_google_sheets_*",
    ],
    "command_tools": ["internal_run_command", "internal_execute_*", "internal_process_*"],
    "database_tools": [
        "internal_query_*",
        "internal_list_database_*",
        "internal_get_database_*",
        "query_databricks",
        "query_datadog_*",
        "query_docker_*",
    ],
    "elasticsearch_tools": ["internal_elasticsearch_*"],
    "data_analysis_tools": [
        "internal_generate_chart",
        "internal_chart_*",
        "analyze_*",
        "export_data_*",
        "generate_chart_from_*",
        "list_data_sources",
        "query_file_with_duckdb",
    ],
    "image_generation": ["internal_generate_image"],
    "document_tools": [
        "internal_generate_pdf",
        "internal_generate_powerpoint",
        "internal_*_pdf",
        "internal_*_pptx",
        "internal_*_docx",
    ],
    "kb_ingest_tools": ["internal_kb_*"],
    "news_tools": [
        "internal_hackernews_*",
        "internal_hn_*",
        "internal_news_*",
        "internal_fetch_rss_*",
    ],
    "openweather_tools": ["internal_get_weather_forecast", "internal_get_current_weather"],
    "openmeteo_tools": ["internal_get_openmeteo_forecast", "internal_get_openmeteo_current"],
    "micromobility_event_tools": [
        "internal_micromobility_analyze_event_impact",
        "internal_micromobility_get_network_health",
        "internal_micromobility_get_parking_compliance",
        "internal_micromobility_get_battery_degradation",
        "internal_micromobility_get_ranger_performance",
    ],
    "github_tools": [
        "internal_github_*",
        "internal_git_*",
        "internal_pr_review_*",
        "internal_create_github_*",
        "internal_deploy_*_github*",
        "internal_enable_github_*",
    ],
    "gitlab_tools": ["internal_gitlab_*"],
    "slack_tools": ["internal_slack_*", "internal_send_slack_*", "internal_search_slack_*"],
    "jira_tools": ["internal_*jira_*"],
    "clickup_tools": ["internal_*clickup_*", "internal_get_sprint_*"],
    "zoom_tools": ["internal_zoom_*"],
    "google_calendar_tools": ["internal_google_calendar_*"],
    "twitter_tools": ["internal_twitter_*"],
    "linkedin_tools": ["internal_linkedin_*"],
    "youtube_tools": ["internal_youtube_*"],
    "spawn_agent_tool": ["spawn_agent", "check_task", "list_background_tasks", "call_remote_agent"],
    "tutorial_tools": [
        "internal_fetch_repository_files",
        "internal_identify_abstractions",
        "internal_analyze_relationships",
        "internal_order_chapters",
        "internal_generate_tutorial_chapter",
        "internal_combine_tutorial",
    ],
    "contract_tools": ["internal_analyze_contract", "internal_generate_contract_report"],
    "followup_tools": [
        "internal_create_followup_item",
        "internal_list_pending_followups",
        "internal_send_followup_message",
        "internal_mark_followup_complete",
        "internal_get_followup_history",
        "internal_search_slack_mentions",
        "internal_update_followup_priority",
        "internal_escalate_followup",
    ],
    "zendesk_tools": [
        "internal_search_zendesk_tickets",
        "internal_get_zendesk_ticket",
        "internal_list_zendesk_tickets",
        "internal_create_zendesk_ticket",
        "internal_update_zendesk_ticket",
        "internal_add_zendesk_comment",
        "internal_get_zendesk_user",
    ],
    "zoho_crm_tools": [
        "internal_search_zoho_crm_records",
        "internal_get_zoho_crm_record",
        "internal_list_zoho_crm_records",
        "internal_create_zoho_crm_record",
        "internal_update_zoho_crm_record",
        "internal_add_zoho_crm_note",
    ],
    "events_tools": ["internal_get_predicthq_events", "internal_get_ticketmaster_events"],
    "mapbox_tools": ["internal_get_static_map", "internal_get_directions"],
    "blog_site_tools": [
        "internal_generate_blog_site",
        "internal_create_github_repository",
        "internal_deploy_blog_to_github",
        "internal_enable_github_pages",
    ],
    "role_tools": [
        "get_project_info",
        "get_project_context",
        "update_project_context",
        "escalate_to_human",
        "get_my_human_contact",
        "check_escalation_status",
        "get_project_agents",
        "get_my_role",
        "get_pending_escalations",
    ],
    "onepassword_tools": ["internal_1password_*"],
    "diagram_tools": ["internal_generate_diagram", "internal_generate_quick_diagram"],
    "infographic_tools": ["internal_generate_infographic", "internal_generate_slack_infographic"],
    "video_tools": ["internal_scrape_website_for_video", "internal_generate_video"],
    "recall_tools": [
        "internal_recall_send_bot",
        "internal_recall_get_bot_status",
        "internal_recall_list_bots",
        "internal_recall_get_transcript",
        "internal_recall_get_recording",
        "internal_recall_remove_bot",
        "internal_recall_summarize_meeting",
    ],
    "speckit_tools": ["speckit_specify", "speckit_plan", "speckit_tasks", "speckit_commit"],
}


async def platform_update_agent(
    agent_name: str,
    description: str | None = None,
    system_prompt: str | None = None,
    status: str | None = None,
    tools_list: list[str] | None = None,
    image_llm_provider: str | None = None,
    image_llm_model: str | None = None,
    runtime_context: Any = None,
) -> dict:
    """
    Update an existing agent's description, system prompt, status, or tools.

    Only updates fields that are explicitly provided (not None).
    Security: always scoped to the current tenant.

    Args:
        agent_name: The agent's name/slug to update
        description: New description (optional)
        system_prompt: New system prompt (optional)
        status: New status: ACTIVE or INACTIVE (optional)
        tools_list: List of tool category names to enable (optional).
                    Uses the same categories as platform_create_agent.
                    Adds tools without removing existing ones.

    Returns:
        dict with success and message
    """
    if not runtime_context or not runtime_context.tenant_id:
        return {"success": False, "message": "No tenant context available"}

    try:
        from src.models.agent import Agent

        db = runtime_context.db_session
        normalized_tools_list = normalize_tool_categories(tools_list)
        result = await db.execute(
            select(Agent).where(
                Agent.tenant_id == runtime_context.tenant_id,
                Agent.agent_name == agent_name,
            )
        )
        agent = result.scalar_one_or_none()
        if not agent:
            return {"success": False, "message": f"Agent '{agent_name}' not found"}

        if description is not None:
            agent.description = description
        if system_prompt is not None:
            agent.system_prompt = system_prompt
        if status is not None:
            if status.upper() not in ("ACTIVE", "INACTIVE"):
                return {"success": False, "message": "status must be ACTIVE or INACTIVE"}
            agent.status = status.upper()

        # Enable tools via AgentTool rows (direct pattern match, not capability groups)
        tools_enabled: list[str] = []
        if normalized_tools_list:
            import fnmatch

            from src.models.agent_tool import AgentTool
            from src.services.agents.adk_tools import tool_registry

            available_tool_names = [t["name"] for t in tool_registry.list_tools()]

            for cat in normalized_tools_list:
                patterns = TOOL_CATEGORY_TO_PATTERNS.get(cat, [])

                oauth_app_id = None
                slack_bot_id = None
                oauth_providers = (PLATFORM_TOOL_CATALOG.get(cat) or {}).get("requires_oauth") or []
                if oauth_providers:
                    oauth_app_id = await _resolve_oauth_app_id(
                        db=db,
                        provider=oauth_providers[0],
                        tenant_id=runtime_context.tenant_id,
                        user_id=runtime_context.user_id if runtime_context else None,
                    )
                    # An already-connected SlackBot is a valid, independent credential source
                    # for Slack tools — fall back to it when no Slack OAuth app is configured.
                    if oauth_app_id is None and oauth_providers[0] == "slack":
                        slack_bot_id = await _resolve_slack_bot_id(db, runtime_context.tenant_id, agent.id)

                for tool_name in available_tool_names:
                    if any(fnmatch.fnmatch(tool_name, p) for p in patterns):
                        existing = (
                            await db.execute(
                                select(AgentTool).where(
                                    AgentTool.agent_id == agent.id,
                                    AgentTool.tool_name == tool_name,
                                )
                            )
                        ).scalar_one_or_none()
                        if existing:
                            existing.enabled = True
                            if existing.oauth_app_id is None and oauth_app_id is not None:
                                existing.oauth_app_id = oauth_app_id
                            if existing.slack_bot_id is None and slack_bot_id is not None:
                                existing.slack_bot_id = slack_bot_id
                        else:
                            db.add(
                                AgentTool(
                                    agent_id=agent.id,
                                    tool_name=tool_name,
                                    config={},
                                    enabled=True,
                                    oauth_app_id=oauth_app_id,
                                    slack_bot_id=slack_bot_id,
                                )
                            )
                        tools_enabled.append(tool_name)

        # Ensure LLM config is set — inherit from PE's per-tenant AgentLLMConfig if missing
        from uuid import UUID as _UUID

        from src.models.agent_llm_config import AgentLLMConfig

        tenant_id = runtime_context.tenant_id
        platform_tenant_id = _UUID("00000000-0000-0000-0000-000000000000")

        # Check if this agent already has an LLM config for this tenant
        existing_llm = (
            await db.execute(
                select(AgentLLMConfig)
                .where(
                    AgentLLMConfig.agent_id == agent.id,
                    AgentLLMConfig.tenant_id == tenant_id,
                )
                .limit(1)
            )
        ).scalar_one_or_none()

        pe_cfg = None
        if not existing_llm or not existing_llm.api_key:
            # Look up PE agent and its per-tenant config
            from src.models.agent import Agent as _Agent

            pe_agent = (
                await db.execute(
                    select(_Agent).where(
                        _Agent.agent_name == "platform_engineer_agent",
                        _Agent.tenant_id == platform_tenant_id,
                    )
                )
            ).scalar_one_or_none()

            if pe_agent:
                pe_cfg = (
                    await db.execute(
                        select(AgentLLMConfig)
                        .where(
                            AgentLLMConfig.agent_id == pe_agent.id,
                            AgentLLMConfig.tenant_id == tenant_id,
                        )
                        .limit(1)
                    )
                ).scalar_one_or_none()

                if pe_cfg and pe_cfg.api_key:
                    if existing_llm:
                        existing_llm.api_key = pe_cfg.api_key
                        existing_llm.provider = pe_cfg.provider
                        existing_llm.model_name = pe_cfg.model_name
                    else:
                        db.add(
                            AgentLLMConfig(
                                id=uuid4(),
                                agent_id=agent.id,
                                tenant_id=tenant_id,
                                name="Default",
                                provider=pe_cfg.provider,
                                model_name=pe_cfg.model_name,
                                api_key=pe_cfg.api_key,
                                temperature=0.7,
                                max_tokens=4096,
                                top_p=1.0,
                                is_default=True,
                                display_order=0,
                                enabled=True,
                            )
                        )

        image_config = resolve_image_generation_config(
            tools_list=normalized_tools_list,
            image_llm_provider=image_llm_provider,
            image_llm_model=image_llm_model,
            fallback_provider=(existing_llm.provider if existing_llm else None)
            or (pe_cfg.provider if pe_cfg else None),
        )
        if image_config:
            await upsert_image_generation_llm_config(
                db_session=db,
                agent=agent,
                tenant_id=tenant_id,
                encrypted_api_key=(existing_llm.api_key if existing_llm else None)
                or (pe_cfg.api_key if pe_cfg else ""),
                api_base=(existing_llm.api_base if existing_llm else None) or (pe_cfg.api_base if pe_cfg else None),
                additional_params=(existing_llm.additional_params if existing_llm else None)
                or (pe_cfg.additional_params if pe_cfg else None),
                provider=image_config["provider"],
                model_name=image_config["model"],
            )

        await db.commit()

        msg = f"Agent '{agent_name}' updated successfully."
        if tools_enabled:
            msg += f" Enabled {len(tools_enabled)} tools."
        return {"success": True, "message": msg, "tools_enabled": tools_enabled}

    except Exception as e:
        logger.exception("Error updating agent")
        return {"success": False, "message": str(e)}


async def platform_list_database_connections(
    connection_type: str | None = None,
    agent_name: str | None = None,
    runtime_context: Any = None,
) -> dict:
    """
    List active database connections for the current tenant.

    Optionally filter by database type and/or annotate which connections are
    already attached to a target agent.
    """
    if not runtime_context or not runtime_context.tenant_id:
        return {"success": False, "message": "No tenant context available"}

    try:
        from src.models.database_connection import DatabaseConnection

        db = runtime_context.db_session
        tenant_id = runtime_context.tenant_id
        normalized_type = connection_type.strip().upper() if connection_type else None

        stmt = select(DatabaseConnection).where(
            DatabaseConnection.tenant_id == tenant_id,
            DatabaseConnection.status == "active",
        )
        if normalized_type:
            stmt = stmt.where(DatabaseConnection.database_type == normalized_type)

        result = await db.execute(stmt)
        connections = list(result.scalars().all())

        attached_ids: set[str] = set()
        if agent_name:
            agent = await _resolve_target_agent(db, agent_name, tenant_id)
            if not agent:
                return {"success": False, "message": f"Agent '{agent_name}' not found"}
            attached_ids = set((agent.agent_metadata or {}).get("allowed_database_connections", []))

        formatted_connections = [
            {
                "id": str(conn.id),
                "name": conn.name,
                "type": conn.database_type,
                "host": conn.host,
                "port": conn.port,
                "database": conn.database_name,
                "database_path": conn.database_path,
                "attached": str(conn.id) in attached_ids,
            }
            for conn in connections
        ]

        return {
            "success": True,
            "connections": formatted_connections,
            "count": len(formatted_connections),
            "connection_type": normalized_type,
            "agent_name": agent_name,
        }
    except Exception as e:
        logger.exception("Error listing database connections for platform engineer")
        return {"success": False, "message": str(e)}


async def platform_attach_database_connections(
    agent_name: str,
    connection_ids: list[str] | None = None,
    connection_type: str | None = None,
    replace: bool = False,
    runtime_context: Any = None,
) -> dict:
    """
    Attach one or more active tenant database connections to an agent.

    Connections can be selected either explicitly by UUID or implicitly by
    database type (e.g. ELASTICSEARCH).
    """
    if not runtime_context or not runtime_context.tenant_id:
        return {"success": False, "message": "No tenant context available"}

    if not connection_ids and not connection_type:
        return {"success": False, "message": "Provide connection_ids or connection_type"}

    try:
        from uuid import UUID

        from sqlalchemy.orm.attributes import flag_modified

        from src.models.database_connection import DatabaseConnection
        from src.services.cache import get_agent_cache

        db = runtime_context.db_session
        tenant_id = runtime_context.tenant_id

        agent = await _resolve_target_agent(db, agent_name, tenant_id)
        if not agent:
            return {"success": False, "message": f"Agent '{agent_name}' not found"}

        normalized_type = connection_type.strip().upper() if connection_type else None
        stmt = select(DatabaseConnection).where(
            DatabaseConnection.tenant_id == tenant_id,
            DatabaseConnection.status == "active",
        )

        if connection_ids:
            try:
                parsed_ids = [UUID(cid) for cid in connection_ids]
            except ValueError:
                return {"success": False, "message": "One or more connection_ids are invalid UUIDs"}
            stmt = stmt.where(DatabaseConnection.id.in_(parsed_ids))
        elif normalized_type:
            stmt = stmt.where(DatabaseConnection.database_type == normalized_type)

        result = await db.execute(stmt)
        connections = list(result.scalars().all())

        if not connections:
            if normalized_type:
                return {
                    "success": False,
                    "message": f"No active {normalized_type} database connections found for this tenant",
                }
            return {"success": False, "message": "No matching active database connections found"}

        if connection_ids and len(connections) != len(connection_ids):
            return {"success": False, "message": "One or more connection_ids are invalid for this tenant"}

        current_ids = set((agent.agent_metadata or {}).get("allowed_database_connections", []))
        target_ids = {str(conn.id) for conn in connections}
        updated_ids = target_ids if replace else current_ids | target_ids

        metadata = dict(agent.agent_metadata or {})
        metadata["allowed_database_connections"] = sorted(updated_ids)
        agent.agent_metadata = metadata
        flag_modified(agent, "agent_metadata")
        await db.commit()

        cache = get_agent_cache()
        await cache.invalidate_agent(
            slug=agent.slug or agent.agent_name,
            agent_id=str(agent.id),
            tenant_id=str(tenant_id),
        )

        return {
            "success": True,
            "agent_name": agent.agent_name,
            "attached_connection_ids": sorted(target_ids),
            "attached_connections": [
                {
                    "id": str(conn.id),
                    "name": conn.name,
                    "type": conn.database_type,
                }
                for conn in connections
            ],
            "total_attached_count": len(updated_ids),
            "replace": replace,
        }
    except Exception as e:
        logger.exception("Error attaching database connections to agent")
        try:
            await runtime_context.db_session.rollback()
        except Exception:
            pass
        return {"success": False, "message": str(e)}


async def platform_list_knowledge_bases(
    status: str | None = None,
    agent_name: str | None = None,
    runtime_context: Any = None,
) -> dict:
    """List tenant knowledge bases and optionally annotate which are attached to an agent."""
    if not runtime_context or not runtime_context.tenant_id:
        return {"success": False, "message": "No tenant context available"}

    try:
        from src.models.agent_knowledge_base import AgentKnowledgeBase
        from src.models.knowledge_base import KnowledgeBase

        db = runtime_context.db_session
        tenant_id = runtime_context.tenant_id
        _VALID_KB_STATUSES = {"ACTIVE", "INACTIVE", "ERROR"}
        _KB_STATUS_ALIASES = {"READY": "ACTIVE", "ENABLED": "ACTIVE", "DISABLED": "INACTIVE"}
        normalized_status = status.strip().upper() if status else None
        if normalized_status:
            normalized_status = _KB_STATUS_ALIASES.get(normalized_status, normalized_status)
            if normalized_status not in _VALID_KB_STATUSES:
                normalized_status = None  # ignore unknown values rather than crashing

        stmt = select(KnowledgeBase).where(KnowledgeBase.tenant_id == tenant_id)
        if normalized_status:
            stmt = stmt.where(KnowledgeBase.status == normalized_status)

        result = await db.execute(stmt)
        knowledge_bases = list(result.scalars().all())

        attached_ids: set[int] = set()
        if agent_name:
            agent = await _resolve_target_agent(db, agent_name, tenant_id)
            if not agent:
                return {"success": False, "message": f"Agent '{agent_name}' not found"}

            kb_result = await db.execute(
                select(AgentKnowledgeBase.knowledge_base_id).where(
                    AgentKnowledgeBase.agent_id == agent.id,
                    AgentKnowledgeBase.is_active.is_(True),
                )
            )
            attached_ids = set(kb_result.scalars().all())

        return {
            "success": True,
            "knowledge_bases": [
                {
                    "id": kb.id,
                    "name": kb.name,
                    "description": kb.description,
                    "status": str(kb.status),
                    "vector_db_provider": str(kb.vector_db_provider),
                    "embedding_provider": str(kb.embedding_provider),
                    "document_count": kb.total_documents,
                    "total_chunks": kb.total_chunks,
                    "attached": kb.id in attached_ids,
                }
                for kb in knowledge_bases
            ],
            "count": len(knowledge_bases),
            "agent_name": agent_name,
        }
    except Exception as e:
        logger.exception("Error listing knowledge bases for platform engineer")
        return {"success": False, "message": str(e)}


async def platform_create_knowledge_base(
    name: str,
    description: str | None = None,
    embedding_provider: str = "SENTENCE_TRANSFORMERS",
    embedding_model: str = "all-MiniLM-L6-v2",
    embedding_config: dict[str, Any] | None = None,
    vector_db_provider: str = "QDRANT",
    vector_db_config: dict[str, Any] | None = None,
    chunking_strategy: str = "SEMANTIC",
    chunk_size: int = 1500,
    chunk_overlap: int = 150,
    min_chunk_size: int = 500,
    max_chunk_size: int = 3000,
    chunking_config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict:
    """Create a knowledge base for the current tenant."""
    if not runtime_context or not runtime_context.tenant_id:
        return {"success": False, "message": "No tenant context available"}

    try:
        from src.models.knowledge_base import (
            ChunkingStrategy,
            EmbeddingProvider,
            KnowledgeBase,
            KnowledgeBaseStatus,
            VectorDBProvider,
        )

        db = runtime_context.db_session

        try:
            embedding_provider_enum = EmbeddingProvider(embedding_provider.strip().upper())
        except ValueError:
            return {"success": False, "message": f"Invalid embedding provider: {embedding_provider}"}

        try:
            vector_db_provider_enum = VectorDBProvider(vector_db_provider.strip().upper())
        except ValueError:
            return {"success": False, "message": f"Invalid vector DB provider: {vector_db_provider}"}

        try:
            chunking_strategy_enum = ChunkingStrategy(chunking_strategy.strip().upper())
        except ValueError:
            return {"success": False, "message": f"Invalid chunking strategy: {chunking_strategy}"}

        kb = KnowledgeBase(
            name=name,
            description=description,
            tenant_id=runtime_context.tenant_id,
            embedding_provider=embedding_provider_enum,
            embedding_model=embedding_model,
            vector_db_provider=vector_db_provider_enum,
            chunking_strategy=chunking_strategy_enum,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            min_chunk_size=min_chunk_size,
            max_chunk_size=max_chunk_size,
            chunking_config=chunking_config or {},
            status=KnowledgeBaseStatus.ACTIVE,
        )
        kb.set_embedding_config_encrypted(embedding_config or {})
        kb.set_vector_db_config_encrypted(vector_db_config or {})

        db.add(kb)
        await db.commit()
        await db.refresh(kb)

        return {
            "success": True,
            "knowledge_base_id": kb.id,
            "name": kb.name,
            "status": str(kb.status),
            "vector_db_provider": str(kb.vector_db_provider),
            "embedding_provider": str(kb.embedding_provider),
            "message": f"Knowledge base '{kb.name}' created successfully.",
        }
    except Exception as e:
        logger.exception("Error creating knowledge base")
        try:
            await runtime_context.db_session.rollback()
        except Exception:
            pass
        return {"success": False, "message": str(e)}


async def platform_attach_knowledge_base(
    agent_name: str,
    knowledge_base_id: int,
    retrieval_config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict:
    """Attach a knowledge base to an agent."""
    if not runtime_context or not runtime_context.tenant_id:
        return {"success": False, "message": "No tenant context available"}

    try:
        from src.models.agent_knowledge_base import AgentKnowledgeBase
        from src.models.knowledge_base import KnowledgeBase

        db = runtime_context.db_session
        tenant_id = runtime_context.tenant_id

        agent = await _resolve_target_agent(db, agent_name, tenant_id)
        if not agent:
            return {"success": False, "message": f"Agent '{agent_name}' not found"}

        kb = (
            await db.execute(
                select(KnowledgeBase).where(
                    KnowledgeBase.id == knowledge_base_id,
                    KnowledgeBase.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if not kb:
            return {"success": False, "message": f"Knowledge base '{knowledge_base_id}' not found"}

        existing = (
            await db.execute(
                select(AgentKnowledgeBase).where(
                    AgentKnowledgeBase.agent_id == agent.id,
                    AgentKnowledgeBase.knowledge_base_id == knowledge_base_id,
                )
            )
        ).scalar_one_or_none()

        if existing:
            existing.retrieval_config = retrieval_config or {}
            existing.is_active = True
        else:
            db.add(
                AgentKnowledgeBase(
                    agent_id=agent.id,
                    knowledge_base_id=knowledge_base_id,
                    retrieval_config=retrieval_config or {},
                    is_active=True,
                )
            )

        await db.commit()
        return {
            "success": True,
            "agent_name": agent.agent_name,
            "knowledge_base_id": kb.id,
            "knowledge_base_name": kb.name,
            "message": f"Knowledge base '{kb.name}' attached to agent '{agent.agent_name}'.",
        }
    except Exception as e:
        logger.exception("Error attaching knowledge base to agent")
        try:
            await runtime_context.db_session.rollback()
        except Exception:
            pass
        return {"success": False, "message": str(e)}


async def platform_list_mcp_servers(
    status: str | None = None,
    agent_name: str | None = None,
    runtime_context: Any = None,
) -> dict:
    """List tenant MCP servers and optionally annotate which are attached to an agent."""
    if not runtime_context or not runtime_context.tenant_id:
        return {"success": False, "message": "No tenant context available"}

    try:
        from src.models.agent_mcp_server import AgentMCPServer
        from src.models.mcp_server import MCPServer

        db = runtime_context.db_session
        tenant_id = runtime_context.tenant_id
        normalized_status = status.strip().upper() if status else None

        stmt = select(MCPServer).where(MCPServer.tenant_id == tenant_id)
        if normalized_status:
            stmt = stmt.where(MCPServer.status == normalized_status)

        result = await db.execute(stmt)
        servers = list(result.scalars().all())

        attached_ids: set[str] = set()
        if agent_name:
            agent = await _resolve_target_agent(db, agent_name, tenant_id)
            if not agent:
                return {"success": False, "message": f"Agent '{agent_name}' not found"}
            mcp_result = await db.execute(
                select(AgentMCPServer.mcp_server_id).where(
                    AgentMCPServer.agent_id == agent.id,
                    AgentMCPServer.is_active.is_(True),
                )
            )
            attached_ids = {str(mcp_id) for mcp_id in mcp_result.scalars().all()}

        return {
            "success": True,
            "mcp_servers": [
                {
                    "id": str(server.id),
                    "name": server.name,
                    "description": server.description,
                    "transport_type": server.transport_type,
                    "server_type": server.server_type,
                    "auth_type": server.auth_type,
                    "status": server.status,
                    "url": server.url,
                    "attached": str(server.id) in attached_ids,
                }
                for server in servers
            ],
            "count": len(servers),
            "agent_name": agent_name,
        }
    except Exception as e:
        logger.exception("Error listing MCP servers for platform engineer")
        return {"success": False, "message": str(e)}


async def platform_create_mcp_server(
    name: str,
    description: str,
    transport_type: str = "http",
    url: str | None = None,
    command: str | None = None,
    args: list[str] | None = None,
    env_vars: dict[str, Any] | None = None,
    server_type: str = "http",
    auth_type: str = "none",
    auth_config: dict[str, Any] | None = None,
    headers: dict[str, Any] | None = None,
    capabilities: dict[str, Any] | None = None,
    server_metadata: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict:
    """Create an MCP server for the current tenant."""
    if not runtime_context or not runtime_context.tenant_id:
        return {"success": False, "message": "No tenant context available"}

    try:
        from src.models.mcp_server import MCPServer

        db = runtime_context.db_session
        normalized_transport = transport_type.strip().lower()

        if normalized_transport not in {"http", "stdio"}:
            return {"success": False, "message": "Transport type must be 'http' or 'stdio'"}
        if normalized_transport == "http" and not url:
            return {"success": False, "message": "URL is required for HTTP transport"}
        if normalized_transport == "stdio" and not command:
            return {"success": False, "message": "Command is required for stdio transport"}

        server = MCPServer(
            tenant_id=runtime_context.tenant_id,
            name=name,
            url=url,
            description=description,
            transport_type=normalized_transport,
            command=command,
            args=args,
            env_vars=env_vars,
            server_type=server_type,
            auth_type=auth_type,
            auth_config=auth_config,
            headers=headers,
            capabilities=capabilities,
            server_metadata=server_metadata or {},
            status="ACTIVE",
        )

        db.add(server)
        await db.commit()
        await db.refresh(server)

        return {
            "success": True,
            "mcp_server_id": str(server.id),
            "name": server.name,
            "transport_type": server.transport_type,
            "status": server.status,
            "message": f"MCP server '{server.name}' created successfully.",
        }
    except Exception as e:
        logger.exception("Error creating MCP server")
        try:
            await runtime_context.db_session.rollback()
        except Exception:
            pass
        return {"success": False, "message": str(e)}


async def platform_attach_mcp_server(
    agent_name: str,
    mcp_server_id: str,
    mcp_config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict:
    """Attach an MCP server to an agent."""
    if not runtime_context or not runtime_context.tenant_id:
        return {"success": False, "message": "No tenant context available"}

    try:
        from uuid import UUID

        from src.models.agent_mcp_server import AgentMCPServer
        from src.models.mcp_server import MCPServer

        db = runtime_context.db_session
        tenant_id = runtime_context.tenant_id

        agent = await _resolve_target_agent(db, agent_name, tenant_id)
        if not agent:
            return {"success": False, "message": f"Agent '{agent_name}' not found"}

        try:
            mcp_uuid = UUID(mcp_server_id)
        except ValueError:
            return {"success": False, "message": "Invalid MCP server ID format"}

        server = (
            await db.execute(
                select(MCPServer).where(
                    MCPServer.id == mcp_uuid,
                    MCPServer.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if not server:
            return {"success": False, "message": f"MCP server '{mcp_server_id}' not found"}

        existing = (
            await db.execute(
                select(AgentMCPServer).where(
                    AgentMCPServer.agent_id == agent.id,
                    AgentMCPServer.mcp_server_id == mcp_uuid,
                )
            )
        ).scalar_one_or_none()

        if existing:
            existing.mcp_config = mcp_config or {}
            existing.is_active = True
        else:
            db.add(
                AgentMCPServer(
                    agent_id=agent.id,
                    mcp_server_id=mcp_uuid,
                    mcp_config=mcp_config or {},
                    is_active=True,
                )
            )

        await db.commit()
        return {
            "success": True,
            "agent_name": agent.agent_name,
            "mcp_server_id": str(server.id),
            "mcp_server_name": server.name,
            "message": f"MCP server '{server.name}' attached to agent '{agent.agent_name}'.",
        }
    except Exception as e:
        logger.exception("Error attaching MCP server to agent")
        try:
            await runtime_context.db_session.rollback()
        except Exception:
            pass
        return {"success": False, "message": str(e)}


async def platform_get_agent_autonomous(
    agent_name: str,
    runtime_context: Any = None,
) -> dict:
    """Return the current autonomous configuration for an agent."""
    if not runtime_context or not runtime_context.tenant_id:
        return {"success": False, "message": "No tenant context available"}

    try:
        from src.models.scheduled_task import ScheduledTask

        db = runtime_context.db_session
        tenant_id = runtime_context.tenant_id
        agent = await _resolve_target_agent(db, agent_name, tenant_id)
        if not agent:
            return {"success": False, "message": f"Agent '{agent_name}' not found"}

        task = (
            await db.execute(
                select(ScheduledTask).where(
                    ScheduledTask.config["agent_id"].as_string() == str(agent.id),
                    ScheduledTask.task_type == "autonomous_agent",
                    ScheduledTask.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()

        if not task:
            return {
                "success": True,
                "agent_name": agent.agent_name,
                "enabled": bool(agent.autonomous_enabled),
                "configured": False,
            }

        cfg = task.config or {}
        schedule = task.cron_expression or task.interval_seconds
        return {
            "success": True,
            "agent_name": agent.agent_name,
            "enabled": bool(agent.autonomous_enabled),
            "configured": True,
            "task_id": str(task.id),
            "goal": cfg.get("goal"),
            "schedule": schedule,
            "schedule_type": task.schedule_type,
            "max_steps": cfg.get("max_steps", 20),
            "is_active": task.is_active,
            "require_approval": cfg.get("require_approval", False),
            "approval_mode": cfg.get("approval_mode", "smart"),
            "approval_channel": cfg.get("approval_channel"),
        }
    except Exception as e:
        logger.exception("Error getting autonomous config for agent")
        return {"success": False, "message": str(e)}


async def platform_set_agent_autonomous(
    agent_name: str,
    goal: str,
    schedule: str,
    max_steps: int = 20,
    is_active: bool = True,
    require_approval: bool = False,
    approval_mode: str = "smart",
    require_approval_tools: list[str] | None = None,
    approval_channel: str | None = None,
    approval_channel_config: dict[str, Any] | None = None,
    approval_timeout_minutes: int = 60,
    runtime_context: Any = None,
) -> dict:
    """Create or update an agent's autonomous configuration."""
    if not runtime_context or not runtime_context.tenant_id:
        return {"success": False, "message": "No tenant context available"}
    if not runtime_context.user_id:
        return {"success": False, "message": "No user context available"}

    try:
        import uuid

        from src.models.scheduled_task import ScheduledTask
        from src.schemas.autonomous_agent import parse_schedule

        db = runtime_context.db_session
        tenant_id = runtime_context.tenant_id
        agent = await _resolve_target_agent(db, agent_name, tenant_id)
        if not agent:
            return {"success": False, "message": f"Agent '{agent_name}' not found"}

        sched = parse_schedule(schedule)
        task = (
            await db.execute(
                select(ScheduledTask).where(
                    ScheduledTask.config["agent_id"].as_string() == str(agent.id),
                    ScheduledTask.task_type == "autonomous_agent",
                    ScheduledTask.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()

        cfg = {
            "agent_id": str(agent.id),
            "goal": goal,
            "max_steps": max_steps,
            "autonomous_conversation_id": (task.config or {}).get("autonomous_conversation_id") if task else None,
            "require_approval": require_approval,
            "approval_mode": approval_mode,
            "require_approval_tools": require_approval_tools or [],
            "approval_channel": approval_channel,
            "approval_channel_config": approval_channel_config or {},
            "approval_timeout_minutes": approval_timeout_minutes,
        }

        if task:
            task.description = goal[:255]
            task.schedule_type = sched["schedule_type"]
            task.cron_expression = sched.get("cron_expression")
            task.interval_seconds = sched.get("interval_seconds")
            task.is_active = is_active
            task.config = cfg
        else:
            task = ScheduledTask(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                name=f"[Autonomous] {agent.agent_name}",
                description=goal[:255],
                task_type="autonomous_agent",
                schedule_type=sched["schedule_type"],
                cron_expression=sched.get("cron_expression"),
                interval_seconds=sched.get("interval_seconds"),
                is_active=is_active,
                created_by=runtime_context.user_id,
                config=cfg,
            )
            db.add(task)

        agent.autonomous_enabled = is_active
        await db.commit()
        await db.refresh(task)

        return {
            "success": True,
            "agent_name": agent.agent_name,
            "task_id": str(task.id),
            "goal": goal,
            "schedule": task.cron_expression or task.interval_seconds,
            "schedule_type": task.schedule_type,
            "max_steps": max_steps,
            "is_active": task.is_active,
            "enabled": bool(agent.autonomous_enabled),
            "message": f"Autonomous mode configured for agent '{agent.agent_name}'.",
        }
    except Exception as e:
        logger.exception("Error setting autonomous config for agent")
        try:
            await runtime_context.db_session.rollback()
        except Exception:
            pass
        return {"success": False, "message": str(e)}


async def platform_disable_agent_autonomous(
    agent_name: str,
    delete_task: bool = True,
    runtime_context: Any = None,
) -> dict:
    """Disable an agent's autonomous configuration."""
    if not runtime_context or not runtime_context.tenant_id:
        return {"success": False, "message": "No tenant context available"}

    try:
        from src.models.scheduled_task import ScheduledTask

        db = runtime_context.db_session
        tenant_id = runtime_context.tenant_id
        agent = await _resolve_target_agent(db, agent_name, tenant_id)
        if not agent:
            return {"success": False, "message": f"Agent '{agent_name}' not found"}

        task = (
            await db.execute(
                select(ScheduledTask).where(
                    ScheduledTask.config["agent_id"].as_string() == str(agent.id),
                    ScheduledTask.task_type == "autonomous_agent",
                    ScheduledTask.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()

        if task:
            if delete_task:
                await db.delete(task)
            else:
                task.is_active = False

        agent.autonomous_enabled = False
        await db.commit()

        action = "deleted" if task and delete_task else "disabled"
        return {
            "success": True,
            "agent_name": agent.agent_name,
            "enabled": False,
            "message": f"Autonomous mode {action} for agent '{agent.agent_name}'.",
        }
    except Exception as e:
        logger.exception("Error disabling autonomous config for agent")
        try:
            await runtime_context.db_session.rollback()
        except Exception:
            pass
        return {"success": False, "message": str(e)}


# ---------------------------------------------------------------------------
# Sub-agent wiring
# ---------------------------------------------------------------------------


async def platform_list_sub_agents(
    agent_name: str,
    runtime_context: Any = None,
) -> dict:
    """List sub-agents registered to a parent agent."""
    if not runtime_context or not runtime_context.tenant_id:
        return {"success": False, "message": "No tenant context available"}

    try:
        from src.models.agent_sub_agent import AgentSubAgent

        db = runtime_context.db_session
        tenant_id = runtime_context.tenant_id

        parent = await _resolve_target_agent(db, agent_name, tenant_id)
        if not parent:
            return {"success": False, "message": f"Agent '{agent_name}' not found"}

        from sqlalchemy.orm import selectinload

        result = await db.execute(
            select(AgentSubAgent)
            .options(selectinload(AgentSubAgent.sub_agent))
            .where(AgentSubAgent.parent_agent_id == parent.id)
            .order_by(AgentSubAgent.execution_order)
        )
        rels = result.scalars().all()

        sub_agents = []
        for rel in rels:
            child = rel.sub_agent
            if child:
                sub_agents.append(
                    {
                        "relationship_id": str(rel.id),
                        "sub_agent_id": str(child.id),
                        "sub_agent_name": child.agent_name,
                        "description": child.description,
                        "execution_order": rel.execution_order,
                        "is_active": rel.is_active,
                    }
                )

        return {
            "success": True,
            "parent_agent": agent_name,
            "sub_agents": sub_agents,
            "count": len(sub_agents),
        }
    except Exception as e:
        logger.exception("Error listing sub-agents")
        return {"success": False, "message": str(e)}


async def platform_add_sub_agent(
    parent_agent_name: str,
    sub_agent_name: str,
    execution_order: int = 0,
    runtime_context: Any = None,
) -> dict:
    """
    Wire a sub-agent to a parent agent.

    After this call, when the parent agent uses spawn_agent(agent_name=sub_agent_name),
    the routing layer will delegate to the registered sub-agent instead of self-cloning.
    """
    if not runtime_context or not runtime_context.tenant_id:
        return {"success": False, "message": "No tenant context available"}

    try:
        from src.models.agent_sub_agent import AgentSubAgent

        db = runtime_context.db_session
        tenant_id = runtime_context.tenant_id

        parent = await _resolve_target_agent(db, parent_agent_name, tenant_id)
        if not parent:
            return {"success": False, "message": f"Parent agent '{parent_agent_name}' not found"}

        child = await _resolve_target_agent(db, sub_agent_name, tenant_id)
        if not child:
            return {"success": False, "message": f"Sub-agent '{sub_agent_name}' not found"}

        if parent.id == child.id:
            return {"success": False, "message": "An agent cannot be its own sub-agent"}

        existing = (
            await db.execute(
                select(AgentSubAgent).where(
                    AgentSubAgent.parent_agent_id == parent.id,
                    AgentSubAgent.sub_agent_id == child.id,
                )
            )
        ).scalar_one_or_none()

        if existing:
            # Reactivate if it was soft-deleted, update execution_order
            existing.is_active = True
            existing.execution_order = execution_order
            await db.commit()
            return {
                "success": True,
                "message": f"Sub-agent '{child.agent_name}' is already linked to '{parent.agent_name}' (reactivated).",
                "relationship_id": str(existing.id),
                "parent_agent": parent.agent_name,
                "sub_agent": child.agent_name,
            }

        rel = AgentSubAgent(
            parent_agent_id=parent.id,
            sub_agent_id=child.id,
            execution_order=execution_order,
            is_active=True,
        )
        db.add(rel)
        await db.commit()
        await db.refresh(rel)

        return {
            "success": True,
            "message": f"Sub-agent '{child.agent_name}' wired to '{parent.agent_name}'.",
            "relationship_id": str(rel.id),
            "parent_agent": parent.agent_name,
            "sub_agent": child.agent_name,
            "execution_order": rel.execution_order,
        }
    except Exception as e:
        logger.exception("Error adding sub-agent")
        try:
            await runtime_context.db_session.rollback()
        except Exception:
            pass
        return {"success": False, "message": str(e)}


async def platform_remove_sub_agent(
    parent_agent_name: str,
    sub_agent_name: str,
    runtime_context: Any = None,
) -> dict:
    """Remove (unlink) a sub-agent from a parent agent."""
    if not runtime_context or not runtime_context.tenant_id:
        return {"success": False, "message": "No tenant context available"}

    try:
        from src.models.agent_sub_agent import AgentSubAgent

        db = runtime_context.db_session
        tenant_id = runtime_context.tenant_id

        parent = await _resolve_target_agent(db, parent_agent_name, tenant_id)
        if not parent:
            return {"success": False, "message": f"Parent agent '{parent_agent_name}' not found"}

        child = await _resolve_target_agent(db, sub_agent_name, tenant_id)
        if not child:
            return {"success": False, "message": f"Sub-agent '{sub_agent_name}' not found"}

        rel = (
            await db.execute(
                select(AgentSubAgent).where(
                    AgentSubAgent.parent_agent_id == parent.id,
                    AgentSubAgent.sub_agent_id == child.id,
                )
            )
        ).scalar_one_or_none()

        if not rel:
            return {
                "success": False,
                "message": f"No link found between '{parent.agent_name}' and '{child.agent_name}'",
            }

        await db.delete(rel)
        await db.commit()

        return {
            "success": True,
            "message": f"Sub-agent '{child.agent_name}' removed from '{parent.agent_name}'.",
            "parent_agent": parent.agent_name,
            "sub_agent": child.agent_name,
        }
    except Exception as e:
        logger.exception("Error removing sub-agent")
        try:
            await runtime_context.db_session.rollback()
        except Exception:
            pass
        return {"success": False, "message": str(e)}


# ---------------------------------------------------------------------------
# Channel management helpers
# ---------------------------------------------------------------------------


async def _scrub_tokens_from_conversation(
    db: Any,
    conversation_id: str | None,
    sensitive_values: list[str],
) -> None:
    """Redact sensitive token values from the last 20 messages of a conversation."""
    from src.models.message import Message

    if not conversation_id:
        return
    sensitive_values = [v for v in sensitive_values if v]
    if not sensitive_values:
        return

    try:
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(20)
        )
        messages = result.scalars().all()

        for msg in messages:
            original = msg.content or ""
            scrubbed = original
            for val in sensitive_values:
                if val in scrubbed:
                    scrubbed = scrubbed.replace(val, "[REDACTED]")
            if scrubbed != original:
                msg.content = scrubbed

        await db.commit()
    except Exception:
        logger.exception("Error scrubbing tokens from conversation")


async def _resolve_oauth_app_id(db: Any, provider: str, tenant_id: Any, user_id: Any = None) -> Any | None:
    """
    Resolve the OAuthApp.id for a given provider.

    Priority:
    1. User's personal UserOAuthToken linked to an OAuthApp for this provider
    2. Platform/tenant OAuthApp (is_platform_app=True or tenant-owned) for this provider
    """
    from sqlalchemy import func

    from src.models.oauth_app import OAuthApp
    from src.models.user_oauth_token import UserOAuthToken

    if user_id:
        result = await db.execute(
            select(OAuthApp.id)
            .join(UserOAuthToken, UserOAuthToken.oauth_app_id == OAuthApp.id)
            .where(
                UserOAuthToken.account_id == user_id,
                func.lower(OAuthApp.provider) == provider.lower(),
                OAuthApp.is_active.is_(True),
            )
            .limit(1)
        )
        app_id = result.scalar_one_or_none()
        if app_id:
            return app_id

    # Only tenant-owned apps — platform apps are credential-less templates, never assigned to tools
    result = await db.execute(
        select(OAuthApp.id)
        .where(
            OAuthApp.tenant_id == tenant_id,
            func.lower(OAuthApp.provider) == provider.lower(),
            OAuthApp.is_active.is_(True),
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _resolve_slack_bot_id(db: Any, tenant_id: Any, agent_id: Any = None) -> Any | None:
    """
    Resolve an active SlackBot to use as the Slack credential for internal_slack_* tools.

    A connected SlackBot (Socket Mode bot/app token) is a valid, independent credential
    source for Slack tools — it does not require a separate Slack OAuth app. However, a
    bot is a dedicated credential for the agent it was connected to: it must NEVER be
    silently reused as another agent's Slack credential, so there is no tenant-wide
    fallback here — only a bot already linked to this exact agent counts.
    """
    from src.models.slack_bot import SlackBot

    if not agent_id:
        return None

    result = await db.execute(
        select(SlackBot.id)
        .where(
            SlackBot.agent_id == agent_id,
            SlackBot.tenant_id == tenant_id,
            SlackBot.is_active.is_(True),
            SlackBot.deleted_at.is_(None),
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _resolve_target_agent(db: Any, agent_name: str, tenant_id: Any) -> Any:
    """Look up an agent by name for the calling tenant, with a fallback to the platform tenant for PE."""
    from uuid import UUID

    from src.models.agent import Agent

    result = await db.execute(
        select(Agent).where(
            Agent.tenant_id == tenant_id,
            Agent.agent_name == agent_name,
        )
    )
    agent = result.scalar_one_or_none()
    if agent:
        return agent

    if agent_name == "platform_engineer_agent":
        platform_tenant_id = UUID("00000000-0000-0000-0000-000000000000")
        result = await db.execute(
            select(Agent).where(
                Agent.tenant_id == platform_tenant_id,
                Agent.agent_name == "platform_engineer_agent",
            )
        )
        return result.scalar_one_or_none()

    return None


async def platform_create_slack_bot(
    agent_name: str,
    bot_name: str,
    bot_token: str,
    connection_mode: str = "socket",
    app_token: str | None = None,
    signing_secret: str | None = None,
    app_id: str = "",
    runtime_context: Any = None,
) -> dict:
    """
    Create a Slack bot for an agent and activate it.

    Args:
        agent_name: Slug name of the target agent (or 'platform_engineer_agent' for the PE itself)
        bot_name: Display name for the bot in Slack
        bot_token: Bot user OAuth token (xoxb-...)
        connection_mode: 'socket' (default, needs app_token) or 'event' (needs signing_secret)
        app_token: App-level token for Socket Mode (xapp-...)
        signing_secret: Signing secret for Event Mode
        app_id: Slack App ID (optional — shown in app settings at api.slack.com)

    Returns:
        dict with success, bot_id, workspace_name, and webhook_url (Event Mode only)
    """
    if not runtime_context or not runtime_context.tenant_id:
        return {"success": False, "message": "No tenant context available"}

    try:
        from src.services.slack.slack_bot_manager import SlackBotManager

        db = runtime_context.db_session
        tenant_id = runtime_context.tenant_id

        agent = await _resolve_target_agent(db, agent_name, tenant_id)
        if not agent:
            return {"success": False, "message": f"Agent '{agent_name}' not found"}

        manager = SlackBotManager(db)
        slack_bot = await manager.create_bot(
            agent_id=agent.id,
            tenant_id=tenant_id,
            bot_name=bot_name,
            slack_app_id=app_id or "auto",
            slack_bot_token=bot_token,
            slack_app_token=app_token,
            connection_mode=connection_mode,
            signing_secret=signing_secret,
            created_by=runtime_context.user_id if runtime_context.user_id else None,
        )

        await manager.start_bot(slack_bot.id)

        conv_id = str(runtime_context.conversation_id) if runtime_context.conversation_id else None
        await _scrub_tokens_from_conversation(
            db=db,
            conversation_id=conv_id,
            sensitive_values=[bot_token, app_token or "", signing_secret or ""],
        )

        result: dict[str, Any] = {
            "success": True,
            "bot_id": str(slack_bot.id),
            "workspace_name": slack_bot.slack_workspace_name,
        }
        if slack_bot.webhook_url:
            result["webhook_url"] = slack_bot.webhook_url
        return result

    except Exception as e:
        logger.exception("Error creating Slack bot")
        try:
            await runtime_context.db_session.rollback()
        except Exception:
            pass
        return {"success": False, "message": str(e)}


async def platform_create_telegram_bot(
    agent_name: str,
    bot_name: str,
    bot_token: str,
    runtime_context: Any = None,
) -> dict:
    """
    Create a Telegram bot for an agent and start long polling.

    Args:
        agent_name: Slug name of the target agent (or 'platform_engineer_agent' for the PE itself)
        bot_name: Display name for the bot
        bot_token: Bot token from @BotFather

    Returns:
        dict with success, bot_id, bot_username
    """
    if not runtime_context or not runtime_context.tenant_id:
        return {"success": False, "message": "No tenant context available"}

    try:
        from src.services.telegram.telegram_bot_manager import TelegramBotManager

        db = runtime_context.db_session
        tenant_id = runtime_context.tenant_id

        agent = await _resolve_target_agent(db, agent_name, tenant_id)
        if not agent:
            return {"success": False, "message": f"Agent '{agent_name}' not found"}

        manager = TelegramBotManager(db)
        telegram_bot = await manager.create_bot(
            agent_id=agent.id,
            tenant_id=tenant_id,
            bot_name=bot_name,
            bot_token=bot_token,
            created_by=runtime_context.user_id if runtime_context.user_id else None,
        )

        await manager.start_bot(telegram_bot.id)

        conv_id = str(runtime_context.conversation_id) if runtime_context.conversation_id else None
        await _scrub_tokens_from_conversation(
            db=db,
            conversation_id=conv_id,
            sensitive_values=[bot_token],
        )

        return {
            "success": True,
            "bot_id": str(telegram_bot.id),
            "bot_username": telegram_bot.bot_username,
        }

    except Exception as e:
        logger.exception("Error creating Telegram bot")
        try:
            await runtime_context.db_session.rollback()
        except Exception:
            pass
        return {"success": False, "message": str(e)}


async def platform_list_agent_channels(
    agent_name: str,
    runtime_context: Any = None,
) -> dict:
    """
    List all Slack and Telegram bots connected to a given agent.

    Args:
        agent_name: Slug name of the agent

    Returns:
        dict with slack (list) and telegram (list) channel summaries
    """
    if not runtime_context or not runtime_context.tenant_id:
        return {"error": "No tenant context available"}

    try:
        from src.models.slack_bot import SlackBot
        from src.models.telegram_bot import TelegramBot

        db = runtime_context.db_session
        tenant_id = runtime_context.tenant_id

        agent = await _resolve_target_agent(db, agent_name, tenant_id)
        if not agent:
            return {"error": f"Agent '{agent_name}' not found"}

        slack_result = await db.execute(
            select(SlackBot).where(
                SlackBot.agent_id == agent.id,
                SlackBot.tenant_id == tenant_id,
                SlackBot.deleted_at.is_(None),
            )
        )
        slack_bots = slack_result.scalars().all()

        telegram_result = await db.execute(
            select(TelegramBot).where(
                TelegramBot.agent_id == agent.id,
                TelegramBot.tenant_id == tenant_id,
                TelegramBot.deleted_at.is_(None),
            )
        )
        telegram_bots = telegram_result.scalars().all()

        return {
            "agent_name": agent_name,
            "slack": [
                {
                    "bot_id": str(b.id),
                    "bot_name": b.bot_name,
                    "workspace_name": b.slack_workspace_name,
                    "status": b.connection_status,
                    "is_active": b.is_active,
                    "connection_mode": b.connection_mode,
                }
                for b in slack_bots
            ],
            "telegram": [
                {
                    "bot_id": str(b.id),
                    "bot_name": b.bot_name,
                    "bot_username": b.bot_username,
                    "status": b.connection_status,
                    "is_active": b.is_active,
                }
                for b in telegram_bots
            ],
        }

    except Exception as e:
        logger.exception("Error listing agent channels")
        return {"error": str(e)}


async def platform_delete_agent_channel(
    channel: str,
    bot_id: str,
    runtime_context: Any = None,
) -> dict:
    """
    Disconnect a Slack or Telegram bot from an agent (soft-delete).

    Args:
        channel: 'slack' or 'telegram'
        bot_id: UUID of the bot to remove

    Returns:
        dict with success and message
    """
    if not runtime_context or not runtime_context.tenant_id:
        return {"success": False, "message": "No tenant context available"}

    if channel not in ("slack", "telegram"):
        return {"success": False, "message": "channel must be 'slack' or 'telegram'"}

    try:
        from datetime import datetime
        from uuid import UUID

        db = runtime_context.db_session
        tenant_id = runtime_context.tenant_id
        bot_uuid = UUID(bot_id)

        if channel == "slack":
            from src.models.slack_bot import SlackBot
            from src.services.slack.slack_bot_manager import SlackBotManager

            bot = (
                await db.execute(
                    select(SlackBot).where(
                        SlackBot.id == bot_uuid,
                        SlackBot.tenant_id == tenant_id,
                    )
                )
            ).scalar_one_or_none()
            if not bot:
                return {"success": False, "message": "Slack bot not found"}

            manager = SlackBotManager(db)
            await manager.stop_bot(bot.id)
            bot.is_active = False
            bot.deleted_at = datetime.utcnow()
            await db.commit()

        else:
            from src.models.telegram_bot import TelegramBot
            from src.services.telegram.telegram_bot_manager import TelegramBotManager

            bot = (
                await db.execute(
                    select(TelegramBot).where(
                        TelegramBot.id == bot_uuid,
                        TelegramBot.tenant_id == tenant_id,
                    )
                )
            ).scalar_one_or_none()
            if not bot:
                return {"success": False, "message": "Telegram bot not found"}

            manager = TelegramBotManager(db)
            await manager.stop_bot(bot.id)
            bot.is_active = False
            bot.deleted_at = datetime.utcnow()
            await db.commit()

        return {"success": True, "message": f"{channel.capitalize()} bot disconnected"}

    except ValueError as e:
        return {"success": False, "message": f"Invalid bot_id: {e}"}
    except Exception as e:
        logger.exception("Error deleting agent channel")
        try:
            db = runtime_context.db_session
            await db.rollback()
        except Exception:
            pass
        return {"success": False, "message": str(e)}
