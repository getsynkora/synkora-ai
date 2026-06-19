"""
Agent Output Service.

This service handles sending agent responses to configured outputs
(Slack, Email, Webhook, etc.) and tracks delivery status.
"""

import logging
import re
import traceback
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
import markdown as md_lib
from jinja2.sandbox import SandboxedEnvironment
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import (
    AgentOutputConfig,
    AgentOutputDelivery,
    DeliveryStatus,
    OAuthApp,
    OutputProvider,
)
from src.models.slack_bot import SlackBot
from src.services.agents.security import decrypt_value
from src.services.slack.formatters import create_slack_blocks, format_text_for_slack

logger = logging.getLogger(__name__)


class OutputFormatter:
    """Formats agent responses using templates."""

    # SECURITY: Use SandboxedEnvironment to prevent template injection attacks
    _sandbox_env = SandboxedEnvironment(
        autoescape=True,  # Auto-escape HTML by default
    )

    @staticmethod
    def format_output(template: str | None, agent_response: str, context: dict[str, Any]) -> str:
        """
        Format output using Jinja2 sandboxed template.

        SECURITY: Uses SandboxedEnvironment to prevent Server-Side Template Injection (SSTI).
        This prevents attackers from accessing Python objects or executing arbitrary code.

        Args:
            template: Jinja2 template string (optional)
            agent_response: Raw agent response
            context: Additional context variables

        Returns:
            Formatted output string
        """
        if not template:
            return agent_response

        try:
            # SECURITY: Use sandboxed environment instead of direct Template instantiation
            jinja_template = OutputFormatter._sandbox_env.from_string(template)
            return jinja_template.render(response=agent_response, **context)
        except Exception as e:
            logger.error(f"Template formatting error: {e}")
            return agent_response


def _markdown_to_html(text: str) -> str:
    """Convert markdown text to HTML using the markdown library."""
    return md_lib.markdown(
        text,
        extensions=["tables", "fenced_code", "nl2br", "sane_lists"],
    )


def _build_agent_email_html(body_html: str, agent_name: str = "Agent", subject: str = "Agent Report") -> str:
    """Wrap rendered HTML content in a styled email template."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{subject}</title>
  <style>
    body {{ margin:0; padding:0; background:#f3f4f6; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; color:#111827; line-height:1.6; }}
    .wrap {{ width:100%; background:#f3f4f6; padding:40px 20px; }}
    .card {{ max-width:640px; margin:0 auto; background:#ffffff; border-radius:12px; overflow:hidden; box-shadow:0 4px 6px rgba(0,0,0,0.07); }}
    .header {{ background:linear-gradient(135deg,#1a1a1a 0%,#2d2d2d 100%); padding:32px 40px; }}
    .header-label {{ font-size:11px; font-weight:600; letter-spacing:.15em; text-transform:uppercase; color:#9ca3af; margin-bottom:6px; }}
    .header-title {{ font-size:20px; font-weight:700; color:#ffffff; }}
    .body {{ padding:32px 40px; }}
    .body h1,.body h2 {{ font-size:18px; font-weight:700; color:#111827; margin:24px 0 8px; border-bottom:1px solid #e5e7eb; padding-bottom:6px; }}
    .body h3,.body h4 {{ font-size:15px; font-weight:600; color:#374151; margin:20px 0 6px; }}
    .body p {{ margin:0 0 14px; font-size:14px; color:#374151; }}
    .body ul,.body ol {{ margin:0 0 14px; padding-left:20px; font-size:14px; color:#374151; }}
    .body li {{ margin-bottom:4px; }}
    .body table {{ width:100%; border-collapse:collapse; margin:16px 0; font-size:13px; }}
    .body th {{ background:#f9fafb; text-align:left; padding:8px 12px; border:1px solid #e5e7eb; font-weight:600; color:#111827; }}
    .body td {{ padding:8px 12px; border:1px solid #e5e7eb; color:#374151; }}
    .body tr:nth-child(even) td {{ background:#f9fafb; }}
    .body code {{ background:#f3f4f6; border-radius:4px; padding:2px 5px; font-family:monospace; font-size:12px; color:#1f2937; }}
    .body pre {{ background:#1f2937; color:#e5e7eb; border-radius:8px; padding:16px; overflow-x:auto; margin:16px 0; }}
    .body pre code {{ background:none; padding:0; color:inherit; font-size:13px; }}
    .body blockquote {{ border-left:3px solid #d1d5db; padding-left:12px; margin:14px 0; color:#6b7280; font-style:italic; }}
    .body hr {{ border:none; border-top:1px solid #e5e7eb; margin:24px 0; }}
    .footer {{ background:#f9fafb; border-top:1px solid #e5e7eb; padding:20px 40px; text-align:center; font-size:12px; color:#9ca3af; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <div class="header">
        <div class="header-label">Agent Output</div>
        <div class="header-title">{agent_name}</div>
      </div>
      <div class="body">
        {body_html}
      </div>
      <div class="footer">Generated by {agent_name}</div>
    </div>
  </div>
</body>
</html>"""


