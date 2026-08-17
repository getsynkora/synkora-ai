"""
Internal Command Execution Tools.

Provides safe command-line execution capabilities for agents with enterprise-grade security.
Includes comprehensive allowlists, path validation, URL filtering, and dangerous flag detection.
"""

import ast
import json
import logging
import os
import re
import shlex
import subprocess
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Maximum characters returned from a single command's stdout.
# Prevents `cat` on large files from flooding the LLM context window and
# triggering aggressive pruning that wipes all prior tool results.
# Agents should use internal_read_file (paginated) or internal_grep instead.
MAX_COMMAND_OUTPUT_CHARS = 8000

# Allowed domains for external requests (curl/wget)
ALLOWED_DOMAINS = [
    "api.github.com",
    "raw.githubusercontent.com",
    "github.com",
    "pypi.org",
    "files.pythonhosted.org",
    "registry.npmjs.org",
    "nodejs.org",
    "archive.ubuntu.com",
    "security.ubuntu.com",
    "ports.ubuntu.com",
    "deb.debian.org",
    "security.debian.org",
]


def _get_workspace_path(config: dict[str, Any] | None) -> str | None:
    """Get the workspace path from config or RuntimeContext (including Celery task fallback)."""
    from src.services.agents.workspace_manager import get_workspace_path_from_config

    return get_workspace_path_from_config(config)


# Blocked path patterns (sensitive files/directories)
BLOCKED_PATHS = [
    # System-level sensitive files
    "/etc/passwd",
    "/etc/shadow",
    "/etc/sudoers",
    "/etc/ssh",
    # Home directory sensitive files
    "/root",
    "/.ssh",
    "/.bash_history",
    "/.zsh_history",
    "/.git-credentials",
    "/.npmrc",
    "/.docker/config.json",
    # Cloud credentials
    "/.aws/credentials",
    "/.gcloud/credentials",
    "/.azure/credentials",
    # SSH keys and history
    "known_hosts",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "authorized_keys",
    # Environment and configuration files
    "/.env",
    # Kernel and system-specific virtual filesystems
    "/proc",
    "/sys",
    "/dev",
    # Application-specific directories (often containing sensitive data)
    "/home/appuser",
]

_PATH_BOUNDARY_CHARS = ("/", " ", "'", '"', "=", ":", "\t", "\n")


def _is_blocked_path_match(path: str, blocked: str) -> bool:
    """Check if `blocked` appears in `path` as a real path component, not as an
    arbitrary substring of an unrelated name.

    A naive `blocked in path` substring check false-positives badly — e.g. the
    "/sys" entry (meant to block the /sys kernel virtual filesystem) also matches
    ".../system-architecture.md", and the "id_rsa" entry matches
    "invalid_rsa_config.txt". Entries starting with "/" already carry their own
    left path-boundary; bare filename entries (e.g. "id_rsa", "known_hosts")
    need a boundary on both sides.
    """
    start = 0
    while True:
        idx = path.find(blocked, start)
        if idx == -1:
            return False
        end = idx + len(blocked)
        left_ok = blocked.startswith("/") or idx == 0 or path[idx - 1] in _PATH_BOUNDARY_CHARS
        right_ok = end == len(path) or path[end] in _PATH_BOUNDARY_CHARS
        if left_ok and right_ok:
            return True
        start = idx + 1


