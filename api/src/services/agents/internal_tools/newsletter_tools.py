"""Newsletter rendering tool for autonomous agents.

The agent provides structured JSON (gathered by a sibling gatherer agent);
this tool renders it to production-quality HTML using a fixed Jinja2 template,
generates a PDF and an OG share image via the scraper service, uploads both to
S3, and returns the final email HTML ready to pass to internal_send_email.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import uuid
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_MAX_JSON_BYTES = 512 * 1024  # 512 KB


async def internal_render_newsletter(
    newsletter_json: str,
    edition: int = 1,
    template: str = "editorial",
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Render a newsletter from structured JSON into production-quality HTML.

    Accepts the JSON payload produced by the gatherer agent, enriches it with
    OG images fetched in parallel, renders it with the editorial Jinja2 template,
    optionally generates a PDF and a 1200x630 OG share image via Playwright, and
    returns the final HTML plus S3 URLs for the PDF and share image.

    Args:
        newsletter_json:
            JSON string with keys: date, hackernews, rss_news, github_trending,
            papers, producthunt, youtube, twitter, lead_why_it_matters,
            editors_take.
        edition:
            Edition/volume number shown in the masthead.
        template:
            Built-in template name ("editorial" or "minimal") OR an S3 key
            under ``newsletter-templates/{tenant_id}/`` for a tenant-uploaded
            custom template.
        config:
            Runtime tool config injected by adk_tools.py.  Contains tenant_id
            and _runtime_context.

    Returns:
        ``{"success": True, "html": ..., "pdf_url": ..., "image_url": ..., "subject": ...}``
        or ``{"success": False, "error": ...}``.
    """
    if len(newsletter_json.encode()) > _MAX_JSON_BYTES:
        return {"success": False, "error": "newsletter_json too large (max 512 KB)"}

    try:
        data: dict[str, Any] = json.loads(newsletter_json)
    except json.JSONDecodeError as exc:
        return {"success": False, "error": f"Invalid JSON: {exc}"}

    tenant_id: str = (config or {}).get("tenant_id", "default")
    date_str: str = data.get("date", "unknown")
    file_id: str = uuid.uuid4().hex[:8]

    # ------------------------------------------------------------------
    # 0. If caller used the default template, check agent's assigned template
    # ------------------------------------------------------------------
    if template == "editorial":
        try:
            from src.services.email.email_template_apply_service import (
                get_newsletter_template_name,
                resolve_agent_email_template,
            )

            runtime_context = (config or {}).get("_runtime_context")
            if runtime_context:
                agent_id = getattr(runtime_context, "agent_id", None)
                db = getattr(runtime_context, "db_session", None)
                if agent_id and db:
                    assigned = await resolve_agent_email_template(agent_id, db)
                    resolved = get_newsletter_template_name(assigned)
                    if resolved and resolved != "__custom__":
                        template = resolved
                    elif resolved == "__custom__" and assigned and assigned.get("html_content"):
                        # Will be handled below as custom_template_html
                        template = "__custom__"
        except Exception as _e:
            logger.debug(f"Could not resolve agent email template: {_e}")

    # ------------------------------------------------------------------
    # 1. Resolve custom template from S3 or DB if not a built-in name
    # ------------------------------------------------------------------
    _builtin_names = {"editorial", "minimal"}
    custom_template_html: str | None = None

    if template == "__custom__":
        # Use CUSTOM_HTML content from agent's assigned template
        try:
            from src.services.email.email_template_apply_service import resolve_agent_email_template

            runtime_context = (config or {}).get("_runtime_context")
            if runtime_context:
                agent_id = getattr(runtime_context, "agent_id", None)
                db = getattr(runtime_context, "db_session", None)
                if agent_id and db:
                    assigned = await resolve_agent_email_template(agent_id, db)
                    custom_template_html = (assigned or {}).get("html_content")
            template = "editorial"  # fall back to editorial layout for rendering
        except Exception as _e:
            logger.warning(f"Could not load custom template HTML: {_e}")
            template = "editorial"
    elif template not in _builtin_names:
        try:
            from src.services.storage.s3_storage import get_s3_storage

            s3 = get_s3_storage()
            s3_key = f"newsletter-templates/{tenant_id}/{template}"
            raw = s3.download_file(s3_key)
            custom_template_html = raw.decode("utf-8")
            logger.info(f"Loaded custom newsletter template from S3: {s3_key}")
        except Exception as exc:
            logger.warning(f"Custom template '{template}' not in S3: {exc}. Falling back to editorial.")
            template = "editorial"

    # ------------------------------------------------------------------
    # 2. Image enrichment — all parallel, all fail-silent
    # ------------------------------------------------------------------

    async def _fetch_og_image(url: str) -> str | None:
        try:
            async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
                r = await client.get(url, headers={"User-Agent": "AI-Agent/1.0"})
                text = r.text
                m = re.search(r'property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', text, re.I)
                if not m:
                    m = re.search(r'content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', text, re.I)
                return m.group(1) if m else None
        except Exception:
            return None

    def _youtube_thumbnail(url: str) -> str | None:
        m = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
        return f"https://img.youtube.com/vi/{m.group(1)}/mqdefault.jpg" if m else None

    hn: list[dict] = data.get("hackernews") or []
    rss: list[dict] = data.get("rss_news") or []
    lead_candidate = max(hn, key=lambda x: x.get("score", 0)) if hn else (rss[0] if rss else {})
    lead_url = lead_candidate.get("url", "")

    # Schedule OG fetches
    lead_task: asyncio.Task | None = None
    if not data.get("lead_image_url") and lead_url.startswith("http"):
        lead_task = asyncio.create_task(_fetch_og_image(lead_url))

    news_all = (hn + rss)[:8]
    news_img_tasks: dict[int, asyncio.Task] = {}
    for i, item in enumerate(news_all):
        if not item.get("image_url") and item.get("url", "").startswith("http"):
            news_img_tasks[i] = asyncio.create_task(_fetch_og_image(item["url"]))

    products = (data.get("producthunt") or [])[:4]
    prod_img_tasks: dict[int, asyncio.Task] = {}
    for i, p in enumerate(products):
        if not p.get("image_url") and p.get("url", "").startswith("http"):
            prod_img_tasks[i] = asyncio.create_task(_fetch_og_image(p["url"]))

    # YouTube thumbnails — no HTTP needed, derived from video ID
    for item in data.get("youtube") or []:
        if not item.get("thumbnail_url") and item.get("url"):
            item["thumbnail_url"] = _youtube_thumbnail(item["url"])

    # Collect all results
    if lead_task:
        data["lead_image_url"] = await lead_task

    for i, task in news_img_tasks.items():
        img = await task
        if img:
            news_all[i]["image_url"] = img

    for i, task in prod_img_tasks.items():
        img = await task
        if img:
            products[i]["image_url"] = img

    # ------------------------------------------------------------------
    # 3. Render email HTML (680px) — no PDF/image URLs yet
    # ------------------------------------------------------------------
    from src.services.newsletter.render_service import NewsletterRenderService

    service = NewsletterRenderService()
    render_kwargs: dict[str, Any] = {
        "edition": edition,
        "template": template,
        "custom_template_html": custom_template_html,
    }

    wide_html = service.render(data, width=1200, **render_kwargs)

    # ------------------------------------------------------------------
    # 4. Generate PDF + OG image via scraper service (fail-silent)
    # ------------------------------------------------------------------
    pdf_s3_key: str | None = None
    image_s3_key: str | None = None

    try:
        from src.core.scraper_client import ScraperServiceClient
        from src.services.storage.s3_storage import get_s3_storage

        scraper = ScraperServiceClient()
        session_id = f"newsletter_{file_id}"

        # Render HTML in browser at 1200px wide
        await scraper.browser_render_html(wide_html, session_id=session_id, viewport_width=1200, viewport_height=900)

        # PDF
        pdf_result = await scraper.browser_pdf(session_id=session_id, format="A4", print_background=True)
        if pdf_result.get("pdf_base64"):
            pdf_bytes = base64.b64decode(pdf_result["pdf_base64"])
            s3 = get_s3_storage()
            pdf_s3_key = f"newsletters/{tenant_id}/{date_str}/{file_id}.pdf"
            s3.upload_file(file_content=pdf_bytes, key=pdf_s3_key, content_type="application/pdf")

        # OG share image at 1200x630
        await scraper.browser_render_html(wide_html, session_id=session_id, viewport_width=1200, viewport_height=630)
        img_result = await scraper.browser_screenshot(
            session_id=session_id, full_page=False, image_type="jpeg", quality=90
        )
        if img_result.get("image_base64"):
            img_bytes = base64.b64decode(img_result["image_base64"])
            s3 = get_s3_storage()
            image_s3_key = f"newsletters/{tenant_id}/{date_str}/{file_id}_og.jpg"
            s3.upload_file(file_content=img_bytes, key=image_s3_key, content_type="image/jpeg")

        try:
            await scraper.browser_close_session(session_id=session_id)
        except Exception:
            pass

    except Exception as exc:
        logger.warning(f"Newsletter PDF/image generation skipped: {exc}")

    # ------------------------------------------------------------------
    # 5. Final email render — inject pdf_url + image_url into footer
    # ------------------------------------------------------------------
    final_html = service.render(
        data,
        width=680,
        pdf_url=None,
        image_url=None,
        **render_kwargs,
    )

    subject = f"The Signal \u2014 AI & Tech Daily \u00b7 {date_str}"

    # ------------------------------------------------------------------
    # 6. Store rendered HTML in Redis so it never passes through LLM
    #    tool-call arguments (large JSON causes truncation errors).
    #    internal_send_email resolves the key automatically.
    # ------------------------------------------------------------------
    render_key = f"newsletter:rendered:{tenant_id}:{file_id}"
    try:
        from src.config.redis import get_redis_async

        await (get_redis_async()).set(
            render_key,
            json.dumps(
                {"html": final_html, "subject": subject, "pdf_s3_key": pdf_s3_key, "image_s3_key": image_s3_key}
            ),
            ex=3600,
        )
    except Exception as exc:
        logger.warning(f"Redis unavailable, returning inline HTML: {exc}")
        return {"success": True, "html": final_html, "subject": subject, "pdf_url": pdf_url, "image_url": image_url}

    return {"success": True, "subject": subject, "body": render_key}
