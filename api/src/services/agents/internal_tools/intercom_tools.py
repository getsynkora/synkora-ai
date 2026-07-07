"""
Intercom Integration Tools.

Provides helpers for creating and managing Intercom conversations and contacts.
Auth: Bearer token (OAuth access token or Personal Access Token).
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_INTERCOM_BASE = "https://api.intercom.io"


async def _get_intercom_credentials(runtime_context: Any, tool_name: str) -> dict[str, Any]:
    """Resolve Intercom credentials via CredentialResolver."""
    if not runtime_context:
        raise ValueError("No runtime context available. Please configure Intercom integration in OAuth Apps.")
    from src.services.agents.credential_resolver import CredentialResolver

    resolver = CredentialResolver(runtime_context)
    creds = await resolver.get_intercom_credentials(tool_name)
    if not creds:
        raise ValueError(
            "Intercom authentication not configured. "
            "Please connect your Intercom account in OAuth Apps settings."
        )
    return creds


async def _make_intercom_request(
    method: str,
    endpoint: str,
    creds: dict[str, Any],
    params: dict[str, Any] | None = None,
    json_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Make an authenticated request to the Intercom API."""
    access_token = creds["access_token"]
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Intercom-Version": "2.11",
    }
    async with httpx.AsyncClient() as client:
        response = await client.request(
            method=method,
            url=f"{_INTERCOM_BASE}{endpoint}",
            headers=headers,
            params=params,
            json=json_data,
            timeout=30.0,
        )
        response.raise_for_status()
        if response.status_code == 204:
            return {}
        return response.json()


async def _find_or_create_contact(creds: dict[str, Any], email: str, name: str | None = None) -> str | None:
    """
    Find an existing Intercom contact by email or create a new one.
    Returns the contact ID or None on failure.
    """
    try:
        result = await _make_intercom_request(
            "POST",
            "/contacts/search",
            creds,
            json_data={
                "query": {"field": "email", "operator": "=", "value": email},
                "pagination": {"per_page": 1},
            },
        )
        contacts = result.get("data", [])
        if contacts:
            return contacts[0]["id"]

        # Create new contact
        body: dict[str, Any] = {"role": "user", "email": email}
        if name:
            body["name"] = name
        contact = await _make_intercom_request("POST", "/contacts", creds, json_data=body)
        return contact.get("id")
    except Exception as e:
        logger.warning("Failed to find/create Intercom contact: %s", e)
        return None


def _format_conversation(conv: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": conv.get("id"),
        "title": conv.get("title", ""),
        "state": conv.get("state"),
        "open": conv.get("open", True),
        "created_at": conv.get("created_at"),
        "updated_at": conv.get("updated_at"),
        "url": f"https://app.intercom.com/a/inbox/conversation/{conv.get('id')}",
    }


async def create_intercom_conversation(
    access_token: str,
    message_body: str,
    contact_email: str | None = None,
    contact_name: str | None = None,
) -> dict[str, Any]:
    """
    Create an Intercom conversation (admin-initiated) with provided credentials.
    Used by the handoff registry without requiring a full runtime context.
    """
    creds = {"access_token": access_token}

    # Resolve the contact
    contact_id = None
    if contact_email:
        contact_id = await _find_or_create_contact(creds, contact_email, contact_name)

    if not contact_id:
        # Cannot create an outbound conversation without a contact — tag instead
        logger.warning("No Intercom contact resolved; skipping conversation creation")
        return {"id": None, "note": "No contact resolved, conversation not created"}

    # Create an outbound conversation (admin-initiated message)
    # For this we use the /conversations endpoint with from.type = admin
    # First get admin list to pick the first admin as sender
    try:
        admins = await _make_intercom_request("GET", "/admins", creds)
        admin_list = admins.get("admins", [])
        admin_id = str(admin_list[0]["id"]) if admin_list else None
    except Exception:
        admin_id = None

    if admin_id:
        body: dict[str, Any] = {
            "from": {"type": "admin", "id": admin_id},
            "to": {"type": "user", "id": contact_id},
            "subject": "Support Handoff",
            "body": message_body,
            "message_type": "inapp",
            "template": "plain",
        }
    else:
        # Fall back to a contact-initiated conversation note
        body = {
            "type": "user",
            "id": contact_id,
            "body": message_body,
        }

    try:
        result = await _make_intercom_request("POST", "/messages", creds, json_data=body)
        conv_id = result.get("conversation_id") or result.get("id")
        return {"id": conv_id, "contact_id": contact_id}
    except Exception as e:
        logger.warning("Could not create Intercom conversation: %s", e)
        return {"id": None, "note": str(e)}


