"""Newsletter rendering service using Jinja2 templates."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import jinja2

logger = logging.getLogger(__name__)


class NewsletterRenderService:
    """Render newsletter data into production-quality HTML using Jinja2 templates."""

    TEMPLATE_DIR = Path(__file__).parent / "templates"

    def __init__(self) -> None:
        self._builtin_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.TEMPLATE_DIR)),
            autoescape=True,
        )

    def _get_template(
        self,
        template_name: str,
        custom_html: str | None = None,
    ) -> jinja2.Template:
        """Resolve a Jinja2 template from a built-in name or custom HTML string."""
        if custom_html:
            env = jinja2.Environment(autoescape=True)
            return env.from_string(custom_html)
        fname = template_name if template_name.endswith(".html") else f"{template_name}.html"
        return self._builtin_env.get_template(fname)

    def render(
        self,
        data: dict[str, Any],
        edition: int = 1,
        pdf_url: str | None = None,
        image_url: str | None = None,
        width: int = 680,
        template: str = "editorial",
        custom_template_html: str | None = None,
    ) -> str:
        """Render newsletter data to HTML.

        Args:
            data: Structured newsletter payload (hackernews, rss_news, github_trending, etc.)
            edition: Edition number shown in masthead.
            pdf_url: Presigned URL for the generated PDF, injected into footer.
            image_url: Presigned URL for the OG share image, injected into footer.
            width: Container width in px (680 for email, 1200 for PDF/OG image).
            template: Built-in template name ("editorial", "minimal", or "micromobility") or custom name.
            custom_template_html: Raw Jinja2 HTML string for tenant-uploaded templates.

        Returns:
            Rendered HTML string.
        """
        tmpl = self._get_template(template, custom_template_html)

        hn = data.get("hackernews") or []
        rss = data.get("rss_news") or []

        # Lead story: highest-scoring HN item, fallback to first RSS item
        lead: dict[str, Any] = {}
        if hn:
            lead = max(hn, key=lambda x: x.get("score", 0))
        elif rss:
            lead = rss[0]

        # Merge + deduplicate remaining news items (exclude lead)
        seen_urls: set[str | None] = {lead.get("url")}
        news_items: list[dict] = []
        for item in hn + rss:
            url = item.get("url")
            if url not in seen_urls and len(news_items) < 8:
                seen_urls.add(url)
                news_items.append(item)

        # Human-readable date
        date_str = data.get("date", "")
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            date_str = dt.strftime("%A, %B %-d, %Y")
        except Exception:
            pass  # keep raw string if unparseable

        return tmpl.render(
            date=date_str,
            edition=f"Vol. {edition}",
            container_width=width,
            lead_headline=lead.get("title", ""),
            lead_summary=lead.get("summary", lead.get("title", "")),
            lead_why_it_matters=data.get("lead_why_it_matters", ""),
            lead_url=lead.get("url", lead.get("hn_url", "#")),
            lead_source=lead.get("source", "Hacker News"),
            lead_image_url=lead.get("image_url") or data.get("lead_image_url"),
            news_items=news_items,
            github_items=(data.get("github_trending") or [])[:8],
            papers=(data.get("papers") or [])[:6],
            products=(data.get("producthunt") or [])[:4],
            youtube_items=(data.get("youtube") or []),
            twitter=data.get("twitter"),
            editors_take=data.get("editors_take", ""),
            pdf_url=pdf_url,
            image_url=image_url,
        )
