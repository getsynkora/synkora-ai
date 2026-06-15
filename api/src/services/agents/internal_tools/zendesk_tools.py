"""
Zendesk Integration Tools.

Provides tools for managing Zendesk tickets, users, and support conversations.
Supports both OAuth (Bearer token) and API token (Basic Auth) authentication.
"""

import base64
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


async def _get_zendesk_credentials(runtime_context: Any, tool_name: str) -> dict[str, Any]:
    """Get Zendesk credentials from runtime context via CredentialResolver."""
    if not runtime_context:
        raise ValueError("No runtime context available. Please configure Zendesk integration in OAuth Apps.")

    from src.services.agents.credential_resolver import CredentialResolver

    resolver = CredentialResolver(runtime_context)
    credentials = await resolver.get_zendesk_credentials(tool_name)

    if not credentials:
        raise ValueError(
            "Zendesk authentication not configured. Please connect your Zendesk account in OAuth Apps settings."
        )

    return credentials


async def _make_zendesk_request(
    method: str,
    endpoint: str,
    zendesk_config: dict[str, Any],
    params: dict[str, Any] | None = None,
    json_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Make an authenticated request to the Zendesk API."""
    subdomain = zendesk_config["subdomain"]
    base_url = f"https://{subdomain}.zendesk.com/api/v2"

    auth_type = zendesk_config.get("auth_type", "oauth")
    if auth_type == "oauth":
        headers = {
            "Authorization": f"Bearer {zendesk_config['access_token']}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
    else:
        email = zendesk_config["email"]
        api_token = zendesk_config["api_token"]
        raw = f"{email}/token:{api_token}"
        encoded = base64.b64encode(raw.encode()).decode()
        headers = {
            "Authorization": f"Basic {encoded}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async with httpx.AsyncClient() as client:
        response = await client.request(
            method=method,
            url=f"{base_url}{endpoint}",
            headers=headers,
            params=params,
            json=json_data,
            timeout=30.0,
        )
        response.raise_for_status()
        if response.status_code == 204:
            return {}
        return response.json()


def _format_ticket(ticket: dict[str, Any], subdomain: str) -> dict[str, Any]:
    """Normalize a Zendesk ticket object into a clean dict."""
    return {
        "id": ticket.get("id"),
        "subject": ticket.get("subject", ""),
        "description": ticket.get("description", ""),
        "status": ticket.get("status"),
        "priority": ticket.get("priority"),
        "type": ticket.get("type"),
        "requester_id": ticket.get("requester_id"),
        "assignee_id": ticket.get("assignee_id"),
        "group_id": ticket.get("group_id"),
        "tags": ticket.get("tags", []),
        "created_at": ticket.get("created_at"),
        "updated_at": ticket.get("updated_at"),
        "url": f"https://{subdomain}.zendesk.com/agent/tickets/{ticket.get('id')}",
    }


async def internal_search_zendesk_tickets(
    query: str,
    status: str | None = None,
    priority: str | None = None,
    max_results: int = 25,
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """
    Search Zendesk tickets using a free-text query.

    Args:
        query: Search terms (e.g., "login error", "password reset")
        status: Filter by status: 'new', 'open', 'pending', 'hold', 'solved', 'closed' (optional)
        priority: Filter by priority: 'low', 'normal', 'high', 'urgent' (optional)
        max_results: Maximum number of results (default: 25)
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with matching tickets
    """
    try:
        zd = await _get_zendesk_credentials(runtime_context, "internal_search_zendesk_tickets")

        search_query = f"type:ticket {query}"
        if status:
            search_query += f" status:{status}"
        if priority:
            search_query += f" priority:{priority}"

        data = await _make_zendesk_request(
            "GET",
            "/search.json",
            zd,
            params={"query": search_query, "per_page": min(max_results, 100)},
        )

        tickets = [
            _format_ticket(t, zd["subdomain"]) for t in data.get("results", []) if t.get("result_type") == "ticket"
        ]

        return {
            "success": True,
            "tickets": tickets,
            "total": data.get("count", len(tickets)),
        }

    except Exception as e:
        logger.error("Failed to search Zendesk tickets: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_get_zendesk_ticket(
    ticket_id: int,
    include_comments: bool = True,
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """
    Get detailed information about a Zendesk ticket including comments.

    Args:
        ticket_id: Zendesk ticket ID
        include_comments: Whether to include ticket comments (default: True)
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with ticket details and comments
    """
    try:
        zd = await _get_zendesk_credentials(runtime_context, "internal_get_zendesk_ticket")

        ticket_data = await _make_zendesk_request("GET", f"/tickets/{ticket_id}.json", zd)
        ticket = _format_ticket(ticket_data["ticket"], zd["subdomain"])

        comments = []
        if include_comments:
            comments_data = await _make_zendesk_request("GET", f"/tickets/{ticket_id}/comments.json", zd)
            comments = [
                {
                    "id": c.get("id"),
                    "body": c.get("body", ""),
                    "public": c.get("public", True),
                    "author_id": c.get("author_id"),
                    "created_at": c.get("created_at"),
                }
                for c in comments_data.get("comments", [])
            ]

        return {"success": True, "ticket": ticket, "comments": comments}

    except Exception as e:
        logger.error("Failed to get Zendesk ticket %s: %s", ticket_id, e, exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_create_zendesk_ticket(
    subject: str,
    description: str,
    priority: str = "normal",
    ticket_type: str | None = None,
    tags: list[str] | None = None,
    requester_email: str | None = None,
    assignee_id: int | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """
    Create a new Zendesk support ticket.

    Args:
        subject: Ticket subject/title
        description: Ticket description (body of the first comment)
        priority: Priority level: 'low', 'normal', 'high', 'urgent' (default: 'normal')
        ticket_type: Ticket type: 'problem', 'incident', 'question', 'task' (optional)
        tags: List of tags to add to the ticket (optional)
        requester_email: Email of the requester (optional, defaults to authenticated user)
        assignee_id: Zendesk user ID to assign the ticket to (optional)
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with created ticket details
    """
    try:
        zd = await _get_zendesk_credentials(runtime_context, "internal_create_zendesk_ticket")

        ticket_body: dict[str, Any] = {
            "subject": subject,
            "comment": {"body": description},
            "priority": priority,
        }
        if ticket_type:
            ticket_body["type"] = ticket_type
        if tags:
            ticket_body["tags"] = tags
        if requester_email:
            ticket_body["requester"] = {"email": requester_email}
        if assignee_id:
            ticket_body["assignee_id"] = assignee_id

        data = await _make_zendesk_request("POST", "/tickets.json", zd, json_data={"ticket": ticket_body})
        ticket = _format_ticket(data["ticket"], zd["subdomain"])

        return {"success": True, "ticket": ticket}

    except Exception as e:
        logger.error("Failed to create Zendesk ticket: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_update_zendesk_ticket(
    ticket_id: int,
    status: str | None = None,
    priority: str | None = None,
    subject: str | None = None,
    assignee_id: int | None = None,
    tags: list[str] | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """
    Update a Zendesk ticket's fields.

    Args:
        ticket_id: Zendesk ticket ID
        status: New status: 'new', 'open', 'pending', 'hold', 'solved', 'closed' (optional)
        priority: New priority: 'low', 'normal', 'high', 'urgent' (optional)
        subject: New subject (optional)
        assignee_id: Zendesk user ID to assign the ticket to (optional)
        tags: Replace tags list (optional)
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with updated ticket details
    """
    try:
        zd = await _get_zendesk_credentials(runtime_context, "internal_update_zendesk_ticket")

        updates: dict[str, Any] = {}
        if status:
            updates["status"] = status
        if priority:
            updates["priority"] = priority
        if subject:
            updates["subject"] = subject
        if assignee_id is not None:
            updates["assignee_id"] = assignee_id
        if tags is not None:
            updates["tags"] = tags

        if not updates:
            return {"success": False, "error": "No fields to update provided"}

        data = await _make_zendesk_request("PUT", f"/tickets/{ticket_id}.json", zd, json_data={"ticket": updates})
        ticket = _format_ticket(data["ticket"], zd["subdomain"])

        return {"success": True, "ticket": ticket}

    except Exception as e:
        logger.error("Failed to update Zendesk ticket %s: %s", ticket_id, e, exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_add_zendesk_comment(
    ticket_id: int,
    body: str,
    public: bool = True,
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """
    Add a comment (reply) to a Zendesk ticket.

    Args:
        ticket_id: Zendesk ticket ID
        body: Comment text
        public: Whether the comment is public (visible to requester) or internal (default: True)
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with the updated ticket
    """
    try:
        zd = await _get_zendesk_credentials(runtime_context, "internal_add_zendesk_comment")

        data = await _make_zendesk_request(
            "PUT",
            f"/tickets/{ticket_id}.json",
            zd,
            json_data={"ticket": {"comment": {"body": body, "public": public}}},
        )
        ticket = _format_ticket(data["ticket"], zd["subdomain"])

        return {"success": True, "ticket": ticket, "comment_added": True}

    except Exception as e:
        logger.error("Failed to add comment to Zendesk ticket %s: %s", ticket_id, e, exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_list_zendesk_tickets(
    status: str | None = None,
    assignee_id: int | None = None,
    max_results: int = 25,
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """
    List recent Zendesk tickets, optionally filtered by status or assignee.

    Args:
        status: Filter by status: 'new', 'open', 'pending', 'hold', 'solved', 'closed' (optional)
        assignee_id: Filter by assignee user ID (optional)
        max_results: Maximum number of results (default: 25)
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with list of tickets
    """
    try:
        zd = await _get_zendesk_credentials(runtime_context, "internal_list_zendesk_tickets")

        params: dict[str, Any] = {"per_page": min(max_results, 100), "sort_by": "updated_at", "sort_order": "desc"}

        if status or assignee_id:
            # Use search endpoint for filtered queries
            query = "type:ticket"
            if status:
                query += f" status:{status}"
            if assignee_id:
                query += f" assignee_id:{assignee_id}"
            data = await _make_zendesk_request(
                "GET", "/search.json", zd, params={"query": query, "per_page": params["per_page"]}
            )
            tickets = [
                _format_ticket(t, zd["subdomain"]) for t in data.get("results", []) if t.get("result_type") == "ticket"
            ]
            total = data.get("count", len(tickets))
        else:
            data = await _make_zendesk_request("GET", "/tickets.json", zd, params=params)
            tickets = [_format_ticket(t, zd["subdomain"]) for t in data.get("tickets", [])]
            total = data.get("count", len(tickets))

        return {"success": True, "tickets": tickets, "total": total}

    except Exception as e:
        logger.error("Failed to list Zendesk tickets: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_get_zendesk_user(
    user_id: int,
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """
    Get a Zendesk user's details.

    Args:
        user_id: Zendesk user ID
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with user details
    """
    try:
        zd = await _get_zendesk_credentials(runtime_context, "internal_get_zendesk_user")

        data = await _make_zendesk_request("GET", f"/users/{user_id}.json", zd)
        user = data.get("user", {})

        return {
            "success": True,
            "user": {
                "id": user.get("id"),
                "name": user.get("name", ""),
                "email": user.get("email", ""),
                "role": user.get("role"),
                "active": user.get("active", True),
                "created_at": user.get("created_at"),
                "phone": user.get("phone"),
                "organization_id": user.get("organization_id"),
            },
        }

    except Exception as e:
        logger.error("Failed to get Zendesk user %s: %s", user_id, e, exc_info=True)
        return {"success": False, "error": str(e)}
