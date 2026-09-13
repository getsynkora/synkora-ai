"""
AI War Room Controller — Multi-agent debate endpoints.

Provides CRUD for debate sessions, real-time debate streaming,
external agent participation, and public spectator access.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import secrets
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import PlainTextResponse

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.models.agent import Agent
from src.models.debate_session import DebateSession
from src.models.tenant import Account
from src.schemas.debate import (
    DebateCreateRequest,
    DebateJoinRequest,
    DebateListItem,
    DebateRespondRequest,
    DebateUpdateRequest,
    public_participants,
)
from src.services.agents.workflows.debate_executor import PARTICIPANT_COLORS, DebateExecutor

logger = logging.getLogger(__name__)

router = APIRouter()
public_router = APIRouter()

# ── Templates ─────────────────────────────────────────────────────────────────

DEBATE_TEMPLATES = [
    {
        "id": "tech-strategy",
        "name": "Technology Strategy",
        "description": "Debate the best technical approach for a problem",
        "topic_template": "What is the best approach for {topic}?",
        "suggested_roles": ["Advocate", "Critic", "Pragmatist"],
    },
    {
        "id": "product-decision",
        "name": "Product Decision",
        "description": "Multi-perspective analysis of a product decision",
        "topic_template": "Should we {topic}?",
        "suggested_roles": ["Product", "Engineering", "Business"],
    },
    {
        "id": "open-debate",
        "name": "Open Debate",
        "description": "Free-form debate on any topic",
        "topic_template": "{topic}",
        "suggested_roles": ["For", "Against"],
    },
    {
        "id": "code-review",
        "name": "Architecture Review",
        "description": "Agents debate architectural approaches",
        "topic_template": "Evaluate the trade-offs of {topic}",
        "suggested_roles": ["Monolith Advocate", "Microservices Advocate", "Moderator"],
    },
    {
        "id": "pr-review",
        "name": "PR Review",
        "description": "Multi-agent review of a GitHub Pull Request",
        "topic_template": "Review this Pull Request: {topic}",
        "suggested_roles": ["Security Reviewer", "Performance Critic", "Code Quality", "Architecture"],
        "context_type": "github_pr",
    },
    {
        "id": "life-audit",
        "name": "Rate My Life",
        "description": "5 specialist AI agents score your life across 6 dimensions and debate disagreements",
        "topic_template": "Rate My Life: AI Life Audit",
        "suggested_roles": [
            "Career Strategist",
            "Wellness Coach",
            "Relationship Counselor",
            "Life Philosopher",
            "The Synthesizer",
        ],
        "context_type": "life-audit",
    },
]


@router.get("/war-room/templates")
async def get_templates(
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_account: Account = Depends(get_current_account),
):
    """Get available debate templates."""
    return {"templates": DEBATE_TEMPLATES}


@router.post("/war-room/fetch-pr")
async def fetch_pr_info(
    request: dict,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_account: Account = Depends(get_current_account),
):
    """Fetch GitHub PR information from a URL for debate context."""
    url = request.get("url", "")

    # Parse GitHub PR URL: https://github.com/owner/repo/pull/123
    import re

    match = re.match(r"https?://github\.com/([^/]+/[^/]+)/pull/(\d+)", url)
    if not match:
        raise HTTPException(
            status_code=400,
            detail="Invalid GitHub PR URL. Expected format: https://github.com/owner/repo/pull/123",
        )

    repo_full_name = match.group(1)
    pr_number = int(match.group(2))

    # Fetch PR info from GitHub API (public repos, no auth needed)
    import httpx

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Fetch PR details
            pr_resp = await client.get(
                f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}",
                headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "AI-Agent/1.0"},
            )
            if pr_resp.status_code == 404:
                raise HTTPException(status_code=404, detail="PR not found. It may be private or doesn't exist.")
            pr_resp.raise_for_status()
            pr_data = pr_resp.json()

            # Fetch diff
            diff_resp = await client.get(
                f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}",
                headers={"Accept": "application/vnd.github.v3.diff", "User-Agent": "AI-Agent/1.0"},
            )
            diff_text = diff_resp.text if diff_resp.status_code == 200 else ""

            # Truncate diff to 50K chars to avoid overwhelming LLM context
            if len(diff_text) > 50000:
                diff_text = diff_text[:50000] + "\n\n... (diff truncated, too large to display fully)"

            # Fetch files changed
            files_resp = await client.get(
                f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/files",
                headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "AI-Agent/1.0"},
            )
            files_data = files_resp.json() if files_resp.status_code == 200 else []
            files_changed = [f.get("filename", "") for f in files_data] if isinstance(files_data, list) else []
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"GitHub API error: {e.response.status_code}")
    except httpx.RequestError as e:
        logger.error(f"Failed to reach GitHub API: {e}")
        raise HTTPException(status_code=502, detail="Failed to reach GitHub API")

    return {
        "repo_full_name": repo_full_name,
        "pr_number": pr_number,
        "pr_title": pr_data.get("title", ""),
        "pr_description": pr_data.get("body", "") or "",
        "pr_author": pr_data.get("user", {}).get("login", ""),
        "pr_base_branch": pr_data.get("base", {}).get("ref", ""),
        "pr_head_branch": pr_data.get("head", {}).get("ref", ""),
        "pr_diff": diff_text,
        "pr_files_changed": files_changed,
        "additions": pr_data.get("additions", 0),
        "deletions": pr_data.get("deletions", 0),
        "changed_files": pr_data.get("changed_files", 0),
        "state": pr_data.get("state", ""),
        "mergeable": pr_data.get("mergeable"),
        "html_url": pr_data.get("html_url", url),
    }


@router.post("/war-room/debates")
async def create_debate(
    request: DebateCreateRequest,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
):
    """Create a new debate session."""
    # Verify all participant agents exist and belong to tenant
    participants = []
    for i, p in enumerate(request.participants):
        result = await db.execute(select(Agent).filter(Agent.id == p.agent_id, Agent.tenant_id == tenant_id))
        agent = result.scalar_one_or_none()
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent {p.agent_id} not found")

        participants.append(
            {
                "id": str(uuid.uuid4()),
                "agent_id": str(p.agent_id),
                "agent_name": agent.agent_name,
                "role": p.role,
                "is_external": False,
                "color": PARTICIPANT_COLORS[i % len(PARTICIPANT_COLORS)],
            }
        )

    # Verify synthesizer if specified
    if request.synthesizer_agent_id:
        result = await db.execute(
            select(Agent).filter(Agent.id == request.synthesizer_agent_id, Agent.tenant_id == tenant_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Synthesizer agent not found")

    share_token = secrets.token_urlsafe(32) if request.is_public else None

    session = DebateSession(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        topic=request.topic,
        debate_type=request.debate_type,
        rounds=request.rounds,
        current_round=0,
        status="pending",
        is_public=request.is_public,
        allow_external=request.allow_external,
        share_token=share_token,
        participants=participants,
        messages=[],
        synthesizer_agent_id=request.synthesizer_agent_id,
        created_by=current_account.id,
    )
    # Store context in debate_metadata
    if request.context:
        session.debate_metadata = {"context": request.context.model_dump(exclude_none=True)}

    db.add(session)
    await db.commit()
    await db.refresh(session)

    return _session_to_schema(session, requesting_account_id=current_account.id)


@router.get("/war-room/debates")
async def list_debates(
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
):
    """List debate sessions for the tenant."""
    query = select(DebateSession).filter(DebateSession.tenant_id == tenant_id)
    if status:
        query = query.filter(DebateSession.status == status)
    query = query.order_by(DebateSession.created_at.desc()).limit(limit)

    result = await db.execute(query)
    sessions = result.scalars().all()

    return {
        "debates": [
            DebateListItem(
                id=str(s.id),
                topic=s.topic,
                debate_type=s.debate_type,
                rounds=s.rounds,
                current_round=s.current_round,
                status=s.status,
                participant_count=len(s.participants or []),
                is_public=s.is_public,
                created_at=s.created_at.isoformat() if s.created_at else "",
            )
            for s in sessions
        ]
    }


@router.get("/war-room/debates/{debate_id}")
async def get_debate(
    debate_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
):
    """Get debate session details."""
    session = await _get_debate_session(db, debate_id, tenant_id)
    return _session_to_schema(session, requesting_account_id=current_account.id)


@router.put("/war-room/debates/{debate_id}")
async def update_debate(
    debate_id: uuid.UUID,
    request: DebateUpdateRequest,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
):
    """Update a pending debate session."""
    session = await _get_debate_session(db, debate_id, tenant_id)
    if session.status != "pending":
        raise HTTPException(status_code=400, detail="Can only edit pending debates")

    if request.topic is not None:
        session.topic = request.topic
    if request.debate_type is not None:
        session.debate_type = request.debate_type
    if request.rounds is not None:
        session.rounds = request.rounds
    if request.is_public is not None:
        session.is_public = request.is_public
        if request.is_public and not session.share_token:
            session.share_token = secrets.token_urlsafe(32)
    if request.allow_external is not None:
        session.allow_external = request.allow_external

    if request.participants is not None:
        participants = []
        for i, p in enumerate(request.participants):
            result = await db.execute(select(Agent).filter(Agent.id == p.agent_id, Agent.tenant_id == tenant_id))
            agent = result.scalar_one_or_none()
            if not agent:
                raise HTTPException(status_code=404, detail=f"Agent {p.agent_id} not found")
            participants.append(
                {
                    "id": str(uuid.uuid4()),
                    "agent_id": str(p.agent_id),
                    "agent_name": agent.agent_name,
                    "role": p.role,
                    "is_external": False,
                    "color": PARTICIPANT_COLORS[i % len(PARTICIPANT_COLORS)],
                }
            )
        session.participants = participants

    if request.synthesizer_agent_id is not None:
        result = await db.execute(
            select(Agent).filter(Agent.id == request.synthesizer_agent_id, Agent.tenant_id == tenant_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Synthesizer agent not found")
        session.synthesizer_agent_id = request.synthesizer_agent_id

    if request.context is not None:
        session.debate_metadata = {"context": request.context.model_dump(exclude_none=True)}

    await db.commit()
    await db.refresh(session)
    return _session_to_schema(session, requesting_account_id=current_account.id)


@router.post("/war-room/debates/{debate_id}/start")
async def start_debate(
    debate_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
):
    """Start executing a debate. Returns SSE stream of debate events."""
    session = await _get_debate_session(db, debate_id, tenant_id)
    if session.status not in ("pending", "error"):
        raise HTTPException(status_code=400, detail=f"Debate already {session.status}")

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


@router.post("/war-room/debates/{debate_id}/stop")
async def stop_debate(
    debate_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
):
    """Stop a running debate and mark it as completed."""
    session = await _get_debate_session(db, debate_id, tenant_id)
    if session.status not in ("active", "synthesizing"):
        raise HTTPException(status_code=400, detail=f"Debate is not running (status: {session.status})")

    session.status = "completed"
    session.completed_at = datetime.now(UTC)
    await db.commit()
    return _session_to_schema(session, requesting_account_id=current_account.id)


@router.delete("/war-room/debates/{debate_id}")
async def delete_debate(
    debate_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
):
    """Delete a debate session."""
    session = await _get_debate_session(db, debate_id, tenant_id)
    await db.delete(session)
    await db.commit()
    return {"status": "deleted"}


# ── External Agent Participation (authenticated — for tenant's own external agents) ──


@router.post("/war-room/debates/{debate_id}/join")
async def join_debate(
    debate_id: uuid.UUID,
    request: DebateJoinRequest,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
):
    """Add an external agent to a debate (tenant-authenticated)."""
    session = await _get_debate_session(db, debate_id, tenant_id)
    return await _join_debate_internal(session, request, db)


@router.post("/war-room/debates/{debate_id}/respond")
async def external_respond(
    debate_id: uuid.UUID,
    request: DebateRespondRequest,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
):
    """External agent submits a response (tenant-authenticated)."""
    session = await _get_debate_session(db, debate_id, tenant_id)
    return await _respond_internal(session, request, db)


# ── Public External Agent Participation (no auth — uses share_token) ──────────
# Joining uses the share link; responding also requires a private participant capability.


@public_router.post("/api/v1/war-room/{share_token}/join")
async def public_join_debate(
    share_token: str,
    request: DebateJoinRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """
    External agent joins a public debate (no authentication required).

    Any agent from any platform can call this endpoint with the debate's share_token.
    Provide a callback_url if you want Synkora to POST round context to your agent,
    or omit it and use the /respond endpoint to push responses.
    """
    session = await _get_public_session(db, share_token)
    return await _join_debate_internal(session, request, db)


@public_router.post("/api/v1/war-room/{share_token}/respond")
async def public_external_respond(
    share_token: str,
    request: DebateRespondRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """
    External agent submits a debate response using its private participant capability.

    Use the participant_id and private participant_token received from /join.
    """
    session = await _get_public_session(db, share_token)
    return await _respond_internal(session, request, db)


@public_router.get("/api/v1/war-room/{share_token}/rounds/{round_num}")
async def get_round_context(
    share_token: str,
    round_num: int,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get debate context for a specific round (no auth).

    External agents can poll this to get prior messages before submitting their response.
    """
    session = await _get_public_session(db, share_token)
    messages = session.messages or []
    prior = [
        {
            "agent_name": m.get("agent_name"),
            "round": m.get("round"),
            "content": m.get("content"),
            "is_external": m.get("is_external", False),
        }
        for m in messages
        if m.get("round", 0) < round_num
    ]
    current_round_msgs = [
        {
            "agent_name": m.get("agent_name"),
            "round": m.get("round"),
            "content": m.get("content"),
            "is_external": m.get("is_external", False),
        }
        for m in messages
        if m.get("round") == round_num
    ]
    return {
        "debate_topic": session.topic,
        "round": round_num,
        "total_rounds": session.rounds,
        "current_round": session.current_round,
        "status": session.status,
        "prior_messages": prior,
        "current_round_messages": current_round_msgs,
    }


