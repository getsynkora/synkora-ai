"""
Model Router — selects the optimal AgentLLMConfig for a given query.

Supports five routing modes:
  fixed       — always use the default config (current behaviour, zero overhead)
  round_robin — weighted random selection across enabled configs
  cost_opt    — cheapest viable config that passes complexity + budget gates
  intent      — match config to query intent tags
  latency_opt — prefer known-fast models (by preset or observed TTFT)

The router returns a RoutingDecision containing the primary config ID and
an ordered list of fallback config IDs for failover when a circuit is open.

routing_config keys (all optional):
  quality_floor     float 0–1  Minimum quality_tier a selected config must meet.
  max_cost_per_1k   float      Budget cap in USD/1k input tokens; configs above
                               this are excluded from cost_opt selection.
"""

import logging
import random
from dataclasses import dataclass, field

from src.services.agents.routing.intent_classifier import ClassificationResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Models known for fast time-to-first-token (< 300ms p50)
# ---------------------------------------------------------------------------
_FAST_MODEL_NAMES: frozenset[str] = frozenset(
    {
        "claude-haiku-4-5",
        "claude-haiku-4-5-20251001",
        "claude-3-haiku-20240307",
        "gpt-4o-mini",
        "gpt-4o-mini-2024-07-18",
        "gemini-1.5-flash",
        "gemini-1.5-flash-latest",
        "gemini-2.0-flash",
        "gemini-flash-2.0",
        "mistral-small-latest",
        "mixtral-8x7b-instruct",
        "llama-3.1-8b-instant",  # Groq
        "llama3-8b-8192",  # Groq
    }
)

# ---------------------------------------------------------------------------
# Built-in cost hints (USD per 1k tokens) — used when routing_rules don't
# specify costs.  Kept in sync with public pricing as of April 2026.
# Operators can override per-config via routing_rules.cost_per_1k_input.
# ---------------------------------------------------------------------------
_BUILTIN_COSTS: dict[str, float] = {
    # Anthropic — input cost per 1k tokens
    "claude-opus-4-6": 0.015,
    "claude-sonnet-4-6": 0.003,
    "claude-haiku-4-5": 0.0008,
    "claude-haiku-4-5-20251001": 0.0008,
    "claude-3-5-sonnet-20241022": 0.003,
    "claude-3-5-haiku-20241022": 0.0008,
    "claude-3-haiku-20240307": 0.00025,
    # OpenAI — input cost per 1k tokens
    "gpt-4o": 0.005,
    "gpt-4o-mini": 0.00015,
    "gpt-4-turbo": 0.01,
    "o1": 0.015,
    "o1-mini": 0.003,
    "o3-mini": 0.0011,
    # Google — input cost per 1k tokens
    "gemini-1.5-pro": 0.00125,
    "gemini-1.5-flash": 0.000075,
    "gemini-2.0-flash": 0.0001,
    "gemini-2.5-pro": 0.00125,
    # Mistral — input cost per 1k tokens
    "mistral-small-latest": 0.001,
    "mistral-large-latest": 0.003,
    # Meta / Groq — input cost per 1k tokens
    "llama-3.1-8b-instant": 0.00005,
    "llama3-70b-8192": 0.00059,
}

