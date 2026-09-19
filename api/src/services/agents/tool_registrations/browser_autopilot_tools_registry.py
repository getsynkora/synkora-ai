"""
Browser Autopilot Tool Registry

Registers internal_browser_autopilot — a single goal-directed browsing tool
that runs TypeSafe's fast decide-and-act loop server-side, instead of the
agent issuing one click/fill/select tool call per step.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register_browser_autopilot_tools(registry) -> None:
    """Register internal_browser_autopilot with the ADK tool registry."""

    from src.services.agents.internal_tools.browser_autopilot import MAX_STEPS, internal_browser_autopilot
    from src.services.agents.tool_registrations.browser_tools_registry import _resolve_session_id

    async def _autopilot_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_browser_autopilot(
            goal=kwargs.get("goal"),
            url=kwargs.get("url"),
            session_id=_resolve_session_id(kwargs, runtime_context),
            page_id=kwargs.get("page_id"),
            max_steps=kwargs.get("max_steps", MAX_STEPS),
            runtime_context=runtime_context,
            config=config,
        )

    registry.register_tool(
        name="internal_browser_autopilot",
        description="""Drive the browser toward ONE goal in a single tool call — do NOT combine this
with manual internal_browser_click/fill/select calls in the same task; it manages its own
navigate-observe-decide-act loop internally and returns only the final outcome.

Use this instead of the step-by-step browser tools when the task is "go do X on this website"
(fill out and submit a form, search for something and open a result, apply filters) rather than
a single precise interaction you need to control exactly. It is much faster and cheaper per step
than snapshotting and clicking manually, because each decision is one TypeSafe request instead of
a full reasoning turn.

Prefer the manual internal_browser_* tools when you need to inspect intermediate page state, handle
an unusual/multi-step flow this can't infer from the goal alone, or the site needs a fixed field
value you already know exactly (this tool infers TYPE_TEXT values from the goal each time).

Returns: {{"success": bool, "status": "done"|"blocked"|"max_steps", "steps": int, "history": [...]}}.
A "blocked" or "max_steps" result means it could not complete the goal — check "history" for what
it tried, and either provide a more specific goal or fall back to manual tools.

IMPORTANT: Configure TypeSafe AI first via Settings → Integrations → AI Evaluation, and make sure
this agent has a default LLM configured (used to generate the text typed into form fields).""",
        parameters={
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": (
                        "Plain-language description of what to accomplish on the page — be specific "
                        "about every field/filter that must be set, since a matching result alone "
                        "does not prove a requested filter was applied."
                    ),
                },
                "url": {
                    "type": "string",
                    "description": "URL to navigate to before starting. Omit to continue on the current page.",
                },
                "page_id": {
                    "type": "string",
                    "description": "Specific tab to use. Omit to use the current/most recent tab.",
                },
                "max_steps": {
                    "type": "integer",
                    "description": f"Maximum actions to attempt before giving up (default/cap: {MAX_STEPS}).",
                },
                "session_id": {
                    "type": "string",
                    "description": "Browser session label — reuse the same value to continue in the same session.",
                },
            },
            "required": ["goal"],
        },
        function=_autopilot_wrapper,
    )

    logger.info("Registered internal_browser_autopilot tool")
