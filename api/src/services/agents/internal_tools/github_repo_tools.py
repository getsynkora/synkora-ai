"""
GitHub Repository Tools for repository information and content.

Provides tools for accessing repository information, README files,
directory listings, and code search.
"""

import base64
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


async def _get_github_token(
    runtime_context: dict[str, Any],
    config: dict[str, Any] | None = None,
    owner: str | None = None,
    repo: str | None = None,
) -> str:
    """Get GitHub token from runtime context or OAuth app."""
    from src.services.agents.internal_tools.github_auth_helper import get_github_token_from_context

    tool_name = None
    if config:
        tool_name = config.get("_tool_name")

    if not tool_name:
        logger.warning("⚠️ No _tool_name in config, using fallback 'github_repo_tools'")
        tool_name = "github_repo_tools"

    logger.info(f"🔍 [GitHub Repo Tools] Looking up GitHub OAuth for tool_name='{tool_name}'")

    token = await get_github_token_from_context(runtime_context, tool_name=tool_name, owner=owner, repo=repo)

    if not token:
        raise ValueError("GitHub token not found. Please configure GitHub OAuth or provide a token.")

    return token


async def _make_github_request(
    method: str,
    endpoint: str,
    token: str,
    params: dict[str, Any] | None = None,
    json_data: dict[str, Any] | None = None,
    accept: str = "application/vnd.github+json",
) -> dict[str, Any] | list[Any] | str | None:
    """Make authenticated request to GitHub API."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": accept,
        "X-GitHub-Api-Version": "2022-11-28",
    }

    url = f"https://api.github.com{endpoint}"

    # follow_redirects=True: api.github.com is a fixed, trusted host (not user-controlled,
    # so no SSRF risk) and legitimately issues 301/302s for some normalized paths (e.g. a
    # trailing/double slash on the contents endpoint). Without this, httpx's default of not
    # following redirects means response.json() below gets called on the empty redirect body.
    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.request(
            method=method, url=url, headers=headers, params=params, json=json_data, timeout=30.0
        )
        response.raise_for_status()

        if response.status_code == 204:
            return None

        # Handle raw content responses
        if accept == "application/vnd.github.raw":
            return response.text

        return response.json()


async def internal_github_get_repo_info(
    owner: str,
    repo: str,
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Get detailed information about a GitHub repository.

    Args:
        owner: Repository owner (GitHub username or organization)
        repo: Repository name
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with repository details
    """
    try:
        token = await _get_github_token(runtime_context, config, owner=owner, repo=repo)

        result = await _make_github_request("GET", f"/repos/{owner}/{repo}", token)

        return {
            "success": True,
            "repository": {
                "id": result["id"],
                "name": result["name"],
                "full_name": result["full_name"],
                "description": result.get("description"),
                "private": result["private"],
                "html_url": result["html_url"],
                "clone_url": result["clone_url"],
                "ssh_url": result["ssh_url"],
                "default_branch": result["default_branch"],
                "language": result.get("language"),
                "topics": result.get("topics", []),
                "visibility": result.get("visibility"),
                "fork": result["fork"],
                "forks_count": result["forks_count"],
                "stargazers_count": result["stargazers_count"],
                "watchers_count": result["watchers_count"],
                "open_issues_count": result["open_issues_count"],
                "size": result["size"],
                "created_at": result["created_at"],
                "updated_at": result["updated_at"],
                "pushed_at": result["pushed_at"],
                "has_issues": result["has_issues"],
                "has_wiki": result["has_wiki"],
                "has_pages": result["has_pages"],
                "archived": result["archived"],
                "disabled": result["disabled"],
                "license": result["license"]["name"] if result.get("license") else None,
                "owner": {
                    "login": result["owner"]["login"],
                    "type": result["owner"]["type"],
                    "html_url": result["owner"]["html_url"],
                },
            },
        }

    except Exception as e:
        logger.error(f"Failed to get repo info: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_github_get_readme(
    owner: str,
    repo: str,
    ref: str | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Get the README file content from a repository.

    Args:
        owner: Repository owner (GitHub username or organization)
        repo: Repository name
        ref: Branch, tag, or commit SHA (optional, defaults to default branch)
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with README content
    """
    try:
        token = await _get_github_token(runtime_context, config, owner=owner, repo=repo)

        params = {}
        if ref:
            params["ref"] = ref

        result = await _make_github_request("GET", f"/repos/{owner}/{repo}/readme", token, params=params)

        # Decode base64 content
        content = ""
        if result.get("content"):
            try:
                content = base64.b64decode(result["content"]).decode("utf-8")
            except Exception:
                content = "[Could not decode README content]"

        return {
            "success": True,
            "readme": {
                "name": result["name"],
                "path": result["path"],
                "sha": result["sha"],
                "size": result["size"],
                "html_url": result["html_url"],
                "content": content,
            },
        }

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return {"success": True, "readme": None, "message": "No README found in repository"}
        logger.warning(f"Failed to get README: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.warning(f"Failed to get README: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_github_list_repo_contents(
    owner: str,
    repo: str,
    path: str = "",
    ref: str | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    List contents of a directory in a repository.

    Args:
        owner: Repository owner (GitHub username or organization)
        repo: Repository name
        path: Path to directory (empty string for root)
        ref: Branch, tag, or commit SHA (optional, defaults to default branch)
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with directory contents
    """
    try:
        token = await _get_github_token(runtime_context, config, owner=owner, repo=repo)

        params = {}
        if ref:
            params["ref"] = ref

        endpoint = f"/repos/{owner}/{repo}/contents/{path}".rstrip("/")
        result = await _make_github_request("GET", endpoint, token, params=params)

        # Handle single file response
        if isinstance(result, dict):
            # This is a file, not a directory
            content = ""
            if result.get("content") and result.get("encoding") == "base64":
                try:
                    content = base64.b64decode(result["content"]).decode("utf-8")
                except Exception:
                    content = "[Binary file or could not decode]"

            return {
                "success": True,
                "type": "file",
                "file": {
                    "name": result["name"],
                    "path": result["path"],
                    "sha": result["sha"],
                    "size": result["size"],
                    "html_url": result["html_url"],
                    "download_url": result.get("download_url"),
                    "content": content,
                },
            }

        # Directory listing
        items = []
        for item in result if isinstance(result, list) else []:
            items.append(
                {
                    "name": item["name"],
                    "path": item["path"],
                    "type": item["type"],  # 'file', 'dir', or 'submodule'
                    "sha": item["sha"],
                    "size": item.get("size", 0),
                    "html_url": item["html_url"],
                    "download_url": item.get("download_url"),
                }
            )

        return {
            "success": True,
            "type": "directory",
            "path": path,
            "items": items,
            "count": len(items),
        }

    except Exception as e:
        logger.error(f"Failed to list repo contents: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_github_get_file_content(
    owner: str,
    repo: str,
    path: str,
    ref: str | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Get the content of a specific file from a repository.

    Args:
        owner: Repository owner (GitHub username or organization)
        repo: Repository name
        path: Path to file
        ref: Branch, tag, or commit SHA (optional, defaults to default branch)
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with file content
    """
    try:
        token = await _get_github_token(runtime_context, config, owner=owner, repo=repo)

        params = {}
        if ref:
            params["ref"] = ref

        endpoint = f"/repos/{owner}/{repo}/contents/{path}".rstrip("/")
        result = await _make_github_request("GET", endpoint, token, params=params)

        if isinstance(result, list):
            return {"success": False, "error": f"Path '{path}' is a directory, not a file"}

        # Decode base64 content
        content = ""
        if result.get("content") and result.get("encoding") == "base64":
            try:
                content = base64.b64decode(result["content"]).decode("utf-8")
            except Exception:
                content = "[Binary file or could not decode]"

        return {
            "success": True,
            "file": {
                "name": result["name"],
                "path": result["path"],
                "sha": result["sha"],
                "size": result["size"],
                "html_url": result["html_url"],
                "download_url": result.get("download_url"),
                "content": content,
            },
        }

    except Exception as e:
        logger.error(f"Failed to get file content: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_github_search_code(
    query: str,
    owner: str | None = None,
    repo: str | None = None,
    language: str | None = None,
    path: str | None = None,
    extension: str | None = None,
    per_page: int = 30,
    page: int = 1,
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Search for code across GitHub repositories.

    Args:
        query: Search query (code to find)
        owner: Filter by repository owner (optional)
        repo: Filter by specific repo as 'owner/repo' (optional)
        language: Filter by programming language (optional)
        path: Filter by file path (optional)
        extension: Filter by file extension (optional)
        per_page: Number of results per page (max 100, default 30)
        page: Page number (default 1)
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with search results
    """
    try:
        token = await _get_github_token(runtime_context, config)

        # Build search query
        q_parts = [query]
        if repo:
            q_parts.append(f"repo:{repo}")
        elif owner:
            q_parts.append(f"user:{owner}")
        if language:
            q_parts.append(f"language:{language}")
        if path:
            q_parts.append(f"path:{path}")
        if extension:
            q_parts.append(f"extension:{extension}")

        params = {
            "q": " ".join(q_parts),
            "per_page": min(per_page, 100),
            "page": page,
        }

        result = await _make_github_request("GET", "/search/code", token, params=params)

        items = []
        for item in result.get("items", []):
            items.append(
                {
                    "name": item["name"],
                    "path": item["path"],
                    "sha": item["sha"],
                    "html_url": item["html_url"],
                    "repository": item["repository"]["full_name"],
                    "score": item.get("score"),
                }
            )

        return {
            "success": True,
            "total_count": result.get("total_count", 0),
            "items": items,
            "page": page,
            "per_page": per_page,
        }

    except Exception as e:
        logger.error(f"Failed to search code: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_github_search_repos(
    query: str,
    language: str | None = None,
    sort: str | None = None,
    order: str = "desc",
    per_page: int = 30,
    page: int = 1,
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Search for repositories across GitHub.

    Args:
        query: Search query
        language: Filter by programming language (optional)
        sort: Sort by - 'stars', 'forks', 'help-wanted-issues', 'updated' (optional)
        order: Sort order - 'asc' or 'desc' (default: desc)
        per_page: Number of results per page (max 100, default 30)
        page: Page number (default 1)
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with search results
    """
    try:
        token = await _get_github_token(runtime_context, config)

        # Build search query
        q_parts = [query]
        if language:
            q_parts.append(f"language:{language}")

        params = {
            "q": " ".join(q_parts),
            "order": order,
            "per_page": min(per_page, 100),
            "page": page,
        }

        if sort:
            params["sort"] = sort

        result = await _make_github_request("GET", "/search/repositories", token, params=params)

        items = []
        for item in result.get("items", []):
            items.append(
                {
                    "full_name": item["full_name"],
                    "description": item.get("description"),
                    "html_url": item["html_url"],
                    "language": item.get("language"),
                    "topics": item.get("topics", []),
                    "stargazers_count": item["stargazers_count"],
                    "forks_count": item["forks_count"],
                    "open_issues_count": item["open_issues_count"],
                    "updated_at": item["updated_at"],
                    "license": item["license"]["name"] if item.get("license") else None,
                    "owner": item["owner"]["login"],
                }
            )

        return {
            "success": True,
            "total_count": result.get("total_count", 0),
            "items": items,
            "page": page,
            "per_page": per_page,
        }

    except Exception as e:
        logger.error(f"Failed to search repos: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_github_get_branches(
    owner: str,
    repo: str,
    protected: bool | None = None,
    per_page: int = 30,
    page: int = 1,
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    List branches in a repository.

    Args:
        owner: Repository owner (GitHub username or organization)
        repo: Repository name
        protected: Filter by protected status (optional)
        per_page: Number of branches per page (max 100, default 30)
        page: Page number (default 1)
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with list of branches
    """
    try:
        token = await _get_github_token(runtime_context, config, owner=owner, repo=repo)

        params = {
            "per_page": min(per_page, 100),
            "page": page,
        }

        if protected is not None:
            params["protected"] = str(protected).lower()

        result = await _make_github_request("GET", f"/repos/{owner}/{repo}/branches", token, params=params)

        branches = []
        for branch in result if isinstance(result, list) else []:
            branches.append(
                {
                    "name": branch["name"],
                    "sha": branch["commit"]["sha"],
                    "protected": branch.get("protected", False),
                }
            )

        return {
            "success": True,
            "branches": branches,
            "count": len(branches),
            "page": page,
            "per_page": per_page,
        }

    except Exception as e:
        logger.error(f"Failed to get branches: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_github_get_commits(
    owner: str,
    repo: str,
    sha: str | None = None,
    path: str | None = None,
    author: str | None = None,
    since: str | None = None,
    until: str | None = None,
    per_page: int = 30,
    page: int = 1,
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    List commits in a repository.

    Args:
        owner: Repository owner (GitHub username or organization)
        repo: Repository name
        sha: Branch name, tag, or commit SHA to start listing from (optional)
        path: Filter by file path (optional)
        author: Filter by author username or email (optional)
        since: Only commits after this date (ISO 8601 format, optional)
        until: Only commits before this date (ISO 8601 format, optional)
        per_page: Number of commits per page (max 100, default 30)
        page: Page number (default 1)
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with list of commits
    """
    try:
        token = await _get_github_token(runtime_context, config, owner=owner, repo=repo)

        params = {
            "per_page": min(per_page, 100),
            "page": page,
        }

        if sha:
            params["sha"] = sha
        if path:
            params["path"] = path
        if author:
            params["author"] = author
        if since:
            params["since"] = since
        if until:
            params["until"] = until

        result = await _make_github_request("GET", f"/repos/{owner}/{repo}/commits", token, params=params)

        commits = []
        for commit in result if isinstance(result, list) else []:
            commits.append(
                {
                    "sha": commit["sha"],
                    "message": commit["commit"]["message"],
                    "author": {
                        "name": commit["commit"]["author"]["name"],
                        "email": commit["commit"]["author"]["email"],
                        "date": commit["commit"]["author"]["date"],
                        "login": commit["author"]["login"] if commit.get("author") else None,
                    },
                    "committer": {
                        "name": commit["commit"]["committer"]["name"],
                        "date": commit["commit"]["committer"]["date"],
                        "login": commit["committer"]["login"] if commit.get("committer") else None,
                    },
                    "html_url": commit["html_url"],
                    "parents": [p["sha"] for p in commit.get("parents", [])],
                }
            )

        return {
            "success": True,
            "commits": commits,
            "count": len(commits),
            "page": page,
            "per_page": per_page,
        }

    except Exception as e:
        logger.error(f"Failed to get commits: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_github_get_contributors(
    owner: str,
    repo: str,
    per_page: int = 30,
    page: int = 1,
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    List contributors to a repository.

    Args:
        owner: Repository owner (GitHub username or organization)
        repo: Repository name
        per_page: Number of contributors per page (max 100, default 30)
        page: Page number (default 1)
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with list of contributors
    """
    try:
        token = await _get_github_token(runtime_context, config, owner=owner, repo=repo)

        params = {
            "per_page": min(per_page, 100),
            "page": page,
        }

        result = await _make_github_request("GET", f"/repos/{owner}/{repo}/contributors", token, params=params)

        contributors = []
        for contributor in result if isinstance(result, list) else []:
            contributors.append(
                {
                    "login": contributor["login"],
                    "contributions": contributor["contributions"],
                    "html_url": contributor["html_url"],
                    "avatar_url": contributor["avatar_url"],
                    "type": contributor["type"],
                }
            )

        return {
            "success": True,
            "contributors": contributors,
            "count": len(contributors),
            "page": page,
            "per_page": per_page,
        }

    except Exception as e:
        logger.error(f"Failed to get contributors: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
