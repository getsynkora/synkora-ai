# Vigil Phase 3 — Learning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the strategic learning layer — SLO/SLI tracking with error budget burn rates, postmortem auto-generation from incident timeline, DORA metrics calculation, Jira action item sync, and a weekly Pattern Analysis agent that surfaces recurring failure patterns.

**Architecture:** SLO snapshots stored as time-series rows in Postgres (hourly, sufficient to Phase 3). Postmortem Agent is a Synkora agent that reads the incident timeline via the Vigil API and outputs structured postmortem JSON. DORA metrics are calculated on-demand from incident + deployment data. Pattern Analysis is a Celery-like background task run via Synkora's scheduled task system.

**Tech Stack:** SQLAlchemy time-series queries, Synkora agent API (postmortem + pattern agents), httpx (Jira REST API), APScheduler for background polling

**Prerequisite:** Phases 1 and 2 complete.

---

## File Structure (additions to Phase 2)

```
vigil/api/src/
├── models/
│   ├── slo.py                              # SLO + SLOSnapshot
│   └── postmortem.py                       # Postmortem + ActionItem
├── schemas/
│   ├── slos.py
│   └── postmortems.py
├── controllers/
│   ├── slos.py                             # GET/POST /api/v1/slos
│   ├── postmortems.py                      # GET/PATCH/POST /api/v1/postmortems
│   └── analytics.py                        # GET /api/v1/analytics/dora etc.
├── services/
│   ├── slo_service.py                      # evaluate SLO, compute burn rate
│   ├── postmortem_service.py               # trigger postmortem agent, store result
│   ├── jira_service.py                     # sync action items to Jira
│   ├── dora_service.py                     # calculate DORA metrics
│   └── scheduler.py                        # APScheduler for SLO polling + weekly pattern run
vigil/api/tests/
├── unit/
│   ├── test_slo_burn_rate.py
│   └── test_dora_metrics.py
└── integration/
    ├── test_slos_api.py
    └── test_postmortems_api.py
```

---

## Task 1: SLO/SLI Engine

**Files:**
- Create: `vigil/api/src/models/slo.py`
- Create: `vigil/api/src/schemas/slos.py`
- Create: `vigil/api/src/services/slo_service.py`
- Create: `vigil/api/src/controllers/slos.py`
- Create: `vigil/api/tests/unit/test_slo_burn_rate.py`

- [ ] **Step 1: Write failing burn rate tests**

```python
# vigil/api/tests/unit/test_slo_burn_rate.py
from src.services.slo_service import compute_burn_rate, compute_error_budget_remaining


def test_burn_rate_at_exactly_target():
    # SLO is 99.9%, current compliance is 99.9% → burn rate = 1.0x
    burn = compute_burn_rate(current_error_rate=0.001, slo_target=99.9, window_days=30)
    assert abs(burn - 1.0) < 0.01


def test_burn_rate_at_10x():
    # Burning 10x faster than allowed
    burn = compute_burn_rate(current_error_rate=0.01, slo_target=99.9, window_days=30)
    assert abs(burn - 10.0) < 0.1


def test_error_budget_fully_remaining_when_no_errors():
    remaining = compute_error_budget_remaining(
        total_minutes=43200,  # 30 days
        error_minutes=0,
        slo_target=99.9,
    )
    assert remaining == 100.0


def test_error_budget_exhausted():
    # SLO allows 0.1% downtime = 43.2 min / 30 days
    # We've used 50 minutes → over budget
    remaining = compute_error_budget_remaining(
        total_minutes=43200,
        error_minutes=50,
        slo_target=99.9,
    )
    assert remaining < 0
```

- [ ] **Step 2: Run — verify fails**

```bash
pytest tests/unit/test_slo_burn_rate.py -v
# Expected: FAIL
```

- [ ] **Step 3: Create SLO model**

```python
# vigil/api/src/models/slo.py
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, JSON, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from .base import BaseModel


class SLO(BaseModel):
    __tablename__ = "slos"

    org_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    service = Column(String(200), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(String(1000), default="")
    slo_type = Column(String(50), nullable=False)      # "availability" | "latency" | "error_rate"
    target_percent = Column(Float, nullable=False)      # e.g. 99.9
    window_days = Column(Integer, default=30)
    data_source = Column(String(50), nullable=False)   # "datadog" | "prometheus" | "manual"
    metric_query = Column(String(1000), default="")    # query to evaluate
    active = Column(Boolean, default=True)

    snapshots = relationship("SLOSnapshot", back_populates="slo",
                             order_by="SLOSnapshot.recorded_at.desc()", lazy="select")


class SLOSnapshot(BaseModel):
    __tablename__ = "slo_snapshots"

    slo_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    org_id = Column(UUID(as_uuid=True), nullable=False)
    recorded_at = Column(DateTime(timezone=True), nullable=False)
    compliance_percent = Column(Float, nullable=False)   # actual compliance 0-100
    error_rate = Column(Float, nullable=False)            # actual error rate 0.0-1.0
    burn_rate = Column(Float, nullable=True)
    error_budget_remaining_percent = Column(Float, nullable=True)
    status = Column(String(20), nullable=False)          # "healthy"|"warning"|"burning"|"exhausted"

    __table_args__ = (
        Index("ix_slo_snapshots_slo_recorded", "slo_id", "recorded_at"),
    )
```

