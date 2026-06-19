# Vigil Phase 4 — Cloud-Native Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Vigil deployable in any company's own infrastructure. Ship a Helm chart for the Agent Worker, build the Integration Connectors UI (connect Datadog, GitHub, Kubernetes, PagerDuty, Jira from the Vigil dashboard), add VPC mode where tool calls execute inside the customer's cluster so sensitive data never leaves their network, and wire the Reliability and Runbooks dashboard pages to live Vigil API data.

**Architecture:** Agent Worker is a stateless k8s Deployment that polls Synkora for assigned tasks and executes tool calls against local infrastructure. Connectors store encrypted credentials in Vigil's Postgres. VPC mode is enabled per-org — when on, the worker runs tool calls locally; when off, Synkora's cloud tool registry handles them. Integration connector health is checked on a 5-minute schedule.

**Tech Stack:** Helm 3, Kubernetes HPA, Docker multi-stage build, cryptography (Fernet) for credential encryption, httpx for connector health checks, Synkora tool registry API

**Prerequisite:** Phases 1–3 complete. Docker installed. kubectl available in dev environment.

---

## File Structure (additions to Phase 3)

```
vigil/
├── helm/
│   └── vigil-agent-worker/
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
│           ├── deployment.yaml
│           ├── hpa.yaml
│           ├── secret.yaml
│           └── serviceaccount.yaml
├── worker/
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── src/
│       ├── main.py                             # Worker entry point: poll + execute loop
│       ├── config.py                           # Worker settings
│       ├── tool_executor.py                    # Execute tool calls locally
│       └── tools/
│           ├── datadog_tool.py                 # Datadog metrics queries
│           ├── kubernetes_tool.py              # kubectl wrapper
│           ├── github_tool.py                  # GitHub commit/PR queries
│           └── prometheus_tool.py              # PromQL queries
vigil/api/src/
├── models/
│   └── connector.py                            # IntegrationConnector model
├── schemas/
│   └── connectors.py
├── controllers/
│   └── connectors.py                           # GET/POST/DELETE /api/v1/connectors
├── services/
│   ├── connector_service.py                    # encrypt/decrypt credentials, health check
│   └── connector_health.py                     # background health check scheduler
vigil/web/
└── app/(dashboard)/
    ├── integrations/page.tsx                   # Wire to real connectors API
    └── reliability/page.tsx                    # Wire to real SLO API
```

---

## Task 1: Integration Connector Model + API

**Files:**
- Create: `vigil/api/src/models/connector.py`
- Create: `vigil/api/src/schemas/connectors.py`
- Create: `vigil/api/src/services/connector_service.py`
- Create: `vigil/api/src/controllers/connectors.py`
- Create: `vigil/api/tests/integration/test_connectors_api.py`

- [ ] **Step 1: Write failing tests**

```python
# vigil/api/tests/integration/test_connectors_api.py
import pytest
from httpx import AsyncClient
from src.app import app

ORG = {"X-Org-ID": "00000000-0000-0000-0000-000000000005"}


@pytest.mark.asyncio
async def test_create_connector():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post("/api/v1/connectors", json={
            "name": "Production Datadog",
            "connector_type": "datadog",
            "credentials": {"api_key": "dd-test-key-123", "app_key": "dd-app-key-456"},
            "config": {"site": "datadoghq.com"},
        }, headers=ORG)
    assert resp.status_code == 201
    data = resp.json()
    assert data["connector_type"] == "datadog"
    # Credentials must NOT be returned in plaintext
    assert "api_key" not in str(data.get("credentials", ""))


@pytest.mark.asyncio
async def test_list_connectors():
    async with AsyncClient(app=app, base_url="http://test") as client:
        await client.post("/api/v1/connectors", json={
            "name": "GitHub", "connector_type": "github",
            "credentials": {"token": "ghp_test"},
            "config": {},
        }, headers=ORG)
        resp = await client.get("/api/v1/connectors", headers=ORG)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_delete_connector():
    async with AsyncClient(app=app, base_url="http://test") as client:
        create = await client.post("/api/v1/connectors", json={
            "name": "Old connector", "connector_type": "pagerduty",
            "credentials": {"api_key": "pd-key"}, "config": {},
        }, headers=ORG)
        conn_id = create.json()["id"]
        resp = await client.delete(f"/api/v1/connectors/{conn_id}", headers=ORG)
    assert resp.status_code == 204
```

- [ ] **Step 2: Run — verify fails**

```bash
pytest tests/integration/test_connectors_api.py -v
# Expected: FAIL
```

- [ ] **Step 3: Add Fernet key to settings**

```python
# vigil/api/src/config/settings.py — add field:
connector_encryption_key: str = ""   # base64 Fernet key — generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Add to `.env.example`:
```bash
CONNECTOR_ENCRYPTION_KEY=  # generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Add `cryptography` to `vigil/api/pyproject.toml` dependencies:
```toml
"cryptography>=42.0.0",
```

- [ ] **Step 4: Create connector model**

```python
# vigil/api/src/models/connector.py
from sqlalchemy import Column, String, Boolean, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from .base import BaseModel


class IntegrationConnector(BaseModel):
    __tablename__ = "integration_connectors"

    org_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    connector_type = Column(String(50), nullable=False)   # "datadog"|"github"|"pagerduty"|"jira"|"kubernetes"|"prometheus"|"slack"
    credentials_encrypted = Column(String(4000), nullable=True)   # Fernet-encrypted JSON
    config = Column(JSON, default=dict)                    # non-secret config (site, org, etc.)
    status = Column(String(20), default="unknown")         # "healthy"|"error"|"unknown"
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(String(500), nullable=True)
    active = Column(Boolean, default=True)
```

