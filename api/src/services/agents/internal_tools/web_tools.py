"""
Web Tools for Synkora Agents.

Provides web content fetching capabilities for agents to retrieve
and extract text from URLs.
"""

import asyncio
import ipaddress
import logging
import os
import socket
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Maximum content length to return (characters)
MAX_CONTENT_LENGTH = 50000

# Request timeout in seconds
REQUEST_TIMEOUT = 30

# User agent for HTTP requests
USER_AGENT = "AI-Agent/1.0 (Web Fetch Tool)"

# Blocked hostnames for SSRF protection
BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "metadata.goog",
}

# Blocked hostname patterns (cloud metadata endpoints)
BLOCKED_HOSTNAME_PATTERNS = [
    "169.254.169.254",  # AWS/GCP/Azure metadata
    "metadata.google.internal",
    "metadata.azure.com",
]


def _load_platform_blocked_domains() -> list[str]:
    """Load platform-level blocked domains from environment variable."""
    raw = os.getenv("AGENT_BLOCKED_DOMAINS", "")
    return [d.strip().lower() for d in raw.split(",") if d.strip()]


def _is_domain_blocked(url: str, blocked_domains: list[str]) -> bool:
    """
    Check if the URL's hostname matches any entry in the blocked domains list.

    Supports exact hostname match and subdomain matching (e.g. blocking
    "example.com" also blocks "sub.example.com").
    """
    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        if not hostname:
            return False
        for blocked in blocked_domains:
            blocked = blocked.lower()
            if hostname == blocked or hostname.endswith("." + blocked):
                return True
    except Exception:
        pass
    return False


def _is_ip_blocked(ip_str: str) -> bool:
    """
    Check if an IP address is in a private/blocked range.

    Blocks: private networks, loopback, link-local, multicast, reserved.
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        )
    except ValueError:
        return False


def _resolve_hostname(hostname: str) -> list:
    """Blocking DNS lookup — intended to be called via run_in_executor."""
    return socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)


async def _is_url_safe(url: str) -> tuple[bool, str | None]:
    """
    Validate URL for SSRF protection.

    DNS resolution runs in a thread-pool executor to avoid blocking the event loop.

    Returns (is_safe, error_message).
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname

        if not hostname:
            return False, "Invalid URL: no hostname"

        # Check blocked hostnames
        hostname_lower = hostname.lower()
        if hostname_lower in BLOCKED_HOSTNAMES:
            return False, f"Blocked hostname: {hostname}"

        for pattern in BLOCKED_HOSTNAME_PATTERNS:
            if pattern in hostname_lower:
                return False, f"Blocked hostname pattern: {hostname}"

        # Resolve hostname and check IP — off-loaded to thread pool to avoid blocking event loop
        try:
            loop = asyncio.get_running_loop()
            try:
                resolved_ips = await asyncio.wait_for(
                    loop.run_in_executor(None, _resolve_hostname, hostname),
                    timeout=5.0,
                )
            except TimeoutError:
                raise ValueError(f"DNS resolution timeout for hostname: {hostname}")
            for _family, _, _, _, sockaddr in resolved_ips:
                ip_str = sockaddr[0]
                if _is_ip_blocked(ip_str):
                    return False, f"URL resolves to blocked IP range: {ip_str}"
        except socket.gaierror as e:
            return False, f"Failed to resolve hostname: {e}"

        return True, None

    except Exception as e:
        return False, f"URL validation error: {e}"


def _html_to_text(html: str, max_length: int = MAX_CONTENT_LENGTH) -> str:
    """
    Convert HTML to clean readable text using BeautifulSoup.

    Extracts text content, preserving basic structure with headings,
    paragraphs, and list items.

    Args:
        html: Raw HTML string
        max_length: Maximum output length

    Returns:
        Clean text extracted from HTML
    """
    soup = BeautifulSoup(html, "html.parser")

    # Remove script, style, nav, footer, header elements
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        tag.decompose()

    # Extract text with basic formatting
    lines = []
    for element in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "pre", "code", "td", "th", "div"]):
        text = element.get_text(strip=True)
        if not text:
            continue

        tag_name = element.name
        if tag_name in ("h1", "h2", "h3"):
            lines.append(f"\n## {text}\n")
        elif tag_name in ("h4", "h5", "h6"):
            lines.append(f"\n### {text}\n")
        elif tag_name == "li":
            lines.append(f"- {text}")
        elif tag_name in ("pre", "code"):
            lines.append(f"```\n{text}\n```")
        else:
            lines.append(text)

    result = "\n".join(lines)

    # Deduplicate consecutive blank lines
    while "\n\n\n" in result:
        result = result.replace("\n\n\n", "\n\n")

    if len(result) > max_length:
        result = result[:max_length] + "\n\n[Content truncated...]"

    return result.strip()


JINA_READER_BASE = "https://r.jina.ai/"


