"""
Freshdesk Integration Tools.

Provides helpers for creating and managing Freshdesk support tickets.
Auth: API key via HTTP Basic Auth (api_key:X).
"""

import base64
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_PRIORITY = {"low": 1, "medium": 2, "normal": 2, "high": 3, "urgent": 4}
_STATUS = {"open": 2, "pending": 3, "resolved": 4, "closed": 5}


async def _get_freshdesk_credentials(runtime_context: Any, tool_name: str) -> dict[str, Any]:
    """Resolve Freshdesk credentials via CredentialResolver."""
    if not runtime_context:
        raise ValueError("No runtime context available. Please configure Freshdesk integration in OAuth Apps.")
    from src.services.agents.credential_resolver import CredentialResolver

    resolver = CredentialResolver(runtime_context)
    creds = await resolver.get_freshdesk_credentials(tool_name)
    if not creds:
        raise ValueError(
            "Freshdesk authentication not configured. "
            "Please add your Freshdesk API key in OAuth Apps settings."
        )
    return creds


async def _make_freshdesk_request(
    method: str,
    endpoint: str,
    creds: dict[str, Any],
    params: dict[str, Any] | None = None,
    json_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Make an authenticated request to the Freshdesk v2 API."""
    subdomain = creds["subdomain"]
    api_key = creds["api_key"]
    base_url = f"https://{subdomain}.freshdesk.com/api/v2"

    # Freshdesk Basic Auth: api_key as username, "X" as password
    raw = f"{api_key}:X"
    encoded = base64.b64encode(raw.encode()).decode()
    headers = {
        "Authorization": f"Basic {encoded}",
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
    return {
        "id": ticket.get("id"),
        "subject": ticket.get("subject", ""),
        "description": ticket.get("description_text", ""),
        "status": ticket.get("status"),
        "priority": ticket.get("priority"),
        "requester_id": ticket.get("requester_id"),
        "responder_id": ticket.get("responder_id"),
        "tags": ticket.get("tags", []),
        "created_at": ticket.get("created_at"),
        "updated_at": ticket.get("updated_at"),
        "url": f"https://{subdomain}.freshdesk.com/a/tickets/{ticket.get('id')}",
    }


async def create_freshdesk_ticket(
    subdomain: str,
    api_key: str,
    subject: str,
    description: str,
    requester_email: str | None = None,
    priority: str = "normal",
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """
    Create a Freshdesk ticket directly with provided credentials.
    Used by the handoff registry without requiring a full runtime context.
    """
    creds = {"subdomain": subdomain, "api_key": api_key}
    body: dict[str, Any] = {
        "subject": subject,
        "description": description,
        "status": _STATUS["open"],
        "priority": _PRIORITY.get(priority, 2),
        "source": 7,  # Chat
        "tags": tags or ["ai_handoff"],
    }
    if requester_email:
        body["email"] = requester_email
    else:
        body["name"] = "Support Request"

    data = await _make_freshdesk_request("POST", "/tickets", creds, json_data=body)
    return _format_ticket(data, subdomain)


async def internal_create_freshdesk_ticket(
    subject: str,
    description: str,
    priority: str = "normal",
    requester_email: str | None = None,
    tags: list[str] | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Create a new Freshdesk support ticket.

    Args:
        subject: Ticket subject
        description: Ticket description / body
        priority: 'low', 'normal', 'high', or 'urgent'
        requester_email: Requester email (optional)
        tags: List of tags (optional)
        config: Config dict
        runtime_context: Runtime context for auth

    Returns:
        Dict with created ticket details
    """
    try:
        creds = await _get_freshdesk_credentials(runtime_context, "internal_create_freshdesk_ticket")
        ticket = await create_freshdesk_ticket(
            subdomain=creds["subdomain"],
            api_key=creds["api_key"],
            subject=subject,
            description=description,
            requester_email=requester_email,
            priority=priority,
            tags=tags,
        )
        return {"success": True, "ticket": ticket}
    except Exception as e:
        logger.error("Failed to create Freshdesk ticket: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_update_freshdesk_ticket(
    ticket_id: int,
    status: str | None = None,
    priority: str | None = None,
    subject: str | None = None,
    tags: list[str] | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Update a Freshdesk ticket.

    Args:
        ticket_id: Freshdesk ticket ID
        status: 'open', 'pending', 'resolved', 'closed'
        priority: 'low', 'normal', 'high', 'urgent'
        subject: New subject
        tags: Replace tags list
        config: Config dict
        runtime_context: Runtime context for auth
    """
    try:
        creds = await _get_freshdesk_credentials(runtime_context, "internal_update_freshdesk_ticket")
        updates: dict[str, Any] = {}
        if status:
            updates["status"] = _STATUS.get(status, 2)
        if priority:
            updates["priority"] = _PRIORITY.get(priority, 2)
        if subject:
            updates["subject"] = subject
        if tags is not None:
            updates["tags"] = tags
        if not updates:
            return {"success": False, "error": "No fields to update provided"}

        data = await _make_freshdesk_request("PUT", f"/tickets/{ticket_id}", creds, json_data=updates)
        return {"success": True, "ticket": _format_ticket(data, creds["subdomain"])}
    except Exception as e:
        logger.error("Failed to update Freshdesk ticket %s: %s", ticket_id, e, exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_add_freshdesk_reply(
    ticket_id: int,
    body: str,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Add a public reply to a Freshdesk ticket.

    Args:
        ticket_id: Freshdesk ticket ID
        body: Reply text (HTML or plain text)
        config: Config dict
        runtime_context: Runtime context for auth
    """
    try:
        creds = await _get_freshdesk_credentials(runtime_context, "internal_add_freshdesk_reply")
        data = await _make_freshdesk_request(
            "POST",
            f"/tickets/{ticket_id}/reply",
            creds,
            json_data={"body": body},
        )
        return {"success": True, "conversation_id": data.get("id")}
    except Exception as e:
        logger.error("Failed to add reply to Freshdesk ticket %s: %s", ticket_id, e, exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_list_freshdesk_tickets(
    status: str | None = None,
    max_results: int = 25,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    List Freshdesk tickets, optionally filtered by status.

    Args:
        status: 'open', 'pending', 'resolved', 'closed' (optional)
        max_results: Maximum number of results
        config: Config dict
        runtime_context: Runtime context for auth
    """
    try:
        creds = await _get_freshdesk_credentials(runtime_context, "internal_list_freshdesk_tickets")
        params: dict[str, Any] = {"per_page": min(max_results, 100), "order_by": "updated_at", "order_type": "desc"}
        if status:
            params["filter"] = status
        data = await _make_freshdesk_request("GET", "/tickets", creds, params=params)
        tickets = [_format_ticket(t, creds["subdomain"]) for t in (data if isinstance(data, list) else [])]
        return {"success": True, "tickets": tickets, "total": len(tickets)}
    except Exception as e:
        logger.error("Failed to list Freshdesk tickets: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}
