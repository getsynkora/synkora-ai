"""
Google ADK Tools Implementation.

Provides tools that can be used with Google Agent SDK's native function calling.
Supports both built-in tools and external MCP (Model Context Protocol) servers.
"""

import logging
import os
from collections.abc import Callable
from typing import Any

import httpx
from bs4 import BeautifulSoup
from github import Github
from googleapiclient.discovery import build
from sqlalchemy import select

logger = logging.getLogger(__name__)


class ADKToolRegistry:
    """Registry for Google ADK tools."""

    def __init__(self):
        self.tools: dict[str, dict[str, Any]] = {}
        self._register_default_tools()

    def _register_default_tools(self):
        """Register all default tools."""
        # Internal tools
        from src.services.agents.internal_tools import (
            internal_create_directory,
            internal_directory_tree,
            internal_edit_file,
            internal_generate_chart,
            internal_get_database_schema,
            internal_get_file_info,
            internal_glob,
            internal_grep,
            internal_list_database_connections,
            internal_list_directory,
            internal_move_file,
            internal_notebook_edit,
            internal_query_and_chart,
            internal_query_database,
            internal_read_file,
            internal_run_command,
            internal_search_files,
            internal_web_fetch,
            internal_write_file,
        )

        # Google Drive tools - use modular registry
        from src.services.agents.tool_registrations.google_drive_tools_registry import (
            register_google_drive_tools,
        )

        register_google_drive_tools(self)

        # Gmail tools - use modular registry
        from src.services.agents.tool_registrations.gmail_tools_registry import (
            register_gmail_tools,
        )

        register_gmail_tools(self)

        # Mailisk inbox tools - disposable inboxes for browser signup/login tests
        from src.services.agents.tool_registrations.mailisk_tools_registry import (
            register_mailisk_tools,
        )

        register_mailisk_tools(self)

        # Google Calendar tools - use modular registry
        from src.services.agents.tool_registrations.google_calendar_tools_registry import (
            register_google_calendar_tools,
        )

        register_google_calendar_tools(self)

        # Zoom tools - use modular registry
        from src.services.agents.tool_registrations.zoom_tools_registry import register_zoom_tools

        register_zoom_tools(self)

        # Slack tools - use modular registry
        from src.services.agents.tool_registrations.slack_tools_registry import register_slack_tools

        register_slack_tools(self)

        # Elasticsearch tools - use modular registry
        from src.services.agents.tool_registrations.elasticsearch_tools_registry import (
            register_elasticsearch_tools,
        )

        register_elasticsearch_tools(self)

        # Tutorial tools - use modular registry
        from src.services.agents.tool_registrations.tutorial_tools_registry import (
            register_tutorial_tools,
        )

        register_tutorial_tools(self)

        # S3 tools - use modular registry
        from src.services.agents.tool_registrations.storage_tools_registry import (
            register_storage_tools,
        )

        register_storage_tools(self)

        # Contract analysis tools - use modular registry
        from src.services.agents.tool_registrations.contract_tools_registry import (
            register_contract_tools,
        )

        register_contract_tools(self)

        # Followup tools - use modular registry
        from src.services.agents.tool_registrations.followup_tools_registry import (
            register_followup_tools,
        )

        register_followup_tools(self)

        # Interactive user input tools - render forms inside chat
        from src.services.agents.tool_registrations.user_input_tools_registry import (
            register_user_input_tools,
        )

        register_user_input_tools(self)

        # Scheduler tools - use modular registry
        from src.services.agents.tool_registrations.scheduler_tools_registry import (
            register_scheduler_tools,
        )

        register_scheduler_tools(self)

        # Tool Discovery tools - meta-tools for on-demand tool loading (always included)
        from src.services.agents.tool_registrations.tool_discovery_registry import (
            register_tool_discovery_tools,
        )

        register_tool_discovery_tools(self)

        # Data Analysis tools - use modular registry
        from src.services.agents.tool_registrations.data_analysis_tools_registry import (
            register_data_analysis_tools,
        )

        register_data_analysis_tools(self)

        # PR Review tools - use modular registry
        from src.services.agents.tool_registrations.pr_review_tools_registry import (
            register_pr_review_tools,
        )

        register_pr_review_tools(self)

        # ClickUp tools - use modular registry
        from src.services.agents.tool_registrations.clickup_tools_registry import (
            register_clickup_tools,
        )

        register_clickup_tools(self)

        # Jira tools - use modular registry
        from src.services.agents.tool_registrations.jira_tools_registry import register_jira_tools

        register_jira_tools(self)

        # Micromobility tools - use modular registry
        from src.services.agents.tool_registrations.micromobility_tools_registry import (
            register_micromobility_tools,
        )

        register_micromobility_tools(self)

        # Micromobility intelligence tools - computed fleet analytics
        from src.services.agents.tool_registrations.micromobility_intelligence_tools_registry import (
            register_micromobility_intelligence_tools,
        )

        register_micromobility_intelligence_tools(self)

        # Micromobility event impact & IoT intelligence tools
        from src.services.agents.tool_registrations.micromobility_event_tools_registry import (
            register_micromobility_event_tools,
        )

        register_micromobility_event_tools(self)

        # OpenWeather tools - weather forecast and current conditions (requires API key)
        from src.services.agents.tool_registrations.openweather_tools_registry import (
            register_openweather_tools,
        )

        register_openweather_tools(self)

        # Open-Meteo tools - free weather, no API key required
        from src.services.agents.tool_registrations.openmeteo_tools_registry import (
            register_openmeteo_tools,
        )

        register_openmeteo_tools(self)

        # Events tools - PredictHQ and Ticketmaster event discovery
        from src.services.agents.tool_registrations.events_tools_registry import register_events_tools

        register_events_tools(self)

        # Mapbox tools - static maps and directions
        from src.services.agents.tool_registrations.mapbox_tools_registry import register_mapbox_tools

        register_mapbox_tools(self)

        # Document generation tools - use modular registry
        from src.services.agents.tool_registrations.document_tools_registry import (
            register_document_tools,
        )

        register_document_tools(self)

        # Blog site creation tools - use modular registry
        from src.services.agents.tool_registrations.blog_site_tools_registry import (
            register_blog_site_tools,
        )

        register_blog_site_tools(self)

        # Browser automation tools - use modular registry
        from src.services.agents.tool_registrations.browser_tools_registry import (
            register_browser_tools,
        )

        register_browser_tools(self)

        from src.services.agents.tool_registrations.email_tools_registry import register_email_tools

        register_email_tools(self)

        from src.services.agents.tool_registrations.push_notification_tools_registry import (
            register_push_notification_tools,
        )

        register_push_notification_tools(self)

        # Newsletter rendering tools - use modular registry
        from src.services.agents.tool_registrations.newsletter_tools_registry import (
            register_newsletter_tools,
        )

        register_newsletter_tools(self)

        # Role-based agent tools - use modular registry
        from src.services.agents.tool_registrations.role_tools_registry import register_role_tools

        register_role_tools(self)

        # 1Password tools - use modular registry
        from src.services.agents.tool_registrations.onepassword_tools_registry import register_1password_tools

        register_1password_tools(self)

        # YouTube tools - use modular registry
        from src.services.agents.tool_registrations.youtube_tools_registry import register_youtube_tools

        register_youtube_tools(self)

        # Twitter/X tools - use modular registry
        from src.services.agents.tool_registrations.twitter_tools_registry import register_twitter_tools

        register_twitter_tools(self)

        # LinkedIn tools - use modular registry
        from src.services.agents.tool_registrations.linkedin_tools_registry import register_linkedin_tools

        register_linkedin_tools(self)

        # Hacker News tools - use modular registry
        from src.services.agents.tool_registrations.hackernews_tools_registry import register_hackernews_tools

        register_hackernews_tools(self)

        # News tools (NewsAPI + RSS) - use modular registry
        from src.services.agents.tool_registrations.news_tools_registry import register_news_tools

        register_news_tools(self)

        # GitLab tools - use modular registry
        from src.services.agents.tool_registrations.gitlab_tools_registry import register_gitlab_tools

        register_gitlab_tools(self)

        # GitHub Comment tools - use modular registry
        from src.services.agents.tool_registrations.github_comment_tools_registry import (
            register_github_comment_tools,
        )

        register_github_comment_tools(self)

        # GitHub PR Management tools - use modular registry
        from src.services.agents.tool_registrations.github_pr_management_tools_registry import (
            register_github_pr_management_tools,
        )

        register_github_pr_management_tools(self)

        # GitHub Issue tools - use modular registry
        from src.services.agents.tool_registrations.github_issue_tools_registry import (
            register_github_issue_tools,
        )

        register_github_issue_tools(self)

        # GitHub Repo tools - use modular registry
        from src.services.agents.tool_registrations.github_repo_tools_registry import (
            register_github_repo_tools,
        )

        register_github_repo_tools(self)

        # Diagram generation tools - use modular registry
        from src.services.agents.tool_registrations.diagram_tools_registry import (
            register_diagram_tools,
        )

        register_diagram_tools(self)

        # Infographic generation tools
        from src.services.agents.tool_registrations.infographic_tools_registry import (
            register_infographic_tools,
        )

        register_infographic_tools(self)

        # AI image generation tools (DALL-E 3 / Google Imagen 3)
        from src.services.agents.tool_registrations.image_generation_tools_registry import (
            register_image_generation_tools,
        )

        register_image_generation_tools(self)

        # Recall.ai meeting bot tools - use modular registry
        from src.services.agents.tool_registrations.recall_tools_registry import register_recall_tools

        register_recall_tools(self)

        # Spawn agent tools - use modular registry
        from src.services.agents.tool_registrations.spawn_agent_tools_registry import register_spawn_agent_tools

        register_spawn_agent_tools(self)

        # Remote agent tools (A2A / MCP callers) - use modular registry
        from src.services.agents.tool_registrations.remote_agent_tools_registry import register_remote_agent_tools

        register_remote_agent_tools(self)

        # Knowledge base ingest tools - use modular registry
        from src.services.agents.tool_registrations.kb_ingest_tools_registry import register_kb_ingest_tools

        register_kb_ingest_tools(self)

        # Multi-agent transfer tool
        self.register_tool(
            name="transfer_to_agent",
            description="Transfer control to another agent in the system. Use this to delegate tasks to specialized agents based on their descriptions and capabilities.",
            parameters={
                "type": "object",
                "properties": {
                    "agent_name": {"type": "string", "description": "Name of the agent to transfer to"},
                    "task": {"type": "string", "description": "Task description to pass to the target agent"},
                },
                "required": ["agent_name", "task"],
            },
            function=transfer_to_agent,
        )

        self.register_tool(
            name="internal_read_file",
            description="""Read a file and return its content. Automatically detects file type based on extension.

IMPORTANT: All file paths must be within the workspace directory. The workspace path is provided in your context. Always use paths like: {workspace_path}/files/example.txt or {workspace_path}/repos/project/file.py

TIP FOR LARGE FILES: If a file is large (>300 lines) and you're looking for specific code, use internal_grep first
with path=<file_path> and a pattern matching the function/class/variable you need. This finds the exact line numbers
instantly, then you can read just that section with start_line + max_lines. Avoid reading the same large file
multiple times in overlapping chunks — use grep to locate what you need.

For text files: Returns content as string with token counting and pagination support.
For media files: Returns content as base64 encoded string with MIME type metadata.

Supported text extensions: .txt, .md, .py, .js, .ts, .jsx, .tsx, .json, .xml, .yaml, .yml, .csv, .html, .css, .sql, .sh, .go, .rs, .java, .rb, .php, .c, .cpp, .h, .swift, .toml, .graphql
Supported media extensions: .jpg, .jpeg, .png, .gif, .bmp, .webp, .svg, .mp4, .pdf, .doc, .docx""",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Absolute path to the file (must be within workspace directory)",
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "1-based line number to start reading from (default: 1, only for text files)",
                        "default": 1,
                    },
                    "max_lines": {
                        "type": "integer",
                        "description": "Maximum number of lines to read (0 or None = no limit, only for text files)",
                    },
                },
                "required": ["file_path"],
            },
            function=internal_read_file,
        )

        self.register_tool(
            name="internal_search_files",
            description="""Search for files in a directory matching a regex pattern. Returns list of matching files with their paths and names.

IMPORTANT: Directory path must be within the workspace directory.""",
            parameters={
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Directory to search in (must be within workspace)"},
                    "regex_pattern": {
                        "type": "string",
                        "description": "Regular expression pattern to match file names",
                    },
                },
                "required": ["directory", "regex_pattern"],
            },
            function=internal_search_files,
        )

        # Claude Code-style tools for enhanced code exploration
        self.register_tool(
            name="internal_glob",
            description="""Find files matching a glob pattern within the workspace.

Supports recursive glob patterns like **/*.py, src/**/*.ts, etc.
Returns matching file paths sorted by modification time (most recent first).

IMPORTANT: Path must be within the workspace directory.""",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern to match (e.g. '**/*.py', 'src/**/*.ts', '*.json')",
                    },
                    "path": {
                        "type": "string",
                        "description": "Directory to search in (defaults to workspace root)",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of files to return (default: 1000)",
                        "default": 1000,
                    },
                },
                "required": ["pattern"],
            },
            function=internal_glob,
        )

        self.register_tool(
            name="internal_grep",
            description="""Search file contents for a regex pattern. Works on a single file OR an entire directory tree.

PREFERRED APPROACH FOR LARGE FILES: Instead of reading a large file in chunks with internal_read_file,
use internal_grep with path=<file_path> to instantly find relevant lines by pattern. This is far more
efficient - you get only the lines that match plus a few lines of context, rather than reading hundreds
of lines hoping to find the right section.

Example usage:
- Find a function in a large file: pattern="def myFunction|class MyClass", path="/path/to/file.dart"
- Find all usages of a variable: pattern="totalBalance|balanceProvider", path="/path/to/repo/lib"
- Find imports: pattern="^import.*router", path="/path/to/file.dart", include="*.dart"

Similar to ripgrep - walks the directory tree and searches file contents using regex.
Returns matching files with line numbers and content snippets with context.

IMPORTANT: Path must be within the workspace directory.""",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Regex pattern to search for in file contents",
                    },
                    "path": {
                        "type": "string",
                        "description": "File or directory to search in (defaults to workspace root). Can be a specific file path to search within that file only.",
                    },
                    "include": {
                        "type": "string",
                        "description": "Glob pattern to filter files (e.g. '*.py', '*.ts', '*.dart')",
                    },
                    "case_insensitive": {
                        "type": "boolean",
                        "description": "Case insensitive search (default: false)",
                        "default": False,
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of matches to return (default: 50)",
                        "default": 50,
                    },
                    "context_lines": {
                        "type": "integer",
                        "description": "Number of context lines around each match (default: 2)",
                        "default": 2,
                    },
                },
                "required": ["pattern"],
            },
            function=internal_grep,
        )

        self.register_tool(
            name="internal_web_fetch",
            description="""Fetch content from a URL and return it as text.

Retrieves web page content, converting HTML to clean readable text.
Follows redirects and handles common error cases.
Auto-retries via Jina Reader if a site returns 403/404 (use_reader=true forces Jina).

Use this to fetch documentation, API references, or any web content.""",
            parameters={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL to fetch content from (must be http:// or https://)",
                    },
                    "extract_text": {
                        "type": "boolean",
                        "description": "Extract text from HTML, stripping tags (default: true)",
                        "default": True,
                    },
                    "max_length": {
                        "type": "integer",
                        "description": "Maximum content length to return (default: 50000)",
                        "default": 50000,
                    },
                    "use_reader": {
                        "type": "boolean",
                        "description": "Use Jina Reader proxy for clean markdown output (default: false)",
                        "default": False,
                    },
                    "auto_fallback": {
                        "type": "boolean",
                        "description": "Auto-retry via Jina Reader if site returns 403/404 (default: true)",
                        "default": True,
                    },
                },
                "required": ["url"],
            },
            function=internal_web_fetch,
        )

        self.register_tool(
            name="internal_notebook_edit",
            description="""Edit a Jupyter notebook (.ipynb) cell.

Supports replacing, inserting, or deleting cells in Jupyter notebooks.
Can edit cell content and change cell types (code/markdown).

IMPORTANT: Notebook path must be within the workspace directory.""",
            parameters={
                "type": "object",
                "properties": {
                    "notebook_path": {
                        "type": "string",
                        "description": "Path to the .ipynb file",
                    },
                    "cell_number": {
                        "type": "integer",
                        "description": "0-indexed cell number to edit",
                    },
                    "new_source": {
                        "type": "string",
                        "description": "New source content for the cell (ignored for delete mode)",
                        "default": "",
                    },
                    "cell_type": {
                        "type": "string",
                        "enum": ["code", "markdown"],
                        "description": "Cell type (defaults to existing cell type)",
                    },
                    "edit_mode": {
                        "type": "string",
                        "enum": ["replace", "insert", "delete"],
                        "description": "Edit mode: replace, insert, or delete (default: replace)",
                        "default": "replace",
                    },
                },
                "required": ["notebook_path", "cell_number"],
            },
            function=internal_notebook_edit,
        )

        self.register_tool(
            name="internal_write_file",
            description="""Write content to a file. Creates directories as needed and validates file extensions.

IMPORTANT: All file paths must be within the workspace directory. Use paths like: {workspace_path}/files/example.txt

Supported extensions: .txt, .md, .py, .js, .ts, .jsx, .tsx, .json, .xml, .yaml, .yml, .csv, .html, .css, .sql, .sh, .go, .rs, .java, .rb, .php, .c, .cpp, .h, .swift, .toml, .graphql
Maximum file size: 10MB""",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Absolute path where to write the file (must be within workspace directory)",
                    },
                    "content": {
                        "type": "string",
                        "description": "Complete file content to write",
                    },
                    "encoding": {"type": "string", "description": "File encoding (default: utf-8)", "default": "utf-8"},
                },
                "required": ["file_path", "content"],
            },
            function=internal_write_file,
        )

        self.register_tool(
            name="internal_edit_file",
            description="""Edit a file by searching for a pattern and replacing it with new content.

IMPORTANT: File path must be within the workspace directory.""",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to edit (must be within workspace directory)",
                    },
                    "search_pattern": {"type": "string", "description": "Text pattern to search for"},
                    "replace_with": {"type": "string", "description": "Text to replace the pattern with"},
                },
                "required": ["file_path", "search_pattern", "replace_with"],
            },
            function=internal_edit_file,
        )

        self.register_tool(
            name="internal_get_file_info",
            description="""Get information about a file or directory including size, permissions, and timestamps.

IMPORTANT: Path must be within the workspace directory.""",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file or directory (must be within workspace)",
                    }
                },
                "required": ["file_path"],
            },
            function=internal_get_file_info,
        )

        self.register_tool(
            name="internal_move_file",
            description="""Move or rename a file or directory. Creates destination directories as needed.

IMPORTANT: Both source and destination paths must be within the workspace directory.""",
            parameters={
                "type": "object",
                "properties": {
                    "source_path": {"type": "string", "description": "Source path (must be within workspace)"},
                    "destination_path": {
                        "type": "string",
                        "description": "Destination path (must be within workspace)",
                    },
                },
                "required": ["source_path", "destination_path"],
            },
            function=internal_move_file,
        )

        self.register_tool(
            name="internal_create_directory",
            description="""Create a directory with parent directories as needed.

IMPORTANT: Directory path must be within the workspace directory.""",
            parameters={
                "type": "object",
                "properties": {
                    "directory_path": {
                        "type": "string",
                        "description": "Path of directory to create (must be within workspace)",
                    }
                },
                "required": ["directory_path"],
            },
            function=internal_create_directory,
        )

        self.register_tool(
            name="internal_list_directory",
            description="""List directory contents with file sizes, permissions, and timestamps.

IMPORTANT: Directory path must be within the workspace directory.""",
            parameters={
                "type": "object",
                "properties": {
                    "directory_path": {"type": "string", "description": "Path to directory (must be within workspace)"},
                    "include_hidden": {
                        "type": "boolean",
                        "description": "Whether to include hidden files (default: false)",
                        "default": False,
                    },
                },
                "required": ["directory_path"],
            },
            function=internal_list_directory,
        )

        self.register_tool(
            name="internal_directory_tree",
            description="""Generate a directory tree structure showing hierarchical view of directories and files.

IMPORTANT: Directory path must be within the workspace directory.""",
            parameters={
                "type": "object",
                "properties": {
                    "directory_path": {"type": "string", "description": "Path to directory (must be within workspace)"},
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum depth of directory tree (optional, no limit if not specified)",
                    },
                    "show_hidden": {
                        "type": "boolean",
                        "description": "Whether to include hidden files (default: false)",
                        "default": False,
                    },
                },
                "required": ["directory_path"],
            },
            function=internal_directory_tree,
        )

        # Internal command execution tool
        self.register_tool(
            name="internal_run_command",
            description="""Execute safe command-line operations from an allowlist of development tools.

IMPORTANT: File paths in write commands must be within the workspace directory.

Supports: Git, GitHub CLI, npm, pip, Docker, file operations (ls, cat, mkdir, etc.), and more.""",
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "oneOf": [
                            {"type": "array", "items": {"type": "string"}},
                            {"type": "string"},
                        ],
                        "description": "Command to run (e.g., ['git', 'status']). File paths must be within workspace.",
                    },
                    "working_directory": {
                        "type": "string",
                        "description": "Directory to run command in. Optional - defaults to workspace. Can be any valid directory path.",
                    },
                    "input_text": {"type": "string", "description": "Text to pass to command's stdin (optional)"},
                    "timeout": {
                        "type": "integer",
                        "description": "Command timeout in seconds (default: 300)",
                        "default": 300,
                    },
                },
                "required": ["command"],
            },
            function=internal_run_command,
        )

        # Git tools - use modular registries
        from src.services.agents.tool_registrations.git_branch_tools_registry import register_git_branch_tools
        from src.services.agents.tool_registrations.git_commit_tools_registry import register_git_commit_tools
        from src.services.agents.tool_registrations.git_repo_tools_registry import register_git_repo_tools

        register_git_repo_tools(self)
        register_git_branch_tools(self)
        register_git_commit_tools(self)

        # Internal database tools - create wrappers that extract tenant_id and db_session from _runtime_context
        async def internal_query_database_wrapper(connection_id: str, query: str, config: dict[str, Any] | None = None):
            logger.info(f"[DB Tool] query_database_wrapper called with connection_id={connection_id}")
            logger.debug(f"[DB Tool] Config keys: {list(config.keys()) if config else 'None'}")

            # Extract runtime context from config
            runtime_context = config.get("_runtime_context") if config else None

            tenant_id = None
            db_session = None

            if runtime_context:
                if isinstance(runtime_context, dict):
                    tenant_id = runtime_context.get("tenant_id")
                    db_session = runtime_context.get("db_session")
                else:
                    tenant_id = getattr(runtime_context, "tenant_id", None)
                    db_session = getattr(runtime_context, "db_session", None)

            logger.info(
                f"[DB Tool] Extracted tenant_id={tenant_id}, db_session={'present' if db_session else 'missing'}"
            )

            if not tenant_id or not db_session:
                error_msg = f"Missing tenant_id or db_session in runtime context. tenant_id={tenant_id}, db_session={'present' if db_session else 'missing'}"
                logger.error(f"[DB Tool] {error_msg}")
                return {"success": False, "error": error_msg}

            # Enforce per-agent allowed connections — no attachment means no access
            allowed = getattr(runtime_context, "allowed_database_connections", None) or []
            if not allowed:
                return {
                    "success": False,
                    "error": "No database connections are attached to this agent. "
                    "Attach connections in the agent's Database Connections settings first.",
                }
            if connection_id not in allowed:
                return {
                    "success": False,
                    "error": f"Database connection '{connection_id}' is not attached to this agent. "
                    "Use internal_list_database_connections to see available connections.",
                }

            return await internal_query_database(
                connection_id=connection_id, query=query, tenant_id=tenant_id, db_session=db_session, config=config
            )

        async def internal_list_database_connections_wrapper(config: dict[str, Any] | None = None):
            logger.info("[DB Tool] list_database_connections_wrapper called")
            logger.debug(f"[DB Tool] Config keys: {list(config.keys()) if config else 'None'}")

            # Extract runtime context from config
            runtime_context = config.get("_runtime_context") if config else None

            tenant_id = None
            db_session = None

            if runtime_context:
                if isinstance(runtime_context, dict):
                    tenant_id = runtime_context.get("tenant_id")
                    db_session = runtime_context.get("db_session")
                else:
                    tenant_id = getattr(runtime_context, "tenant_id", None)
                    db_session = getattr(runtime_context, "db_session", None)

            logger.info(
                f"[DB Tool] Extracted tenant_id={tenant_id}, db_session={'present' if db_session else 'missing'}"
            )

            if not tenant_id or not db_session:
                error_msg = f"Missing tenant_id or db_session in runtime context. tenant_id={tenant_id}, db_session={'present' if db_session else 'missing'}"
                logger.error(f"[DB Tool] {error_msg}")
                return {"success": False, "error": error_msg}

            # Enforce per-agent allowed connections list
            allowed = getattr(runtime_context, "allowed_database_connections", None) or []
            if not allowed:
                return {
                    "success": True,
                    "connections": [],
                    "count": 0,
                    "message": "No database connections are attached to this agent. "
                    "Attach connections in the agent's Database Connections settings first.",
                }

            result = await internal_list_database_connections(tenant_id=tenant_id, db_session=db_session, config=config)

            # Filter to only attached connections
            if result.get("success") and allowed:
                result["connections"] = [c for c in result.get("connections", []) if c["id"] in allowed]
                result["count"] = len(result["connections"])

            return result

        async def internal_get_database_schema_wrapper(connection_id: str, config: dict[str, Any] | None = None):
            logger.info(f"[DB Tool] get_database_schema_wrapper called with connection_id={connection_id}")
            logger.debug(f"[DB Tool] Config keys: {list(config.keys()) if config else 'None'}")

            # Extract runtime context from config
            runtime_context = config.get("_runtime_context") if config else None

            tenant_id = None
            db_session = None

            if runtime_context:
                if isinstance(runtime_context, dict):
                    tenant_id = runtime_context.get("tenant_id")
                    db_session = runtime_context.get("db_session")
                else:
                    tenant_id = getattr(runtime_context, "tenant_id", None)
                    db_session = getattr(runtime_context, "db_session", None)

            logger.info(
                f"[DB Tool] Extracted tenant_id={tenant_id}, db_session={'present' if db_session else 'missing'}"
            )

            if not tenant_id or not db_session:
                error_msg = f"Missing tenant_id or db_session in runtime context. tenant_id={tenant_id}, db_session={'present' if db_session else 'missing'}"
                logger.error(f"[DB Tool] {error_msg}")
                return {"success": False, "error": error_msg}

            return await internal_get_database_schema(
                connection_id=connection_id, tenant_id=tenant_id, db_session=db_session, config=config
            )

        async def internal_generate_chart_wrapper(
            query_result: dict[str, Any],
            title: str,
            chart_type: str | None = None,
            description: str | None = None,
            config: dict[str, Any] | None = None,
        ):
            logger.info(f"[Chart Tool] generate_chart_wrapper called with title={title}")
            logger.debug(f"[Chart Tool] Config keys: {list(config.keys()) if config else 'None'}")

            # Extract runtime context from config
            runtime_context = config.get("_runtime_context") if config else None

            tenant_id = None
            agent_id = None
            db_session = None
            conversation_id = None
            message_id = None

            if runtime_context:
                if isinstance(runtime_context, dict):
                    tenant_id = runtime_context.get("tenant_id")
                    agent_id = runtime_context.get("agent_id")
                    db_session = runtime_context.get("db_session")
                    conversation_id = runtime_context.get("conversation_id")
                    message_id = runtime_context.get("message_id")
                else:
                    tenant_id = getattr(runtime_context, "tenant_id", None)
                    agent_id = getattr(runtime_context, "agent_id", None)
                    db_session = getattr(runtime_context, "db_session", None)
                    conversation_id = getattr(runtime_context, "conversation_id", None)
                    message_id = getattr(runtime_context, "message_id", None)

            logger.info(
                f"[Chart Tool] Extracted tenant_id={tenant_id}, agent_id={agent_id}, db_session={'present' if db_session else 'missing'}"
            )

            if not tenant_id or not agent_id or not db_session:
                error_msg = f"Missing required fields in runtime context. tenant_id={tenant_id}, agent_id={agent_id}, db_session={'present' if db_session else 'missing'}"
                logger.error(f"[Chart Tool] {error_msg}")
                return {"success": False, "error": error_msg}

            return await internal_generate_chart(
                query_result=query_result,
                chart_type=chart_type,
                title=title,
                agent_id=agent_id,
                tenant_id=tenant_id,
                db_session=db_session,
                conversation_id=conversation_id,
                message_id=message_id,
                description=description,
                config=config,
            )

        async def internal_query_and_chart_wrapper(
            connection_id: str,
            query: str,
            chart_title: str,
            chart_type: str | None = None,
            chart_description: str | None = None,
            config: dict[str, Any] | None = None,
        ):
            logger.info(
                f"[Chart Tool] query_and_chart_wrapper called with connection_id={connection_id}, title={chart_title}"
            )
            logger.debug(f"[Chart Tool] Config keys: {list(config.keys()) if config else 'None'}")

            # Extract runtime context from config
            runtime_context = config.get("_runtime_context") if config else None

            tenant_id = None
            agent_id = None
            db_session = None
            conversation_id = None
            message_id = None

            if runtime_context:
                if isinstance(runtime_context, dict):
                    tenant_id = runtime_context.get("tenant_id")
                    agent_id = runtime_context.get("agent_id")
                    db_session = runtime_context.get("db_session")
                    conversation_id = runtime_context.get("conversation_id")
                    message_id = runtime_context.get("message_id")
                else:
                    tenant_id = getattr(runtime_context, "tenant_id", None)
                    agent_id = getattr(runtime_context, "agent_id", None)
                    db_session = getattr(runtime_context, "db_session", None)
                    conversation_id = getattr(runtime_context, "conversation_id", None)
                    message_id = getattr(runtime_context, "message_id", None)

            logger.info(
                f"[Chart Tool] Extracted tenant_id={tenant_id}, agent_id={agent_id}, db_session={'present' if db_session else 'missing'}"
            )

            if not tenant_id or not agent_id or not db_session:
                error_msg = f"Missing required fields in runtime context. tenant_id={tenant_id}, agent_id={agent_id}, db_session={'present' if db_session else 'missing'}"
                logger.error(f"[Chart Tool] {error_msg}")
                return {"success": False, "error": error_msg}

            return await internal_query_and_chart(
                connection_id=connection_id,
                query=query,
                chart_title=chart_title,
                tenant_id=tenant_id,
                agent_id=agent_id,
                db_session=db_session,
                chart_type=chart_type,
                conversation_id=conversation_id,
                message_id=message_id,
                chart_description=chart_description,
                config=config,
            )

        self.register_tool(
            name="internal_query_database",
            description=(
                "Execute a SQL (or Elasticsearch DSL / PostgREST JSON) query on a connected "
                "database. Returns rows, row count, and column names.\n\n"
                "DATABASE-TYPE RULES:\n"
                "• PostgreSQL / MySQL / DuckDB / SQLite / BigQuery / Snowflake / ClickHouse / SQLServer:\n"
                "  Use standard SQL. For large tables prefer aggregation over SELECT *.\n"
                "  LARGE-TABLE RULES:\n"
                "  1. NEVER write SELECT * without LIMIT on any table not confirmed small (< 1 000 rows).\n"
                "  2. For analysis (totals, averages, trends): use GROUP BY + COUNT/SUM/AVG/MIN/MAX.\n"
                "     • Count by status:  SELECT status, COUNT(*) FROM orders GROUP BY status\n"
                "     • Daily trend:      SELECT DATE(created_at), COUNT(*) FROM events GROUP BY 1 ORDER BY 1\n"
                "     • Top N:            SELECT user_id, SUM(amount) FROM payments GROUP BY user_id ORDER BY 2 DESC LIMIT 10\n"
                "  3. For sampling: SELECT * FROM table LIMIT 100\n"
                "  4. Broad SELECT * on tables > 50 000 rows is automatically blocked.\n\n"
                "• Supabase (PostgREST):\n"
                "  Supports simple aggregates: COUNT(*), MAX(col), MIN(col), SUM(col), AVG(col) with GROUP BY.\n"
                "  Supports SQL syntax or JSON format:\n"
                "  SQL (aggregates): SELECT binary_user_id, COUNT(*) AS errors FROM migration_queue GROUP BY binary_user_id ORDER BY errors DESC\n"
                "  SQL (filtered):   SELECT id, name FROM users WHERE status = 'active' LIMIT 100\n"
                '  JSON:             {"table": "users", "select": "id,name,status", "eq": {"status": "active"}, "limit": 100}\n'
                "  Does NOT support: EXTRACT, DATE_TRUNC, CAST, CASE, COALESCE — use RPC for those:\n"
                '  RPC:   {"rpc": "my_function", "params": {}}\n\n'
                "• Elasticsearch: Use Elasticsearch DSL JSON.\n"
                "• MongoDB: Use MongoDB query JSON."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "connection_id": {"type": "string", "description": "UUID of the database connection to use"},
                    "query": {
                        "type": "string",
                        "description": (
                            "SQL query to execute. Must use aggregation (GROUP BY / COUNT / SUM / AVG) "
                            "for large tables. Add LIMIT ≤ 1000 when fetching raw rows. "
                            "Elasticsearch connections accept DSL JSON instead of SQL."
                        ),
                    },
                },
                "required": ["connection_id", "query"],
            },
            function=internal_query_database_wrapper,
        )

        self.register_tool(
            name="internal_list_database_connections",
            description="List all active database connections available to the agent. Returns connection details including name, type, host, and database.",
            parameters={"type": "object", "properties": {}, "required": []},
            function=internal_list_database_connections_wrapper,
        )

        self.register_tool(
            name="internal_get_database_schema",
            description="Get schema information for a database connection. Returns tables/indices, columns, and data types to help understand the database structure.",
            parameters={
                "type": "object",
                "properties": {"connection_id": {"type": "string", "description": "UUID of the database connection"}},
                "required": ["connection_id"],
            },
            function=internal_get_database_schema_wrapper,
        )

        self.register_tool(
            name="internal_generate_chart",
            description='Generate a chart visualization from pre-aggregated data. IMPORTANT: After calling this tool the chart is automatically rendered in the UI — do NOT embed any image URL or markdown image syntax in your response. Simply describe the chart you created. IMPORTANT: query_result must contain PRE-AGGREGATED data, NOT raw API records. Raw records (e.g. individual trips with id/pick_up_time fields) will be rejected. You must aggregate the data first: fetch records, group/count them by the desired dimension (e.g. by date, by status), then pass the aggregated list. The aggregated data must be a list of rows with exactly 2 columns: column 1 = label (x-axis, e.g. date string), column 2 = numeric value (y-axis, e.g. count). Example: query_result=[{"date": "2026-04-20", "trips": 15}, {"date": "2026-04-21", "trips": 12}]. For flat summary stats (e.g. {"total": 276, "pending": 216}), pass the dict directly — it will be auto-converted.',
            parameters={
                "type": "object",
                "properties": {
                    "query_result": {
                        "type": "object",
                        "description": "Pre-aggregated chart data. Either: (a) a list of 2-column rows [{label_col: x, value_col: numeric_y}, ...], or (b) a flat dict of {label: numeric_value} pairs for summary stats. Do NOT pass raw API list responses with many columns — aggregate first.",
                    },
                    "chart_type": {
                        "type": "string",
                        "description": "Type of chart: line, bar, pie, doughnut, scatter, bubble, radar, polarArea (optional, auto-detected if not provided)",
                        "enum": ["line", "bar", "pie", "doughnut", "scatter", "bubble", "radar", "polarArea"],
                    },
                    "title": {"type": "string", "description": "Chart title"},
                    "description": {"type": "string", "description": "Optional chart description"},
                },
                "required": ["query_result", "title"],
            },
            function=internal_generate_chart_wrapper,
        )

        self.register_tool(
            name="internal_query_and_chart",
            description="Execute a database query and automatically generate a chart from the results in one step. Combines query execution and visualization. IMPORTANT: After calling this tool the chart is automatically rendered in the UI — do NOT embed any image URL or markdown image syntax in your response. Simply describe the chart you created.",
            parameters={
                "type": "object",
                "properties": {
                    "connection_id": {"type": "string", "description": "UUID of the database connection to use"},
                    "query": {"type": "string", "description": "SQL query or Elasticsearch DSL query to execute"},
                    "chart_title": {"type": "string", "description": "Title for the generated chart"},
                    "chart_type": {
                        "type": "string",
                        "description": "Type of chart (optional, auto-detected if not provided)",
                        "enum": ["line", "bar", "pie", "doughnut", "scatter", "bubble", "radar", "polarArea"],
                    },
                    "chart_description": {"type": "string", "description": "Optional chart description"},
                },
                "required": ["connection_id", "query", "chart_title"],
            },
            function=internal_query_and_chart_wrapper,
        )

        # Web tools
        self.register_tool(
            name="web_search",
            description="Search the web using Google Search. Returns top search results with titles, URLs, and snippets.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"},
                    "num_results": {
                        "type": "integer",
                        "description": "Number of results to return (default: 5)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
            function=web_search,
        )

        self.register_tool(
            name="web_crawl",
            description="Crawl and extract content from a web page. Returns the main text content, title, and metadata.",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to crawl"},
                    "extract_links": {
                        "type": "boolean",
                        "description": "Whether to extract links from the page",
                        "default": False,
                    },
                },
                "required": ["url"],
            },
            function=web_crawl,
        )

        # GitHub composite tool (provides all GitHub functionality through one tool)
        self.register_tool(
            name="github",
            description="Access GitHub functionality including searching repositories, getting repo info, listing issues/PRs, creating issues, getting user information, and listing authenticated user's repositories. Specify the action you want to perform.",
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "The GitHub action to perform",
                        "enum": [
                            "search_repos",
                            "get_repo",
                            "list_issues",
                            "create_issue",
                            "list_pull_requests",
                            "get_user",
                            "list_my_repos",
                        ],
                    },
                    "query": {"type": "string", "description": "Search query (for search_repos action)"},
                    "owner": {"type": "string", "description": "Repository owner username (for repo-specific actions)"},
                    "repo": {"type": "string", "description": "Repository name (for repo-specific actions)"},
                    "username": {"type": "string", "description": "GitHub username (for get_user action)"},
                    "title": {"type": "string", "description": "Issue title (for create_issue action)"},
                    "body": {"type": "string", "description": "Issue body/description (for create_issue action)"},
                    "labels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of label names (for create_issue action)",
                        "default": [],
                    },
                    "state": {
                        "type": "string",
                        "description": "State filter: open, closed, all (for list_issues and list_pull_requests)",
                        "enum": ["open", "closed", "all"],
                        "default": "open",
                    },
                    "sort": {
                        "type": "string",
                        "description": "Sort by: stars, forks, updated (for search_repos)",
                        "enum": ["stars", "forks", "updated"],
                        "default": "stars",
                    },
                    "limit": {"type": "integer", "description": "Number of results to return", "default": 10},
                },
                "required": ["action"],
            },
            function=github_composite,
            requires_auth="github",  # NEW: Mark tool as requiring GitHub auth
        )

        # GitHub individual tools (kept for backward compatibility)
        self.register_tool(
            name="github_search_repos",
            description="Search GitHub repositories. Returns repository information including name, description, stars, and URL.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (e.g., 'machine learning python')"},
                    "sort": {
                        "type": "string",
                        "description": "Sort by: stars, forks, updated",
                        "enum": ["stars", "forks", "updated"],
                        "default": "stars",
                    },
                    "limit": {"type": "integer", "description": "Number of results to return", "default": 5},
                },
                "required": ["query"],
            },
            function=github_search_repos,
            requires_auth="github",  # NEW
        )

        self.register_tool(
            name="github_get_repo",
            description="Get detailed information about a specific GitHub repository.",
            parameters={
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner username"},
                    "repo": {"type": "string", "description": "Repository name"},
                },
                "required": ["owner", "repo"],
            },
            function=github_get_repo,
            requires_auth="github",  # NEW
        )

        self.register_tool(
            name="github_list_issues",
            description="List issues from a GitHub repository.",
            parameters={
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner username"},
                    "repo": {"type": "string", "description": "Repository name"},
                    "state": {
                        "type": "string",
                        "description": "Issue state: open, closed, all",
                        "enum": ["open", "closed", "all"],
                        "default": "open",
                    },
                    "limit": {"type": "integer", "description": "Number of issues to return", "default": 10},
                },
                "required": ["owner", "repo"],
            },
            function=github_list_issues,
            requires_auth="github",  # NEW
        )

        self.register_tool(
            name="github_create_issue",
            description="Create a new issue in a GitHub repository. Requires authentication.",
            parameters={
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner username"},
                    "repo": {"type": "string", "description": "Repository name"},
                    "title": {"type": "string", "description": "Issue title"},
                    "body": {"type": "string", "description": "Issue description/body"},
                    "labels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of label names",
                        "default": [],
                    },
                },
                "required": ["owner", "repo", "title"],
            },
            function=github_create_issue,
            requires_auth="github",  # NEW
        )

        self.register_tool(
            name="github_list_pull_requests",
            description="List pull requests from a GitHub repository.",
            parameters={
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repository owner username"},
                    "repo": {"type": "string", "description": "Repository name"},
                    "state": {
                        "type": "string",
                        "description": "PR state: open, closed, all",
                        "enum": ["open", "closed", "all"],
                        "default": "open",
                    },
                    "limit": {"type": "integer", "description": "Number of PRs to return", "default": 10},
                },
                "required": ["owner", "repo"],
            },
            function=github_list_pull_requests,
            requires_auth="github",  # NEW
        )

        self.register_tool(
            name="github_get_user",
            description="Get information about a GitHub user.",
            parameters={
                "type": "object",
                "properties": {"username": {"type": "string", "description": "GitHub username"}},
                "required": ["username"],
            },
            function=github_get_user,
            requires_auth="github",  # NEW
        )

        # Gmail tools are registered via gmail_tools_registry.py
        # with full OAuth support and comprehensive functionality

        # YouTube tools
        self.register_tool(
            name="youtube_search",
            description="Search YouTube videos. Returns video titles, descriptions, URLs, and view counts.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "description": "Maximum number of results", "default": 5},
                },
                "required": ["query"],
            },
            function=youtube_search,
        )

        self.register_tool(
            name="youtube_get_video_info",
            description="Get detailed information about a YouTube video.",
            parameters={
                "type": "object",
                "properties": {"video_id": {"type": "string", "description": "YouTube video ID"}},
                "required": ["video_id"],
            },
            function=youtube_get_video_info,
        )

    def register_tool(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        function: Callable,
        requires_auth: str | None = None,  # NEW PARAMETER
        tool_category: str | None = None,  # "action" | "read" | None
    ):
        """Register a new tool with optional auth requirement and category."""
        self.tools[name] = {
            "name": name,
            "description": description,
            "parameters": parameters,
            "function": function,
            "requires_auth": requires_auth,  # Store auth requirement
            "tool_category": tool_category,  # Used by HITL approval gate
        }
        auth_info = f" (requires_auth: {requires_auth})" if requires_auth else ""
        logger.info(f"Registered tool: {name}{auth_info}")

    def get_tool(self, name: str) -> dict[str, Any] | None:
        """Get a tool by name."""
        return self.tools.get(name)

    def list_tools(self) -> list[dict[str, Any]]:
        """List all registered tools."""
        return [
            {"name": tool["name"], "description": tool["description"], "parameters": tool["parameters"]}
            for tool in self.tools.values()
        ]

    async def execute_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        runtime_context: "RuntimeContext" = None,  # NEW PARAMETER
        config: dict[str, Any] | None = None,  # Keep for backward compatibility
    ) -> Any:
        """
        Execute a tool with automatic credential injection.

        Args:
            name: Tool name
            arguments: Tool arguments (NO credentials)
            runtime_context: Runtime execution context (NEW)
            config: Legacy config dict (for backward compatibility)
        """
        tool = self.get_tool(name)
        if not tool:
            raise ValueError(f"Tool not found: {name}")

        # Guard: if runtime_context has an assigned tool list, reject calls for unassigned tools
        if runtime_context is not None and runtime_context.all_available_tools is not None:
            assigned_names = {t["name"] for t in runtime_context.all_available_tools}
            if name not in assigned_names:
                logger.warning(
                    f"Blocked attempt to execute unassigned tool '{name}' for agent {runtime_context.agent_id}"
                )
                return {"success": False, "error": f"Tool '{name}' is not assigned to this agent."}

        try:
            # VALIDATE REQUIRED PARAMETERS FIRST - before any execution
            tool_params = tool.get("parameters", {})
            required_params = tool_params.get("required", [])

            # Check if any required parameters are missing
            missing_params = [param for param in required_params if param not in arguments]

            if missing_params:
                error_msg = f"Missing required parameter(s) for tool '{name}': {', '.join(missing_params)}"
                logger.info(f"❌ {error_msg}")
                logger.debug(f"   Tool: {name}")
                logger.debug(f"   Provided arguments: {list(arguments.keys()) if arguments else '(empty)'}")
                logger.debug(f"   Required parameters: {required_params}")

                # Return detailed error that will help LLM fix the call
                properties = tool_params.get("properties", {})
                param_descriptions = {}
                for param in required_params:
                    if param in properties:
                        param_descriptions[param] = properties[param].get("description", "No description")

                # Build explicit hint showing what was provided vs expected
                provided_keys = list(arguments.keys()) if arguments else []
                hint = f"You provided parameters: {provided_keys}. Required parameters are: {required_params}. Please call {name} again using the exact parameter names listed in 'required_parameters'."

                return {
                    "error": error_msg,
                    "tool_name": name,
                    "missing_parameters": missing_params,
                    "required_parameters": required_params,
                    "provided_parameters": provided_keys,
                    "parameter_descriptions": param_descriptions,
                    "hint": hint,
                }

            # NEW: Handle credential injection if runtime_context provided
            if runtime_context:
                logger.info(f"🔧 [execute_tool] Tool '{name}' - runtime_context provided")
                logger.info(
                    f"🔧 [execute_tool] runtime_context attributes: tenant_id={runtime_context.tenant_id}, agent_id={runtime_context.agent_id}, llm_client={'present' if runtime_context.llm_client else 'MISSING'}"
                )

                from src.services.agents.credential_resolver import CredentialResolver
                from src.services.agents.runtime_context import set_authenticated_client

                # Check if tool requires authentication
                auth_type = tool.get("requires_auth")

                if auth_type:
                    logger.info(f"🔐 Tool '{name}' requires authentication: {auth_type}")

                    # Create credential resolver
                    resolver = CredentialResolver(runtime_context)

                    # Resolve and inject authenticated client
                    client = await resolver.resolve_for_tool(name, auth_type)

                    if client:
                        set_authenticated_client(auth_type, client)
                        logger.info(f"✅ Injected {auth_type} client for tool '{name}'")
                    else:
                        logger.warning(f"⚠️  No {auth_type} credentials configured for tool '{name}'")

                # IMPORTANT: For tools that need runtime_context (like tutorial tools),
                # we need to pass it via config dict
                config = config or {}
                config["_runtime_context"] = runtime_context
                config["_tool_name"] = name  # Add tool name for credential lookup
                # Use only the agent's assigned tools for discovery; fall back to full registry
                config["_all_available_tools"] = (
                    runtime_context.all_available_tools
                    if runtime_context.all_available_tools is not None
                    else self.list_tools()
                )
                logger.info(f"🔧 [execute_tool] Added runtime_context and tool_name '{name}' to config")

                # HITL: Check approval gate before executing action tools
                gate_result = await _check_approval_gate(name, tool, arguments, runtime_context)
                if gate_result is not None:
                    return gate_result

                # Execute tool with config that contains runtime_context
                result = await tool["function"](config=config, **arguments)
                return result

            # LEGACY: Old behavior for backward compatibility
            else:
                logger.info(f"🔧 [execute_tool] Tool '{name}' - NO runtime_context (legacy mode)")
                # Pass config to the tool function (old way)
                config = config or {}
                config["_all_available_tools"] = self.list_tools()  # For tool discovery
                result = await tool["function"](config=config, **arguments)
                return result

        except TypeError as e:
            # Handle TypeError specifically (usually means wrong arguments)
            error_str = str(e)
            logger.info(f"TypeError in tool execution ({name}): {error_str}")
            logger.debug(f"   Provided arguments: {list(arguments.keys()) if arguments else '(empty)'}")

            # Extract missing parameter from error message if possible
            if "missing" in error_str and "required positional argument" in error_str:
                import re

                match = re.search(r"'(\w+)'", error_str)
                param_name = match.group(1) if match else "unknown"

                return {
                    "error": f"Tool '{name}' is missing required parameter: {param_name}",
                    "tool_name": name,
                    "type_error": error_str,
                    "hint": f"Please call {name} again with the required '{param_name}' parameter.",
                }

            return {
                "error": f"Parameter error for tool '{name}': {error_str}",
                "tool_name": name,
                "provided_arguments": list(arguments.keys()) if arguments else [],
                "hint": "Check the tool's parameter requirements and try again.",
            }

        except Exception as e:
            logger.error(f"Tool execution error ({name}): {e}", exc_info=True)
            return {"error": str(e), "tool_name": name}

    async def load_agent_custom_tools(self, agent_id: str, db: Any):
        """
        Load custom tools (OpenAPI-based) attached to an agent.

        Args:
            agent_id: Agent ID (UUID as string)
            db: Database session
        """
        try:
            from uuid import UUID

            from src.models import AgentTool, CustomTool
            from src.services.custom_tools import OpenAPIParser, ToolExecutor

            # Get agent's custom tools
            agent_uuid = UUID(agent_id)
            result = await db.execute(
                select(AgentTool).filter(
                    AgentTool.agent_id == agent_uuid, AgentTool.enabled, AgentTool.custom_tool_id.isnot(None)
                )
            )
            agent_tools = list(result.scalars().all())

            if not agent_tools:
                logger.info(f"No custom tools attached to agent {agent_id}")
                return

            logger.info(f"Loading custom tools for agent {agent_id}, found {len(agent_tools)} tool operations")

            # Load all required CustomTool rows in a single IN query (avoids N+1).
            unique_custom_tool_ids = list({at.custom_tool_id for at in agent_tools if at.custom_tool_id})
            ct_result = await db.execute(
                select(CustomTool).filter(CustomTool.id.in_(unique_custom_tool_ids), CustomTool.enabled)
            )
            custom_tools_by_id = {ct.id: ct for ct in ct_result.scalars().all()}

            custom_tools_map = {}
            for agent_tool in agent_tools:
                ct_id = agent_tool.custom_tool_id
                if ct_id is None:
                    continue
                custom_tool = custom_tools_by_id.get(ct_id)
                if custom_tool and ct_id not in custom_tools_map:
                    custom_tools_map[ct_id] = {"custom_tool": custom_tool, "operations": []}

                # Add this operation to the list
                if ct_id in custom_tools_map:
                    custom_tools_map[ct_id]["operations"].append(
                        {
                            "operation_id": agent_tool.operation_id,
                            "tool_name": agent_tool.tool_name,
                            "config": agent_tool.config or {},
                        }
                    )

            # Register tools for each custom tool
            for _custom_tool_id, tool_data in custom_tools_map.items():
                custom_tool = tool_data["custom_tool"]
                operations = tool_data["operations"]

                try:
                    # Create parser for this custom tool
                    parser = OpenAPIParser(schema=custom_tool.openapi_schema, server_url=custom_tool.server_url)

                    # Create executor for this custom tool
                    executor = ToolExecutor(
                        parser=parser, auth_type=custom_tool.auth_type, auth_config=custom_tool.auth_config
                    )

                    # Register each operation as a separate tool
                    for op in operations:
                        operation_id = op["operation_id"]
                        tool_name = op["tool_name"]

                        # Get operation definition from parser
                        operation_def = parser.get_tool_definition(operation_id)

                        if not operation_def:
                            logger.warning(f"Operation {operation_id} not found in custom tool {custom_tool.name}")
                            continue

                        # Convert OpenAPI parameters array to JSON Schema object format
                        parameters_schema = self._convert_openapi_params_to_schema(operation_def)

                        # Create wrapper function for this operation
                        def create_custom_tool_wrapper(exec, op_id, op_def):
                            async def custom_tool_wrapper(config: dict[str, Any] | None = None, **kwargs):
                                try:
                                    # Execute the operation
                                    result = await exec.execute(op_id, kwargs)
                                    return result
                                except Exception as e:
                                    logger.warning(f"Custom tool execution error ({op_id}): {e}")
                                    return {"error": str(e)}

                            return custom_tool_wrapper

                        # Register the tool
                        self.register_tool(
                            name=tool_name,
                            description=operation_def.get("description", f"{custom_tool.name} - {operation_id}"),
                            parameters=parameters_schema,
                            function=create_custom_tool_wrapper(executor, operation_id, operation_def),
                        )

                        logger.info(f"Registered custom tool operation: {tool_name}")

                    logger.info(f"Loaded {len(operations)} operations from custom tool: {custom_tool.name}")

                except Exception as e:
                    logger.error(f"Failed to load custom tool {custom_tool.name}: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Failed to load agent custom tools: {e}", exc_info=True)

    def _convert_openapi_params_to_schema(self, operation_def: dict[str, Any]) -> dict[str, Any]:
        """
        Convert OpenAPI parameters array to JSON Schema object format.

        OpenAPI returns parameters as an array like:
        [{"name": "location", "in": "query", "schema": {"type": "string"}, "required": True}]

        But LLMs expect JSON Schema format like:
        {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "..."}
            },
            "required": ["location"]
        }

        Args:
            operation_def: Operation definition from OpenAPI parser

        Returns:
            JSON Schema formatted parameters object
        """
        parameters = operation_def.get("parameters", [])
        request_body = operation_def.get("request_body")

        properties = {}
        required = []

        # Process parameters (query, path, header, cookie)
        for param in parameters:
            param_name = param.get("name")
            if not param_name:
                continue

            # Get schema from parameter
            param_schema = param.get("schema", {})

            # Build property definition
            prop_def = {"type": param_schema.get("type", "string"), "description": param.get("description", "")}

            # Add other schema properties if present
            if "enum" in param_schema:
                prop_def["enum"] = param_schema["enum"]
            if "default" in param_schema:
                prop_def["default"] = param_schema["default"]
            if "format" in param_schema:
                prop_def["format"] = param_schema["format"]
            if "items" in param_schema:
                prop_def["items"] = param_schema["items"]

            properties[param_name] = prop_def

            # Track required parameters
            if param.get("required", False):
                required.append(param_name)

        # Process request body if present
        if request_body:
            body_schema = request_body.get("schema", {})

            # If the body schema has properties, merge them
            if "properties" in body_schema:
                for prop_name, prop_def in body_schema["properties"].items():
                    properties[prop_name] = prop_def

                # Add required fields from body schema
                if "required" in body_schema:
                    required.extend(body_schema["required"])
            else:
                # If no properties, add the whole body as a single parameter
                properties["body"] = body_schema
                if request_body.get("required", False):
                    required.append("body")

        # Build final schema
        schema = {"type": "object", "properties": properties}

        if required:
            schema["required"] = required

        return schema

    async def load_agent_mcp_tools(self, agent_id: str, db: Any):
        """
        Load tools from MCP servers attached to an agent.

        Respects the enabled_tools configuration in AgentMCPServer.mcp_config.
        If enabled_tools is empty or null, all tools are loaded.

        Args:
            agent_id: Agent ID (UUID as string)
            db: Database session
        """
        try:
            from uuid import UUID

            from sqlalchemy.orm import selectinload

            from src.models import AgentMCPServer
            from src.services.mcp import mcp_client_manager

            # Get agent's MCP server associations with config (eager-load mcp_server to avoid lazy load in async)
            agent_uuid = UUID(agent_id)
            result = await db.execute(
                select(AgentMCPServer)
                .filter(AgentMCPServer.agent_id == agent_uuid, AgentMCPServer.is_active)
                .options(selectinload(AgentMCPServer.mcp_server))
            )
            associations = list(result.scalars().all())

            if not associations:
                logger.info(f"No MCP servers attached to agent {agent_id}")
                return

            logger.info(f"Loading MCP tools for agent {agent_id}, found {len(associations)} MCP server associations")

            # Get the single MCP client that manages all servers for this agent
            client = await mcp_client_manager.get_agent_client(agent_id=agent_uuid, db=db)

            if not client:
                logger.warning(f"No MCP client available for agent {agent_id}")
                return

            registered_tool_names: list[str] = []

            # Load tools from each MCP server
            for assoc in associations:
                try:
                    server_name = assoc.mcp_server.name

                    # Discover all available tools from this specific server
                    all_tools = await client.discover_tools(server_name=server_name)

                    # Get enabled_tools from mcp_config
                    enabled_tools = assoc.mcp_config.get("enabled_tools", []) if assoc.mcp_config else []

                    # Filter tools based on enabled_tools config
                    tools_to_register = []
                    for tool_def in all_tools:
                        # FastMCP returns Tool objects with attributes
                        tool_name = tool_def.name if hasattr(tool_def, "name") else str(tool_def)

                        # If enabled_tools is specified and not empty, only register tools in the list
                        if enabled_tools:
                            # FastMCP adds server name prefix in multi-server mode
                            # Database stores tool names without prefix, so we need to check both:
                            # 1. Tool name with prefix (e.g., "GitHub_list_branches")
                            # 2. Tool name without prefix (e.g., "list_branches")

                            # Try to match with prefix removed
                            tool_name_without_prefix = tool_name

                            # Remove exact server name prefix (e.g., "GitHub_")
                            exact_prefix = f"{server_name}_"
                            if tool_name.startswith(exact_prefix):
                                tool_name_without_prefix = tool_name[len(exact_prefix) :]

                            # Check if either the full name or name without prefix is in enabled_tools
                            if tool_name not in enabled_tools and tool_name_without_prefix not in enabled_tools:
                                logger.debug(f"Skipping tool {tool_name} - not in enabled_tools list")
                                continue

                        tools_to_register.append(tool_def)

                    # Register filtered tools
                    for tool_def in tools_to_register:
                        # FastMCP returns Tool objects with attributes
                        tool_name = tool_def.name if hasattr(tool_def, "name") else str(tool_def)
                        tool_description = tool_def.description if hasattr(tool_def, "description") else ""
                        tool_input_schema = tool_def.inputSchema if hasattr(tool_def, "inputSchema") else {}

                        # Create a wrapper function that captures the client and tool name
                        def create_mcp_tool_wrapper(mcp_client, mcp_tool_name, mcp_server_name):
                            async def mcp_tool_wrapper(config: dict[str, Any] | None = None, **kwargs):
                                try:
                                    # Use the tool name as-is when calling MCP server
                                    result = await mcp_client.execute_tool(
                                        tool_name=mcp_tool_name, arguments=kwargs, server_name=mcp_server_name
                                    )

                                    # Extract content from CallToolResult object
                                    # FastMCP returns CallToolResult with content array
                                    if hasattr(result, "content") and result.content:
                                        # Extract text from content array
                                        content_parts = []
                                        for content_item in result.content:
                                            if hasattr(content_item, "text"):
                                                content_parts.append(content_item.text)
                                            elif hasattr(content_item, "type") and content_item.type == "text":
                                                content_parts.append(str(content_item))

                                        # If we extracted text, return it
                                        if content_parts:
                                            combined_text = "\n".join(content_parts)
                                            # Try to parse as JSON if it looks like JSON
                                            try:
                                                import json

                                                return json.loads(combined_text)
                                            except (json.JSONDecodeError, ValueError):
                                                # Not JSON, return as text
                                                return {"result": combined_text}

                                    if isinstance(result, dict):
                                        return result
                                    else:
                                        return {"result": str(result)}

                                except Exception as e:
                                    logger.warning(f"MCP tool execution error ({mcp_server_name}.{mcp_tool_name}): {e}")
                                    return {"error": str(e)}

                            return mcp_tool_wrapper

                        # Register the tool with the name as discovered (no prefix)
                        self.register_tool(
                            name=tool_name,
                            description=tool_description,
                            parameters=tool_input_schema,
                            function=create_mcp_tool_wrapper(client, tool_name, server_name),
                        )
                        registered_tool_names.append(tool_name)

                    if enabled_tools:
                        logger.info(
                            f"Loaded {len(tools_to_register)}/{len(all_tools)} enabled tools "
                            f"from MCP server: {server_name}"
                        )
                    else:
                        logger.info(f"Loaded all {len(tools_to_register)} tools from MCP server: {server_name}")

                except Exception as e:
                    logger.error(f"Failed to load tools from MCP server {server_name}: {e}")

            return registered_tool_names

        except Exception as e:
            logger.error(f"Failed to load agent MCP tools: {e}", exc_info=True)
            return []

    def register_platform_tools_for_agent(self, agent: Any) -> list[str]:
        """
        If agent is a platform engineer agent, load platform management tools.

        Called from ChatStreamService BEFORE _select_tools() so the tool names
        are included in the final tool list passed to the LLM.

        Returns the list of registered platform tool names (empty for non-platform agents).
        """
        is_platform_eng = (agent.agent_metadata or {}).get("is_platform_engineer", False)
        if not is_platform_eng:
            return []
        from src.services.agents.tool_registrations.platform_tools_registry import register_platform_tools
        from src.services.agents.tool_registrations.scheduler_tools_registry import register_scheduler_tools

        register_platform_tools(self)
        register_scheduler_tools(self)
        logger.info("Registered platform engineer tools + scheduler tools for agent '%s'", agent.agent_name)
        return [
            "platform_list_agents",
            "platform_get_available_tools",
            "platform_check_integration",
            "platform_create_agent",
            "platform_update_agent",
            "platform_list_database_connections",
            "platform_attach_database_connections",
            "platform_list_knowledge_bases",
            "platform_create_knowledge_base",
            "platform_attach_knowledge_base",
            "platform_list_mcp_servers",
            "platform_create_mcp_server",
            "platform_attach_mcp_server",
            "platform_get_agent_autonomous",
            "platform_set_agent_autonomous",
            "platform_disable_agent_autonomous",
            "platform_create_slack_bot",
            "platform_create_telegram_bot",
            "platform_list_agent_channels",
            "platform_delete_agent_channel",
            "internal_create_cron_scheduled_task",
            "internal_create_scheduled_task",
            "internal_list_scheduled_tasks",
            "internal_delete_scheduled_task",
        ]


