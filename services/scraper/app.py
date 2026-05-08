"""
Scraper Microservice — Playwright browser automation + crawl4ai

Endpoints:
  POST /v1/scrape/google-play          - scrape Google Play reviews
  POST /v1/scrape/apple                - scrape Apple App Store reviews
  POST /v1/browser/navigate            - navigate to URL
  POST /v1/browser/snapshot            - AI-friendly page snapshot with element refs
  POST /v1/browser/click               - click element
  POST /v1/browser/fill                - fill input
  POST /v1/browser/type                - type text
  POST /v1/browser/fill-form           - fill multiple form fields
  POST /v1/browser/select              - select dropdown option
  POST /v1/browser/check               - check/uncheck checkbox
  POST /v1/browser/press               - press keyboard key
  POST /v1/browser/wait                - wait for conditions
  POST /v1/browser/screenshot          - take screenshot (returns base64)
  POST /v1/browser/hover               - hover over element
  POST /v1/browser/drag                - drag and drop
  POST /v1/browser/evaluate            - evaluate JavaScript
  POST /v1/browser/get-cookies         - get cookies
  POST /v1/browser/set-cookies         - set cookies
  POST /v1/browser/clear-cookies       - clear cookies
  POST /v1/browser/new-page            - open new tab
  POST /v1/browser/close-page          - close a tab
  POST /v1/browser/list-pages          - list open tabs
  POST /v1/browser/list-frames         - list iframes
  POST /v1/browser/wait-for-new-page   - wait for popup
  POST /v1/browser/close-session       - close browser session
  POST /v1/browser/resize              - resize viewport
  POST /v1/browser/pdf                 - generate PDF (returns base64)
  POST /v1/browser/get-storage         - get localStorage/sessionStorage
  POST /v1/browser/set-storage         - set localStorage/sessionStorage
  POST /v1/browser/clear-storage       - clear localStorage/sessionStorage
  POST /v1/browser/get-console         - get console messages
  POST /v1/browser/get-errors          - get page errors
  POST /v1/browser/get-network         - get network requests
  POST /v1/browser/scroll-into-view    - scroll element into view
  POST /v1/browser/handle-dialog       - set dialog handler
  POST /v1/browser/upload-file         - upload files to input
  POST /v1/browser/set-offline         - toggle offline mode
  POST /v1/browser/set-extra-headers   - set extra HTTP headers
  POST /v1/browser/set-http-credentials - set HTTP auth credentials
  POST /v1/browser/focus-page          - bring page to front
  POST /v1/browser/simple-navigate     - stateless navigate + extract content
  POST /v1/browser/extract-links       - stateless link extraction
  POST /v1/browser/extract-structured-data - stateless CSS selector extraction
  POST /v1/browser/check-element-exists   - stateless element check
  GET  /health
"""

import base64
import ipaddress
import json
import logging
import re
import socket
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import FastAPI
from pydantic import BaseModel

from browser_session import BrowserSession

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Synkora Scraper Service")


# ===========================================================================
# Utilities
# ===========================================================================

DEFAULT_TIMEOUT = 8000
MAX_TIMEOUT = 60000
MIN_TIMEOUT = 500


def normalize_timeout(timeout_ms: int | None, default: int = DEFAULT_TIMEOUT) -> int:
    if timeout_ms is None:
        return default
    return max(MIN_TIMEOUT, min(MAX_TIMEOUT, timeout_ms))


BLOCKED_IP_RANGES = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def _is_internal_ip(hostname: str) -> bool:
    try:
        ip_str = socket.gethostbyname(hostname)
        ip = ipaddress.ip_address(ip_str)
        return any(ip in net for net in BLOCKED_IP_RANGES)
    except Exception:
        return True


def _is_url_allowed(url: str) -> bool:
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        return not _is_internal_ip(hostname)
    except Exception:
        return False


def _get_locator_strategies(page, ref: str, state=None) -> list:
    from playwright.async_api import Page as _Page  # noqa: F401

    ref = ref.strip()
    strategies = []

    if state and re.match(r"^e\d+$", ref):
        from browser_session import ElementRef

        if ref in state.element_refs:
            elem_ref = state.element_refs[ref]
            if elem_ref.selector:
                strategies.append(("css", page.locator(elem_ref.selector)))
            locator = page.get_by_role(elem_ref.role, name=elem_ref.name)
            if elem_ref.nth == 0:
                strategies.append(("role", locator.first))
            else:
                strategies.append(("role", locator.nth(elem_ref.nth)))
            if elem_ref.role in ("combobox", "listbox"):
                role_locator = page.get_by_role(elem_ref.role)
                if elem_ref.nth == 0:
                    strategies.append(("role_no_name", role_locator.first))
                else:
                    strategies.append(("role_no_name", role_locator.nth(elem_ref.nth)))
            return strategies

    role_match = re.match(r"^(\w+):(.+)$", ref)
    if role_match:
        role, name = role_match.groups()
        strategies.append(("role", page.get_by_role(role, name=name)))
        return strategies
    if ref.startswith("text="):
        strategies.append(("text", page.get_by_text(ref[5:])))
        return strategies
    if ref.startswith("label="):
        strategies.append(("label", page.get_by_label(ref[6:])))
        return strategies
    if ref.startswith("placeholder="):
        strategies.append(("placeholder", page.get_by_placeholder(ref[12:])))
        return strategies
    strategies.append(("css", page.locator(ref)))
    return strategies


def _resolve_locator(page, ref: str, state=None):
    strategies = _get_locator_strategies(page, ref, state)
    return strategies[0][1] if strategies else page.locator(ref)


# ===========================================================================
# Health
# ===========================================================================


@app.get("/health")
async def health():
    return {"status": "ok"}


# ===========================================================================
# App Store Scraping
# ===========================================================================


class GooglePlayScrapeRequest(BaseModel):
    app_id: str
    country: str = "us"
    lang: str = "en"
    count: int = 200


class AppleScrapeRequest(BaseModel):
    app_id: str
    country: str = "us"
    count: int = 200


