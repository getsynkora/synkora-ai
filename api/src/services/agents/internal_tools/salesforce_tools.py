"""
Salesforce Integration Tools.

Provides helpers for creating and managing Salesforce Cases and Contacts.
Auth: OAuth 2.0 (instance_url + access_token).
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_SF_API_VERSION = "v59.0"


async def _get_salesforce_credentials(runtime_context: Any, tool_name: str) -> dict[str, Any]:
    """Resolve Salesforce credentials via CredentialResolver."""
    if not runtime_context:
        raise ValueError("No runtime context available. Please configure Salesforce integration in OAuth Apps.")
    from src.services.agents.credential_resolver import CredentialResolver

    resolver = CredentialResolver(runtime_context)
    creds = await resolver.get_salesforce_credentials(tool_name)
    if not creds:
        raise ValueError(
            "Salesforce authentication not configured. Please connect your Salesforce account in OAuth Apps settings."
        )
    return creds


async def _make_salesforce_request(
    method: str,
    path: str,
    creds: dict[str, Any],
    params: dict[str, Any] | None = None,
    json_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Make an authenticated request to the Salesforce REST API."""
    instance_url = creds["instance_url"].rstrip("/")
    access_token = creds["access_token"]
    url = f"{instance_url}/services/data/{_SF_API_VERSION}{path}"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    async with httpx.AsyncClient() as client:
        response = await client.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json_data,
            timeout=30.0,
        )
        response.raise_for_status()
        if response.status_code in (204, 201) and not response.content:
            return {}
        return response.json()


async def _soql(creds: dict[str, Any], query: str) -> list[dict[str, Any]]:
    """Run a SOQL query and return the records list."""
    data = await _make_salesforce_request("GET", "/query", creds, params={"q": query})
    return data.get("records", [])


def _format_case(case: dict[str, Any], instance_url: str) -> dict[str, Any]:
    case_id = case.get("Id") or case.get("id", "")
    return {
        "id": case_id,
        "case_number": case.get("CaseNumber"),
        "subject": case.get("Subject", ""),
        "description": case.get("Description", ""),
        "status": case.get("Status"),
        "priority": case.get("Priority"),
        "origin": case.get("Origin"),
        "contact_id": case.get("ContactId"),
        "created_at": case.get("CreatedDate"),
        "url": f"{instance_url.rstrip('/')}/{case_id}",
    }


async def create_salesforce_case(
    instance_url: str,
    access_token: str,
    subject: str,
    description: str,
    priority: str = "Medium",
    origin: str = "Chat",
    contact_email: str | None = None,
    contact_name: str | None = None,
) -> dict[str, Any]:
    """
    Create a Salesforce Case directly with provided credentials.
    Used by the handoff registry without requiring a full runtime context.
    """
    creds = {"instance_url": instance_url, "access_token": access_token}

    # Map generic priority labels to Salesforce values
    sf_priority = {"low": "Low", "normal": "Medium", "medium": "Medium", "high": "High", "urgent": "High"}.get(
        priority.lower(), "Medium"
    )

    body: dict[str, Any] = {
        "Subject": subject,
        "Description": description,
        "Status": "New",
        "Origin": origin,
        "Priority": sf_priority,
    }

    # Optionally resolve / create a Contact and attach
    if contact_email:
        try:
            records = await _soql(
                creds,
                f"SELECT Id FROM Contact WHERE Email = '{contact_email}' LIMIT 1",
            )
            if records:
                body["ContactId"] = records[0]["Id"]
            elif contact_name:
                parts = (contact_name or "").split(" ", 1)
                new_contact = await _make_salesforce_request(
                    "POST",
                    "/sobjects/Contact",
                    creds,
                    json_data={
                        "FirstName": parts[0],
                        "LastName": parts[1] if len(parts) > 1 else "Unknown",
                        "Email": contact_email,
                    },
                )
                if new_contact.get("id"):
                    body["ContactId"] = new_contact["id"]
        except Exception as e:
            logger.warning("Could not resolve/create Salesforce Contact: %s", e)

    result = await _make_salesforce_request("POST", "/sobjects/Case", creds, json_data=body)
    case_id = result.get("id", "")
    return {
        "id": case_id,
        "subject": subject,
        "status": "New",
        "priority": sf_priority,
        "url": f"{instance_url.rstrip('/')}/lightning/r/Case/{case_id}/view",
    }


