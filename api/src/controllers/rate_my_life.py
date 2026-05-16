"""
Rate My Life Controller — AI Life Audit via Multi-Agent Debate.

Creates a pre-configured War Room debate with 5 specialist AI agents
who score a user's life across 6 dimensions, debate disagreements,
and produce a shareable scorecard.

Agents are real Agent records (auto-provisioned on first use per tenant),
and the debate runs through the standard DebateExecutor.
"""

import logging
import re
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.models.agent import Agent
from src.models.agent_llm_config import AgentLLMConfig
from src.models.debate_session import DebateSession
from src.models.tenant import Account
from src.services.agents.workflows.debate_executor import PARTICIPANT_COLORS, DebateExecutor

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Specialist Agent Definitions ─────────────────────────────────────────────

LIFE_AUDIT_AGENTS = [
    {
        "slug": "life_audit_career_strategist",
        "name": "Career Strategist",
        "description": "Direct, ambitious, data-driven life audit specialist focused on career and financial growth.",
        "system_prompt": (
            "You are the Career Strategist — direct, ambitious, and data-driven. "
            "You believe professional growth and financial security are the foundation "
            "of a fulfilling life. You tend to score Career & Growth and Financial Health "
            "higher when someone is investing in their future, even at the cost of other areas. "
            "You challenge agents who downplay career ambition."
        ),
        "color_index": 0,
    },
    {
        "slug": "life_audit_wellness_coach",
        "name": "Wellness Coach",
        "description": "Warm, holistic, evidence-based life audit specialist focused on physical and mental health.",
        "system_prompt": (
            "You are the Wellness Coach — warm, holistic, and evidence-based. "
            "You believe physical and mental health are non-negotiable foundations "
            "that everything else is built on. You tend to flag burnout risks others miss "
            "and score Physical Health and Mental Wellbeing strictly. You push back when "
            "other agents dismiss health concerns."
        ),
        "color_index": 1,
    },
    {
        "slug": "life_audit_relationship_counselor",
        "name": "Relationship Counselor",
        "description": "Empathetic, insightful, brutally honest life audit specialist focused on relationships.",
        "system_prompt": (
            "You are the Relationship Counselor — empathetic, insightful, and brutally honest. "
            "You believe strong relationships are the single best predictor of life satisfaction. "
            "You score Relationships higher and are skeptical of people who claim to be fine "
            "while isolated. You challenge the Career Strategist when work is clearly damaging relationships."
        ),
        "color_index": 2,
    },
    {
        "slug": "life_audit_life_philosopher",
        "name": "Life Philosopher",
        "description": "Wise, Stoic-inspired life audit specialist focused on meaning and personal growth.",
        "system_prompt": (
            "You are the Life Philosopher — wise, Stoic-inspired, and focused on the big picture. "
            "You care about meaning, purpose, and personal growth above material metrics. "
            "You tend to score Personal Growth higher and ask the deeper 'why' questions. "
            "You challenge surface-level assessments and push for existential honesty."
        ),
        "color_index": 4,
    },
    {
        "slug": "life_audit_synthesizer",
        "name": "The Synthesizer",
        "description": "Balanced, fair, and sharp — synthesizes all specialist scores into a final life verdict.",
        "system_prompt": (
            "You are The Synthesizer — balanced, fair, and sharp. "
            "Your job is to weigh ALL other agents' scores and reasoning, resolve disagreements, "
            "and produce the definitive final assessment. You compute a weighted overall Life Score "
            "and deliver a verdict that acknowledges tensions between dimensions."
        ),
        "is_synthesizer": True,
    },
]

PLATFORM_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")

# ── Request / Response Schemas ───────────────────────────────────────────────


class DimensionAnswer(BaseModel):
    dimension: str
    score: int = Field(ge=1, le=10)
    context: str = ""


class LifeAuditRequest(BaseModel):
    answers: list[DimensionAnswer]


