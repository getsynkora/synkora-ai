"""Offline regression coverage for the ten source-review findings."""

import asyncio
import importlib
import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException

from src.services.security import sandbox_capability as capability

ROOT = Path(__file__).resolve().parents[5]
SECRET = "synthetic-security-regression-key-123456789"


def load_service(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_capability_scope_expiry_and_service_interoperability(monkeypatch):
    service = load_service("sandbox_capability_test", "services/sandbox/capability.py")
    monkeypatch.setattr(capability.time, "time", lambda: 1000)
    token = capability.issue_capability(SECRET, "tenant-a", "workspace-a")
    assert service.verify_capability(token, SECRET, "tenant-a", "workspace-a")
    for tenant, workspace in [("tenant-b", "workspace-a"), ("tenant-a", "workspace-b")]:
        assert not service.verify_capability(token, SECRET, tenant, workspace)
    assert not service.verify_capability(SECRET, SECRET, "tenant-a", "workspace-a")
    assert not service.verify_capability(token + "0", SECRET, "tenant-a", "workspace-a")
    monkeypatch.setattr(capability.time, "time", lambda: 1060)
    assert not service.verify_capability(token, SECRET, "tenant-a", "workspace-a")
    with pytest.raises(ValueError):
        capability.issue_capability("", "tenant-a", "workspace-a")


def test_command_namespace_has_no_shared_network(monkeypatch, tmp_path):
    isolation = load_service("sandbox_isolation_test", "services/sandbox/isolation.py")
    monkeypatch.setattr(isolation.shutil, "which", lambda *a, **k: "/usr/bin/bwrap")
    monkeypatch.setattr(isolation, "runtime_config", lambda: tmp_path)
    args = isolation.isolated_command(tmp_path, tmp_path, ["true"], {})
    assert "--unshare-all" in args
    assert "--share-net" not in args
    assert "--clearenv" in args


@pytest.mark.asyncio
async def test_local_session_cannot_execute():
    from src.services.compute.session import LocalComputeSession

    result = await LocalComputeSession("/tmp").exec_command(["xargs", "sh", "-c"], input_text="id")
    assert not result["success"]


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy_local", [False, True])
async def test_unconfigured_and_local_agents_use_isolation(monkeypatch, legacy_local):
    from src.models.agent_compute import ComputeType
    from src.services.compute import resolver
    from src.services.compute.backends import factory

    compute = SimpleNamespace(compute_type=ComputeType.LOCAL) if legacy_local else None
    db = SimpleNamespace(execute=AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: compute)))
    backend = SimpleNamespace(checkout_session=AsyncMock(return_value=object()), backend_type="sandbox")
    monkeypatch.setattr(factory, "get_backend_for_tenant", AsyncMock(return_value=backend))
    tenant = uuid4()
    result = await resolver.build_compute_session_for_agent(uuid4(), db, tenant)
    assert result is backend.checkout_session.return_value
    assert backend.checkout_session.call_args.kwargs["tenant_id"] == str(tenant)
    with pytest.raises(RuntimeError):
        await resolver.build_compute_session_for_agent(uuid4(), db)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["feedback", "outcome"])
@pytest.mark.parametrize("owned", [False, True])
async def test_evaluation_requires_owned_resource(monkeypatch, kind, owned):
    from src.controllers.agents import eval as controller
    from src.services.eval import feedback_service, outcome_service

    agent, tenant, resource = SimpleNamespace(id=uuid4()), uuid4(), uuid4()
    monkeypatch.setattr(controller, "_get_agent", AsyncMock(return_value=agent))
    db = SimpleNamespace(
        execute=AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: resource if owned else None))
    )
    record = MagicMock()
    if kind == "feedback":
        monkeypatch.setattr(feedback_service, "record_feedback", record)
        body = controller.FeedbackRequest(message_id=resource, rating=1, trace_id="victim-trace")
        handler = controller.submit_feedback
    else:
        monkeypatch.setattr(outcome_service, "record_explicit_outcome", record)
        body = controller.OutcomeRequest(conversation_id=resource, helpful=True, trace_id="victim-trace")
        handler = controller.submit_outcome
    if owned:
        await handler("own-agent", body, tenant, db)
        assert record.call_args.kwargs["trace_id"] is None
        assert record.call_args.kwargs["tenant_id"] == tenant
    else:
        with pytest.raises(HTTPException) as exc:
            await handler("own-agent", body, tenant, db)
        assert exc.value.status_code == 404
        record.assert_not_called()
    # Verify that the query binds both the supplied resource and authorized agent.
    query = db.execute.call_args.args[0].compile()
    assert resource in query.params.values()
    assert agent.id in query.params.values()
    assert "conversations.agent_id" in str(query)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind,resource", [("feedback", "message_id"), ("outcome", "conversation_id")])
