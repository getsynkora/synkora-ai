"""
Browser Tools Registry

Registers all browser automation tools with the ADK tool registry.
Provides web scraping, content extraction, and full interactive browser automation.
"""

import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


def _resolve_session_id(kwargs: dict[str, Any], runtime_context: Any) -> str:
    """
    Resolve the browser session_id for a tool call.

    An explicit ``session_id`` kwarg always wins. Otherwise the session is scoped
    to the current conversation (falling back to a stable per-tenant id for
    background tasks with no conversation_id), mirroring
    ``workspace_manager.get_workspace_path_from_config``'s session scoping.

    Without this, every call that omits ``session_id`` would share one global
    "default" browser session/page-pool across every tenant and conversation.
    """
    session_id = kwargs.get("session_id")
    if session_id:
        return session_id

    tenant_id = getattr(runtime_context, "tenant_id", None) if runtime_context else None
    conversation_id = getattr(runtime_context, "conversation_id", None) if runtime_context else None

    if conversation_id:
        return str(conversation_id)
    if tenant_id:
        tenant_uuid = tenant_id if isinstance(tenant_id, uuid.UUID) else uuid.UUID(str(tenant_id))
        return str(uuid.uuid5(tenant_uuid, "browser_background"))
    return "default"


def register_browser_tools(registry):
    """
    Register all browser automation tools with the ADK tool registry.

    Args:
        registry: ADKToolRegistry instance
    """
    # Legacy read-only tools
    # New interactive browser tools
    from src.services.agents.internal_tools.browser_geolocation import (
        internal_browser_clear_proxy,
        internal_browser_get_country_info,
        internal_browser_get_current_location,
        internal_browser_list_countries,
        internal_browser_set_country,
        internal_browser_set_geolocation,
        internal_browser_set_proxy,
    )
    from src.services.agents.internal_tools.browser_interactive import (
        internal_browser_check,
        internal_browser_clear_cookies,
        internal_browser_clear_storage,
        internal_browser_click,
        internal_browser_close_page,
        internal_browser_close_session,
        internal_browser_drag,
        internal_browser_evaluate,
        internal_browser_fill,
        internal_browser_fill_form,
        internal_browser_focus_page,
        internal_browser_get_console,
        internal_browser_get_cookies,
        internal_browser_get_errors,
        internal_browser_get_network_requests,
        internal_browser_get_storage,
        internal_browser_handle_dialog,
        internal_browser_hover,
        internal_browser_list_frames,
        internal_browser_list_pages,
        internal_browser_navigate,
        internal_browser_new_page,
        internal_browser_pdf,
        internal_browser_press,
        internal_browser_resize,
        internal_browser_screenshot,
        internal_browser_scroll_into_view,
        internal_browser_select,
        internal_browser_set_cookies,
        internal_browser_set_extra_headers,
        internal_browser_set_http_credentials,
        internal_browser_set_offline,
        internal_browser_set_storage,
        internal_browser_snapshot,
        internal_browser_type,
        internal_browser_upload_file,
        internal_browser_wait,
        internal_browser_wait_for_new_page,
    )
    from src.services.agents.internal_tools.browser_tools import (
        check_element_exists,
        extract_links,
        extract_structured_data,
        navigate_to_url,
    )

    # =========================================================================
    # LEGACY TOOLS (simple read-only, new browser per call)
    # =========================================================================

    async def navigate_to_url_wrapper(config: dict[str, Any] | None = None, **kwargs):
        return await navigate_to_url(url=kwargs.get("url"))

    async def extract_links_wrapper(config: dict[str, Any] | None = None, **kwargs):
        return await extract_links(url=kwargs.get("url"))

    async def extract_structured_data_wrapper(config: dict[str, Any] | None = None, **kwargs):
        return await extract_structured_data(url=kwargs.get("url"), selector=kwargs.get("selector"))

    async def check_element_exists_wrapper(config: dict[str, Any] | None = None, **kwargs):
        return await check_element_exists(url=kwargs.get("url"), selector=kwargs.get("selector"))

    # =========================================================================
    # INTERACTIVE TOOLS (persistent session, full automation)
    # =========================================================================

    async def browser_navigate_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_navigate(
            url=kwargs.get("url"),
            session_id=_resolve_session_id(kwargs, runtime_context),
            page_id=kwargs.get("page_id"),
            wait_until=kwargs.get("wait_until", "load"),
            timeout_ms=kwargs.get("timeout_ms"),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_snapshot_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_snapshot(
            session_id=_resolve_session_id(kwargs, runtime_context),
            page_id=kwargs.get("page_id"),
            interactive_only=kwargs.get("interactive_only", True),
            max_elements=kwargs.get("max_elements", 150),
            include_text=kwargs.get("include_text", True),
            frame_selector=kwargs.get("frame_selector"),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_click_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_click(
            ref=kwargs.get("ref"),
            session_id=_resolve_session_id(kwargs, runtime_context),
            page_id=kwargs.get("page_id"),
            double_click=kwargs.get("double_click", False),
            button=kwargs.get("button", "left"),
            modifiers=kwargs.get("modifiers"),
            timeout_ms=kwargs.get("timeout_ms"),
            frame_selector=kwargs.get("frame_selector"),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_fill_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_fill(
            ref=kwargs.get("ref"),
            text=kwargs.get("text"),
            session_id=_resolve_session_id(kwargs, runtime_context),
            page_id=kwargs.get("page_id"),
            clear_first=kwargs.get("clear_first", True),
            timeout_ms=kwargs.get("timeout_ms"),
            frame_selector=kwargs.get("frame_selector"),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_type_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_type(
            ref=kwargs.get("ref"),
            text=kwargs.get("text"),
            session_id=_resolve_session_id(kwargs, runtime_context),
            page_id=kwargs.get("page_id"),
            delay_ms=kwargs.get("delay_ms", 0),
            submit=kwargs.get("submit", False),
            timeout_ms=kwargs.get("timeout_ms"),
            frame_selector=kwargs.get("frame_selector"),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_fill_form_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_fill_form(
            fields=kwargs.get("fields", []),
            session_id=_resolve_session_id(kwargs, runtime_context),
            page_id=kwargs.get("page_id"),
            submit_ref=kwargs.get("submit_ref"),
            timeout_ms=kwargs.get("timeout_ms"),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_select_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_select(
            ref=kwargs.get("ref"),
            values=kwargs.get("values", []),
            session_id=_resolve_session_id(kwargs, runtime_context),
            page_id=kwargs.get("page_id"),
            timeout_ms=kwargs.get("timeout_ms"),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_check_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_check(
            ref=kwargs.get("ref"),
            checked=kwargs.get("checked", True),
            session_id=_resolve_session_id(kwargs, runtime_context),
            page_id=kwargs.get("page_id"),
            timeout_ms=kwargs.get("timeout_ms"),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_press_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_press(
            key=kwargs.get("key"),
            session_id=_resolve_session_id(kwargs, runtime_context),
            page_id=kwargs.get("page_id"),
            ref=kwargs.get("ref"),
            timeout_ms=kwargs.get("timeout_ms"),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_wait_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_wait(
            session_id=_resolve_session_id(kwargs, runtime_context),
            page_id=kwargs.get("page_id"),
            time_ms=kwargs.get("time_ms"),
            selector=kwargs.get("selector"),
            text=kwargs.get("text"),
            text_gone=kwargs.get("text_gone"),
            url_pattern=kwargs.get("url_pattern"),
            load_state=kwargs.get("load_state"),
            timeout_ms=kwargs.get("timeout_ms"),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_screenshot_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_screenshot(
            session_id=_resolve_session_id(kwargs, runtime_context),
            page_id=kwargs.get("page_id"),
            ref=kwargs.get("ref"),
            full_page=kwargs.get("full_page", False),
            image_type=kwargs.get("image_type", "png"),
            quality=kwargs.get("quality"),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_get_cookies_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_get_cookies(
            session_id=_resolve_session_id(kwargs, runtime_context),
            page_id=kwargs.get("page_id"),
            urls=kwargs.get("urls"),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_set_cookies_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_set_cookies(
            cookies=kwargs.get("cookies", []),
            session_id=_resolve_session_id(kwargs, runtime_context),
            page_id=kwargs.get("page_id"),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_clear_cookies_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_clear_cookies(
            session_id=_resolve_session_id(kwargs, runtime_context),
            page_id=kwargs.get("page_id"),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_new_page_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_new_page(
            session_id=_resolve_session_id(kwargs, runtime_context),
            url=kwargs.get("url"),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_close_page_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_close_page(
            page_id=kwargs.get("page_id"),
            session_id=_resolve_session_id(kwargs, runtime_context),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_list_pages_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_list_pages(
            session_id=_resolve_session_id(kwargs, runtime_context),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_list_frames_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_list_frames(
            session_id=_resolve_session_id(kwargs, runtime_context),
            page_id=kwargs.get("page_id"),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_wait_for_new_page_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_wait_for_new_page(
            session_id=_resolve_session_id(kwargs, runtime_context),
            timeout_ms=kwargs.get("timeout_ms", 15000),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_close_session_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_close_session(
            session_id=_resolve_session_id(kwargs, runtime_context),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_get_console_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_get_console(
            session_id=_resolve_session_id(kwargs, runtime_context),
            page_id=kwargs.get("page_id"),
            limit=kwargs.get("limit", 50),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_get_errors_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_get_errors(
            session_id=_resolve_session_id(kwargs, runtime_context),
            page_id=kwargs.get("page_id"),
            limit=kwargs.get("limit", 20),
            runtime_context=runtime_context,
            config=config,
        )

    # =========================================================================
    # REGISTER LEGACY TOOLS
    # =========================================================================

    registry.register_tool(
        name="navigate_to_url",
        description="Navigate to a URL and extract the page content including title, text, and metadata. Use this for simple read-only page content extraction. For interactive automation, use internal_browser_navigate instead.",
        parameters={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The complete URL to navigate to (must include http:// or https://)",
                }
            },
            "required": ["url"],
        },
        function=navigate_to_url_wrapper,
    )

    registry.register_tool(
        name="extract_links",
        description="Extract all hyperlinks from a webpage with their text and URLs.",
        parameters={
            "type": "object",
            "properties": {"url": {"type": "string", "description": "The URL of the page to extract links from"}},
            "required": ["url"],
        },
        function=extract_links_wrapper,
    )

    registry.register_tool(
        name="extract_structured_data",
        description="Extract specific elements from a webpage using CSS selectors.",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL of the page to extract data from"},
                "selector": {
                    "type": "string",
                    "description": "CSS selector to identify the elements to extract",
                },
            },
            "required": ["url", "selector"],
        },
        function=extract_structured_data_wrapper,
    )

    registry.register_tool(
        name="check_element_exists",
        description="Check if a specific element exists on a webpage using a CSS selector.",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL of the page to check"},
                "selector": {"type": "string", "description": "CSS selector to check for"},
            },
            "required": ["url", "selector"],
        },
        function=check_element_exists_wrapper,
    )

    # =========================================================================
    # REGISTER INTERACTIVE TOOLS
    # =========================================================================

    registry.register_tool(
        name="internal_browser_navigate",
        description="Navigate to a URL in a persistent browser session. Use this for multi-step browser automation where you need to maintain state (cookies, login sessions, etc.) across multiple actions.",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to navigate to"},
                "session_id": {
                    "type": "string",
                    "description": "Browser session ID (default: 'default')",
                    "default": "default",
                },
                "page_id": {"type": "string", "description": "Specific page/tab ID (optional)"},
                "wait_until": {
                    "type": "string",
                    "enum": ["load", "domcontentloaded", "networkidle"],
                    "description": "Wait condition (default: 'load')",
                    "default": "load",
                },
                "timeout_ms": {"type": "integer", "description": "Navigation timeout in milliseconds"},
            },
            "required": ["url"],
        },
        function=browser_navigate_wrapper,
    )

    registry.register_tool(
        name="internal_browser_snapshot",
        description="Get AI-friendly snapshot of the page with clickable element references (refs). Returns a list of interactive elements like buttons, links, inputs with refs like 'e1', 'e2'. Use these refs in subsequent click/fill/type actions. ALWAYS call this before interacting with a page to get current element refs. Use frame_selector to snapshot inside a cross-origin iframe (e.g., Magic.link OTP form).",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
                "page_id": {"type": "string", "description": "Specific page/tab ID (optional)"},
                "interactive_only": {
                    "type": "boolean",
                    "description": "Only include interactive elements",
                    "default": True,
                },
                "max_elements": {"type": "integer", "description": "Maximum elements to return", "default": 150},
                "include_text": {"type": "boolean", "description": "Include visible text content", "default": True},
                "frame_selector": {
                    "type": "string",
                    "description": "CSS selector for a cross-origin iframe to snapshot instead of the main page, e.g. \"iframe[src*='magic.link']\". Use internal_browser_list_frames first to discover frame URLs.",
                },
            },
            "required": [],
        },
        function=browser_snapshot_wrapper,
    )

    registry.register_tool(
        name="internal_browser_click",
        description="Click an element on the page. Use refs from internal_browser_snapshot (e.g., 'e1', 'e2') or role:name format (e.g., 'button:Login', 'link:Sign up') or CSS selectors. Use frame_selector to click inside a cross-origin iframe.",
        parameters={
            "type": "object",
            "properties": {
                "ref": {
                    "type": "string",
                    "description": "Element reference - snapshot ref ('e1'), role:name ('button:Login'), or CSS selector ('#submit')",
                },
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
                "page_id": {"type": "string", "description": "Specific page/tab ID (optional)"},
                "double_click": {"type": "boolean", "description": "Perform double-click", "default": False},
                "button": {
                    "type": "string",
                    "enum": ["left", "right", "middle"],
                    "description": "Mouse button",
                    "default": "left",
                },
                "modifiers": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["Alt", "Control", "Meta", "Shift"]},
                    "description": "Keyboard modifiers to hold",
                },
                "timeout_ms": {"type": "integer", "description": "Click timeout in milliseconds"},
                "frame_selector": {
                    "type": "string",
                    "description": "CSS selector for a cross-origin iframe, e.g. \"iframe[src*='magic.link']\". Required when the element is inside a cross-origin iframe.",
                },
            },
            "required": ["ref"],
        },
        function=browser_click_wrapper,
    )

    registry.register_tool(
        name="internal_browser_fill",
        description="Fill text into an input field, replacing existing content. Use for entering email, password, search queries, form data, OTP codes, etc. Use frame_selector to fill inside a cross-origin iframe.",
        parameters={
            "type": "object",
            "properties": {
                "ref": {"type": "string", "description": "Element reference for the input field"},
                "text": {"type": "string", "description": "Text to fill"},
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
                "page_id": {"type": "string", "description": "Specific page/tab ID (optional)"},
                "clear_first": {"type": "boolean", "description": "Clear field before filling", "default": True},
                "timeout_ms": {"type": "integer", "description": "Timeout in milliseconds"},
                "frame_selector": {
                    "type": "string",
                    "description": "CSS selector for a cross-origin iframe, e.g. \"iframe[src*='magic.link']\". Required when the input is inside a cross-origin iframe.",
                },
            },
            "required": ["ref", "text"],
        },
        function=browser_fill_wrapper,
    )

    registry.register_tool(
        name="internal_browser_type",
        description="Type text character by character, simulating real human typing. Use when fill() doesn't work or when you need to trigger keyboard events (e.g., autocomplete, search suggestions). Use frame_selector to type inside a cross-origin iframe.",
        parameters={
            "type": "object",
            "properties": {
                "ref": {"type": "string", "description": "Element reference"},
                "text": {"type": "string", "description": "Text to type"},
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
                "page_id": {"type": "string", "description": "Specific page/tab ID (optional)"},
                "delay_ms": {
                    "type": "integer",
                    "description": "Delay between keystrokes (50-100 for realistic typing)",
                    "default": 0,
                },
                "submit": {"type": "boolean", "description": "Press Enter after typing", "default": False},
                "timeout_ms": {"type": "integer", "description": "Timeout in milliseconds"},
                "frame_selector": {
                    "type": "string",
                    "description": "CSS selector for a cross-origin iframe, e.g. \"iframe[src*='magic.link']\". Required when the element is inside a cross-origin iframe.",
                },
            },
            "required": ["ref", "text"],
        },
        function=browser_type_wrapper,
    )

    registry.register_tool(
        name="internal_browser_fill_form",
        description="Fill multiple form fields at once and optionally submit. Perfect for login forms, registration, checkout, etc.",
        parameters={
            "type": "object",
            "properties": {
                "fields": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "ref": {"type": "string", "description": "Element reference"},
                            "value": {
                                "description": "Value to set (string for text, boolean for checkbox, array for select)"
                            },
                        },
                        "required": ["ref", "value"],
                    },
                    "description": "List of fields to fill",
                },
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
                "page_id": {"type": "string", "description": "Specific page/tab ID (optional)"},
                "submit_ref": {
                    "type": "string",
                    "description": "Element ref to click after filling (e.g., submit button)",
                },
                "timeout_ms": {"type": "integer", "description": "Timeout per field in milliseconds"},
            },
            "required": ["fields"],
        },
        function=browser_fill_form_wrapper,
    )

    registry.register_tool(
        name="internal_browser_select",
        description="Select option(s) from a dropdown/select element.",
        parameters={
            "type": "object",
            "properties": {
                "ref": {"type": "string", "description": "Element reference for the select element"},
                "values": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Values or labels to select",
                },
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
                "page_id": {"type": "string", "description": "Specific page/tab ID (optional)"},
                "timeout_ms": {"type": "integer", "description": "Timeout in milliseconds"},
            },
            "required": ["ref", "values"],
        },
        function=browser_select_wrapper,
    )

    registry.register_tool(
        name="internal_browser_check",
        description="Check or uncheck a checkbox or radio button.",
        parameters={
            "type": "object",
            "properties": {
                "ref": {"type": "string", "description": "Element reference for checkbox/radio"},
                "checked": {"type": "boolean", "description": "True to check, False to uncheck", "default": True},
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
                "page_id": {"type": "string", "description": "Specific page/tab ID (optional)"},
                "timeout_ms": {"type": "integer", "description": "Timeout in milliseconds"},
            },
            "required": ["ref"],
        },
        function=browser_check_wrapper,
    )

    registry.register_tool(
        name="internal_browser_press",
        description="Press a keyboard key. Use for Enter, Tab, Escape, arrow keys, shortcuts like Control+a, etc.",
        parameters={
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Key to press: 'Enter', 'Tab', 'Escape', 'ArrowDown', 'Control+a', 'Meta+c', etc.",
                },
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
                "page_id": {"type": "string", "description": "Specific page/tab ID (optional)"},
                "ref": {"type": "string", "description": "Element to focus before pressing (optional)"},
                "timeout_ms": {"type": "integer", "description": "Timeout in milliseconds"},
            },
            "required": ["key"],
        },
        function=browser_press_wrapper,
    )

    registry.register_tool(
        name="internal_browser_wait",
        description="Wait for various conditions: time delay, element visibility, text appearance/disappearance, URL change, or page load state.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
                "page_id": {"type": "string", "description": "Specific page/tab ID (optional)"},
                "time_ms": {"type": "integer", "description": "Simple delay in milliseconds"},
                "selector": {"type": "string", "description": "Wait for CSS selector to be visible"},
                "text": {"type": "string", "description": "Wait for text to appear"},
                "text_gone": {"type": "string", "description": "Wait for text to disappear (e.g., 'Loading...')"},
                "url_pattern": {"type": "string", "description": "Wait for URL to match pattern (glob)"},
                "load_state": {
                    "type": "string",
                    "enum": ["load", "domcontentloaded", "networkidle"],
                    "description": "Wait for page load state",
                },
                "timeout_ms": {"type": "integer", "description": "Maximum wait time in milliseconds"},
            },
            "required": [],
        },
        function=browser_wait_wrapper,
    )

    registry.register_tool(
        name="internal_browser_screenshot",
        description="Take a screenshot of the current page or a specific element in the browser session. Returns a presigned image_url that you MUST share with the user EXACTLY as provided (including all query parameters). The URL contains authentication tokens - do NOT modify, shorten, or reconstruct it.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
                "page_id": {"type": "string", "description": "Specific page/tab ID (optional)"},
                "ref": {
                    "type": "string",
                    "description": "Element ref to screenshot (optional, screenshots element only)",
                },
                "full_page": {"type": "boolean", "description": "Capture full scrollable page", "default": False},
                "image_type": {
                    "type": "string",
                    "enum": ["png", "jpeg"],
                    "description": "Image format",
                    "default": "png",
                },
                "quality": {"type": "integer", "description": "JPEG quality 0-100 (only for jpeg)"},
            },
            "required": [],
        },
        function=browser_screenshot_wrapper,
    )

    registry.register_tool(
        name="internal_browser_get_cookies",
        description="Get cookies from the browser session. Useful for checking authentication state or saving session for later.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
                "page_id": {"type": "string", "description": "Specific page/tab ID (optional)"},
                "urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter cookies by URLs (optional)",
                },
            },
            "required": [],
        },
        function=browser_get_cookies_wrapper,
    )

    registry.register_tool(
        name="internal_browser_set_cookies",
        description="Set cookies in the browser session. Use to restore saved sessions or set authentication cookies.",
        parameters={
            "type": "object",
            "properties": {
                "cookies": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Cookie name"},
                            "value": {"type": "string", "description": "Cookie value"},
                            "url": {"type": "string", "description": "Cookie URL scope"},
                            "domain": {"type": "string", "description": "Cookie domain"},
                            "path": {"type": "string", "description": "Cookie path"},
                            "expires": {"type": "number", "description": "Expiry timestamp"},
                            "httpOnly": {"type": "boolean", "description": "HTTP only flag"},
                            "secure": {"type": "boolean", "description": "Secure flag"},
                            "sameSite": {
                                "type": "string",
                                "enum": ["Lax", "None", "Strict"],
                                "description": "SameSite policy",
                            },
                        },
                        "required": ["name", "value"],
                    },
                    "description": "List of cookies to set",
                },
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
                "page_id": {"type": "string", "description": "Specific page/tab ID (optional)"},
            },
            "required": ["cookies"],
        },
        function=browser_set_cookies_wrapper,
    )

    registry.register_tool(
        name="internal_browser_clear_cookies",
        description="Clear all cookies from the browser session. Use to log out or reset session state.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
                "page_id": {"type": "string", "description": "Specific page/tab ID (optional)"},
            },
            "required": [],
        },
        function=browser_clear_cookies_wrapper,
    )

    registry.register_tool(
        name="internal_browser_new_page",
        description="Open a new browser tab/page in the session.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
                "url": {"type": "string", "description": "URL to navigate to (optional)"},
            },
            "required": [],
        },
        function=browser_new_page_wrapper,
    )

    registry.register_tool(
        name="internal_browser_close_page",
        description="Close a browser tab/page.",
        parameters={
            "type": "object",
            "properties": {
                "page_id": {"type": "string", "description": "Page ID to close"},
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
            },
            "required": ["page_id"],
        },
        function=browser_close_page_wrapper,
    )

    registry.register_tool(
        name="internal_browser_list_pages",
        description="List all open browser tabs/pages in the session.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
            },
            "required": [],
        },
        function=browser_list_pages_wrapper,
    )

    registry.register_tool(
        name="internal_browser_list_frames",
        description="List all frames/iframes on the current page. Use this to discover cross-origin iframes (e.g., Magic.link OTP, embedded OAuth forms). Returns index, url, and name for each frame. Use the url to build a frame_selector like \"iframe[src*='magic.link']\" for snapshot/fill/click.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
                "page_id": {"type": "string", "description": "Specific page/tab ID (optional)"},
            },
            "required": [],
        },
        function=browser_list_frames_wrapper,
    )

    registry.register_tool(
        name="internal_browser_wait_for_new_page",
        description="""Wait for a new browser tab or popup to open and return its page_id.

Use after triggering an action that opens a popup (e.g., Magic.link email submission, OAuth consent screen, target=_blank links). The popup is automatically registered.

Workflow:
1. Trigger the action that opens a popup (e.g., click "Send Magic Link")
2. Call this tool — it will wait and return the new page_id
3. Use snapshot(page_id=<new_page_id>) to see the popup contents
4. Use fill/click with page_id=<new_page_id> to interact with the popup""",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
                "timeout_ms": {
                    "type": "integer",
                    "description": "Maximum time to wait for popup in milliseconds",
                    "default": 15000,
                },
            },
            "required": [],
        },
        function=browser_wait_for_new_page_wrapper,
    )

    registry.register_tool(
        name="internal_browser_close_session",
        description="Close browser session and all its pages. Call this when done with browser automation to free resources.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Browser session ID to close", "default": "default"},
            },
            "required": [],
        },
        function=browser_close_session_wrapper,
    )

    registry.register_tool(
        name="internal_browser_get_console",
        description="Get console messages (logs, warnings, errors) from the browser page. Useful for debugging.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
                "page_id": {"type": "string", "description": "Specific page/tab ID (optional)"},
                "limit": {"type": "integer", "description": "Maximum messages to return", "default": 50},
            },
            "required": [],
        },
        function=browser_get_console_wrapper,
    )

    registry.register_tool(
        name="internal_browser_get_errors",
        description="Get page errors (JavaScript errors, failed resources) from the browser page. Useful for debugging.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
                "page_id": {"type": "string", "description": "Specific page/tab ID (optional)"},
                "limit": {"type": "integer", "description": "Maximum errors to return", "default": 20},
            },
            "required": [],
        },
        function=browser_get_errors_wrapper,
    )

    # =========================================================================
    # GEOLOCATION / COUNTRY SIMULATION TOOLS
    # =========================================================================

    async def browser_set_country_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_set_country(
            country_code=kwargs.get("country_code"),
            session_id=_resolve_session_id(kwargs, runtime_context),
            apply_to_existing=kwargs.get("apply_to_existing", True),
            proxy_url=kwargs.get("proxy_url"),
            custom_latitude=kwargs.get("custom_latitude"),
            custom_longitude=kwargs.get("custom_longitude"),
            custom_timezone=kwargs.get("custom_timezone"),
            custom_locale=kwargs.get("custom_locale"),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_set_geolocation_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_set_geolocation(
            latitude=kwargs.get("latitude"),
            longitude=kwargs.get("longitude"),
            accuracy=kwargs.get("accuracy", 100),
            session_id=_resolve_session_id(kwargs, runtime_context),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_list_countries_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_list_countries(
            region=kwargs.get("region"),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_get_country_info_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_get_country_info(
            country_code=kwargs.get("country_code"),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_get_current_location_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_get_current_location(
            session_id=_resolve_session_id(kwargs, runtime_context),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_set_proxy_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_set_proxy(
            proxy_url=kwargs.get("proxy_url"),
            session_id=_resolve_session_id(kwargs, runtime_context),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_clear_proxy_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_clear_proxy(
            session_id=_resolve_session_id(kwargs, runtime_context),
            runtime_context=runtime_context,
            config=config,
        )

    registry.register_tool(
        name="internal_browser_set_country",
        description="""Configure browser to simulate browsing from a specific country. Sets geolocation (GPS coordinates), timezone, locale, and language headers. Optionally routes traffic through a proxy for IP-based geolocation.

Without proxy: Browser APIs (navigator.geolocation, timezone, locale) report the target country, but IP-based detection will show your actual location.

With proxy: Full country simulation - both browser APIs AND IP address indicate the target country.

Use cases:
- Test geo-restricted content
- Test localized website versions
- Test location-based features
- QA testing from different countries""",
        parameters={
            "type": "object",
            "properties": {
                "country_code": {
                    "type": "string",
                    "description": "ISO 3166-1 alpha-2 country code (e.g., 'US', 'DE', 'JP', 'AM' for Armenia, 'GB' for UK)",
                },
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
                "proxy_url": {
                    "type": "string",
                    "description": "Proxy URL for IP-based geolocation. Formats: http://host:port, http://user:pass@host:port, socks5://user:pass@host:port. For Bright Data: http://user-country-am:pass@brd.superproxy.io:22225",
                },
                "apply_to_existing": {
                    "type": "boolean",
                    "description": "Recreate browser context with new settings (restores open pages)",
                    "default": True,
                },
                "custom_latitude": {
                    "type": "number",
                    "description": "Override default latitude for more specific location",
                },
                "custom_longitude": {
                    "type": "number",
                    "description": "Override default longitude for more specific location",
                },
                "custom_timezone": {
                    "type": "string",
                    "description": "Override default timezone (e.g., 'America/Los_Angeles')",
                },
                "custom_locale": {
                    "type": "string",
                    "description": "Override default locale (e.g., 'en-US', 'de-DE')",
                },
            },
            "required": ["country_code"],
        },
        function=browser_set_country_wrapper,
    )

    registry.register_tool(
        name="internal_browser_set_geolocation",
        description="Set custom GPS coordinates for the browser. Use this for precise location simulation without full country settings.",
        parameters={
            "type": "object",
            "properties": {
                "latitude": {
                    "type": "number",
                    "description": "Latitude coordinate (-90 to 90)",
                },
                "longitude": {
                    "type": "number",
                    "description": "Longitude coordinate (-180 to 180)",
                },
                "accuracy": {
                    "type": "number",
                    "description": "Location accuracy in meters",
                    "default": 100,
                },
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
            },
            "required": ["latitude", "longitude"],
        },
        function=browser_set_geolocation_wrapper,
    )

    registry.register_tool(
        name="internal_browser_list_countries",
        description="List all supported countries for browser simulation. Filter by region: europe, americas, asia, middle_east, africa.",
        parameters={
            "type": "object",
            "properties": {
                "region": {
                    "type": "string",
                    "description": "Filter by region: 'europe', 'americas', 'asia', 'middle_east', 'africa'",
                    "enum": ["europe", "americas", "asia", "middle_east", "africa"],
                },
            },
            "required": [],
        },
        function=browser_list_countries_wrapper,
    )

    registry.register_tool(
        name="internal_browser_get_country_info",
        description="Get detailed information about a country's simulation settings including coordinates, timezone, locale, and languages.",
        parameters={
            "type": "object",
            "properties": {
                "country_code": {
                    "type": "string",
                    "description": "ISO 3166-1 alpha-2 country code (e.g., 'AM', 'US', 'DE')",
                },
            },
            "required": ["country_code"],
        },
        function=browser_get_country_info_wrapper,
    )

    registry.register_tool(
        name="internal_browser_get_current_location",
        description="Get the current geolocation settings for a browser session. Shows if country simulation and/or proxy is active.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
            },
            "required": [],
        },
        function=browser_get_current_location_wrapper,
    )

    registry.register_tool(
        name="internal_browser_set_proxy",
        description="""Set a proxy for the browser session. All browser traffic will be routed through the proxy server.

Use this for:
- IP-based geolocation (appear to be from proxy's country)
- Testing through corporate proxies
- Bypassing regional restrictions

Supported formats:
- http://host:port
- http://user:pass@host:port
- socks5://host:port
- socks5://user:pass@host:port

Popular proxy providers with country selection:
- Bright Data: http://user-country-XX:pass@brd.superproxy.io:22225
- Oxylabs: http://user:pass@pr.oxylabs.io:7777
- SmartProxy: http://user:pass@gate.smartproxy.com:7000""",
        parameters={
            "type": "object",
            "properties": {
                "proxy_url": {
                    "type": "string",
                    "description": "Proxy server URL (e.g., http://user:pass@proxy.example.com:8080)",
                },
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
            },
            "required": ["proxy_url"],
        },
        function=browser_set_proxy_wrapper,
    )

    registry.register_tool(
        name="internal_browser_clear_proxy",
        description="Remove proxy from browser session and use direct connection.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
            },
            "required": [],
        },
        function=browser_clear_proxy_wrapper,
    )

    # =========================================================================
    # ADDITIONAL ACTION TOOLS (hover, scroll, drag, dialog, upload, etc.)
    # =========================================================================

    async def browser_hover_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_hover(
            ref=kwargs.get("ref"),
            session_id=_resolve_session_id(kwargs, runtime_context),
            page_id=kwargs.get("page_id"),
            timeout_ms=kwargs.get("timeout_ms"),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_scroll_into_view_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_scroll_into_view(
            ref=kwargs.get("ref"),
            session_id=_resolve_session_id(kwargs, runtime_context),
            page_id=kwargs.get("page_id"),
            timeout_ms=kwargs.get("timeout_ms"),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_drag_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_drag(
            source_ref=kwargs.get("source_ref"),
            target_ref=kwargs.get("target_ref"),
            session_id=_resolve_session_id(kwargs, runtime_context),
            page_id=kwargs.get("page_id"),
            timeout_ms=kwargs.get("timeout_ms"),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_handle_dialog_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_handle_dialog(
            action=kwargs.get("action", "accept"),
            prompt_text=kwargs.get("prompt_text"),
            session_id=_resolve_session_id(kwargs, runtime_context),
            page_id=kwargs.get("page_id"),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_upload_file_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_upload_file(
            file_ref=kwargs.get("file_ref"),
            file_paths=kwargs.get("file_paths", []),
            session_id=_resolve_session_id(kwargs, runtime_context),
            page_id=kwargs.get("page_id"),
            timeout_ms=kwargs.get("timeout_ms"),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_evaluate_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_evaluate(
            expression=kwargs.get("expression"),
            session_id=_resolve_session_id(kwargs, runtime_context),
            page_id=kwargs.get("page_id"),
            ref=kwargs.get("ref"),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_resize_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_resize(
            width=kwargs.get("width"),
            height=kwargs.get("height"),
            session_id=_resolve_session_id(kwargs, runtime_context),
            page_id=kwargs.get("page_id"),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_pdf_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_pdf(
            session_id=_resolve_session_id(kwargs, runtime_context),
            page_id=kwargs.get("page_id"),
            path=kwargs.get("path"),
            format=kwargs.get("format", "Letter"),
            print_background=kwargs.get("print_background", True),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_get_storage_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_get_storage(
            storage_type=kwargs.get("storage_type", "local"),
            key=kwargs.get("key"),
            session_id=_resolve_session_id(kwargs, runtime_context),
            page_id=kwargs.get("page_id"),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_set_storage_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_set_storage(
            key=kwargs.get("key"),
            value=kwargs.get("value"),
            storage_type=kwargs.get("storage_type", "local"),
            session_id=_resolve_session_id(kwargs, runtime_context),
            page_id=kwargs.get("page_id"),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_clear_storage_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_clear_storage(
            storage_type=kwargs.get("storage_type", "local"),
            session_id=_resolve_session_id(kwargs, runtime_context),
            page_id=kwargs.get("page_id"),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_set_offline_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_set_offline(
            offline=kwargs.get("offline", True),
            session_id=_resolve_session_id(kwargs, runtime_context),
            page_id=kwargs.get("page_id"),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_set_extra_headers_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_set_extra_headers(
            headers=kwargs.get("headers", {}),
            session_id=_resolve_session_id(kwargs, runtime_context),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_set_http_credentials_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_set_http_credentials(
            username=kwargs.get("username"),
            password=kwargs.get("password"),
            session_id=_resolve_session_id(kwargs, runtime_context),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_focus_page_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_focus_page(
            page_id=kwargs.get("page_id"),
            session_id=_resolve_session_id(kwargs, runtime_context),
            runtime_context=runtime_context,
            config=config,
        )

    async def browser_get_network_requests_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_get_network_requests(
            session_id=_resolve_session_id(kwargs, runtime_context),
            page_id=kwargs.get("page_id"),
            filter_type=kwargs.get("filter_pattern") or kwargs.get("filter_type"),
            limit=kwargs.get("limit", 50),
            runtime_context=runtime_context,
            config=config,
        )

    # Register additional action tools
    registry.register_tool(
        name="internal_browser_hover",
        description="Hover over an element. Useful for triggering hover menus, tooltips, or dropdown previews.",
        parameters={
            "type": "object",
            "properties": {
                "ref": {"type": "string", "description": "Element reference to hover over"},
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
                "page_id": {"type": "string", "description": "Specific page/tab ID (optional)"},
                "timeout_ms": {"type": "integer", "description": "Timeout in milliseconds"},
            },
            "required": ["ref"],
        },
        function=browser_hover_wrapper,
    )

    registry.register_tool(
        name="internal_browser_scroll_into_view",
        description="Scroll an element into view. Use when an element is not visible in the viewport.",
        parameters={
            "type": "object",
            "properties": {
                "ref": {"type": "string", "description": "Element reference to scroll into view"},
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
                "page_id": {"type": "string", "description": "Specific page/tab ID (optional)"},
                "timeout_ms": {"type": "integer", "description": "Timeout in milliseconds"},
            },
            "required": ["ref"],
        },
        function=browser_scroll_into_view_wrapper,
    )

    registry.register_tool(
        name="internal_browser_drag",
        description="Drag an element and drop it onto another element. Useful for drag-and-drop interfaces, reordering lists, file dropping.",
        parameters={
            "type": "object",
            "properties": {
                "source_ref": {"type": "string", "description": "Element reference to drag from"},
                "target_ref": {"type": "string", "description": "Element reference to drop onto"},
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
                "page_id": {"type": "string", "description": "Specific page/tab ID (optional)"},
                "timeout_ms": {"type": "integer", "description": "Timeout in milliseconds"},
            },
            "required": ["source_ref", "target_ref"],
        },
        function=browser_drag_wrapper,
    )

    registry.register_tool(
        name="internal_browser_handle_dialog",
        description="""Set up a handler for JavaScript dialogs (alert, confirm, prompt).
IMPORTANT: Call this BEFORE the action that triggers the dialog, not after.

Example workflow:
1. await internal_browser_handle_dialog(action="accept")
2. await internal_browser_click(ref="e1")  # This triggers the dialog""",
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["accept", "dismiss"],
                    "description": "'accept' to click OK/Yes, 'dismiss' to click Cancel/No",
                    "default": "accept",
                },
                "prompt_text": {
                    "type": "string",
                    "description": "Text to enter if dialog is a prompt (optional)",
                },
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
                "page_id": {"type": "string", "description": "Specific page/tab ID (optional)"},
            },
            "required": [],
        },
        function=browser_handle_dialog_wrapper,
    )

    registry.register_tool(
        name="internal_browser_upload_file",
        description="Upload file(s) to a file input element. Set the file paths for a file input.",
        parameters={
            "type": "object",
            "properties": {
                "file_ref": {"type": "string", "description": "Element reference for the file input"},
                "file_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of file paths to upload",
                },
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
                "page_id": {"type": "string", "description": "Specific page/tab ID (optional)"},
                "timeout_ms": {"type": "integer", "description": "Timeout in milliseconds"},
            },
            "required": ["file_ref", "file_paths"],
        },
        function=browser_upload_file_wrapper,
    )

    registry.register_tool(
        name="internal_browser_evaluate",
        description="""Execute JavaScript code in the page context.
Can run expressions or functions. If ref is provided, the expression should be a function that receives the element.

Examples:
- expression="document.title" -> returns page title
- expression="window.scrollY" -> returns scroll position
- expression="(el) => el.textContent", ref="e5" -> returns element text""",
        parameters={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "JavaScript expression to evaluate",
                },
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
                "page_id": {"type": "string", "description": "Specific page/tab ID (optional)"},
                "ref": {
                    "type": "string",
                    "description": "Element reference - if provided, expression should be a function: (el) => ...",
                },
            },
            "required": ["expression"],
        },
        function=browser_evaluate_wrapper,
    )

    registry.register_tool(
        name="internal_browser_resize",
        description="Resize the browser viewport. Use for testing responsive designs or simulating different screen sizes.",
        parameters={
            "type": "object",
            "properties": {
                "width": {"type": "integer", "description": "Viewport width in pixels"},
                "height": {"type": "integer", "description": "Viewport height in pixels"},
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
                "page_id": {"type": "string", "description": "Specific page/tab ID (optional)"},
            },
            "required": ["width", "height"],
        },
        function=browser_resize_wrapper,
    )

    registry.register_tool(
        name="internal_browser_pdf",
        description="Generate a PDF of the current page. Only works in headless mode.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
                "page_id": {"type": "string", "description": "Specific page/tab ID (optional)"},
                "path": {
                    "type": "string",
                    "description": "File path to save PDF (if not provided, returns base64)",
                },
                "format": {
                    "type": "string",
                    "description": "Page format - Letter, A4, Legal, etc.",
                    "default": "Letter",
                },
                "print_background": {
                    "type": "boolean",
                    "description": "Include background graphics",
                    "default": True,
                },
            },
            "required": [],
        },
        function=browser_pdf_wrapper,
    )

    # Storage tools
    registry.register_tool(
        name="internal_browser_get_storage",
        description="Get values from localStorage or sessionStorage. Useful for reading auth tokens, user preferences, cached data.",
        parameters={
            "type": "object",
            "properties": {
                "storage_type": {
                    "type": "string",
                    "enum": ["local", "session"],
                    "description": "'local' for localStorage, 'session' for sessionStorage",
                    "default": "local",
                },
                "key": {
                    "type": "string",
                    "description": "Specific key to get (if None, returns all storage)",
                },
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
                "page_id": {"type": "string", "description": "Specific page/tab ID (optional)"},
            },
            "required": [],
        },
        function=browser_get_storage_wrapper,
    )

    registry.register_tool(
        name="internal_browser_set_storage",
        description="Set a value in localStorage or sessionStorage. Useful for setting auth tokens, preferences, feature flags.",
        parameters={
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Storage key"},
                "value": {"type": "string", "description": "Value to store"},
                "storage_type": {
                    "type": "string",
                    "enum": ["local", "session"],
                    "description": "'local' for localStorage, 'session' for sessionStorage",
                    "default": "local",
                },
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
                "page_id": {"type": "string", "description": "Specific page/tab ID (optional)"},
            },
            "required": ["key", "value"],
        },
        function=browser_set_storage_wrapper,
    )

    registry.register_tool(
        name="internal_browser_clear_storage",
        description="Clear localStorage or sessionStorage. Use to reset application state.",
        parameters={
            "type": "object",
            "properties": {
                "storage_type": {
                    "type": "string",
                    "enum": ["local", "session"],
                    "description": "'local' for localStorage, 'session' for sessionStorage",
                    "default": "local",
                },
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
                "page_id": {"type": "string", "description": "Specific page/tab ID (optional)"},
            },
            "required": [],
        },
        function=browser_clear_storage_wrapper,
    )

    # Network settings tools
    registry.register_tool(
        name="internal_browser_set_offline",
        description="Set browser offline/online mode. Use to test offline functionality, service workers, network error handling.",
        parameters={
            "type": "object",
            "properties": {
                "offline": {
                    "type": "boolean",
                    "description": "True to go offline, False to go online",
                    "default": True,
                },
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
                "page_id": {"type": "string", "description": "Specific page/tab ID (optional)"},
            },
            "required": [],
        },
        function=browser_set_offline_wrapper,
    )

    registry.register_tool(
        name="internal_browser_set_extra_headers",
        description="Set extra HTTP headers that will be sent with every request. Useful for custom auth, debug headers, API versioning.",
        parameters={
            "type": "object",
            "properties": {
                "headers": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                    "description": "Dictionary of header name -> value",
                },
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
            },
            "required": ["headers"],
        },
        function=browser_set_extra_headers_wrapper,
    )

    registry.register_tool(
        name="internal_browser_set_http_credentials",
        description="Set HTTP Basic Auth credentials for the browser session. Call with no args to clear credentials.",
        parameters={
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "Username for HTTP Basic Auth (None to clear)"},
                "password": {"type": "string", "description": "Password for HTTP Basic Auth (None to clear)"},
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
            },
            "required": [],
        },
        function=browser_set_http_credentials_wrapper,
    )

    registry.register_tool(
        name="internal_browser_focus_page",
        description="Focus/switch to a specific browser page/tab. Use when working with multiple tabs.",
        parameters={
            "type": "object",
            "properties": {
                "page_id": {"type": "string", "description": "Page ID to focus"},
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
            },
            "required": ["page_id"],
        },
        function=browser_focus_page_wrapper,
    )

    registry.register_tool(
        name="internal_browser_get_network_requests",
        description="Get recorded network requests from the page. Useful for debugging API calls, checking request/response status.",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Browser session ID", "default": "default"},
                "page_id": {"type": "string", "description": "Specific page/tab ID (optional)"},
                "filter_pattern": {
                    "type": "string",
                    "description": "Filter requests by URL pattern (substring match)",
                },
                "limit": {"type": "integer", "description": "Maximum requests to return", "default": 50},
            },
            "required": [],
        },
        function=browser_get_network_requests_wrapper,
    )

    logger.info(
        "Registered 47 browser automation tools (5 legacy + 20 interactive + 7 geolocation/proxy + 15 additional)"
    )
