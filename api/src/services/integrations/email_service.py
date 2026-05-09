"""Email service with support for multiple providers (SMTP, SendGrid)."""

import logging
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any
from uuid import UUID

# Configurable branding/contact info — set these env vars when self-hosting
_APP_BASE_URL = os.getenv("APP_BASE_URL", "https://synkora.ai")
_SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "support@localhost")
_DOCS_URL = os.getenv("DOCS_URL", "")

try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Content, Email, Mail, To

    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from sqlalchemy.ext.asyncio import AsyncSession

from .integration_config_service import IntegrationConfigService

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails using configured providers."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.config_service = IntegrationConfigService(db)

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str | None = None,
        from_email: str | None = None,
        from_name: str | None = None,
        tenant_id: UUID | None = None,
        provider: str | None = None,
        attachments: list[dict] | None = None,
    ) -> dict[str, Any]:
        """
        Send an email using the configured provider.

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML content of the email
            text_content: Plain text content (optional, will be generated from HTML if not provided)
            from_email: Sender email (optional, uses config default if not provided)
            from_name: Sender name (optional)
            tenant_id: Tenant ID (None for platform-wide config)
            provider: Specific provider to use (optional, uses active config if not provided)

        Returns:
            Dict with success status and message
        """
        try:
            # Get email configuration
            config_data = await self.config_service.get_active_config_data(
                tenant_id=tenant_id, integration_type="email", provider=provider
            )

            logger.info(f"Retrieved email config_data: {config_data}")

            if not config_data:
                logger.error("No email configuration found")
                return {
                    "success": False,
                    "message": "No email configuration found. Please configure an email provider.",
                }

            provider_name = config_data.get("provider", "smtp")
            logger.info(f"Using email provider: {provider_name}")

            # Extract from_email and from_name from settings if not provided
            settings = config_data.get("settings", {})
            default_from_email = config_data.get("from_email") or settings.get("from_email")
            default_from_name = config_data.get("from_name") or settings.get("from_name")

            if provider_name == "sendgrid":
                return self._send_via_sendgrid(
                    to_email=to_email,
                    subject=subject,
                    html_content=html_content,
                    text_content=text_content,
                    from_email=from_email or default_from_email,
                    from_name=from_name or default_from_name,
                    config=config_data,
                )
            elif provider_name == "mailgun":
                return self._send_via_mailgun(
                    to_email=to_email,
                    subject=subject,
                    html_content=html_content,
                    text_content=text_content,
                    from_email=from_email or default_from_email,
                    from_name=from_name or default_from_name,
                    config=config_data,
                )
            elif provider_name == "brevo":
                return self._send_via_brevo(
                    to_email=to_email,
                    subject=subject,
                    html_content=html_content,
                    text_content=text_content,
                    from_email=from_email or default_from_email,
                    from_name=from_name or default_from_name,
                    config=config_data,
                )
            elif provider_name == "resend":
                return self._send_via_resend(
                    to_email=to_email,
                    subject=subject,
                    html_content=html_content,
                    text_content=text_content,
                    from_email=from_email or default_from_email,
                    from_name=from_name or default_from_name,
                    config=config_data,
                )
            elif provider_name == "mailtrap":
                return self._send_via_mailtrap(
                    to_email=to_email,
                    subject=subject,
                    html_content=html_content,
                    text_content=text_content,
                    from_email=from_email or default_from_email,
                    from_name=from_name or default_from_name,
                    config=config_data,
                )
            else:  # smtp
                return self._send_via_smtp(
                    to_email=to_email,
                    subject=subject,
                    html_content=html_content,
                    text_content=text_content,
                    from_email=from_email or default_from_email,
                    from_name=from_name or default_from_name,
                    config=config_data,
                    attachments=attachments,
                )
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return {"success": False, "message": f"Failed to send email: {str(e)}"}

    def _send_via_smtp(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str | None,
        from_email: str,
        from_name: str | None,
        config: dict[str, Any],
        attachments: list[dict] | None = None,
    ) -> dict[str, Any]:
        """Send email via SMTP."""
        from email.mime.application import MIMEApplication
        from email.mime.image import MIMEImage

        try:
            # Use "mixed" when attachments are present, "alternative" otherwise
            if attachments:
                msg = MIMEMultipart("mixed")
                alt = MIMEMultipart("alternative")
                if text_content:
                    alt.attach(MIMEText(text_content, "plain"))
                alt.attach(MIMEText(html_content, "html"))
                msg.attach(alt)
                for a in attachments:
                    content = a.get("content", b"")
                    filename = a.get("filename", "attachment")
                    ctype = a.get("content_type", "application/octet-stream")
                    if ctype.startswith("image/"):
                        part = MIMEImage(content, name=filename)
                    else:
                        part = MIMEApplication(content, Name=filename)
                    part["Content-Disposition"] = f'attachment; filename="{filename}"'
                    msg.attach(part)
            else:
                msg = MIMEMultipart("alternative")
                if text_content:
                    msg.attach(MIMEText(text_content, "plain"))
                msg.attach(MIMEText(html_content, "html"))

            msg["Subject"] = subject
            msg["From"] = f"{from_name} <{from_email}>" if from_name else from_email
            msg["To"] = to_email

            # Connect to SMTP server
            # Support both flat and nested config structures
            settings = config.get("settings", {})
            credentials = config.get("credentials", {})

            smtp_host = config.get("smtp_host") or settings.get("host")
            smtp_port = config.get("smtp_port") or settings.get("port", 587)
            smtp_username = config.get("smtp_username") or credentials.get("username")
            smtp_password = config.get("smtp_password") or credentials.get("password")

            use_tls = config.get("use_tls")
            if use_tls is None:
                use_tls = settings.get("use_tls", True)

            logger.info(
                f"SMTP config - host: {smtp_host}, port: {smtp_port}, username: {smtp_username}, has_password: {bool(smtp_password)}, use_tls: {use_tls}"
            )

            require_auth = settings.get("require_auth", True)
            if not smtp_host:
                return {"success": False, "message": "SMTP configuration is incomplete"}
            if require_auth and (not smtp_username or not smtp_password):
                logger.error(
                    f"SMTP configuration is incomplete - host: {smtp_host}, username: {smtp_username}, has_password: {bool(smtp_password)}"
                )
                return {"success": False, "message": "SMTP configuration is incomplete"}

            # Create SMTP connection with timeout to prevent hanging
            # Default timeout: 30 seconds (connection + operations)
            # Increased timeout for Kubernetes network latency
            smtp_timeout = config.get("smtp_timeout") or settings.get("timeout", 60)
            server = None

            logger.info(
                f"Attempting SMTP connection to {smtp_host}:{smtp_port} (timeout={smtp_timeout}s, TLS={use_tls})"
            )

            try:
                # Port 465 implies implicit SSL even when use_tls is False
                use_ssl = settings.get("use_ssl", False) or (not use_tls and smtp_port == 465)
                if use_tls:
                    logger.debug("Creating SMTP connection (will use STARTTLS)...")
                    server = smtplib.SMTP(smtp_host, smtp_port, timeout=smtp_timeout)
                    logger.debug("SMTP connection established, starting TLS...")
                    server.starttls()
                    logger.debug("TLS negotiation complete")
                elif use_ssl:
                    logger.debug("Creating SMTP_SSL connection...")
                    server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=smtp_timeout)
                    logger.debug("SMTP_SSL connection established")
                else:
                    logger.debug("Creating plain SMTP connection (no TLS)...")
                    server = smtplib.SMTP(smtp_host, smtp_port, timeout=smtp_timeout)
                    logger.debug("Plain SMTP connection established")

                if require_auth and smtp_username and smtp_password:
                    logger.debug("Authenticating with SMTP server...")
                    server.login(smtp_username, smtp_password)
                    logger.debug("SMTP authentication successful")
                else:
                    logger.debug("Skipping SMTP auth (require_auth=False or no credentials)")

                logger.debug(f"Sending email to {to_email}...")
                server.sendmail(from_email, to_email, msg.as_string())
                logger.debug("Email sent successfully")
                server.quit()
            except (smtplib.SMTPConnectError, OSError, TimeoutError) as smtp_error:
                error_type = type(smtp_error).__name__
                logger.error(
                    f"SMTP connection failed ({error_type}): {str(smtp_error)}. "
                    f"Host: {smtp_host}:{smtp_port}, Timeout: {smtp_timeout}s. "
                    f"This often indicates a network connectivity issue in Kubernetes. "
                    f"Check: 1) Network policies blocking outbound SMTP, 2) Firewall rules, "
                    f"3) DNS resolution for {smtp_host}, 4) SMTP server allowing connections from cluster IPs"
                )
                # Ensure connection is closed even on error
                if server:
                    try:
                        server.quit()
                    except Exception:
                        pass  # Ignore errors during cleanup
                raise smtp_error
            except Exception as smtp_error:
                error_type = type(smtp_error).__name__
                logger.error(
                    f"SMTP operation failed ({error_type}): {str(smtp_error)}. "
                    f"Host: {smtp_host}:{smtp_port}, Timeout: {smtp_timeout}s"
                )
                # Ensure connection is closed even on error
                if server:
                    try:
                        server.quit()
                    except Exception:
                        pass  # Ignore errors during cleanup
                raise smtp_error

            logger.info(f"Email sent successfully via SMTP to {to_email}")
            return {"success": True, "message": "Email sent successfully via SMTP", "provider": "smtp"}

        except Exception as e:
            logger.error(f"SMTP send failed: {str(e)}")
            return {"success": False, "message": f"SMTP send failed: {str(e)}", "provider": "smtp"}

    def _send_via_sendgrid(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str | None,
        from_email: str,
        from_name: str | None,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Send email via SendGrid."""
        if not SENDGRID_AVAILABLE:
            return {
                "success": False,
                "message": "SendGrid library is not installed. Install with: pip install sendgrid",
                "provider": "sendgrid",
            }

        try:
            # SendGrid API key is stored in credentials.api_key (as per integration config structure)
            credentials = config.get("credentials", {})
            api_key = credentials.get("api_key")

            if not api_key:
                logger.error(
                    f"SendGrid API key not found in config.credentials.api_key. Config keys: {list(config.keys())}, Credentials keys: {list(credentials.keys()) if credentials else 'None'}"
                )
                return {
                    "success": False,
                    "message": "SendGrid API key is not configured in credentials.api_key",
                    "provider": "sendgrid",
                }

            # Create SendGrid message
            from_email_obj = Email(from_email, from_name)
            to_email_obj = To(to_email)

            # Use text content if provided, otherwise use HTML
            content = Content("text/html", html_content)
            if text_content:
                mail = Mail(from_email_obj, to_email_obj, subject, content)
                mail.add_content(Content("text/plain", text_content))
            else:
                mail = Mail(from_email_obj, to_email_obj, subject, content)

            # Send email
            sg = SendGridAPIClient(api_key)
            response = sg.send(mail)

            logger.info(f"Email sent successfully via SendGrid to {to_email}")
            return {
                "success": True,
                "message": "Email sent successfully via SendGrid",
                "provider": "sendgrid",
                "status_code": response.status_code,
            }

        except Exception as e:
            logger.error(f"SendGrid send failed: {str(e)}")
            return {"success": False, "message": f"SendGrid send failed: {str(e)}", "provider": "sendgrid"}

    def _send_via_mailgun(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str | None,
        from_email: str,
        from_name: str | None,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Send email via Mailgun REST API."""
        if not REQUESTS_AVAILABLE:
            return {
                "success": False,
                "message": "requests library is not installed. Install with: pip install requests",
                "provider": "mailgun",
            }

        try:
            # Mailgun API key and domain are stored in credentials (as per integration config structure)
            credentials = config.get("credentials", {})
            settings = config.get("settings", {})

            api_key = credentials.get("api_key")
            domain = credentials.get("domain") or settings.get("domain")

            if not api_key:
                logger.error(
                    f"Mailgun API key not found in config.credentials.api_key. Config keys: {list(config.keys())}, Credentials keys: {list(credentials.keys()) if credentials else 'None'}"
                )
                return {
                    "success": False,
                    "message": "Mailgun API key is not configured in credentials.api_key",
                    "provider": "mailgun",
                }

            if not domain:
                logger.error("Mailgun domain not found in config")
                return {
                    "success": False,
                    "message": "Mailgun domain is not configured. Set it in credentials.domain or settings.domain",
                    "provider": "mailgun",
                }

            # Format from address with optional name
            if from_name:
                from_formatted = f"{from_name} <{from_email}>"
            else:
                from_formatted = from_email

            # Prepare Mailgun API request
            api_url = f"https://api.mailgun.net/v3/{domain}/messages"

            data = {
                "from": from_formatted,
                "to": to_email,
                "subject": subject,
                "html": html_content,
            }

            # Add text content if provided
            if text_content:
                data["text"] = text_content

            # Add reply-to if configured
            reply_to = settings.get("reply_to")
            if reply_to:
                data["h:Reply-To"] = reply_to

            # Send request to Mailgun API
            response = requests.post(api_url, auth=("api", api_key), data=data, timeout=30)

            if response.status_code in [200, 201]:
                response_data = response.json()
                message_id = response_data.get("id")
                logger.info(f"Email sent successfully via Mailgun to {to_email}. Message ID: {message_id}")
                return {
                    "success": True,
                    "message": "Email sent successfully via Mailgun",
                    "message_id": message_id,
                    "provider": "mailgun",
                    "status_code": response.status_code,
                }
            else:
                error_msg = response.text or f"HTTP {response.status_code}"
                logger.warning(f"Mailgun API returned status {response.status_code}: {error_msg}")
                return {
                    "success": False,
                    "message": f"Mailgun API error: {error_msg}",
                    "status_code": response.status_code,
                    "provider": "mailgun",
                }

        except requests.exceptions.RequestException as e:
            logger.warning(f"Mailgun API request failed: {str(e)}")
            return {"success": False, "message": f"Mailgun API request failed: {str(e)}", "provider": "mailgun"}
        except Exception as e:
            logger.error(f"Mailgun send failed: {str(e)}")
            return {"success": False, "message": f"Mailgun send failed: {str(e)}", "provider": "mailgun"}

    def _send_via_brevo(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str | None,
        from_email: str,
        from_name: str | None,
        config: dict,
    ) -> dict[str, Any]:
        """Send email via Brevo Transactional Email API (HTTPS, no SMTP required)."""
        try:
            if not REQUESTS_AVAILABLE:
                return {"success": False, "message": "requests library is not installed", "provider": "brevo"}

            credentials = config.get("credentials", {})
            settings = config.get("settings", {})
            api_key = credentials.get("api_key")

            if not api_key:
                logger.warning("Brevo API key not found in config.credentials.api_key")
                return {"success": False, "message": "Brevo API key is not configured", "provider": "brevo"}

            sender_email = from_email or settings.get("from_email")
            sender_name = from_name or settings.get("from_name")

            if not sender_email:
                return {"success": False, "message": "Sender email is not configured", "provider": "brevo"}

            payload: dict[str, Any] = {
                "sender": {"email": sender_email, "name": sender_name} if sender_name else {"email": sender_email},
                "to": [{"email": to_email}],
                "subject": subject,
                "htmlContent": html_content,
            }

            if text_content:
                payload["textContent"] = text_content

            reply_to = settings.get("reply_to")
            if reply_to:
                payload["replyTo"] = {"email": reply_to}

            response = requests.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={"api-key": api_key, "Content-Type": "application/json"},
                json=payload,
                timeout=30,
            )

            if response.status_code in [200, 201]:
                message_id = response.json().get("messageId")
                logger.info(f"Email sent successfully to {to_email} via Brevo. Message ID: {message_id}")
                return {
                    "success": True,
                    "message": "Email sent successfully",
                    "message_id": message_id,
                    "provider": "brevo",
                }

            error_msg = response.text or f"HTTP {response.status_code}"
            logger.warning(f"Brevo API returned status {response.status_code}: {error_msg}")
            return {"success": False, "message": f"Brevo API error: {error_msg}", "provider": "brevo"}

        except requests.exceptions.RequestException as e:
            logger.warning(f"Brevo API request failed: {str(e)}")
            return {"success": False, "message": f"Brevo API request failed: {str(e)}", "provider": "brevo"}
        except Exception as e:
            logger.error(f"Brevo send failed: {str(e)}")
            return {"success": False, "message": f"Brevo send failed: {str(e)}", "provider": "brevo"}

    def _send_via_resend(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str | None,
        from_email: str,
        from_name: str | None,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Send email via Resend API (https://resend.com)."""
        try:
            api_key = config.get("api_key") or config.get("credentials", {}).get("api_key")
            if not api_key:
                return {"success": False, "message": "Resend api_key is required", "provider": "resend"}

            sender = f"{from_name} <{from_email}>" if from_name else from_email
            payload: dict[str, Any] = {
                "from": sender,
                "to": [to_email],
                "subject": subject,
                "html": html_content,
            }
            if text_content:
                payload["text"] = text_content

            response = requests.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=30,
            )

            if response.status_code in [200, 201]:
                logger.info(f"Email sent to {to_email} via Resend")
                return {
                    "success": True,
                    "message": "Email sent successfully",
                    "provider": "resend",
                    "message_id": response.json().get("id"),
                }

            error_msg = response.text or f"HTTP {response.status_code}"
            logger.warning(f"Resend API returned {response.status_code}: {error_msg}")
            return {"success": False, "message": f"Resend API error: {error_msg}", "provider": "resend"}

        except Exception as e:
            logger.error(f"Resend send failed: {e}")
            return {"success": False, "message": f"Resend send failed: {str(e)}", "provider": "resend"}

    def _send_via_mailtrap(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str | None,
        from_email: str,
        from_name: str | None,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Send email via Mailtrap sending API (https://send.api.mailtrap.io)."""
        try:
            api_token = config.get("api_token") or config.get("credentials", {}).get("api_token")
            if not api_token:
                return {"success": False, "message": "Mailtrap api_token is required", "provider": "mailtrap"}

            sender_email = from_email or "hello@demomailtrap.co"
            payload = {
                "from": {"email": sender_email, "name": from_name or "Newsletter Agent"},
                "to": [{"email": to_email}],
                "subject": subject,
                "html": html_content,
            }
            if text_content:
                payload["text"] = text_content

            response = requests.post(
                "https://send.api.mailtrap.io/api/send",
                headers={"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"},
                json=payload,
                timeout=30,
            )

            if response.status_code in [200, 201]:
                logger.info(f"Email sent to {to_email} via Mailtrap")
                return {"success": True, "message": "Email sent successfully", "provider": "mailtrap"}

            error_msg = response.text or f"HTTP {response.status_code}"
            logger.warning(f"Mailtrap API returned {response.status_code}: {error_msg}")
            return {"success": False, "message": f"Mailtrap API error: {error_msg}", "provider": "mailtrap"}

        except Exception as e:
            logger.error(f"Mailtrap send failed: {e}")
            return {"success": False, "message": f"Mailtrap send failed: {str(e)}", "provider": "mailtrap"}

    async def send_verification_email(
        self,
        to_email: str,
        verification_token: str,
        tenant_id: UUID | None = None,
        base_url: str = "https://synkora.ai",
    ) -> dict[str, Any]:
        """Send email verification email."""
        verification_url = f"{base_url}/verify-email?token={verification_token}"

        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <meta http-equiv="X-UA-Compatible" content="IE=edge">
            <title>Verify Your Email - Synkora AI</title>
            <!--[if mso]>
            <noscript>
                <xml>
                    <o:OfficeDocumentSettings>
                        <o:PixelsPerInch>96</o:PixelsPerInch>
                    </o:OfficeDocumentSettings>
                </xml>
            </noscript>
            <![endif]-->
            <style>
                /* Reset and base styles */
                body {{
                    margin: 0;
                    padding: 0;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif;
                    -webkit-font-smoothing: antialiased;
                    -moz-osx-font-smoothing: grayscale;
                    background-color: #f3f4f6;
                    color: #111827;
                    line-height: 1.6;
                }}

                /* Email container */
                .email-wrapper {{
                    width: 100%;
                    background-color: #f3f4f6;
                    padding: 40px 20px;
                }}

                .email-container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: #ffffff;
                    border-radius: 16px;
                    overflow: hidden;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.07);
                }}

                /* Header */
                .header {{
                    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
                    padding: 48px 40px 40px;
                    text-align: center;
                }}

                .logo {{
                    font-size: 32px;
                    font-weight: 800;
                    color: #ffffff;
                    margin: 0 0 8px 0;
                    letter-spacing: -0.5px;
                }}

                .tagline {{
                    font-size: 14px;
                    color: rgba(255, 255, 255, 0.9);
                    margin: 0;
                    font-weight: 500;
                    letter-spacing: 0.5px;
                }}

                /* Content */
                .content {{
                    padding: 48px 40px;
                }}

                .greeting {{
                    font-size: 26px;
                    font-weight: 700;
                    color: #111827;
                    margin: 0 0 16px 0;
                    text-align: center;
                }}

                .message {{
                    font-size: 16px;
                    color: #4b5563;
                    margin: 0 0 32px 0;
                    line-height: 1.7;
                    text-align: center;
                }}

                /* Button - Enhanced for email clients */
                .button-container {{
                    text-align: center;
                    margin: 32px 0;
                }}

                .button {{
                    display: inline-block;
                    padding: 18px 48px;
                    background-color: #ef4444;
                    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
                    color: #ffffff !important;
                    text-decoration: none;
                    border-radius: 12px;
                    font-size: 16px;
                    font-weight: 700;
                    letter-spacing: 0.3px;
                    box-shadow: 0 4px 14px rgba(239, 68, 68, 0.4);
                    mso-padding-alt: 0;
                }}

                /* MSO button fallback */
                .button-td {{
                    background-color: #ef4444;
                    border-radius: 12px;
                }}

                /* Alternative link */
                .link-section {{
                    margin: 32px 0;
                    padding: 20px;
                    background-color: #f9fafb;
                    border-radius: 12px;
                }}

                .link-text {{
                    font-size: 13px;
                    color: #6b7280;
                    margin: 0 0 12px 0;
                    text-align: center;
                }}

                .verification-link {{
                    word-break: break-all;
                    font-size: 12px;
                    color: #dc2626;
                    background-color: #ffffff;
                    padding: 12px 16px;
                    border-radius: 8px;
                    border: 1px solid #e5e7eb;
                    display: block;
                    margin: 0;
                    font-family: 'Courier New', Courier, monospace;
                    text-align: center;
                }}

                /* Expiry notice */
                .expiry-notice {{
                    background-color: #fef3c7;
                    border-radius: 12px;
                    padding: 16px 20px;
                    margin: 24px 0 0 0;
                    font-size: 14px;
                    color: #92400e;
                    text-align: center;
                }}

                .expiry-notice strong {{
                    font-weight: 600;
                }}

                /* Footer */
                .footer {{
                    background-color: #f9fafb;
                    padding: 32px 40px;
                    border-top: 1px solid #e5e7eb;
                    text-align: center;
                }}

                .footer-text {{
                    font-size: 13px;
                    color: #6b7280;
                    margin: 0 0 12px 0;
                    line-height: 1.6;
                }}

                .footer-link {{
                    color: #ef4444;
                    text-decoration: none;
                    font-weight: 500;
                }}

                .footer-link:hover {{
                    text-decoration: underline;
                }}

                .footer-copyright {{
                    font-size: 12px;
                    color: #9ca3af;
                    margin: 16px 0 0 0;
                }}

                .social-links {{
                    margin: 16px 0;
                }}

                .social-links a {{
                    display: inline-block;
                    margin: 0 8px;
                    color: #6b7280;
                    text-decoration: none;
                    font-size: 13px;
                }}

                .social-links a:hover {{
                    color: #ef4444;
                }}

                /* Mobile responsive */
                @media only screen and (max-width: 600px) {{
                    .email-wrapper {{
                        padding: 20px 12px;
                    }}

                    .header {{
                        padding: 36px 24px 32px;
                    }}

                    .logo {{
                        font-size: 28px;
                    }}

                    .content {{
                        padding: 36px 24px;
                    }}

                    .greeting {{
                        font-size: 22px;
                    }}

                    .message {{
                        font-size: 15px;
                    }}

                    .button {{
                        padding: 16px 36px;
                        font-size: 15px;
                    }}

                    .footer {{
                        padding: 28px 24px;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="email-wrapper">
                <div class="email-container">
                    <!-- Header -->
                    <div class="header">
                        <h1 class="logo">Synkora AI</h1>
                        <p class="tagline">Build AI Agents For Every Role</p>
                    </div>

                    <!-- Content -->
                    <div class="content">
                        <h2 class="greeting">Verify Your Email Address</h2>

                        <p class="message">
                            Welcome to Synkora AI! You're one step away from building intelligent
                            AI agents for your team. Click the button below to verify your email
                            and get started.
                        </p>

                        <div class="button-container">
                            <!--[if mso]>
                            <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" xmlns:w="urn:schemas-microsoft-com:office:word" href="{verification_url}" style="height:54px;v-text-anchor:middle;width:220px;" arcsize="22%" strokecolor="#dc2626" fillcolor="#ef4444">
                                <w:anchorlock/>
                                <center style="color:#ffffff;font-family:sans-serif;font-size:16px;font-weight:bold;">Verify Email</center>
                            </v:roundrect>
                            <![endif]-->
                            <!--[if !mso]><!-->
                            <a href="{verification_url}" class="button" target="_blank">Verify My Email</a>
                            <!--<![endif]-->
                        </div>

                        <div class="link-section">
                            <p class="link-text">Or copy and paste this link into your browser:</p>
                            <div class="verification-link">{verification_url}</div>
                        </div>

                        <div class="expiry-notice">
                            <strong>Note:</strong> This link expires in 24 hours for security.
                        </div>
                    </div>

                    <!-- Footer -->
                    <div class="footer">
                        <p class="footer-text">
                            If you didn't create an account with Synkora AI, you can safely ignore this email.
                        </p>
                        <div class="social-links">
                            <a href="{_APP_BASE_URL}">Website</a>
                            {('<a href="' + _DOCS_URL + '">Docs</a>') if _DOCS_URL else ""}
                            <a href="mailto:{_SUPPORT_EMAIL}">Support</a>
                        </div>
                        <p class="footer-copyright">
                            &copy; {datetime.now().year} Synkora AI. All rights reserved.
                        </p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"""
        Synkora AI - Build AI Agents For Every Role

        VERIFY YOUR EMAIL ADDRESS

        Welcome to Synkora AI! You're one step away from building intelligent AI agents for your team.

        Click this link to verify your email:
        {verification_url}

        Note: This link expires in 24 hours for security.

        If you didn't create an account with Synkora AI, you can safely ignore this email.

        ---
        Website: {_APP_BASE_URL}
        {("Docs: " + _DOCS_URL) if _DOCS_URL else ""}
        Support: {_SUPPORT_EMAIL}

        (c) {datetime.now().year} Synkora AI. All rights reserved.
        """

        return await self.send_email(
            to_email=to_email,
            subject="Verify Your Email - Synkora AI",
            html_content=html_content,
            text_content=text_content,
            tenant_id=tenant_id,
        )

    async def send_welcome_email(
        self,
        to_email: str,
        user_name: str | None = None,
        tenant_id: UUID | None = None,
        base_url: str = "https://synkora.ai",
    ) -> dict[str, Any]:
        """Send welcome email after email verification with core features."""
        dashboard_url = f"{base_url}/dashboard"
        docs_url = _DOCS_URL or f"{base_url}/docs"

        display_name = user_name.split()[0] if user_name else "there"

        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <meta http-equiv="X-UA-Compatible" content="IE=edge">
            <title>Welcome to Synkora AI</title>
            <!--[if mso]>
            <noscript>
                <xml>
                    <o:OfficeDocumentSettings>
                        <o:PixelsPerInch>96</o:PixelsPerInch>
                    </o:OfficeDocumentSettings>
                </xml>
            </noscript>
            <![endif]-->
            <style>
                body {{
                    margin: 0;
                    padding: 0;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica Neue', sans-serif;
                    -webkit-font-smoothing: antialiased;
                    background-color: #f3f4f6;
                    color: #111827;
                    line-height: 1.6;
                }}

                .email-wrapper {{
                    width: 100%;
                    background-color: #f3f4f6;
                    padding: 40px 20px;
                }}

                .email-container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: #ffffff;
                    border-radius: 16px;
                    overflow: hidden;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.07);
                }}

                .header {{
                    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
                    padding: 48px 40px;
                    text-align: center;
                }}

                .logo {{
                    font-size: 32px;
                    font-weight: 800;
                    color: #ffffff;
                    margin: 0 0 8px 0;
                }}

                .tagline {{
                    font-size: 14px;
                    color: rgba(255, 255, 255, 0.9);
                    margin: 0;
                    font-weight: 500;
                }}

                .content {{
                    padding: 48px 40px;
                }}

                .welcome-text {{
                    font-size: 28px;
                    font-weight: 700;
                    color: #111827;
                    margin: 0 0 16px 0;
                    text-align: center;
                }}

                .intro {{
                    font-size: 16px;
                    color: #4b5563;
                    margin: 0 0 32px 0;
                    text-align: center;
                    line-height: 1.7;
                }}

                .features-section {{
                    margin: 32px 0;
                }}

                .features-title {{
                    font-size: 18px;
                    font-weight: 700;
                    color: #111827;
                    margin: 0 0 20px 0;
                    text-align: center;
                }}

                .feature-card {{
                    background: linear-gradient(135deg, #fef2f2 0%, #fff7ed 100%);
                    border-radius: 12px;
                    padding: 20px;
                    margin-bottom: 16px;
                }}

                .feature-icon {{
                    font-size: 24px;
                    margin-bottom: 8px;
                }}

                .feature-name {{
                    font-size: 16px;
                    font-weight: 700;
                    color: #111827;
                    margin: 0 0 6px 0;
                }}

                .feature-desc {{
                    font-size: 14px;
                    color: #6b7280;
                    margin: 0;
                    line-height: 1.5;
                }}

                .cta-section {{
                    text-align: center;
                    margin: 40px 0 24px 0;
                }}

                .button {{
                    display: inline-block;
                    padding: 18px 48px;
                    background-color: #ef4444;
                    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
                    color: #ffffff !important;
                    text-decoration: none;
                    border-radius: 12px;
                    font-size: 16px;
                    font-weight: 700;
                    box-shadow: 0 4px 14px rgba(239, 68, 68, 0.4);
                }}

                .secondary-link {{
                    display: inline-block;
                    margin-top: 16px;
                    color: #6b7280;
                    text-decoration: none;
                    font-size: 14px;
                }}

                .secondary-link:hover {{
                    color: #ef4444;
                }}

                .tips-section {{
                    background-color: #f9fafb;
                    border-radius: 12px;
                    padding: 24px;
                    margin: 32px 0 0 0;
                }}

                .tips-title {{
                    font-size: 14px;
                    font-weight: 700;
                    color: #111827;
                    margin: 0 0 12px 0;
                }}

                .tip-item {{
                    font-size: 14px;
                    color: #4b5563;
                    margin: 8px 0;
                    padding-left: 20px;
                    position: relative;
                }}

                .tip-item:before {{
                    content: "→";
                    position: absolute;
                    left: 0;
                    color: #ef4444;
                }}

                .footer {{
                    background-color: #f9fafb;
                    padding: 32px 40px;
                    border-top: 1px solid #e5e7eb;
                    text-align: center;
                }}

                .footer-text {{
                    font-size: 13px;
                    color: #6b7280;
                    margin: 0 0 12px 0;
                }}

                .social-links {{
                    margin: 16px 0;
                }}

                .social-links a {{
                    display: inline-block;
                    margin: 0 8px;
                    color: #6b7280;
                    text-decoration: none;
                    font-size: 13px;
                }}

                .footer-copyright {{
                    font-size: 12px;
                    color: #9ca3af;
                    margin: 16px 0 0 0;
                }}

                @media only screen and (max-width: 600px) {{
                    .email-wrapper {{
                        padding: 20px 12px;
                    }}

                    .header, .content, .footer {{
                        padding-left: 24px;
                        padding-right: 24px;
                    }}

                    .welcome-text {{
                        font-size: 24px;
                    }}

                    .button {{
                        padding: 16px 36px;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="email-wrapper">
                <div class="email-container">
                    <!-- Header -->
                    <div class="header">
                        <h1 class="logo">Synkora AI</h1>
                        <p class="tagline">Build AI Agents For Every Role</p>
                    </div>

                    <!-- Content -->
                    <div class="content">
                        <h2 class="welcome-text">Welcome, {display_name}! 🎉</h2>

                        <p class="intro">
                            Your email is verified and you're ready to start building AI agents
                            that work 24/7 for your team. Here's what you can do with Synkora AI:
                        </p>

                        <!-- Features -->
                        <div class="features-section">
                            <h3 class="features-title">What You Can Build</h3>

                            <div class="feature-card">
                                <div class="feature-icon">🧑‍💼</div>
                                <h4 class="feature-name">AI Product Manager</h4>
                                <p class="feature-desc">
                                    Automate backlog prioritization, sprint planning, and status reports.
                                    Your AI PM keeps projects on track around the clock.
                                </p>
                            </div>

                            <div class="feature-card">
                                <div class="feature-icon">👨‍💻</div>
                                <h4 class="feature-name">AI Software Engineer</h4>
                                <p class="feature-desc">
                                    Code review, bug triage, documentation generation, and CI/CD monitoring.
                                    An AI teammate that never misses a PR.
                                </p>
                            </div>

                            <div class="feature-card">
                                <div class="feature-icon">📢</div>
                                <h4 class="feature-name">AI Marketing Lead</h4>
                                <p class="feature-desc">
                                    Content creation, campaign analysis, SEO optimization, and social media
                                    management. Scale your marketing effortlessly.
                                </p>
                            </div>
                        </div>

                        <!-- CTA -->
                        <div class="cta-section">
                            <!--[if mso]>
                            <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" xmlns:w="urn:schemas-microsoft-com:office:word" href="{dashboard_url}" style="height:54px;v-text-anchor:middle;width:240px;" arcsize="22%" strokecolor="#dc2626" fillcolor="#ef4444">
                                <w:anchorlock/>
                                <center style="color:#ffffff;font-family:sans-serif;font-size:16px;font-weight:bold;">Go to Dashboard</center>
                            </v:roundrect>
                            <![endif]-->
                            <!--[if !mso]><!-->
                            <a href="{dashboard_url}" class="button" target="_blank">Go to Dashboard</a>
                            <!--<![endif]-->
                            <br>
                            <a href="{docs_url}" class="secondary-link" target="_blank">Read the Documentation →</a>
                        </div>

                        <!-- Quick Tips -->
                        <div class="tips-section">
                            <h4 class="tips-title">Quick Start Tips</h4>
                            <p class="tip-item">Create your first agent in under 5 minutes</p>
                            <p class="tip-item">Connect your knowledge base for smarter responses</p>
                            <p class="tip-item">Deploy to Slack, Discord, or embed on your website</p>
                            <p class="tip-item">Use pre-built templates to get started fast</p>
                        </div>
                    </div>

                    <!-- Footer -->
                    <div class="footer">
                        <p class="footer-text">
                            Questions? We're here to help you succeed.
                        </p>
                        <div class="social-links">
                            <a href="{_APP_BASE_URL}">Website</a>
                            <a href="{docs_url}">Docs</a>
                            <a href="mailto:{_SUPPORT_EMAIL}">Support</a>
                        </div>
                        <p class="footer-copyright">
                            &copy; {datetime.now().year} Synkora AI. All rights reserved.
                        </p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"""
        Synkora AI - Build AI Agents For Every Role

        WELCOME, {display_name.upper()}!

        Your email is verified and you're ready to start building AI agents that work 24/7 for your team.

        WHAT YOU CAN BUILD:

        AI Product Manager
        Automate backlog prioritization, sprint planning, and status reports. Your AI PM keeps projects on track around the clock.

        AI Software Engineer
        Code review, bug triage, documentation generation, and CI/CD monitoring. An AI teammate that never misses a PR.

        AI Marketing Lead
        Content creation, campaign analysis, SEO optimization, and social media management. Scale your marketing effortlessly.

        QUICK START TIPS:
        - Create your first agent in under 5 minutes
        - Connect your knowledge base for smarter responses
        - Deploy to Slack, Discord, or embed on your website
        - Use pre-built templates to get started fast

        Go to Dashboard: {dashboard_url}
        Documentation: {docs_url}

        ---
        Questions? We're here to help you succeed.
        Website: {_APP_BASE_URL}
        Support: {_SUPPORT_EMAIL}

        (c) {datetime.now().year} Synkora AI. All rights reserved.
        """

        return await self.send_email(
            to_email=to_email,
            subject="Welcome to Synkora AI - Let's Build Your First Agent!",
            html_content=html_content,
            text_content=text_content,
            tenant_id=tenant_id,
        )

    async def send_team_invitation_email(
        self,
        to_email: str,
        invitation_token: str,
        inviter_name: str,
        team_name: str,
        role: str,
        tenant_id: UUID | None = None,
        base_url: str = "https://synkora.ai",
    ) -> dict[str, Any]:
        """Send team invitation email."""
        invitation_url = f"{base_url}/accept-invite?token={invitation_token}"

        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Team Invitation - Synkora</title>
            <style>
                body {{
                    margin: 0;
                    padding: 0;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', sans-serif;
                    background-color: #f3f4f6;
                    color: #111827;
                    line-height: 1.6;
                }}
                .email-wrapper {{
                    width: 100%;
                    background-color: #f3f4f6;
                    padding: 40px 20px;
                }}
                .email-container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: #ffffff;
                    border-radius: 12px;
                    overflow: hidden;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.07);
                }}
                .header {{
                    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
                    padding: 40px 40px 30px;
                    text-align: center;
                }}
                .logo {{
                    font-size: 28px;
                    font-weight: 700;
                    color: #ffffff;
                    margin: 0;
                }}
                .content {{
                    padding: 40px;
                }}
                .greeting {{
                    font-size: 24px;
                    font-weight: 600;
                    color: #111827;
                    margin: 0 0 16px 0;
                }}
                .message {{
                    font-size: 16px;
                    color: #4b5563;
                    margin: 0 0 24px 0;
                }}
                .invite-box {{
                    background-color: #fef2f2;
                    border: 1px solid #fecaca;
                    border-radius: 8px;
                    padding: 20px;
                    margin: 24px 0;
                }}
                .invite-detail {{
                    display: flex;
                    margin-bottom: 8px;
                    font-size: 14px;
                }}
                .invite-label {{
                    color: #6b7280;
                    width: 80px;
                }}
                .invite-value {{
                    color: #111827;
                    font-weight: 500;
                }}
                .button-container {{
                    text-align: center;
                    margin: 32px 0;
                }}
                .button {{
                    display: inline-block;
                    padding: 16px 32px;
                    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
                    color: #ffffff;
                    text-decoration: none;
                    border-radius: 8px;
                    font-size: 16px;
                    font-weight: 600;
                }}
                .link-text {{
                    font-size: 14px;
                    color: #6b7280;
                    margin: 24px 0 16px;
                    text-align: center;
                }}
                .invitation-link {{
                    word-break: break-all;
                    font-size: 13px;
                    color: #dc2626;
                    background-color: #fef2f2;
                    padding: 12px 16px;
                    border-radius: 6px;
                    display: block;
                    margin: 16px 0;
                }}
                .expiry-notice {{
                    background-color: #fef2f2;
                    border-left: 4px solid #ef4444;
                    padding: 12px 16px;
                    margin: 24px 0;
                    border-radius: 4px;
                    font-size: 14px;
                    color: #991b1b;
                }}
                .footer {{
                    background-color: #f9fafb;
                    padding: 30px 40px;
                    border-top: 1px solid #e5e7eb;
                    text-align: center;
                }}
                .footer-text {{
                    font-size: 13px;
                    color: #6b7280;
                    margin: 0 0 16px 0;
                }}
                .footer-link {{
                    color: #ef4444;
                    text-decoration: none;
                }}
            </style>
        </head>
        <body>
            <div class="email-wrapper">
                <div class="email-container">
                    <div class="header">
                        <h1 class="logo">Synkora</h1>
                    </div>
                    <div class="content">
                        <h2 class="greeting">You're Invited!</h2>
                        <p class="message">
                            <strong>{inviter_name}</strong> has invited you to join <strong>{team_name}</strong> on Synkora.
                        </p>
                        <div class="invite-box">
                            <div class="invite-detail">
                                <span class="invite-label">Team:</span>
                                <span class="invite-value">{team_name}</span>
                            </div>
                            <div class="invite-detail">
                                <span class="invite-label">Role:</span>
                                <span class="invite-value">{role.capitalize()}</span>
                            </div>
                            <div class="invite-detail">
                                <span class="invite-label">Invited by:</span>
                                <span class="invite-value">{inviter_name}</span>
                            </div>
                        </div>
                        <div class="button-container">
                            <a href="{invitation_url}" class="button">Accept Invitation</a>
                        </div>
                        <p class="link-text">Or copy and paste this link into your browser:</p>
                        <div class="invitation-link">{invitation_url}</div>
                        <div class="expiry-notice">
                            <strong>Note:</strong> This invitation will expire in 7 days.
                        </div>
                    </div>
                    <div class="footer">
                        <p class="footer-text">
                            If you don't want to join this team, you can safely ignore this email.
                        </p>
                        <p class="footer-text">
                            Need help? Contact us at <a href="mailto:{_SUPPORT_EMAIL}" class="footer-link">{_SUPPORT_EMAIL}</a>
                        </p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"""
        You're Invited to Join {team_name} on Synkora!

        {inviter_name} has invited you to join {team_name} on Synkora.

        Team: {team_name}
        Role: {role.capitalize()}
        Invited by: {inviter_name}

        Click here to accept the invitation:
        {invitation_url}

        Note: This invitation will expire in 7 days.

        If you don't want to join this team, you can safely ignore this email.

        Need help? Contact us at {_SUPPORT_EMAIL}
        """

        return await self.send_email(
            to_email=to_email,
            subject=f"You're invited to join {team_name} on Synkora",
            html_content=html_content,
            text_content=text_content,
            tenant_id=tenant_id,
        )

    async def send_password_reset_email(
        self, to_email: str, reset_token: str, tenant_id: UUID | None = None, base_url: str = "https://synkora.ai"
    ) -> dict[str, Any]:
        """Send password reset email."""
        reset_url = f"{base_url}/reset-password?token={reset_token}"

        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Reset Your Password - Synkora</title>
            <style>
                body {{
                    margin: 0;
                    padding: 0;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', sans-serif;
                    background-color: #f3f4f6;
                    color: #111827;
                    line-height: 1.6;
                }}
                .email-wrapper {{
                    width: 100%;
                    background-color: #f3f4f6;
                    padding: 40px 20px;
                }}
                .email-container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: #ffffff;
                    border-radius: 12px;
                    overflow: hidden;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.07);
                }}
                .header {{
                    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
                    padding: 40px 40px 30px;
                    text-align: center;
                }}
                .logo {{
                    font-size: 28px;
                    font-weight: 700;
                    color: #ffffff;
                    margin: 0;
                }}
                .content {{
                    padding: 40px;
                }}
                .greeting {{
                    font-size: 24px;
                    font-weight: 600;
                    color: #111827;
                    margin: 0 0 16px 0;
                }}
                .message {{
                    font-size: 16px;
                    color: #4b5563;
                    margin: 0 0 24px 0;
                }}
                .button-container {{
                    text-align: center;
                    margin: 32px 0;
                }}
                .button {{
                    display: inline-block;
                    padding: 16px 32px;
                    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
                    color: #ffffff;
                    text-decoration: none;
                    border-radius: 8px;
                    font-size: 16px;
                    font-weight: 600;
                    box-shadow: 0 4px 12px rgba(239, 68, 68, 0.3);
                }}
                .link-text {{
                    font-size: 14px;
                    color: #6b7280;
                    margin: 24px 0 16px;
                    text-align: center;
                }}
                .reset-link {{
                    word-break: break-all;
                    font-size: 13px;
                    color: #dc2626;
                    background-color: #fef2f2;
                    padding: 12px 16px;
                    border-radius: 6px;
                    border: 1px solid #fecaca;
                    display: block;
                    margin: 16px 0;
                    font-family: 'Courier New', monospace;
                }}
                .expiry-notice {{
                    background-color: #fef2f2;
                    border-left: 4px solid #ef4444;
                    padding: 12px 16px;
                    margin: 24px 0;
                    border-radius: 4px;
                    font-size: 14px;
                    color: #991b1b;
                }}
                .footer {{
                    background-color: #f9fafb;
                    padding: 30px 40px;
                    border-top: 1px solid #e5e7eb;
                    text-align: center;
                }}
                .footer-text {{
                    font-size: 13px;
                    color: #6b7280;
                    margin: 0 0 16px 0;
                }}
                .footer-link {{
                    color: #ef4444;
                    text-decoration: none;
                }}
            </style>
        </head>
        <body>
            <div class="email-wrapper">
                <div class="email-container">
                    <div class="header">
                        <h1 class="logo">Synkora</h1>
                    </div>
                    <div class="content">
                        <h2 class="greeting">Reset Your Password</h2>
                        <p class="message">
                            We received a request to reset your password. Click the button below to create a new password:
                        </p>
                        <div class="button-container">
                            <a href="{reset_url}" class="button">Reset Password</a>
                        </div>
                        <p class="link-text">Or copy and paste this link into your browser:</p>
                        <div class="reset-link">{reset_url}</div>
                        <div class="expiry-notice">
                            <strong>⏰ Important:</strong> This link will expire in 1 hour for security reasons.
                        </div>
                    </div>
                    <div class="footer">
                        <p class="footer-text">
                            If you didn't request a password reset, you can safely ignore this email. Your password will not be changed.
                        </p>
                        <p class="footer-text">
                            Need help? Contact us at <a href="mailto:{_SUPPORT_EMAIL}" class="footer-link">{_SUPPORT_EMAIL}</a>
                        </p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"""
        Reset Your Password

        We received a request to reset your password. Visit this link to create a new password:

        {reset_url}

        This link will expire in 1 hour.

        If you didn't request a password reset, you can safely ignore this email. Your password will not be changed.
        """

        return await self.send_email(
            to_email=to_email,
            subject="Reset Your Password",
            html_content=html_content,
            text_content=text_content,
            tenant_id=tenant_id,
        )

    async def test_connection(
        self,
        tenant_id: UUID | None = None,
        provider: str | None = None,
        config_id: str | None = None,
        test_email: str | None = None,
    ) -> dict[str, Any]:
        """Test email configuration by attempting to connect."""
        # If config_id is provided, use that specific config
        if config_id:
            config_data = await self.config_service.get_config_data(config_id)
            if not config_data:
                return {"success": False, "message": "Configuration not found"}
        else:
            # Otherwise use active config
            config_data = await self.config_service.get_active_config_data(
                tenant_id=tenant_id, integration_type="email", provider=provider
            )

            if not config_data:
                return {"success": False, "message": "No email configuration found"}

        provider_name = config_data.get("provider", "smtp")

        try:
            if provider_name == "sendgrid":
                # For SendGrid, just check if API key is present
                credentials = config_data.get("credentials", {})
                if credentials.get("api_key"):
                    return {"success": True, "message": "SendGrid configuration is valid", "provider": "sendgrid"}
                else:
                    return {"success": False, "message": "SendGrid API key is missing", "provider": "sendgrid"}
            elif provider_name == "brevo":
                credentials = config_data.get("credentials", {})
                api_key = credentials.get("api_key")

                if not api_key:
                    return {"success": False, "message": "Brevo API key is missing", "provider": "brevo"}

                if not REQUESTS_AVAILABLE:
                    return {"success": False, "message": "requests library is not installed", "provider": "brevo"}

                try:
                    response = requests.get(
                        "https://api.brevo.com/v3/account",
                        headers={"api-key": api_key},
                        timeout=10,
                    )
                    if response.status_code == 200:
                        email = response.json().get("email", "")
                        return {
                            "success": True,
                            "message": f"Brevo connection successful. Account: {email}",
                            "provider": "brevo",
                        }
                    elif response.status_code == 401:
                        return {
                            "success": False,
                            "message": "Brevo authentication failed — check your API key",
                            "provider": "brevo",
                        }
                    else:
                        return {
                            "success": False,
                            "message": f"Brevo connection test failed: HTTP {response.status_code}",
                            "provider": "brevo",
                        }
                except requests.exceptions.RequestException as e:
                    return {"success": False, "message": f"Brevo connection test failed: {str(e)}", "provider": "brevo"}

            elif provider_name == "mailgun":
                # For Mailgun, check API key and domain
                credentials = config_data.get("credentials", {})
                settings = config_data.get("settings", {})
                api_key = credentials.get("api_key")
                domain = credentials.get("domain") or settings.get("domain")

                if not api_key:
                    return {"success": False, "message": "Mailgun API key is missing", "provider": "mailgun"}

                if not domain:
                    return {"success": False, "message": "Mailgun domain is missing", "provider": "mailgun"}

                # Test connection by making a lightweight API call
                if not REQUESTS_AVAILABLE:
                    return {"success": False, "message": "requests library is not installed", "provider": "mailgun"}

                try:
                    api_url = f"https://api.mailgun.net/v3/domains/{domain}"
                    response = requests.get(api_url, auth=("api", api_key), timeout=10)

                    if response.status_code == 200:
                        return {"success": True, "message": "Mailgun configuration is valid", "provider": "mailgun"}
                    elif response.status_code == 401:
                        return {
                            "success": False,
                            "message": "Mailgun authentication failed - check your API key",
                            "provider": "mailgun",
                        }
                    elif response.status_code == 404:
                        return {
                            "success": False,
                            "message": f"Mailgun domain not found: {domain}",
                            "provider": "mailgun",
                        }
                    else:
                        return {
                            "success": False,
                            "message": f"Mailgun connection test failed: HTTP {response.status_code}",
                            "provider": "mailgun",
                        }
                except requests.exceptions.RequestException as e:
                    return {
                        "success": False,
                        "message": f"Mailgun connection test failed: {str(e)}",
                        "provider": "mailgun",
                    }
                except Exception as e:
                    return {
                        "success": False,
                        "message": f"Mailgun connection test error: {str(e)}",
                        "provider": "mailgun",
                    }
            else:  # smtp
                # Test SMTP connection
                # Support both flat and nested config structures
                settings = config_data.get("settings", {})
                credentials = config_data.get("credentials", {})

                smtp_host = config_data.get("smtp_host") or settings.get("host")
                smtp_port = config_data.get("smtp_port") or settings.get("port", 587)
                smtp_username = config_data.get("smtp_username") or credentials.get("username")
                smtp_password = config_data.get("smtp_password") or credentials.get("password")

                use_tls = config_data.get("use_tls")
                if use_tls is None:
                    use_tls = settings.get("use_tls", True)

                logger.info(
                    f"Testing SMTP config - host: {smtp_host}, port: {smtp_port}, username: {smtp_username}, has_password: {bool(smtp_password)}"
                )

                if not smtp_host or not smtp_username or not smtp_password:
                    logger.error(
                        f"SMTP test configuration is incomplete - host: {smtp_host}, username: {smtp_username}, has_password: {bool(smtp_password)}"
                    )
                    return {"success": False, "message": "SMTP configuration is incomplete", "provider": "smtp"}

                # Try to connect — port 465 implies implicit SSL
                use_ssl = not use_tls and smtp_port == 465
                if use_tls:
                    server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
                    server.starttls()
                elif use_ssl:
                    server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
                else:
                    server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)

                server.login(smtp_username, smtp_password)
                server.quit()

                return {"success": True, "message": "SMTP connection successful", "provider": "smtp"}

        except Exception as e:
            logger.error(f"Email connection test failed: {str(e)}")
            return {"success": False, "message": f"Connection test failed: {str(e)}", "provider": provider_name}
