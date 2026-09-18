"""
TypeSafe AI Evaluation Tools Registry

Registers internal_typesafe_evaluate, internal_typesafe_evaluate_profile, and
internal_format_evaluation_report with the ADK tool registry.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

_VALID_PROFILES = ["recruiting", "content_moderation", "lead_scoring", "support_triage"]


def register_typesafe_tools(registry) -> None:
    """Register all TypeSafe AI evaluation tools with the ADK tool registry."""

    from src.services.agents.internal_tools.typesafe_tools import (
        internal_format_evaluation_report,
        internal_typesafe_evaluate,
        internal_typesafe_evaluate_profile,
    )

    # ------------------------------------------------------------------
    # internal_typesafe_evaluate
    # ------------------------------------------------------------------

    async def _evaluate_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_typesafe_evaluate(
            state=kwargs.get("state", ""),
            questions=kwargs.get("questions", {}),
            model=kwargs.get("model"),
            config=config,
            runtime_context=runtime_context,
        )

    registry.register_tool(
        name="internal_typesafe_evaluate",
        description="""Evaluate any text against custom structured questions using TypeSafe AI (Jev model).
All questions run in parallel in a single API call — fast and cost-efficient.

Use this tool when you need to make structured judgments about text content and the built-in profiles don't cover your exact use case.

Supported question types:
- noul:   Yes/No with a 0–1 probability  {"type":"noul","question":"Is this X?"}
- choice: Select from options with probabilities  {"type":"choice","question":"Which?","options":["a","b","c"]}
- score:  Rate on an ordered scale  {"type":"score","question":"How?","levels":["low","medium","high"]}

Example questions dict for evaluating a support ticket:
{
  "is_urgent":  {"type":"noul",   "question":"Is this a time-sensitive issue?"},
  "intent":     {"type":"choice", "question":"What does the customer want?", "options":["refund","info","cancel","escalate"]},
  "sentiment":  {"type":"score",  "question":"How negative is the sentiment?", "levels":["positive","neutral","frustrated","angry"]}
}

IMPORTANT: Configure TypeSafe AI first via Settings → Integrations → AI Evaluation.""",
        parameters={
            "type": "object",
            "properties": {
                "state": {
                    "type": "string",
                    "description": "The text content to evaluate (resume, message, document, form submission, etc.)",
                },
                "questions": {
                    "type": "object",
                    "description": (
                        "Dict of {answer_key: question_definition}. Each value is an object with:\n"
                        "  - type: 'noul' | 'choice' | 'score'\n"
                        "  - question: the evaluation instruction\n"
                        "  - options: list of strings (choice only)\n"
                        "  - levels: list of strings, low-to-high (score only)"
                    ),
                },
                "model": {
                    "type": "string",
                    "description": "Override the TypeSafe model (default: jev-latest)",
                },
            },
            "required": ["state", "questions"],
        },
        function=_evaluate_wrapper,
    )

    # ------------------------------------------------------------------
    # internal_typesafe_evaluate_profile
    # ------------------------------------------------------------------

    async def _profile_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_typesafe_evaluate_profile(
            state=kwargs.get("state", ""),
            profile=kwargs.get("profile", ""),
            extra_context=kwargs.get("extra_context", ""),
            model=kwargs.get("model"),
            config=config,
            runtime_context=runtime_context,
        )

    registry.register_tool(
        name="internal_typesafe_evaluate_profile",
        description="""Evaluate text using a pre-built TypeSafe AI evaluation profile.
Fires all profile questions in a single parallel API call.

Available profiles:
- recruiting         Evaluate resumes/applications: meets_minimum, experience_fit, competency_score, role_match, routing, needs_human_review, evaluation_confidence
- content_moderation Detect policy violations: is_harmful, policy_violation, severity, violation_type, recommended_action
- lead_scoring       Score and route leads: icp_fit, buyer_intent, has_urgency, pain_point_match, routing, priority
- support_triage     Triage support tickets: primary_intent, urgency, frustration_level, churn_risk, routing, needs_immediate_human

The extra_context string is injected into relevant questions to make evaluations specific.
For recruiting, pass the job description. For lead_scoring, pass the ICP definition. For moderation, pass the policy rules.

IMPORTANT: Configure TypeSafe AI first via Settings → Integrations → AI Evaluation.""",
        parameters={
            "type": "object",
            "properties": {
                "state": {
                    "type": "string",
                    "description": "The text to evaluate (resume text, lead profile, support message, social post, etc.)",
                },
                "profile": {
                    "type": "string",
                    "enum": _VALID_PROFILES,
                    "description": "The evaluation profile to use",
                },
                "extra_context": {
                    "type": "string",
                    "description": (
                        "Context injected into profile questions. Strongly recommended — specificity improves accuracy.\n"
                        "- recruiting: paste the full job description and required competencies\n"
                        "- lead_scoring: paste your ICP definition and the problem you solve\n"
                        "- content_moderation: paste relevant policy rules\n"
                        "- support_triage: paste product/tier context if needed"
                    ),
                },
                "model": {
                    "type": "string",
                    "description": "Override the TypeSafe model (default: jev-latest)",
                },
            },
            "required": ["state", "profile"],
        },
        function=_profile_wrapper,
    )

    # ------------------------------------------------------------------
    # internal_format_evaluation_report
    # ------------------------------------------------------------------

    async def _report_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_format_evaluation_report(
            evaluation_data=kwargs.get("evaluation_data", {}),
            title=kwargs.get("title", "Evaluation Report"),
            config=config,
            runtime_context=runtime_context,
        )

    registry.register_tool(
        name="internal_format_evaluation_report",
        description="""Format TypeSafe AI evaluation output into a clean markdown report.

Works with output from both internal_typesafe_evaluate and internal_typesafe_evaluate_profile.
The report includes:
- All answers with visual probability bars for choice questions
- Yes/No with confidence for noul questions
- Score level with confidence for score questions
- An Action Summary section highlighting routing decisions and escalation flags
- Token usage footer

USAGE: Call this AFTER getting evaluation results. Pass the complete result dict as evaluation_data.""",
        parameters={
            "type": "object",
            "properties": {
                "evaluation_data": {
                    "type": "object",
                    "description": "The complete result dict returned by internal_typesafe_evaluate or internal_typesafe_evaluate_profile",
                },
                "title": {
                    "type": "string",
                    "description": "Report title/heading (default: 'Evaluation Report')",
                },
            },
            "required": ["evaluation_data"],
        },
        function=_report_wrapper,
    )

    logger.info("Registered 3 TypeSafe AI evaluation tools")
