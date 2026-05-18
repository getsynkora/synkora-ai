"""
Function Calling Implementation for Multi-Provider LLM Support.

Implements Google ADK-style function calling that works across different LLM providers.
"""

import asyncio
import datetime
import json
import logging
import os
import time
import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

# Timeout for non-streaming LLM calls (function calling / tool detection).
# Large contexts (many tool results) can take several minutes to process.
# Configurable via LLM_FUNCTION_CALLING_TIMEOUT env var.
LLM_FUNCTION_CALLING_TIMEOUT = int(os.getenv("LLM_FUNCTION_CALLING_TIMEOUT", "600"))

if TYPE_CHECKING:
    from src.services.security.pii_redactor import PIIRedactor

from src.helpers.streaming_helpers import convert_to_json_serializable
from src.services.agents.config import AgenticConfig
from src.services.agents.error_tracker import FunctionCallingErrorTracker
from src.services.observability.langfuse_service import LangfuseService

logger = logging.getLogger(__name__)


def _compact_schema(schema: dict) -> dict:
    """
    Strip ``description`` fields from a JSON parameter schema recursively.

    Preserves everything the LLM needs to call a tool correctly:
    - property names and types
    - enum values (critical for correct values)
    - required arrays
    - default values
    - nested object and array item schemas

    Removes only verbose English prose in ``description`` fields, which
    add significant token cost without improving call accuracy for modern
    LLMs that can infer meaning from names and types.

    The tool-level ``description`` (passed separately as a sibling key)
    is NOT touched — only parameter-level descriptions are stripped.
    """
    if not isinstance(schema, dict):
        return schema

    result: dict = {}
    for key, value in schema.items():
        if key == "description":
            continue  # strip parameter descriptions
        elif key == "properties" and isinstance(value, dict):
            result["properties"] = {prop_name: _compact_schema(prop_def) for prop_name, prop_def in value.items()}
        elif key == "items":
            result["items"] = _compact_schema(value) if isinstance(value, dict) else value
        elif key in ("anyOf", "oneOf", "allOf") and isinstance(value, list):
            result[key] = [_compact_schema(v) if isinstance(v, dict) else v for v in value]
        else:
            result[key] = value

    return result


def _scrub_for_observability(data: dict) -> dict:
    """Remove message content from observability payloads to avoid PII in traces."""
    import copy

    scrubbed = copy.deepcopy(data)
    if "messages" in scrubbed:
        for msg in scrubbed["messages"]:
            if isinstance(msg, dict) and "content" in msg:
                msg["content"] = f"[{len(str(msg.get('content', '')))} chars]"
    return scrubbed


@dataclass
class ToolExecutionResult:
    """Result of a single tool execution."""

    name: str
    result: Any
    success: bool
    duration_ms: int = 0
    retry_count: int = 0
    error: str | None = None


