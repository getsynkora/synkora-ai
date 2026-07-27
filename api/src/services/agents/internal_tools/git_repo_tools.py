"""
Git Repository Tools.

Handles repository lifecycle: cloning, adding remotes, and cleanup.
All operations work on the local filesystem within the agent workspace.
"""

import logging
import os
import uuid
from typing import Any

from .git_helpers import (
    MAX_CLONE_TIMEOUT,
    MAX_REPO_SIZE_MB,
    _convert_https_to_ssh,
    _get_workspace_path,
    async_get_repo_size,
    async_makedirs,
    async_path_exists,
    async_rmtree,
    async_run_git_command,
    async_validate_repo_path,
)

logger = logging.getLogger(__name__)


async def internal_git_clone_repo(
    repo_url: str, use_ssh: bool = False, config: dict[str, Any] | None = None, runtime_context: Any = None
) -> dict[str, Any]:
    """
    Clone a Git repository into the workspace directory.

    Args:
        repo_url: Repository URL (HTTPS or SSH)
        use_ssh: Whether to convert HTTPS URLs to SSH (default: False, uses PAT instead)
        config: Configuration dictionary containing workspace_path
        runtime_context: Runtime context for credential resolution (provides GitHub PAT)

    Returns:
        Dictionary with success, repo_path, message, and size_mb.
    """
    try:
        from .github_auth_helper import prepare_authenticated_git_url

        workspace_path = _get_workspace_path(config)
        if not workspace_path and runtime_context and getattr(runtime_context, "tenant_id", None):
            # Fallback: create workspace directly from runtime_context when ContextVar isn't propagated
            import uuid as _uuid

            from src.services.agents.workspace_manager import get_workspace_manager

            tenant_id = runtime_context.tenant_id
            conversation_id = getattr(runtime_context, "conversation_id", None) or _uuid.uuid5(
                _uuid.UUID(str(tenant_id)), "background_tasks"
            )
            workspace_path = get_workspace_manager().get_or_create_workspace(tenant_id, conversation_id)
        if not workspace_path:
            return {
                "success": False,
                "error": "No workspace path configured. Clone requires a valid workspace.",
                "repo_path": None,
            }

        if not use_ssh and runtime_context:
            repo_url, used_token = await prepare_authenticated_git_url(
                repo_url, runtime_context, tool_name="internal_git_clone_repo"
            )
            if used_token:
                logger.info("✅ Using GitHub OAuth/PAT token for authentication")
        elif use_ssh:
            repo_url = _convert_https_to_ssh(repo_url)

        # Pre-check repo size via GitHub API before cloning to avoid downloading
        # hundreds of MB only to reject the repo afterwards.
        # Only applies to github.com URLs when credentials are available.
        _gh_match = __import__("re").search(r"github\.com[:/](?:[^@/]+@)?([^/]+)/([^/]+?)(?:\.git)?$", repo_url)
        if _gh_match and runtime_context:
            try:
                from .github_auth_helper import get_github_token_from_context

                _token = await get_github_token_from_context(runtime_context, tool_name="internal_git_clone_repo")
                if _token:
                    import asyncio as _asyncio

                    from github import Github as _Github

                    _slug = f"{_gh_match.group(1)}/{_gh_match.group(2)}"

                    def _fetch_size() -> float:
                        return _Github(_token).get_repo(_slug).size / 1024  # KB → MB

                    _size_mb = await _asyncio.get_event_loop().run_in_executor(None, _fetch_size)
                    if _size_mb > MAX_REPO_SIZE_MB:
                        return {
                            "success": False,
                            "error": (
                                f"Repository size ({_size_mb:.1f}MB) exceeds maximum allowed size "
                                f"({MAX_REPO_SIZE_MB}MB). Cannot clone this repository."
                            ),
                            "repo_path": None,
                        }
                    logger.info(f"Pre-clone size check passed: {_size_mb:.1f}MB")
            except Exception as _pre_check_err:
                # Non-fatal: if the pre-check fails, proceed and let the post-clone check catch it
                logger.debug(f"Pre-clone size check skipped: {_pre_check_err}")

        repos_dir = os.path.join(workspace_path, "repos")
        await async_makedirs(repos_dir, config)

        repo_dir = os.path.join(repos_dir, f"git_{uuid.uuid4().hex[:12]}")
        logger.info(f"Cloning '{repo_url}' into {repo_dir}")

        result = await async_run_git_command(
            ["git", "clone", repo_url, repo_dir], working_directory=None, config=config, timeout=MAX_CLONE_TIMEOUT
        )

        if not result["success"]:
            await async_rmtree(repo_dir, config)
            return {"success": False, "error": f"Failed to clone repository: {result['error']}", "repo_path": None}

        repo_size = await async_get_repo_size(repo_dir, config)
        if repo_size > MAX_REPO_SIZE_MB:
            await async_rmtree(repo_dir, config)
            return {
                "success": False,
                "error": f"Repository size ({repo_size:.1f}MB) exceeds maximum allowed size ({MAX_REPO_SIZE_MB}MB)",
                "repo_path": None,
            }

        logger.info(f"Successfully cloned repository to {repo_dir} (size: {repo_size:.1f}MB)")
        return {
            "success": True,
            "repo_path": repo_dir,
            "message": f"Successfully cloned repository to {repo_dir}",
            "size_mb": round(repo_size, 2),
        }

    except Exception as e:
        logger.error(f"Failed to clone repository: {e}", exc_info=True)
        return {"success": False, "error": str(e), "repo_path": None}


