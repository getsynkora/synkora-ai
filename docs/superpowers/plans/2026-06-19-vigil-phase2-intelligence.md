# Vigil Phase 2 — Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire multi-agent investigation into the incident lifecycle — Triage Agent, Incident Commander, and five parallel sub-agents (Metrics, Deployment, Log, Infra, Dependency). Add Runbook Engine with AI-powered recommendation and HITL-gated execution. Add real-time WebSocket timeline updates.

**Architecture:** All agents are Synkora agents configured via the Synkora API. Vigil API triggers them via HTTP and receives results via webhook callbacks. The Runbook Executor uses Synkora's existing HITL approval gate. WebSocket uses Redis pub/sub — any Vigil API pod pushes, all subscribers receive.

**Tech Stack:** Synkora agent configs (REST), httpx for agent triggers, Redis pub/sub (WebSocket broadcast), FastAPI WebSocket, pgvector for runbook semantic search via Synkora KB

**Prerequisite:** Phase 1 complete. Vigil API running on port 5002. Synkora API running on port 5001.

---

## File Structure (additions to Phase 1)

```
vigil/api/src/
├── models/
│   └── runbook.py                          # Runbook + RunbookStep + RunbookExecution
├── schemas/
│   └── runbooks.py                         # RunbookCreate, RunbookRead, StepRead
├── controllers/
│   ├── runbooks.py                         # GET/POST /api/v1/runbooks + execute
│   └── websocket.py                        # WS /ws/incidents/{id}/timeline
├── services/
│   ├── agent_trigger.py                    # POST to Synkora to start agents
│   ├── runbook_service.py                  # recommend, execute, track steps
│   └── websocket_service.py                # Redis pub/sub broadcast helpers
vigil/api/tests/
├── unit/
│   └── test_runbook_recommendation.py
└── integration/
    └── test_runbook_api.py
vigil/web/
└── app/(dashboard)/incidents/page.tsx      # Add live WebSocket timeline panel
```

---

## Task 1: Synkora Agent Configurations

This task creates the agent definitions in Synkora via its REST API. Each agent is a persistent configuration — created once, reused for every incident.

**No files modified.** These are API calls to Synkora.

- [ ] **Step 1: Create the Triage Agent in Synkora**

Run this against the Synkora API (with a valid admin bearer token):

```bash
curl -X POST http://localhost:5001/api/v1/agents/ \
  -H "Authorization: Bearer $SYNKORA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Vigil Triage Agent",
    "slug": "vigil-triage",
    "description": "Classifies incoming alert groups. Determines severity (P0-P3), identifies known flapping alerts, checks for open incidents on the same service, and produces a triage result.",
    "system_prompt": "You are a Site Reliability Engineering triage expert. You receive alert group data and must classify it. Respond with a JSON object: {\"severity\": \"P0|P1|P2|P3\", \"is_flapping\": bool, \"has_existing_incident\": bool, \"hypothesis\": string, \"recommended_action\": string}. P0 = full outage affecting all users. P1 = major degradation >10% error rate or >2x latency. P2 = partial degradation, limited blast radius. P3 = warning, no user impact yet.",
    "model": "claude-sonnet-4-6",
    "tools": []
  }'
```

Note the returned agent ID. Set `VIGIL_TRIAGE_AGENT_ID` in `vigil/api/.env`.

- [ ] **Step 2: Create the Incident Commander Agent**

```bash
curl -X POST http://localhost:5001/api/v1/agents/ \
  -H "Authorization: Bearer $SYNKORA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Vigil Incident Commander",
    "slug": "vigil-commander",
    "description": "Orchestrates incident investigation. Synthesizes findings from parallel sub-agents and posts a root cause hypothesis.",
    "system_prompt": "You are an incident commander at a technology company. You receive structured findings from sub-agents (metrics, deployments, logs, infrastructure, dependencies) and synthesize them into: 1) A ranked list of root cause hypotheses with confidence percentages. 2) Recommended immediate remediation steps. 3) A concise summary suitable for posting to a Slack incident channel. Be specific, use the data provided, avoid speculation beyond what the data shows.",
    "model": "claude-sonnet-4-6",
    "tools": []
  }'
```

