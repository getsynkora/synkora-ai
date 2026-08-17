"""
GitHub Pull Request Management Tools.

Provides tools for managing GitHub pull requests including:
- Merging PRs
- Closing/reopening PRs
- Updating PR title, body, labels
- Requesting reviewers
- Adding/removing labels
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
        logger.warning("⚠️ No _tool_name in config, using fallback 'github_pr_management_tools'")
        tool_name = "github_pr_management_tools"

    logger.info(f"🔍 [GitHub PR Management Tools] Looking up GitHub OAuth for tool_name='{tool_name}'")

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


async def internal_github_merge_pr(
    owner: str,
    repo: str,
    pr_number: int,
    commit_title: str | None = None,
    commit_message: str | None = None,
    merge_method: str = "merge",
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Merge a pull request.

    Args:
        owner: Repository owner (GitHub username or organization)
        repo: Repository name
        pr_number: Pull request number
        commit_title: Title for the merge commit (optional)
        commit_message: Message for the merge commit (optional)
        merge_method: Merge method - 'merge', 'squash', or 'rebase' (default: merge)
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with merge result
    """
    try:
        token = await _get_github_token(runtime_context, config, owner=owner, repo=repo)

        valid_methods = ["merge", "squash", "rebase"]
        if merge_method not in valid_methods:
            return {"success": False, "error": f"Invalid merge_method. Must be one of: {valid_methods}"}

        json_data = {"merge_method": merge_method}

        if commit_title:
            json_data["commit_title"] = commit_title
        if commit_message:
            json_data["commit_message"] = commit_message

        result = await _make_github_request(
            "PUT", f"/repos/{owner}/{repo}/pulls/{pr_number}/merge", token, json_data=json_data
        )

        return {
            "success": True,
            "merged": result.get("merged", True),
            "sha": result.get("sha"),
            "message": result.get("message", f"Pull request #{pr_number} merged successfully"),
        }

    except httpx.HTTPStatusError as e:
        error_message = str(e)
        if e.response.status_code == 405:
            error_message = "Pull request is not mergeable. It may have conflicts or require reviews."
        elif e.response.status_code == 409:
            error_message = "Merge conflict or head branch was modified."
        logger.error(f"Failed to merge PR: {error_message}", exc_info=True)
        return {"success": False, "error": error_message}
    except Exception as e:
        logger.error(f"Failed to merge PR: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_github_close_pr(
    owner: str,
    repo: str,
    pr_number: int,
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Close a pull request without merging.

    Args:
        owner: Repository owner (GitHub username or organization)
        repo: Repository name
        pr_number: Pull request number
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with close result
    """
    try:
        token = await _get_github_token(runtime_context, config, owner=owner, repo=repo)

        json_data = {"state": "closed"}

        result = await _make_github_request(
            "PATCH", f"/repos/{owner}/{repo}/pulls/{pr_number}", token, json_data=json_data
        )

        return {
            "success": True,
            "pr": {
                "number": result["number"],
                "state": result["state"],
                "title": result["title"],
                "html_url": result["html_url"],
            },
            "message": f"Pull request #{pr_number} closed successfully",
        }

    except Exception as e:
        logger.error(f"Failed to close PR: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_github_reopen_pr(
    owner: str,
    repo: str,
    pr_number: int,
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Reopen a closed pull request.

    Args:
        owner: Repository owner (GitHub username or organization)
        repo: Repository name
        pr_number: Pull request number
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with reopen result
    """
    try:
        token = await _get_github_token(runtime_context, config, owner=owner, repo=repo)

        json_data = {"state": "open"}

        result = await _make_github_request(
            "PATCH", f"/repos/{owner}/{repo}/pulls/{pr_number}", token, json_data=json_data
        )

        return {
            "success": True,
            "pr": {
                "number": result["number"],
                "state": result["state"],
                "title": result["title"],
                "html_url": result["html_url"],
            },
            "message": f"Pull request #{pr_number} reopened successfully",
        }

    except Exception as e:
        logger.error(f"Failed to reopen PR: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_github_update_pr(
    owner: str,
    repo: str,
    pr_number: int,
    title: str | None = None,
    body: str | None = None,
    base: str | None = None,
    maintainer_can_modify: bool | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Update a pull request's title, body, or base branch.

    Args:
        owner: Repository owner (GitHub username or organization)
        repo: Repository name
        pr_number: Pull request number
        title: New title for the PR (optional)
        body: New body/description for the PR (optional)
        base: New base branch (optional)
        maintainer_can_modify: Allow maintainers to push to head branch (optional)
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with updated PR details
    """
    try:
        token = await _get_github_token(runtime_context, config, owner=owner, repo=repo)

        json_data = {}
        if title is not None:
            json_data["title"] = title
        if body is not None:
            json_data["body"] = body
        if base is not None:
            json_data["base"] = base
        if maintainer_can_modify is not None:
            json_data["maintainer_can_modify"] = maintainer_can_modify

        if not json_data:
            return {"success": False, "error": "No fields to update. Provide at least one of: title, body, base"}

        result = await _make_github_request(
            "PATCH", f"/repos/{owner}/{repo}/pulls/{pr_number}", token, json_data=json_data
        )

        return {
            "success": True,
            "pr": {
                "number": result["number"],
                "title": result["title"],
                "body": result.get("body", ""),
                "state": result["state"],
                "base_branch": result["base"]["ref"],
                "html_url": result["html_url"],
            },
            "message": f"Pull request #{pr_number} updated successfully",
        }

    except Exception as e:
        logger.error(f"Failed to update PR: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_github_request_reviewers(
    owner: str,
    repo: str,
    pr_number: int,
    reviewers: list[str] | None = None,
    team_reviewers: list[str] | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Request reviewers for a pull request.

    Args:
        owner: Repository owner (GitHub username or organization)
        repo: Repository name
        pr_number: Pull request number
        reviewers: List of GitHub usernames to request as reviewers
        team_reviewers: List of team slugs to request as reviewers
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with reviewer request result
    """
    try:
        token = await _get_github_token(runtime_context, config, owner=owner, repo=repo)

        json_data = {}
        if reviewers:
            json_data["reviewers"] = reviewers
        if team_reviewers:
            json_data["team_reviewers"] = team_reviewers

        if not json_data:
            return {"success": False, "error": "Provide at least one reviewer or team_reviewer"}

        result = await _make_github_request(
            "POST", f"/repos/{owner}/{repo}/pulls/{pr_number}/requested_reviewers", token, json_data=json_data
        )

        return {
            "success": True,
            "pr": {
                "number": result["number"],
                "title": result["title"],
                "requested_reviewers": [r["login"] for r in result.get("requested_reviewers", [])],
                "requested_teams": [t["slug"] for t in result.get("requested_teams", [])],
            },
            "message": f"Reviewers requested for PR #{pr_number}",
        }

    except Exception as e:
        logger.error(f"Failed to request reviewers: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_github_remove_reviewers(
    owner: str,
    repo: str,
    pr_number: int,
    reviewers: list[str] | None = None,
    team_reviewers: list[str] | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Remove requested reviewers from a pull request.

    Args:
        owner: Repository owner (GitHub username or organization)
        repo: Repository name
        pr_number: Pull request number
        reviewers: List of GitHub usernames to remove
        team_reviewers: List of team slugs to remove
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with removal result
    """
    try:
        token = await _get_github_token(runtime_context, config, owner=owner, repo=repo)

        json_data = {}
        if reviewers:
            json_data["reviewers"] = reviewers
        if team_reviewers:
            json_data["team_reviewers"] = team_reviewers

        if not json_data:
            return {"success": False, "error": "Provide at least one reviewer or team_reviewer to remove"}

        await _make_github_request(
            "DELETE", f"/repos/{owner}/{repo}/pulls/{pr_number}/requested_reviewers", token, json_data=json_data
        )

        return {
            "success": True,
            "message": f"Reviewers removed from PR #{pr_number}",
        }

    except Exception as e:
        logger.error(f"Failed to remove reviewers: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_github_add_labels(
    owner: str,
    repo: str,
    issue_number: int,
    labels: list[str],
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Add labels to an issue or pull request.

    Args:
        owner: Repository owner (GitHub username or organization)
        repo: Repository name
        issue_number: Issue or PR number
        labels: List of label names to add
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with updated labels
    """
    try:
        token = await _get_github_token(runtime_context, config, owner=owner, repo=repo)

        json_data = {"labels": labels}

        result = await _make_github_request(
            "POST", f"/repos/{owner}/{repo}/issues/{issue_number}/labels", token, json_data=json_data
        )

        return {
            "success": True,
            "labels": [label["name"] for label in result] if isinstance(result, list) else [],
            "message": f"Labels added to #{issue_number}",
        }

    except Exception as e:
        logger.error(f"Failed to add labels: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_github_remove_label(
    owner: str,
    repo: str,
    issue_number: int,
    label: str,
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Remove a label from an issue or pull request.

    Args:
        owner: Repository owner (GitHub username or organization)
        repo: Repository name
        issue_number: Issue or PR number
        label: Label name to remove
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with removal result
    """
    try:
        token = await _get_github_token(runtime_context, config, owner=owner, repo=repo)

        # URL-encode the label name
        from urllib.parse import quote

        encoded_label = quote(label, safe="")

        await _make_github_request(
            "DELETE", f"/repos/{owner}/{repo}/issues/{issue_number}/labels/{encoded_label}", token
        )

        return {
            "success": True,
            "message": f"Label '{label}' removed from #{issue_number}",
        }

    except Exception as e:
        logger.error(f"Failed to remove label: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_github_update_branch(
    owner: str,
    repo: str,
    pr_number: int,
    expected_head_sha: str | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Update a pull request's head branch with the latest changes from the base branch.

    This is equivalent to clicking the "Update branch" button on GitHub.

    Args:
        owner: Repository owner (GitHub username or organization)
        repo: Repository name
        pr_number: Pull request number
        expected_head_sha: Expected SHA of the PR's head ref (for optimistic locking)
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with update result
    """
    try:
        token = await _get_github_token(runtime_context, config, owner=owner, repo=repo)

        json_data = {}
        if expected_head_sha:
            json_data["expected_head_sha"] = expected_head_sha

        result = await _make_github_request(
            "PUT", f"/repos/{owner}/{repo}/pulls/{pr_number}/update-branch", token, json_data=json_data
        )

        return {
            "success": True,
            "message": result.get("message", f"Branch updated for PR #{pr_number}"),
            "url": result.get("url"),
        }

    except Exception as e:
        logger.error(f"Failed to update branch: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_github_create_pr(
    repo_owner: str,
    repo_name: str,
    title: str,
    head_branch: str,
    base_branch: str = "main",
    body: str = "",
    draft: bool = False,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Create a pull request using the GitHub API.

    Uses the GitHub OAuth token from the runtime context — does not require
    the gh CLI to be installed or authenticated.

    Args:
        repo_owner: Repository owner (username or organization)
        repo_name: Repository name
        title: Pull request title
        head_branch: Branch containing the changes (source branch)
        base_branch: Branch to merge into (target branch, default: "main")
        body: Pull request description/body (markdown supported)
        draft: Whether to create as a draft PR (default: False)
        config: Configuration dictionary
        runtime_context: Runtime context for credential resolution

    Returns:
        Dictionary with success, pr_url, pr_number, and message.
    """
    try:
        import requests

        from .github_auth_helper import get_github_token_from_context

        token = await get_github_token_from_context(
            runtime_context, tool_name="internal_github_create_pr", owner=repo_owner, repo=repo_name
        )

        if not token:
            return {
                "success": False,
                "error": "No GitHub token available. Please configure GitHub OAuth for this agent.",
            }

        api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        payload = {"title": title, "head": head_branch, "base": base_branch, "body": body, "draft": draft}

        logger.info(f"Creating PR: {repo_owner}/{repo_name} - {head_branch} -> {base_branch}")
        response = requests.post(api_url, json=payload, headers=headers, timeout=30)

        if response.status_code == 201:
            pr_data = response.json()
            pr_url = pr_data.get("html_url", "")
            pr_number = pr_data.get("number", 0)
            logger.info(f"✅ Successfully created PR #{pr_number}: {pr_url}")
            return {
                "success": True,
                "pr_url": pr_url,
                "pr_number": pr_number,
                "message": f"Successfully created PR #{pr_number}",
                "state": pr_data.get("state", "open"),
                "draft": pr_data.get("draft", False),
            }

        elif response.status_code == 422:
            error_data = response.json()
            errors = error_data.get("errors", [])
            error_messages = [e.get("message", str(e)) for e in errors]

            if any("pull request already exists" in msg.lower() for msg in error_messages):
                existing_pr = await _find_existing_pr(repo_owner, repo_name, head_branch, base_branch, token)
                if existing_pr:
                    return {
                        "success": True,
                        "pr_url": existing_pr["html_url"],
                        "pr_number": existing_pr["number"],
                        "message": f"PR already exists: #{existing_pr['number']}",
                        "already_existed": True,
                    }

            error_msg = "; ".join(error_messages) if error_messages else error_data.get("message", "Unknown error")
            logger.error(f"Failed to create PR (422): {error_msg}")
            return {"success": False, "error": f"GitHub API error: {error_msg}"}

        else:
            error_data = response.json() if response.text else {}
            error_msg = error_data.get("message", f"HTTP {response.status_code}")
            logger.error(f"Failed to create PR: {error_msg}")
            return {"success": False, "error": f"GitHub API error ({response.status_code}): {error_msg}"}

    except Exception as e:
        logger.error(f"Failed to create PR: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def _find_existing_pr(
    repo_owner: str, repo_name: str, head_branch: str, base_branch: str, token: str
) -> dict[str, Any] | None:
    """Find an existing open PR for the given branches."""
    import requests

    try:
        api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls"
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        params = {"head": f"{repo_owner}:{head_branch}", "base": base_branch, "state": "open"}

        response = requests.get(api_url, headers=headers, params=params, timeout=15)
        if response.status_code == 200:
            prs = response.json()
            if prs:
                return prs[0]
        return None
    except Exception as e:
        logger.warning(f"Could not find existing PR: {e}")
        return None