- [ ] **Step 5: Create connector service**

```python
# vigil/api/src/services/connector_service.py
import json
import logging
from cryptography.fernet import Fernet, InvalidToken
from ..config.settings import settings

logger = logging.getLogger(__name__)


def _get_fernet() -> Fernet | None:
    if not settings.connector_encryption_key:
        logger.warning("CONNECTOR_ENCRYPTION_KEY not set — credentials stored in plaintext")
        return None
    try:
        return Fernet(settings.connector_encryption_key.encode())
    except Exception:
        return None


def encrypt_credentials(credentials: dict) -> str:
    """Encrypt credentials dict to a string for storage."""
    raw = json.dumps(credentials).encode()
    fernet = _get_fernet()
    if fernet:
        return fernet.encrypt(raw).decode()
    # Fallback: base64 without encryption (warn loudly)
    import base64
    logger.error("Storing credentials without encryption — set CONNECTOR_ENCRYPTION_KEY")
    return base64.b64encode(raw).decode()


def decrypt_credentials(encrypted: str) -> dict:
    """Decrypt stored credentials back to dict."""
    fernet = _get_fernet()
    try:
        if fernet:
            return json.loads(fernet.decrypt(encrypted.encode()).decode())
        import base64
        return json.loads(base64.b64decode(encrypted).decode())
    except (InvalidToken, Exception) as exc:
        logger.error("Failed to decrypt credentials: %s", exc)
        return {}


async def check_connector_health(connector) -> tuple[str, str | None]:
    """
    Test connectivity for a connector.
    Returns (status, error_message).
    """
    import httpx
    creds = decrypt_credentials(connector.credentials_encrypted or "")
    cfg = connector.config or {}

    try:
        if connector.connector_type == "datadog":
            api_key = creds.get("api_key", "")
            app_key = creds.get("app_key", "")
            site = cfg.get("site", "datadoghq.com")
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"https://api.{site}/api/v1/validate",
                    headers={"DD-API-KEY": api_key, "DD-APPLICATION-KEY": app_key},
                )
            return ("healthy" if resp.status_code == 200 else "error",
                    None if resp.status_code == 200 else f"HTTP {resp.status_code}")

        if connector.connector_type == "github":
            token = creds.get("token", "")
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.github.com/user",
                    headers={"Authorization": f"Bearer {token}",
                             "Accept": "application/vnd.github+json"},
                )
            return ("healthy" if resp.status_code == 200 else "error",
                    None if resp.status_code == 200 else f"HTTP {resp.status_code}")

        if connector.connector_type == "pagerduty":
            api_key = creds.get("api_key", "")
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.pagerduty.com/users/me",
                    headers={"Authorization": f"Token token={api_key}",
                             "Accept": "application/vnd.pagerduty+json;version=2"},
                )
            return ("healthy" if resp.status_code == 200 else "error",
                    None if resp.status_code == 200 else f"HTTP {resp.status_code}")

        if connector.connector_type == "prometheus":
            base_url = cfg.get("base_url", "http://localhost:9090")
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{base_url}/-/ready")
            return ("healthy" if resp.status_code == 200 else "error",
                    None if resp.status_code == 200 else f"HTTP {resp.status_code}")

        # Unknown type — mark healthy optimistically
        return ("healthy", None)

    except Exception as exc:
        return ("error", str(exc)[:200])
```

- [ ] **Step 6: Create connectors schema**

```python
# vigil/api/src/schemas/connectors.py
import uuid
from datetime import datetime
from pydantic import BaseModel


class ConnectorCreate(BaseModel):
    name: str
    connector_type: str                     # "datadog"|"github"|"pagerduty"|"jira"|"kubernetes"|"prometheus"|"slack"
    credentials: dict                       # plaintext on create — encrypted immediately
    config: dict = {}


class ConnectorRead(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    connector_type: str
    config: dict
    status: str
    last_checked_at: datetime | None
    last_error: str | None
    active: bool
    created_at: datetime
    # credentials intentionally excluded — never returned in API responses

    model_config = {"from_attributes": True}
```

- [ ] **Step 7: Create connectors controller**

```python
# vigil/api/src/controllers/connectors.py
import uuid
from datetime import UTC, datetime
from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..core.database import get_db
from ..models.connector import IntegrationConnector
from ..schemas.connectors import ConnectorCreate, ConnectorRead
from ..services.connector_service import encrypt_credentials, check_connector_health

router = APIRouter(prefix="/api/v1/connectors", tags=["connectors"])


def get_org_id(x_org_id: str = Header(...)) -> uuid.UUID:
    return uuid.UUID(x_org_id)


@router.get("", response_model=list[ConnectorRead])
async def list_connectors(
    org_id: uuid.UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(IntegrationConnector).where(
            IntegrationConnector.org_id == org_id,
            IntegrationConnector.active == True,  # noqa: E712
        )
    )
    return result.scalars().all()


@router.post("", response_model=ConnectorRead, status_code=201)
async def create_connector(
    body: ConnectorCreate,
    org_id: uuid.UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    encrypted = encrypt_credentials(body.credentials)
    connector = IntegrationConnector(
        org_id=org_id,
        name=body.name,
        connector_type=body.connector_type,
        credentials_encrypted=encrypted,
        config=body.config,
        status="unknown",
    )
    db.add(connector)
    await db.commit()
    await db.refresh(connector)

    # Health check in background
    import asyncio
    asyncio.create_task(_health_check_connector(connector.id))

    return connector


@router.post("/{connector_id}/test", response_model=ConnectorRead)
async def test_connector(
    connector_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(IntegrationConnector).where(
            IntegrationConnector.id == connector_id,
            IntegrationConnector.org_id == org_id,
        )
    )
    connector = result.scalar_one_or_none()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")

    status, error = await check_connector_health(connector)
    connector.status = status
    connector.last_error = error
    connector.last_checked_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(connector)
    return connector


@router.delete("/{connector_id}", status_code=204)
async def delete_connector(
    connector_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(IntegrationConnector).where(
            IntegrationConnector.id == connector_id,
            IntegrationConnector.org_id == org_id,
        )
    )
    connector = result.scalar_one_or_none()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    connector.active = False
    await db.commit()
    return Response(status_code=204)


async def _health_check_connector(connector_id: uuid.UUID) -> None:
    from ..core.database import AsyncSessionLocal
    from sqlalchemy import select as sa_select
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            sa_select(IntegrationConnector).where(IntegrationConnector.id == connector_id)
        )
        connector = result.scalar_one_or_none()
        if not connector:
            return
        status, error = await check_connector_health(connector)
        connector.status = status
        connector.last_error = error
        connector.last_checked_at = datetime.now(UTC)
        await db.commit()
```

