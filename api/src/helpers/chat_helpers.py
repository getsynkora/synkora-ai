"""
Chat Helper Functions.

Utility functions for chat operations including conversation handling,
message metadata building, token estimation, and validation.
"""

import logging
import uuid
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
    else:
        return obj


def validate_conversation_id(conversation_id: str | None) -> uuid.UUID | None:
    """
    Validate and convert conversation ID to UUID.

    Args:
        conversation_id: Conversation ID string

    Returns:
        UUID object or None if invalid/not provided
    """
    if not conversation_id:
        return None

    try:
        return uuid.UUID(conversation_id)
    except ValueError:
        logger.warning(f"Invalid conversation_id format: {conversation_id}")
        return None


def estimate_tokens(text: str, model: str = "gpt-4") -> int:
    """
    Estimate token count from text using tiktoken.

    Uses the TokenCounter service for accurate token counting.
    Falls back to rough estimation if TokenCounter is not available.

    Args:
        text: Text to estimate tokens for
        model: Model name for encoding selection (default: gpt-4)

    Returns:
        Token count
    """
    try:
        from src.services.agents.token_counter import TokenCounter

        return TokenCounter.count_tokens(text, model)
    except ImportError:
        return len(text) // 4


def estimate_messages_tokens(messages: list[dict[str, Any]], model: str = "gpt-4") -> int:
    """
    Estimate token count for a list of messages.

    Uses the TokenCounter service for accurate token counting.

    Args:
        messages: List of message dicts with 'role' and 'content' keys
        model: Model name for encoding selection (default: gpt-4)

    Returns:
        Total token count
    """
    try:
        from src.services.agents.token_counter import TokenCounter

        return TokenCounter.count_messages_tokens(messages, model)
    except ImportError:
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            total += len(content) // 4
        return total


def build_message_metadata(
    sources: list[dict[str, Any]] | None = None,
    charts: list[dict[str, Any]] | None = None,
    diagrams: list[dict[str, Any]] | None = None,
    infographics: list[dict[str, Any]] | None = None,
    generated_images: list[dict[str, Any]] | None = None,
    forms: list[dict[str, Any]] | None = None,
    fleet_cards: list[dict[str, Any]] | None = None,
    workflow_type: str | None = None,
    execution_log: list[dict[str, Any]] | None = None,
    workflow_state: dict[str, Any] | None = None,
    timing: dict[str, float] | None = None,
    usage: dict[str, int] | None = None,
) -> dict[str, Any]:
    """
    Build message metadata dictionary.

    Args:
        sources: Retrieved RAG sources
        charts: Chart data
        workflow_type: Workflow type if workflow agent
        execution_log: Workflow execution log
        workflow_state: Workflow state
        timing: Timing metrics (duration, time_to_first_token)
        usage: Token usage (input_tokens, output_tokens, total_tokens)

    Returns:
        Metadata dictionary
    """
    metadata = {}

    if sources:
        metadata["sources"] = sources

    if charts:
        metadata["charts"] = charts

    if diagrams:
        metadata["diagrams"] = diagrams

    if infographics:
        metadata["infographics"] = infographics

    if generated_images:
        metadata["generated_images"] = generated_images

    if forms:
        metadata["forms"] = forms

    if fleet_cards:
        metadata["fleet_cards"] = fleet_cards

    if workflow_type:
        metadata["workflow_type"] = workflow_type

    if execution_log:
        metadata["execution_log"] = execution_log

    if workflow_state:
        metadata["workflow_state"] = workflow_state

    if timing:
        metadata["timing"] = timing

    if usage:
        metadata["usage"] = usage

    # Convert numpy types to Python native types for JSON serialization
    return convert_to_json_serializable(metadata)


def format_attachment_context(attachments: list[dict[str, Any]]) -> str:
    """
    Format file attachments into context string.

    Args:
        attachments: List of attachment metadata

    Returns:
        Formatted attachment context string
    """
    if not attachments:
        return ""

    attachment_parts = ["# Attached Files\n"]

    for i, attachment in enumerate(attachments, 1):
        file_name = attachment.get("file_name", "Unknown")
        file_type = attachment.get("file_type", "")
        extracted_text = attachment.get("extracted_text", "")

        attachment_parts.append(f"\n## File {i}: {file_name}\n")
        attachment_parts.append(f"Type: {file_type}\n")

        if extracted_text:
            attachment_parts.append(f"Content:\n{extracted_text}\n")
        else:
            attachment_parts.append("(No text content extracted)\n")

    return "\n".join(attachment_parts)


def calculate_time_metrics(start_time: float, first_token_time: float | None, end_time: float) -> dict[str, float]:
    """
    Calculate timing metrics for chat response.

    Args:
        start_time: Request start timestamp
        first_token_time: First token timestamp (may be None)
        end_time: Request end timestamp

    Returns:
        Dictionary with timing metrics
    """
    metrics = {"total_time": round(end_time - start_time, 2)}

    if first_token_time:
        metrics["time_to_first_token"] = round(first_token_time - start_time, 2)

    return metrics
