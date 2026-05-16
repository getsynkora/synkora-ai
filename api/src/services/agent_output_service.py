"""
Agent Output Service.

This service handles sending agent responses to configured outputs
(Slack, Email, Webhook, etc.) and tracks delivery status.
"""

import logging
import traceback
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
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

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"channel": channel_id, "text": message, "unfurl_links": False, "unfurl_media": False},
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

        if not recipients:
            raise ValueError("No recipients specified")

        if not db:
            raise ValueError("Database session required for email delivery")

        from src.services.integrations.email_service import EmailService

        email_service = EmailService(db)
        results = []
        for recipient in recipients:
            result = await email_service.send_email(
                to_email=recipient,
                subject=subject,
                html_content=f"<p>{message}</p>" if not message.strip().startswith("<") else message,
                text_content=message,
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

        payload = {"message": message, "timestamp": datetime.now(UTC).isoformat()}

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

            if output_config.provider == OutputProvider.SLACK:
                result = await provider.send(oauth_app, output_config.config, formatted_output, slack_bot=slack_bot)
            elif output_config.provider == OutputProvider.EMAIL:
                result = await provider.send(
                    oauth_app,
                    output_config.config,
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