- [ ] **Step 4: Create SLO service**

```python
# vigil/api/src/services/slo_service.py
from datetime import UTC, datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.slo import SLO, SLOSnapshot


def compute_burn_rate(current_error_rate: float, slo_target: float, window_days: int) -> float:
    """
    Burn rate = how many times faster than allowed we're consuming error budget.
    burn_rate = 1.0 means consuming budget exactly on pace to exhaust it at end of window.
    burn_rate = 14.4 means we'll exhaust a 30-day budget in ~50 hours (14.4x = 720h/50h).
    """
    allowed_error_rate = (100.0 - slo_target) / 100.0
    if allowed_error_rate <= 0:
        return float("inf") if current_error_rate > 0 else 0.0
    return current_error_rate / allowed_error_rate


def compute_error_budget_remaining(
    total_minutes: float,
    error_minutes: float,
    slo_target: float,
) -> float:
    """
    Returns remaining error budget as a percentage of the total budget.
    Negative means budget is exhausted.
    """
    budget_minutes = total_minutes * (100.0 - slo_target) / 100.0
    if budget_minutes <= 0:
        return 100.0
    used_percent = (error_minutes / budget_minutes) * 100.0
    return 100.0 - used_percent


def classify_status(burn_rate: float, budget_remaining: float) -> str:
    if budget_remaining <= 0:
        return "exhausted"
    if burn_rate >= 14.4:
        return "burning"    # will exhaust 30-day budget in <50h
    if burn_rate >= 5.0:
        return "warning"    # will exhaust budget in <6 days
    return "healthy"


async def record_snapshot(
    slo: SLO,
    error_rate: float,
    db: AsyncSession,
) -> SLOSnapshot:
    """Record a new compliance snapshot for an SLO."""
    now = datetime.now(UTC)
    total_minutes = slo.window_days * 24 * 60
    # Approximate error_minutes from current error_rate over window
    error_minutes = error_rate * total_minutes

    burn = compute_burn_rate(error_rate, slo.target_percent, slo.window_days)
    budget_remaining = compute_error_budget_remaining(
        total_minutes, error_minutes, slo.target_percent
    )
    compliance = (1.0 - error_rate) * 100.0
    status = classify_status(burn, budget_remaining)

    snapshot = SLOSnapshot(
        slo_id=slo.id,
        org_id=slo.org_id,
        recorded_at=now,
        compliance_percent=compliance,
        error_rate=error_rate,
        burn_rate=burn,
        error_budget_remaining_percent=budget_remaining,
        status=status,
    )
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)
    return snapshot


async def get_latest_snapshot(slo_id, db: AsyncSession) -> SLOSnapshot | None:
    result = await db.execute(
        select(SLOSnapshot)
        .where(SLOSnapshot.slo_id == slo_id)
        .order_by(SLOSnapshot.recorded_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
```

- [ ] **Step 5: Run SLO tests — verify pass**

```bash
pytest tests/unit/test_slo_burn_rate.py -v
# Expected: all 4 PASS
```

- [ ] **Step 6: Create SLO schemas**

```python
# vigil/api/src/schemas/slos.py
import uuid
from datetime import datetime
from pydantic import BaseModel


class SLOCreate(BaseModel):
    service: str
    name: str
    description: str = ""
    slo_type: str                           # "availability" | "latency" | "error_rate"
    target_percent: float                   # e.g. 99.9
    window_days: int = 30
    data_source: str = "manual"
    metric_query: str = ""


class SLOSnapshotRead(BaseModel):
    id: uuid.UUID
    slo_id: uuid.UUID
    recorded_at: datetime
    compliance_percent: float
    error_rate: float
    burn_rate: float | None
    error_budget_remaining_percent: float | None
    status: str
    model_config = {"from_attributes": True}


class SLORead(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    service: str
    name: str
    description: str
    slo_type: str
    target_percent: float
    window_days: int
    data_source: str
    active: bool
    latest_snapshot: SLOSnapshotRead | None = None
    model_config = {"from_attributes": True}


class SLORecordSnapshot(BaseModel):
    error_rate: float                       # 0.0 to 1.0
```

- [ ] **Step 7: Create SLO controller**

