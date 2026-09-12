"""Offline regression checks for the application-security review fixes.

All identities and payloads are synthetic. No database, provider, or storage requests.
"""

import io
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy.dialects import postgresql


def query_parts(query):
    compiled = query.compile(dialect=postgresql.dialect())
    return str(compiled), compiled.params


@pytest.mark.asyncio
@pytest.mark.parametrize("flag,allowed", [(False, False), ("false", False), (True, True), ("true", True)])
async def test_global_settings_require_platform_authority(flag, allowed):
    from src.middleware.auth_middleware import require_platform_admin

    account = SimpleNamespace(is_platform_admin=flag)
    if allowed:
        await require_platform_admin(account)
    else:
        with pytest.raises(HTTPException) as error:
            await require_platform_admin(account)
        assert error.value.status_code == 403


def test_global_routes_all_use_platform_guard():
    from src.controllers.platform_settings import router
    from src.middleware.auth_middleware import require_platform_admin

    assert router.routes
    for route in router.routes:
        assert require_platform_admin in [dep.call for dep in route.dependant.dependencies]


@pytest.mark.asyncio
async def test_tenant_member_cannot_edit_sensitive_agent_config():
    from src.controllers.agents import database_connections, llm_configs
    from src.middleware.auth_middleware import require_role
    from src.models import AccountRole
    from src.services.auth_service import AuthService

    # The route dependencies use the same current-database role policy as agent CRUD.
    for router in (llm_configs.router, database_connections.router):
        for route in router.routes:
            if route.methods & {"POST", "PATCH", "PUT", "DELETE"}:
                assert any(dep.call.__name__ == "check_role" for dep in route.dependant.dependencies)
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=lambda: SimpleNamespace(is_platform_admin=False)),
                MagicMock(scalar_one_or_none=lambda: SimpleNamespace(role=AccountRole.NORMAL)),
            ]
        )
    )
    assert not await AuthService.check_permission(db, uuid4(), uuid4(), AccountRole.ADMIN)
    # Exercise the dependency's denied response too.
    db.execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: SimpleNamespace(is_platform_admin=False)),
        MagicMock(scalar_one_or_none=lambda: SimpleNamespace(role=AccountRole.NORMAL)),
    ]
    with pytest.raises(HTTPException) as error:
        await require_role(AccountRole.ADMIN)(SimpleNamespace(id=uuid4()), uuid4(), db)
    assert error.value.status_code == 403


def test_avatar_signing_requires_object_tenant(monkeypatch):
    from src.controllers.agents import index

    tenant, other = uuid4(), uuid4()
    storage = SimpleNamespace(
        bucket_name="test-bucket",
        extract_own_key_from_url=lambda value: None,
        generate_presigned_url=MagicMock(return_value="https://storage.example/authorized"),
    )
    monkeypatch.setattr(index, "_get_storage_service", lambda: storage)
    assert index.convert_s3_uri_to_presigned_url(f"s3://test-bucket/tenants/{other}/image.png", tenant) is None
    assert index.convert_s3_uri_to_presigned_url(f"s3://other-bucket/tenants/{tenant}/image.png", tenant) is None
    storage.generate_presigned_url.assert_not_called()
    assert index.convert_s3_uri_to_presigned_url(f"s3://test-bucket/tenants/{tenant}/image.png", tenant)
    storage.generate_presigned_url.assert_called_once()
    assert index.validate_avatar_reference("https://images.example/avatar.png", tenant).startswith("https://")


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["oauth_app_id", "slack_bot_id"])
@pytest.mark.parametrize("owned", [False, True])
async def test_output_update_checks_replacement_credential(field, owned):
    from src.controllers.agents.outputs import OutputConfigUpdate, update_output_config

    tenant = uuid4()
    config = SimpleNamespace(to_dict=lambda: {}, provider="slack")
    credential = SimpleNamespace(provider="slack")
    db = SimpleNamespace(
        execute=AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: config)),
        scalar=AsyncMock(return_value=credential if owned else None),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    body = OutputConfigUpdate(**{field: 17 if field == "oauth_app_id" else str(uuid4())})
    if owned:
        await update_output_config(uuid4(), uuid4(), body, db, SimpleNamespace(), tenant)
        db.commit.assert_awaited_once()
    else:
        with pytest.raises(HTTPException) as error:
            await update_output_config(uuid4(), uuid4(), body, db, SimpleNamespace(), tenant)
        assert error.value.status_code == 400
        db.commit.assert_not_awaited()
    sql, params = query_parts(db.scalar.call_args.args[0])
    assert "tenant_id =" in sql and tenant in params.values()


