# Vigil Phase 1 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Vigil API service with alert ingestion, deduplication, correlation, incident lifecycle engine, service catalog, and on-call paging — the data foundation every subsequent phase depends on.

**Architecture:** New FastAPI service at `vigil/api/` in the monorepo. Uses its own Postgres database (separate from Synkora) with `org_id` on every table for multi-tenancy. Redis Streams decouple alert ingestion from processing. Vigil frontend Incidents page is wired to the real Vigil API at the end of this phase.

**Tech Stack:** FastAPI, SQLAlchemy 2 (async), Alembic, asyncpg, redis.asyncio, Pydantic v2, pytest-asyncio, uv

---

## File Structure

```
vigil/api/
├── src/
│   ├── app.py                              # FastAPI entry point + router registration
│   ├── config/
│   │   └── settings.py                     # Pydantic BaseSettings
│   ├── core/
│   │   ├── database.py                     # Async engine, session factory, get_db dep
│   │   └── redis.py                        # Redis async connection, get_redis dep
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py                         # BaseModel: UUID PK, created_at, updated_at
│   │   ├── service.py                      # Service (catalog entry + dependency graph)
│   │   ├── alert.py                        # AlertGroup
│   │   ├── incident.py                     # Incident + TimelineEvent
│   │   └── oncall.py                       # OnCallSchedule
│   ├── schemas/
│   │   ├── services.py
│   │   ├── alerts.py
│   │   └── incidents.py
│   ├── controllers/
│   │   ├── services.py                     # GET/POST/PATCH /api/v1/services
│   │   ├── alerts.py                       # POST /api/v1/alerts/ingest
│   │   └── incidents.py                    # GET/POST/PATCH /api/v1/incidents
│   └── services/
│       ├── alert_ingestion.py              # compute_fingerprint, stream publish
│       ├── alert_worker.py                 # Redis Stream consumer: dedup + correlate
│       ├── incident_service.py             # state machine, MTTR, next inc number
│       └── notification_service.py         # page on-call via Slack
├── migrations/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_base_model.py
│   │   ├── test_alert_fingerprint.py
│   │   ├── test_alert_correlation.py
│   │   └── test_incident_lifecycle.py
│   └── integration/
│       ├── test_services_api.py
│       ├── test_alert_ingestion_api.py
│       └── test_incidents_api.py
├── pyproject.toml
├── Dockerfile
├── alembic.ini
└── .env.example
```

---

## Task 1: Project Skeleton

**Files:**
- Create: `vigil/api/pyproject.toml`
- Create: `vigil/api/src/app.py`
- Create: `vigil/api/src/config/settings.py`
- Create: `vigil/api/src/core/database.py`
- Create: `vigil/api/src/core/redis.py`
- Create: `vigil/api/.env.example`

- [ ] **Step 1: Create pyproject.toml**

```toml
# vigil/api/pyproject.toml
[project]
name = "vigil-api"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "sqlalchemy>=2.0.0",
    "asyncpg>=0.29.0",
    "alembic>=1.13.0",
    "pydantic>=2.7.0",
    "pydantic-settings>=2.3.0",
    "redis>=5.0.0",
    "httpx>=0.27.0",
    "python-jose[cryptography]>=3.3.0",
    "cryptography>=42.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "anyio>=4.0.0",
    "httpx>=0.27.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 120
target-version = "py311"
select = ["E", "W", "F", "I", "B", "C4", "UP"]
```

- [ ] **Step 2: Create settings**

```python
# vigil/api/src/config/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/vigil"
    redis_url: str = "redis://localhost:6379/1"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    synkora_api_url: str = "http://localhost:5001"
    synkora_admin_token: str = ""
    slack_bot_token: str = ""
    alert_dedup_ttl: int = 900           # seconds
    alert_correlation_window: int = 5    # minutes
    vigil_triage_agent_id: str = ""
    vigil_commander_agent_id: str = ""
    connector_encryption_key: str = ""


settings = Settings()
```

- [ ] **Step 3: Create database core**

```python
# vigil/api/src/core/database.py
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from ..config.settings import settings

engine = create_async_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=10,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

- [ ] **Step 4: Create Redis core**

```python
# vigil/api/src/core/redis.py
from redis.asyncio import Redis, ConnectionPool
from ..config.settings import settings

_pool: ConnectionPool | None = None


def get_redis_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool.from_url(
            settings.redis_url,
            max_connections=50,
            decode_responses=True,
        )
    return _pool


async def get_redis() -> Redis:
    return Redis(connection_pool=get_redis_pool())
```

- [ ] **Step 5: Create app.py**

```python
# vigil/api/src/app.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Vigil API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "vigil-api"}
```

- [ ] **Step 6: Create .env.example**

```bash
# vigil/api/.env.example
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/vigil
REDIS_URL=redis://localhost:6379/1
JWT_SECRET=change-me-in-production
SYNKORA_API_URL=http://localhost:5001
SYNKORA_ADMIN_TOKEN=
SLACK_BOT_TOKEN=
VIGIL_TRIAGE_AGENT_ID=
VIGIL_COMMANDER_AGENT_ID=
CONNECTOR_ENCRYPTION_KEY=
```

- [ ] **Step 7: Install deps and verify app starts**

```bash
cd vigil/api
uv sync
uvicorn src.app:app --port 5002 --reload
# Expected: Uvicorn running on http://0.0.0.0:5002

curl http://localhost:5002/health
# Expected: {"status":"ok","service":"vigil-api"}
```

---

## Task 2: Base Model + Alembic Setup

**Files:**
- Create: `vigil/api/src/models/base.py`
- Create: `vigil/api/src/models/__init__.py`
- Create: `vigil/api/alembic.ini`
- Create: `vigil/api/migrations/env.py`
- Create: `vigil/api/migrations/script.py.mako`
- Create: `vigil/api/tests/unit/test_base_model.py`

- [ ] **Step 1: Write failing test**

```python
# vigil/api/tests/unit/test_base_model.py
import uuid
from sqlalchemy import Column, String


def test_base_model_has_uuid_pk():
    from src.models.base import BaseModel

    class SampleModel(BaseModel):
        __tablename__ = "sample_test_unique_abc"
        name = Column(String(100))

    instance = SampleModel(name="test")
    # id is None until flushed to DB, but default is callable
    assert SampleModel.id.default is not None