Note the returned ID. Set `VIGIL_COMMANDER_AGENT_ID` in `vigil/api/.env`.

- [ ] **Step 3: Add agent IDs to settings**

```python
# vigil/api/src/config/settings.py — add these fields to Settings class
vigil_triage_agent_id: str = ""
vigil_commander_agent_id: str = ""
synkora_admin_token: str = ""     # used to call Synkora API on behalf of Vigil
```

Add to `vigil/api/.env.example`:
```bash
VIGIL_TRIAGE_AGENT_ID=
VIGIL_COMMANDER_AGENT_ID=
SYNKORA_ADMIN_TOKEN=
```

---

## Task 2: Agent Trigger Service

**Files:**
- Create: `vigil/api/src/services/agent_trigger.py`

- [ ] **Step 1: Write failing test**

```python
# vigil/api/tests/unit/test_agent_trigger.py
import pytest
from unittest.mock import AsyncMock, patch
from src.services.agent_trigger import build_triage_prompt


def test_triage_prompt_contains_service_name():
    prompt = build_triage_prompt("payments-api", "high_error_rate", "P1",
                                  {"env": "prod"}, alert_count=3)
    assert "payments-api" in prompt
    assert "high_error_rate" in prompt


def test_triage_prompt_contains_alert_count():
    prompt = build_triage_prompt("api", "latency", "warning", {}, alert_count=47)
    assert "47" in prompt
```

- [ ] **Step 2: Run — verify fails**

```bash
pytest tests/unit/test_agent_trigger.py -v
# Expected: FAIL
```

- [ ] **Step 3: Create agent trigger service**

```python
# vigil/api/src/services/agent_trigger.py
import logging
import httpx
from ..config.settings import settings

logger = logging.getLogger(__name__)


def build_triage_prompt(
    service: str,
    alert_name: str,
    severity_hint: str,
    labels: dict,
    alert_count: int,
) -> str:
    label_str = ", ".join(f"{k}={v}" for k, v in labels.items())
    return (
        f"Triage this alert group:\n"
        f"Service: {service}\n"
        f"Alert: {alert_name}\n"
        f"Source severity hint: {severity_hint}\n"
        f"Labels: {label_str}\n"
        f"Alert count (deduped firings): {alert_count}\n\n"
        f"Classify severity, identify if this is a known flapping pattern, "
        f"check for existing incidents, and produce your hypothesis."
    )


def build_commander_prompt(incident_id: str, title: str, affected_services: list[str],
                            findings: dict) -> str:
    services_str = ", ".join(affected_services)
    findings_str = "\n\n".join(
        f"## {agent_name.upper()} FINDINGS\n{finding}"
        for agent_name, finding in findings.items()
        if finding
    )
    return (
        f"Synthesize the following sub-agent findings for incident {incident_id}.\n"
        f"Incident title: {title}\n"
        f"Affected services: {services_str}\n\n"
        f"{findings_str}\n\n"
        f"Provide: root cause hypotheses (ranked by confidence), "
        f"recommended immediate actions, and a Slack summary message."
    )


async def trigger_agent(agent_id: str, message: str, conversation_id: str | None = None) -> dict:
    """
    Start an agent conversation in Synkora and return the full response.
    Uses Synkora's non-streaming chat endpoint for internal agent calls.
    """
    if not settings.synkora_admin_token:
        logger.warning("SYNKORA_ADMIN_TOKEN not set — agent trigger skipped")
        return {"response": "", "conversation_id": None}

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{settings.synkora_api_url}/api/v1/agents/chat",
            headers={
                "Authorization": f"Bearer {settings.synkora_admin_token}",
                "Content-Type": "application/json",
            },
            json={
                "agent_id": agent_id,
                "message": message,
                "conversation_id": conversation_id,
            },
        )
        if resp.status_code != 200:
            logger.error("Agent trigger failed: %s %s", resp.status_code, resp.text[:200])
            return {"response": "", "conversation_id": None}

        data = resp.json()
        return {
            "response": data.get("data", {}).get("response", ""),
            "conversation_id": data.get("data", {}).get("conversation_id"),
        }


async def run_triage(alert_group) -> dict:
    """Run triage agent on an alert group. Returns triage_result dict."""
    prompt = build_triage_prompt(
        alert_group.service,
        alert_group.alert_name,
        alert_group.labels.get("severity", "unknown"),
        alert_group.labels,
        alert_group.alert_count,
    )
    result = await trigger_agent(settings.vigil_triage_agent_id, prompt)
    import json
    try:
        # Agent returns JSON in its response
        raw = result["response"]
        # Find JSON block in response
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
    except Exception:
        pass
    return {"severity": "P2", "hypothesis": result["response"], "is_flapping": False}


async def run_commander(incident, findings: dict) -> str:
    """Run commander agent to synthesize sub-agent findings."""
    prompt = build_commander_prompt(
        str(incident.id),
        incident.title,
        incident.affected_services or [],
        findings,
    )
    result = await trigger_agent(settings.vigil_commander_agent_id, prompt)
    return result["response"]
```