class SlackOutputProvider:
    """Sends outputs to Slack channels."""

    @staticmethod
    async def send(
        oauth_app: OAuthApp | None, config: dict[str, Any], message: str, slack_bot: SlackBot | None = None
    ) -> dict[str, Any]:
        """
        Send message to Slack channel.

        Args:
            oauth_app: OAuth app with Slack credentials (or None if using slack_bot)
            config: Channel configuration {"channel": "#general"} or {"channel_id": "C123"}
            message: Message to send
            slack_bot: SlackBot with encrypted bot token (alternative to oauth_app)

        Returns:
            Response from Slack API
        """
        if slack_bot is not None:
            # Use Slack bot token (xoxb-*)
            raw_token = slack_bot.slack_bot_token
            try:
                token = decrypt_value(raw_token)
            except Exception:
                token = raw_token  # Already decrypted or plaintext
        elif oauth_app is not None:
            if oauth_app.auth_method == "api_token":
                token = oauth_app.api_token
            else:
                token = oauth_app.access_token
        else:
            raise ValueError("Either oauth_app or slack_bot must be provided")

        if not token:
            raise ValueError("No Slack token available")

        channel_id = config.get("channel_id")
        if not channel_id:
            raise ValueError("No channel_id in config")

        blocks = create_slack_blocks(message)
        # Plain-text fallback for notifications/accessibility
        fallback_text = format_text_for_slack(message)[:150].strip()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={
                    "channel": channel_id,
                    "blocks": blocks,
                    "text": fallback_text,
                    "unfurl_links": False,
                    "unfurl_media": False,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            if not data.get("ok"):
                raise Exception(f"Slack API error: {data.get('error')}")

            return {"success": True, "message_ts": data.get("ts"), "channel": data.get("channel")}


class EmailOutputProvider:
    """Sends outputs via email."""

    @staticmethod
    async def send(
        oauth_app: OAuthApp | None,
        config: dict[str, Any],
        message: str,
        db: AsyncSession | None = None,
        tenant_id: UUID | None = None,
    ) -> dict[str, Any]:
        """
        Send email using the configured email integration.

        Args:
            oauth_app: Not used (email uses integration config)
            config: Email configuration {"recipients": [...], "subject_template": "..."}
            message: Message body (HTML or plain text)
            db: Database session for loading integration config
            tenant_id: Tenant ID for scoping integration config

        Returns:
            Response dict
        """
        recipients = config.get("recipients", [])
        subject = config.get("subject_template", "Agent Response")
        agent_name = config.get("agent_name", "Agent")
        agent_id = config.get("agent_id")
        tenant_id_str = config.get("tenant_id")

        if not recipients:
            raise ValueError("No recipients specified")

        if not db:
            raise ValueError("Database session required for email delivery")

        # Convert message to HTML (markdown → HTML)
        body_html = message if message.strip().startswith("<") else _markdown_to_html(message)

        # Try to use the agent's assigned EmailTemplate first
        html_content = None
        if agent_id and db:
            try:
                from src.services.email.email_template_apply_service import (
                    apply_template_to_html,
                    resolve_agent_email_template,
                )

                tid = UUID(tenant_id_str) if tenant_id_str else None
                tmpl = await resolve_agent_email_template(UUID(agent_id), db)
                if tmpl:
                    html_content, _ = await apply_template_to_html(
                        body_html, tmpl, db=db, tenant_id=tid, subject=subject
                    )
            except Exception as exc:
                logger.warning(f"Failed to apply agent email template: {exc}")

        # Fallback: wrap in our generic styled agent output template
        if not html_content:
            html_content = _build_agent_email_html(body_html, agent_name=agent_name, subject=subject)

        # Plain-text fallback for email clients that don't render HTML
        plain_text = re.sub(r"<[^>]+>", "", re.sub(r"[#*_~`>]", "", message)).strip()

        from src.services.integrations.email_service import EmailService

        email_service = EmailService(db)
        results = []
        for recipient in recipients:
            result = await email_service.send_email(
                to_email=recipient,
                subject=subject,
                html_content=html_content,
                text_content=plain_text,
                tenant_id=tenant_id,
            )
            results.append(result)

        return {
            "success": True,
            "recipients": recipients,
            "results": results,
            "message_id": f"email_{datetime.now(UTC).timestamp()}",
        }


class WebhookOutputProvider:
    """Sends outputs to webhook URLs."""

    @staticmethod
    async def send(oauth_app: OAuthApp | None, config: dict[str, Any], message: str) -> dict[str, Any]:
        """
        Send webhook request.

        Args:
            oauth_app: OAuth app (not used for webhooks)
            config: Webhook configuration {"url": "...", "headers": {...}, "method": "POST"}
            message: Message to send

        Returns:
            Response from webhook endpoint
        """
        url = config.get("url")
        if not url:
            raise ValueError("No webhook URL specified")

        method = config.get("method", "POST").upper()
        headers = config.get("headers", {})

        # Build a rich structured payload with multiple format options so
        # the receiving end can use whatever fits best.
        plain_text = re.sub(r"[#*_~`>]", "", message).strip()
        html_body = _markdown_to_html(message)

        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "message": {
                "markdown": message,
                "plain_text": plain_text,
                "html": html_body,
            },
        }

        async with httpx.AsyncClient() as client:
            response = await client.request(method, url, json=payload, headers=headers, timeout=30.0)
            response.raise_for_status()

            return {
                "success": True,
                "status_code": response.status_code,
                "response_body": response.text[:500],  # Truncate for storage
            }