async def internal_create_salesforce_case(
    subject: str,
    description: str,
    priority: str = "normal",
    contact_email: str | None = None,
    contact_name: str | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Create a new Salesforce support Case.

    Args:
        subject: Case subject
        description: Case description
        priority: 'low', 'normal', 'high', or 'urgent'
        contact_email: Requester email (optional)
        contact_name: Requester full name (optional, used when creating new contact)
        config: Config dict
        runtime_context: Runtime context for auth
    """
    try:
        creds = await _get_salesforce_credentials(runtime_context, "internal_create_salesforce_case")
        case = await create_salesforce_case(
            instance_url=creds["instance_url"],
            access_token=creds["access_token"],
            subject=subject,
            description=description,
            priority=priority,
            contact_email=contact_email,
            contact_name=contact_name,
        )
        return {"success": True, "case": case}
    except Exception as e:
        logger.error("Failed to create Salesforce case: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_update_salesforce_case(
    case_id: str,
    status: str | None = None,
    priority: str | None = None,
    subject: str | None = None,
    description: str | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Update a Salesforce Case.

    Args:
        case_id: Salesforce Case ID (15 or 18-char)
        status: 'New', 'Working', 'Escalated', 'Closed'
        priority: 'Low', 'Medium', 'High'
        subject: New subject
        description: New description
        config: Config dict
        runtime_context: Runtime context for auth
    """
    try:
        creds = await _get_salesforce_credentials(runtime_context, "internal_update_salesforce_case")
        updates: dict[str, Any] = {}
        if status:
            updates["Status"] = status
        if priority:
            updates["Priority"] = {"low": "Low", "normal": "Medium", "medium": "Medium", "high": "High"}.get(
                priority.lower(), priority
            )
        if subject:
            updates["Subject"] = subject
        if description:
            updates["Description"] = description
        if not updates:
            return {"success": False, "error": "No fields to update provided"}

        await _make_salesforce_request("PATCH", f"/sobjects/Case/{case_id}", creds, json_data=updates)
        return {"success": True, "case_id": case_id, "updated_fields": list(updates.keys())}
    except Exception as e:
        logger.error("Failed to update Salesforce case %s: %s", case_id, e, exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_add_salesforce_case_comment(
    case_id: str,
    comment: str,
    is_published: bool = True,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Add a comment to a Salesforce Case.

    Args:
        case_id: Salesforce Case ID
        comment: Comment body text
        is_published: Whether the comment is visible to the customer
        config: Config dict
        runtime_context: Runtime context for auth
    """
    try:
        creds = await _get_salesforce_credentials(runtime_context, "internal_add_salesforce_case_comment")
        result = await _make_salesforce_request(
            "POST",
            "/sobjects/CaseComment",
            creds,
            json_data={
                "ParentId": case_id,
                "CommentBody": comment,
                "IsPublished": is_published,
            },
        )
        return {"success": True, "comment_id": result.get("id")}
    except Exception as e:
        logger.error("Failed to add comment to Salesforce case %s: %s", case_id, e, exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_list_salesforce_cases(
    status: str | None = None,
    max_results: int = 25,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    List recent Salesforce Cases via SOQL.

    Args:
        status: Filter by status (optional)
        max_results: Maximum number of results
        config: Config dict
        runtime_context: Runtime context for auth
    """
    try:
        creds = await _get_salesforce_credentials(runtime_context, "internal_list_salesforce_cases")
        where = f"WHERE Status = '{status}'" if status else "WHERE IsClosed = false"
        limit = min(max_results, 200)
        query = (
            f"SELECT Id, CaseNumber, Subject, Status, Priority, Origin, CreatedDate "
            f"FROM Case {where} ORDER BY CreatedDate DESC LIMIT {limit}"
        )
        records = await _soql(creds, query)
        cases = [_format_case(r, creds["instance_url"]) for r in records]
        return {"success": True, "cases": cases, "total": len(cases)}
    except Exception as e:
        logger.error("Failed to list Salesforce cases: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}
