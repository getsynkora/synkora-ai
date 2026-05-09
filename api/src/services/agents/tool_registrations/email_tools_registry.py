"""
Email Tools Registry

Registers all email-related tools with the ADK tool registry.
This modular approach keeps tool registration organized and maintainable.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register_email_tools(registry):
    """
    Register all email tools with the ADK tool registry.

    Args:
        registry: ADKToolRegistry instance
    """
    from src.services.agents.internal_tools.email_tools import (
        internal_send_bulk_emails,
        internal_send_email,
        internal_test_email_connection,
    )

    def _resolve_redacted_email(value: str, runtime_context, field_name: str = "recipient_email") -> str:
        """
        Resolve [EMAIL_REDACTED] placeholder from task_config in shared_state.

        Args:
            value: The potentially redacted email value
            runtime_context: Runtime context with shared_state
            field_name: The field name to look up in task_config (default: recipient_email)
        """
        if not value or "[EMAIL_REDACTED]" not in str(value):
            return value

        if not runtime_context or not runtime_context.shared_state:
            logger.warning("📧 Cannot resolve [EMAIL_REDACTED] - no shared_state")
            return value

        task_config = runtime_context.shared_state.get("task_config", {})
        resolved = task_config.get(field_name)

        if resolved:
            logger.info(f"📧 Resolved [EMAIL_REDACTED] from task_config.{field_name} -> {resolved}")
            return resolved

        logger.warning(f"📧 Could not resolve [EMAIL_REDACTED] - {field_name} not in task_config")
        return value

    async def _resolve_body(body: str | None) -> tuple[str | None, bool, list | None]:
        """
        If body is a Redis key that resolves to stored content (e.g. a newsletter
        render key), return (html_content, is_html=True, attachments).
        Otherwise return (body, False, None) unchanged.
        """
        if not body:
            return body, False, None
        try:
            import json as _json

            from src.config.redis import get_redis_async

            redis = get_redis_async()
            raw = await redis.get(body)
            if not raw:
                return body, False, None
            payload = _json.loads(raw)
            html_content = payload.get("html")
            if not html_content:
                return body, False, None
            logger.info(f"📧 Resolved body from Redis key ({len(html_content)} bytes)")
            await redis.delete(body)

            # Fetch PDF and image from S3 as attachments
            attachments = []
            for s3_key, filename, content_type in [
                (payload.get("pdf_s3_key"), "newsletter.pdf", "application/pdf"),
                (payload.get("image_s3_key"), "newsletter-preview.jpg", "image/jpeg"),
            ]:
                if not s3_key:
                    continue
                try:
                    from src.services.storage.s3_storage import get_s3_storage

                    file_bytes = get_s3_storage().download_file(s3_key)
                    attachments.append({"filename": filename, "content": file_bytes, "content_type": content_type})
                    logger.info(f"📧 Attached {filename} from S3 ({len(file_bytes)} bytes)")
                except Exception as exc:
                    logger.warning(f"📧 Could not attach {filename}: {exc}")

            return html_content, True, attachments or None
        except Exception:
            return body, False, None

    # Email tools - create wrappers that inject runtime_context
    async def internal_send_email_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        to_email = kwargs.get("to_email")
        body = kwargs.get("body")
        html = kwargs.get("html", False)

        logger.info(f"📧 [send_email] Called with to_email={to_email!r}, subject={kwargs.get('subject')!r}")

        # Resolve [EMAIL_REDACTED] placeholder from shared_state
        to_email = _resolve_redacted_email(to_email, runtime_context)

        # Resolve body: if it's a Redis key, fetch stored HTML + attachments
        resolved_body, is_stored_html, attachments = await _resolve_body(body)
        if is_stored_html:
            body, html = resolved_body, True
            # Newsletter HTML is already fully designed — skip the branding wrapper
            config = {**(config or {}), "apply_branding": False, "attachments": attachments}

        return await internal_send_email(
            to_email=to_email,
            subject=kwargs.get("subject"),
            body=body,
            html=html,
            from_email=kwargs.get("from_email"),
            from_name=kwargs.get("from_name"),
            cc=kwargs.get("cc"),
            bcc=kwargs.get("bcc"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_send_bulk_emails_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_send_bulk_emails(
            recipients=kwargs.get("recipients"),
            subject=kwargs.get("subject"),
            body=kwargs.get("body"),
            html=kwargs.get("html", False),
            from_email=kwargs.get("from_email"),
            from_name=kwargs.get("from_name"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_test_email_connection_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_test_email_connection(runtime_context=runtime_context, config=config)

    # Register all email tools
    registry.register_tool(
        name="internal_send_email",
        description="Send an email to a recipient using the configured email integration (SMTP, SendGrid, Mailgun). Use this when you need to send notifications, updates, or any communication via email. Supports both plain text and HTML content.",
        parameters={
            "type": "object",
            "properties": {
                "to_email": {"type": "string", "description": "Recipient email address (e.g., 'user@example.com')"},
                "subject": {"type": "string", "description": "Email subject line"},
                "body": {
                    "type": "string",
                    "description": "Email body content (plain text or HTML based on html parameter)",
                },
                "html": {
                    "type": "boolean",
                    "description": "Whether the body contains HTML content (default: false for plain text)",
                    "default": False,
                },
                "from_email": {
                    "type": "string",
                    "description": "Optional sender email address (uses integration config default if not provided)",
                },
                "from_name": {"type": "string", "description": "Optional sender name to display"},
                "cc": {"type": "string", "description": "Optional carbon copy recipients (comma-separated)"},
                "bcc": {"type": "string", "description": "Optional blind carbon copy recipients (comma-separated)"},
            },
            "required": ["to_email", "subject", "body"],
        },
        function=internal_send_email_wrapper,
    )

    registry.register_tool(
        name="internal_send_bulk_emails",
        description="Send the same email to multiple recipients at once. Useful for notifications, announcements, or newsletters. Maximum 100 recipients per call. Each email is sent individually to maintain privacy.",
        parameters={
            "type": "object",
            "properties": {
                "recipients": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of recipient email addresses (max 100)",
                },
                "subject": {"type": "string", "description": "Email subject line"},
                "body": {"type": "string", "description": "Email body content"},
                "html": {"type": "boolean", "description": "Whether the body contains HTML content", "default": False},
                "from_email": {"type": "string", "description": "Optional sender email address"},
                "from_name": {"type": "string", "description": "Optional sender name"},
            },
            "required": ["recipients", "subject", "body"],
        },
        function=internal_send_bulk_emails_wrapper,
    )

    registry.register_tool(
        name="internal_test_email_connection",
        description="Test the email configuration to verify that the email integration is properly configured and can connect to the email provider. Use this to troubleshoot email issues before attempting to send actual emails.",
        parameters={"type": "object", "properties": {}, "required": []},
        function=internal_test_email_connection_wrapper,
    )

    logger.info("Registered 3 email tools")