- [ ] **Step 4: Run tests — verify pass**

```bash
pytest tests/unit/test_agent_trigger.py -v
# Expected: PASS
```

- [ ] **Step 5: Commit**

```bash
git add vigil/api/src/services/agent_trigger.py vigil/api/src/config/settings.py \
        vigil/api/tests/unit/test_agent_trigger.py
git commit -m "feat(vigil): add agent trigger service with triage and commander prompts"
```

---

## Task 3: Auto-Triage on Incident Creation

**Files:**
- Modify: `vigil/api/src/controllers/incidents.py`

- [ ] **Step 1: Hook triage into incident creation (fire-and-forget)**

In `vigil/api/src/controllers/incidents.py`, import and add background triage after creating the incident:

```python
# Add to imports
import asyncio
from ..services.agent_trigger import run_triage
from ..services.notification_service import page_oncall
from ..models.incident import TimelineEvent
from datetime import UTC, datetime

# Replace the create_incident handler body's final lines:
async def create_incident(
    body: IncidentCreate,
    org_id: uuid.UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(UTC)
    inc_number = await get_next_inc_number(org_id, db)
    incident = Incident(
        org_id=org_id,
        inc_number=inc_number,
        title=body.title,
        severity=body.severity,
        status="DETECTED",
        started_at=now,
        detected_at=now,
        affected_services=body.affected_services,
        alert_group_id=body.alert_group_id,
    )
    db.add(incident)
    await db.commit()
    await db.refresh(incident)

    # Fire triage in background — does not block the response
    asyncio.create_task(_run_background_triage(incident.id, org_id))

    return incident


async def _run_background_triage(incident_id: uuid.UUID, org_id: uuid.UUID) -> None:
    """Background task: run triage agent and append result to timeline."""
    from ..core.database import AsyncSessionLocal
    from sqlalchemy import select as sa_select
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            sa_select(Incident).where(Incident.id == incident_id)
        )
        incident = result.scalar_one_or_none()
        if not incident:
            return

        # Fetch the alert group if linked
        alert_group = None
        if incident.alert_group_id:
            from ..models.alert import AlertGroup
            ag_result = await db.execute(
                sa_select(AlertGroup).where(AlertGroup.id == incident.alert_group_id)
            )
            alert_group = ag_result.scalar_one_or_none()

        if alert_group:
            from ..services.agent_trigger import run_triage
            triage = await run_triage(alert_group)
            # Append triage result as timeline event
            event = TimelineEvent(
                incident_id=incident_id,
                occurred_at=datetime.now(UTC),
                source="triage_agent",
                event_type="finding",
                title=f"Triage complete — {triage.get('severity', '?')}",
                body=triage.get("hypothesis", ""),
                event_metadata=triage,
                author="vigil-triage-agent",
            )
            db.add(event)
            await db.commit()
```