def test_base_model_has_timestamps():
    from src.models.base import BaseModel
    assert hasattr(BaseModel, "created_at")
    assert hasattr(BaseModel, "updated_at")
```

- [ ] **Step 2: Run — verify fails**

```bash
cd vigil/api
pytest tests/unit/test_base_model.py -v
# Expected: FAIL — module not found
```

- [ ] **Step 3: Create base model**

```python
# vigil/api/src/models/base.py
import uuid
from datetime import UTC, datetime
from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class BaseModel(Base):
    __abstract__ = True

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
```

- [ ] **Step 4: Create models __init__**

```python
# vigil/api/src/models/__init__.py
from .base import Base, BaseModel

__all__ = ["Base", "BaseModel"]
```

- [ ] **Step 5: Run test — verify passes**

```bash
pytest tests/unit/test_base_model.py -v
# Expected: PASS
```

- [ ] **Step 6: Configure Alembic**

```ini
# vigil/api/alembic.ini
[alembic]
script_location = migrations
prepend_sys_path = .
sqlalchemy.url = postgresql+asyncpg://postgres:postgres@localhost:5432/vigil

[loggers]
keys = root,sqlalchemy,alembic
[handlers]
keys = console
[formatters]
keys = generic
[logger_root]
level = WARN
handlers = console
qualname =
[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine
[logger_alembic]
level = INFO
handlers =
qualname = alembic
[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic
[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

```
## vigil/api/migrations/script.py.mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

```python
# vigil/api/migrations/env.py
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
from src.models.base import Base
# Import all models to register them with Base.metadata
from src.models import service, alert, incident, oncall  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 7: Commit**

```bash
git add vigil/api/
git commit -m "feat(vigil): add API skeleton, base model, Alembic config"
```

---

## Task 3: Service Catalog

**Files:**
- Create: `vigil/api/src/models/service.py`
- Create: `vigil/api/src/schemas/services.py`
- Create: `vigil/api/src/controllers/services.py`
- Create: `vigil/api/tests/integration/test_services_api.py`

- [ ] **Step 1: Write failing integration tests**

```python
# vigil/api/tests/integration/test_services_api.py
import pytest
from httpx import AsyncClient
from src.app import app

ORG = {"X-Org-ID": "00000000-0000-0000-0000-000000000001"}


@pytest.mark.asyncio
async def test_create_service():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post("/api/v1/services", json={
            "name": "payments-api",
            "slug": "payments-api",
            "description": "Handles payment processing",
            "team": "payments",
            "tier": 1,
            "dependencies": ["payments-db", "fraud-service"],
        }, headers=ORG)
    assert resp.status_code == 201
    data = resp.json()
    assert data["slug"] == "payments-api"
    assert data["tier"] == 1
    assert "id" in data


@pytest.mark.asyncio
async def test_list_services():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.get("/api/v1/services", headers=ORG)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_blast_radius_returns_dependents():
    async with AsyncClient(app=app, base_url="http://test") as client:
        await client.post("/api/v1/services", json={
            "name": "payments-db", "slug": "payments-db",
            "team": "payments", "tier": 1, "dependencies": [],
        }, headers=ORG)
        await client.post("/api/v1/services", json={
            "name": "payments-api", "slug": "blast-test-payments-api",
            "team": "payments", "tier": 1, "dependencies": ["payments-db"],
        }, headers=ORG)
        resp = await client.get("/api/v1/services/payments-db/blast-radius", headers=ORG)
    assert resp.status_code == 200
    slugs = [s["slug"] for s in resp.json()]
    assert "blast-test-payments-api" in slugs
```

- [ ] **Step 2: Run — verify fails**

```bash
pytest tests/integration/test_services_api.py -v
# Expected: FAIL — routes not defined
```

- [ ] **Step 3: Create Service model**

```python
# vigil/api/src/models/service.py
from sqlalchemy import Column, String, Integer, JSON, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from .base import BaseModel


class Service(BaseModel):
    __tablename__ = "services"

    org_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    slug = Column(String(200), nullable=False)
    description = Column(String(1000), default="")
    team = Column(String(200), default="")
    tier = Column(Integer, default=2)           # 1=critical 2=important 3=supporting
    repo_url = Column(String(500), nullable=True)
    runbook_url = Column(String(500), nullable=True)
    oncall_schedule_id = Column(UUID(as_uuid=True), nullable=True)
    dependencies = Column(JSON, default=list)   # list of service slugs
    tags = Column(JSON, default=dict)

    __table_args__ = (
        UniqueConstraint("org_id", "slug", name="uq_service_org_slug"),
    )
```

- [ ] **Step 4: Create schemas**

```python
# vigil/api/src/schemas/services.py
import uuid
from datetime import datetime
from pydantic import BaseModel


class ServiceCreate(BaseModel):
    name: str
    slug: str
    description: str = ""
    team: str = ""
    tier: int = 2
    repo_url: str | None = None
    runbook_url: str | None = None
    dependencies: list[str] = []
    tags: dict = {}


class ServiceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    team: str | None = None
    tier: int | None = None
    dependencies: list[str] | None = None
    tags: dict | None = None


class ServiceRead(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    slug: str
    description: str
    team: str
    tier: int
    repo_url: str | None
    dependencies: list[str]
    tags: dict
    created_at: datetime
    model_config = {"from_attributes": True}
```

- [ ] **Step 5: Create controller**

```python
# vigil/api/src/controllers/services.py
import uuid
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..core.database import get_db
from ..models.service import Service
from ..schemas.services import ServiceCreate, ServiceUpdate, ServiceRead

router = APIRouter(prefix="/api/v1/services", tags=["services"])


def get_org_id(x_org_id: str = Header(...)) -> uuid.UUID:
    return uuid.UUID(x_org_id)


@router.get("", response_model=list[ServiceRead])
async def list_services(org_id: uuid.UUID = Depends(get_org_id),
                         db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Service).where(Service.org_id == org_id))
    return result.scalars().all()


@router.post("", response_model=ServiceRead, status_code=201)
async def create_service(body: ServiceCreate,
                          org_id: uuid.UUID = Depends(get_org_id),
                          db: AsyncSession = Depends(get_db)):
    service = Service(org_id=org_id, **body.model_dump())
    db.add(service)
    await db.commit()
    await db.refresh(service)
    return service


@router.get("/{slug}", response_model=ServiceRead)
async def get_service(slug: str,
                       org_id: uuid.UUID = Depends(get_org_id),
                       db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Service).where(Service.org_id == org_id, Service.slug == slug)
    )
    svc = result.scalar_one_or_none()
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    return svc


@router.get("/{slug}/blast-radius", response_model=list[ServiceRead])
async def blast_radius(slug: str,
                        org_id: uuid.UUID = Depends(get_org_id),
                        db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Service).where(Service.org_id == org_id))
    all_services = result.scalars().all()
    return [s for s in all_services if slug in (s.dependencies or [])]


@router.patch("/{slug}", response_model=ServiceRead)
async def update_service(slug: str, body: ServiceUpdate,
                          org_id: uuid.UUID = Depends(get_org_id),
                          db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Service).where(Service.org_id == org_id, Service.slug == slug)
    )
    svc = result.scalar_one_or_none()
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(svc, field, value)
    await db.commit()
    await db.refresh(svc)
    return svc
```

- [ ] **Step 6: Register router and migrate**

```python
# vigil/api/src/app.py — add:
from .controllers.services import router as services_router
app.include_router(services_router)
```

```python
# vigil/api/src/models/__init__.py — update:
from .base import Base, BaseModel
from .service import Service
__all__ = ["Base", "BaseModel", "Service"]
```

```bash
cd vigil/api
alembic revision --autogenerate -m "add_services_table"
alembic upgrade head
```

- [ ] **Step 7: Run tests — verify pass**

```bash
pytest tests/integration/test_services_api.py -v
# Expected: all 3 PASS
```

- [ ] **Step 8: Commit**

```bash
git add vigil/api/src/models/service.py vigil/api/src/schemas/services.py \
        vigil/api/src/controllers/services.py vigil/api/src/app.py \
        vigil/api/src/models/__init__.py vigil/api/migrations/
git commit -m "feat(vigil): add service catalog with blast radius"
```

---

## Task 4: Alert + Incident Models

**Files:**
- Create: `vigil/api/src/models/alert.py`
- Create: `vigil/api/src/models/incident.py`
- Create: `vigil/api/src/models/oncall.py`
- Create: `vigil/api/src/services/incident_service.py`
- Create: `vigil/api/tests/unit/test_incident_lifecycle.py`

- [ ] **Step 1: Write failing lifecycle test**

```python
# vigil/api/tests/unit/test_incident_lifecycle.py
from src.services.incident_service import can_transition, VALID_TRANSITIONS


def test_detected_can_go_to_investigating():
    assert can_transition("DETECTED", "INVESTIGATING") is True


def test_resolved_cannot_go_back():
    assert can_transition("RESOLVED", "INVESTIGATING") is False


def test_all_statuses_covered():
    expected = {"DETECTED", "INVESTIGATING", "IDENTIFIED",
                "MITIGATING", "MONITORING", "RESOLVED"}
    assert set(VALID_TRANSITIONS.keys()) == expected
```

- [ ] **Step 2: Run — verify fails**

```bash
pytest tests/unit/test_incident_lifecycle.py -v
# Expected: FAIL
```

- [ ] **Step 3: Create Alert model**

```python
# vigil/api/src/models/alert.py
from datetime import UTC, datetime
from sqlalchemy import Column, String, Integer, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from .base import BaseModel


class AlertGroup(BaseModel):
    __tablename__ = "alert_groups"

    org_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    fingerprint = Column(String(64), nullable=False, index=True)
    source = Column(String(50), nullable=False)
    alert_name = Column(String(200), nullable=False)
    service = Column(String(200), nullable=False)
    labels = Column(JSON, default=dict)
    first_fired_at = Column(DateTime(timezone=True), nullable=False,
                            default=lambda: datetime.now(UTC))
    last_fired_at = Column(DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(UTC))
    alert_count = Column(Integer, default=1)
    status = Column(String(20), default="firing")    # "firing"|"resolved"|"suppressed"
    triage_result = Column(JSON, nullable=True)
    incident_id = Column(UUID(as_uuid=True), nullable=True, index=True)
```

- [ ] **Step 4: Create Incident model**

```python
# vigil/api/src/models/incident.py
from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from .base import BaseModel


class Incident(BaseModel):
    __tablename__ = "incidents"

    org_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    inc_number = Column(String(20), nullable=False)    # INC-0001
    title = Column(String(500), nullable=False)
    severity = Column(String(5), nullable=False)       # P0|P1|P2|P3
    status = Column(String(30), default="DETECTED")
    started_at = Column(DateTime(timezone=True), nullable=False)
    detected_at = Column(DateTime(timezone=True), nullable=False)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    mttr_seconds = Column(Integer, nullable=True)
    assigned_to = Column(UUID(as_uuid=True), nullable=True)
    alert_group_id = Column(UUID(as_uuid=True), nullable=True)
    affected_services = Column(JSON, default=list)
    root_cause = Column(String(2000), nullable=True)

    timeline_events = relationship(
        "TimelineEvent",
        back_populates="incident",
        order_by="TimelineEvent.occurred_at",
        lazy="select",
    )


class TimelineEvent(BaseModel):
    __tablename__ = "timeline_events"

    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id"),
                         nullable=False, index=True)
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    source = Column(String(100), nullable=False)
    event_type = Column(String(50), nullable=False)
    title = Column(String(500), nullable=False)
    body = Column(String(5000), default="")
    event_metadata = Column(JSON, default=dict)
    author = Column(String(200), nullable=False)

    incident = relationship("Incident", back_populates="timeline_events")
```

- [ ] **Step 5: Create OnCall model**

```python
# vigil/api/src/models/oncall.py
from sqlalchemy import Column, String, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID
from .base import BaseModel


class OnCallSchedule(BaseModel):
    __tablename__ = "oncall_schedules"

    org_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    team = Column(String(200), nullable=False)
    rotation_type = Column(String(20), default="weekly")
    participants = Column(JSON, default=list)           # Slack user IDs or emails
    current_oncall = Column(String(200), nullable=True) # Slack user ID
    handoff_hour_utc = Column(String(5), default="09:00")
    escalation_policy = Column(JSON, default=dict)
    pagerduty_schedule_id = Column(String(100), nullable=True)
    active = Column(Boolean, default=True)
```

- [ ] **Step 6: Create incident service with state machine**

```python
# vigil/api/src/services/incident_service.py
from datetime import UTC, datetime
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

VALID_TRANSITIONS: dict[str, list[str]] = {
    "DETECTED":      ["INVESTIGATING"],
    "INVESTIGATING": ["IDENTIFIED", "MONITORING", "RESOLVED"],
    "IDENTIFIED":    ["MITIGATING", "MONITORING"],
    "MITIGATING":    ["MONITORING", "RESOLVED"],
    "MONITORING":    ["RESOLVED", "INVESTIGATING"],
    "RESOLVED":      [],
}


def can_transition(current: str, target: str) -> bool:
    return target in VALID_TRANSITIONS.get(current, [])


async def resolve_incident(incident, db: AsyncSession) -> None:
    now = datetime.now(UTC)
    incident.status = "RESOLVED"
    incident.resolved_at = now
    incident.mttr_seconds = int((now - incident.started_at).total_seconds())
    await db.commit()
    await db.refresh(incident)


async def get_next_inc_number(org_id, db: AsyncSession) -> str:
    from ..models.incident import Incident
    result = await db.execute(
        select(func.count()).where(Incident.org_id == org_id)
    )
    count = result.scalar() or 0
    return f"INC-{count + 1:04d}"
```

- [ ] **Step 7: Run lifecycle test — verify passes**

```bash
pytest tests/unit/test_incident_lifecycle.py -v
# Expected: all 3 PASS
```

- [ ] **Step 8: Update models __init__ and migrate**

```python
# vigil/api/src/models/__init__.py
from .base import Base, BaseModel
from .service import Service
from .alert import AlertGroup
from .incident import Incident, TimelineEvent
from .oncall import OnCallSchedule

__all__ = ["Base", "BaseModel", "Service", "AlertGroup",
           "Incident", "TimelineEvent", "OnCallSchedule"]
```

```bash
alembic revision --autogenerate -m "add_alert_groups_incidents_timeline_oncall"
alembic upgrade head
```

- [ ] **Step 9: Commit**

```bash
git add vigil/api/src/models/ vigil/api/src/services/incident_service.py \
        vigil/api/migrations/ vigil/api/tests/
git commit -m "feat(vigil): add alert, incident, timeline, and on-call models"
```

---

## Task 5: Alert Ingestion API + Deduplication

**Files:**
- Create: `vigil/api/src/services/alert_ingestion.py`
- Create: `vigil/api/src/schemas/alerts.py`
- Create: `vigil/api/src/controllers/alerts.py`
- Create: `vigil/api/tests/unit/test_alert_fingerprint.py`
- Create: `vigil/api/tests/integration/test_alert_ingestion_api.py`

- [ ] **Step 1: Write failing fingerprint unit tests**

```python
# vigil/api/tests/unit/test_alert_fingerprint.py
from src.services.alert_ingestion import compute_fingerprint


def test_same_inputs_same_fingerprint():
    fp1 = compute_fingerprint("datadog", "high_error_rate", "payments-api",
                               {"env": "prod", "region": "us-east-1"})
    fp2 = compute_fingerprint("datadog", "high_error_rate", "payments-api",
                               {"env": "prod", "region": "us-east-1"})
    assert fp1 == fp2


def test_different_service_different_fingerprint():
    fp1 = compute_fingerprint("datadog", "high_error_rate", "payments-api", {})
    fp2 = compute_fingerprint("datadog", "high_error_rate", "checkout-api", {})
    assert fp1 != fp2


def test_label_order_independent():
    fp1 = compute_fingerprint("prom", "crash", "worker", {"pod": "abc", "ns": "prod"})
    fp2 = compute_fingerprint("prom", "crash", "worker", {"ns": "prod", "pod": "abc"})
    assert fp1 == fp2


def test_volatile_labels_excluded():
    fp1 = compute_fingerprint("cw", "cpu", "api", {"timestamp": "t1", "env": "prod"})
    fp2 = compute_fingerprint("cw", "cpu", "api", {"timestamp": "t2", "env": "prod"})
    assert fp1 == fp2
```

- [ ] **Step 2: Run — verify fails**

```bash
pytest tests/unit/test_alert_fingerprint.py -v
# Expected: FAIL
```

- [ ] **Step 3: Create alert ingestion service**

```python
# vigil/api/src/services/alert_ingestion.py
import hashlib
import json
from redis.asyncio import Redis
from ..config.settings import settings

_VOLATILE_LABELS = {"timestamp", "value", "startsAt", "endsAt", "generatorURL"}


def compute_fingerprint(source: str, alert_name: str, service: str, labels: dict) -> str:
    """Deterministic SHA-256 fingerprint. Volatile labels excluded. Order-independent."""
    stable = {k: v for k, v in sorted(labels.items()) if k not in _VOLATILE_LABELS}
    raw = f"{source}:{alert_name}:{service}:{json.dumps(stable, sort_keys=True)}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def ingest_alert(redis: Redis, org_id: str, alert_data: dict) -> dict:
    """
    Publish alert to Redis Stream after dedup check.
    Returns {"deduplicated": bool, "fingerprint": str}.
    """
    fingerprint = compute_fingerprint(
        alert_data["source"],
        alert_data["alert_name"],
        alert_data["service"],
        alert_data.get("labels", {}),
    )
    dedup_key = f"vigil:alert:dedup:{org_id}:{fingerprint}"

    existing = await redis.get(dedup_key)
    if existing:
        await redis.expire(dedup_key, settings.alert_dedup_ttl)
        return {"deduplicated": True, "fingerprint": fingerprint}

    await redis.setex(dedup_key, settings.alert_dedup_ttl, "1")
    await redis.xadd(f"vigil:alerts:{org_id}", {
        "fingerprint": fingerprint,
        "org_id": org_id,
        "data": json.dumps(alert_data),
    })
    return {"deduplicated": False, "fingerprint": fingerprint}
```

- [ ] **Step 4: Run fingerprint tests — verify pass**

```bash
pytest tests/unit/test_alert_fingerprint.py -v
# Expected: all 4 PASS
```

- [ ] **Step 5: Create alert schemas**

```python
# vigil/api/src/schemas/alerts.py
import uuid
from datetime import UTC, datetime
from pydantic import BaseModel, Field


class AlertIngest(BaseModel):
    source: str
    alert_name: str
    service: str
    severity: str = "warning"
    labels: dict = {}
    metric_value: float | None = None
    threshold: float | None = None
    fired_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    message: str = ""


class AlertIngestResponse(BaseModel):
    alert_id: uuid.UUID | None
    fingerprint: str
    deduplicated: bool
    incident_id: uuid.UUID | None = None


class AlertGroupRead(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    fingerprint: str
    source: str
    alert_name: str
    service: str
    labels: dict
    first_fired_at: datetime
    last_fired_at: datetime
    alert_count: int
    status: str
    incident_id: uuid.UUID | None
    model_config = {"from_attributes": True}
```

- [ ] **Step 6: Create alerts controller**

```python
# vigil/api/src/controllers/alerts.py
import uuid
from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from redis.asyncio import Redis
from ..core.database import get_db
from ..core.redis import get_redis
from ..models.alert import AlertGroup
from ..schemas.alerts import AlertIngest, AlertIngestResponse, AlertGroupRead
from ..services.alert_ingestion import ingest_alert

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


def get_org_id(x_org_id: str = Header(...)) -> uuid.UUID:
    return uuid.UUID(x_org_id)


@router.post("/ingest", response_model=AlertIngestResponse, status_code=202)
async def ingest(body: AlertIngest,
                 org_id: uuid.UUID = Depends(get_org_id),
                 db: AsyncSession = Depends(get_db),
                 redis: Redis = Depends(get_redis)):
    result = await ingest_alert(redis, str(org_id), body.model_dump(mode="json"))

    if result["deduplicated"]:
        existing = await db.execute(
            select(AlertGroup).where(
                AlertGroup.org_id == org_id,
                AlertGroup.fingerprint == result["fingerprint"],
                AlertGroup.status == "firing",
            )
        )
        group = existing.scalar_one_or_none()
        return AlertIngestResponse(
            alert_id=group.id if group else None,
            fingerprint=result["fingerprint"],
            deduplicated=True,
            incident_id=group.incident_id if group else None,
        )

    group = AlertGroup(
        org_id=org_id,
        fingerprint=result["fingerprint"],
        source=body.source,
        alert_name=body.alert_name,
        service=body.service,
        labels=body.labels,
        first_fired_at=body.fired_at,
        last_fired_at=body.fired_at,
        status="firing",
    )
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return AlertIngestResponse(
        alert_id=group.id,
        fingerprint=result["fingerprint"],
        deduplicated=False,
    )


@router.get("", response_model=list[AlertGroupRead])
async def list_alert_groups(status: str | None = None,
                              org_id: uuid.UUID = Depends(get_org_id),
                              db: AsyncSession = Depends(get_db)):
    query = select(AlertGroup).where(AlertGroup.org_id == org_id)
    if status:
        query = query.where(AlertGroup.status == status)
    result = await db.execute(query.order_by(AlertGroup.first_fired_at.desc()).limit(200))
    return result.scalars().all()
```

- [ ] **Step 7: Register and run integration tests**

Add to `vigil/api/src/app.py`:
```python
from .controllers.alerts import router as alerts_router
app.include_router(alerts_router)
```

```python
# vigil/api/tests/integration/test_alert_ingestion_api.py
import pytest
from httpx import AsyncClient
from src.app import app

ORG = {"X-Org-ID": "00000000-0000-0000-0000-000000000001"}
ALERT = {"source": "datadog", "alert_name": "high_error_rate",
         "service": "payments-api", "labels": {"env": "prod"}}


@pytest.mark.asyncio
async def test_ingest_new_alert_returns_202():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post("/api/v1/alerts/ingest", json=ALERT, headers=ORG)
    assert resp.status_code == 202
    assert resp.json()["deduplicated"] is False
    assert "fingerprint" in resp.json()


@pytest.mark.asyncio
async def test_duplicate_alert_is_deduplicated():
    async with AsyncClient(app=app, base_url="http://test") as client:
        await client.post("/api/v1/alerts/ingest", json=ALERT, headers=ORG)
        resp = await client.post("/api/v1/alerts/ingest", json=ALERT, headers=ORG)
    assert resp.json()["deduplicated"] is True
```

```bash
pytest tests/integration/test_alert_ingestion_api.py -v
# Expected: PASS
```

- [ ] **Step 8: Commit**

```bash
git add vigil/api/src/services/alert_ingestion.py vigil/api/src/schemas/alerts.py \
        vigil/api/src/controllers/alerts.py vigil/api/src/app.py vigil/api/tests/
git commit -m "feat(vigil): add alert ingestion with Redis Stream and fingerprint dedup"
```

---

## Task 6: Alert Worker — Correlation

**Files:**
- Create: `vigil/api/src/services/alert_worker.py`
- Create: `vigil/api/tests/unit/test_alert_correlation.py`

- [ ] **Step 1: Write failing correlation tests**

```python
# vigil/api/tests/unit/test_alert_correlation.py
from datetime import UTC, datetime, timedelta
from src.services.alert_worker import alerts_are_correlated


def test_same_service_within_window_correlated():
    t = datetime.now(UTC)
    a1 = {"service": "payments-api", "last_fired_at": t.isoformat()}
    a2 = {"service": "payments-api",
          "last_fired_at": (t + timedelta(minutes=2)).isoformat()}
    assert alerts_are_correlated(a1, a2, window_minutes=5) is True


def test_same_service_outside_window_not_correlated():
    t = datetime.now(UTC)
    a1 = {"service": "payments-api", "last_fired_at": t.isoformat()}
    a2 = {"service": "payments-api",
          "last_fired_at": (t + timedelta(minutes=10)).isoformat()}
    assert alerts_are_correlated(a1, a2, window_minutes=5) is False


def test_different_service_not_correlated():
    t = datetime.now(UTC)
    a1 = {"service": "payments-api", "last_fired_at": t.isoformat()}
    a2 = {"service": "checkout-api", "last_fired_at": t.isoformat()}
    assert alerts_are_correlated(a1, a2, window_minutes=5) is False
```

- [ ] **Step 2: Run — verify fails**

```bash
pytest tests/unit/test_alert_correlation.py -v
# Expected: FAIL
```

- [ ] **Step 3: Create alert worker**

```python
# vigil/api/src/services/alert_worker.py
import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from redis.asyncio import Redis
from sqlalchemy import select
from ..core.database import AsyncSessionLocal
from ..core.redis import get_redis
from ..config.settings import settings
from ..models.alert import AlertGroup

logger = logging.getLogger(__name__)


def alerts_are_correlated(a1: dict, a2: dict, window_minutes: int = 5) -> bool:
    """Two alerts are correlated if same service and fired within window_minutes."""
    if a1["service"] != a2["service"]:
        return False
    t1 = datetime.fromisoformat(a1["last_fired_at"])
    t2 = datetime.fromisoformat(a2["last_fired_at"])
    return abs((t1 - t2).total_seconds()) <= window_minutes * 60


async def process_stream_entry(fields: dict) -> None:
    org_id = fields["org_id"]
    fingerprint = fields["fingerprint"]

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AlertGroup).where(
                AlertGroup.org_id == org_id,
                AlertGroup.fingerprint == fingerprint,
                AlertGroup.status == "firing",
            )
        )
        group = result.scalar_one_or_none()
        if not group:
            return

        window_start = datetime.now(UTC) - timedelta(
            minutes=settings.alert_correlation_window
        )
        correlated = await db.execute(
            select(AlertGroup).where(
                AlertGroup.org_id == org_id,
                AlertGroup.service == group.service,
                AlertGroup.status == "firing",
                AlertGroup.last_fired_at >= window_start,
                AlertGroup.id != group.id,
            )
        )
        correlated_groups = correlated.scalars().all()
        if correlated_groups:
            logger.info("Alert %s correlated with %d group(s)", fingerprint,
                        len(correlated_groups))
        await db.commit()


async def run_worker(org_id: str) -> None:
    redis: Redis = await get_redis()
    stream_key = f"vigil:alerts:{org_id}"
    group_name = "vigil-alert-workers"
    consumer_name = f"worker-{org_id[:8]}"

    try:
        await redis.xgroup_create(stream_key, group_name, id="0", mkstream=True)
    except Exception:
        pass

    while True:
        try:
            messages = await redis.xreadgroup(
                group_name, consumer_name,
                {stream_key: ">"},
                count=10, block=5000,
            )
            if not messages:
                continue
            for _stream, entries in messages:
                for entry_id, raw_fields in entries:
                    await process_stream_entry(dict(raw_fields))
                    await redis.xack(stream_key, group_name, entry_id)
        except Exception as exc:
            logger.exception("Worker error: %s", exc)
            await asyncio.sleep(1)
```

- [ ] **Step 4: Run correlation tests — verify pass**

```bash
pytest tests/unit/test_alert_correlation.py -v
# Expected: all 3 PASS
```

- [ ] **Step 5: Commit**

```bash
git add vigil/api/src/services/alert_worker.py vigil/api/tests/unit/test_alert_correlation.py
git commit -m "feat(vigil): add alert worker with correlation logic"
```

---

## Task 7: Incident Controller + On-Call Paging

**Files:**
- Create: `vigil/api/src/schemas/incidents.py`
- Create: `vigil/api/src/controllers/incidents.py`
- Create: `vigil/api/src/services/notification_service.py`
- Create: `vigil/api/tests/integration/test_incidents_api.py`

- [ ] **Step 1: Write failing integration tests**

```python
# vigil/api/tests/integration/test_incidents_api.py
import pytest
from httpx import AsyncClient
from src.app import app

ORG = {"X-Org-ID": "00000000-0000-0000-0000-000000000002"}
INC = {"title": "payments-api error spike", "severity": "P1",
       "affected_services": ["payments-api"]}


@pytest.mark.asyncio
async def test_create_incident():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post("/api/v1/incidents", json=INC, headers=ORG)
    assert resp.status_code == 201
    data = resp.json()
    assert data["severity"] == "P1"
    assert data["status"] == "DETECTED"
    assert data["inc_number"].startswith("INC-")


@pytest.mark.asyncio
async def test_list_incidents():
    async with AsyncClient(app=app, base_url="http://test") as client:
        await client.post("/api/v1/incidents", json=INC, headers=ORG)
        resp = await client.get("/api/v1/incidents", headers=ORG)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_append_timeline_event():
    async with AsyncClient(app=app, base_url="http://test") as client:
        create = await client.post("/api/v1/incidents", json=INC, headers=ORG)
        inc_id = create.json()["id"]
        resp = await client.post(f"/api/v1/incidents/{inc_id}/timeline", json={
            "title": "Root cause found",
            "body": "PR #2847 reduced pool size",
            "source": "metrics_agent",
            "event_type": "finding",
            "author": "metrics-agent",
        }, headers=ORG)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_resolve_sets_mttr():
    async with AsyncClient(app=app, base_url="http://test") as client:
        create = await client.post("/api/v1/incidents", json=INC, headers=ORG)
        inc_id = create.json()["id"]
        resp = await client.post(f"/api/v1/incidents/{inc_id}/resolve",
                                  json={"root_cause": "pool misconfiguration"},
                                  headers=ORG)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "RESOLVED"
    assert data["mttr_seconds"] is not None
```

- [ ] **Step 2: Run — verify fails**

```bash
pytest tests/integration/test_incidents_api.py -v
# Expected: FAIL
```

- [ ] **Step 3: Create incident schemas**

```python
# vigil/api/src/schemas/incidents.py
import uuid
from datetime import UTC, datetime
from pydantic import BaseModel, Field


class TimelineEventCreate(BaseModel):
    title: str
    body: str = ""
    source: str
    event_type: str
    author: str
    event_metadata: dict = {}
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TimelineEventRead(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    occurred_at: datetime
    source: str
    event_type: str
    title: str
    body: str
    author: str
    event_metadata: dict
    model_config = {"from_attributes": True}


class IncidentCreate(BaseModel):
    title: str
    severity: str
    affected_services: list[str] = []
    alert_group_id: uuid.UUID | None = None


class IncidentResolve(BaseModel):
    root_cause: str = ""


class IncidentRead(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    inc_number: str
    title: str
    severity: str
    status: str
    started_at: datetime
    detected_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    mttr_seconds: int | None
    affected_services: list[str]
    root_cause: str | None
    timeline_events: list[TimelineEventRead] = []
    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Create incidents controller**

```python
# vigil/api/src/controllers/incidents.py
import asyncio
import uuid
from datetime import UTC, datetime
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..core.database import get_db
from ..models.incident import Incident, TimelineEvent
from ..schemas.incidents import (IncidentCreate, IncidentRead, IncidentResolve,
                                   TimelineEventCreate, TimelineEventRead)
from ..services.incident_service import can_transition, get_next_inc_number, resolve_incident

router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])


def get_org_id(x_org_id: str = Header(...)) -> uuid.UUID:
    return uuid.UUID(x_org_id)


@router.get("", response_model=list[IncidentRead])
async def list_incidents(status: str | None = None, severity: str | None = None,
                          org_id: uuid.UUID = Depends(get_org_id),
                          db: AsyncSession = Depends(get_db)):
    query = select(Incident).where(Incident.org_id == org_id)
    if status:
        query = query.where(Incident.status == status)
    if severity:
        query = query.where(Incident.severity == severity)
    result = await db.execute(query.order_by(Incident.started_at.desc()).limit(100))
    return result.scalars().all()


@router.post("", response_model=IncidentRead, status_code=201)
async def create_incident(body: IncidentCreate,
                           org_id: uuid.UUID = Depends(get_org_id),
                           db: AsyncSession = Depends(get_db)):
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
    return incident


@router.get("/{incident_id}", response_model=IncidentRead)
async def get_incident(incident_id: uuid.UUID,
                        org_id: uuid.UUID = Depends(get_org_id),
                        db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Incident).where(Incident.id == incident_id, Incident.org_id == org_id)
    )
    inc = result.scalar_one_or_none()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    return inc


