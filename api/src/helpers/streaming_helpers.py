"""
Streaming Helper Functions.

Utility functions for Server-Sent Events (SSE) streaming operations.
"""

import datetime
import decimal
import json
import logging
import re
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


def convert_to_json_serializable(obj: Any) -> Any:
    """
    Recursively convert numpy types and other non-JSON-serializable types to Python native types.

    Args:
        obj: Object to convert

    Returns:
        JSON-serializable version of the object
    """
    if isinstance(obj, dict):
        return {key: convert_to_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_json_serializable(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_to_json_serializable(item) for item in obj)
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
        return obj.isoformat()
    elif isinstance(obj, decimal.Decimal):
        return float(obj)
    elif isinstance(obj, uuid.UUID):
        return str(obj)
    else:
        return obj


def extract_user_friendly_error(error: Exception) -> str:
    """
    Extract a user-friendly error message from LLM provider exceptions.

    Converts technical error messages from litellm, OpenAI, Anthropic, etc.
    into simple, actionable messages for end users.

    Args:
        error: The exception to extract a message from

    Returns:
        A user-friendly error message string
    """
    error_str = str(error)
    error_type = type(error).__name__

    # Check for authentication/API key errors
    auth_patterns = [
        r"AuthenticationError",
        r"Invalid.*api.?key",
        r"invalid.*token",
        r"Unauthorized",
        r"401",
        r"token_not_found",
        r"Invalid proxy server token",
    ]
    for pattern in auth_patterns:
        if re.search(pattern, error_str, re.IGNORECASE):
            return "API key is invalid or expired. Please check your LLM configuration."

    # Check for payload / context too large errors FIRST — Groq returns 413 with
    # code=rate_limit_exceeded when TPM is exceeded, so this must come before
    # the generic rate-limit check to avoid showing the wrong message.
    if re.search(r"413", error_str) or re.search(
        r"Payload Too Large|Request Entity Too Large|request.*too.*large", error_str, re.IGNORECASE
    ):
        # Groq free-tier TPM exceeded — give a specific, actionable message
        if re.search(r"tokens per minute|TPM|Limit \d+, Requested \d+", error_str):
            return (
                "Your message is too large for this model's token limit. "
                "Try shortening your message, reducing the system prompt, or upgrading your Groq plan."
            )
        return "The conversation has grown too large. Please start a new conversation or clear history."

    # Check for rate limit / service unavailable errors
    rate_limit_patterns = [
        r"RateLimitError",
        r"rate.?limit",
        r"429",
        r"too many requests",
        r"quota exceeded",
        r"ServiceUnavailableError",
        r"503",
        r"Too many connections",
        r"No deployments available",
    ]
    for pattern in rate_limit_patterns:
        if re.search(pattern, error_str, re.IGNORECASE):
            return "The AI service is busy. Please try again in a few seconds."

    # Check for connection/network errors
    connection_patterns = [
        r"ConnectionError",
        r"APIConnectionError",
        r"connection.*refused",
        r"network.*error",
        r"timeout",
        r"ECONNREFUSED",
    ]
    for pattern in connection_patterns:
        if re.search(pattern, error_str, re.IGNORECASE):
            return "Unable to connect to the AI provider. Please check your network or try again."

    # Check for context length errors
    context_patterns = [
        r"context.?length",
        r"maximum.*tokens",
        r"too long",
        r"content.*too.*large",
    ]
    for pattern in context_patterns:
        if re.search(pattern, error_str, re.IGNORECASE):
            return "Message too long. Please try with a shorter message."

    # Check for model not found errors
    model_patterns = [
        r"model.*not.*found",
        r"invalid.*model",
        r"does not exist",
        r"no such model",
        r"not_found_error",  # Anthropic 404: {'type': 'not_found_error', 'message': 'model: ...'}
        r"\"type\":\s*\"not_found_error\"",
        r"404",
    ]
    for pattern in model_patterns:
        if re.search(pattern, error_str, re.IGNORECASE):
            # Try to extract the model name from Anthropic's error message
            model_match = re.search(r"'message':\s*'model:\s*([^']+)'", error_str)
            if model_match:
                model_name = model_match.group(1)
                return f"Model '{model_name}' not found. Please update the agent's model configuration."
            return "The configured AI model is not available. Please check agent settings."

    # Check for content policy/safety errors
    safety_patterns = [
        r"content.*policy",
        r"safety",
        r"blocked",
        r"refused",
        r"inappropriate",
    ]
    for pattern in safety_patterns:
        if re.search(pattern, error_str, re.IGNORECASE):
            return "Request blocked by content policy. Please rephrase your message."

    # Check for billing/quota errors
    billing_patterns = [
        r"billing",
        r"insufficient.*funds",
        r"payment",
        r"credit",
        r"quota",
    ]
    for pattern in billing_patterns:
        if re.search(pattern, error_str, re.IGNORECASE):
            return "AI provider billing issue. Please check your account."

    # Default: return a generic but helpful message
    # Don't expose raw technical details to users
    logger.warning(f"Unhandled LLM error ({error_type}): {error_str}")
    return "An error occurred while processing your request. Please try again."


# Patterns for errors that are expected/recoverable and should NOT trigger Sentry alerts
_EXPECTED_ERROR_PATTERNS = [
    r"rate.?limit",
    r"RateLimitError",
    r"too many requests",
    r"quota exceeded",
    r"ServiceUnavailableError",
    r"503",
    r"Too many connections",
    r"No deployments available",
    r"AuthenticationError",
    r"Invalid.*api.?key",
    r"invalid.*token",
    r"Unauthorized",
    r"token_not_found",
    r"context.?length",
    r"maximum.*tokens",
    r"content.*too.*large",
    r"content.*policy",
    r"model.*not.*found",
    r"Invalid proxy server token",
    r"maximum allowed",  # Anthropic max_tokens exceeded
    r"413",  # Payload too large / Groq TPM exceeded
    r"Payload Too Large",
    r"Request Entity Too Large",
    r"tokens per minute",  # Groq TPM rate limit
]


def is_expected_llm_error(error: Exception) -> bool:
    """Return True for known recoverable LLM errors that should not create Sentry alerts."""
    error_str = str(error)
    return any(re.search(p, error_str, re.IGNORECASE) for p in _EXPECTED_ERROR_PATTERNS)


async def generate_sse_event(event_type: str, data: dict[str, Any]) -> str:
    """
    Generate a Server-Sent Event formatted string.

    Args:
        event_type: Type of event (chunk, status, error, done, etc.)
        data: Event data to send

    Returns:
        SSE formatted string
    """
    event_data = {"type": event_type, **data}
    # Convert numpy types to Python native types for JSON serialization
    event_data = convert_to_json_serializable(event_data)
    return f"data: {json.dumps(event_data)}\n\n"


async def generate_start_event(agent_name: str, start_time: float, **kwargs) -> str:
    """
    Generate chat start event.

    Args:
        agent_name: Name of the agent
        start_time: Start timestamp
        **kwargs: Additional data (e.g., workflow_type)

    Returns:
        SSE formatted start event
    """
    data = {"agent": agent_name, "start_time": start_time, **kwargs}
    return await generate_sse_event("start", data)


async def generate_chunk_event(content: str) -> str:
    """
    Generate content chunk event.

    Args:
        content: Text content to stream

    Returns:
        SSE formatted chunk event
    """
    return await generate_sse_event("chunk", {"content": content})


async def generate_status_event(message: str) -> str:
    """
    Generate status update event.

    Args:
        message: Status message to display

    Returns:
        SSE formatted status event
    """
    return await generate_sse_event("status", {"content": message})


async def generate_tool_status_event(
    tool_name: str,
    status: str,
    description: str | None = None,
    arguments: dict | None = None,
    duration_ms: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
) -> str:
    """
    Generate a rich tool status event with details about what the tool is doing.

    Args:
        tool_name: Name of the tool being executed
        status: Status of the tool (started, completed, error)
        description: Human-readable description of what the tool is doing
        arguments: Tool arguments (for displaying file paths, etc.)
        duration_ms: Execution duration in milliseconds (for completed status)
        input_tokens: Number of input tokens used (optional)
        output_tokens: Number of output tokens generated (optional)

    Returns:
        SSE formatted tool status event
    """
    data = {
        "tool_name": tool_name,
        "status": status,
    }

    if description:
        data["description"] = description
    else:
        # Generate a description based on tool name and arguments
        data["description"] = _generate_tool_description(tool_name, arguments)

    if arguments:
        # Include relevant argument info for display (e.g., file paths)
        data["details"] = _extract_display_details(tool_name, arguments)

    # Include execution metrics when available
    if duration_ms is not None:
        data["duration_ms"] = duration_ms

    if input_tokens is not None:
        data["input_tokens"] = input_tokens

    if output_tokens is not None:
        data["output_tokens"] = output_tokens

    return await generate_sse_event("tool_status", data)


def _generate_tool_description(tool_name: str, arguments: dict | None) -> str:
    """Generate a human-readable description for a tool execution."""
    tool_descriptions = {
        # File operations
        "internal_write_file": "Writing file",
        "internal_read_file": "Reading file",
        "internal_edit_file": "Editing file",
        "internal_create_directory": "Creating directory",
        "internal_directory_tree": "Listing directory tree",
        "internal_get_file_info": "Getting file info",
        # Command execution
        "internal_run_command": "Running command",
        # Git operations
        "internal_git_clone_repo": "Cloning repository",
        "internal_git_create_branch": "Creating branch",
        "internal_git_switch_branch": "Switching branch",
        "internal_git_commit_and_push": "Committing changes",
        "internal_github_create_pr": "Creating pull request",
        "internal_git_get_status": "Checking git status",
        "internal_git_get_diff": "Getting git diff",
        "internal_git_pull_changes": "Pulling changes",
        # GitHub operations
        "internal_github_create_issue": "Creating GitHub issue",
        "internal_github_create_pull_request": "Creating pull request",
        "internal_github_get_pull_request": "Fetching pull request",
        "internal_github_list_issues": "Listing issues",
        # Browser operations
        "internal_browser_navigate": "Navigating to page",
        "internal_browser_snapshot": "Taking screenshot",
        "internal_browser_click": "Clicking element",
        "internal_browser_type": "Typing text",
        # Search operations
        "internal_search_available_tools": "Searching available tools",
        "internal_web_search": "Searching the web",
        # Database operations
        "internal_execute_sql": "Executing SQL query",
        "internal_get_database_schema": "Getting database schema",
    }

    base_desc = tool_descriptions.get(tool_name, f"Using {tool_name.replace('internal_', '').replace('_', ' ')}")

    # Add context from arguments
    if arguments:
        if "file_path" in arguments:
            path = arguments["file_path"]
            # Show just the filename or last path segment
            filename = path.split("/")[-1] if "/" in path else path
            return f"{base_desc}: {filename}"
        elif "path" in arguments:
            path = arguments["path"]
            filename = path.split("/")[-1] if "/" in path else path
            return f"{base_desc}: {filename}"
        elif "command" in arguments:
            cmd = arguments["command"]
            if isinstance(cmd, list):
                cmd = " ".join(cmd[:3])  # Show first 3 parts
            elif isinstance(cmd, str):
                cmd = " ".join(cmd.split()[:3])
            if len(cmd) > 40:
                cmd = cmd[:40] + "..."
            return f"{base_desc}: {cmd}"
        elif "repo_url" in arguments:
            url = arguments["repo_url"]
            # Extract repo name from URL
            repo_name = url.split("/")[-1].replace(".git", "")
            return f"{base_desc}: {repo_name}"
        elif "url" in arguments:
            return f"{base_desc}"
        elif "query" in arguments:
            query = arguments["query"]
            if len(query) > 30:
                query = query[:30] + "..."
            return f"{base_desc}: {query}"

    return base_desc


def _extract_display_details(tool_name: str, arguments: dict) -> dict:
    """Extract display-relevant details from tool arguments."""
    details = {}

    # File path for file operations
    if "file_path" in arguments:
        details["file_path"] = arguments["file_path"]
    elif "path" in arguments:
        details["path"] = arguments["path"]

    # Command for execution
    if "command" in arguments:
        cmd = arguments["command"]
        if isinstance(cmd, list):
            details["command"] = " ".join(cmd)
        else:
            details["command"] = cmd

    # URL for web/git operations
    if "repo_url" in arguments:
        details["repo_url"] = arguments["repo_url"]
    elif "url" in arguments:
        details["url"] = arguments["url"]

    # Branch names
    if "branch_name" in arguments:
        details["branch"] = arguments["branch_name"]

    return details


async def generate_error_event(error: str, **kwargs) -> str:
    """
    Generate error event.

    Args:
        error: Error message
        **kwargs: Additional error data

    Returns:
        SSE formatted error event
    """
    data = {"error": error, **kwargs}
    return await generate_sse_event("error", data)


async def generate_done_event(
    sources: list[dict[str, Any]] | None = None, metadata: dict[str, Any] | None = None, **kwargs
) -> str:
    """
    Generate completion event.

    Args:
        sources: Retrieved RAG sources
        metadata: Response metadata (timing, tokens, etc.)
        **kwargs: Additional completion data

    Returns:
        SSE formatted done event
    """
    data = {}

    if sources:
        data["sources"] = sources

    # Merge caller metadata and inject AI content disclosure fields
    merged_metadata = dict(metadata) if metadata else {}
    merged_metadata.setdefault("generated_by_ai", True)
    merged_metadata.setdefault("model_provider", "ai")  # generic — does not expose actual provider
    data["metadata"] = merged_metadata

    data.update(kwargs)

    return await generate_sse_event("done", data)


async def generate_first_token_event(time_to_first_token: float) -> str:
    """
    Generate first token timing event.

    Args:
        time_to_first_token: Time elapsed to first token

    Returns:
        SSE formatted event
    """
    return await generate_sse_event("first_token", {"time_to_first_token": time_to_first_token})


async def generate_security_block_stream(details: dict[str, Any] | None = None) -> AsyncGenerator[str, None]:
    """
    Generate security block message stream.

    Args:
        details: Optional additional fields to include in the response

    Yields:
        SSE formatted security violation message
    """
    import uuid

    security_response = {
        "error": "Your message was flagged by the security filter. Please rephrase and try again. If this keeps happening, contact your workspace admin.",
        "error_type": "security_violation",
        "violation_id": f"CHAT_{uuid.uuid4().hex[:8]}",
    }

    if details:
        security_response.update(details)

    yield await generate_sse_event("error", security_response)