@pytest.mark.asyncio
async def test_delivery_rejects_foreign_credentials(monkeypatch):
    from src.models import OutputProvider
    from src.services.agent_output_service import AgentOutputService

    tenant = uuid4()
    db = SimpleNamespace(
        add=MagicMock(side_effect=lambda row: setattr(row, "attempt_count", 0)),
        commit=AsyncMock(),
        refresh=AsyncMock(),
        flush=AsyncMock(),
        execute=AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: None)),
    )
    service = AgentOutputService(db)
    provider = SimpleNamespace(send=AsyncMock())
    service.providers[OutputProvider.SLACK] = provider
    output = SimpleNamespace(
        id=uuid4(),
        agent_id=uuid4(),
        tenant_id=tenant,
        provider=OutputProvider.SLACK,
        output_template=None,
        oauth_app_id=17,
        slack_bot_id=None,
        config={},
    )
    delivery = await service._send_single_output(output, "synthetic message", {})
    assert delivery.status.value == "failed"
    provider.send.assert_not_awaited()
    sql, params = query_parts(db.execute.call_args.args[0])
    assert "tenant_id =" in sql and tenant in params.values()


@pytest.mark.asyncio
@pytest.mark.parametrize("owned", [False, True])
async def test_followup_references_checked_before_task_persistence(owned):
    from src.services.scheduler.scheduler_service import SchedulerService

    tenant, agent, followup = uuid4(), uuid4(), uuid4()
    db = SimpleNamespace(scalar=AsyncMock(side_effect=[followup, agent] if owned else [None]))
    service = SchedulerService(db)
    config = {"agent_id": str(agent), "followup_item_id": str(followup)}
    if owned:
        await service._validate_references(tenant, "followup_reminder", config)
    else:
        with pytest.raises(ValueError, match="Follow-up"):
            await service._validate_references(tenant, "followup_reminder", config)
    sql, params = query_parts(db.scalar.call_args_list[0].args[0])
    assert "tenant_id =" in sql
    assert {tenant, agent, followup} <= set(params.values())


@pytest.mark.asyncio
async def test_chat_approval_resolution_binds_actor_tenant_and_conversation():
    from src.services.human_approval_service import HumanApprovalService

    tenant, account, conversation = uuid4(), uuid4(), uuid4()
    db = SimpleNamespace(execute=AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: None)))
    service = HumanApprovalService(db)
    service.handle_reply = AsyncMock()
    result = await service.handle_chat_reply("my-agent", str(conversation), "yes", account, tenant, db)
    assert result is None
    service.handle_reply.assert_not_awaited()
    sql, params = query_parts(db.execute.call_args.args[0])
    assert "conversations.account_id =" in sql
    assert "tenant_account_joins.account_id =" in sql
    assert "agent_approval_requests.tenant_id =" in sql
    assert {tenant, account, conversation, "my-agent"} <= set(params.values())