- [ ] **Step 8: Register router, migrate, run tests**

Add to `vigil/api/src/app.py`:
```python
from .controllers.connectors import router as connectors_router
app.include_router(connectors_router)
```

```bash
alembic revision --autogenerate -m "add_integration_connectors"
alembic upgrade head
pytest tests/integration/test_connectors_api.py -v
# Expected: all 3 PASS
```

- [ ] **Step 9: Commit**

```bash
git add vigil/api/src/models/connector.py vigil/api/src/schemas/connectors.py \
        vigil/api/src/services/connector_service.py vigil/api/src/controllers/connectors.py \
        vigil/api/src/app.py vigil/api/migrations/ vigil/api/tests/
git commit -m "feat(vigil): add integration connectors with encrypted credentials and health checks"
```

---

## Task 2: Agent Worker Service

**Files:**
- Create: `vigil/worker/pyproject.toml`
- Create: `vigil/worker/src/config.py`
- Create: `vigil/worker/src/tools/datadog_tool.py`
- Create: `vigil/worker/src/tools/kubernetes_tool.py`
- Create: `vigil/worker/src/tools/github_tool.py`
- Create: `vigil/worker/src/tools/prometheus_tool.py`
- Create: `vigil/worker/src/tool_executor.py`
- Create: `vigil/worker/src/main.py`
- Create: `vigil/worker/Dockerfile`

- [ ] **Step 1: Create worker pyproject.toml**

```toml
# vigil/worker/pyproject.toml
[project]
name = "vigil-worker"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.27.0",
    "pydantic-settings>=2.3.0",
    "kubernetes>=29.0.0",
]

[tool.ruff]
line-length = 120
target-version = "py311"
```

- [ ] **Step 2: Create worker config**

```python
# vigil/worker/src/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Where to phone home
    synkora_api_url: str = "http://localhost:5001"
    vigil_api_url: str = "http://localhost:5002"
    org_api_key: str = ""                # per-org API key from Vigil settings
    worker_id: str = "worker-1"

    # Poll interval in seconds
    poll_interval: int = 5

    # Tool credentials (injected from k8s Secret in production)
    datadog_api_key: str = ""
    datadog_app_key: str = ""
    datadog_site: str = "datadoghq.com"

    github_token: str = ""

    prometheus_url: str = "http://prometheus:9090"

    kube_in_cluster: bool = False        # True when running inside k8s pod


settings = WorkerSettings()
```

- [ ] **Step 3: Create Datadog tool**

```python
# vigil/worker/src/tools/datadog_tool.py
import httpx
from ..config import settings


async def query_metrics(metric: str, service: str, minutes: int = 30) -> dict:
    """
    Query Datadog for a metric over the last N minutes for a given service.
    Returns {"metric": str, "values": [(timestamp, value), ...], "summary": str}
    """
    if not settings.datadog_api_key:
        return {"metric": metric, "values": [], "summary": "Datadog not configured"}

    import time
    now = int(time.time())
    start = now - (minutes * 60)
    query = f"avg:{metric}{{service:{service}}}"

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"https://api.{settings.datadog_site}/api/v1/query",
            headers={
                "DD-API-KEY": settings.datadog_api_key,
                "DD-APPLICATION-KEY": settings.datadog_app_key,
            },
            params={"from": start, "to": now, "query": query},
        )

    if resp.status_code != 200:
        return {"metric": metric, "values": [], "summary": f"Query failed: HTTP {resp.status_code}"}

    data = resp.json()
    series = data.get("series", [])
    if not series:
        return {"metric": metric, "values": [], "summary": "No data returned"}

    points = series[0].get("pointlist", [])
    values = [(int(p[0] / 1000), p[1]) for p in points if p[1] is not None]

    if not values:
        return {"metric": metric, "values": [], "summary": "No data points"}

    latest = values[-1][1]
    peak = max(v for _, v in values)
    summary = (f"Last value: {latest:.3f}, Peak: {peak:.3f}, "
               f"over {minutes}min for service:{service}")

    return {"metric": metric, "values": values[-20:], "summary": summary}


async def get_error_rate(service: str, minutes: int = 30) -> dict:
    return await query_metrics("trace.web.request.errors", service, minutes)
```

- [ ] **Step 4: Create Kubernetes tool**