@router.post("/{incident_id}/timeline", response_model=TimelineEventRead, status_code=201)
async def append_timeline_event(incident_id: uuid.UUID, body: TimelineEventCreate,
                                  org_id: uuid.UUID = Depends(get_org_id),
                                  db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Incident).where(Incident.id == incident_id, Incident.org_id == org_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Incident not found")
    event = TimelineEvent(
        incident_id=incident_id,
        occurred_at=body.occurred_at,
        source=body.source,
        event_type=body.event_type,
        title=body.title,
        body=body.body,
        event_metadata=body.event_metadata,
        author=body.author,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


@router.post("/{incident_id}/resolve", response_model=IncidentRead)
async def resolve(incident_id: uuid.UUID, body: IncidentResolve,
                   org_id: uuid.UUID = Depends(get_org_id),
                   db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Incident).where(Incident.id == incident_id, Incident.org_id == org_id)
    )
    inc = result.scalar_one_or_none()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    if inc.status == "RESOLVED":
        raise HTTPException(status_code=400, detail="Already resolved")
    inc.root_cause = body.root_cause
    await resolve_incident(inc, db)
    return inc
```

- [ ] **Step 5: Create notification service**

```python
# vigil/api/src/services/notification_service.py
import logging
import httpx
from ..config.settings import settings

logger = logging.getLogger(__name__)

SEVERITY_EMOJI = {"P0": ":red_circle:", "P1": ":orange_circle:",
                  "P2": ":yellow_circle:", "P3": ":white_circle:"}


async def page_oncall(incident, oncall_user_id: str) -> bool:
    if not settings.slack_bot_token:
        logger.warning("SLACK_BOT_TOKEN not set")
        return False
    emoji = SEVERITY_EMOJI.get(incident.severity, ":white_circle:")
    msg = (f"{emoji} *{incident.severity} — {incident.inc_number}*\n"
           f"*{incident.title}*\n"
           f"Services: {', '.join(incident.affected_services or [])}")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {settings.slack_bot_token}"},
                json={"channel": oncall_user_id, "text": msg},
                timeout=10,
            )
            return resp.json().get("ok", False)
        except Exception as exc:
            logger.exception("Slack page error: %s", exc)
            return False