@pytest.mark.asyncio
@pytest.mark.parametrize("authorized", [False, True])
async def test_chat_approval_service_rechecks_owner_and_locks_decision(authorized):
    from src.models.agent_approval import ApprovalStatus
    from src.services.human_approval_service import HumanApprovalService

    tenant, agent, conversation, account = uuid4(), uuid4(), uuid4(), uuid4()
    approval = SimpleNamespace(
        id=uuid4(),
        notification_channel="chat",
        conversation_id=conversation,
        status=ApprovalStatus.PENDING,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    db = SimpleNamespace(
        execute=AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: approval)),
        scalar=AsyncMock(return_value=conversation if authorized else None),
        commit=AsyncMock(),
    )
    service = HumanApprovalService(db)
    service._store_execution_token = AsyncMock()
    service._fire_approved_run = AsyncMock()
    service._update_slack_message_if_applicable = AsyncMock()
    result = await service.handle_reply(
        approval.id, "yes", db, tenant_id=tenant, agent_id=agent, account_id=account, conversation_id=conversation
    )
    if authorized:
        assert result == "approved"
        assert approval.responded_by == str(account)
        service._store_execution_token.assert_awaited_once()
    else:
        assert result == "not_found"
        db.commit.assert_not_awaited()
        service._store_execution_token.assert_not_awaited()
    sql, params = query_parts(db.execute.call_args.args[0])
    assert "FOR UPDATE" in sql and {tenant, agent} <= set(params.values())


def test_session_creation_time_is_write_once():
    from src.services.security.token_blacklist import TokenBlacklistService

    values = {}

    def set_value(key, value, *, ex, nx):
        assert nx and ex > 0
        if key not in values:
            values[key] = value
            return True
        return False

    service = object.__new__(TokenBlacklistService)
    service._redis = SimpleNamespace(set=set_value, get=values.get)
    account = uuid4()
    assert service.store_session_created_at(account, "family", 1000)
    assert service.store_session_created_at(account, "family", 2000)
    assert service.get_session_created_at(account, "family") == 1000


@pytest.mark.asyncio
@pytest.mark.parametrize("header", [None, b"2", b"invalid"])
@pytest.mark.parametrize("swallow", [False, True])
async def test_body_limit_counts_stream_and_survives_handler_exception_mapping(monkeypatch, header, swallow):
    from src import app as app_module

    monkeypatch.setattr(app_module, "MAX_REQUEST_BODY_SIZE", 4)
    chunks = iter(
        [
            {"type": "http.request", "body": b"abc", "more_body": True},
            {"type": "http.request", "body": b"de", "more_body": False},
        ]
    )
    receive = AsyncMock(side_effect=lambda: next(chunks))
    send = AsyncMock()

    async def application(scope, receive, send):
        try:
            await receive()
            await receive()
        except HTTPException:
            if not swallow:
                raise
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    scope = {"type": "http", "path": "/example", "headers": [] if header is None else [(b"content-length", header)]}
    await app_module.RequestSizeLimitMiddleware(application)(scope, receive, send)
    assert send.call_args_list[0].args[0]["status"] == 413
    assert len([call for call in send.call_args_list if call.args[0]["type"] == "http.response.start"]) == 1


@pytest.mark.asyncio
async def test_upload_limit_preserves_small_files_and_rejects_oversize():
    from src.services.security.upload_limits import read_bounded_upload

    assert await read_bounded_upload(UploadFile(io.BytesIO(b"abc")), 3) == b"abc"
    with pytest.raises(HTTPException) as error:
        await read_bounded_upload(UploadFile(io.BytesIO(b"abcd")), 3)
    assert error.value.status_code == 413


@pytest.mark.asyncio
async def test_malformed_webhook_log_does_not_contain_body(monkeypatch, caplog):
    from src.controllers.agents import webhooks

    monkeypatch.setattr(webhooks.webhook_rate_limiter, "is_rate_limited", AsyncMock(return_value=(False, "")))
    monkeypatch.setattr(webhooks.webhook_rate_limiter, "record_request", AsyncMock())
    db = SimpleNamespace(
        execute=AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: SimpleNamespace(id=uuid4())))
    )
    request = SimpleNamespace(body=AsyncMock(return_value=b"synthetic-private-body"), headers={})
    with pytest.raises(HTTPException):
        await webhooks.receive_webhook("synthetic-route", request, db)
    assert "synthetic-private-body" not in caplog.text
    assert "Invalid webhook JSON" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("age", [None, 24, 0])