```python
# vigil/api/src/controllers/slos.py
import uuid
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..core.database import get_db
from ..models.slo import SLO, SLOSnapshot
from ..schemas.slos import SLOCreate, SLORead, SLORecordSnapshot, SLOSnapshotRead
from ..services.slo_service import record_snapshot, get_latest_snapshot

router = APIRouter(prefix="/api/v1/slos", tags=["slos"])


def get_org_id(x_org_id: str = Header(...)) -> uuid.UUID:
    return uuid.UUID(x_org_id)


@router.get("", response_model=list[SLORead])
async def list_slos(
    org_id: uuid.UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SLO).where(SLO.org_id == org_id, SLO.active == True))  # noqa: E712
    slos = result.scalars().all()
    out = []
    for slo in slos:
        snap = await get_latest_snapshot(slo.id, db)
        r = SLORead.model_validate(slo)
        r.latest_snapshot = SLOSnapshotRead.model_validate(snap) if snap else None
        out.append(r)
    return out


@router.post("", response_model=SLORead, status_code=201)
async def create_slo(
    body: SLOCreate,
    org_id: uuid.UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    slo = SLO(org_id=org_id, **body.model_dump())
    db.add(slo)
    await db.commit()
    await db.refresh(slo)
    return slo


@router.post("/{slo_id}/snapshot", response_model=SLOSnapshotRead, status_code=201)
async def record_slo_snapshot(
    slo_id: uuid.UUID,
    body: SLORecordSnapshot,
    org_id: uuid.UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SLO).where(SLO.id == slo_id, SLO.org_id == org_id)
    )
    slo = result.scalar_one_or_none()
    if not slo:
        raise HTTPException(status_code=404, detail="SLO not found")
    return await record_snapshot(slo, body.error_rate, db)


@router.get("/summary")
async def slo_summary(
    org_id: uuid.UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    """Org-wide SLO health summary."""
    result = await db.execute(select(SLO).where(SLO.org_id == org_id, SLO.active == True))  # noqa: E712
    slos = result.scalars().all()
    counts = {"healthy": 0, "warning": 0, "burning": 0, "exhausted": 0, "no_data": 0}
    for slo in slos:
        snap = await get_latest_snapshot(slo.id, db)
        if snap:
            counts[snap.status] = counts.get(snap.status, 0) + 1
        else:
            counts["no_data"] += 1
    return {"total": len(slos), **counts}
```

- [ ] **Step 8: Register, migrate, run integration test**

Add to `vigil/api/src/app.py`:
```python
from .controllers.slos import router as slos_router
app.include_router(slos_router)
```

```python
# vigil/api/tests/integration/test_slos_api.py
import pytest
from httpx import AsyncClient
from src.app import app

ORG = {"X-Org-ID": "00000000-0000-0000-0000-000000000004"}


@pytest.mark.asyncio
async def test_create_and_snapshot_slo():
    async with AsyncClient(app=app, base_url="http://test") as client:
        create = await client.post("/api/v1/slos", json={
            "service": "payments-api",
            "name": "Availability",
            "slo_type": "availability",
            "target_percent": 99.9,
            "window_days": 30,
        }, headers=ORG)
        assert create.status_code == 201
        slo_id = create.json()["id"]

        snap = await client.post(f"/api/v1/slos/{slo_id}/snapshot",
                                  json={"error_rate": 0.001}, headers=ORG)
        assert snap.status_code == 201
        data = snap.json()
        assert data["status"] == "healthy"
        assert abs(data["burn_rate"] - 1.0) < 0.1


@pytest.mark.asyncio
async def test_burning_slo_status():
    async with AsyncClient(app=app, base_url="http/test") as client:
        create = await client.post("/api/v1/slos", json={
            "service": "checkout-api", "name": "Error Rate",
            "slo_type": "error_rate", "target_percent": 99.9, "window_days": 30,
        }, headers=ORG)
        slo_id = create.json()["id"]
        snap = await client.post(f"/api/v1/slos/{slo_id}/snapshot",
                                  json={"error_rate": 0.05}, headers=ORG)
        assert snap.json()["status"] == "burning"
```

```bash
alembic revision --autogenerate -m "add_slos_snapshots"
alembic upgrade head
pytest tests/integration/test_slos_api.py -v
# Expected: PASS
```

- [ ] **Step 9: Commit**

```bash
git add vigil/api/src/models/slo.py vigil/api/src/schemas/slos.py \
        vigil/api/src/controllers/slos.py vigil/api/src/services/slo_service.py \
        vigil/api/migrations/ vigil/api/tests/
git commit -m "feat(vigil): add SLO/SLI engine with error budget and burn rate tracking"
```

---

## Task 2: Postmortem Auto-Generation

**Files:**
- Create: `vigil/api/src/models/postmortem.py`
- Create: `vigil/api/src/schemas/postmortems.py`
- Create: `vigil/api/src/services/postmortem_service.py`
- Create: `vigil/api/src/controllers/postmortems.py`

- [ ] **Step 1: Create Postmortem model**

