"""
Shared helpers for local Git operations.

Provides security constants, input validation, path validation, and the
core _run_git_command utility used by git_repo_tools, git_branch_tools,
and git_commit_tools.
"""

import asyncio
import logging
import os
import re
import shutil
import subprocess
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Security configuration
# ---------------------------------------------------------------------------

MAX_REPO_SIZE_MB = 2048  # Maximum allowed repository size (in MB)
MAX_CLONE_TIMEOUT = 1800  # Maximum clone timeout (30 minutes)
MAX_COMMAND_TIMEOUT = 300  # Maximum command timeout (5 minutes)
MAX_BRANCH_NAME_LENGTH = 255
MAX_COMMIT_MESSAGE_LENGTH = 1000
MAX_REMOTE_NAME_LENGTH = 100
ALLOWED_URL_SCHEMES = {"https", "ssh", "git"}

VALID_BRANCH_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9._/-]+$")
VALID_REMOTE_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9._-]+$")
SSH_URL_PATTERN = re.compile(r"^git@[\w.-]+:[\w.-]+/[\w.-]+(?:\.git)?$")
HTTPS_URL_PATTERN = re.compile(r"^https://[\w.-]+/[\w.-]+/[\w.-]+(?:\.git)?$")

BLOCKED_PATTERNS = [
    r"[;&|`$]",  # Shell injection characters
    r"\.\.",  # Path traversal
    r"~",  # Home directory access
    r"\$\{",  # Variable expansion
]


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _get_workspace_path(config: dict[str, Any] | None) -> str | None:
    """
    Get the workspace path for git operations.

    When a remote ComputeSession is active (Sandbox, RemoteSSH, etc.), git commands
    execute on the remote target via async_run_git_command(), so paths must be scoped
    to *that* target's own workspace root (session.base_path) — not the local
    WorkspaceManager path, which only exists on this container's filesystem and has
    no relationship to the remote target's directory layout. Using the wrong path here
    causes clones to "succeed" outside the remote's workspace sandbox while every
    subsequent path-validated remote operation (exists/list/read/write) then rejects
    that same path as escaping the workspace.

    Falls back to the local WorkspaceManager path when there is no remote session.
    """
    compute_session = (config or {}).get("_compute_session")
    if compute_session is None:
        try:
            from src.services.agents.runtime_context import get_runtime_context

            ctx = get_runtime_context()
            compute_session = getattr(ctx, "compute_session", None) if ctx else None
        except Exception:
            compute_session = None

    if compute_session is not None and getattr(compute_session, "is_remote", False):
        base_path = getattr(compute_session, "base_path", None)
        if base_path:
            return base_path

    from src.services.agents.workspace_manager import get_workspace_path_from_config

    return get_workspace_path_from_config(config)


