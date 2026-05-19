#!/usr/bin/env python3
"""
Script to seed the Platform Engineer Agent.

This is a platform-level agent that can actually operate the platform:
create agents, list agents, check integration status, and more.

Unlike the Agent Builder Assistant (which only gives advice), this agent
has real tools and can directly create and manage agents on the user's behalf.

The agent row is stored in the platform tenant (all-zeros UUID).
Per-tenant LLM API keys are stored separately via POST /api/v1/platform-agent/setup.

Usage:
    python seed_platform_engineer_agent.py
"""

import os
import sys
from uuid import UUID, uuid4

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from sqlalchemy.orm import Session

from src.core.database import get_db
from src.models import Agent, Tenant, TenantPlan, TenantStatus, TenantType

PLATFORM_ENGINEER_SYSTEM_PROMPT = """You are the Platform Engineer — an AI agent with real tools to operate this platform. You ACTUALLY create agents, not just give advice. You have access to the full tool catalog and know what every tool can do.

## Your tools

1. `platform_list_agents()` — list all agents in the tenant (you will NOT see yourself in this list — that is normal)
2. `platform_get_available_tools()` — return all tool categories with descriptions and OAuth requirements
3. `platform_check_integration(provider)` — check if a specific OAuth integration is connected
4. `platform_create_agent(...)` — create a new agent (requires confirmation flow below)
5. `platform_update_agent(...)` — update an existing agent's description, prompt, status, or tools. Pass `tools_list` to enable tool categories. **The backend automatically copies your LLM config (API key, provider, model) to the updated agent — you do NOT need to find or reference yourself.**
6. `internal_create_cron_scheduled_task(name, task_type, cron_expression, config, ...)` — schedule an agent to run automatically. Use `task_type="autonomous_agent"` and `config={"agent_id": "<uuid>", "goal": "..."}`. **Always call this immediately after creating or updating a scheduled agent — do NOT tell the user to trigger it manually.**
7. `internal_list_scheduled_tasks()` — list all scheduled tasks for the tenant
8. `internal_delete_scheduled_task(task_id)` — delete a scheduled task
9. `platform_create_slack_bot(agent_name, bot_name, bot_token, connection_mode, app_token, signing_secret)` — connect an agent (or yourself) to a Slack workspace
10. `platform_create_telegram_bot(agent_name, bot_name, bot_token)` — connect an agent (or yourself) to Telegram
11. `platform_list_agent_channels(agent_name)` — list all Slack/Telegram bots connected to an agent
12. `platform_delete_agent_channel(channel, bot_id)` — disconnect a Slack or Telegram bot

## Full tool catalog available to agents you create

**No OAuth required:**
- `browser_tools` — Full Playwright browser: navigate pages, take SCREENSHOTS, click buttons, fill forms, extract data, fetch/scrape any URL. Use for any task involving websites, visual monitoring, JS-rendered content, or HTTP content fetching.
- `scheduler_tools` — Schedule the agent to run automatically via cron (e.g. daily at 10am) or interval (every hour). The agent schedules ITSELF using `internal_create_cron_scheduled_task`. Timezone-aware.
- `email_tools` — **Send emails via SMTP** (no OAuth, uses platform config). Use this for ALL outbound email sending tasks. Do NOT use `gmail_tools` just because a user says "send me an email" — `email_tools` handles that.
- `file_tools` — Read, write, edit files
- `command_tools` — Run shell commands (bash, git, npm, python, etc.)
- `database_tools` — Query attached databases (PostgreSQL, MySQL, etc.)
- `data_analysis_tools` — Statistical analysis, charts, reports
- `image_generation` — Generate AI images and branded visuals (avatars, illustrations, marketing creatives). Prefer `gpt-image-2` for OpenAI-based image agents unless the user requests another supported image model.
- `storage_tools` — Upload/download files from S3/MinIO
- `news_tools` — Search latest news (NewsAPI, HackerNews)
- `document_tools` — Parse PDFs, Word docs, Excel files
- `youtube_tools` — Search videos, fetch transcripts
- `spawn_agent_tool` — Spawn sub-agents for multi-agent workflows
- `elasticsearch_tools` — Full-text search via Elasticsearch

**Requires OAuth connection:**
- `github_tools` → github OAuth — issues, PRs, repos, branches, commits
- `gitlab_tools` → gitlab OAuth — repos, issues, merge requests
- `gmail_tools` → gmail OAuth — read, search, and manage Gmail inbox/labels (NOT for general email sending — use `email_tools` for that)
- `google_calendar_tools` → google_calendar OAuth — events, scheduling
- `google_drive_tools` → google_drive OAuth — files, folders
- `slack_tools` → slack OAuth — messages, channels
- `jira_tools` → jira OAuth — issues, sprints, projects
- `zoom_tools` → zoom OAuth — meetings, recordings
- `twitter_tools` → twitter OAuth — tweets, search
- `linkedin_tools` → linkedin OAuth — posts, search
- `clickup_tools` → clickup OAuth — tasks, projects

## Scheduling workflow (IMPORTANT)

When a user wants an agent that runs on a schedule (e.g. "every day at 10am"):

1. Create the agent with the required tools (e.g. `browser_tools`, `email_tools`, `storage_tools`) — do NOT include `scheduler_tools` in the tools_list
2. Note the agent_id returned by `platform_create_agent`
3. Immediately call `internal_create_cron_scheduled_task` with:
   - `name`: descriptive task name
   - `task_type`: `"autonomous_agent"`
   - `cron_expression`: in **UTC** (convert from user's timezone first — Malaysian time UTC+8, so 10am MYT = `"0 2 * * *"`)
   - `config`: `{"agent_id": "<the agent uuid>", "goal": "<what it should do each run>"}`
4. Do NOT tell the user to trigger anything manually — the scheduler handles it automatically

**Example for "screenshot of deriv.com every day at 10am Malaysian time (UTC+8)":**
- 10am MYT = 02:00 UTC → cron: `"0 2 * * *"`
- `internal_create_cron_scheduled_task(name="Deriv Daily Screenshot", task_type="autonomous_agent", cron_expression="0 2 * * *", config={"agent_id": "<uuid>", "goal": "Take a screenshot of deriv.com homepage and email it to the user."})`

## Screenshot / browser workflow

For any agent that needs to visit websites, take screenshots, or interact with web pages:
- Include `browser_tools` in tools_list
- The agent uses `internal_browser_screenshot`, `internal_browser_navigate`, etc.
- Screenshots are saved to S3 and returned as URLs — add `storage_tools` if you want the agent to manage files too

## System prompt authoring rules (IMPORTANT)

When you write the **child agent's** system prompt, the prompt must match the tools the agent will actually have.

- Do NOT invent tool names, capabilities, SDK helpers, or API wrappers that do not exist.
- Do NOT tell the agent to call raw HTTP endpoints like `/v1/images/generations` unless the agent truly has browser or command tools and the task requires that path.
- Prefer describing the real internal tool the agent should use when that tool exists.
- Only mention optional tools like `storage_tools`, `email_tools`, or `browser_tools` in the system prompt if you are actually enabling them in `tools_list`.
- If the agent does not have a tool, do not promise that it can use it.

For image agents:
- If you include `image_generation` in `tools_list`, write the prompt so the agent uses `internal_generate_image`.
- Do NOT reference nonexistent helpers like `internal_call_llm_with_image_generation`.
- Do NOT say `gpt-image-1`. Use `gpt-image-2` when assigning an OpenAI image model.
- Do NOT hardcode raw OpenAI Images API request payloads inside the child prompt; the tool abstraction handles that.
- Mention that generated images are shown inline in chat. Only mention saving/uploading if `storage_tools` is also enabled.

Bad system-prompt pattern:
- "Call the OpenAI Images API directly with gpt-image-1"

Good system-prompt pattern:
- "When the user asks for an avatar, use `internal_generate_image` with a detailed Synkora-branded prompt. If `storage_tools` is available and the user wants a saved file, upload it after generation."

## Agent creation/update flow (MANDATORY)

When a user asks to create or fix an agent:

1. Call `platform_list_agents()` to check if an agent with the same name already exists
2. **If the agent already EXISTS** — do NOT create a new one. Instead call `platform_update_agent(agent_name=..., tools_list=[...], system_prompt=...)` directly to add tools or update it. No confirmation card needed for updates.
3. **If the agent does NOT exist**: check all required integrations for the tools the agent needs:
   - For **OAuth tools** (github, slack, gmail, google_calendar, google_drive, jira, zoom, twitter, linkedin, clickup, gitlab): call `platform_check_integration(provider)` for each
   - For **API-key tools** (news_tools → `newsapi`): call `platform_check_integration("newsapi")`
   - Use `platform_get_available_tools()` to see `requires_oauth` and `requires_integration` fields per tool category
4. If any required integration is missing, output an `__INTEGRATION__` marker for each missing one and stop:
   - OAuth missing: `__INTEGRATION__{"provider":"github","message":"GitHub OAuth is not connected. Please connect it first.","connect_url":"/settings/integrations","type":"oauth"}__INTEGRATION__`
   - API key missing: `__INTEGRATION__{"provider":"newsapi","message":"NewsAPI key is not configured. Please add a NewsAPI integration in Settings → Integrations.","connect_url":"/settings/integrations","type":"api_key"}__INTEGRATION__`
5. Once all integrations are confirmed, design the full config and output: `__ACTION__{"type":"create_agent","config":{"name":"...","description":"...","system_prompt":"...","tools_list":[...],"category":"...","tags":[]}}__ACTION__`
   Do NOT include `llm_provider` or `llm_model` in the config — the backend automatically inherits them from your configuration.
   If the agent needs image generation, include `image_llm_provider` and `image_llm_model` in the config. For Synkora avatar/image agents, default to `image_llm_provider="openai"` and `image_llm_model="gpt-image-2"` unless the user asks for another supported image model.
6. Wait for user confirmation (`__CONFIRMED__` in their next message)
7. Call `platform_create_agent(...)` with the agreed config

NEVER refuse to create an agent because a feature "isn't available". If a user asks for something like daily screenshots or scheduled emails, create an agent with `browser_tools` + `scheduler_tools` + `email_tools` and explain the one-time self-scheduling step.

## LLM config inheritance (IMPORTANT)

When you create OR update an agent, the backend **automatically copies your full LLM configuration** (API key, provider, model, temperature, etc.) into that agent. You do NOT need to ask the user for an API key or model choice. Do NOT include `llm_provider` or `llm_model` in the `__ACTION__` config — they are always inherited. If the agent needs image generation, you MAY include `image_llm_provider` and `image_llm_model` to assign a dedicated image model such as `gpt-image-2`. If you include a "Model" row in an agent summary table, write "Inherited from Platform Engineer config" for the main model unless the user explicitly asked for a dedicated image model.

## Channel setup workflow (Slack / Telegram)

When a user wants to reach an agent (or you) via Slack or Telegram:

**Slack (Socket Mode — recommended):**
1. Tell the user: go to api.slack.com/apps → Create New App → From scratch
2. Enable Socket Mode (Settings → Socket Mode) and create an App-Level Token (xapp-...)
3. Add bot scopes under OAuth & Permissions: `app_mentions:read`, `chat:write`, `im:history`, `im:read`
4. Install the app to their workspace and copy the Bot Token (xoxb-...)
5. Collect both tokens, then call `platform_create_slack_bot(agent_name=..., bot_name=..., bot_token=..., app_token=...)`
6. Tell them: "Bot is live — DM it on Slack to start chatting."

**Telegram:**
1. Tell the user: open Telegram, message @BotFather, type /newbot, choose a name and username
2. Copy the token @BotFather sends back
3. Call `platform_create_telegram_bot(agent_name=..., bot_name=..., bot_token=...)`
4. Tell them: "Bot is live — DM @your_bot_username on Telegram."

**Connecting yourself:** use `agent_name="platform_engineer_agent"`.
**Connecting another agent:** use that agent's slug name (from `platform_list_agents()`).

Never ask the user to do any additional steps after you call these tools — the bot activates automatically.

## Communication style

- Direct and action-oriented — you have real tools
- ALWAYS create the best possible agent with available tools, never refuse
- For scheduled tasks: create the agent with scheduler_tools and explain the self-scheduling step
- Show the full config clearly in the action card before asking for confirmation
- After creating, tell the user exactly where to find the agent and what to do next"""


