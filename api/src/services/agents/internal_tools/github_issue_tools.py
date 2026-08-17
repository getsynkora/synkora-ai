"""
GitHub Issue Tools for managing issues.

Provides tools for creating, updating, listing, and managing GitHub issues,
including assignment and label management.
"""

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
        logger.warning("⚠️ No _tool_name in config, using fallback 'github_issue_tools'")
        tool_name = "github_issue_tools"

    logger.info(f"🔍 [GitHub Issue Tools] Looking up GitHub OAuth for tool_name='{tool_name}'")

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
) -> dict[str, Any] | list[Any] | None:
    """Make authenticated request to GitHub API."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    url = f"https://api.github.com{endpoint}"

    async with httpx.AsyncClient() as client:
        response = await client.request(
            method=method, url=url, headers=headers, params=params, json=json_data, timeout=30.0
        )
        response.raise_for_status()

        if response.status_code == 204:
            return None

        return response.json()


async def internal_github_create_issue(
    owner: str,
    repo: str,
    title: str,
    body: str = "",
    labels: list[str] | None = None,
    assignees: list[str] | None = None,
    milestone: int | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Create a new issue in a GitHub repository.

    Args:
        owner: Repository owner (GitHub username or organization)
        repo: Repository name
        title: Issue title
        body: Issue body/description (markdown supported)
        labels: List of label names to add
        assignees: List of GitHub usernames to assign
        milestone: Milestone number to associate with the issue
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with created issue details
    """
    try:
        token = await _get_github_token(runtime_context, config, owner=owner, repo=repo)

        json_data = {"title": title, "body": body}

        if labels:
            json_data["labels"] = labels
        if assignees:
            json_data["assignees"] = assignees
        if milestone:
            json_data["milestone"] = milestone

        result = await _make_github_request("POST", f"/repos/{owner}/{repo}/issues", token, json_data=json_data)

        return {
            "success": True,
            "issue": {
                "number": result["number"],
                "title": result["title"],
                "body": result.get("body", ""),
                "state": result["state"],
                "html_url": result["html_url"],
                "labels": [label["name"] for label in result.get("labels", [])],
                "assignees": [a["login"] for a in result.get("assignees", [])],
                "user": result["user"]["login"],
                "created_at": result["created_at"],
            },
            "message": f"Issue #{result['number']} created successfully",
        }

    except Exception as e:
        logger.error(f"Failed to create issue: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_github_get_issue(
    owner: str,
    repo: str,
    issue_number: int,
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Get details of a specific issue.

    Args:
        owner: Repository owner (GitHub username or organization)
        repo: Repository name
        issue_number: Issue number
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with issue details
    """
    try:
        token = await _get_github_token(runtime_context, config, owner=owner, repo=repo)

        result = await _make_github_request("GET", f"/repos/{owner}/{repo}/issues/{issue_number}", token)

        return {
            "success": True,
            "issue": {
                "number": result["number"],
                "title": result["title"],
                "body": result.get("body", ""),
                "state": result["state"],
                "state_reason": result.get("state_reason"),
                "html_url": result["html_url"],
                "labels": [label["name"] for label in result.get("labels", [])],
                "assignees": [a["login"] for a in result.get("assignees", [])],
                "user": result["user"]["login"],
                "created_at": result["created_at"],
                "updated_at": result["updated_at"],
                "closed_at": result.get("closed_at"),
                "comments": result.get("comments", 0),
                "milestone": result["milestone"]["title"] if result.get("milestone") else None,
                "is_pull_request": "pull_request" in result,
            },
        }

    except Exception as e:
        logger.error(f"Failed to get issue: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_github_list_issues(
    owner: str,
    repo: str,
    state: str = "open",
    labels: str | None = None,
    assignee: str | None = None,
    creator: str | None = None,
    mentioned: str | None = None,
    sort: str = "created",
    direction: str = "desc",
    per_page: int = 30,
    page: int = 1,
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    List issues in a repository.

    Args:
        owner: Repository owner (GitHub username or organization)
        repo: Repository name
        state: Filter by state - 'open', 'closed', or 'all' (default: open)
        labels: Comma-separated list of label names to filter by
        assignee: Filter by assignee username (use '*' for any, 'none' for unassigned)
        creator: Filter by issue creator username
        mentioned: Filter by mentioned username
        sort: Sort by - 'created', 'updated', or 'comments' (default: created)
        direction: Sort direction - 'asc' or 'desc' (default: desc)
        per_page: Number of issues per page (max 100, default 30)
        page: Page number (default 1)
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with list of issues
    """
    try:
        token = await _get_github_token(runtime_context, config, owner=owner, repo=repo)

        params = {
            "state": state,
            "sort": sort,
            "direction": direction,
            "per_page": min(per_page, 100),
            "page": page,
        }

        if labels:
            params["labels"] = labels
        if assignee:
            params["assignee"] = assignee
        if creator:
            params["creator"] = creator
        if mentioned:
            params["mentioned"] = mentioned

        result = await _make_github_request("GET", f"/repos/{owner}/{repo}/issues", token, params=params)

        issues = []
        for issue in result if isinstance(result, list) else []:
            # Skip pull requests (they appear in issues list)
            if "pull_request" in issue:
                continue

            issues.append(
                {
                    "number": issue["number"],
                    "title": issue["title"],
                    "state": issue["state"],
                    "html_url": issue["html_url"],
                    "labels": [label["name"] for label in issue.get("labels", [])],
                    "assignees": [a["login"] for a in issue.get("assignees", [])],
                    "user": issue["user"]["login"],
                    "created_at": issue["created_at"],
                    "updated_at": issue["updated_at"],
                    "comments": issue.get("comments", 0),
                }
            )

        return {
            "success": True,
            "issues": issues,
            "count": len(issues),
            "page": page,
            "per_page": per_page,
        }

    except Exception as e:
        logger.error(f"Failed to list issues: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_github_update_issue(
    owner: str,
    repo: str,
    issue_number: int,
    title: str | None = None,
    body: str | None = None,
    state: str | None = None,
    state_reason: str | None = None,
    labels: list[str] | None = None,
    assignees: list[str] | None = None,
    milestone: int | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Update an issue.

    Args:
        owner: Repository owner (GitHub username or organization)
        repo: Repository name
        issue_number: Issue number
        title: New title (optional)
        body: New body/description (optional)
        state: New state - 'open' or 'closed' (optional)
        state_reason: Reason for closing - 'completed', 'not_planned', or 'reopened' (optional)
        labels: Replace labels with this list (optional)
        assignees: Replace assignees with this list (optional)
        milestone: Milestone number (use 0 to remove, optional)
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with updated issue details
    """
    try:
        token = await _get_github_token(runtime_context, config, owner=owner, repo=repo)

        json_data = {}
        if title is not None:
            json_data["title"] = title
        if body is not None:
            json_data["body"] = body
        if state is not None:
            json_data["state"] = state
        if state_reason is not None:
            json_data["state_reason"] = state_reason
        if labels is not None:
            json_data["labels"] = labels
        if assignees is not None:
            json_data["assignees"] = assignees
        if milestone is not None:
            json_data["milestone"] = milestone if milestone != 0 else None

        if not json_data:
            return {"success": False, "error": "No fields to update"}

        result = await _make_github_request(
            "PATCH", f"/repos/{owner}/{repo}/issues/{issue_number}", token, json_data=json_data
        )

        return {
            "success": True,
            "issue": {
                "number": result["number"],
                "title": result["title"],
                "body": result.get("body", ""),
                "state": result["state"],
                "state_reason": result.get("state_reason"),
                "html_url": result["html_url"],
                "labels": [label["name"] for label in result.get("labels", [])],
                "assignees": [a["login"] for a in result.get("assignees", [])],
            },
            "message": f"Issue #{issue_number} updated successfully",
        }

    except Exception as e:
        logger.error(f"Failed to update issue: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_github_close_issue(
    owner: str,
    repo: str,
    issue_number: int,
    state_reason: str = "completed",
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Close an issue.

    Args:
        owner: Repository owner (GitHub username or organization)
        repo: Repository name
        issue_number: Issue number
        state_reason: Reason for closing - 'completed' or 'not_planned' (default: completed)
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with closed issue details
    """
    return await internal_github_update_issue(
        owner=owner,
        repo=repo,
        issue_number=issue_number,
        state="closed",
        state_reason=state_reason,
        config=config,
        runtime_context=runtime_context,
    )


async def internal_github_reopen_issue(
    owner: str,
    repo: str,
    issue_number: int,
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Reopen a closed issue.

    Args:
        owner: Repository owner (GitHub username or organization)
        repo: Repository name
        issue_number: Issue number
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with reopened issue details
    """
    return await internal_github_update_issue(
        owner=owner,
        repo=repo,
        issue_number=issue_number,
        state="open",
        state_reason="reopened",
        config=config,
        runtime_context=runtime_context,
    )


async def internal_github_assign_issue(
    owner: str,
    repo: str,
    issue_number: int,
    assignees: list[str],
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Add assignees to an issue.

    Args:
        owner: Repository owner (GitHub username or organization)
        repo: Repository name
        issue_number: Issue number
        assignees: List of GitHub usernames to assign
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with updated assignees
    """
    try:
        token = await _get_github_token(runtime_context, config, owner=owner, repo=repo)

        json_data = {"assignees": assignees}

        result = await _make_github_request(
            "POST", f"/repos/{owner}/{repo}/issues/{issue_number}/assignees", token, json_data=json_data
        )

        return {
            "success": True,
            "issue": {
                "number": result["number"],
                "title": result["title"],
                "assignees": [a["login"] for a in result.get("assignees", [])],
                "html_url": result["html_url"],
            },
            "message": f"Assignees added to issue #{issue_number}",
        }

    except Exception as e:
        logger.error(f"Failed to assign issue: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_github_unassign_issue(
    owner: str,
    repo: str,
    issue_number: int,
    assignees: list[str],
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Remove assignees from an issue.

    Args:
        owner: Repository owner (GitHub username or organization)
        repo: Repository name
        issue_number: Issue number
        assignees: List of GitHub usernames to remove
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with updated assignees
    """
    try:
        token = await _get_github_token(runtime_context, config, owner=owner, repo=repo)

        json_data = {"assignees": assignees}

        result = await _make_github_request(
            "DELETE", f"/repos/{owner}/{repo}/issues/{issue_number}/assignees", token, json_data=json_data
        )

        return {
            "success": True,
            "issue": {
                "number": result["number"],
                "title": result["title"],
                "assignees": [a["login"] for a in result.get("assignees", [])],
                "html_url": result["html_url"],
            },
            "message": f"Assignees removed from issue #{issue_number}",
        }

    except Exception as e:
        logger.error(f"Failed to unassign issue: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_github_lock_issue(
    owner: str,
    repo: str,
    issue_number: int,
    lock_reason: str | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Lock an issue to prevent comments.

    Args:
        owner: Repository owner (GitHub username or organization)
        repo: Repository name
        issue_number: Issue number
        lock_reason: Reason for locking - 'off-topic', 'too heated', 'resolved', 'spam' (optional)
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with lock result
    """
    try:
        token = await _get_github_token(runtime_context, config, owner=owner, repo=repo)

        json_data = {}
        if lock_reason:
            json_data["lock_reason"] = lock_reason

        await _make_github_request(
            "PUT",
            f"/repos/{owner}/{repo}/issues/{issue_number}/lock",
            token,
            json_data=json_data if json_data else None,
        )

        return {
            "success": True,
            "message": f"Issue #{issue_number} locked successfully",
        }

    except Exception as e:
        logger.error(f"Failed to lock issue: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_github_unlock_issue(
    owner: str,
    repo: str,
    issue_number: int,
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Unlock an issue to allow comments.

    Args:
        owner: Repository owner (GitHub username or organization)
        repo: Repository name
        issue_number: Issue number
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with unlock result
    """
    try:
        token = await _get_github_token(runtime_context, config, owner=owner, repo=repo)

        await _make_github_request("DELETE", f"/repos/{owner}/{repo}/issues/{issue_number}/lock", token)

        return {
            "success": True,
            "message": f"Issue #{issue_number} unlocked successfully",
        }

    except Exception as e:
        logger.error(f"Failed to unlock issue: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_github_search_issues(
    query: str,
    sort: str | None = None,
    order: str = "desc",
    per_page: int = 30,
    page: int = 1,
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Search for issues and pull requests across GitHub.

    Args:
        query: Search query (e.g., 'repo:owner/repo is:issue is:open label:bug')
        sort: Sort by - 'comments', 'reactions', 'created', 'updated' (optional)
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

        params = {
            "q": query,
            "per_page": min(per_page, 100),
            "page": page,
        }

        if sort:
            params["sort"] = sort
            params["order"] = order

        result = await _make_github_request("GET", "/search/issues", token, params=params)

        items = []
        for item in result.get("items", []):
            items.append(
                {
                    "number": item["number"],
                    "title": item["title"],
                    "state": item["state"],
                    "html_url": item["html_url"],
                    "repository_url": item["repository_url"],
                    "labels": [label["name"] for label in item.get("labels", [])],
                    "assignees": [a["login"] for a in item.get("assignees", [])],
                    "user": item["user"]["login"],
                    "created_at": item["created_at"],
                    "updated_at": item["updated_at"],
                    "comments": item.get("comments", 0),
                    "is_pull_request": "pull_request" in item,
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
        logger.error(f"Failed to search issues: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
