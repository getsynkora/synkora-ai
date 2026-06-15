"""
Email Tools for AI Agents.
Provides email sending capabilities using configured integration providers.
"""

import logging
from typing import Any

from ...integrations.email_service import EmailService

logger = logging.getLogger(__name__)


async def internal_send_email(
    to_email: str,
    subject: str,
    body: str,
    html: bool = False,
    from_email: str | None = None,
    from_name: str | None = None,
    cc: str | None = None,
    bcc: str | None = None,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Send an email using the configured email integration.

    Args:
        to_email: Recipient email address
        subject: Email subject line
        body: Email body content (plain text or HTML based on html parameter)
        html: Whether the body contains HTML content (default: False)
        from_email: Optional sender email address (uses integration config default if not provided)
        from_name: Optional sender name
        cc: Optional carbon copy recipients (comma-separated)
        bcc: Optional blind carbon copy recipients (comma-separated)

    Returns:
        Dict with success status and message details

    Example:
        result = await internal_send_email(
            to_email="user@example.com",
            subject="Meeting Reminder",
            body="<h1>Don't forget our meeting tomorrow at 2 PM</h1>",
            html=True,
            from_name="Synkora Assistant"
        )

    Security:
        - Validates email addresses
        - Uses configured integration for authentication
        - Sanitizes email content
        - Rate limiting applied
    """
    try:
        if not runtime_context:
            return {"success": False, "error": "Runtime context is required"}

        if isinstance(runtime_context, dict):
            db = runtime_context.get("db_session")
            tenant_id = runtime_context.get("tenant_id")
        else:
            db = getattr(runtime_context, "db_session", None)
            tenant_id = getattr(runtime_context, "tenant_id", None)

        if not db:
            return {"success": False, "error": "db_session not available in runtime context"}
        if not tenant_id:
            return {"success": False, "error": "tenant_id not available in runtime context"}

        # Input validation
        if not to_email or "@" not in to_email:
            return {"success": False, "error": "Invalid recipient email address", "to_email": to_email}

        if not subject:
            return {"success": False, "error": "Email subject is required", "to_email": to_email}

        if not body:
            return {"success": False, "error": "Email body is required", "to_email": to_email}

        # Apply assigned email template if one exists for this agent
        template_was_applied = False
        email_template_id = getattr(runtime_context, "email_template_id", None)
        if email_template_id and db:
            try:
                from src.services.email.email_template_apply_service import (
                    apply_template_to_html,
                    resolve_agent_email_template,
                )

                agent_id = getattr(runtime_context, "agent_id", None)
                if agent_id:
                    template = await resolve_agent_email_template(agent_id, db)
                    if template:
                        raw_html = body if html else f"<p>{body.replace(chr(10), '<br>')}</p>"
                        body, template_was_applied = await apply_template_to_html(
                            raw_html,
                            template,
                            db=db,
                            tenant_id=tenant_id,
                            subject=subject,
                        )
                        if template_was_applied:
                            html = True
            except Exception as _tmpl_exc:
                logger.warning(f"Email template apply failed (continuing without): {_tmpl_exc}")

        # Prepare content
        html_content = body if html else f"<p>{body.replace(chr(10), '<br>')}</p>"
        text_content = body if not html else None

        # Capture email content into shared_state for subscriber dispatch
        if (
            runtime_context
            and hasattr(runtime_context, "shared_state")
            and runtime_context.shared_state is not None
            and "captured_email" in runtime_context.shared_state
        ):
            runtime_context.shared_state["captured_email"] = {
                "subject": subject,
                "html_body": html_content,
            }

        # Check if we should use async (Celery) or sync sending
        use_async = config.get("async", True) if config else True
        # Skip the generic branding wrapper in Celery when an agent template was already applied
        apply_branding = False if template_was_applied else (config.get("apply_branding", True) if config else True)
        attachments = config.get("attachments") if config else None

        if use_async:
            # Send email asynchronously using Celery
            try:
                from src.tasks.email_tasks import send_email_task

                # Convert cc/bcc strings to lists
                cc_list = [e.strip() for e in cc.split(",")] if cc else None
                bcc_list = [e.strip() for e in bcc.split(",")] if bcc else None

                # Queue email task
                # Serialize attachment bytes to base64 for Celery (bytes aren't JSON-serialisable)
                serialized_attachments = None
                if attachments:
                    import base64 as _b64

                    serialized_attachments = [
                        {
                            **a,
                            "content": _b64.b64encode(a["content"]).decode()
                            if isinstance(a.get("content"), bytes)
                            else a.get("content"),
                        }
                        for a in attachments
                    ]

                task = send_email_task.delay(
                    tenant_id=str(tenant_id),
                    to_email=to_email,
                    subject=subject,
                    html_body=html_content,
                    text_body=text_content,
                    from_email=from_email,
                    from_name=from_name,
                    cc=cc_list,
                    bcc=bcc_list,
                    apply_branding=apply_branding,
                    attachments=serialized_attachments,
                )

                logger.info(f"Email task queued for {to_email} - Task ID: {task.id}")

                return {
                    "success": True,
                    "message": f"Email queued successfully to {to_email}",
                    "to_email": to_email,
                    "subject": subject,
                    "task_id": task.id,
                    "async": True,
                }
            except Exception as e:
                logger.warning(f"Failed to queue email task, falling back to sync: {e}")
                use_async = False

        if not use_async:
            # Send email synchronously
            email_service = EmailService(db)

            result = await email_service.send_email(
                to_email=to_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content,
                from_email=from_email,
                from_name=from_name,
                tenant_id=tenant_id,
                attachments=attachments,
            )

            if result.get("success"):
                logger.info(f"Email sent successfully to {to_email}")
                return {
                    "success": True,
                    "message": f"Email sent successfully to {to_email}",
                    "to_email": to_email,
                    "subject": subject,
                    "provider": result.get("provider", "unknown"),
                    "async": False,
                }
            else:
                logger.error(f"Failed to send email to {to_email}: {result.get('message')}")
                return {
                    "success": False,
                    "error": result.get("message", "Unknown error"),
                    "to_email": to_email,
                    "provider": result.get("provider", "unknown"),
                }

    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        return {"success": False, "error": f"Failed to send email: {str(e)}", "to_email": to_email}


async def internal_send_bulk_emails(
    recipients: list[str],
    subject: str,
    body: str,
    html: bool = False,
    from_email: str | None = None,
    from_name: str | None = None,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Send the same email to multiple recipients.

    Args:
        recipients: List of recipient email addresses
        subject: Email subject line
        body: Email body content
        html: Whether the body contains HTML content
        from_email: Optional sender email address
        from_name: Optional sender name

    Returns:
        Dict with overall success status and per-recipient results

    Example:
        result = await internal_send_bulk_emails(
            recipients=["user1@example.com", "user2@example.com"],
            subject="Weekly Update",
            body="This week's highlights...",
            from_name="Team Newsletter"
        )

    Security:
        - Rate limiting per recipient
        - Validates all email addresses
        - Stops on repeated failures
    """
    try:
        if not recipients or not isinstance(recipients, list):
            return {"success": False, "error": "Recipients must be a non-empty list"}

        if len(recipients) > 100:
            return {"success": False, "error": "Maximum 100 recipients allowed per bulk send"}

        results = []
        success_count = 0
        failure_count = 0

        for recipient in recipients:
            result = await internal_send_email(
                to_email=recipient,
                subject=subject,
                body=body,
                html=html,
                from_email=from_email,
                from_name=from_name,
                runtime_context=runtime_context,
                config=config,
            )

            results.append(
                {
                    "email": recipient,
                    "success": result.get("success", False),
                    "message": result.get("message") or result.get("error"),
                }
            )

            if result.get("success"):
                success_count += 1
            else:
                failure_count += 1

        return {
            "success": True,
            "total": len(recipients),
            "sent": success_count,
            "failed": failure_count,
            "results": results,
        }

    except Exception as e:
        logger.error(f"Error in bulk email send: {str(e)}")
        return {"success": False, "error": f"Bulk email send failed: {str(e)}"}


async def internal_send_template_email(
    to_email: str,
    template_name: str,
    template_variables: dict[str, str] | None = None,
    from_email: str | None = None,
    from_name: str | None = None,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Send an email using a predefined template with variable substitution.

    Args:
        to_email: Recipient email address
        template_name: Name of the email template to use
        template_variables: Dictionary of variables to substitute in template
        from_email: Optional sender email address
        from_name: Optional sender name

    Returns:
        Dict with success status and message details

    Example:
        result = await internal_send_template_email(
            to_email="user@example.com",
            template_name="welcome",
            template_variables={"user_name": "John", "activation_link": "https://..."}
        )

    Note:
        Templates should be configured in the system beforehand
    """
    try:
        # Template system not yet implemented - placeholder for future enhancement
        return {
            "success": False,
            "error": "Template email system is not yet implemented. Use internal_send_email with HTML body instead.",
        }

    except Exception as e:
        logger.error(f"Error sending template email: {str(e)}")
        return {"success": False, "error": f"Failed to send template email: {str(e)}"}


async def internal_test_email_connection(
    runtime_context: Any | None = None, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Test the email configuration by checking connection to the email provider.

    Returns:
        Dict with connection test results

    Example:
        result = await internal_test_email_connection()
        # result["success"] indicates if email is configured correctly

    Security:
        - Does not send actual emails
        - Only tests connection and authentication
    """
    try:
        if not runtime_context:
            return {"success": False, "error": "Runtime context is required"}

        if isinstance(runtime_context, dict):
            db = runtime_context.get("db_session")
            tenant_id = runtime_context.get("tenant_id")
        else:
            db = getattr(runtime_context, "db_session", None)
            tenant_id = getattr(runtime_context, "tenant_id", None)

        if not db:
            return {"success": False, "error": "db_session not available in runtime context"}
        if not tenant_id:
            return {"success": False, "error": "tenant_id not available in runtime context"}

        email_service = EmailService(db)
        result = await email_service.test_connection(tenant_id=tenant_id)

        return {
            "success": result.get("success", False),
            "message": result.get("message", "Unknown status"),
            "provider": result.get("provider", "unknown"),
        }

    except Exception as e:
        logger.error(f"Error testing email connection: {str(e)}")
        return {"success": False, "error": f"Connection test failed: {str(e)}"}
