"""
GitLab Tools for repository and project management.

Provides GitLab API operations including:
- User/project information
- Merge request management
- Issue management
- Repository operations
- Git clone with GitLab authentication

Supports both gitlab.com and self-hosted GitLab instances.
"""

import logging
import os
import uuid
from typing import Any
from urllib.parse import quote

import httpx

from .git_helpers import (
    _get_workspace_path,
    async_get_repo_size,
    async_makedirs,
    async_rmtree,
    async_run_git_command,
)

logger = logging.getLogger(__name__)

# Git operation limits
MAX_REPO_SIZE_MB = 500
MAX_CLONE_TIMEOUT = 600


async def _get_gitlab_credentials(runtime_context: Any, tool_name: str = "internal_gitlab_get_user") -> dict[str, Any]:
    """
    Get GitLab API credentials from runtime context.

    Args:
        runtime_context: RuntimeContext with db_session
        tool_name: Name of the tool requesting access

    Returns:
        Dict with access_token and base_url

    Raises:
        ValueError: If no token is available
    """
    from src.services.agents.credential_resolver import CredentialResolver

    resolver = CredentialResolver(runtime_context)
    token, base_url = await resolver.get_gitlab_token(tool_name)

    if not token:
        raise ValueError("No GitLab access token available. Please configure GitLab OAuth or API token.")

    return {
        "access_token": token,
        "base_url": base_url or "https://gitlab.com",
    }