@app.post("/v1/scrape/google-play")
async def scrape_google_play(req: GooglePlayScrapeRequest):
    import json as _json
    import re as _re
    from datetime import UTC as _UTC, datetime as _dt

    from bs4 import BeautifulSoup
    from crawl4ai import AsyncWebCrawler

    url = f"https://play.google.com/store/apps/details?id={req.app_id}&hl={req.lang}&gl={req.country}&showAllReviews=true"

    js_code = """
    async function loadReviews() {
        const sleep = (ms) => new Promise(r => setTimeout(r, ms));
        await sleep(4000);
        let seeAllBtn = Array.from(document.querySelectorAll('button, div[role="button"]'))
            .find(el => /see all|all reviews|reviews/i.test(el.textContent));
        if (seeAllBtn) { seeAllBtn.click(); await sleep(3000); }
        let modal = null;
        for (let i = 0; i < 10; i++) {
            modal = document.querySelector('div[role="dialog"] div[style*="overflow"]');
            if (modal) break;
            await sleep(1000);
        }
        if (!modal) {
            for (let i = 0; i < 20; i++) { window.scrollTo(0, document.body.scrollHeight); await sleep(2000); }
            return;
        }
        let lastHeight = 0, sameScrolls = 0;
        for (let i = 0; i < 60; i++) {
            modal.scrollTo(0, modal.scrollHeight);
            await sleep(2000);
            const newHeight = modal.scrollHeight;
            if (newHeight === lastHeight) { sameScrolls++; if (sameScrolls >= 3) break; }
            else { sameScrolls = 0; lastHeight = newHeight; }
        }
    }
    await loadReviews();
    """

    async with AsyncWebCrawler(verbose=False) as crawler:
        result = await crawler.arun(url=url, wait_for="css:body", js_code=js_code, bypass_cache=True, page_timeout=120000)
        if not result.success:
            return {"reviews": [], "error": result.error_message}
        html = result.html

    reviews = []
    # Try structured data first
    script_pattern = r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>'
    for script in _re.findall(script_pattern, html, _re.DOTALL):
        try:
            data = _json.loads(script)
            if isinstance(data, dict) and data.get("@type") == "Review":
                try:
                    review = {
                        "reviewId": data.get("identifier", ""),
                        "userName": data.get("author", {}).get("name", "Anonymous"),
                        "score": int(data.get("reviewRating", {}).get("ratingValue", 0)),
                        "content": data.get("reviewBody", ""),
                        "at": data.get("datePublished", _dt.now(_UTC).isoformat()),
                        "thumbsUpCount": 0,
                        "reviewCreatedVersion": None,
                        "replyContent": None,
                        "repliedAt": None,
                    }
                    reviews.append(review)
                except Exception:
                    pass
        except Exception:
            pass

    # Fallback: parse HTML elements
    if not reviews:
        soup = BeautifulSoup(html, "html.parser")
        for container in soup.find_all("div", class_="EGFGHd")[:200]:
            try:
                header = container.find("header", class_="c1bOId")
                review_id = header.get("data-review-id", "") if header else ""
                if not review_id:
                    review_id = f"review_{hash(str(container)[:100])}"

                author_elem = container.find("div", class_="X5PpBb")
                author_name = author_elem.get_text(strip=True) if author_elem else "Anonymous"

                rating = 0
                rating_container = container.find("div", class_="iXRFPc")
                if rating_container:
                    m = _re.search(r"Rated (\d+) star", rating_container.get("aria-label", ""))
                    if m:
                        rating = int(m.group(1))

                content_elem = container.find("div", class_="h3YV2d")
                content = content_elem.get_text(strip=True) if content_elem else ""
                if not content or len(content) < 20:
                    continue

                review = {
                    "reviewId": review_id,
                    "userName": author_name,
                    "score": rating if rating > 0 else 3,
                    "content": content,
                    "at": _dt.now(_UTC).isoformat(),
                    "thumbsUpCount": 0,
                    "reviewCreatedVersion": None,
                    "replyContent": None,
                    "repliedAt": None,
                }
                reviews.append(review)
            except Exception:
                continue

    return {"reviews": reviews[: req.count]}


@app.post("/v1/scrape/apple")
async def scrape_apple(req: AppleScrapeRequest):
    import hashlib
    import json as _json
    import re as _re
    from datetime import UTC as _UTC, datetime as _dt

    from bs4 import BeautifulSoup
    from crawl4ai import AsyncWebCrawler

    url = f"https://apps.apple.com/{req.country}/app/id{req.app_id}"

    async with AsyncWebCrawler(verbose=False) as crawler:
        result = await crawler.arun(url=url, bypass_cache=True)
        if not result.success:
            return {"reviews": [], "error": result.error_message}
        html = result.html

    reviews = []

    def _gen_id(data: dict) -> str:
        s = f"{data.get('author','')}_{data.get('date','')}_{data.get('content','')[:100]}"
        return hashlib.md5(s.encode()).hexdigest()

    script_pattern = r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>'
    for script in _re.findall(script_pattern, html, _re.DOTALL):
        try:
            data = _json.loads(script)
            items = [data] if isinstance(data, dict) else (data if isinstance(data, list) else [])
            for item in items:
                if not isinstance(item, dict) or item.get("@type") != "Review":
                    continue
                author = item.get("author", {})
                author_name = author.get("name", "Anonymous") if isinstance(author, dict) else str(author)
                review_body = item.get("reviewBody", "")
                date_str = item.get("datePublished", "")
                try:
                    review_date = _dt.fromisoformat(date_str.replace("Z", "+00:00")) if date_str else _dt.now(_UTC)
                except Exception:
                    review_date = _dt.now(_UTC)
                review_data = {
                    "author": author_name,
                    "rating": int(item.get("reviewRating", {}).get("ratingValue", 0)),
                    "title": item.get("name", ""),
                    "content": review_body,
                    "date": review_date.isoformat(),
                    "version": None,
                    "developerResponse": None,
                }
                review_data["reviewId"] = _gen_id(review_data)
                reviews.append(review_data)
        except Exception:
            pass

    if not reviews:
        soup = BeautifulSoup(html, "html.parser")
        for review_elem in soup.find_all("div", class_="we-customer-review"):
            try:
                author_elem = review_elem.find("span", class_="we-customer-review__user")
                author = author_elem.text.strip() if author_elem else "Anonymous"

                rating_elem = review_elem.find("figure", class_="we-star-rating")
                rating = 0
                if rating_elem and "aria-label" in rating_elem.attrs:
                    m = _re.search(r"(\d+)", rating_elem["aria-label"])
                    if m:
                        rating = int(m.group(1))

                title_elem = review_elem.find("h3", class_="we-customer-review__title")
                title = title_elem.text.strip() if title_elem else ""

                content_elem = review_elem.find("p", class_="we-customer-review__body")
                content = content_elem.text.strip() if content_elem else ""

                date_elem = review_elem.find("time")
                review_date = _dt.now(_UTC)
                if date_elem and "datetime" in date_elem.attrs:
                    try:
                        review_date = _dt.fromisoformat(date_elem["datetime"].replace("Z", "+00:00"))
                    except Exception:
                        pass

                review_data = {
                    "author": author,
                    "rating": rating,
                    "title": title,
                    "content": content,
                    "date": review_date.isoformat(),
                    "version": None,
                    "developerResponse": None,
                }
                review_data["reviewId"] = _gen_id(review_data)
                reviews.append(review_data)
            except Exception:
                continue

    return {"reviews": reviews[: req.count]}


