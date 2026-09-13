"""Execute connection isolation SQL and atomic quotas against a private Redis process."""

import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text

from src.controllers.agents.tools import SaveAgentToolRequest, _authorize_oauth_connections, save_agent_tool
from src.models.oauth_app import OAuthApp
from src.services.agent_api.api_key_service import AgentApiKeyService
from src.services.agents.credential_resolver import CredentialResolver


@pytest.mark.asyncio
async def test_connection_scope_and_assignment_execute_real_sql():
    tenant, other = uuid4(), uuid4()
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE oauth_apps(id INTEGER, tenant_id CHAR(32), is_platform_app BOOLEAN, is_active BOOLEAN, auth_method TEXT, access_token TEXT, refresh_token TEXT, api_token TEXT)"
            )
        )
        rows = [
            (1, tenant.hex, 0, 1, "oauth", "own", None, None),
            (2, other.hex, 0, 1, "oauth", "foreign", None, None),
            (3, None, 1, 1, "oauth", None, None, None),
            (4, None, 1, 1, "oauth", "platform-secret", None, None),
            (5, tenant.hex, 0, 0, "oauth", None, None, None),
        ]
        for row in rows:
            connection.exec_driver_sql("INSERT INTO oauth_apps VALUES (?,?,?,?,?,?,?,?)", row)

        async def execute(stmt):
            return connection.execute(stmt)

        db = SimpleNamespace(execute=execute)
        resolver = CredentialResolver(SimpleNamespace(tenant_id=tenant, db_session=db))
        query = resolver._oauth_apps().with_only_columns(OAuthApp.id).where(OAuthApp.is_active.is_(True))
        assert set(connection.execute(query).scalars()) == {1, 3}
        await _authorize_oauth_connections(db, tenant, [1, 3])
        for ids in ([2], [1, 2], [5], [999]):
            with pytest.raises(HTTPException) as exc:
                await _authorize_oauth_connections(db, tenant, ids)
            assert exc.value.status_code == 404
        resolver.context.tenant_id = None
        assert connection.execute(resolver._oauth_apps().with_only_columns(OAuthApp.id)).scalars().all() == []


@pytest.mark.asyncio
async def test_foreign_assignment_denied_before_mutation():
    db = AsyncMock()
    db.add = MagicMock()
    db.execute.side_effect = [
        SimpleNamespace(scalar_one_or_none=lambda: object()),
        SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [])),
    ]
    with pytest.raises(HTTPException) as exc:
        await save_agent_tool(
            str(uuid4()),
            SaveAgentToolRequest(tool_name="gitlab_test", config={}, oauth_app_id=912),
            SimpleNamespace(id=uuid4()),
            uuid4(),
            db,
        )
    assert exc.value.status_code == 404
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_legacy_helper_never_falls_back_to_another_member():
    db = AsyncMock()
    db.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: None)
    user, tenant = uuid4(), uuid4()
    resolver = CredentialResolver(SimpleNamespace(user_id=user, tenant_id=tenant, db_session=db))
    assert await resolver._get_user_token_record(12) is None
    db.execute.assert_awaited_once()
    params = db.execute.call_args.args[0].compile().params.values()
    assert user in params and tenant in params
    resolver.context.user_id = None
    assert await resolver._get_user_token_record(12) is None
    db.execute.assert_awaited_once()


@pytest.fixture
def private_redis(tmp_path):
    import redis

    binary = shutil.which("redis-server")
    if not binary:
        pytest.skip("redis-server required for real concurrency test")
    directory = tempfile.TemporaryDirectory(prefix="quota-", dir="/private/tmp")
    socket = directory.name + "/redis.sock"
    process = subprocess.Popen(
        [binary, "--port", "0", "--unixsocket", socket, "--save", "", "--appendonly", "no"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    client = redis.Redis(unix_socket_path=socket)
    try:
        for _ in range(100):
            try:
                if client.ping():
                    break
            except redis.ConnectionError:
                time.sleep(0.02)
        else:
            pytest.fail("Private Redis did not start")
        yield client
    finally:
        client.close()
        process.terminate()
        process.wait(timeout=5)
        directory.cleanup()


@pytest.mark.parametrize("limits", [(1, 100, 100), (100, 1, 100), (100, 100, 1)])
def test_concurrent_quota_is_atomic(private_redis, limits):
    key = SimpleNamespace(rate_limit_per_minute=limits[0], rate_limit_per_hour=limits[1], rate_limit_per_day=limits[2])
    with ThreadPoolExecutor(max_workers=16) as pool:
        accepted = list(
            pool.map(
                lambda _: AgentApiKeyService._check_rate_limit_redis(private_redis, "test", 1000, key)[0], range(32)
            )
        )
    assert sum(accepted) == 1
    for window in ("minute", "hour", "day"):
        assert private_redis.zcard(f"api_rate:test:{window}") == 1


def test_quota_expiry_and_same_timestamp_members(private_redis):
    key = SimpleNamespace(rate_limit_per_minute=2, rate_limit_per_hour=100, rate_limit_per_day=100)

    def check(now):
        return AgentApiKeyService._check_rate_limit_redis(private_redis, "test", now, key)[0]

    assert check(1000) and check(1000)
    assert not check(1000)
    assert check(1060)
    assert private_redis.zcard("api_rate:test:hour") == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy", [False, True])
async def test_gitlab_preserves_current_members_token_formats(legacy):
    from src.models.agent_tool import AgentTool
    from src.models.user_oauth_token import UserOAuthToken
    from src.services.agents.security import encrypt_value

    user, tenant = uuid4(), uuid4()
    token = UserOAuthToken(account_id=user, oauth_app_id=12)
    token.access_token = encrypt_value("personal") if legacy else "personal"
    app = SimpleNamespace(id=12, config={}, client_id=None, client_secret=None, app_name="GitLab")

    async def execute(stmt):
        entity = stmt.column_descriptions[0]["entity"]
        value = {AgentTool: SimpleNamespace(oauth_app_id=12), OAuthApp: app, UserOAuthToken: token}[entity]
        if entity is UserOAuthToken:
            params = stmt.compile().params.values()
            assert user in params and tenant in params
        return SimpleNamespace(scalar_one_or_none=lambda: value)

    resolver = CredentialResolver(
        SimpleNamespace(tenant_id=tenant, user_id=user, agent_id=uuid4(), db_session=SimpleNamespace(execute=execute))
    )
    assert await resolver.get_gitlab_token("gitlab_test") == ("personal", "https://gitlab.com")