async def internal_git_add_remote(
    repo_path: str, remote_name: str, remote_url: str, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Add or update a remote in a local repository.

    Args:
        repo_path: Path to the local Git repository (must be within workspace)
        remote_name: Name of the remote (e.g., "upstream")
        remote_url: URL of the remote repository
        config: Configuration dictionary containing workspace_path

    Returns:
        Dictionary with success status and message.
    """
    try:
        workspace_path = _get_workspace_path(config)
        if not workspace_path:
            runtime_context = config.get("_runtime_context") if config else None
            if runtime_context and getattr(runtime_context, "tenant_id", None):
                import uuid as _uuid

                from src.services.agents.workspace_manager import get_workspace_manager

                tenant_id = runtime_context.tenant_id
                tenant_uuid = tenant_id if isinstance(tenant_id, _uuid.UUID) else _uuid.UUID(str(tenant_id))
                conversation_id = getattr(runtime_context, "conversation_id", None) or _uuid.uuid5(
                    tenant_uuid, "background_tasks"
                )
                workspace_path = get_workspace_manager().get_or_create_workspace(tenant_id, conversation_id)
        is_valid, error = await async_validate_repo_path(repo_path, workspace_path, config)
        if not is_valid:
            return {"success": False, "error": error}

        if not await async_path_exists(repo_path, config):
            return {"success": False, "error": f"Repository path does not exist: {repo_path}"}

        check_result = await async_run_git_command(["git", "remote", "get-url", remote_name], repo_path, config)

        if check_result["success"]:
            existing_url = check_result["output"]
            if remote_url in existing_url:
                return {
                    "success": True,
                    "message": f"Remote '{remote_name}' already exists with correct URL",
                    "already_exists": True,
                }

            logger.info(f"Updating remote '{remote_name}' URL")
            update_result = await async_run_git_command(
                ["git", "remote", "set-url", remote_name, remote_url], repo_path, config
            )
            if not update_result["success"]:
                return {"success": False, "error": f"Failed to update remote URL: {update_result['error']}"}

            return {"success": True, "message": f"Updated remote '{remote_name}' URL to {remote_url}", "updated": True}

        logger.info(f"Adding remote '{remote_name}' with URL: {remote_url}")
        add_result = await async_run_git_command(["git", "remote", "add", remote_name, remote_url], repo_path, config)
        if not add_result["success"]:
            return {"success": False, "error": f"Failed to add remote: {add_result['error']}"}

        return {
            "success": True,
            "message": f"Successfully added remote '{remote_name}'",
            "remote_name": remote_name,
            "remote_url": remote_url,
        }

    except Exception as e:
        logger.error(f"Failed to add remote: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_git_cleanup_repo(repo_path: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Clean up a cloned repository by removing its directory.

    Args:
        repo_path: Path to the repository to clean up (must be within workspace)
        config: Configuration dictionary containing workspace_path

    Returns:
        Dictionary with success status and message.
    """
    try:
        if not await async_path_exists(repo_path, config):
            return {"success": True, "message": "Repository path does not exist (already cleaned up)"}

        workspace_path = _get_workspace_path(config)
        if not workspace_path:
            runtime_context = config.get("_runtime_context") if config else None
            if runtime_context and getattr(runtime_context, "tenant_id", None):
                import uuid as _uuid

                from src.services.agents.workspace_manager import get_workspace_manager

                tenant_id = runtime_context.tenant_id
                tenant_uuid = tenant_id if isinstance(tenant_id, _uuid.UUID) else _uuid.UUID(str(tenant_id))
                conversation_id = getattr(runtime_context, "conversation_id", None) or _uuid.uuid5(
                    tenant_uuid, "background_tasks"
                )
                workspace_path = get_workspace_manager().get_or_create_workspace(tenant_id, conversation_id)
        is_valid, error = await async_validate_repo_path(repo_path, workspace_path, config)
        if not is_valid:
            return {"success": False, "error": f"Can only cleanup directories within workspace. {error}"}

        logger.info(f"Cleaning up repository at {repo_path}")
        await async_rmtree(repo_path, config)
        return {"success": True, "message": f"Successfully cleaned up repository at {repo_path}"}

    except Exception as e:
        logger.error(f"Failed to cleanup repository: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