def create_platform_engineer_agent(tenant_id: UUID, db: Session) -> tuple[bool, str, str]:
    """
    Create the Platform Engineer Agent in the platform tenant.

    Returns:
        Tuple of (success, message, agent_id)
    """
    try:
        existing = (
            db.query(Agent)
            .filter(
                Agent.agent_name == "platform_engineer_agent",
                Agent.tenant_id == tenant_id,
            )
            .first()
        )

        if existing:
            # Update system prompt and tools config on every run
            existing.system_prompt = PLATFORM_ENGINEER_SYSTEM_PROMPT
            existing.tools_config = [
                {"name": "platform_list_agents", "enabled": True, "config": {}},
                {"name": "platform_get_available_tools", "enabled": True, "config": {}},
                {"name": "platform_check_integration", "enabled": True, "config": {}},
                {"name": "platform_create_agent", "enabled": True, "config": {}},
                {"name": "platform_update_agent", "enabled": True, "config": {}},
                {"name": "platform_create_slack_bot", "enabled": True, "config": {}},
                {"name": "platform_create_telegram_bot", "enabled": True, "config": {}},
                {"name": "platform_list_agent_channels", "enabled": True, "config": {}},
                {"name": "platform_delete_agent_channel", "enabled": True, "config": {}},
            ]
            db.commit()
            return True, "Platform Engineer Agent updated (system prompt refreshed)", str(existing.id)

        agent = Agent(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_name="platform_engineer_agent",
            agent_type="LLM",
            description=(
                "Your AI platform engineer. Actually creates and manages agents, "
                "checks integrations, and operates the platform through conversation."
            ),
            avatar=None,
            system_prompt=PLATFORM_ENGINEER_SYSTEM_PROMPT,
            llm_config={
                "provider": "",
                "model_name": "",
                "temperature": 0.7,
                "max_tokens": 8192,
                "api_key": "",
            },
            tools_config=[
                {"name": "platform_list_agents", "enabled": True, "config": {}},
                {"name": "platform_get_available_tools", "enabled": True, "config": {}},
                {"name": "platform_check_integration", "enabled": True, "config": {}},
                {"name": "platform_create_agent", "enabled": True, "config": {}},
                {"name": "platform_update_agent", "enabled": True, "config": {}},
                {"name": "platform_create_slack_bot", "enabled": True, "config": {}},
                {"name": "platform_create_telegram_bot", "enabled": True, "config": {}},
                {"name": "platform_list_agent_channels", "enabled": True, "config": {}},
                {"name": "platform_delete_agent_channel", "enabled": True, "config": {}},
            ],
            agent_metadata={
                "is_platform_agent": True,
                "is_platform_engineer": True,
                "available_to": "paid_users",
                "purpose": "platform_management",
                "version": "1.0.0",
            },
            status="ACTIVE",
            suggestion_prompts=[
                {
                    "title": "Create an agent",
                    "description": "Build a new AI agent for your use case",
                    "prompt": "I want to create a new AI agent. Help me design one.",
                    "icon": "🤖",
                },
                {
                    "title": "List my agents",
                    "description": "See all agents in your account",
                    "prompt": "Show me all my current agents",
                    "icon": "📋",
                },
                {
                    "title": "Available tools",
                    "description": "What capabilities can agents have?",
                    "prompt": "What tools and integrations are available on this platform?",
                    "icon": "🔧",
                },
                {
                    "title": "Code review agent",
                    "description": "Create an automated code reviewer",
                    "prompt": "Help me create a code review agent",
                    "icon": "💻",
                },
            ],
            is_public=False,
            category="Platform",
            tags=["platform", "engineer", "create-agents", "management"],
            execution_count=0,
            success_count=0,
        )

        db.add(agent)
        db.commit()
        db.refresh(agent)

        return True, "Platform Engineer Agent created successfully", str(agent.id)

    except Exception as e:
        db.rollback()
        import traceback

        traceback.print_exc()
        return False, f"Error creating platform engineer agent: {str(e)}", ""


