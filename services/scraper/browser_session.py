"""
Browser Session Manager for persistent browser automation.
"""

import asyncio
import base64
import ipaddress
import logging
import os
import re
import socket
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import urlparse
from weakref import WeakValueDictionary

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

logger = logging.getLogger(__name__)

MAX_SESSIONS = int(os.getenv("SCRAPER_MAX_SESSIONS", "20"))
MAX_PAGES_PER_SESSION = int(os.getenv("SCRAPER_MAX_PAGES_PER_SESSION", "8"))
SESSION_IDLE_TTL_SECONDS = int(os.getenv("SCRAPER_SESSION_IDLE_TTL_SECONDS", "1800"))

BLOCKED_IP_RANGES = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("ff00::/8"),
]


def _is_internal_ip(hostname: str) -> bool:
    try:
        try:
            addresses = [ipaddress.ip_address(hostname)]
        except ValueError:
            infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
            addresses = list({ipaddress.ip_address(info[4][0]) for info in infos})
        if not addresses:
            return True
        return any(any(ip in net for net in BLOCKED_IP_RANGES) for ip in addresses)
    except Exception:
        return True


def _is_url_allowed(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme in ("about", "data", "blob"):
            return True
        if parsed.scheme not in ("http", "https"):
            return False
        return bool(parsed.hostname) and not _is_internal_ip(parsed.hostname)
    except Exception:
        return False


@dataclass
class ConsoleMessage:
    """Browser console message"""

    type: str
    text: str
    timestamp: str
    location: dict[str, Any] | None = None


@dataclass
class PageError:
    """Page error record"""

    message: str
    name: str | None = None
    stack: str | None = None
    timestamp: str = ""


@dataclass
class NetworkRequest:
    """Network request record"""

    id: str
    timestamp: str
    method: str
    url: str
    resource_type: str
    status: int | None = None
    ok: bool | None = None


@dataclass
class ElementRef:
    """Element reference for AI-friendly interactions"""

    role: str
    name: str | None = None
    nth: int = 0
    selector: str | None = None


@dataclass
class PageState:
    """State tracking for a browser page"""

    console: list[ConsoleMessage] = field(default_factory=list)
    errors: list[PageError] = field(default_factory=list)
    requests: list[NetworkRequest] = field(default_factory=list)
    element_refs: dict[str, ElementRef] = field(default_factory=dict)
    next_request_id: int = 0
    next_ref_id: int = 0

    MAX_CONSOLE = 500
    MAX_ERRORS = 200
    MAX_REQUESTS = 500

    def add_console(self, msg_type: str, text: str, location: dict | None = None):
        self.console.append(
            ConsoleMessage(
                type=msg_type,
                text=text,
                timestamp=datetime.now().isoformat(),
                location=location,
            )
        )
        if len(self.console) > self.MAX_CONSOLE:
            self.console.pop(0)

    def add_error(self, message: str, name: str | None = None, stack: str | None = None):
        self.errors.append(
            PageError(
                message=message,
                name=name,
                stack=stack,
                timestamp=datetime.now().isoformat(),
            )
        )
        if len(self.errors) > self.MAX_ERRORS:
            self.errors.pop(0)

    def add_request(self, method: str, url: str, resource_type: str) -> str:
        self.next_request_id += 1
        req_id = f"r{self.next_request_id}"
        self.requests.append(
            NetworkRequest(
                id=req_id,
                timestamp=datetime.now().isoformat(),
                method=method,
                url=url,
                resource_type=resource_type,
            )
        )
        if len(self.requests) > self.MAX_REQUESTS:
            self.requests.pop(0)
        return req_id

    def update_request_response(self, req_id: str, status: int, ok: bool):
        for req in self.requests:
            if req.id == req_id:
                req.status = status
                req.ok = ok
                break

    def generate_ref_id(self) -> str:
        self.next_ref_id += 1
        return f"e{self.next_ref_id}"


class BrowserSession:
    """
    Persistent browser session manager.
    Maintains browser instance across multiple tool calls for stateful automation.
    """

    _instances: dict[str, "BrowserSession"] = {}
    _lock = asyncio.Lock()

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.playwright: Playwright | None = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.pages: dict[str, Page] = {}
        self.page_states: WeakValueDictionary[int, PageState] = WeakValueDictionary()
        self._page_state_store: dict[int, PageState] = {}  # Strong refs
        self.current_page_id: str | None = None
        self.created_at = datetime.now()
        self.last_activity = datetime.now()

    @classmethod
    async def get_or_create(cls, session_id: str) -> "BrowserSession":
        """Get existing session or create new one"""
        async with cls._lock:
            if session_id not in cls._instances:
                await cls._cleanup_idle_locked()
                if len(cls._instances) >= MAX_SESSIONS:
                    raise RuntimeError(f"Browser session capacity reached ({MAX_SESSIONS})")
                session = cls(session_id)
                await session._initialize()
                cls._instances[session_id] = session
                logger.info(f"Created new browser session: {session_id}")
            else:
                cls._instances[session_id].last_activity = datetime.now()
            return cls._instances[session_id]

    @classmethod
    async def _cleanup_idle_locked(cls):
        """Close idle sessions. Caller must hold cls._lock."""
        if SESSION_IDLE_TTL_SECONDS <= 0:
            return
        now = datetime.now()
        idle_session_ids = [
            sid
            for sid, session in cls._instances.items()
            if (now - session.last_activity).total_seconds() > SESSION_IDLE_TTL_SECONDS
        ]
        for sid in idle_session_ids:
            try:
                await cls._instances[sid]._cleanup()
            finally:
                cls._instances.pop(sid, None)
                logger.info(f"Closed idle browser session: {sid}")

    @classmethod
    async def close_session(cls, session_id: str):
        """Close and remove a session"""
        async with cls._lock:
            if session_id in cls._instances:
                session = cls._instances[session_id]
                await session._cleanup()
                del cls._instances[session_id]
                logger.info(f"Closed browser session: {session_id}")

    @classmethod
    async def close_all_sessions(cls):
        """Close all active sessions"""
        async with cls._lock:
            for session_id in list(cls._instances.keys()):
                await cls._instances[session_id]._cleanup()
            cls._instances.clear()
            logger.info("Closed all browser sessions")

    async def _initialize(self):
        """Initialize browser instance"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--disable-gpu",
            ],
        )
        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        await self.context.route("**/*", self._guard_route)
        self.context.on("page", self._on_context_page)

    async def _guard_route(self, route):
        if _is_url_allowed(route.request.url):
            await route.continue_()
        else:
            await route.abort()

    async def _cleanup(self):
        """Cleanup browser resources"""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            logger.error(f"Error cleaning up browser session: {e}")

    async def new_page(self, page_id: str | None = None) -> tuple[str, Page]:
        """Create a new page/tab"""
        if not self.context:
            raise RuntimeError("Browser session not initialized")
        if len(self.pages) >= MAX_PAGES_PER_SESSION:
            raise RuntimeError(f"Browser page capacity reached for session ({MAX_PAGES_PER_SESSION})")

        page = await self.context.new_page()
        page_id = page_id or f"page_{len(self.pages) + 1}"
        self.pages[page_id] = page
        self.current_page_id = page_id

        # Initialize page state
        state = PageState()
        self._page_state_store[id(page)] = state

        # Attach event listeners
        self._attach_page_listeners(page, state)

        logger.info(f"Created new page: {page_id}")
        return page_id, page

    def _attach_page_listeners(self, page: Page, state: PageState):
        """Attach event listeners to track page state"""

        def on_console(msg):
            state.add_console(
                msg_type=msg.type,
                text=msg.text,
                location={"url": msg.location.get("url")} if msg.location else None,
            )

        def on_page_error(err):
            state.add_error(
                message=str(err),
                name=type(err).__name__,
            )

        def on_request(request):
            state.add_request(
                method=request.method,
                url=request.url,
                resource_type=request.resource_type,
            )

        def on_response(response):
            # Find and update matching request
            for req in reversed(state.requests):
                if req.url == response.url and req.status is None:
                    req.status = response.status
                    req.ok = response.ok
                    break

        def on_close():
            # Find and remove this page from session tracking
            page_id_to_remove = next((pid for pid, p in self.pages.items() if p is page), None)
            if page_id_to_remove:
                self.pages.pop(page_id_to_remove, None)
                self._page_state_store.pop(id(page), None)
                if self.current_page_id == page_id_to_remove:
                    # Fall back to the most recently opened non-popup page, or any page
                    self.current_page_id = next(
                        (pid for pid in reversed(list(self.pages.keys())) if pid.startswith("page_")),
                        next(iter(self.pages.keys()), None),
                    )
                logger.info(f"Page '{page_id_to_remove}' closed, current_page_id={self.current_page_id}")

        page.on("console", on_console)
        page.on("pageerror", on_page_error)
        page.on("request", on_request)
        page.on("response", on_response)
        page.on("close", on_close)
        page.on("crash", on_close)

        def on_popup(popup_page):
            asyncio.ensure_future(self._register_popup(popup_page))

        page.on("popup", on_popup)

    async def get_page(self, page_id: str | None = None) -> Page:
        """Get a page by ID or current page.

        If the requested page is closed/crashed, it is removed and we fall
        back to the most recent non-popup page (or create a new one).
        """
        page_id = page_id or self.current_page_id

        if page_id and page_id in self.pages:
            page = self.pages[page_id]
            if not page.is_closed():
                return page
            # Page is closed — clean it up and fall through to fallback
            logger.warning(f"Page '{page_id}' is closed, recovering session")
            self.pages.pop(page_id, None)
            self._page_state_store.pop(id(page), None)
            if self.current_page_id == page_id:
                self.current_page_id = next(
                    (pid for pid in reversed(list(self.pages.keys())) if pid.startswith("page_")),
                    next(iter(self.pages.keys()), None),
                )
            page_id = self.current_page_id

        if not page_id or page_id not in self.pages:
            # No usable page — create a fresh one
            page_id, page = await self.new_page()
            return page

        return self.pages[page_id]

    def get_page_state(self, page: Page) -> PageState:
        """Get state for a page"""
        page_key = id(page)
        if page_key not in self._page_state_store:
            self._page_state_store[page_key] = PageState()
        return self._page_state_store[page_key]

    async def close_page(self, page_id: str):
        """Close a specific page"""
        if page_id in self.pages:
            page = self.pages[page_id]
            page_key = id(page)
            await page.close()
            del self.pages[page_id]
            if page_key in self._page_state_store:
                del self._page_state_store[page_key]
            if self.current_page_id == page_id:
                self.current_page_id = next(iter(self.pages.keys()), None)
            logger.info(f"Closed page: {page_id}")

    async def list_pages(self) -> list[dict[str, Any]]:
        """List all open pages"""
        pages_info = []
        for page_id, page in self.pages.items():
            try:
                pages_info.append(
                    {
                        "id": page_id,
                        "url": page.url,
                        "title": await page.title(),
                        "is_current": page_id == self.current_page_id,
                    }
                )
            except Exception:
                pages_info.append(
                    {
                        "id": page_id,
                        "url": "unknown",
                        "title": "unknown",
                        "is_current": page_id == self.current_page_id,
                    }
                )
        return pages_info

    def _on_context_page(self, new_page: "Page"):
        """Called when context opens a new page (e.g. target=_blank links)."""
        asyncio.ensure_future(self._register_popup(new_page))

    async def _register_popup(self, popup_page: "Page") -> str:
        """Register a popup or new page opened by an existing page.

        Idempotent: skips pages already registered (e.g. fired by both
        page.on("popup") and context.on("page") for the same popup, or
        pages explicitly created via new_page()).

        Does NOT change current_page_id — the active page stays on whatever
        the agent was working with. Use wait_for_new_page() to explicitly
        switch to the popup when needed.
        """
        if any(p is popup_page for p in self.pages.values()):
            return ""
        page_id = f"popup_{len(self.pages) + 1}"
        self.pages[page_id] = popup_page
        # Do NOT set current_page_id here — an unexpected popup (e.g. a
        # "Play" button opening a new tab) must not hijack the active page.
        # The agent calls wait_for_new_page() explicitly when it needs the popup.
        state = PageState()
        self._page_state_store[id(popup_page)] = state
        self._attach_page_listeners(popup_page, state)
        logger.info(f"Auto-registered popup/new-page as: {page_id}")
        return page_id

    async def wait_for_new_page(self, existing_page_ids: set, timeout_ms: int = 15000) -> "str | None":
        """Poll until a new page_id appears that is not in existing_page_ids."""
        deadline = asyncio.get_event_loop().time() + timeout_ms / 1000
        while asyncio.get_event_loop().time() < deadline:
            new_ids = set(self.pages.keys()) - existing_page_ids
            if new_ids:
                return next(iter(new_ids))
            await asyncio.sleep(0.2)
        return None


def to_ai_friendly_error(error: Exception, context: str) -> str:
    """Convert Playwright errors to AI-friendly messages"""
    message = str(error)

    # Strict mode: multiple elements matched
    if "strict mode violation" in message.lower():
        count_match = re.search(r"resolved to (\d+) elements", message)
        count = count_match.group(1) if count_match else "multiple"
        return (
            f'Selector "{context}" matched {count} elements. '
            f"Run a new snapshot to get updated refs, or use a more specific selector."
        )

    # Element not visible/found
    if ("timeout" in message.lower() or "waiting for" in message.lower()) and (
        "visible" in message.lower() or "not found" in message.lower()
    ):
        return f'Element "{context}" not found or not visible. Run a new snapshot to see current page elements.'

    # Element covered/not interactable
    if (
        "intercepts pointer events" in message.lower()
        or "not visible" in message.lower()
        or "not receive pointer events" in message.lower()
    ):
        return (
            f'Element "{context}" is not interactable (hidden or covered). '
            f"Try scrolling it into view, closing overlays, or re-snapshotting."
        )

    return message