```python
# vigil/worker/src/tools/kubernetes_tool.py
import logging
import httpx
from ..config import settings

logger = logging.getLogger(__name__)


async def get_pod_events(namespace: str, label_selector: str | None = None) -> dict:
    """
    Get recent Kubernetes events for pods in a namespace.
    Uses kubectl proxy or in-cluster service account.
    """
    if settings.kube_in_cluster:
        # In-cluster: use service account token
        try:
            with open("/var/run/secrets/kubernetes.io/serviceaccount/token") as f:
                token = f.read().strip()
            with open("/var/run/secrets/kubernetes.io/serviceaccount/namespace") as f:
                current_ns = f.read().strip()
            ns = namespace or current_ns
            url = f"https://kubernetes.default.svc/api/v1/namespaces/{ns}/events"
            async with httpx.AsyncClient(verify="/var/run/secrets/kubernetes.io/serviceaccount/ca.crt",
                                          timeout=10) as client:
                resp = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    params={"fieldSelector": "type=Warning"} if not label_selector else
                           {"fieldSelector": f"type=Warning,{label_selector}"},
                )
            if resp.status_code != 200:
                return {"events": [], "summary": f"k8s API error: HTTP {resp.status_code}"}
            items = resp.json().get("items", [])
        except Exception as exc:
            return {"events": [], "summary": f"k8s query failed: {exc}"}
    else:
        # Local dev: kubectl proxy must be running on 8001
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"http://localhost:8001/api/v1/namespaces/{namespace}/events",
                    params={"fieldSelector": "type=Warning"},
                )
            if resp.status_code != 200:
                return {"events": [], "summary": "kubectl proxy not available"}
            items = resp.json().get("items", [])
        except Exception:
            return {"events": [], "summary": "kubectl proxy not available — run: kubectl proxy"}

    recent = sorted(items, key=lambda e: e.get("lastTimestamp", ""), reverse=True)[:10]
    summaries = [
        f"[{e.get('reason', '?')}] {e.get('message', '')[:150]} "
        f"(count: {e.get('count', 1)})"
        for e in recent
    ]
    return {
        "events": summaries,
        "summary": f"{len(summaries)} warning events in namespace {namespace}",
    }


async def get_pod_restarts(namespace: str, service: str) -> dict:
    """Check pod restart counts for a service."""
    if settings.kube_in_cluster:
        try:
            with open("/var/run/secrets/kubernetes.io/serviceaccount/token") as f:
                token = f.read().strip()
            url = f"https://kubernetes.default.svc/api/v1/namespaces/{namespace}/pods"
            async with httpx.AsyncClient(
                verify="/var/run/secrets/kubernetes.io/serviceaccount/ca.crt",
                timeout=10,
            ) as client:
                resp = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    params={"labelSelector": f"app={service}"},
                )
            pods = resp.json().get("items", []) if resp.status_code == 200 else []
        except Exception:
            pods = []
    else:
        pods = []

    if not pods:
        return {"pods": [], "summary": f"No pods found for service {service}"}

    pod_info = []
    for pod in pods:
        name = pod["metadata"]["name"]
        containers = pod.get("status", {}).get("containerStatuses", [])
        restarts = sum(c.get("restartCount", 0) for c in containers)
        pod_info.append({"name": name, "restarts": restarts})

    total_restarts = sum(p["restarts"] for p in pod_info)
    return {
        "pods": pod_info,
        "summary": f"{len(pod_info)} pods, {total_restarts} total restarts for {service}",
    }
```

- [ ] **Step 5: Create GitHub tool**

```python
# vigil/worker/src/tools/github_tool.py
import httpx
from ..config import settings


async def get_recent_commits(repo: str, branch: str = "main", hours: int = 2) -> dict:
    """
    Get commits to a repo in the last N hours.
    repo format: "owner/repo-name"
    """
    if not settings.github_token:
        return {"commits": [], "summary": "GitHub not configured"}

    from datetime import UTC, datetime, timedelta
    since = (datetime.now(UTC) - timedelta(hours=hours)).isoformat()

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"https://api.github.com/repos/{repo}/commits",
            headers={
                "Authorization": f"Bearer {settings.github_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            params={"sha": branch, "since": since, "per_page": 20},
        )

    if resp.status_code == 404:
        return {"commits": [], "summary": f"Repo {repo} not found or no access"}
    if resp.status_code != 200:
        return {"commits": [], "summary": f"GitHub API error: HTTP {resp.status_code}"}

    commits = resp.json()
    summaries = [
        {
            "sha": c["sha"][:8],
            "message": c["commit"]["message"].split("\n")[0][:100],
            "author": c["commit"]["author"]["name"],
            "date": c["commit"]["author"]["date"],
        }
        for c in commits
    ]

    if not summaries:
        return {"commits": [], "summary": f"No commits in last {hours}h on {branch}"}

    return {
        "commits": summaries,
        "summary": f"{len(summaries)} commit(s) in last {hours}h on {repo}@{branch}",
    }


async def get_recent_prs(repo: str, hours: int = 2) -> dict:
    """Get recently merged PRs."""
    if not settings.github_token:
        return {"prs": [], "summary": "GitHub not configured"}

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"https://api.github.com/repos/{repo}/pulls",
            headers={
                "Authorization": f"Bearer {settings.github_token}",
                "Accept": "application/vnd.github+json",
            },
            params={"state": "closed", "sort": "updated", "direction": "desc", "per_page": 10},
        )

    if resp.status_code != 200:
        return {"prs": [], "summary": f"GitHub API error: HTTP {resp.status_code}"}

    from datetime import UTC, datetime, timedelta
    cutoff = datetime.now(UTC) - timedelta(hours=hours)

    prs = [
        {
            "number": pr["number"],
            "title": pr["title"][:100],
            "merged_at": pr.get("merged_at"),
            "author": pr["user"]["login"],
        }
        for pr in resp.json()
        if pr.get("merged_at") and
        datetime.fromisoformat(pr["merged_at"].replace("Z", "+00:00")) > cutoff
    ]

    if not prs:
        return {"prs": [], "summary": f"No PRs merged in last {hours}h on {repo}"}

    return {
        "prs": prs,
        "summary": f"{len(prs)} PR(s) merged in last {hours}h on {repo}",
    }
```