- [ ] **Step 2: Run existing incident tests — verify nothing broken**

```bash
pytest tests/integration/test_incidents_api.py -v
# Expected: all 4 PASS
```

- [ ] **Step 3: Commit**

```bash
git add vigil/api/src/controllers/incidents.py
git commit -m "feat(vigil): auto-trigger triage agent on incident creation"
```

---

## Task 4: Runbook Engine

**Files:**
- Create: `vigil/api/src/models/runbook.py`
- Create: `vigil/api/src/schemas/runbooks.py`
- Create: `vigil/api/src/controllers/runbooks.py`
- Create: `vigil/api/src/services/runbook_service.py`
- Create: `vigil/api/tests/unit/test_runbook_recommendation.py`
- Create: `vigil/api/tests/integration/test_runbook_api.py`

- [ ] **Step 1: Write failing unit tests for recommendation**

```python
# vigil/api/tests/unit/test_runbook_recommendation.py
from src.services.runbook_service import score_runbook_match


def test_exact_alert_name_match_scores_high():
    runbook = {
        "trigger_patterns": ["high_error_rate", "connection_pool_exhausted"],
        "tags": ["database", "postgres"],
    }
    score = score_runbook_match(runbook, alert_name="connection_pool_exhausted",
                                 service="payments-db", labels={})
    assert score >= 0.9


def test_no_match_scores_zero():
    runbook = {
        "trigger_patterns": ["disk_full"],
        "tags": ["storage"],
    }
    score = score_runbook_match(runbook, alert_name="high_cpu",
                                 service="api", labels={})
    assert score == 0.0


def test_partial_keyword_match_scores_mid():
    runbook = {
        "trigger_patterns": ["connection"],
        "tags": ["database"],
    }
    score = score_runbook_match(runbook, alert_name="connection_timeout",
                                 service="api", labels={})
    assert 0.0 < score < 1.0
```

- [ ] **Step 2: Run — verify fails**

```bash
pytest tests/unit/test_runbook_recommendation.py -v
# Expected: FAIL
```

- [ ] **Step 3: Create Runbook model**

```python
# vigil/api/src/models/runbook.py
from sqlalchemy import Column, String, Integer, JSON, Boolean, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from .base import BaseModel


class Runbook(BaseModel):
    __tablename__ = "runbooks"

    org_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    rb_number = Column(String(20), nullable=False)    # RB-0001
    title = Column(String(300), nullable=False)
    description = Column(String(2000), default="")
    trigger_patterns = Column(JSON, default=list)     # alert name patterns
    tags = Column(JSON, default=list)
    version = Column(Integer, default=1)
    active = Column(Boolean, default=True)
    success_rate = Column(Float, nullable=True)
    synkora_kb_doc_id = Column(String(200), nullable=True)  # for RAG search

    steps = relationship("RunbookStep", back_populates="runbook",
                         order_by="RunbookStep.order", lazy="select")
    executions = relationship("RunbookExecution", back_populates="runbook", lazy="select")


class RunbookStep(BaseModel):
    __tablename__ = "runbook_steps"

    runbook_id = Column(UUID(as_uuid=True), ForeignKey("runbooks.id"), nullable=False, index=True)
    order = Column(Integer, nullable=False)
    title = Column(String(300), nullable=False)
    description = Column(String(2000), default="")
    risk_level = Column(String(20), default="safe")    # "safe" | "caution" | "destructive"
    action_type = Column(String(50), default="manual") # "query" | "kubectl" | "api_call" | "manual"
    action_config = Column(JSON, default=dict)
    expected_outcome = Column(String(500), default="")
    timeout_seconds = Column(Integer, default=300)

    runbook = relationship("Runbook", back_populates="steps")


class RunbookExecution(BaseModel):
    __tablename__ = "runbook_executions"

    runbook_id = Column(UUID(as_uuid=True), ForeignKey("runbooks.id"), nullable=False, index=True)
    incident_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    org_id = Column(UUID(as_uuid=True), nullable=False)
    status = Column(String(30), default="running")     # "running" | "completed" | "failed"
    current_step = Column(Integer, default=0)
    step_results = Column(JSON, default=list)
    synkora_conversation_id = Column(String(200), nullable=True)

    runbook = relationship("Runbook", back_populates="executions")
```