# Allowlist of safe commands with their allowed subcommands
SAFE_COMMANDS: dict[str, list[str]] = {
    # --- File/Directory (Read-Only) ---
    "ls": [],
    "cat": [],
    "head": [],
    "tail": [],
    "wc": [],
    "find": [],
    "pwd": [],
    "tree": [],
    "file": [],
    "stat": [],
    "diff": [],
    "diff3": [],
    "dirname": [],
    "basename": [],
    "realpath": [],
    "readlink": [],
    "md5sum": [],
    "sha256sum": [],
    "gzip": [],
    "gunzip": [],
    # --- File/Directory (Write) ---
    "mkdir": [],
    "touch": [],
    "cp": [],
    "mv": [],
    "rm": [],
    "rmdir": [],
    "patch": [],
    # --- Text Processing & Search ---
    "grep": [],
    "sort": [],
    "uniq": [],
    "cut": [],
    "awk": [],
    "sed": [],
    "tr": [],
    "tee": [],
    "ag": [],
    "rg": [],
    "jq": [],
    "xargs": [],
    "bc": [],
    "xxd": [],
    "strings": [],
    # --- Archiving ---
    "tar": [
        "--list",
        "-t",
        "tf",
        "cf",
        "xf",
        "-c",
        "-x",
    ],
    "zip": [
        "-l",
        "--list",
    ],
    "unzip": [
        "-l",
    ],
    # --- Networking (Read-Only) ---
    "curl": [],
    "wget": [],
    # --- System Info & Utilities ---
    "echo": [],
    "which": [],
    "whereis": [],
    "locate": [],
    "date": [],
    # SECURITY: whoami, hostname, uname removed — leak container identity / infra topology / kernel version
    "df": [],
    "du": [],
    "ps": [],
    # --- Version Control (Git) ---
    "git": [
        "add",
        "apply",
        "blame",
        "branch",
        "checkout",
        "cherry-pick",
        "clean",
        "clone",
        "commit",
        "diff",
        "fetch",
        "init",
        "log",
        "ls-files",
        "merge",
        "pull",
        "push",
        "rebase",
        "remote",
        "reset",
        "rev-parse",
        "show",
        "status",
        "stash",
        "tag",
    ],
    # --- Version Control (GitHub CLI) ---
    "gh": [
        "pr",
        "search",
        "issue",
        "repo",
        "api",
        "workflow",
        "run",
    ],
    # --- Version Control (GitLab CLI) ---
    "glab": [
        "mr",
        "issue",
        "repo",
        "project",
        "api",
        "ci",
        "pipeline",
        "release",
        "config",
        "auth",
        "ssh-key",
        "variable",
    ],
    # --- Language Runtimes & Execution ---
    # SECURITY: These commands are REMOVED as they can execute arbitrary code
    # If you need to run scripts, use dedicated endpoints with proper sandboxing
    # "python": [],    # REMOVED - can execute arbitrary code via -c flag
    # "python3": [],   # REMOVED - can execute arbitrary code via -c flag
    # "node": [],      # REMOVED - can execute arbitrary code via -e flag
    # "java": [],      # REMOVED - can execute arbitrary code
    # "bash": [],      # REMOVED - shell access allows arbitrary command execution
    # "sh": [],        # REMOVED - shell access allows arbitrary command execution
    # "perl": [],      # REMOVED - can execute arbitrary code via -e flag
    # "ruby": [],      # REMOVED - can execute arbitrary code via -e flag
    # --- Package Managers ---
    # SECURITY: Package manager subcommands are restricted to prevent arbitrary code execution
    # Commands like 'npm run', 'yarn run', 'poetry run' can execute arbitrary scripts
    # defined in package.json/pyproject.toml which could contain malicious code
    "pip": [
        "list",
        "show",
        "freeze",
        "install",
        "uninstall",
    ],
    "pip3": [
        "list",
        "show",
        "freeze",
        "install",
        "uninstall",
    ],
    "npm": [
        "list",
        "ls",
        "install",
        "uninstall",
        "ci",
        # SECURITY: 'run' REMOVED - can execute arbitrary scripts from package.json
        # SECURITY: 'exec' blocked in dangerous_flags_map
    ],
    "yarn": [
        "install",
        "add",
        "remove",
        # SECURITY: 'run' REMOVED - can execute arbitrary scripts from package.json
        # SECURITY: 'dlx' blocked in dangerous_flags_map
    ],
    "poetry": [
        "install",
        "add",
        "remove",
        # SECURITY: 'run' REMOVED - can execute arbitrary commands
        "build",
        "check",
    ],
    # --- Build Systems & Compilers ---
    # SECURITY: make and cmake removed — can execute arbitrary Makefile/CMakeLists targets
    "gcc": [],
    "g++": [],
    "javac": [],
    "go": [
        "build",
        # SECURITY: 'run' REMOVED - executes Go source code directly
        "test",
        "mod",
        "install",
        "get",
    ],
    "cargo": [
        "build",
        # SECURITY: 'run' REMOVED - executes compiled code directly
        "test",
        "check",
        "install",
        "update",
    ],
    "mvn": [
        "package",
        "install",
        "test",
        "clean",
    ],
    "gradle": [
        "build",
        "test",
        # SECURITY: 'run' REMOVED - executes application code directly
    ],
    # --- Testing ---
    "pytest": [],
    "jest": [],
    # --- Linters & Formatters ---
    "flake8": [],
    "black": [],
    "eslint": [],
    "prettier": [],
    "ruff": [],
    # --- Environment Management ---
    "virtualenv": [],
    "conda": [
        "list",
        "create",
        "install",
        "env",
        # SECURITY: 'run' REMOVED - can execute arbitrary commands in environments
    ],
    # --- Database ---
    "sqlite3": [],
    # --- Containerization ---
    "docker": [
        "build",
        # SECURITY: 'run' REMOVED - can escape containers, mount host filesystems, access host network
        "ps",
        "logs",
        "stop",
        "rm",
        "rmi",
        "images",
        "pull",
        "push",
    ],
    "docker-compose": [
        "up",
        "down",
        "build",
        "logs",
        "ps",
        # SECURITY: 'run' REMOVED - same risks as docker run
    ],
}


