"""
Zendesk Tools Registry

Registers all Zendesk-related tools with the ADK tool registry.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register_zendesk_tools(registry):
    """Register all Zendesk tools with the ADK tool registry."""
    from src.services.agents.internal_tools.zendesk_tools import (
        internal_add_zendesk_comment,
        internal_create_zendesk_ticket,
        internal_get_zendesk_ticket,
        internal_get_zendesk_user,
        internal_list_zendesk_tickets,
        internal_search_zendesk_tickets,
        internal_update_zendesk_ticket,
    )

    async def search_wrapper(config: dict[str, Any] | None = None, **kwargs):
        rc = config.get("_runtime_context") if config else None
        return await internal_search_zendesk_tickets(
            query=kwargs.get("query", ""),
            status=kwargs.get("status"),
            priority=kwargs.get("priority"),
            max_results=kwargs.get("max_results", 25),
            runtime_context=rc,
            config=config,
        )

    async def get_ticket_wrapper(config: dict[str, Any] | None = None, **kwargs):
        rc = config.get("_runtime_context") if config else None
        return await internal_get_zendesk_ticket(
            ticket_id=kwargs.get("ticket_id"),
            include_comments=kwargs.get("include_comments", True),
            runtime_context=rc,
            config=config,
        )

    async def list_wrapper(config: dict[str, Any] | None = None, **kwargs):
        rc = config.get("_runtime_context") if config else None
        return await internal_list_zendesk_tickets(
            status=kwargs.get("status"),
            assignee_id=kwargs.get("assignee_id"),
            max_results=kwargs.get("max_results", 25),
            runtime_context=rc,
            config=config,
        )

    async def create_wrapper(config: dict[str, Any] | None = None, **kwargs):
        rc = config.get("_runtime_context") if config else None
        return await internal_create_zendesk_ticket(
            subject=kwargs.get("subject"),
            description=kwargs.get("description"),
            priority=kwargs.get("priority", "normal"),
            ticket_type=kwargs.get("ticket_type"),
            tags=kwargs.get("tags"),
            requester_email=kwargs.get("requester_email"),
            assignee_id=kwargs.get("assignee_id"),
            runtime_context=rc,
            config=config,
        )

    async def update_wrapper(config: dict[str, Any] | None = None, **kwargs):
        rc = config.get("_runtime_context") if config else None
        return await internal_update_zendesk_ticket(
            ticket_id=kwargs.get("ticket_id"),
            status=kwargs.get("status"),
            priority=kwargs.get("priority"),
            subject=kwargs.get("subject"),
            assignee_id=kwargs.get("assignee_id"),
            tags=kwargs.get("tags"),
            runtime_context=rc,
            config=config,
        )

    async def comment_wrapper(config: dict[str, Any] | None = None, **kwargs):
        rc = config.get("_runtime_context") if config else None
        return await internal_add_zendesk_comment(
            ticket_id=kwargs.get("ticket_id"),
            body=kwargs.get("body"),
            public=kwargs.get("public", True),
            runtime_context=rc,
            config=config,
        )

    async def get_user_wrapper(config: dict[str, Any] | None = None, **kwargs):
        rc = config.get("_runtime_context") if config else None
        return await internal_get_zendesk_user(
            user_id=kwargs.get("user_id"),
            runtime_context=rc,
            config=config,
        )

    registry.register_tool(
        name="internal_search_zendesk_tickets",
        description="Search Zendesk support tickets by keyword. Optionally filter by status (new/open/pending/hold/solved/closed) or priority (low/normal/high/urgent). Returns ticket IDs, subjects, status, and URLs.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search terms (e.g., 'login error', 'billing question')"},
                "status": {
                    "type": "string",
                    "description": "Filter by status: new, open, pending, hold, solved, closed",
                },
                "priority": {"type": "string", "description": "Filter by priority: low, normal, high, urgent"},
                "max_results": {
                    "type": "integer",
                    "description": "Maximum results to return (default: 25)",
                    "default": 25,
                },
            },
            "required": ["query"],
        },
        function=search_wrapper,
    )

    registry.register_tool(
        name="internal_get_zendesk_ticket",
        description="Get full details of a Zendesk ticket by ID, including all comments and conversation history.",
        parameters={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "integer", "description": "Zendesk ticket ID"},
                "include_comments": {
                    "type": "boolean",
                    "description": "Include ticket comments (default: true)",
                    "default": True,
                },
            },
            "required": ["ticket_id"],
        },
        function=get_ticket_wrapper,
    )

    registry.register_tool(
        name="internal_list_zendesk_tickets",
        description="List recent Zendesk tickets, optionally filtered by status or assignee. Returns tickets sorted by last update.",
        parameters={
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filter by status: new, open, pending, hold, solved, closed",
                },
                "assignee_id": {"type": "integer", "description": "Filter by assignee's Zendesk user ID"},
                "max_results": {"type": "integer", "description": "Maximum results (default: 25)", "default": 25},
            },
            "required": [],
        },
        function=list_wrapper,
    )

    registry.register_tool(
        name="internal_create_zendesk_ticket",
        description="Create a new Zendesk support ticket with subject, description, priority, and optional tags.",
        parameters={
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "Ticket subject/title"},
                "description": {"type": "string", "description": "Ticket description (body of first comment)"},
                "priority": {
                    "type": "string",
                    "description": "Priority: low, normal, high, urgent (default: normal)",
                    "default": "normal",
                },
                "ticket_type": {"type": "string", "description": "Type: problem, incident, question, task"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags to apply to the ticket"},
                "requester_email": {"type": "string", "description": "Email of the requester"},
                "assignee_id": {"type": "integer", "description": "Zendesk user ID to assign the ticket to"},
            },
            "required": ["subject", "description"],
        },
        function=create_wrapper,
        tool_category="action",
    )

    registry.register_tool(
        name="internal_update_zendesk_ticket",
        description="Update a Zendesk ticket's status, priority, subject, assignee, or tags.",
        parameters={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "integer", "description": "Zendesk ticket ID"},
                "status": {"type": "string", "description": "New status: new, open, pending, hold, solved, closed"},
                "priority": {"type": "string", "description": "New priority: low, normal, high, urgent"},
                "subject": {"type": "string", "description": "New subject"},
                "assignee_id": {"type": "integer", "description": "User ID to assign the ticket to"},
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Replace existing tags with these",
                },
            },
            "required": ["ticket_id"],
        },
        function=update_wrapper,
        tool_category="action",
    )

    registry.register_tool(
        name="internal_add_zendesk_comment",
        description="Add a public reply or internal note to a Zendesk ticket.",
        parameters={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "integer", "description": "Zendesk ticket ID"},
                "body": {"type": "string", "description": "Comment text"},
                "public": {
                    "type": "boolean",
                    "description": "True for public reply, False for internal note (default: true)",
                    "default": True,
                },
            },
            "required": ["ticket_id", "body"],
        },
        function=comment_wrapper,
        tool_category="action",
    )

    registry.register_tool(
        name="internal_get_zendesk_user",
        description="Get Zendesk user details by user ID, including name, email, and role.",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {"type": "integer", "description": "Zendesk user ID"},
            },
            "required": ["user_id"],
        },
        function=get_user_wrapper,
    )

    logger.info("Registered 7 Zendesk tools")