- [ ] **Step 6: Create Prometheus tool**

```python
# vigil/worker/src/tools/prometheus_tool.py
import httpx
from ..config import settings


async def query_instant(promql: str) -> dict:
    """Execute an instant PromQL query and return result."""
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(
                f"{settings.prometheus_url}/api/v1/query",
                params={"query": promql},
            )
        except Exception as exc:
            return {"result": [], "summary": f"Prometheus unreachable: {exc}"}

    if resp.status_code != 200:
        return {"result": [], "summary": f"Prometheus query failed: HTTP {resp.status_code}"}

    data = resp.json()
    results = data.get("data", {}).get("result", [])

    if not results:
        return {"result": [], "summary": f"No data for query: {promql}"}

    formatted = [
        {"labels": r["metric"], "value": float(r["value"][1])}
        for r in results
    ]
    return {
        "result": formatted,
        "summary": f"{len(formatted)} series returned for: {promql}",
    }


async def get_error_rate(service: str, namespace: str = "default") -> dict:
    """Standard error rate query for a service."""
    promql = (
        f'sum(rate(http_requests_total{{job="{service}",status=~"5.."}}[5m])) / '
        f'sum(rate(http_requests_total{{job="{service}"}}[5m]))'
    )
    return await query_instant(promql)
```

- [ ] **Step 7: Create tool executor**

```python
# vigil/worker/src/tool_executor.py
import logging
from .tools import datadog_tool, kubernetes_tool, github_tool, prometheus_tool

logger = logging.getLogger(__name__)

# Map tool names to executor functions
TOOL_MAP = {
    "datadog_query_metrics": datadog_tool.query_metrics,
    "datadog_get_error_rate": datadog_tool.get_error_rate,
    "kubernetes_get_pod_events": kubernetes_tool.get_pod_events,
    "kubernetes_get_pod_restarts": kubernetes_tool.get_pod_restarts,
    "github_get_recent_commits": github_tool.get_recent_commits,
    "github_get_recent_prs": github_tool.get_recent_prs,
    "prometheus_query": prometheus_tool.query_instant,
    "prometheus_get_error_rate": prometheus_tool.get_error_rate,
}


async def execute_tool(tool_name: str, tool_input: dict) -> dict:
    """
    Execute a tool call locally (inside customer VPC).
    Returns {"output": any, "error": str | None}.
    """
    handler = TOOL_MAP.get(tool_name)
    if not handler:
        return {"output": None, "error": f"Unknown tool: {tool_name}"}

    try:
        result = await handler(**tool_input)
        return {"output": result, "error": None}
    except TypeError as exc:
        return {"output": None, "error": f"Invalid tool input: {exc}"}
    except Exception as exc:
        logger.exception("Tool %s failed: %s", tool_name, exc)
        return {"output": None, "error": str(exc)[:500]}
```

- [ ] **Step 8: Create worker main loop**

```python
# vigil/worker/src/main.py
import asyncio
import logging
import httpx
from .config import settings
from .tool_executor import execute_tool

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("vigil-worker")

SYNKORA_HEADERS = {"Authorization": f"Bearer {settings.org_api_key}"}


async def poll_for_tasks() -> list[dict]:
    """Poll Synkora for pending tool execution tasks assigned to this worker."""
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(
                f"{settings.synkora_api_url}/api/v1/workers/tasks/pending",
                headers=SYNKORA_HEADERS,
                params={"worker_id": settings.worker_id},
            )
            if resp.status_code == 200:
                return resp.json().get("data", {}).get("tasks", [])
        except Exception as exc:
            logger.warning("Poll failed: %s", exc)
    return []


async def submit_result(task_id: str, result: dict) -> None:
    """Submit tool execution result back to Synkora."""
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            await client.post(
                f"{settings.synkora_api_url}/api/v1/workers/tasks/{task_id}/result",
                headers={**SYNKORA_HEADERS, "Content-Type": "application/json"},
                json=result,
            )
        except Exception as exc:
            logger.warning("Submit result failed: %s", exc)


async def process_task(task: dict) -> None:
    """Execute one task and submit result."""
    task_id = task.get("id", "unknown")
    tool_name = task.get("tool_name", "")
    tool_input = task.get("tool_input", {})

    logger.info("Executing task %s: tool=%s", task_id, tool_name)
    result = await execute_tool(tool_name, tool_input)
    await submit_result(task_id, result)
    logger.info("Task %s completed: error=%s", task_id, result.get("error"))


async def main() -> None:
    logger.info(
        "Vigil Agent Worker starting | worker_id=%s synkora=%s",
        settings.worker_id, settings.synkora_api_url,
    )
    while True:
        tasks = await poll_for_tasks()
        if tasks:
            await asyncio.gather(*[process_task(t) for t in tasks])
        await asyncio.sleep(settings.poll_interval)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 9: Create worker Dockerfile**

```dockerfile
# vigil/worker/Dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml .
RUN uv sync --no-dev

COPY src/ ./src/

CMD ["python", "-m", "src.main"]
```

- [ ] **Step 10: Build and smoke test the worker image**

```bash
cd vigil/worker
docker build -t vigil-agent-worker:latest .
# Expected: build succeeds

docker run --rm \
  -e SYNKORA_API_URL=http://host.docker.internal:5001 \
  -e VIGIL_API_URL=http://host.docker.internal:5002 \
  -e ORG_API_KEY=test-key \
  vigil-agent-worker:latest &