def _check_shell_metacharacters(command: list[str]) -> bool:
    """
    Check for shell metacharacters that could be used for command injection.

    NOTE: Since we use subprocess.run() with a list (not shell=True), many shell
    metacharacters are actually safe because there's no shell interpretation.
    However, we still block the most dangerous ones as a defense-in-depth measure.

    Args:
        command: Command as list of strings

    Returns:
        True if no dangerous metacharacters found, False otherwise
    """
    # Shell metacharacters that could enable command injection
    # Note: With subprocess.run() using a list, these are less dangerous but we
    # still block them as a precaution against future changes
    dangerous_patterns = [
        ";",  # Command separator
        "&",  # Background / AND operator
        "$(",  # Command substitution
        "$((",  # Arithmetic expansion
        "${",  # Variable expansion
        ">>",  # Append redirect
        "<<",  # Here document
        "<(",  # Process substitution
        ">(",  # Process substitution
    ]

    # NOTE: We intentionally DO NOT block:
    # - '|' (pipe) - Safe with subprocess list (no shell=True); used in grep regex patterns like 'foo\|bar'
    # - '\n' (newlines) - Safe with subprocess list, needed for gh pr create --body
    # - '`' (backticks) - Safe with subprocess list, may appear in markdown content

    for arg in command:
        for pattern in dangerous_patterns:
            if pattern in arg:
                logger.warning(f"Shell metacharacter '{pattern}' detected in command argument")
                return False

    return True


def _sanitize_command_for_logging(command: list[str]) -> str:
    """
    Sanitize command for logging by removing sensitive information.

    Args:
        command: Command as list of strings

    Returns:
        Sanitized command string for logging
    """
    sensitive_patterns = [
        r"(password[=:]\s*)([^\s@]+)",  # password=... or password: ...
        r"(token[=:]\s*)([^\s]+)",
        r"(key[=:]\s*)([^\s]+)",
        r"(secret[=:]\s*)([^\s]+)",
        r"(:)([^/\s]+)(@)",  # user:password@host
        r"(-p\s+)([^\s]+)",  # -p password
        r"(--password[=\s]+)([^\s]+)",
        r"(--token[=\s]+)([^\s]+)",
    ]

    command_str = " ".join(command)

    for pattern in sensitive_patterns:
        if pattern == r"(:)([^/\s]+)(@)":
            command_str = re.sub(pattern, r"\1[REDACTED]\3", command_str, flags=re.IGNORECASE)
        else:
            command_str = re.sub(pattern, r"\1[REDACTED]", command_str, flags=re.IGNORECASE)

    return command_str