# ---------------------------------------------------------------------------
# HITL: Approval gate helpers
# ---------------------------------------------------------------------------

# Tools whose category is "action" (write/post/send/create/modify operations).
# Used in "smart" approval mode to automatically gate any of these.
_ACTION_TOOL_NAMES: frozenset[str] = frozenset(
    {
        # Twitter / social
        "internal_twitter_post_tweet",
        "internal_twitter_reply_to_tweet",
        "internal_twitter_retweet",
        # Email
        "internal_send_email",
        "internal_send_bulk_emails",
        "internal_gmail_send_email",
        "internal_gmail_send_reply",
        # Slack
        "internal_slack_send_message",
        "internal_slack_send_dm",
        "internal_slack_post_blocks",
        "internal_slack_upload_file",
        # GitHub
        "internal_github_create_issue",
        "internal_github_comment_on_issue",
        "internal_github_create_pr",
        "internal_github_merge_pr",
        "internal_github_close_issue",
        # Jira
        "internal_jira_create_issue",
        "internal_jira_update_issue",
        "internal_jira_add_comment",
        # Git
        "internal_git_commit_and_push",
        # WhatsApp
        "internal_whatsapp_send_message",
        # File writes
        "internal_write_file",
        "internal_edit_file",
        "internal_move_file",
        # Calendar
        "internal_google_calendar_create_event",
        "internal_google_calendar_update_event",
        "internal_google_calendar_delete_event",
        # Drive
        "internal_google_drive_upload_file",
        "internal_google_drive_delete_file",
        # Database writes
        "internal_query_database",  # can be write query
        # Zoom
        "internal_zoom_create_meeting",
        "internal_zoom_update_meeting",
        "internal_zoom_delete_meeting",
    }
)