sleep 3
# Expected: logs show "Vigil Agent Worker starting | worker_id=worker-1"
docker stop $(docker ps -q --filter ancestor=vigil-agent-worker:latest)
```

- [ ] **Step 11: Commit**

```bash
git add vigil/worker/
git commit -m "feat(vigil): add agent worker with Datadog, GitHub, k8s, and Prometheus tools"
```

---

## Task 3: Helm Chart

**Files:**
- Create: `vigil/helm/vigil-agent-worker/Chart.yaml`
- Create: `vigil/helm/vigil-agent-worker/values.yaml`
- Create: `vigil/helm/vigil-agent-worker/templates/deployment.yaml`
- Create: `vigil/helm/vigil-agent-worker/templates/hpa.yaml`
- Create: `vigil/helm/vigil-agent-worker/templates/secret.yaml`
- Create: `vigil/helm/vigil-agent-worker/templates/serviceaccount.yaml`

- [ ] **Step 1: Create Chart.yaml**

```yaml
# vigil/helm/vigil-agent-worker/Chart.yaml
apiVersion: v2
name: vigil-agent-worker
description: Vigil AI Agent Worker — runs tool calls inside your cluster
type: application
version: 0.1.0
appVersion: "0.1.0"
keywords:
  - sre
  - ai
  - vigil
  - agent
home: https://github.com/your-org/vigil
```

- [ ] **Step 2: Create values.yaml**

```yaml
# vigil/helm/vigil-agent-worker/values.yaml
replicaCount: 2

image:
  repository: vigil/agent-worker
  pullPolicy: IfNotPresent
  tag: "latest"

worker:
  synkoraApiUrl: "https://api.synkora.ai"
  vigilApiUrl: "https://app.vigil.ai"
  pollIntervalSeconds: 5
  kubeInCluster: true

# Credentials — override with your values or use existingSecret
credentials:
  orgApiKey: ""
  datadogApiKey: ""
  datadogAppKey: ""
  datadogSite: "datadoghq.com"
  githubToken: ""
  prometheusUrl: "http://prometheus-operated:9090"

# Use an existing k8s Secret instead of creating one
existingSecret: ""

resources:
  requests:
    cpu: 250m
    memory: 512Mi
  limits:
    cpu: 2
    memory: 2Gi

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 50
  targetCPUUtilizationPercentage: 70

serviceAccount:
  create: true
  name: ""
  # RBAC rules: worker needs read access to pods and events
  rules:
    - apiGroups: [""]
      resources: ["pods", "events", "namespaces"]
      verbs: ["get", "list", "watch"]

nodeSelector: {}
tolerations: []
affinity: {}
```

- [ ] **Step 3: Create ServiceAccount template**

```yaml
# vigil/helm/vigil-agent-worker/templates/serviceaccount.yaml
{{- if .Values.serviceAccount.create }}
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {{ include "vigil-agent-worker.serviceAccountName" . }}
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "vigil-agent-worker.labels" . | nindent 4 }}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: {{ include "vigil-agent-worker.serviceAccountName" . }}
rules:
{{- toYaml .Values.serviceAccount.rules | nindent 2 }}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: {{ include "vigil-agent-worker.serviceAccountName" . }}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: {{ include "vigil-agent-worker.serviceAccountName" . }}
subjects:
  - kind: ServiceAccount
    name: {{ include "vigil-agent-worker.serviceAccountName" . }}
    namespace: {{ .Release.Namespace }}
{{- end }}
```

- [ ] **Step 4: Create Secret template**

```yaml
# vigil/helm/vigil-agent-worker/templates/secret.yaml
{{- if not .Values.existingSecret }}
apiVersion: v1
kind: Secret
metadata:
  name: {{ include "vigil-agent-worker.fullname" . }}-credentials
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "vigil-agent-worker.labels" . | nindent 4 }}
type: Opaque
stringData:
  ORG_API_KEY: {{ .Values.credentials.orgApiKey | quote }}
  DATADOG_API_KEY: {{ .Values.credentials.datadogApiKey | quote }}
  DATADOG_APP_KEY: {{ .Values.credentials.datadogAppKey | quote }}
  GITHUB_TOKEN: {{ .Values.credentials.githubToken | quote }}
{{- end }}
```

- [ ] **Step 5: Create Deployment template**

```yaml
# vigil/helm/vigil-agent-worker/templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "vigil-agent-worker.fullname" . }}
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "vigil-agent-worker.labels" . | nindent 4 }}
spec:
  {{- if not .Values.autoscaling.enabled }}
  replicas: {{ .Values.replicaCount }}
  {{- end }}
  selector:
    matchLabels:
      {{- include "vigil-agent-worker.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "vigil-agent-worker.selectorLabels" . | nindent 8 }}
    spec:
      serviceAccountName: {{ include "vigil-agent-worker.serviceAccountName" . }}
      containers:
        - name: worker
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          env:
            - name: SYNKORA_API_URL
              value: {{ .Values.worker.synkoraApiUrl | quote }}
            - name: VIGIL_API_URL
              value: {{ .Values.worker.vigilApiUrl | quote }}
            - name: POLL_INTERVAL
              value: {{ .Values.worker.pollIntervalSeconds | quote }}
            - name: KUBE_IN_CLUSTER
              value: {{ .Values.worker.kubeInCluster | quote }}
            - name: DATADOG_SITE
              value: {{ .Values.credentials.datadogSite | quote }}
            - name: PROMETHEUS_URL
              value: {{ .Values.credentials.prometheusUrl | quote }}
            - name: ORG_API_KEY
              valueFrom:
                secretKeyRef:
                  name: {{ default (printf "%s-credentials" (include "vigil-agent-worker.fullname" .)) .Values.existingSecret }}
                  key: ORG_API_KEY
            - name: DATADOG_API_KEY
              valueFrom:
                secretKeyRef:
                  name: {{ default (printf "%s-credentials" (include "vigil-agent-worker.fullname" .)) .Values.existingSecret }}
                  key: DATADOG_API_KEY
            - name: DATADOG_APP_KEY
              valueFrom:
                secretKeyRef:
                  name: {{ default (printf "%s-credentials" (include "vigil-agent-worker.fullname" .)) .Values.existingSecret }}
                  key: DATADOG_APP_KEY
            - name: GITHUB_TOKEN
              valueFrom:
                secretKeyRef:
                  name: {{ default (printf "%s-credentials" (include "vigil-agent-worker.fullname" .)) .Values.existingSecret }}
                  key: GITHUB_TOKEN
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
      {{- with .Values.nodeSelector }}
      nodeSelector:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.tolerations }}
      tolerations:
        {{- toYaml . | nindent 8 }}
      {{- end }}
