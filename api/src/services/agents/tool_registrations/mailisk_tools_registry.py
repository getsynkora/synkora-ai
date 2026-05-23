"""Mailisk tool registrations."""

from typing import Any

from src.services.agents.internal_tools.mailisk_tools import (
    internal_mailisk_generate_test_email,
    internal_mailisk_list_namespaces,
    internal_mailisk_wait_for_email,
    internal_mailisk_wait_for_verification_code,
    internal_mailisk_wait_for_verification_link,
)


def register_mailisk_tools(adk_tools_instance) -> None:
    """Register Mailisk inbox tools used by browser-driven signup/login tests."""

    async def mailisk_list_namespaces_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_mailisk_list_namespaces(config=config, runtime_context=runtime_context)

    async def mailisk_generate_test_email_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_mailisk_generate_test_email(
            local_part_prefix=kwargs.get("local_part_prefix", "synkora"),
            namespace=kwargs.get("namespace"),
            config=config,
            runtime_context=runtime_context,
        )

    async def mailisk_wait_for_email_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_mailisk_wait_for_email(
            recipient_email=kwargs.get("recipient_email"),
            to_addr_prefix=kwargs.get("to_addr_prefix"),
            from_addr_includes=kwargs.get("from_addr_includes"),
            subject_includes=kwargs.get("subject_includes"),
            namespace=kwargs.get("namespace"),
            timeout_ms=kwargs.get("timeout_ms", 60_000),
            limit=kwargs.get("limit", 10),
            wait=kwargs.get("wait", True),
            config=config,
            runtime_context=runtime_context,
        )

    async def mailisk_wait_for_verification_code_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_mailisk_wait_for_verification_code(
            recipient_email=kwargs.get("recipient_email"),
            to_addr_prefix=kwargs.get("to_addr_prefix"),
            from_addr_includes=kwargs.get("from_addr_includes"),
            subject_includes=kwargs.get("subject_includes"),
            namespace=kwargs.get("namespace"),
            timeout_ms=kwargs.get("timeout_ms", 60_000),
            code_length=kwargs.get("code_length", 6),
            regex=kwargs.get("regex"),
            config=config,
            runtime_context=runtime_context,
        )

    async def mailisk_wait_for_verification_link_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_mailisk_wait_for_verification_link(
            recipient_email=kwargs.get("recipient_email"),
            to_addr_prefix=kwargs.get("to_addr_prefix"),
            from_addr_includes=kwargs.get("from_addr_includes"),
            subject_includes=kwargs.get("subject_includes"),
            namespace=kwargs.get("namespace"),
            timeout_ms=kwargs.get("timeout_ms", 60_000),
            domain_includes=kwargs.get("domain_includes"),
            url_includes=kwargs.get("url_includes"),
            prefer_https=kwargs.get("prefer_https", True),
            config=config,
            runtime_context=runtime_context,
        )

    adk_tools_instance.register_tool(
        name="internal_mailisk_list_namespaces",
        description="List namespaces available to the configured Mailisk account. Use this to verify Mailisk is configured correctly for browser signup/login testing.",
        parameters={"type": "object", "properties": {}, "required": []},
        function=mailisk_list_namespaces_wrapper,
    )

    adk_tools_instance.register_tool(
        name="internal_mailisk_generate_test_email",
        description="Generate a unique Mailisk inbox address for a signup or login test flow. Use the returned email address when the browser needs to create a new account.",
        parameters={
            "type": "object",
            "properties": {
                "local_part_prefix": {
                    "type": "string",
                    "description": "Optional prefix for the generated address, e.g. 'checkout-test' or 'synkora'.",
                },
                "namespace": {
                    "type": "string",
                    "description": "Optional Mailisk namespace override. Defaults to the configured namespace.",
                },
            },
            "required": [],
        },
        function=mailisk_generate_test_email_wrapper,
    )

    adk_tools_instance.register_tool(
        name="internal_mailisk_wait_for_email",
        description="Wait for and fetch email delivered to a Mailisk inbox. Useful after signup, password reset, or OTP send actions in the browser.",
        parameters={
            "type": "object",
            "properties": {
                "recipient_email": {
                    "type": "string",
                    "description": "Exact generated Mailisk address to watch. Preferred when you already created a test email address.",
                },
                "to_addr_prefix": {
                    "type": "string",
                    "description": "Optional Mailisk recipient prefix filter. Use when you only know the local-part prefix.",
                },
                "from_addr_includes": {
                    "type": "string",
                    "description": "Optional sender fragment filter such as 'noreply' or a domain name.",
                },
                "subject_includes": {
                    "type": "string",
                    "description": "Optional subject fragment filter such as 'Verify' or 'OTP'.",
                },
                "namespace": {
                    "type": "string",
                    "description": "Optional Mailisk namespace override.",
                },
                "timeout_ms": {
                    "type": "integer",
                    "description": "How long to wait for the email in milliseconds.",
                    "default": 60000,
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of emails to return (1-20).",
                    "default": 10,
                },
                "wait": {
                    "type": "boolean",
                    "description": "If true, long-poll until matching email arrives or the timeout elapses.",
                    "default": True,
                },
            },
            "required": [],
        },
        function=mailisk_wait_for_email_wrapper,
    )

    adk_tools_instance.register_tool(
        name="internal_mailisk_wait_for_verification_code",
        description="Wait for a Mailisk email and extract a verification or OTP code from the message body.",
        parameters={
            "type": "object",
            "properties": {
                "recipient_email": {"type": "string", "description": "Exact Mailisk address to watch."},
                "to_addr_prefix": {
                    "type": "string",
                    "description": "Optional Mailisk recipient prefix when exact address is not available.",
                },
                "from_addr_includes": {"type": "string", "description": "Optional sender filter."},
                "subject_includes": {"type": "string", "description": "Optional subject filter."},
                "namespace": {"type": "string", "description": "Optional namespace override."},
                "timeout_ms": {
                    "type": "integer",
                    "description": "How long to wait in milliseconds.",
                    "default": 60000,
                },
                "code_length": {
                    "type": "integer",
                    "description": "Preferred numeric code length. Defaults to 6.",
                    "default": 6,
                },
                "regex": {
                    "type": "string",
                    "description": "Optional custom regex with a capture group for unusual code formats.",
                },
            },
            "required": [],
        },
        function=mailisk_wait_for_verification_code_wrapper,
    )

    adk_tools_instance.register_tool(
        name="internal_mailisk_wait_for_verification_link",
        description="Wait for a Mailisk email and extract the most likely verification or magic link so the browser can navigate to it.",
        parameters={
            "type": "object",
            "properties": {
                "recipient_email": {"type": "string", "description": "Exact Mailisk address to watch."},
                "to_addr_prefix": {
                    "type": "string",
                    "description": "Optional Mailisk recipient prefix when exact address is not available.",
                },
                "from_addr_includes": {"type": "string", "description": "Optional sender filter."},
                "subject_includes": {"type": "string", "description": "Optional subject filter."},
                "namespace": {"type": "string", "description": "Optional namespace override."},
                "timeout_ms": {
                    "type": "integer",
                    "description": "How long to wait in milliseconds.",
                    "default": 60000,
                },
                "domain_includes": {
                    "type": "string",
                    "description": "Optional domain fragment filter for the extracted link.",
                },
                "url_includes": {
                    "type": "string",
                    "description": "Optional URL fragment filter for the extracted link.",
                },
                "prefer_https": {
                    "type": "boolean",
                    "description": "Prefer HTTPS links when multiple candidates exist.",
                    "default": True,
                },
            },
            "required": [],
        },
        function=mailisk_wait_for_verification_link_wrapper,
    )
