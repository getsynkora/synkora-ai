"""
JEV Router — delegates routing decisions to TypeSafe's jev-latest model.

One API call per turn, all questions in parallel:
  - model_tier (choice)  → which AgentLLMConfig to use
  - tool_{name} (noul)   → which tools are needed this turn
  - complexity (score)   → escalation override (expert → always heavy)

Activated by routing_mode = "jev" on the Agent model.
Falls back to IntentClassifier + ModelRouter on any failure.

routing_config["jev"] schema (all keys optional):
  {
    "model": "jev-latest",
    "features": {
      "model_routing": true,    // JEV picks fast|standard|heavy tier
      "tool_filtering": true,   // JEV prunes tool list before LLM sees it
      "intent_routing": true,   // subsumes intent routing (tier = intent)
      "cost_routing": false     // subsumes cost_opt (tier = cost decision)
    },
    "model_tier_map": {
      "fast":     "<AgentLLMConfig UUID>",
      "standard": "<AgentLLMConfig UUID>",
      "heavy":    "<AgentLLMConfig UUID>"
    },
    "tool_filtering_threshold": "yes"   // "yes" | "unclear"
  }
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Maximum tools included in one JEV call.  Tools beyond this cap are excluded
# from filtering questions and always passed through to the LLM.
_MAX_TOOL_QUESTIONS = 50


class JevRoutingError(Exception):
    """Raised when JEV routing fails; signals the caller to fall back."""


class JevRoutingConfig:
    """
    Type-annotated view of routing_config["jev"].

    Not enforced at runtime — the dict is used directly.
    Provided for IDE / type-checker support only.
    """

    model: str  # default "jev-latest"
    features: dict[str, bool]
    model_tier_map: dict[str, str]  # {"fast": "<uuid>", "standard": "<uuid>", "heavy": "<uuid>"}
    tool_filtering_threshold: str  # "yes" | "unclear"


@dataclass
class JevRoutingResult:
    """Result of a single JEV routing call."""

    config_id: str
    """ID of the AgentLLMConfig selected by JEV (or fallback default)."""

    fallback_config_ids: list[str] = field(default_factory=list)
    """Ordered fallback config IDs if the primary is unavailable."""

    allowed_tool_names: set[str] | None = None
    """
    Set of tool names JEV approved for this turn.
    None means tool_filtering was disabled — all tools pass through.
    Empty set means JEV approved zero tools (still respects always_include).
    """

    complexity: str = "moderate"
    """JEV complexity score: trivial | simple | moderate | complex | expert."""

    model_tier: str = "standard"
    """JEV model tier answer: fast | standard | heavy (or whatever tiers are mapped)."""


# ---------------------------------------------------------------------------
# Question builder
# ---------------------------------------------------------------------------


def build_jev_questions(
    features: dict[str, bool],
    tool_list: list[dict[str, Any]],
    model_tier_map: dict[str, str],
) -> dict[str, dict[str, Any]]:
    """
    Build the questions dict for a single TypeSafe evaluate() call.

    Args:
        features:       Feature-flag dict from routing_config["jev"]["features"].
        tool_list:      List of {"name": str, "description": str} dicts from the registry.
        model_tier_map: {"fast": uuid, "standard": uuid, ...} from routing_config.

    Returns:
        Questions dict ready for TypeSafeClient.evaluate().
    """
    questions: dict[str, dict[str, Any]] = {}

    # Model tier — only if routing is enabled and there are mapped tiers to choose from
    if features.get("model_routing", True) and model_tier_map:
        available_tiers = list(model_tier_map.keys())
        if available_tiers:
            questions["model_tier"] = {
                "type": "choice",
                "question": "Which model tier does this query require given the agent's purpose?",
                "options": available_tiers,
            }

    # Per-tool noul questions — capped at _MAX_TOOL_QUESTIONS
    if features.get("tool_filtering", True):
        for tool in tool_list[:_MAX_TOOL_QUESTIONS]:
            desc = (tool.get("description") or "")[:200]  # truncate for payload
            questions[f"tool_{tool['name']}"] = {
                "type": "noul",
                "question": (f"Is the tool '{tool['name']}' needed to answer this query? Tool description: {desc}"),
            }

    # Complexity score — always included; used for escalation override and logging
    questions["complexity"] = {
        "type": "score",
        "question": "How complex is the reasoning or synthesis required to answer this query?",
        "levels": ["trivial", "simple", "moderate", "complex", "expert"],
    }

    return questions


# ---------------------------------------------------------------------------
# Answer parser
# ---------------------------------------------------------------------------


def _extract_answer(answer: Any) -> str:
    """Normalize a single JEV answer value to a plain string."""
    if isinstance(answer, dict):
        # TypeSafe returns {"answer": "yes", "confidence": 0.9, ...} for noul/score
        # and {"choice": "standard", ...} for choice
        return str(answer.get("answer") or answer.get("choice") or "").lower()
    return str(answer).lower()


def parse_jev_answers(
    answers: dict[str, Any],
    features: dict[str, bool],
    tool_list: list[dict[str, Any]],
    model_tier_map: dict[str, str],
    llm_configs: list,  # list[AgentLLMConfig]
    threshold: str = "yes",
) -> JevRoutingResult:
    """
    Parse JEV answers into a JevRoutingResult.

    Escalation override: complexity == "expert" forces the "heavy" tier
    regardless of the model_tier answer.

    Args:
        answers:       Raw "answers" dict from TypeSafeClient.evaluate().
        features:      Feature flags (same as passed to build_jev_questions).
        tool_list:     Same tool_list as build_jev_questions (to know which tools were asked about).
        model_tier_map: Maps tier name → AgentLLMConfig UUID string.
        llm_configs:   All enabled AgentLLMConfig rows for this agent.
        threshold:     "yes" → strict (only "yes" answers pass);
                       "unclear" → permissive ("yes" or "unclear" pass).

    Returns:
        JevRoutingResult
    """
    # ── Complexity ────────────────────────────────────────────────────────
    complexity = _extract_answer(answers.get("complexity", "moderate")) or "moderate"

    # ── Model tier ────────────────────────────────────────────────────────
    model_tier = _extract_answer(answers.get("model_tier", "standard")) or "standard"

    # Escalation override: expert complexity always wakes the heavy model
    if complexity == "expert" and "heavy" in model_tier_map:
        model_tier = "heavy"

    # Map tier → AgentLLMConfig
    config_id: str | None = None
    if features.get("model_routing", True) and model_tier_map:
        target_uuid = model_tier_map.get(model_tier)
        if target_uuid:
            selected = next(
                (c for c in llm_configs if str(c.id) == target_uuid and c.enabled),
                None,
            )
            if selected:
                config_id = str(selected.id)

    # Default config fallback
    if not config_id:
        default = next((c for c in llm_configs if c.is_default and c.enabled), None)
        if default:
            config_id = str(default.id)
        elif llm_configs:
            config_id = str(llm_configs[0].id)

    # Fallback chain: remaining enabled configs that aren't the primary
    fallback_ids = [str(c.id) for c in llm_configs if c.enabled and str(c.id) != config_id]

    # ── Tool filtering ────────────────────────────────────────────────────
    allowed_tool_names: set[str] | None = None

    if features.get("tool_filtering", True):
        allowed: set[str] = set()
        asked_names = {t["name"] for t in tool_list[:_MAX_TOOL_QUESTIONS]}

        for tool in tool_list[:_MAX_TOOL_QUESTIONS]:
            key = f"tool_{tool['name']}"
            if key not in answers:
                # JEV didn't answer this tool — include it (permissive unknown)
                allowed.add(tool["name"])
                continue

            answer_val = _extract_answer(answers[key])

            if threshold == "unclear":
                if answer_val in ("yes", "unclear"):
                    allowed.add(tool["name"])
            else:
                if answer_val == "yes":
                    allowed.add(tool["name"])

        # Tools beyond the cap were not asked about — always include them
        for tool in tool_list[_MAX_TOOL_QUESTIONS:]:
            allowed.add(tool["name"])

        allowed_tool_names = allowed
        logger.debug(
            "[jev-router] tool_filter: %d / %d tools approved (threshold=%s)",
            len(allowed),
            len(asked_names),
            threshold,
        )

    return JevRoutingResult(
        config_id=config_id or "",
        fallback_config_ids=fallback_ids,
        allowed_tool_names=allowed_tool_names,
        complexity=complexity,
        model_tier=model_tier,
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def run_jev_routing(
    db_agent: Any,
    query: str,
    history: list[dict[str, Any]] | None,
    llm_configs: list,
    typesafe_client: Any,
    jev_config: dict[str, Any],
) -> JevRoutingResult:
    """
    Make one JEV API call covering all routing decisions for this turn.

    Args:
        db_agent:         Agent ORM instance (needs .description, .agent_name).
        query:            The user's current message.
        history:          Prior conversation turns (may be None).
        llm_configs:      All enabled AgentLLMConfig rows for this agent.
        typesafe_client:  Initialized TypeSafeClient.
        jev_config:       routing_config["jev"] dict (may be empty).

    Returns:
        JevRoutingResult

    Raises:
        JevRoutingError: on API failure or misconfiguration — caller should fall back.
    """
    # Parse config with defaults
    features: dict[str, bool] = jev_config.get(
        "features",
        {"model_routing": True, "tool_filtering": True},
    )
    model_tier_map: dict[str, str] = jev_config.get("model_tier_map", {})
    threshold: str = jev_config.get("tool_filtering_threshold", "yes")
    jev_model: str = jev_config.get("model", "jev-latest")

    # Fetch tool list from global registry
    try:
        from src.services.agents.adk_tools import get_tool_registry

        all_tools = get_tool_registry().list_tools()
    except Exception as exc:
        logger.warning("[jev-router] Could not read tool registry: %s", exc)
        all_tools = []

    # Build state string for JEV
    history_summary = ""
    if history:
        recent = history[-5:]
        history_summary = " | ".join(f"{m.get('role', '?')}: {str(m.get('content', ''))[:100]}" for m in recent)

    state = (
        f"Agent purpose: {getattr(db_agent, 'description', '') or 'General purpose agent'}\n"
        f"Query: {query}\n"
        f"Conversation turns: {len(history) if history else 0}\n"
        f"Recent history: {history_summary}"
    )

    questions = build_jev_questions(features, all_tools, model_tier_map)

    # Raise early if neither model_routing nor tool_filtering is active
    # (complexity is always included but alone it doesn't make a routing decision)
    if not features.get("model_routing", True) and not features.get("tool_filtering", True):
        raise JevRoutingError("No JEV questions built — all features disabled in jev_config.features")

    logger.debug(
        "[jev-router] agent=%s questions=%d (tools=%d, model_routing=%s)",
        getattr(db_agent, "agent_name", "?"),
        len(questions),
        sum(1 for k in questions if k.startswith("tool_")),
        features.get("model_routing", True),
    )

    try:
        result = await typesafe_client.evaluate(
            state=state,
            questions=questions,
            model=jev_model,
        )
    except Exception as exc:
        raise JevRoutingError(f"TypeSafe API call failed: {exc}") from exc

    if "error" in result:
        raise JevRoutingError(f"JEV API returned error: {result['error']}")

    answers = result.get("answers", {})
    return parse_jev_answers(answers, features, all_tools, model_tier_map, llm_configs, threshold)
