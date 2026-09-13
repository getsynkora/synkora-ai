"""
News Tools for Synkora Agents.

Provides news fetching capabilities:
- NewsAPI integration (via OAuth App with api_token auth method)
- RSS/Atom feed parser (no credentials required)
"""

import logging
import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import defusedxml.ElementTree as SafeET
import httpx

logger = logging.getLogger(__name__)

NEWSAPI_BASE = "https://newsapi.org/v2"
REQUEST_TIMEOUT = 30


async def _get_newsapi_key(runtime_context: Any) -> str:
    """
    Resolve NewsAPI key from OAuthApp via runtime context.

    Resolution order:
    1. User's personal token (UserOAuthToken.access_token)
    2. OAuthApp.api_token fallback
    """
    from sqlalchemy import select

    from src.models.agent_tool import AgentTool
    from src.models.oauth_app import OAuthApp
    from src.models.user_oauth_token import UserOAuthToken
    from src.services.agents.security import decrypt_value

    db = runtime_context.db_session

    # Get agent tool config
    result = await db.execute(
        select(AgentTool).filter(
            AgentTool.agent_id == runtime_context.agent_id,
            AgentTool.tool_name == "internal_news_search",
            AgentTool.enabled,
        )
    )
    agent_tool = result.scalar_one_or_none()

    if not agent_tool or not agent_tool.oauth_app_id:
        raise ValueError("No OAuth app configured for internal_news_search. Please add a NewsAPI OAuth app.")

    # Get OAuth app
    result = await db.execute(
        select(OAuthApp).filter(
            OAuthApp.id == agent_tool.oauth_app_id,
            OAuthApp.provider.ilike("newsapi"),
            OAuthApp.is_active,
        )
    )
    oauth_app = result.scalar_one_or_none()

    if not oauth_app:
        raise ValueError("No active NewsAPI OAuth app found")

    # Try user token first
    result = await db.execute(select(UserOAuthToken).filter(UserOAuthToken.oauth_app_id == oauth_app.id))
    user_token = result.scalar_one_or_none()

    if user_token and user_token.access_token:
        logger.info(f"Using user's NewsAPI token (OAuth app: '{oauth_app.app_name}')")
        return decrypt_value(user_token.access_token)

    if oauth_app.api_token:
        logger.info(f"Using NewsAPI app token '{oauth_app.app_name}'")
        return decrypt_value(oauth_app.api_token)

    raise ValueError("No NewsAPI key available. Please connect your NewsAPI account.")


async def internal_news_search(
    query: str,
    category: str | None = None,
    language: str = "en",
    from_date: str | None = None,
    page_size: int = 20,
    sort_by: str = "publishedAt",
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Search for recent news articles using NewsAPI.

    Args:
        query: Search query string
        category: Filter by category (technology, science, business, health, entertainment, sports)
        language: Language code (en, de, fr, etc.)
        from_date: Start date YYYY-MM-DD, defaults to yesterday
        page_size: Number of articles to return (max 100)
        sort_by: Sort order: publishedAt | relevancy | popularity
        runtime_context: Agent runtime context for credential resolution
        config: Optional configuration dictionary

    Returns:
        Dictionary with articles list and metadata
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    if not query:
        return {"success": False, "error": "Search query is required"}

    try:
        api_key = await _get_newsapi_key(runtime_context)

        params: dict[str, Any] = {
            "q": query,
            "language": language,
            "pageSize": min(page_size, 100),
            "sortBy": sort_by,
            "apiKey": api_key,
        }

        if from_date:
            params["from"] = from_date

        # Note: `category` is only supported by /v2/top-headlines, not /v2/everything.
        # Append it to the query string instead so the filter still takes effect.
        if category:
            params["q"] = f"{params['q']} {category}"

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(f"{NEWSAPI_BASE}/everything", params=params)

        if response.status_code == 401:
            return {"success": False, "error": "Invalid NewsAPI key. Check your credentials."}
        if response.status_code == 429:
            return {"success": False, "error": "NewsAPI rate limit exceeded. Try again later."}

        response.raise_for_status()
        data = response.json()

        if data.get("status") != "ok":
            return {"success": False, "error": data.get("message", "NewsAPI request failed")}

        articles = []
        for article in data.get("articles", []):
            articles.append(
                {
                    "title": article.get("title", ""),
                    "description": article.get("description", ""),
                    "url": article.get("url", ""),
                    "source": article.get("source", {}).get("name", ""),
                    "published_at": article.get("publishedAt", ""),
                    "content": article.get("content", ""),
                }
            )

        return {
            "success": True,
            "articles": articles,
            "total_results": data.get("totalResults", len(articles)),
        }

    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"NewsAPI search failed: {e}", exc_info=True)
        return {"success": False, "error": f"News search failed: {str(e)}"}