async def test_refresh_enforces_absolute_age_before_rotation(monkeypatch, age):
    from src.services import session_service

    account = SimpleNamespace(id=uuid4(), status="ACTIVE", auth_version=0)
    blacklist = MagicMock()
    blacklist.is_blacklisted.return_value = False
    blacklist.get_account_token_version.return_value = 0
    blacklist.validate_refresh_token_family.return_value = True
    blacklist.get_session_created_at.return_value = (
        None if age is None else (datetime.now(UTC) - timedelta(hours=age)).timestamp()
    )
    monkeypatch.setattr(session_service, "get_token_blacklist_service", lambda: blacklist)
    monkeypatch.setattr(
        session_service.AuthService,
        "decode_token",
        lambda _: {
            "sub": str(account.id),
            "type": "refresh",
            "fid": "family",
            "ver": 0,
        },
    )
    monkeypatch.setattr(session_service.AuthService, "validate_account_auth_version", lambda *args: None)
    monkeypatch.setattr(session_service.settings, "jwt_max_session_age_hours", 12)
    create = AsyncMock(return_value={"access_token": "synthetic"})
    monkeypatch.setattr(session_service.SessionService, "create_session", create)
    db = SimpleNamespace(execute=AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: account)))
    if age == 0:
        assert await session_service.SessionService.refresh_session(db, "synthetic", uuid4())
        create.assert_awaited_once()
        assert create.call_args.kwargs["family_id"] == "family"
    else:
        with pytest.raises(ValueError):
            await session_service.SessionService.refresh_session(db, "synthetic", uuid4())
        create.assert_not_awaited()


def test_followup_worker_reloads_task_and_filters_child_tenant(monkeypatch):
    from sqlalchemy import and_

    from src.models.agent import Agent
    from src.models.followup import FollowupItem
    from src.models.scheduled_task import ScheduledTask
    from src.tasks import followup_reminder_task as worker

    tenant, agent, followup, task_id = uuid4(), uuid4(), uuid4(), uuid4()
    task = SimpleNamespace(tenant_id=tenant, config={"agent_id": str(agent), "followup_item_id": str(followup)})
    queries = {}

    def query(model):
        q = MagicMock()
        q.filter.return_value = q
        q.first.return_value = {ScheduledTask: task, Agent: SimpleNamespace(id=agent), FollowupItem: None}[model]
        queries[model] = q
        return q

    db = SimpleNamespace(query=query, commit=MagicMock(), close=MagicMock())
    monkeypatch.setattr(worker, "get_db", lambda: iter([db]))
    result = worker.execute_followup_reminder.run(
        str(task_id), str(tenant), str(uuid4()), {"followup_item_id": str(uuid4())}
    )
    assert result["success"] is False
    db.commit.assert_not_called()
    sql, params = query_parts(and_(*queries[FollowupItem].filter.call_args.args))
    assert "followup_items.tenant_id =" in sql
    assert {tenant, agent, followup} <= set(params.values())


@pytest.mark.asyncio
async def test_request_limit_accepts_complete_small_body(monkeypatch):
    from src import app as app_module

    monkeypatch.setattr(app_module, "MAX_REQUEST_BODY_SIZE", 4)
    receive = AsyncMock(return_value={"type": "http.request", "body": b"abcd", "more_body": False})
    send = AsyncMock()

    async def application(scope, receive, send):
        assert (await receive())["body"] == b"abcd"
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    await app_module.RequestSizeLimitMiddleware(application)(
        {"type": "http", "path": "/example", "headers": []}, receive, send
    )
    assert send.call_args_list[0].args[0]["status"] == 200


def test_all_agent_configuration_mutations_have_role_guard():
    import importlib

    for name in (
        "tools",
        "knowledge_bases",
        "mcp_servers",
        "context_files",
        "skills",
        "custom_tools",
        "versions",
        "chat_config",
        "sub_agents",
        "outputs",
        "webhooks",
        "llm_configs",
        "database_connections",
    ):
        module = importlib.import_module(f"src.controllers.agents.{name}")
        routers = [
            obj
            for key, obj in vars(module).items()
            if key.endswith("router") and "public" not in key and hasattr(obj, "routes")
        ]
        for router in routers:
            for route in router.routes:
                if route.methods & {"POST", "PATCH", "PUT", "DELETE"}:
                    assert any(dep.call.__name__ == "check_role" for dep in route.dependant.dependencies), (
                        name,
                        route.path,
                    )
