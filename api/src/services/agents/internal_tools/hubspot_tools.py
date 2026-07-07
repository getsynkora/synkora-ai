"""
HubSpot CRM Integration Tools.

Provides helpers for creating and managing HubSpot tickets and contacts.
Auth: OAuth Bearer token or Private App access token.
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_HUBSPOT_BASE = "https://api.hubapi.com"

_PRIORITY_MAP = {"low": "LOW", "normal": "MEDIUM", "medium": "MEDIUM", "high": "HIGH", "urgent": "HIGH"}


async def _get_hubspot_credentials(runtime_context: Any, tool_name: str) -> dict[str, Any]:
    """Resolve HubSpot credentials via CredentialResolver."""
    if not runtime_context:
        raise ValueError("No runtime context available. Please configure HubSpot integration in OAuth Apps.")
    from src.services.agents.credential_resolver import CredentialResolver

    resolver = CredentialResolver(runtime_context)
    creds = await resolver.get_hubspot_credentials(tool_name)
    if not creds:
        raise ValueError(
            "HubSpot authentication not configured. Please connect your HubSpot account in OAuth Apps settings."
        )
    return creds


async def _make_hubspot_request(
    method: str,
    endpoint: str,
    creds: dict[str, Any],
    params: dict[str, Any] | None = None,
    json_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Make an authenticated request to the HubSpot API."""
    access_token = creds["access_token"]
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient() as client:
        response = await client.request(
            method=method,
            url=f"{_HUBSPOT_BASE}{endpoint}",
            headers=headers,
            params=params,
            json=json_data,
            timeout=30.0,
        )
        response.raise_for_status()
        if response.status_code == 204:
            return {}
        return response.json()


def _format_ticket(ticket: dict[str, Any]) -> dict[str, Any]:
    props = ticket.get("properties", {})
    return {
        "id": ticket.get("id"),
        "subject": props.get("subject", ""),
        "content": props.get("content", ""),
        "status": props.get("hs_pipeline_stage"),
        "priority": props.get("hs_ticket_priority"),
        "created_at": props.get("createdate"),
        "updated_at": props.get("hs_lastmodifieddate"),
        "url": f"https://app.hubspot.com/contacts/tickets/{ticket.get('id')}",
    }


async def create_hubspot_ticket(
    access_token: str,
    subject: str,
    content: str,
    priority: str = "normal",
    pipeline: str = "0",
    pipeline_stage: str = "1",
    contact_email: str | None = None,
) -> dict[str, Any]:
    """
    Create a HubSpot ticket directly with provided credentials.
    Used by the handoff registry without requiring a full runtime context.
    """
    creds = {"access_token": access_token}
    properties: dict[str, Any] = {
        "subject": subject,
        "content": content,
        "hs_pipeline": pipeline,
        "hs_pipeline_stage": pipeline_stage,
        "hs_ticket_priority": _PRIORITY_MAP.get(priority, "MEDIUM"),
    }
    data = await _make_hubspot_request(
        "POST",
        "/crm/v3/objects/tickets",
        creds,
        json_data={"properties": properties},
    )
    ticket = _format_ticket(data)

    # Associate contact if email provided
    if contact_email and data.get("id"):
        try:
            await _associate_contact_to_ticket(creds, data["id"], contact_email)
        except Exception as e:
            logger.warning("Could not associate contact to HubSpot ticket: %s", e)

    return ticket


async def _associate_contact_to_ticket(creds: dict[str, Any], ticket_id: str, email: str) -> None:
    """Find or create a contact and associate with the ticket."""
    # Search for existing contact
    try:
        search = await _make_hubspot_request(
            "POST",
            "/crm/v3/objects/contacts/search",
            creds,
            json_data={
                "filterGroups": [{"filters": [{"propertyName": "email", "operator": "EQ", "value": email}]}],
                "limit": 1,
            },
        )
        results = search.get("results", [])
        contact_id = results[0]["id"] if results else None
    except Exception:
        contact_id = None

    if not contact_id:
        # Create minimal contact
        try:
            contact = await _make_hubspot_request(
                "POST",
                "/crm/v3/objects/contacts",
                creds,
                json_data={"properties": {"email": email}},
            )
            contact_id = contact.get("id")
        except Exception:
            return

    if contact_id:
        await _make_hubspot_request(
            "PUT",
            f"/crm/v4/objects/tickets/{ticket_id}/associations/contacts/{contact_id}",
            creds,
            json_data=[{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 16}],
        )


async def internal_create_hubspot_ticket(
    subject: str,
    content: str,
    priority: str = "normal",
    contact_email: str | None = None,
    pipeline_stage: str = "1",
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Create a new HubSpot support ticket.

    Args:
        subject: Ticket subject
        content: Ticket description / body
        priority: 'low', 'normal', 'high', or 'urgent'
        contact_email: Associate with this contact email (optional)
        pipeline_stage: Pipeline stage ID (default '1' = New)
        config: Config dict
        runtime_context: Runtime context for auth
    """
    try:
        creds = await _get_hubspot_credentials(runtime_context, "internal_create_hubspot_ticket")
        ticket = await create_hubspot_ticket(
            access_token=creds["access_token"],
            subject=subject,
            content=content,
            priority=priority,
            pipeline_stage=pipeline_stage,
            contact_email=contact_email,
        )
        return {"success": True, "ticket": ticket}
    except Exception as e:
        logger.error("Failed to create HubSpot ticket: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_update_hubspot_ticket(
    ticket_id: str,
    subject: str | None = None,
    content: str | None = None,
    priority: str | None = None,
    pipeline_stage: str | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Update a HubSpot ticket.

    Args:
        ticket_id: HubSpot ticket object ID
        subject: New subject
        content: New description
        priority: 'low', 'normal', 'high', 'urgent'
        pipeline_stage: Pipeline stage ID
        config: Config dict
        runtime_context: Runtime context for auth
    """
    try:
        creds = await _get_hubspot_credentials(runtime_context, "internal_update_hubspot_ticket")
        properties: dict[str, Any] = {}
        if subject:
            properties["subject"] = subject
        if content:
            properties["content"] = content
        if priority:
            properties["hs_ticket_priority"] = _PRIORITY_MAP.get(priority, "MEDIUM")
        if pipeline_stage:
            properties["hs_pipeline_stage"] = pipeline_stage
        if not properties:
            return {"success": False, "error": "No fields to update provided"}

        data = await _make_hubspot_request(
            "PATCH",
            f"/crm/v3/objects/tickets/{ticket_id}",
            creds,
            json_data={"properties": properties},
        )
        return {"success": True, "ticket": _format_ticket(data)}
    except Exception as e:
        logger.error("Failed to update HubSpot ticket %s: %s", ticket_id, e, exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_list_hubspot_tickets(
    max_results: int = 25,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    List recent HubSpot tickets.

    Args:
        max_results: Maximum number of results
        config: Config dict
        runtime_context: Runtime context for auth
    """
    try:
        creds = await _get_hubspot_credentials(runtime_context, "internal_list_hubspot_tickets")
        data = await _make_hubspot_request(
            "GET",
            "/crm/v3/objects/tickets",
            creds,
            params={
                "limit": min(max_results, 100),
                "properties": "subject,content,hs_pipeline_stage,hs_ticket_priority,createdate",
                "sort": "-createdate",
            },
        )
        tickets = [_format_ticket(t) for t in data.get("results", [])]
        return {"success": True, "tickets": tickets, "total": data.get("total", len(tickets))}
    except Exception as e:
        logger.error("Failed to list HubSpot tickets: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}