class DiscordOutputProvider:
    """Sends outputs to Discord channels via webhooks."""

    @staticmethod
    async def send(oauth_app: OAuthApp | None, config: dict[str, Any], message: str) -> dict[str, Any]:
        """
        Send message to Discord channel via webhook URL.

        Args:
            oauth_app: Not used
            config: {"webhook_url": "https://discord.com/api/webhooks/..."}
            message: Message to send
        """
        webhook_url = config.get("webhook_url")
        if not webhook_url:
            raise ValueError("No Discord webhook_url in config")

        username = config.get("username", "Agent")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                webhook_url,
                json={"content": message[:2000], "username": username},  # Discord 2000 char limit
                timeout=30.0,
            )
            response.raise_for_status()
            return {"success": True, "status_code": response.status_code}


class MSTeamsOutputProvider:
    """Sends outputs to MS Teams channels via incoming webhooks."""

    @staticmethod
    async def send(oauth_app: OAuthApp | None, config: dict[str, Any], message: str) -> dict[str, Any]:
        """
        Send Adaptive Card message to MS Teams channel.

        Args:
            oauth_app: Not used
            config: {"webhook_url": "https://...webhook.office.com/..."}
            message: Message to send
        """
        webhook_url = config.get("webhook_url")
        if not webhook_url:
            raise ValueError("No MS Teams webhook_url in config")

        payload = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.2",
                        "body": [{"type": "TextBlock", "text": message, "wrap": True}],
                    },
                }
            ],
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(webhook_url, json=payload, timeout=30.0)
            response.raise_for_status()
            return {"success": True, "status_code": response.status_code}


