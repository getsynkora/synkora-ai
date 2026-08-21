"""
Interactive Browser Tools — proxied to the synkora-scraper microservice.

All functions maintain the same signatures as before so that callers
(agent tools, etc.) continue to work unchanged.  Internally every call is
forwarded to the scraper service via ScraperServiceClient.

The screenshot endpoint returns ``image_base64`` from the scraper; this proxy
then uploads the bytes to S3 and returns a presigned URL — keeping S3 logic
in the API where credentials are available.
"""

import logging
import os
from typing import Any, Literal

from src.services.agents.internal_tools.browser_session import BrowserSession  # noqa: F401 (kept for test patching)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Timeout constants — kept for backward-compat with callers and tests
# ---------------------------------------------------------------------------
DEFAULT_TIMEOUT: int = 30_000  # ms
MAX_TIMEOUT: int = 120_000  # ms
MIN_TIMEOUT: int = 1_000  # ms


def normalize_timeout(value: int | None, default: int | None = None) -> int:
    """Clamp *value* to [MIN_TIMEOUT, MAX_TIMEOUT], falling back to *default*."""
    if default is None:
        default = DEFAULT_TIMEOUT
    if value is None:
        return default
    return max(MIN_TIMEOUT, min(MAX_TIMEOUT, value))


def _get_workspace_path(config: dict | None) -> str | None:
    """Extract workspace_path from a tool config dict."""
    if not config:
        return None
    return config.get("workspace_path")


def _validate_path_in_workspace(path: str, workspace: str | None) -> tuple[bool, str | None]:
    """Return (True, None) if *path* is inside *workspace*, else (False, reason)."""
    if workspace is None:
        return False, "No workspace path available"
    resolved_path = os.path.realpath(path)
    resolved_workspace = os.path.realpath(workspace)
    if not resolved_path.startswith(resolved_workspace):
        return False, f"Path is outside workspace: {path}"
    return True, None


def _get_locator_strategies(page: Any, ref: str, state: Any = None) -> list:
    """Return a list of Playwright locator strategies for *ref*."""
    strategies = []
    if state is not None and hasattr(state, "element_refs") and ref in state.element_refs:
        element_ref = state.element_refs[ref]
        selector = getattr(element_ref, "selector", None)
        role = getattr(element_ref, "role", None)
        name = getattr(element_ref, "name", "")
        nth = getattr(element_ref, "nth", 0)
        if selector:
            strategies.append(page.locator(selector))
        if role:
            role_loc = page.get_by_role(role, name=name)
            strategies.append(role_loc.nth(nth) if nth else role_loc)
    if not strategies:
        strategies.append(page.locator(ref))
    return strategies


def _resolve_locator(page: Any, ref: str, state: Any = None) -> Any:
    """Resolve *ref* to the first available Playwright locator."""
    strategies = _get_locator_strategies(page, ref, state)
    return strategies[0] if strategies else page.locator(ref)


def _scraper():
    from src.core.scraper_client import get_scraper_client

    return get_scraper_client()


async def _call(coro) -> dict:
    """Await *coro* and return its result; convert any exception to ``{"success": False}``."""
    try:
        return await coro
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# NAVIGATION
# =============================================================================


