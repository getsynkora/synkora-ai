"""
Multi-provider LLM client for Google ADK agents.


Supports Google Gemini, OpenAI, Anthropic Claude, and LiteLLM.
"""

import asyncio
import logging
import os
import random
import time
from collections.abc import AsyncGenerator
from contextvars import ContextVar
from typing import Any

from src.services.agents.config import ModelConfig
from src.services.observability.langfuse_service import LangfuseService
from src.services.performance.circuit_breaker import CircuitBreakerOpen, get_circuit_breaker
from src.services.performance.metrics import get_metrics_collector

logger = logging.getLogger(__name__)

# Per-coroutine storage for LLM usage data.
# Using ContextVar instead of instance state avoids race conditions when the
# same MultiProviderLLMClient is shared across concurrent requests in a pool.
_llm_usage_ctx: ContextVar[dict | None] = ContextVar("llm_usage", default=None)

# Anthropic models that support prompt caching
_ANTHROPIC_CACHEABLE_PREFIXES = ("claude-3", "claude-sonnet", "claude-haiku", "claude-opus")

# Default streaming timeout in seconds (configurable via environment)
# This prevents hanging connections when LLM providers don't respond
DEFAULT_STREAMING_TIMEOUT = int(os.getenv("LLM_STREAMING_TIMEOUT", "300"))  # 5 minutes default
# Timeout between chunks - if no chunk received in this time, cancel the stream
CHUNK_TIMEOUT = int(os.getenv("LLM_CHUNK_TIMEOUT", "60"))  # 60 seconds between chunks


class LLMStreamingTimeoutError(Exception):
    """Exception raised when LLM streaming times out."""

    def __init__(self, message: str, timeout: int, provider: str):
        self.timeout = timeout
        self.provider = provider
        super().__init__(message)


class LLMProviderError(Exception):
    """Raised when the LLM provider fails and a fallback should be attempted.

    Callers that maintain a fallback chain (e.g. ChatStreamService) should
    catch this exception, log a warning, then retry with the next configured
    LLM config before surfacing any error to the user.
    """

    def __init__(self, message: str, provider: str, original_error: Exception):
        self.provider = provider
        self.original_error = original_error
        super().__init__(message)


# Error patterns that indicate a provider is unhealthy (rate-limited, down, auth failure).
# These are the same categories tracked by is_expected_llm_error() in streaming_helpers.py.
_PROVIDER_ERROR_PATTERNS = (
    "RateLimitError",
    "rate limit",
    "ratelimit",
    "too many requests",
    "quota exceeded",
    "ServiceUnavailableError",
    "service unavailable",
    "overloaded",
    "APIStatusError",
    "APIConnectionError",
    "APITimeoutError",
    "AuthenticationError",
    "invalid api key",
    "invalid_api_key",
    "Unauthorized",
    "502",
    "503",
    "529",
)


def _is_provider_error(exc: Exception) -> bool:
    """Return True when *exc* is a known recoverable provider failure.

    These are errors where retrying against a different LLM config is
    reasonable (rate-limits, server errors, auth mismatches).  They are
    intentionally broad: false positives just mean we try a fallback that
    might also fail; false negatives mean the user sees the raw error.
    """
    exc_str = f"{type(exc).__name__}: {exc}"
    lower = exc_str.lower()
    return any(p.lower() in lower for p in _PROVIDER_ERROR_PATTERNS)


