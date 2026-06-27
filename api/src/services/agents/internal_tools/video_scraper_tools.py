"""
Video Scraper Tool — extracts structured marketing content from a website URL
for use in the short-form video generation pipeline.
"""

from __future__ import annotations

import io
import logging
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_MAX_CONTENT_BYTES = 500_000
_USER_AGENT = "AI-Agent/1.0 (Web Fetch Tool)"
_CTA_KEYWORDS = {"buy", "get", "try", "order", "shop", "start", "sign up", "learn more", "discover", "download"}


async def internal_scrape_website_for_video(
    url: str,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Scrape a website and extract structured content for short-form video generation.

    Extracts headline, product benefits, CTAs, brand color, and hero image URL.
    Safe against SSRF via existing _is_url_safe validation.

    Args:
        url: Full URL of the page to scrape (must start with https://)
        config: Runtime config dict (unused, kept for tool signature consistency)

    Returns:
        {
            "success": True,
            "url": str,
            "title": str,
            "description": str,
            "benefits": list[str],
            "cta": str,
            "brand_color": str,   # hex e.g. "#FF5733"
            "hero_image_url": str | None,
        }
    """
    from src.services.agents.internal_tools.web_tools import _is_url_safe

    is_safe, error = await _is_url_safe(url)
    if not is_safe:
        return {"success": False, "error": f"URL not allowed: {error}"}

    html = await _fetch_html(url)
    if isinstance(html, dict):
        return html  # error dict

    soup = BeautifulSoup(html, "html.parser")

    title = _extract_title(soup)
    description = _extract_description(soup)
    benefits = _extract_benefits(soup)
    cta = _extract_cta(soup)
    hero_image_url = _extract_hero_image(soup, url)
    brand_color = await _extract_dominant_color(hero_image_url) if hero_image_url else "#1A1A2E"

    return {
        "success": True,
        "url": url,
        "title": title or urlparse(url).netloc,
        "description": description,
        "benefits": benefits,
        "cta": cta,
        "brand_color": brand_color or "#1A1A2E",
        "hero_image_url": hero_image_url,
    }


async def _fetch_html(url: str) -> str | dict:
    """Fetch page HTML. Returns HTML string or error dict."""
    from src.services.agents.internal_tools.web_tools import _is_url_safe

    try:
        async with httpx.AsyncClient(
            timeout=30,
            follow_redirects=False,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            response = await client.get(url)

            # Handle one redirect manually (SSRF-safe)
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("location", "")
                if not location:
                    return {"success": False, "error": "Redirect with no location header"}
                redirect_url = location if location.startswith("http") else urljoin(url, location)
                is_safe, err = await _is_url_safe(redirect_url)
                if not is_safe:
                    return {"success": False, "error": f"Redirect target blocked: {err}"}
                response = await client.get(redirect_url)

            if response.status_code != 200:
                return {
                    "success": False,
                    "error": (
                        f"HTTP {response.status_code}. Site may be blocking scrapers — try a direct product page URL."
                    ),
                }

            return response.text[:_MAX_CONTENT_BYTES]

    except httpx.TimeoutException:
        return {
            "success": False,
            "error": "Request timed out. Try a direct product page URL.",
        }
    except Exception as exc:
        return {"success": False, "error": f"Failed to fetch URL: {exc}"}


def _extract_title(soup: BeautifulSoup) -> str:
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        return og_title["content"].strip()
    if soup.title:
        return soup.title.get_text(strip=True)
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    return ""


def _extract_description(soup: BeautifulSoup) -> str:
    og_desc = soup.find("meta", property="og:description")
    if og_desc and og_desc.get("content"):
        return og_desc["content"].strip()
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        return meta_desc["content"].strip()
    return ""


def _extract_benefits(soup: BeautifulSoup) -> list[str]:
    """Extract up to 6 bullet-point benefits from ul/li elements."""
    benefits: list[str] = []
    for ul in soup.find_all("ul"):
        items = [li.get_text(strip=True) for li in ul.find_all("li") if len(li.get_text(strip=True)) > 10]
        benefits.extend(items[:3])
        if len(benefits) >= 6:
            break
    return benefits[:6]


def _extract_cta(soup: BeautifulSoup) -> str:
    """Find first button or link with action-like text."""
    for el in soup.find_all(["button", "a"]):
        text = el.get_text(strip=True)
        if any(kw in text.lower() for kw in _CTA_KEYWORDS) and 3 < len(text) < 60:
            return text
    return "Learn more"


def _extract_hero_image(soup: BeautifulSoup, base_url: str) -> str | None:
    og_image = soup.find("meta", property="og:image")
    if og_image and og_image.get("content"):
        raw = og_image["content"].strip()
        return raw if raw.startswith("http") else urljoin(base_url, raw)
    return None


async def _extract_dominant_color(image_url: str) -> str | None:
    """Download image and return its dominant color as a hex string using Pillow."""
    try:
        from PIL import Image

        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            resp = await client.get(image_url)
            if resp.status_code != 200:
                return None

        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        img = img.resize((50, 50))  # Downsample for speed
        pixels = list(img.getdata())

        # Bucket pixels into 32-step bins and pick most frequent
        buckets: dict[tuple[int, int, int], int] = {}
        for r, g, b in pixels:
            key = (r // 32 * 32, g // 32 * 32, b // 32 * 32)
            buckets[key] = buckets.get(key, 0) + 1

        dominant = max(buckets, key=lambda k: buckets[k])
        return "#{:02X}{:02X}{:02X}".format(*dominant)

    except Exception as exc:
        logger.debug(f"Brand color extraction failed: {exc}")
        return None