```

- [ ] **Step 6: Register router**

Add to `vigil/api/src/app.py`:
```python
from .controllers.incidents import router as incidents_router
app.include_router(incidents_router)
```

- [ ] **Step 7: Run tests — verify pass**

```bash
pytest tests/integration/test_incidents_api.py -v
# Expected: all 4 PASS
```

- [ ] **Step 8: Commit**

```bash
git add vigil/api/src/schemas/incidents.py vigil/api/src/controllers/incidents.py \
        vigil/api/src/services/notification_service.py vigil/api/src/app.py \
        vigil/api/tests/
git commit -m "feat(vigil): add incident controller with timeline, MTTR, and on-call paging"
```

---

## Task 8: Frontend — Wire Incidents Page to Vigil API

**Files:**
- Create: `vigil/web/lib/api/vigil-client.ts`
- Modify: `vigil/web/app/(dashboard)/incidents/page.tsx`
- Modify: `vigil/web/.env.local.example`

- [ ] **Step 1: Create Vigil API client**

```typescript
// vigil/web/lib/api/vigil-client.ts
const VIGIL_API_URL =
  process.env.NEXT_PUBLIC_VIGIL_API_URL || "http://localhost:5002";

function getHeaders(): Record<string, string> {
  const user =
    typeof window !== "undefined"
      ? JSON.parse(localStorage.getItem("vigil_user") || "{}")
      : {};
  const orgId = user?.tenant_id || "00000000-0000-0000-0000-000000000001";
  const token =
    typeof window !== "undefined"
      ? localStorage.getItem("vigil_token") || ""
      : "";
  return {
    "Content-Type": "application/json",
    "X-Org-ID": orgId,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function vigiRequest<T>(
  method: string,
  path: string,
  body?: unknown
): Promise<T> {
  const res = await fetch(`${VIGIL_API_URL}${path}`, {
    method,
    headers: getHeaders(),
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ message: res.statusText }));
    throw new Error(err?.message || "Vigil API request failed");
  }
  return res.json();
}

