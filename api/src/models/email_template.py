"""Email Template model.

Stores reusable email templates that can be assigned to agents.
Supports built-in, custom HTML, and third-party provider templates
(SendGrid, Mailchimp, Brevo).
"""

from enum import StrEnum

from sqlalchemy import JSON, Boolean, Column, ForeignKey, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, relationship

from .base import BaseModel


class EmailTemplateType(StrEnum):
    """Type of email template."""

    BUILTIN = "BUILTIN"  # Built-in Jinja2 template ("editorial", "minimal")
    CUSTOM_HTML = "CUSTOM_HTML"  # Raw HTML stored in DB; Jinja2 vars supported
    SENDGRID = "SENDGRID"  # SendGrid Dynamic Template ID
    MAILCHIMP = "MAILCHIMP"  # Mailchimp template ID
    BREVO = "BREVO"  # Brevo (Sendinblue) template ID


class EmailTemplate(BaseModel):
    """Email template record.

    Agents can be assigned one template. When the agent calls
    internal_send_email or internal_render_newsletter, this template
    is applied automatically (agents can still override per-call).
    """

    __tablename__ = "email_templates"

    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Owner tenant",
    )

    name = Column(String(100), nullable=False, comment="Human-readable template name")
    description = Column(String(500), nullable=True, comment="Optional description")

    template_type = Column(
        SQLEnum(EmailTemplateType),
        nullable=False,
        default=EmailTemplateType.BUILTIN,
        index=True,
        comment="Template type",
    )

    # --- Internal templates ---
    builtin_name = Column(
        String(50),
        nullable=True,
        comment="Built-in template name: 'editorial' or 'minimal'",
    )
    html_content = Column(
        Text,
        nullable=True,
        comment="Raw HTML content for CUSTOM_HTML templates (Jinja2 vars supported)",
    )

    # --- Third-party provider templates ---
    external_provider = Column(
        String(50),
        nullable=True,
        comment="Provider slug: sendgrid | mailchimp | brevo",
    )
    external_template_id = Column(
        String(200),
        nullable=True,
        comment="Template ID/name in the external provider system",
    )
    # JSON: {"integration_id": "uuid"} — points to Integration record for credentials
    external_config = Column(
        JSON,
        nullable=True,
        comment="Provider-specific config (integration_id, from_email, etc.)",
    )

    preview_html = Column(
        Text,
        nullable=True,
        comment="Cached preview HTML shown in the UI",
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Soft-disable without deleting",
    )

    # Relationships
    agents: Mapped[list["Agent"]] = relationship(
        "Agent",
        back_populates="email_template",
        foreign_keys="Agent.email_template_id",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<EmailTemplate id={self.id} name={self.name!r} type={self.template_type}>"