async def internal_create_intercom_conversation(
    message_body: str,
    contact_email: str | None = None,
    contact_name: str | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Create an Intercom conversation / outbound message.

    Args:
        message_body: Message text
        contact_email: Target contact email (optional)
        contact_name: Target contact name (optional)
        config: Config dict
        runtime_context: Runtime context for auth
    """
    try:
        creds = await _get_intercom_credentials(runtime_context, "internal_create_intercom_conversation")
        result = await create_intercom_conversation(
            access_token=creds["access_token"],
            message_body=message_body,
            contact_email=contact_email,
            contact_name=contact_name,
        )
        return {"success": True, "conversation": result}
    except Exception as e:
        logger.error("Failed to create Intercom conversation: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_reply_intercom_conversation(
    conversation_id: str,
    message_body: str,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Send an admin reply to an Intercom conversation.

    Args:
        conversation_id: Intercom conversation ID
        message_body: Reply text
        config: Config dict
        runtime_context: Runtime context for auth
    """
    try:
        creds = await _get_intercom_credentials(runtime_context, "internal_reply_intercom_conversation")
        # Get first admin
        admins = await _make_intercom_request("GET", "/admins", creds)
        admin_list = admins.get("admins", [])
        if not admin_list:
            return {"success": False, "error": "No Intercom admin found to reply as"}

        result = await _make_intercom_request(
            "POST",
            f"/conversations/{conversation_id}/reply",
            creds,
            json_data={
                "type": "admin",
                "admin_id": str(admin_list[0]["id"]),
                "message_type": "comment",
                "body": message_body,
            },
        )
        return {"success": True, "conversation": _format_conversation(result)}
    except Exception as e:
        logger.error("Failed to reply to Intercom conversation %s: %s", conversation_id, e, exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_close_intercom_conversation(
    conversation_id: str,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Close an Intercom conversation.

    Args:
        conversation_id: Intercom conversation ID
        config: Config dict
        runtime_context: Runtime context for auth
    """
    try:
        creds = await _get_intercom_credentials(runtime_context, "internal_close_intercom_conversation")
        admins = await _make_intercom_request("GET", "/admins", creds)
        admin_list = admins.get("admins", [])
        if not admin_list:
            return {"success": False, "error": "No Intercom admin found"}

        result = await _make_intercom_request(
            "POST",
            f"/conversations/{conversation_id}/parts",
            creds,
            json_data={
                "message_type": "close",
                "type": "admin",
                "admin_id": str(admin_list[0]["id"]),
            },
        )
        return {"success": True, "conversation": _format_conversation(result)}
    except Exception as e:
        logger.error("Failed to close Intercom conversation %s: %s", conversation_id, e, exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_list_intercom_conversations(
    state: str = "open",
    max_results: int = 25,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    List Intercom conversations.

    Args:
        state: 'open', 'closed', 'snoozed', or 'all'
        max_results: Maximum number of results
        config: Config dict
        runtime_context: Runtime context for auth
    """
    try:
        creds = await _get_intercom_credentials(runtime_context, "internal_list_intercom_conversations")
        params: dict[str, Any] = {"per_page": min(max_results, 150)}
        if state != "all":
            params["state"] = state

        data = await _make_intercom_request("GET", "/conversations", creds, params=params)
        convs = [_format_conversation(c) for c in data.get("conversations", [])]
        return {"success": True, "conversations": convs, "total": data.get("total_count", len(convs))}
    except Exception as e:
        logger.error("Failed to list Intercom conversations: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}