def _validate_repo_path(repo_path: str, workspace_path: str | None) -> tuple[bool, str | None]:
    """
    Validate that a repository path is within the workspace directory.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not workspace_path:
        return False, "No workspace path configured. Repository operations require a valid workspace."

    try:
        real_path = os.path.realpath(repo_path)
        real_workspace = os.path.realpath(workspace_path)

        real_path = real_path.removeprefix("/private")
        real_workspace = real_workspace.removeprefix("/private")

        if not (real_path.startswith(real_workspace + os.sep) or real_path == real_workspace):
            return (
                False,
                f"Repository path '{repo_path}' is outside the workspace directory. Use workspace path: {workspace_path}",
            )

        return True, None
    except Exception as e:
        return False, f"Error validating repository path: {str(e)}"


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def _validate_input(input_str: str, input_type: str) -> dict[str, Any]:
    """Validate input strings for security compliance."""
    if not input_str or not isinstance(input_str, str):
        return {"valid": False, "error": f"Invalid {input_type}: must be a non-empty string"}

    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, input_str):
            logger.warning(f"Blocked pattern detected in {input_type}: {pattern}")
            return {"valid": False, "error": f"Invalid {input_type}: contains forbidden characters"}

    if input_type == "branch_name":
        if len(input_str) > MAX_BRANCH_NAME_LENGTH:
            return {"valid": False, "error": f"Branch name exceeds maximum length ({MAX_BRANCH_NAME_LENGTH})"}
        if not VALID_BRANCH_NAME_PATTERN.match(input_str):
            return {"valid": False, "error": "Branch name contains invalid characters"}

    elif input_type == "remote_name":
        if len(input_str) > MAX_REMOTE_NAME_LENGTH:
            return {"valid": False, "error": f"Remote name exceeds maximum length ({MAX_REMOTE_NAME_LENGTH})"}
        if not VALID_REMOTE_NAME_PATTERN.match(input_str):
            return {"valid": False, "error": "Remote name contains invalid characters"}

    elif input_type == "commit_message":
        if len(input_str) > MAX_COMMIT_MESSAGE_LENGTH:
            return {"valid": False, "error": f"Commit message exceeds maximum length ({MAX_COMMIT_MESSAGE_LENGTH})"}

    elif input_type == "repo_url":
        if not (HTTPS_URL_PATTERN.match(input_str) or SSH_URL_PATTERN.match(input_str)):
            return {"valid": False, "error": "Invalid repository URL format"}
        parsed = urlparse(input_str)
        if parsed.scheme and parsed.scheme not in ALLOWED_URL_SCHEMES:
            return {"valid": False, "error": f"URL scheme not allowed: {parsed.scheme}"}

    elif input_type == "repo_path":
        if not os.path.exists(input_str):
            return {"valid": False, "error": f"Repository path does not exist: {input_str}"}
        # Path safety is enforced by _validate_repo_path (workspace containment check)

    return {"valid": True}


# ---------------------------------------------------------------------------
# Output sanitisation
# ---------------------------------------------------------------------------


def _sanitize_output(output: str) -> str:
    """Remove sensitive information from command output."""
    if not output:
        return output

    sanitized = output
    ssh_key_pattern = r"-----BEGIN [A-Z ]+-----.*?-----END [A-Z ]+-----"
    sanitized = re.sub(ssh_key_pattern, "[REDACTED SSH KEY]", sanitized, flags=re.DOTALL)
    token_pattern = r"(token|password|secret)[:=]\s*[^\s]+"
    sanitized = re.sub(token_pattern, r"\1: [REDACTED]", sanitized, flags=re.IGNORECASE)
    return sanitized


# ---------------------------------------------------------------------------
# Git command runner
# ---------------------------------------------------------------------------


def _run_git_command(command: list[str], working_directory: str | None = None, timeout: int = 300) -> dict[str, Any]:
    """
    Run a git command and return the result.

    Returns:
        Dictionary with 'success', 'output', 'error', and 'return_code' keys.
    """
    try:
        env = os.environ.copy()
        env["GIT_SSH_COMMAND"] = "ssh -o StrictHostKeyChecking=yes -o BatchMode=yes"

        result = subprocess.run(
            command, cwd=working_directory, capture_output=True, text=True, timeout=timeout, check=False, env=env
        )

        success = result.returncode == 0
        return {
            "success": success,
            "output": result.stdout.strip(),
            "error": result.stderr.strip() if not success else "",
            "return_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out after {timeout}s: {' '.join(command)}")
        return {
            "success": False,
            "output": "",
            "error": f"Command timed out after {timeout} seconds",
            "return_code": -1,
        }
    except Exception as e:
        logger.error(f"Failed to run command {' '.join(command)}: {e}")
        return {"success": False, "output": "", "error": str(e), "return_code": -1}


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------


def _convert_https_to_ssh(url: str) -> str:
    """Convert an HTTPS Git URL to its SSH equivalent."""
    if not url.startswith("https://"):
        return url
    try:
        parsed_url = urlparse(url)
        if not parsed_url.hostname or not parsed_url.path:
            logger.warning(f"Could not parse URL '{url}', using original")
            return url
        ssh_url = f"git@{parsed_url.hostname}:{parsed_url.path.lstrip('/')}"
        logger.info(f"Converted HTTPS URL to SSH: {ssh_url}")
        return ssh_url
    except Exception as e:
        logger.warning(f"Failed to parse URL '{url}': {e}")
        return url


# ---------------------------------------------------------------------------
# Repo size helper
# ---------------------------------------------------------------------------


def _get_repo_size(repo_path: str) -> float:
    """Get repository size in MB."""
    total_size = 0
    for dirpath, _dirnames, filenames in os.walk(repo_path):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            if os.path.exists(filepath):
                total_size += os.path.getsize(filepath)
    return total_size / (1024 * 1024)


# ---------------------------------------------------------------------------
# Async helpers — route through compute session when remote
# ---------------------------------------------------------------------------


async def async_run_git_command(
    command: list[str],
    working_directory: str | None = None,
    config: dict[str, Any] | None = None,
    timeout: int = 300,
) -> dict[str, Any]:
    """Run a git command, routing through the compute session when configured."""
    from src.services.compute.resolver import get_compute_session_from_config

    _cs = await get_compute_session_from_config(config)
    if _cs is not None and _cs.is_remote:
        return await _cs.exec_command(command=command, cwd=working_directory, timeout=timeout)
    return await asyncio.get_event_loop().run_in_executor(
        None, lambda: _run_git_command(command, working_directory, timeout)
    )


async def async_path_exists(path: str, config: dict[str, Any] | None = None) -> bool:
    """Check if a path exists, routing through the compute session when configured."""
    from src.services.compute.resolver import get_compute_session_from_config

    _cs = await get_compute_session_from_config(config)
    if _cs is not None and _cs.is_remote:
        return await _cs.file_exists(path)
    return os.path.exists(path)


async def async_makedirs(path: str, config: dict[str, Any] | None = None) -> None:
    """Create a directory (and parents), routing through the compute session when configured."""
    from src.services.compute.resolver import get_compute_session_from_config

    _cs = await get_compute_session_from_config(config)
    if _cs is not None and _cs.is_remote:
        await _cs.create_dir(path)
        return
    os.makedirs(path, exist_ok=True)


async def async_rmtree(path: str, config: dict[str, Any] | None = None) -> None:
    """Remove a directory tree, routing through the compute session when configured."""
    from src.services.compute.resolver import get_compute_session_from_config

    _cs = await get_compute_session_from_config(config)
    if _cs is not None and _cs.is_remote:
        await _cs.exec_command(["rm", "-rf", path])
        return
    shutil.rmtree(path, ignore_errors=True)


async def async_get_repo_size(path: str, config: dict[str, Any] | None = None) -> float:
    """Get repository size in MB, routing through the compute session when configured."""
    from src.services.compute.resolver import get_compute_session_from_config

    _cs = await get_compute_session_from_config(config)
    if _cs is not None and _cs.is_remote:
        result = await _cs.exec_command(["du", "-sm", path])
        if result.get("success") and result.get("output"):
            try:
                return float(result["output"].split()[0])
            except (ValueError, IndexError):
                pass
        return 0.0
    return await asyncio.get_event_loop().run_in_executor(None, lambda: _get_repo_size(path))


async def async_write_file(path: str, content: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Write a text file, routing through the compute session when configured."""
    from src.services.compute.resolver import get_compute_session_from_config

    _cs = await get_compute_session_from_config(config)
    if _cs is not None and _cs.is_remote:
        return await _cs.write_file(path, content)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def async_write_file_bytes(path: str, content: bytes, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Write binary content to a file, routing through the compute session when configured."""
    from src.services.compute.resolver import get_compute_session_from_config

    _cs = await get_compute_session_from_config(config)
    if _cs is not None and _cs.is_remote:
        return await _cs.write_file_bytes(path, content)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
        with open(path, "wb") as fh:
            fh.write(content)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def async_read_file_bytes(path: str, config: dict[str, Any] | None = None) -> bytes | None:
    """Read binary file content, routing through the compute session when configured."""
    from src.services.compute.resolver import get_compute_session_from_config

    _cs = await get_compute_session_from_config(config)
    if _cs is not None and _cs.is_remote:
        return await _cs.read_file_bytes(path)
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except Exception:
        return None


async def async_validate_repo_path(
    repo_path: str, workspace_path: str | None, config: dict[str, Any] | None = None
) -> tuple[bool, str | None]:
    """Validate repo path is within workspace, using string comparison for remote sessions."""
    from src.services.compute.resolver import get_compute_session_from_config

    _cs = await get_compute_session_from_config(config)
    if _cs is not None and _cs.is_remote:
        if not workspace_path:
            return False, "No workspace path configured. Repository operations require a valid workspace."
        if not (repo_path.startswith(workspace_path + "/") or repo_path == workspace_path):
            return (
                False,
                f"Repository path '{repo_path}' is outside the workspace directory. Use workspace path: {workspace_path}",
            )
        return True, None
    return _validate_repo_path(repo_path, workspace_path)