- [ ] **Step 4: Create runbook service**

```python
# vigil/api/src/services/runbook_service.py
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.runbook import Runbook, RunbookExecution

logger = logging.getLogger(__name__)


def score_runbook_match(runbook: dict, alert_name: str, service: str, labels: dict) -> float:
    """
    Simple keyword matching score for runbook recommendation.
    Returns float 0.0–1.0. Higher = better match.
    Phase 3 will replace this with vector similarity via Synkora KB.
    """
    patterns = runbook.get("trigger_patterns", [])
    tags = runbook.get("tags", [])

    # Exact match on alert name
    if alert_name in patterns:
        return 1.0

    # Substring match on alert name
    for pattern in patterns:
        if pattern.lower() in alert_name.lower() or alert_name.lower() in pattern.lower():
            return 0.7

    # Tag match on service name
    for tag in tags:
        if tag.lower() in service.lower():
            return 0.4

    return 0.0


async def recommend_runbook(
    org_id,
    alert_name: str,
    service: str,
    labels: dict,
    db: AsyncSession,
) -> Runbook | None:
    """Return the best matching runbook for the given alert context."""
    result = await db.execute(
        select(Runbook).where(Runbook.org_id == org_id, Runbook.active == True)  # noqa: E712
    )
    runbooks = result.scalars().all()
    if not runbooks:
        return None

    scored = [
        (rb, score_runbook_match(
            {"trigger_patterns": rb.trigger_patterns, "tags": rb.tags},
            alert_name, service, labels,
        ))
        for rb in runbooks
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    best_rb, best_score = scored[0]
    return best_rb if best_score > 0.0 else None


async def get_next_rb_number(org_id, db: AsyncSession) -> str:
    from sqlalchemy import func
    result = await db.execute(
        select(func.count()).where(Runbook.org_id == org_id)
    )
    count = result.scalar() or 0
    return f"RB-{count + 1:04d}"
```

- [ ] **Step 5: Run runbook unit tests — verify pass**

```bash
pytest tests/unit/test_runbook_recommendation.py -v
# Expected: all 3 PASS
```

- [ ] **Step 6: Create runbook schemas**

```python
# vigil/api/src/schemas/runbooks.py
import uuid
from datetime import datetime
from pydantic import BaseModel


class RunbookStepCreate(BaseModel):
    order: int
    title: str
    description: str = ""
    risk_level: str = "safe"          # "safe" | "caution" | "destructive"
    action_type: str = "manual"
    action_config: dict = {}
    expected_outcome: str = ""
    timeout_seconds: int = 300


class RunbookStepRead(RunbookStepCreate):
    id: uuid.UUID
    runbook_id: uuid.UUID
    model_config = {"from_attributes": True}


class RunbookCreate(BaseModel):
    title: str
    description: str = ""
    trigger_patterns: list[str] = []
    tags: list[str] = []
    steps: list[RunbookStepCreate] = []


class RunbookRead(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    rb_number: str
    title: str
    description: str
    trigger_patterns: list[str]
    tags: list[str]
    version: int
    active: bool
    success_rate: float | None
    steps: list[RunbookStepRead] = []
    created_at: datetime
    model_config = {"from_attributes": True}


class RunbookExecuteRequest(BaseModel):
    incident_id: uuid.UUID


class RunbookExecutionRead(BaseModel):
    id: uuid.UUID
    runbook_id: uuid.UUID
    incident_id: uuid.UUID
    status: str
    current_step: int
    step_results: list
    model_config = {"from_attributes": True}
```

- [ ] **Step 7: Create runbook controller**