class AgentOutputService:
    """Main service for handling agent outputs."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.providers = {
            OutputProvider.SLACK: SlackOutputProvider(),
            OutputProvider.EMAIL: EmailOutputProvider(),
            OutputProvider.WEBHOOK: WebhookOutputProvider(),
            OutputProvider.DISCORD: DiscordOutputProvider(),
            OutputProvider.MS_TEAMS: MSTeamsOutputProvider(),
        }

    async def get_enabled_outputs(self, agent_id: UUID, trigger_type: str = "webhook") -> list[AgentOutputConfig]:
        """
        Get enabled output configurations for an agent.

        Args:
            agent_id: Agent UUID
            trigger_type: "webhook" or "chat"

        Returns:
            List of enabled output configurations
        """
        stmt = select(AgentOutputConfig).filter(AgentOutputConfig.agent_id == agent_id, AgentOutputConfig.is_enabled)

        if trigger_type == "webhook":
            stmt = stmt.filter(AgentOutputConfig.send_on_webhook_trigger)
        elif trigger_type == "chat":
            stmt = stmt.filter(AgentOutputConfig.send_on_chat_completion)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def send_outputs(
        self,
        agent_id: UUID,
        agent_response: str,
        context: dict[str, Any],
        webhook_event_id: UUID | None = None,
        trigger_type: str = "webhook",
    ) -> list[AgentOutputDelivery]:
        """
        Send agent response to all configured outputs.

        Args:
            agent_id: Agent UUID
            agent_response: Raw agent response text
            context: Additional context (agent_name, event_type, etc.)
            webhook_event_id: Optional webhook event that triggered this
            trigger_type: "webhook" or "chat"

        Returns:
            List of delivery records
        """
        outputs = await self.get_enabled_outputs(agent_id, trigger_type)
        deliveries = []

        for output_config in outputs:
            delivery = await self._send_single_output(output_config, agent_response, context, webhook_event_id)
            deliveries.append(delivery)

        return deliveries

    async def _send_single_output(
        self,
        output_config: AgentOutputConfig,
        agent_response: str,
        context: dict[str, Any],
        webhook_event_id: UUID | None = None,
    ) -> AgentOutputDelivery:
        """
        Send to a single output destination.

        Args:
            output_config: Output configuration
            agent_response: Raw agent response
            context: Context for template rendering
            webhook_event_id: Optional webhook event ID

        Returns:
            Delivery record
        """
        # Create delivery record
        delivery = AgentOutputDelivery(
            output_config_id=output_config.id,
            agent_id=output_config.agent_id,
            tenant_id=output_config.tenant_id,
            webhook_event_id=webhook_event_id,
            provider=output_config.provider,
            raw_response=agent_response,
            status=DeliveryStatus.PENDING,
        )
        self.db.add(delivery)
        await self.db.flush()

        try:
            # Format output
            formatted_output = OutputFormatter.format_output(output_config.output_template, agent_response, context)
            delivery.formatted_output = formatted_output

            # Update status to sending
            delivery.status = DeliveryStatus.SENDING
            delivery.attempt_count += 1
            delivery.last_attempt_at = datetime.now(UTC)
            await self.db.flush()

            # Get OAuth app if needed
            oauth_app = None
            if output_config.oauth_app_id:
                result = await self.db.execute(select(OAuthApp).filter(OAuthApp.id == output_config.oauth_app_id))
                oauth_app = result.scalar_one_or_none()

            # Get Slack bot if needed
            slack_bot = None
            if output_config.slack_bot_id:
                result = await self.db.execute(select(SlackBot).filter(SlackBot.id == output_config.slack_bot_id))
                slack_bot = result.scalar_one_or_none()

            # Send to provider
            provider = self.providers.get(output_config.provider)
            if not provider:
                raise ValueError(f"Unknown provider: {output_config.provider}")

            # Merge runtime fields into email config
            email_config = {
                **output_config.config,
                "agent_name": context.get("agent_name", "Agent"),
                "agent_id": str(output_config.agent_id),
                "tenant_id": str(output_config.tenant_id),
            }

            if output_config.provider == OutputProvider.SLACK:
                result = await provider.send(oauth_app, output_config.config, formatted_output, slack_bot=slack_bot)
            elif output_config.provider == OutputProvider.EMAIL:
                result = await provider.send(
                    oauth_app,
                    email_config,
                    formatted_output,
                    db=self.db,
                    tenant_id=output_config.tenant_id,
                )
            else:
                result = await provider.send(oauth_app, output_config.config, formatted_output)

            # Update delivery as successful
            delivery.status = DeliveryStatus.DELIVERED
            delivery.delivered_at = datetime.now(UTC)
            delivery.provider_response = result
            delivery.provider_message_id = result.get("message_id") or result.get("message_ts")

        except Exception as e:
            # Update delivery as failed
            delivery.status = DeliveryStatus.FAILED
            delivery.error_message = str(e)
            delivery.error_details = {"traceback": traceback.format_exc(), "error_type": type(e).__name__}
            logger.error(f"Output delivery failed: {e}", exc_info=True)

        await self.db.commit()
        return delivery

    async def retry_failed_delivery(self, delivery_id: UUID) -> AgentOutputDelivery:
        """
        Retry a failed delivery.

        Args:
            delivery_id: Delivery UUID

        Returns:
            Updated delivery record
        """
        result = await self.db.execute(select(AgentOutputDelivery).filter(AgentOutputDelivery.id == delivery_id))
        delivery = result.scalar_one_or_none()
        if not delivery:
            raise ValueError(f"Delivery {delivery_id} not found")

        output_config = delivery.output_config

        if delivery.attempt_count >= output_config.max_retries:
            raise ValueError(f"Max retries ({output_config.max_retries}) exceeded")

        # Retry the delivery
        delivery.status = DeliveryStatus.RETRYING
        await self.db.flush()

        try:
            delivery.attempt_count += 1
            delivery.last_attempt_at = datetime.now(UTC)

            # Get OAuth app if needed
            oauth_app = None
            if output_config.oauth_app_id:
                result = await self.db.execute(select(OAuthApp).filter(OAuthApp.id == output_config.oauth_app_id))
                oauth_app = result.scalar_one_or_none()

            # Get Slack bot if needed
            slack_bot = None
            if output_config.slack_bot_id:
                result = await self.db.execute(select(SlackBot).filter(SlackBot.id == output_config.slack_bot_id))
                slack_bot = result.scalar_one_or_none()

            # Send to provider
            provider = self.providers.get(output_config.provider)
            if output_config.provider == OutputProvider.SLACK:
                result = await provider.send(
                    oauth_app, output_config.config, delivery.formatted_output, slack_bot=slack_bot
                )
            elif output_config.provider == OutputProvider.EMAIL:
                result = await provider.send(
                    oauth_app,
                    output_config.config,
                    delivery.formatted_output,
                    db=self.db,
                    tenant_id=output_config.tenant_id,
                )
            else:
                result = await provider.send(oauth_app, output_config.config, delivery.formatted_output)

            # Update as successful
            delivery.status = DeliveryStatus.DELIVERED
            delivery.delivered_at = datetime.now(UTC)
            delivery.provider_response = result
            delivery.provider_message_id = result.get("message_id") or result.get("message_ts")

        except Exception as e:
            delivery.status = DeliveryStatus.FAILED
            delivery.error_message = str(e)
            delivery.error_details = {"traceback": traceback.format_exc(), "error_type": type(e).__name__}
            logger.error(f"Retry delivery failed: {e}", exc_info=True)

        await self.db.commit()
        return delivery
