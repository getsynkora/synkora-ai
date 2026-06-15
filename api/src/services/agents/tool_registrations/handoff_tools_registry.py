"""Human Handoff tool registry."""

import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


async def _try_create_zendesk_ticket(runtime_context: Any, reason: str, conversation_summary: str) -> str | None:
    """
    Create a Zendesk ticket for the handoff.
    Returns a human-readable reference string on success, None on failure/not-configured.
    """
    try:
        from src.services.agents.credential_resolver import CredentialResolver
        from src.services.agents.internal_tools.zendesk_tools import _make_zendesk_request

        resolver = CredentialResolver(runtime_context)
        zd = await resolver.get_zendesk_credentials("internal_create_zendesk_ticket")
        if not zd:
            return None

        body = f"User requested human support via AI agent.\n\nReason: {reason}"
        if conversation_summary:
            body += f"\n\nConversation summary:\n{conversation_summary}"

        data = await _make_zendesk_request(
            "POST",
            "/tickets.json",
            zd,
            json_data={
                "ticket": {
                    "subject": f"Support Request: {reason[:80]}",
                    "comment": {"body": body},
                    "priority": "normal",
                    "tags": ["ai_handoff"],
                }
            },
        )
        ticket = data.get("ticket", {})
        ticket_id = ticket.get("id")
        if ticket_id:
            ticket_url = f"https://{zd['subdomain']}.zendesk.com/agent/tickets/{ticket_id}"
            logger.info("Created Zendesk ticket #%s for handoff", ticket_id)
            return f"Zendesk ticket #{ticket_id} ({ticket_url})"
    except Exception as exc:
        logger.warning("Zendesk ticket creation failed during handoff: %s", exc)
    return None


async def _try_create_zoho_lead(runtime_context: Any, reason: str, conversation_summary: str) -> str | None:
    """
    Create a Zoho CRM Lead for the handoff.
    Returns a human-readable reference string on success, None on failure/not-configured.
    """
    try:
        from src.services.agents.credential_resolver import CredentialResolver
        from src.services.agents.internal_tools.zoho_crm_tools import _make_zoho_request

        resolver = CredentialResolver(runtime_context)
        zoho = await resolver.get_zoho_crm_credentials("internal_create_zoho_crm_record")
        if not zoho:
            return None

        description = f"User requested human support via AI agent.\n\nReason: {reason}"
        if conversation_summary:
            description += f"\n\nConversation summary:\n{conversation_summary}"

        # Get user info from shared_state if available
        user_name = "Support Request"
        user_email = None
        if runtime_context and runtime_context.shared_state:
            user_name = runtime_context.shared_state.get("external_user_name") or user_name
            user_email = runtime_context.shared_state.get("external_user_email")

        fields: dict[str, Any] = {
            "Last_Name": user_name,
            "Lead_Source": "AI Agent Handoff",
            "Description": description,
        }
        if user_email:
            fields["Email"] = user_email

        data = await _make_zoho_request("POST", "/Leads", zoho, json_data={"data": [fields]})
        result = (data.get("data") or [{}])[0]
        details = result.get("details", {})
        record_id = details.get("id")
        if record_id and result.get("status") == "success":
            logger.info("Created Zoho CRM Lead %s for handoff", record_id)
            return f"Zoho CRM lead #{record_id}"
    except Exception as exc:
        logger.warning("Zoho CRM lead creation failed during handoff: %s", exc)
    return None


async def handoff_to_human(reason: str, config: dict[str, Any] | None = None) -> str:
    """
    Transfer the conversation to a human support agent.

    Sets conversation.handoff_status = "active" in the DB and signals the
    streaming layer to emit a handoff_initiated SSE event.
    Also creates a Zendesk ticket and/or Zoho CRM lead if those integrations
    are configured for the agent.
    """
    config = config or {}
    runtime_context = config.get("_runtime_context")

    conversation_id = None
    conversation_summary = ""
    if runtime_context and runtime_context.shared_state:
        conversation_id = runtime_context.shared_state.get("conversation_id")

    if conversation_id:
        try:
            from sqlalchemy import select

            from src.core.database import get_async_session_factory
            from src.models.conversation import Conversation
            from src.models.message import Message

            session_factory = get_async_session_factory()
            async with session_factory() as db:
                result = await db.execute(select(Conversation).filter(Conversation.id == conversation_id))
                conv = result.scalar_one_or_none()
                if conv:
                    if conv.handoff_status == "active":
                        return "A support agent is already connected to this conversation."
                    conv.handoff_status = "active"
                    conv.handoff_at = datetime.now(UTC)
                    conv.handoff_summary = reason
                    await db.commit()
                    logger.info("Handoff activated for conversation %s", conversation_id)

                # Build a brief summary from the last few messages for the ticket body
                msgs_result = await db.execute(
                    select(Message)
                    .filter(Message.conversation_id == conversation_id)
                    .order_by(Message.created_at.desc())
                    .limit(6)
                )
                recent_msgs = list(reversed(msgs_result.scalars().all()))
                if recent_msgs:
                    lines = []
                    for m in recent_msgs:
                        role_label = {"user": "User", "assistant": "Agent", "operator": "Operator"}.get(
                            m.role.lower() if hasattr(m.role, "lower") else str(m.role).lower(), "Unknown"
                        )
                        snippet = (m.content or "")[:300]
                        lines.append(f"{role_label}: {snippet}")
                    conversation_summary = "\n".join(lines)
        except Exception as exc:
            logger.error("Failed to update conversation handoff status: %s", exc, exc_info=True)

    # Create external tickets if the agent has those integrations configured
    ticket_refs: list[str] = []
    if runtime_context:
        zd_ref = await _try_create_zendesk_ticket(runtime_context, reason, conversation_summary)
        if zd_ref:
            ticket_refs.append(zd_ref)

        zoho_ref = await _try_create_zoho_lead(runtime_context, reason, conversation_summary)
        if zoho_ref:
            ticket_refs.append(zoho_ref)

    # Signal chat_stream_service to emit handoff_initiated SSE
    if runtime_context and runtime_context.shared_state is not None:
        runtime_context.shared_state["handoff_initiated"] = {
            "reason": reason,
            "conversation_id": str(conversation_id) if conversation_id else None,
            "ticket_refs": ticket_refs,
        }

    if ticket_refs:
        refs_text = " and ".join(ticket_refs)
        return (
            f"I've connected you with a support agent. "
            f"Your request has been logged as {refs_text}. "
            f"They'll review your conversation and respond shortly. "
            f"You can continue typing if you have additional details to share."
        )

    return (
        "I've connected you with a support agent. "
        "They'll review your conversation and respond shortly. "
        "You can continue typing if you have additional details to share."
    )


def register_handoff_tools(registry) -> None:
    """Register human handoff tools."""
    registry.register_tool(
        name="handoff_to_human",
        description=(
            "Transfer the user to a human support agent. "
            "Call this tool whenever the user asks to speak to a human, requests live support, "
            "wants to talk to a person, or asks to escalate to a human agent. "
            "Also call this when handling sensitive requests like refunds, complaints, or legal matters "
            "that require human judgment. "
            "Provide a brief reason describing why the handoff is needed."
        ),
        parameters={
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Brief reason for the handoff (e.g., 'refund request', 'billing dispute', 'user requested human agent')",
                }
            },
            "required": ["reason"],
        },
        function=handoff_to_human,
    )
