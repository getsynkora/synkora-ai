# Cloud Provider Integrations (AWS, GCP, Azure, DigitalOcean) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let agents pull logs, metrics, alerts, resource health, and security findings from AWS, GCP, Azure, and DigitalOcean for incident-response investigations.

**Architecture:** Credentials reuse the existing `OAuthApp` model (`auth_method='api_token'`, no new table). Each provider gets a thin `CloudProviderAdapter` subclass (in `services/cloud_providers/`) that does the actual REST/SDK calls, a set of `internal_*` tool functions (in `services/agents/internal_tools/`) that resolve credentials via a shared helper and call the adapter, and a `tool_registrations/*_tools_registry.py` file that registers the 5 tools per provider with the ADK tool registry (`tool_category="read"`, `requires_auth="aws"|"gcp"|"azure"|"digitalocean"`). `apps.py` gets a live-network validate-on-save hook per provider. The frontend gets 4 new `PROVIDERS` entries in `oauth-apps/create/page.tsx`.

**Tech Stack:** `boto3` (AWS, already a dependency), `httpx` + `pyjwt` (GCP service-account JWT auth), `httpx` (Azure OAuth2 client-credentials, DigitalOcean bearer PAT) — no new heavy SDKs. `moto` added as a new dev-dependency for AWS adapter tests.

Full design: `docs/superpowers/specs/2026-08-16-cloud-provider-integrations-design.md`

---

## Task 1: `CloudProviderAdapter` base class

**Files:**
- Create: `api/src/services/cloud_providers/__init__.py`
- Create: `api/src/services/cloud_providers/base_adapter.py`
- Test: `api/tests/unit/services/cloud_providers/test_base_adapter.py`
- Create: `api/tests/unit/services/cloud_providers/__init__.py`

- [ ] **Step 1: Write the failing test**

```python
# api/tests/unit/services/cloud_providers/test_base_adapter.py
import pytest

from src.services.cloud_providers.base_adapter import CloudProviderAdapter


class _FakeAdapter(CloudProviderAdapter):
    async def get_logs(self, log_source, start_time, end_time, filter_query="", limit=100):
        return self._ok(entries=["line1"])

    async def get_metrics(self, metric_name, start_time, end_time, resource_id="", period_seconds=300):
        return self._fail("not implemented in fake")

    async def list_alerts(self, active_only=True):
        return self._ok(alerts=[])

    async def get_resource_health(self, resource_id=""):
        return self._ok(status="healthy")

    async def list_security_findings(self, severity=""):
        return self._ok(findings=[])


@pytest.mark.unit
class TestCloudProviderAdapter:
    def test_cannot_instantiate_base_class_directly(self):
        with pytest.raises(TypeError):
            CloudProviderAdapter(credentials={})

    @pytest.mark.asyncio
    async def test_ok_helper_shape(self):
        adapter = _FakeAdapter(credentials={"api_token": "x"})
        result = await adapter.get_logs("app-logs", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z")
        assert result == {"success": True, "error": None, "entries": ["line1"]}

    @pytest.mark.asyncio
    async def test_fail_helper_shape(self):
        adapter = _FakeAdapter(credentials={"api_token": "x"})
        result = await adapter.get_metrics("cpu", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z")
        assert result == {"success": False, "error": "not implemented in fake"}

    def test_stores_credentials(self):
        adapter = _FakeAdapter(credentials={"api_token": "secret"})
        assert adapter.credentials == {"api_token": "secret"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/unit/services/cloud_providers/test_base_adapter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.cloud_providers'`

- [ ] **Step 3: Write minimal implementation**

```python
# api/src/services/cloud_providers/__init__.py
```

(empty file)

```python
# api/src/services/cloud_providers/base_adapter.py
"""
CloudProviderAdapter — abstract base class for cloud infrastructure adapters.

Each concrete adapter (AWS/GCP/Azure/DigitalOcean) wraps that provider's
read-only operational APIs (logs, metrics, alerts, resource health, security
findings) behind a single common interface so the `internal_*` tool layer
never needs to know which provider it's talking to.

All methods return a dict shaped `{"success": bool, "error": str | None, ...}`
so tool functions can pass the result straight back to the LLM without
re-shaping it. Providers that don't support a capability (e.g. DigitalOcean
has no log-query API) still implement the method — they just return
`_fail("Not supported by <provider>")` instead of raising or being omitted,
so the LLM gets an explicit answer instead of guessing.
"""

from abc import ABC, abstractmethod
from typing import Any


class CloudProviderAdapter(ABC):
    """Common interface for read-only cloud provider operational APIs."""

    def __init__(self, credentials: dict[str, Any]):
        """
        Args:
            credentials: Resolved credential dict from `cloud_shared.get_cloud_provider_config()`
                (contains decrypted secrets — never log this dict).
        """
        self.credentials = credentials

    @staticmethod
    def _ok(**data: Any) -> dict[str, Any]:
        return {"success": True, "error": None, **data}

    @staticmethod
    def _fail(error: str) -> dict[str, Any]:
        return {"success": False, "error": error}

    @abstractmethod
    async def get_logs(
        self,
        log_source: str,
        start_time: str,
        end_time: str,
        filter_query: str = "",
        limit: int = 100,
    ) -> dict[str, Any]:
        """Fetch log entries from `log_source` between `start_time`/`end_time` (ISO 8601)."""
        ...

    @abstractmethod
    async def get_metrics(
        self,
        metric_name: str,
        start_time: str,
        end_time: str,
        resource_id: str = "",
        period_seconds: int = 300,
    ) -> dict[str, Any]:
        """Fetch a time series for `metric_name`, optionally scoped to `resource_id`."""
        ...

    @abstractmethod
    async def list_alerts(self, active_only: bool = True) -> dict[str, Any]:
        """List alerts/alarms, optionally filtered to only currently-active ones."""
        ...

    @abstractmethod
    async def get_resource_health(self, resource_id: str = "") -> dict[str, Any]:
        """Get health/status for a specific resource, or all resources if `resource_id` is empty."""
        ...

    @abstractmethod
    async def list_security_findings(self, severity: str = "") -> dict[str, Any]:
        """List security findings, optionally filtered by `severity` (e.g. 'HIGH', 'CRITICAL')."""
        ...
```

```python
# api/tests/unit/services/cloud_providers/__init__.py
```

(empty file)

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/unit/services/cloud_providers/test_base_adapter.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add api/src/services/cloud_providers/__init__.py api/src/services/cloud_providers/base_adapter.py api/tests/unit/services/cloud_providers/__init__.py api/tests/unit/services/cloud_providers/test_base_adapter.py
git commit -m "feat: add CloudProviderAdapter base class for cloud infra integrations"
```

## Task 2: Shared credential-resolution helper (`cloud_shared.py`)

**Files:**
- Create: `api/src/services/agents/internal_tools/cloud_shared.py`
- Test: `api/tests/unit/services/agents/internal_tools/test_cloud_shared.py`

- [ ] **Step 1: Write the failing test**

```python
# api/tests/unit/services/agents/internal_tools/test_cloud_shared.py
"""Tests for the shared cloud-provider credential-resolution helper."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.agents.internal_tools.cloud_shared import get_cloud_provider_config


def _mock_db_returning(agent_tool, oauth_app):
    """Build a mock async session whose execute() returns agent_tool then oauth_app in order."""
    agent_tool_result = MagicMock()
    agent_tool_result.scalar_one_or_none.return_value = agent_tool
    oauth_app_result = MagicMock()
    oauth_app_result.scalar_one_or_none.return_value = oauth_app

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[agent_tool_result, oauth_app_result])
    db.__aenter__ = AsyncMock(return_value=db)
    db.__aexit__ = AsyncMock(return_value=False)
    return db


@pytest.mark.unit
class TestGetCloudProviderConfig:
    @pytest.mark.asyncio
    async def test_resolves_credentials_when_fully_configured(self):
        runtime_context = SimpleNamespace(agent_id="agent-1")
        agent_tool = SimpleNamespace(oauth_app_id=42)
        oauth_app = SimpleNamespace(
            id=42,
            client_id="AKIA_TEST",
            api_token="encrypted-blob",
            config={"region": "us-east-1"},
        )
        db = _mock_db_returning(agent_tool, oauth_app)

        with (
            patch(
                "src.services.agents.internal_tools.cloud_shared.get_async_session_factory",
                return_value=lambda: db,
            ),
            patch(
                "src.services.agents.internal_tools.cloud_shared.decrypt_value",
                return_value="decrypted-secret",
            ),
        ):
            result = await get_cloud_provider_config(runtime_context, "internal_aws_get_logs", "aws")

        assert result["client_id"] == "AKIA_TEST"
        assert result["api_token"] == "decrypted-secret"
        assert result["config"] == {"region": "us-east-1"}

    @pytest.mark.asyncio
    async def test_raises_when_no_agent_tool_configured(self):
        runtime_context = SimpleNamespace(agent_id="agent-1")
        db = _mock_db_returning(agent_tool=None, oauth_app=None)

        with patch(
            "src.services.agents.internal_tools.cloud_shared.get_async_session_factory",
            return_value=lambda: db,
        ):
            with pytest.raises(ValueError, match="No OAuth app configured"):
                await get_cloud_provider_config(runtime_context, "internal_aws_get_logs", "aws")

    @pytest.mark.asyncio
    async def test_raises_when_oauth_app_not_found(self):
        runtime_context = SimpleNamespace(agent_id="agent-1")
        agent_tool = SimpleNamespace(oauth_app_id=42)
        db = _mock_db_returning(agent_tool=agent_tool, oauth_app=None)

        with patch(
            "src.services.agents.internal_tools.cloud_shared.get_async_session_factory",
            return_value=lambda: db,
        ):
            with pytest.raises(ValueError, match="No active aws OAuth app found"):
                await get_cloud_provider_config(runtime_context, "internal_aws_get_logs", "aws")

    @pytest.mark.asyncio
    async def test_raises_when_api_token_missing(self):
        runtime_context = SimpleNamespace(agent_id="agent-1")
        agent_tool = SimpleNamespace(oauth_app_id=42)
        oauth_app = SimpleNamespace(id=42, client_id=None, api_token=None, config={})
        db = _mock_db_returning(agent_tool, oauth_app)

        with patch(
            "src.services.agents.internal_tools.cloud_shared.get_async_session_factory",
            return_value=lambda: db,
        ):
            with pytest.raises(ValueError, match="credential is missing"):
                await get_cloud_provider_config(runtime_context, "internal_aws_get_logs", "aws")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/unit/services/agents/internal_tools/test_cloud_shared.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.agents.internal_tools.cloud_shared'`

- [ ] **Step 3: Write minimal implementation**

```python
# api/src/services/agents/internal_tools/cloud_shared.py
"""
Shared credential-resolution helper for cloud provider tools (AWS/GCP/Azure/DigitalOcean).

Auth: credentials stored in OAuthApp (auth_method='api_token'), one row per
tenant per provider, linked to a specific agent via AgentTool.oauth_app_id —
identical pattern to openweather_tools.py's _get_openweather_config, generalized
across all 4 cloud providers via the `provider` parameter.
"""

from typing import Any

from sqlalchemy import select

from src.core.database import get_async_session_factory
from src.models.agent_tool import AgentTool
from src.models.oauth_app import OAuthApp
from src.services.agents.security import decrypt_value


async def get_cloud_provider_config(runtime_context: Any, tool_name: str, provider: str) -> dict[str, Any]:
    """
    Resolve cloud provider credentials from the linked OAuthApp.

    Args:
        runtime_context: Object with an `agent_id` attribute (injected by the tool wrapper).
        tool_name: The `internal_*` tool name, used to look up the AgentTool row.
        provider: OAuthApp.provider value to match — 'aws', 'gcp', 'azure', or 'digitalocean'.

    Returns:
        dict with `client_id` (plain, may be None), `api_token` (decrypted secret),
        and `config` (provider-specific JSON, e.g. {"region": ...} for AWS).

    Raises:
        ValueError: at each missing-link step (no OAuth app configured / no active
            app found / credential missing), mirroring _get_openweather_config.
    """
    async with get_async_session_factory()() as db:
        result = await db.execute(
            select(AgentTool).filter(
                AgentTool.agent_id == runtime_context.agent_id,
                AgentTool.tool_name == tool_name,
                AgentTool.enabled,
            )
        )
        agent_tool = result.scalar_one_or_none()
        if not agent_tool or not agent_tool.oauth_app_id:
            raise ValueError(
                f"No OAuth app configured for tool '{tool_name}'. "
                f"Please connect a {provider} OAuth app in Agent Tools settings."
            )

        result = await db.execute(
            select(OAuthApp).filter(
                OAuthApp.id == agent_tool.oauth_app_id,
                OAuthApp.provider.ilike(provider),
                OAuthApp.is_active,
            )
        )
        oauth_app = result.scalar_one_or_none()
        if not oauth_app:
            raise ValueError(f"No active {provider} OAuth app found. Check your integrations.")

        if not oauth_app.api_token:
            raise ValueError(f"{provider} credential is missing. Edit the OAuth app and add your credentials.")

        return {
            "client_id": oauth_app.client_id,
            "api_token": decrypt_value(oauth_app.api_token),
            "config": oauth_app.config or {},
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/unit/services/agents/internal_tools/test_cloud_shared.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add api/src/services/agents/internal_tools/cloud_shared.py api/tests/unit/services/agents/internal_tools/test_cloud_shared.py
git commit -m "feat: add shared cloud-provider credential resolution helper"
```

## Task 3: Add `moto` dev-dependency (needed for AWS adapter tests)

**Files:**
- Modify: `api/pyproject.toml:153-171` (`dev` optional-dependencies group)

- [ ] **Step 1: Add the dependency**

Edit `api/pyproject.toml`'s `dev` list (around line 158, after `pytest-mock`):

```toml
dev = [
    # Testing
    "pytest>=8.3.0,<9.0.0",
    "pytest-cov>=6.0.0,<7.0.0",
    "pytest-asyncio>=0.24.0,<1.0.0",
    "pytest-mock>=3.14.0,<4.0.0",
    "moto[cloudwatch,cloudwatchlogs,ec2,securityhub,sts]>=5.0.0,<6.0.0",
    "faker>=33.0.0,<34.0.0",
    "factory-boy>=3.3.0,<4.0.0",

    # Code Quality
    "ruff>=0.8.0,<1.0.0",
    "mypy>=1.14.0,<2.0.0",
    "types-redis>=4.6.0",
    "types-requests>=2.32.0",

    # Development Tools
    "ipython>=8.31.0,<9.0.0",
    "ipdb>=0.13.0,<1.0.0",
]
```

- [ ] **Step 2: Rebuild the api container so the new dependency installs**

Run: `docker compose build api && docker compose up -d api`
Expected: build succeeds, `moto` appears in the container's installed packages.

Run: `docker compose exec -T api python -c "import moto; print(moto.__version__)"`
Expected: prints a version string (e.g. `5.x.x`), no `ModuleNotFoundError`.

- [ ] **Step 3: Commit**

```bash
git add api/pyproject.toml
git commit -m "chore: add moto dev-dependency for AWS adapter unit tests"
```

## Task 4: AWS adapter (`boto3`, `run_in_executor`)

**Files:**
- Create: `api/src/services/cloud_providers/aws_adapter.py`
- Test: `api/tests/unit/services/cloud_providers/test_aws_adapter.py`

- [ ] **Step 1: Write the failing test**

```python
# api/tests/unit/services/cloud_providers/test_aws_adapter.py
"""Tests for AWSAdapter using moto to mock AWS APIs."""

import boto3
import pytest
from moto import mock_aws

from src.services.cloud_providers.aws_adapter import AWSAdapter


def _credentials(region="us-east-1"):
    return {
        "client_id": "testing",
        "api_token": "testing",
        "config": {"region": region},
    }


@pytest.mark.unit
class TestAWSAdapterInit:
    def test_builds_boto3_session_from_credentials(self):
        adapter = AWSAdapter(_credentials())
        creds = adapter.session.get_credentials()
        assert creds.access_key == "testing"
        assert creds.secret_key == "testing"
        assert adapter.session.region_name == "us-east-1"

    def test_defaults_region_when_missing(self):
        adapter = AWSAdapter({"client_id": "testing", "api_token": "testing", "config": {}})
        assert adapter.session.region_name == "us-east-1"


@pytest.mark.unit
class TestAWSAdapterListAlerts:
    @pytest.mark.asyncio
    @mock_aws
    async def test_list_alerts_returns_alarms(self):
        client = boto3.client("cloudwatch", region_name="us-east-1")
        client.put_metric_alarm(
            AlarmName="high-cpu",
            MetricName="CPUUtilization",
            Namespace="AWS/EC2",
            Statistic="Average",
            Period=300,
            EvaluationPeriods=1,
            Threshold=80.0,
            ComparisonOperator="GreaterThanThreshold",
        )

        adapter = AWSAdapter(_credentials())
        result = await adapter.list_alerts(active_only=False)

        assert result["success"] is True
        assert any(a["AlarmName"] == "high-cpu" for a in result["alerts"])

    @pytest.mark.asyncio
    @mock_aws
    async def test_list_alerts_wraps_client_error(self):
        adapter = AWSAdapter({"client_id": "testing", "api_token": "testing", "config": {"region": "not-a-region"}})
        result = await adapter.list_alerts()
        assert result["success"] is False
        assert "error" in result


@pytest.mark.unit
class TestAWSAdapterResourceHealth:
    @pytest.mark.asyncio
    @mock_aws
    async def test_get_resource_health_no_instances(self):
        adapter = AWSAdapter(_credentials())
        result = await adapter.get_resource_health()
        assert result["success"] is True
        assert result["instances"] == []


@pytest.mark.unit
class TestAWSAdapterSecurityFindings:
    @pytest.mark.asyncio
    @mock_aws
    async def test_list_security_findings_when_hub_not_enabled(self):
        adapter = AWSAdapter(_credentials())
        result = await adapter.list_security_findings()
        # Security Hub is not enabled by default in moto — must fail gracefully, not raise.
        assert isinstance(result, dict)
        assert "success" in result


@pytest.mark.unit
class TestAWSAdapterLogsAndMetrics:
    @pytest.mark.asyncio
    @mock_aws
    async def test_get_logs_missing_log_group_returns_user_actionable_error(self):
        adapter = AWSAdapter(_credentials())
        result = await adapter.get_logs(
            log_source="/aws/lambda/does-not-exist",
            start_time="2026-01-01T00:00:00Z",
            end_time="2026-01-02T00:00:00Z",
        )
        assert result["success"] is False
        assert "does-not-exist" in result["error"] or "not found" in result["error"].lower()

    @pytest.mark.asyncio
    @mock_aws
    async def test_get_metrics_returns_datapoints_shape(self):
        adapter = AWSAdapter(_credentials())
        result = await adapter.get_metrics(
            metric_name="CPUUtilization",
            start_time="2026-01-01T00:00:00Z",
            end_time="2026-01-02T00:00:00Z",
        )
        assert result["success"] is True
        assert "datapoints" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/unit/services/cloud_providers/test_aws_adapter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.cloud_providers.aws_adapter'`

- [ ] **Step 3: Write minimal implementation**

```python
# api/src/services/cloud_providers/aws_adapter.py
"""
AWS adapter — CloudWatch Logs/Metrics/Alarms, EC2 instance status, Security Hub findings.

Uses boto3 directly (already a project dependency, needed for SigV4 request
signing — there's no lightweight REST alternative for AWS's signing scheme).
Blocking boto3 calls are wrapped in `run_in_executor`, the same idiom used by
`s3_storage.py` elsewhere in this codebase.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from src.services.cloud_providers.base_adapter import CloudProviderAdapter

logger = logging.getLogger(__name__)


def _friendly_error(e: Exception) -> str:
    if isinstance(e, NoCredentialsError):
        return "AWS credentials are invalid or expired — please reconnect in Integrations."
    if isinstance(e, ClientError):
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("UnrecognizedClientException", "InvalidClientTokenId", "AccessDenied", "AccessDeniedException"):
            return "AWS credentials are invalid or expired — please reconnect in Integrations."
        return f"AWS error ({code}): {e.response.get('Error', {}).get('Message', str(e))}"
    return f"AWS error: {e}"