# ===========================================================================
# Browser endpoint helpers
# ===========================================================================


async def _get_session_and_page(session_id: str, page_id: str | None = None):
    session = await BrowserSession.get_or_create(session_id)
    page = await session.get_page(page_id)
    return session, page


# ===========================================================================
# Stateless browser operations (from browser_tools.py)
# ===========================================================================


class SimpleNavigateRequest(BaseModel):
    url: str
    wait_for: str = "domcontentloaded"


class ExtractLinksRequest(BaseModel):
    url: str


class ExtractStructuredDataRequest(BaseModel):
    url: str
    selector: str


class CheckElementExistsRequest(BaseModel):
    url: str
    selector: str


@app.post("/v1/browser/simple-navigate")
async def browser_simple_navigate(req: SimpleNavigateRequest):
    if not _is_url_allowed(req.url):
        return {"success": False, "error": f"URL not allowed: {req.url}"}
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
            try:
                page = await browser.new_page()
                page.set_default_timeout(30000)
                response = await page.goto(req.url, wait_until=req.wait_for, timeout=20000)
                title = await page.title()
                text_content = await page.evaluate("document.body.innerText")
                meta_description = await page.evaluate("""
                    () => { const m = document.querySelector('meta[name="description"]'); return m ? m.content : ''; }
                """)
                if len(text_content) > 50000:
                    text_content = text_content[:50000] + "..."
                return {
                    "success": True,
                    "url": req.url,
                    "title": title,
                    "text_content": text_content,
                    "meta_description": meta_description,
                    "status_code": response.status if response else None,
                    "final_url": page.url,
                }
            finally:
                await browser.close()
    except Exception as e:
        return {"success": False, "error": str(e), "url": req.url}


@app.post("/v1/browser/extract-links")
async def browser_extract_links(req: ExtractLinksRequest):
    if not _is_url_allowed(req.url):
        return {"success": False, "error": f"URL not allowed: {req.url}"}
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
            try:
                page = await browser.new_page()
                await page.goto(req.url, wait_until="domcontentloaded", timeout=20000)
                links = await page.evaluate("""
                    () => Array.from(document.querySelectorAll('a')).map(a => ({
                        href: a.href, text: a.textContent.trim(), title: a.title
                    })).filter(l => l.href)
                """)
                return {"success": True, "url": req.url, "links": links, "count": len(links)}
            finally:
                await browser.close()
    except Exception as e:
        return {"success": False, "error": str(e), "url": req.url}


@app.post("/v1/browser/extract-structured-data")
async def browser_extract_structured_data(req: ExtractStructuredDataRequest):
    if not _is_url_allowed(req.url):
        return {"success": False, "error": f"URL not allowed: {req.url}"}
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
            try:
                page = await browser.new_page()
                await page.goto(req.url, wait_until="domcontentloaded", timeout=20000)
                elements = await page.query_selector_all(req.selector)
                data = [{"text": (await e.inner_text()).strip(), "html": await e.inner_html()} for e in elements]
                return {"success": True, "url": req.url, "selector": req.selector, "data": data, "count": len(data)}
            finally:
                await browser.close()
    except Exception as e:
        return {"success": False, "error": str(e), "url": req.url}


@app.post("/v1/browser/check-element-exists")
async def browser_check_element_exists(req: CheckElementExistsRequest):
    if not _is_url_allowed(req.url):
        return {"success": False, "error": f"URL not allowed: {req.url}"}
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
            try:
                page = await browser.new_page()
                await page.goto(req.url, wait_until="domcontentloaded", timeout=20000)
                element = await page.query_selector(req.selector)
                exists = element is not None
                result = {"success": True, "url": req.url, "selector": req.selector, "exists": exists}
                if exists:
                    result["text"] = (await element.inner_text()).strip()
                return result
            finally:
                await browser.close()
    except Exception as e:
        return {"success": False, "error": str(e), "url": req.url}


# ===========================================================================
# Stateful browser session endpoints
# ===========================================================================


class NavigateRequest(BaseModel):
    url: str
    session_id: str = "default"
    page_id: str | None = None
    wait_until: str = "load"
    timeout_ms: int | None = None