export interface VigilIncident {
  id: string;
  inc_number: string;
  title: string;
  severity: string;
  status: string;
  started_at: string;
  resolved_at: string | null;
  mttr_seconds: number | null;
  affected_services: string[];
  root_cause: string | null;
  timeline_events: VigilTimelineEvent[];
}

export interface VigilTimelineEvent {
  id: string;
  occurred_at: string;
  source: string;
  event_type: string;
  title: string;
  body: string;
  author: string;
}

export async function getIncidents(status?: string): Promise<VigilIncident[]> {
  const q = status ? `?status=${status}` : "";
  return vigiRequest("GET", `/api/v1/incidents${q}`);
}

export async function createIncident(data: {
  title: string;
  severity: string;
  affected_services?: string[];
}): Promise<VigilIncident> {
  return vigiRequest("POST", "/api/v1/incidents", data);
}

export async function resolveIncident(
  id: string,
  rootCause: string
): Promise<VigilIncident> {
  return vigiRequest("POST", `/api/v1/incidents/${id}/resolve`, {
    root_cause: rootCause,
  });
}

export function connectIncidentTimeline(
  incidentId: string,
  onEvent: (event: VigilTimelineEvent) => void
): () => void {
  const wsUrl = VIGIL_API_URL.replace("http://", "ws://").replace(
    "https://",
    "wss://"
  );
  const ws = new WebSocket(`${wsUrl}/ws/incidents/${incidentId}/timeline`);
  ws.onmessage = (msg) => {
    try {
      const data = JSON.parse(msg.data);
      if (data.type === "timeline_event") onEvent(data.event);
    } catch {}
  };
  const ping = setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) ws.send("ping");
  }, 30000);
  return () => {
    clearInterval(ping);
    ws.close();
  };
}
```

- [ ] **Step 2: Add env var to example file**

Append to `vigil/web/.env.local.example`:
```bash
NEXT_PUBLIC_VIGIL_API_URL=http://localhost:5002
```

- [ ] **Step 3: Add active incidents banner to incidents page**

In `vigil/web/app/(dashboard)/incidents/page.tsx`, add to imports:
```typescript
import { getIncidents, VigilIncident } from "@/lib/api/vigil-client";
```

Add state inside the component:
```typescript
const [activeIncidents, setActiveIncidents] = useState<VigilIncident[]>([]);

