"""
Email Template Service

Provides branded, responsive email templates.
Branding is loaded from platform settings or can be overridden.

Built-in wrapper layouts live as Jinja2 HTML files under the ``wrappers/``
sub-directory.  Adding a new layout only requires dropping a new file there —
no Python code changes needed.  The file must accept these template variables:

    {{ content }}         — agent-generated HTML (injected verbatim)
    {{ subject }}         — email subject line
    {{ platform_name }}   — from EmailBranding
    {{ logo_url }}        — from EmailBranding (may be empty)
    {{ primary_color }}   — hex colour string
    {{ secondary_color }} — hex colour string
    {{ footer_text }}     — computed footer text
    {{ support_email }}   — from EmailBranding (may be empty)
"""

import logging
from dataclasses import dataclass, replace
from pathlib import Path
from uuid import UUID

import jinja2
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class EmailBranding:
    """Email branding configuration."""

    platform_name: str = "Synkora"
    logo_url: str | None = None
    primary_color: str = "#2d8b69"
    secondary_color: str = "#171717"
    accent_color: str = "#f0c56d"
    background_color: str = "#fcfaf5"
    text_color: str = "#171717"
    support_email: str | None = None
    footer_text: str | None = None


class EmailTemplateService:
    """Service for wrapping email content in branded templates."""

    WRAPPERS_DIR = Path(__file__).parent / "wrappers"

    def __init__(self, db: AsyncSession | None = None):
        self.db = db
        self._wrapper_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.WRAPPERS_DIR)),
            autoescape=False,  # content is trusted internal HTML
        )

    def _branding_for_builtin(self, builtin_name: str, branding: EmailBranding) -> EmailBranding:
        """Return builtin-specific branding overrides when needed."""
        if builtin_name == "micromobility":
            return replace(
                branding,
                platform_name="OTORIDE",
                logo_url=None,
                primary_color="#44b889",
                secondary_color="#102128",
                accent_color="#8fdab9",
                background_color="#eef4ef",
                text_color="#102128",
                support_email=None,
                footer_text="Delivered by OTORIDE shared mobility platform.",
            )

        return branding

    async def get_branding(self, tenant_id: UUID | None = None) -> EmailBranding:
        """
        Get branding configuration from platform settings.

        Args:
            tenant_id: Optional tenant ID for tenant-specific branding (future)

        Returns:
            EmailBranding configuration
        """
        branding = EmailBranding()

        if not self.db:
            return branding

        try:
            from src.models.platform_settings import PlatformSettings

            result = await self.db.execute(select(PlatformSettings))
            settings = result.scalar_one_or_none()
            if settings:
                if settings.platform_name:
                    branding.platform_name = settings.platform_name
                if settings.platform_logo_url:
                    branding.logo_url = settings.platform_logo_url
                if settings.support_email:
                    branding.support_email = settings.support_email
                if hasattr(settings, "primary_color") and settings.primary_color:
                    branding.primary_color = settings.primary_color
                if hasattr(settings, "secondary_color") and settings.secondary_color:
                    branding.secondary_color = settings.secondary_color

        except Exception as e:
            logger.warning(f"Failed to load branding from settings: {e}")

        return branding

    async def wrap_content(
        self,
        content: str,
        subject: str | None = None,
        branding: EmailBranding | None = None,
        tenant_id: UUID | None = None,
    ) -> str:
        """
        Wrap email content in a branded, responsive template.
        Warm editorial email wrapper aligned with the newer platform design system.

        Args:
            content: HTML content to wrap
            subject: Optional subject to show as header
            branding: Optional branding override
            tenant_id: Optional tenant ID for tenant-specific branding

        Returns:
            Complete HTML email with branding
        """
        if branding is None:
            branding = await self.get_branding(tenant_id)

        # Build logo HTML with a restrained editorial treatment.
        logo_html = ""
        if branding.logo_url:
            logo_html = f'''
            <img src="{branding.logo_url}" alt="{branding.platform_name}"
                 style="max-height: 40px; max-width: 160px;">
            '''
        else:
            logo_html = f"""
            <span style="font-family: Georgia, 'Times New Roman', serif; font-size: 28px; letter-spacing: -0.5px;">
                <span style="font-weight: 700; color: {branding.secondary_color};">{branding.platform_name}</span>
                <span style="font-weight: 400; color: #5f584f;"> Platform Brief</span>
            </span>
            """

        # Build footer
        footer_text = branding.footer_text or f"Sent by {branding.platform_name}"
        support_html = ""
        if branding.support_email:
            support_html = f"""
            <span style="color: #757575;"> · </span>
            <a href="mailto:{branding.support_email}" style="color: #757575; text-decoration: underline;">Contact Support</a>
            """

        template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <title>{subject or branding.platform_name}</title>
    <!--[if mso]>
    <style type="text/css">
        body, table, td {{font-family: Arial, sans-serif !important;}}
    </style>
    <![endif]-->