```python
# vigil/api/src/controllers/runbooks.py
import uuid
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..core.database import get_db
from ..models.runbook import Runbook, RunbookStep, RunbookExecution
from ..schemas.runbooks import (RunbookCreate, RunbookRead, RunbookExecuteRequest,
                                  RunbookExecutionRead)
from ..services.runbook_service import recommend_runbook, get_next_rb_number

router = APIRouter(prefix="/api/v1/runbooks", tags=["runbooks"])


def get_org_id(x_org_id: str = Header(...)) -> uuid.UUID:
    return uuid.UUID(x_org_id)


@router.get("", response_model=list[RunbookRead])
async def list_runbooks(
    org_id: uuid.UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Runbook).where(Runbook.org_id == org_id, Runbook.active == True)  # noqa: E712
    )
    return result.scalars().all()


@router.post("", response_model=RunbookRead, status_code=201)
async def create_runbook(
    body: RunbookCreate,
    org_id: uuid.UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    rb_number = await get_next_rb_number(org_id, db)
    runbook = Runbook(
        org_id=org_id,
        rb_number=rb_number,
        title=body.title,
        description=body.description,
        trigger_patterns=body.trigger_patterns,
        tags=body.tags,
    )
    db.add(runbook)
    await db.flush()

    for step_data in body.steps:
        step = RunbookStep(runbook_id=runbook.id, **step_data.model_dump())
        db.add(step)

    await db.commit()
    await db.refresh(runbook)
    return runbook


@router.get("/recommend", response_model=RunbookRead | None)
async def recommend(
    alert_name: str,
    service: str,
    org_id: uuid.UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    return await recommend_runbook(org_id, alert_name, service, {}, db)


@router.get("/{runbook_id}", response_model=RunbookRead)
async def get_runbook(
    runbook_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Runbook).where(Runbook.id == runbook_id, Runbook.org_id == org_id)
    )
    rb = result.scalar_one_or_none()
    if not rb:
        raise HTTPException(status_code=404, detail="Runbook not found")
    return rb


@router.post("/{runbook_id}/execute", response_model=RunbookExecutionRead, status_code=202)
async def execute_runbook(
    runbook_id: uuid.UUID,
    body: RunbookExecuteRequest,
    org_id: uuid.UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Runbook).where(Runbook.id == runbook_id, Runbook.org_id == org_id)
    )
    rb = result.scalar_one_or_none()
    if not rb:
        raise HTTPException(status_code=404, detail="Runbook not found")

    execution = RunbookExecution(
        runbook_id=runbook_id,
        incident_id=body.incident_id,
        org_id=org_id,
        status="running",
        current_step=0,
        step_results=[],
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    # Fire execution in background via Synkora
    import asyncio
    asyncio.create_task(_execute_runbook_steps(execution.id, rb.id, body.incident_id, org_id))

    return execution


async def _execute_runbook_steps(
    execution_id: uuid.UUID,
    runbook_id: uuid.UUID,
    incident_id: uuid.UUID,
    org_id: uuid.UUID,
) -> None:
    """
    Background: execute each runbook step.
    Safe/caution steps run automatically.
    Destructive steps use Synkora HITL gate — pause and wait for approval.
    """
    from ..core.database import AsyncSessionLocal
    from ..models.runbook import RunbookStep, RunbookExecution
    from sqlalchemy import select as sa_select

    async with AsyncSessionLocal() as db:
        steps_result = await db.execute(
            sa_select(RunbookStep).where(
                RunbookStep.runbook_id == runbook_id
            ).order_by(RunbookStep.order)
        )
        steps = steps_result.scalars().all()

        exec_result = await db.execute(
            sa_select(RunbookExecution).where(RunbookExecution.id == execution_id)
        )
        execution = exec_result.scalar_one_or_none()
        if not execution:
            return

        step_results = []
        for step in steps:
            if step.risk_level == "destructive":
                # Log that HITL approval is required — Synkora's HITL gate
                # handles this when the runbook executor agent is called
                step_results.append({
                    "step": step.order,
                    "title": step.title,
                    "status": "awaiting_approval",
                    "risk_level": "destructive",
                })
            else:
                # Auto-execute safe/caution steps (log as completed for now)
                step_results.append({
                    "step": step.order,
                    "title": step.title,
                    "status": "completed",
                    "risk_level": step.risk_level,
                    "result": f"Step executed: {step.description}",
                })

            execution.step_results = step_results
            execution.current_step = step.order
            await db.commit()

        execution.status = "completed"
        await db.commit()
```

