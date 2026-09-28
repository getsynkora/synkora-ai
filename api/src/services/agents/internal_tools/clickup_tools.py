"""
ClickUp Integration Tools for Issue Debugging and Task Management.

Provides tools for fetching and analyzing ClickUp tasks/issues.
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


async def _get_typesafe_client(runtime_context: Any | None) -> Any | None:
    """Return a TypeSafeClient for triage, or None if not configured."""
    if not runtime_context:
        return None
    try:
        from src.core.typesafe_client import make_typesafe_client
        from src.services.agents.credential_resolver import CredentialResolver

        credentials = await CredentialResolver(runtime_context).get_typesafe_credentials()
        if not credentials:
            return None
        return make_typesafe_client(credentials)
    except Exception as exc:
        logger.warning("Could not build TypeSafe client for triage: %s", exc)
        return None


async def _get_clickup_token(runtime_context: Any, tool_name: str) -> str:
    """Get ClickUp API token from runtime context using CredentialResolver."""
    if not runtime_context:
        raise ValueError("No runtime context available. Please configure ClickUp integration in OAuth Apps.")

    from src.services.agents.credential_resolver import CredentialResolver

    resolver = CredentialResolver(runtime_context)
    token = await resolver.get_clickup_token(tool_name)

    if not token:
        raise ValueError(
            "ClickUp authentication not configured. Please connect your ClickUp account in OAuth Apps settings."
        )

    return token


async def _make_clickup_request(
    method: str,
    endpoint: str,
    token: str,
    params: dict[str, Any] | None = None,
    json_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Make authenticated request to ClickUp API."""
    headers = {"Authorization": token, "Content-Type": "application/json"}

    url = f"https://api.clickup.com/api/v2{endpoint}"

    async with httpx.AsyncClient() as client:
        response = await client.request(
            method=method, url=url, headers=headers, params=params, json=json_data, timeout=30.0
        )
        response.raise_for_status()
        return response.json()