class MultiProviderLLMClient:
    """
    Multi-provider LLM client that abstracts different LLM providers.

    This client can be used by Google ADK agents to interact with various
    LLM providers using a unified interface.

    Supports a "mock" provider for load testing that simulates LLM responses
    without making real API calls. Enable via:
    - Setting provider to "mock" in agent config
    - Or setting LOAD_TEST_MODE=true environment variable to force mock for all agents
    """

    # Mock response templates for load testing
    MOCK_RESPONSES = [
        "I understand your question. Let me help you with that. Based on my analysis, here's what I can tell you about this topic. The key points to consider are the following aspects of your query.",
        "Thank you for reaching out! I'd be happy to assist you with this matter. Here's a comprehensive response that addresses your needs and provides actionable guidance.",
        "Great question! Let me break this down for you step by step. First, we need to understand the context. Then, I'll provide specific recommendations based on best practices.",
        "I appreciate you bringing this to my attention. After careful consideration, here's my detailed response covering the main aspects of your inquiry.",
        "Let me provide you with a thorough answer. The situation you've described has several important factors to consider, and I'll address each one systematically.",
    ]

    def __init__(
        self,
        config: ModelConfig,
        observability_config: dict[str, Any] | None = None,
        streaming_timeout: int | None = None,
        chunk_timeout: int | None = None,
        langfuse_service: "LangfuseService | None" = None,
    ):
        """
        Initialize the multi-provider client.

        Args:
            config: Model configuration with provider details
            observability_config: Optional observability configuration for tracing
            streaming_timeout: Total timeout for streaming in seconds (default: 300s)
            chunk_timeout: Timeout between chunks in seconds (default: 60s)
            langfuse_service: Optional pre-configured LangfuseService (avoids creating duplicate clients)
        """
        self.config = config
        # Normalize provider name to lowercase for consistent comparison
        self.provider = config.provider.lower() if config.provider else ""

        # LOAD TEST MODE: Force mock provider if LOAD_TEST_MODE is enabled
        if os.getenv("LOAD_TEST_MODE", "").lower() in ("true", "1", "yes"):
            logger.info(f"🧪 LOAD_TEST_MODE enabled - overriding provider '{self.provider}' with 'mock'")
            self.provider = "mock"

        self._client = None
        self.observability_config = observability_config or {}
        self.langfuse_service = langfuse_service or LangfuseService.for_agent(self.observability_config)
        self.streaming_timeout = streaming_timeout or DEFAULT_STREAMING_TIMEOUT
        self.chunk_timeout = chunk_timeout or CHUNK_TIMEOUT
        self._initialize_provider()

    def _initialize_provider(self):
        """Initialize the appropriate provider client."""
        # Provider is already normalized to lowercase in __init__
        if self.provider == "mock":
            self._initialize_mock()
        elif self.provider in ["google", "gemini"]:
            self._initialize_google()
        elif self.provider in ["openai", "deepseek", "lm_studio", "vllm"]:
            self._initialize_openai()
        elif self.provider in ["anthropic", "claude"]:
            self._initialize_anthropic()
        elif self.provider == "openrouter":
            self._initialize_openrouter()
        elif self.provider == "minimax":
            self._initialize_minimax()
        elif self.provider == "groq":
            self._initialize_groq()
        elif self.provider == "litellm":
            self._initialize_litellm()
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def _initialize_mock(self):
        """Initialize mock provider for load testing."""
        self._client = None  # No client needed
        logger.info(
            f"🧪 Initialized MOCK LLM provider (model: {self.config.model_name}) - NO REAL API CALLS WILL BE MADE"
        )

    def _initialize_google(self):
        """Initialize Google Gemini client."""
        try:
            from google import genai

            self._client = genai.Client(api_key=self.config.api_key)
            logger.info(f"Initialized Google Gemini client with model: {self.config.model_name}")
        except ImportError:
            raise ImportError("google-genai package not installed. Install with: pip install google-genai")

    def _initialize_openai(self):
        """Initialize an OpenAI-compatible client."""
        try:
            from openai import AsyncOpenAI

            kwargs: dict = {"api_key": self.config.api_key or "not-required"}
            default_base_urls = {
                "deepseek": "https://api.deepseek.com",
            }
            base_url = self.config.api_base or default_base_urls.get(self.provider)
            if base_url:
                kwargs["base_url"] = base_url
            self._client = AsyncOpenAI(**kwargs)
            logger.info(
                f"Initialized OpenAI-compatible client (provider={self.provider}) with model: {self.config.model_name}"
            )
        except ImportError:
            raise ImportError("openai package not installed. Install with: pip install openai")

    def _initialize_anthropic(self):
        """Initialize Anthropic Claude client."""
        try:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=self.config.api_key)
            logger.info(f"Initialized Anthropic client with model: {self.config.model_name}")
        except ImportError:
            raise ImportError("anthropic package not installed. Install with: pip install anthropic")

    def _initialize_openrouter(self):
        """Initialize OpenRouter client (uses OpenAI-compatible API)."""
        try:
            from openai import AsyncOpenAI

            base_url = self.config.api_base or "https://openrouter.ai/api/v1"
            self._client = AsyncOpenAI(
                api_key=self.config.api_key,
                base_url=base_url,
            )
            logger.info(f"Initialized OpenRouter client with model: {self.config.model_name}")
        except ImportError:
            raise ImportError("openai package not installed. Install with: pip install openai")

    def _initialize_minimax(self):
        """Initialize MiniMax client (uses OpenAI-compatible API)."""
        try:
            from openai import AsyncOpenAI

            base_url = self.config.api_base or "https://api.minimax.chat/v1"
            self._client = AsyncOpenAI(
                api_key=self.config.api_key,
                base_url=base_url,
            )
            logger.info(f"Initialized MiniMax client with model: {self.config.model_name}")
        except ImportError:
            raise ImportError("openai package not installed. Install with: pip install openai")

    def _initialize_groq(self):
        """Initialize Groq client (uses OpenAI-compatible API)."""
        try:
            from openai import AsyncOpenAI

            base_url = self.config.api_base or "https://api.groq.com/openai/v1"
            self._client = AsyncOpenAI(
                api_key=self.config.api_key,
                base_url=base_url,
            )
            logger.info(f"Initialized Groq client with model: {self.config.model_name}")
        except ImportError:
            raise ImportError("openai package not installed. Install with: pip install openai")

    def _initialize_litellm(self):
        """Initialize LiteLLM client."""
        try:
            import litellm

            # LiteLLM doesn't need a client object, it's a function-based API.
            # api_base is passed per-call (see completion_params["api_base"]) to avoid
            # mutating the process-wide litellm.api_base which would corrupt concurrent
            # agents using different base URLs.
            self._client = litellm

            logger.info(
                f"Initialized litellm with model: {self.config.model_name}"
                + (f", base URL: {self.config.api_base}" if self.config.api_base else "")
            )
        except ImportError:
            raise ImportError("litellm package not installed. Install with: pip install litellm")

    def _supports_prompt_cache(self) -> bool:
        """Return True if the current model supports Anthropic prompt caching."""
        return any(p in self.config.model_name.lower() for p in _ANTHROPIC_CACHEABLE_PREFIXES)

    def set_cost_context(
        self,
        tenant_id,
        agent_id=None,
        conversation_id=None,
        routing_rules=None,
        optimization_flags=None,
        enable_response_cache: bool = False,
        system_prompt_hash: str = "",
        agent_updated_at=None,
    ) -> None:
        """
        Store per-request metadata for usage tracking.

        Safe to call on a shared pooled client because this sets request-scoped
        metadata on the instance before the request starts; ContextVar captures
        per-coroutine usage data separately during the actual API call.
        """
        self._cost_context = {
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "conversation_id": conversation_id,
            "routing_rules": routing_rules,
            "optimization_flags": optimization_flags or {},
            "enable_response_cache": enable_response_cache,
            "system_prompt_hash": system_prompt_hash,
            "agent_updated_at": agent_updated_at,
        }

    def _read_and_fire_usage(self, response_cache_hit: bool = False) -> None:
        """
        Read per-coroutine usage from ContextVar and schedule a DB write.

        Safe for concurrent use: ContextVar is per-coroutine, not shared.
        Clears the ContextVar after reading to prevent double-firing.
        """
        usage = _llm_usage_ctx.get()
        ctx = getattr(self, "_cost_context", None)
        if not ctx or not ctx.get("tenant_id"):
            return
        if not usage and not response_cache_hit:
            return
        if not usage:
            usage = {"input_tokens": 0, "output_tokens": 0}
        try:
            from src.services.billing.llm_cost_service import fire_persist_llm_usage

            flags = {**ctx.get("optimization_flags", {})}
            flags["response_cache_hit"] = response_cache_hit
            flags["routing_mode"] = getattr(self.config, "routing_mode", "fixed")
            fire_persist_llm_usage(
                tenant_id=ctx["tenant_id"],
                provider=self.provider,
                model_name=self.config.model_name,
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                agent_id=ctx.get("agent_id"),
                conversation_id=ctx.get("conversation_id"),
                cache_read_tokens=usage.get("cache_read_tokens", 0),
                cache_creation_tokens=usage.get("cache_creation_tokens", 0),
                cached_input_tokens=usage.get("cached_input_tokens", 0),
                optimization_flags=flags,
                routing_rules=ctx.get("routing_rules"),
            )
        except Exception:
            pass
        _llm_usage_ctx.set(None)

    async def _with_streaming_timeout(
        self,
        generator: AsyncGenerator[str, None],
        total_timeout: int | None = None,
        chunk_timeout: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Wrap an async generator with timeout protection.

        This method provides two levels of timeout protection:
        1. Total timeout: Maximum time for the entire streaming operation
        2. Chunk timeout: Maximum time to wait between chunks

        Args:
            generator: The async generator to wrap
            total_timeout: Total timeout in seconds (uses instance default if None)
            chunk_timeout: Timeout between chunks in seconds (uses instance default if None)

        Yields:
            Chunks from the underlying generator

        Raises:
            LLMStreamingTimeoutError: If any timeout is exceeded
        """
        total_timeout = total_timeout or self.streaming_timeout
        chunk_timeout = chunk_timeout or self.chunk_timeout

        start_time = time.time()
        last_chunk_time = start_time

        try:
            async for chunk in generator:
                current_time = time.time()

                # Check total timeout
                if current_time - start_time > total_timeout:
                    logger.warning(
                        f"LLM streaming total timeout exceeded: {total_timeout}s for provider {self.provider}"
                    )
                    raise LLMStreamingTimeoutError(
                        f"LLM streaming exceeded total timeout of {total_timeout} seconds",
                        timeout=total_timeout,
                        provider=self.provider,
                    )

                # Reset chunk timer
                last_chunk_time = current_time
                yield chunk

        except TimeoutError:
            elapsed = time.time() - last_chunk_time
            logger.warning(
                f"LLM streaming chunk timeout: no chunk received in {elapsed:.1f}s for provider {self.provider}"
            )
            raise LLMStreamingTimeoutError(
                f"LLM streaming chunk timeout: no response in {chunk_timeout} seconds",
                timeout=chunk_timeout,
                provider=self.provider,
            )
        finally:
            # Fire usage recording after stream completes or fails.
            # ContextVar is set by the provider-specific generator before it returns.
            self._read_and_fire_usage()

    async def _wrap_with_chunk_timeout(
        self,
        generator: AsyncGenerator[str, None],
    ) -> AsyncGenerator[str, None]:
        """
        Wrap generator to timeout if no chunk is received within chunk_timeout.

        This is a simpler version that only checks between chunks, not total time.
        Use _with_streaming_timeout for full timeout protection.
        """

        async def get_next_chunk():
            return await generator.__anext__()

        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(get_next_chunk(), timeout=self.chunk_timeout)
                    yield chunk
                except StopAsyncIteration:
                    break
        except TimeoutError:
            logger.warning(
                f"LLM streaming chunk timeout: no chunk received in {self.chunk_timeout}s for provider {self.provider}"
            )
            raise LLMStreamingTimeoutError(
                f"LLM streaming chunk timeout: no response in {self.chunk_timeout} seconds",
                timeout=self.chunk_timeout,
                provider=self.provider,
            )

    def _prepare_litellm_model_name(self, model_name: str) -> str:
        """
        Prepare model name for LiteLLM by adding provider prefix if needed.

        When api_base is set (proxy mode — e.g. a self-hosted LiteLLM proxy), the proxy
        routes requests by plain model name using its own internal config.  Adding a
        provider prefix (e.g. "google/gemini-2.5-flash") in proxy mode causes the LiteLLM
        Python SDK to switch to the provider's native SDK (Vertex AI, Cohere SDK, etc.)
        which sends the request in a non-OpenAI-compatible format that the proxy cannot
        handle.  Only "openai/" and "anthropic/" prefixes are safe because those providers
        speak OpenAI-compatible or Anthropic-compatible protocols that LiteLLM proxies
        explicitly support.

        Without api_base (direct SDK mode), provider prefixes are required so LiteLLM
        knows which backend SDK to invoke.

        Args:
            model_name: The model name (e.g., 'claude-sonnet-4.5' or 'anthropic/claude-sonnet-4.5')

        Returns:
            Properly formatted model name with provider prefix (direct mode) or plain
            model name (proxy mode).
        """
        # If model already has a provider prefix, return as-is
        if "/" in model_name:
            return model_name

        # Proxy mode: api_base is set (self-hosted LiteLLM proxy or similar).
        # Return the bare model name — do NOT add a provider prefix.
        # The LiteLLM SDK is told to use OpenAI-compatible routing via
        # custom_llm_provider="openai" in the completion call, which sends the
        # request as-is to api_base/v1/chat/completions without touching the
        # model name.  Adding "openai/" here was causing proxies that register
        # models by plain name (e.g. "llama-4-maverick") to reject requests for
        # "openai/llama-4-maverick" with a 400.
        # NOTE: this only runs for provider=litellm.
        if self.config.api_base:
            return model_name

        # Direct SDK mode: add provider prefix so LiteLLM picks the right backend.
        model_lower = model_name.lower()

        # Anthropic/Claude models
        if "claude" in model_lower:
            return f"anthropic/{model_name}"

        # OpenAI models
        elif any(prefix in model_lower for prefix in ["gpt-", "o1-", "o3-", "o4-", "chatgpt", "codex"]):
            return f"openai/{model_name}"

        # Google models
        elif any(prefix in model_lower for prefix in ["gemini", "gemma", "palm"]):
            return f"google/{model_name}"

        # Cohere models
        elif "command" in model_lower or "cohere" in model_lower:
            return f"cohere/{model_name}"

        # Mistral models
        elif "mistral" in model_lower or "mixtral" in model_lower:
            return f"mistral/{model_name}"

        # If we can't detect, return as-is and let LiteLLM handle it
        logger.warning(f"Could not detect provider for model '{model_name}', passing as-is to LiteLLM")
        return model_name

    async def generate_content(
        self,
        prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        trace_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs,
    ) -> str:
        """
        Generate content using the configured provider with optional Langfuse tracing.

        Args:
            prompt: The input prompt
            temperature: Sampling temperature (overrides config)
            max_tokens: Maximum tokens to generate (overrides config)
            trace_id: Optional Langfuse trace ID to attach generation to
            metadata: Optional metadata for the trace
            **kwargs: Additional provider-specific parameters

        Returns:
            Generated text content
        """
        temp = temperature if temperature is not None else self.config.temperature
        max_tok = max_tokens if max_tokens is not None else self.config.max_tokens

        # Platform ceiling: cap max_tokens to prevent runaway costs
        _platform_max = int(os.getenv("PLATFORM_MAX_TOKENS_PER_RESPONSE", "32000"))
        if max_tok and max_tok > _platform_max:
            logger.debug("max_tokens %d exceeds platform ceiling %d; capping.", max_tok, _platform_max)
            max_tok = _platform_max

        # Response cache check (opt-in, 6 correctness gates enforced inside)
        _ctx = getattr(self, "_cost_context", {}) or {}
        if _ctx.get("enable_response_cache"):
            try:
                from src.services.cache.llm_response_cache import get_cached_response

                _cached = await get_cached_response(
                    provider=self.provider,
                    model_name=self.config.model_name,
                    temperature=temp,
                    messages=[{"role": "user", "content": prompt}],
                    system_prompt_hash=_ctx.get("system_prompt_hash", ""),
                    tenant_id=_ctx.get("tenant_id") or "",
                    agent_id=str(_ctx.get("agent_id") or ""),
                )
                if _cached is not None:
                    self._read_and_fire_usage(response_cache_hit=True)
                    return _cached
            except Exception:
                pass  # fail-open

        # PERFORMANCE: Get circuit breaker scoped to provider+model (not just provider)
        # so a failing deployment of model-A doesn't block calls to model-B on the same
        # provider.  Operators can pin a tighter scope via routing_rules.config_id.
        _cb_key = f"llm_{self.provider}_{self.config.model_name}".replace("/", "_")
        circuit_breaker = get_circuit_breaker(
            name=_cb_key,
            failure_threshold=5,
            recovery_timeout=60,
        )

        # PERFORMANCE: Get metrics collector
        metrics = get_metrics_collector()

        # Check if tracing should be enabled
        should_trace = self.langfuse_service.should_trace(self.observability_config)
        generation_id = None
        start_time = time.time()

        logger.info(
            f"🔍 LLM Generation - should_trace: {should_trace}, observability_config: {self.observability_config}"
        )

        try:
            # Create Langfuse generation if tracing is enabled
            if should_trace:
                logger.info(f"📊 Creating Langfuse generation for model: {self.config.model_name}")
                generation_id = self.langfuse_service.create_generation(
                    name="llm_generation",
                    model=self.config.model_name,
                    input_data={"prompt": prompt},
                    metadata={
                        "provider": self.provider,
                        "temperature": temp,
                        "max_tokens": max_tok,
                        **(metadata or {}),
                    },
                    trace_id=trace_id,
                )
                logger.info(f"✅ Langfuse generation created with ID: {generation_id}")

            # PERFORMANCE: Track LLM request metrics
            metrics.inc_counter("llm_requests_total")

            # PERFORMANCE: Use circuit breaker for LLM calls
            async def _do_generate():
                # Generate content
                # Provider is already normalized to lowercase in __init__
                if self.provider == "mock":
                    return await self._generate_mock(prompt, temp, max_tok, **kwargs)
                elif self.provider in ["google", "gemini"]:
                    return await self._generate_google(prompt, temp, max_tok, **kwargs)
                elif self.provider in ["openai", "deepseek", "openrouter", "minimax", "groq"]:
                    return await self._generate_openai(prompt, temp, max_tok, **kwargs)
                elif self.provider in ["anthropic", "claude"]:
                    return await self._generate_anthropic(prompt, temp, max_tok, **kwargs)
                elif self.provider == "litellm":
                    return await self._generate_litellm(prompt, temp, max_tok, **kwargs)
                else:
                    raise ValueError(f"Unsupported provider: {self.provider}")

            _llm_call_start = time.time()
            response = await circuit_breaker.call_async(_do_generate)
            _llm_call_latency_ms = int((time.time() - _llm_call_start) * 1000)

            # Capture actual API-reported token counts BEFORE _read_and_fire_usage()
            # clears the ContextVar.  We use these below in fire_llm_call so the lens
            # shows real numbers instead of TokenCounter estimates (which return 0 for
            # models tiktoken doesn't know, e.g. claude-sonnet-4-6).
            _api_usage = _llm_usage_ctx.get() or {}

            # Fire token usage recording (non-blocking) — this clears _llm_usage_ctx
            self._read_and_fire_usage()

            # Store in response cache if opt-in
            if _ctx.get("enable_response_cache") and response:
                try:
                    from src.services.cache.llm_response_cache import set_cached_response

                    await set_cached_response(
                        provider=self.provider,
                        model_name=self.config.model_name,
                        temperature=temp,
                        messages=[{"role": "user", "content": prompt}],
                        response=response,
                        system_prompt_hash=_ctx.get("system_prompt_hash", ""),
                        tenant_id=_ctx.get("tenant_id") or "",
                        agent_id=str(_ctx.get("agent_id") or ""),
                    )
                except Exception:
                    pass  # fail-open

            # PERFORMANCE: Track request duration
            duration = time.time() - start_time
            metrics.observe_histogram("llm_request_duration_seconds", duration)

            # Update Langfuse generation with output
            if should_trace and generation_id:
                logger.info(f"📝 Updating Langfuse generation {generation_id} with output")
                # Count tokens using accurate TokenCounter
                from src.services.agents.token_counter import TokenCounter

                input_tokens = TokenCounter.count_tokens(prompt, self.config.model_name)
                output_tokens = TokenCounter.count_tokens(response, self.config.model_name)

                # PERFORMANCE: Track token usage
                metrics.inc_counter("llm_tokens_total", int(input_tokens + output_tokens))

                self.langfuse_service.update_generation(
                    generation_id=generation_id,
                    output_data={"response": response},
                    usage={
                        "input": int(input_tokens),
                        "output": int(output_tokens),
                        "total": int(input_tokens + output_tokens),
                    },
                    metadata={"latency_ms": int((time.time() - start_time) * 1000)},
                )
                logger.info(f"✅ Langfuse generation {generation_id} updated successfully")

            # Fire LLM call trace event (fire-and-forget, zero latency impact)
            try:
                from src.services.agents.agent_trace_service import fire_llm_call
                from src.services.agents.runtime_context import get_runtime_context
                from src.services.billing.llm_cost_service import calculate_cost as _calc_cost

                _rt = get_runtime_context()
                if _rt is not None:
                    _rt.llm_call_index += 1
                    _rt.event_sequence += 1
                    # Prefer real API-reported counts captured above; fall back to
                    # TokenCounter only if the provider didn't return usage data.
                    _in_tokens = int(_api_usage.get("input_tokens") or 0)
                    _out_tokens = int(_api_usage.get("output_tokens") or 0)
                    if _in_tokens == 0 and _out_tokens == 0:
                        from src.services.agents.token_counter import TokenCounter

                        _in_tokens = TokenCounter.count_tokens(prompt, self.config.model_name)
                        _out_tokens = TokenCounter.count_tokens(response or "", self.config.model_name)
                    fire_llm_call(
                        tenant_id=_rt.tenant_id,
                        agent_id=_rt.agent_id,
                        conversation_id=_rt.conversation_id,
                        model=self.config.model_name,
                        call_index=_rt.llm_call_index,
                        input_tokens=int(_in_tokens),
                        output_tokens=int(_out_tokens),
                        cost_usd=_calc_cost(self.config.model_name, int(_in_tokens), int(_out_tokens)) or 0.0,
                        latency_ms=_llm_call_latency_ms,
                        response_preview=(response or "")[:3000],
                        status="success",
                        error=None,
                        sequence=_rt.event_sequence,
                        system_prompt=(prompt or "")[:2000] if prompt else None,
                        cache_read_tokens=int(_api_usage.get("cache_read_tokens") or 0),
                        cache_creation_tokens=int(_api_usage.get("cache_creation_tokens") or 0),
                    )
            except Exception:
                pass  # never block LLM response

            return response

        except CircuitBreakerOpen as e:
            logger.warning(f"Circuit breaker open for {self.provider}: {e}")
            raise LLMProviderError(
                f"Provider '{self.provider}' circuit breaker is open: {e}",
                provider=self.provider,
                original_error=e,
            )

        except Exception as e:
            # Log error to Langfuse if tracing is enabled
            if should_trace and generation_id:
                self.langfuse_service.update_generation(
                    generation_id=generation_id,
                    output_data={"error": str(e)},
                    metadata={
                        "error": True,
                        "error_type": type(e).__name__,
                        "latency_ms": int((time.time() - start_time) * 1000),
                    },
                )
            # Fire failed LLM call trace event
            try:
                from src.services.agents.agent_trace_service import fire_llm_call
                from src.services.agents.runtime_context import get_runtime_context

                _rt = get_runtime_context()
                if _rt is not None:
                    _rt.llm_call_index += 1
                    _rt.event_sequence += 1
                    fire_llm_call(
                        tenant_id=_rt.tenant_id,
                        agent_id=_rt.agent_id,
                        conversation_id=_rt.conversation_id,
                        model=self.config.model_name,
                        call_index=_rt.llm_call_index,
                        input_tokens=0,
                        output_tokens=0,
                        cost_usd=0.0,
                        latency_ms=int((time.time() - start_time) * 1000),
                        response_preview=None,
                        status="error",
                        error=str(e)[:500],
                        sequence=_rt.event_sequence,
                    )
            except Exception:
                pass
            # Re-raise as LLMProviderError for known recoverable provider failures
            # so callers with a fallback chain can try the next config.
            if _is_provider_error(e):
                raise LLMProviderError(
                    f"Provider '{self.provider}' failed: {e}",
                    provider=self.provider,
                    original_error=e,
                ) from e
            raise

    async def _generate_mock(self, prompt: str, temperature: float, max_tokens: int | None, **kwargs) -> str:
        """
        Generate mock content for load testing.

        Simulates a realistic response delay without calling any real LLM API.
        """
        # Simulate some processing delay (50-200ms)
        await asyncio.sleep(random.uniform(0.05, 0.2))

        # Select a random response
        response = random.choice(self.MOCK_RESPONSES)

        logger.debug(f"🧪 Mock LLM generated response ({len(response)} chars)")
        return response

    async def _generate_mock_stream(
        self, prompt: str, temperature: float, max_tokens: int | None, **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Generate mock streaming content for load testing.

        Simulates realistic LLM streaming behavior:
        - Initial delay (simulating prompt processing)
        - Word-by-word streaming with variable delays
        - Realistic response length and content
        """
        # Simulate initial processing delay (like real LLM "thinking" time)
        # This simulates the time to first token (TTFT)
        initial_delay = random.uniform(0.1, 0.5)
        await asyncio.sleep(initial_delay)

        # Select a random response and split into words
        response = random.choice(self.MOCK_RESPONSES)
        words = response.split()

        # Stream word by word with realistic delays
        for i, word in enumerate(words):
            # Add space before word (except first word)
            chunk = f" {word}" if i > 0 else word
            yield chunk

            # Simulate inter-token delay (10-50ms per token, like real LLM)
            await asyncio.sleep(random.uniform(0.01, 0.05))

        logger.debug(f"🧪 Mock LLM streamed {len(words)} words")

    async def _generate_google(self, prompt: str, temperature: float, max_tokens: int | None, **kwargs) -> str:
        """Generate content using Google Gemini."""
        from google.genai import types

        config_params = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            top_p=self.config.top_p,
        )

        response = self._client.models.generate_content(
            model=self.config.model_name,
            contents=prompt,
            config=config_params,
        )

        return response.text if hasattr(response, "text") else str(response)

    def _build_openai_params(self, max_tokens: int | None, temperature: float | None) -> dict[str, Any]:
        """Build safe OpenAI API parameters, omitting unsupported fields.

        - Uses 'max_completion_tokens' (the current standard, accepted by all models).
        - Omits 'temperature' when None or 1.0 — reasoning models (o-series, gpt-5)
          reject any value other than the default 1. Standard models accept it fine.
          Users who need a specific temperature should set it in the LLM config;
          leaving it null/1 makes the config work for all model families.
        """
        params: dict[str, Any] = {}
        if max_tokens is not None:
            params["max_completion_tokens"] = max_tokens
        if temperature is not None and temperature != 1.0:
            params["temperature"] = temperature
        return params

    async def _generate_openai(self, prompt: str, temperature: float, max_tokens: int | None, **kwargs) -> str:
        """Generate content using OpenAI."""
        response = await self._client.chat.completions.create(
            model=self.config.model_name,
            messages=[{"role": "user", "content": prompt}],
            **self._build_openai_params(max_tokens, temperature),
            **kwargs,
        )
        if response.usage:
            cached = 0
            details = getattr(response.usage, "prompt_tokens_details", None)
            if details and hasattr(details, "cached_tokens"):
                cached = details.cached_tokens or 0
            _llm_usage_ctx.set(
                {
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
                    "cached_input_tokens": cached,
                }
            )
        return response.choices[0].message.content

    async def _generate_anthropic(self, prompt: str, temperature: float, max_tokens: int | None, **kwargs) -> str:
        """Generate content using Anthropic Claude."""
        max_tok = max_tokens or 4096  # Claude requires max_tokens

        # Add extra headers if configured (e.g., for extended context)
        extra_headers = {}
        if hasattr(self.config, "additional_params") and self.config.additional_params:
            if "extra_headers" in self.config.additional_params:
                extra_headers = self.config.additional_params["extra_headers"]

        # Enable prompt-caching beta header for supported models (transparent to output quality)
        if self._supports_prompt_cache():
            extra_headers["anthropic-beta"] = "prompt-caching-2024-07-31"

        create_kwargs: dict = {
            "model": self.config.model_name,
            "max_tokens": max_tok,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
            **({"extra_headers": extra_headers} if extra_headers else {}),
        }

        response = await self._client.messages.create(**create_kwargs, timeout=600.0, **kwargs)

        _llm_usage_ctx.set(
            {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "cache_read_tokens": getattr(response.usage, "cache_read_input_tokens", 0) or 0,
                "cache_creation_tokens": getattr(response.usage, "cache_creation_input_tokens", 0) or 0,
            }
        )

        return response.content[0].text

    async def _generate_litellm(self, prompt: str, temperature: float, max_tokens: int | None, **kwargs) -> str:
        """Generate content using LiteLLM (supports 100+ providers)."""
        import litellm

        # Prepare model name with provider prefix
        model_name = self._prepare_litellm_model_name(self.config.model_name)

        # Prepare completion parameters
        completion_params = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "api_key": self.config.api_key,
            "num_retries": 3,
            "drop_params": True,  # Silently drop unsupported params (e.g. temperature for gpt-5)
        }

        # Add base URL if provided; also force OpenAI-compatible routing so LiteLLM
        # SDK does not try to detect the provider from the model name (which would send
        # gemini-* to Vertex AI or fail for unknown names like "llama-4-maverick").
        if self.config.api_base:
            completion_params["api_base"] = self.config.api_base
            completion_params["custom_llm_provider"] = "openai"

        # Add any additional kwargs
        completion_params.update(kwargs)

        # LiteLLM uses async completion
        response = await litellm.acompletion(**completion_params)

        return response.choices[0].message.content

    async def generate_content_stream(
        self,
        prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout: int | None = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """
        Generate content with streaming using the configured provider.

        Args:
            prompt: The input prompt
            temperature: Sampling temperature (overrides config)
            max_tokens: Maximum tokens to generate (overrides config)
            timeout: Total streaming timeout in seconds (uses instance default if None)
            **kwargs: Additional provider-specific parameters

        Yields:
            Text chunks as they are generated

        Raises:
            LLMStreamingTimeoutError: If streaming times out
        """
        temp = temperature if temperature is not None else self.config.temperature
        max_tok = max_tokens if max_tokens is not None else self.config.max_tokens

        # Platform ceiling
        _platform_max = int(os.getenv("PLATFORM_MAX_TOKENS_PER_RESPONSE", "32000"))
        if max_tok and max_tok > _platform_max:
            max_tok = _platform_max

        # Wrap the streaming with timeout protection (both total and chunk timeout)
        async def _stream():
            # Provider is already normalized to lowercase in __init__
            if self.provider == "mock":
                async for chunk in self._generate_mock_stream(prompt, temp, max_tok, **kwargs):
                    yield chunk
            elif self.provider in ["google", "gemini"]:
                async for chunk in self._generate_google_stream(prompt, temp, max_tok, **kwargs):
                    yield chunk
            elif self.provider in ["openai", "deepseek", "openrouter", "minimax", "groq"]:
                async for chunk in self._generate_openai_stream(prompt, temp, max_tok, **kwargs):
                    yield chunk
            elif self.provider in ["anthropic", "claude"]:
                async for chunk in self._generate_anthropic_stream(prompt, temp, max_tok, **kwargs):
                    yield chunk
            elif self.provider == "litellm":
                async for chunk in self._generate_litellm_stream(prompt, temp, max_tok, **kwargs):
                    yield chunk
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")

        # Apply full timeout wrapper (checks both total timeout and chunk timeout).
        # Translate CircuitBreakerOpen / known provider errors to LLMProviderError
        # so callers with a fallback chain can retry with the next LLM config.
        try:
            async for chunk in self._with_streaming_timeout(
                self._wrap_with_chunk_timeout(_stream()),
                total_timeout=timeout or self.streaming_timeout,
            ):
                yield chunk
        except LLMProviderError:
            raise  # already translated
        except CircuitBreakerOpen as e:
            raise LLMProviderError(
                f"Provider '{self.provider}' circuit breaker is open: {e}",
                provider=self.provider,
                original_error=e,
            ) from e
        except Exception as e:
            if _is_provider_error(e):
                raise LLMProviderError(
                    f"Provider '{self.provider}' stream failed: {e}",
                    provider=self.provider,
                    original_error=e,
                ) from e
            raise

    async def generate_content_stream_with_messages(
        self,
        messages: list[dict[str, Any]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout: int | None = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """
        Generate content with streaming using messages array (for conversation history).

        Args:
            messages: Array of message objects with role and content
            temperature: Sampling temperature (overrides config)
            max_tokens: Maximum tokens to generate (overrides config)
            timeout: Total streaming timeout in seconds (uses instance default if None)
            **kwargs: Additional provider-specific parameters

        Yields:
            Text chunks as they are generated

        Raises:
            LLMStreamingTimeoutError: If streaming times out
        """
        temp = temperature if temperature is not None else self.config.temperature
        max_tok = max_tokens if max_tokens is not None else self.config.max_tokens

        # Platform ceiling
        _platform_max = int(os.getenv("PLATFORM_MAX_TOKENS_PER_RESPONSE", "32000"))
        if max_tok and max_tok > _platform_max:
            max_tok = _platform_max

        # Note: max_tokens limits vary by model (e.g., Claude supports up to 200k output tokens)
        # We no longer cap this artificially - let the API handle model-specific limits
        if max_tok and max_tok > 100000:
            logger.info(f"📝 Using high max_tokens value: {max_tok} (ensure model supports this)")

        # Wrap the streaming with timeout protection (both total and chunk timeout)
        async def _stream():
            # Provider is already normalized to lowercase in __init__
            if self.provider == "mock":
                # For mock, extract the last user message as prompt
                prompt = messages[-1]["content"] if messages else ""
                async for chunk in self._generate_mock_stream(prompt, temp, max_tok, **kwargs):
                    yield chunk
            elif self.provider in ["google", "gemini"]:
                async for chunk in self._generate_google_stream_with_messages(messages, temp, max_tok, **kwargs):
                    yield chunk
            elif self.provider in ["openai", "deepseek", "openrouter", "minimax", "groq"]:
                async for chunk in self._generate_openai_stream_with_messages(messages, temp, max_tok, **kwargs):
                    yield chunk
            elif self.provider in ["anthropic", "claude"]:
                async for chunk in self._generate_anthropic_stream_with_messages(messages, temp, max_tok, **kwargs):
                    yield chunk
            elif self.provider == "litellm":
                async for chunk in self._generate_litellm_stream_with_messages(messages, temp, max_tok, **kwargs):
                    yield chunk
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")

        # Apply full timeout wrapper (checks both total timeout and chunk timeout).
        # Translate CircuitBreakerOpen / known provider errors to LLMProviderError
        # so callers with a fallback chain can retry with the next LLM config.
        try:
            async for chunk in self._with_streaming_timeout(
                self._wrap_with_chunk_timeout(_stream()),
                total_timeout=timeout or self.streaming_timeout,
            ):
                yield chunk
        except LLMProviderError:
            raise  # already translated
        except CircuitBreakerOpen as e:
            raise LLMProviderError(
                f"Provider '{self.provider}' circuit breaker is open: {e}",
                provider=self.provider,
                original_error=e,
            ) from e
        except Exception as e:
            if _is_provider_error(e):
                raise LLMProviderError(
                    f"Provider '{self.provider}' stream failed: {e}",
                    provider=self.provider,
                    original_error=e,
                ) from e
            raise

    async def _generate_google_stream(
        self, prompt: str, temperature: float, max_tokens: int | None, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Generate content using Google Gemini with streaming (single-turn)."""
        from google.genai import types

        config_params = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            top_p=self.config.top_p,
        )

        response = self._client.models.generate_content_stream(
            model=self.config.model_name,
            contents=prompt,
            config=config_params,
        )

        for chunk in response:
            if hasattr(chunk, "text") and chunk.text:
                yield chunk.text

    async def _generate_google_stream_with_messages(
        self, messages: list[dict[str, Any]], temperature: float, max_tokens: int | None, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Generate content using Google Gemini with streaming and full conversation history."""
        from google.genai import types

        # Gemini handles system prompt via system_instruction, not as a message
        system_parts = [m["content"] for m in messages if m.get("role") == "system"]
        conversation_messages = [m for m in messages if m.get("role") != "system"]
        system_instruction = "\n\n".join(system_parts) if system_parts else None

        # Convert OpenAI-format messages to Gemini Content objects
        # Gemini uses "user" / "model" roles (OpenAI uses "user" / "assistant")
        gemini_contents = []
        for msg in conversation_messages:
            role = msg.get("role", "user")
            content = msg.get("content") or ""
            gemini_role = "model" if role == "assistant" else "user"
            gemini_contents.append(types.Content(role=gemini_role, parts=[types.Part(text=str(content))]))

        config_kwargs: dict[str, Any] = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
            "top_p": self.config.top_p,
        }
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction

        config_params = types.GenerateContentConfig(**config_kwargs)

        response = self._client.models.generate_content_stream(
            model=self.config.model_name,
            contents=gemini_contents,
            config=config_params,
        )

        for chunk in response:
            if hasattr(chunk, "text") and chunk.text:
                yield chunk.text

    async def _generate_openai_stream(
        self, prompt: str, temperature: float, max_tokens: int | None, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Generate content using OpenAI with streaming."""
        stream = await self._client.chat.completions.create(
            model=self.config.model_name,
            messages=[{"role": "user", "content": prompt}],
            **self._build_openai_params(max_tokens, temperature),
            stream=True,
            **kwargs,
        )
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def _generate_anthropic_stream(
        self, prompt: str, temperature: float, max_tokens: int | None, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Generate content using Anthropic Claude with streaming."""
        max_tok = max_tokens or 4096

        # Add extra headers if configured (e.g., for extended context)
        extra_headers = {}
        if hasattr(self.config, "additional_params") and self.config.additional_params:
            if "extra_headers" in self.config.additional_params:
                extra_headers = self.config.additional_params["extra_headers"]

        async with self._client.messages.stream(
            model=self.config.model_name,
            max_tokens=max_tok,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
            extra_headers=extra_headers if extra_headers else None,
            **kwargs,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def _generate_litellm_stream(
        self, prompt: str, temperature: float, max_tokens: int | None, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Generate content using LiteLLM with streaming."""
        import litellm

        # Prepare model name with provider prefix
        model_name = self._prepare_litellm_model_name(self.config.model_name)

        completion_params = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "api_key": self.config.api_key,
            "stream": True,
            "num_retries": 3,
            "drop_params": True,  # Silently drop unsupported params (e.g. temperature for gpt-5)
        }

        if self.config.api_base:
            completion_params["api_base"] = self.config.api_base
            completion_params["custom_llm_provider"] = "openai"

        completion_params.update(kwargs)

        logger.info(f"🔄 Starting LiteLLM stream for model: {model_name}")

        # LiteLLM acompletion returns an async generator directly
        response = await litellm.acompletion(**completion_params)

        chunk_count = 0
        # Iterate through the stream
        async for chunk in response:
            # Check if chunk has content and it's not None
            if hasattr(chunk, "choices") and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                if hasattr(delta, "content") and delta.content is not None:
                    # Only yield non-empty content
                    if delta.content:
                        chunk_count += 1
                        logger.debug(f"📤 LiteLLM chunk #{chunk_count}: {len(delta.content)} chars")
                        yield delta.content

        logger.info(f"✅ LiteLLM stream completed: {chunk_count} chunks")

    async def _generate_openai_stream_with_messages(
        self, messages: list[dict[str, Any]], temperature: float, max_tokens: int | None, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Generate content using OpenAI with streaming and messages array."""
        # stream_options with include_usage is OpenAI-specific — gate on provider
        extra_stream: dict = {}
        if self.provider == "openai":
            extra_stream["stream_options"] = {"include_usage": True}

        stream = await self._client.chat.completions.create(
            model=self.config.model_name,
            messages=messages,
            **self._build_openai_params(max_tokens, temperature),
            stream=True,
            **extra_stream,
            **kwargs,
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
            # Final chunk carries usage when stream_options was set
            if getattr(chunk, "usage", None) and chunk.usage:
                cached = 0
                details = getattr(chunk.usage, "prompt_tokens_details", None)
                if details and hasattr(details, "cached_tokens"):
                    cached = details.cached_tokens or 0
                _llm_usage_ctx.set(
                    {
                        "input_tokens": chunk.usage.prompt_tokens,
                        "output_tokens": chunk.usage.completion_tokens,
                        "cached_input_tokens": cached,
                    }
                )

    async def _generate_anthropic_stream_with_messages(
        self, messages: list[dict[str, Any]], temperature: float, max_tokens: int | None, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Generate content using Anthropic Claude with streaming and messages array."""
        max_tok = max_tokens or 4096

        # Anthropic requires system prompt as top-level parameter, not as a message with role "system"
        system_parts = [m["content"] for m in messages if m.get("role") == "system"]
        filtered_messages = [m for m in messages if m.get("role") != "system"]
        system_prompt = "\n\n".join(system_parts) if system_parts else None

        # Add extra headers if configured (e.g., for extended context)
        extra_headers = {}
        if hasattr(self.config, "additional_params") and self.config.additional_params:
            if "extra_headers" in self.config.additional_params:
                extra_headers = self.config.additional_params["extra_headers"]

        # Prompt caching for supported models (transparent to output quality).
        # cache_control on the system prompt caches the entire system prefix,
        # which is re-used across every turn of the conversation.
        system_value: str | list | None = None
        if system_prompt:
            if self._supports_prompt_cache():
                extra_headers["anthropic-beta"] = "prompt-caching-2024-07-31"
                system_value = [
                    {
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ]
            else:
                system_value = system_prompt

        stream_kwargs: dict[str, Any] = {
            "model": self.config.model_name,
            "max_tokens": max_tok,
            "temperature": temperature,
            "messages": filtered_messages,
            **({"system": system_value} if system_value else {}),
            **({"extra_headers": extra_headers} if extra_headers else {}),
            **kwargs,
        }

        try:
            async with self._client.messages.stream(**stream_kwargs) as stream:
                async for text in stream.text_stream:
                    yield text
                # Capture usage after stream is fully consumed.
                # get_final_message() is available in anthropic>=0.42.0 (current pin: 0.50.0).
                try:
                    final_msg = await stream.get_final_message()
                    if final_msg and final_msg.usage:
                        _llm_usage_ctx.set(
                            {
                                "input_tokens": final_msg.usage.input_tokens,
                                "output_tokens": final_msg.usage.output_tokens,
                                "cache_read_tokens": getattr(final_msg.usage, "cache_read_input_tokens", 0) or 0,
                                "cache_creation_tokens": getattr(final_msg.usage, "cache_creation_input_tokens", 0)
                                or 0,
                            }
                        )
                except Exception:
                    pass  # usage capture never blocks streaming
        except Exception as e:
            err_str = str(e)
            if "max_tokens" in err_str and "maximum allowed" in err_str:
                # Extract the model's actual limit from the error message if possible
                import re

                match = re.search(r"maximum allowed number of output tokens for \S+ is (\d+)", err_str)
                model_limit = match.group(1) if match else "the model's limit"
                raise ValueError(
                    f"max_tokens ({max_tok}) exceeds {model_limit} for model '{self.config.model_name}'. "
                    f"Please update the LLM configuration in Settings → LLM Config."
                ) from e
            raise

    async def _generate_litellm_stream_with_messages(
        self, messages: list[dict[str, Any]], temperature: float, max_tokens: int | None, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Generate content using LiteLLM with streaming and messages array."""
        import litellm

        # Prepare model name with provider prefix
        model_name = self._prepare_litellm_model_name(self.config.model_name)

        completion_params = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "api_key": self.config.api_key,
            "stream": True,
            "num_retries": 3,
            "drop_params": True,  # Silently drop unsupported params (e.g. temperature for gpt-5)
        }

        if self.config.api_base:
            completion_params["api_base"] = self.config.api_base

        completion_params.update(kwargs)

        logger.info(f"🔄 Starting LiteLLM stream with messages for model: {model_name}")

        # LiteLLM acompletion returns an async generator directly
        response = await litellm.acompletion(**completion_params)

        chunk_count = 0
        # Iterate through the stream
        async for chunk in response:
            # Check if chunk has content and it's not None
            if hasattr(chunk, "choices") and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                if hasattr(delta, "content") and delta.content is not None:
                    # Only yield non-empty content
                    if delta.content:
                        chunk_count += 1
                        logger.debug(f"📤 LiteLLM chunk #{chunk_count}: {len(delta.content)} chars")
                        yield delta.content

        logger.info(f"✅ LiteLLM stream with messages completed: {chunk_count} chunks")

    def get_provider_info(self) -> dict[str, Any]:
        """Get information about the current provider."""
        return {
            "provider": self.provider,
            "model": self.config.model_name,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