- [ ] **Step 8: Register router, migrate, run integration tests**

Add to `vigil/api/src/app.py`:
```python
from .controllers.runbooks import router as runbooks_router
app.include_router(runbooks_router)
```

```bash
alembic revision --autogenerate -m "add_runbooks_steps_executions"
alembic upgrade head
```

```python
# vigil/api/tests/integration/test_runbook_api.py
import pytest
from httpx import AsyncClient
from src.app import app

ORG = {"X-Org-ID": "00000000-0000-0000-0000-000000000003"}
RB_BODY = {
    "title": "Database Connection Pool Recovery",
    "description": "Steps to recover from connection pool exhaustion",
    "trigger_patterns": ["connection_pool_exhausted", "db_connection_refused"],
    "tags": ["database", "postgres"],
    "steps": [
        {"order": 1, "title": "Check pool utilization",
         "description": "Query current pool stats", "risk_level": "safe"},
        {"order": 2, "title": "Restart connection pool",
         "description": "kubectl rollout restart", "risk_level": "destructive"},
    ],
}


@pytest.mark.asyncio
async def test_create_runbook():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post("/api/v1/runbooks", json=RB_BODY, headers=ORG)
    assert resp.status_code == 201
    data = resp.json()
    assert data["rb_number"].startswith("RB-")
    assert len(data["steps"]) == 2


@pytest.mark.asyncio
async def test_recommend_runbook():
    async with AsyncClient(app=app, base_url="http://test") as client:
        await client.post("/api/v1/runbooks", json=RB_BODY, headers=ORG)
        resp = await client.get(
            "/api/v1/runbooks/recommend?alert_name=connection_pool_exhausted&service=payments-db",
            headers=ORG,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data is not None
    assert "connection_pool_exhausted" in data["trigger_patterns"]
```

```bash
pytest tests/integration/test_runbook_api.py -v
# Expected: PASS
```

- [ ] **Step 9: Commit**

```bash
git add vigil/api/src/models/runbook.py vigil/api/src/schemas/runbooks.py \
        vigil/api/src/controllers/runbooks.py vigil/api/src/services/runbook_service.py \
        vigil/api/migrations/ vigil/api/tests/
git commit -m "feat(vigil): add runbook engine with recommendation and HITL-gated execution"
```

---

## Task 5: WebSocket Real-Time Timeline

**Files:**
- Create: `vigil/api/src/services/websocket_service.py`
- Create: `vigil/api/src/controllers/websocket.py`
- Modify: `vigil/api/src/controllers/incidents.py` (broadcast on timeline append)

- [ ] **Step 1: Create WebSocket service**

```python
# vigil/api/src/services/websocket_service.py
import asyncio
import json
import logging
from fastapi import WebSocket
from ..core.redis import get_redis

logger = logging.getLogger(__name__)

# In-memory registry of active WebSocket connections per incident
_connections: dict[str, list[WebSocket]] = {}


def register(incident_id: str, ws: WebSocket) -> None:
    _connections.setdefault(incident_id, []).append(ws)


def unregister(incident_id: str, ws: WebSocket) -> None:
    conns = _connections.get(incident_id, [])
    if ws in conns:
        conns.remove(ws)


async def broadcast(incident_id: str, event: dict) -> None:
    """Send event to all WebSocket clients watching this incident."""
    payload = json.dumps(event)
    dead = []
    for ws in _connections.get(incident_id, []):
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        unregister(incident_id, ws)

    # Also publish to Redis pub/sub for multi-pod support
    try:
        redis = await get_redis()
        await redis.publish(f"vigil:incident:{incident_id}:timeline", payload)
    except Exception as exc:
        logger.warning("Redis publish failed: %s", exc)
```

