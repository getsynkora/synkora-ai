"""
Agent API endpoints.

Provides REST API endpoints for managing and executing Google Agent SDK agents.
"""

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.controllers.agents.models import AgentResponse
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.models.agent import Agent
from src.models.tenant import Account
from src.services.agents.adk_tools import tool_registry
from src.services.agents.agent_manager import AgentManager

logger = logging.getLogger(__name__)

# Create router
agents_tools_router = APIRouter()

# Global agent manager instance
agent_manager = AgentManager()


#
@agents_tools_router.get("/tools", response_model=AgentResponse)
async def list_tools():
    """
    List all available tools that can be assigned to agents.

    Returns:
        List of available tools with their descriptions and parameters
    """
    try:
        tools = tool_registry.list_tools()

        return AgentResponse(success=True, message=f"Found {len(tools)} available tools", data={"tools": tools})
    except Exception as e:
        logger.error(f"Failed to list tools: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list tools")


# Agent Tools Configuration Endpoints


class SaveAgentToolRequest(BaseModel):
    """Request model for saving agent tool configuration."""

    tool_name: str = Field(..., description="Name of the tool")
    config: dict[str, Any] = Field(..., description="Tool configuration")
    enabled: bool = Field(True, description="Whether the tool is enabled")
    custom_tool_id: str | None = Field(None, description="UUID of custom tool (for custom tool operations)")
    operation_id: str | None = Field(None, description="Operation ID from custom tool's OpenAPI schema")
    oauth_app_id: int | None = Field(None, description="OAuth app ID to use for this tool")
    slack_bot_id: str | None = Field(None, description="Slack bot UUID to pin for Slack tools")