# ── Public Spectator Endpoints (no auth) ──────────────────────────────────────


@public_router.get("/api/v1/war-room/{share_token}/public")
async def get_public_debate(
    share_token: str,
    db: AsyncSession = Depends(get_async_db),
):
    """Get public debate data (no auth required)."""
    result = await db.execute(
        select(DebateSession).filter(
            DebateSession.share_token == share_token,
            DebateSession.is_public.is_(True),
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Debate not found")

    return _session_to_schema(session)


@public_router.get("/api/v1/war-room/{share_token}/live")
async def stream_public_debate(
    share_token: str,
    db: AsyncSession = Depends(get_async_db),
):
    """SSE stream for public spectators (no auth, read-only)."""
    result = await db.execute(
        select(DebateSession).filter(
            DebateSession.share_token == share_token,
            DebateSession.is_public.is_(True),
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Debate not found")

    async def event_stream():
        """Poll for new messages and stream them."""
        last_count = 0
        while True:
            await db.refresh(session)
            messages = session.messages or []
            new_messages = messages[last_count:]
            last_count = len(messages)

            for msg in new_messages:
                yield f"data: {json.dumps({'type': 'message', **msg})}\n\n"

            if session.status in ("completed", "error"):
                if session.verdict:
                    yield f"data: {json.dumps({'type': 'verdict', 'content': session.verdict})}\n\n"
                yield f"data: {json.dumps({'type': 'debate_end', 'status': session.status})}\n\n"
                return

            await asyncio.sleep(1)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Agent Script Generator ─────────────────────────────────────────────────────


@public_router.get("/api/v1/war-room/{share_token}/agent-script")
async def get_agent_script(
    share_token: str,
    provider: Literal["anthropic", "openai", "ollama"] = Query(
        "anthropic", description="LLM provider: anthropic, openai, ollama"
    ),
    agent_name: str = Query("External Agent", description="Display name for the agent"),
    model: str | None = Query(None, description="Model name override"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Generate a ready-to-run Python script that connects an external agent to this debate.

    The script handles: joining the debate, polling for rounds, calling the LLM, and posting responses.
    Supports Anthropic (Claude), OpenAI (GPT), and Ollama (local models).
    """
    session = await _get_public_session(db, share_token)
    api_base = os.environ.get("APP_BASE_URL", "http://localhost:5001")

    # Default models per provider
    default_models = {
        "anthropic": "claude-sonnet-4-20250514",
        "openai": "gpt-4o",
        "ollama": "llama3.1",
    }
    model_name = model or default_models.get(provider, "claude-sonnet-4-20250514")

    script = _generate_agent_script(
        api_base=api_base,
        share_token=share_token,
        agent_name=agent_name,
        provider=provider,
        model_name=model_name,
        topic=session.topic,
    )

    return PlainTextResponse(content=script, media_type="text/plain")


def _generate_agent_script(
    api_base: str,
    share_token: str,
    agent_name: str,
    provider: str,
    model_name: str,
    topic: str,
) -> str:
    """Generate a self-contained Python script for an external agent to participate in a debate."""

    # Build the provider-specific LLM call block
    if provider == "anthropic":
        pip_package = "anthropic"
        env_instruction = "export ANTHROPIC_API_KEY=sk-ant-..."
        llm_block = """
    # -- Anthropic (Claude) --
    from anthropic import Anthropic
    client = Anthropic()  # uses ANTHROPIC_API_KEY env var
    response = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text"""
    elif provider == "openai":
        pip_package = "openai"
        env_instruction = "export OPENAI_API_KEY=sk-..."
        llm_block = """
    # -- OpenAI (GPT) --
    from openai import OpenAI
    client = OpenAI()  # uses OPENAI_API_KEY env var
    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content"""
    else:  # ollama
        pip_package = "requests"
        env_instruction = "# Ollama runs locally, no API key needed"
        llm_block = """
    # -- Ollama (local) --
    import urllib.request
    data = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read())
    return result.get("response", "")"""

    if provider not in {"anthropic", "openai", "ollama"}:
        raise ValueError("Unsupported provider")

    return f'''#!/usr/bin/env python3
"""
Synkora War Room — External Agent Participant
Generated participant client.

This script connects an AI agent to a live Synkora debate.
It joins the debate, waits for each round, generates arguments using your chosen LLM,
and posts responses automatically.

Usage:
    pip install {pip_package}
    {env_instruction}
    python debate_agent.py
"""

import json
import time
import sys

API_BASE = {api_base!r}
SHARE_TOKEN = {share_token!r}
AGENT_NAME = {agent_name!r}
MODEL = {model_name!r}

def join_debate():
    """Join the debate and get participant ID."""
    import urllib.request
    data = json.dumps({{"agent_name": AGENT_NAME}}).encode()
    req = urllib.request.Request(
        f"{{API_BASE}}/api/v1/war-room/{{SHARE_TOKEN}}/join",
        data=data,
        headers={{"Content-Type": "application/json"}},
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
    print(f"Joined debate as '{{AGENT_NAME}}'")
    print(f"  Topic: {{result.get('debate_topic', 'N/A')}}")
    print(f"  Participants: {{', '.join(p['agent_name'] for p in result.get('participants', []))}}")
    print(f"  Rounds: {{result.get('total_rounds', '?')}}")
    return result["participant_id"], result["participant_token"], result.get("total_rounds", 3)

def get_round_context(round_num):
    """Poll for round context."""
    import urllib.request
    url = f"{{API_BASE}}/api/v1/war-room/{{SHARE_TOKEN}}/rounds/{{round_num}}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def post_response(participant_id, participant_token, round_num, content):
    """Submit debate response."""
    import urllib.request
    data = json.dumps({{
        "participant_id": participant_id,
        "participant_token": participant_token,
        "round": round_num,
        "content": content,
    }}).encode()
    req = urllib.request.Request(
        f"{{API_BASE}}/api/v1/war-room/{{SHARE_TOKEN}}/respond",
        data=data,
        headers={{"Content-Type": "application/json"}},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def generate_argument(topic, round_num, total_rounds, prior_messages, current_messages):
    """Generate an argument using the configured LLM."""
    context_parts = []
    if prior_messages:
        context_parts.append("Previous rounds:")
        for msg in prior_messages:
            context_parts.append(f"  [{{msg['agent_name']}}] (Round {{msg['round']}}): {{msg['content'][:500]}}")
    if current_messages:
        context_parts.append(f"\\nOther arguments this round (Round {{round_num}}):")
        for msg in current_messages:
            context_parts.append(f"  [{{msg['agent_name']}}]: {{msg['content'][:500]}}")

    context = "\\n".join(context_parts) if context_parts else "This is the opening round."

    prompt = f"""You are '{{AGENT_NAME}}' in a structured debate.
Topic: {{topic}}
Round {{round_num}} of {{total_rounds}}.

{{context}}

Provide a compelling, well-reasoned argument. Be concise (2-4 paragraphs).
Use markdown formatting: **bold** for emphasis, bullet points for lists, `code` for technical terms.
Build on or counter prior arguments if they exist."""
{llm_block}

def main():
    print("=" * 60)
    print(f"  Synkora War Room — External Agent")
    print(f"  Agent: {{AGENT_NAME}}")
    print(f"  Model: {{MODEL}} ({provider})")
    print("=" * 60)
    print()

    # Step 1: Join the debate
    participant_id, participant_token, total_rounds = join_debate()
    print()

    # Step 2: Participate in each round
    responded_rounds = set()

    while True:
        time.sleep(3)  # Poll every 3 seconds

        try:
            # Check each round we haven't responded to yet
            for round_num in range(1, total_rounds + 1):
                if round_num in responded_rounds:
                    continue

                ctx = get_round_context(round_num)

                # If the debate is completed or errored, exit
                if ctx.get("status") in ("completed", "error"):
                    print("\\nDebate has ended.")
                    return

                # Only respond if the debate is on this round or past it
                if ctx.get("current_round", 0) < round_num:
                    continue

                # Check if we already responded (in case of restart)
                already_responded = any(
                    m.get("agent_name") == AGENT_NAME
                    for m in ctx.get("current_round_messages", [])
                )
                if already_responded:
                    responded_rounds.add(round_num)
                    continue

                print(f"Round {{round_num}}/{{total_rounds}} — Generating argument...")

                argument = generate_argument(
                    topic=ctx["debate_topic"],
                    round_num=round_num,
                    total_rounds=total_rounds,
                    prior_messages=ctx.get("prior_messages", []),
                    current_messages=ctx.get("current_round_messages", []),
                )

                print(f"  Posting response ({{len(argument)}} chars)...")
                post_response(participant_id, participant_token, round_num, argument)
                responded_rounds.add(round_num)
                print(f"  Done! Waiting for next round...\\n")

            # If we've responded to all rounds, wait for completion
            if len(responded_rounds) >= total_rounds:
                ctx = get_round_context(total_rounds)
                if ctx.get("status") in ("completed", "synthesizing"):
                    print("\\nAll rounds complete. Waiting for verdict...")
                    time.sleep(5)
                    print("Debate finished!")
                    return

        except Exception as e:
            # Don't crash on transient errors
            if "409" in str(e):  # Already responded
                continue
            print(f"  (polling... {{e}})")
            time.sleep(5)

if __name__ == "__main__":
    main()
'''


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _get_debate_session(db: AsyncSession, debate_id: uuid.UUID, tenant_id: uuid.UUID) -> DebateSession:
    """Fetch a debate session with tenant check."""
    result = await db.execute(
        select(DebateSession).filter(
            DebateSession.id == debate_id,
            DebateSession.tenant_id == tenant_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Debate not found")
    return session


async def _get_public_session(db: AsyncSession, share_token: str) -> DebateSession:
    """Fetch a public debate session by share token (no tenant auth)."""
    result = await db.execute(
        select(DebateSession).filter(
            DebateSession.share_token == share_token,
            DebateSession.is_public.is_(True),
            DebateSession.allow_external.is_(True),
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=404,
            detail="Debate not found or does not allow external agents",
        )
    return session


async def _join_debate_internal(session: DebateSession, request: DebateJoinRequest, db: AsyncSession) -> dict[str, Any]:
    """
    Add an external agent to a debate.

    Works for any agent — OpenAI, Claude, Gemini, a bash script, a human with curl.
    Two participation modes:

    1. Callback mode: provide callback_url and we POST round context to it.
       Your endpoint receives: {debate_topic, round, total_rounds, prior_messages, instructions}
       Your endpoint returns: {content: "your argument"}

    2. Push mode: omit callback_url and poll GET /rounds/{n} for context,
       then POST /respond with your argument.
    """
    await db.refresh(session, with_for_update=True)
    if not session.allow_external:
        raise HTTPException(status_code=403, detail="This debate does not allow external agents")
    if session.status == "completed":
        raise HTTPException(status_code=400, detail="Debate is already completed")

    participants = list(session.participants or [])
    if len(participants) >= 8:
        raise HTTPException(status_code=400, detail="Maximum 8 participants reached")

    # Check for duplicate agent name
    existing_names = {p.get("agent_name", "").lower() for p in participants}
    if request.agent_name.lower() in existing_names:
        raise HTTPException(status_code=409, detail=f"An agent named '{request.agent_name}' is already in this debate")

    participant_id = str(uuid.uuid4())
    participant_token = secrets.token_urlsafe(32)
    color_idx = len(participants) % len(PARTICIPANT_COLORS)

    participants.append(
        {
            "id": participant_id,
            "agent_id": None,
            "agent_name": request.agent_name,
            "role": None,
            "is_external": True,
            "callback_url": request.callback_url,
            "auth_token": request.auth_token,
            "participant_token_hash": hashlib.sha256(participant_token.encode()).hexdigest(),
            "color": PARTICIPANT_COLORS[color_idx],
        }
    )
    session.participants = participants
    await db.commit()

    return {
        "participant_id": participant_id,
        "participant_token": participant_token,
        "debate_topic": session.topic,
        "current_round": session.current_round,
        "total_rounds": session.rounds,
        "status": session.status,
        "participants": [
            {"agent_name": p.get("agent_name"), "is_external": p.get("is_external", False)} for p in participants
        ],
        "instructions": (
            "You have joined the debate. "
            + (
                "Your callback_url will receive POST requests with round context. "
                'Return {"content": "your argument"} in the response body.'
                if request.callback_url
                else "Poll GET /rounds/{round_num} for context, then POST /respond with "
                '{"participant_id": "...", "participant_token": "...", "round": N, "content": "your argument"}.'
            )
        ),
    }


async def _respond_internal(session: DebateSession, request: DebateRespondRequest, db: AsyncSession) -> dict[str, Any]:
    """Record a response authenticated with a private per-participant capability."""
    await db.refresh(session, with_for_update=True)
    if session.status != "active" or request.round != session.current_round or request.round > session.rounds:
        raise HTTPException(409, "Responses are accepted only for the active round")
    participants = session.participants or []
    participant = next((p for p in participants if p["id"] == request.participant_id), None)
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")
    if not participant.get("is_external"):
        raise HTTPException(status_code=400, detail="Only external participants use this endpoint")

    stored_hash = participant.get("participant_token_hash")
    supplied = hashlib.sha256((request.participant_token or "").encode()).hexdigest()
    if not stored_hash or not request.participant_token or not hmac.compare_digest(stored_hash, supplied):
        raise HTTPException(403, "Invalid participant credentials")

    key = f"{request.participant_id}:{request.round}"
    submissions = dict(session.external_responses or {})
    if key in submissions:
        raise HTTPException(409, "Already responded for this round")

    msg = {
        "id": str(uuid.uuid4()),
        "participant_id": request.participant_id,
        "agent_name": participant["agent_name"],
        "round": request.round,
        "content": request.content,
        "is_verdict": False,
        "is_external": True,
        "created_at": datetime.now(UTC).isoformat(),
        "color": participant.get("color", "#6366f1"),
    }
    submissions[key] = msg
    session.external_responses = submissions
    await db.commit()

    return {"status": "accepted", "message_id": msg["id"]}


def _session_to_schema(session: DebateSession, requesting_account_id: uuid.UUID | None = None) -> dict[str, Any]:
    """Convert a DebateSession model to API response dict.

    Args:
        session: The debate session to serialize.
        requesting_account_id: The account making the request. share_token is
            only included when this matches session.created_by to prevent
            leaking the token to non-creators.
    """
    # SECURITY: Only the debate creator should see the share_token
    include_share_token = requesting_account_id is not None and session.created_by == requesting_account_id

    return {
        "id": str(session.id),
        "topic": session.topic,
        "debate_type": session.debate_type,
        "rounds": session.rounds,
        "current_round": session.current_round,
        "status": session.status,
        "is_public": session.is_public,
        "allow_external": session.allow_external,
        "share_token": session.share_token if include_share_token else None,
        "participants": public_participants(session.participants or []),
        "messages": session.messages or [],
        "debate_metadata": session.debate_metadata or {},
        "verdict": session.verdict,
        "created_at": session.created_at.isoformat() if session.created_at else "",
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
    }