@app.post("/v1/browser/navigate")
async def browser_navigate(req: NavigateRequest):
    try:
        session, page = await _get_session_and_page(req.session_id, req.page_id)
        timeout = normalize_timeout(req.timeout_ms, 30000)
        response = await page.goto(req.url, wait_until=req.wait_until, timeout=timeout)
        return {
            "success": True,
            "url": page.url,
            "title": await page.title(),
            "status": response.status if response else None,
            "session_id": req.session_id,
            "page_id": session.current_page_id,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


class SnapshotRequest(BaseModel):
    session_id: str = "default"
    page_id: str | None = None
    interactive_only: bool = True
    max_elements: int = 150
    include_text: bool = True
    frame_selector: str | None = None


@app.post("/v1/browser/snapshot")
async def browser_snapshot(req: SnapshotRequest):
    try:
        session, page = await _get_session_and_page(req.session_id, req.page_id)
        state = session.get_page_state(page)
        state.element_refs.clear()
        state.next_ref_id = 0

        interactive_roles = [
            "button", "link", "textbox", "checkbox", "radio", "combobox", "listbox",
            "option", "menuitem", "tab", "switch", "slider", "spinbutton", "searchbox",
        ]

        frame_root = page.frame_locator(req.frame_selector) if req.frame_selector else None
        snapshot_lines = []
        refs = {}
        elements_found = 0

        from browser_session import ElementRef

        for role in interactive_roles:
            if elements_found >= req.max_elements:
                break
            try:
                locator = frame_root.get_by_role(role) if frame_root else page.get_by_role(role)
                count = await locator.count()
                for i in range(min(count, req.max_elements - elements_found)):
                    try:
                        element = locator.nth(i)
                        if not await element.is_visible():
                            continue
                        name = None
                        try:
                            name = await element.get_attribute("aria-label")
                            if not name:
                                name = (await element.inner_text() or "").strip()[:50]
                        except Exception:
                            pass
                        ref_id = state.generate_ref_id()
                        css_selector = None
                        try:
                            css_selector = await element.evaluate("""el => {
                                if (el.id) return '#' + CSS.escape(el.id);
                                const testId = el.getAttribute('data-testid');
                                if (testId) return '[data-testid="' + testId + '"]';
                                const path = [];
                                let cur = el;
                                while (cur && cur.nodeType === 1) {
                                    let sel = cur.tagName.toLowerCase();
                                    if (cur.id) { path.unshift('#' + CSS.escape(cur.id)); break; }
                                    const parent = cur.parentElement;
                                    if (parent) {
                                        const siblings = Array.from(parent.children).filter(c => c.tagName === cur.tagName);
                                        if (siblings.length > 1) sel += ':nth-of-type(' + (siblings.indexOf(cur) + 1) + ')';
                                    }
                                    path.unshift(sel);
                                    cur = cur.parentElement;
                                    if (path.length >= 5) break;
                                }
                                return path.join(' > ');
                            }""")
                        except Exception:
                            pass
                        elem_ref = ElementRef(role=role, name=name, nth=i, selector=css_selector)
                        state.element_refs[ref_id] = elem_ref
                        refs[ref_id] = {"role": role, "name": name, "nth": i, "selector": css_selector}
                        name_str = f' "{name}"' if name else ""
                        snapshot_lines.append(f"{role}{name_str} [ref={ref_id}]")
                        elements_found += 1
                    except Exception:
                        continue
            except Exception:
                continue

        text_content = ""
        if req.include_text:
            try:
                text_content = await page.evaluate("document.body.innerText")
                if len(text_content) > 5000:
                    text_content = text_content[:5000] + "\n...[truncated]"
            except Exception:
                pass

        return {
            "success": True,
            "snapshot": "\n".join(snapshot_lines),
            "refs": refs,
            "ref_count": len(refs),
            "url": page.url,
            "title": await page.title(),
            "text_content": text_content if req.include_text else None,
            "session_id": req.session_id,
            "page_id": session.current_page_id,
        }
    except Exception as e:
        logger.error(f"Snapshot error: {e}")
        return {"success": False, "error": str(e)}


class ClickRequest(BaseModel):
    ref: str
    session_id: str = "default"
    page_id: str | None = None
    double_click: bool = False
    button: str = "left"
    modifiers: list[str] | None = None
    timeout_ms: int | None = None
    frame_selector: str | None = None


@app.post("/v1/browser/click")
async def browser_click(req: ClickRequest):
    try:
        session, page = await _get_session_and_page(req.session_id, req.page_id)
        state = session.get_page_state(page)
        timeout = normalize_timeout(req.timeout_ms)
        strategies = _get_locator_strategies(page, req.ref, state) or [("css", page.locator(req.ref))]
        click_opts: dict[str, Any] = {"timeout": timeout, "button": req.button}
        if req.modifiers:
            click_opts["modifiers"] = req.modifiers
        last_err = None
        for strategy_name, locator in strategies:
            try:
                try:
                    await locator.scroll_into_view_if_needed(timeout=timeout // 2)
                except Exception:
                    pass
                if req.double_click:
                    await locator.dblclick(**click_opts)
                else:
                    await locator.click(**click_opts)
                return {"success": True, "action": "double_click" if req.double_click else "click", "ref": req.ref, "session_id": req.session_id}
            except Exception as e:
                last_err = e
                continue
        return {"success": False, "error": str(last_err or f"Could not click: {req.ref}")}
    except Exception as e:
        return {"success": False, "error": str(e)}


class FillRequest(BaseModel):
    ref: str
    text: str
    session_id: str = "default"
    page_id: str | None = None
    clear_first: bool = True
    timeout_ms: int | None = None
    frame_selector: str | None = None


@app.post("/v1/browser/fill")
async def browser_fill(req: FillRequest):
    try:
        session, page = await _get_session_and_page(req.session_id, req.page_id)
        state = session.get_page_state(page)
        timeout = normalize_timeout(req.timeout_ms)
        strategies = _get_locator_strategies(page, req.ref, state) or [("css", page.locator(req.ref))]

        # Detect combobox
        is_combobox = False
        from browser_session import ElementRef

        if state and re.match(r"^e\d+$", req.ref):
            elem_ref = state.element_refs.get(req.ref)
            if elem_ref and elem_ref.role in ("combobox", "listbox"):
                is_combobox = True
        elif req.ref.startswith(("combobox:", "listbox:")):
            is_combobox = True

        if is_combobox:
            for _, locator in strategies:
                try:
                    await locator.click(timeout=timeout)
                    break
                except Exception:
                    continue
            await page.wait_for_timeout(300)
            for method in [
                lambda: page.get_by_role("option", name=req.text, exact=True).first.click(timeout=timeout),
                lambda: page.get_by_role("option", name=req.text).first.click(timeout=timeout),
                lambda: page.get_by_role("listitem").filter(has_text=req.text).first.click(timeout=timeout),
                lambda: page.get_by_text(req.text, exact=True).first.click(timeout=timeout),
            ]:
                try:
                    await method()
                    return {"success": True, "action": "select_combobox", "ref": req.ref, "session_id": req.session_id}
                except Exception:
                    continue
            return {"success": False, "error": f"Could not select option '{req.text}' in dropdown {req.ref}"}

        last_err = None
        for _, locator in strategies:
            try:
                if req.clear_first:
                    await locator.fill("", timeout=timeout)
                await locator.fill(req.text, timeout=timeout)
                return {"success": True, "action": "fill", "ref": req.ref, "text": req.text, "session_id": req.session_id}
            except Exception as e:
                last_err = e
                continue
        return {"success": False, "error": str(last_err or f"Could not fill: {req.ref}")}
    except Exception as e:
        return {"success": False, "error": str(e)}


class TypeRequest(BaseModel):
    ref: str
    text: str
    session_id: str = "default"
    page_id: str | None = None
    delay_ms: int = 0
    submit: bool = False
    timeout_ms: int | None = None
    frame_selector: str | None = None


@app.post("/v1/browser/type")
async def browser_type(req: TypeRequest):
    try:
        session, page = await _get_session_and_page(req.session_id, req.page_id)
        state = session.get_page_state(page)
        timeout = normalize_timeout(req.timeout_ms)
        strategies = _get_locator_strategies(page, req.ref, state) or [("css", page.locator(req.ref))]
        last_err = None
        for _, locator in strategies:
            try:
                await locator.type(req.text, delay=req.delay_ms, timeout=timeout)
                if req.submit:
                    await locator.press("Enter")
                return {"success": True, "action": "type", "ref": req.ref, "session_id": req.session_id}
            except Exception as e:
                last_err = e
                continue
        return {"success": False, "error": str(last_err)}
    except Exception as e:
        return {"success": False, "error": str(e)}


class FillFormRequest(BaseModel):
    fields: list[dict[str, Any]]
    session_id: str = "default"
    page_id: str | None = None
    submit_ref: str | None = None
    timeout_ms: int | None = None


@app.post("/v1/browser/fill-form")
async def browser_fill_form(req: FillFormRequest):
    results = []
    for field in req.fields:
        ref = field.get("ref", "")
        value = field.get("value")
        if isinstance(value, bool):
            r = await browser_check(CheckRequest(ref=ref, checked=value, session_id=req.session_id, page_id=req.page_id, timeout_ms=req.timeout_ms))
        elif isinstance(value, list):
            r = await browser_select(SelectRequest(ref=ref, values=value, session_id=req.session_id, page_id=req.page_id, timeout_ms=req.timeout_ms))
        else:
            r = await browser_fill(FillRequest(ref=ref, text=str(value), session_id=req.session_id, page_id=req.page_id, timeout_ms=req.timeout_ms))
        results.append({"ref": ref, **r})

    submit_result = None
    if req.submit_ref:
        submit_result = await browser_click(ClickRequest(ref=req.submit_ref, session_id=req.session_id, page_id=req.page_id))

    return {"success": True, "fields_filled": len(results), "results": results, "submit_result": submit_result}


class SelectRequest(BaseModel):
    ref: str
    values: list[str]
    session_id: str = "default"
    page_id: str | None = None
    timeout_ms: int | None = None


@app.post("/v1/browser/select")
async def browser_select(req: SelectRequest):
    try:
        session, page = await _get_session_and_page(req.session_id, req.page_id)
        state = session.get_page_state(page)
        timeout = normalize_timeout(req.timeout_ms)
        strategies = _get_locator_strategies(page, req.ref, state) or [("css", page.locator(req.ref))]
        last_err = None
        for _, locator in strategies:
            try:
                selected = await locator.select_option(req.values, timeout=timeout)
                return {"success": True, "action": "select", "ref": req.ref, "selected": selected, "session_id": req.session_id}
            except Exception as e:
                last_err = e
                continue
        return {"success": False, "error": str(last_err)}
    except Exception as e:
        return {"success": False, "error": str(e)}


class CheckRequest(BaseModel):
    ref: str
    checked: bool = True
    session_id: str = "default"
    page_id: str | None = None
    timeout_ms: int | None = None


@app.post("/v1/browser/check")
async def browser_check(req: CheckRequest):
    try:
        session, page = await _get_session_and_page(req.session_id, req.page_id)
        state = session.get_page_state(page)
        timeout = normalize_timeout(req.timeout_ms)
        locator = _resolve_locator(page, req.ref, state)
        if req.checked:
            await locator.check(timeout=timeout)
        else:
            await locator.uncheck(timeout=timeout)
        return {"success": True, "action": "check", "ref": req.ref, "checked": req.checked, "session_id": req.session_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


class PressRequest(BaseModel):
    key: str
    session_id: str = "default"
    page_id: str | None = None
    ref: str | None = None
    timeout_ms: int | None = None


@app.post("/v1/browser/press")
async def browser_press(req: PressRequest):
    try:
        session, page = await _get_session_and_page(req.session_id, req.page_id)
        state = session.get_page_state(page)
        timeout = normalize_timeout(req.timeout_ms)
        if req.ref:
            locator = _resolve_locator(page, req.ref, state)
            await locator.press(req.key, timeout=timeout)
        else:
            await page.keyboard.press(req.key)
        return {"success": True, "action": "press", "key": req.key, "session_id": req.session_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


class WaitRequest(BaseModel):
    session_id: str = "default"
    page_id: str | None = None
    time_ms: int | None = None
    selector: str | None = None
    text: str | None = None
    text_gone: str | None = None
    url_pattern: str | None = None
    load_state: str | None = None
    timeout_ms: int | None = None


@app.post("/v1/browser/wait")
async def browser_wait(req: WaitRequest):
    try:
        session, page = await _get_session_and_page(req.session_id, req.page_id)
        timeout = normalize_timeout(req.timeout_ms, 30000)

        if req.time_ms:
            await page.wait_for_timeout(req.time_ms)
            return {"success": True, "waited": f"{req.time_ms}ms", "session_id": req.session_id}
        if req.selector:
            await page.wait_for_selector(req.selector, state="visible", timeout=timeout)
            return {"success": True, "waited": f"selector '{req.selector}'", "session_id": req.session_id}
        if req.text:
            await page.wait_for_function(
                f"() => document.body.innerText.includes({json.dumps(req.text)})", timeout=timeout
            )
            return {"success": True, "waited": f"text '{req.text}'", "session_id": req.session_id}
        if req.text_gone:
            await page.wait_for_function(
                f"() => !document.body.innerText.includes({json.dumps(req.text_gone)})", timeout=timeout
            )
            return {"success": True, "waited": f"text gone '{req.text_gone}'", "session_id": req.session_id}
        if req.load_state:
            await page.wait_for_load_state(req.load_state, timeout=timeout)
            return {"success": True, "waited": f"load_state '{req.load_state}'", "session_id": req.session_id}
        return {"success": False, "error": "No wait condition specified"}
    except Exception as e:
        return {"success": False, "error": str(e)}


class ScreenshotRequest(BaseModel):
    session_id: str = "default"
    page_id: str | None = None
    ref: str | None = None
    full_page: bool = False
    image_type: str = "png"
    quality: int | None = None


@app.post("/v1/browser/screenshot")
async def browser_screenshot(req: ScreenshotRequest):
    """Takes a screenshot and returns base64-encoded image data."""
    try:
        session, page = await _get_session_and_page(req.session_id, req.page_id)
        state = session.get_page_state(page)
        opts: dict[str, Any] = {"type": req.image_type}
        if req.image_type == "jpeg" and req.quality:
            opts["quality"] = req.quality
        if req.ref:
            locator = _resolve_locator(page, req.ref, state)
            img_bytes = await locator.screenshot(**opts)
        else:
            opts["full_page"] = req.full_page
            img_bytes = await page.screenshot(**opts)
        return {
            "success": True,
            "image_base64": base64.b64encode(img_bytes).decode("utf-8"),
            "format": req.image_type,
            "full_page": req.full_page if not req.ref else False,
            "element_ref": req.ref,
            "page_url": page.url,
            "session_id": req.session_id,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


class HoverRequest(BaseModel):
    ref: str
    session_id: str = "default"
    page_id: str | None = None
    timeout_ms: int | None = None


@app.post("/v1/browser/hover")
async def browser_hover(req: HoverRequest):
    try:
        session, page = await _get_session_and_page(req.session_id, req.page_id)
        state = session.get_page_state(page)
        timeout = normalize_timeout(req.timeout_ms)
        locator = _resolve_locator(page, req.ref, state)
        await locator.hover(timeout=timeout)
        return {"success": True, "action": "hover", "ref": req.ref, "session_id": req.session_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


class ScrollIntoViewRequest(BaseModel):
    ref: str
    session_id: str = "default"
    page_id: str | None = None
    timeout_ms: int | None = None


@app.post("/v1/browser/scroll-into-view")
async def browser_scroll_into_view(req: ScrollIntoViewRequest):
    try:
        session, page = await _get_session_and_page(req.session_id, req.page_id)
        state = session.get_page_state(page)
        timeout = normalize_timeout(req.timeout_ms)
        locator = _resolve_locator(page, req.ref, state)
        await locator.scroll_into_view_if_needed(timeout=timeout)
        return {"success": True, "action": "scroll_into_view", "ref": req.ref, "session_id": req.session_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


class DragRequest(BaseModel):
    source_ref: str
    target_ref: str
    session_id: str = "default"
    page_id: str | None = None
    timeout_ms: int | None = None


@app.post("/v1/browser/drag")
async def browser_drag(req: DragRequest):
    try:
        session, page = await _get_session_and_page(req.session_id, req.page_id)
        state = session.get_page_state(page)
        timeout = normalize_timeout(req.timeout_ms)
        source = _resolve_locator(page, req.source_ref, state)
        target = _resolve_locator(page, req.target_ref, state)
        await source.drag_to(target, timeout=timeout)
        return {"success": True, "action": "drag", "source": req.source_ref, "target": req.target_ref, "session_id": req.session_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


class EvaluateRequest(BaseModel):
    expression: str
    session_id: str = "default"
    page_id: str | None = None
    ref: str | None = None


@app.post("/v1/browser/evaluate")
async def browser_evaluate(req: EvaluateRequest):
    try:
        session, page = await _get_session_and_page(req.session_id, req.page_id)
        state = session.get_page_state(page)
        if req.ref:
            locator = _resolve_locator(page, req.ref, state)
            result = await locator.evaluate(req.expression)
        else:
            result = await page.evaluate(req.expression)
        return {"success": True, "result": result, "session_id": req.session_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


class GetCookiesRequest(BaseModel):
    session_id: str = "default"
    page_id: str | None = None
    urls: list[str] | None = None


@app.post("/v1/browser/get-cookies")
async def browser_get_cookies(req: GetCookiesRequest):
    try:
        session, _ = await _get_session_and_page(req.session_id, req.page_id)
        cookies = await session.context.cookies(req.urls) if req.urls else await session.context.cookies()
        return {"success": True, "cookies": cookies, "count": len(cookies), "session_id": req.session_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


class SetCookiesRequest(BaseModel):
    cookies: list[dict[str, Any]]
    session_id: str = "default"
    page_id: str | None = None


@app.post("/v1/browser/set-cookies")
async def browser_set_cookies(req: SetCookiesRequest):
    try:
        session, _ = await _get_session_and_page(req.session_id, req.page_id)
        await session.context.add_cookies(req.cookies)
        return {"success": True, "action": "set_cookies", "count": len(req.cookies), "session_id": req.session_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


class ClearCookiesRequest(BaseModel):
    session_id: str = "default"
    page_id: str | None = None


@app.post("/v1/browser/clear-cookies")
async def browser_clear_cookies(req: ClearCookiesRequest):
    try:
        session, _ = await _get_session_and_page(req.session_id, req.page_id)
        await session.context.clear_cookies()
        return {"success": True, "action": "clear_cookies", "session_id": req.session_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


class NewPageRequest(BaseModel):
    session_id: str = "default"
    url: str | None = None


@app.post("/v1/browser/new-page")
async def browser_new_page(req: NewPageRequest):
    try:
        session = await BrowserSession.get_or_create(req.session_id)
        page_id, page = await session.new_page()
        if req.url:
            await page.goto(req.url)
        return {"success": True, "page_id": page_id, "url": page.url, "session_id": req.session_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


class ClosePageRequest(BaseModel):
    page_id: str
    session_id: str = "default"


@app.post("/v1/browser/close-page")
async def browser_close_page(req: ClosePageRequest):
    try:
        session = await BrowserSession.get_or_create(req.session_id)
        await session.close_page(req.page_id)
        return {"success": True, "action": "close_page", "page_id": req.page_id, "session_id": req.session_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


class ListPagesRequest(BaseModel):
    session_id: str = "default"


@app.post("/v1/browser/list-pages")
async def browser_list_pages(req: ListPagesRequest):
    try:
        session = await BrowserSession.get_or_create(req.session_id)
        pages = await session.list_pages()
        return {"success": True, "pages": pages, "count": len(pages), "session_id": req.session_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


class ListFramesRequest(BaseModel):
    session_id: str = "default"
    page_id: str | None = None


@app.post("/v1/browser/list-frames")
async def browser_list_frames(req: ListFramesRequest):
    try:
        session, page = await _get_session_and_page(req.session_id, req.page_id)
        frames = []
        for i, frame in enumerate(page.frames):
            frames.append({"index": i, "url": frame.url, "name": frame.name})
        return {"success": True, "frames": frames, "count": len(frames), "session_id": req.session_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


class WaitForNewPageRequest(BaseModel):
    session_id: str = "default"
    timeout_ms: int = 15000


@app.post("/v1/browser/wait-for-new-page")
async def browser_wait_for_new_page(req: WaitForNewPageRequest):
    try:
        session = await BrowserSession.get_or_create(req.session_id)
        existing = set(session.pages.keys())
        new_page_id = await session.wait_for_new_page(existing, req.timeout_ms)
        if new_page_id:
            page = session.pages[new_page_id]
            session.current_page_id = new_page_id
            return {"success": True, "new_page_id": new_page_id, "url": page.url, "title": await page.title(), "session_id": req.session_id}
        return {"success": False, "error": "No new page appeared within timeout"}
    except Exception as e:
        return {"success": False, "error": str(e)}


class CloseSessionRequest(BaseModel):
    session_id: str = "default"


@app.post("/v1/browser/close-session")
async def browser_close_session(req: CloseSessionRequest):
    try:
        await BrowserSession.close_session(req.session_id)
        return {"success": True, "action": "close_session", "session_id": req.session_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


class ResizeRequest(BaseModel):
    width: int
    height: int
    session_id: str = "default"
    page_id: str | None = None


@app.post("/v1/browser/resize")
async def browser_resize(req: ResizeRequest):
    try:
        session, page = await _get_session_and_page(req.session_id, req.page_id)
        await page.set_viewport_size({"width": req.width, "height": req.height})
        return {"success": True, "action": "resize", "width": req.width, "height": req.height, "session_id": req.session_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


class RenderHtmlRequest(BaseModel):
    html: str
    session_id: str = "default"
    viewport_width: int = 1200
    viewport_height: int = 900


@app.post("/v1/browser/render-html")
async def browser_render_html(req: RenderHtmlRequest):
    """Load raw HTML into the browser session using page.set_content()."""
    try:
        session, page = await _get_session_and_page(req.session_id, None)
        await page.set_viewport_size({"width": req.viewport_width, "height": req.viewport_height})
        await page.set_content(req.html, wait_until="networkidle")
        return {"success": True, "action": "render_html", "session_id": req.session_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


class PdfRequest(BaseModel):
    session_id: str = "default"
    page_id: str | None = None
    format: str = "Letter"
    print_background: bool = True


@app.post("/v1/browser/pdf")
async def browser_pdf(req: PdfRequest):
    try:
        session, page = await _get_session_and_page(req.session_id, req.page_id)
        pdf_bytes = await page.pdf(format=req.format, print_background=req.print_background)
        return {
            "success": True,
            "action": "pdf",
            "pdf_base64": base64.b64encode(pdf_bytes).decode("utf-8"),
            "size_bytes": len(pdf_bytes),
            "session_id": req.session_id,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


class GetStorageRequest(BaseModel):
    storage_type: str = "local"
    key: str | None = None
    session_id: str = "default"
    page_id: str | None = None


@app.post("/v1/browser/get-storage")
async def browser_get_storage(req: GetStorageRequest):
    try:
        session, page = await _get_session_and_page(req.session_id, req.page_id)
        storage_obj = "localStorage" if req.storage_type == "local" else "sessionStorage"
        if req.key:
            result = await page.evaluate(f"{storage_obj}.getItem({json.dumps(req.key)})")
            return {"success": True, "storage_type": req.storage_type, "key": req.key, "value": result, "session_id": req.session_id}
        else:
            result = await page.evaluate(f"""
                Object.fromEntries(
                    Array.from({{length: {storage_obj}.length}}, (_, i) => {storage_obj}.key(i))
                    .map(k => [k, {storage_obj}.getItem(k)])
                )
            """)
            return {"success": True, "storage_type": req.storage_type, "data": result, "count": len(result), "session_id": req.session_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


class SetStorageRequest(BaseModel):
    storage_type: str = "local"
    items: dict[str, str]
    session_id: str = "default"
    page_id: str | None = None


@app.post("/v1/browser/set-storage")
async def browser_set_storage(req: SetStorageRequest):
    try:
        session, page = await _get_session_and_page(req.session_id, req.page_id)
        storage_obj = "localStorage" if req.storage_type == "local" else "sessionStorage"
        for key, value in req.items.items():
            await page.evaluate(f"{storage_obj}.setItem({json.dumps(key)}, {json.dumps(value)})")
        return {"success": True, "action": "set_storage", "storage_type": req.storage_type, "count": len(req.items), "session_id": req.session_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


class ClearStorageRequest(BaseModel):
    storage_type: str = "local"
    session_id: str = "default"
    page_id: str | None = None


@app.post("/v1/browser/clear-storage")
async def browser_clear_storage(req: ClearStorageRequest):
    try:
        session, page = await _get_session_and_page(req.session_id, req.page_id)
        storage_obj = "localStorage" if req.storage_type == "local" else "sessionStorage"
        await page.evaluate(f"{storage_obj}.clear()")
        return {"success": True, "action": "clear_storage", "storage_type": req.storage_type, "session_id": req.session_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


class GetConsoleRequest(BaseModel):
    session_id: str = "default"
    page_id: str | None = None
    limit: int = 50


@app.post("/v1/browser/get-console")
async def browser_get_console(req: GetConsoleRequest):
    try:
        session, page = await _get_session_and_page(req.session_id, req.page_id)
        state = session.get_page_state(page)
        msgs = state.console[-req.limit:]
        return {
            "success": True,
            "messages": [{"type": m.type, "text": m.text, "timestamp": m.timestamp} for m in msgs],
            "count": len(msgs),
            "session_id": req.session_id,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


class GetErrorsRequest(BaseModel):
    session_id: str = "default"
    page_id: str | None = None
    limit: int = 20


@app.post("/v1/browser/get-errors")
async def browser_get_errors(req: GetErrorsRequest):
    try:
        session, page = await _get_session_and_page(req.session_id, req.page_id)
        state = session.get_page_state(page)
        errs = state.errors[-req.limit:]
        return {
            "success": True,
            "errors": [{"message": e.message, "name": e.name, "timestamp": e.timestamp} for e in errs],
            "count": len(errs),
            "session_id": req.session_id,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


class GetNetworkRequest(BaseModel):
    session_id: str = "default"
    page_id: str | None = None
    limit: int = 50
    filter_type: str | None = None


@app.post("/v1/browser/get-network")
async def browser_get_network(req: GetNetworkRequest):
    try:
        session, page = await _get_session_and_page(req.session_id, req.page_id)
        state = session.get_page_state(page)
        reqs = state.requests
        if req.filter_type:
            reqs = [r for r in reqs if r.resource_type == req.filter_type]
        reqs = reqs[-req.limit:]
        return {
            "success": True,
            "requests": [{"id": r.id, "method": r.method, "url": r.url, "status": r.status, "ok": r.ok, "resource_type": r.resource_type} for r in reqs],
            "count": len(reqs),
            "session_id": req.session_id,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


class HandleDialogRequest(BaseModel):
    action: str = "accept"
    prompt_text: str | None = None
    session_id: str = "default"
    page_id: str | None = None


@app.post("/v1/browser/handle-dialog")
async def browser_handle_dialog(req: HandleDialogRequest):
    try:
        session, page = await _get_session_and_page(req.session_id, req.page_id)

        async def dialog_handler(dialog):
            if req.action == "accept":
                if req.prompt_text and dialog.type == "prompt":
                    await dialog.accept(req.prompt_text)
                else:
                    await dialog.accept()
            else:
                await dialog.dismiss()

        page.once("dialog", dialog_handler)
        return {"success": True, "action": "dialog_handler_set", "dialog_action": req.action, "session_id": req.session_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


class UploadFileRequest(BaseModel):
    file_ref: str
    file_paths: list[str]
    session_id: str = "default"
    page_id: str | None = None
    timeout_ms: int | None = None


@app.post("/v1/browser/upload-file")
async def browser_upload_file(req: UploadFileRequest):
    try:
        session, page = await _get_session_and_page(req.session_id, req.page_id)
        state = session.get_page_state(page)
        timeout = normalize_timeout(req.timeout_ms)
        locator = _resolve_locator(page, req.file_ref, state)
        await locator.set_input_files(req.file_paths, timeout=timeout)
        return {"success": True, "action": "upload_file", "ref": req.file_ref, "files": req.file_paths, "session_id": req.session_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


class SetOfflineRequest(BaseModel):
    offline: bool
    session_id: str = "default"


@app.post("/v1/browser/set-offline")
async def browser_set_offline(req: SetOfflineRequest):
    try:
        session = await BrowserSession.get_or_create(req.session_id)
        await session.context.set_offline(req.offline)
        return {"success": True, "offline": req.offline, "session_id": req.session_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


class SetExtraHeadersRequest(BaseModel):
    headers: dict[str, str]
    session_id: str = "default"


@app.post("/v1/browser/set-extra-headers")
async def browser_set_extra_headers(req: SetExtraHeadersRequest):
    try:
        session = await BrowserSession.get_or_create(req.session_id)
        await session.context.set_extra_http_headers(req.headers)
        return {"success": True, "action": "set_extra_headers", "session_id": req.session_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


class SetHttpCredentialsRequest(BaseModel):
    username: str
    password: str
    session_id: str = "default"


@app.post("/v1/browser/set-http-credentials")
async def browser_set_http_credentials(req: SetHttpCredentialsRequest):
    try:
        session = await BrowserSession.get_or_create(req.session_id)
        await session.context.set_http_credentials({"username": req.username, "password": req.password})
        return {"success": True, "action": "set_http_credentials", "session_id": req.session_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


class FocusPageRequest(BaseModel):
    session_id: str = "default"
    page_id: str | None = None


@app.post("/v1/browser/focus-page")
async def browser_focus_page(req: FocusPageRequest):
    try:
        session, page = await _get_session_and_page(req.session_id, req.page_id)
        await page.bring_to_front()
        return {"success": True, "action": "focus_page", "session_id": req.session_id, "page_id": session.current_page_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5003)