def _validate_path(path: str, workspace_path: str | None = None) -> bool:
    """
    Validate that a file path is within the workspace directory.

    Args:
        path: The file path to validate
        workspace_path: The workspace directory path (required)

    Returns:
        True if path is allowed, False otherwise
    """
    try:
        # Workspace path is required for security
        if not workspace_path:
            logger.warning("Path validation failed: No workspace path configured")
            return False

        # Resolve to absolute path to prevent directory traversal
        abs_path = os.path.abspath(path)

        # Resolve symlinks to prevent symlink attacks
        try:
            real_path = os.path.realpath(abs_path)
            # Handle common platform prefixes
            real_path = real_path.removeprefix("/private")
            real_path = real_path.removeprefix("/System/Volumes/Data")
        except (OSError, RuntimeError):
            # If we can't resolve the path (e.g., doesn't exist yet), use abs_path
            real_path = abs_path.removeprefix("/private")
            real_path = real_path.removeprefix("/System/Volumes/Data")

        # Normalize workspace path
        real_workspace = os.path.realpath(workspace_path)
        real_workspace = real_workspace.removeprefix("/private")
        real_workspace = real_workspace.removeprefix("/System/Volumes/Data")

        # Check if path matches any blocked patterns
        for blocked in BLOCKED_PATHS:
            if _is_blocked_path_match(real_path, blocked):
                logger.warning(f"Path validation failed: '{real_path}' matches blocked pattern '{blocked}'")
                return False

        # Check if path is within workspace directory
        if real_path.startswith(real_workspace + os.sep) or real_path == real_workspace:
            logger.debug(f"Path validation passed: '{real_path}' is within workspace '{real_workspace}'")
            return True

        logger.warning(f"Path validation failed: '{real_path}' is not within workspace '{real_workspace}'")
        return False
    except Exception as e:
        logger.warning(f"Path validation error: {e}")
        return False


def _validate_url(url: str) -> bool:
    """
    Validate that a URL is from an allowed domain.

    Args:
        url: The URL to validate

    Returns:
        True if URL is allowed, False otherwise
    """
    try:
        parsed = urlparse(url)

        if parsed.scheme not in ["http", "https"]:
            logger.warning(f"URL validation failed: scheme '{parsed.scheme}' is not allowed")
            return False

        # Check if domain is in allowlist
        if parsed.netloc in ALLOWED_DOMAINS:
            logger.debug(f"URL validation passed: '{url}' domain is allowed")
            return True

        # Check if it's a subdomain of an allowed domain
        for allowed_domain in ALLOWED_DOMAINS:
            if parsed.netloc.endswith(f".{allowed_domain}"):
                logger.debug(f"URL validation passed: '{url}' is subdomain of allowed domain")
                return True

        logger.warning(f"URL validation failed: '{url}' domain '{parsed.netloc}' is not allowed")
        return False
    except Exception as e:
        logger.warning(f"URL validation error: {e}")
        return False


def _validate_dangerous_flags(command_name: str, command: list[str]) -> bool:
    """
    Validate and prevent the use of dangerous flags for specific commands.

    Args:
        command_name: Name of the command
        command: Full command as list

    Returns:
        True if no dangerous flags found, False otherwise
    """
    dangerous_flags_map = {
        "rm": ["-rf", "-fr", "--recursive", "--force"],
        "rmdir": ["-rf", "-fr", "--recursive", "--force"],
        "find": ["-delete"],  # -exec/-execdir allowed; workspace path validation confines them
        "tar": ["--absolute-names", "--no-overwrite-dir"],
        # sed -i (in-place edit) is allowed; workspace path validation already confines it
        # awk -f (run script file) is allowed; workspace path validation confines the script file
        "npm": ["exec", "npx"],  # Can execute arbitrary packages
        "yarn": ["dlx"],  # Can download and execute packages
    }

    if command_name in dangerous_flags_map:
        for flag in dangerous_flags_map[command_name]:
            if flag in command:
                logger.warning(f"Dangerous flag '{flag}' not allowed for {command_name}")
                return False

    # Check for combined flags like -rf
    if command_name in ["rm", "rmdir"]:
        for arg in command[1:]:
            if arg.startswith("-") and not arg.startswith("--") and "r" in arg and "f" in arg:
                logger.warning(f"Dangerous flag combination '{arg}' not allowed for {command_name}")
                return False

    return True


def _validate_file_paths(command_name: str, command: list[str], workspace_path: str | None = None) -> bool:
    """
    Validate file paths for file operation commands.

    Args:
        command_name: Name of the command
        command: Full command as list
        workspace_path: The workspace directory path

    Returns:
        True if all file paths are valid, False otherwise
    """
    if command_name in [
        "cat",
        "ls",
        "mkdir",
        "touch",
        "cp",
        "mv",
        "rm",
        "rmdir",
        "head",
        "tail",
        "patch",
    ]:
        for arg in command[1:]:
            if not arg.startswith("-") and not _validate_path(arg, workspace_path):
                logger.warning(f"Path validation failed for {command_name}: {arg}")
                return False

    if command_name == "find":
        # Only validate the search-path positional arguments (those before the first predicate).
        # Predicate values like `-name *pattern*` are not filesystem paths and must not be
        # passed to _validate_path — os.path.abspath() would resolve them relative to cwd,
        # producing paths like /app/api/*pattern* which are outside the workspace.
        for arg in command[1:]:
            if arg.startswith("-"):
                break  # hit first predicate; everything after is predicate args, not paths
            if not _validate_path(arg, workspace_path):
                logger.warning(f"Path validation failed for {command_name}: {arg}")
                return False

    return True


