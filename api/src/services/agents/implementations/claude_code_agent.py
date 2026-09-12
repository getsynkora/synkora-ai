"""
Claude Code Agent implementation using Claude Agent SDK.

Provides powerful code-focused agentic capabilities using Claude's native
agent loop with built-in tools for file operations, bash commands, and code search.
"""

import logging
import os
from collections.abc import AsyncGenerator
from typing import Any

from src.services.agents.base_agent import BaseAgent
from src.services.agents.config import AgentConfig

logger = logging.getLogger(__name__)


class ClaudeCodeAgent(BaseAgent):
    """
    Agent powered by Claude Agent SDK for code-focused tasks.

    This agent leverages Claude's native agentic capabilities for:
    - Code review and bug fixing
    - Codebase analysis and documentation
    - DevOps automation with bash commands
    - File manipulation and code generation

    Note: This agent only works with Claude models (direct API, Bedrock, or Vertex AI).
    For multi-provider support, use the standard LLMAgent with FunctionCallingHandler.
    """

    def __init__(self, config: AgentConfig, observability_config: dict[str, Any] | None = None):
        """
        Initialize the Claude Code Agent.

        Args:
            config: Agent configuration
            observability_config: Optional observability configuration
        """
        super().__init__(config, observability_config)
        self._sdk_initialized = False
        self._session_id = None
        self._api_key: str | None = None
        self._api_base: str | None = None

    def initialize_client(self, api_key: str | None = None) -> None:
        """
        Override base initialize_client to store API key and base URL for Claude Agent SDK.

        The actual SDK initialization happens lazily when execute_stream is called.
        This method stores the API key/base URL and sets a marker for the agent loader.

        Args:
            api_key: Anthropic API key
        """
        key = api_key or getattr(self.config.llm_config, "api_key", None)
        base_url = getattr(self.config.llm_config, "api_base", None)

        if key:
            self._api_key = key
            self._api_base = base_url
            # Set a marker so agent_loader_service knows this agent is "initialized"
            self.llm_client = {"type": "claude_agent_sdk", "initialized": True}  # type: ignore
            self._sdk_initialized = True
            logger.info(
                f"Claude Code Agent '{self.config.name}' initialized{' with custom base URL' if base_url else ''}"
            )
        else:
            logger.warning(f"No API key provided for Claude Code Agent: {self.config.name}")

    def _get_api_key(self) -> str:
        """Get the API key, raising an error if not available."""
        key = self._api_key or getattr(self.config.llm_config, "api_key", None)
        if not key:
            raise ValueError("Anthropic API key is required for Claude Code Agent")
        return key

    def _get_base_url(self) -> str | None:
        """Get the base URL for LiteLLM/custom endpoints, if configured."""
        return self._api_base or getattr(self.config.llm_config, "api_base", None)

    def _get_model(self) -> str:
        """Get the model name from config."""
        model = getattr(self.config.llm_config, "model_name", None)
        if model:
            # Strip provider prefix if present (e.g., "anthropic/claude-sonnet-4-6" -> "claude-sonnet-4-6")
            if "/" in model:
                model = model.split("/")[-1]
            return model
        return "claude-sonnet-4-6"  # Default

    def _build_cli_env(self) -> dict[str, str]:
        """
        Build environment variables for the CLI subprocess.

        Includes:
        - Runtime discovery environment only; unrelated API secrets are not inherited
        - ANTHROPIC_API_KEY for authentication
        - ANTHROPIC_BASE_URL for LiteLLM/custom endpoints (if configured)
        """
        cli_env = {k: os.environ[k] for k in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR") if k in os.environ}
        cli_env["ANTHROPIC_API_KEY"] = self._get_api_key()

        base_url = self._get_base_url()
        if base_url:
            cli_env["ANTHROPIC_BASE_URL"] = base_url
            logger.debug(f"Using custom base URL: {base_url}")

        return cli_env

    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """
        Execute the Claude Code Agent (non-streaming).

        Args:
            input_data: Dictionary containing:
                - prompt: The user prompt/task
                - workspace_path: Optional working directory for file operations
                - allowed_tools: Optional list of allowed tools
                - permission_mode: Permission mode (default: "acceptEdits")
                - max_turns: Maximum agentic turns (default: 50)

        Returns:
            Dictionary containing:
                - response: The final response text
                - tool_calls: List of tools that were called
                - usage: Token usage information
                - cost_usd: Total cost in USD
        """
        prompt = input_data.get("prompt")
        if not prompt:
            raise ValueError("'prompt' is required in input_data")

        workspace_path = input_data.get("workspace_path")
        allowed_tools = input_data.get(
            "allowed_tools",
            [
                "Read",
                "Write",
                "Edit",
                "Glob",
                "Grep",
                "NotebookEdit",
                "Bash",
                "WebFetch",
                "WebSearch",
                "Task",
                "TaskOutput",
                "TaskStop",
                "TodoWrite",
            ],
        )
        permission_mode = input_data.get("permission_mode", "acceptEdits")
        max_turns = input_data.get("max_turns", 50)
        system_prompt = input_data.get("system_prompt", self.config.system_prompt)

        try:
            from claude_agent_sdk import ClaudeAgentOptions, query

            options = ClaudeAgentOptions(
                allowed_tools=allowed_tools,
                permission_mode=permission_mode,
                system_prompt=system_prompt,
                cwd=workspace_path,
                max_turns=max_turns,
                model=self._get_model(),
                env=self._build_cli_env(),
            )

            # Execute and collect results
            tool_calls = []
            response_parts = []
            total_cost = 0.0
            usage_data = {"input_tokens": 0, "output_tokens": 0}

            async for message in query(prompt=prompt, options=options):
                if hasattr(message, "content"):
                    for block in message.content:
                        if hasattr(block, "text"):
                            response_parts.append(block.text)
                        elif hasattr(block, "type") and block.type == "tool_use":
                            tool_calls.append({"name": block.name, "input": block.input})

                if hasattr(message, "usage") and message.usage:
                    usage_data["input_tokens"] = message.usage.get("input_tokens", 0)
                    usage_data["output_tokens"] = message.usage.get("output_tokens", 0)

                if hasattr(message, "total_cost_usd") and message.total_cost_usd:
                    total_cost = message.total_cost_usd

            response_text = "\n".join(response_parts)

            logger.info(
                f"Claude Code Agent completed: {len(tool_calls)} tools called, "
                f"{usage_data['input_tokens'] + usage_data['output_tokens']} tokens"
            )

            return {
                "response": response_text,
                "tool_calls": tool_calls,
                "usage": usage_data,
                "cost_usd": total_cost,
                "model": self._get_model(),
                "provider": "anthropic",
            }

        except ImportError:
            logger.error("claude-agent-sdk not installed")
            raise ImportError(
                "claude-agent-sdk is required for ClaudeCodeAgent. Install with: pip install claude-agent-sdk"
            )
        except Exception as e:
            logger.warning(f"Claude Code Agent execution failed: {e}", exc_info=True)
            raise

    async def execute_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        workspace_path: str | None = None,
        allowed_tools: list[str] | None = None,
        mcp_servers: dict[str, Any] | None = None,
        max_turns: int = 50,
        model: str | None = None,
        **kwargs,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Execute with Claude Agent SDK and yield streaming events.

        Args:
            prompt: The user prompt/task
            system_prompt: Optional system prompt
            workspace_path: Optional working directory
            allowed_tools: List of allowed tools
            mcp_servers: MCP server configurations as dict[str, McpServerConfig]
            max_turns: Maximum agentic turns
            model: Model to use (defaults to config model)

        Yields:
            Dictionary events in Synkora SSE format:
            - {"type": "start", "agent_name": "..."}
            - {"type": "first_token", "time_to_first_token": 0.5}
            - {"type": "text", "content": "..."}
            - {"type": "function_call", "name": "...", "arguments": {...}}
            - {"type": "function_result", "name": "...", "result": {...}}
            - {"type": "done", "metadata": {...}}
        """
        import time

        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            ResultMessage,
            SystemMessage,
            TextBlock,
            ThinkingBlock,
            ToolResultBlock,
            ToolUseBlock,
            UserMessage,
            query,
        )
        from claude_agent_sdk.types import StreamEvent

        start_time = time.time()
        first_token_time = None
        model_name = model or self._get_model()

        # Stderr callback to capture CLI output for debugging
        def stderr_callback(output: str) -> None:
            output_stripped = output.strip()
            if output_stripped:
                logger.info(f"[Claude CLI] {output_stripped}")

        try:
            # Build options
            final_system_prompt = system_prompt or self.config.system_prompt

            options_kwargs: dict[str, Any] = {
                "permission_mode": "acceptEdits",
                "max_turns": max_turns,
                "env": self._build_cli_env(),
                "stderr": stderr_callback,
                "model": model_name,
                "include_partial_messages": True,  # Enable streaming of partial messages
            }

            if final_system_prompt:
                options_kwargs["system_prompt"] = final_system_prompt

            if workspace_path:
                options_kwargs["cwd"] = workspace_path

            if allowed_tools:
                options_kwargs["allowed_tools"] = allowed_tools

            # mcp_servers should be dict[str, McpServerConfig]
            if mcp_servers:
                options_kwargs["mcp_servers"] = mcp_servers

            options = ClaudeAgentOptions(**options_kwargs)

            logger.info(f"Starting Claude Code Agent stream: model={model_name}, max_turns={max_turns}")

            # Yield start event
            yield {"type": "start", "agent_name": self.config.name, "timestamp": start_time}

            # Track metrics
            total_input_tokens = 0
            total_output_tokens = 0
            total_cost = 0.0
            tool_calls = []
            last_text_content = ""
            message_count = 0
            is_thinking = False  # Track thinking state to avoid flooding status events
            tool_id_to_name: dict[str, str] = {}  # Map tool_use_id to tool name for display

            # Stream from Claude Agent SDK
            async for message in query(prompt=prompt, options=options):
                msg_type = type(message).__name__
                message_count += 1
                # Use DEBUG for high-frequency StreamEvents, INFO for others
                if msg_type == "StreamEvent":
                    logger.debug(f"[SDK MSG #{message_count}] Type: {msg_type}")
                else:
                    logger.info(f"[SDK MSG #{message_count}] Type: {msg_type}")

                # Handle SystemMessage (init)
                if isinstance(message, SystemMessage):
                    if message.subtype == "init":
                        logger.info(
                            f"Claude CLI initialized: session={message.data.get('session_id')}, "
                            f"model={message.data.get('model')}"
                        )
                    else:
                        logger.debug(f"SystemMessage subtype: {message.subtype}")
                    continue

                # Handle AssistantMessage (Claude's responses)
                if isinstance(message, AssistantMessage):
                    block_count = len(message.content) if message.content else 0
                    logger.info(f"[SDK MSG #{message_count}] AssistantMessage with {block_count} blocks")

                    # First token timing
                    if first_token_time is None and message.content:
                        first_token_time = time.time()
                        logger.info(f"First token received at {first_token_time - start_time:.2f}s")
                        yield {
                            "type": "first_token",
                            "time_to_first_token": first_token_time - start_time,
                        }

                    # Process content blocks using isinstance checks
                    for idx, block in enumerate(message.content):
                        block_class = type(block).__name__
                        logger.debug(f"[SDK MSG #{message_count}] Block {idx}: {block_class}")

                        # Text content - stream it
                        if isinstance(block, TextBlock):
                            text = block.text
                            logger.debug(f"[SDK MSG #{message_count}] TextBlock: {len(text)} chars")
                            if text and text != last_text_content:
                                # Check if this text was already streamed via StreamEvent deltas
                                # (last_text_content accumulates all streamed text, so if it ends
                                # with this text, we already sent it)
                                if last_text_content.endswith(text):
                                    logger.debug(
                                        f"[SDK MSG #{message_count}] Skipping duplicate TextBlock "
                                        f"(already streamed via StreamEvent)"
                                    )
                                elif text.startswith(last_text_content):
                                    # Partial overlap - yield only the new part
                                    new_text = text[len(last_text_content) :]
                                    if new_text:
                                        logger.debug(
                                            f"[SDK MSG #{message_count}] Yielding new text: {len(new_text)} chars"
                                        )
                                        yield {"type": "text", "content": new_text}
                                        last_text_content = text
                                else:
                                    # Completely new text (no StreamEvent streaming happened)
                                    logger.debug(f"[SDK MSG #{message_count}] Yielding text: {len(text)} chars")
                                    yield {"type": "text", "content": text}
                                    last_text_content = text

                        # Tool use
                        elif isinstance(block, ToolUseBlock):
                            tool_name = block.name
                            tool_input = block.input
                            tool_use_id = block.id if hasattr(block, "id") else None
                            tool_calls.append({"name": tool_name, "input": tool_input})
                            # Store mapping for later result events
                            if tool_use_id:
                                tool_id_to_name[tool_use_id] = tool_name
                            logger.info(f"[SDK MSG #{message_count}] Tool call: {tool_name} (id={tool_use_id})")
                            yield {
                                "type": "function_call",
                                "name": tool_name,
                                "arguments": tool_input,
                            }

                        # Tool result
                        elif isinstance(block, ToolResultBlock):
                            tool_use_id = block.tool_use_id
                            result_content = block.content
                            # Get actual tool name from our mapping
                            tool_name = tool_id_to_name.get(tool_use_id, tool_use_id)
                            logger.info(f"[SDK MSG #{message_count}] Tool result for: {tool_name}")
                            yield {
                                "type": "function_result",
                                "name": tool_name,
                                "result": result_content,
                            }

                        # Thinking block (extended thinking)
                        elif isinstance(block, ThinkingBlock):
                            thinking_text = block.thinking
                            if thinking_text:
                                logger.debug(f"[SDK MSG #{message_count}] Thinking: {len(thinking_text)} chars")
                                # Only emit thinking_start once, not for every chunk
                                if not is_thinking:
                                    is_thinking = True
                                    yield {"type": "thinking_start"}
                                # Don't stream every thinking chunk to frontend - too noisy

                        else:
                            logger.warning(f"[SDK MSG #{message_count}] Unknown block type: {block_class}")

                    # Check for errors in the message
                    if message.error:
                        logger.warning(f"Assistant message error: {message.error}")

                # Handle ResultMessage (final result)
                elif isinstance(message, ResultMessage):
                    logger.info(
                        f"[SDK MSG #{message_count}] ResultMessage: turns={message.num_turns}, "
                        f"duration={message.duration_ms}ms, cost=${message.total_cost_usd or 0:.4f}"
                    )

                    # Extract usage from result
                    if message.usage:
                        total_input_tokens = message.usage.get("input_tokens", 0)
                        total_output_tokens = message.usage.get("output_tokens", 0)

                    if message.total_cost_usd:
                        total_cost = message.total_cost_usd

                    # If there's a result text and we haven't yielded it yet
                    if message.result and message.result != last_text_content:
                        # Check if already streamed via StreamEvent
                        if last_text_content.endswith(message.result):
                            logger.debug(
                                f"[SDK MSG #{message_count}] Skipping duplicate result text "
                                f"(already streamed via StreamEvent)"
                            )
                        elif message.result.startswith(last_text_content):
                            new_text = message.result[len(last_text_content) :]
                            if new_text and not message.is_error:
                                logger.debug(f"[SDK MSG #{message_count}] Final result text: {len(new_text)} chars")
                                yield {"type": "text", "content": new_text}
                        elif not message.is_error:
                            logger.debug(f"[SDK MSG #{message_count}] Final result text: {len(message.result)} chars")
                            yield {"type": "text", "content": message.result}

                # Handle StreamEvent (incremental streaming content from Anthropic API)
                elif isinstance(message, StreamEvent):
                    # StreamEvent.event contains the raw Anthropic API stream event
                    event = message.event
                    event_type = event.get("type", "")

                    # Log event type for debugging
                    delta_type = ""
                    if event_type == "content_block_delta":
                        delta = event.get("delta", {})
                        delta_type = delta.get("type", "unknown")
                    logger.debug(f"[SDK MSG #{message_count}] StreamEvent: {event_type}/{delta_type}")

                    # content_block_delta contains incremental text
                    if event_type == "content_block_delta":
                        delta = event.get("delta", {})
                        delta_type = delta.get("type", "")

                        if delta_type == "text_delta":
                            text = delta.get("text", "")
                            if text:
                                # Text content means thinking is done
                                if is_thinking:
                                    is_thinking = False
                                    yield {"type": "thinking_end"}
                                # First token timing
                                if first_token_time is None:
                                    first_token_time = time.time()
                                    yield {
                                        "type": "first_token",
                                        "time_to_first_token": first_token_time - start_time,
                                    }
                                # Yield the text delta
                                yield {"type": "text", "content": text}
                                last_text_content += text

                        elif delta_type == "thinking_delta":
                            # Extended thinking - only emit start event once
                            if not is_thinking:
                                is_thinking = True
                                yield {"type": "thinking_start"}

                        elif delta_type == "input_json_delta":
                            # Tool input being streamed (for debugging/display)
                            partial_json = delta.get("partial_json", "")
                            if partial_json:
                                logger.debug(f"Tool input delta: {partial_json[:100]}...")

                    # content_block_start signals new content block
                    elif event_type == "content_block_start":
                        content_block = event.get("content_block", {})
                        block_type = content_block.get("type", "")
                        if block_type == "tool_use":
                            # Tool use starting - capture the mapping early
                            tool_name = content_block.get("name", "unknown")
                            tool_id = content_block.get("id")
                            if tool_id and tool_name:
                                tool_id_to_name[tool_id] = tool_name
                            logger.debug(f"Tool use starting: {tool_name} (id={tool_id})")

                    # message_delta may contain stop_reason
                    elif event_type == "message_delta":
                        delta = event.get("delta", {})
                        stop_reason = delta.get("stop_reason")
                        if stop_reason:
                            logger.debug(f"Message stop reason: {stop_reason}")

                # Handle UserMessage (tool results from SDK)
                elif isinstance(message, UserMessage):
                    # UserMessage contains tool results - extract and yield as function_result
                    if hasattr(message, "content") and message.content:
                        for block in message.content:
                            if isinstance(block, ToolResultBlock):
                                tool_use_id = block.tool_use_id
                                # Get actual tool name from our mapping
                                tool_name = tool_id_to_name.get(tool_use_id, tool_use_id)
                                logger.debug(f"[SDK MSG #{message_count}] Tool result: {tool_name}")
                                # Truncate large results for the event
                                result_preview = str(block.content)[:500] if block.content else ""
                                yield {
                                    "type": "function_result",
                                    "name": tool_name,
                                    "result": result_preview,
                                    "is_error": block.is_error if hasattr(block, "is_error") else False,
                                }

                else:
                    logger.warning(f"[SDK MSG #{message_count}] Unhandled message type: {msg_type}")

            # Yield done event with metadata
            end_time = time.time()
            logger.info(
                f"Stream completed: {message_count} messages, {len(tool_calls)} tools, "
                f"{end_time - start_time:.2f}s total"
            )
            yield {
                "type": "done",
                "metadata": {
                    "total_time": end_time - start_time,
                    "time_to_first_token": (first_token_time - start_time) if first_token_time else None,
                    "input_tokens": total_input_tokens,
                    "output_tokens": total_output_tokens,
                    "total_tokens": total_input_tokens + total_output_tokens,
                    "cost_usd": total_cost,
                    "tool_calls_count": len(tool_calls),
                    "model": model_name,
                },
            }

        except ImportError:
            logger.error("claude-agent-sdk not installed")
            yield {
                "type": "error",
                "error": "claude-agent-sdk is not installed. Install with: pip install claude-agent-sdk",
            }
        except Exception as e:
            logger.warning(f"Claude Code Agent streaming failed: {e}", exc_info=True)
            yield {"type": "error", "error": str(e)}

    async def resume_session(
        self,
        session_id: str,
        prompt: str,
        **kwargs,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Resume an existing Claude Agent SDK session.

        Args:
            session_id: The session ID to resume
            prompt: Follow-up prompt

        Yields:
            Streaming events in Synkora SSE format
        """
        try:
            # Use ClaudeAgentOptions.resume to continue the session
            async for event in self.execute_stream(
                prompt=prompt,
                **kwargs,
            ):
                yield event

        except Exception as e:
            logger.error(f"Failed to resume Claude Agent SDK session: {e}")
            yield {"type": "error", "error": str(e)}


def create_claude_code_agent(
    api_key: str,
    name: str = "claude_code_agent",
    system_prompt: str | None = None,
) -> ClaudeCodeAgent:
    """
    Create a pre-configured Claude Code Agent.

    Args:
        api_key: Anthropic API key
        name: Agent name
        system_prompt: Optional system prompt

    Returns:
        Configured Claude Code Agent
    """
    from src.services.agents.config import ModelConfig

    config = AgentConfig(
        name=name,
        description="Claude Code Agent for code-focused tasks using Claude Agent SDK",
        system_prompt=system_prompt
        or (
            "You are an expert software engineer. Help the user with code analysis, "
            "bug fixing, documentation, and development tasks. Use the available tools "
            "to read files, search code, and make changes when needed."
        ),
        llm_config=ModelConfig(
            provider="anthropic",
            model_name="claude-sonnet-4-6",
            api_key=api_key,
        ),
    )

    agent = ClaudeCodeAgent(config)
    return agent
