"""Async HTTP client for the synkora-scraper microservice."""

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SCRAPER_SERVICE_URL = os.getenv("SCRAPER_SERVICE_URL", "http://synkora-scraper:5003")
SCRAPER_API_KEY = os.getenv("SCRAPER_API_KEY")


class ScraperServiceClient:
    """Thin async client wrapping the scraper microservice HTTP API."""

    def __init__(self, base_url: str = SCRAPER_SERVICE_URL, api_key: str | None = SCRAPER_API_KEY):
        self._base_url = base_url
        self._api_key = api_key
        self._client: httpx.AsyncClient | None = None

    def _headers(self) -> dict[str, str]:
        return {"X-Scraper-Key": self._api_key} if self._api_key else {}

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=180.0)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # -----------------------------------------------------------------------
    # App-store scraping
    # -----------------------------------------------------------------------

    async def scrape_google_play(
        self,
        app_id: str,
        country: str = "us",
        lang: str = "en",
        count: int = 200,
    ) -> list[dict[str, Any]]:
        payload = {"app_id": app_id, "country": country, "lang": lang, "count": count}
        r = await self._get_client().post(
            "/v1/scrape/google-play",
            json=payload,
            headers=self._headers(),
            timeout=180.0,
        )
        r.raise_for_status()
        return r.json()["reviews"]

    async def scrape_apple(
        self,
        app_id: str,
        country: str = "us",
        count: int = 200,
    ) -> list[dict[str, Any]]:
        payload = {"app_id": app_id, "country": country, "count": count}
        r = await self._get_client().post(
            "/v1/scrape/apple",
            json=payload,
            headers=self._headers(),
            timeout=180.0,
        )
        r.raise_for_status()
        return r.json()["reviews"]

    # -----------------------------------------------------------------------
    # Browser – helper
    # -----------------------------------------------------------------------

    async def _browser(self, path: str, payload: dict[str, Any], timeout: float = 60.0) -> dict[str, Any]:
        try:
            r = await self._get_client().post(path, json=payload, headers=self._headers(), timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.error("Scraper browser call %s failed: %s", path, e)
            raise  # re-raise so callers can decide; browser_interactive wraps with try/except

    # -----------------------------------------------------------------------
    # Browser – navigation & page info
    # -----------------------------------------------------------------------

    async def browser_render_html(
        self,
        html: str,
        session_id: str = "default",
        viewport_width: int = 1200,
        viewport_height: int = 900,
    ) -> dict[str, Any]:
        """Load raw HTML into a browser session via page.set_content()."""
        return await self._browser(
            "/v1/browser/render-html",
            {
                "html": html,
                "session_id": session_id,
                "viewport_width": viewport_width,
                "viewport_height": viewport_height,
            },
            timeout=30.0,
        )

    async def browser_navigate(self, url: str, session_id: str = "default", **kwargs) -> dict[str, Any]:
        return await self._browser("/v1/browser/navigate", {"url": url, "session_id": session_id, **kwargs})

    async def browser_snapshot(self, session_id: str = "default", **kwargs) -> dict[str, Any]:
        return await self._browser("/v1/browser/snapshot", {"session_id": session_id, **kwargs})

    async def browser_screenshot(self, session_id: str = "default", **kwargs) -> dict[str, Any]:
        return await self._browser("/v1/browser/screenshot", {"session_id": session_id, **kwargs})

    async def browser_pdf(self, session_id: str = "default", **kwargs) -> dict[str, Any]:
        return await self._browser("/v1/browser/pdf", {"session_id": session_id, **kwargs})

    # -----------------------------------------------------------------------
    # Browser – interactions
    # -----------------------------------------------------------------------

    async def browser_click(self, ref: str, session_id: str = "default", **kwargs) -> dict[str, Any]:
        return await self._browser("/v1/browser/click", {"ref": ref, "session_id": session_id, **kwargs})

    async def browser_fill(self, ref: str, text: str, session_id: str = "default", **kwargs) -> dict[str, Any]:
        return await self._browser("/v1/browser/fill", {"ref": ref, "text": text, "session_id": session_id, **kwargs})

    async def browser_type(self, ref: str, text: str, session_id: str = "default", **kwargs) -> dict[str, Any]:
        return await self._browser("/v1/browser/type", {"ref": ref, "text": text, "session_id": session_id, **kwargs})

    async def browser_fill_form(self, fields: list[dict], session_id: str = "default", **kwargs) -> dict[str, Any]:
        return await self._browser("/v1/browser/fill-form", {"fields": fields, "session_id": session_id, **kwargs})

    async def browser_select(
        self, ref: str, values: list[str], session_id: str = "default", **kwargs
    ) -> dict[str, Any]:
        return await self._browser(
            "/v1/browser/select", {"ref": ref, "values": values, "session_id": session_id, **kwargs}
        )

    async def browser_check(self, ref: str, session_id: str = "default", **kwargs) -> dict[str, Any]:
        return await self._browser("/v1/browser/check", {"ref": ref, "session_id": session_id, **kwargs})

    async def browser_press(self, key: str, session_id: str = "default", **kwargs) -> dict[str, Any]:
        return await self._browser("/v1/browser/press", {"key": key, "session_id": session_id, **kwargs})

    async def browser_hover(self, ref: str, session_id: str = "default", **kwargs) -> dict[str, Any]:
        return await self._browser("/v1/browser/hover", {"ref": ref, "session_id": session_id, **kwargs})

    async def browser_drag(
        self, source_ref: str, target_ref: str, session_id: str = "default", **kwargs
    ) -> dict[str, Any]:
        return await self._browser(
            "/v1/browser/drag", {"source_ref": source_ref, "target_ref": target_ref, "session_id": session_id, **kwargs}
        )

    async def browser_scroll_into_view(self, ref: str, session_id: str = "default", **kwargs) -> dict[str, Any]:
        return await self._browser("/v1/browser/scroll-into-view", {"ref": ref, "session_id": session_id, **kwargs})

    async def browser_evaluate(self, expression: str, session_id: str = "default", **kwargs) -> dict[str, Any]:
        return await self._browser(
            "/v1/browser/evaluate", {"expression": expression, "session_id": session_id, **kwargs}
        )

    # -----------------------------------------------------------------------
    # Browser – wait / timing
    # -----------------------------------------------------------------------

    async def browser_wait(self, session_id: str = "default", **kwargs) -> dict[str, Any]:
        return await self._browser("/v1/browser/wait", {"session_id": session_id, **kwargs}, timeout=120.0)

    async def browser_wait_for_new_page(self, session_id: str = "default", **kwargs) -> dict[str, Any]:
        return await self._browser("/v1/browser/wait-for-new-page", {"session_id": session_id, **kwargs}, timeout=30.0)

    # -----------------------------------------------------------------------
    # Browser – cookies & storage
    # -----------------------------------------------------------------------

    async def browser_get_cookies(self, session_id: str = "default", **kwargs) -> dict[str, Any]:
        return await self._browser("/v1/browser/get-cookies", {"session_id": session_id, **kwargs})

    async def browser_set_cookies(self, cookies: list[dict], session_id: str = "default", **kwargs) -> dict[str, Any]:
        return await self._browser("/v1/browser/set-cookies", {"cookies": cookies, "session_id": session_id, **kwargs})

    async def browser_clear_cookies(self, session_id: str = "default", **kwargs) -> dict[str, Any]:
        return await self._browser("/v1/browser/clear-cookies", {"session_id": session_id, **kwargs})

    async def browser_get_storage(self, session_id: str = "default", **kwargs) -> dict[str, Any]:
        return await self._browser("/v1/browser/get-storage", {"session_id": session_id, **kwargs})

    async def browser_set_storage(self, session_id: str = "default", **kwargs) -> dict[str, Any]:
        return await self._browser("/v1/browser/set-storage", {"session_id": session_id, **kwargs})

    async def browser_clear_storage(self, session_id: str = "default", **kwargs) -> dict[str, Any]:
        return await self._browser("/v1/browser/clear-storage", {"session_id": session_id, **kwargs})

    # -----------------------------------------------------------------------
    # Browser – page management
    # -----------------------------------------------------------------------

    async def browser_new_page(self, session_id: str = "default", **kwargs) -> dict[str, Any]:
        return await self._browser("/v1/browser/new-page", {"session_id": session_id, **kwargs})

    async def browser_close_page(self, page_id: str, session_id: str = "default", **kwargs) -> dict[str, Any]:
        return await self._browser("/v1/browser/close-page", {"page_id": page_id, "session_id": session_id, **kwargs})

    async def browser_list_pages(self, session_id: str = "default", **kwargs) -> dict[str, Any]:
        return await self._browser("/v1/browser/list-pages", {"session_id": session_id, **kwargs})

    async def browser_list_frames(self, session_id: str = "default", **kwargs) -> dict[str, Any]:
        return await self._browser("/v1/browser/list-frames", {"session_id": session_id, **kwargs})

    async def browser_close_session(self, session_id: str = "default", **kwargs) -> dict[str, Any]:
        return await self._browser("/v1/browser/close-session", {"session_id": session_id, **kwargs})

    async def browser_resize(self, width: int, height: int, session_id: str = "default", **kwargs) -> dict[str, Any]:
        return await self._browser(
            "/v1/browser/resize", {"width": width, "height": height, "session_id": session_id, **kwargs}
        )

    async def browser_handle_dialog(self, session_id: str = "default", **kwargs) -> dict[str, Any]:
        return await self._browser("/v1/browser/handle-dialog", {"session_id": session_id, **kwargs})

    async def browser_upload_file(
        self, file_ref: str, file_paths: list[str], session_id: str = "default", **kwargs
    ) -> dict[str, Any]:
        return await self._browser(
            "/v1/browser/upload-file",
            {"file_ref": file_ref, "file_paths": file_paths, "session_id": session_id, **kwargs},
        )

    # -----------------------------------------------------------------------
    # Browser – diagnostics
    # -----------------------------------------------------------------------

    async def browser_get_console(self, session_id: str = "default", **kwargs) -> dict[str, Any]:
        return await self._browser("/v1/browser/get-console", {"session_id": session_id, **kwargs})

    async def browser_get_errors(self, session_id: str = "default", **kwargs) -> dict[str, Any]:
        return await self._browser("/v1/browser/get-errors", {"session_id": session_id, **kwargs})

    async def browser_get_network_requests(self, session_id: str = "default", **kwargs) -> dict[str, Any]:
        return await self._browser("/v1/browser/get-network", {"session_id": session_id, **kwargs})

    # -----------------------------------------------------------------------
    # Browser – advanced context settings
    # -----------------------------------------------------------------------

    async def browser_set_offline(self, offline: bool, session_id: str = "default", **kwargs) -> dict[str, Any]:
        return await self._browser("/v1/browser/set-offline", {"offline": offline, "session_id": session_id, **kwargs})

    async def browser_set_extra_headers(
        self, headers: dict[str, str], session_id: str = "default", **kwargs
    ) -> dict[str, Any]:
        return await self._browser(
            "/v1/browser/set-extra-headers", {"headers": headers, "session_id": session_id, **kwargs}
        )

    async def browser_set_http_credentials(
        self, username: str, password: str, session_id: str = "default", **kwargs
    ) -> dict[str, Any]:
        return await self._browser(
            "/v1/browser/set-http-credentials",
            {"username": username, "password": password, "session_id": session_id, **kwargs},
        )

    async def browser_focus_page(self, session_id: str = "default", **kwargs) -> dict[str, Any]:
        return await self._browser("/v1/browser/focus-page", {"session_id": session_id, **kwargs})

    # -----------------------------------------------------------------------
    # Simple one-shot browser operations (from browser_tools.py)
    # -----------------------------------------------------------------------

    async def browser_simple_navigate(self, url: str, wait_for: str = "domcontentloaded") -> dict[str, Any]:
        return await self._browser("/v1/browser/simple-navigate", {"url": url, "wait_for": wait_for})

    async def browser_extract_links(self, url: str) -> dict[str, Any]:
        return await self._browser("/v1/browser/extract-links", {"url": url})

    async def browser_extract_structured_data(self, url: str, selector: str) -> dict[str, Any]:
        return await self._browser("/v1/browser/extract-structured-data", {"url": url, "selector": selector})

    async def browser_check_element_exists(self, url: str, selector: str) -> dict[str, Any]:
        return await self._browser("/v1/browser/check-element-exists", {"url": url, "selector": selector})

    # -----------------------------------------------------------------------
    # Geolocation / proxy (from browser_geolocation.py)
    # -----------------------------------------------------------------------

    async def browser_set_country(
        self,
        country_code: str,
        session_id: str = "default",
        apply_to_existing: bool = True,
        proxy_url: str | None = None,
        custom_latitude: float | None = None,
        custom_longitude: float | None = None,
        custom_timezone: str | None = None,
        custom_locale: str | None = None,
    ) -> dict[str, Any]:
        return await self._browser(
            "/v1/browser/set-country",
            {
                "country_code": country_code,
                "session_id": session_id,
                "apply_to_existing": apply_to_existing,
                "proxy_url": proxy_url,
                "custom_latitude": custom_latitude,
                "custom_longitude": custom_longitude,
                "custom_timezone": custom_timezone,
                "custom_locale": custom_locale,
            },
        )

    async def browser_set_geolocation(
        self,
        latitude: float,
        longitude: float,
        accuracy: float = 100,
        session_id: str = "default",
    ) -> dict[str, Any]:
        return await self._browser(
            "/v1/browser/set-geolocation",
            {
                "latitude": latitude,
                "longitude": longitude,
                "accuracy": accuracy,
                "session_id": session_id,
            },
        )

    async def browser_get_location(self, session_id: str = "default") -> dict[str, Any]:
        return await self._browser("/v1/browser/get-location", {"session_id": session_id})

    async def browser_set_proxy(self, proxy_url: str, session_id: str = "default") -> dict[str, Any]:
        return await self._browser("/v1/browser/set-proxy", {"proxy_url": proxy_url, "session_id": session_id})

    async def browser_clear_proxy(self, session_id: str = "default") -> dict[str, Any]:
        return await self._browser("/v1/browser/clear-proxy", {"session_id": session_id})


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_scraper_client: ScraperServiceClient | None = None


def get_scraper_client() -> ScraperServiceClient:
    global _scraper_client
    if _scraper_client is None:
        _scraper_client = ScraperServiceClient()
    return _scraper_client