useEffect(() => {
  getIncidents("INVESTIGATING")
    .then(setActiveIncidents)
    .catch(() => {});
}, []);
```

Add banner in the `view === "agents"` block, between the header `div` and the search bar `div`:
```tsx
{activeIncidents.length > 0 && (
  <div style={{ marginBottom: 20 }}>
    <p style={{ fontSize: 11, fontWeight: 700, color: "#D94F3D",
                letterSpacing: "0.06em", textTransform: "uppercase",
                marginBottom: 8 }}>
      Active Incidents
    </p>
    {activeIncidents.map((inc) => (
      <div key={inc.id} style={{
        display: "flex", alignItems: "center", gap: 12,
        padding: "12px 16px", borderRadius: 10, marginBottom: 6,
        background: "rgba(217,79,61,0.06)",
        border: "1px solid rgba(217,79,61,0.12)",
      }}>
        <span style={{ fontSize: 11, fontWeight: 800, padding: "2px 8px",
                       borderRadius: 20, background: "rgba(217,79,61,0.12)",
                       color: "#D94F3D" }}>
          {inc.severity}
        </span>
        <span style={{ fontSize: 13, fontWeight: 600, color: "#1C1A16", flex: 1 }}>
          {inc.inc_number} — {inc.title}
        </span>
        <span style={{ fontSize: 11, fontWeight: 600, padding: "2px 8px",
                       borderRadius: 20, background: "rgba(200,125,47,0.1)",
                       color: "#C87D2F" }}>
          {inc.status}
        </span>
      </div>
    ))}
  </div>
)}
```

- [ ] **Step 4: Verify build**

```bash
cd vigil/web && pnpm build
# Expected: build completes, 0 errors
```

- [ ] **Step 5: Commit**

```bash
git add vigil/web/lib/api/vigil-client.ts \
        vigil/web/app/"(dashboard)"/incidents/page.tsx \
        vigil/web/.env.local.example