class LifeAuditScores(BaseModel):
    career: float = 0
    financial: float = 0
    physical: float = 0
    mental: float = 0
    relationships: float = 0
    growth: float = 0
    overall: float = 0


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/rate-my-life")
async def create_life_audit(
    request: LifeAuditRequest,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Create a life audit debate session.

    Auto-provisions the 5 specialist agents (if they don't exist yet for
    this tenant), then creates a standard DebateSession and returns the ID.
    """
    if len(request.answers) != 6:
        raise HTTPException(status_code=400, detail="Exactly 6 dimension answers required")

    # 1. Ensure all specialist agents exist for this tenant
    agent_map = await _ensure_life_audit_agents(db, tenant_id)

    # 2. Build questionnaire context
    answers_text = "\n".join(
        f"- {a.dimension}: {a.score}/10" + (f' -- "{a.context}"' if a.context else "") for a in request.answers
    )
    context_text = (
        "The user has completed a life self-assessment questionnaire. "
        "Your task is to analyze their answers, provide your own scores for each "
        "of the 6 life dimensions (1-10), explain your reasoning, and challenge "
        "other agents where you disagree.\n\n"
        f"[User's Self-Assessment]\n{answers_text}\n\n"
        "IMPORTANT: At the end of your response, include a structured scores section "
        "in EXACTLY this format on a single line:\n"
        "[SCORES] Career: X, Financial: X, Physical: X, Mental: X, Relationships: X, Growth: X\n"
        "where X is your score from 1-10 for each dimension."
    )

    # 3. Build participants list from real agent records
    participants = []
    synthesizer_agent_id = None
    for i, defn in enumerate(LIFE_AUDIT_AGENTS):
        agent = agent_map[defn["slug"]]
        if defn.get("is_synthesizer"):
            synthesizer_agent_id = agent.id
            continue
        participants.append(
            {
                "id": str(uuid.uuid4()),
                "agent_id": str(agent.id),
                "agent_name": defn["name"],
                "role": defn["name"],
                "is_external": False,
                "color": PARTICIPANT_COLORS[defn.get("color_index", i) % len(PARTICIPANT_COLORS)],
            }
        )

    share_token = secrets.token_urlsafe(32)

    session = DebateSession(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        topic="Rate My Life: AI Life Audit",
        debate_type="structured",
        rounds=2,
        current_round=0,
        status="pending",
        is_public=True,
        allow_external=False,
        share_token=share_token,
        participants=participants,
        messages=[],
        synthesizer_agent_id=synthesizer_agent_id,
        created_by=current_account.id,
        debate_metadata={
            "type": "life-audit",
            "context": {"type": "text", "text": context_text},
            "answers": [a.model_dump() for a in request.answers],
        },
    )

    db.add(session)
    await db.commit()
    await db.refresh(session)

    return {
        "id": str(session.id),
        "share_token": share_token,
        "status": "pending",
    }


@router.post("/rate-my-life/{audit_id}/stream")
async def stream_life_audit(
    audit_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
):
    """Start the life audit debate. Returns SSE stream via standard DebateExecutor."""
    session = await _get_audit_session(db, audit_id, tenant_id)
    if session.status not in ("pending", "error"):
        raise HTTPException(status_code=400, detail=f"Audit already {session.status}")

    executor = DebateExecutor(db)

    return StreamingResponse(
        executor.execute_debate(session),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/rate-my-life/{audit_id}")
async def get_life_audit(
    audit_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
):
    """Get a completed life audit with parsed scores."""
    session = await _get_audit_session(db, audit_id, tenant_id)
    return _build_audit_result(session)


@router.get("/rate-my-life/history/list")
async def list_life_audits(
    limit: int = Query(20, ge=1, le=100),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
):
    """Get the user's life audit history for progress tracking."""
    result = await db.execute(
        select(DebateSession)
        .filter(
            DebateSession.tenant_id == tenant_id,
            DebateSession.created_by == current_account.id,
            DebateSession.debate_metadata["type"].as_string() == "life-audit",
        )
        .order_by(DebateSession.created_at.desc())
        .limit(limit)
    )
    sessions = result.scalars().all()

    return {"audits": [_build_audit_result(s) for s in sessions]}


@router.get("/rate-my-life/public/{share_token}")
async def get_public_life_audit(
    share_token: str,
    db: AsyncSession = Depends(get_async_db),
):
    """Get a life audit scorecard by share token (no auth required)."""
    result = await db.execute(
        select(DebateSession).filter(
            DebateSession.share_token == share_token,
            DebateSession.is_public.is_(True),
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Life audit not found")

    metadata = session.debate_metadata or {}
    if metadata.get("type") != "life-audit":
        raise HTTPException(status_code=404, detail="Not a life audit")

    return _build_audit_result(session)


# ── Agent Provisioning ───────────────────────────────────────────────────────


async def _ensure_life_audit_agents(
    db: AsyncSession,
    tenant_id: uuid.UUID,
) -> dict[str, Agent]:
    """
    Ensure all 5 life audit specialist agents exist for this tenant.

    Uses the same LLM config inheritance pattern as platform_create_agent:
    copies the Platform Engineer's per-tenant LLM config to new agents.

    Returns a map of slug -> Agent.
    """
    slugs = [d["slug"] for d in LIFE_AUDIT_AGENTS]

    # Check which already exist
    result = await db.execute(
        select(Agent).filter(
            Agent.tenant_id == tenant_id,
            Agent.slug.in_(slugs),
        )
    )
    existing = {a.slug: a for a in result.scalars().all()}

    if len(existing) == len(slugs):
        return existing

    # Get PE's per-tenant LLM config for inheritance
    pe_cfg = await _get_pe_llm_config(db, tenant_id)
    if not pe_cfg:
        raise HTTPException(
            status_code=400,
            detail=(
                "No LLM configuration found. Please configure your Platform Engineer "
                "agent's LLM settings first (Settings > Platform Engineer > LLM Config)."
            ),
        )

    for defn in LIFE_AUDIT_AGENTS:
        if defn["slug"] in existing:
            continue

        agent = Agent(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            agent_name=defn["slug"],
            slug=defn["slug"],
            agent_type="LLM",
            description=defn["description"],
            system_prompt=defn["system_prompt"],
            llm_config={
                "provider": pe_cfg.provider,
                "model_name": pe_cfg.model_name,
                "temperature": 0.8,
                "max_tokens": 4096,
                "api_key": pe_cfg.api_key,
                "api_base": pe_cfg.api_base,
            },
            tools_config=[],
            agent_metadata={"is_life_audit_agent": True},
            status="ACTIVE",
            is_public=False,
            category="Life Audit",
            tags=["life-audit", "rate-my-life"],
            execution_count=0,
            success_count=0,
        )
        db.add(agent)
        await db.flush()

        # Create AgentLLMConfig row (same pattern as platform_create_agent)
        llm_cfg = AgentLLMConfig(
            id=uuid.uuid4(),
            agent_id=agent.id,
            tenant_id=tenant_id,
            name=f"Primary {pe_cfg.model_name}",
            provider=pe_cfg.provider,
            model_name=pe_cfg.model_name,
            api_key=pe_cfg.api_key,
            api_base=pe_cfg.api_base,
            temperature=0.8,
            max_tokens=4096,
            top_p=pe_cfg.top_p if pe_cfg.top_p is not None else 1.0,
            additional_params=pe_cfg.additional_params or {},
            is_default=True,
            display_order=0,
            enabled=True,
        )
        db.add(llm_cfg)
        existing[defn["slug"]] = agent

    await db.commit()
    return existing


async def _get_pe_llm_config(db: AsyncSession, tenant_id: uuid.UUID) -> AgentLLMConfig | None:
    """Get the Platform Engineer agent's per-tenant LLM config."""
    pe_agent = (
        await db.execute(
            select(Agent).where(
                Agent.agent_name == "platform_engineer_agent",
                Agent.tenant_id == PLATFORM_TENANT_ID,
            )
        )
    ).scalar_one_or_none()
    if not pe_agent:
        return None

    return (
        await db.execute(
            select(AgentLLMConfig)
            .where(
                AgentLLMConfig.agent_id == pe_agent.id,
                AgentLLMConfig.tenant_id == tenant_id,
                AgentLLMConfig.enabled.is_(True),
            )
            .limit(1)
        )
    ).scalar_one_or_none()


# ── Score Parsing ────────────────────────────────────────────────────────────

SCORE_PATTERN = re.compile(
    r"\[SCORES\]\s*"
    r"Career:\s*(\d+),?\s*"
    r"Financial:\s*(\d+),?\s*"
    r"Physical:\s*(\d+),?\s*"
    r"Mental:\s*(\d+),?\s*"
    r"Relationships:\s*(\d+),?\s*"
    r"Growth:\s*(\d+)"
    r"(?:,?\s*Overall:\s*(\d+))?",
    re.IGNORECASE,
)


def _parse_scores_from_message(content: str) -> dict[str, int] | None:
    """Extract structured scores from an agent's message."""
    match = SCORE_PATTERN.search(content)
    if not match:
        return None
    scores = {
        "career": int(match.group(1)),
        "financial": int(match.group(2)),
        "physical": int(match.group(3)),
        "mental": int(match.group(4)),
        "relationships": int(match.group(5)),
        "growth": int(match.group(6)),
    }
    if match.group(7):
        scores["overall"] = int(match.group(7))
    return {k: max(1, min(10, v)) for k, v in scores.items()}


def _extract_highlight_quote(content: str, max_len: int = 200) -> str:
    """Extract a compelling quote from agent content."""
    for line in content.split("\n"):
        line = line.strip()
        if line and not line.startswith("[SCORES]") and len(line) > 30:
            return line[:max_len] + ("..." if len(line) > max_len else "")
    return content[:max_len]


def _build_audit_result(session: DebateSession) -> dict:
    """Build a life audit result from a debate session with parsed scores."""
    metadata = session.debate_metadata or {}
    answers = metadata.get("answers", [])

    messages = session.messages or []
    all_scores: list[dict[str, int]] = []
    highlights: list[dict] = []

    dim_labels = {
        "career": "Career & Growth",
        "financial": "Financial Health",
        "physical": "Physical Health",
        "mental": "Mental Wellbeing",
        "relationships": "Relationships",
        "growth": "Personal Growth",
    }

    for msg in messages:
        if msg.get("is_verdict"):
            continue
        scores = _parse_scores_from_message(msg.get("content", ""))
        if scores:
            all_scores.append(scores)
            dims = list(dim_labels.keys())
            best_dim = max(dims, key=lambda d: scores.get(d, 0))
            highlights.append(
                {
                    "agent_name": msg.get("agent_name", ""),
                    "dimension": dim_labels.get(best_dim, best_dim),
                    "quote": _extract_highlight_quote(msg.get("content", "")),
                    "score": scores.get(best_dim, 0),
                }
            )

    # Prefer synthesizer scores, fall back to agent average
    verdict_scores = _parse_scores_from_message(session.verdict) if session.verdict else None

    final = LifeAuditScores()
    dims = ["career", "financial", "physical", "mental", "relationships", "growth"]

    if verdict_scores:
        for d in dims:
            setattr(final, d, verdict_scores.get(d, 0))
        final.overall = verdict_scores.get(
            "overall",
            round(sum(getattr(final, d) for d in dims) / 6, 1),
        )
    elif all_scores:
        for d in dims:
            setattr(final, d, round(sum(s.get(d, 0) for s in all_scores) / len(all_scores), 1))
        final.overall = round(sum(getattr(final, d) for d in dims) / 6, 1)

    return {
        "id": str(session.id),
        "status": session.status,
        "scores": final.model_dump(),
        "agent_highlights": highlights,
        "verdict": session.verdict,
        "share_token": session.share_token,
        "created_at": session.created_at.isoformat() if session.created_at else "",
        "answers": answers,
    }


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _get_audit_session(db: AsyncSession, audit_id: uuid.UUID, tenant_id: uuid.UUID) -> DebateSession:
    result = await db.execute(
        select(DebateSession).filter(
            DebateSession.id == audit_id,
            DebateSession.tenant_id == tenant_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Life audit not found")
    return session
