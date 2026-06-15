"""
Zoho CRM Integration Tools.

Provides tools for managing Zoho CRM records — contacts, leads, deals, accounts, and notes.
Supports OAuth 2.0 authentication with data-center-specific API URLs.
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

VALID_MODULES = {"Leads", "Contacts", "Accounts", "Deals", "Tasks", "Calls", "Events", "Notes"}


async def _get_zoho_crm_credentials(runtime_context: Any, tool_name: str) -> dict[str, Any]:
    """Get Zoho CRM credentials from runtime context via CredentialResolver."""
    if not runtime_context:
        raise ValueError("No runtime context available. Please configure Zoho CRM integration in OAuth Apps.")

    from src.services.agents.credential_resolver import CredentialResolver

    resolver = CredentialResolver(runtime_context)
    credentials = await resolver.get_zoho_crm_credentials(tool_name)

    if not credentials:
        raise ValueError(
            "Zoho CRM authentication not configured. Please connect your Zoho CRM account in OAuth Apps settings."
        )

    return credentials


async def _make_zoho_request(
    method: str,
    endpoint: str,
    zoho_config: dict[str, Any],
    params: dict[str, Any] | None = None,
    json_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Make an authenticated request to the Zoho CRM API."""
    dc = zoho_config.get("data_center", "com")
    base_url = f"https://www.zohoapis.{dc}/crm/v3"
    access_token = zoho_config["access_token"]

    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
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