async def _make_gitlab_request(
    endpoint: str,
    method: str = "GET",
    credentials: dict[str, Any] = None,
    params: dict[str, Any] = None,
    json_data: dict[str, Any] = None,
) -> dict[str, Any]:
    """Make authenticated request to GitLab API."""
    base_url = credentials.get("base_url", "https://gitlab.com").rstrip("/")
    url = f"{base_url}/api/v4{endpoint}"

    headers = {
        "Authorization": f"Bearer {credentials.get('access_token')}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient() as client:
        if method == "GET":
            response = await client.get(url, headers=headers, params=params, timeout=30.0)
        elif method == "POST":
            response = await client.post(url, headers=headers, json=json_data, timeout=30.0)
        elif method == "PUT":
            response = await client.put(url, headers=headers, json=json_data, timeout=30.0)
        elif method == "DELETE":
            response = await client.delete(url, headers=headers, timeout=30.0)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        if response.status_code == 401:
            raise ValueError("GitLab authentication failed. Token may be expired or invalid.")
        elif response.status_code == 403:
            raise ValueError("GitLab API access forbidden. Check your token permissions.")
        elif response.status_code == 404:
            raise ValueError("GitLab resource not found. Check the project/resource ID.")
        elif response.status_code == 429:
            raise ValueError("GitLab API rate limit exceeded. Please try again later.")

        response.raise_for_status()

        if response.status_code == 204 or not response.content:
            return {"success": True}

        return response.json()


async def internal_gitlab_get_user(
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Get the authenticated GitLab user's information.

    Returns:
        User profile information
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    try:
        config = config or {}
        tool_name = config.get("_tool_name", "internal_gitlab_get_user")
        credentials = await _get_gitlab_credentials(runtime_context, tool_name)

        result = await _make_gitlab_request("/user", credentials=credentials)

        return {
            "success": True,
            "user": {
                "id": result.get("id"),
                "username": result.get("username"),
                "name": result.get("name"),
                "email": result.get("email"),
                "avatar_url": result.get("avatar_url"),
                "web_url": result.get("web_url"),
                "state": result.get("state"),
                "is_admin": result.get("is_admin", False),
            },
        }

    except Exception as e:
        logger.error(f"Failed to get GitLab user: {e}")
        return {"success": False, "error": str(e)}


async def internal_gitlab_list_projects(
    owned: bool = True,
    membership: bool = False,
    search: str | None = None,
    per_page: int = 20,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    List GitLab projects accessible to the authenticated user.

    Args:
        owned: Only show projects owned by user (default: True)
        membership: Only show projects where user is a member
        search: Search term to filter projects
        per_page: Number of projects per page (max 100)

    Returns:
        List of projects
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    try:
        config = config or {}
        tool_name = config.get("_tool_name", "internal_gitlab_list_projects")
        credentials = await _get_gitlab_credentials(runtime_context, tool_name)

        params = {
            "per_page": min(per_page, 100),
            "order_by": "last_activity_at",
            "sort": "desc",
        }

        if owned:
            params["owned"] = "true"
        if membership:
            params["membership"] = "true"
        if search:
            params["search"] = search

        result = await _make_gitlab_request("/projects", credentials=credentials, params=params)

        projects = []
        for project in result if isinstance(result, list) else []:
            projects.append(
                {
                    "id": project.get("id"),
                    "name": project.get("name"),
                    "path_with_namespace": project.get("path_with_namespace"),
                    "description": project.get("description"),
                    "web_url": project.get("web_url"),
                    "ssh_url_to_repo": project.get("ssh_url_to_repo"),
                    "http_url_to_repo": project.get("http_url_to_repo"),
                    "default_branch": project.get("default_branch"),
                    "visibility": project.get("visibility"),
                    "last_activity_at": project.get("last_activity_at"),
                    "open_issues_count": project.get("open_issues_count"),
                    "forks_count": project.get("forks_count"),
                    "star_count": project.get("star_count"),
                }
            )

        return {
            "success": True,
            "projects": projects,
            "count": len(projects),
        }

    except Exception as e:
        logger.error(f"Failed to list GitLab projects: {e}")
        return {"success": False, "error": str(e)}


async def internal_gitlab_get_project(
    project_id: str,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Get detailed information about a GitLab project.

    Args:
        project_id: Project ID or URL-encoded path (e.g., "123" or "namespace/project")

    Returns:
        Project details
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    if not project_id:
        return {"success": False, "error": "Project ID is required"}

    try:
        config = config or {}
        tool_name = config.get("_tool_name", "internal_gitlab_get_project")
        credentials = await _get_gitlab_credentials(runtime_context, tool_name)

        # URL-encode project path if it contains /
        encoded_id = quote(str(project_id), safe="")

        result = await _make_gitlab_request(f"/projects/{encoded_id}", credentials=credentials)

        return {
            "success": True,
            "project": {
                "id": result.get("id"),
                "name": result.get("name"),
                "path_with_namespace": result.get("path_with_namespace"),
                "description": result.get("description"),
                "web_url": result.get("web_url"),
                "ssh_url_to_repo": result.get("ssh_url_to_repo"),
                "http_url_to_repo": result.get("http_url_to_repo"),
                "default_branch": result.get("default_branch"),
                "visibility": result.get("visibility"),
                "created_at": result.get("created_at"),
                "last_activity_at": result.get("last_activity_at"),
                "open_issues_count": result.get("open_issues_count"),
                "forks_count": result.get("forks_count"),
                "star_count": result.get("star_count"),
                "namespace": result.get("namespace", {}).get("full_path"),
            },
        }

    except Exception as e:
        logger.error(f"Failed to get GitLab project: {e}")
        return {"success": False, "error": str(e)}


async def internal_gitlab_create_merge_request(
    project_id: str,
    source_branch: str,
    target_branch: str,
    title: str,
    description: str = "",
    remove_source_branch: bool = False,
    squash: bool = False,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Create a merge request in a GitLab project.

    Args:
        project_id: Project ID or URL-encoded path
        source_branch: Branch containing changes
        target_branch: Branch to merge into
        title: Merge request title
        description: Merge request description (markdown supported)
        remove_source_branch: Delete source branch after merge
        squash: Squash commits on merge

    Returns:
        Created merge request details
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    if not all([project_id, source_branch, target_branch, title]):
        return {"success": False, "error": "project_id, source_branch, target_branch, and title are required"}

    try:
        config = config or {}
        tool_name = config.get("_tool_name", "internal_gitlab_create_merge_request")
        credentials = await _get_gitlab_credentials(runtime_context, tool_name)

        encoded_id = quote(str(project_id), safe="")

        json_data = {
            "source_branch": source_branch,
            "target_branch": target_branch,
            "title": title,
            "description": description,
            "remove_source_branch": remove_source_branch,
            "squash": squash,
        }

        result = await _make_gitlab_request(
            f"/projects/{encoded_id}/merge_requests",
            method="POST",
            credentials=credentials,
            json_data=json_data,
        )

        return {
            "success": True,
            "merge_request": {
                "id": result.get("id"),
                "iid": result.get("iid"),
                "title": result.get("title"),
                "state": result.get("state"),
                "web_url": result.get("web_url"),
                "source_branch": result.get("source_branch"),
                "target_branch": result.get("target_branch"),
                "author": result.get("author", {}).get("username"),
            },
            "message": f"Merge request !{result.get('iid')} created successfully",
        }

    except Exception as e:
        logger.error(f"Failed to create GitLab merge request: {e}")
        return {"success": False, "error": str(e)}


async def internal_gitlab_list_merge_requests(
    project_id: str,
    state: str = "opened",
    per_page: int = 20,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    List merge requests for a GitLab project.

    Args:
        project_id: Project ID or URL-encoded path
        state: Filter by state (opened, closed, merged, all)
        per_page: Number of MRs per page (max 100)

    Returns:
        List of merge requests
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    if not project_id:
        return {"success": False, "error": "Project ID is required"}

    try:
        config = config or {}
        tool_name = config.get("_tool_name", "internal_gitlab_list_merge_requests")
        credentials = await _get_gitlab_credentials(runtime_context, tool_name)

        encoded_id = quote(str(project_id), safe="")

        params = {
            "state": state,
            "per_page": min(per_page, 100),
            "order_by": "updated_at",
            "sort": "desc",
        }

        result = await _make_gitlab_request(
            f"/projects/{encoded_id}/merge_requests",
            credentials=credentials,
            params=params,
        )

        merge_requests = []
        for mr in result if isinstance(result, list) else []:
            merge_requests.append(
                {
                    "id": mr.get("id"),
                    "iid": mr.get("iid"),
                    "title": mr.get("title"),
                    "state": mr.get("state"),
                    "web_url": mr.get("web_url"),
                    "source_branch": mr.get("source_branch"),
                    "target_branch": mr.get("target_branch"),
                    "author": mr.get("author", {}).get("username"),
                    "created_at": mr.get("created_at"),
                    "updated_at": mr.get("updated_at"),
                    "merge_status": mr.get("merge_status"),
                }
            )

        return {
            "success": True,
            "merge_requests": merge_requests,
            "count": len(merge_requests),
        }

    except Exception as e:
        logger.error(f"Failed to list GitLab merge requests: {e}")
        return {"success": False, "error": str(e)}


async def internal_gitlab_get_merge_request(
    project_id: str,
    merge_request_iid: int,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Get details of a specific merge request.

    Args:
        project_id: Project ID or URL-encoded path
        merge_request_iid: Merge request internal ID (IID, not ID)

    Returns:
        Merge request details
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    if not project_id or not merge_request_iid:
        return {"success": False, "error": "project_id and merge_request_iid are required"}

    try:
        config = config or {}
        tool_name = config.get("_tool_name", "internal_gitlab_get_merge_request")
        credentials = await _get_gitlab_credentials(runtime_context, tool_name)

        encoded_id = quote(str(project_id), safe="")

        result = await _make_gitlab_request(
            f"/projects/{encoded_id}/merge_requests/{merge_request_iid}",
            credentials=credentials,
        )

        return {
            "success": True,
            "merge_request": {
                "id": result.get("id"),
                "iid": result.get("iid"),
                "title": result.get("title"),
                "description": result.get("description"),
                "state": result.get("state"),
                "web_url": result.get("web_url"),
                "source_branch": result.get("source_branch"),
                "target_branch": result.get("target_branch"),
                "author": result.get("author", {}).get("username"),
                "assignee": result.get("assignee", {}).get("username") if result.get("assignee") else None,
                "created_at": result.get("created_at"),
                "updated_at": result.get("updated_at"),
                "merged_at": result.get("merged_at"),
                "closed_at": result.get("closed_at"),
                "merge_status": result.get("merge_status"),
                "has_conflicts": result.get("has_conflicts"),
                "changes_count": result.get("changes_count"),
            },
        }

    except Exception as e:
        logger.error(f"Failed to get GitLab merge request: {e}")
        return {"success": False, "error": str(e)}


async def internal_gitlab_list_issues(
    project_id: str,
    state: str = "opened",
    labels: str | None = None,
    per_page: int = 20,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    List issues for a GitLab project.

    Args:
        project_id: Project ID or URL-encoded path
        state: Filter by state (opened, closed, all)
        labels: Comma-separated list of label names
        per_page: Number of issues per page (max 100)

    Returns:
        List of issues
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    if not project_id:
        return {"success": False, "error": "Project ID is required"}

    try:
        config = config or {}
        tool_name = config.get("_tool_name", "internal_gitlab_list_issues")
        credentials = await _get_gitlab_credentials(runtime_context, tool_name)

        encoded_id = quote(str(project_id), safe="")

        params = {
            "state": state,
            "per_page": min(per_page, 100),
            "order_by": "updated_at",
            "sort": "desc",
        }

        if labels:
            params["labels"] = labels

        result = await _make_gitlab_request(
            f"/projects/{encoded_id}/issues",
            credentials=credentials,
            params=params,
        )

        issues = []
        for issue in result if isinstance(result, list) else []:
            issues.append(
                {
                    "id": issue.get("id"),
                    "iid": issue.get("iid"),
                    "title": issue.get("title"),
                    "state": issue.get("state"),
                    "web_url": issue.get("web_url"),
                    "author": issue.get("author", {}).get("username"),
                    "assignee": issue.get("assignee", {}).get("username") if issue.get("assignee") else None,
                    "labels": issue.get("labels", []),
                    "created_at": issue.get("created_at"),
                    "updated_at": issue.get("updated_at"),
                }
            )

        return {
            "success": True,
            "issues": issues,
            "count": len(issues),
        }

    except Exception as e:
        logger.error(f"Failed to list GitLab issues: {e}")
        return {"success": False, "error": str(e)}


async def internal_gitlab_create_issue(
    project_id: str,
    title: str,
    description: str = "",
    labels: str | None = None,
    assignee_ids: list[int] | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Create an issue in a GitLab project.

    Args:
        project_id: Project ID or URL-encoded path
        title: Issue title
        description: Issue description (markdown supported)
        labels: Comma-separated list of label names
        assignee_ids: List of user IDs to assign

    Returns:
        Created issue details
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    if not project_id or not title:
        return {"success": False, "error": "project_id and title are required"}

    try:
        config = config or {}
        tool_name = config.get("_tool_name", "internal_gitlab_create_issue")
        credentials = await _get_gitlab_credentials(runtime_context, tool_name)

        encoded_id = quote(str(project_id), safe="")

        json_data = {
            "title": title,
            "description": description,
        }

        if labels:
            json_data["labels"] = labels
        if assignee_ids:
            json_data["assignee_ids"] = assignee_ids

        result = await _make_gitlab_request(
            f"/projects/{encoded_id}/issues",
            method="POST",
            credentials=credentials,
            json_data=json_data,
        )

        return {
            "success": True,
            "issue": {
                "id": result.get("id"),
                "iid": result.get("iid"),
                "title": result.get("title"),
                "state": result.get("state"),
                "web_url": result.get("web_url"),
                "author": result.get("author", {}).get("username"),
            },
            "message": f"Issue #{result.get('iid')} created successfully",
        }

    except Exception as e:
        logger.error(f"Failed to create GitLab issue: {e}")
        return {"success": False, "error": str(e)}


async def internal_gitlab_list_branches(
    project_id: str,
    search: str | None = None,
    per_page: int = 20,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    List branches in a GitLab project.

    Args:
        project_id: Project ID or URL-encoded path
        search: Search term to filter branches
        per_page: Number of branches per page (max 100)

    Returns:
        List of branches
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    if not project_id:
        return {"success": False, "error": "Project ID is required"}

    try:
        config = config or {}
        tool_name = config.get("_tool_name", "internal_gitlab_list_branches")
        credentials = await _get_gitlab_credentials(runtime_context, tool_name)

        encoded_id = quote(str(project_id), safe="")

        params = {"per_page": min(per_page, 100)}
        if search:
            params["search"] = search

        result = await _make_gitlab_request(
            f"/projects/{encoded_id}/repository/branches",
            credentials=credentials,
            params=params,
        )

        branches = []
        for branch in result if isinstance(result, list) else []:
            branches.append(
                {
                    "name": branch.get("name"),
                    "merged": branch.get("merged"),
                    "protected": branch.get("protected"),
                    "default": branch.get("default"),
                    "web_url": branch.get("web_url"),
                    "commit": {
                        "id": branch.get("commit", {}).get("id"),
                        "message": branch.get("commit", {}).get("message"),
                        "author": branch.get("commit", {}).get("author_name"),
                        "committed_at": branch.get("commit", {}).get("committed_date"),
                    },
                }
            )

        return {
            "success": True,
            "branches": branches,
            "count": len(branches),
        }

    except Exception as e:
        logger.error(f"Failed to list GitLab branches: {e}")
        return {"success": False, "error": str(e)}


async def internal_gitlab_create_branch(
    project_id: str,
    branch_name: str,
    ref: str = "main",
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Create a new branch in a GitLab project.

    Args:
        project_id: Project ID or URL-encoded path
        branch_name: Name of the new branch to create
        ref: Source branch, tag, or commit SHA to create branch from (default: main)

    Returns:
        Created branch details
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    if not project_id or not branch_name:
        return {"success": False, "error": "project_id and branch_name are required"}

    try:
        config = config or {}
        tool_name = config.get("_tool_name", "internal_gitlab_create_branch")
        credentials = await _get_gitlab_credentials(runtime_context, tool_name)

        encoded_id = quote(str(project_id), safe="")

        json_data = {
            "branch": branch_name,
            "ref": ref,
        }

        result = await _make_gitlab_request(
            f"/projects/{encoded_id}/repository/branches",
            method="POST",
            credentials=credentials,
            json_data=json_data,
        )

        return {
            "success": True,
            "branch": {
                "name": result.get("name"),
                "merged": result.get("merged"),
                "protected": result.get("protected"),
                "default": result.get("default"),
                "web_url": result.get("web_url"),
                "commit": {
                    "id": result.get("commit", {}).get("id"),
                    "message": result.get("commit", {}).get("message"),
                    "author": result.get("commit", {}).get("author_name"),
                    "committed_at": result.get("commit", {}).get("committed_date"),
                },
            },
            "message": f"Branch '{branch_name}' created successfully from '{ref}'",
        }

    except Exception as e:
        logger.error(f"Failed to create GitLab branch: {e}")
        return {"success": False, "error": str(e)}


async def internal_gitlab_create_file(
    project_id: str,
    file_path: str,
    content: str,
    commit_message: str,
    branch: str = "main",
    encoding: str = "text",
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Create a new file in a GitLab repository.

    Args:
        project_id: Project ID or URL-encoded path
        file_path: Path for the new file in the repository
        content: File content
        commit_message: Commit message for this change
        branch: Branch to create the file in (default: main)
        encoding: Content encoding - 'text' or 'base64' (default: text)

    Returns:
        Created file details
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    if not all([project_id, file_path, content, commit_message]):
        return {"success": False, "error": "project_id, file_path, content, and commit_message are required"}

    try:
        config = config or {}
        tool_name = config.get("_tool_name", "internal_gitlab_create_file")
        credentials = await _get_gitlab_credentials(runtime_context, tool_name)

        encoded_project = quote(str(project_id), safe="")
        encoded_file = quote(file_path, safe="")

        json_data = {
            "branch": branch,
            "content": content,
            "commit_message": commit_message,
            "encoding": encoding,
        }

        result = await _make_gitlab_request(
            f"/projects/{encoded_project}/repository/files/{encoded_file}",
            method="POST",
            credentials=credentials,
            json_data=json_data,
        )

        return {
            "success": True,
            "file": {
                "file_path": result.get("file_path"),
                "branch": result.get("branch"),
            },
            "message": f"File '{file_path}' created successfully on branch '{branch}'",
        }

    except Exception as e:
        logger.error(f"Failed to create GitLab file: {e}")
        return {"success": False, "error": str(e)}


async def internal_gitlab_update_file(
    project_id: str,
    file_path: str,
    content: str,
    commit_message: str,
    branch: str = "main",
    encoding: str = "text",
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Update an existing file in a GitLab repository.

    Args:
        project_id: Project ID or URL-encoded path
        file_path: Path to the file in the repository
        content: New file content
        commit_message: Commit message for this change
        branch: Branch containing the file (default: main)
        encoding: Content encoding - 'text' or 'base64' (default: text)

    Returns:
        Updated file details
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    if not all([project_id, file_path, content, commit_message]):
        return {"success": False, "error": "project_id, file_path, content, and commit_message are required"}

    try:
        config = config or {}
        tool_name = config.get("_tool_name", "internal_gitlab_update_file")
        credentials = await _get_gitlab_credentials(runtime_context, tool_name)

        encoded_project = quote(str(project_id), safe="")
        encoded_file = quote(file_path, safe="")

        json_data = {
            "branch": branch,
            "content": content,
            "commit_message": commit_message,
            "encoding": encoding,
        }

        result = await _make_gitlab_request(
            f"/projects/{encoded_project}/repository/files/{encoded_file}",
            method="PUT",
            credentials=credentials,
            json_data=json_data,
        )

        return {
            "success": True,
            "file": {
                "file_path": result.get("file_path"),
                "branch": result.get("branch"),
            },
            "message": f"File '{file_path}' updated successfully on branch '{branch}'",
        }

    except Exception as e:
        logger.error(f"Failed to update GitLab file: {e}")
        return {"success": False, "error": str(e)}


async def internal_gitlab_delete_file(
    project_id: str,
    file_path: str,
    commit_message: str,
    branch: str = "main",
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Delete a file from a GitLab repository.

    Args:
        project_id: Project ID or URL-encoded path
        file_path: Path to the file in the repository
        commit_message: Commit message for this deletion
        branch: Branch containing the file (default: main)

    Returns:
        Deletion confirmation
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    if not all([project_id, file_path, commit_message]):
        return {"success": False, "error": "project_id, file_path, and commit_message are required"}

    try:
        config = config or {}
        tool_name = config.get("_tool_name", "internal_gitlab_delete_file")
        credentials = await _get_gitlab_credentials(runtime_context, tool_name)

        encoded_project = quote(str(project_id), safe="")
        encoded_file = quote(file_path, safe="")

        json_data = {
            "branch": branch,
            "commit_message": commit_message,
        }

        await _make_gitlab_request(
            f"/projects/{encoded_project}/repository/files/{encoded_file}",
            method="DELETE",
            credentials=credentials,
            json_data=json_data,
        )

        return {
            "success": True,
            "message": f"File '{file_path}' deleted successfully from branch '{branch}'",
        }

    except Exception as e:
        logger.error(f"Failed to delete GitLab file: {e}")
        return {"success": False, "error": str(e)}


async def internal_gitlab_get_file(
    project_id: str,
    file_path: str,
    ref: str = "main",
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Get a file from a GitLab repository.

    Args:
        project_id: Project ID or URL-encoded path
        file_path: Path to the file in the repository
        ref: Branch, tag, or commit SHA (default: main)

    Returns:
        File content and metadata
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    if not project_id or not file_path:
        return {"success": False, "error": "project_id and file_path are required"}

    try:
        config = config or {}
        tool_name = config.get("_tool_name", "internal_gitlab_get_file")
        credentials = await _get_gitlab_credentials(runtime_context, tool_name)

        encoded_project = quote(str(project_id), safe="")
        encoded_file = quote(file_path, safe="")

        params = {"ref": ref}

        result = await _make_gitlab_request(
            f"/projects/{encoded_project}/repository/files/{encoded_file}",
            credentials=credentials,
            params=params,
        )

        import base64

        content = ""
        if result.get("content"):
            try:
                content = base64.b64decode(result.get("content")).decode("utf-8")
            except Exception:
                content = "[Binary file - cannot decode]"

        return {
            "success": True,
            "file": {
                "file_name": result.get("file_name"),
                "file_path": result.get("file_path"),
                "size": result.get("size"),
                "encoding": result.get("encoding"),
                "ref": result.get("ref"),
                "content": content,
                "last_commit_id": result.get("last_commit_id"),
            },
        }

    except Exception as e:
        logger.error(f"Failed to get GitLab file: {e}")
        return {"success": False, "error": str(e)}


async def internal_gitlab_clone_repo(
    repo_url: str,
    use_ssh: bool = False,
    depth: int = 1,
    branch: str | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Clone a GitLab repository into the workspace directory.

    Uses GitLab OAuth or API token for authentication when available.

    Defaults to a shallow, single-branch clone (depth=1): a full clone of a
    large repo is a single long-lived, large HTTP transfer, which is fragile
    to mid-stream network failures regardless of repo size. Pass depth=0 for
    a full clone when the task genuinely needs complete history.

    Args:
        repo_url: GitLab repository URL (HTTPS or SSH)
        use_ssh: Whether to use SSH instead of HTTPS (default: False)
        depth: Number of commits of history to fetch (default: 1, shallow). Pass 0 for a full clone.
        branch: Specific branch to clone directly (default: None, clones the repo's default branch)
        config: Configuration dictionary containing workspace_path
        runtime_context: Runtime context for credential resolution

    Returns:
        Dictionary with:
        - success: bool
        - repo_path: str (path to cloned repository within workspace)
        - message: str
        - error: str (if failed)
    """
    if not repo_url:
        return {"success": False, "error": "Repository URL is required", "repo_path": None}

    try:
        from .gitlab_auth_helper import prepare_authenticated_gitlab_url

        # Get workspace path
        workspace_path = _get_workspace_path(config)
        if not workspace_path:
            return {
                "success": False,
                "error": "No workspace path configured. Clone requires a valid workspace.",
                "repo_path": None,
            }

        # Prepare authenticated URL (injects GitLab token if available)
        if not use_ssh and runtime_context:
            config = config or {}
            tool_name = config.get("_tool_name", "internal_gitlab_clone_repo")
            repo_url, used_token = await prepare_authenticated_gitlab_url(
                repo_url, runtime_context, tool_name=tool_name
            )
            if used_token:
                logger.info("✅ Using GitLab OAuth/API token for authentication")
        elif use_ssh:
            # Convert HTTPS to SSH if requested (requires SSH keys configured)
            if repo_url.startswith("https://"):
                repo_url = repo_url.replace("https://", "git@").replace("/", ":", 1)
                logger.info(f"Converted to SSH URL: {repo_url}")

        # Create repos directory within workspace
        repos_dir = os.path.join(workspace_path, "repos")
        await async_makedirs(repos_dir, config)

        # Generate unique directory name for the repo
        repo_dir = os.path.join(repos_dir, f"gitlab_{uuid.uuid4().hex[:12]}")
        clone_cmd = ["git", "clone"]
        if depth > 0:
            clone_cmd.extend(["--depth", str(depth)])
        if branch:
            clone_cmd.extend(["--branch", branch])
        clone_cmd.extend([repo_url, repo_dir])

        logger.info(
            f"Cloning GitLab repo '{repo_url}' into {repo_dir} (depth={depth or 'full'}, branch={branch or 'default'})"
        )

        # Clone the repository
        result = await async_run_git_command(
            clone_cmd,
            working_directory=None,
            config=config,
            timeout=MAX_CLONE_TIMEOUT,
        )

        if not result["success"]:
            await async_rmtree(repo_dir, config)
            return {"success": False, "error": f"Failed to clone repository: {result['error']}", "repo_path": None}

        # Check repository size
        repo_size = await async_get_repo_size(repo_dir, config)
        if repo_size > MAX_REPO_SIZE_MB:
            await async_rmtree(repo_dir, config)
            return {
                "success": False,
                "error": f"Repository size ({repo_size:.1f}MB) exceeds maximum ({MAX_REPO_SIZE_MB}MB)",
                "repo_path": None,
            }

        logger.info(f"Successfully cloned GitLab repository to {repo_dir} (size: {repo_size:.1f}MB)")
        return {
            "success": True,
            "repo_path": repo_dir,
            "message": f"Successfully cloned repository to {repo_dir}",
            "size_mb": round(repo_size, 2),
        }

    except Exception as e:
        logger.error(f"Failed to clone GitLab repository: {e}", exc_info=True)
        return {"success": False, "error": str(e), "repo_path": None}


# =============================================================================
# Comment Tools
# =============================================================================


async def internal_gitlab_post_mr_comment(
    project_id: str,
    merge_request_iid: int,
    body: str,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Post a comment (note) on a GitLab merge request.

    Args:
        project_id: Project ID or URL-encoded path
        merge_request_iid: Merge request internal ID (IID)
        body: Comment body (markdown supported)

    Returns:
        Created comment details
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    if not project_id or not merge_request_iid or not body:
        return {"success": False, "error": "project_id, merge_request_iid, and body are required"}

    try:
        config = config or {}
        tool_name = config.get("_tool_name", "internal_gitlab_post_mr_comment")
        credentials = await _get_gitlab_credentials(runtime_context, tool_name)

        encoded_id = quote(str(project_id), safe="")

        json_data = {"body": body}

        result = await _make_gitlab_request(
            f"/projects/{encoded_id}/merge_requests/{merge_request_iid}/notes",
            method="POST",
            credentials=credentials,
            json_data=json_data,
        )

        return {
            "success": True,
            "comment": {
                "id": result.get("id"),
                "body": result.get("body"),
                "author": result.get("author", {}).get("username"),
                "created_at": result.get("created_at"),
            },
            "message": f"Comment posted on MR !{merge_request_iid}",
        }

    except Exception as e:
        logger.error(f"Failed to post MR comment: {e}")
        return {"success": False, "error": str(e)}


async def internal_gitlab_post_issue_comment(
    project_id: str,
    issue_iid: int,
    body: str,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Post a comment (note) on a GitLab issue.

    Args:
        project_id: Project ID or URL-encoded path
        issue_iid: Issue internal ID (IID)
        body: Comment body (markdown supported)

    Returns:
        Created comment details
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    if not project_id or not issue_iid or not body:
        return {"success": False, "error": "project_id, issue_iid, and body are required"}

    try:
        config = config or {}
        tool_name = config.get("_tool_name", "internal_gitlab_post_issue_comment")
        credentials = await _get_gitlab_credentials(runtime_context, tool_name)

        encoded_id = quote(str(project_id), safe="")

        json_data = {"body": body}

        result = await _make_gitlab_request(
            f"/projects/{encoded_id}/issues/{issue_iid}/notes",
            method="POST",
            credentials=credentials,
            json_data=json_data,
        )

        return {
            "success": True,
            "comment": {
                "id": result.get("id"),
                "body": result.get("body"),
                "author": result.get("author", {}).get("username"),
                "created_at": result.get("created_at"),
            },
            "message": f"Comment posted on issue #{issue_iid}",
        }

    except Exception as e:
        logger.error(f"Failed to post issue comment: {e}")
        return {"success": False, "error": str(e)}


async def internal_gitlab_update_note(
    project_id: str,
    noteable_type: str,
    noteable_iid: int,
    note_id: int,
    body: str,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Update a comment (note) on a GitLab merge request or issue.

    Args:
        project_id: Project ID or URL-encoded path
        noteable_type: 'merge_requests' or 'issues'
        noteable_iid: MR or issue internal ID (IID)
        note_id: Note ID to update
        body: New comment body (markdown supported)

    Returns:
        Updated comment details
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    if noteable_type not in ["merge_requests", "issues"]:
        return {"success": False, "error": "noteable_type must be 'merge_requests' or 'issues'"}

    try:
        config = config or {}
        tool_name = config.get("_tool_name", "internal_gitlab_update_note")
        credentials = await _get_gitlab_credentials(runtime_context, tool_name)

        encoded_id = quote(str(project_id), safe="")

        json_data = {"body": body}

        result = await _make_gitlab_request(
            f"/projects/{encoded_id}/{noteable_type}/{noteable_iid}/notes/{note_id}",
            method="PUT",
            credentials=credentials,
            json_data=json_data,
        )

        return {
            "success": True,
            "comment": {
                "id": result.get("id"),
                "body": result.get("body"),
                "author": result.get("author", {}).get("username"),
                "updated_at": result.get("updated_at"),
            },
            "message": f"Comment {note_id} updated",
        }

    except Exception as e:
        logger.error(f"Failed to update note: {e}")
        return {"success": False, "error": str(e)}


async def internal_gitlab_list_mr_comments(
    project_id: str,
    merge_request_iid: int,
    per_page: int = 20,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    List comments (notes) on a GitLab merge request.

    Args:
        project_id: Project ID or URL-encoded path
        merge_request_iid: Merge request internal ID (IID)
        per_page: Number of comments per page (max 100)

    Returns:
        List of comments
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    if not project_id or not merge_request_iid:
        return {"success": False, "error": "project_id and merge_request_iid are required"}

    try:
        config = config or {}
        tool_name = config.get("_tool_name", "internal_gitlab_list_mr_comments")
        credentials = await _get_gitlab_credentials(runtime_context, tool_name)

        encoded_id = quote(str(project_id), safe="")

        params = {"per_page": min(per_page, 100), "sort": "asc"}

        result = await _make_gitlab_request(
            f"/projects/{encoded_id}/merge_requests/{merge_request_iid}/notes",
            credentials=credentials,
            params=params,
        )

        comments = []
        for note in result if isinstance(result, list) else []:
            comments.append(
                {
                    "id": note.get("id"),
                    "body": note.get("body"),
                    "author": note.get("author", {}).get("username"),
                    "created_at": note.get("created_at"),
                    "updated_at": note.get("updated_at"),
                    "system": note.get("system", False),
                }
            )

        return {
            "success": True,
            "comments": comments,
            "count": len(comments),
        }

    except Exception as e:
        logger.error(f"Failed to list MR comments: {e}")
        return {"success": False, "error": str(e)}


async def internal_gitlab_list_issue_comments(
    project_id: str,
    issue_iid: int,
    per_page: int = 20,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    List comments (notes) on a GitLab issue.

    Args:
        project_id: Project ID or URL-encoded path
        issue_iid: Issue internal ID (IID)
        per_page: Number of comments per page (max 100)

    Returns:
        List of comments
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    if not project_id or not issue_iid:
        return {"success": False, "error": "project_id and issue_iid are required"}

    try:
        config = config or {}
        tool_name = config.get("_tool_name", "internal_gitlab_list_issue_comments")
        credentials = await _get_gitlab_credentials(runtime_context, tool_name)

        encoded_id = quote(str(project_id), safe="")

        params = {"per_page": min(per_page, 100), "sort": "asc"}

        result = await _make_gitlab_request(
            f"/projects/{encoded_id}/issues/{issue_iid}/notes",
            credentials=credentials,
            params=params,
        )

        comments = []
        for note in result if isinstance(result, list) else []:
            comments.append(
                {
                    "id": note.get("id"),
                    "body": note.get("body"),
                    "author": note.get("author", {}).get("username"),
                    "created_at": note.get("created_at"),
                    "updated_at": note.get("updated_at"),
                    "system": note.get("system", False),
                }
            )

        return {
            "success": True,
            "comments": comments,
            "count": len(comments),
        }

    except Exception as e:
        logger.error(f"Failed to list issue comments: {e}")
        return {"success": False, "error": str(e)}


# =============================================================================
# Merge Request Management Tools
# =============================================================================


async def internal_gitlab_merge_mr(
    project_id: str,
    merge_request_iid: int,
    squash: bool = False,
    should_remove_source_branch: bool = False,
    merge_commit_message: str | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Merge a merge request.

    Args:
        project_id: Project ID or URL-encoded path
        merge_request_iid: Merge request internal ID (IID)
        squash: Squash commits into single commit
        should_remove_source_branch: Remove source branch after merge
        merge_commit_message: Custom merge commit message

    Returns:
        Merged MR details
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    if not project_id or not merge_request_iid:
        return {"success": False, "error": "project_id and merge_request_iid are required"}

    try:
        config = config or {}
        tool_name = config.get("_tool_name", "internal_gitlab_merge_mr")
        credentials = await _get_gitlab_credentials(runtime_context, tool_name)

        encoded_id = quote(str(project_id), safe="")

        json_data = {
            "squash": squash,
            "should_remove_source_branch": should_remove_source_branch,
        }

        if merge_commit_message:
            json_data["merge_commit_message"] = merge_commit_message

        result = await _make_gitlab_request(
            f"/projects/{encoded_id}/merge_requests/{merge_request_iid}/merge",
            method="PUT",
            credentials=credentials,
            json_data=json_data,
        )

        return {
            "success": True,
            "merge_request": {
                "id": result.get("id"),
                "iid": result.get("iid"),
                "title": result.get("title"),
                "state": result.get("state"),
                "merged_at": result.get("merged_at"),
                "merged_by": result.get("merged_by", {}).get("username") if result.get("merged_by") else None,
                "web_url": result.get("web_url"),
            },
            "message": f"MR !{merge_request_iid} merged successfully",
        }

    except Exception as e:
        logger.error(f"Failed to merge MR: {e}")
        return {"success": False, "error": str(e)}


async def internal_gitlab_close_mr(
    project_id: str,
    merge_request_iid: int,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Close a merge request without merging.

    Args:
        project_id: Project ID or URL-encoded path
        merge_request_iid: Merge request internal ID (IID)

    Returns:
        Closed MR details
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    if not project_id or not merge_request_iid:
        return {"success": False, "error": "project_id and merge_request_iid are required"}

    try:
        config = config or {}
        tool_name = config.get("_tool_name", "internal_gitlab_close_mr")
        credentials = await _get_gitlab_credentials(runtime_context, tool_name)

        encoded_id = quote(str(project_id), safe="")

        json_data = {"state_event": "close"}

        result = await _make_gitlab_request(
            f"/projects/{encoded_id}/merge_requests/{merge_request_iid}",
            method="PUT",
            credentials=credentials,
            json_data=json_data,
        )

        return {
            "success": True,
            "merge_request": {
                "id": result.get("id"),
                "iid": result.get("iid"),
                "title": result.get("title"),
                "state": result.get("state"),
                "web_url": result.get("web_url"),
            },
            "message": f"MR !{merge_request_iid} closed",
        }

    except Exception as e:
        logger.error(f"Failed to close MR: {e}")
        return {"success": False, "error": str(e)}


async def internal_gitlab_reopen_mr(
    project_id: str,
    merge_request_iid: int,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Reopen a closed merge request.

    Args:
        project_id: Project ID or URL-encoded path
        merge_request_iid: Merge request internal ID (IID)

    Returns:
        Reopened MR details
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    if not project_id or not merge_request_iid:
        return {"success": False, "error": "project_id and merge_request_iid are required"}

    try:
        config = config or {}
        tool_name = config.get("_tool_name", "internal_gitlab_reopen_mr")
        credentials = await _get_gitlab_credentials(runtime_context, tool_name)

        encoded_id = quote(str(project_id), safe="")

        json_data = {"state_event": "reopen"}

        result = await _make_gitlab_request(
            f"/projects/{encoded_id}/merge_requests/{merge_request_iid}",
            method="PUT",
            credentials=credentials,
            json_data=json_data,
        )

        return {
            "success": True,
            "merge_request": {
                "id": result.get("id"),
                "iid": result.get("iid"),
                "title": result.get("title"),
                "state": result.get("state"),
                "web_url": result.get("web_url"),
            },
            "message": f"MR !{merge_request_iid} reopened",
        }

    except Exception as e:
        logger.error(f"Failed to reopen MR: {e}")
        return {"success": False, "error": str(e)}


async def internal_gitlab_approve_mr(
    project_id: str,
    merge_request_iid: int,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Approve a merge request.

    Args:
        project_id: Project ID or URL-encoded path
        merge_request_iid: Merge request internal ID (IID)

    Returns:
        Approval result
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    if not project_id or not merge_request_iid:
        return {"success": False, "error": "project_id and merge_request_iid are required"}

    try:
        config = config or {}
        tool_name = config.get("_tool_name", "internal_gitlab_approve_mr")
        credentials = await _get_gitlab_credentials(runtime_context, tool_name)

        encoded_id = quote(str(project_id), safe="")

        await _make_gitlab_request(
            f"/projects/{encoded_id}/merge_requests/{merge_request_iid}/approve",
            method="POST",
            credentials=credentials,
        )

        return {
            "success": True,
            "message": f"MR !{merge_request_iid} approved",
        }

    except Exception as e:
        logger.error(f"Failed to approve MR: {e}")
        return {"success": False, "error": str(e)}


async def internal_gitlab_unapprove_mr(
    project_id: str,
    merge_request_iid: int,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Unapprove (revoke approval) of a merge request.

    Args:
        project_id: Project ID or URL-encoded path
        merge_request_iid: Merge request internal ID (IID)

    Returns:
        Unapproval result
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    if not project_id or not merge_request_iid:
        return {"success": False, "error": "project_id and merge_request_iid are required"}

    try:
        config = config or {}
        tool_name = config.get("_tool_name", "internal_gitlab_unapprove_mr")
        credentials = await _get_gitlab_credentials(runtime_context, tool_name)

        encoded_id = quote(str(project_id), safe="")

        await _make_gitlab_request(
            f"/projects/{encoded_id}/merge_requests/{merge_request_iid}/unapprove",
            method="POST",
            credentials=credentials,
        )

        return {
            "success": True,
            "message": f"Approval removed from MR !{merge_request_iid}",
        }

    except Exception as e:
        logger.error(f"Failed to unapprove MR: {e}")
        return {"success": False, "error": str(e)}


async def internal_gitlab_update_mr(
    project_id: str,
    merge_request_iid: int,
    title: str | None = None,
    description: str | None = None,
    target_branch: str | None = None,
    labels: str | None = None,
    assignee_ids: list[int] | None = None,
    reviewer_ids: list[int] | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Update a merge request.

    Args:
        project_id: Project ID or URL-encoded path
        merge_request_iid: Merge request internal ID (IID)
        title: New title
        description: New description
        target_branch: New target branch
        labels: Comma-separated list of labels
        assignee_ids: List of user IDs to assign
        reviewer_ids: List of user IDs to request review

    Returns:
        Updated MR details
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    if not project_id or not merge_request_iid:
        return {"success": False, "error": "project_id and merge_request_iid are required"}

    try:
        config = config or {}
        tool_name = config.get("_tool_name", "internal_gitlab_update_mr")
        credentials = await _get_gitlab_credentials(runtime_context, tool_name)

        encoded_id = quote(str(project_id), safe="")

        json_data = {}
        if title is not None:
            json_data["title"] = title
        if description is not None:
            json_data["description"] = description
        if target_branch is not None:
            json_data["target_branch"] = target_branch
        if labels is not None:
            json_data["labels"] = labels
        if assignee_ids is not None:
            json_data["assignee_ids"] = assignee_ids
        if reviewer_ids is not None:
            json_data["reviewer_ids"] = reviewer_ids

        if not json_data:
            return {"success": False, "error": "No fields to update"}

        result = await _make_gitlab_request(
            f"/projects/{encoded_id}/merge_requests/{merge_request_iid}",
            method="PUT",
            credentials=credentials,
            json_data=json_data,
        )

        return {
            "success": True,
            "merge_request": {
                "id": result.get("id"),
                "iid": result.get("iid"),
                "title": result.get("title"),
                "description": result.get("description"),
                "state": result.get("state"),
                "labels": result.get("labels", []),
                "web_url": result.get("web_url"),
            },
            "message": f"MR !{merge_request_iid} updated",
        }

    except Exception as e:
        logger.error(f"Failed to update MR: {e}")
        return {"success": False, "error": str(e)}


# =============================================================================
# Issue Management Tools
# =============================================================================


async def internal_gitlab_get_issue(
    project_id: str,
    issue_iid: int,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Get details of a specific issue.

    Args:
        project_id: Project ID or URL-encoded path
        issue_iid: Issue internal ID (IID)

    Returns:
        Issue details
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    if not project_id or not issue_iid:
        return {"success": False, "error": "project_id and issue_iid are required"}

    try:
        config = config or {}
        tool_name = config.get("_tool_name", "internal_gitlab_get_issue")
        credentials = await _get_gitlab_credentials(runtime_context, tool_name)

        encoded_id = quote(str(project_id), safe="")

        result = await _make_gitlab_request(
            f"/projects/{encoded_id}/issues/{issue_iid}",
            credentials=credentials,
        )

        return {
            "success": True,
            "issue": {
                "id": result.get("id"),
                "iid": result.get("iid"),
                "title": result.get("title"),
                "description": result.get("description"),
                "state": result.get("state"),
                "labels": result.get("labels", []),
                "assignees": [a.get("username") for a in result.get("assignees", [])],
                "author": result.get("author", {}).get("username"),
                "milestone": result.get("milestone", {}).get("title") if result.get("milestone") else None,
                "web_url": result.get("web_url"),
                "created_at": result.get("created_at"),
                "updated_at": result.get("updated_at"),
                "closed_at": result.get("closed_at"),
            },
        }

    except Exception as e:
        logger.error(f"Failed to get issue: {e}")
        return {"success": False, "error": str(e)}


async def internal_gitlab_update_issue(
    project_id: str,
    issue_iid: int,
    title: str | None = None,
    description: str | None = None,
    labels: str | None = None,
    assignee_ids: list[int] | None = None,
    milestone_id: int | None = None,
    state_event: str | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Update an issue.

    Args:
        project_id: Project ID or URL-encoded path
        issue_iid: Issue internal ID (IID)
        title: New title
        description: New description
        labels: Comma-separated list of labels
        assignee_ids: List of user IDs to assign
        milestone_id: Milestone ID (0 to remove)
        state_event: 'close' or 'reopen'

    Returns:
        Updated issue details
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    if not project_id or not issue_iid:
        return {"success": False, "error": "project_id and issue_iid are required"}

    try:
        config = config or {}
        tool_name = config.get("_tool_name", "internal_gitlab_update_issue")
        credentials = await _get_gitlab_credentials(runtime_context, tool_name)

        encoded_id = quote(str(project_id), safe="")

        json_data = {}
        if title is not None:
            json_data["title"] = title
        if description is not None:
            json_data["description"] = description
        if labels is not None:
            json_data["labels"] = labels
        if assignee_ids is not None:
            json_data["assignee_ids"] = assignee_ids
        if milestone_id is not None:
            json_data["milestone_id"] = milestone_id if milestone_id != 0 else None
        if state_event is not None:
            json_data["state_event"] = state_event

        if not json_data:
            return {"success": False, "error": "No fields to update"}

        result = await _make_gitlab_request(
            f"/projects/{encoded_id}/issues/{issue_iid}",
            method="PUT",
            credentials=credentials,
            json_data=json_data,
        )

        return {
            "success": True,
            "issue": {
                "id": result.get("id"),
                "iid": result.get("iid"),
                "title": result.get("title"),
                "state": result.get("state"),
                "labels": result.get("labels", []),
                "assignees": [a.get("username") for a in result.get("assignees", [])],
                "web_url": result.get("web_url"),
            },
            "message": f"Issue #{issue_iid} updated",
        }

    except Exception as e:
        logger.error(f"Failed to update issue: {e}")
        return {"success": False, "error": str(e)}


async def internal_gitlab_close_issue(
    project_id: str,
    issue_iid: int,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Close an issue.

    Args:
        project_id: Project ID or URL-encoded path
        issue_iid: Issue internal ID (IID)

    Returns:
        Closed issue details
    """
    return await internal_gitlab_update_issue(
        project_id=project_id,
        issue_iid=issue_iid,
        state_event="close",
        config=config,
        runtime_context=runtime_context,
    )


async def internal_gitlab_reopen_issue(
    project_id: str,
    issue_iid: int,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Reopen a closed issue.

    Args:
        project_id: Project ID or URL-encoded path
        issue_iid: Issue internal ID (IID)

    Returns:
        Reopened issue details
    """
    return await internal_gitlab_update_issue(
        project_id=project_id,
        issue_iid=issue_iid,
        state_event="reopen",
        config=config,
        runtime_context=runtime_context,
    )


async def internal_gitlab_search_users(
    project_id: str,
    search: str,
    per_page: int = 20,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Search for users in a project (members).

    Args:
        project_id: Project ID or URL-encoded path
        search: Search term (username or name)
        per_page: Number of users per page (max 100)

    Returns:
        List of matching users
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    if not project_id or not search:
        return {"success": False, "error": "project_id and search are required"}

    try:
        config = config or {}
        tool_name = config.get("_tool_name", "internal_gitlab_search_users")
        credentials = await _get_gitlab_credentials(runtime_context, tool_name)

        encoded_id = quote(str(project_id), safe="")

        params = {
            "search": search,
            "per_page": min(per_page, 100),
        }

        result = await _make_gitlab_request(
            f"/projects/{encoded_id}/members/all",
            credentials=credentials,
            params=params,
        )

        users = []
        for user in result if isinstance(result, list) else []:
            users.append(
                {
                    "id": user.get("id"),
                    "username": user.get("username"),
                    "name": user.get("name"),
                    "avatar_url": user.get("avatar_url"),
                    "access_level": user.get("access_level"),
                }
            )

        return {
            "success": True,
            "users": users,
            "count": len(users),
        }

    except Exception as e:
        logger.error(f"Failed to search users: {e}")
        return {"success": False, "error": str(e)}


async def internal_gitlab_get_mr_diff(
    project_id: str,
    merge_request_iid: int,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Get the diff of a merge request.

    Args:
        project_id: Project ID or URL-encoded path
        merge_request_iid: Merge request internal ID (IID)

    Returns:
        MR diff information
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    if not project_id or not merge_request_iid:
        return {"success": False, "error": "project_id and merge_request_iid are required"}

    try:
        config = config or {}
        tool_name = config.get("_tool_name", "internal_gitlab_get_mr_diff")
        credentials = await _get_gitlab_credentials(runtime_context, tool_name)

        encoded_id = quote(str(project_id), safe="")

        result = await _make_gitlab_request(
            f"/projects/{encoded_id}/merge_requests/{merge_request_iid}/changes",
            credentials=credentials,
        )

        changes = []
        for change in result.get("changes", []):
            changes.append(
                {
                    "old_path": change.get("old_path"),
                    "new_path": change.get("new_path"),
                    "new_file": change.get("new_file", False),
                    "renamed_file": change.get("renamed_file", False),
                    "deleted_file": change.get("deleted_file", False),
                    "diff": change.get("diff", ""),
                }
            )

        return {
            "success": True,
            "merge_request": {
                "id": result.get("id"),
                "iid": result.get("iid"),
                "title": result.get("title"),
            },
            "changes": changes,
            "changes_count": len(changes),
        }

    except Exception as e:
        logger.error(f"Failed to get MR diff: {e}")
        return {"success": False, "error": str(e)}