def _parse_rss_date(date_str: str | None) -> str | None:
    """Parse an RSS pubDate or Atom updated/published string to ISO format."""
    if not date_str:
        return None
    date_str = date_str.strip()
    # Try RFC 2822 (RSS pubDate)
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.isoformat()
    except Exception:
        pass
    # Try ISO 8601 (Atom)
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(date_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt.isoformat()
        except ValueError:
            continue
    return date_str


def _parse_feed(xml_text: str, max_items: int, filter_hours: int) -> dict[str, Any]:
    """Parse RSS 2.0 or Atom feed XML and return structured items."""
    root = SafeET.fromstring(xml_text)

    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "content": "http://purl.org/rss/1.0/modules/content/",
        "dc": "http://purl.org/dc/elements/1.1/",
    }

    now = datetime.now(tz=UTC)
    cutoff_hours = filter_hours * 3600
    items = []
    feed_title = ""

    # Detect feed type
    is_atom = root.tag == "{http://www.w3.org/2005/Atom}feed" or root.tag == "feed"

    if is_atom:
        # Atom feed
        title_el = root.find("atom:title", ns) or root.find("title")
        feed_title = title_el.text.strip() if title_el is not None and title_el.text else ""
        entries = root.findall("atom:entry", ns) or root.findall("entry")

        for entry in entries:
            if len(items) >= max_items:
                break

            title_el = entry.find("atom:title", ns) or entry.find("title")
            title = title_el.text.strip() if title_el is not None and title_el.text else ""

            link_el = entry.find("atom:link", ns) or entry.find("link")
            url = ""
            if link_el is not None:
                url = link_el.get("href", "") or link_el.text or ""

            summary_el = (
                entry.find("atom:summary", ns)
                or entry.find("summary")
                or entry.find("atom:content", ns)
                or entry.find("content")
            )
            summary = summary_el.text.strip() if summary_el is not None and summary_el.text else ""

            pub_el = (
                entry.find("atom:published", ns)
                or entry.find("published")
                or entry.find("atom:updated", ns)
                or entry.find("updated")
            )
            pub_str = pub_el.text if pub_el is not None else None
            pub_iso = _parse_rss_date(pub_str)

            # Apply time filter
            if pub_iso and filter_hours > 0:
                try:
                    pub_dt = datetime.fromisoformat(pub_iso)
                    if pub_dt.tzinfo is None:
                        pub_dt = pub_dt.replace(tzinfo=UTC)
                    if (now - pub_dt).total_seconds() > cutoff_hours:
                        continue
                except Exception:
                    pass

            items.append(
                {"title": title, "summary": summary, "url": url, "published_at": pub_iso or "", "source": feed_title}
            )
    else:
        # RSS 2.0
        channel = root.find("channel") or root
        title_el = channel.find("title")
        feed_title = title_el.text.strip() if title_el is not None and title_el.text else ""

        for item in channel.findall("item"):
            if len(items) >= max_items:
                break

            title_el = item.find("title")
            title = title_el.text.strip() if title_el is not None and title_el.text else ""

            link_el = item.find("link")
            url = link_el.text.strip() if link_el is not None and link_el.text else ""

            desc_el = item.find("description")
            summary = desc_el.text.strip() if desc_el is not None and desc_el.text else ""
            # Strip HTML from description if present
            if summary and "<" in summary:
                summary = re.sub(r"<[^>]+>", "", summary).strip()

            pub_el = item.find("pubDate") or item.find("dc:date", ns)
            pub_str = pub_el.text if pub_el is not None else None
            pub_iso = _parse_rss_date(pub_str)

            # Apply time filter
            if pub_iso and filter_hours > 0:
                try:
                    pub_dt = datetime.fromisoformat(pub_iso)
                    if pub_dt.tzinfo is None:
                        pub_dt = pub_dt.replace(tzinfo=UTC)
                    if (now - pub_dt).total_seconds() > cutoff_hours:
                        continue
                except Exception:
                    pass

            items.append(
                {"title": title, "summary": summary, "url": url, "published_at": pub_iso or "", "source": feed_title}
            )

    return {"items": items, "feed_title": feed_title}


async def internal_fetch_rss_feed(
    url: str,
    max_items: int = 20,
    filter_hours: int = 24,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Fetch and parse an RSS or Atom feed.

    Works reliably on all major news sites (TechCrunch, The Verge, Wired,
    ArsTechnica, etc.) without getting blocked — RSS feeds bypass anti-scraping.

    Args:
        url: RSS or Atom feed URL
        max_items: Maximum items to return (default 20)
        filter_hours: Only return items from last N hours (0 = no filter)
        runtime_context: Agent runtime context (not required for RSS)
        config: Optional configuration dictionary

    Returns:
        Dictionary with items list, count, and feed metadata
    """
    if not url or not url.startswith(("http://", "https://")):
        return {"success": False, "error": "Invalid URL. Must start with http:// or https://"}

    try:
        from src.services.security.public_http import fetch_public_url

        response = await fetch_public_url(
            url,
            timeout=REQUEST_TIMEOUT,
            headers={
                "User-Agent": "AI-Agent/1.0 RSS Reader",
                "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
            },
        )

        if response.status_code >= 400:
            return {"success": False, "error": f"HTTP {response.status_code} fetching feed: {url}"}

        parsed = _parse_feed(response.text, max_items=max_items, filter_hours=filter_hours)

        return {
            "success": True,
            "items": parsed["items"],
            "count": len(parsed["items"]),
            "feed_title": parsed["feed_title"],
        }

    except ET.ParseError as e:
        return {"success": False, "error": f"Failed to parse feed XML: {str(e)}"}
    except httpx.TimeoutException:
        return {"success": False, "error": f"Feed request timed out after {REQUEST_TIMEOUT} seconds"}
    except httpx.ConnectError as e:
        return {"success": False, "error": f"Connection error fetching feed: {str(e)}"}
    except Exception as e:
        logger.error(f"RSS feed fetch failed for {url}: {e}", exc_info=True)
        return {"success": False, "error": f"Failed to fetch RSS feed: {str(e)}"}