</head>
<body style="margin: 0; padding: 0; background-color: #ffffff; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif; -webkit-font-smoothing: antialiased; color: #292929;">
    <!-- Wrapper -->
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #ffffff;">
        <tr>
            <td align="center" style="padding: 0;">

                <!-- Main Container -->
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width: 600px;">

                    <!-- Header -->
                    <tr>
                        <td style="padding: 32px 20px 24px 20px;">
                            {logo_html}
                        </td>
                    </tr>

                    <!-- Section Divider -->
                    <tr>
                        <td style="padding: 0 20px;">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td style="border-bottom: 1px solid #e6e6e6; padding-bottom: 8px;">
                                        <span style="font-size: 12px; font-weight: 600; color: #757575; text-transform: uppercase; letter-spacing: 0.5px;">Platform Update</span>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 24px 20px 32px 20px;">
                            <style>
                                /* Typography */
                                h1 {{ font-family: Georgia, 'Times New Roman', serif; font-size: 22px; font-weight: 700; line-height: 1.3; color: #292929; margin: 0 0 8px 0; letter-spacing: -0.3px; }}
                                h2 {{ font-family: Georgia, 'Times New Roman', serif; font-size: 20px; font-weight: 700; line-height: 1.3; color: #292929; margin: 32px 0 8px 0; letter-spacing: -0.3px; }}
                                h3 {{ font-family: Georgia, 'Times New Roman', serif; font-size: 18px; font-weight: 700; line-height: 1.3; color: #292929; margin: 24px 0 6px 0; }}
                                p {{ margin: 0 0 16px 0; font-size: 16px; line-height: 1.6; color: #505050; }}
                                a {{ color: {branding.secondary_color}; text-decoration: none; }}
                                a:hover {{ text-decoration: underline; }}
                                strong, b {{ font-weight: 700; color: #292929; }}

                                /* Lists */
                                ul, ol {{ padding-left: 20px; margin: 0 0 16px 0; }}
                                li {{ margin-bottom: 12px; font-size: 16px; line-height: 1.5; color: #505050; }}

                                /* Article Card Style */
                                .article-card {{
                                    padding: 20px 0;
                                    border-bottom: 1px solid #e6e6e6;
                                }}
                                .article-card:last-child {{
                                    border-bottom: none;
                                }}
                                .article-meta {{
                                    font-size: 13px;
                                    color: #757575;
                                    margin-bottom: 6px;
                                }}
                                .article-title {{
                                    font-family: Georgia, 'Times New Roman', serif;
                                    font-size: 20px;
                                    font-weight: 700;
                                    line-height: 1.3;
                                    color: #292929;
                                    margin: 0 0 6px 0;
                                    letter-spacing: -0.3px;
                                }}
                                .article-excerpt {{
                                    font-size: 15px;
                                    line-height: 1.5;
                                    color: #757575;
                                    margin: 0 0 10px 0;
                                }}
                                .article-stats {{
                                    font-size: 13px;
                                    color: #757575;
                                }}
                                .article-stats span {{
                                    margin-right: 12px;
                                }}

                                /* Source/Author badge */
                                .source-badge {{
                                    display: inline-block;
                                    font-size: 13px;
                                    color: #757575;
                                    margin-bottom: 8px;
                                }}
                                .source-badge a {{
                                    color: #292929;
                                    font-weight: 500;
                                }}

                                /* Plus/Save icon style */
                                .plus-icon {{
                                    display: inline-block;
                                    width: 20px;
                                    height: 20px;
                                    border: 1px solid #e6e6e6;
                                    border-radius: 50%;
                                    text-align: center;
                                    line-height: 18px;
                                    font-size: 14px;
                                    color: {branding.primary_color};
                                    margin-right: 8px;
                                    vertical-align: middle;
                                }}

                                /* Category/Tag */
                                .category {{
                                    display: inline-block;
                                    font-size: 12px;
                                    color: #757575;
                                    background: #f2f2f2;
                                    padding: 3px 8px;
                                    border-radius: 3px;
                                    margin-right: 6px;
                                }}

                                /* Highlight box */
                                .highlight {{
                                    background: #fafafa;
                                    border-left: 3px solid {branding.primary_color};
                                    padding: 16px 20px;
                                    margin: 20px 0;
                                }}
                                .highlight p {{
                                    margin: 0;
                                    color: #505050;
                                }}

                                /* Divider */
                                hr {{
                                    border: none;
                                    border-top: 1px solid #e6e6e6;
                                    margin: 24px 0;
                                }}

                                /* Read time style */
                                .read-time {{
                                    color: #757575;
                                    font-size: 13px;
                                }}
                            </style>
                            {content}
                        </td>
                    </tr>

                    <!-- CTA Section -->
                    <tr>
                        <td style="padding: 0 20px 32px 20px; text-align: center;">
                            <p style="font-size: 15px; color: #505050; margin: 0 0 16px 0;">Open your workspace to review agents, workflows, and the latest changes.</p>
                            <a href="#" style="display: inline-block; background-color: {branding.primary_color}; color: #ffffff; padding: 12px 24px; border-radius: 20px; font-size: 14px; font-weight: 500; text-decoration: none;">
                                Open workspace
                            </a>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #292929; padding: 24px 20px;">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td style="text-align: center; padding-bottom: 16px;">
                                        <span style="font-family: Georgia, 'Times New Roman', serif; font-size: 18px; font-weight: 700; color: #ffffff;">{branding.platform_name}</span>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="text-align: center;">
                                        <span style="font-size: 12px; color: #757575;">
                                            {footer_text}
                                            {support_html}
                                        </span>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="text-align: center; padding-top: 16px;">
                                        <a href="#" style="font-size: 12px; color: #757575; text-decoration: underline;">Unsubscribe</a>
                                        <span style="color: #757575;"> · </span>
                                        <a href="#" style="font-size: 12px; color: #757575; text-decoration: underline;">Privacy Policy</a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                </table>
                <!-- /Main Container -->

            </td>
        </tr>
    </table>
    <!-- /Wrapper -->
</body>
</html>"""

        return template

    async def wrap_content_for_builtin(
        self,
        builtin_name: str,
        content: str,
        subject: str | None = None,
        branding: EmailBranding | None = None,
        tenant_id: UUID | None = None,
    ) -> str:
        """Render content using a file-based Jinja2 wrapper layout.

        Looks for ``wrappers/{builtin_name}.html``.  Falls back to
        ``wrappers/editorial.html`` when the requested file does not exist so
        that unknown names never cause a hard failure.

        Adding a new built-in layout requires only dropping a new HTML file in
        the ``wrappers/`` directory — no Python code changes needed.
        """
        if branding is None:
            branding = await self.get_branding(tenant_id)
        branding = self._branding_for_builtin(builtin_name, branding)

        fname = f"{builtin_name}.html"
        if not (self.WRAPPERS_DIR / fname).exists():
            logger.warning("Email wrapper '%s' not found, falling back to editorial", fname)
            fname = "editorial.html"

        tmpl = self._wrapper_env.get_template(fname)
        return tmpl.render(
            content=content,
            subject=subject or branding.platform_name,
            platform_name=branding.platform_name,
            logo_url=branding.logo_url or "",
            primary_color=branding.primary_color,
            secondary_color=branding.secondary_color,
            footer_text=branding.footer_text or f"Sent by {branding.platform_name}",
            support_email=branding.support_email or "",
        )

    async def create_notification_email(
        self,
        title: str,
        message: str,
        cta_text: str | None = None,
        cta_url: str | None = None,
        branding: EmailBranding | None = None,
        tenant_id: UUID | None = None,
    ) -> str:
        """
        Create a simple notification email with optional CTA button.

        Args:
            title: Email title/heading
            message: Main message content
            cta_text: Optional call-to-action button text
            cta_url: Optional call-to-action button URL
            branding: Optional branding override
            tenant_id: Optional tenant ID

        Returns:
            Complete HTML email
        """
        if branding is None:
            branding = await self.get_branding(tenant_id)

        cta_html = ""
        if cta_text and cta_url:
            cta_html = f'''
            <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin: 28px 0 8px 0;">
                <tr>
                    <td style="background: linear-gradient(135deg, {branding.primary_color} 0%, {branding.secondary_color} 100%); border-radius: 8px; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);">
                        <a href="{cta_url}" target="_blank"
                           style="display: inline-block; padding: 14px 32px; color: #ffffff; text-decoration: none; font-weight: 600; font-size: 15px; letter-spacing: 0.3px;">
                            {cta_text}
                        </a>
                    </td>
                </tr>
            </table>
            '''

        content = f"""
        <h1 style="margin: 0 0 20px 0; font-size: 26px; font-weight: 700; color: {branding.secondary_color}; font-family: Georgia, 'Times New Roman', serif; letter-spacing: -0.5px;">
            {title}
        </h1>
        <p style="margin: 0 0 16px 0; color: #4b5563; line-height: 1.7;">
            {message}
        </p>
        {cta_html}
        """

        return await self.wrap_content(content, subject=title, branding=branding)
