"""
Git Repository Tools Registry.

Registers tools for repository lifecycle: cloning, adding remotes, and cleanup.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register_git_repo_tools(registry):
    """Register git repository lifecycle tools with the ADK tool registry."""
    from src.services.agents.internal_tools.git_repo_tools import (
        internal_git_add_remote,
        internal_git_cleanup_repo,
        internal_git_clone_repo,
    )

    async def internal_git_clone_repo_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_git_clone_repo(
            repo_url=kwargs.get("repo_url"),
            use_ssh=kwargs.get("use_ssh", False),
            depth=kwargs.get("depth", 1),
            branch=kwargs.get("branch"),
            config=config,
            runtime_context=runtime_context,
        )

    async def internal_git_add_remote_wrapper(config: dict[str, Any] | None = None, **kwargs):
        return await internal_git_add_remote(
            repo_path=kwargs.get("repo_path"),
            remote_name=kwargs.get("remote_name"),
            remote_url=kwargs.get("remote_url"),
            config=config,
        )

    async def internal_git_cleanup_repo_wrapper(config: dict[str, Any] | None = None, **kwargs):
        return await internal_git_cleanup_repo(
            repo_path=kwargs.get("repo_path"),
            config=config,
        )

    registry.register_tool(
        name="internal_git_clone_repo",
        description=(
            "Clone a Git repository into a temporary directory. Uses GitHub PAT/OAuth token for authentication "
            "if configured. Supports both HTTPS and SSH URLs. Returns the path to the cloned repository. "
            "Defaults to a shallow, single-branch clone (fast and reliable even for large repos); pass a "
            "'branch' to clone a specific branch directly, or 'depth: 0' for a full clone with complete "
            "history (only needed for tasks like git log/blame across old commits)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "repo_url": {"type": "string", "description": "Repository URL (HTTPS or SSH format)"},
                "use_ssh": {
                    "type": "boolean",
                    "description": "Whether to convert HTTPS URLs to SSH (default: false, uses PAT token authentication)",
                    "default": False,
                },
                "depth": {
                    "type": "integer",
                    "description": (
                        "Number of commits of history to fetch. Default 1 (shallow clone, recommended for "
                        "most tasks). Use 0 for a full clone with complete history."
                    ),
                    "default": 1,
                },
                "branch": {
                    "type": "string",
                    "description": "Specific branch to clone directly. Omit to clone the repository's default branch.",
                },
            },
            "required": ["repo_url"],
        },
        function=internal_git_clone_repo_wrapper,
    )

    registry.register_tool(
        name="internal_git_add_remote",
        description="Add a remote to a local Git repository. Useful for adding upstream remotes in fork workflows. Updates the URL if the remote already exists.",
        parameters={
            "type": "object",
            "properties": {
                "repo_path": {"type": "string", "description": "Path to the local Git repository"},
                "remote_name": {"type": "string", "description": "Name of the remote (e.g., 'upstream', 'origin')"},
                "remote_url": {"type": "string", "description": "URL of the remote repository"},
            },
            "required": ["repo_path", "remote_name", "remote_url"],
        },
        function=internal_git_add_remote_wrapper,
    )

    registry.register_tool(
        name="internal_git_cleanup_repo",
        description="Clean up a cloned repository by removing its directory. Only works on directories within the workspace for security.",
        parameters={
            "type": "object",
            "properties": {
                "repo_path": {"type": "string", "description": "Path to the repository to clean up"},
            },
            "required": ["repo_path"],
        },
        function=internal_git_cleanup_repo_wrapper,
    )

    logger.info("Registered 3 git repo tools")
