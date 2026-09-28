"""
Jira Integration Tools for Issue Debugging and Project Management.

Provides tools for fetching and analyzing Jira issues and projects.
Supports both API token (Basic Auth) and OAuth 2.0 (Bearer token) authentication.
"""

import base64
import logging
from datetime import UTC
from typing import Any

import httpx

logger = logging.getLogger(__name__)


async def _get_jira_credentials(runtime_context: Any, tool_name: str) -> dict[str, Any]:
    """
    Get Jira credentials from runtime context using CredentialResolver.

    Returns a config dict:
    - For API token auth: {auth_type: 'basic', domain, email, api_token}
    - For OAuth auth: {auth_type: 'oauth', cloud_id, access_token, domain}
    """
    if not runtime_context:
        raise ValueError("No runtime context available. Please configure Jira integration in OAuth Apps.")

    from src.services.agents.credential_resolver import CredentialResolver

    resolver = CredentialResolver(runtime_context)
    credentials = await resolver.get_jira_credentials(tool_name)

    if not credentials:
        raise ValueError("Jira authentication not configured. Please connect your Jira account in OAuth Apps settings.")

    return credentials


def _get_jira_browse_url(jira_config: dict[str, Any], issue_key: str) -> str:
    """Get the browse URL for a Jira issue."""
    domain = jira_config.get("domain", "")
    if domain:
        # Clean up domain if it's a full URL
        domain = domain.replace("https://", "").replace("http://", "").rstrip("/")
        if ".atlassian.net" in domain:
            return f"https://{domain}/browse/{issue_key}"
        else:
            return f"https://{domain}.atlassian.net/browse/{issue_key}"
    return f"https://jira.atlassian.com/browse/{issue_key}"