class FunctionCallingHandler:
    """
    Handles function calling for LLM agents across different providers.

    Implements the function calling loop:
    1. Send prompt with available tools to LLM
    2. LLM responds with function calls or final answer
    3. Execute requested functions
    4. Send function results back to LLM
    5. Repeat until LLM provides final answer
    """

    def __init__(
        self,
        llm_client,
        tools: list[str] | None = None,
        runtime_context: Optional["RuntimeContext"] = None,  # NEW
        tool_configs: dict[str, dict[str, Any]] | None = None,  # Keep for backward compat
        trace_id: str | None = None,
        observability_config: dict[str, Any] | None = None,
        agentic_config: AgenticConfig | None = None,
        langfuse_service: "LangfuseService | None" = None,
        pii_redactor: Optional["PIIRedactor"] = None,
    ):
        """
        Initialize function calling handler.

        Args:
            llm_client: The LLM client instance
            tools: List of tool names to make available (None = all tools)
            runtime_context: Runtime execution context (NEW)
            tool_configs: Dictionary mapping tool names to their configurations (legacy)
            trace_id: Optional Langfuse trace ID for observability
            observability_config: Optional observability configuration
            agentic_config: Configuration for agentic loop behavior (parallel tools, retries, etc.)
            langfuse_service: Optional pre-configured LangfuseService (avoids creating duplicate clients)
            pii_redactor: Optional PIIRedactor for redacting PII in tool results (None = disabled)
        """
        self.llm_client = llm_client
        # Normalize provider to lowercase for consistent comparison
        self.provider = llm_client.provider.lower() if hasattr(llm_client, "provider") else "unknown"
        self.runtime_context = runtime_context  # Store context
        self.tool_configs = tool_configs or {}  # Legacy
        self.available_tools = self._get_available_tools(tools)
        self.trace_id = trace_id
        self.observability_config = observability_config or {}
        self.langfuse_service = langfuse_service or LangfuseService.for_agent(self.observability_config)
        self.agentic_config = agentic_config or AgenticConfig()
        self.pii_redactor = pii_redactor

    def _get_available_tools(self, tool_names: list[str] | None) -> list[dict[str, Any]]:
        """Get tool definitions in the format needed."""
        # Import here to avoid circular import
        from src.services.agents.adk_tools import tool_registry

        # If no tools specified (None or empty list), return empty list
        if not tool_names:
            return []

        # Filter to only requested tools
        all_tools = tool_registry.list_tools()
        return [t for t in all_tools if t["name"] in tool_names]

    def _convert_tools_to_provider_format(self) -> Any:
        """Convert tools to provider-specific format."""
        if self.provider in ["google", "gemini"]:
            return self._convert_to_google_format()
        elif self.provider == "openai":
            return self._convert_to_openai_format()
        elif self.provider in ["anthropic", "claude"]:
            return self._convert_to_anthropic_format()
        else:
            # For other providers, return OpenAI format (most compatible)
            return self._convert_to_openai_format()

    def _convert_to_google_format(self) -> list[dict[str, Any]]:
        """Convert to Google Gemini function calling format."""
        from google.genai import types

        google_tools = []
        for tool in self.available_tools:
            function_declaration = types.FunctionDeclaration(
                name=tool["name"],
                description=tool["description"],
                parameters=_compact_schema(tool["parameters"]),
            )
            google_tools.append(types.Tool(function_declarations=[function_declaration]))

        return google_tools

    def _convert_to_openai_format(self) -> list[dict[str, Any]]:
        """Convert to OpenAI function calling format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": _compact_schema(tool["parameters"]),
                },
            }
            for tool in self.available_tools
        ]

    def _convert_to_anthropic_format(self) -> list[dict[str, Any]]:
        """Convert to Anthropic Claude tool format (type: custom required by Claude 4.x)."""
        return [
            {
                "type": "custom",
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": _compact_schema(tool["parameters"]),
            }
            for tool in self.available_tools
        ]

    async def generate_with_functions(
        self, prompt: str, temperature: float = 0.7, max_tokens: int | None = None, max_iterations: int = 20
    ) -> str:
        """
        Generate content with function calling support.

        Args:
            prompt: The user prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            max_iterations: Maximum function calling iterations

        Returns:
            Final response text
        """
        if not self.available_tools:
            # No tools available, just generate normally
            return await self.llm_client.generate_content(prompt=prompt, temperature=temperature, max_tokens=max_tokens)

        # Implement function calling loop
        conversation_history = [{"role": "user", "content": prompt}]

        for iteration in range(max_iterations):
            logger.info(f"Function calling iteration {iteration + 1}/{max_iterations}")

            # Generate response with tools
            response = await self._generate_with_tools(conversation_history, temperature, max_tokens)

            # Check if response contains function calls
            function_calls = self._extract_function_calls(response)

            if not function_calls:
                # No function calls, return final answer
                return self._extract_text_response(response)

            # Execute function calls — returns ordered list matching function_calls
            execution_results = await self._execute_functions(function_calls)

            # Add assistant's function call to conversation
            # For OpenAI format, we need to include tool_calls in the message
            assistant_message = {
                "role": "assistant",
                "content": None,  # No text content when making function calls
                "tool_calls": [
                    {
                        "id": f"call_{i}",
                        "type": "function",
                        "function": {"name": fc["name"], "arguments": json.dumps(fc["arguments"])},
                    }
                    for i, fc in enumerate(function_calls)
                ],
            }
            conversation_history.append(assistant_message)

            # Add function results as tool messages — use index to match call_id exactly
            for i, exec_result in enumerate(execution_results):
                result = exec_result.result if isinstance(exec_result, ToolExecutionResult) else exec_result
                func_name_i = function_calls[i]["name"] if i < len(function_calls) else "unknown"
                content = json.dumps(convert_to_json_serializable(result))
                # Trust boundary: wrap external tool output to reduce prompt-injection risk
                if isinstance(content, str) and len(content) > 0:
                    content = f'<external-tool-result tool="{func_name_i}">\n{content}\n</external-tool-result>'
                # PII redaction — no-op when pii_redactor is None (all existing agents unaffected)
                if self.pii_redactor:
                    content = self.pii_redactor.redact_tool_result(content)
                conversation_history.append(
                    {
                        "role": "tool",
                        "tool_call_id": f"call_{i}",
                        "content": content,
                    }
                )

        # Max iterations reached - generate a final summary response without tools
        logger.warning(f"Max function calling iterations ({max_iterations}) reached")

        # Add a system message to inform the LLM that max iterations was reached
        conversation_history.append(
            {
                "role": "user",
                "content": "[System: Maximum tool iterations reached. Please provide a summary of what you accomplished and what remains to be done, if anything. Do not call any more tools.]",
            }
        )

        # Make one final LLM call without tools to get a summary response
        messages = self._convert_history_to_openai_format(conversation_history)

        # Filter out tool-related messages (Anthropic requires tools= param if tool messages exist)
        filtered_messages = self._filter_tool_messages_for_summary(messages)

        chunks = []
        async for chunk in self.llm_client.generate_content_stream_with_messages(
            messages=filtered_messages, temperature=temperature, max_tokens=max_tokens
        ):
            chunks.append(chunk)
        return "".join(chunks)

    async def generate_with_functions_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        max_iterations: int = 20,
        messages: list[dict[str, str]] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Generate content with function calling support and streaming.

        Args:
            prompt: System prompt/instructions (used as system message)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            max_iterations: Maximum function calling iterations
            messages: Optional structured conversation history with proper roles.
                      If provided, these are used as the conversation history
                      instead of wrapping the prompt in a single user message.

        Yields:
            Dictionary with type and content:
            - {"type": "text", "content": "text chunk"}
            - {"type": "function_call", "name": "tool_name", "arguments": {...}}
            - {"type": "function_result", "name": "tool_name", "result": {...}}
        """
        if not self.available_tools:
            # No tools, stream normally
            async for chunk in self.llm_client.generate_content_stream(
                prompt=prompt, temperature=temperature, max_tokens=max_tokens
            ):
                yield {"type": "text", "content": chunk}
            return

        # Build PII-aware system prompt suffix when redact_for_response is active
        pii_system_note = ""
        if self.pii_redactor and self.pii_redactor.config.redact_for_response:
            pii_system_note = (
                "\n\nIMPORTANT — PII REDACTION: Tool results may contain placeholder tokens "
                "such as [EMAIL_1], [PHONE_1], [SSN_1], [CARD_1], [IP_1]. "
                "These tokens represent redacted personal data. "
                "Always reproduce them exactly as-is (e.g. show '[EMAIL_1]' in a table cell, not '—' or empty). "
                "Never attempt to infer, reconstruct, or omit these values."
            )

        # Build conversation history from structured messages if provided
        if messages:
            # Start with system message containing the prompt (system instructions)
            conversation_history = [{"role": "system", "content": prompt + pii_system_note}]
            # Add structured conversation messages
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role in ["user", "assistant"] and content:
                    conversation_history.append({"role": role, "content": content})
            logger.info(f"📝 Using structured conversation: {len(messages)} messages passed to LLM")
        else:
            conversation_history = [{"role": "user", "content": prompt + pii_system_note}]

        error_tracker = FunctionCallingErrorTracker(max_repeated_errors=3)

        # Import context pruning for managing tool results
        from src.services.agents.context_pruning import (
            PruningSettings,
            prune_tool_results,
        )

        pruning_settings = PruningSettings(
            enabled=True,
            keep_last_results=3,
            max_result_chars=5000,
            head_chars=1500,
            tail_chars=1500,
            max_total_tool_chars=400000,
        )

        # Deduplication cache: maps (tool_name + serialized_args) → result.
        # Avoids redundant tool re-execution within a single agentic run.
        # IMPORTANT: entries are evicted when their corresponding conversation-history
        # messages are pruned/truncated (see eviction block below).  This lets the LLM
        # re-read the full content of a pruned file instead of being stuck with a
        # truncated version indefinitely.
        _tool_call_cache: dict[str, Any] = {}

        # Loop detection: track the sequence of tool names called each iteration.
        # If the same pattern repeats LOOP_REPEAT_THRESHOLD times consecutively,
        # the agent is stuck doing the same thing without making progress.
        _iteration_tool_sequences: list[tuple[str, ...]] = []
        LOOP_REPEAT_THRESHOLD = 3
        # Polling/status tools are designed to be called repeatedly while waiting
        # for background work to complete — exclude them from loop detection.
        _POLLING_TOOL_NAMES: frozenset[str] = frozenset({"check_task", "list_background_tasks"})

        # "Not found" note deduplication: tracks keys we've already injected a
        # persistent user message for so we don't spam the conversation.
        _not_found_noted: set[str] = set()

        for iteration in range(max_iterations):
            logger.info(f"Function calling iteration {iteration + 1}/{max_iterations}")

            # Prune old tool results to prevent context bloat during long agentic loops
            if iteration > 0:  # Only prune after first iteration when we have tool results
                # Build tool_call_id → cache_key mapping BEFORE pruning so we can evict
                # pruned entries from _tool_call_cache.  Without this the LLM re-requests
                # a file, the cache returns the (now-truncated) version from history, and
                # the agent loops until it hits the max-iteration limit.
                _call_id_to_cache_key: dict[str, str] = {}
                for _msg in conversation_history:
                    if _msg.get("role") == "assistant" and _msg.get("tool_calls"):
                        for _tc in _msg["tool_calls"]:
                            _tc_id = _tc.get("id", "")
                            try:
                                _args = json.loads(_tc.get("function", {}).get("arguments", "{}"))
                                _ck = f"{_tc['function']['name']}:{json.dumps(_args, sort_keys=True)}"
                            except Exception:
                                _ck = _tc.get("function", {}).get("name", "")
                            if _tc_id and _ck:
                                _call_id_to_cache_key[_tc_id] = _ck

                conversation_history, pruning_stats = prune_tool_results(conversation_history, pruning_settings)
                if pruning_stats.chars_saved > 0:
                    logger.info(
                        f"Pruned {pruning_stats.chars_saved:,} chars "
                        f"(~{pruning_stats.estimated_tokens_saved:,} tokens) from tool results"
                        + (
                            f" ({pruning_stats.data_bearing_pruned} data-bearing trimmed)"
                            if pruning_stats.data_bearing_pruned
                            else ""
                        )
                    )
                    if self.runtime_context is not None:
                        try:
                            from src.services.agents.agent_trace_service import fire_tool_pruning

                            self.runtime_context.event_sequence += 1
                            fire_tool_pruning(
                                tenant_id=self.runtime_context.tenant_id,
                                agent_id=self.runtime_context.agent_id,
                                conversation_id=self.runtime_context.conversation_id,
                                sequence=self.runtime_context.event_sequence,
                                turn_index=self.runtime_context.llm_call_index,
                                tool_results_count=pruning_stats.tool_results_count,
                                tool_results_pruned=pruning_stats.tool_results_pruned,
                                data_bearing_pruned=pruning_stats.data_bearing_pruned,
                                chars_saved=pruning_stats.chars_saved,
                                estimated_tokens_saved=pruning_stats.estimated_tokens_saved,
                                original_chars=pruning_stats.original_chars,
                                pruned_chars=pruning_stats.pruned_chars,
                            )
                        except Exception as _prune_trace_err:
                            logger.warning("fire_tool_pruning failed (non-critical): %s", _prune_trace_err)

                # Evict any cache entries whose messages were truncated or replaced with
                # placeholders so the next identical request re-executes the tool and
                # gets fresh full content (which will land at the end of history and be
                # protected from pruning as one of the last keep_last_results entries).
                if pruning_stats.tool_results_pruned > 0:
                    from src.services.agents.context_pruning import RESULT_PRUNED_MARKER as _SUMMARY_MARKER

                    _TRIM_MARKER = "[... "
                    _PLACEHOLDER_MARKER = "[Previous "
                    for _msg in conversation_history:
                        if _msg.get("role") == "tool":
                            _content = _msg.get("content", "")
                            if isinstance(_content, str) and (
                                _TRIM_MARKER in _content
                                or _PLACEHOLDER_MARKER in _content
                                or _SUMMARY_MARKER in _content
                            ):
                                _tc_id = _msg.get("tool_call_id", "")
                                _ck = _call_id_to_cache_key.get(_tc_id)
                                if _ck and _ck in _tool_call_cache:
                                    del _tool_call_cache[_ck]
                                    logger.debug(f"Dedup cache evicted pruned entry: {_ck[:80]}")

            # Generate response with tools (non-streaming for function detection)
            _llm_iter_start = time.time()
            response = await self._generate_with_tools(conversation_history, temperature, max_tokens)
            _llm_iter_latency_ms = int((time.time() - _llm_iter_start) * 1000)

            # Fire LLM call trace event (fire-and-forget, zero latency)
            if self.runtime_context is not None:
                try:
                    from src.services.agents.agent_trace_service import fire_llm_call

                    self.runtime_context.llm_call_index += 1
                    self.runtime_context.event_sequence += 1
                    _usage = getattr(response, "usage", None)
                    # LiteLLM normalises to prompt_tokens/completion_tokens but some
                    # providers (Anthropic native) still return input_tokens/output_tokens.
                    # Fall back to the Anthropic names so tokens are never silently 0.
                    _in_tok = int(getattr(_usage, "prompt_tokens", None) or getattr(_usage, "input_tokens", None) or 0)
                    _out_tok = int(
                        getattr(_usage, "completion_tokens", None) or getattr(_usage, "output_tokens", None) or 0
                    )
                    _cache_read_tok = int(
                        getattr(_usage, "cache_read_input_tokens", None)
                        or getattr(_usage, "cache_read_tokens", None)
                        or 0
                    )
                    _cache_creation_tok = int(
                        getattr(_usage, "cache_creation_input_tokens", None)
                        or getattr(_usage, "cache_creation_tokens", None)
                        or 0
                    )
                    _resp_text = ""
                    if hasattr(response, "choices") and response.choices:
                        _msg = response.choices[0].message
                        _resp_text = (getattr(_msg, "content", "") or "")[:500]
                    from src.services.billing.llm_cost_service import calculate_cost as _calc_cost

                    _model_name = str(getattr(response, "model", "") or "")
                    _cost = _calc_cost(_model_name, _in_tok, _out_tok) or 0.0

                    # Capture LLM inputs for inspection in Agent Lens
                    _sys_parts = [m.get("content", "") for m in conversation_history if m.get("role") == "system"]
                    _sys_prompt_trace = ("\n\n".join(s for s in _sys_parts if s))[:2000] or None
                    _non_sys = [m for m in conversation_history if m.get("role") != "system"]
                    _msgs_preview = []
                    for _m in _non_sys[-20:]:
                        _c = _m.get("content")
                        if isinstance(_c, str):
                            _c = _c[:500]
                        elif isinstance(_c, list):
                            _c = [
                                {
                                    "type": _x.get("type", ""),
                                    "text": (_x.get("text", "")[:200] if _x.get("type") == "text" else "[non-text]"),
                                }
                                for _x in _c
                            ]
                        _msgs_preview.append({"role": _m.get("role"), "content": _c})
                    _messages_json = json.dumps(_msgs_preview, default=str)[:16000] if _msgs_preview else None
                    _tool_defs = []
                    for _t in self.available_tools or []:
                        _fn = _t.get("function", _t) if isinstance(_t, dict) else {}
                        _tool_defs.append(
                            {
                                "name": _fn.get("name", ""),
                                "description": (_fn.get("description", "") or "")[:200],
                                "parameters": _fn.get("parameters"),
                            }
                        )
                    _tools_json = json.dumps(_tool_defs, default=str) if _tool_defs else None

                    # Context window pressure: estimate utilization % from token counts.
                    # ModelConfig has no context_window field; use 128k as a safe
                    # universal fallback (correct for most modern models).
                    _ctx_window = 128000
                    _total_tok = _in_tok + _out_tok
                    _ctx_pct = round((_total_tok / _ctx_window) * 100, 2) if _total_tok else None

                    fire_llm_call(
                        tenant_id=self.runtime_context.tenant_id,
                        agent_id=self.runtime_context.agent_id,
                        conversation_id=self.runtime_context.conversation_id,
                        model=_model_name,
                        call_index=self.runtime_context.llm_call_index,
                        input_tokens=_in_tok,
                        output_tokens=_out_tok,
                        cost_usd=_cost,
                        latency_ms=_llm_iter_latency_ms,
                        response_preview=_resp_text,
                        status="success",
                        error=None,
                        sequence=self.runtime_context.event_sequence,
                        system_prompt=_sys_prompt_trace,
                        messages_json=_messages_json,
                        tools_json=_tools_json,
                        cache_read_tokens=_cache_read_tok,
                        cache_creation_tokens=_cache_creation_tok,
                        context_utilization_pct=_ctx_pct,
                    )
                except Exception as _llm_trace_err:
                    logger.warning("fire_llm_call failed (non-critical): %s", _llm_trace_err)

            # Check for function calls
            function_calls = self._extract_function_calls(response)

            # Log tool calling decision (no content - only metadata)
            has_tools = (
                hasattr(response, "choices")
                and response.choices
                and hasattr(response.choices[0].message, "tool_calls")
                and response.choices[0].message.tool_calls
            )
            logger.debug(
                f"LLM response: has_tool_calls={has_tools}, extracted_calls={len(function_calls)}, "
                f"available_tools={len(self.available_tools)}, history_msgs={len(conversation_history)}"
            )

            if not function_calls:
                # No function calls — use the text already in the non-streaming response.
                # The non-streaming call already has the full text; extracting it here
                # avoids a redundant second LLM call and the intermittent 0-chunks bug:
                # passing `tools` to a streaming call lets the model return tool_call
                # deltas (delta.content=None) instead of text deltas, silently dropping
                # the entire response.
                text_content = self._extract_text_response(response)
                if text_content:
                    yield {"type": "text", "content": text_content}
                    return

                # Fallback: non-streaming response had no text (rare). Stream without
                # tools so the model is forced to produce text content, not tool calls.
                if self.provider in ["anthropic", "claude"]:
                    messages = self._convert_history_to_anthropic_format(conversation_history)
                else:
                    messages = self._convert_history_to_openai_format(conversation_history)

                async for chunk in self.llm_client.generate_content_stream_with_messages(
                    messages=messages, temperature=temperature, max_tokens=max_tokens
                ):
                    yield {"type": "text", "content": chunk}
                return

            # Loop detection: check BEFORE yielding or executing to avoid orphaned tool events.
            # Only flag as a loop when the SAME tool is called with the SAME arguments
            # repeatedly — different queries/args on the same tool are legitimate progress.
            def _call_fingerprint(fc: dict[str, Any]) -> str:
                try:
                    return f"{fc['name']}:{json.dumps(fc.get('arguments', {}), sort_keys=True)}"
                except Exception:
                    return fc["name"]

            current_sequence = tuple(_call_fingerprint(fc) for fc in function_calls)
            # Only track iterations where at least one non-polling tool is called.
            # check_task / list_background_tasks are designed for repeated polling
            # and must not trigger the stuck-loop guard.
            _non_polling_calls = [fc for fc in function_calls if fc["name"] not in _POLLING_TOOL_NAMES]
            if _non_polling_calls:
                _iteration_tool_sequences.append(current_sequence)
                if len(_iteration_tool_sequences) > LOOP_REPEAT_THRESHOLD:
                    _iteration_tool_sequences.pop(0)
            if len(_iteration_tool_sequences) == LOOP_REPEAT_THRESHOLD and len(set(_iteration_tool_sequences)) == 1:
                loop_tools = ", ".join(f"`{fc['name']}`" for fc in function_calls)
                logger.warning(
                    f"🔁 Loop detected: identical tool call(s) {current_sequence} repeated "
                    f"{LOOP_REPEAT_THRESHOLD} times with same arguments. Stopping."
                )
                yield {
                    "type": "text",
                    "content": (
                        f"\n\n⚠️ **Stuck Loop Detected**\n\n"
                        f"The same tool call ({loop_tools}) was made {LOOP_REPEAT_THRESHOLD} times "
                        f"in a row with identical arguments without making progress. "
                        f"Stopping to avoid wasting resources."
                    ),
                }
                return

            # Yield function calls
            for func_call in function_calls:
                yield {"type": "function_call", "name": func_call["name"], "arguments": func_call["arguments"]}

            # Separate cached vs uncached calls to avoid redundant fetches.
            # After context pruning replaces old tool results with placeholders the LLM
            # may re-request the exact same tool+args — serve those from cache instantly.
            uncached_calls: list[dict[str, Any]] = []
            cached_results_by_idx: dict[int, Any] = {}
            for idx, fc in enumerate(function_calls):
                try:
                    cache_key = f"{fc['name']}:{json.dumps(fc['arguments'], sort_keys=True)}"
                except Exception:
                    cache_key = None
                if cache_key and cache_key in _tool_call_cache:
                    cached_results_by_idx[idx] = _tool_call_cache[cache_key]
                    logger.debug(f"Tool dedup cache HIT: {fc['name']} — skipping redundant call")
                else:
                    uncached_calls.append((idx, fc, cache_key))

            # Execute only uncached calls
            fresh_exec_results: list[ToolExecutionResult] = []
            if uncached_calls:
                fresh_exec_results = await self._execute_functions([fc for _, fc, _ in uncached_calls])
                # Store in cache
                for (_idx, _fc, cache_key), exec_result in zip(uncached_calls, fresh_exec_results, strict=False):
                    if cache_key:
                        _tool_call_cache[cache_key] = exec_result.result

            # Merge: build ordered list of results matching original function_calls order
            fresh_iter = iter(fresh_exec_results)
            execution_results: list[ToolExecutionResult] = []
            for idx, fc in enumerate(function_calls):
                if idx in cached_results_by_idx:
                    execution_results.append(
                        ToolExecutionResult(name=fc["name"], result=cached_results_by_idx[idx], success=True)
                    )
                else:
                    execution_results.append(next(fresh_iter))

            # Check for repeated errors (circuit breaker)
            for exec_result in execution_results:
                if not exec_result.success or (
                    isinstance(exec_result.result, dict) and exec_result.result.get("error")
                ):
                    error_message = exec_result.error or (
                        exec_result.result.get("error", "") if isinstance(exec_result.result, dict) else ""
                    )

                    # "File not found" is a deterministic, non-transient error — retrying the
                    # same path will never succeed.  Instead of counting toward the circuit
                    # breaker (which would kill the whole agent), inject a persistent user
                    # message into conversation history.  User-role messages are never touched
                    # by the context pruner, so the agent will remember the path doesn't exist
                    # even after many iterations of pruning.
                    _NOT_FOUND_PHRASES = (
                        "file not found",
                        "not found",
                        "no such file",
                        "does not exist",
                        "path not found",
                        "no such directory",
                        "exceeds maximum allowed size",
                    )
                    if any(p in error_message.lower() for p in _NOT_FOUND_PHRASES):
                        note_key = f"{exec_result.name}:{error_message[:150]}"
                        if note_key not in _not_found_noted:
                            _not_found_noted.add(note_key)
                            conversation_history.append(
                                {
                                    "role": "user",
                                    "content": (
                                        f"[System note: {error_message} — this path does not exist. "
                                        "Do not retry it; look for the correct path instead.]"
                                    ),
                                }
                            )
                            logger.debug(f"Injected persistent not-found note for: {error_message[:120]}")
                        continue  # Do not count toward circuit breaker

                    should_break = error_tracker.track_error(exec_result.name, error_message)
                    if should_break:
                        yield {
                            "type": "text",
                            "content": f"\n\n⚠️ **Circuit Breaker Activated**\n\nTool `{exec_result.name}` failed {error_tracker.max_repeated_errors} times in a row.\n- Last error: {error_message[:300]}\n\nStopping to prevent infinite loop. Please fix the underlying issue.",
                        }
                        return
                else:
                    # Reset error count on success so legitimate retries after fixing params still work
                    error_tracker.error_counts.pop(exec_result.name, None)

            # Yield function results and check for charts
            for exec_result in execution_results:
                func_name = exec_result.name
                result = exec_result.result
                yield {"type": "function_result", "name": func_name, "result": result}

                # If this was a chart creation tool, also emit a chart event
                # Handle internal_generate_chart, internal_query_and_chart, and generate_chart_from_data
                if func_name in ["internal_generate_chart", "internal_query_and_chart", "generate_chart_from_data"]:
                    chart_data = None

                    if func_name == "internal_query_and_chart" and isinstance(result, dict) and "chart" in result:
                        # internal_query_and_chart returns chart info under "chart" key
                        chart_data = result.get("chart", {})
                    elif func_name == "generate_chart_from_data" and isinstance(result, dict) and "chart" in result:
                        # generate_chart_from_data returns chart config under "chart" key
                        chart_config = result.get("chart", {})

                        # Convert to format expected by ChartRenderer component
                        # ChartRenderer expects: {id, title, description, chart_type, library, config, data, created_at}
                        yield {
                            "type": "chart",
                            "chart": {
                                "id": f"inline_{func_name}_{hash(str(chart_config))}",
                                "title": chart_config.get("title", "Chart"),
                                "description": chart_config.get("description", ""),
                                "chart_type": chart_config.get("chart_type", "bar"),
                                "library": chart_config.get("library", "chartjs"),
                                "config": chart_config.get("config", {}),
                                "data": chart_config.get("data", {}),
                                "table_data": chart_config.get("table_data"),
                                "created_at": datetime.datetime.now().isoformat(),
                                "inline": True,
                            },
                        }
                        chart_data = None  # Already handled
                    elif isinstance(result, dict) and "chart_id" in result:
                        # internal_generate_chart returns chart info directly
                        chart_data = result

                    if chart_data and "chart_id" in chart_data:
                        yield {
                            "type": "chart",
                            "chart_id": chart_data["chart_id"],
                            "chart_type": chart_data.get("chart_type"),
                            "chart_config": chart_data.get("chart_config"),
                            "chart_data": chart_data.get("chart_data"),
                        }

                # Emit charts returned by analyze_data_statistics
                if (
                    func_name == "analyze_data_statistics"
                    and isinstance(result, dict)
                    and result.get("success")
                    and "charts" in result
                ):
                    for stat_chart in result.get("charts", []):
                        yield {
                            "type": "chart",
                            "chart": {
                                "id": f"stat_{uuid.uuid4().hex[:8]}",
                                "title": stat_chart.get("title", "Statistics"),
                                "description": stat_chart.get("description", ""),
                                "chart_type": stat_chart.get("chart_type", "bar"),
                                "library": stat_chart.get("library", "chartjs"),
                                "config": stat_chart.get("config", {}),
                                "data": stat_chart.get("data", {}),
                                "table_data": stat_chart.get("table_data"),
                                "created_at": datetime.datetime.now().isoformat(),
                                "inline": True,
                            },
                        }

                # Diagram tool detection
                if func_name in ["internal_generate_diagram", "internal_generate_quick_diagram"]:
                    if isinstance(result, dict) and result.get("success") and "diagram" in result:
                        diagram_info = result["diagram"]
                        yield {
                            "type": "diagram",
                            "diagram": {
                                "id": f"diag_{uuid.uuid4().hex[:8]}",
                                "title": diagram_info.get("title", "Diagram"),
                                "diagram_type": diagram_info.get("diagram_type", "architecture"),
                                "style": diagram_info.get("style"),
                                "svg_url": diagram_info.get("svg_url"),
                                "svg_content": diagram_info.get("svg_content"),
                                "png_url": diagram_info.get("png_url"),
                                "created_at": datetime.datetime.now().isoformat(),
                            },
                        }

                # Mapbox static map — emit as inline image block
                if func_name in ["internal_get_static_map", "internal_get_directions"]:
                    if isinstance(result, dict) and result.get("success") and result.get("map_url"):
                        yield {
                            "type": "vehicle_map",
                            "map": {
                                "id": f"map_{uuid.uuid4().hex[:8]}",
                                "map_url": result["map_url"],
                                "embed_url": result.get("embed_url"),
                                "center": result.get("center") or result.get("origin"),
                                "zoom": result.get("zoom", 13),
                                "marker_count": result.get("marker_count", 0),
                                "distance_km": result.get("distance_km"),
                                "duration_min": result.get("duration_min"),
                                "profile": result.get("profile"),
                                "created_at": datetime.datetime.now().isoformat(),
                            },
                        }

                # Fleet health / intelligence — emit as fleet_card
                if func_name in [
                    "internal_micromobility_get_fleet_health",
                    "internal_micromobility_get_zone_demand_supply",
                    "internal_micromobility_predict_demand",
                    "internal_micromobility_get_rebalancing_plan",
                    "internal_micromobility_get_trip_performance",
                    "internal_micromobility_analyze_event_impact",
                    "internal_micromobility_get_network_health",
                    "internal_micromobility_get_parking_compliance",
                    "internal_micromobility_get_battery_degradation",
                    "internal_micromobility_get_ranger_performance",
                ]:
                    if isinstance(result, dict) and result.get("success"):
                        yield {
                            "type": "fleet_card",
                            "card": {
                                "id": f"fleet_{uuid.uuid4().hex[:8]}",
                                "tool": func_name,
                                "data": result,
                                "created_at": datetime.datetime.now().isoformat(),
                            },
                        }

                # Image generation tool detection
                if func_name == "internal_generate_image":
                    if isinstance(result, dict) and result.get("success"):
                        yield {
                            "type": "generated_image",
                            "generated_image": {
                                "id": f"img_{uuid.uuid4().hex[:8]}",
                                "url": result.get("url"),
                                "prompt": result.get("prompt", ""),
                                "revised_prompt": result.get("revised_prompt", ""),
                                "model": result.get("model", ""),
                                "provider": result.get("provider", ""),
                                "size": result.get("size", ""),
                                "created_at": datetime.datetime.now().isoformat(),
                            },
                        }

                # Infographic tool detection
                if func_name in ["internal_generate_infographic", "internal_generate_slack_infographic"]:
                    if isinstance(result, dict) and result.get("success"):
                        yield {
                            "type": "infographic",
                            "infographic": {
                                "id": f"infog_{uuid.uuid4().hex[:8]}",
                                "title": result.get("title", "Infographic"),
                                "theme": result.get("theme", "dark"),
                                "svg_url": result.get("svg_url"),
                                "svg_content": result.get("svg_content"),
                                "png_url": result.get("png_url"),
                                "created_at": datetime.datetime.now().isoformat(),
                            },
                        }

            # Update conversation history with proper format
            # Generate UNIQUE tool_call IDs per call so parallel calls to the same tool
            # each get their own ID and their own result message.
            call_ids = [f"call_{uuid.uuid4().hex[:8]}" for _ in function_calls]

            assistant_message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": call_ids[i],
                        "type": "function",
                        "function": {"name": fc["name"], "arguments": json.dumps(fc["arguments"])},
                    }
                    for i, fc in enumerate(function_calls)
                ],
            }
            conversation_history.append(assistant_message)

            # Add tool results — matched by index (not name) so each call gets its own result
            for i, exec_result in enumerate(execution_results):
                result = exec_result.result

                # Strip large SVG/binary content from diagram results before sending to LLM.
                # The SVG is already emitted as a separate SSE event for the frontend; the LLM
                # only needs to know the diagram was generated (not the raw SVG markup).
                if exec_result.name in ("internal_generate_diagram", "internal_generate_quick_diagram"):
                    if isinstance(result, dict) and result.get("success") and "diagram" in result:
                        diag = result["diagram"]
                        result = {
                            "success": True,
                            "message": "Diagram generated and rendered successfully. It has been displayed to the user inline.",
                            "diagram": {
                                "title": diag.get("title"),
                                "diagram_type": diag.get("diagram_type"),
                                "style": diag.get("style"),
                                "svg_url": diag.get("svg_url"),
                                "png_url": diag.get("png_url"),
                            },
                        }

                # Strip URL from image generation results — already emitted as a separate SSE event.
                if exec_result.name == "internal_generate_image":
                    if isinstance(result, dict) and result.get("success"):
                        result = {
                            "success": True,
                            "message": "Image generated and displayed to the user inline.",
                            "model": result.get("model"),
                            "provider": result.get("provider"),
                        }

                # Strip SVG content from infographic results — already emitted as a separate SSE event.
                if exec_result.name in ("internal_generate_infographic", "internal_generate_slack_infographic"):
                    if isinstance(result, dict) and result.get("success"):
                        result = {
                            "success": True,
                            "message": "Infographic generated and rendered successfully. It has been displayed to the user inline.",
                            "title": result.get("title"),
                            "svg_url": result.get("svg_url"),
                            "png_url": result.get("png_url"),
                        }

                content = json.dumps(convert_to_json_serializable(result)) if not isinstance(result, str) else result
                # Trust boundary: wrap external tool output to reduce prompt-injection risk
                if isinstance(content, str) and len(content) > 0:
                    content = f'<external-tool-result tool="{func_name}">\n{content}\n</external-tool-result>'
                # PII redaction — no-op when pii_redactor is None (all existing agents unaffected)
                if self.pii_redactor:
                    content = self.pii_redactor.redact_tool_result(content)
                conversation_history.append({"role": "tool", "tool_call_id": call_ids[i], "content": content})

        # Max iterations reached - generate a final summary response without tools
        logger.warning(f"Max function calling iterations ({max_iterations}) reached")

        # Add a system message to inform the LLM that max iterations was reached
        conversation_history.append(
            {
                "role": "user",
                "content": "[System: Maximum tool iterations reached. Please provide a summary of what you accomplished and what remains to be done, if anything. Do not call any more tools.]",
            }
        )

        # Make one final LLM call without tools to get a summary response
        messages = self._convert_history_to_openai_format(conversation_history)

        # Filter out tool-related messages for the final call (Anthropic requires tools= param if tool messages exist)
        filtered_messages = self._filter_tool_messages_for_summary(messages)

        # Stream the final response without tools so the agent summarizes
        async for chunk in self.llm_client.generate_content_stream_with_messages(
            messages=filtered_messages, temperature=temperature, max_tokens=max_tokens
        ):
            yield {"type": "text", "content": chunk}

    @staticmethod
    async def _litellm_stream_and_collect(completion_params: dict[str, Any]) -> Any:
        """Stream a LiteLLM call and accumulate into a single response object.

        Using stream=True avoids Cloudflare 524 errors on proxied LiteLLM deployments:
        streaming connections keep Cloudflare's proxy read timeout from firing because
        the server sends chunks before the 120-second window expires.
        """
        import litellm

        completion_params = {**completion_params, "stream": True}
        logger.debug(
            "LiteLLM streaming acompletion starting for model: %s, messages: %d",
            completion_params.get("model"),
            len(completion_params.get("messages", [])),
        )
        import asyncio

        stream = await litellm.acompletion(**completion_params)
        chunks = [chunk async for chunk in stream]

        # stream_chunk_builder_async was removed in litellm ≥ 1.55.
        # Wrap the synchronous builder in a coroutine to preserve the async
        # interface without spinning up a thread (it's pure in-memory work).
        async def _build() -> Any:
            return litellm.stream_chunk_builder(
                chunks=chunks,
                messages=completion_params.get("messages"),
            )

        response = await _build()
        logger.debug("LiteLLM streaming acompletion completed for model: %s", completion_params.get("model"))
        return response

    async def _generate_with_tools(
        self, conversation_history: list[dict[str, Any]], temperature: float, max_tokens: int | None
    ) -> Any:
        """Generate response with tools based on provider."""
        # Use LLM client's configured max_tokens if not specified
        # This is critical for tool calls that generate large content (e.g., PDF generation)
        if max_tokens is None and hasattr(self.llm_client, "config") and self.llm_client.config:
            max_tokens = self.llm_client.config.max_tokens
            if max_tokens:
                logger.info(f"📝 Using LLM config max_tokens: {max_tokens}")

        # Ensure a reasonable default for Anthropic models which require max_tokens
        # Use 16384 as default to support large content generation (e.g., PDFs, documents)
        if max_tokens is None:
            max_tokens = 16384  # Higher default for tool calling with large content
            logger.info(f"📝 Using default max_tokens: {max_tokens}")

        if self.provider == "mock":
            return await self._generate_mock_with_tools(conversation_history, temperature, max_tokens)
        elif self.provider in ["google", "gemini"]:
            return await self._generate_google_with_tools(conversation_history, temperature, max_tokens)
        elif self.provider == "openai":
            return await self._generate_openai_with_tools(conversation_history, temperature, max_tokens)
        elif self.provider in ["anthropic", "claude"]:
            return await self._generate_anthropic_with_tools(conversation_history, temperature, max_tokens)
        else:
            return await self._generate_openai_with_tools(conversation_history, temperature, max_tokens)

    async def _generate_mock_with_tools(
        self, conversation_history: list[dict[str, Any]], temperature: float, max_tokens: int | None
    ) -> Any:
        """
        Generate mock response for load testing.

        Returns a mock response that simulates an LLM responding WITHOUT calling any tools.
        This allows load testing the full pipeline without incurring LLM API costs.
        """
        import random

        # Simulate LLM processing delay (100-500ms)
        await asyncio.sleep(random.uniform(0.1, 0.5))

        # Mock responses that don't require tool calls
        mock_responses = [
            "I understand your question. Let me help you with that. Based on my analysis, here's what I can tell you about this topic.",
            "Thank you for reaching out! I'd be happy to assist you with this matter. Here's a comprehensive response.",
            "Great question! Let me break this down for you step by step. The key points to consider are as follows.",
            "I appreciate you bringing this to my attention. Here's my detailed response covering the main aspects.",
            "Let me provide you with a thorough answer to your question. Here's what you need to know.",
        ]

        # Create a mock response object that mimics OpenAI/LiteLLM structure
        class MockMessage:
            def __init__(self, content):
                self.content = content
                self.tool_calls = None  # No tool calls in mock mode

        class MockChoice:
            def __init__(self, message):
                self.message = message
                self.finish_reason = "stop"

        class MockUsage:
            def __init__(self):
                self.prompt_tokens = 100
                self.completion_tokens = 50
                self.total_tokens = 150

        class MockResponse:
            def __init__(self, content):
                self.choices = [MockChoice(MockMessage(content))]
                self.usage = MockUsage()
                self.model = "mock-model"

        response_text = random.choice(mock_responses)
        logger.debug(f"🧪 Mock function calling returning response ({len(response_text)} chars)")

        return MockResponse(response_text)

    async def _generate_google_with_tools(
        self, conversation_history: list[dict[str, Any]], temperature: float, max_tokens: int | None
    ) -> Any:
        """Generate with Google Gemini function calling."""
        from google.genai import types

        # Convert conversation to Google format
        contents = self._convert_history_to_google_format(conversation_history)

        # Get tools in Google format
        tools = self._convert_to_google_format()

        config = types.GenerateContentConfig(temperature=temperature, max_output_tokens=max_tokens, tools=tools)

        response = self.llm_client._client.models.generate_content(
            model=self.llm_client.config.model_name, contents=contents, config=config
        )

        return response

    async def _generate_openai_with_tools(
        self, conversation_history: list[dict[str, Any]], temperature: float, max_tokens: int | None
    ) -> Any:
        """Generate with OpenAI function calling."""
        messages = self._convert_history_to_openai_format(conversation_history)
        tools = self._convert_to_openai_format()

        # Check if tracing should be enabled
        should_trace = self.langfuse_service.should_trace(self.observability_config)
        import time

        start_time = time.time()

        logger.info(
            f"🔍 LLM Generation (function_calling) - should_trace: {should_trace}, observability_config: {self.observability_config}"
        )

        try:
            # For LiteLLM, use litellm.acompletion
            if self.provider == "litellm":
                import litellm

                # Prepare model name with provider prefix (e.g., anthropic/claude-4-5-sonnet)
                model_name = self.llm_client._prepare_litellm_model_name(self.llm_client.config.model_name)

                completion_params = {
                    "model": model_name,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "tools": tools,
                    "tool_choice": "auto",
                    "api_key": self.llm_client.config.api_key,
                    "timeout": LLM_FUNCTION_CALLING_TIMEOUT,
                    "num_retries": 1,  # One retry on 429/503 to avoid silent hangs
                    "drop_params": True,  # Silently drop unsupported params (e.g. temperature for gpt-5)
                }

                # Add base URL if provided
                if self.llm_client.config.api_base:
                    completion_params["api_base"] = self.llm_client.config.api_base

                response = await self._litellm_stream_and_collect(completion_params)
            else:
                response = await self.llm_client._client.chat.completions.create(
                    model=self.llm_client.config.model_name,
                    messages=messages,
                    **self.llm_client._build_openai_params(max_tokens, temperature),
                    tools=tools,
                    tool_choice="auto",
                    timeout=LLM_FUNCTION_CALLING_TIMEOUT,
                )

            # Create Langfuse generation if tracing is enabled (after getting response)
            if should_trace and self.trace_id:
                logger.info(f"📊 Creating Langfuse generation for model: {self.llm_client.config.model_name}")

                # Extract usage information if available
                usage_data = None
                if hasattr(response, "usage") and response.usage:
                    usage = response.usage
                    # Anthropic uses input_tokens/output_tokens; OpenAI uses prompt_tokens/completion_tokens
                    input_tokens = getattr(usage, "input_tokens", None) or getattr(usage, "prompt_tokens", None) or 0
                    output_tokens = (
                        getattr(usage, "output_tokens", None) or getattr(usage, "completion_tokens", None) or 0
                    )
                    usage_data = {
                        "input": input_tokens,
                        "output": output_tokens,
                        "total": getattr(usage, "total_tokens", None) or (input_tokens + output_tokens),
                    }

                # Extract response content
                response_content = self._extract_text_response(response)
                function_calls = self._extract_function_calls(response)

                self.langfuse_service.create_generation(
                    name="llm_generation_with_tools",
                    model=self.llm_client.config.model_name,
                    input_data=_scrub_for_observability({"messages": messages, "tools_count": len(tools)}),
                    output_data={
                        "response": response_content,
                        "function_calls": function_calls,
                        "has_function_calls": len(function_calls) > 0,
                    },
                    usage=usage_data,
                    metadata={
                        "provider": self.provider,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "has_tools": True,
                        "tool_count": len(tools),
                        "latency_ms": int((time.time() - start_time) * 1000),
                        "function_calls_count": len(function_calls),
                    },
                    trace_id=self.trace_id,
                )

            return response

        except Exception as e:
            # Log error to Langfuse if tracing is enabled
            if should_trace and self.trace_id:
                logger.warning(f"LLM generation failed: {e}")
                self.langfuse_service.create_generation(
                    name="llm_generation_with_tools",
                    model=self.llm_client.config.model_name,
                    input_data=_scrub_for_observability({"messages": messages, "tools_count": len(tools)}),
                    output_data={"error": str(e)},
                    metadata={
                        "provider": self.provider,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "has_tools": True,
                        "tool_count": len(tools),
                        "error": True,
                        "error_type": type(e).__name__,
                        "latency_ms": int((time.time() - start_time) * 1000),
                    },
                    trace_id=self.trace_id,
                )
            raise

    async def _generate_anthropic_with_tools(
        self, conversation_history: list[dict[str, Any]], temperature: float, max_tokens: int | None
    ) -> Any:
        """Generate with Anthropic Claude tool use."""
        messages = self._convert_history_to_anthropic_format(conversation_history)
        tools = self._convert_to_anthropic_format()

        # Extract system prompt from conversation history (Anthropic requires it top-level)
        system_parts = [m["content"] for m in conversation_history if m.get("role") == "system"]
        system_prompt = "\n\n".join(system_parts) if system_parts else None

        # For LiteLLM with Anthropic, use litellm.acompletion
        if self.provider == "litellm":
            import litellm

            completion_params = {
                "model": self.llm_client.config.model_name,
                "max_tokens": max_tokens or 4096,
                "temperature": temperature,
                "messages": messages,
                "tools": tools,
                "api_key": self.llm_client.config.api_key,
                "timeout": LLM_FUNCTION_CALLING_TIMEOUT,
                "num_retries": 1,  # One retry on 429/503 to avoid silent hangs
                "drop_params": True,  # Silently drop unsupported params (e.g. temperature for gpt-5)
            }

            # Add base URL if provided
            if self.llm_client.config.api_base:
                completion_params["api_base"] = self.llm_client.config.api_base

            response = await self._litellm_stream_and_collect(completion_params)
        else:
            # For native Anthropic client
            # Cap max_tokens for this non-streaming tool-detection call.
            # The SDK rejects non-streaming calls with high max_tokens (>10min threshold).
            # This call only needs to detect tool_use blocks, not generate a full response.
            tool_detection_max_tokens = min(max_tokens or 4096, 4096)
            create_params: dict[str, Any] = {
                "model": self.llm_client.config.model_name,
                "max_tokens": tool_detection_max_tokens,
                "temperature": temperature,
                "messages": messages,
                "tools": tools,
            }
            if system_prompt:
                create_params["system"] = system_prompt

            # Add cache_control to the last tool entry — caches the entire tool list prefix.
            # Any change to the tool list will change the last entry, auto-busting the cache.
            _CACHEABLE = ("claude-3", "claude-sonnet", "claude-haiku", "claude-opus")
            model = getattr(self.llm_client.config, "model_name", "")
            if tools and any(p in model.lower() for p in _CACHEABLE):
                try:
                    create_params["tools"] = list(tools)
                    create_params["tools"][-1] = {
                        **create_params["tools"][-1],
                        "cache_control": {"type": "ephemeral"},
                    }
                    create_params.setdefault("extra_headers", {})["anthropic-beta"] = "prompt-caching-2024-07-31"
                except Exception:
                    pass  # caching is optional; fall back to uncached call

            response = await self.llm_client._client.messages.create(**create_params, timeout=300)

        return response

    def _extract_function_calls(self, response: Any) -> list[dict[str, Any]]:
        """Extract function calls from provider response."""
        if self.provider in ["google", "gemini"]:
            return self._extract_google_function_calls(response)
        elif self.provider in ["openai", "litellm", "mock"]:
            # OpenAI, LiteLLM, and mock all use the same response format
            return self._extract_openai_function_calls(response)
        elif self.provider in ["anthropic", "claude"]:
            return self._extract_anthropic_function_calls(response)
        return []

    def _extract_google_function_calls(self, response: Any) -> list[dict[str, Any]]:
        """Extract function calls from Google response."""
        function_calls = []

        if hasattr(response, "candidates") and response.candidates:
            for candidate in response.candidates:
                if hasattr(candidate, "content") and hasattr(candidate.content, "parts"):
                    for part in candidate.content.parts:
                        if hasattr(part, "function_call"):
                            function_calls.append(
                                {"name": part.function_call.name, "arguments": dict(part.function_call.args)}
                            )

        return function_calls

    def _extract_openai_function_calls(self, response: Any) -> list[dict[str, Any]]:
        """Extract function calls from OpenAI response."""
        function_calls = []

        if hasattr(response, "choices") and response.choices:
            message = response.choices[0].message
            if hasattr(message, "tool_calls") and message.tool_calls:
                for tool_call in message.tool_calls:
                    function_calls.append(
                        {"name": tool_call.function.name, "arguments": json.loads(tool_call.function.arguments)}
                    )

        return function_calls

    def _extract_anthropic_function_calls(self, response: Any) -> list[dict[str, Any]]:
        """Extract function calls from Anthropic response."""
        function_calls = []

        if hasattr(response, "content"):
            for block in response.content:
                if hasattr(block, "type") and block.type == "tool_use":
                    function_calls.append({"name": block.name, "arguments": block.input})

        return function_calls

    def _extract_text_response(self, response: Any) -> str:
        """Extract text from provider response."""
        if self.provider in ["google", "gemini"]:
            return response.text if hasattr(response, "text") else str(response)
        elif self.provider in ["openai", "litellm", "mock"]:
            # OpenAI, LiteLLM, and mock all use the same response format
            if hasattr(response, "choices") and response.choices:
                message = response.choices[0].message
                return message.content or ""
            return str(response)
        elif self.provider in ["anthropic", "claude"]:
            text_blocks = [block.text for block in response.content if hasattr(block, "text")]
            return " ".join(text_blocks)
        return str(response)

    async def _execute_single_tool_with_retry(
        self,
        func_name: str,
        func_args: dict[str, Any],
        should_trace: bool,
    ) -> ToolExecutionResult:
        """
        Execute a single tool with retry and exponential backoff.

        Args:
            func_name: Tool function name
            func_args: Tool arguments
            should_trace: Whether to create Langfuse spans

        Returns:
            ToolExecutionResult with result, timing, and retry info
        """
        from src.services.agents.adk_tools import tool_registry

        max_retries = self.agentic_config.tool_retry_attempts
        base_delay = self.agentic_config.tool_retry_delay
        last_result = None
        last_error = None

        for attempt in range(max_retries + 1):
            start_time = time.time()

            try:
                if attempt > 0:
                    logger.info(f"Retrying function: {func_name} (attempt {attempt + 1}/{max_retries + 1})")

                logger.info(f"Executing function: {func_name} with args: {func_args}")

                # Validate func_args against the tool's declared JSON schema
                tool_schema = next(
                    (
                        t
                        for t in self.available_tools
                        if t.get("name") == func_name or t.get("function", {}).get("name") == func_name
                    ),
                    None,
                )
                if tool_schema:
                    params_schema = tool_schema.get("parameters") or tool_schema.get("function", {}).get(
                        "parameters", {}
                    )
                    if params_schema and params_schema.get("properties"):
                        try:
                            import jsonschema

                            jsonschema.validate(func_args, params_schema)
                        except jsonschema.ValidationError as ve:
                            logger.warning(f"Tool {func_name} called with invalid args: {ve.message}")
                            return ToolExecutionResult(
                                name=func_name,
                                result={"error": f"Invalid tool arguments: {ve.message}"},
                                success=False,
                                error=ve.message,
                            )

                # Execute with appropriate context
                if self.runtime_context:
                    async with self.runtime_context.scoped_db_context() as tool_runtime_context:
                        result = await tool_registry.execute_tool(
                            func_name,
                            func_args,
                            runtime_context=tool_runtime_context,
                        )
                else:
                    # Legacy path
                    tool_config = self.tool_configs.get(func_name, {})
                    if "_runtime_context" in self.tool_configs:
                        tool_config["_runtime_context"] = self.tool_configs["_runtime_context"]
                    result = await tool_registry.execute_tool(func_name, func_args, config=tool_config)

                duration_ms = int((time.time() - start_time) * 1000)

                # Check if result contains a non-empty error (key existence is not enough)
                if isinstance(result, dict) and result.get("error"):
                    logger.info(f"Function {func_name} returned error: {result.get('error')}")
                    last_result = result
                    last_error = result.get("error", "")

                    # Don't retry parameter validation errors or missing config - they won't succeed on retry
                    if "Missing required parameter" in str(last_error) or "not configured" in str(last_error).lower():
                        break

                    # Don't retry missing system commands - the binary won't appear on retry
                    if (
                        "command not found" in str(last_error).lower()
                        or "no such file or directory" in str(last_error).lower()
                    ):
                        logger.info(f"Not retrying {func_name}: missing system command: {str(last_error)[:100]}")
                        break

                    # Don't retry deterministic size/capacity errors
                    if (
                        "exceeds maximum allowed size" in str(last_error)
                        or "exceeds maximum" in str(last_error).lower()
                    ):
                        logger.info(
                            f"Not retrying {func_name}: deterministic size limit error: {str(last_error)[:100]}"
                        )
                        break

                    # Don't retry HTTP 4xx client errors - they are permanent failures
                    error_str = str(last_error)
                    if any(
                        pattern in error_str
                        for pattern in [
                            "404 Not Found",
                            "401 Unauthorized",
                            "403 Forbidden",
                            "400 Bad Request",
                            "422 Unprocessable",
                            "Client error '4",
                        ]
                    ):
                        logger.info(f"Not retrying {func_name}: permanent HTTP client error: {error_str[:100]}")
                        break

                    if attempt < max_retries:
                        delay = base_delay * (2**attempt)
                        logger.info(f"Will retry {func_name} in {delay:.1f}s")
                        await asyncio.sleep(delay)
                        continue
                else:
                    logger.info(f"Function {func_name} completed successfully in {duration_ms}ms")

                    # Trace success
                    self._trace_tool_execution(func_name, func_args, result, "success", duration_ms, should_trace)

                    if self.runtime_context is not None:
                        from src.services.agents.agent_trace_service import fire_tool_call

                        self.runtime_context.event_sequence += 1
                        fire_tool_call(
                            tenant_id=self.runtime_context.tenant_id,
                            agent_id=self.runtime_context.agent_id,
                            conversation_id=self.runtime_context.conversation_id,
                            tool_name=func_name,
                            success=True,
                            duration_ms=duration_ms,
                            retry_count=attempt,
                            args=func_args,
                            result=result,
                            error_message=None,
                            sequence=self.runtime_context.event_sequence,
                        )

                    return ToolExecutionResult(
                        name=func_name,
                        result=result,
                        success=True,
                        duration_ms=duration_ms,
                        retry_count=attempt,
                    )

            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                logger.warning(f"Function {func_name} failed: {e}")
                last_error = str(e)
                last_result = {"error": str(e)}

                if attempt < max_retries:
                    delay = base_delay * (2**attempt)
                    logger.info(f"Will retry {func_name} in {delay:.1f}s after error")
                    await asyncio.sleep(delay)
                    continue

        # All retries exhausted
        duration_ms = int((time.time() - start_time) * 1000) if start_time else 0
        self._trace_tool_execution(
            func_name, func_args, last_result, "error", duration_ms, should_trace, error=last_error
        )

        if self.runtime_context is not None:
            from src.services.agents.agent_trace_service import fire_tool_call

            self.runtime_context.event_sequence += 1
            fire_tool_call(
                tenant_id=self.runtime_context.tenant_id,
                agent_id=self.runtime_context.agent_id,
                conversation_id=self.runtime_context.conversation_id,
                tool_name=func_name,
                success=False,
                duration_ms=duration_ms,
                retry_count=max_retries,
                args=func_args,
                result=last_result,
                error_message=last_error,
                sequence=self.runtime_context.event_sequence,
            )

        return ToolExecutionResult(
            name=func_name,
            result=last_result or {"error": "Unknown error"},
            success=False,
            duration_ms=duration_ms,
            retry_count=max_retries,
            error=last_error,
        )

    def _trace_tool_execution(
        self,
        func_name: str,
        func_args: dict[str, Any],
        result: Any,
        status: str,
        duration_ms: int,
        should_trace: bool,
        error: str | None = None,
    ) -> None:
        """Create a Langfuse span for a tool execution."""
        if not (should_trace and self.trace_id):
            return

        try:
            metadata = {
                "operation": "tool_execution",
                "tool_type": "function_call",
                "completed": True,
                "latency_ms": duration_ms,
            }
            if error:
                metadata["error"] = error
                metadata["error_type"] = "tool_error"

            self.langfuse_service.create_span(
                name=f"tool_{func_name}",
                input_data={"tool_name": func_name, "arguments": func_args},
                output_data={"result": result, "status": status},
                trace_id=self.trace_id,
                metadata=metadata,
            )
        except Exception as e:
            logger.warning(f"Failed to create tool span: {e}")

    async def _execute_functions(self, function_calls: list[dict[str, Any]]) -> list[ToolExecutionResult]:
        """
        Execute function calls and return results as an ordered list matching function_calls.

        Returns a list in the same order as the input function_calls so that callers can
        zip results with calls by index. This avoids the dict-keyed-by-name bug where
        multiple parallel calls to the same tool (e.g. internal_web_fetch with different
        URLs) would overwrite each other in a name-keyed dict.
        """
        # Check if tool tracing is enabled
        should_trace = (
            self.observability_config
            and self.observability_config.get("trace_tools", True)
            and self.langfuse_service.should_trace(self.observability_config)
        )

        use_parallel = self.agentic_config.parallel_tools and len(function_calls) > 1

        if use_parallel:
            # Execute all tools in parallel
            logger.info(f"Executing {len(function_calls)} tools in parallel")
            tasks = [
                self._execute_single_tool_with_retry(fc["name"], fc["arguments"], should_trace) for fc in function_calls
            ]
            raw_results = await asyncio.gather(*tasks, return_exceptions=True)

            results: list[ToolExecutionResult] = []
            for i, exec_result in enumerate(raw_results):
                if isinstance(exec_result, Exception):
                    func_name = function_calls[i]["name"]
                    logger.warning(f"Parallel execution failed for {func_name}: {exec_result}")
                    results.append(
                        ToolExecutionResult(
                            name=func_name,
                            result={"error": str(exec_result)},
                            success=False,
                            error=str(exec_result),
                        )
                    )
                else:
                    results.append(exec_result)

        else:
            # Sequential execution (single tool or parallel disabled)
            results = []
            for func_call in function_calls:
                exec_result = await self._execute_single_tool_with_retry(
                    func_call["name"], func_call["arguments"], should_trace
                )
                results.append(exec_result)

        return results

    def _convert_history_to_google_format(self, history: list[dict[str, Any]]) -> list:
        """Convert conversation history to Google format."""
        # Simplified - just use the last user message for now
        last_user_msg = next((msg for msg in reversed(history) if msg["role"] == "user"), None)
        return last_user_msg["content"] if last_user_msg else ""

    def _convert_history_to_openai_format(self, history: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert conversation history to OpenAI format."""
        messages = []
        for msg in history:
            if msg["role"] == "system":
                # System message (contains instructions/context)
                messages.append({"role": "system", "content": msg["content"]})
            elif msg["role"] == "user":
                messages.append({"role": "user", "content": msg["content"]})
            elif msg["role"] == "assistant":
                # Check if this is a function call message
                if "tool_calls" in msg:
                    # When assistant makes tool calls, content must be None or empty string
                    messages.append({"role": "assistant", "content": None, "tool_calls": msg["tool_calls"]})
                elif "function_calls" in msg:
                    # Legacy format - skip this message as it's handled differently
                    continue
                else:
                    # Regular assistant message with text content
                    content = msg.get("content", "")
                    # Ensure content is a string, not an object
                    if isinstance(content, dict):
                        content = json.dumps(content)
                    messages.append({"role": "assistant", "content": content})
            elif msg["role"] == "tool":
                # Tool response message
                messages.append({"role": "tool", "tool_call_id": msg["tool_call_id"], "content": msg["content"]})
            elif msg["role"] == "function":
                # Legacy function response - skip for now
                continue
        return messages

    def _filter_tool_messages_for_summary(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Filter out tool-related messages from conversation history.

        Used when making a final LLM call without tools (e.g., after max iterations).
        Anthropic requires the tools= parameter if tool messages exist in history,
        so we strip them out and condense tool call rounds into brief summaries.
        """
        filtered = []
        i = 0
        while i < len(messages):
            msg = messages[i]

            if msg.get("role") == "tool":
                # Skip tool result messages
                i += 1
                continue

            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                # Replace tool call assistant message with a text summary
                tool_names = [tc["function"]["name"] for tc in msg["tool_calls"] if "function" in tc]
                summary = f"[Used tools: {', '.join(tool_names)}]"

                # Collect the tool results that follow
                results_summary = []
                j = i + 1
                while j < len(messages) and messages[j].get("role") == "tool":
                    content = messages[j].get("content", "")
                    # Truncate long results
                    if len(content) > 200:
                        content = content[:200] + "..."
                    results_summary.append(content)
                    j += 1

                if results_summary:
                    summary += f" Results: {'; '.join(results_summary)}"

                filtered.append({"role": "assistant", "content": summary})
                i = j  # Skip past the tool result messages
                continue

            filtered.append(msg)
            i += 1

        return filtered

    def _convert_history_to_anthropic_format(self, history: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert conversation history to Anthropic format."""
        messages = []
        i = 0
        while i < len(history):
            msg = history[i]
            role = msg.get("role")

            if role == "system":
                # System messages are passed top-level in Anthropic, skip here
                i += 1
                continue

            elif role == "assistant":
                if "tool_calls" in msg and msg["tool_calls"]:
                    # Convert OpenAI-style tool_calls to Anthropic tool_use content blocks
                    content_blocks = []
                    for tc in msg["tool_calls"]:
                        fn = tc.get("function", {})
                        try:
                            input_args = json.loads(fn.get("arguments", "{}"))
                        except (json.JSONDecodeError, TypeError):
                            input_args = {}
                        content_blocks.append(
                            {
                                "type": "tool_use",
                                "id": tc["id"],
                                "name": fn.get("name", ""),
                                "input": input_args,
                            }
                        )
                    messages.append({"role": "assistant", "content": content_blocks})
                else:
                    content = msg.get("content") or ""
                    messages.append({"role": "assistant", "content": content})
                i += 1

            elif role == "tool":
                # Collect consecutive tool results into a single user message
                tool_result_blocks = []
                while i < len(history) and history[i].get("role") == "tool":
                    t = history[i]
                    tool_result_blocks.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": t.get("tool_call_id", ""),
                            "content": t.get("content", ""),
                        }
                    )
                    i += 1
                messages.append({"role": "user", "content": tool_result_blocks})

            elif role == "user":
                content = msg.get("content", "")
                messages.append({"role": "user", "content": content})
                i += 1

            else:
                i += 1

        return messages