class AWSAdapter(CloudProviderAdapter):
    def __init__(self, credentials: dict[str, Any]):
        super().__init__(credentials)
        config = credentials.get("config") or {}
        self.session = boto3.Session(
            aws_access_key_id=credentials.get("client_id"),
            aws_secret_access_key=credentials.get("api_token"),
            region_name=config.get("region", "us-east-1"),
        )

    async def _run(self, func, *args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    async def get_logs(
        self,
        log_source: str,
        start_time: str,
        end_time: str,
        filter_query: str = "",
        limit: int = 100,
    ) -> dict[str, Any]:
        try:
            client = self.session.client("logs")
            start_ms = int(datetime.fromisoformat(start_time.replace("Z", "+00:00")).timestamp() * 1000)
            end_ms = int(datetime.fromisoformat(end_time.replace("Z", "+00:00")).timestamp() * 1000)
            kwargs: dict[str, Any] = {
                "logGroupName": log_source,
                "startTime": start_ms,
                "endTime": end_ms,
                "limit": min(limit, 10000),
            }
            if filter_query:
                kwargs["filterPattern"] = filter_query
            resp = await self._run(client.filter_log_events, **kwargs)
            events = [
                {
                    "timestamp": e["timestamp"],
                    "message": e["message"],
                    "log_stream": e.get("logStreamName"),
                }
                for e in resp.get("events", [])
            ]
            return self._ok(entries=events)
        except (ClientError, BotoCoreError, NoCredentialsError) as e:
            return self._fail(_friendly_error(e))

    async def get_metrics(
        self,
        metric_name: str,
        start_time: str,
        end_time: str,
        resource_id: str = "",
        period_seconds: int = 300,
    ) -> dict[str, Any]:
        try:
            client = self.session.client("cloudwatch")
            namespace, _, name = metric_name.rpartition(":")
            namespace = namespace or "AWS/EC2"
            name = name or metric_name
            dimensions = [{"Name": "InstanceId", "Value": resource_id}] if resource_id else []
            resp = await self._run(
                client.get_metric_statistics,
                Namespace=namespace,
                MetricName=name,
                Dimensions=dimensions,
                StartTime=datetime.fromisoformat(start_time.replace("Z", "+00:00")),
                EndTime=datetime.fromisoformat(end_time.replace("Z", "+00:00")),
                Period=period_seconds,
                Statistics=["Average", "Maximum", "Minimum"],
            )
            datapoints = [
                {
                    "timestamp": dp["Timestamp"].isoformat(),
                    "average": dp.get("Average"),
                    "maximum": dp.get("Maximum"),
                    "minimum": dp.get("Minimum"),
                    "unit": dp.get("Unit"),
                }
                for dp in resp.get("Datapoints", [])
            ]
            return self._ok(datapoints=sorted(datapoints, key=lambda d: d["timestamp"]))
        except (ClientError, BotoCoreError, NoCredentialsError) as e:
            return self._fail(_friendly_error(e))

    async def list_alerts(self, active_only: bool = True) -> dict[str, Any]:
        try:
            client = self.session.client("cloudwatch")
            kwargs: dict[str, Any] = {}
            if active_only:
                kwargs["StateValue"] = "ALARM"
            resp = await self._run(client.describe_alarms, **kwargs)
            alarms = [
                {
                    "AlarmName": a["AlarmName"],
                    "StateValue": a["StateValue"],
                    "MetricName": a.get("MetricName"),
                    "Namespace": a.get("Namespace"),
                    "Threshold": a.get("Threshold"),
                }
                for a in resp.get("MetricAlarms", [])
            ]
            return self._ok(alerts=alarms)
        except (ClientError, BotoCoreError, NoCredentialsError) as e:
            return self._fail(_friendly_error(e))

    async def get_resource_health(self, resource_id: str = "") -> dict[str, Any]:
        try:
            client = self.session.client("ec2")
            kwargs: dict[str, Any] = {"IncludeAllInstances": True}
            if resource_id:
                kwargs["InstanceIds"] = [resource_id]
            resp = await self._run(client.describe_instance_status, **kwargs)
            instances = [
                {
                    "InstanceId": i["InstanceId"],
                    "InstanceState": i.get("InstanceState", {}).get("Name"),
                    "SystemStatus": i.get("SystemStatus", {}).get("Status"),
                    "InstanceStatus": i.get("InstanceStatus", {}).get("Status"),
                }
                for i in resp.get("InstanceStatuses", [])
            ]
            return self._ok(instances=instances)
        except (ClientError, BotoCoreError, NoCredentialsError) as e:
            return self._fail(_friendly_error(e))

    async def list_security_findings(self, severity: str = "") -> dict[str, Any]:
        try:
            client = self.session.client("securityhub")
            kwargs: dict[str, Any] = {"MaxResults": 100}
            if severity:
                kwargs["Filters"] = {"SeverityLabel": [{"Value": severity.upper(), "Comparison": "EQUALS"}]}
            resp = await self._run(client.get_findings, **kwargs)
            findings = [
                {
                    "Id": f.get("Id"),
                    "Title": f.get("Title"),
                    "Severity": f.get("Severity", {}).get("Label"),
                    "ResourceId": (f.get("Resources") or [{}])[0].get("Id"),
                    "Description": f.get("Description"),
                }
                for f in resp.get("Findings", [])
            ]
            return self._ok(findings=findings)
        except (ClientError, BotoCoreError, NoCredentialsError) as e:
            return self._fail(_friendly_error(e))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/unit/services/cloud_providers/test_aws_adapter.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add api/src/services/cloud_providers/aws_adapter.py api/tests/unit/services/cloud_providers/test_aws_adapter.py
git commit -m "feat: add AWS cloud provider adapter (CloudWatch Logs/Metrics/Alarms, EC2, Security Hub)"
```

## Task 5: AWS tool functions (`internal_tools/aws_tools.py`)

**Files:**
- Create: `api/src/services/agents/internal_tools/aws_tools.py`
- Test: `api/tests/unit/services/agents/internal_tools/test_aws_tools.py`

- [ ] **Step 1: Write the failing test**

```python
# api/tests/unit/services/agents/internal_tools/test_aws_tools.py
"""Tests for internal_aws_* tool functions."""

from unittest.mock import AsyncMock, patch

import pytest

from src.services.agents.internal_tools.aws_tools import (
    internal_aws_get_logs,
    internal_aws_get_metrics,
    internal_aws_get_resource_health,
    internal_aws_list_alerts,
    internal_aws_list_security_findings,
)

_CFG = {"client_id": "AKIA", "api_token": "secret", "config": {"region": "us-east-1"}}


@pytest.mark.unit
class TestAWSToolsNoRuntimeContext:
    @pytest.mark.asyncio
    async def test_get_logs_without_runtime_context(self):
        result = await internal_aws_get_logs(runtime_context=None, log_source="x", start_time="a", end_time="b")
        assert result == {"success": False, "error": "No runtime context available."}


@pytest.mark.unit
class TestAWSToolsHappyPath:
    @pytest.mark.asyncio
    async def test_get_logs_delegates_to_adapter(self):
        with (
            patch(
                "src.services.agents.internal_tools.aws_tools.get_cloud_provider_config",
                new=AsyncMock(return_value=_CFG),
            ),
            patch("src.services.agents.internal_tools.aws_tools.AWSAdapter") as MockAdapter,
        ):
            MockAdapter.return_value.get_logs = AsyncMock(return_value={"success": True, "error": None, "entries": []})
            result = await internal_aws_get_logs(
                runtime_context=object(), log_source="/aws/lambda/foo", start_time="a", end_time="b"
            )
            MockAdapter.assert_called_once_with(_CFG)
            MockAdapter.return_value.get_logs.assert_called_once_with(
                log_source="/aws/lambda/foo", start_time="a", end_time="b", filter_query="", limit=100
            )
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_get_metrics_delegates_to_adapter(self):
        with (
            patch(
                "src.services.agents.internal_tools.aws_tools.get_cloud_provider_config",
                new=AsyncMock(return_value=_CFG),
            ),
            patch("src.services.agents.internal_tools.aws_tools.AWSAdapter") as MockAdapter,
        ):
            MockAdapter.return_value.get_metrics = AsyncMock(
                return_value={"success": True, "error": None, "datapoints": []}
            )
            result = await internal_aws_get_metrics(
                runtime_context=object(), metric_name="CPUUtilization", start_time="a", end_time="b"
            )
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_list_alerts_delegates_to_adapter(self):
        with (
            patch(
                "src.services.agents.internal_tools.aws_tools.get_cloud_provider_config",
                new=AsyncMock(return_value=_CFG),
            ),
            patch("src.services.agents.internal_tools.aws_tools.AWSAdapter") as MockAdapter,
        ):
            MockAdapter.return_value.list_alerts = AsyncMock(
                return_value={"success": True, "error": None, "alerts": []}
            )
            result = await internal_aws_list_alerts(runtime_context=object())
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_get_resource_health_delegates_to_adapter(self):
        with (
            patch(
                "src.services.agents.internal_tools.aws_tools.get_cloud_provider_config",
                new=AsyncMock(return_value=_CFG),
            ),
            patch("src.services.agents.internal_tools.aws_tools.AWSAdapter") as MockAdapter,
        ):
            MockAdapter.return_value.get_resource_health = AsyncMock(
                return_value={"success": True, "error": None, "instances": []}
            )
            result = await internal_aws_get_resource_health(runtime_context=object())
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_list_security_findings_delegates_to_adapter(self):
        with (
            patch(
                "src.services.agents.internal_tools.aws_tools.get_cloud_provider_config",
                new=AsyncMock(return_value=_CFG),
            ),
            patch("src.services.agents.internal_tools.aws_tools.AWSAdapter") as MockAdapter,
        ):
            MockAdapter.return_value.list_security_findings = AsyncMock(
                return_value={"success": True, "error": None, "findings": []}
            )
            result = await internal_aws_list_security_findings(runtime_context=object())
            assert result["success"] is True


@pytest.mark.unit
class TestAWSToolsCredentialError:
    @pytest.mark.asyncio
    async def test_returns_error_dict_when_credential_resolution_fails(self):
        with patch(
            "src.services.agents.internal_tools.aws_tools.get_cloud_provider_config",
            new=AsyncMock(side_effect=ValueError("No OAuth app configured for tool 'x'.")),
        ):
            result = await internal_aws_list_alerts(runtime_context=object())
            assert result == {"success": False, "error": "No OAuth app configured for tool 'x'."}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/unit/services/agents/internal_tools/test_aws_tools.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.agents.internal_tools.aws_tools'`

- [ ] **Step 3: Write minimal implementation**

```python
# api/src/services/agents/internal_tools/aws_tools.py
"""
AWS Tools — CloudWatch Logs/Metrics/Alarms, EC2 instance status, Security Hub findings.

Auth: access_key_id/secret_access_key stored in OAuthApp (provider='aws',
auth_method='api_token'), region in OAuthApp.config.
"""

import logging
from typing import Any

from src.services.agents.internal_tools.cloud_shared import get_cloud_provider_config
from src.services.cloud_providers.aws_adapter import AWSAdapter

logger = logging.getLogger(__name__)


async def internal_aws_get_logs(
    runtime_context: Any | None = None,
    log_source: str = "",
    start_time: str = "",
    end_time: str = "",
    filter_query: str = "",
    limit: int = 100,
) -> dict[str, Any]:
    """
    Fetch CloudWatch Logs entries from a log group.

    Args:
        log_source: CloudWatch Logs log group name (e.g. '/aws/lambda/my-function')
        start_time: Start of the time range, ISO 8601 (e.g. '2026-01-01T00:00:00Z')
        end_time: End of the time range, ISO 8601
        filter_query: Optional CloudWatch Logs filter pattern
        limit: Max number of log entries to return (default 100)
    """
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        cfg = await get_cloud_provider_config(runtime_context, "internal_aws_get_logs", "aws")
        adapter = AWSAdapter(cfg)
        return await adapter.get_logs(
            log_source=log_source, start_time=start_time, end_time=end_time, filter_query=filter_query, limit=limit
        )
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"internal_aws_get_logs failed: {e}")
        return {"success": False, "error": str(e)}


async def internal_aws_get_metrics(
    runtime_context: Any | None = None,
    metric_name: str = "",
    start_time: str = "",
    end_time: str = "",
    resource_id: str = "",
    period_seconds: int = 300,
) -> dict[str, Any]:
    """
    Fetch a CloudWatch metric time series.

    Args:
        metric_name: Metric name, optionally prefixed with namespace (e.g. 'AWS/EC2:CPUUtilization').
            Defaults to the 'AWS/EC2' namespace if no prefix is given.
        start_time: Start of the time range, ISO 8601
        end_time: End of the time range, ISO 8601
        resource_id: Optional EC2 instance ID to scope the metric to
        period_seconds: Granularity of datapoints in seconds (default 300)
    """
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        cfg = await get_cloud_provider_config(runtime_context, "internal_aws_get_metrics", "aws")
        adapter = AWSAdapter(cfg)
        return await adapter.get_metrics(
            metric_name=metric_name,
            start_time=start_time,
            end_time=end_time,
            resource_id=resource_id,
            period_seconds=period_seconds,
        )
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"internal_aws_get_metrics failed: {e}")
        return {"success": False, "error": str(e)}


async def internal_aws_list_alerts(
    runtime_context: Any | None = None,
    active_only: bool = True,
) -> dict[str, Any]:
    """
    List CloudWatch Alarms.

    Args:
        active_only: If True (default), only return alarms currently in ALARM state.
    """
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        cfg = await get_cloud_provider_config(runtime_context, "internal_aws_list_alerts", "aws")
        adapter = AWSAdapter(cfg)
        return await adapter.list_alerts(active_only=active_only)
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"internal_aws_list_alerts failed: {e}")
        return {"success": False, "error": str(e)}


async def internal_aws_get_resource_health(
    runtime_context: Any | None = None,
    resource_id: str = "",
) -> dict[str, Any]:
    """
    Get EC2 instance health/status.

    Args:
        resource_id: Optional EC2 instance ID. If omitted, returns status for all instances.
    """
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        cfg = await get_cloud_provider_config(runtime_context, "internal_aws_get_resource_health", "aws")
        adapter = AWSAdapter(cfg)
        return await adapter.get_resource_health(resource_id=resource_id)
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"internal_aws_get_resource_health failed: {e}")
        return {"success": False, "error": str(e)}


async def internal_aws_list_security_findings(
    runtime_context: Any | None = None,
    severity: str = "",
) -> dict[str, Any]:
    """
    List AWS Security Hub findings.

    Args:
        severity: Optional severity filter — one of 'INFORMATIONAL', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'.
    """
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        cfg = await get_cloud_provider_config(runtime_context, "internal_aws_list_security_findings", "aws")
        adapter = AWSAdapter(cfg)
        return await adapter.list_security_findings(severity=severity)
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"internal_aws_list_security_findings failed: {e}")
        return {"success": False, "error": str(e)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/unit/services/agents/internal_tools/test_aws_tools.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add api/src/services/agents/internal_tools/aws_tools.py api/tests/unit/services/agents/internal_tools/test_aws_tools.py
git commit -m "feat: add internal_aws_* tool functions"
```

## Task 6: AWS tool registry + `adk_tools.py` wiring

**Files:**
- Create: `api/src/services/agents/tool_registrations/aws_tools_registry.py`
- Modify: `api/src/services/agents/adk_tools.py` (add `register_aws_tools(self)` call in `_register_default_tools()`)
- Test: `api/tests/unit/services/agents/tool_registrations/test_aws_tools_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# api/tests/unit/services/agents/tool_registrations/test_aws_tools_registry.py
"""Tests for AWS tool registration with the ADK tool registry."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.agents.tool_registrations.aws_tools_registry import register_aws_tools

_EXPECTED_TOOLS = {
    "internal_aws_get_logs",
    "internal_aws_get_metrics",
    "internal_aws_list_alerts",
    "internal_aws_get_resource_health",
    "internal_aws_list_security_findings",
}


@pytest.mark.unit
class TestRegisterAwsTools:
    def test_registers_all_five_tools_with_read_category_and_aws_auth(self):
        registry = MagicMock()
        register_aws_tools(registry)

        assert registry.register_tool.call_count == 5
        registered_names = set()
        for call in registry.register_tool.call_args_list:
            kwargs = call.kwargs
            registered_names.add(kwargs["name"])
            assert kwargs["requires_auth"] == "aws"
            assert kwargs["tool_category"] == "read"
            assert callable(kwargs["function"])
            assert kwargs["parameters"]["type"] == "object"
        assert registered_names == _EXPECTED_TOOLS

    @pytest.mark.asyncio
    async def test_get_logs_wrapper_forwards_runtime_context_and_kwargs(self):
        registry = MagicMock()
        register_aws_tools(registry)
        wrapper = next(
            call.kwargs["function"]
            for call in registry.register_tool.call_args_list
            if call.kwargs["name"] == "internal_aws_get_logs"
        )

        runtime_context = object()
        with patch(
            "src.services.agents.tool_registrations.aws_tools_registry.internal_aws_get_logs",
            new=AsyncMock(return_value={"success": True, "error": None, "entries": []}),
        ) as mock_fn:
            result = await wrapper(
                config={"_runtime_context": runtime_context},
                log_source="/aws/lambda/foo",
                start_time="a",
                end_time="b",
            )
            mock_fn.assert_called_once_with(
                runtime_context=runtime_context,
                log_source="/aws/lambda/foo",
                start_time="a",
                end_time="b",
                filter_query="",
                limit=100,
            )
            assert result["success"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/unit/services/agents/tool_registrations/test_aws_tools_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.agents.tool_registrations.aws_tools_registry'`

- [ ] **Step 3: Write minimal implementation**

```python
# api/src/services/agents/tool_registrations/aws_tools_registry.py
"""
AWS Tools Registry

Registers CloudWatch Logs/Metrics/Alarms, EC2 status, and Security Hub tools
with the ADK tool registry. All 5 tools are read-only (tool_category="read")
so they don't trigger HITL approval gating.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register_aws_tools(registry):
    """
    Register all AWS tools with the ADK tool registry.

    Args:
        registry: ADKToolRegistry instance
    """
    from src.services.agents.internal_tools.aws_tools import (
        internal_aws_get_logs,
        internal_aws_get_metrics,
        internal_aws_get_resource_health,
        internal_aws_list_alerts,
        internal_aws_list_security_findings,
    )

    async def aws_get_logs_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_aws_get_logs(
            runtime_context=runtime_context,
            log_source=kwargs.get("log_source", ""),
            start_time=kwargs.get("start_time", ""),
            end_time=kwargs.get("end_time", ""),
            filter_query=kwargs.get("filter_query", ""),
            limit=kwargs.get("limit", 100),
        )

    async def aws_get_metrics_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_aws_get_metrics(
            runtime_context=runtime_context,
            metric_name=kwargs.get("metric_name", ""),
            start_time=kwargs.get("start_time", ""),
            end_time=kwargs.get("end_time", ""),
            resource_id=kwargs.get("resource_id", ""),
            period_seconds=kwargs.get("period_seconds", 300),
        )

    async def aws_list_alerts_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_aws_list_alerts(
            runtime_context=runtime_context,
            active_only=kwargs.get("active_only", True),
        )

    async def aws_get_resource_health_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_aws_get_resource_health(
            runtime_context=runtime_context,
            resource_id=kwargs.get("resource_id", ""),
        )

    async def aws_list_security_findings_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_aws_list_security_findings(
            runtime_context=runtime_context,
            severity=kwargs.get("severity", ""),
        )

    registry.register_tool(
        name="internal_aws_get_logs",
        description=(
            "Fetch AWS CloudWatch Logs entries from a log group. Use during incident investigation "
            "to pull application/Lambda/ECS logs. Keywords: AWS, CloudWatch Logs, log group, Lambda logs."
        ),
        parameters={
            "type": "object",
            "properties": {
                "log_source": {
                    "type": "string",
                    "description": "CloudWatch Logs log group name, e.g. '/aws/lambda/my-function'",
                },
                "start_time": {"type": "string", "description": "Start of time range, ISO 8601"},
                "end_time": {"type": "string", "description": "End of time range, ISO 8601"},
                "filter_query": {"type": "string", "description": "Optional CloudWatch Logs filter pattern"},
                "limit": {"type": "integer", "description": "Max entries to return (default 100)", "default": 100},
            },
            "required": ["log_source", "start_time", "end_time"],
        },
        function=aws_get_logs_wrapper,
        requires_auth="aws",
        tool_category="read",
    )

    registry.register_tool(
        name="internal_aws_get_metrics",
        description=(
            "Fetch an AWS CloudWatch metric time series (e.g. CPUUtilization, latency). "
            "Keywords: AWS, CloudWatch Metrics, EC2 metrics, get_metric_statistics."
        ),
        parameters={
            "type": "object",
            "properties": {
                "metric_name": {
                    "type": "string",
                    "description": "Metric name, optionally 'Namespace:MetricName' (default namespace AWS/EC2)",
                },
                "start_time": {"type": "string", "description": "Start of time range, ISO 8601"},
                "end_time": {"type": "string", "description": "End of time range, ISO 8601"},
                "resource_id": {"type": "string", "description": "Optional EC2 instance ID to scope to"},
                "period_seconds": {
                    "type": "integer",
                    "description": "Datapoint granularity in seconds (default 300)",
                    "default": 300,
                },
            },
            "required": ["metric_name", "start_time", "end_time"],
        },
        function=aws_get_metrics_wrapper,
        requires_auth="aws",
        tool_category="read",
    )

    registry.register_tool(
        name="internal_aws_list_alerts",
        description=(
            "List AWS CloudWatch Alarms. Keywords: AWS, CloudWatch Alarms, alerting, describe_alarms."
        ),
        parameters={
            "type": "object",
            "properties": {
                "active_only": {
                    "type": "boolean",
                    "description": "If true (default), only return alarms currently in ALARM state",
                    "default": True,
                },
            },
            "required": [],
        },
        function=aws_list_alerts_wrapper,
        requires_auth="aws",
        tool_category="read",
    )

    registry.register_tool(
        name="internal_aws_get_resource_health",
        description=(
            "Get AWS EC2 instance health/status. Keywords: AWS, EC2, instance status, resource health."
        ),
        parameters={
            "type": "object",
            "properties": {
                "resource_id": {
                    "type": "string",
                    "description": "Optional EC2 instance ID; omit to check all instances",
                },
            },
            "required": [],
        },
        function=aws_get_resource_health_wrapper,
        requires_auth="aws",
        tool_category="read",
    )

    registry.register_tool(
        name="internal_aws_list_security_findings",
        description=(
            "List AWS Security Hub findings. Keywords: AWS, Security Hub, GuardDuty, security findings, "
            "vulnerabilities."
        ),
        parameters={
            "type": "object",
            "properties": {
                "severity": {
                    "type": "string",
                    "description": "Optional severity filter: INFORMATIONAL, LOW, MEDIUM, HIGH, CRITICAL",
                },
            },
            "required": [],
        },
        function=aws_list_security_findings_wrapper,
        requires_auth="aws",
        tool_category="read",
    )

    logger.info("Registered 5 AWS tools")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/unit/services/agents/tool_registrations/test_aws_tools_registry.py -v`
Expected: 2 passed

- [ ] **Step 5: Wire into `adk_tools.py`**

In `api/src/services/agents/adk_tools.py`, inside `_register_default_tools()` (near the other `register_*_tools(self)` calls, e.g. right after the `register_google_calendar_tools(self)` block at line ~179), add:

```python
        # AWS tools - use modular registry
        from src.services.agents.tool_registrations.aws_tools_registry import (
            register_aws_tools,
        )

        register_aws_tools(self)
```

- [ ] **Step 6: Verify the full tool registry loads without error**

Run: `docker compose exec -T api python -c "from src.services.agents.adk_tools import ADKToolRegistry; r = ADKToolRegistry(); print('internal_aws_get_logs' in r.tools)"`
Expected: prints `True`

- [ ] **Step 7: Commit**

```bash
git add api/src/services/agents/tool_registrations/aws_tools_registry.py api/tests/unit/services/agents/tool_registrations/test_aws_tools_registry.py api/src/services/agents/adk_tools.py
git commit -m "feat: register AWS tools with the ADK tool registry"
```

## Task 7: GCP adapter (`httpx` + service-account JWT auth)

No new dependency needed for tests — mock `httpx.AsyncClient` directly with a fake class (the same `monkeypatch.setattr(httpx, "AsyncClient", ...)` pattern already used in `tests/unit/services/slack/test_slack_message_handler.py::test_upload_diagram_fetches_svg_url_when_content_missing`), rather than adding `respx` as a new dependency.

**Files:**
- Create: `api/src/services/cloud_providers/gcp_adapter.py`
- Test: `api/tests/unit/services/cloud_providers/test_gcp_adapter.py`

- [ ] **Step 1: Write the failing test**

```python
# api/tests/unit/services/cloud_providers/test_gcp_adapter.py
"""Tests for GCPAdapter using a fake httpx.AsyncClient (no respx dependency)."""

import json

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from src.services.cloud_providers.gcp_adapter import GCPAdapter


def _test_private_key_pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


_PRIVATE_KEY_PEM = _test_private_key_pem()


def _credentials(project_id="my-project"):
    service_account = {
        "type": "service_account",
        "project_id": project_id,
        "private_key": _PRIVATE_KEY_PEM,
        "client_email": "agent@my-project.iam.gserviceaccount.com",
    }
    return {
        "client_id": None,
        "api_token": json.dumps(service_account),
        "config": {"project_id": project_id},
    }


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = json.dumps(self._json)

    @property
    def is_success(self):
        return 200 <= self.status_code < 300

    def json(self):
        return self._json


class _FakeAsyncClient:
    """Routes requests by matching a substring of the URL against `responses`."""

    responses: dict[str, _FakeResponse] = {}

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    def _resolve(self, url):
        for key, resp in self.responses.items():
            if key in url:
                return resp
        raise AssertionError(f"unexpected URL in test: {url}")

    async def post(self, url, **kwargs):
        return self._resolve(url)

    async def get(self, url, **kwargs):
        return self._resolve(url)

    async def request(self, method, url, **kwargs):
        return self._resolve(url)


@pytest.fixture(autouse=True)
def _patch_httpx(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.responses = {
        "oauth2.googleapis.com/token": _FakeResponse(json_data={"access_token": "fake-access-token"}),
    }
    yield


@pytest.mark.unit
class TestGCPAdapterInit:
    def test_parses_service_account_and_project_id(self):
        adapter = GCPAdapter(_credentials(project_id="proj-a"))
        assert adapter.project_id == "proj-a"
        assert adapter.service_account["client_email"] == "agent@my-project.iam.gserviceaccount.com"

    def test_falls_back_to_service_account_project_id_when_config_missing(self):
        creds = _credentials(project_id="proj-b")
        creds["config"] = {}
        adapter = GCPAdapter(creds)
        assert adapter.project_id == "proj-b"


@pytest.mark.unit
class TestGCPAdapterGetLogs:
    @pytest.mark.asyncio
    async def test_get_logs_returns_entries(self):
        _FakeAsyncClient.responses["logging.googleapis.com"] = _FakeResponse(
            json_data={"entries": [{"textPayload": "hello"}]}
        )
        adapter = GCPAdapter(_credentials())
        result = await adapter.get_logs("my-log", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z")
        assert result["success"] is True
        assert result["entries"] == [{"textPayload": "hello"}]

    @pytest.mark.asyncio
    async def test_get_logs_returns_error_on_failed_token_exchange(self):
        _FakeAsyncClient.responses["oauth2.googleapis.com/token"] = _FakeResponse(status_code=401, json_data={})
        adapter = GCPAdapter(_credentials())
        result = await adapter.get_logs("my-log", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z")
        assert result["success"] is False
        assert "credentials are invalid" in result["error"]


@pytest.mark.unit
class TestGCPAdapterOtherCapabilities:
    @pytest.mark.asyncio
    async def test_get_metrics_returns_datapoints(self):
        _FakeAsyncClient.responses["monitoring.googleapis.com"] = _FakeResponse(
            json_data={"timeSeries": [{"points": []}]}
        )
        adapter = GCPAdapter(_credentials())
        result = await adapter.get_metrics("compute.googleapis.com/instance/cpu/utilization", "a", "b")
        assert result["success"] is True
        assert result["datapoints"] == [{"points": []}]

    @pytest.mark.asyncio
    async def test_list_alerts_filters_disabled_when_active_only(self):
        _FakeAsyncClient.responses["monitoring.googleapis.com"] = _FakeResponse(
            json_data={"alertPolicies": [{"displayName": "on", "enabled": True}, {"displayName": "off", "enabled": False}]}
        )
        adapter = GCPAdapter(_credentials())
        result = await adapter.list_alerts(active_only=True)
        assert result["success"] is True
        assert [a["displayName"] for a in result["alerts"]] == ["on"]

    @pytest.mark.asyncio
    async def test_get_resource_health_filters_by_resource_id(self):
        _FakeAsyncClient.responses["compute.googleapis.com"] = _FakeResponse(
            json_data={
                "items": {
                    "zones/us-central1-a": {
                        "instances": [
                            {"name": "vm-1", "status": "RUNNING", "zone": "z1"},
                            {"name": "vm-2", "status": "STOPPED", "zone": "z1"},
                        ]
                    }
                }
            }
        )
        adapter = GCPAdapter(_credentials())
        result = await adapter.get_resource_health(resource_id="vm-2")
        assert result["success"] is True
        assert [i["name"] for i in result["instances"]] == ["vm-2"]

    @pytest.mark.asyncio
    async def test_list_security_findings_returns_findings(self):
        _FakeAsyncClient.responses["securitycenter.googleapis.com"] = _FakeResponse(
            json_data={"listFindingsResults": [{"finding": {"name": "f1", "severity": "HIGH"}}]}
        )
        adapter = GCPAdapter(_credentials())
        result = await adapter.list_security_findings(severity="HIGH")
        assert result["success"] is True
        assert result["findings"] == [{"name": "f1", "severity": "HIGH"}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/unit/services/cloud_providers/test_gcp_adapter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.cloud_providers.gcp_adapter'`

- [ ] **Step 3: Write minimal implementation**

```python
# api/src/services/cloud_providers/gcp_adapter.py
"""
GCP adapter — Cloud Logging, Cloud Monitoring, Compute Engine, Security Command Center.

Auth: the full service-account JSON key is stored as OAuthApp.api_token. We sign
a JWT with the service account's private key (RS256, via the already-present
`pyjwt` + `cryptography` — the same libraries used for GitHub App JWT auth in
credential_resolver.py) and exchange it for a bearer token at Google's OAuth2
token endpoint. Plain REST calls via httpx — no google-cloud-* SDKs.
"""

import json
import time
from typing import Any

import httpx
import jwt as pyjwt

from src.services.cloud_providers.base_adapter import CloudProviderAdapter

_SCOPE = "https://www.googleapis.com/auth/cloud-platform.read-only"
_TOKEN_URL = "https://oauth2.googleapis.com/token"


class GCPAdapter(CloudProviderAdapter):
    def __init__(self, credentials: dict[str, Any]):
        super().__init__(credentials)
        self.service_account = json.loads(credentials["api_token"])
        config = credentials.get("config") or {}
        self.project_id = config.get("project_id") or self.service_account.get("project_id")

    async def _get_access_token(self) -> str:
        now = int(time.time())
        claims = {
            "iss": self.service_account["client_email"],
            "scope": _SCOPE,
            "aud": _TOKEN_URL,
            "iat": now,
            "exp": now + 3600,
        }
        signed = pyjwt.encode(claims, self.service_account["private_key"], algorithm="RS256")
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                _TOKEN_URL,
                data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": signed},
            )
        if not resp.is_success:
            raise ValueError("GCP credentials are invalid or expired — please reconnect in Integrations.")
        return resp.json()["access_token"]

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        token = await self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(timeout=30) as client:
            return await client.request(method, url, headers=headers, **kwargs)

    async def get_logs(
        self, log_source: str, start_time: str, end_time: str, filter_query: str = "", limit: int = 100
    ) -> dict[str, Any]:
        try:
            filter_parts = [f'timestamp>="{start_time}"', f'timestamp<="{end_time}"']
            if log_source:
                filter_parts.append(f'logName="projects/{self.project_id}/logs/{log_source}"')
            if filter_query:
                filter_parts.append(filter_query)
            body = {
                "resourceNames": [f"projects/{self.project_id}"],
                "filter": " AND ".join(filter_parts),
                "pageSize": min(limit, 1000),
                "orderBy": "timestamp desc",
            }
            resp = await self._request("POST", "https://logging.googleapis.com/v2/entries:list", json=body)
            if not resp.is_success:
                return self._fail(f"GCP Logging error {resp.status_code}: {resp.text[:300]}")
            return self._ok(entries=resp.json().get("entries", []))
        except ValueError as e:
            return self._fail(str(e))
        except Exception as e:
            return self._fail(f"GCP error: {e}")

    async def get_metrics(
        self, metric_name: str, start_time: str, end_time: str, resource_id: str = "", period_seconds: int = 300
    ) -> dict[str, Any]:
        try:
            metric_filter = f'metric.type="{metric_name}"'
            if resource_id:
                metric_filter += f' AND resource.labels.instance_id="{resource_id}"'
            params = {
                "filter": metric_filter,
                "interval.startTime": start_time,
                "interval.endTime": end_time,
                "aggregation.alignmentPeriod": f"{period_seconds}s",
            }
            url = f"https://monitoring.googleapis.com/v3/projects/{self.project_id}/timeSeries"
            resp = await self._request("GET", url, params=params)
            if not resp.is_success:
                return self._fail(f"GCP Monitoring error {resp.status_code}: {resp.text[:300]}")
            return self._ok(datapoints=resp.json().get("timeSeries", []))
        except ValueError as e:
            return self._fail(str(e))
        except Exception as e:
            return self._fail(f"GCP error: {e}")

    async def list_alerts(self, active_only: bool = True) -> dict[str, Any]:
        try:
            url = f"https://monitoring.googleapis.com/v3/projects/{self.project_id}/alertPolicies"
            resp = await self._request("GET", url)
            if not resp.is_success:
                return self._fail(f"GCP Monitoring error {resp.status_code}: {resp.text[:300]}")
            policies = resp.json().get("alertPolicies", [])
            if active_only:
                policies = [p for p in policies if p.get("enabled", True)]
            return self._ok(alerts=policies)
        except ValueError as e:
            return self._fail(str(e))
        except Exception as e:
            return self._fail(f"GCP error: {e}")

    async def get_resource_health(self, resource_id: str = "") -> dict[str, Any]:
        try:
            url = f"https://compute.googleapis.com/compute/v1/projects/{self.project_id}/aggregated/instances"
            resp = await self._request("GET", url)
            if not resp.is_success:
                return self._fail(f"GCP Compute error {resp.status_code}: {resp.text[:300]}")
            instances = []
            for scoped in resp.json().get("items", {}).values():
                for inst in scoped.get("instances", []):
                    if resource_id and inst.get("name") != resource_id:
                        continue
                    instances.append(
                        {"name": inst.get("name"), "status": inst.get("status"), "zone": inst.get("zone")}
                    )
            return self._ok(instances=instances)
        except ValueError as e:
            return self._fail(str(e))
        except Exception as e:
            return self._fail(f"GCP error: {e}")

    async def list_security_findings(self, severity: str = "") -> dict[str, Any]:
        try:
            url = f"https://securitycenter.googleapis.com/v1/projects/{self.project_id}/sources/-/findings"
            params = {}
            if severity:
                params["filter"] = f'severity="{severity.upper()}"'
            resp = await self._request("GET", url, params=params)
            if not resp.is_success:
                return self._fail(f"GCP Security Command Center error {resp.status_code}: {resp.text[:300]}")
            findings = [r.get("finding", {}) for r in resp.json().get("listFindingsResults", [])]
            return self._ok(findings=findings)
        except ValueError as e:
            return self._fail(str(e))
        except Exception as e:
            return self._fail(f"GCP error: {e}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/unit/services/cloud_providers/test_gcp_adapter.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add api/src/services/cloud_providers/gcp_adapter.py api/tests/unit/services/cloud_providers/test_gcp_adapter.py
git commit -m "feat: add GCP cloud provider adapter (Cloud Logging/Monitoring/Compute/SCC)"
```

## Task 8: GCP tool functions (`internal_tools/gcp_tools.py`)

**Files:**
- Create: `api/src/services/agents/internal_tools/gcp_tools.py`
- Test: `api/tests/unit/services/agents/internal_tools/test_gcp_tools.py`

- [ ] **Step 1: Write the failing test**

```python
# api/tests/unit/services/agents/internal_tools/test_gcp_tools.py
"""Tests for internal_gcp_* tool functions."""

from unittest.mock import AsyncMock, patch

import pytest

from src.services.agents.internal_tools.gcp_tools import (
    internal_gcp_get_logs,
    internal_gcp_get_metrics,
    internal_gcp_get_resource_health,
    internal_gcp_list_alerts,
    internal_gcp_list_security_findings,
)

_CFG = {"client_id": None, "api_token": "{}", "config": {"project_id": "proj"}}


@pytest.mark.unit
class TestGCPToolsNoRuntimeContext:
    @pytest.mark.asyncio
    async def test_get_logs_without_runtime_context(self):
        result = await internal_gcp_get_logs(runtime_context=None, log_source="x", start_time="a", end_time="b")
        assert result == {"success": False, "error": "No runtime context available."}


@pytest.mark.unit
class TestGCPToolsHappyPath:
    @pytest.mark.asyncio
    async def test_get_logs_delegates_to_adapter(self):
        with (
            patch(
                "src.services.agents.internal_tools.gcp_tools.get_cloud_provider_config",
                new=AsyncMock(return_value=_CFG),
            ),
            patch("src.services.agents.internal_tools.gcp_tools.GCPAdapter") as MockAdapter,
        ):
            MockAdapter.return_value.get_logs = AsyncMock(return_value={"success": True, "error": None, "entries": []})
            result = await internal_gcp_get_logs(
                runtime_context=object(), log_source="my-log", start_time="a", end_time="b"
            )
            MockAdapter.assert_called_once_with(_CFG)
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_get_metrics_delegates_to_adapter(self):
        with (
            patch(
                "src.services.agents.internal_tools.gcp_tools.get_cloud_provider_config",
                new=AsyncMock(return_value=_CFG),
            ),
            patch("src.services.agents.internal_tools.gcp_tools.GCPAdapter") as MockAdapter,
        ):
            MockAdapter.return_value.get_metrics = AsyncMock(
                return_value={"success": True, "error": None, "datapoints": []}
            )
            result = await internal_gcp_get_metrics(
                runtime_context=object(), metric_name="compute.googleapis.com/instance/cpu/utilization",
                start_time="a", end_time="b",
            )
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_list_alerts_delegates_to_adapter(self):
        with (
            patch(
                "src.services.agents.internal_tools.gcp_tools.get_cloud_provider_config",
                new=AsyncMock(return_value=_CFG),
            ),
            patch("src.services.agents.internal_tools.gcp_tools.GCPAdapter") as MockAdapter,
        ):
            MockAdapter.return_value.list_alerts = AsyncMock(
                return_value={"success": True, "error": None, "alerts": []}
            )
            result = await internal_gcp_list_alerts(runtime_context=object())
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_get_resource_health_delegates_to_adapter(self):
        with (
            patch(
                "src.services.agents.internal_tools.gcp_tools.get_cloud_provider_config",
                new=AsyncMock(return_value=_CFG),
            ),
            patch("src.services.agents.internal_tools.gcp_tools.GCPAdapter") as MockAdapter,
        ):
            MockAdapter.return_value.get_resource_health = AsyncMock(
                return_value={"success": True, "error": None, "instances": []}
            )
            result = await internal_gcp_get_resource_health(runtime_context=object())
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_list_security_findings_delegates_to_adapter(self):
        with (
            patch(
                "src.services.agents.internal_tools.gcp_tools.get_cloud_provider_config",
                new=AsyncMock(return_value=_CFG),
            ),
            patch("src.services.agents.internal_tools.gcp_tools.GCPAdapter") as MockAdapter,
        ):
            MockAdapter.return_value.list_security_findings = AsyncMock(
                return_value={"success": True, "error": None, "findings": []}
            )
            result = await internal_gcp_list_security_findings(runtime_context=object())
            assert result["success"] is True


@pytest.mark.unit
class TestGCPToolsCredentialError:
    @pytest.mark.asyncio
    async def test_returns_error_dict_when_credential_resolution_fails(self):
        with patch(
            "src.services.agents.internal_tools.gcp_tools.get_cloud_provider_config",
            new=AsyncMock(side_effect=ValueError("No OAuth app configured for tool 'x'.")),
        ):
            result = await internal_gcp_list_alerts(runtime_context=object())
            assert result == {"success": False, "error": "No OAuth app configured for tool 'x'."}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/unit/services/agents/internal_tools/test_gcp_tools.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.agents.internal_tools.gcp_tools'`

- [ ] **Step 3: Write minimal implementation**

```python
# api/src/services/agents/internal_tools/gcp_tools.py
"""
GCP Tools — Cloud Logging, Cloud Monitoring, Compute Engine, Security Command Center.

Auth: full service-account JSON key stored in OAuthApp (provider='gcp',
auth_method='api_token'), project_id in OAuthApp.config (falls back to the
service account JSON's own project_id if omitted).
"""

import logging
from typing import Any

from src.services.agents.internal_tools.cloud_shared import get_cloud_provider_config
from src.services.cloud_providers.gcp_adapter import GCPAdapter

logger = logging.getLogger(__name__)


async def internal_gcp_get_logs(
    runtime_context: Any | None = None,
    log_source: str = "",
    start_time: str = "",
    end_time: str = "",
    filter_query: str = "",
    limit: int = 100,
) -> dict[str, Any]:
    """
    Fetch Cloud Logging entries.

    Args:
        log_source: Cloud Logging log ID (e.g. 'run.googleapis.com%2Fstderr')
        start_time: Start of time range, ISO 8601
        end_time: End of time range, ISO 8601
        filter_query: Optional additional Cloud Logging filter expression
        limit: Max entries to return (default 100)
    """
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        cfg = await get_cloud_provider_config(runtime_context, "internal_gcp_get_logs", "gcp")
        adapter = GCPAdapter(cfg)
        return await adapter.get_logs(
            log_source=log_source, start_time=start_time, end_time=end_time, filter_query=filter_query, limit=limit
        )
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"internal_gcp_get_logs failed: {e}")
        return {"success": False, "error": str(e)}


async def internal_gcp_get_metrics(
    runtime_context: Any | None = None,
    metric_name: str = "",
    start_time: str = "",
    end_time: str = "",
    resource_id: str = "",
    period_seconds: int = 300,
) -> dict[str, Any]:
    """
    Fetch a Cloud Monitoring metric time series.

    Args:
        metric_name: Full metric type, e.g. 'compute.googleapis.com/instance/cpu/utilization'
        start_time: Start of time range, ISO 8601
        end_time: End of time range, ISO 8601
        resource_id: Optional Compute Engine instance ID to scope to
        period_seconds: Alignment period in seconds (default 300)
    """
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        cfg = await get_cloud_provider_config(runtime_context, "internal_gcp_get_metrics", "gcp")
        adapter = GCPAdapter(cfg)
        return await adapter.get_metrics(
            metric_name=metric_name,
            start_time=start_time,
            end_time=end_time,
            resource_id=resource_id,
            period_seconds=period_seconds,
        )
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"internal_gcp_get_metrics failed: {e}")
        return {"success": False, "error": str(e)}


async def internal_gcp_list_alerts(
    runtime_context: Any | None = None,
    active_only: bool = True,
) -> dict[str, Any]:
    """
    List Cloud Monitoring alerting policies.

    Args:
        active_only: If True (default), only return enabled policies.
    """
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        cfg = await get_cloud_provider_config(runtime_context, "internal_gcp_list_alerts", "gcp")
        adapter = GCPAdapter(cfg)
        return await adapter.list_alerts(active_only=active_only)
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"internal_gcp_list_alerts failed: {e}")
        return {"success": False, "error": str(e)}


async def internal_gcp_get_resource_health(
    runtime_context: Any | None = None,
    resource_id: str = "",
) -> dict[str, Any]:
    """
    Get Compute Engine instance health/status.

    Args:
        resource_id: Optional instance name. If omitted, returns status for all instances.
    """
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        cfg = await get_cloud_provider_config(runtime_context, "internal_gcp_get_resource_health", "gcp")
        adapter = GCPAdapter(cfg)
        return await adapter.get_resource_health(resource_id=resource_id)
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"internal_gcp_get_resource_health failed: {e}")
        return {"success": False, "error": str(e)}


async def internal_gcp_list_security_findings(
    runtime_context: Any | None = None,
    severity: str = "",
) -> dict[str, Any]:
    """
    List Security Command Center findings.

    Args:
        severity: Optional severity filter — one of 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'.
    """
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        cfg = await get_cloud_provider_config(runtime_context, "internal_gcp_list_security_findings", "gcp")
        adapter = GCPAdapter(cfg)
        return await adapter.list_security_findings(severity=severity)
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"internal_gcp_list_security_findings failed: {e}")
        return {"success": False, "error": str(e)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/unit/services/agents/internal_tools/test_gcp_tools.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add api/src/services/agents/internal_tools/gcp_tools.py api/tests/unit/services/agents/internal_tools/test_gcp_tools.py
git commit -m "feat: add internal_gcp_* tool functions"
```

## Task 9: GCP tool registry + `adk_tools.py` wiring

**Files:**
- Create: `api/src/services/agents/tool_registrations/gcp_tools_registry.py`
- Modify: `api/src/services/agents/adk_tools.py` (add `register_gcp_tools(self)` call)
- Test: `api/tests/unit/services/agents/tool_registrations/test_gcp_tools_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# api/tests/unit/services/agents/tool_registrations/test_gcp_tools_registry.py
"""Tests for GCP tool registration with the ADK tool registry."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.agents.tool_registrations.gcp_tools_registry import register_gcp_tools

_EXPECTED_TOOLS = {
    "internal_gcp_get_logs",
    "internal_gcp_get_metrics",
    "internal_gcp_list_alerts",
    "internal_gcp_get_resource_health",
    "internal_gcp_list_security_findings",
}


@pytest.mark.unit
class TestRegisterGcpTools:
    def test_registers_all_five_tools_with_read_category_and_gcp_auth(self):
        registry = MagicMock()
        register_gcp_tools(registry)

        assert registry.register_tool.call_count == 5
        registered_names = set()
        for call in registry.register_tool.call_args_list:
            kwargs = call.kwargs
            registered_names.add(kwargs["name"])
            assert kwargs["requires_auth"] == "gcp"
            assert kwargs["tool_category"] == "read"
            assert callable(kwargs["function"])
        assert registered_names == _EXPECTED_TOOLS

    @pytest.mark.asyncio
    async def test_get_logs_wrapper_forwards_runtime_context_and_kwargs(self):
        registry = MagicMock()
        register_gcp_tools(registry)
        wrapper = next(
            call.kwargs["function"]
            for call in registry.register_tool.call_args_list
            if call.kwargs["name"] == "internal_gcp_get_logs"
        )

        runtime_context = object()
        with patch(
            "src.services.agents.tool_registrations.gcp_tools_registry.internal_gcp_get_logs",
            new=AsyncMock(return_value={"success": True, "error": None, "entries": []}),
        ) as mock_fn:
            result = await wrapper(
                config={"_runtime_context": runtime_context},
                log_source="my-log",
                start_time="a",
                end_time="b",
            )
            mock_fn.assert_called_once_with(
                runtime_context=runtime_context,
                log_source="my-log",
                start_time="a",
                end_time="b",
                filter_query="",
                limit=100,
            )
            assert result["success"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/unit/services/agents/tool_registrations/test_gcp_tools_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.agents.tool_registrations.gcp_tools_registry'`

- [ ] **Step 3: Write minimal implementation**

```python
# api/src/services/agents/tool_registrations/gcp_tools_registry.py
"""
GCP Tools Registry

Registers Cloud Logging/Monitoring/Compute/Security-Command-Center tools with
the ADK tool registry. All 5 tools are read-only (tool_category="read").
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register_gcp_tools(registry):
    """
    Register all GCP tools with the ADK tool registry.

    Args:
        registry: ADKToolRegistry instance
    """
    from src.services.agents.internal_tools.gcp_tools import (
        internal_gcp_get_logs,
        internal_gcp_get_metrics,
        internal_gcp_get_resource_health,
        internal_gcp_list_alerts,
        internal_gcp_list_security_findings,
    )

    async def gcp_get_logs_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gcp_get_logs(
            runtime_context=runtime_context,
            log_source=kwargs.get("log_source", ""),
            start_time=kwargs.get("start_time", ""),
            end_time=kwargs.get("end_time", ""),
            filter_query=kwargs.get("filter_query", ""),
            limit=kwargs.get("limit", 100),
        )

    async def gcp_get_metrics_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gcp_get_metrics(
            runtime_context=runtime_context,
            metric_name=kwargs.get("metric_name", ""),
            start_time=kwargs.get("start_time", ""),
            end_time=kwargs.get("end_time", ""),
            resource_id=kwargs.get("resource_id", ""),
            period_seconds=kwargs.get("period_seconds", 300),
        )

    async def gcp_list_alerts_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gcp_list_alerts(
            runtime_context=runtime_context,
            active_only=kwargs.get("active_only", True),
        )

    async def gcp_get_resource_health_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gcp_get_resource_health(
            runtime_context=runtime_context,
            resource_id=kwargs.get("resource_id", ""),
        )

    async def gcp_list_security_findings_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gcp_list_security_findings(
            runtime_context=runtime_context,
            severity=kwargs.get("severity", ""),
        )

    registry.register_tool(
        name="internal_gcp_get_logs",
        description=(
            "Fetch Google Cloud Logging entries. Use during incident investigation to pull "
            "Cloud Run/GKE/App Engine logs. Keywords: GCP, Google Cloud, Cloud Logging, Stackdriver."
        ),
        parameters={
            "type": "object",
            "properties": {
                "log_source": {"type": "string", "description": "Cloud Logging log ID, e.g. 'run.googleapis.com%2Fstderr'"},
                "start_time": {"type": "string", "description": "Start of time range, ISO 8601"},
                "end_time": {"type": "string", "description": "End of time range, ISO 8601"},
                "filter_query": {"type": "string", "description": "Optional additional Cloud Logging filter expression"},
                "limit": {"type": "integer", "description": "Max entries to return (default 100)", "default": 100},
            },
            "required": ["log_source", "start_time", "end_time"],
        },
        function=gcp_get_logs_wrapper,
        requires_auth="gcp",
        tool_category="read",
    )

    registry.register_tool(
        name="internal_gcp_get_metrics",
        description=(
            "Fetch a Google Cloud Monitoring metric time series (e.g. CPU utilization). "
            "Keywords: GCP, Google Cloud, Cloud Monitoring, Stackdriver Monitoring."
        ),
        parameters={
            "type": "object",
            "properties": {
                "metric_name": {
                    "type": "string",
                    "description": "Full metric type, e.g. 'compute.googleapis.com/instance/cpu/utilization'",
                },
                "start_time": {"type": "string", "description": "Start of time range, ISO 8601"},
                "end_time": {"type": "string", "description": "End of time range, ISO 8601"},
                "resource_id": {"type": "string", "description": "Optional Compute Engine instance ID to scope to"},
                "period_seconds": {
                    "type": "integer",
                    "description": "Alignment period in seconds (default 300)",
                    "default": 300,
                },
            },
            "required": ["metric_name", "start_time", "end_time"],
        },
        function=gcp_get_metrics_wrapper,
        requires_auth="gcp",
        tool_category="read",
    )

    registry.register_tool(
        name="internal_gcp_list_alerts",
        description=(
            "List Google Cloud Monitoring alerting policies. Keywords: GCP, Google Cloud, "
            "alert policies, Cloud Monitoring alerts."
        ),
        parameters={
            "type": "object",
            "properties": {
                "active_only": {
                    "type": "boolean",
                    "description": "If true (default), only return enabled policies",
                    "default": True,
                },
            },
            "required": [],
        },
        function=gcp_list_alerts_wrapper,
        requires_auth="gcp",
        tool_category="read",
    )

    registry.register_tool(
        name="internal_gcp_get_resource_health",
        description=(
            "Get Google Compute Engine instance health/status. Keywords: GCP, Google Cloud, "
            "Compute Engine, GKE, instance status."
        ),
        parameters={
            "type": "object",
            "properties": {
                "resource_id": {
                    "type": "string",
                    "description": "Optional Compute Engine instance name; omit to check all instances",
                },
            },
            "required": [],
        },
        function=gcp_get_resource_health_wrapper,
        requires_auth="gcp",
        tool_category="read",
    )

    registry.register_tool(
        name="internal_gcp_list_security_findings",
        description=(
            "List Google Cloud Security Command Center findings. Keywords: GCP, Google Cloud, "
            "Security Command Center, SCC, vulnerabilities."
        ),
        parameters={
            "type": "object",
            "properties": {
                "severity": {
                    "type": "string",
                    "description": "Optional severity filter: LOW, MEDIUM, HIGH, CRITICAL",
                },
            },
            "required": [],
        },
        function=gcp_list_security_findings_wrapper,
        requires_auth="gcp",
        tool_category="read",
    )

    logger.info("Registered 5 GCP tools")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/unit/services/agents/tool_registrations/test_gcp_tools_registry.py -v`
Expected: 2 passed

- [ ] **Step 5: Wire into `adk_tools.py`**

In `_register_default_tools()`, right after the AWS registration block added in Task 6, add:

```python
        # GCP tools - use modular registry
        from src.services.agents.tool_registrations.gcp_tools_registry import (
            register_gcp_tools,
        )

        register_gcp_tools(self)
```

- [ ] **Step 6: Verify the full tool registry loads without error**

Run: `docker compose exec -T api python -c "from src.services.agents.adk_tools import ADKToolRegistry; r = ADKToolRegistry(); print('internal_gcp_get_logs' in r.tools)"`
Expected: prints `True`

- [ ] **Step 7: Commit**

```bash
git add api/src/services/agents/tool_registrations/gcp_tools_registry.py api/tests/unit/services/agents/tool_registrations/test_gcp_tools_registry.py api/src/services/agents/adk_tools.py
git commit -m "feat: register GCP tools with the ADK tool registry"
```

---

## Task 10: Azure adapter (`httpx` + OAuth2 client-credentials flow)

**Files:**
- Create: `api/src/services/cloud_providers/azure_adapter.py`
- Test: `api/tests/unit/services/cloud_providers/test_azure_adapter.py`

Azure credentials from `OAuthApp`: `client_id` = AD app client ID, `api_token` (decrypted) = AD
app client secret, `config` = `{"azure_tenant_id": "...", "subscription_id": "..."}`.

Two token scopes are needed: `https://management.azure.com/.default` for ARM (VM/AKS resource
health, alert rules, Defender for Cloud findings) and `https://api.loganalytics.io/.default` for
the Log Analytics query API (Azure Monitor Logs). `get_metrics`/`get_resource_health` require a
full ARM resource ID (e.g.
`/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Compute/virtualMachines/{vm}`) since
Azure Monitor Metrics has no "list all resources" shortcut — return `_fail(...)` with a clear
message if `resource_id` is missing rather than guessing.

- [ ] **Step 1: Write the failing test**

Create `api/tests/unit/services/cloud_providers/test_azure_adapter.py`:

```python
"""Tests for AzureAdapter (Azure Monitor Logs/Metrics/Alerts, Resource Health, Defender)."""

import pytest

from src.services.cloud_providers.azure_adapter import AzureAdapter


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.is_success = 200 <= status_code < 300
        self.text = str(json_data)

    def json(self):
        return self._json_data


class _FakeAsyncClient:
    """Routes requests by URL substring against a class-level `responses` dict.

    Each test sets `_FakeAsyncClient.responses = {"substring": _FakeResponse(...)}`
    before invoking the adapter, mirroring the pattern already used in
    tests/unit/services/slack/test_slack_message_handler.py for httpx mocking.
    """

    responses: dict[str, _FakeResponse] = {}
    requests: list[tuple[str, str, dict]] = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, **kwargs):
        type(self).requests.append(("POST", url, kwargs))
        for substring, resp in type(self).responses.items():
            if substring in url:
                return resp
        raise AssertionError(f"No fake response configured for POST {url}")

    async def request(self, method, url, **kwargs):
        type(self).requests.append((method, url, kwargs))
        for substring, resp in type(self).responses.items():
            if substring in url:
                return resp
        raise AssertionError(f"No fake response configured for {method} {url}")


@pytest.fixture(autouse=True)
def _reset_fake_client(monkeypatch):
    import httpx

    _FakeAsyncClient.responses = {}
    _FakeAsyncClient.requests = []
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    yield


def _credentials(config=None):
    return {
        "client_id": "app-client-id",
        "api_token": "app-client-secret",
        "config": config or {"azure_tenant_id": "tenant-123", "subscription_id": "sub-456"},
    }


class TestAzureAdapterInit:
    def test_stores_tenant_subscription_and_app_credentials(self):
        adapter = AzureAdapter(_credentials())

        assert adapter.tenant_id == "tenant-123"
        assert adapter.subscription_id == "sub-456"
        assert adapter.client_id == "app-client-id"
        assert adapter.client_secret == "app-client-secret"


class TestGetLogs:
    @pytest.mark.asyncio
    async def test_get_logs_success(self):
        _FakeAsyncClient.responses = {
            "oauth2/v2.0/token": _FakeResponse(200, {"access_token": "tok-logs"}),
            "query": _FakeResponse(
                200,
                {
                    "tables": [
                        {
                            "columns": [{"name": "TimeGenerated"}, {"name": "Message"}],
                            "rows": [["2026-08-16T00:00:00Z", "disk usage high"]],
                        }
                    ]
                },
            ),
        }
        adapter = AzureAdapter(_credentials())

        result = await adapter.get_logs(
            log_source="workspace-abc",
            start_time="2026-08-16T00:00:00Z",
            end_time="2026-08-16T01:00:00Z",
        )

        assert result["success"] is True
        assert result["data"][0]["Message"] == "disk usage high"

    @pytest.mark.asyncio
    async def test_get_logs_token_exchange_failure(self):
        _FakeAsyncClient.responses = {
            "oauth2/v2.0/token": _FakeResponse(401, {"error": "invalid_client"}),
        }
        adapter = AzureAdapter(_credentials())

        result = await adapter.get_logs(
            log_source="workspace-abc", start_time="2026-08-16T00:00:00Z", end_time="2026-08-16T01:00:00Z"
        )

        assert result["success"] is False
        assert "invalid or expired" in result["error"]


class TestGetMetrics:
    @pytest.mark.asyncio
    async def test_get_metrics_requires_resource_id(self):
        adapter = AzureAdapter(_credentials())

        result = await adapter.get_metrics(metric_name="Percentage CPU", start_time="2026-08-16T00:00:00Z", end_time="2026-08-16T01:00:00Z")

        assert result["success"] is False
        assert "resource_id" in result["error"]

    @pytest.mark.asyncio
    async def test_get_metrics_success(self):
        _FakeAsyncClient.responses = {
            "oauth2/v2.0/token": _FakeResponse(200, {"access_token": "tok-mgmt"}),
            "/providers/microsoft.insights/metrics": _FakeResponse(
                200,
                {"value": [{"name": {"value": "Percentage CPU"}, "timeseries": [{"data": [{"average": 12.5}]}]}]},
            ),
        }
        adapter = AzureAdapter(_credentials())

        result = await adapter.get_metrics(
            metric_name="Percentage CPU",
            start_time="2026-08-16T00:00:00Z",
            end_time="2026-08-16T01:00:00Z",
            resource_id="/subscriptions/sub-456/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
        )

        assert result["success"] is True
        assert result["data"][0]["name"]["value"] == "Percentage CPU"


class TestListAlerts:
    @pytest.mark.asyncio
    async def test_list_alerts_filters_active(self):
        _FakeAsyncClient.responses = {
            "oauth2/v2.0/token": _FakeResponse(200, {"access_token": "tok-mgmt"}),
            "providers/Microsoft.AlertsManagement/alerts": _FakeResponse(
                200,
                {
                    "value": [
                        {"properties": {"essentials": {"alertState": "New"}}},
                        {"properties": {"essentials": {"alertState": "Closed"}}},
                    ]
                },
            ),
        }
        adapter = AzureAdapter(_credentials())

        result = await adapter.list_alerts(active_only=True)

        assert result["success"] is True
        assert len(result["data"]) == 1
        assert result["data"][0]["properties"]["essentials"]["alertState"] == "New"


class TestGetResourceHealth:
    @pytest.mark.asyncio
    async def test_get_resource_health_requires_resource_id(self):
        adapter = AzureAdapter(_credentials())

        result = await adapter.get_resource_health(resource_id="")

        assert result["success"] is False
        assert "resource_id" in result["error"]

    @pytest.mark.asyncio
    async def test_get_resource_health_success(self):
        _FakeAsyncClient.responses = {
            "oauth2/v2.0/token": _FakeResponse(200, {"access_token": "tok-mgmt"}),
            "providers/Microsoft.ResourceHealth/availabilityStatuses": _FakeResponse(
                200, {"properties": {"availabilityState": "Available"}}
            ),
        }
        adapter = AzureAdapter(_credentials())

        result = await adapter.get_resource_health(
            resource_id="/subscriptions/sub-456/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1"
        )

        assert result["success"] is True
        assert result["data"]["properties"]["availabilityState"] == "Available"


class TestListSecurityFindings:
    @pytest.mark.asyncio
    async def test_list_security_findings_filters_by_severity(self):
        _FakeAsyncClient.responses = {
            "oauth2/v2.0/token": _FakeResponse(200, {"access_token": "tok-mgmt"}),
            "providers/Microsoft.Security/assessments": _FakeResponse(
                200,
                {
                    "value": [
                        {"properties": {"status": {"severity": "High"}}},
                        {"properties": {"status": {"severity": "Low"}}},
                    ]
                },
            ),
        }
        adapter = AzureAdapter(_credentials())

        result = await adapter.list_security_findings(severity="high")

        assert result["success"] is True
        assert len(result["data"]) == 1
        assert result["data"][0]["properties"]["status"]["severity"] == "High"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T api pytest tests/unit/services/cloud_providers/test_azure_adapter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.cloud_providers.azure_adapter'`

- [ ] **Step 3: Write the adapter implementation**

Create `api/src/services/cloud_providers/azure_adapter.py`:

```python
"""Azure cloud provider adapter: Monitor Logs/Metrics/Alerts, Resource Health, Defender for Cloud."""

from typing import Any

import httpx

from src.services.cloud_providers.base_adapter import CloudProviderAdapter

_MANAGEMENT_SCOPE = "https://management.azure.com/.default"
_LOG_ANALYTICS_SCOPE = "https://api.loganalytics.io/.default"
_API_VERSION = "2023-11-01"


class AzureAdapter(CloudProviderAdapter):
    def __init__(self, credentials: dict[str, Any]):
        super().__init__(credentials)
        config = credentials.get("config") or {}
        self.tenant_id = config.get("azure_tenant_id", "")
        self.subscription_id = config.get("subscription_id", "")
        self.client_id = credentials.get("client_id", "")
        self.client_secret = credentials.get("api_token", "")

    async def _get_access_token(self, scope: str) -> str:
        url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": scope,
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, data=data)
        if not resp.is_success:
            raise ValueError("Azure credentials are invalid or expired — please reconnect in Integrations.")
        return resp.json()["access_token"]

    async def _request(self, method: str, url: str, scope: str = _MANAGEMENT_SCOPE, **kwargs) -> httpx.Response:
        token = await self._get_access_token(scope)
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(timeout=30) as client:
            return await client.request(method, url, headers=headers, **kwargs)

    async def get_logs(
        self,
        log_source: str,
        start_time: str,
        end_time: str,
        filter_query: str = "",
        limit: int = 100,
    ) -> dict[str, Any]:
        try:
            query = filter_query or "union * | order by TimeGenerated desc"
            url = f"https://api.loganalytics.io/v1/workspaces/{log_source}/query"
            body = {"query": f"{query} | take {limit}", "timespan": f"{start_time}/{end_time}"}
            resp = await self._request("POST", url, scope=_LOG_ANALYTICS_SCOPE, json=body)
            if not resp.is_success:
                return self._fail(f"Azure Monitor Logs error ({resp.status_code}): {resp.text}")
            table = (resp.json().get("tables") or [{}])[0]
            columns = [c["name"] for c in table.get("columns", [])]
            rows = table.get("rows", [])
            entries = [dict(zip(columns, row, strict=False)) for row in rows]
            return self._ok(data=entries)
        except ValueError as e:
            return self._fail(str(e))
        except httpx.HTTPError as e:
            return self._fail(f"Azure Monitor Logs request failed: {e}")

    async def get_metrics(
        self,
        metric_name: str,
        start_time: str,
        end_time: str,
        resource_id: str = "",
        period_seconds: int = 300,
    ) -> dict[str, Any]:
        if not resource_id:
            return self._fail("resource_id is required for Azure Monitor Metrics (full ARM resource ID).")
        try:
            interval = f"PT{max(period_seconds // 60, 1)}M"
            url = (
                f"https://management.azure.com{resource_id}/providers/microsoft.insights/metrics"
                f"?api-version=2018-01-01&metricnames={metric_name}"
                f"&timespan={start_time}/{end_time}&interval={interval}"
            )
            resp = await self._request("GET", url)
            if not resp.is_success:
                return self._fail(f"Azure Monitor Metrics error ({resp.status_code}): {resp.text}")
            return self._ok(data=resp.json().get("value", []))
        except ValueError as e:
            return self._fail(str(e))
        except httpx.HTTPError as e:
            return self._fail(f"Azure Monitor Metrics request failed: {e}")

    async def list_alerts(self, active_only: bool = True) -> dict[str, Any]:
        try:
            url = (
                f"https://management.azure.com/subscriptions/{self.subscription_id}"
                f"/providers/Microsoft.AlertsManagement/alerts?api-version={_API_VERSION}"
            )
            resp = await self._request("GET", url)
            if not resp.is_success:
                return self._fail(f"Azure Monitor alerts error ({resp.status_code}): {resp.text}")
            alerts = resp.json().get("value", [])
            if active_only:
                alerts = [
                    a for a in alerts if a.get("properties", {}).get("essentials", {}).get("alertState") == "New"
                ]
            return self._ok(data=alerts)
        except ValueError as e:
            return self._fail(str(e))
        except httpx.HTTPError as e:
            return self._fail(f"Azure Monitor alerts request failed: {e}")

    async def get_resource_health(self, resource_id: str = "") -> dict[str, Any]:
        if not resource_id:
            return self._fail("resource_id is required for Azure Resource Health (full ARM resource ID).")
        try:
            url = (
                f"https://management.azure.com{resource_id}"
                f"/providers/Microsoft.ResourceHealth/availabilityStatuses/current?api-version=2022-10-01"
            )
            resp = await self._request("GET", url)
            if not resp.is_success:
                return self._fail(f"Azure Resource Health error ({resp.status_code}): {resp.text}")
            return self._ok(data=resp.json())
        except ValueError as e:
            return self._fail(str(e))
        except httpx.HTTPError as e:
            return self._fail(f"Azure Resource Health request failed: {e}")

    async def list_security_findings(self, severity: str = "") -> dict[str, Any]:
        try:
            url = (
                f"https://management.azure.com/subscriptions/{self.subscription_id}"
                f"/providers/Microsoft.Security/assessments?api-version=2020-01-01"
            )
            resp = await self._request("GET", url)
            if not resp.is_success:
                return self._fail(f"Defender for Cloud error ({resp.status_code}): {resp.text}")
            findings = resp.json().get("value", [])
            if severity:
                findings = [
                    f
                    for f in findings
                    if f.get("properties", {}).get("status", {}).get("severity", "").lower() == severity.lower()
                ]
            return self._ok(data=findings)
        except ValueError as e:
            return self._fail(str(e))
        except httpx.HTTPError as e:
            return self._fail(f"Defender for Cloud request failed: {e}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T api pytest tests/unit/services/cloud_providers/test_azure_adapter.py -v`
Expected: 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add api/src/services/cloud_providers/azure_adapter.py api/tests/unit/services/cloud_providers/test_azure_adapter.py
git commit -m "feat: add Azure cloud provider adapter (Monitor Logs/Metrics/Alerts, Resource Health, Defender)"
```

---

## Task 11: Azure tool functions

**Files:**
- Create: `api/src/services/agents/internal_tools/azure_tools.py`
- Test: `api/tests/unit/services/agents/internal_tools/test_azure_tools.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/unit/services/agents/internal_tools/test_azure_tools.py`:

```python
"""Tests for internal_azure_* tool functions."""

from unittest.mock import AsyncMock, patch

import pytest

from src.services.agents.internal_tools.azure_tools import (
    internal_azure_get_logs,
    internal_azure_get_metrics,
    internal_azure_get_resource_health,
    internal_azure_list_alerts,
    internal_azure_list_security_findings,
)


class _FakeRuntimeContext:
    agent_id = "agent-1"


@pytest.mark.asyncio
async def test_get_logs_no_runtime_context():
    result = await internal_azure_get_logs(
        runtime_context=None, log_source="ws-1", start_time="t0", end_time="t1"
    )
    assert result["success"] is False
    assert "runtime context" in result["error"]


@pytest.mark.asyncio
async def test_get_logs_delegates_to_adapter():
    with (
        patch(
            "src.services.agents.internal_tools.azure_tools.get_cloud_provider_config",
            new=AsyncMock(return_value={"client_id": "c", "api_token": "s", "config": {}}),
        ),
        patch("src.services.agents.internal_tools.azure_tools.AzureAdapter") as MockAdapter,
    ):
        MockAdapter.return_value.get_logs = AsyncMock(return_value={"success": True, "data": []})

        result = await internal_azure_get_logs(
            runtime_context=_FakeRuntimeContext(), log_source="ws-1", start_time="t0", end_time="t1"
        )

        assert result == {"success": True, "data": []}
        MockAdapter.return_value.get_logs.assert_called_once_with(
            log_source="ws-1", start_time="t0", end_time="t1", filter_query="", limit=100
        )


@pytest.mark.asyncio
async def test_get_metrics_delegates_to_adapter():
    with (
        patch(
            "src.services.agents.internal_tools.azure_tools.get_cloud_provider_config",
            new=AsyncMock(return_value={"client_id": "c", "api_token": "s", "config": {}}),
        ),
        patch("src.services.agents.internal_tools.azure_tools.AzureAdapter") as MockAdapter,
    ):
        MockAdapter.return_value.get_metrics = AsyncMock(return_value={"success": True, "data": []})

        result = await internal_azure_get_metrics(
            runtime_context=_FakeRuntimeContext(),
            metric_name="Percentage CPU",
            start_time="t0",
            end_time="t1",
            resource_id="/subscriptions/s/resourceGroups/r/providers/Microsoft.Compute/virtualMachines/vm1",
        )

        assert result["success"] is True
        MockAdapter.return_value.get_metrics.assert_called_once()


@pytest.mark.asyncio
async def test_list_alerts_delegates_to_adapter():
    with (
        patch(
            "src.services.agents.internal_tools.azure_tools.get_cloud_provider_config",
            new=AsyncMock(return_value={"client_id": "c", "api_token": "s", "config": {}}),
        ),
        patch("src.services.agents.internal_tools.azure_tools.AzureAdapter") as MockAdapter,
    ):
        MockAdapter.return_value.list_alerts = AsyncMock(return_value={"success": True, "data": []})

        result = await internal_azure_list_alerts(runtime_context=_FakeRuntimeContext())

        assert result["success"] is True
        MockAdapter.return_value.list_alerts.assert_called_once_with(active_only=True)


@pytest.mark.asyncio
async def test_get_resource_health_delegates_to_adapter():
    with (
        patch(
            "src.services.agents.internal_tools.azure_tools.get_cloud_provider_config",
            new=AsyncMock(return_value={"client_id": "c", "api_token": "s", "config": {}}),
        ),
        patch("src.services.agents.internal_tools.azure_tools.AzureAdapter") as MockAdapter,
    ):
        MockAdapter.return_value.get_resource_health = AsyncMock(return_value={"success": True, "data": {}})

        result = await internal_azure_get_resource_health(
            runtime_context=_FakeRuntimeContext(), resource_id="/subscriptions/s/resourceGroups/r/x"
        )

        assert result["success"] is True
        MockAdapter.return_value.get_resource_health.assert_called_once_with(
            resource_id="/subscriptions/s/resourceGroups/r/x"
        )


@pytest.mark.asyncio
async def test_list_security_findings_delegates_to_adapter():
    with (
        patch(
            "src.services.agents.internal_tools.azure_tools.get_cloud_provider_config",
            new=AsyncMock(return_value={"client_id": "c", "api_token": "s", "config": {}}),
        ),
        patch("src.services.agents.internal_tools.azure_tools.AzureAdapter") as MockAdapter,
    ):
        MockAdapter.return_value.list_security_findings = AsyncMock(return_value={"success": True, "data": []})

        result = await internal_azure_list_security_findings(runtime_context=_FakeRuntimeContext(), severity="high")

        assert result["success"] is True
        MockAdapter.return_value.list_security_findings.assert_called_once_with(severity="high")


@pytest.mark.asyncio
async def test_credential_error_returns_failure_dict():
    with patch(
        "src.services.agents.internal_tools.azure_tools.get_cloud_provider_config",
        new=AsyncMock(side_effect=ValueError("No OAuth app configured for tool 'internal_azure_get_logs'.")),
    ):
        result = await internal_azure_get_logs(
            runtime_context=_FakeRuntimeContext(), log_source="ws-1", start_time="t0", end_time="t1"
        )

        assert result["success"] is False
        assert "No OAuth app configured" in result["error"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T api pytest tests/unit/services/agents/internal_tools/test_azure_tools.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.agents.internal_tools.azure_tools'`

- [ ] **Step 3: Write the tool functions**

Create `api/src/services/agents/internal_tools/azure_tools.py`:

```python
"""LLM-facing internal_azure_* tool functions — thin wrappers around AzureAdapter."""

from typing import Any

from src.services.agents.internal_tools.cloud_shared import get_cloud_provider_config
from src.services.cloud_providers.azure_adapter import AzureAdapter


async def internal_azure_get_logs(
    runtime_context: Any,
    log_source: str,
    start_time: str,
    end_time: str,
    filter_query: str = "",
    limit: int = 100,
) -> dict[str, Any]:
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        config = await get_cloud_provider_config(runtime_context, "internal_azure_get_logs", "azure")
        adapter = AzureAdapter(config)
        return await adapter.get_logs(
            log_source=log_source, start_time=start_time, end_time=end_time, filter_query=filter_query, limit=limit
        )
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Azure Monitor Logs request failed: {e}"}


async def internal_azure_get_metrics(
    runtime_context: Any,
    metric_name: str,
    start_time: str,
    end_time: str,
    resource_id: str = "",
    period_seconds: int = 300,
) -> dict[str, Any]:
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        config = await get_cloud_provider_config(runtime_context, "internal_azure_get_metrics", "azure")
        adapter = AzureAdapter(config)
        return await adapter.get_metrics(
            metric_name=metric_name,
            start_time=start_time,
            end_time=end_time,
            resource_id=resource_id,
            period_seconds=period_seconds,
        )
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Azure Monitor Metrics request failed: {e}"}


async def internal_azure_list_alerts(runtime_context: Any, active_only: bool = True) -> dict[str, Any]:
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        config = await get_cloud_provider_config(runtime_context, "internal_azure_list_alerts", "azure")
        adapter = AzureAdapter(config)
        return await adapter.list_alerts(active_only=active_only)
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Azure Monitor alerts request failed: {e}"}


async def internal_azure_get_resource_health(runtime_context: Any, resource_id: str = "") -> dict[str, Any]:
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        config = await get_cloud_provider_config(runtime_context, "internal_azure_get_resource_health", "azure")
        adapter = AzureAdapter(config)
        return await adapter.get_resource_health(resource_id=resource_id)
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Azure Resource Health request failed: {e}"}


async def internal_azure_list_security_findings(runtime_context: Any, severity: str = "") -> dict[str, Any]:
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        config = await get_cloud_provider_config(
            runtime_context, "internal_azure_list_security_findings", "azure"
        )
        adapter = AzureAdapter(config)
        return await adapter.list_security_findings(severity=severity)
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Defender for Cloud request failed: {e}"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T api pytest tests/unit/services/agents/internal_tools/test_azure_tools.py -v`
Expected: 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add api/src/services/agents/internal_tools/azure_tools.py api/tests/unit/services/agents/internal_tools/test_azure_tools.py
git commit -m "feat: add internal_azure_* tool functions"
```

---

## Task 12: Azure tool registry + `adk_tools.py` wiring

**Files:**
- Create: `api/src/services/agents/tool_registrations/azure_tools_registry.py`
- Modify: `api/src/services/agents/adk_tools.py` (`_register_default_tools()`)
- Test: `api/tests/unit/services/agents/tool_registrations/test_azure_tools_registry.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/unit/services/agents/tool_registrations/test_azure_tools_registry.py`:

```python
"""Tests for register_azure_tools() ADK registry wiring."""

from unittest.mock import AsyncMock, patch

import pytest

from src.services.agents.adk_tools import ADKToolRegistry
from src.services.agents.tool_registrations.azure_tools_registry import register_azure_tools

_AZURE_TOOL_NAMES = [
    "internal_azure_get_logs",
    "internal_azure_get_metrics",
    "internal_azure_list_alerts",
    "internal_azure_get_resource_health",
    "internal_azure_list_security_findings",
]


def test_register_azure_tools_registers_all_five():
    registry = ADKToolRegistry.__new__(ADKToolRegistry)
    registry.tools = {}
    register_azure_tools(registry)

    for name in _AZURE_TOOL_NAMES:
        assert name in registry.tools
        assert registry.tools[name]["requires_auth"] == "azure"
        assert registry.tools[name]["tool_category"] == "read"


@pytest.mark.asyncio
async def test_get_logs_wrapper_forwards_runtime_context():
    registry = ADKToolRegistry.__new__(ADKToolRegistry)
    registry.tools = {}
    register_azure_tools(registry)
    wrapper = registry.tools["internal_azure_get_logs"]["function"]

    with patch(
        "src.services.agents.tool_registrations.azure_tools_registry.internal_azure_get_logs",
        new=AsyncMock(return_value={"success": True, "data": []}),
    ) as mock_fn:
        fake_context = object()
        result = await wrapper(
            config={"_runtime_context": fake_context},
            log_source="ws-1",
            start_time="t0",
            end_time="t1",
        )

        assert result == {"success": True, "data": []}
        mock_fn.assert_called_once_with(
            runtime_context=fake_context, log_source="ws-1", start_time="t0", end_time="t1", filter_query="", limit=100
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/unit/services/agents/tool_registrations/test_azure_tools_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.agents.tool_registrations.azure_tools_registry'`

- [ ] **Step 3: Write the registry file**

Create `api/src/services/agents/tool_registrations/azure_tools_registry.py`:

```python
"""Registers internal_azure_* tools with the ADK tool registry (Microsoft Azure)."""

from typing import Any

from src.services.agents.internal_tools.azure_tools import (
    internal_azure_get_logs,
    internal_azure_get_metrics,
    internal_azure_get_resource_health,
    internal_azure_list_alerts,
    internal_azure_list_security_findings,
)


def register_azure_tools(registry: Any) -> None:
    async def get_logs_wrapper(
        config: dict | None = None,
        log_source: str = "",
        start_time: str = "",
        end_time: str = "",
        filter_query: str = "",
        limit: int = 100,
        **kwargs,
    ) -> dict[str, Any]:
        runtime_context = (config or {}).get("_runtime_context")
        return await internal_azure_get_logs(
            runtime_context=runtime_context,
            log_source=log_source,
            start_time=start_time,
            end_time=end_time,
            filter_query=filter_query,
            limit=limit,
        )

    async def get_metrics_wrapper(
        config: dict | None = None,
        metric_name: str = "",
        start_time: str = "",
        end_time: str = "",
        resource_id: str = "",
        period_seconds: int = 300,
        **kwargs,
    ) -> dict[str, Any]:
        runtime_context = (config or {}).get("_runtime_context")
        return await internal_azure_get_metrics(
            runtime_context=runtime_context,
            metric_name=metric_name,
            start_time=start_time,
            end_time=end_time,
            resource_id=resource_id,
            period_seconds=period_seconds,
        )

    async def list_alerts_wrapper(config: dict | None = None, active_only: bool = True, **kwargs) -> dict[str, Any]:
        runtime_context = (config or {}).get("_runtime_context")
        return await internal_azure_list_alerts(runtime_context=runtime_context, active_only=active_only)

    async def get_resource_health_wrapper(
        config: dict | None = None, resource_id: str = "", **kwargs
    ) -> dict[str, Any]:
        runtime_context = (config or {}).get("_runtime_context")
        return await internal_azure_get_resource_health(runtime_context=runtime_context, resource_id=resource_id)

    async def list_security_findings_wrapper(
        config: dict | None = None, severity: str = "", **kwargs
    ) -> dict[str, Any]:
        runtime_context = (config or {}).get("_runtime_context")
        return await internal_azure_list_security_findings(runtime_context=runtime_context, severity=severity)

    registry.register_tool(
        name="internal_azure_get_logs",
        description=(
            "Query Azure Monitor Logs (Log Analytics) for a workspace. Use for investigating "
            "application/VM/AKS log entries during an incident. Keywords: Azure, Log Analytics, "
            "Azure Monitor Logs, KQL, workspace logs."
        ),
        parameters={
            "type": "object",
            "properties": {
                "log_source": {"type": "string", "description": "Log Analytics workspace ID."},
                "start_time": {"type": "string", "description": "ISO 8601 start of the time range."},
                "end_time": {"type": "string", "description": "ISO 8601 end of the time range."},
                "filter_query": {
                    "type": "string",
                    "description": "Optional KQL query body (defaults to a recent-events query).",
                },
                "limit": {"type": "integer", "description": "Max rows to return.", "default": 100},
            },
            "required": ["log_source", "start_time", "end_time"],
        },
        function=get_logs_wrapper,
        requires_auth="azure",
        tool_category="read",
    )

    registry.register_tool(
        name="internal_azure_get_metrics",
        description=(
            "Get Azure Monitor Metrics (e.g. Percentage CPU, Network In) for a specific ARM "
            "resource. Keywords: Azure Monitor Metrics, VM metrics, AKS metrics, resource metrics."
        ),
        parameters={
            "type": "object",
            "properties": {
                "metric_name": {"type": "string", "description": "Azure metric name, e.g. 'Percentage CPU'."},
                "start_time": {"type": "string", "description": "ISO 8601 start of the time range."},
                "end_time": {"type": "string", "description": "ISO 8601 end of the time range."},
                "resource_id": {
                    "type": "string",
                    "description": "Full ARM resource ID (required — no cross-resource shortcut exists).",
                },
                "period_seconds": {"type": "integer", "description": "Aggregation interval in seconds.", "default": 300},
            },
            "required": ["metric_name", "start_time", "end_time", "resource_id"],
        },
        function=get_metrics_wrapper,
        requires_auth="azure",
        tool_category="read",
    )

    registry.register_tool(
        name="internal_azure_list_alerts",
        description=(
            "List Azure Monitor alert rule firings for the subscription. Keywords: Azure alerts, "
            "alert rules, AlertsManagement."
        ),
        parameters={
            "type": "object",
            "properties": {
                "active_only": {"type": "boolean", "description": "Only return active (New) alerts.", "default": True},
            },
            "required": [],
        },
        function=list_alerts_wrapper,
        requires_auth="azure",
        tool_category="read",
    )

    registry.register_tool(
        name="internal_azure_get_resource_health",
        description=(
            "Get the current availability status of an Azure resource (VM, AKS, etc). Keywords: "
            "Azure Resource Health, VM health, AKS health, availability status."
        ),
        parameters={
            "type": "object",
            "properties": {
                "resource_id": {"type": "string", "description": "Full ARM resource ID (required)."},
            },
            "required": ["resource_id"],
        },
        function=get_resource_health_wrapper,
        requires_auth="azure",
        tool_category="read",
    )

    registry.register_tool(
        name="internal_azure_list_security_findings",
        description=(
            "List Microsoft Defender for Cloud security assessments for the subscription, "
            "optionally filtered by severity. Keywords: Defender for Cloud, security assessments, "
            "Azure security findings."
        ),
        parameters={
            "type": "object",
            "properties": {
                "severity": {"type": "string", "description": "Filter by severity, e.g. 'High'. Empty for all."},
            },
            "required": [],
        },
        function=list_security_findings_wrapper,
        requires_auth="azure",
        tool_category="read",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/unit/services/agents/tool_registrations/test_azure_tools_registry.py -v`
Expected: 2 tests PASS

- [ ] **Step 5: Wire into `_register_default_tools()`**

In `api/src/services/agents/adk_tools.py`, in `_register_default_tools()`, right after the GCP
registration block added in Task 9, add:

```python
        # Azure tools - use modular registry
        from src.services.agents.tool_registrations.azure_tools_registry import (
            register_azure_tools,
        )

        register_azure_tools(self)
```

- [ ] **Step 6: Verify the full tool registry loads without error**

Run: `docker compose exec -T api python -c "from src.services.agents.adk_tools import ADKToolRegistry; r = ADKToolRegistry(); print('internal_azure_get_logs' in r.tools)"`
Expected: prints `True`

- [ ] **Step 7: Commit**

```bash
git add api/src/services/agents/tool_registrations/azure_tools_registry.py api/tests/unit/services/agents/tool_registrations/test_azure_tools_registry.py api/src/services/agents/adk_tools.py
git commit -m "feat: register Azure tools with the ADK tool registry"
```

---

## Task 13: DigitalOcean adapter (`httpx` bearer PAT)

**Files:**
- Create: `api/src/services/cloud_providers/digitalocean_adapter.py`
- Test: `api/tests/unit/services/cloud_providers/test_digitalocean_adapter.py`

DigitalOcean credentials from `OAuthApp`: only `api_token` (decrypted) is used — a personal
access token. No `client_id`, no `config`. Per the capability matrix, DO has no log-query API and
no security-findings equivalent, so `get_logs`/`list_security_findings` return
`_fail("Not supported by DigitalOcean")` immediately without any network call.

- [ ] **Step 1: Write the failing test**

Create `api/tests/unit/services/cloud_providers/test_digitalocean_adapter.py`:

```python
"""Tests for DigitalOceanAdapter (Droplet metrics/alerts/health; logs & findings unsupported)."""

import pytest

from src.services.cloud_providers.digitalocean_adapter import DigitalOceanAdapter


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.is_success = 200 <= status_code < 300
        self.text = str(json_data)

    def json(self):
        return self._json_data


class _FakeAsyncClient:
    responses: dict[str, _FakeResponse] = {}

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def request(self, method, url, **kwargs):
        for substring, resp in type(self).responses.items():
            if substring in url:
                return resp
        raise AssertionError(f"No fake response configured for {method} {url}")


@pytest.fixture(autouse=True)
def _reset_fake_client(monkeypatch):
    import httpx

    _FakeAsyncClient.responses = {}
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    yield


def _credentials():
    return {"client_id": "", "api_token": "do-pat-token", "config": {}}


class TestUnsupportedCapabilities:
    @pytest.mark.asyncio
    async def test_get_logs_not_supported(self):
        adapter = DigitalOceanAdapter(_credentials())

        result = await adapter.get_logs(log_source="droplet-1", start_time="t0", end_time="t1")

        assert result == {"success": False, "data": None, "error": "Not supported by DigitalOcean"}

    @pytest.mark.asyncio
    async def test_list_security_findings_not_supported(self):
        adapter = DigitalOceanAdapter(_credentials())

        result = await adapter.list_security_findings()

        assert result == {"success": False, "data": None, "error": "Not supported by DigitalOcean"}


class TestGetMetrics:
    @pytest.mark.asyncio
    async def test_get_metrics_success(self):
        _FakeAsyncClient.responses = {
            "monitoring/metrics/droplet/cpu": _FakeResponse(
                200, {"data": {"result": [{"metric": {}, "values": [[1723766400, "12.5"]]}]}}
            ),
        }
        adapter = DigitalOceanAdapter(_credentials())

        result = await adapter.get_metrics(
            metric_name="cpu", start_time="1723766000", end_time="1723766400", resource_id="12345"
        )

        assert result["success"] is True
        assert result["data"][0]["values"][0][1] == "12.5"

    @pytest.mark.asyncio
    async def test_get_metrics_requires_resource_id(self):
        adapter = DigitalOceanAdapter(_credentials())

        result = await adapter.get_metrics(metric_name="cpu", start_time="t0", end_time="t1")

        assert result["success"] is False
        assert "resource_id" in result["error"]


class TestListAlerts:
    @pytest.mark.asyncio
    async def test_list_alerts_filters_enabled(self):
        _FakeAsyncClient.responses = {
            "monitoring/alerts": _FakeResponse(
                200,
                {
                    "policies": [
                        {"uuid": "p1", "enabled": True},
                        {"uuid": "p2", "enabled": False},
                    ]
                },
            ),
        }
        adapter = DigitalOceanAdapter(_credentials())

        result = await adapter.list_alerts(active_only=True)

        assert result["success"] is True
        assert len(result["data"]) == 1
        assert result["data"][0]["uuid"] == "p1"


class TestGetResourceHealth:
    @pytest.mark.asyncio
    async def test_get_resource_health_success(self):
        _FakeAsyncClient.responses = {
            "droplets/12345": _FakeResponse(200, {"droplet": {"id": 12345, "status": "active"}}),
        }
        adapter = DigitalOceanAdapter(_credentials())

        result = await adapter.get_resource_health(resource_id="12345")

        assert result["success"] is True
        assert result["data"]["status"] == "active"

    @pytest.mark.asyncio
    async def test_get_resource_health_requires_resource_id(self):
        adapter = DigitalOceanAdapter(_credentials())

        result = await adapter.get_resource_health(resource_id="")

        assert result["success"] is False
        assert "resource_id" in result["error"]

    @pytest.mark.asyncio
    async def test_get_resource_health_auth_failure(self):
        _FakeAsyncClient.responses = {
            "droplets/12345": _FakeResponse(401, {"message": "Unable to authenticate"}),
        }
        adapter = DigitalOceanAdapter(_credentials())

        result = await adapter.get_resource_health(resource_id="12345")

        assert result["success"] is False
        assert "invalid or expired" in result["error"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T api pytest tests/unit/services/cloud_providers/test_digitalocean_adapter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.cloud_providers.digitalocean_adapter'`

- [ ] **Step 3: Write the adapter implementation**

Create `api/src/services/cloud_providers/digitalocean_adapter.py`:

```python
"""DigitalOcean cloud provider adapter: Droplet metrics, monitoring alerts, resource health.

Logs and security findings have no DigitalOcean API equivalent (see capability matrix in
docs/superpowers/specs/2026-08-16-cloud-provider-integrations-design.md) — those two methods
return a clear "not supported" result instead of being omitted.
"""

from typing import Any

import httpx

from src.services.cloud_providers.base_adapter import CloudProviderAdapter

_BASE_URL = "https://api.digitalocean.com/v2"


class DigitalOceanAdapter(CloudProviderAdapter):
    def __init__(self, credentials: dict[str, Any]):
        super().__init__(credentials)
        self.token = credentials.get("api_token", "")

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self.token}"}
        async with httpx.AsyncClient(timeout=30) as client:
            return await client.request(method, f"{_BASE_URL}{path}", headers=headers, **kwargs)

    def _friendly_error(self, resp: httpx.Response) -> str:
        if resp.status_code in (401, 403):
            return "DigitalOcean token is invalid or expired — please reconnect in Integrations."
        return f"DigitalOcean error ({resp.status_code}): {resp.text}"

    async def get_logs(
        self,
        log_source: str,
        start_time: str,
        end_time: str,
        filter_query: str = "",
        limit: int = 100,
    ) -> dict[str, Any]:
        return self._fail("Not supported by DigitalOcean")

    async def get_metrics(
        self,
        metric_name: str,
        start_time: str,
        end_time: str,
        resource_id: str = "",
        period_seconds: int = 300,
    ) -> dict[str, Any]:
        if not resource_id:
            return self._fail("resource_id (droplet ID) is required for DigitalOcean metrics.")
        try:
            path = f"/monitoring/metrics/droplet/{metric_name}"
            params = {"host_id": resource_id, "start": start_time, "end": end_time}
            resp = await self._request("GET", path, params=params)
            if not resp.is_success:
                return self._fail(self._friendly_error(resp))
            return self._ok(data=resp.json().get("data", {}).get("result", []))
        except httpx.HTTPError as e:
            return self._fail(f"DigitalOcean metrics request failed: {e}")

    async def list_alerts(self, active_only: bool = True) -> dict[str, Any]:
        try:
            resp = await self._request("GET", "/monitoring/alerts")
            if not resp.is_success:
                return self._fail(self._friendly_error(resp))
            policies = resp.json().get("policies", [])
            if active_only:
                policies = [p for p in policies if p.get("enabled")]
            return self._ok(data=policies)
        except httpx.HTTPError as e:
            return self._fail(f"DigitalOcean alerts request failed: {e}")

    async def get_resource_health(self, resource_id: str = "") -> dict[str, Any]:
        if not resource_id:
            return self._fail("resource_id (droplet ID) is required for DigitalOcean resource health.")
        try:
            resp = await self._request("GET", f"/droplets/{resource_id}")
            if not resp.is_success:
                return self._fail(self._friendly_error(resp))
            return self._ok(data=resp.json().get("droplet", {}))
        except httpx.HTTPError as e:
            return self._fail(f"DigitalOcean droplet status request failed: {e}")

    async def list_security_findings(self, severity: str = "") -> dict[str, Any]:
        return self._fail("Not supported by DigitalOcean")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T api pytest tests/unit/services/cloud_providers/test_digitalocean_adapter.py -v`
Expected: 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add api/src/services/cloud_providers/digitalocean_adapter.py api/tests/unit/services/cloud_providers/test_digitalocean_adapter.py
git commit -m "feat: add DigitalOcean cloud provider adapter (Droplet metrics/alerts/health)"
```

---

## Task 14: DigitalOcean tool functions

**Files:**
- Create: `api/src/services/agents/internal_tools/digitalocean_tools.py`
- Test: `api/tests/unit/services/agents/internal_tools/test_digitalocean_tools.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/unit/services/agents/internal_tools/test_digitalocean_tools.py`:

```python
"""Tests for internal_digitalocean_* tool functions."""

from unittest.mock import AsyncMock, patch

import pytest

from src.services.agents.internal_tools.digitalocean_tools import (
    internal_digitalocean_get_logs,
    internal_digitalocean_get_metrics,
    internal_digitalocean_get_resource_health,
    internal_digitalocean_list_alerts,
    internal_digitalocean_list_security_findings,
)


class _FakeRuntimeContext:
    agent_id = "agent-1"


@pytest.mark.asyncio
async def test_get_metrics_no_runtime_context():
    result = await internal_digitalocean_get_metrics(
        runtime_context=None, metric_name="cpu", start_time="t0", end_time="t1", resource_id="123"
    )
    assert result["success"] is False
    assert "runtime context" in result["error"]


@pytest.mark.asyncio
async def test_get_metrics_delegates_to_adapter():
    with (
        patch(
            "src.services.agents.internal_tools.digitalocean_tools.get_cloud_provider_config",
            new=AsyncMock(return_value={"client_id": "", "api_token": "s", "config": {}}),
        ),
        patch("src.services.agents.internal_tools.digitalocean_tools.DigitalOceanAdapter") as MockAdapter,
    ):
        MockAdapter.return_value.get_metrics = AsyncMock(return_value={"success": True, "data": []})

        result = await internal_digitalocean_get_metrics(
            runtime_context=_FakeRuntimeContext(), metric_name="cpu", start_time="t0", end_time="t1", resource_id="123"
        )

        assert result["success"] is True
        MockAdapter.return_value.get_metrics.assert_called_once_with(
            metric_name="cpu", start_time="t0", end_time="t1", resource_id="123", period_seconds=300
        )


@pytest.mark.asyncio
async def test_list_alerts_delegates_to_adapter():
    with (
        patch(
            "src.services.agents.internal_tools.digitalocean_tools.get_cloud_provider_config",
            new=AsyncMock(return_value={"client_id": "", "api_token": "s", "config": {}}),
        ),
        patch("src.services.agents.internal_tools.digitalocean_tools.DigitalOceanAdapter") as MockAdapter,
    ):
        MockAdapter.return_value.list_alerts = AsyncMock(return_value={"success": True, "data": []})

        result = await internal_digitalocean_list_alerts(runtime_context=_FakeRuntimeContext())

        assert result["success"] is True
        MockAdapter.return_value.list_alerts.assert_called_once_with(active_only=True)


@pytest.mark.asyncio
async def test_get_resource_health_delegates_to_adapter():
    with (
        patch(
            "src.services.agents.internal_tools.digitalocean_tools.get_cloud_provider_config",
            new=AsyncMock(return_value={"client_id": "", "api_token": "s", "config": {}}),
        ),
        patch("src.services.agents.internal_tools.digitalocean_tools.DigitalOceanAdapter") as MockAdapter,
    ):
        MockAdapter.return_value.get_resource_health = AsyncMock(return_value={"success": True, "data": {}})

        result = await internal_digitalocean_get_resource_health(
            runtime_context=_FakeRuntimeContext(), resource_id="123"
        )

        assert result["success"] is True
        MockAdapter.return_value.get_resource_health.assert_called_once_with(resource_id="123")


@pytest.mark.asyncio
async def test_get_logs_returns_not_supported_without_credential_lookup():
    with patch(
        "src.services.agents.internal_tools.digitalocean_tools.get_cloud_provider_config",
        new=AsyncMock(return_value={"client_id": "", "api_token": "s", "config": {}}),
    ):
        result = await internal_digitalocean_get_logs(
            runtime_context=_FakeRuntimeContext(), log_source="d-1", start_time="t0", end_time="t1"
        )

        assert result == {"success": False, "data": None, "error": "Not supported by DigitalOcean"}


@pytest.mark.asyncio
async def test_list_security_findings_returns_not_supported():
    with patch(
        "src.services.agents.internal_tools.digitalocean_tools.get_cloud_provider_config",
        new=AsyncMock(return_value={"client_id": "", "api_token": "s", "config": {}}),
    ):
        result = await internal_digitalocean_list_security_findings(runtime_context=_FakeRuntimeContext())

        assert result == {"success": False, "data": None, "error": "Not supported by DigitalOcean"}


@pytest.mark.asyncio
async def test_credential_error_returns_failure_dict():
    with patch(
        "src.services.agents.internal_tools.digitalocean_tools.get_cloud_provider_config",
        new=AsyncMock(side_effect=ValueError("No OAuth app configured for tool 'internal_digitalocean_list_alerts'.")),
    ):
        result = await internal_digitalocean_list_alerts(runtime_context=_FakeRuntimeContext())

        assert result["success"] is False
        assert "No OAuth app configured" in result["error"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T api pytest tests/unit/services/agents/internal_tools/test_digitalocean_tools.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.agents.internal_tools.digitalocean_tools'`

- [ ] **Step 3: Write the tool functions**

Create `api/src/services/agents/internal_tools/digitalocean_tools.py`:

```python
"""LLM-facing internal_digitalocean_* tool functions — thin wrappers around DigitalOceanAdapter."""

from typing import Any

from src.services.agents.internal_tools.cloud_shared import get_cloud_provider_config
from src.services.cloud_providers.digitalocean_adapter import DigitalOceanAdapter


async def internal_digitalocean_get_logs(
    runtime_context: Any,
    log_source: str,
    start_time: str,
    end_time: str,
    filter_query: str = "",
    limit: int = 100,
) -> dict[str, Any]:
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        config = await get_cloud_provider_config(runtime_context, "internal_digitalocean_get_logs", "digitalocean")
        adapter = DigitalOceanAdapter(config)
        return await adapter.get_logs(
            log_source=log_source, start_time=start_time, end_time=end_time, filter_query=filter_query, limit=limit
        )
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"DigitalOcean request failed: {e}"}


async def internal_digitalocean_get_metrics(
    runtime_context: Any,
    metric_name: str,
    start_time: str,
    end_time: str,
    resource_id: str = "",
    period_seconds: int = 300,
) -> dict[str, Any]:
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        config = await get_cloud_provider_config(runtime_context, "internal_digitalocean_get_metrics", "digitalocean")
        adapter = DigitalOceanAdapter(config)
        return await adapter.get_metrics(
            metric_name=metric_name,
            start_time=start_time,
            end_time=end_time,
            resource_id=resource_id,
            period_seconds=period_seconds,
        )
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"DigitalOcean metrics request failed: {e}"}


async def internal_digitalocean_list_alerts(runtime_context: Any, active_only: bool = True) -> dict[str, Any]:
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        config = await get_cloud_provider_config(
            runtime_context, "internal_digitalocean_list_alerts", "digitalocean"
        )
        adapter = DigitalOceanAdapter(config)
        return await adapter.list_alerts(active_only=active_only)
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"DigitalOcean alerts request failed: {e}"}


async def internal_digitalocean_get_resource_health(runtime_context: Any, resource_id: str = "") -> dict[str, Any]:
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        config = await get_cloud_provider_config(
            runtime_context, "internal_digitalocean_get_resource_health", "digitalocean"
        )
        adapter = DigitalOceanAdapter(config)
        return await adapter.get_resource_health(resource_id=resource_id)
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"DigitalOcean droplet status request failed: {e}"}


async def internal_digitalocean_list_security_findings(runtime_context: Any, severity: str = "") -> dict[str, Any]:
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        config = await get_cloud_provider_config(
            runtime_context, "internal_digitalocean_list_security_findings", "digitalocean"
        )
        adapter = DigitalOceanAdapter(config)
        return await adapter.list_security_findings(severity=severity)
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"DigitalOcean request failed: {e}"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T api pytest tests/unit/services/agents/internal_tools/test_digitalocean_tools.py -v`
Expected: 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add api/src/services/agents/internal_tools/digitalocean_tools.py api/tests/unit/services/agents/internal_tools/test_digitalocean_tools.py
git commit -m "feat: add internal_digitalocean_* tool functions"
```

---

## Task 15: DigitalOcean tool registry + `adk_tools.py` wiring

**Files:**
- Create: `api/src/services/agents/tool_registrations/digitalocean_tools_registry.py`
- Modify: `api/src/services/agents/adk_tools.py` (`_register_default_tools()`)
- Test: `api/tests/unit/services/agents/tool_registrations/test_digitalocean_tools_registry.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/unit/services/agents/tool_registrations/test_digitalocean_tools_registry.py`:

```python
"""Tests for register_digitalocean_tools() ADK registry wiring."""

from unittest.mock import AsyncMock, patch

import pytest

from src.services.agents.adk_tools import ADKToolRegistry
from src.services.agents.tool_registrations.digitalocean_tools_registry import register_digitalocean_tools

_DO_TOOL_NAMES = [
    "internal_digitalocean_get_logs",
    "internal_digitalocean_get_metrics",
    "internal_digitalocean_list_alerts",
    "internal_digitalocean_get_resource_health",
    "internal_digitalocean_list_security_findings",
]


def test_register_digitalocean_tools_registers_all_five():
    registry = ADKToolRegistry.__new__(ADKToolRegistry)
    registry.tools = {}
    register_digitalocean_tools(registry)

    for name in _DO_TOOL_NAMES:
        assert name in registry.tools
        assert registry.tools[name]["requires_auth"] == "digitalocean"
        assert registry.tools[name]["tool_category"] == "read"


@pytest.mark.asyncio
async def test_get_metrics_wrapper_forwards_runtime_context():
    registry = ADKToolRegistry.__new__(ADKToolRegistry)
    registry.tools = {}
    register_digitalocean_tools(registry)
    wrapper = registry.tools["internal_digitalocean_get_metrics"]["function"]

    with patch(
        "src.services.agents.tool_registrations.digitalocean_tools_registry.internal_digitalocean_get_metrics",
        new=AsyncMock(return_value={"success": True, "data": []}),
    ) as mock_fn:
        fake_context = object()
        result = await wrapper(
            config={"_runtime_context": fake_context},
            metric_name="cpu",
            start_time="t0",
            end_time="t1",
            resource_id="123",
        )

        assert result == {"success": True, "data": []}
        mock_fn.assert_called_once_with(
            runtime_context=fake_context,
            metric_name="cpu",
            start_time="t0",
            end_time="t1",
            resource_id="123",
            period_seconds=300,
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/unit/services/agents/tool_registrations/test_digitalocean_tools_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.agents.tool_registrations.digitalocean_tools_registry'`

- [ ] **Step 3: Write the registry file**

Create `api/src/services/agents/tool_registrations/digitalocean_tools_registry.py`:

```python
"""Registers internal_digitalocean_* tools with the ADK tool registry."""

from typing import Any

from src.services.agents.internal_tools.digitalocean_tools import (
    internal_digitalocean_get_logs,
    internal_digitalocean_get_metrics,
    internal_digitalocean_get_resource_health,
    internal_digitalocean_list_alerts,
    internal_digitalocean_list_security_findings,
)


def register_digitalocean_tools(registry: Any) -> None:
    async def get_logs_wrapper(
        config: dict | None = None,
        log_source: str = "",
        start_time: str = "",
        end_time: str = "",
        filter_query: str = "",
        limit: int = 100,
        **kwargs,
    ) -> dict[str, Any]:
        runtime_context = (config or {}).get("_runtime_context")
        return await internal_digitalocean_get_logs(
            runtime_context=runtime_context,
            log_source=log_source,
            start_time=start_time,
            end_time=end_time,
            filter_query=filter_query,
            limit=limit,
        )

    async def get_metrics_wrapper(
        config: dict | None = None,
        metric_name: str = "",
        start_time: str = "",
        end_time: str = "",
        resource_id: str = "",
        period_seconds: int = 300,
        **kwargs,
    ) -> dict[str, Any]:
        runtime_context = (config or {}).get("_runtime_context")
        return await internal_digitalocean_get_metrics(
            runtime_context=runtime_context,
            metric_name=metric_name,
            start_time=start_time,
            end_time=end_time,
            resource_id=resource_id,
            period_seconds=period_seconds,
        )

    async def list_alerts_wrapper(config: dict | None = None, active_only: bool = True, **kwargs) -> dict[str, Any]:
        runtime_context = (config or {}).get("_runtime_context")
        return await internal_digitalocean_list_alerts(runtime_context=runtime_context, active_only=active_only)

    async def get_resource_health_wrapper(
        config: dict | None = None, resource_id: str = "", **kwargs
    ) -> dict[str, Any]:
        runtime_context = (config or {}).get("_runtime_context")
        return await internal_digitalocean_get_resource_health(runtime_context=runtime_context, resource_id=resource_id)

    async def list_security_findings_wrapper(
        config: dict | None = None, severity: str = "", **kwargs
    ) -> dict[str, Any]:
        runtime_context = (config or {}).get("_runtime_context")
        return await internal_digitalocean_list_security_findings(runtime_context=runtime_context, severity=severity)

    registry.register_tool(
        name="internal_digitalocean_get_logs",
        description=(
            "Not supported by DigitalOcean — DO has no log-query API. Calling this always returns "
            "a 'Not supported by DigitalOcean' error so the agent gets an explicit answer instead "
            "of guessing. Keywords: DigitalOcean logs, droplet logs."
        ),
        parameters={
            "type": "object",
            "properties": {
                "log_source": {"type": "string", "description": "Unused — DO has no log-query API."},
                "start_time": {"type": "string", "description": "Unused."},
                "end_time": {"type": "string", "description": "Unused."},
                "filter_query": {"type": "string", "description": "Unused."},
                "limit": {"type": "integer", "description": "Unused.", "default": 100},
            },
            "required": ["log_source", "start_time", "end_time"],
        },
        function=get_logs_wrapper,
        requires_auth="digitalocean",
        tool_category="read",
    )

    registry.register_tool(
        name="internal_digitalocean_get_metrics",
        description=(
            "Get DigitalOcean Droplet monitoring metrics (e.g. cpu, memory, disk) for a specific "
            "droplet. Keywords: DigitalOcean metrics, droplet CPU, droplet memory, DO monitoring."
        ),
        parameters={
            "type": "object",
            "properties": {
                "metric_name": {"type": "string", "description": "Metric name, e.g. 'cpu', 'memory', 'disk'."},
                "start_time": {"type": "string", "description": "Unix timestamp (seconds) for range start."},
                "end_time": {"type": "string", "description": "Unix timestamp (seconds) for range end."},
                "resource_id": {"type": "string", "description": "Droplet ID (required)."},
                "period_seconds": {"type": "integer", "description": "Unused for DO metrics.", "default": 300},
            },
            "required": ["metric_name", "start_time", "end_time", "resource_id"],
        },
        function=get_metrics_wrapper,
        requires_auth="digitalocean",
        tool_category="read",
    )

    registry.register_tool(
        name="internal_digitalocean_list_alerts",
        description=(
            "List DigitalOcean monitoring alert policies. Keywords: DigitalOcean alerts, monitoring "
            "alert policies, DO alerts."
        ),
        parameters={
            "type": "object",
            "properties": {
                "active_only": {"type": "boolean", "description": "Only return enabled alert policies.", "default": True},
            },
            "required": [],
        },
        function=list_alerts_wrapper,
        requires_auth="digitalocean",
        tool_category="read",
    )

    registry.register_tool(
        name="internal_digitalocean_get_resource_health",
        description=(
            "Get the current status of a DigitalOcean Droplet (e.g. active, off, archive). "
            "Keywords: DigitalOcean droplet status, droplet health."
        ),
        parameters={
            "type": "object",
            "properties": {
                "resource_id": {"type": "string", "description": "Droplet ID (required)."},
            },
            "required": ["resource_id"],
        },
        function=get_resource_health_wrapper,
        requires_auth="digitalocean",
        tool_category="read",
    )

    registry.register_tool(
        name="internal_digitalocean_list_security_findings",
        description=(
            "Not supported by DigitalOcean — DO has no security-findings API equivalent. Calling "
            "this always returns a 'Not supported by DigitalOcean' error. Keywords: DigitalOcean "
            "security findings."
        ),
        parameters={
            "type": "object",
            "properties": {
                "severity": {"type": "string", "description": "Unused — not supported by DigitalOcean."},
            },
            "required": [],
        },
        function=list_security_findings_wrapper,
        requires_auth="digitalocean",
        tool_category="read",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/unit/services/agents/tool_registrations/test_digitalocean_tools_registry.py -v`
Expected: 2 tests PASS

- [ ] **Step 5: Wire into `_register_default_tools()`**

In `api/src/services/agents/adk_tools.py`, in `_register_default_tools()`, right after the Azure
registration block added in Task 12, add:

```python
        # DigitalOcean tools - use modular registry
        from src.services.agents.tool_registrations.digitalocean_tools_registry import (
            register_digitalocean_tools,
        )

        register_digitalocean_tools(self)
```

- [ ] **Step 6: Verify the full tool registry loads without error**

Run: `docker compose exec -T api python -c "from src.services.agents.adk_tools import ADKToolRegistry; r = ADKToolRegistry(); print(sum(1 for n in r.tools if n.startswith(('internal_aws_', 'internal_gcp_', 'internal_azure_', 'internal_digitalocean_'))))"`
Expected: prints `20`

- [ ] **Step 7: Commit**

```bash
git add api/src/services/agents/tool_registrations/digitalocean_tools_registry.py api/tests/unit/services/agents/tool_registrations/test_digitalocean_tools_registry.py api/src/services/agents/adk_tools.py
git commit -m "feat: register DigitalOcean tools with the ADK tool registry"
```

---

## Task 16: Cloud credential validate-on-save functions

**Files:**
- Create: `api/src/services/cloud_providers/credential_validators.py`
- Test: `api/tests/unit/services/cloud_providers/test_credential_validators.py`

One async function per provider, each making a real, minimal, read-only API call to confirm the
credential works, raising `ValueError` with a user-actionable message on failure. These are called
from `apps.py` in Task 17 — kept in a separate module (not inline in the controller) so they can be
unit-tested without spinning up FastAPI.

- [ ] **Step 1: Write the failing test**

Create `api/tests/unit/services/cloud_providers/test_credential_validators.py`:

```python
"""Tests for cloud provider validate-on-save credential checks."""

import json

import pytest

from src.services.cloud_providers.credential_validators import (
    validate_aws_credentials,
    validate_azure_credentials,
    validate_digitalocean_credentials,
    validate_gcp_credentials,
)


class TestValidateAWSCredentials:
    @pytest.mark.asyncio
    async def test_success(self, monkeypatch):
        class _FakeSTS:
            def get_caller_identity(self):
                return {"Account": "123456789012", "Arn": "arn:aws:iam::123456789012:user/test"}

        class _FakeSession:
            def __init__(self, **kwargs):
                pass

            def client(self, service_name):
                assert service_name == "sts"
                return _FakeSTS()

        import boto3

        monkeypatch.setattr(boto3, "Session", _FakeSession)

        await validate_aws_credentials(access_key_id="AKIA...", secret_access_key="secret", region="us-east-1")

    @pytest.mark.asyncio
    async def test_failure_raises_value_error(self, monkeypatch):
        from botocore.exceptions import ClientError

        class _FakeSTS:
            def get_caller_identity(self):
                raise ClientError(
                    {"Error": {"Code": "InvalidClientTokenId", "Message": "invalid"}}, "GetCallerIdentity"
                )

        class _FakeSession:
            def __init__(self, **kwargs):
                pass

            def client(self, service_name):
                return _FakeSTS()

        import boto3

        monkeypatch.setattr(boto3, "Session", _FakeSession)

        with pytest.raises(ValueError, match="AWS credentials"):
            await validate_aws_credentials(access_key_id="bad", secret_access_key="bad", region="us-east-1")


class TestValidateGCPCredentials:
    @pytest.mark.asyncio
    async def test_success(self, monkeypatch):
        import httpx

        from src.services.cloud_providers import credential_validators

        async def _fake_get_token(service_account, scope):
            return "fake-token"

        class _FakeResponse:
            status_code = 200
            is_success = True
            text = "{}"

            def json(self):
                return {"projectId": "my-project"}

        class _FakeAsyncClient:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, url, **kwargs):
                return _FakeResponse()

        monkeypatch.setattr(credential_validators, "_get_gcp_access_token", _fake_get_token)
        monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

        sa_json = json.dumps({"client_email": "sa@my-project.iam.gserviceaccount.com", "private_key": "key"})
        await validate_gcp_credentials(service_account_json=sa_json, project_id="my-project")

    @pytest.mark.asyncio
    async def test_invalid_json_raises_value_error(self):
        with pytest.raises(ValueError, match="valid JSON"):
            await validate_gcp_credentials(service_account_json="not json", project_id="my-project")

    @pytest.mark.asyncio
    async def test_project_lookup_failure_raises_value_error(self, monkeypatch):
        import httpx

        from src.services.cloud_providers import credential_validators

        async def _fake_get_token(service_account, scope):
            return "fake-token"

        class _FakeResponse:
            status_code = 403
            is_success = False
            text = "permission denied"

            def json(self):
                return {}

        class _FakeAsyncClient:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, url, **kwargs):
                return _FakeResponse()

        monkeypatch.setattr(credential_validators, "_get_gcp_access_token", _fake_get_token)
        monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

        sa_json = json.dumps({"client_email": "sa@my-project.iam.gserviceaccount.com", "private_key": "key"})
        with pytest.raises(ValueError, match="GCP credentials"):
            await validate_gcp_credentials(service_account_json=sa_json, project_id="my-project")


class TestValidateAzureCredentials:
    @pytest.mark.asyncio
    async def test_success(self, monkeypatch):
        import httpx

        class _FakeResponse:
            is_success = True
            status_code = 200
            text = "{}"

            def json(self):
                return {"access_token": "tok"}

        class _FakeAsyncClient:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, url, **kwargs):
                return _FakeResponse()

        monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

        await validate_azure_credentials(
            tenant_id="tenant-1", client_id="app-1", client_secret="secret-1", subscription_id="sub-1"
        )

    @pytest.mark.asyncio
    async def test_failure_raises_value_error(self, monkeypatch):
        import httpx

        class _FakeResponse:
            is_success = False
            status_code = 401
            text = "invalid_client"

            def json(self):
                return {}

        class _FakeAsyncClient:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, url, **kwargs):
                return _FakeResponse()

        monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

        with pytest.raises(ValueError, match="Azure credentials"):
            await validate_azure_credentials(
                tenant_id="tenant-1", client_id="bad", client_secret="bad", subscription_id="sub-1"
            )


class TestValidateDigitalOceanCredentials:
    @pytest.mark.asyncio
    async def test_success(self, monkeypatch):
        import httpx

        class _FakeResponse:
            is_success = True
            status_code = 200
            text = "{}"

            def json(self):
                return {"account": {"status": "active"}}

        class _FakeAsyncClient:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, url, **kwargs):
                return _FakeResponse()

        monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

        await validate_digitalocean_credentials(token="do-pat")

    @pytest.mark.asyncio
    async def test_failure_raises_value_error(self, monkeypatch):
        import httpx

        class _FakeResponse:
            is_success = False
            status_code = 401
            text = "Unable to authenticate"

            def json(self):
                return {}

        class _FakeAsyncClient:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, url, **kwargs):
                return _FakeResponse()

        monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

        with pytest.raises(ValueError, match="DigitalOcean"):
            await validate_digitalocean_credentials(token="bad-token")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T api pytest tests/unit/services/cloud_providers/test_credential_validators.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.cloud_providers.credential_validators'`

- [ ] **Step 3: Write the validators module**

Create `api/src/services/cloud_providers/credential_validators.py`:

```python
"""Live, read-only validate-on-save checks for the 4 cloud provider integrations.

Called from controllers/oauth/apps.py at create/update time so an invalid credential is
rejected immediately with HTTPException(400, ...) instead of being stored silently broken.
Each function raises ValueError with a user-actionable message on failure.
"""

import asyncio
import json
import time
from typing import Any

import httpx
import jwt as pyjwt

_GCP_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GCP_SCOPE = "https://www.googleapis.com/auth/cloud-platform.read-only"


async def validate_aws_credentials(access_key_id: str, secret_access_key: str, region: str = "us-east-1") -> None:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

    def _check() -> None:
        session = boto3.Session(
            aws_access_key_id=access_key_id, aws_secret_access_key=secret_access_key, region_name=region
        )
        client = session.client("sts")
        client.get_caller_identity()

    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, _check)
    except (ClientError, NoCredentialsError, BotoCoreError) as e:
        raise ValueError(
            "AWS credentials are invalid or expired — please check the access key ID and secret access key."
        ) from e


async def _get_gcp_access_token(service_account: dict[str, Any], scope: str) -> str:
    now = int(time.time())
    claims = {
        "iss": service_account["client_email"],
        "scope": scope,
        "aud": _GCP_TOKEN_URL,
        "iat": now,
        "exp": now + 3600,
    }
    signed = pyjwt.encode(claims, service_account["private_key"], algorithm="RS256")
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            _GCP_TOKEN_URL,
            data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": signed},
        )
    if not resp.is_success:
        raise ValueError("GCP credentials are invalid or expired — please check the service account key.")
    return resp.json()["access_token"]


async def validate_gcp_credentials(service_account_json: str, project_id: str) -> None:
    try:
        service_account = json.loads(service_account_json)
    except (json.JSONDecodeError, TypeError) as e:
        raise ValueError("GCP service account key must be valid JSON.") from e

    token = await _get_gcp_access_token(service_account, _GCP_SCOPE)
    url = f"https://cloudresourcemanager.googleapis.com/v1/projects/{project_id}"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})
    if not resp.is_success:
        raise ValueError(
            f"GCP credentials could not access project '{project_id}' "
            f"(status {resp.status_code}) — check the service account's permissions and project_id."
        )


async def validate_azure_credentials(tenant_id: str, client_id: str, client_secret: str, subscription_id: str) -> None:
    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://management.azure.com/.default",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, data=data)
    if not resp.is_success:
        raise ValueError(
            "Azure credentials are invalid or expired — please check the tenant ID, client ID, and client secret."
        )


async def validate_digitalocean_credentials(token: str) -> None:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get("https://api.digitalocean.com/v2/account", headers={"Authorization": f"Bearer {token}"})
    if not resp.is_success:
        raise ValueError("DigitalOcean token is invalid or expired — please check the personal access token.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T api pytest tests/unit/services/cloud_providers/test_credential_validators.py -v`
Expected: 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add api/src/services/cloud_providers/credential_validators.py api/tests/unit/services/cloud_providers/test_credential_validators.py
git commit -m "feat: add live validate-on-save credential checks for cloud providers"
```

---

## Task 17: Wire cloud validators into `apps.py` create/update

**Files:**
- Modify: `api/src/controllers/oauth/apps.py`
- Test: `api/tests/unit/controllers/oauth/test_apps_cloud_validation.py`

Validation only runs when the relevant provider + `auth_method == "api_token"` fields are actually
being set (mirrors the existing `_validate_mailisk_config` early-return pattern) — so editing an
unrelated field on an existing cloud OAuth app doesn't force re-validation of unchanged secrets.

- [ ] **Step 1: Write the failing test**

Create `api/tests/unit/controllers/oauth/test_apps_cloud_validation.py` (create parent dirs if
absent — check with `ls api/tests/unit/controllers/oauth/` first; if missing, no `__init__.py` is
needed, matching the existing `tests/unit/services/agents/` convention):

```python
"""Tests for _validate_cloud_provider_config() live validate-on-save dispatch."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from src.controllers.oauth.apps import _validate_cloud_provider_config


class TestValidateCloudProviderConfig:
    @pytest.mark.asyncio
    async def test_non_cloud_provider_skips_validation(self):
        # Should return immediately without attempting any network call.
        await _validate_cloud_provider_config("github", "oauth", None, None, {})

    @pytest.mark.asyncio
    async def test_aws_success_calls_validator(self):
        with patch(
            "src.controllers.oauth.apps.validate_aws_credentials", new=AsyncMock(return_value=None)
        ) as mock_validate:
            await _validate_cloud_provider_config("aws", "api_token", "AKIA...", "secret", {"region": "us-west-2"})

            mock_validate.assert_called_once_with(access_key_id="AKIA...", secret_access_key="secret", region="us-west-2")

    @pytest.mark.asyncio
    async def test_aws_failure_raises_http_exception(self):
        with patch(
            "src.controllers.oauth.apps.validate_aws_credentials",
            new=AsyncMock(side_effect=ValueError("AWS credentials are invalid or expired.")),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await _validate_cloud_provider_config("aws", "api_token", "bad", "bad", {})

            assert exc_info.value.status_code == 400
            assert "AWS credentials" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_gcp_success_calls_validator(self):
        with patch(
            "src.controllers.oauth.apps.validate_gcp_credentials", new=AsyncMock(return_value=None)
        ) as mock_validate:
            await _validate_cloud_provider_config("gcp", "api_token", None, "{}", {"project_id": "proj-1"})

            mock_validate.assert_called_once_with(service_account_json="{}", project_id="proj-1")

    @pytest.mark.asyncio
    async def test_azure_success_calls_validator(self):
        with patch(
            "src.controllers.oauth.apps.validate_azure_credentials", new=AsyncMock(return_value=None)
        ) as mock_validate:
            await _validate_cloud_provider_config(
                "azure",
                "api_token",
                "app-1",
                "secret-1",
                {"azure_tenant_id": "tenant-1", "subscription_id": "sub-1"},
            )

            mock_validate.assert_called_once_with(
                tenant_id="tenant-1", client_id="app-1", client_secret="secret-1", subscription_id="sub-1"
            )

    @pytest.mark.asyncio
    async def test_digitalocean_success_calls_validator(self):
        with patch(
            "src.controllers.oauth.apps.validate_digitalocean_credentials", new=AsyncMock(return_value=None)
        ) as mock_validate:
            await _validate_cloud_provider_config("digitalocean", "api_token", None, "do-pat", {})

            mock_validate.assert_called_once_with(token="do-pat")

    @pytest.mark.asyncio
    async def test_wrong_auth_method_skips_validation(self):
        # A cloud provider row saved with a non-api_token auth_method (shouldn't normally
        # happen, but must not crash) skips the live check rather than erroring.
        await _validate_cloud_provider_config("aws", "oauth", "id", "secret", {})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T api pytest tests/unit/controllers/oauth/test_apps_cloud_validation.py -v`
Expected: FAIL with `ImportError: cannot import name '_validate_cloud_provider_config'`

- [ ] **Step 3: Add the dispatcher + wire it into create/update**

In `api/src/controllers/oauth/apps.py`, add the import (near the top, with the other
`services.cloud_providers` style imports) and the dispatcher function right after
`_validate_mailisk_config`:

```python
from ...services.cloud_providers.credential_validators import (
    validate_aws_credentials,
    validate_azure_credentials,
    validate_digitalocean_credentials,
    validate_gcp_credentials,
)
```

```python
async def _validate_cloud_provider_config(
    provider: str, auth_method: str, client_id: str | None, api_token: str | None, config: dict | None
) -> None:
    """Live, read-only validate-on-save check for the 4 cloud provider integrations.

    Only runs when auth_method is 'api_token' and the provider matches one of the 4 supported
    cloud providers — no-op for every other provider/auth_method combination.
    """
    provider_lower = str(provider).lower()
    if auth_method != "api_token" or provider_lower not in ("aws", "gcp", "azure", "digitalocean"):
        return

    config = config or {}
    try:
        if provider_lower == "aws":
            if not client_id or not api_token:
                return
            await validate_aws_credentials(
                access_key_id=client_id, secret_access_key=api_token, region=config.get("region", "us-east-1")
            )
        elif provider_lower == "gcp":
            if not api_token:
                return
            await validate_gcp_credentials(service_account_json=api_token, project_id=config.get("project_id", ""))
        elif provider_lower == "azure":
            if not client_id or not api_token:
                return
            await validate_azure_credentials(
                tenant_id=config.get("azure_tenant_id", ""),
                client_id=client_id,
                client_secret=api_token,
                subscription_id=config.get("subscription_id", ""),
            )
        elif provider_lower == "digitalocean":
            if not api_token:
                return
            await validate_digitalocean_credentials(token=api_token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
```

In `create_oauth_app`, right after the existing `_validate_mailisk_config(data.provider, ...)` call
(around line 210), add:

```python
        await _validate_cloud_provider_config(data.provider, data.auth_method, data.client_id, data.api_token, data.config)
```

In `update_oauth_app`, right after the existing `_validate_mailisk_config(app.provider, ...)` call
(around line 309-313), add:

```python
        await _validate_cloud_provider_config(
            app.provider,
            data.auth_method or app.auth_method,
            data.client_id if data.client_id is not None else app.client_id,
            data.api_token,
            data.config if data.config is not None else app.config,
        )
```

Note `update_oauth_app` intentionally only validates when `data.api_token` (the new plaintext
value) is provided — an existing encrypted `app.api_token` can't be decrypted here without adding
an unnecessary decrypt-then-revalidate round trip for a field that didn't change; skipping when
`data.api_token is None` matches the same "only validate what's actually being set" behavior as
`_validate_mailisk_config`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T api pytest tests/unit/controllers/oauth/test_apps_cloud_validation.py -v`
Expected: 7 tests PASS

- [ ] **Step 5: Run the full existing oauth apps test suite to check for regressions**

Run: `docker compose exec -T api pytest tests/unit/controllers/oauth/ -v`
Expected: all PASS (no existing test exercises a cloud provider, so none should be affected)

- [ ] **Step 6: Commit**

```bash
git add api/src/controllers/oauth/apps.py api/tests/unit/controllers/oauth/test_apps_cloud_validation.py
git commit -m "feat: validate cloud provider credentials on OAuth app create/update"
```

---

## Task 18: Least-privilege policy docs (write these before the frontend, since `setupGuide` links to them)

**Files:**
- Create: `docs/integrations/aws-readonly-policy.json`
- Create: `docs/integrations/gcp-readonly-roles.md`
- Create: `docs/integrations/azure-readonly-roles.md`
- Create: `docs/integrations/digitalocean-readonly-token.md`

No tests — these are static reference docs linked from the frontend's `setupGuide` field, not
executable code.

- [ ] **Step 1: Create the AWS least-privilege IAM policy**

Create `docs/integrations/aws-readonly-policy.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SynkoraCloudWatchReadOnly",
      "Effect": "Allow",
      "Action": [
        "cloudwatch:Get*",
        "cloudwatch:List*",
        "cloudwatch:Describe*"
      ],
      "Resource": "*"
    },
    {
      "Sid": "SynkoraCloudWatchLogsReadOnly",
      "Effect": "Allow",
      "Action": [
        "logs:Get*",
        "logs:List*",
        "logs:Describe*",
        "logs:FilterLogEvents",
        "logs:StartQuery",
        "logs:StopQuery"
      ],
      "Resource": "*"
    },
    {
      "Sid": "SynkoraEC2ReadOnly",
      "Effect": "Allow",
      "Action": [
        "ec2:Describe*"
      ],
      "Resource": "*"
    },
    {
      "Sid": "SynkoraRDSReadOnly",
      "Effect": "Allow",
      "Action": [
        "rds:Describe*",
        "rds:ListTagsForResource"
      ],
      "Resource": "*"
    },
    {
      "Sid": "SynkoraLambdaReadOnly",
      "Effect": "Allow",
      "Action": [
        "lambda:GetFunction",
        "lambda:GetFunctionConfiguration",
        "lambda:ListFunctions"
      ],
      "Resource": "*"
    },
    {
      "Sid": "SynkoraSecurityHubReadOnly",
      "Effect": "Allow",
      "Action": [
        "securityhub:Get*",
        "securityhub:List*",
        "securityhub:Describe*"
      ],
      "Resource": "*"
    },
    {
      "Sid": "SynkoraGuardDutyReadOnly",
      "Effect": "Allow",
      "Action": [
        "guardduty:List*",
        "guardduty:Get*"
      ],
      "Resource": "*"
    }
  ]
}
```

- [ ] **Step 2: Create the GCP least-privilege roles doc**

Create `docs/integrations/gcp-readonly-roles.md`:

```markdown
# GCP Least-Privilege Setup for Synkora

Create a dedicated service account and grant it these **predefined, read-only** IAM roles at the
project level (no custom role needed):

| Role | Purpose |
|---|---|
| `roles/logging.viewer` | Cloud Logging — read log entries |
| `roles/monitoring.viewer` | Cloud Monitoring — read metrics, alert policies, incidents |
| `roles/compute.viewer` | Compute Engine — read instance/GKE resource status |
| `roles/securitycenter.findingsViewer` | Security Command Center — read findings |
| `roles/resourcemanager.projectIamAdmin` is **not** needed — only used at setup time to grant the
  service account these roles, then can be removed from your own account. |

## Steps

1. In the GCP Console, go to **IAM & Admin → Service Accounts → Create Service Account**.
2. Grant the roles above under **Grant this service account access to project**.
3. Create a JSON key for the service account (**Keys → Add Key → JSON**) and download it.
4. In Synkora, go to **Integrations → Add Integration → Google Cloud Platform**, paste the full
   downloaded JSON as the API token, and set `project_id` in the Config JSON field.

Security Command Center findings require SCC to be enabled on the project/organization — if it
isn't, `internal_gcp_list_security_findings` will return an explicit "not enabled" error rather
than failing silently.
```

- [ ] **Step 3: Create the Azure least-privilege roles doc**

Create `docs/integrations/azure-readonly-roles.md`:

```markdown
# Azure Least-Privilege Setup for Synkora

Register an **Azure AD App Registration** and grant it these **built-in, read-only** RBAC roles,
scoped to the subscription (or a specific resource group if you want tighter scope):

| Role | Purpose |
|---|---|
| `Reader` | VM/AKS/general resource metadata and health |
| `Monitoring Reader` | Azure Monitor Logs, Metrics, and Alert rules |
| `Security Reader` | Microsoft Defender for Cloud assessments |

## Steps

1. In the Azure Portal, go to **Azure Active Directory → App registrations → New registration**.
2. Under **Certificates & secrets**, create a new client secret and copy its value immediately (it
   is not shown again).
3. In **Subscriptions → [your subscription] → Access control (IAM) → Add role assignment**, assign
   `Reader`, `Monitoring Reader`, and `Security Reader` to the app registration.
4. In Synkora, go to **Integrations → Add Integration → Microsoft Azure**, enter the app's Client
   ID as the client ID and the client secret as the API token, then set `azure_tenant_id` and
   `subscription_id` in the Config JSON field.

Log Analytics workspace queries additionally require the app to have at least `Reader` access on
the specific workspace resource (covered by the subscription-level `Reader` role above unless the
workspace lives in a different subscription).
```

- [ ] **Step 4: Create the DigitalOcean read-only token doc**

Create `docs/integrations/digitalocean-readonly-token.md`:

```markdown
# DigitalOcean Least-Privilege Setup for Synkora

1. In the DigitalOcean control panel, go to **API → Tokens/Keys → Generate New Token**.
2. Give it a descriptive name (e.g. `synkora-readonly`).
3. Set scope to **Read-only** — DigitalOcean personal access tokens support a read-only scope
   toggle at creation time; do not grant write access.
4. Copy the token immediately (it is not shown again) and paste it as the API token when adding
   the integration in Synkora (**Integrations → Add Integration → DigitalOcean**). No Config JSON
   fields are required for DigitalOcean.

Note: DigitalOcean has no log-query API and no security-findings equivalent to AWS Security
Hub/GCP SCC/Azure Defender — `internal_digitalocean_get_logs` and
`internal_digitalocean_list_security_findings` always return a "Not supported by DigitalOcean"
result rather than being omitted from the agent's tool list.
```

- [ ] **Step 5: Commit**

```bash
git add docs/integrations/aws-readonly-policy.json docs/integrations/gcp-readonly-roles.md docs/integrations/azure-readonly-roles.md docs/integrations/digitalocean-readonly-token.md
git commit -m "docs: add least-privilege setup guides for AWS/GCP/Azure/DigitalOcean integrations"
```

---

## Task 19: Frontend — add the 4 cloud providers to the `PROVIDERS` array

**Files:**
- Modify: `web/app/(dashboard)/oauth-apps/create/page.tsx`

No test — this file has no existing unit test suite (confirmed: `web/app/(dashboard)/oauth-apps/`
has no colocated `*.test.tsx`), and adding one is out of scope per YAGNI (the existing Kling
AI/Minimax entries that this change directly mirrors have none either). Verification is manual
(Step 3).

- [ ] **Step 1: Add 4 icon components**

In `web/app/(dashboard)/oauth-apps/create/page.tsx`, right after the existing `MinimaxIcon`
component (around line 219, before `const PROVIDERS = [`), add:

```tsx
const AWSIcon = () => (
  <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none">
    <rect width="24" height="24" rx="6" fill="#232F3E"/>
    <path d="M6 15c2 1.5 10 1.5 12 0M8 10.5c1-2 7-2 8 0M9 7c.5-1 5-1 6 0" stroke="#FF9900" strokeWidth="1.3" strokeLinecap="round" fill="none"/>
  </svg>
)

const GCPIcon = () => (
  <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none">
    <rect width="24" height="24" rx="6" fill="#FFFFFF" stroke="#E5E7EB"/>
    <path d="M9 8h6l3 4-3 4H9l-3-4z" fill="#4285F4"/>
    <path d="M9 8l-3 4 3 4" fill="#EA4335" fillOpacity="0.85"/>
  </svg>
)

const AzureIcon = () => (
  <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none">
    <rect width="24" height="24" rx="6" fill="#0078D4"/>
    <path d="M9 6l-4 12h4l2-6 3 6h4L11 6H9z" fill="white"/>
  </svg>
)

const DigitalOceanIcon = () => (
  <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none">
    <rect width="24" height="24" rx="6" fill="#0080FF"/>
    <circle cx="12" cy="10" r="5" fill="white"/>
    <rect x="10" y="16" width="4" height="3" fill="white"/>
  </svg>
)
```

- [ ] **Step 2: Add the 4 provider entries to `PROVIDERS`**

Right after the `minimax_video` entry (the closing `},` before the array's closing `]` at line
622), add:

```tsx
  {
    value: 'aws',
    label: 'AWS',
    icon: <AWSIcon />,
    color: 'text-orange-700',
    bgColor: 'bg-orange-50',
    description: 'CloudWatch logs/metrics/alarms, EC2/RDS/Lambda health, Security Hub + GuardDuty findings',
    defaultScopes: [],
    redirectUri: '',
    setupGuide: 'https://github.com/synkora/synkora/blob/main/docs/integrations/aws-readonly-policy.json',
    supportsOAuth: false,
    supportsApiToken: true,
    apiTokenDescription: 'Enter your AWS Secret Access Key as the API token, and your Access Key ID as the Client ID field above. Add {"region": "us-east-1"} in the Config JSON field below.',
  },
  {
    value: 'gcp',
    label: 'Google Cloud Platform',
    icon: <GCPIcon />,
    color: 'text-blue-700',
    bgColor: 'bg-blue-50',
    description: 'Cloud Logging/Monitoring, Compute Engine/GKE health, Security Command Center findings',
    defaultScopes: [],
    redirectUri: '',
    setupGuide: 'https://github.com/synkora/synkora/blob/main/docs/integrations/gcp-readonly-roles.md',
    supportsOAuth: false,
    supportsApiToken: true,
    apiTokenDescription: 'Paste your full service account JSON key as the API token. Add {"project_id": "your-project-id"} in the Config JSON field below.',
  },
  {
    value: 'azure',
    label: 'Microsoft Azure',
    icon: <AzureIcon />,
    color: 'text-blue-800',
    bgColor: 'bg-blue-50',
    description: 'Azure Monitor Logs/Metrics/Alerts, VM/AKS health, Defender for Cloud findings',
    defaultScopes: [],
    redirectUri: '',
    setupGuide: 'https://github.com/synkora/synkora/blob/main/docs/integrations/azure-readonly-roles.md',
    supportsOAuth: false,
    supportsApiToken: true,
    apiTokenDescription: 'Enter your AD App client secret as the API token, and the client ID as the Client ID field above. Add {"azure_tenant_id": "...", "subscription_id": "..."} in the Config JSON field below.',
  },
  {
    value: 'digitalocean',
    label: 'DigitalOcean',
    icon: <DigitalOceanIcon />,
    color: 'text-sky-700',
    bgColor: 'bg-sky-50',
    description: 'Droplet/App Platform metrics, monitoring alert policies, Droplet status',
    defaultScopes: [],
    redirectUri: '',
    setupGuide: 'https://github.com/synkora/synkora/blob/main/docs/integrations/digitalocean-readonly-token.md',
    supportsOAuth: false,
    supportsApiToken: true,
    apiTokenDescription: 'Enter your DigitalOcean personal access token (read-only scope) as the API token.',
  },
```

- [ ] **Step 3: Manually verify in the browser**

Run: `cd web && pnpm dev` (if not already running), then navigate to
`http://localhost:3005/oauth-apps/create`.
Expected: AWS, Google Cloud Platform, Microsoft Azure, and DigitalOcean all appear as selectable
provider cards; selecting each shows the API Token field (no OAuth button) with the
`apiTokenDescription` hint text, and the "Setup Guide" link points to the corresponding new
`docs/integrations/*.md`/`.json` doc.

- [ ] **Step 4: Type-check**

Run: `cd web && pnpm type-check`
Expected: no new TypeScript errors introduced by this change.

- [ ] **Step 5: Commit**

```bash
git add "web/app/(dashboard)/oauth-apps/create/page.tsx"
git commit -m "feat: add AWS/GCP/Azure/DigitalOcean to the OAuth app creation provider list"
```

---

## Task 20: Full-suite verification

**Files:** none (verification only, no code changes)

- [ ] **Step 1: Run every new/modified backend test file together**

Run:
```bash
docker compose exec -T api pytest \
  tests/unit/services/cloud_providers/ \
  tests/unit/services/agents/internal_tools/test_aws_tools.py \
  tests/unit/services/agents/internal_tools/test_gcp_tools.py \
  tests/unit/services/agents/internal_tools/test_azure_tools.py \
  tests/unit/services/agents/internal_tools/test_digitalocean_tools.py \
  tests/unit/services/agents/tool_registrations/ \
  tests/unit/controllers/oauth/test_apps_cloud_validation.py \
  -v
```
Expected: all tests PASS (60 tests: 8 base_adapter/credential_resolver-style + moto AWS adapter +
GCP/Azure/DO adapter tests + 4×7 tool-function tests + 4×2 registry tests + 8 credential-validator
tests + 7 apps.py validation tests — exact count will vary slightly by final assertions written
per task, but zero failures/errors is the pass bar).

- [ ] **Step 2: Run the full existing unit test suite to confirm no regressions**

Run: `docker compose exec -T api pytest tests/unit/ -q`
Expected: all PASS — no pre-existing test broken by the new `adk_tools.py` imports or `apps.py`
changes.

- [ ] **Step 3: Lint and type-check the new backend files**

Run:
```bash
docker compose exec -T api ruff check src/services/cloud_providers/ src/services/agents/internal_tools/aws_tools.py src/services/agents/internal_tools/gcp_tools.py src/services/agents/internal_tools/azure_tools.py src/services/agents/internal_tools/digitalocean_tools.py src/services/agents/internal_tools/cloud_shared.py src/services/agents/tool_registrations/aws_tools_registry.py src/services/agents/tool_registrations/gcp_tools_registry.py src/services/agents/tool_registrations/azure_tools_registry.py src/services/agents/tool_registrations/digitalocean_tools_registry.py src/controllers/oauth/apps.py
docker compose exec -T api ruff format --check src/services/cloud_providers/
```
Expected: no errors. Fix any reported issues and re-run before proceeding.

- [ ] **Step 4: Verify the ADK tool registry loads all 20 new tools with no collisions**

Run:
```bash
docker compose exec -T api python -c "
from src.services.agents.adk_tools import ADKToolRegistry
r = ADKToolRegistry()
names = [n for n in r.tools if n.startswith(('internal_aws_', 'internal_gcp_', 'internal_azure_', 'internal_digitalocean_'))]
assert len(names) == 20, f'expected 20, got {len(names)}: {names}'
print('OK: 20 cloud provider tools registered')
"
```
Expected: prints `OK: 20 cloud provider tools registered`

- [ ] **Step 5: Frontend type-check**

Run: `cd web && pnpm type-check`
Expected: no errors.

- [ ] **Step 6: Restart the API container to pick up all changes for manual smoke-testing**

Run: `docker compose restart api`
Expected: container restarts cleanly; check `docker compose logs -f api` briefly for startup
errors before moving on to manually connecting a real (or sandbox) cloud credential via
`/oauth-apps/create` and wiring it to a test agent's Agent Tools settings.

---

## Self-Review Notes

- **Spec coverage**: every capability-matrix cell (Logs/Metrics/Alerts/Resource
  Health/Security Findings × AWS/GCP/Azure/DigitalOcean) has a concrete adapter method + tool
  function + registry entry (Tasks 4-15), including DigitalOcean's two explicit "not supported"
  cells. Credential storage reuses `OAuthApp` with no new model/migration (Task 2, Task 19).
  Validate-on-save is implemented for all 4 providers with live network calls (Tasks 16-17).
  Least-privilege docs exist for all 4 providers (Task 18) and are linked from the frontend
  `setupGuide` field (Task 19). Secret masking and encryption-at-rest require no new code — both
  are inherited for free by reusing `OAuthApp`/`AgentTool` (`to_dict()`'s existing
  `has_api_token`-only pattern, existing Fernet `encrypt_value`/`decrypt_value`).
- **No-plaintext-logging requirement**: every adapter's error paths return `resp.text`/exception
  messages, never full request bodies or the credentials dict itself — verified no adapter method
  logs `credentials`, `service_account`, or raw tokens anywhere.
- **Test dependency deviation from the original design doc**: added `moto` (Task 3) but did *not*
  add `respx` as the design doc's Testing section suggested — used the codebase's existing
  `monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)` pattern instead (already
  established in `test_slack_message_handler.py`), avoiding an unnecessary new dependency while
  still fully covering GCP/Azure/DigitalOcean's httpx-based request paths.
- **Type consistency check**: `get_cloud_provider_config(runtime_context, tool_name, provider)`
  signature (Task 2) is called identically across all 20 tool functions (Tasks 5, 8, 11, 14) with
  only the `tool_name`/`provider` string arguments varying. `CloudProviderAdapter.__init__(self,
  credentials: dict)` (Task 1) is the constructor signature used identically by `AWSAdapter`,
  `GCPAdapter`, `AzureAdapter`, `DigitalOceanAdapter` (Tasks 4, 7, 10, 13) via `super().__init__()`.
  `register_tool(name, description, parameters, function, requires_auth, tool_category)` (existing
  `adk_tools.py` method) is called with the same 6 keyword arguments across all 20 registrations
  (Tasks 6, 9, 12, 15).
- **Placeholder scan**: no `TBD`/`TODO`/"add error handling" placeholders — every step has complete
  code and exact commands with expected output.