async def _fetch_via_jina(url: str, max_length: int = MAX_CONTENT_LENGTH) -> dict[str, Any]:
    """Fetch a URL via Jina Reader proxy, which returns clean markdown."""
    jina_url = f"{JINA_READER_BASE}{url}"
    try:
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True,  # r.jina.ai is a trusted proxy — safe to follow its redirects
            headers={"User-Agent": USER_AGENT, "Accept": "text/plain"},
        ) as client:
            response = await client.get(jina_url)

        if response.status_code >= 400:
            return {
                "url": url,
                "error": f"HTTP {response.status_code} via Jina Reader",
                "status_code": response.status_code,
            }

        content = response.text
        is_truncated = len(content) > max_length
        if is_truncated:
            content = content[:max_length] + "\n\n[Content truncated...]"

        return {
            "url": url,
            "content": content,
            "content_type": "text/markdown",
            "status_code": response.status_code,
            "content_length": len(content),
            "is_truncated": is_truncated,
            "via_jina": True,
        }
    except Exception as e:
        return {"url": url, "error": f"Jina Reader fetch failed: {str(e)}"}


async def internal_web_fetch(
    url: str,
    extract_text: bool = True,
    max_length: int = MAX_CONTENT_LENGTH,
    use_reader: bool = False,
    auto_fallback: bool = True,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Fetch content from a URL and return it as text.

    Retrieves web page content, optionally converting HTML to clean readable
    text. Follows redirects and handles common error cases.

    Args:
        url: URL to fetch content from
        extract_text: Whether to extract text from HTML (strip tags). Default True.
        max_length: Maximum content length to return (default 50000 chars)
        use_reader: Use Jina Reader proxy for clean markdown output. Default False.
        auto_fallback: Auto-retry via Jina Reader if site returns 403/404. Default True.
        config: Optional configuration dictionary

    Returns:
        Dictionary containing:
        - url: The fetched URL
        - content: Page content (text or raw HTML)
        - content_type: Response content type
        - status_code: HTTP status code
        - title: Page title (if HTML)
        - content_length: Length of returned content
        - is_truncated: Whether content was truncated
        - via_jina: True if fetched via Jina Reader
        - error: Error message (if any)
    """
    try:
        # Basic URL validation
        if not url or not url.startswith(("http://", "https://")):
            return {"error": "Invalid URL. Must start with http:// or https://"}

        # SSRF protection - always validate URL before making any request (including via Jina)
        is_safe, error = await _is_url_safe(url)
        if not is_safe:
            return {"error": f"URL blocked for security: {error}"}

        # Domain blocklist check (platform-level + any passed via config)
        platform_blocked = _load_platform_blocked_domains()
        agent_blocked: list[str] = (config or {}).get("blocked_domains", []) if config else []
        all_blocked = platform_blocked + agent_blocked
        if all_blocked and _is_domain_blocked(url, all_blocked):
            parsed_host = urlparse(url).hostname or url
            logger.warning("URL blocked by domain blocklist: %s", parsed_host)
            return {"error": f"URL blocked by domain policy: {parsed_host}"}

        # If explicitly requested, go through Jina Reader (URL already validated above)
        if use_reader:
            return await _fetch_via_jina(url, max_length)

        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT,
            follow_redirects=False,  # SSRF: manually follow redirects to re-validate each hop
            headers={"User-Agent": USER_AGENT},
        ) as client:
            response = await client.get(url)

        # Handle redirects with SSRF re-validation on each hop
        redirect_count = 0
        while response.is_redirect and redirect_count < 5:
            redirect_url = str(response.headers.get("location", ""))
            if not redirect_url:
                break
            # Resolve relative redirects
            if redirect_url.startswith("/"):
                from urllib.parse import urlparse as _urlparse

                parsed = _urlparse(url)
                redirect_url = f"{parsed.scheme}://{parsed.netloc}{redirect_url}"
            # Re-check SSRF for redirect target
            hop_safe, hop_error = await _is_url_safe(redirect_url)
            if not hop_safe:
                return {"error": f"Redirect blocked for security: {hop_error}"}
            async with httpx.AsyncClient(
                timeout=REQUEST_TIMEOUT,
                follow_redirects=False,
                headers={"User-Agent": USER_AGENT},
            ) as client:
                response = await client.get(redirect_url)
            url = redirect_url
            redirect_count += 1

        content_type = response.headers.get("content-type", "")
        status_code = response.status_code

        if status_code in (403, 404) and auto_fallback:
            logger.info(f"Got {status_code} for {url}, retrying via Jina Reader")
            return await _fetch_via_jina(url, max_length)

        if status_code >= 400:
            return {
                "url": url,
                "error": f"HTTP {status_code}: {response.reason_phrase}",
                "status_code": status_code,
            }

        # Determine if response is HTML
        is_html = "text/html" in content_type

        raw_text = response.text
        title = None

        if is_html and extract_text:
            # Extract title
            soup = BeautifulSoup(raw_text, "html.parser")
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.get_text(strip=True)

            content = _html_to_text(raw_text, max_length)
        else:
            content = raw_text
            if len(content) > max_length:
                content = content[:max_length]

        is_truncated = len(content) >= max_length

        result: dict[str, Any] = {
            "url": str(response.url),
            "content": content,
            "content_type": content_type,
            "status_code": status_code,
            "content_length": len(content),
            "is_truncated": is_truncated,
        }

        if title:
            result["title"] = title

        return result

    except httpx.TimeoutException:
        return {"url": url, "error": f"Request timed out after {REQUEST_TIMEOUT} seconds"}
    except httpx.ConnectError as e:
        return {"url": url, "error": f"Connection error: {str(e)}"}
    except Exception as e:
        logger.warning(f"Error fetching URL {url}: {e}", exc_info=True)
        return {"url": url, "error": f"Failed to fetch URL: {str(e)}"}