git commit -m "feat(vigil): wire incidents page to Vigil API with live incident banner"
```

---

## Task 9: Dockerfile + Final Verification

**Files:**
- Create: `vigil/api/Dockerfile`

- [ ] **Step 1: Create Dockerfile**

```dockerfile
# vigil/api/Dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml .
RUN uv sync --no-dev

COPY src/ ./src/
COPY migrations/ ./migrations/
COPY alembic.ini .

EXPOSE 5002

CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "5002"]
```

- [ ] **Step 2: Run full test suite**

```bash
cd vigil/api
pytest --tb=short -q
# Expected: all tests pass, 0 failures
```

Output should show tests from:
- `tests/unit/test_base_model.py` (2 tests)
- `tests/unit/test_alert_fingerprint.py` (4 tests)
- `tests/unit/test_alert_correlation.py` (3 tests)
- `tests/unit/test_incident_lifecycle.py` (3 tests)
- `tests/integration/test_services_api.py` (3 tests)
- `tests/integration/test_alert_ingestion_api.py` (2 tests)
- `tests/integration/test_incidents_api.py` (4 tests)

- [ ] **Step 3: Verify frontend builds clean**

```bash
cd vigil/web && pnpm build
# Expected: Build Output — 12 routes, 0 errors
```

- [ ] **Step 4: Final commit**

```bash
git add vigil/api/Dockerfile
git commit -m "feat(vigil): add Dockerfile — Phase 1 complete"
```

---

## Phase 1 Complete

At the end of this phase:

| Endpoint | What it does |
|---|---|
| `GET /health` | Vigil API live check |
| `POST /api/v1/alerts/ingest` | Accepts alerts, deduplicates, publishes to Redis Stream |
| `GET /api/v1/alerts` | List alert groups |
| `GET/POST /api/v1/services` | Service catalog CRUD |
| `GET /api/v1/services/{slug}/blast-radius` | Returns dependents |
| `GET/POST /api/v1/incidents` | Incident CRUD |
| `POST /api/v1/incidents/{id}/timeline` | Append timeline event |
| `POST /api/v1/incidents/{id}/resolve` | Resolve + compute MTTR |

Vigil frontend Incidents page shows a live banner of active incidents pulled from Vigil API.

Next: **Phase 2 — Intelligence** (multi-agent investigation, runbook engine, WebSocket timeline).