async def internal_get_clickup_task(
    task_id: str, config: dict[str, Any] | None = None, runtime_context: Any | None = None
) -> dict[str, Any]:
    """
    Get detailed information about a ClickUp task.

    Args:
        task_id: ClickUp task ID
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with task details
    """
    try:
        token = await _get_clickup_token(runtime_context, tool_name="internal_get_clickup_task")

        # Get task details
        task_data = await _make_clickup_request("GET", f"/task/{task_id}", token)

        # Get task comments
        comments_data = await _make_clickup_request("GET", f"/task/{task_id}/comment", token)

        return {
            "success": True,
            "task": {
                "id": task_data["id"],
                "name": task_data["name"],
                "description": task_data.get("description", ""),
                "status": task_data["status"]["status"],
                "priority": task_data.get("priority"),
                "due_date": task_data.get("due_date"),
                "creator": task_data["creator"]["username"],
                "assignees": [a["username"] for a in task_data.get("assignees", [])],
                "tags": [tag["name"] for tag in task_data.get("tags", [])],
                "custom_fields": task_data.get("custom_fields", []),
                "url": task_data["url"],
                "created_at": task_data["date_created"],
                "updated_at": task_data["date_updated"],
            },
            "comments": [
                {
                    "id": comment["id"],
                    "text": comment["comment_text"],
                    "user": comment["user"]["username"],
                    "date": comment["date"],
                }
                for comment in comments_data.get("comments", [])
            ],
            "attachments": task_data.get("attachments", []),
        }

    except Exception as e:
        logger.error(f"Failed to get ClickUp task: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_search_clickup_tasks(
    list_id: str,
    query: str | None = None,
    status: list[str] | None = None,
    assignees: list[str] | None = None,
    tags: list[str] | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """
    Search for ClickUp tasks in a list.

    Args:
        list_id: ClickUp list ID
        query: Search query
        status: Filter by status
        assignees: Filter by assignees
        tags: Filter by tags
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with search results
    """
    try:
        token = await _get_clickup_token(runtime_context, tool_name="internal_search_clickup_tasks")

        # Build query parameters
        params = {}
        if query:
            params["search"] = query
        if status:
            params["statuses"] = status
        if assignees:
            params["assignees"] = assignees
        if tags:
            params["tags"] = tags

        # Get tasks
        result = await _make_clickup_request("GET", f"/list/{list_id}/task", token, params=params)

        tasks = [
            {
                "id": task["id"],
                "name": task["name"],
                "description": task.get("description", ""),
                "status": task["status"]["status"],
                "priority": task.get("priority"),
                "url": task["url"],
                "assignees": [a["username"] for a in task.get("assignees", [])],
                "tags": [tag["name"] for tag in task.get("tags", [])],
            }
            for task in result.get("tasks", [])
        ]

        # TypeSafe triage: filter tasks by query relevance before returning
        from src.services.agents.internal_tools.issue_triage import triage_issues

        _typesafe_client = await _get_typesafe_client(runtime_context)
        _triage_items = [{"title": t["name"], "summary": t.get("description", ""), "_id": t["id"]} for t in tasks]
        _kept_items, _triage_note = await triage_issues(_typesafe_client, _triage_items, query_context=query or "")
        _kept_ids = {item["_id"] for item in _kept_items}
        tasks = [t for t in tasks if t["id"] in _kept_ids]
        return {"success": True, "tasks": tasks, "total": len(tasks), "triage": _triage_note.to_dict()}

    except Exception as e:
        logger.error(f"Failed to search ClickUp tasks: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_add_clickup_comment(
    task_id: str,
    comment_text: str,
    notify_all: bool = False,
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """
    Add a comment to a ClickUp task.

    Args:
        task_id: ClickUp task ID
        comment_text: Comment text
        notify_all: Notify all task watchers
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with comment result
    """
    try:
        token = await _get_clickup_token(runtime_context, tool_name="internal_add_clickup_comment")

        result = await _make_clickup_request(
            "POST",
            f"/task/{task_id}/comment",
            token,
            json_data={"comment_text": comment_text, "notify_all": notify_all},
        )

        return {
            "success": True,
            "comment_id": result["id"],
            "comment_text": result["comment_text"],
            "date": result["date"],
        }

    except Exception as e:
        logger.error(f"Failed to add ClickUp comment: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_update_clickup_task(
    task_id: str,
    updates: dict[str, Any],
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """
    Update a ClickUp task.

    Args:
        task_id: ClickUp task ID
        updates: Dictionary of fields to update (name, description, status, priority, etc.)
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with update result
    """
    try:
        token = await _get_clickup_token(runtime_context, tool_name="internal_update_clickup_task")

        result = await _make_clickup_request("PUT", f"/task/{task_id}", token, json_data=updates)

        return {"success": True, "task_id": result["id"], "updated_fields": list(updates.keys())}

    except Exception as e:
        logger.error(f"Failed to update ClickUp task: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_get_clickup_workspace(
    config: dict[str, Any] | None = None, runtime_context: Any | None = None
) -> dict[str, Any]:
    """
    Get ClickUp workspace (team) information.

    Args:
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with workspace details
    """
    try:
        token = await _get_clickup_token(runtime_context, tool_name="internal_get_clickup_workspace")

        result = await _make_clickup_request("GET", "/team", token)

        teams = [
            {
                "id": team["id"],
                "name": team["name"],
                "avatar": team.get("avatar"),
                "members": len(team.get("members", [])),
            }
            for team in result.get("teams", [])
        ]

        return {"success": True, "teams": teams}

    except Exception as e:
        logger.error(f"Failed to get ClickUp workspace: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_get_clickup_spaces(
    team_id: str,
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """
    Get all spaces in a ClickUp workspace/team.

    Args:
        team_id: ClickUp team/workspace ID
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with spaces list
    """
    try:
        token = await _get_clickup_token(runtime_context, tool_name="internal_get_clickup_spaces")

        result = await _make_clickup_request("GET", f"/team/{team_id}/space", token)

        spaces = [
            {
                "id": space["id"],
                "name": space["name"],
                "private": space.get("private", False),
                "statuses": [s["status"] for s in space.get("statuses", [])],
            }
            for space in result.get("spaces", [])
        ]

        return {"success": True, "spaces": spaces, "total": len(spaces)}

    except Exception as e:
        logger.error(f"Failed to get ClickUp spaces: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_get_clickup_folders(
    space_id: str,
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """
    Get all folders in a ClickUp space.

    Args:
        space_id: ClickUp space ID
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with folders list
    """
    try:
        token = await _get_clickup_token(runtime_context, tool_name="internal_get_clickup_folders")

        result = await _make_clickup_request("GET", f"/space/{space_id}/folder", token)

        folders = [
            {
                "id": folder["id"],
                "name": folder["name"],
                "hidden": folder.get("hidden", False),
                "list_count": len(folder.get("lists", [])),
            }
            for folder in result.get("folders", [])
        ]

        return {"success": True, "folders": folders, "total": len(folders)}

    except Exception as e:
        logger.error(f"Failed to get ClickUp folders: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_get_clickup_lists(
    folder_id: str | None = None,
    space_id: str | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """
    Get lists from a ClickUp folder or space (folderless lists).

    Args:
        folder_id: ClickUp folder ID (for lists in a folder)
        space_id: ClickUp space ID (for folderless lists)
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with lists
    """
    try:
        if not folder_id and not space_id:
            return {"success": False, "error": "Either folder_id or space_id must be provided"}

        token = await _get_clickup_token(runtime_context, tool_name="internal_get_clickup_lists")

        if folder_id:
            endpoint = f"/folder/{folder_id}/list"
        else:
            endpoint = f"/space/{space_id}/list"

        result = await _make_clickup_request("GET", endpoint, token)

        lists = [
            {
                "id": lst["id"],
                "name": lst["name"],
                "task_count": lst.get("task_count", 0),
                "status": lst.get("status", {}).get("status") if lst.get("status") else None,
            }
            for lst in result.get("lists", [])
        ]

        return {"success": True, "lists": lists, "total": len(lists)}

    except Exception as e:
        logger.error(f"Failed to get ClickUp lists: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_create_clickup_task(
    list_id: str,
    name: str,
    description: str | None = None,
    status: str | None = None,
    priority: int | None = None,
    assignees: list[int] | None = None,
    tags: list[str] | None = None,
    due_date: int | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """
    Create a new task in a ClickUp list.

    Args:
        list_id: ClickUp list ID
        name: Task name/title
        description: Task description (optional)
        status: Task status (optional, uses list's default if not specified)
        priority: Priority level 1-4 (1=Urgent, 2=High, 3=Normal, 4=Low) (optional)
        assignees: List of user IDs to assign (optional)
        tags: List of tag names (optional)
        due_date: Due date as Unix timestamp in milliseconds (optional)
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with created task details
    """
    try:
        token = await _get_clickup_token(runtime_context, tool_name="internal_create_clickup_task")

        task_data: dict[str, Any] = {"name": name}

        if description:
            task_data["description"] = description
        if status:
            task_data["status"] = status
        if priority is not None:
            task_data["priority"] = priority
        if assignees:
            task_data["assignees"] = assignees
        if tags:
            task_data["tags"] = tags
        if due_date:
            task_data["due_date"] = due_date

        result = await _make_clickup_request("POST", f"/list/{list_id}/task", token, json_data=task_data)

        return {
            "success": True,
            "task": {
                "id": result["id"],
                "name": result["name"],
                "description": result.get("description", ""),
                "status": result["status"]["status"],
                "url": result["url"],
                "creator": result["creator"]["username"],
            },
        }

    except Exception as e:
        logger.error(f"Failed to create ClickUp task: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_get_clickup_members(
    team_id: str,
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """
    Get all members in a ClickUp workspace/team.

    Args:
        team_id: ClickUp team/workspace ID
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with members list
    """
    try:
        token = await _get_clickup_token(runtime_context, tool_name="internal_get_clickup_members")

        # Get team details which includes members
        result = await _make_clickup_request("GET", "/team", token)

        members = []
        for team in result.get("teams", []):
            if str(team["id"]) == str(team_id):
                for member in team.get("members", []):
                    user = member.get("user", {})
                    members.append(
                        {
                            "id": user.get("id"),
                            "username": user.get("username"),
                            "email": user.get("email"),
                            "color": user.get("color"),
                            "profilePicture": user.get("profilePicture"),
                            "role": member.get("role"),
                        }
                    )
                break

        return {"success": True, "members": members, "total": len(members)}

    except Exception as e:
        logger.error(f"Failed to get ClickUp members: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_get_clickup_list_summary(
    list_id: str,
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """
    Get a summary of a ClickUp list with task counts by status and assignee.

    Args:
        list_id: ClickUp list ID
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with list summary including task statistics
    """
    try:
        token = await _get_clickup_token(runtime_context, tool_name="internal_get_clickup_list_summary")

        # Get list details
        list_result = await _make_clickup_request("GET", f"/list/{list_id}", token)

        # Get all tasks in the list
        tasks_result = await _make_clickup_request("GET", f"/list/{list_id}/task", token)

        tasks = tasks_result.get("tasks", [])

        # Count by status
        status_counts: dict[str, int] = {}
        for task in tasks:
            status = task.get("status", {}).get("status", "Unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

        # Count by assignee
        assignee_counts: dict[str, dict[str, Any]] = {}
        unassigned_count = 0
        for task in tasks:
            assignees = task.get("assignees", [])
            if not assignees:
                unassigned_count += 1
            else:
                for assignee in assignees:
                    username = assignee.get("username", "Unknown")
                    if username not in assignee_counts:
                        assignee_counts[username] = {"count": 0, "id": assignee.get("id")}
                    assignee_counts[username]["count"] += 1

        return {
            "success": True,
            "list": {
                "id": list_result["id"],
                "name": list_result["name"],
                "task_count": list_result.get("task_count", len(tasks)),
            },
            "summary": {
                "total_tasks": len(tasks),
                "by_status": status_counts,
                "by_assignee": {k: v["count"] for k, v in assignee_counts.items()},
                "unassigned": unassigned_count,
            },
            "assignee_details": assignee_counts,
        }

    except Exception as e:
        logger.error(f"Failed to get ClickUp list summary: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
