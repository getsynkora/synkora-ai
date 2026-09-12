"""
Bridge between Synkora tools and Claude Agent SDK MCP format.

Allows the Claude Agent SDK to use Synkora's existing tool implementations
(OAuth-integrated, multi-tenant) via in-process MCP servers.

Usage:
    from src.services.agents.claude_sdk_bridge import create_synkora_mcp_config

    mcp_config = create_synkora_mcp_config(
        tool_names=["internal_read_file", "internal_write_file"],
        runtime_context=runtime_context,
    )

    # Pass to Claude Agent SDK options as dict[str, McpServerConfig]
    options = ClaudeAgentOptions(mcp_servers={"synkora": mcp_config})
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Server name used for MCP tool naming: mcp__synkora_tools__<tool_name>
MCP_SERVER_NAME = "synkora_tools"


def create_synkora_mcp_config(
    tool_names: list[str],
    runtime_context: Any = None,
    server_name: str = MCP_SERVER_NAME,
) -> dict[str, Any]:
    """
    Create an in-process MCP server config that exposes Synkora tools to Claude Agent SDK.

    Uses the SDK's @tool decorator and create_sdk_mcp_server() to create a proper
    McpSdkServerConfig that can be passed to ClaudeAgentOptions.mcp_servers.

    Args:
        tool_names: List of Synkora tool names to expose
        runtime_context: Runtime context for credential injection
        server_name: Name for the MCP server (used in tool naming: mcp__<name>__<tool>)

    Returns:
        McpSdkServerConfig dict for Claude Agent SDK
    """
    from claude_agent_sdk import create_sdk_mcp_server, tool

    from src.services.agents.adk_tools import tool_registry

    if runtime_context is not None and runtime_context.tool_registry is not None:
        tool_registry = runtime_context.tool_registry

    # Load tool definitions from registry
    all_tools = tool_registry.list_tools()
    tool_map = {t["name"]: t for t in all_tools}

    sdk_tools = []
    loaded_names = []

    for tool_name in tool_names:
        tool_def = tool_map.get(tool_name)
        if not tool_def:
            logger.warning(f"Tool '{tool_name}' not found in registry, skipping")
            continue

        # Build input schema from tool definition
        parameters = tool_def.get("parameters", {"type": "object", "properties": {}})

        # Create the tool handler with closure over tool_name and runtime_context
        # Each iteration needs its own closure variables
        def _make_handler(t_name: str, ctx: Any):
            async def handler(args: dict[str, Any]) -> dict[str, Any]:
                try:
                    if ctx:
                        result = await tool_registry.execute_tool(t_name, args, runtime_context=ctx)
                    else:
                        result = await tool_registry.execute_tool(t_name, args)

                    # Convert result to MCP content format
                    if isinstance(result, str):
                        return {"content": [{"type": "text", "text": result}]}
                    elif isinstance(result, dict):
                        import json

                        return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}
                    else:
                        return {"content": [{"type": "text", "text": str(result)}]}
                except Exception as e:
                    logger.error(f"Synkora MCP tool '{t_name}' failed: {e}")
                    return {
                        "content": [{"type": "text", "text": f"Error: {e}"}],
                        "is_error": True,
                    }

            return handler

        # Create SDK tool using @tool decorator
        sdk_tool = tool(
            name=tool_name,
            description=tool_def.get("description", f"Synkora tool: {tool_name}"),
            input_schema=parameters,
        )(_make_handler(tool_name, runtime_context))

        sdk_tools.append(sdk_tool)
        loaded_names.append(tool_name)

    logger.info(f"MCP Bridge loaded {len(sdk_tools)} tools: {loaded_names}")

    # Create in-process MCP server
    mcp_server_config = create_sdk_mcp_server(
        name=server_name,
        version="1.0.0",
        tools=sdk_tools,
    )

    logger.info(f"Created MCP server '{server_name}' with {len(sdk_tools)} Synkora tools")

    return mcp_server_config


def get_mcp_tool_names(tool_names: list[str], server_name: str = MCP_SERVER_NAME) -> list[str]:
    """
    Convert Synkora tool names to MCP-format allowed_tools names.

    Claude Agent SDK uses the format: mcp__<server_name>__<tool_name>

    Args:
        tool_names: List of Synkora tool names
        server_name: MCP server name

    Returns:
        List of MCP-formatted tool names for allowed_tools
    """
    return [f"mcp__{server_name}__{name}" for name in tool_names]


def get_default_claude_code_tools() -> list[str]:
    """
    Get the default set of Synkora tools to expose to Claude Code Agent.

    Returns:
        List of tool names suitable for code-focused tasks
    """
    return [
        # File operations
        "internal_read_file",
        "internal_write_file",
        "internal_edit_file",
        "internal_search_files",
        "internal_list_directory",
        "internal_directory_tree",
        "internal_get_file_info",
        "internal_move_file",
        "internal_create_directory",
        # Command execution
        "internal_run_command",
        # Git operations
        "internal_git_get_status",
        "internal_git_create_branch",
        "internal_git_switch_branch",
        "internal_git_list_branches",
        "internal_git_commit_and_push",
        "internal_git_pull_changes",
        "internal_git_get_diff",
        "internal_git_get_commit_history",
        "internal_git_clone_repo",
        "internal_github_create_pr",
        # Database
        "internal_query_database",
        "internal_get_database_schema",
        "internal_list_database_connections",
    ]
