"""
Agent configuration management.

Provides configuration classes for Google Agent SDK integration.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


@dataclass
class AgenticConfig:
    """
    Configuration for agentic loop behavior.

    Used by FunctionCallingHandler to control tool execution.

    Attributes:
        max_iterations: Maximum function calling iterations (default: 150)
        tool_choice: Tool choice strategy - "auto", "required", "none", or specific tool name
        parallel_tools: Whether to execute independent tools in parallel
        tool_retry_attempts: Number of retry attempts for failed tools
        tool_retry_delay: Initial delay in seconds for exponential backoff
        thinking_enabled: Whether to log reasoning traces
    """

    max_iterations: int = 150
    tool_choice: str = "auto"
    parallel_tools: bool = True
    tool_retry_attempts: int = 2
    tool_retry_delay: float = 1.0
    thinking_enabled: bool = False


class AgentType(StrEnum):
    """Types of agents supported."""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    LOOP = "loop"
    LLM_AGENT = "llm_agent"
    MULTI_AGENT = "multi_agent"
    CUSTOM = "custom"
    CLAUDE_CODE = "claude_code"  # Claude Agent SDK powered agent


class AgentStatus(StrEnum):
    """Agent execution status."""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class ToolConfig(BaseModel):
    """Configuration for agent tools."""

    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    function: str | None = Field(None, description="Function reference")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Tool parameters")
    enabled: bool = Field(default=True, description="Whether tool is enabled")


class ModelConfig(BaseModel):
    """Configuration for LLM models."""

    provider: str = Field(default="gemini", description="Model provider (gemini, openai, etc.)")
    model_name: str = Field(default="gemini-2.0-flash-exp", description="Model name")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Model temperature")
    max_tokens: int | None = Field(None, description="Maximum tokens to generate")
    top_p: float | None = Field(None, ge=0.0, le=1.0, description="Top-p sampling")
    api_key: str | None = Field(None, description="API key for the model provider")
    api_base: str | None = Field(None, description="Base URL for API (used by LiteLLM)")
    additional_params: dict[str, Any] = Field(default_factory=dict, description="Additional model parameters")


class AgentConfig(BaseModel):
    """Configuration for an agent."""

    model_config = {"use_enum_values": True}

    name: str = Field(..., description="Agent name")
    description: str = Field(..., description="Agent description")
    avatar: str | None = Field(None, description="Agent avatar URL")
    agent_type: AgentType = Field(default=AgentType.LLM_AGENT, description="Type of agent")
    llm_config: ModelConfig = Field(default_factory=ModelConfig, description="Model configuration")
    tools: list[ToolConfig] = Field(default_factory=list, description="Available tools")
    system_prompt: str | None = Field(None, description="System prompt for the agent")
    suggestion_prompts: list[dict[str, Any]] = Field(
        default_factory=list, description="Suggestion prompts for chat interface"
    )
    max_iterations: int = Field(default=150, ge=1, description="Maximum iterations")
    timeout: int = Field(default=300, ge=1, description="Timeout in seconds")
    memory_enabled: bool = Field(default=True, description="Enable conversation memory")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class WorkflowConfig(BaseModel):
    """Configuration for multi-agent workflows."""

    name: str = Field(..., description="Workflow name")
    description: str = Field(..., description="Workflow description")
    agents: list[str] = Field(..., description="List of agent names in the workflow")
    execution_mode: str = Field(default="sequential", description="Execution mode (sequential, parallel, conditional)")
    routing_logic: dict[str, Any] | None = Field(None, description="Routing logic for conditional workflows")
    max_retries: int = Field(default=3, ge=0, description="Maximum retries on failure")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class DeploymentConfig(BaseModel):
    """Configuration for agent deployment."""

    environment: str = Field(default="development", description="Deployment environment")
    scaling: dict[str, Any] = Field(
        default_factory=lambda: {"min_instances": 1, "max_instances": 10},
        description="Scaling configuration",
    )
    monitoring: dict[str, Any] = Field(
        default_factory=lambda: {"enabled": True, "metrics": ["latency", "errors", "throughput"]},
        description="Monitoring configuration",
    )
    logging: dict[str, Any] = Field(
        default_factory=lambda: {"level": "INFO", "format": "json"},
        description="Logging configuration",
    )