# Output cost per 1k tokens for every model in _BUILTIN_COSTS.
# Output is billed separately (typically 3–5x input rate).
# Source: official provider pricing pages.
_BUILTIN_OUTPUT_COSTS: dict[str, float] = {
    # Anthropic
    "claude-opus-4-6": 0.075,  # $75 / 1M output
    "claude-sonnet-4-6": 0.015,  # $15 / 1M output
    "claude-haiku-4-5": 0.004,  # $4  / 1M output
    "claude-haiku-4-5-20251001": 0.004,
    "claude-3-5-sonnet-20241022": 0.015,
    "claude-3-5-haiku-20241022": 0.004,
    "claude-3-haiku-20240307": 0.00125,  # $1.25 / 1M output
    # OpenAI
    "gpt-4o": 0.015,  # $15 / 1M output
    "gpt-4o-mini": 0.0006,  # $0.60 / 1M output
    "gpt-4-turbo": 0.030,  # $30 / 1M output
    "o1": 0.060,  # $60 / 1M output
    "o1-mini": 0.012,  # $12 / 1M output
    "o3-mini": 0.0044,  # $4.40 / 1M output
    # Google
    "gemini-1.5-pro": 0.005,  # $5   / 1M output
    "gemini-1.5-flash": 0.0003,  # $0.30 / 1M output
    "gemini-2.0-flash": 0.0004,  # $0.40 / 1M output
    "gemini-2.5-pro": 0.010,  # $10  / 1M output
    # Mistral
    "mistral-small-latest": 0.003,  # $3   / 1M output
    "mistral-large-latest": 0.009,  # $9   / 1M output
    # Meta / Groq
    "llama-3.1-8b-instant": 0.00008,
    "llama3-70b-8192": 0.00079,
}

# ---------------------------------------------------------------------------
# Built-in context window sizes (input tokens) per model name.
# Used by the context-window pre-filter when routing_rules don't specify
# max_input_tokens.  Operators can override via routing_rules.max_input_tokens.
# ---------------------------------------------------------------------------
_BUILTIN_CONTEXT_WINDOWS: dict[str, int] = {
    # Anthropic
    "claude-opus-4-6": 200_000,
    "claude-sonnet-4-6": 200_000,
    "claude-haiku-4-5": 200_000,
    "claude-haiku-4-5-20251001": 200_000,
    "claude-3-5-sonnet-20241022": 200_000,
    "claude-3-5-haiku-20241022": 200_000,
    "claude-3-haiku-20240307": 200_000,
    "claude-3-opus-20240229": 200_000,
    # OpenAI
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
    "gpt-4-turbo": 128_000,
    "o1": 200_000,
    "o1-mini": 128_000,
    "o3-mini": 200_000,
    # Google
    "gemini-1.5-pro": 1_048_576,
    "gemini-1.5-flash": 1_048_576,
    "gemini-2.0-flash": 1_048_576,
    "gemini-2.5-pro": 1_048_576,
    # Mistral
    "mistral-small-latest": 32_768,
    "mistral-large-latest": 131_072,
    # Groq
    "llama-3.1-8b-instant": 131_072,
    "llama3-70b-8192": 8_192,
    "llama3-8b-8192": 8_192,
}


@dataclass
class RoutingDecision:
    """Result of a routing decision."""

    primary_config_id: str
    """ID of the selected AgentLLMConfig to use first."""

    fallback_config_ids: list[str] = field(default_factory=list)
    """Ordered fallback IDs to try if the primary circuit is open.
    Non-fallback-only configs always appear before is_fallback=True configs."""

    routing_mode: str = "fixed"
    """Mode that produced this decision."""

    classification: ClassificationResult | None = None
    """Classification result (None when routing_mode='fixed')."""

    selected_model: str = ""
    """Human-readable model name for logging."""

    def __repr__(self) -> str:
        fb = f", fallbacks={self.fallback_config_ids}" if self.fallback_config_ids else ""
        return (
            f"RoutingDecision(mode={self.routing_mode}, "
            f"model={self.selected_model}, "
            f"primary={self.primary_config_id}{fb})"
        )