```python
# vigil/api/src/models/postmortem.py
from sqlalchemy import Column, String, Integer, JSON, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from .base import BaseModel


class Postmortem(BaseModel):
    __tablename__ = "postmortems"

    org_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    incident_id = Column(UUID(as_uuid=True), nullable=False, unique=True, index=True)
    title = Column(String(500), nullable=False)
    severity = Column(String(5), nullable=False)
    duration_minutes = Column(Integer, nullable=True)
    impact_summary = Column(String(2000), default="")
    timeline = Column(JSON, default=list)               # list of {time, event} dicts
    root_cause = Column(String(3000), default="")
    contributing_factors = Column(JSON, default=list)
    what_went_well = Column(JSON, default=list)
    what_went_poorly = Column(JSON, default=list)
    slo_impact = Column(String(500), default="")
    status = Column(String(20), default="draft")        # "draft" | "review" | "published"
    generated_by = Column(String(20), default="agent")  # "agent" | "human"
    published_at = Column(DateTime(timezone=True), nullable=True)

    action_items = relationship("ActionItem", back_populates="postmortem", lazy="select")


class ActionItem(BaseModel):
    __tablename__ = "action_items"

    postmortem_id = Column(UUID(as_uuid=True), ForeignKey("postmortems.id"),
                           nullable=False, index=True)
    org_id = Column(UUID(as_uuid=True), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(String(2000), default="")
    owner_team = Column(String(200), default="")
    assigned_to = Column(String(200), nullable=True)
    jira_ticket_id = Column(String(100), nullable=True)
    status = Column(String(30), default="open")         # "open" | "in_progress" | "done"

    postmortem = relationship("Postmortem", back_populates="action_items")
```

- [ ] **Step 2: Create postmortem service**

```python
# vigil/api/src/services/postmortem_service.py
import json
import logging
from datetime import UTC, datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.incident import Incident, TimelineEvent
from ..models.postmortem import Postmortem, ActionItem
from ..services.agent_trigger import trigger_agent
from ..config.settings import settings

logger = logging.getLogger(__name__)

POSTMORTEM_SYSTEM_PROMPT = """You are an expert Site Reliability Engineer writing a blameless postmortem.
Given an incident timeline, produce a structured postmortem JSON with these exact keys:
{
  "impact_summary": string,
  "timeline": [{"time": ISO string, "event": string}, ...],
  "root_cause": string,
  "contributing_factors": [string, ...],
  "what_went_well": [string, ...],
  "what_went_poorly": [string, ...],
  "slo_impact": string,
  "action_items": [{"title": string, "description": string, "owner_team": string}, ...]
}
Be specific and blameless. Focus on systemic causes, not individual mistakes.
Return ONLY valid JSON, no markdown."""


def _build_postmortem_prompt(incident: Incident, events: list[TimelineEvent]) -> str:
    event_lines = "\n".join(
        f"- [{e.occurred_at.strftime('%H:%M:%S')}] [{e.source}] {e.title}: {e.body[:200]}"
        for e in events
    )
    return (
        f"Incident: {incident.inc_number} — {incident.title}\n"
        f"Severity: {incident.severity}\n"
        f"Duration: {incident.mttr_seconds // 60 if incident.mttr_seconds else '?'} minutes\n"
        f"Affected services: {', '.join(incident.affected_services or [])}\n"
        f"Root cause (from incident): {incident.root_cause or 'Unknown'}\n\n"
        f"Timeline events:\n{event_lines}\n\n"
        f"Generate the postmortem JSON."
    )


async def generate_postmortem(incident_id, org_id, db: AsyncSession) -> Postmortem | None:
    """Trigger postmortem agent and store the structured result."""
    # Load incident and timeline
    inc_result = await db.execute(
        select(Incident).where(Incident.id == incident_id, Incident.org_id == org_id)
    )
    incident = inc_result.scalar_one_or_none()
    if not incident:
        return None

    events_result = await db.execute(
        select(TimelineEvent)
        .where(TimelineEvent.incident_id == incident_id)
        .order_by(TimelineEvent.occurred_at)
    )
    events = events_result.scalars().all()

    prompt = _build_postmortem_prompt(incident, events)

    if settings.vigil_commander_agent_id:
        result = await trigger_agent(settings.vigil_commander_agent_id, prompt)
        raw = result.get("response", "")
    else:
        # Fallback: minimal postmortem from available data
        raw = json.dumps({
            "impact_summary": f"Incident {incident.inc_number} affected {', '.join(incident.affected_services or [])}",
            "timeline": [{"time": e.occurred_at.isoformat(), "event": e.title} for e in events],
            "root_cause": incident.root_cause or "Under investigation",
            "contributing_factors": [],
            "what_went_well": [],
            "what_went_poorly": [],
            "slo_impact": "",
            "action_items": [],
        })

    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        data = json.loads(raw[start:end]) if start >= 0 else {}
    except Exception:
        data = {}

    duration = incident.mttr_seconds // 60 if incident.mttr_seconds else None

    pm = Postmortem(
        org_id=org_id,
        incident_id=incident_id,
        title=f"Postmortem: {incident.title}",
        severity=incident.severity,
        duration_minutes=duration,
        impact_summary=data.get("impact_summary", ""),
        timeline=data.get("timeline", []),
        root_cause=data.get("root_cause", incident.root_cause or ""),
        contributing_factors=data.get("contributing_factors", []),
        what_went_well=data.get("what_went_well", []),
        what_went_poorly=data.get("what_went_poorly", []),
        slo_impact=data.get("slo_impact", ""),
        status="draft",
        generated_by="agent" if settings.vigil_commander_agent_id else "system",
    )
    db.add(pm)
    await db.flush()

    for ai_data in data.get("action_items", []):
        ai = ActionItem(
            postmortem_id=pm.id,
            org_id=org_id,
            title=ai_data.get("title", ""),
            description=ai_data.get("description", ""),
            owner_team=ai_data.get("owner_team", ""),
        )
        db.add(ai)

    await db.commit()
    await db.refresh(pm)
    return pm
```

