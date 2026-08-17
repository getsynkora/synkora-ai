"""
GitHub Authentication Helper for Internal Git Tools.

Extracts GitHub OAuth/PAT tokens from runtime context and injects them into Git URLs.
"""

import logging
from typing import Any
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger(__name__)


async def get_github_token_from_context(
    runtime_context: Any, tool_name: str = "github_operations", owner: str | None = None, repo: str | None = None
) -> str | None:
    """
    Extract GitHub token from runtime context.

    Args:
        runtime_context: RuntimeContext instance
        tool_name: Name of the tool requesting GitHub access
        owner: Repository owner/org being accessed (needed to pick the right
            installation for GitHub Apps installed on multiple orgs)
        repo: Repository name being accessed (used with owner)

    Returns:
        GitHub token (PAT or OAuth) or None
    """
    if not runtime_context:
        logger.debug("No runtime context provided")
        return None

    try:
        # Create credential resolver (same pattern as slack_tools.py)
        from src.services.agents.credential_resolver import CredentialResolver

        resolver = CredentialResolver(runtime_context)

        # Get GitHub client (contains the token)
        github_client = await resolver.get_github_client(tool_name, owner=owner, repo=repo)
        if not github_client:
            logger.warning(f"No GitHub client available for tool '{tool_name}'")
            return None

        # Extract token from PyGithub client internals
        # PyGithub stores auth in _Github__requester._Github__Requester__auth
        if hasattr(github_client, "_Github__requester"):
            requester = github_client._Github__requester
            if hasattr(requester, "_Requester__auth"):
                auth = requester._Requester__auth
                if hasattr(auth, "token"):
                    token = auth.token
                    logger.info("✅ Successfully extracted GitHub token from OAuth configuration")
                    return token

        logger.warning("Could not extract token from GitHub client")
        return None

    except Exception as e:
        logger.error(f"Failed to get GitHub token: {e}", exc_info=True)
        return None


def inject_token_into_url(url: str, token: str) -> str:
    """
    Inject GitHub token into HTTPS URL for authentication.

    Examples:
        'https://github.com/user/repo.git' + token
        -> 'https://x-access-token:TOKEN@github.com/user/repo.git'

        'https://github.com/user/repo' + token
        -> 'https://x-access-token:TOKEN@github.com/user/repo'

    Args:
        url: Git repository URL (HTTPS)
        token: GitHub PAT or OAuth token

    Returns:
        URL with injected token
    """
    if not url.startswith("https://"):
        logger.warning(f"URL is not HTTPS, cannot inject token: {url}")
        return url

    if not token:
        logger.warning("No token provided for injection")
        return url

    try:
        # Parse URL
        parsed = urlparse(url)

        # Check if token already exists in URL
        if "@" in parsed.netloc:
            logger.debug("Token already present in URL")
            return url

        # Inject token as username:password. A bare "TOKEN@host" (username only,
        # no password) makes git think the password is still missing and it
        # falls back to an interactive prompt, which fails with "could not
        # read Password ... No such device or address" in non-interactive
        # environments. "x-access-token" as username works for both PATs and
        # GitHub App installation tokens (ghs_ prefix).
        new_netloc = f"x-access-token:{token}@{parsed.netloc}"

        # Reconstruct URL with token
        new_parsed = parsed._replace(netloc=new_netloc)
        authenticated_url = urlunparse(new_parsed)

        logger.debug(f"Injected token into URL: {parsed.netloc} -> x-access-token:TOKEN@{parsed.netloc}")
        return authenticated_url

    except Exception as e:
        logger.error(f"Failed to inject token into URL: {e}")
        return url


async def prepare_authenticated_git_url(
    url: str,
    runtime_context: Any = None,
    tool_name: str = "github_operations",
    owner: str | None = None,
    repo: str | None = None,
) -> tuple[str, bool]:
    """
    Prepare an authenticated Git URL for clone/push/pull operations.

    This function:
    1. Tries to get GitHub token from runtime context
    2. If token available, injects it into HTTPS URL
    3. Returns authenticated URL and whether token was used

    Args:
        url: Original Git URL (can be HTTPS or SSH)
        runtime_context: RuntimeContext for credential resolution
        tool_name: Tool name for credential lookup
        owner: Repository owner/org being accessed (needed to pick the right
            installation for GitHub Apps installed on multiple orgs)
        repo: Repository name being accessed (used with owner)

    Returns:
        Tuple of (authenticated_url, used_token)
    """
    # Convert SSH to HTTPS if needed
    if url.startswith("git@"):
        # Convert git@github.com:user/repo.git -> https://github.com/user/repo.git
        url = url.replace(":", "/").replace("git@", "https://")
        logger.debug(f"Converted SSH URL to HTTPS: {url}")

    # Try to get token from context
    token = await get_github_token_from_context(runtime_context, tool_name, owner=owner, repo=repo)

    if token and url.startswith("https://"):
        # Inject token into URL
        authenticated_url = inject_token_into_url(url, token)
        return authenticated_url, True

    # No token available or not HTTPS URL
    logger.warning(
        "⚠️  No GitHub token available - Git operations may fail if SSH keys not configured. "
        "Please configure a GitHub OAuth app with 'repo' scope for the agent."
    )
    return url, False