class ModelRouter:
    """
    Stateless model router.  A single instance can be shared across requests.
    """

    def select(
        self,
        routing_mode: str,
        routing_config: dict | None,
        llm_configs: list,  # list[AgentLLMConfig]
        classification: ClassificationResult | None,
        explicit_config_id: str | None = None,
    ) -> RoutingDecision:
        """
        Select the optimal LLM config and build the fallback chain.

        Args:
            routing_mode:      Agent's routing_mode field.
            routing_config:    Agent's routing_config JSON (quality_floor, etc.).
            llm_configs:       All enabled AgentLLMConfig rows for this agent.
            classification:    Pre-computed intent/complexity result (may be None).
            explicit_config_id: If the caller pinned a specific config, always honour it.

        Returns:
            RoutingDecision with primary + fallback config IDs.
        """
        enabled = [c for c in llm_configs if c.enabled]
        if not enabled:
            raise ValueError("Agent has no enabled LLM configurations.")

        # Explicit override always wins — no routing needed
        if explicit_config_id:
            match = next((c for c in enabled if str(c.id) == explicit_config_id), None)
            if match:
                return RoutingDecision(
                    primary_config_id=str(match.id),
                    routing_mode="explicit",
                    selected_model=match.model_name,
                )

        routing_config = routing_config or {}
        mode = (routing_mode or "fixed").lower()

        # Context-window pre-filter: drop configs that can't hold the estimated input.
        # Applied before any mode-specific selection so every mode benefits.
        if classification and classification.estimated_input_tokens > 0:
            ctx_ok = [c for c in enabled if self._context_fits(c, classification.estimated_input_tokens)]
            if ctx_ok:
                enabled = ctx_ok
            else:
                logger.warning(
                    f"[routing] All configs filtered by context-window check "
                    f"(estimated_tokens={classification.estimated_input_tokens}); skipping filter"
                )

        if mode == "fixed":
            return self._decision_fixed(enabled)
        elif mode == "round_robin":
            return self._decision_round_robin(enabled)
        elif mode == "cost_opt":
            return self._decision_cost_opt(enabled, classification, routing_config)
        elif mode == "intent":
            return self._decision_intent(enabled, classification)
        elif mode == "latency_opt":
            return self._decision_latency_opt(enabled)
        else:
            logger.warning(f"Unknown routing_mode '{mode}', falling back to fixed.")
            return self._decision_fixed(enabled)

    # ------------------------------------------------------------------
    # Mode implementations
    # ------------------------------------------------------------------

    def _decision_fixed(self, configs: list) -> RoutingDecision:
        primary = self._default_config(configs)
        fallbacks = [c for c in configs if str(c.id) != str(primary.id) and not self._is_fallback_only(c)]
        return RoutingDecision(
            primary_config_id=str(primary.id),
            fallback_config_ids=[str(c.id) for c in fallbacks],
            routing_mode="fixed",
            selected_model=primary.model_name,
        )

    def _decision_round_robin(self, configs: list) -> RoutingDecision:
        # Exclude fallback-only configs from the weighted lottery
        candidates = [c for c in configs if not self._is_fallback_only(c)] or configs
        weights = [max(float(getattr(c, "routing_weight", None) or 1.0), 0.001) for c in candidates]
        primary = random.choices(candidates, weights=weights, k=1)[0]

        # Fallback order: remaining non-fallback-only first, then fallback-only last
        fallback_primary = [c for c in candidates if str(c.id) != str(primary.id)]
        fallback_only = [c for c in configs if self._is_fallback_only(c)]
        return RoutingDecision(
            primary_config_id=str(primary.id),
            fallback_config_ids=[str(c.id) for c in fallback_primary + fallback_only],
            routing_mode="round_robin",
            selected_model=primary.model_name,
        )

    def _decision_cost_opt(
        self,
        configs: list,
        classification: ClassificationResult | None,
        routing_config: dict,
    ) -> RoutingDecision:
        complexity = classification.complexity if classification else 0.5

        # Separate non-fallback configs from fallback-only configs
        non_fallback = [c for c in configs if not self._is_fallback_only(c)]
        fallback_only = [c for c in configs if self._is_fallback_only(c)]

        # Budget cap: exclude configs that exceed max_cost_per_1k
        max_cost = float(routing_config.get("max_cost_per_1k", 999.0))
        affordable = [c for c in non_fallback if self._input_cost(c) <= max_cost]
        if not affordable:
            logger.warning(f"[cost_opt] No configs within budget ${max_cost:.5f}/1k; ignoring budget cap")
            affordable = non_fallback

        # Quality gate: exclude configs below quality_floor
        quality_floor = float(routing_config.get("quality_floor", 0.0))
        if quality_floor > 0:
            quality_ok = [c for c in affordable if self._quality_tier(c) >= quality_floor]
            if quality_ok:
                affordable = quality_ok
            else:
                logger.warning(f"[cost_opt] No configs meet quality_floor={quality_floor}; ignoring quality gate")

        # Filter by complexity gate
        viable = [c for c in affordable if self._complexity_fits(c, complexity)]
        if not viable:
            viable = affordable  # loosen gate if nothing fits

        # Sort by input cost (ascending) — cheapest first
        viable.sort(key=lambda c: self._input_cost(c))
        primary = viable[0]

        # Build fallback: next cheapest → fallback-only last
        ordered_fallbacks = list(viable[1:]) + fallback_only

        logger.info(
            f"[cost_opt] complexity={complexity:.2f} intent={classification.intent if classification else '?'} "
            f"budget=${max_cost:.5f}/1k quality_floor={quality_floor} "
            f"→ {primary.model_name} (${self._input_cost(primary):.5f}/1k)"
        )

        return RoutingDecision(
            primary_config_id=str(primary.id),
            fallback_config_ids=[str(c.id) for c in ordered_fallbacks],
            routing_mode="cost_opt",
            classification=classification,
            selected_model=primary.model_name,
        )

    def _decision_intent(
        self,
        configs: list,
        classification: ClassificationResult | None,
    ) -> RoutingDecision:
        intent = classification.intent if classification else "general"

        non_fallback = [c for c in configs if not self._is_fallback_only(c)]
        fallback_only = [c for c in configs if self._is_fallback_only(c)]

        # Find configs that explicitly list this intent
        intent_matched = [c for c in non_fallback if intent in (self._routing_rules(c).get("intents") or [])]

        # Also filter by complexity gate when classification is available
        if classification and intent_matched:
            complexity = classification.complexity
            gated = [c for c in intent_matched if self._complexity_fits(c, complexity)]
            if gated:
                intent_matched = gated

        if intent_matched:
            # Sort by priority (lower number = higher priority)
            intent_matched.sort(key=lambda c: self._routing_rules(c).get("priority", 99))
            primary = intent_matched[0]
            # Fallbacks: remaining intent-matched → unmatched non-fallback → fallback-only
            remaining_matched = list(intent_matched[1:])
            unmatched = [c for c in non_fallback if str(c.id) not in {str(x.id) for x in intent_matched}]
            ordered_fallbacks = remaining_matched + unmatched + fallback_only
        else:
            # No specific-intent match — check for a "general" wildcard config.
            # "general" acts as a catch-all for any intent not explicitly listed elsewhere.
            general_configs = [c for c in non_fallback if "general" in (self._routing_rules(c).get("intents") or [])]
            if general_configs:
                general_configs.sort(key=lambda c: self._routing_rules(c).get("priority", 99))
                primary = general_configs[0]
                # Fallbacks: remaining non-fallback-only first, then fallback-only last
                remaining_non_fb = [c for c in non_fallback if str(c.id) != str(primary.id)]
                ordered_fallbacks = remaining_non_fb + fallback_only
                logger.info(f"[intent] No match for '{intent}' — using 'general' wildcard → {primary.model_name}")
            else:
                # No intent-specific config, no general wildcard → use default
                primary = self._default_config(non_fallback) if non_fallback else self._default_config(configs)
                remaining_non_fb = [c for c in non_fallback if str(c.id) != str(primary.id)]
                ordered_fallbacks = remaining_non_fb + fallback_only

        logger.info(f"[intent] intent={intent} → {primary.model_name} (matched={len(intent_matched)} configs)")

        return RoutingDecision(
            primary_config_id=str(primary.id),
            fallback_config_ids=[str(c.id) for c in ordered_fallbacks],
            routing_mode="intent",
            classification=classification,
            selected_model=primary.model_name,
        )

    def _decision_latency_opt(self, configs: list) -> RoutingDecision:
        non_fallback = [c for c in configs if not self._is_fallback_only(c)]
        fallback_only = [c for c in configs if self._is_fallback_only(c)]

        fast = [c for c in non_fallback if c.model_name in _FAST_MODEL_NAMES]
        slow = [c for c in non_fallback if c.model_name not in _FAST_MODEL_NAMES]

        ordered = fast + slow + fallback_only
        if not ordered:
            ordered = configs

        primary = ordered[0]
        logger.info(f"[latency_opt] → {primary.model_name} (fast={primary.model_name in _FAST_MODEL_NAMES})")

        return RoutingDecision(
            primary_config_id=str(primary.id),
            fallback_config_ids=[str(c.id) for c in ordered[1:]],
            routing_mode="latency_opt",
            selected_model=primary.model_name,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _default_config(configs: list):
        default = next((c for c in configs if c.is_default), None)
        return default or configs[0]

    @staticmethod
    def _routing_rules(config) -> dict:
        rules = getattr(config, "routing_rules", None)
        return rules if isinstance(rules, dict) else {}

    def _is_fallback_only(self, config) -> bool:
        return bool(self._routing_rules(config).get("is_fallback", False))

    def _complexity_fits(self, config, complexity: float) -> bool:
        rules = self._routing_rules(config)
        min_c = float(rules.get("min_complexity", 0.0))
        max_c = float(rules.get("max_complexity", 1.0))
        return min_c <= complexity <= max_c

    def _input_cost(self, config) -> float:
        rules = self._routing_rules(config)
        if "cost_per_1k_input" in rules:
            return float(rules["cost_per_1k_input"])
        return _BUILTIN_COSTS.get(config.model_name, 999.0)

    def _quality_tier(self, config) -> float:
        """
        Quality tier for the config (0.0–1.0).

        Operators set this via routing_rules.quality_tier.  When not set we
        derive a rough estimate from cost: more expensive models are assumed
        higher quality.  This is a heuristic, not a guarantee.
        """
        rules = self._routing_rules(config)
        if "quality_tier" in rules:
            return float(rules["quality_tier"])
        # Derive from cost: map cost → 0.0–1.0 using a log scale capped at $0.02/1k
        cost = self._input_cost(config)
        if cost >= 999.0:
            return 0.5  # Unknown cost — assume medium quality
        import math

        # log scale: $0.00005 → ~0.1, $0.003 → ~0.6, $0.015 → ~0.9
        return min(1.0, max(0.0, (math.log10(cost + 1e-6) + 6) / 6.0))

    def _context_fits(self, config, estimated_tokens: int) -> bool:
        """
        Return True if the estimated input token count fits within the model's
        context window (with a 10% safety headroom).

        Checks, in order:
          1. routing_rules.max_input_tokens  (operator override)
          2. _BUILTIN_CONTEXT_WINDOWS lookup by model name
          3. llm_provider_presets lookup
          If the context window is unknown, the config is not filtered out.
        """
        rules = self._routing_rules(config)
        ctx_limit: int | None = None

        if "max_input_tokens" in rules:
            ctx_limit = int(rules["max_input_tokens"])
        else:
            ctx_limit = _BUILTIN_CONTEXT_WINDOWS.get(config.model_name)
            if ctx_limit is None:
                # Try preset lookup as last resort
                try:
                    from src.services.agents.llm_provider_presets import get_model_preset

                    preset = get_model_preset(getattr(config, "provider", ""), config.model_name)
                    if preset and preset.max_input_tokens:
                        ctx_limit = preset.max_input_tokens
                except Exception:
                    pass

        if ctx_limit is None:
            return True  # Unknown context window — don't filter

        # 10% headroom so we don't push right up to the model's hard limit
        return estimated_tokens <= int(ctx_limit * 0.9)


# Module-level singleton
_router = ModelRouter()


def get_router() -> ModelRouter:
    return _router