async def _check_approval_gate(
    tool_name: str,
    tool_def: dict[str, Any],
    arguments: dict[str, Any],
    runtime_context: Any,
) -> dict[str, Any] | None:
    """
    HITL approval gate called before every tool execution.

    Returns a non-None dict (to be used as the tool result) if the action
    needs human approval and has NOT yet been approved.  Returns None to
    allow normal execution.
    """
    import hashlib
    import json as _json
    from uuid import UUID

    if runtime_context is None:
        return None

    approval_config: dict = (
        runtime_context.shared_state.get("approval_config", {}) if runtime_context.shared_state else {}
    )
    if not approval_config.get("require_approval"):
        return None

    mode = approval_config.get("approval_mode", "smart")

    # Determine whether this specific tool should be gated
    needs_gate: bool
    if mode == "smart":
        needs_gate = tool_def.get("tool_category") == "action" or tool_name in _ACTION_TOOL_NAMES
    else:  # explicit
        needs_gate = tool_name in approval_config.get("require_approval_tools", [])

    if not needs_gate:
        return None

    # Check if this exact call was already pre-approved via Redis token
    task_id = approval_config.get("task_id", "")
    args_hash = hashlib.sha256(_json.dumps(arguments, sort_keys=True).encode()).hexdigest()
    token_key = f"approval_token:{task_id}:{tool_name}:{args_hash}"

    from src.config.redis import get_redis_async

    redis = get_redis_async()
    token = await redis.get(token_key)
    if token:
        # Consume the one-time token and allow execution
        await redis.delete(token_key)
        logger.info(f"HITL: approval token found for {tool_name} — proceeding")
        return None

    # No token → create approval request and block execution
    logger.info(f"HITL: gating tool '{tool_name}' for task {task_id} — requesting approval")

    try:
        from src.core.database import create_celery_async_session, reset_async_engine

        reset_async_engine()
        async_session_factory = create_celery_async_session()

        async with async_session_factory() as db:
            from src.services.human_approval_service import HumanApprovalService

            svc = HumanApprovalService(db)
            result = await svc.create_and_notify(
                task_id=UUID(str(task_id)),
                agent_id=UUID(str(approval_config.get("agent_id", "00000000-0000-0000-0000-000000000000"))),
                tenant_id=UUID(str(approval_config.get("tenant_id", "00000000-0000-0000-0000-000000000000"))),
                agent_name=approval_config.get("agent_name", ""),
                tool_name=tool_name,
                tool_args=arguments,
                channel=approval_config.get("approval_channel", "chat"),
                channel_config=approval_config.get("approval_channel_config", {}),
                timeout_minutes=approval_config.get("approval_timeout_minutes", 60),
            )
            return result
    except Exception as exc:
        logger.error(f"HITL gate error for tool '{tool_name}': {exc}", exc_info=True)
        # Fail open with an informational message rather than crashing
        return {
            "approval_required": True,
            "message": f"Could not reach approval service for '{tool_name}': {exc}",
            "status": "awaiting_approval",
        }