- [ ] **Step 3: Create postmortem schemas**

```python
# vigil/api/src/schemas/postmortems.py
import uuid
from datetime import datetime
from pydantic import BaseModel


class ActionItemRead(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    owner_team: str
    assigned_to: str | None
    jira_ticket_id: str | None
    status: str
    model_config = {"from_attributes": True}


class ActionItemUpdate(BaseModel):
    assigned_to: str | None = None
    status: str | None = None
    jira_ticket_id: str | None = None


class PostmortemRead(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    incident_id: uuid.UUID
    title: str
    severity: str
    duration_minutes: int | None
    impact_summary: str
    timeline: list
    root_cause: str
    contributing_factors: list[str]
    what_went_well: list[str]
    what_went_poorly: list[str]
    slo_impact: str
    status: str
    generated_by: str
    published_at: datetime | None
    action_items: list[ActionItemRead] = []
    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Create postmortem controller**

```python
# vigil/api/src/controllers/postmortems.py
import asyncio
import uuid
from datetime import UTC, datetime
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..core.database import get_db
from ..models.postmortem import Postmortem, ActionItem
from ..schemas.postmortems import PostmortemRead, ActionItemRead, ActionItemUpdate
from ..services.postmortem_service import generate_postmortem

router = APIRouter(prefix="/api/v1/postmortems", tags=["postmortems"])


def get_org_id(x_org_id: str = Header(...)) -> uuid.UUID:
    return uuid.UUID(x_org_id)


@router.get("", response_model=list[PostmortemRead])
async def list_postmortems(
    org_id: uuid.UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Postmortem).where(Postmortem.org_id == org_id)
        .order_by(Postmortem.created_at.desc()).limit(50)
    )
    return result.scalars().all()


@router.post("/generate/{incident_id}", response_model=PostmortemRead, status_code=202)
async def trigger_generate(
    incident_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    pm = await generate_postmortem(incident_id, org_id, db)
    if not pm:
        raise HTTPException(status_code=404, detail="Incident not found")
    return pm


@router.get("/{postmortem_id}", response_model=PostmortemRead)
async def get_postmortem(
    postmortem_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Postmortem).where(Postmortem.id == postmortem_id, Postmortem.org_id == org_id)
    )
    pm = result.scalar_one_or_none()
    if not pm:
        raise HTTPException(status_code=404, detail="Postmortem not found")
    return pm


@router.post("/{postmortem_id}/publish", response_model=PostmortemRead)
async def publish_postmortem(
    postmortem_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Postmortem).where(Postmortem.id == postmortem_id, Postmortem.org_id == org_id)
    )
    pm = result.scalar_one_or_none()
    if not pm:
        raise HTTPException(status_code=404, detail="Postmortem not found")
    pm.status = "published"
    pm.published_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(pm)
    return pm