@agents_tools_router.get("/{agent_id}/tools", response_model=AgentResponse)
async def list_agent_tools(
    agent_id: str, tenant_id: uuid.UUID = Depends(get_current_tenant_id), db: AsyncSession = Depends(get_async_db)
):
    """
    List all tools configured for a specific agent.

    Args:
        agent_id: UUID of the agent
        tenant_id: Tenant ID from JWT token
        db: Database session

    Returns:
        List of configured tools with custom tool information
    """
    try:
        from src.models.agent_tool import AgentTool

        # Convert string to UUID
        try:
            agent_uuid = uuid.UUID(agent_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid agent ID format")

        # SECURITY: Single OR query to prevent timing attacks
        # Checks: (agent belongs to tenant) OR (agent is public)
        from sqlalchemy import or_

        result = await db.execute(
            select(Agent).filter(Agent.id == agent_uuid, or_(Agent.tenant_id == tenant_id, Agent.is_public.is_(True)))
        )
        agent = result.scalar_one_or_none()
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent with ID '{agent_id}' not found")

        # Get all tools for this agent with eager loading to prevent N+1 queries
        tools_result = await db.execute(
            select(AgentTool).options(selectinload(AgentTool.custom_tool)).filter(AgentTool.agent_id == agent_uuid)
        )
        tools = tools_result.scalars().all()

        # Build response with custom tool information (already loaded via selectinload)
        tools_list = []
        for tool in tools:
            tool_data = tool.to_dict(include_config=True)

            # If this is a custom tool operation, include custom tool details
            custom_tool = tool.custom_tool  # Already loaded via selectinload
            if custom_tool:
                tool_data["custom_tool"] = {
                    "id": str(custom_tool.id),
                    "name": custom_tool.name,
                    "description": custom_tool.description,
                    "server_url": custom_tool.server_url,
                    "operation_id": tool.operation_id,
                }

            tools_list.append(tool_data)

        return AgentResponse(
            success=True, message=f"Found {len(tools_list)} tools for agent", data={"tools": tools_list}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list agent tools: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list agent tools")


@agents_tools_router.post("/{agent_id}/tools", response_model=AgentResponse)
async def save_agent_tool(
    agent_id: str,
    request: SaveAgentToolRequest,
    current_account: Account = Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Save or update a tool configuration for an agent.

    Args:
        agent_id: UUID of the agent
        request: Tool configuration request
        current_account: Authenticated user
        tenant_id: Tenant ID from JWT token
        db: Database session

    Returns:
        Success confirmation

    SECURITY: Requires authentication and verifies agent belongs to tenant.
    """
    try:
        from src.models.agent_tool import AgentTool

        # Convert string to UUID
        try:
            agent_uuid = uuid.UUID(agent_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid agent ID format")

        # SECURITY: Verify agent exists AND belongs to current tenant
        result = await db.execute(select(Agent).filter(Agent.id == agent_uuid, Agent.tenant_id == tenant_id))
        agent = result.scalar_one_or_none()
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent with ID '{agent_id}' not found")

        # Check if tool already exists for this agent
        existing_result = await db.execute(
            select(AgentTool).filter(AgentTool.agent_id == agent_uuid, AgentTool.tool_name == request.tool_name)
        )
        existing_tool = existing_result.scalar_one_or_none()

        slack_bot_uuid = uuid.UUID(request.slack_bot_id) if request.slack_bot_id else None

        if existing_tool:
            # Update existing tool
            existing_tool.config = request.config
            existing_tool.enabled = request.enabled
            existing_tool.oauth_app_id = request.oauth_app_id
            existing_tool.custom_tool_id = uuid.UUID(request.custom_tool_id) if request.custom_tool_id else None
            existing_tool.operation_id = request.operation_id
            existing_tool.slack_bot_id = slack_bot_uuid
            message = f"Tool '{request.tool_name}' updated successfully"
        else:
            # Create new tool
            new_tool = AgentTool(
                agent_id=agent_uuid,
                tool_name=request.tool_name,
                config=request.config,
                enabled=request.enabled,
                oauth_app_id=request.oauth_app_id,
                custom_tool_id=uuid.UUID(request.custom_tool_id) if request.custom_tool_id else None,
                operation_id=request.operation_id,
                slack_bot_id=slack_bot_uuid,
            )
            db.add(new_tool)
            message = f"Tool '{request.tool_name}' configured successfully"

        await db.commit()

        return AgentResponse(
            success=True, message=message, data={"tool_name": request.tool_name, "enabled": request.enabled}
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to save agent tool: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save tool configuration"
        )


class TestToolRequest(BaseModel):
    """Request model for testing a tool configuration."""

    config: dict[str, Any] = Field(..., description="Tool configuration to test")


@agents_tools_router.post("/{agent_id}/tools/{tool_name}/test", response_model=AgentResponse)
async def test_agent_tool(
    agent_id: str,
    tool_name: str,
    request: TestToolRequest,
    current_account: Account = Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Test a tool configuration.

    Args:
        agent_id: UUID of the agent
        tool_name: Name of the tool to test
        request: Test request with tool configuration
        current_account: Authenticated user
        tenant_id: Tenant ID from JWT token
        db: Database session

    Returns:
        Test result

    SECURITY: Requires authentication and verifies agent belongs to tenant.
    """
    config = request.config
    try:
        # Convert string to UUID
        try:
            agent_uuid = uuid.UUID(agent_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid agent ID format")

        # SECURITY: Verify agent exists AND belongs to current tenant
        result = await db.execute(select(Agent).filter(Agent.id == agent_uuid, Agent.tenant_id == tenant_id))
        agent = result.scalar_one_or_none()
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent with ID '{agent_id}' not found")

        # Tool-specific validation
        # Internal tools don't require configuration
        if tool_name.startswith("internal_"):
            # Internal tools are always valid (no config required)
            return AgentResponse(
                success=True,
                message=f"Tool '{tool_name}' configuration is valid (internal tool)",
                data={"tool_name": tool_name, "valid": True},
            )

        # For non-internal tools, validate that required fields are present
        if not config:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Configuration cannot be empty")

        if tool_name == "web_search":
            if "SERPAPI_KEY" not in config or not config["SERPAPI_KEY"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="SERPAPI_KEY is required for web_search tool"
                )
        elif tool_name == "GMAIL":
            if "GMAIL_CREDENTIALS_PATH" not in config or not config["GMAIL_CREDENTIALS_PATH"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="GMAIL_CREDENTIALS_PATH is required for gmail tool"
                )
        elif tool_name == "youtube":
            if "YOUTUBE_API_KEY" not in config or not config["YOUTUBE_API_KEY"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="YOUTUBE_API_KEY is required for youtube tool"
                )

        # If validation passes, return success
        return AgentResponse(
            success=True,
            message=f"Tool '{tool_name}' configuration is valid",
            data={"tool_name": tool_name, "valid": True},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to test tool configuration: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to test tool configuration"
        )


@agents_tools_router.delete("/{agent_id}/tools/{tool_id}", response_model=AgentResponse)
async def delete_agent_tool(
    agent_id: str,
    tool_id: str,
    current_account: Account = Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Delete a tool configuration from an agent.

    Args:
        agent_id: UUID of the agent
        tool_id: UUID of the tool to delete
        current_account: Authenticated user
        tenant_id: Tenant ID from JWT token
        db: Database session

    Returns:
        Deletion confirmation

    SECURITY: Requires authentication and verifies agent belongs to tenant.
    """
    try:
        from src.models.agent_tool import AgentTool

        # Convert string to UUID
        try:
            agent_uuid = uuid.UUID(agent_id)
            tool_uuid = uuid.UUID(tool_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid agent ID or tool ID format")

        # SECURITY: First verify agent belongs to current tenant
        result = await db.execute(select(Agent).filter(Agent.id == agent_uuid, Agent.tenant_id == tenant_id))
        agent = result.scalar_one_or_none()
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent with ID '{agent_id}' not found")

        # Find and delete the tool
        tool_result = await db.execute(
            select(AgentTool).filter(AgentTool.agent_id == agent_uuid, AgentTool.id == tool_uuid)
        )
        tool = tool_result.scalar_one_or_none()

        if not tool:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Tool with ID '{tool_id}' not found for this agent"
            )

        tool_name = tool.tool_name
        await db.delete(tool)
        await db.commit()

        return AgentResponse(success=True, message=f"Tool '{tool_name}' deleted successfully")

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete agent tool: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete tool")


# =============================================================================
# Agent Capabilities Endpoints
# =============================================================================

# Capability definitions - match frontend data layer
CAPABILITIES = [
    {
        "id": "code-github",
        "name": "Code & GitHub",
        "description": "Clone repos, create PRs, manage branches, code review",
        "icon": "💻",
        "tool_patterns": [
            "internal_git_*",
            "internal_github_*",
            "internal_gitlab_*",
            "internal_pr_review_*",
            "internal_create_github_*",
            "internal_deploy_*_github*",
            "internal_enable_github_*",
        ],
        "requires_oauth": ["github", "gitlab"],
    },
    {
        "id": "project-mgmt",
        "name": "Project Management",
        "description": "Manage Jira issues, ClickUp tasks, comments, and workflows",
        "icon": "📋",
        "tool_patterns": ["internal_*jira_*", "internal_*clickup_*", "internal_get_sprint_*"],
        "requires_oauth": ["jira", "clickup"],
    },
    {
        "id": "communication",
        "name": "Slack",
        "description": "Send messages, search conversations, manage channels",
        "icon": "💬",
        "tool_patterns": ["internal_slack_*", "internal_send_slack_*", "internal_search_slack_*"],
        "requires_oauth": ["SLACK"],
    },
    {
        "id": "meetings-calendar",
        "name": "Calendar & Zoom",
        "description": "Manage calendar events, schedule meetings, video conferencing",
        "icon": "📅",
        "tool_patterns": ["internal_zoom_*", "internal_google_calendar_*"],
        "requires_oauth": ["zoom", "google_calendar"],
    },
    {
        "id": "files-storage",
        "name": "Files & Storage",
        "description": "Read, write, search files, manage cloud storage",
        "icon": "📁",
        "tool_patterns": [
            "internal_read_*_file",
            "internal_write_file",
            "internal_edit_file",
            "internal_search_files",
            "internal_get_file_info",
            "internal_move_file",
            "internal_create_directory",
            "internal_list_directory",
            "internal_directory_tree",
            "internal_s3_*",
            "internal_storage_*",
            "internal_google_drive_*",
            "internal_google_docs_*",
            "internal_google_sheets_*",
            "internal_glob",
            "internal_grep",
            "internal_read_file",
        ],
        "requires_oauth": ["google_drive"],
    },
    {
        "id": "database-analytics",
        "name": "Database & Analytics",
        "description": "Query databases, generate charts, Elasticsearch search",
        "icon": "📊",
        "tool_patterns": [
            "internal_query_*",
            "internal_list_database_*",
            "internal_get_database_*",
            "internal_generate_chart",
            "internal_elasticsearch_*",
            "internal_chart_*",
            "analyze_*",
            "export_data_*",
            "generate_chart_from_*",
            "query_databricks",
            "query_datadog_*",
            "query_docker_*",
        ],
    },
    {
        "id": "image-generation",
        "name": "Image Generation",
        "description": "Generate AI images from text prompts (gpt-image-2, Google Imagen, Grok Aurora)",
        "icon": "🎨",
        "tool_patterns": ["internal_generate_image"],
    },
    {
        "id": "documents",
        "name": "Documents",
        "description": "Generate PDFs, PowerPoints, Google Docs and Sheets",
        "icon": "📄",
        "tool_patterns": [
            "internal_generate_pdf",
            "internal_generate_powerpoint",
            "internal_generate_google_doc",
            "internal_generate_google_sheet",
            "internal_*_pdf",
            "internal_*_pptx",
            "internal_*_docx",
        ],
    },
    {
        "id": "social-media",
        "name": "Social Media",
        "description": "Post to Twitter, LinkedIn, search YouTube, Hacker News",
        "icon": "📱",
        "tool_patterns": [
            "internal_twitter_*",
            "internal_linkedin_*",
            "internal_youtube_*",
            "internal_hackernews_*",
            "internal_hn_*",
            "internal_news_*",
            "internal_fetch_rss_*",
        ],
    },
    {
        "id": "browser-web",
        "name": "Browser & Web",
        "description": "Web automation, screenshots, scraping, link extraction",
        "icon": "🌐",
        "tool_patterns": [
            "internal_browser_*",
            "internal_navigate_*",
            "internal_screenshot_*",
            "internal_extract_*",
            "internal_check_element*",
            "internal_scrape_*",
            "internal_web_*",
            "web_search",
            "navigate_to_url",
            "extract_links",
            "extract_structured_data",
            "check_element_exists",
        ],
    },
    {
        "id": "system-commands",
        "name": "System & Commands",
        "description": "Execute system commands, manage processes",
        "icon": "⚡",
        "tool_patterns": ["internal_run_command", "internal_execute_*", "internal_process_*"],
    },
    {
        "id": "passwords-secrets",
        "name": "Passwords & Secrets",
        "description": "Access 1Password vaults, retrieve credentials securely",
        "icon": "🔐",
        "tool_patterns": ["internal_1password_*", "internal_onepassword_*", "internal_op_*"],
    },
    {
        "id": "email",
        "name": "Email",
        "description": "Send, read, and search emails via Gmail",
        "icon": "✉️",
        "tool_patterns": [
            "internal_email_*",
            "internal_gmail_*",
            "internal_send_email",
            "internal_send_bulk_emails",
            "internal_test_email_connection",
            "internal_read_email*",
            "internal_search_email*",
        ],
        "requires_oauth": ["GMAIL"],
    },
    {
        "id": "scheduling",
        "name": "Scheduling & Automation",
        "description": "Schedule recurring tasks, cron jobs, reminders, and automated workflows",
        "icon": "⏰",
        "tool_patterns": [
            "internal_create_scheduled_task",
            "internal_create_cron_scheduled_task",
            "internal_list_scheduled_tasks",
            "internal_delete_scheduled_task",
            "internal_toggle_scheduled_task",
            "internal_schedule_*",
        ],
    },
    {
        "id": "multi-agent",
        "name": "Multi-Agent",
        "description": "Spawn sub-agents, check background task status, call remote agents via A2A",
        "icon": "🤖",
        "tool_patterns": ["spawn_agent", "check_task", "list_background_tasks", "call_remote_agent"],
    },
]


def _match_tool_pattern(tool_name: str, pattern: str) -> bool:
    """Match a tool name against a pattern. Supports wildcard (*) at the end."""
    import fnmatch

    return fnmatch.fnmatch(tool_name, pattern)


def _get_tools_for_capability(capability_id: str, available_tools: list[str]) -> list[str]:
    """Get all tools that match a capability's patterns."""
    capability = next((c for c in CAPABILITIES if c["id"] == capability_id), None)
    if not capability:
        return []

    matched_tools = []
    for tool_name in available_tools:
        for pattern in capability["tool_patterns"]:
            if _match_tool_pattern(tool_name, pattern):
                matched_tools.append(tool_name)
                break
    return matched_tools


@agents_tools_router.get("/capabilities", response_model=AgentResponse)
async def list_capabilities():
    """
    List all available capabilities with their matched tools.

    Returns:
        List of capabilities with their tool lists
    """
    try:
        # Get all available tools from registry
        tools = tool_registry.list_tools()
        available_tool_names = [t["name"] for t in tools]

        # Build capabilities response with matched tools
        capabilities_with_tools = []
        for cap in CAPABILITIES:
            matched_tools = _get_tools_for_capability(cap["id"], available_tool_names)
            capabilities_with_tools.append(
                {
                    **cap,
                    "tools": matched_tools,
                    "tool_count": len(matched_tools),
                }
            )

        return AgentResponse(
            success=True,
            message=f"Found {len(CAPABILITIES)} capabilities",
            data={"capabilities": capabilities_with_tools},
        )
    except Exception as e:
        logger.error(f"Failed to list capabilities: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list capabilities")


class EnableCapabilityRequest(BaseModel):
    """Request model for enabling a capability."""

    oauth_app_id: int | None = Field(None, description="OAuth app ID to use for tools requiring OAuth")


class EnableCapabilitiesBulkRequest(BaseModel):
    """Request model for enabling multiple capabilities at once."""

    capability_ids: list[str] = Field(..., description="List of capability IDs to enable")
    oauth_app_ids: dict[str, int] | None = Field(
        None, description="Map of OAuth provider to OAuth app ID (e.g., {'github': 1, 'SLACK': 2})"
    )


# NOTE: Bulk endpoint MUST be defined BEFORE the parameterized /{capability_id} endpoint
# Otherwise FastAPI will match "bulk" as a capability_id parameter
@agents_tools_router.post("/{agent_id}/capabilities/bulk", response_model=AgentResponse)
async def enable_capabilities_bulk(
    agent_id: str,
    request: EnableCapabilitiesBulkRequest,
    current_account: Account = Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Enable multiple capabilities at once on an agent.

    Args:
        agent_id: UUID of the agent
        request: List of capability IDs and optional OAuth app mappings
        current_account: Authenticated user
        tenant_id: Tenant ID from JWT token
        db: Database session

    Returns:
        Success confirmation with list of all enabled tools

    SECURITY: Requires authentication and verifies agent belongs to tenant.
    """
    try:
        from src.models.agent_tool import AgentTool

        # Validate agent ID
        try:
            agent_uuid = uuid.UUID(agent_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid agent ID format")

        # SECURITY: Verify agent exists AND belongs to current tenant
        result = await db.execute(select(Agent).filter(Agent.id == agent_uuid, Agent.tenant_id == tenant_id))
        agent = result.scalar_one_or_none()
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent with ID '{agent_id}' not found")

        # Validate all capability IDs
        valid_cap_ids = {c["id"] for c in CAPABILITIES}
        invalid_ids = [cid for cid in request.capability_ids if cid not in valid_cap_ids]
        if invalid_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid capability IDs: {', '.join(invalid_ids)}"
            )

        # Get available tools
        tools = tool_registry.list_tools()
        available_tool_names = [t["name"] for t in tools]

        # Collect all tools to enable across capabilities
        all_tools_to_enable = set()
        capability_results = []

        for cap_id in request.capability_ids:
            capability = next((c for c in CAPABILITIES if c["id"] == cap_id), None)
            matched_tools = _get_tools_for_capability(cap_id, available_tool_names)

            capability_results.append(
                {
                    "capability_id": cap_id,
                    "capability_name": capability["name"] if capability else cap_id,
                    "tool_count": len(matched_tools),
                    "requires_oauth": capability.get("requires_oauth", []) if capability else [],
                }
            )

            all_tools_to_enable.update(matched_tools)

        # Enable each tool
        enabled_tools = []
        oauth_app_ids = request.oauth_app_ids or {}

        for tool_name in all_tools_to_enable:
            # Determine which OAuth app to use based on tool name and capability
            oauth_app_id = None
            for cap in CAPABILITIES:
                if cap["id"] in request.capability_ids:
                    matched = any(_match_tool_pattern(tool_name, p) for p in cap["tool_patterns"])
                    if matched and cap.get("requires_oauth"):
                        for provider in cap["requires_oauth"]:
                            if provider in oauth_app_ids:
                                oauth_app_id = oauth_app_ids[provider]
                                break
                        break

            # Check if tool already exists
            existing_result = await db.execute(
                select(AgentTool).filter(AgentTool.agent_id == agent_uuid, AgentTool.tool_name == tool_name)
            )
            existing_tool = existing_result.scalar_one_or_none()

            if existing_tool:
                existing_tool.enabled = True
                if oauth_app_id:
                    existing_tool.oauth_app_id = oauth_app_id
            else:
                new_tool = AgentTool(
                    agent_id=agent_uuid,
                    tool_name=tool_name,
                    config={},
                    enabled=True,
                    oauth_app_id=oauth_app_id,
                )
                db.add(new_tool)

            enabled_tools.append(tool_name)

        await db.commit()

        return AgentResponse(
            success=True,
            message=f"Enabled {len(enabled_tools)} tools across {len(request.capability_ids)} capabilities",
            data={
                "capabilities": capability_results,
                "total_tools_enabled": len(enabled_tools),
                "enabled_tools": sorted(enabled_tools),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to enable capabilities: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to enable capabilities")


@agents_tools_router.post("/{agent_id}/capabilities/{capability_id}", response_model=AgentResponse)
async def enable_capability(
    agent_id: str,
    capability_id: str,
    request: EnableCapabilityRequest | None = None,
    current_account: Account = Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Enable all tools for a capability on an agent.

    Args:
        agent_id: UUID of the agent
        capability_id: ID of the capability to enable
        request: Optional OAuth app ID for tools requiring OAuth
        current_account: Authenticated user
        tenant_id: Tenant ID from JWT token
        db: Database session

    Returns:
        Success confirmation with list of enabled tools

    SECURITY: Requires authentication and verifies agent belongs to tenant.
    """
    try:
        from src.models.agent_tool import AgentTool

        # Validate capability
        capability = next((c for c in CAPABILITIES if c["id"] == capability_id), None)
        if not capability:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Capability '{capability_id}' not found")

        # Validate agent ID
        try:
            agent_uuid = uuid.UUID(agent_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid agent ID format")

        # SECURITY: Verify agent exists AND belongs to current tenant
        result = await db.execute(select(Agent).filter(Agent.id == agent_uuid, Agent.tenant_id == tenant_id))
        agent = result.scalar_one_or_none()
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent with ID '{agent_id}' not found")

        # Get available tools and match to capability
        tools = tool_registry.list_tools()
        available_tool_names = [t["name"] for t in tools]
        matched_tools = _get_tools_for_capability(capability_id, available_tool_names)

        if not matched_tools:
            return AgentResponse(
                success=True,
                message=f"No tools found for capability '{capability_id}'",
                data={"enabled_tools": [], "capability": capability_id},
            )

        # Enable each tool
        enabled_tools = []
        oauth_app_id = request.oauth_app_id if request else None

        for tool_name in matched_tools:
            # Check if tool already exists
            existing_result = await db.execute(
                select(AgentTool).filter(AgentTool.agent_id == agent_uuid, AgentTool.tool_name == tool_name)
            )
            existing_tool = existing_result.scalar_one_or_none()

            if existing_tool:
                # Update existing tool to enabled
                existing_tool.enabled = True
                if oauth_app_id:
                    existing_tool.oauth_app_id = oauth_app_id
            else:
                # Create new tool entry
                new_tool = AgentTool(
                    agent_id=agent_uuid,
                    tool_name=tool_name,
                    config={},
                    enabled=True,
                    oauth_app_id=oauth_app_id,
                )
                db.add(new_tool)

            enabled_tools.append(tool_name)

        await db.commit()

        return AgentResponse(
            success=True,
            message=f"Enabled {len(enabled_tools)} tools for capability '{capability['name']}'",
            data={
                "capability": capability_id,
                "capability_name": capability["name"],
                "enabled_tools": enabled_tools,
                "requires_oauth": capability.get("requires_oauth", []),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to enable capability: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to enable capability")


@agents_tools_router.delete("/{agent_id}/capabilities/{capability_id}", response_model=AgentResponse)
async def disable_capability(
    agent_id: str,
    capability_id: str,
    current_account: Account = Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Disable all tools for a capability on an agent.

    Args:
        agent_id: UUID of the agent
        capability_id: ID of the capability to disable
        current_account: Authenticated user
        tenant_id: Tenant ID from JWT token
        db: Database session

    Returns:
        Success confirmation with list of disabled tools

    SECURITY: Requires authentication and verifies agent belongs to tenant.
    """
    try:
        from src.models.agent_tool import AgentTool

        # Validate capability
        capability = next((c for c in CAPABILITIES if c["id"] == capability_id), None)
        if not capability:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Capability '{capability_id}' not found")

        # Validate agent ID
        try:
            agent_uuid = uuid.UUID(agent_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid agent ID format")

        # SECURITY: Verify agent exists AND belongs to current tenant
        result = await db.execute(select(Agent).filter(Agent.id == agent_uuid, Agent.tenant_id == tenant_id))
        agent = result.scalar_one_or_none()
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent with ID '{agent_id}' not found")

        # Get all agent tools
        tools_result = await db.execute(select(AgentTool).filter(AgentTool.agent_id == agent_uuid))
        agent_tools = tools_result.scalars().all()
        tool_names = [t.tool_name for t in agent_tools]

        # Find tools matching this capability
        matched_tools = _get_tools_for_capability(capability_id, tool_names)

        # Disable matching tools
        disabled_tools = []
        for tool in agent_tools:
            if tool.tool_name in matched_tools:
                tool.enabled = False
                disabled_tools.append(tool.tool_name)

        await db.commit()

        return AgentResponse(
            success=True,
            message=f"Disabled {len(disabled_tools)} tools for capability '{capability['name']}'",
            data={
                "capability": capability_id,
                "capability_name": capability["name"],
                "disabled_tools": disabled_tools,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to disable capability: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to disable capability")
