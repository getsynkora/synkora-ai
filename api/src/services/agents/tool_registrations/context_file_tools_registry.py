"""
Context File Tools Registry

Registers the internal_load_context_file tool so agents can load
on-demand context files at runtime.
"""

import logging

logger = logging.getLogger(__name__)


def register_context_file_tools(registry) -> None:
    """Register context file loading tool with ADKToolRegistry."""
    from src.services.agents.internal_tools.context_file_tools import internal_load_context_file

    async def _wrapper(config=None, **kwargs):
        return await internal_load_context_file(
            filename=kwargs.get("filename", ""),
            config=config,
        )

    registry.register_tool(
        name="internal_load_context_file",
        description=(
            "Load the full content of a context file listed under AVAILABLE CONTEXT FILES. "
            "Use this when you need the content of an on-demand file to complete the current task. "
            "Pass the exact filename as shown in the list."
        ),
        parameters={
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Exact filename from the AVAILABLE CONTEXT FILES list",
                }
            },
            "required": ["filename"],
        },
        function=_wrapper,
    )

    logger.info("Registered internal_load_context_file tool")