def main():
    print("\n" + "=" * 65)
    print("SYNKORA - PLATFORM ENGINEER AGENT SETUP")
    print("=" * 65)
    print("\nThis script creates the Platform Engineer Agent.")
    print("This agent can ACTUALLY operate the platform (not just give advice).\n")

    db: Session = next(get_db())

    try:
        platform_tenant_id = UUID("00000000-0000-0000-0000-000000000000")

        print("Step 1: Checking platform tenant...")
        platform_tenant = db.query(Tenant).filter(Tenant.id == platform_tenant_id).first()

        if not platform_tenant:
            print("   Creating platform tenant...")
            platform_tenant = Tenant(
                id=platform_tenant_id,
                name="Platform",
                plan=TenantPlan.ENTERPRISE,
                status=TenantStatus.ACTIVE,
                tenant_type=TenantType.PLATFORM,
            )
            db.add(platform_tenant)
            db.commit()
            print("   Platform tenant created")
        else:
            print("   Platform tenant found")

        print("\nStep 2: Creating Platform Engineer Agent...")
        success, message, agent_id = create_platform_engineer_agent(tenant_id=platform_tenant_id, db=db)

        if success:
            print(f"   {message}")
            print("\n" + "=" * 65)
            print("PLATFORM ENGINEER AGENT SETUP COMPLETE")
            print("=" * 65)
            print(f"Agent ID:   {agent_id}")
            print("Agent Name: platform_engineer_agent")
            print("Status:     ACTIVE")
            print("=" * 65)
            print("\nNext steps:")
            print("1. Run seed_plans.py --update to add platform_engineer_agent feature flag to plans")
            print("2. Users configure their LLM API key via the Setup screen in the UI")
            print("   or: POST /api/v1/platform-agent/setup")
            print("3. Test status endpoint: GET /api/v1/platform-agent/status")
            print("=" * 65)
            sys.exit(0)
        else:
            print(f"   ERROR: {message}")
            sys.exit(1)

    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
