"""
TypeSafe AI Evaluation Tools for Synkora Agents.

Three tools backed by TypeSafe's Jev model (/v1/systemone):

  internal_typesafe_evaluate         — fully generic, agent defines questions
  internal_typesafe_evaluate_profile — named profiles for common domains
  internal_format_evaluation_report  — formats any evaluation output as markdown

Credentials are resolved per-tenant from IntegrationConfig
(integration_type="ai_evaluation", provider="typesafe").
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pre-built evaluation profiles
# ---------------------------------------------------------------------------

# Placeholder token injected into profile question instructions
_CTX = "{extra_context}"

EVALUATION_PROFILES: dict[str, dict[str, dict[str, Any]]] = {
    "recruiting": {
        "meets_minimum": {
            "type": "noul",
            "question": f"Does this candidate meet the minimum qualifications for the role? {_CTX}",
        },
        "experience_fit": {
            "type": "choice",
            "question": f"How would you categorize the candidate's experience level for this role? {_CTX}",
            "options": ["exceeds_requirements", "meets_requirements", "partially_meets", "does_not_meet"],
        },
        "competency_score": {
            "type": "score",
            "question": f"How strongly does the candidate demonstrate the required skills and competencies? {_CTX}",
            "levels": ["weak", "developing", "proficient", "strong", "exceptional"],
        },
        "role_match": {
            "type": "score",
            "question": f"How well does this candidate match the overall role requirements? {_CTX}",
            "levels": ["poor", "fair", "good", "strong", "excellent"],
        },
        "routing": {
            "type": "choice",
            "question": "Based on this evaluation, who should review this candidate next?",
            "options": ["hiring_manager", "technical_recruiter", "technical_screen", "reject_politely"],
        },
        "needs_human_review": {
            "type": "noul",
            "question": "Is this a borderline or ambiguous case that requires human judgment before a decision?",
        },
        "evaluation_confidence": {
            "type": "score",
            "question": "How confident are you in this evaluation given the available information?",
            "levels": ["very_low", "low", "moderate", "high", "very_high"],
        },
    },
    "content_moderation": {
        "is_harmful": {
            "type": "noul",
            "question": "Does this content contain harmful, abusive, threatening, or dangerous material?",
        },
        "policy_violation": {
            "type": "noul",
            "question": f"Does this content violate community standards or platform policies? {_CTX}",
        },
        "severity": {
            "type": "score",
            "question": "How severe is the policy concern in this content?",
            "levels": ["none", "minor", "moderate", "severe", "critical"],
        },
        "violation_type": {
            "type": "choice",
            "question": "What type of policy violation does this content contain, if any?",
            "options": [
                "none",
                "spam",
                "hate_speech",
                "harassment",
                "misinformation",
                "adult_content",
                "violence",
                "other",
            ],
        },
        "recommended_action": {
            "type": "choice",
            "question": "What moderation action should be taken on this content?",
            "options": ["allow", "flag_for_review", "warn_user", "remove", "ban_user"],
        },
    },
    "lead_scoring": {
        "icp_fit": {
            "type": "score",
            "question": f"How well does this lead match the ideal customer profile? {_CTX}",
            "levels": ["very_poor", "poor", "fair", "good", "excellent"],
        },
        "buyer_intent": {
            "type": "score",
            "question": "How strong are the buying intent signals in this lead information?",
            "levels": ["none", "low", "moderate", "high", "very_high"],
        },
        "has_urgency": {
            "type": "noul",
            "question": "Is there urgency or a clear time pressure in this lead's situation?",
        },
        "pain_point_match": {
            "type": "noul",
            "question": f"Does the lead's described pain point clearly match what we solve? {_CTX}",
        },
        "routing": {
            "type": "choice",
            "question": "Who should handle this lead next?",
            "options": ["account_executive", "sales_rep", "sdr_nurture", "disqualify"],
        },
        "priority": {
            "type": "score",
            "question": "What priority level should this lead be assigned?",
            "levels": ["low", "medium", "high", "urgent"],
        },
    },
    "support_triage": {
        "primary_intent": {
            "type": "choice",
            "question": "What is the customer's primary intent or request type?",
            "options": [
                "refund_request",
                "technical_issue",
                "billing_inquiry",
                "feature_request",
                "complaint",
                "general_question",
                "cancellation",
            ],
        },
        "urgency": {
            "type": "score",
            "question": "How urgent is this support request?",
            "levels": ["low", "medium", "high", "critical"],
        },
        "frustration_level": {
            "type": "score",
            "question": "How frustrated or upset does the customer appear to be?",
            "levels": ["calm", "mildly_concerned", "frustrated", "very_frustrated", "extremely_upset"],
        },
        "churn_risk": {
            "type": "noul",
            "question": "Are there signals that this customer may cancel or churn if not helped promptly?",
        },
        "routing": {
            "type": "choice",
            "question": "Which support team or queue should handle this request?",
            "options": ["tier1_general", "tier2_technical", "billing_team", "retention_team", "manager_escalation"],
        },
        "needs_immediate_human": {
            "type": "noul",
            "question": "Does this request require immediate human intervention rather than automated handling?",
        },
    },
}

VALID_PROFILES = sorted(EVALUATION_PROFILES.keys())


# ---------------------------------------------------------------------------
# Credential helper
# ---------------------------------------------------------------------------


async def _get_client(runtime_context: Any):
    """Return a TypeSafeClient for this tenant or None if not configured."""
    if not runtime_context:
        return None
    try:
        from src.core.typesafe_client import make_typesafe_client
        from src.services.agents.credential_resolver import CredentialResolver

        resolver = CredentialResolver(runtime_context)
        credentials = await resolver.get_typesafe_credentials()
        if not credentials:
            return None
        return make_typesafe_client(credentials)
    except Exception as exc:
        logger.error("Failed to build TypeSafe client: %s", exc, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Report formatter helpers
# ---------------------------------------------------------------------------


def _bar(probability: float, width: int = 10) -> str:
    filled = round(probability * width)
    return "█" * filled + "░" * (width - filled)


def _format_answer(key: str, answer: dict[str, Any]) -> str:
    a_type = answer.get("type", "")
    lines = []

    if a_type == "noul":
        prob = answer.get("noul", 0.5)
        icon = "✓" if prob >= 0.5 else "✗"
        label = "Yes" if prob >= 0.5 else "No"
        lines.append(f"**{key}**: {icon} {label} `({prob:.0%})`")

    elif a_type == "choice":
        choice = answer.get("choice", "—")
        confidence = answer.get("confidence", 0.0)
        lines.append(f"**{key}**: `{choice}` ({confidence:.0%} confident)")
        probs = answer.get("probabilities") or {}
        if probs:
            sorted_probs = sorted(probs.items(), key=lambda x: x[1], reverse=True)[:5]
            for opt, p in sorted_probs:
                lines.append(f"  {_bar(p)} {opt}: {p:.0%}")

    elif a_type == "score":
        score = answer.get("score", 0.0)
        confidence = answer.get("confidence", 0.0)
        legend = answer.get("legend") or {}
        # Find the label for the score if legend is provided
        level_label = ""
        if legend and isinstance(legend, dict):
            # legend maps label -> threshold value; find closest
            by_value = sorted(legend.items(), key=lambda x: float(x[1]) if isinstance(x[1], (int, float)) else 0)
            for label, threshold in reversed(by_value):
                if score >= float(threshold) if isinstance(threshold, (int, float)) else True:
                    level_label = f" — *{label}*"
                    break
        lines.append(f"**{key}**: {score:.2f}{level_label} ({confidence:.0%} confident)")

    else:
        lines.append(f"**{key}**: {answer}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


async def internal_typesafe_evaluate(
    state: str,
    questions: dict[str, dict[str, Any]],
    model: str | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """
    Evaluate any text against a set of custom questions using TypeSafe Jev.

    All questions are evaluated in parallel in a single API call.

    Args:
        state:     The text to evaluate (resume, message, document, …)
        questions: Dict of {answer_key: question_definition}. Each question is:
                     Noul:   {"type": "noul",   "question": "Is this X?"}
                     Choice: {"type": "choice", "question": "Which?", "options": ["a","b","c"]}
                     Score:  {"type": "score",  "question": "How?",   "levels": ["low","mid","high"]}
        model:     Override the model (default: jev-latest)

    Returns:
        {
          "success": bool,
          "model": str,
          "answers": {key: {type, noul|choice|score, probabilities?, confidence?, …}},
          "usage": {"input_tokens": int, "output_tokens": int},
          "error": str   # only on failure
        }
    """
    if not state or not state.strip():
        return {"success": False, "error": "state cannot be empty", "answers": {}}

    if not questions:
        return {"success": False, "error": "questions cannot be empty", "answers": {}}

    client = await _get_client(runtime_context)
    if client is None:
        return {
            "success": False,
            "error": (
                "TypeSafe AI is not configured for this tenant. "
                "Go to Settings → Integrations → AI Evaluation and add your TypeSafe API key."
            ),
            "answers": {},
        }

    if model:
        client._default_model = model

    result = await client.evaluate(state=state, questions=questions)

    if "error" in result:
        return {"success": False, **result}

    return {
        "success": True,
        "model": result.get("model", ""),
        "answers": result.get("answers", {}),
        "usage": result.get("usage", {}),
    }


async def internal_typesafe_evaluate_profile(
    state: str,
    profile: str,
    extra_context: str = "",
    model: str | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """
    Evaluate text using a pre-built evaluation profile.

    Available profiles:
      - recruiting         Evaluate resumes/applications against job criteria
      - content_moderation Detect policy violations, harmful content, and recommended actions
      - lead_scoring       Score and route sales leads by ICP fit, intent, and urgency
      - support_triage     Classify, prioritize, and route support tickets

    Args:
        state:         The text to evaluate
        profile:       Profile name (see above)
        extra_context: Context injected into profile questions (e.g. job description,
                       company policy, ICP definition). Highly recommended — the more
                       specific the context, the more accurate the evaluation.
        model:         Override the model (default: jev-latest)

    Returns:
        Same shape as internal_typesafe_evaluate, plus:
        {
          "profile": str,
          "extra_context": str
        }
    """
    if not state or not state.strip():
        return {"success": False, "error": "state cannot be empty", "answers": {}}

    if profile not in EVALUATION_PROFILES:
        return {
            "success": False,
            "error": f"Unknown profile '{profile}'. Valid profiles: {', '.join(VALID_PROFILES)}",
            "answers": {},
        }

    # Build questions, injecting extra_context into placeholders
    raw_questions = EVALUATION_PROFILES[profile]
    questions: dict[str, dict[str, Any]] = {}
    for key, q in raw_questions.items():
        q_copy = dict(q)
        if extra_context and _CTX in q_copy.get("question", ""):
            q_copy["question"] = q_copy["question"].replace(_CTX, f"\nContext: {extra_context}")
        else:
            q_copy["question"] = q_copy["question"].replace(_CTX, "").strip()
        questions[key] = q_copy

    result = await internal_typesafe_evaluate(
        state=state,
        questions=questions,
        model=model,
        config=config,
        runtime_context=runtime_context,
    )

    result["profile"] = profile
    result["extra_context"] = extra_context
    return result


async def internal_format_evaluation_report(
    evaluation_data: dict[str, Any],
    title: str = "Evaluation Report",
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """
    Format evaluation output from internal_typesafe_evaluate or
    internal_typesafe_evaluate_profile into a readable markdown report.

    Works for any profile or custom question set.

    Args:
        evaluation_data: The dict returned by either evaluate tool
        title:           Report heading (default: "Evaluation Report")

    Returns:
        {
          "success": bool,
          "report": str,   # markdown-formatted report
          "error": str     # only on failure
        }
    """
    if not evaluation_data:
        return {"success": False, "error": "evaluation_data is empty", "report": ""}

    if not evaluation_data.get("success"):
        error = evaluation_data.get("error", "Evaluation failed")
        return {"success": False, "error": error, "report": f"**Error:** {error}"}

    answers: dict[str, Any] = evaluation_data.get("answers", {})
    profile = evaluation_data.get("profile", "")
    model = evaluation_data.get("model", "jev-latest")
    usage = evaluation_data.get("usage", {})

    lines = [f"# {title}", ""]

    if profile:
        lines += [f"**Profile:** `{profile}`", ""]

    if not answers:
        lines += ["*No answers returned.*", ""]
    else:
        lines += ["## Results", ""]
        for key, answer in answers.items():
            lines.append(_format_answer(key, answer))
            lines.append("")

    # Summary section for routing/escalation fields if present
    routing_keys = [k for k in answers if "routing" in k.lower()]
    escalation_keys = [k for k in answers if any(w in k.lower() for w in ["human", "escalat", "review", "urgent"])]

    if routing_keys or escalation_keys:
        lines += ["## Action Summary", ""]
        for k in routing_keys:
            a = answers[k]
            choice = a.get("choice", "—")
            lines.append(f"- **Route to:** `{choice}`")
        for k in escalation_keys:
            a = answers[k]
            if a.get("type") == "noul":
                if a.get("noul", 0) >= 0.6:
                    lines.append(f"- **⚠ Human review recommended** ({a.get('noul', 0):.0%} confidence)")
            elif a.get("type") == "score":
                score = a.get("score", 0)
                levels = ["low", "medium", "high", "critical", "urgent"]
                high_levels = levels[len(levels) // 2 :]
                if any(lvl in str(a.get("legend", {})).lower() for lvl in high_levels) or score > 0.6:
                    lines.append(f"- **⚠ High urgency detected** (score: {score:.2f})")
        lines.append("")

    # Footer
    if usage:
        in_tok = usage.get("input_tokens", 0)
        out_tok = usage.get("output_tokens", 0)
        lines += ["---", f"*Model: {model} · {in_tok} input / {out_tok} output tokens*", ""]

    return {"success": True, "report": "\n".join(lines)}