# Tool implementations


async def web_search(query: str, num_results: int = 5, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Search the web using SerpAPI."""
    try:
        from serpapi import GoogleSearch

        config = config or {}
        api_key = config.get("SERPAPI_KEY") or os.getenv("SERPAPI_KEY")
        if not api_key:
            return {"error": "SERPAPI_KEY not configured"}

        params = {"q": query, "api_key": api_key, "num": num_results}

        search = GoogleSearch(params)
        results = search.get_dict()

        organic_results = results.get("organic_results", [])

        return {
            "query": query,
            "results": [
                {"title": r.get("title"), "url": r.get("link"), "snippet": r.get("snippet")}
                for r in organic_results[:num_results]
            ],
        }
    except Exception as e:
        logger.error(f"Web search error: {e}")
        return {"error": str(e)}


async def web_crawl(url: str, extract_links: bool = False, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Crawl a web page and extract content."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, follow_redirects=True, timeout=10.0)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            # Get text
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = "\n".join(chunk for chunk in chunks if chunk)

            result = {
                "url": url,
                "title": soup.title.string if soup.title else None,
                "content": text[:5000],  # Limit content length
            }

            if extract_links:
                links = [a.get("href") for a in soup.find_all("a", href=True)]
                result["links"] = links[:50]  # Limit number of links

            return result
    except Exception as e:
        logger.error(f"Web crawl error: {e}")
        return {"error": str(e)}


async def github_search_repos(
    query: str, sort: str = "stars", limit: int = 5, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Search GitHub repositories.

    Requires GITHUB_OAUTH_TOKEN from oauth_apps table.
    """
    try:
        config = config or {}

        # Get OAuth token from config (loaded from oauth_apps table)
        token = config.get("GITHUB_OAUTH_TOKEN")

        if not token:
            return {"error": "GitHub OAuth token not configured. Please set up GitHub OAuth in OAuth Apps."}

        # Initialize GitHub client
        g = Github(token)

        repos = g.search_repositories(query=query, sort=sort)

        results = []
        for repo in repos[:limit]:
            results.append(
                {
                    "name": repo.full_name,
                    "description": repo.description,
                    "url": repo.html_url,
                    "stars": repo.stargazers_count,
                    "forks": repo.forks_count,
                    "language": repo.language,
                    "topics": repo.get_topics() if token else [],
                }
            )

        return {"query": query, "repositories": results, "authenticated": bool(token)}
    except Exception as e:
        logger.error(f"GitHub search error: {e}")
        return {"error": str(e)}


async def github_get_repo(owner: str, repo: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Get detailed information about a GitHub repository.

    Requires GITHUB_OAUTH_TOKEN from oauth_apps table.
    """
    try:
        config = config or {}

        # Get OAuth token from config (loaded from oauth_apps table)
        token = config.get("GITHUB_OAUTH_TOKEN")

        if not token:
            return {"error": "GitHub OAuth token not configured. Please set up GitHub OAuth in OAuth Apps."}

        g = Github(token)

        repository = g.get_repo(f"{owner}/{repo}")

        result = {
            "name": repository.full_name,
            "description": repository.description,
            "url": repository.html_url,
            "stars": repository.stargazers_count,
            "forks": repository.forks_count,
            "open_issues": repository.open_issues_count,
            "language": repository.language,
            "created_at": repository.created_at.isoformat(),
            "updated_at": repository.updated_at.isoformat(),
            "topics": repository.get_topics(),
            "authenticated": bool(token),
        }

        # Add additional info if authenticated
        if token:
            result.update(
                {
                    "default_branch": repository.default_branch,
                    "license": repository.license.name if repository.license else None,
                    "has_wiki": repository.has_wiki,
                    "has_issues": repository.has_issues,
                    "has_projects": repository.has_projects,
                    "archived": repository.archived,
                }
            )

        return result
    except Exception as e:
        logger.error(f"GitHub get repo error: {e}")
        return {"error": str(e)}


async def github_list_issues(
    owner: str, repo: str, state: str = "open", limit: int = 10, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    List issues from a GitHub repository.

    Requires GITHUB_OAUTH_TOKEN from oauth_apps table.
    """
    try:
        config = config or {}

        # Get OAuth token from config (loaded from oauth_apps table)
        token = config.get("GITHUB_OAUTH_TOKEN")

        if not token:
            return {"error": "GitHub OAuth token not configured. Please set up GitHub OAuth in OAuth Apps."}

        g = Github(token)

        repository = g.get_repo(f"{owner}/{repo}")
        issues = repository.get_issues(state=state)

        results = []
        for issue in issues[:limit]:
            issue_data = {
                "number": issue.number,
                "title": issue.title,
                "state": issue.state,
                "url": issue.html_url,
                "created_at": issue.created_at.isoformat(),
                "comments": issue.comments,
            }

            # Add additional info if authenticated
            if token:
                issue_data.update(
                    {
                        "author": issue.user.login if issue.user else None,
                        "labels": [label.name for label in issue.labels],
                        "assignees": [assignee.login for assignee in issue.assignees],
                        "updated_at": issue.updated_at.isoformat() if issue.updated_at else None,
                    }
                )

            results.append(issue_data)

        return {"repository": f"{owner}/{repo}", "issues": results, "authenticated": bool(token)}
    except Exception as e:
        logger.error(f"GitHub list issues error: {e}")
        return {"error": str(e)}


async def github_create_issue(
    owner: str,
    repo: str,
    title: str,
    body: str = "",
    labels: list[str] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Create a new issue in a GitHub repository.

    Requires GITHUB_OAUTH_TOKEN from oauth_apps table.
    """
    try:
        config = config or {}
        labels = labels or []

        # Get OAuth token from config (loaded from oauth_apps table)
        token = config.get("GITHUB_OAUTH_TOKEN")

        if not token:
            return {"error": "GitHub OAuth token not configured. Please set up GitHub OAuth in OAuth Apps."}

        g = Github(token)
        repository = g.get_repo(f"{owner}/{repo}")

        # Create the issue
        issue = repository.create_issue(title=title, body=body, labels=labels)

        return {
            "success": True,
            "issue": {
                "number": issue.number,
                "title": issue.title,
                "url": issue.html_url,
                "state": issue.state,
                "created_at": issue.created_at.isoformat(),
            },
        }
    except Exception as e:
        logger.error(f"GitHub create issue error: {e}")
        return {"error": str(e)}


async def github_list_pull_requests(
    owner: str, repo: str, state: str = "open", limit: int = 10, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    List pull requests from a GitHub repository.

    Requires GITHUB_OAUTH_TOKEN from oauth_apps table.
    """
    try:
        config = config or {}

        # Get OAuth token from config (loaded from oauth_apps table)
        token = config.get("GITHUB_OAUTH_TOKEN")

        if not token:
            return {"error": "GitHub OAuth token not configured. Please set up GitHub OAuth in OAuth Apps."}

        g = Github(token)

        repository = g.get_repo(f"{owner}/{repo}")
        pulls = repository.get_pulls(state=state)

        results = []
        for pr in pulls[:limit]:
            pr_data = {
                "number": pr.number,
                "title": pr.title,
                "state": pr.state,
                "url": pr.html_url,
                "created_at": pr.created_at.isoformat(),
                "updated_at": pr.updated_at.isoformat() if pr.updated_at else None,
            }

            # Add additional info if authenticated
            if token:
                pr_data.update(
                    {
                        "author": pr.user.login if pr.user else None,
                        "labels": [label.name for label in pr.labels],
                        "assignees": [assignee.login for assignee in pr.assignees],
                        "reviewers": [reviewer.login for reviewer in pr.requested_reviewers],
                        "merged": pr.merged,
                        "mergeable": pr.mergeable,
                        "comments": pr.comments,
                        "commits": pr.commits,
                        "additions": pr.additions,
                        "deletions": pr.deletions,
                    }
                )

            results.append(pr_data)

        return {"repository": f"{owner}/{repo}", "pull_requests": results, "authenticated": bool(token)}
    except Exception as e:
        logger.warning(f"GitHub list pull requests error: {e}")
        return {"error": str(e)}


async def github_get_user(username: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Get information about a GitHub user.

    Requires GITHUB_OAUTH_TOKEN from oauth_apps table.
    """
    try:
        config = config or {}

        # Get OAuth token from config (loaded from oauth_apps table)
        token = config.get("GITHUB_OAUTH_TOKEN")

        if not token:
            return {"error": "GitHub OAuth token not configured. Please set up GitHub OAuth in OAuth Apps."}

        g = Github(token)

        user = g.get_user(username)

        result = {
            "username": user.login,
            "name": user.name,
            "bio": user.bio,
            "url": user.html_url,
            "avatar_url": user.avatar_url,
            "public_repos": user.public_repos,
            "followers": user.followers,
            "following": user.following,
            "created_at": user.created_at.isoformat(),
            "authenticated": bool(token),
        }

        # Add additional info if authenticated
        if token:
            result.update(
                {
                    "company": user.company,
                    "blog": user.blog,
                    "location": user.location,
                    "email": user.email,
                    "hireable": user.hireable,
                    "twitter_username": user.twitter_username,
                }
            )

        return result
    except Exception as e:
        logger.error(f"GitHub get user error: {e}")
        return {"error": str(e)}


async def youtube_search(query: str, max_results: int = 5, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Search YouTube videos."""
    try:
        config = config or {}
        api_key = config.get("YOUTUBE_API_KEY") or os.getenv("YOUTUBE_API_KEY")
        if not api_key:
            return {"error": "YOUTUBE_API_KEY not configured"}

        youtube = build("youtube", "v3", developerKey=api_key)

        request = youtube.search().list(q=query, part="snippet", maxResults=max_results, type="video")
        response = request.execute()

        videos = []
        for item in response.get("items", []):
            videos.append(
                {
                    "video_id": item["id"]["videoId"],
                    "title": item["snippet"]["title"],
                    "description": item["snippet"]["description"],
                    "channel": item["snippet"]["channelTitle"],
                    "url": f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                }
            )

        return {"query": query, "videos": videos}
    except Exception as e:
        logger.error(f"YouTube search error: {e}")
        return {"error": str(e)}


async def youtube_get_video_info(video_id: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Get detailed information about a YouTube video."""
    try:
        config = config or {}
        api_key = config.get("YOUTUBE_API_KEY") or os.getenv("YOUTUBE_API_KEY")
        if not api_key:
            return {"error": "YOUTUBE_API_KEY not configured"}

        youtube = build("youtube", "v3", developerKey=api_key)

        request = youtube.videos().list(part="snippet,statistics,contentDetails", id=video_id)
        response = request.execute()

        if not response.get("items"):
            return {"error": "Video not found"}

        video = response["items"][0]

        return {
            "video_id": video_id,
            "title": video["snippet"]["title"],
            "description": video["snippet"]["description"],
            "channel": video["snippet"]["channelTitle"],
            "published_at": video["snippet"]["publishedAt"],
            "view_count": video["statistics"].get("viewCount"),
            "like_count": video["statistics"].get("likeCount"),
            "comment_count": video["statistics"].get("commentCount"),
            "duration": video["contentDetails"]["duration"],
            "url": f"https://www.youtube.com/watch?v={video_id}",
        }
    except Exception as e:
        logger.error(f"YouTube get video info error: {e}")
        return {"error": str(e)}


async def github_list_my_repos(limit: int = 10, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    List repositories for the authenticated user.

    Requires GITHUB_OAUTH_TOKEN from oauth_apps table.
    """
    try:
        config = config or {}

        # Get OAuth token from config (loaded from oauth_apps table)
        token = config.get("GITHUB_OAUTH_TOKEN")

        if not token:
            logger.info("No GitHub OAuth token found in config")
            return {"error": "GitHub OAuth token not configured. Please set up GitHub OAuth in OAuth Apps."}

        logger.info(f"Using GitHub OAuth token (length: {len(token)})")
        g = Github(token)
        user = g.get_user()

        repos = user.get_repos()

        results = []
        for repo in list(repos)[:limit]:
            results.append(
                {
                    "name": repo.full_name,
                    "description": repo.description,
                    "url": repo.html_url,
                    "stars": repo.stargazers_count,
                    "forks": repo.forks_count,
                    "language": repo.language,
                    "private": repo.private,
                    "created_at": repo.created_at.isoformat(),
                    "updated_at": repo.updated_at.isoformat(),
                }
            )

        return {
            "username": user.login,
            "total_repos": user.public_repos + (user.total_private_repos or 0),
            "repositories": results,
            "authenticated": True,
        }
    except Exception as e:
        logger.error(f"GitHub list my repos error: {e}")
        return {"error": str(e)}


async def github_composite(action: str, config: dict[str, Any] | None = None, **kwargs) -> dict[str, Any]:
    """
    Composite GitHub tool that routes to specific GitHub functions based on action.

    Args:
        action: The GitHub action to perform
        config: Configuration dictionary with auth tokens
        **kwargs: Additional arguments specific to each action
    """
    try:
        if action == "search_repos":
            return await github_search_repos(
                query=kwargs.get("query", ""),
                sort=kwargs.get("sort", "stars"),
                limit=kwargs.get("limit", 5),
                config=config,
            )
        elif action == "get_repo":
            return await github_get_repo(owner=kwargs.get("owner", ""), repo=kwargs.get("repo", ""), config=config)
        elif action == "list_issues":
            return await github_list_issues(
                owner=kwargs.get("owner", ""),
                repo=kwargs.get("repo", ""),
                state=kwargs.get("state", "open"),
                limit=kwargs.get("limit", 10),
                config=config,
            )
        elif action == "create_issue":
            return await github_create_issue(
                owner=kwargs.get("owner", ""),
                repo=kwargs.get("repo", ""),
                title=kwargs.get("title", ""),
                body=kwargs.get("body", ""),
                labels=kwargs.get("labels", []),
                config=config,
            )
        elif action == "list_pull_requests":
            return await github_list_pull_requests(
                owner=kwargs.get("owner", ""),
                repo=kwargs.get("repo", ""),
                state=kwargs.get("state", "open"),
                limit=kwargs.get("limit", 10),
                config=config,
            )
        elif action == "get_user":
            return await github_get_user(username=kwargs.get("username", ""), config=config)
        elif action == "list_my_repos":
            return await github_list_my_repos(limit=kwargs.get("limit", 10), config=config)
        else:
            return {
                "error": f"Unknown action: {action}. Valid actions are: search_repos, get_repo, list_issues, create_issue, list_pull_requests, get_user, list_my_repos"
            }
    except Exception as e:
        logger.error(f"GitHub composite tool error: {e}")
        return {"error": str(e)}


async def transfer_to_agent(agent_name: str, task: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Transfer control to another agent.

    This is the LLM-driven delegation pattern from ADK framework.
    The parent agent's LLM generates this function call to route tasks
    to specialized sub-agents.

    Args:
        agent_name: Name of the agent to transfer to
        task: Task description to pass to the target agent
        config: Configuration dictionary with runtime_context

    Returns:
        Result from the target agent execution
    """
    try:
        config = config or {}
        runtime_context = config.get("_runtime_context")

        if not runtime_context:
            return {"error": "Runtime context not available for agent transfer"}

        # Extract context components
        from src.models.agent import Agent

        if isinstance(runtime_context, dict):
            db_session = runtime_context.get("db_session")
            agent_id = runtime_context.get("agent_id")
        else:
            db_session = getattr(runtime_context, "db_session", None)
            agent_id = getattr(runtime_context, "agent_id", None)

        if not db_session or not agent_id:
            return {"error": "Missing database session or agent ID in runtime context"}

        # Get the current (parent) agent
        result = await db_session.execute(select(Agent).filter(Agent.id == agent_id))
        parent_agent = result.scalar_one_or_none()
        if not parent_agent:
            return {"error": "Parent agent not found"}

        # Check if transfer is allowed
        if not parent_agent.allow_transfer:
            return {"error": f"Agent '{parent_agent.agent_name}' is not allowed to transfer to other agents"}

        # Find the target agent based on transfer_scope
        target_agent = await parent_agent.find_agent_by_name(agent_name, db_session)

        if not target_agent:
            return {
                "error": f"Agent '{agent_name}' not found or not accessible. "
                f"Transfer scope is '{parent_agent.transfer_scope}'. "
                f"Available agents depend on the scope setting."
            }

        logger.info(
            f"Transferring from '{parent_agent.agent_name}' to '{target_agent.agent_name}' with task: {task[:100]}..."
        )

        # Use AgentTool to execute the target agent
        from src.services.agents.agent_tool import AgentTool

        agent_tool = AgentTool(
            agent_id=target_agent.id,
            agent_name=target_agent.agent_name,
            description=target_agent.description or f"Specialized agent: {target_agent.agent_name}",
            db=db_session,
        )

        # Execute the target agent and collect results
        result_parts = []

        # Create or get runtime context object
        if isinstance(runtime_context, dict):
            # Convert dict to RuntimeContext object
            import uuid

            from src.services.agents.runtime_context import RuntimeContext

            context_obj = RuntimeContext(
                tenant_id=uuid.UUID(runtime_context["tenant_id"])
                if isinstance(runtime_context["tenant_id"], str)
                else runtime_context["tenant_id"],
                agent_id=uuid.UUID(runtime_context["agent_id"])
                if isinstance(runtime_context["agent_id"], str)
                else runtime_context["agent_id"],
                db_session=runtime_context["db_session"],
                llm_client=runtime_context.get("llm_client"),
                conversation_id=runtime_context.get("conversation_id"),
                message_id=runtime_context.get("message_id"),
                user_id=runtime_context.get("user_id"),
                shared_state=runtime_context.get("shared_state", {}),
            )
        else:
            context_obj = runtime_context

        async for event in agent_tool.execute(task, context_obj):
            if event.get("type") == "agent_response":
                content = event.get("content", "")
                if content:
                    result_parts.append(content)

        final_result = "\n".join(result_parts) if result_parts else "No response from agent"

        # If target agent has output_key, the result is already saved to state by AgentTool

        return {"success": True, "agent": target_agent.agent_name, "result": final_result}

    except Exception as e:
        logger.error(f"Transfer to agent error: {e}", exc_info=True)
        return {"error": str(e)}


# Global tool registry instance
tool_registry = ADKToolRegistry()