def _validate_git_commands(command_name: str, subcommand: str | None, command: list[str]) -> bool:
    """
    Validate git commands to prevent dangerous operations.

    Args:
        command_name: Name of the command (should be 'git')
        subcommand: Git subcommand (e.g., 'push', 'pull')
        command: Full command as list

    Returns:
        True if git command is safe, False otherwise
    """
    if command_name == "git":
        if subcommand in ["push", "pull"] and ("--force" in command or "-f" in command):
            logger.warning("Safety check failed: '--force' is not allowed for 'git push' or 'git pull'.")
            return False
        if subcommand == "clean" and ("-f" in command or "--force" in command):
            logger.warning("Safety check failed: '--force' is not allowed for 'git clean'.")
            return False
    return True


def _is_command_safe(command: list[str], workspace_path: str | None = None, skip_path_validation: bool = False) -> bool:
    """
    Check if the given command is safe to execute with comprehensive security validation.

    This is a security measure to prevent the execution of arbitrary commands.
    Includes validation for:
    - Command allowlist checking
    - Subcommand validation
    - Dangerous flag detection
    - Path validation for file operations (must be within workspace)
    - URL validation for network operations
    - Git-specific security checks

    Args:
        command: Command as a list of strings (e.g., ["git", "status"])
        workspace_path: The workspace directory path for file path validation
        skip_path_validation: When True, skip local filesystem path validation entirely.
            Use only when the command is being routed to a remote compute session, where
            paths are resolved against the remote target's filesystem, not this container's.
            Does NOT affect the local-execution fail-closed behavior when workspace_path
            is unset/unresolved.

    Returns:
        True if command is safe to execute, False otherwise
    """
    sanitized_command = _sanitize_command_for_logging(command)
    logger.debug(f"Checking safety of command: {sanitized_command}")

    if not command:
        logger.warning("Safety check failed: Empty command list provided")
        return False

    # Check for blocked paths in the command itself.
    # Strip /dev/null first — it is a safe stderr/stdout redirect target and must not
    # trigger the /dev blocked-path entry (e.g. "2>/dev/null" is a valid shell redirect).
    for part in command:
        clean_part = part.replace("/dev/null", "")
        for blocked in BLOCKED_PATHS:
            if _is_blocked_path_match(clean_part, blocked):
                logger.warning(f"Command part validation failed: '{part}' contains blocked pattern '{blocked}'")
                return False

    # Extract command name (handle full paths like /usr/bin/git)
    command_name = command[0].split("/")[-1]
    logger.debug(f"Extracted command name: {command_name}")

    # Check if command is in allowlist
    if command_name not in SAFE_COMMANDS:
        logger.warning(f"Safety check failed: Command '{command_name}' is not in SAFE_COMMANDS allowlist")
        return False

    # Get allowed subcommands for this command
    allowed_subcommands = SAFE_COMMANDS[command_name]

    # Find the subcommand (first non-flag argument that is not a path).
    # Path-like args (starting with /, ./, ../) are flag values, not subcommands
    # (e.g. `git -C /repo show ...` — `/repo` is the value of -C, not a subcommand).
    subcommand = None
    for part in command[1:]:
        if not part.startswith("-"):
            if part.startswith("/") or part.startswith("./") or part.startswith("../"):
                continue
            subcommand = part
            break

    # Check if subcommand is allowed
    if allowed_subcommands and subcommand and subcommand not in allowed_subcommands:
        logger.warning(f"Safety check failed: Subcommand '{subcommand}' is NOT allowed for '{command_name}'")
        return False

    # Comprehensive security validations
    validations = [
        _check_shell_metacharacters(command),  # SECURITY: Check for command injection
        _validate_git_commands(command_name, subcommand, command),
        _validate_dangerous_flags(command_name, command),
        skip_path_validation or _validate_file_paths(command_name, command, workspace_path),
    ]

    if not all(validations):
        logger.warning(f"Security validation failed for command: {sanitized_command}")
        return False

    # URL validation for network commands
    if command_name in ["curl", "wget"]:
        for arg in command[1:]:
            if not arg.startswith("-") and ("://" in arg or arg.startswith("http")):
                if not _validate_url(arg):
                    logger.warning(f"URL validation failed for {command_name}: {arg}")
                    return False

    logger.debug(f"Safety check passed for command: {sanitized_command}")
    return True