async def test_evaluation_document_ids_do_not_collide(monkeypatch, kind, resource):
    module = importlib.import_module(f"src.services.eval.{kind}_service")
    es = SimpleNamespace(index=AsyncMock())
    monkeypatch.setattr(module, "_get_es_client", AsyncMock(return_value=es))
    for tenant in ("tenant-a", "tenant-b"):
        await getattr(module, f"_index_{kind}")({"tenant_id": tenant, "agent_id": "agent", resource: "same-id"})
    ids = [call.kwargs["id"] for call in es.index.call_args_list]
    assert ids == ["tenant-a:agent:same-id", "tenant-b:agent:same-id"]


@pytest.mark.asyncio
@pytest.mark.parametrize("parent", [None, {"agent_id": "foreign-agent"}])
async def test_case_creation_rejects_foreign_parent_without_writes(monkeypatch, parent):
    from src.services.eval import dataset_service as service

    monkeypatch.setattr(service, "get_dataset", AsyncMock(return_value=parent))
    client = AsyncMock()
    monkeypatch.setattr(service, "_get_es_client", client)
    with pytest.raises(ValueError):
        await service.create_case(
            dataset_id="foreign", agent_id=uuid4(), tenant_id=uuid4(), input="x", expected_criteria="y"
        )
    client.assert_not_called()


@pytest.mark.asyncio
async def test_poisoned_case_cannot_mutate_foreign_dataset(monkeypatch):
    from src.services.eval import dataset_service as service

    tenant = uuid4()
    doc = {"tenant_id": str(tenant), "agent_id": "attacker", "dataset_id": "victim"}
    es = SimpleNamespace(get=AsyncMock(return_value={"_source": doc}), delete=AsyncMock(), update=AsyncMock())
    monkeypatch.setattr(service, "_get_es_client", AsyncMock(return_value=es))
    monkeypatch.setattr(service, "get_dataset", AsyncMock(return_value=None))
    assert not await service.delete_case(case_id="poisoned", tenant_id=tenant)
    es.delete.assert_not_called()
    es.update.assert_not_called()


@pytest.mark.asyncio
async def test_direct_identity_claim_cannot_link_account():
    from src.controllers import social_auth

    db = AsyncMock()
    with pytest.raises(HTTPException) as exc:
        await social_auth.link_provider(
            social_auth.LinkProviderRequest(
                provider="google", provider_user_id="victim", provider_email="victim@example.test"
            ),
            SimpleNamespace(id=uuid4()),
            db,
        )
    assert exc.value.status_code == 410
    db.add.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind,prefix", [("_get_oauth_state", "oauth_state"), ("_consume_exchange_tokens", "oauth_exchange")]
)
async def test_concurrent_oauth_consumption_is_single_use(monkeypatch, kind, prefix):
    from src.controllers import social_auth

    values = {f"{prefix}:nonce": json.dumps({"synthetic": "value"})}

    async def getdel(key):
        return values.pop(key, None)

    # No get/delete methods: only the atomic operation is available.
    monkeypatch.setattr(social_auth, "_get_redis_client", lambda: SimpleNamespace(getdel=getdel))
    results = await asyncio.gather(*(getattr(social_auth, kind)("nonce") for _ in range(20)))
    assert sum(value is not None for value in results) == 1