async def _make_jira_request(
    method: str,
    endpoint: str,
    jira_config: dict[str, Any],
    params: dict[str, Any] | None = None,
    json_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Make authenticated request to Jira API.

    Supports both Basic Auth (API token) and OAuth 2.0 (Bearer token).
    """
    auth_type = jira_config.get("auth_type", "basic")

    if auth_type == "oauth":
        # OAuth 2.0 Bearer token authentication
        cloud_id = jira_config.get("cloud_id")
        access_token = jira_config.get("access_token")

        if not cloud_id or not access_token:
            raise ValueError("OAuth requires cloud_id and access_token")

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        # OAuth uses the Atlassian API gateway
        url = f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3{endpoint}"
    else:
        # Basic Auth with API token
        domain = jira_config.get("domain")
        email = jira_config.get("email")
        api_token = jira_config.get("api_token")

        if not domain or not email or not api_token:
            raise ValueError("Basic auth requires domain, email, and api_token")

        auth_string = f"{email}:{api_token}"
        auth_bytes = auth_string.encode("ascii")
        auth_base64 = base64.b64encode(auth_bytes).decode("ascii")

        headers = {
            "Authorization": f"Basic {auth_base64}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        url = f"https://{domain}.atlassian.net/rest/api/3{endpoint}"

    async with httpx.AsyncClient() as client:
        response = await client.request(
            method=method, url=url, headers=headers, params=params, json=json_data, timeout=30.0
        )
        response.raise_for_status()
        return response.json()


async def _get_typesafe_client(runtime_context: Any | None) -> Any | None:
    """Return a TypeSafeClient for issue triage, or None if not configured."""
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
        logger.warning("Could not build TypeSafe client for issue triage: %s", exc)
        return None


async def internal_get_jira_issue(
    issue_key: str, config: dict[str, Any] | None = None, runtime_context: Any | None = None
) -> dict[str, Any]:
    """
    Get detailed information about a Jira issue.

    Args:
        issue_key: Jira issue key (e.g., PROJ-123)
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with issue details
    """
    try:
        jira_config = await _get_jira_credentials(runtime_context, tool_name="internal_get_jira_issue")

        # Get issue details
        issue_data = await _make_jira_request("GET", f"/issue/{issue_key}", jira_config)

        # Get issue comments
        comments_data = await _make_jira_request("GET", f"/issue/{issue_key}/comment", jira_config)

        fields = issue_data["fields"]

        return {
            "success": True,
            "issue": {
                "key": issue_data["key"],
                "id": issue_data["id"],
                "summary": fields.get("summary", ""),
                "description": fields.get("description", ""),
                "status": fields["status"]["name"],
                "priority": fields.get("priority", {}).get("name"),
                "issue_type": fields["issuetype"]["name"],
                "reporter": fields.get("reporter", {}).get("displayName"),
                "assignee": fields.get("assignee", {}).get("displayName"),
                "created": fields.get("created"),
                "updated": fields.get("updated"),
                "labels": fields.get("labels", []),
                "components": [c["name"] for c in fields.get("components", [])],
                "fix_versions": [v["name"] for v in fields.get("fixVersions", [])],
                "url": _get_jira_browse_url(jira_config, issue_data["key"]),
            },
            "comments": [
                {
                    "id": comment["id"],
                    "body": comment["body"],
                    "author": comment["author"]["displayName"],
                    "created": comment["created"],
                    "updated": comment["updated"],
                }
                for comment in comments_data.get("comments", [])
            ],
            "attachments": [
                {
                    "id": attachment["id"],
                    "filename": attachment["filename"],
                    "size": attachment["size"],
                    "mimeType": attachment["mimeType"],
                    "content": attachment["content"],
                }
                for attachment in fields.get("attachment", [])
            ],
        }

    except Exception as e:
        logger.error(f"Failed to get Jira issue: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_search_jira_issues(
    jql: str, max_results: int = 50, config: dict[str, Any] | None = None, runtime_context: Any | None = None
) -> dict[str, Any]:
    """
    Search for Jira issues using JQL (Jira Query Language).

    Args:
        jql: JQL query string (e.g., "project = PROJ AND status = Open")
        max_results: Maximum number of results to return
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with search results
    """
    try:
        jira_config = await _get_jira_credentials(runtime_context, tool_name="internal_search_jira_issues")

        # Handle empty JQL or JQL that's just an ORDER BY clause
        # The new /search/jql endpoint requires a valid JQL query
        jql_normalized = jql.strip() if jql else ""
        if not jql_normalized or jql_normalized.lower().startswith("order by"):
            # Default to all issues if no query provided
            jql_normalized = f"project is not EMPTY {jql_normalized}"

        # Search issues using the new /search/jql endpoint (old /search was deprecated Oct 2025)
        result = await _make_jira_request(
            "POST",
            "/search/jql",
            jira_config,
            json_data={
                "jql": jql_normalized,
                "maxResults": max_results,
                "fields": ["summary", "status", "priority", "assignee", "created", "updated"],
            },
        )

        issues = []
        for issue in result.get("issues", []):
            fields = issue.get("fields", {})
            priority = fields.get("priority")
            assignee = fields.get("assignee")
            status = fields.get("status", {})

            issues.append(
                {
                    "key": issue["key"],
                    "summary": fields.get("summary", ""),
                    "status": status.get("name") if status else None,
                    "priority": priority.get("name") if priority else None,
                    "assignee": assignee.get("displayName") if assignee else None,
                    "created": fields.get("created"),
                    "updated": fields.get("updated"),
                    "url": _get_jira_browse_url(jira_config, issue["key"]),
                }
            )

        # TypeSafe triage: score issues for query relevance before returning
        from src.services.agents.internal_tools.issue_triage import triage_issues

        _typesafe_client = await _get_typesafe_client(runtime_context)
        _triage_items = [{"title": f"{iss['key']}: {iss['summary']}", "summary": iss["summary"]} for iss in issues]
        _kept_items, _triage_note = await triage_issues(_typesafe_client, _triage_items, query_context=jql)
        _kept_titles = {item["title"] for item in _kept_items}
        issues = [iss for iss in issues if f"{iss['key']}: {iss['summary']}" in _kept_titles]

        return {
            "success": True,
            "issues": issues,
            "total": result.get("total", 0),
            "max_results": result.get("maxResults", 0),
            "triage": _triage_note.to_dict(),
        }

    except Exception as e:
        logger.error(f"Failed to search Jira issues: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_add_jira_comment(
    issue_key: str,
    comment_text: str,
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """
    Add a comment to a Jira issue.

    Args:
        issue_key: Jira issue key
        comment_text: Comment text
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with comment result
    """
    try:
        jira_config = await _get_jira_credentials(runtime_context, tool_name="internal_add_jira_comment")

        result = await _make_jira_request(
            "POST",
            f"/issue/{issue_key}/comment",
            jira_config,
            json_data={"body": comment_text},
        )

        return {"success": True, "comment_id": result["id"], "body": result["body"], "created": result["created"]}

    except Exception as e:
        logger.error(f"Failed to add Jira comment: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_update_jira_issue(
    issue_key: str,
    updates: dict[str, Any],
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """
    Update a Jira issue.

    Args:
        issue_key: Jira issue key
        updates: Dictionary of fields to update
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with update result
    """
    try:
        jira_config = await _get_jira_credentials(runtime_context, tool_name="internal_update_jira_issue")

        await _make_jira_request(
            "PUT",
            f"/issue/{issue_key}",
            jira_config,
            json_data={"fields": updates},
        )

        return {"success": True, "issue_key": issue_key, "updated_fields": list(updates.keys())}

    except Exception as e:
        logger.error(f"Failed to update Jira issue: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_transition_jira_issue(
    issue_key: str,
    transition_id: str,
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """
    Transition a Jira issue to a different status.

    Args:
        issue_key: Jira issue key
        transition_id: Transition ID
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with transition result
    """
    try:
        jira_config = await _get_jira_credentials(runtime_context, tool_name="internal_transition_jira_issue")

        await _make_jira_request(
            "POST",
            f"/issue/{issue_key}/transitions",
            jira_config,
            json_data={"transition": {"id": transition_id}},
        )

        return {"success": True, "issue_key": issue_key, "transition_id": transition_id}

    except Exception as e:
        logger.error(f"Failed to transition Jira issue: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_get_jira_project(
    project_key: str, config: dict[str, Any] | None = None, runtime_context: Any | None = None
) -> dict[str, Any]:
    """
    Get Jira project information.

    Args:
        project_key: Jira project key
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with project details
    """
    try:
        jira_config = await _get_jira_credentials(runtime_context, tool_name="internal_get_jira_project")

        result = await _make_jira_request("GET", f"/project/{project_key}", jira_config)

        return {
            "success": True,
            "project": {
                "key": result["key"],
                "name": result["name"],
                "description": result.get("description", ""),
                "lead": result.get("lead", {}).get("displayName"),
                "url": result.get("self"),
                "issue_types": [it["name"] for it in result.get("issueTypes", [])],
            },
        }

    except Exception as e:
        logger.error(f"Failed to get Jira project: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_create_jira_issue(
    project_key: str,
    summary: str,
    issue_type: str = "Task",
    description: str | None = None,
    priority: str | None = None,
    assignee_account_id: str | None = None,
    labels: list[str] | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """
    Create a new Jira issue.

    Args:
        project_key: Jira project key (e.g., 'PROJ')
        summary: Issue summary/title
        issue_type: Issue type (e.g., 'Task', 'Bug', 'Story', 'Epic')
        description: Issue description (optional)
        priority: Priority name (e.g., 'High', 'Medium', 'Low') (optional)
        assignee_account_id: Assignee's Atlassian account ID (optional)
        labels: List of labels (optional)
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with created issue details
    """
    try:
        jira_config = await _get_jira_credentials(runtime_context, tool_name="internal_create_jira_issue")

        # Build the issue fields
        fields = {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"name": issue_type},
        }

        if description:
            # Jira API v3 uses Atlassian Document Format (ADF) for description
            fields["description"] = {
                "type": "doc",
                "version": 1,
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}],
            }

        if priority:
            fields["priority"] = {"name": priority}

        if assignee_account_id:
            fields["assignee"] = {"accountId": assignee_account_id}

        if labels:
            fields["labels"] = labels

        result = await _make_jira_request("POST", "/issue", jira_config, json_data={"fields": fields})

        return {
            "success": True,
            "issue": {
                "id": result["id"],
                "key": result["key"],
                "url": _get_jira_browse_url(jira_config, result["key"]),
            },
        }

    except Exception as e:
        logger.error(f"Failed to create Jira issue: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def _make_jira_agile_request(
    method: str,
    endpoint: str,
    jira_config: dict[str, Any],
    params: dict[str, Any] | None = None,
    json_data: dict[str, Any] | None = None,
) -> dict[str, Any] | list[Any]:
    """
    Make authenticated request to Jira Agile/Software API.

    Uses /rest/agile/1.0/ instead of /rest/api/3/.
    """
    auth_type = jira_config.get("auth_type", "basic")

    if auth_type == "oauth":
        cloud_id = jira_config.get("cloud_id")
        access_token = jira_config.get("access_token")

        if not cloud_id or not access_token:
            raise ValueError("OAuth requires cloud_id and access_token")

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        url = f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/agile/1.0{endpoint}"
    else:
        domain = jira_config.get("domain")
        email = jira_config.get("email")
        api_token = jira_config.get("api_token")

        if not domain or not email or not api_token:
            raise ValueError("Basic auth requires domain, email, and api_token")

        auth_string = f"{email}:{api_token}"
        auth_bytes = auth_string.encode("ascii")
        auth_base64 = base64.b64encode(auth_bytes).decode("ascii")

        headers = {
            "Authorization": f"Basic {auth_base64}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        url = f"https://{domain}.atlassian.net/rest/agile/1.0{endpoint}"

    async with httpx.AsyncClient() as client:
        response = await client.request(
            method=method, url=url, headers=headers, params=params, json=json_data, timeout=30.0
        )
        response.raise_for_status()
        return response.json()


async def internal_get_jira_boards(
    project_key: str | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """
    Get Jira boards (Scrum/Kanban boards).

    Args:
        project_key: Filter boards by project key (optional)
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with list of boards
    """
    try:
        jira_config = await _get_jira_credentials(runtime_context, tool_name="internal_get_jira_boards")

        params = {}
        if project_key:
            params["projectKeyOrId"] = project_key

        result = await _make_jira_agile_request("GET", "/board", jira_config, params=params)

        boards = [
            {
                "id": board["id"],
                "name": board["name"],
                "type": board.get("type"),
                "project_key": board.get("location", {}).get("projectKey"),
            }
            for board in result.get("values", [])
        ]

        return {"success": True, "boards": boards, "total": result.get("total", len(boards))}

    except Exception as e:
        logger.error(f"Failed to get Jira boards: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_get_jira_sprints(
    board_id: int,
    state: str | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """
    Get sprints for a Jira board.

    Args:
        board_id: Board ID
        state: Filter by sprint state ('active', 'closed', 'future') (optional)
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with list of sprints
    """
    try:
        jira_config = await _get_jira_credentials(runtime_context, tool_name="internal_get_jira_sprints")

        params = {}
        if state:
            params["state"] = state

        result = await _make_jira_agile_request("GET", f"/board/{board_id}/sprint", jira_config, params=params)

        sprints = [
            {
                "id": sprint["id"],
                "name": sprint["name"],
                "state": sprint.get("state"),
                "start_date": sprint.get("startDate"),
                "end_date": sprint.get("endDate"),
                "complete_date": sprint.get("completeDate"),
                "goal": sprint.get("goal"),
            }
            for sprint in result.get("values", [])
        ]

        return {"success": True, "sprints": sprints, "total": result.get("total", len(sprints))}

    except Exception as e:
        logger.error(f"Failed to get Jira sprints: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_get_sprint_issues(
    sprint_id: int,
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """
    Get all issues in a sprint.

    Args:
        sprint_id: Sprint ID
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with sprint issues and summary
    """
    try:
        jira_config = await _get_jira_credentials(runtime_context, tool_name="internal_get_sprint_issues")

        result = await _make_jira_agile_request("GET", f"/sprint/{sprint_id}/issue", jira_config)

        issues = []
        status_counts = {}
        assignee_counts = {}

        for issue in result.get("issues", []):
            fields = issue.get("fields", {})
            status = fields.get("status", {})
            assignee = fields.get("assignee")
            priority = fields.get("priority")

            status_name = status.get("name") if status else "Unknown"
            assignee_name = assignee.get("displayName") if assignee else "Unassigned"

            # Count by status
            status_counts[status_name] = status_counts.get(status_name, 0) + 1
            # Count by assignee
            assignee_counts[assignee_name] = assignee_counts.get(assignee_name, 0) + 1

            issues.append(
                {
                    "key": issue["key"],
                    "summary": fields.get("summary", ""),
                    "status": status_name,
                    "priority": priority.get("name") if priority else None,
                    "assignee": assignee_name,
                    "story_points": fields.get("customfield_10016"),  # Common story points field
                }
            )

        return {
            "success": True,
            "issues": issues,
            "total": len(issues),
            "summary": {
                "by_status": status_counts,
                "by_assignee": assignee_counts,
            },
        }

    except Exception as e:
        logger.error(f"Failed to get sprint issues: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_start_jira_sprint(
    sprint_id: int,
    start_date: str | None = None,
    end_date: str | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """
    Start a Jira sprint.

    Args:
        sprint_id: Sprint ID
        start_date: Sprint start date (ISO format, defaults to now)
        end_date: Sprint end date (ISO format, required)
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with result
    """
    try:
        jira_config = await _get_jira_credentials(runtime_context, tool_name="internal_start_jira_sprint")

        from datetime import datetime

        update_data = {"state": "active"}

        if start_date:
            update_data["startDate"] = start_date
        else:
            update_data["startDate"] = datetime.now(UTC).isoformat()

        if end_date:
            update_data["endDate"] = end_date

        await _make_jira_agile_request("POST", f"/sprint/{sprint_id}", jira_config, json_data=update_data)

        return {"success": True, "sprint_id": sprint_id, "state": "active"}

    except Exception as e:
        logger.error(f"Failed to start Jira sprint: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_close_jira_sprint(
    sprint_id: int,
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """
    Close/complete a Jira sprint.

    Args:
        sprint_id: Sprint ID
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with result
    """
    try:
        jira_config = await _get_jira_credentials(runtime_context, tool_name="internal_close_jira_sprint")

        from datetime import datetime

        update_data = {
            "state": "closed",
            "completeDate": datetime.now(UTC).isoformat(),
        }

        await _make_jira_agile_request("POST", f"/sprint/{sprint_id}", jira_config, json_data=update_data)

        return {"success": True, "sprint_id": sprint_id, "state": "closed"}

    except Exception as e:
        logger.error(f"Failed to close Jira sprint: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_get_jira_users(
    project_key: str,
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """
    Get users assignable to issues in a project.

    Args:
        project_key: Project key
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with list of users
    """
    try:
        jira_config = await _get_jira_credentials(runtime_context, tool_name="internal_get_jira_users")

        result = await _make_jira_request(
            "GET", "/user/assignable/search", jira_config, params={"project": project_key}
        )

        users = [
            {
                "account_id": user["accountId"],
                "display_name": user.get("displayName"),
                "email": user.get("emailAddress"),
                "active": user.get("active", True),
            }
            for user in result
        ]

        return {"success": True, "users": users, "total": len(users)}

    except Exception as e:
        logger.error(f"Failed to get Jira users: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
