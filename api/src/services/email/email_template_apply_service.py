"""Email Template Apply Service.

Resolves an EmailTemplate record and applies it to outgoing email content.
Used by internal_send_email and internal_render_newsletter when an agent
has a template assigned.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_BUILTIN_NAMES = {"editorial", "minimal", "micromobility", "data-engineering"}


async def resolve_agent_email_template(
    agent_id: uuid.UUID,
    db: AsyncSession,
) -> dict[str, Any] | None:
    """Return a lightweight dict describing the agent's assigned template, or None."""
    from src.models.agent import Agent
    from src.models.email_template import EmailTemplate

    result = await db.execute(select(Agent.email_template_id).where(Agent.id == agent_id))
    template_id = result.scalar_one_or_none()
    if not template_id:
        return None

    result = await db.execute(
        select(EmailTemplate).where(EmailTemplate.id == template_id, EmailTemplate.is_active.is_(True))
    )
    tmpl = result.scalar_one_or_none()
    if not tmpl:
        return None

    return {
        "id": str(tmpl.id),
        "type": tmpl.template_type,
        "builtin_name": tmpl.builtin_name,
        "html_content": tmpl.html_content,
        "external_provider": tmpl.external_provider,
        "external_template_id": tmpl.external_template_id,
        "external_config": tmpl.external_config or {},
    }


async def apply_template_to_html(
    body_html: str,
    template: dict[str, Any],
    db: AsyncSession | None = None,
    tenant_id: uuid.UUID | None = None,
    subject: str | None = None,
) -> tuple[str, bool]:
    """Wrap body_html with the agent's assigned email template.

    Returns (rendered_html, was_applied) so the caller can skip
    the generic branding wrapper in Celery when a template was applied.

    Handles:
      - BUILTIN: renders via the named built-in layout (editorial / minimal)
      - CUSTOM_HTML: renders via Jinja2 with the stored HTML layout
      - Third-party types (SENDGRID, MAILCHIMP, BREVO): no-op, applied at delivery
    """
    from src.models.email_template import EmailTemplateType

    tmpl_type = template["type"]

    if tmpl_type == EmailTemplateType.BUILTIN:
        try:
            from src.services.email.email_template_service import EmailTemplateService

            builtin_name = template.get("builtin_name") or "editorial"
            svc = EmailTemplateService(db)
            rendered = await svc.wrap_content_for_builtin(
                builtin_name=builtin_name,
                content=body_html,
                subject=subject,
                tenant_id=tenant_id,
            )
            return rendered, True
        except Exception as exc:
            logger.warning(f"Failed to render builtin email template: {exc}")
            return body_html, False

    if tmpl_type == EmailTemplateType.CUSTOM_HTML:
        html_content: str | None = template.get("html_content")
        if not html_content:
            return body_html, False
        try:
            from jinja2 import Environment, Undefined

            env = Environment(undefined=Undefined)
            t = env.from_string(html_content)
            return t.render(body=body_html, content=body_html), True
        except Exception as exc:
            logger.warning(f"Failed to render custom email template: {exc}")
            return body_html, False

    # Third-party providers (SENDGRID, MAILCHIMP, BREVO) — template applied at delivery
    return body_html, False


def get_newsletter_template_name(template: dict[str, Any] | None) -> str | None:
    """Return the newsletter template name to use for internal_render_newsletter.

    For BUILTIN type returns the builtin_name ("editorial", "minimal", or "micromobility").
    For CUSTOM_HTML returns the html_content key so the tool can use it directly.
    Returns None for third-party types (handled at send time, not render time).
    """
    from src.models.email_template import EmailTemplateType

    if not template:
        return None

    if template["type"] == EmailTemplateType.BUILTIN:
        return template.get("builtin_name") or "editorial"

    if template["type"] == EmailTemplateType.CUSTOM_HTML:
        # Signal to newsletter_tools to use the stored HTML directly
        return "__custom__"

    return None  # SendGrid/Mailchimp/Brevo: template applied at delivery, not render