async def internal_browser_navigate(
    url: str,
    session_id: str = "default",
    page_id: str | None = None,
    wait_until: Literal["load", "domcontentloaded", "networkidle"] = "load",
    timeout_ms: int | None = None,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Navigate to a URL in the browser."""
    return await _call(
        _scraper().browser_navigate(
            url=url,
            session_id=session_id,
            page_id=page_id,
            wait_until=wait_until,
            timeout_ms=timeout_ms,
        )
    )


# =============================================================================
# SNAPSHOT
# =============================================================================


async def internal_browser_snapshot(
    session_id: str = "default",
    page_id: str | None = None,
    interactive_only: bool = True,
    max_elements: int = 150,
    include_text: bool = True,
    frame_selector: str | None = None,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Get AI-friendly snapshot of the page with element refs."""
    return await _call(
        _scraper().browser_snapshot(
            session_id=session_id,
            page_id=page_id,
            interactive_only=interactive_only,
            max_elements=max_elements,
            include_text=include_text,
            frame_selector=frame_selector,
        )
    )


# =============================================================================
# CLICK
# =============================================================================


async def internal_browser_click(
    ref: str,
    session_id: str = "default",
    page_id: str | None = None,
    double_click: bool = False,
    button: Literal["left", "right", "middle"] = "left",
    modifiers: list[str] | None = None,
    timeout_ms: int | None = None,
    frame_selector: str | None = None,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Click an element on the page."""
    return await _call(
        _scraper().browser_click(
            ref=ref,
            session_id=session_id,
            page_id=page_id,
            double_click=double_click,
            button=button,
            modifiers=modifiers,
            timeout_ms=timeout_ms,
            frame_selector=frame_selector,
        )
    )


# =============================================================================
# FILL / TYPE
# =============================================================================


async def internal_browser_fill(
    ref: str,
    text: str,
    session_id: str = "default",
    page_id: str | None = None,
    clear_first: bool = True,
    timeout_ms: int | None = None,
    frame_selector: str | None = None,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fill text into an input field."""
    return await _call(
        _scraper().browser_fill(
            ref=ref,
            text=text,
            session_id=session_id,
            page_id=page_id,
            clear_first=clear_first,
            timeout_ms=timeout_ms,
            frame_selector=frame_selector,
        )
    )


async def internal_browser_type(
    ref: str,
    text: str,
    session_id: str = "default",
    page_id: str | None = None,
    delay_ms: int = 0,
    submit: bool = False,
    timeout_ms: int | None = None,
    frame_selector: str | None = None,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Type text character by character."""
    return await _call(
        _scraper().browser_type(
            ref=ref,
            text=text,
            session_id=session_id,
            page_id=page_id,
            delay_ms=delay_ms,
            submit=submit,
            timeout_ms=timeout_ms,
            frame_selector=frame_selector,
        )
    )


async def internal_browser_fill_form(
    fields: list[dict[str, Any]],
    session_id: str = "default",
    page_id: str | None = None,
    submit_ref: str | None = None,
    timeout_ms: int | None = None,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fill multiple form fields at once."""
    return await _call(
        _scraper().browser_fill_form(
            fields=fields,
            session_id=session_id,
            page_id=page_id,
            submit_ref=submit_ref,
            timeout_ms=timeout_ms,
        )
    )


# =============================================================================
# SELECT / CHECK / PRESS
# =============================================================================


async def internal_browser_select(
    ref: str,
    values: list[str],
    session_id: str = "default",
    page_id: str | None = None,
    timeout_ms: int | None = None,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Select option(s) from a dropdown."""
    return await _call(
        _scraper().browser_select(
            ref=ref,
            values=values,
            session_id=session_id,
            page_id=page_id,
            timeout_ms=timeout_ms,
        )
    )


async def internal_browser_check(
    ref: str,
    checked: bool = True,
    session_id: str = "default",
    page_id: str | None = None,
    timeout_ms: int | None = None,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Check or uncheck a checkbox/radio button."""
    return await _call(
        _scraper().browser_check(
            ref=ref,
            checked=checked,
            session_id=session_id,
            page_id=page_id,
            timeout_ms=timeout_ms,
        )
    )


async def internal_browser_press(
    key: str,
    session_id: str = "default",
    page_id: str | None = None,
    ref: str | None = None,
    timeout_ms: int | None = None,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Press a keyboard key."""
    return await _call(
        _scraper().browser_press(
            key=key,
            session_id=session_id,
            page_id=page_id,
            ref=ref,
            timeout_ms=timeout_ms,
        )
    )


# =============================================================================
# WAIT
# =============================================================================


async def internal_browser_wait(
    session_id: str = "default",
    page_id: str | None = None,
    time_ms: int | None = None,
    selector: str | None = None,
    text: str | None = None,
    text_gone: str | None = None,
    url_pattern: str | None = None,
    load_state: Literal["load", "domcontentloaded", "networkidle"] | None = None,
    timeout_ms: int | None = None,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Wait for various conditions."""
    return await _call(
        _scraper().browser_wait(
            session_id=session_id,
            page_id=page_id,
            time_ms=time_ms,
            selector=selector,
            text=text,
            text_gone=text_gone,
            url_pattern=url_pattern,
            load_state=load_state,
            timeout_ms=timeout_ms,
        )
    )


# =============================================================================
# SCREENSHOT
# =============================================================================


async def internal_browser_screenshot(
    session_id: str = "default",
    page_id: str | None = None,
    ref: str | None = None,
    full_page: bool = False,
    image_type: Literal["png", "jpeg"] = "png",
    quality: int | None = None,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Take a screenshot.

    The scraper service captures the screenshot and returns base64 data.
    This proxy uploads to S3 and returns a presigned URL when tenant context
    is available, or falls back to returning the base64 data directly.
    """
    from datetime import UTC, datetime
    from urllib.parse import urlparse
    from uuid import uuid4

    try:
        scraper_result = await _scraper().browser_screenshot(
            session_id=session_id,
            page_id=page_id,
            ref=ref,
            full_page=full_page,
            image_type=image_type,
            quality=quality,
        )
    except Exception as e:
        return {"success": False, "error": str(e)}

    if not scraper_result.get("success"):
        return scraper_result

    image_base64 = scraper_result.get("image_base64", "")
    if not image_base64:
        return {"success": False, "error": "Scraper returned no image data"}

    # Get runtime_context from config if not directly provided
    if not runtime_context and config:
        runtime_context = config.get("_runtime_context")

    # Try S3 upload
    try:
        from src.services.storage.s3_storage import get_s3_storage

        s3_storage = get_s3_storage()
        tenant_id = getattr(runtime_context, "tenant_id", None) if runtime_context else None
        agent_id = getattr(runtime_context, "agent_id", None) if runtime_context else None

        if not tenant_id:
            return {
                "success": False,
                "error": "Cannot save screenshot: tenant_id not available in runtime context.",
            }

        import base64 as _b64

        screenshot_bytes = _b64.b64decode(image_base64)
        page_url = scraper_result.get("page_url", "unknown")
        timestamp = datetime.now(UTC)
        date_path = timestamp.strftime("%Y/%m/%d")
        parsed_url = urlparse(page_url)
        domain = parsed_url.netloc.replace(".", "_").replace(":", "_") or "unknown"
        file_id = str(uuid4())[:8]
        ext = "jpg" if image_type == "jpeg" else "png"
        filename = f"screenshot_{domain}_{file_id}.{ext}"
        s3_key = f"tenants/{tenant_id}/screenshots/{date_path}/{filename}"
        content_type = "image/jpeg" if image_type == "jpeg" else "image/png"

        s3_storage.upload_file(
            file_content=screenshot_bytes,
            key=s3_key,
            content_type=content_type,
            metadata={
                "tenant_id": str(tenant_id),
                "agent_id": str(agent_id) if agent_id else "",
                "source_url": page_url,
                "full_page": str(full_page),
                "session_id": session_id,
            },
        )
        image_url = s3_storage.generate_presigned_url(s3_key, expiration=604800)
        logger.info(f"Screenshot saved to S3: {s3_key}")

        return {
            "success": True,
            "image_url": image_url,
            "format": image_type,
            "full_page": full_page if not ref else False,
            "element_ref": ref,
            "page_url": page_url,
            "session_id": session_id,
            "message": (
                f"Screenshot captured. IMPORTANT: Share this EXACT URL with the user (do not modify it): "
                f"{image_url}\n"
                "To post it in Slack: use internal_slack_post_blocks with an image block referencing this "
                "URL (best resolution), or internal_slack_upload_file with file_url set to this URL to "
                "attach it as a native Slack file. Do not call internal_slack_upload_file without either "
                "file_content or file_url."
            ),
        }

    except Exception as e:
        logger.error(f"S3 upload failed: {e}. Returning base64 fallback.")
        return {
            "success": True,
            "image_base64": image_base64,
            "format": image_type,
            "full_page": full_page if not ref else False,
            "element_ref": ref,
            "page_url": scraper_result.get("page_url", ""),
            "session_id": session_id,
            "message": "Screenshot captured as base64 (S3 upload unavailable).",
        }


# =============================================================================
# COOKIES
# =============================================================================


async def internal_browser_get_cookies(
    session_id: str = "default",
    page_id: str | None = None,
    urls: list[str] | None = None,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Get cookies from the browser context."""
    return await _call(_scraper().browser_get_cookies(session_id=session_id, page_id=page_id, urls=urls))


async def internal_browser_set_cookies(
    cookies: list[dict[str, Any]],
    session_id: str = "default",
    page_id: str | None = None,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Set cookies in the browser context."""
    return await _call(_scraper().browser_set_cookies(cookies=cookies, session_id=session_id, page_id=page_id))


async def internal_browser_clear_cookies(
    session_id: str = "default",
    page_id: str | None = None,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Clear all cookies from the browser context."""
    return await _call(_scraper().browser_clear_cookies(session_id=session_id, page_id=page_id))


# =============================================================================
# PAGE MANAGEMENT
# =============================================================================


async def internal_browser_new_page(
    session_id: str = "default",
    url: str | None = None,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Open a new browser tab/page."""
    return await _call(_scraper().browser_new_page(session_id=session_id, url=url))


async def internal_browser_close_page(
    page_id: str,
    session_id: str = "default",
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Close a browser tab/page."""
    return await _call(_scraper().browser_close_page(page_id=page_id, session_id=session_id))


async def internal_browser_list_pages(
    session_id: str = "default",
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """List all open browser tabs/pages."""
    return await _call(_scraper().browser_list_pages(session_id=session_id))


async def internal_browser_list_frames(
    session_id: str = "default",
    page_id: str | None = None,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """List all frames/iframes on the current page."""
    return await _call(_scraper().browser_list_frames(session_id=session_id, page_id=page_id))


async def internal_browser_wait_for_new_page(
    session_id: str = "default",
    timeout_ms: int = 15000,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Wait for a new browser tab or popup to open."""
    return await _call(_scraper().browser_wait_for_new_page(session_id=session_id, timeout_ms=timeout_ms))


async def internal_browser_close_session(
    session_id: str = "default",
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Close browser session and all its pages."""
    return await _call(_scraper().browser_close_session(session_id=session_id))


# =============================================================================
# INTERACTIONS
# =============================================================================


async def internal_browser_hover(
    ref: str,
    session_id: str = "default",
    page_id: str | None = None,
    timeout_ms: int | None = None,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Hover over an element on the page."""
    return await _call(_scraper().browser_hover(ref=ref, session_id=session_id, page_id=page_id, timeout_ms=timeout_ms))


async def internal_browser_scroll_into_view(
    ref: str,
    session_id: str = "default",
    page_id: str | None = None,
    timeout_ms: int | None = None,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Scroll an element into view."""
    return await _call(
        _scraper().browser_scroll_into_view(ref=ref, session_id=session_id, page_id=page_id, timeout_ms=timeout_ms)
    )


async def internal_browser_drag(
    source_ref: str,
    target_ref: str,
    session_id: str = "default",
    page_id: str | None = None,
    timeout_ms: int | None = None,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Drag an element and drop it onto another element."""
    return await _call(
        _scraper().browser_drag(
            source_ref=source_ref,
            target_ref=target_ref,
            session_id=session_id,
            page_id=page_id,
            timeout_ms=timeout_ms,
        )
    )


async def internal_browser_handle_dialog(
    action: Literal["accept", "dismiss"] = "accept",
    prompt_text: str | None = None,
    session_id: str = "default",
    page_id: str | None = None,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Set up a handler for JavaScript dialogs."""
    return await _call(
        _scraper().browser_handle_dialog(
            session_id=session_id,
            page_id=page_id,
            action=action,
            prompt_text=prompt_text,
        )
    )


async def internal_browser_upload_file(
    file_ref: str,
    file_paths: list[str],
    session_id: str = "default",
    page_id: str | None = None,
    timeout_ms: int | None = None,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Upload file(s) to a file input element."""
    return await _call(
        _scraper().browser_upload_file(
            file_ref=file_ref,
            file_paths=file_paths,
            session_id=session_id,
            page_id=page_id,
            timeout_ms=timeout_ms,
        )
    )


async def internal_browser_evaluate(
    expression: str,
    session_id: str = "default",
    page_id: str | None = None,
    ref: str | None = None,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate JavaScript expression in the browser."""
    return await _call(
        _scraper().browser_evaluate(
            expression=expression,
            session_id=session_id,
            page_id=page_id,
            ref=ref,
        )
    )


# =============================================================================
# RESIZE / PDF
# =============================================================================


async def internal_browser_resize(
    width: int,
    height: int,
    session_id: str = "default",
    page_id: str | None = None,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resize the browser viewport."""
    return await _call(_scraper().browser_resize(width=width, height=height, session_id=session_id, page_id=page_id))


async def internal_browser_pdf(
    session_id: str = "default",
    page_id: str | None = None,
    path: str | None = None,
    format: str = "Letter",
    print_background: bool = True,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate a PDF of the current page (returns base64 data)."""
    try:
        result = await _scraper().browser_pdf(
            session_id=session_id, page_id=page_id, format=format, print_background=print_background
        )
    except Exception as exc:
        return {"success": False, "error": f"Browser PDF failed: {exc}"}

    # If a local path was requested, save the decoded bytes
    if result.get("success") and path and result.get("pdf_base64"):
        import base64
        import os

        # Validate path is within workspace before writing
        workspace_path = config.get("workspace_path") if config else None
        if not workspace_path and config:
            rc = config.get("_runtime_context")
            if rc and getattr(rc, "tenant_id", None):
                import uuid as _uuid

                from src.services.agents.workspace_manager import get_workspace_manager

                tenant_id = rc.tenant_id
                conversation_id = getattr(rc, "conversation_id", None) or _uuid.uuid5(tenant_id, "background_tasks")
                workspace_path = get_workspace_manager().get_or_create_workspace(tenant_id, conversation_id)
        if workspace_path:
            real_path = os.path.realpath(os.path.abspath(path))
            real_workspace = os.path.realpath(workspace_path)
            if not real_path.startswith(real_workspace + os.sep):
                return {"success": False, "error": f"PDF path must be within workspace: {workspace_path}"}

        pdf_bytes = base64.b64decode(result["pdf_base64"])
        parent_dir = os.path.dirname(path)
        from src.services.agents.internal_tools.git_helpers import async_makedirs, async_write_file_bytes

        if parent_dir:
            await async_makedirs(parent_dir, config)
        await async_write_file_bytes(path, pdf_bytes, config)
        return {"success": True, "action": "pdf", "path": path, "size_bytes": len(pdf_bytes), "session_id": session_id}

    return result


# =============================================================================
# STORAGE
# =============================================================================


async def internal_browser_get_storage(
    storage_type: Literal["local", "session"] = "local",
    key: str | None = None,
    session_id: str = "default",
    page_id: str | None = None,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Get values from localStorage or sessionStorage."""
    return await _call(
        _scraper().browser_get_storage(storage_type=storage_type, key=key, session_id=session_id, page_id=page_id)
    )


async def internal_browser_set_storage(
    storage_type: Literal["local", "session"] = "local",
    items: dict[str, str] | None = None,
    session_id: str = "default",
    page_id: str | None = None,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Set values in localStorage or sessionStorage."""
    return await _call(
        _scraper().browser_set_storage(
            storage_type=storage_type, items=items or {}, session_id=session_id, page_id=page_id
        )
    )


async def internal_browser_clear_storage(
    storage_type: Literal["local", "session"] = "local",
    session_id: str = "default",
    page_id: str | None = None,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Clear localStorage or sessionStorage."""
    return await _call(
        _scraper().browser_clear_storage(storage_type=storage_type, session_id=session_id, page_id=page_id)
    )


# =============================================================================
# DIAGNOSTICS
# =============================================================================


async def internal_browser_get_console(
    session_id: str = "default",
    page_id: str | None = None,
    limit: int = 50,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Get console messages from the page."""
    return await _call(_scraper().browser_get_console(session_id=session_id, page_id=page_id, limit=limit))


async def internal_browser_get_errors(
    session_id: str = "default",
    page_id: str | None = None,
    limit: int = 20,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Get page errors."""
    return await _call(_scraper().browser_get_errors(session_id=session_id, page_id=page_id, limit=limit))


async def internal_browser_get_network_requests(
    session_id: str = "default",
    page_id: str | None = None,
    limit: int = 50,
    filter_type: str | None = None,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Get network requests captured during the session."""
    return await _call(
        _scraper().browser_get_network_requests(
            session_id=session_id, page_id=page_id, limit=limit, filter_type=filter_type
        )
    )


# =============================================================================
# CONTEXT SETTINGS
# =============================================================================


async def internal_browser_set_offline(
    offline: bool,
    session_id: str = "default",
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Toggle offline mode."""
    return await _call(_scraper().browser_set_offline(offline=offline, session_id=session_id))


async def internal_browser_set_extra_headers(
    headers: dict[str, str],
    session_id: str = "default",
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Set extra HTTP headers for all requests."""
    return await _call(_scraper().browser_set_extra_headers(headers=headers, session_id=session_id))


async def internal_browser_set_http_credentials(
    username: str,
    password: str,
    session_id: str = "default",
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Set HTTP authentication credentials."""
    return await _call(
        _scraper().browser_set_http_credentials(username=username, password=password, session_id=session_id)
    )


async def internal_browser_focus_page(
    session_id: str = "default",
    page_id: str | None = None,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Bring the page to the front."""
    return await _call(_scraper().browser_focus_page(session_id=session_id, page_id=page_id))