def _format_record(record: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Zoho CRM record to a clean dict with common fields."""
    return {
        "id": record.get("id"),
        "name": record.get("Full_Name")
        or record.get("Name")
        or record.get("Account_Name")
        or record.get("Deal_Name")
        or "",
        "email": record.get("Email"),
        "phone": record.get("Phone") or record.get("Mobile"),
        "owner": (record.get("Owner") or {}).get("name"),
        "created_time": record.get("Created_Time"),
        "modified_time": record.get("Modified_Time"),
        # Include all other fields as-is for completeness
        "fields": {k: v for k, v in record.items() if k not in {"id", "Owner", "$state", "$process_flow", "$approved"}},
    }


async def internal_search_zoho_crm_records(
    module: str,
    query: str,
    max_results: int = 20,
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """
    Search Zoho CRM records by keyword across a module.

    Args:
        module: CRM module name: 'Leads', 'Contacts', 'Accounts', 'Deals', 'Tasks' etc.
        query: Search keyword (searches name, email, phone, etc.)
        max_results: Maximum number of results (default: 20)
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with matching records
    """
    try:
        zoho = await _get_zoho_crm_credentials(runtime_context, "internal_search_zoho_crm_records")

        data = await _make_zoho_request(
            "GET",
            f"/{module}/search",
            zoho,
            params={"word": query, "per_page": min(max_results, 200)},
        )

        records = [_format_record(r) for r in data.get("data", [])]

        return {
            "success": True,
            "module": module,
            "records": records,
            "total": len(records),
        }

    except Exception as e:
        logger.error("Failed to search Zoho CRM %s: %s", module, e, exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_get_zoho_crm_record(
    module: str,
    record_id: str,
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """
    Get a specific Zoho CRM record by ID.

    Args:
        module: CRM module name: 'Leads', 'Contacts', 'Accounts', 'Deals' etc.
        record_id: The record's Zoho CRM ID
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with record details
    """
    try:
        zoho = await _get_zoho_crm_credentials(runtime_context, "internal_get_zoho_crm_record")

        data = await _make_zoho_request("GET", f"/{module}/{record_id}", zoho)
        records = data.get("data", [])

        if not records:
            return {"success": False, "error": f"Record {record_id} not found in {module}"}

        return {"success": True, "module": module, "record": _format_record(records[0])}

    except Exception as e:
        logger.error("Failed to get Zoho CRM record %s/%s: %s", module, record_id, e, exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_list_zoho_crm_records(
    module: str,
    max_results: int = 20,
    sort_by: str | None = None,
    sort_order: str = "desc",
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """
    List records in a Zoho CRM module.

    Args:
        module: CRM module name: 'Leads', 'Contacts', 'Accounts', 'Deals', 'Tasks' etc.
        max_results: Maximum number of records to return (default: 20)
        sort_by: Field to sort by (e.g., 'Modified_Time', 'Created_Time') (optional)
        sort_order: Sort order: 'asc' or 'desc' (default: 'desc')
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with list of records
    """
    try:
        zoho = await _get_zoho_crm_credentials(runtime_context, "internal_list_zoho_crm_records")

        params: dict[str, Any] = {"per_page": min(max_results, 200)}
        if sort_by:
            params["sort_by"] = sort_by
            params["sort_order"] = sort_order

        data = await _make_zoho_request("GET", f"/{module}", zoho, params=params)
        records = [_format_record(r) for r in data.get("data", [])]

        return {
            "success": True,
            "module": module,
            "records": records,
            "total": len(records),
        }

    except Exception as e:
        logger.error("Failed to list Zoho CRM %s: %s", module, e, exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_create_zoho_crm_record(
    module: str,
    fields: dict[str, Any],
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """
    Create a new record in a Zoho CRM module.

    Args:
        module: CRM module name: 'Leads', 'Contacts', 'Accounts', 'Deals' etc.
        fields: Dictionary of field names and values for the new record.
                Examples for Leads: {"Last_Name": "Smith", "Email": "smith@example.com", "Company": "Acme"}
                Examples for Deals: {"Deal_Name": "New Deal", "Stage": "Qualification", "Amount": 10000}
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with the created record ID and details
    """
    try:
        zoho = await _get_zoho_crm_credentials(runtime_context, "internal_create_zoho_crm_record")

        data = await _make_zoho_request("POST", f"/{module}", zoho, json_data={"data": [fields]})

        result = (data.get("data") or [{}])[0]
        details = result.get("details", {})

        return {
            "success": result.get("status") == "success",
            "module": module,
            "record_id": details.get("id"),
            "message": result.get("message", ""),
        }

    except Exception as e:
        logger.error("Failed to create Zoho CRM record in %s: %s", module, e, exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_update_zoho_crm_record(
    module: str,
    record_id: str,
    fields: dict[str, Any],
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """
    Update an existing Zoho CRM record.

    Args:
        module: CRM module name: 'Leads', 'Contacts', 'Accounts', 'Deals' etc.
        record_id: The record's Zoho CRM ID
        fields: Dictionary of field names and new values to update.
                Example: {"Stage": "Closed Won", "Amount": 50000}
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with update result
    """
    try:
        zoho = await _get_zoho_crm_credentials(runtime_context, "internal_update_zoho_crm_record")

        payload = {"id": record_id, **fields}
        data = await _make_zoho_request("PUT", f"/{module}/{record_id}", zoho, json_data={"data": [payload]})

        result = (data.get("data") or [{}])[0]

        return {
            "success": result.get("status") == "success",
            "module": module,
            "record_id": record_id,
            "message": result.get("message", ""),
        }

    except Exception as e:
        logger.error("Failed to update Zoho CRM record %s/%s: %s", module, record_id, e, exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_add_zoho_crm_note(
    module: str,
    record_id: str,
    note_title: str,
    note_content: str,
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """
    Add a note to any Zoho CRM record (Lead, Contact, Deal, etc.).

    Args:
        module: The parent record's module: 'Leads', 'Contacts', 'Accounts', 'Deals' etc.
        record_id: The parent record's Zoho CRM ID
        note_title: Title of the note
        note_content: Body/content of the note
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with created note details
    """
    try:
        zoho = await _get_zoho_crm_credentials(runtime_context, "internal_add_zoho_crm_note")

        payload = {
            "Note_Title": note_title,
            "Note_Content": note_content,
            "Parent_Id": {"id": record_id, "module": {"api_name": module}},
        }

        data = await _make_zoho_request("POST", "/Notes", zoho, json_data={"data": [payload]})
        result = (data.get("data") or [{}])[0]
        details = result.get("details", {})

        return {
            "success": result.get("status") == "success",
            "note_id": details.get("id"),
            "record_id": record_id,
            "module": module,
            "message": result.get("message", ""),
        }

    except Exception as e:
        logger.error("Failed to add note to Zoho CRM %s/%s: %s", module, record_id, e, exc_info=True)
        return {"success": False, "error": str(e)}