@pytest.mark.asyncio
async def test_provider_configuration_platform_guard():
    from src.controllers import social_auth_config as controller
    from src.models.tenant import TenantType

    assert all(
        any(dep.call is controller.require_provider_admin for dep in route.dependant.dependencies)
        for route in controller.router.routes
    )
    dependencies = controller.router.routes[0].dependant.dependencies[0].dependencies
    assert any(dep.name == "_role" for dep in dependencies)
    tenant = SimpleNamespace(tenant_type=TenantType.PLATFORM)
    db = SimpleNamespace(execute=AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: tenant)))
    with pytest.raises(HTTPException) as exc:
        await controller.require_provider_admin(uuid4(), SimpleNamespace(is_platform_admin=False), db, None)
    assert exc.value.status_code == 403
    await controller.require_provider_admin(uuid4(), SimpleNamespace(is_platform_admin=True), db, None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "eval.dataset_service",
        "eval.feedback_service",
        "eval.outcome_service",
        "eval.judge_service",
        "eval.quality_query",
        "agents.agent_trace_service",
    ],
)
async def test_elasticsearch_clients_verify_certificates(monkeypatch, path):
    import elasticsearch

    from src.config.settings import settings

    module = importlib.import_module(f"src.services.{path}")
    monkeypatch.setattr(module, "_es_client", None, raising=False)
    monkeypatch.setattr(settings, "elasticsearch_ca_certs", "/test/tenant-ca.pem")
    constructor = MagicMock()
    monkeypatch.setattr(elasticsearch, "AsyncElasticsearch", constructor)
    await module._get_es_client()
    assert constructor.call_args.kwargs["verify_certs"] is True
    assert constructor.call_args.kwargs["ca_certs"] == "/test/tenant-ca.pem"


@pytest.mark.parametrize(
    "field,value",
    [
        ("resource_type", "account"),
        ("resource_id", "other"),
        ("description", "changed"),
        ("activity_metadata", {"role": "owner"}),
        ("ip_address", "other"),
        ("user_agent", "other"),
        ("status", "failure"),
        ("error_message", "changed"),
        ("tenant_id", "other"),
        ("prev_hash", "f" * 64),
    ],
)
def test_audit_hash_covers_security_fields(field, value):
    from src.models.activity_log import ActivityLog

    args = {
        "entry_id": "entry",
        "action": "update",
        "account_id": "account",
        "tenant_id": "tenant",
        "activity_type": "TEAM",
        "created_at": "2026-09-10T00:00:00+00:00",
        "prev_hash": "0" * 64,
        "secret_key": SECRET,
    }
    original = ActivityLog.compute_hash(**args)
    assert ActivityLog.compute_hash(**{**args, field: value}) != original
    with pytest.raises(ValueError):
        ActivityLog.compute_hash(**{**args, "secret_key": ""})


@pytest.mark.asyncio
async def test_audit_append_locks_before_reading_predecessor(monkeypatch):
    from src.config.settings import settings
    from src.services.activity.activity_log_service import ActivityLogService

    monkeypatch.setattr(settings, "audit_chain_secret", SECRET)
    db = SimpleNamespace(
        execute=AsyncMock(
            return_value=MagicMock(
                scalar_one_or_none=lambda: SimpleNamespace(
                    entry_hash="a" * 64, created_at=datetime(2100, 1, 1, tzinfo=UTC)
                )
            )
        ),
        add=MagicMock(),
    )

    async def flush():
        entry = db.add.call_args.args[0]
        entry.id, entry.status = uuid4(), "success"

    db.flush = flush
    entry = await ActivityLogService(db)._prepare_log_entry(
        uuid4(), uuid4(), "update", "agent", details={"role": "member"}
    )
    assert "pg_advisory_xact_lock" in str(db.execute.call_args_list[0].args[0])
    assert "activity_logs.entry_hash" in str(db.execute.call_args_list[1].args[0])
    assert entry.activity_metadata["_audit"] == {"version": 2, "prev_hash": "a" * 64}
    assert entry.created_at > datetime(2100, 1, 1, tzinfo=UTC)
    assert len(entry.entry_hash) == 64


@pytest.mark.asyncio
async def test_ml_rejects_untrusted_index_writes(monkeypatch):
    ml = load_service("ml_security_test", "services/ml/app.py")
    monkeypatch.setenv("ML_API_KEY", SECRET)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=ml.app), base_url="http://test") as client:
        response = await client.post("/v1/tools/initialize", json={"agent_id": "victim", "tools": []})
        assert response.status_code == 401
        response = await client.post(
            "/v1/tools/initialize", headers={"X-ML-Key": SECRET}, json={"agent_id": "own", "tools": []}
        )
        assert response.status_code == 200
        response = await client.post(
            "/v1/embed", headers={"X-ML-Key": SECRET}, json={"texts": ["test"], "model": "attacker/model"}
        )
        assert response.status_code == 400
    assert ml._tool_indexes == {}


