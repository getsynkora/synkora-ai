"""
GitHub Comment Tools for managing issue and PR comments.

Provides tools for creating, updating, deleting, and listing comments
on GitHub issues and pull requests.
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
) -> str | None:
    """Get GitHub token from runtime context or OAuth app. Returns None if not configured."""
    from src.services.agents.internal_tools.github_auth_helper import get_github_token_from_context

    tool_name = None
    if config:
        tool_name = config.get("_tool_name")

    if not tool_name:
        logger.warning("⚠️ No _tool_name in config, using fallback 'github_comment_tools'")
        tool_name = "github_comment_tools"

    logger.info(f"🔍 [GitHub Comment Tools] Looking up GitHub OAuth for tool_name='{tool_name}'")

    return await get_github_token_from_context(runtime_context, tool_name=tool_name, owner=owner, repo=repo)


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

        # Handle 204 No Content (e.g., delete operations)
        if response.status_code == 204:
            return None

        return response.json()


async def internal_github_post_issue_comment(
    owner: str,
    repo: str,
    issue_number: int,
    body: str,
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Post a comment on a GitHub issue.

    Note: This also works for pull requests since GitHub treats PRs as issues.

    Args:
        owner: Repository owner (GitHub username or organization)
        repo: Repository name
        issue_number: Issue number (or PR number)
        body: Comment body (markdown supported)
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with comment details
    """
    try:
        token = await _get_github_token(runtime_context, config, owner=owner, repo=repo)
        if not token:
            logger.warning("GitHub token not found — configure GitHub OAuth for this agent to post comments")
            return {"success": False, "error": "GitHub token not found. Please configure GitHub OAuth for this agent."}

        json_data = {"body": body}

        result = await _make_github_request(
            "POST", f"/repos/{owner}/{repo}/issues/{issue_number}/comments", token, json_data=json_data
        )

        return {
            "success": True,
            "comment": {
                "id": result["id"],
                "body": result["body"],
                "user": result["user"]["login"],
                "created_at": result["created_at"],
                "updated_at": result["updated_at"],
                "html_url": result["html_url"],
            },
            "message": f"Comment posted successfully on issue #{issue_number}",
        }

    except Exception as e:
        logger.error(f"Failed to post issue comment: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_github_update_comment(
    owner: str,
    repo: str,
    comment_id: int,
    body: str,
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Update an existing comment on a GitHub issue or pull request.

    Args:
        owner: Repository owner (GitHub username or organization)
        repo: Repository name
        comment_id: Comment ID to update
        body: New comment body (markdown supported)
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with updated comment details
    """
    try:
        token = await _get_github_token(runtime_context, config, owner=owner, repo=repo)
        if not token:
            logger.warning("GitHub token not found — configure GitHub OAuth for this agent to update comments")
            return {"success": False, "error": "GitHub token not found. Please configure GitHub OAuth for this agent."}

        json_data = {"body": body}

        result = await _make_github_request(
            "PATCH", f"/repos/{owner}/{repo}/issues/comments/{comment_id}", token, json_data=json_data
        )

        return {
            "success": True,
            "comment": {
                "id": result["id"],
                "body": result["body"],
                "user": result["user"]["login"],
                "created_at": result["created_at"],
                "updated_at": result["updated_at"],
                "html_url": result["html_url"],
            },
            "message": f"Comment {comment_id} updated successfully",
        }

    except Exception as e:
        logger.error(f"Failed to update comment: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_github_delete_comment(
    owner: str,
    repo: str,
    comment_id: int,
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Delete a comment from a GitHub issue or pull request.

    Args:
        owner: Repository owner (GitHub username or organization)
        repo: Repository name
        comment_id: Comment ID to delete
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with deletion confirmation
    """
    try:
        token = await _get_github_token(runtime_context, config, owner=owner, repo=repo)
        if not token:
            logger.warning("GitHub token not found — configure GitHub OAuth for this agent to delete comments")
            return {"success": False, "error": "GitHub token not found. Please configure GitHub OAuth for this agent."}

        await _make_github_request("DELETE", f"/repos/{owner}/{repo}/issues/comments/{comment_id}", token)

        return {
            "success": True,
            "message": f"Comment {comment_id} deleted successfully",
        }

    except Exception as e:
        logger.error(f"Failed to delete comment: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_github_list_comments(
    owner: str,
    repo: str,
    issue_number: int,
    per_page: int = 30,
    page: int = 1,
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    List comments on a GitHub issue or pull request.

    Args:
        owner: Repository owner (GitHub username or organization)
        repo: Repository name
        issue_number: Issue or PR number
        per_page: Number of comments per page (max 100, default 30)
        page: Page number (default 1)
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with list of comments
    """
    try:
        token = await _get_github_token(runtime_context, config, owner=owner, repo=repo)
        if not token:
            logger.warning("GitHub token not found — configure GitHub OAuth for this agent to list comments")
            return {"success": False, "error": "GitHub token not found. Please configure GitHub OAuth for this agent."}

        params = {
            "per_page": min(per_page, 100),
            "page": page,
        }

        result = await _make_github_request(
            "GET", f"/repos/{owner}/{repo}/issues/{issue_number}/comments", token, params=params
        )

        comments = []
        for comment in result if isinstance(result, list) else []:
            comments.append(
                {
                    "id": comment["id"],
                    "body": comment["body"],
                    "user": comment["user"]["login"],
                    "created_at": comment["created_at"],
                    "updated_at": comment["updated_at"],
                    "html_url": comment["html_url"],
                }
            )

        return {
            "success": True,
            "comments": comments,
            "count": len(comments),
            "page": page,
            "per_page": per_page,
        }

    except Exception as e:
        logger.error(f"Failed to list comments: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_github_get_comment(
    owner: str,
    repo: str,
    comment_id: int,
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Get a specific comment from a GitHub issue or pull request.

    Args:
        owner: Repository owner (GitHub username or organization)
        repo: Repository name
        comment_id: Comment ID
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with comment details
    """
    try:
        token = await _get_github_token(runtime_context, config, owner=owner, repo=repo)
        if not token:
            logger.warning("GitHub token not found — configure GitHub OAuth for this agent to get comments")
            return {"success": False, "error": "GitHub token not found. Please configure GitHub OAuth for this agent."}

        result = await _make_github_request("GET", f"/repos/{owner}/{repo}/issues/comments/{comment_id}", token)

        return {
            "success": True,
            "comment": {
                "id": result["id"],
                "body": result["body"],
                "user": result["user"]["login"],
                "created_at": result["created_at"],
                "updated_at": result["updated_at"],
                "html_url": result["html_url"],
                "issue_url": result.get("issue_url", ""),
            },
        }

    except Exception as e:
        logger.error(f"Failed to get comment: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_github_post_pr_review_comment(
    owner: str,
    repo: str,
    pr_number: int,
    body: str,
    commit_id: str,
    path: str,
    line: int | None = None,
    side: str = "RIGHT",
    start_line: int | None = None,
    start_side: str | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Post a review comment on a specific line of a pull request diff.

    Args:
        owner: Repository owner (GitHub username or organization)
        repo: Repository name
        pr_number: Pull request number
        body: Comment body (markdown supported)
        commit_id: SHA of the commit to comment on
        path: Relative file path to comment on
        line: Line number in the diff to comment on (single line)
        side: Which side of the diff to comment on (LEFT or RIGHT)
        start_line: First line of a multi-line comment range
        start_side: Side for start_line (LEFT or RIGHT)
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with review comment details
    """
    try:
        token = await _get_github_token(runtime_context, config, owner=owner, repo=repo)
        if not token:
            logger.warning("GitHub token not found — configure GitHub OAuth for this agent to post PR review comments")
            return {"success": False, "error": "GitHub token not found. Please configure GitHub OAuth for this agent."}

        json_data = {
            "body": body,
            "commit_id": commit_id,
            "path": path,
            "side": side,
        }

        if line is not None:
            json_data["line"] = line

        if start_line is not None:
            json_data["start_line"] = start_line
            if start_side:
                json_data["start_side"] = start_side

        result = await _make_github_request(
            "POST", f"/repos/{owner}/{repo}/pulls/{pr_number}/comments", token, json_data=json_data
        )

        return {
            "success": True,
            "comment": {
                "id": result["id"],
                "body": result["body"],
                "path": result["path"],
                "line": result.get("line"),
                "side": result.get("side"),
                "user": result["user"]["login"],
                "created_at": result["created_at"],
                "html_url": result["html_url"],
            },
            "message": f"Review comment posted on {path}",
        }

    except Exception as e:
        logger.error(f"Failed to post PR review comment: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_github_reply_to_review_comment(
    owner: str,
    repo: str,
    pr_number: int,
    comment_id: int,
    body: str,
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Reply to an existing review comment on a pull request.

    Args:
        owner: Repository owner (GitHub username or organization)
        repo: Repository name
        pr_number: Pull request number
        comment_id: ID of the review comment to reply to
        body: Reply body (markdown supported)
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with reply details
    """
    try:
        token = await _get_github_token(runtime_context, config, owner=owner, repo=repo)
        if not token:
            logger.warning("GitHub token not found — configure GitHub OAuth for this agent to reply to review comments")
            return {"success": False, "error": "GitHub token not found. Please configure GitHub OAuth for this agent."}

        json_data = {
            "body": body,
            "in_reply_to": comment_id,
        }

        result = await _make_github_request(
            "POST", f"/repos/{owner}/{repo}/pulls/{pr_number}/comments", token, json_data=json_data
        )

        return {
            "success": True,
            "comment": {
                "id": result["id"],
                "body": result["body"],
                "user": result["user"]["login"],
                "created_at": result["created_at"],
                "html_url": result["html_url"],
                "in_reply_to_id": result.get("in_reply_to_id"),
            },
            "message": f"Reply posted to comment {comment_id}",
        }

    except Exception as e:
        logger.error(f"Failed to reply to review comment: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