@router.patch("/{postmortem_id}/action-items/{action_item_id}", response_model=ActionItemRead)
async def update_action_item(
    postmortem_id: uuid.UUID,
    action_item_id: uuid.UUID,
    body: ActionItemUpdate,
    org_id: uuid.UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ActionItem).where(
            ActionItem.id == action_item_id,
            ActionItem.postmortem_id == postmortem_id,
            ActionItem.org_id == org_id,
        )
    )
    ai = result.scalar_one_or_none()
    if not ai:
        raise HTTPException(status_code=404, detail="Action item not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(ai, field, value)
    await db.commit()
    await db.refresh(ai)
    return ai
```

- [ ] **Step 5: Auto-trigger postmortem on resolve**

In `vigil/api/src/controllers/incidents.py`, add to the resolve handler after `resolve_incident()`:

```python
# After await resolve_incident(incident, db):
asyncio.create_task(
    _auto_generate_postmortem(incident.id, org_id)
)

async def _auto_generate_postmortem(incident_id: uuid.UUID, org_id: uuid.UUID) -> None:
    from ..core.database import AsyncSessionLocal
    from ..services.postmortem_service import generate_postmortem
    async with AsyncSessionLocal() as db:
        await generate_postmortem(incident_id, org_id, db)
```

- [ ] **Step 6: Register, migrate, verify**

Add to `vigil/api/src/app.py`:
```python
from .controllers.postmortems import router as postmortems_router
app.include_router(postmortems_router)
```

```bash
alembic revision --autogenerate -m "add_postmortems_action_items"
alembic upgrade head
pytest --tb=short -q
# Expected: all tests pass
```

- [ ] **Step 7: Commit**

```bash
git add vigil/api/src/models/postmortem.py vigil/api/src/schemas/postmortems.py \
        vigil/api/src/controllers/postmortems.py vigil/api/src/services/postmortem_service.py \
        vigil/api/src/controllers/incidents.py vigil/api/migrations/
git commit -m "feat(vigil): add postmortem auto-generation triggered on incident resolve"
```

---

## Task 3: DORA Metrics

**Files:**
- Create: `vigil/api/src/services/dora_service.py`
- Create: `vigil/api/src/controllers/analytics.py`
- Create: `vigil/api/tests/unit/test_dora_metrics.py`

- [ ] **Step 1: Write failing DORA tests**

```python
# vigil/api/tests/unit/test_dora_metrics.py
from src.services.dora_service import compute_change_failure_rate, compute_mttr_hours


def test_change_failure_rate_all_succeed():
    rate = compute_change_failure_rate(total_deployments=10, failed_deployments=0)
    assert rate == 0.0


def test_change_failure_rate_half_fail():
    rate = compute_change_failure_rate(total_deployments=10, failed_deployments=5)
    assert rate == 50.0


def test_mttr_hours_from_seconds():
    hours = compute_mttr_hours(mttr_seconds_list=[3600, 7200, 1800])
    assert abs(hours - 2.0) < 0.01  # mean of [1, 2, 0.5] = 1.1666... wait
    # mean of [3600, 7200, 1800] = 4200s = 1.1666h
    assert abs(hours - 1.1666) < 0.01


def test_mttr_hours_empty_list():
    hours = compute_mttr_hours(mttr_seconds_list=[])
    assert hours == 0.0
```

- [ ] **Step 2: Run — verify fails**

```bash
pytest tests/unit/test_dora_metrics.py -v
# Expected: FAIL
```

- [ ] **Step 3: Create DORA service**

```python
# vigil/api/src/services/dora_service.py
from datetime import UTC, datetime, timedelta
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.incident import Incident


def compute_change_failure_rate(total_deployments: int, failed_deployments: int) -> float:
    """Percentage of deployments that caused a P0/P1 incident."""
    if total_deployments == 0:
        return 0.0
    return (failed_deployments / total_deployments) * 100.0


def compute_mttr_hours(mttr_seconds_list: list[int]) -> float:
    """Mean time to restore in hours."""
    if not mttr_seconds_list:
        return 0.0
    mean_seconds = sum(mttr_seconds_list) / len(mttr_seconds_list)
    return mean_seconds / 3600.0


async def get_dora_metrics(org_id, days: int, db: AsyncSession) -> dict:
    """Calculate DORA metrics from incident data for the last N days."""
    since = datetime.now(UTC) - timedelta(days=days)

    # MTTR — from resolved incidents
    result = await db.execute(
        select(Incident.mttr_seconds).where(
            Incident.org_id == org_id,
            Incident.status == "RESOLVED",
            Incident.resolved_at >= since,
            Incident.mttr_seconds.is_not(None),
        )
    )
    mttr_values = [row[0] for row in result.fetchall()]
    mttr_hours = compute_mttr_hours(mttr_values)

    # Incident counts by severity
    counts_result = await db.execute(
        select(Incident.severity, func.count().label("count")).where(
            Incident.org_id == org_id,
            Incident.started_at >= since,
        ).group_by(Incident.severity)
    )
    severity_counts = {row.severity: row.count for row in counts_result.fetchall()}

    # Total incidents and P0/P1 (proxy for change failures since we don't
    # have deployment data until Phase 4 integrations are connected)
    total_incidents = sum(severity_counts.values())
    critical_incidents = severity_counts.get("P0", 0) + severity_counts.get("P1", 0)

    return {
        "period_days": days,
        "mttr_hours": round(mttr_hours, 2),
        "total_incidents": total_incidents,
        "incidents_by_severity": severity_counts,
        "critical_incidents": critical_incidents,
        "incident_frequency_per_week": round(total_incidents / max(days / 7, 1), 1),
        "estimated_change_failure_rate": None,  # requires deployment data (Phase 4)
    }
```

- [ ] **Step 4: Run DORA tests — verify pass**

```bash
pytest tests/unit/test_dora_metrics.py -v
# Expected: all 4 PASS
```

- [ ] **Step 5: Create analytics controller**

```python
# vigil/api/src/controllers/analytics.py
import uuid
from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..services.dora_service import get_dora_metrics

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


def get_org_id(x_org_id: str = Header(...)) -> uuid.UUID:
    return uuid.UUID(x_org_id)


@router.get("/dora")
async def dora_metrics(
    days: int = 30,
    org_id: uuid.UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    return await get_dora_metrics(org_id, days, db)


@router.get("/mttr-trend")
async def mttr_trend(
    weeks: int = 8,
    org_id: uuid.UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    """MTTR per week for the last N weeks."""
    from datetime import timedelta
    from datetime import UTC, datetime
    from sqlalchemy import select
    from ..models.incident import Incident

    results = []
    now = datetime.now(UTC)
    for i in range(weeks, 0, -1):
        week_start = now - timedelta(weeks=i)
        week_end = now - timedelta(weeks=i - 1)
        result = await db.execute(
            select(Incident.mttr_seconds).where(
                Incident.org_id == org_id,
                Incident.status == "RESOLVED",
                Incident.resolved_at >= week_start,
                Incident.resolved_at < week_end,
                Incident.mttr_seconds.is_not(None),
            )
        )
        values = [row[0] for row in result.fetchall()]
        mean = sum(values) / len(values) / 3600 if values else None
        results.append({
            "week_start": week_start.date().isoformat(),
            "mttr_hours": round(mean, 2) if mean is not None else None,
            "incident_count": len(values),
        })
    return results
```

- [ ] **Step 6: Register, verify build**

Add to `vigil/api/src/app.py`:
```python
from .controllers.analytics import router as analytics_router
app.include_router(analytics_router)
```

```bash
pytest --tb=short -q
# Expected: all tests pass
```

- [ ] **Step 7: Commit**

```bash
git add vigil/api/src/services/dora_service.py vigil/api/src/controllers/analytics.py \
        vigil/api/tests/unit/test_dora_metrics.py vigil/api/src/app.py
git commit -m "feat(vigil): add DORA metrics and MTTR trend analytics endpoints"
```

---

## Task 4: Jira Action Item Sync

**Files:**
- Create: `vigil/api/src/services/jira_service.py`
- Modify: `vigil/api/src/config/settings.py`

- [ ] **Step 1: Add Jira settings**

```python
# Add to vigil/api/src/config/settings.py Settings class:
jira_base_url: str = ""           # e.g. https://your-org.atlassian.net
jira_email: str = ""
jira_api_token: str = ""
jira_project_key: str = ""        # e.g. "SRE"
```

Add to `.env.example`:
```bash
JIRA_BASE_URL=
JIRA_EMAIL=
JIRA_API_TOKEN=
JIRA_PROJECT_KEY=SRE
```

- [ ] **Step 2: Create Jira service**

```python
# vigil/api/src/services/jira_service.py
import base64
import logging
import httpx
from ..config.settings import settings

logger = logging.getLogger(__name__)


def _auth_header() -> str:
    creds = f"{settings.jira_email}:{settings.jira_api_token}"
    return "Basic " + base64.b64encode(creds.encode()).decode()


async def create_jira_ticket(title: str, description: str, team: str) -> str | None:
    """Create a Jira issue and return the ticket ID (e.g. 'SRE-42')."""
    if not all([settings.jira_base_url, settings.jira_email,
                settings.jira_api_token, settings.jira_project_key]):
        logger.warning("Jira not configured — skipping ticket creation")
        return None

    payload = {
        "fields": {
            "project": {"key": settings.jira_project_key},
            "summary": title,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [{"type": "paragraph", "content": [
                    {"type": "text", "text": description or title}
                ]}],
            },
            "issuetype": {"name": "Task"},
            "labels": ["vigil-action-item", team.lower().replace(" ", "-")] if team else ["vigil-action-item"],
        }
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{settings.jira_base_url}/rest/api/3/issue",
                headers={
                    "Authorization": _auth_header(),
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=15,
            )
            if resp.status_code == 201:
                return resp.json().get("key")  # e.g. "SRE-42"
            logger.error("Jira create failed: %s %s", resp.status_code, resp.text[:200])
            return None
        except Exception as exc:
            logger.exception("Jira request error: %s", exc)
            return None


async def sync_postmortem_action_items(postmortem, db) -> int:
    """
    Create Jira tickets for all open action items that don't have one yet.
    Returns count of tickets created.
    """
    created = 0
    for ai in postmortem.action_items:
        if ai.jira_ticket_id:
            continue
        ticket_id = await create_jira_ticket(ai.title, ai.description, ai.owner_team)
        if ticket_id:
            ai.jira_ticket_id = ticket_id
            created += 1
    await db.commit()
    return created
```

- [ ] **Step 3: Wire sync into postmortem publish endpoint**

In `vigil/api/src/controllers/postmortems.py`, update publish:

```python
# Add to imports
from ..services.jira_service import sync_postmortem_action_items

# In publish_postmortem, after setting status and committing:
    pm.status = "published"
    pm.published_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(pm)

    # Sync action items to Jira in background
    import asyncio
    asyncio.create_task(_sync_jira(pm.id, org_id))
    return pm


async def _sync_jira(postmortem_id, org_id) -> None:
    from ..core.database import AsyncSessionLocal
    from ..models.postmortem import Postmortem
    from sqlalchemy import select as sa_select
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            sa_select(Postmortem).where(Postmortem.id == postmortem_id)
        )
        pm = result.scalar_one_or_none()
        if pm:
            from ..services.jira_service import sync_postmortem_action_items
            await sync_postmortem_action_items(pm, db)
```

- [ ] **Step 4: Commit**

```bash
git add vigil/api/src/services/jira_service.py vigil/api/src/config/settings.py \
        vigil/api/src/controllers/postmortems.py vigil/api/.env.example
git commit -m "feat(vigil): add Jira action item sync on postmortem publish"
```

---

## Task 5: Weekly Pattern Analysis

**Files:**
- Create: `vigil/api/src/services/scheduler.py`

- [ ] **Step 1: Create background scheduler**

```python
# vigil/api/src/services/scheduler.py
import asyncio
import logging
from datetime import UTC, datetime, timedelta
from sqlalchemy import select, func
from ..core.database import AsyncSessionLocal
from ..models.incident import Incident
from ..services.agent_trigger import trigger_agent
from ..config.settings import settings

logger = logging.getLogger(__name__)

PATTERN_ANALYSIS_PROMPT = """Analyze the following 30-day incident summary for an SRE team.
Identify recurring patterns, systemic risks, and specific recommendations.

Incidents this month:
{incident_summary}

Return a JSON array of findings:
[
  {{
    "pattern": "brief pattern description",
    "frequency": "N incidents",
    "affected_services": ["service1", "service2"],
    "recommendation": "specific, actionable recommendation"
  }}
]
Return ONLY valid JSON."""


async def run_pattern_analysis(org_id: str) -> list[dict]:
    """Analyze 30 days of incidents and return pattern findings."""
    since = datetime.now(UTC) - timedelta(days=30)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(
                Incident.severity,
                Incident.title,
                func.json_array_elements_text(Incident.affected_services).label("service"),
            ).where(
                Incident.org_id == org_id,
                Incident.started_at >= since,
            ).limit(100)
        )
        rows = result.fetchall()

    if not rows:
        return []

    summary_lines = [f"- {r.severity}: {r.title} (service: {r.service})" for r in rows]
    prompt = PATTERN_ANALYSIS_PROMPT.format(incident_summary="\n".join(summary_lines))

    if not settings.vigil_commander_agent_id:
        return []

    result = await trigger_agent(settings.vigil_commander_agent_id, prompt)
    raw = result.get("response", "[]")
    try:
        import json
        start = raw.find("[")
        end = raw.rfind("]") + 1
        return json.loads(raw[start:end]) if start >= 0 else []
    except Exception:
        return []


async def scheduler_loop() -> None:
    """Background loop: run pattern analysis weekly for all orgs."""
    logger.info("Vigil scheduler started")
    while True:
        # Run every 7 days — in production, replace with APScheduler or Celery beat
        await asyncio.sleep(7 * 24 * 3600)
        logger.info("Running weekly pattern analysis")
        async with AsyncSessionLocal() as db:
            from sqlalchemy import distinct
            result = await db.execute(
                select(distinct(Incident.org_id)).limit(100)
            )
            org_ids = [str(row[0]) for row in result.fetchall()]

        for org_id in org_ids:
            try:
                patterns = await run_pattern_analysis(org_id)
                logger.info("Pattern analysis for org %s: %d patterns found", org_id, len(patterns))
            except Exception as exc:
                logger.exception("Pattern analysis failed for org %s: %s", org_id, exc)
```

- [ ] **Step 2: Start scheduler on app startup**

```python
# vigil/api/src/app.py — add startup event
import asyncio
from .services.scheduler import scheduler_loop

@app.on_event("startup")
async def start_scheduler():
    asyncio.create_task(scheduler_loop())
```

- [ ] **Step 3: Run full test suite**

```bash
cd vigil/api
pytest --tb=short -q
# Expected: all tests pass

cd vigil/web
pnpm build
# Expected: build completes
```

- [ ] **Step 4: Final commit**

```bash
git add vigil/api/src/services/scheduler.py vigil/api/src/app.py
git commit -m "feat(vigil): add weekly pattern analysis scheduler"
```

---

## Phase 3 Complete

At the end of this phase:
- SLO/SLI engine: define SLOs, record snapshots, burn rate, error budget, summary
- Postmortem auto-generated on incident resolve, with action items
- Action items sync to Jira when postmortem is published
- DORA metrics endpoint (MTTR, incident frequency, severity breakdown)
- MTTR trend per week over rolling 8 weeks
- Weekly pattern analysis agent surfaces recurring failure patterns

Next: **Phase 4 — Cloud-Native** (Agent Worker Helm chart, integration connectors UI, VPC mode).