@pytest.mark.asyncio
async def test_provider_member_denied_before_configuration_access(monkeypatch):
    from fastapi import FastAPI

    from src.controllers import social_auth_config as controller
    from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
    from src.services.auth_service import AuthService

    application = FastAPI()
    application.include_router(controller.router)
    application.dependency_overrides[get_current_account] = lambda: SimpleNamespace(id=uuid4())
    application.dependency_overrides[get_current_tenant_id] = uuid4
    db = SimpleNamespace(execute=AsyncMock())
    application.dependency_overrides[controller.get_async_db] = lambda: db
    monkeypatch.setattr(AuthService, "check_permission", AsyncMock(return_value=False))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application), base_url="http://test") as client:
        response = await client.get("/api/v1/social-auth-config")
        assert response.status_code == 403
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_audit_writer_and_verifier_agree_and_detect_tampering(monkeypatch):
    from src.config.settings import settings
    from src.models.activity_log import ActivityType
    from src.services.audit_chain_service import append_audit_log, verify_chain

    monkeypatch.setattr(settings, "audit_chain_secret", SECRET)
    db = SimpleNamespace(execute=AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: None)), add=MagicMock())

    async def flush():
        db.add.call_args.args[0].id = uuid4()

    db.flush = flush
    tenant = uuid4()
    entry = await append_audit_log(
        db,
        tenant_id=tenant,
        action="update",
        activity_type=ActivityType.TEAM,
        activity_metadata={"role": "member"},
        status="failure",
        error_message="denied",
    )
    db.execute.return_value = MagicMock(scalars=lambda: SimpleNamespace(all=lambda: [entry]))
    result = await verify_chain(db, tenant)
    assert result["valid"] and result["complete"] and result["checked"] == 1
    entry.activity_metadata["role"] = "owner"
    result = await verify_chain(db, tenant)
    assert not result["valid"] and result["first_broken_id"] == str(entry.id)
    entry.activity_metadata.pop("_audit")
    result = await verify_chain(db, tenant)
    assert not result["valid"] and result["legacy_entries"] == 1


@pytest.mark.asyncio
async def test_all_sandbox_endpoints_reject_foreign_workspace_capability(monkeypatch, tmp_path):
    monkeypatch.setenv("SANDBOX_API_KEY", SECRET)
    monkeypatch.setenv("WORKSPACES_BASE", str(tmp_path / "workspaces"))
    monkeypatch.syspath_prepend(str(ROOT / "services/sandbox"))
    sandbox = load_service("sandbox_http_security_test", "services/sandbox/app.py")
    token = capability.issue_capability(SECRET, "attacker", "workspace")
    foreign = {"tenant_id": "victim", "agent_id": "workspace", "path": "marker"}
    requests = [
        ("POST", "/v1/exec", {"json": {**foreign, "command": ["true"]}}),
        ("GET", "/v1/files", {"params": foreign}),
        ("PUT", "/v1/files", {"json": {**foreign, "content": "overwrite"}}),
        ("GET", "/v1/files/binary", {"params": foreign}),
        ("PUT", "/v1/files/binary", {"json": {**foreign, "content_base64": "eA=="}}),
        ("GET", "/v1/dir", {"params": foreign}),
        ("POST", "/v1/dir", {"json": foreign}),
        ("GET", "/v1/exists", {"params": foreign}),
        ("DELETE", "/v1/workspace", {"params": foreign}),
    ]
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=sandbox.app), base_url="http://test") as client:
        for method, path, kwargs in requests:
            response = await client.request(method, path, headers={"X-Sandbox-Key": token}, **kwargs)
            assert response.status_code == 401, (path, response.text)
    assert not (tmp_path / "workspaces").exists()


@pytest.mark.asyncio
async def test_ml_client_uses_validated_settings_key(monkeypatch):
    from src.config.settings import settings
    from src.core.ml_client import MLServiceClient

    monkeypatch.delenv("ML_API_KEY", raising=False)
    monkeypatch.setattr(settings, "ml_api_key", SECRET)
    client = MLServiceClient("http://test")
    assert client._get_client().headers["X-ML-Key"] == SECRET
    await client.close()
