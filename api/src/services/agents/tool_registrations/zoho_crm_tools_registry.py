"""
Zoho CRM Tools Registry

Registers all Zoho CRM tools with the ADK tool registry.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register_zoho_crm_tools(registry):
    """Register all Zoho CRM tools with the ADK tool registry."""
    from src.services.agents.internal_tools.zoho_crm_tools import (
        internal_add_zoho_crm_note,
        internal_create_zoho_crm_record,
        internal_get_zoho_crm_record,
        internal_list_zoho_crm_records,
        internal_search_zoho_crm_records,
        internal_update_zoho_crm_record,
    )

    async def search_wrapper(config: dict[str, Any] | None = None, **kwargs):
        rc = config.get("_runtime_context") if config else None
        return await internal_search_zoho_crm_records(
            module=kwargs.get("module", "Contacts"),
            query=kwargs.get("query", ""),
            max_results=kwargs.get("max_results", 20),
            runtime_context=rc,
            config=config,
        )

    async def get_wrapper(config: dict[str, Any] | None = None, **kwargs):
        rc = config.get("_runtime_context") if config else None
        return await internal_get_zoho_crm_record(
            module=kwargs.get("module"),
            record_id=kwargs.get("record_id"),
            runtime_context=rc,
            config=config,
        )

    async def list_wrapper(config: dict[str, Any] | None = None, **kwargs):
        rc = config.get("_runtime_context") if config else None
        return await internal_list_zoho_crm_records(
            module=kwargs.get("module", "Contacts"),
            max_results=kwargs.get("max_results", 20),
            sort_by=kwargs.get("sort_by"),
            sort_order=kwargs.get("sort_order", "desc"),
            runtime_context=rc,
            config=config,
        )

    async def create_wrapper(config: dict[str, Any] | None = None, **kwargs):
        rc = config.get("_runtime_context") if config else None
        return await internal_create_zoho_crm_record(
            module=kwargs.get("module"),
            fields=kwargs.get("fields", {}),
            runtime_context=rc,
            config=config,
        )

    async def update_wrapper(config: dict[str, Any] | None = None, **kwargs):
        rc = config.get("_runtime_context") if config else None
        return await internal_update_zoho_crm_record(
            module=kwargs.get("module"),
            record_id=kwargs.get("record_id"),
            fields=kwargs.get("fields", {}),
            runtime_context=rc,
            config=config,
        )

    async def note_wrapper(config: dict[str, Any] | None = None, **kwargs):
        rc = config.get("_runtime_context") if config else None
        return await internal_add_zoho_crm_note(
            module=kwargs.get("module"),
            record_id=kwargs.get("record_id"),
            note_title=kwargs.get("note_title", ""),
            note_content=kwargs.get("note_content", ""),
            runtime_context=rc,
            config=config,
        )

    registry.register_tool(
        name="internal_search_zoho_crm_records",
        description="Search Zoho CRM records by keyword across a module (Leads, Contacts, Accounts, Deals, etc.). Returns matching records with key fields.",
        parameters={
            "type": "object",
            "properties": {
                "module": {
                    "type": "string",
                    "description": "CRM module to search: Leads, Contacts, Accounts, Deals, Tasks, Calls, Events",
                },
                "query": {"type": "string", "description": "Search keyword (searches name, email, phone, etc.)"},
                "max_results": {"type": "integer", "description": "Maximum results (default: 20)", "default": 20},
            },
            "required": ["module", "query"],
        },
        function=search_wrapper,
    )

    registry.register_tool(
        name="internal_get_zoho_crm_record",
        description="Get a specific Zoho CRM record by ID, with all its field values.",
        parameters={
            "type": "object",
            "properties": {
                "module": {
                    "type": "string",
                    "description": "CRM module: Leads, Contacts, Accounts, Deals, Tasks, etc.",
                },
                "record_id": {"type": "string", "description": "The record's Zoho CRM ID"},
            },
            "required": ["module", "record_id"],
        },
        function=get_wrapper,
    )

    registry.register_tool(
        name="internal_list_zoho_crm_records",
        description="List records in a Zoho CRM module, sorted by modification time by default.",
        parameters={
            "type": "object",
            "properties": {
                "module": {
                    "type": "string",
                    "description": "CRM module: Leads, Contacts, Accounts, Deals, Tasks, Calls, Events",
                },
                "max_results": {"type": "integer", "description": "Maximum records (default: 20)", "default": 20},
                "sort_by": {"type": "string", "description": "Field to sort by (e.g., Modified_Time, Created_Time)"},
                "sort_order": {
                    "type": "string",
                    "description": "Sort order: asc or desc (default: desc)",
                    "default": "desc",
                },
            },
            "required": ["module"],
        },
        function=list_wrapper,
    )

    registry.register_tool(
        name="internal_create_zoho_crm_record",
        description=(
            "Create a new record in a Zoho CRM module. "
            "For Leads use fields like Last_Name, Email, Company. "
            "For Contacts use Last_Name, Email, Account_Name. "
            "For Deals use Deal_Name, Stage, Amount, Account_Name. "
            "For Accounts use Account_Name, Website, Phone."
        ),
        parameters={
            "type": "object",
            "properties": {
                "module": {"type": "string", "description": "CRM module: Leads, Contacts, Accounts, Deals, Tasks"},
                "fields": {
                    "type": "object",
                    "description": "Field name/value pairs. Leads require Last_Name. Deals require Deal_Name and Stage.",
                },
            },
            "required": ["module", "fields"],
        },
        function=create_wrapper,
        tool_category="action",
    )

    registry.register_tool(
        name="internal_update_zoho_crm_record",
        description="Update an existing Zoho CRM record's fields. Provide only the fields you want to change.",
        parameters={
            "type": "object",
            "properties": {
                "module": {"type": "string", "description": "CRM module: Leads, Contacts, Accounts, Deals, Tasks"},
                "record_id": {"type": "string", "description": "The record's Zoho CRM ID"},
                "fields": {
                    "type": "object",
                    "description": 'Field name/value pairs to update (e.g., {"Stage": "Closed Won", "Amount": 50000})',
                },
            },
            "required": ["module", "record_id", "fields"],
        },
        function=update_wrapper,
        tool_category="action",
    )

    registry.register_tool(
        name="internal_add_zoho_crm_note",
        description="Add a note to any Zoho CRM record (Lead, Contact, Deal, Account, etc.).",
        parameters={
            "type": "object",
            "properties": {
                "module": {"type": "string", "description": "Parent record's module: Leads, Contacts, Accounts, Deals"},
                "record_id": {"type": "string", "description": "Parent record's Zoho CRM ID"},
                "note_title": {"type": "string", "description": "Title of the note"},
                "note_content": {"type": "string", "description": "Body/content of the note"},
            },
            "required": ["module", "record_id", "note_title", "note_content"],
        },
        function=note_wrapper,
        tool_category="action",
    )

    logger.info("Registered 6 Zoho CRM tools")