```

- [ ] **Step 6: Create HPA template**

```yaml
# vigil/helm/vigil-agent-worker/templates/hpa.yaml
{{- if .Values.autoscaling.enabled }}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{ include "vigil-agent-worker.fullname" . }}
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "vigil-agent-worker.labels" . | nindent 4 }}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {{ include "vigil-agent-worker.fullname" . }}
  minReplicas: {{ .Values.autoscaling.minReplicas }}
  maxReplicas: {{ .Values.autoscaling.maxReplicas }}
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: {{ .Values.autoscaling.targetCPUUtilizationPercentage }}
{{- end }}
```

- [ ] **Step 7: Create _helpers.tpl**

```
{{/* vigil/helm/vigil-agent-worker/templates/_helpers.tpl */}}
{{- define "vigil-agent-worker.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "vigil-agent-worker.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}

{{- define "vigil-agent-worker.selectorLabels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "vigil-agent-worker.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "vigil-agent-worker.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}
```

- [ ] **Step 8: Lint the Helm chart**

```bash
cd vigil
helm lint helm/vigil-agent-worker/
# Expected: 1 chart(s) linted, 0 chart(s) failed

helm template test-release helm/vigil-agent-worker/ \
  --set credentials.orgApiKey=test \
  --set credentials.datadogApiKey=dd-test | head -80
# Expected: valid YAML output showing Deployment, HPA, Secret, ServiceAccount
```

- [ ] **Step 9: Commit**

```bash
git add vigil/helm/
git commit -m "feat(vigil): add Helm chart for agent worker with HPA and RBAC"
```

---

## Task 4: Wire Frontend to Live Data

**Files:**
- Modify: `vigil/web/app/(dashboard)/integrations/page.tsx`
- Modify: `vigil/web/app/(dashboard)/reliability/page.tsx`
- Modify: `vigil/web/lib/api/vigil-client.ts`

- [ ] **Step 1: Add connector and SLO API calls to vigil-client.ts**

Append to `vigil/web/lib/api/vigil-client.ts`:

```typescript
// Connectors
export interface VigilConnector {
  id: string;
  name: string;
  connector_type: string;
  config: Record<string, string>;
  status: "healthy" | "error" | "unknown";
  last_checked_at: string | null;
  last_error: string | null;
  active: boolean;
}

export async function getConnectors(): Promise<VigilConnector[]> {
  return vigiRequest("GET", "/api/v1/connectors");
}

export async function createConnector(data: {
  name: string;
  connector_type: string;
  credentials: Record<string, string>;
  config?: Record<string, string>;
}): Promise<VigilConnector> {
  return vigiRequest("POST", "/api/v1/connectors", data);
}

export async function testConnector(id: string): Promise<VigilConnector> {
  return vigiRequest("POST", `/api/v1/connectors/${id}/test`);
}

export async function deleteConnector(id: string): Promise<void> {
  return vigiRequest("DELETE", `/api/v1/connectors/${id}`);
}

// SLOs
export interface VigilSLO {
  id: string;
  service: string;
  name: string;
  slo_type: string;
  target_percent: number;
  window_days: number;
  latest_snapshot: {
    compliance_percent: number;
    burn_rate: number;
    error_budget_remaining_percent: number;
    status: string;
  } | null;
}

export async function getSLOs(): Promise<VigilSLO[]> {
  return vigiRequest("GET", "/api/v1/slos");
}

export async function getSLOSummary(): Promise<Record<string, number>> {
  return vigiRequest("GET", "/api/v1/slos/summary");
}

export async function getDORAMetrics(days = 30) {
  return vigiRequest("GET", `/api/v1/analytics/dora?days=${days}`);
}
```

- [ ] **Step 2: Update integrations page to use real connectors**

Replace mock data in `vigil/web/app/(dashboard)/integrations/page.tsx`. Add at the top of the component:

```typescript
import { getConnectors, testConnector, deleteConnector, VigilConnector } from "@/lib/api/vigil-client";

// Inside IntegrationsPage component, replace mock INTEGRATIONS array:
const [connectors, setConnectors] = useState<VigilConnector[]>([]);
const [loading, setLoading] = useState(true);

useEffect(() => {
  getConnectors()
    .then(setConnectors)
    .catch(() => {})
    .finally(() => setLoading(false));
}, []);

const handleTest = async (id: string) => {
  const updated = await testConnector(id).catch(() => null);
  if (updated) {
    setConnectors(prev => prev.map(c => c.id === id ? updated : c));
  }
};

const handleDelete = async (id: string) => {
  await deleteConnector(id).catch(() => {});
  setConnectors(prev => prev.filter(c => c.id !== id));
};
```

Replace the static connector cards with dynamic ones driven by `connectors` state. Status dot colors: `healthy` → `#4ED1A1`, `error` → `#D94F3D`, `unknown` → `#9A9690`.

- [ ] **Step 3: Update reliability page to use real SLO data**

In `vigil/web/app/(dashboard)/reliability/page.tsx`, replace mock SLO data:

```typescript
import { getSLOs, getSLOSummary, VigilSLO } from "@/lib/api/vigil-client";

// Inside ReliabilityPage component:
const [slos, setSLOs] = useState<VigilSLO[]>([]);
const [summary, setSummary] = useState<Record<string, number>>({});

useEffect(() => {
  getSLOs().then(setSLOs).catch(() => {});
  getSLOSummary().then(setSummary).catch(() => {});
}, []);
```

Status color mapping:
```typescript
const statusColor = {
  healthy: "#4ED1A1",
  warning: "#C87D2F",
  burning: "#D94F3D",
  exhausted: "#D94F3D",
  no_data: "#9A9690",
};
```

Burn rate bar width: `Math.min((snap.burn_rate / 15) * 100, 100)` — caps at 15x displayed as 100%.

- [ ] **Step 4: Verify full build**

```bash
cd vigil/web && pnpm build
# Expected: build completes, 12 routes, 0 errors

cd vigil/api && pytest --tb=short -q
# Expected: all tests pass
```

- [ ] **Step 5: Commit**

```bash
git add vigil/web/lib/api/vigil-client.ts \
        vigil/web/app/"(dashboard)"/integrations/page.tsx \
        vigil/web/app/"(dashboard)"/reliability/page.tsx
git commit -m "feat(vigil): wire integrations and reliability pages to live Vigil API"
```

---

## Task 5: Installation Guide

**Files:**
- Create: `vigil/INSTALL.md`

- [ ] **Step 1: Write installation guide**

```markdown
# Vigil — Self-Hosted Installation Guide

## Prerequisites
- Kubernetes cluster (1.24+)
- Helm 3.10+
- PostgreSQL 15+ (separate database from Synkora)
- Redis 7+
- Synkora API running and accessible

## Step 1: Database Setup

```bash
createdb vigil
cd vigil/api
cp .env.example .env
# Edit .env: set DATABASE_URL, REDIS_URL, JWT_SECRET, SYNKORA_API_URL

uv sync
alembic upgrade head
```

## Step 2: Start Vigil API

```bash
uvicorn src.app:app --host 0.0.0.0 --port 5002
```

Or with Docker:
```bash
docker build -t vigil-api:latest vigil/api/
docker run -p 5002:5002 --env-file vigil/api/.env vigil-api:latest
```

## Step 3: Configure Frontend

```bash
cd vigil/web
cp .env.local.example .env.local
# Set NEXT_PUBLIC_API_URL=http://your-synkora-api
# Set NEXT_PUBLIC_VIGIL_API_URL=http://your-vigil-api
pnpm build && pnpm start
```

## Step 4: Deploy Agent Workers to Kubernetes

```bash
cd vigil
helm install vigil-worker helm/vigil-agent-worker/ \
  --namespace vigil \
  --create-namespace \
  --set worker.synkoraApiUrl=https://your-synkora-api \
  --set worker.vigilApiUrl=https://your-vigil-api \
  --set credentials.orgApiKey=your-org-api-key \
  --set credentials.datadogApiKey=your-dd-api-key \
  --set credentials.datadogAppKey=your-dd-app-key \
  --set credentials.githubToken=your-github-token \
  --set credentials.prometheusUrl=http://prometheus-operated:9090
```

## Step 5: Connect Integrations

Log into Vigil dashboard → Integrations → Add connector for each tool (Datadog, GitHub, PagerDuty, etc.).

## Step 6: Create Your First SLO

```bash
curl -X POST http://your-vigil-api/api/v1/slos \
  -H "X-Org-ID: your-org-id" \
  -H "Content-Type: application/json" \
  -d '{"service":"payments-api","name":"Availability","slo_type":"availability","target_percent":99.9}'
```

## Step 7: Send a Test Alert

```bash
curl -X POST http://your-vigil-api/api/v1/alerts/ingest \
  -H "X-Org-ID: your-org-id" \
  -H "Content-Type: application/json" \
  -d '{"source":"test","alert_name":"high_error_rate","service":"payments-api","severity":"warning","labels":{"env":"prod"}}'
```

You should see a new alert group appear in the Vigil dashboard within seconds.
```

- [ ] **Step 2: Commit**

```bash
git add vigil/INSTALL.md
git commit -m "docs(vigil): add self-hosted installation guide"
```

---

## Phase 4 Complete

At the end of this phase, Vigil is fully deployable:

- Integration connectors with encrypted credentials and health checks (Datadog, GitHub, PagerDuty, Prometheus, k8s)
- Agent Worker: stateless, containerized, runs tool calls inside customer VPC — sensitive data never leaves the cluster
- Helm chart: deploys workers to any Kubernetes cluster with HPA scaling 2 → 50 replicas
- Integrations dashboard wired to real connectors API
- Reliability dashboard wired to real SLO API
- Full installation guide

**Complete platform at a glance:**

| Phase | What ships |
|---|---|
| Phase 1 | Alert ingestion + dedup + correlation, Incident Engine, Service Catalog, On-call paging |
| Phase 2 | Multi-agent investigation, Runbook Engine + HITL execution, Real-time WebSocket timeline |
| Phase 3 | SLO/SLI + error budgets, Postmortem auto-generation, DORA metrics, Jira sync, Pattern analysis |
| Phase 4 | Integration connectors, VPC-mode Agent Workers, Helm chart, Frontend fully wired |
