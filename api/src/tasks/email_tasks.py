"""
Celery tasks for email operations.
"""

import logging
import uuid
from typing import Any

from src.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="send_email_task", bind=True, max_retries=3, default_retry_delay=60)
def send_email_task(
    self,
    tenant_id: str,
    to_email: str,
    subject: str,
    html_body: str | None = None,
    text_body: str | None = None,
    from_email: str | None = None,
    from_name: str | None = None,
    reply_to: str | None = None,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    attachments: list[dict[str, Any]] | None = None,
    apply_branding: bool = True,
) -> dict[str, Any]:
    """
    Send a single email asynchronously.

    Args:
        tenant_id: Tenant ID for email configuration
        to_email: Recipient email address
        subject: Email subject
        html_body: HTML email body
        text_body: Plain text email body
        from_email: Sender email address (optional)
        from_name: Sender name (optional)
        reply_to: Reply-to email address (optional)
        cc: CC recipients (optional)
        bcc: BCC recipients (optional)
        attachments: Email attachments (optional)
        apply_branding: Whether to wrap content in branded template (default: True)

    Returns:
        dict: Result of email sending operation
    """
    import asyncio

    async def _send_email():
        from src.core.database import create_celery_async_session
        from src.services.email import EmailTemplateService
        from src.services.integrations.email_service import EmailService

        async_session_factory = create_celery_async_session()
        async with async_session_factory() as db:
            try:
                logger.info(f"📧 Sending email to {to_email} - Subject: {subject}")

                # Apply branded template if enabled
                final_html = html_body
                if apply_branding and html_body:
                    template_service = EmailTemplateService(db)
                    final_html = await template_service.wrap_content(
                        content=html_body,
                        subject=subject,
                        tenant_id=uuid.UUID(tenant_id) if tenant_id else None,
                    )

                # Deserialise base64-encoded attachment content back to bytes
                decoded_attachments = None
                if attachments:
                    import base64 as _b64

                    decoded_attachments = [
                        {
                            **a,
                            "content": _b64.b64decode(a["content"])
                            if isinstance(a.get("content"), str)
                            else a.get("content"),
                        }
                        for a in attachments
                    ]

                email_service = EmailService(db)

                result = await email_service.send_email(
                    to_email=to_email,
                    subject=subject,
                    html_content=final_html,
                    text_content=text_body,
                    from_email=from_email,
                    from_name=from_name,
                    tenant_id=uuid.UUID(tenant_id) if tenant_id else None,
                    attachments=decoded_attachments,
                )

                if result.get("success"):
                    logger.info(f"✅ Email sent successfully to {to_email}")
                else:
                    logger.error(f"❌ Failed to send email to {to_email}: {result.get('error')}")

                return result
            except Exception:
                await db.rollback()
                raise

    try:
        return asyncio.run(_send_email())
    except Exception as exc:
        logger.error(f"❌ Error sending email to {to_email}: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))


@celery_app.task(name="send_verification_email_task", bind=True, max_retries=3, default_retry_delay=30)
def send_verification_email_task(self, account_id: str, base_url: str = "https://synkora.ai") -> dict[str, Any]:
    """
    Send email verification email asynchronously.

    Args:
        account_id: Account UUID
        base_url: Base URL for verification link

    Returns:
        dict: Result of email sending operation
    """
    import asyncio

    async def _send_verification_email():
        from src.core.database import create_celery_async_session
        from src.services.auth_service import AuthService

        async_session_factory = create_celery_async_session()
        async with async_session_factory() as db:
            try:
                logger.info(f"📧 Sending verification email for account {account_id}")
                result = await AuthService.send_verification_email(
                    db=db, account_id=uuid.UUID(account_id), base_url=base_url
                )
                if result.get("success"):
                    logger.info(f"✅ Verification email sent for account {account_id}")
                else:
                    logger.error(f"❌ Failed to send verification email: {result.get('error')}")
                return result
            except Exception:
                await db.rollback()
                raise

    try:
        return asyncio.run(_send_verification_email())
    except Exception as exc:
        logger.error(f"❌ Error sending verification email for account {account_id}: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=30 * (2**self.request.retries))


@celery_app.task(name="send_welcome_email_task", bind=True, max_retries=3, default_retry_delay=30)
def send_welcome_email_task(self, account_id: str, base_url: str = "https://synkora.ai") -> dict[str, Any]:
    """
    Send welcome email after email verification.

    Args:
        account_id: Account UUID
        base_url: Base URL for dashboard link

    Returns:
        dict: Result of email sending operation
    """
    import asyncio

    async def _send_welcome_email():
        from sqlalchemy import select

        from src.core.database import create_celery_async_session
        from src.models.tenant import Account, TenantAccountJoin
        from src.services.integrations.email_service import EmailService

        async_session_factory = create_celery_async_session()
        async with async_session_factory() as db:
            try:
                logger.info(f"📧 Sending welcome email for account {account_id}")

                result = await db.execute(select(Account).filter_by(id=uuid.UUID(account_id)))
                account = result.scalar_one_or_none()

                if not account:
                    logger.error(f"Account {account_id} not found")
                    return {"success": False, "error": "Account not found"}

                # Get tenant_id
                tenant_id = None
                membership_result = await db.execute(select(TenantAccountJoin).filter_by(account_id=account.id))
                membership = membership_result.scalar_one_or_none()
                if membership:
                    tenant_id = membership.tenant_id

                email_service = EmailService(db)
                result = await email_service.send_welcome_email(
                    to_email=account.email,
                    user_name=account.name,
                    tenant_id=tenant_id,
                    base_url=base_url,
                )

                if result.get("success"):
                    logger.info(f"✅ Welcome email sent for account {account_id}")
                else:
                    logger.error(f"❌ Failed to send welcome email: {result.get('error')}")

                return result
            except Exception:
                await db.rollback()
                raise

    try:
        return asyncio.run(_send_welcome_email())
    except Exception as exc:
        logger.error(f"❌ Error sending welcome email for account {account_id}: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=30 * (2**self.request.retries))


@celery_app.task(name="send_password_reset_email_task", bind=True, max_retries=3, default_retry_delay=30)
def send_password_reset_email_task(
    self, email: str, reset_token: str, base_url: str = "https://synkora.ai"
) -> dict[str, Any]:
    """
    Send password reset email asynchronously.

    Args:
        email: User email address
        reset_token: Password reset token
        base_url: Base URL for reset link

    Returns:
        dict: Result of email sending operation
    """
    import asyncio

    async def _send_password_reset_email():
        from sqlalchemy import select

        from src.core.database import create_celery_async_session
        from src.models.tenant import Account
        from src.services.integrations.email_service import EmailService

        async_session_factory = create_celery_async_session()
        async with async_session_factory() as db:
            try:
                logger.info(f"📧 Sending password reset email to {email}")

                result = await db.execute(select(Account).filter(Account.email == email))
                account = result.scalar_one_or_none()
                if not account:
                    logger.error(f"Account not found for email {email}")
                    return {"success": False, "error": "Account not found"}

                email_service = EmailService(db)

                result = await email_service.send_password_reset_email(
                    to_email=email, reset_token=reset_token, base_url=base_url
                )

                if result.get("success"):
                    logger.info(f"✅ Password reset email sent to {email}")
                else:
                    logger.error(f"❌ Failed to send password reset email: {result.get('error')}")

                return result
            except Exception:
                await db.rollback()
                raise

    try:
        return asyncio.run(_send_password_reset_email())
    except Exception as exc:
        logger.error(f"❌ Error sending password reset email to {email}: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=30 * (2**self.request.retries))


@celery_app.task(name="send_bulk_emails_task", bind=True)
def send_bulk_emails_task(
    self,
    tenant_id: str,
    recipients: list[dict[str, Any]],
    subject: str,
    html_body: str | None = None,
    text_body: str | None = None,
    from_email: str | None = None,
    from_name: str | None = None,
) -> dict[str, Any]:
    """
    Send bulk emails asynchronously.

    Args:
        tenant_id: Tenant ID for email configuration
        recipients: List of recipient dictionaries with 'email' and optional 'name'
        subject: Email subject (can include {name} placeholder)
        html_body: HTML email body (can include {name} placeholder)
        text_body: Plain text email body (can include {name} placeholder)
        from_email: Sender email address (optional)
        from_name: Sender name (optional)

    Returns:
        dict: Summary of bulk email operation
    """
    logger.info(f"📧 Starting bulk email send to {len(recipients)} recipients")

    results = {"total": len(recipients), "sent": 0, "failed": 0, "errors": []}

    for recipient in recipients:
        try:
            # Personalize subject and body
            recipient_email = recipient.get("email")
            recipient_name = recipient.get("name", "")

            personalized_subject = subject.replace("{name}", recipient_name)
            personalized_html = html_body.replace("{name}", recipient_name) if html_body else None
            personalized_text = text_body.replace("{name}", recipient_name) if text_body else None

            # Queue individual email task
            send_email_task.delay(
                tenant_id=tenant_id,
                to_email=recipient_email,
                subject=personalized_subject,
                html_body=personalized_html,
                text_body=personalized_text,
                from_email=from_email,
                from_name=from_name,
            )

            results["sent"] += 1

        except Exception as e:
            logger.error(f"Error queuing email for {recipient.get('email')}: {e}")
            results["failed"] += 1
            results["errors"].append({"email": recipient.get("email"), "error": str(e)})

    logger.info(f"✅ Bulk email task completed: {results['sent']} sent, {results['failed']} failed")

    return results


@celery_app.task(name="send_team_invitation_email_task", bind=True, max_retries=3, default_retry_delay=60)
def send_team_invitation_email_task(
    self,
    tenant_id: str,
    to_email: str,
    inviter_name: str,
    invitation_token: str,
    base_url: str = "https://synkora.ai",
) -> dict[str, Any]:
    """
    Send team invitation email.

    Args:
        tenant_id: Tenant ID
        to_email: Invitee email
        inviter_name: Name of person sending invitation
        invitation_token: Invitation token
        base_url: Base URL for invitation link

    Returns:
        dict: Result of email sending operation
    """
    import asyncio

    async def _send_team_invitation():
        from sqlalchemy import select

        from src.core.database import create_celery_async_session
        from src.models import Tenant
        from src.services.integrations.email_service import EmailService

        async_session_factory = create_celery_async_session()
        async with async_session_factory() as db:
            try:
                logger.info(f"📧 Sending team invitation to {to_email}")

                # Get tenant name
                result = await db.execute(select(Tenant).filter(Tenant.id == uuid.UUID(tenant_id)))
                tenant = result.scalar_one_or_none()
                team_name = tenant.name if tenant else "the team"

                email_service = EmailService(db)

                result = await email_service.send_team_invitation_email(
                    to_email=to_email,
                    invitation_token=invitation_token,
                    inviter_name=inviter_name,
                    team_name=team_name,
                    role="member",
                    tenant_id=uuid.UUID(tenant_id),
                    base_url=base_url,
                )

                if result.get("success"):
                    logger.info(f"✅ Team invitation email sent to {to_email}")
                else:
                    logger.error(f"❌ Failed to send team invitation to {to_email}: {result.get('message')}")

                return result
            except Exception:
                await db.rollback()
                raise

    try:
        return asyncio.run(_send_team_invitation())
    except Exception as exc:
        logger.error(f"❌ Error sending team invitation to {to_email}: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))


@celery_app.task(
    name="tasks.send_new_login_notification",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def send_new_login_notification(
    self,
    account_id: str,
    ip: str,
    user_agent: str,
    timestamp: str,
) -> dict:
    """Send a notification email when a new login is detected from an unfamiliar IP.

    Currently a stub — logs the notification instead of delivering an email.
    Replace the logger.info call with an actual email dispatch when the email
    templates are ready.

    Args:
        account_id: UUID of the account that logged in.
        ip:         Client IP address from the login request.
        user_agent: User-Agent header value from the login request.
        timestamp:  ISO-8601 UTC timestamp of the login event.
    """
    try:
        logger.info(
            "New login notification: account=%s ip=%s ua=%s timestamp=%s",
            account_id,
            ip,
            user_agent,
            timestamp,
        )
        # TODO: replace with actual email delivery
        # e.g. send_email_task.delay(tenant_id=..., to_email=account.email,
        #          subject="New sign-in to your account", html_body=...)
        return {"sent": True, "account_id": account_id}
    except Exception as exc:
        logger.error("Failed to send new login notification for account %s: %s", account_id, exc)
        raise self.retry(exc=exc)