async def internal_run_command(
    command: list[str] | str,
    working_directory: str | None = None,
    input_text: str | None = None,
    timeout: int = 300,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Run a command-line operation in a safe and controlled manner with enterprise security.

    This tool executes commands from an allowlist of safe operations, preventing
    arbitrary command execution. It supports various development tools, version
    control, package managers, and system utilities.

    Features comprehensive security including:
    - Command allowlist validation
    - Path traversal protection
    - URL domain filtering
    - Dangerous flag detection
    - Working directory validation
    - Sensitive data sanitization in logs

    Args:
        command: Command to run as a list of strings (e.g., ["git", "status"])
        working_directory: Directory to run the command in. Defaults to workspace if not provided.
                          Can be any valid directory path.
        input_text: Text to pass to command's stdin (optional)
        timeout: Command timeout in seconds (default: 300)
        config: Configuration dictionary (optional)

    Returns:
        Dictionary with:
        - success: Boolean indicating if command succeeded
        - output: Command stdout output
        - error: Error message if command failed
        - return_code: Command exit code

    Security:
        - Only allowlisted commands can be executed
        - Subcommands are validated against allowed lists
        - Dangerous flags (e.g., rm -rf, --force for git) are blocked
        - File paths are validated against allowed directories
        - URLs are validated against allowed domains
        - Working directory is validated for safety
        - Commands run with timeout protection
        - Sensitive information is sanitized in logs
    """
    MAX_TIMEOUT = 300
    timeout = min(timeout, MAX_TIMEOUT)

    # Handle string commands by converting to list
    if isinstance(command, str):
        logger.debug(f"Converting string command to list: '{command}'")
        try:
            # Check if it's a JSON array (e.g., '["ls", "-la"]')
            if command.strip().startswith("["):
                try:
                    command = json.loads(command)
                except json.JSONDecodeError:
                    # LLMs occasionally emit command arrays as Python-literal-style
                    # strings rather than strict JSON — e.g. a grep regex alternation
                    # like "a\|b" is valid Python string syntax (an unrecognized escape
                    # is kept as a literal backslash) but invalid JSON (which requires
                    # "\\" for a literal backslash). ast.literal_eval only evaluates
                    # literal data structures (no code execution), so it's a safe
                    # fallback for this otherwise well-formed command array.
                    command = ast.literal_eval(command)
                if not isinstance(command, list):
                    raise ValueError("JSON command must be an array")
            else:
                # Use shlex for shell-style commands (e.g., "ls -la")
                command = shlex.split(command)
        except (ValueError, SyntaxError, json.JSONDecodeError) as e:
            logger.error(f"Failed to parse command string: {e}")
            return {
                "success": False,
                "output": "",
                "error": f"Invalid command format: {e}",
                "return_code": -1,
            }

    # --- Remote compute routing ---
    # If the agent has a remote ComputeSession, execute there instead of locally.
    # Security: the command allowlist check still applies; path validation is skipped
    # because paths are resolved on the remote target.
    from src.services.compute.resolver import get_compute_session_from_config

    _compute_session = await get_compute_session_from_config(config)
    if _compute_session is not None and _compute_session.is_remote:
        # Check global allowlist. Local filesystem path validation is skipped (via
        # skip_path_validation=True) since paths here are resolved on the remote target,
        # not against this container's filesystem.
        if not _is_command_safe(command, None, skip_path_validation=True):
            logger.error(f"Security check FAILED for remote command: '{_sanitize_command_for_logging(command)}'")
            return {
                "success": False,
                "output": "",
                "error": (
                    "Command is not allowed. Only allowlisted commands can be executed "
                    "(scripting interpreters like python/bash/node are blocked and cannot be "
                    "used as a workaround). To modify files, use internal_edit_file or "
                    "internal_write_file. To inspect files, use internal_read_file or internal_grep."
                ),
                "return_code": -1,
            }
        # Check per-agent command override if set
        _allowed_override = (config or {}).get("_allowed_commands_override")
        if _allowed_override is not None:
            _cmd_name = command[0].split("/")[-1]
            if _cmd_name not in _allowed_override:
                return {
                    "success": False,
                    "output": "",
                    "error": f"Command '{_cmd_name}' is not in this agent's allowed command list.",
                    "return_code": -1,
                }
        logger.info(f"Routing command to remote compute: '{_sanitize_command_for_logging(command)}'")
        return await _compute_session.exec_command(
            command=command,
            cwd=working_directory,
            timeout=timeout,
            input_text=input_text,
        )

    # Get workspace path from config or RuntimeContext (used for file path validation in commands)
    workspace_path = _get_workspace_path(config)

    # Sanitize command for logging
    sanitized_command = _sanitize_command_for_logging(command)
    logger.info(f"Received request to run command: '{sanitized_command}' in wd: '{working_directory}'")

    # Default working directory to workspace path if not provided and workspace exists
    if not working_directory and workspace_path:
        working_directory = workspace_path

    # Validate working directory exists and is within workspace
    if working_directory and not os.path.isdir(working_directory):
        logger.error(f"Working directory does not exist: '{working_directory}'")
        return {
            "success": False,
            "output": "",
            "error": f"Working directory '{working_directory}' does not exist",
            "return_code": -1,
        }
    if working_directory and workspace_path and not _validate_path(working_directory, workspace_path):
        logger.error(f"Working directory outside workspace: '{working_directory}'")
        return {
            "success": False,
            "output": "",
            "error": f"Working directory must be within workspace: {workspace_path}",
            "return_code": -1,
        }

    # Security check: Validate command is safe (allowlist + file path validation)
    if not _is_command_safe(command, workspace_path):
        logger.error(f"Security check FAILED for command: '{sanitized_command}'")
        return {
            "success": False,
            "output": "",
            "error": (
                "Command is not allowed or failed security validation. File paths must be "
                "within workspace, and scripting interpreters like python/bash/node are blocked "
                "and cannot be used as a workaround. To modify files, use internal_edit_file or "
                "internal_write_file. To inspect files, use internal_read_file or internal_grep."
            ),
            "return_code": -1,
        }

    logger.info(f"Executing safe command: '{sanitized_command}'")

    try:
        # Execute command with timeout
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,  # Don't raise exception on non-zero exit
            cwd=working_directory,
            input=input_text,
            timeout=timeout,
        )

        success = result.returncode == 0

        if success:
            logger.info(f"Command successful: '{sanitized_command}'. Return code: {result.returncode}")
        else:
            logger.warning(f"Command failed: '{sanitized_command}'. Return code: {result.returncode}")

        stdout = result.stdout
        truncated = False
        if len(stdout) > MAX_COMMAND_OUTPUT_CHARS:
            stdout = stdout[:MAX_COMMAND_OUTPUT_CHARS]
            truncated = True
            logger.warning(
                f"Command output truncated to {MAX_COMMAND_OUTPUT_CHARS} chars "
                f"(original: {len(result.stdout)} chars). "
                "Use internal_read_file with start_line/max_lines to read large files, "
                "or internal_grep to search for specific content."
            )

        if truncated:
            stdout += (
                f"\n\n[OUTPUT TRUNCATED at {MAX_COMMAND_OUTPUT_CHARS} chars - "
                f"original output was {len(result.stdout)} chars / ~{len(result.stdout) // 40} lines. "
                "Use internal_read_file(path, start_line=N, max_lines=100) to read specific sections, "
                "or internal_grep(pattern, path) to find specific content without reading the whole file.]"
            )

        return {
            "success": success,
            "output": stdout,
            "error": result.stderr if not success else "",
            "return_code": result.returncode,
        }

    except FileNotFoundError:
        logger.error(f"Command not found: {command[0]}", exc_info=True)
        return {"success": False, "output": "", "error": f"Command not found: {command[0]}", "return_code": -1}

    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out after {timeout}s: '{sanitized_command}'", exc_info=True)
        return {
            "success": False,
            "output": "",
            "error": f"Command timed out after {timeout} seconds",
            "return_code": -1,
        }

    except Exception as e:
        logger.error(f"Unexpected error executing command '{sanitized_command}': {e}", exc_info=True)
        return {"success": False, "output": "", "error": f"Unexpected error: {str(e)}", "return_code": -1}