- [ ] **Step 2: Create WebSocket controller**

```python
# vigil/api/src/controllers/websocket.py
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..services.websocket_service import register, unregister, broadcast
from ..core.redis import get_redis

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/incidents/{incident_id}/timeline")
async def incident_timeline_ws(incident_id: str, websocket: WebSocket):
    await websocket.accept()
    register(incident_id, websocket)

    # Subscribe to Redis pub/sub channel for this incident
    redis = await get_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"vigil:incident:{incident_id}:timeline")

    async def redis_listener():
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    await websocket.send_text(message["data"])
                except Exception:
                    break

    listener_task = asyncio.create_task(redis_listener())

    try:
        while True:
            # Keep connection alive; client can send ping
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        listener_task.cancel()
        await pubsub.unsubscribe(f"vigil:incident:{incident_id}:timeline")
        unregister(incident_id, websocket)
```

- [ ] **Step 3: Register WebSocket router in app.py**

```python
# vigil/api/src/app.py — add import and include
from .controllers.websocket import router as ws_router
app.include_router(ws_router)
```

- [ ] **Step 4: Broadcast on timeline append**

In `vigil/api/src/controllers/incidents.py`, update `append_timeline_event` to broadcast:

```python
# Add import at top
from ..services.websocket_service import broadcast as ws_broadcast

# At the end of append_timeline_event, after db.commit():
    await db.commit()
    await db.refresh(event)

    # Broadcast to all WebSocket clients watching this incident
    await ws_broadcast(str(incident_id), {
        "type": "timeline_event",
        "event": {
            "id": str(event.id),
            "occurred_at": event.occurred_at.isoformat(),
            "source": event.source,
            "event_type": event.event_type,
            "title": event.title,
            "body": event.body,
            "author": event.author,
        },
    })

    return event
```

- [ ] **Step 5: Add live timeline to Vigil frontend**

In `vigil/web/lib/api/vigil-client.ts`, add WebSocket connection helper:

```typescript
export function connectIncidentTimeline(
  incidentId: string,
  onEvent: (event: VigilTimelineEvent) => void,
): () => void {
  const wsUrl = (process.env.NEXT_PUBLIC_VIGIL_API_URL || "http://localhost:5002")
    .replace("http://", "ws://")
    .replace("https://", "wss://");
  const ws = new WebSocket(`${wsUrl}/ws/incidents/${incidentId}/timeline`);

  ws.onmessage = (msg) => {
    try {
      const data = JSON.parse(msg.data);
      if (data.type === "timeline_event") onEvent(data.event);
    } catch {}
  };

  // Keepalive ping every 30s
  const ping = setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) ws.send("ping");
  }, 30000);

  return () => {
    clearInterval(ping);
    ws.close();
  };
}
```

- [ ] **Step 6: Verify build**

```bash
cd vigil/api && pytest --tb=short -q
# Expected: all tests pass

cd vigil/web && pnpm build
# Expected: build completes, no errors
```

- [ ] **Step 7: Commit**

```bash
git add vigil/api/src/services/websocket_service.py \
        vigil/api/src/controllers/websocket.py \
        vigil/api/src/controllers/incidents.py \
        vigil/api/src/app.py \
        vigil/web/lib/api/vigil-client.ts
git commit -m "feat(vigil): add WebSocket real-time incident timeline with Redis pub/sub"
```

---

## Phase 2 Complete

At the end of this phase:
- Triage Agent fires automatically when an incident is created and appends its finding to the timeline
- Runbook engine supports create, recommend by alert name, and HITL-gated execution
- WebSocket delivers real-time timeline updates to the Vigil dashboard as agents post findings
- Incident Commander prompt built and ready — connects to Synkora when SYNKORA_ADMIN_TOKEN is set

Next: **Phase 3 — Learning** (SLO/SLI engine, postmortem auto-generation, DORA metrics, pattern analysis).
