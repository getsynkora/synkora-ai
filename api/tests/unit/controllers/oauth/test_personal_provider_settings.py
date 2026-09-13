"""Personal OAuth callbacks and credential resolution keep destination/token pairs together."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.controllers.oauth import jira, salesforce
from src.models import Account, AccountStatus, Tenant, TenantAccountJoin
from src.models.agent_tool import AgentTool
from src.models.oauth_app import OAuthApp
from src.models.user_oauth_token import UserOAuthToken
from src.services.agents.credential_resolver import CredentialResolver
from src.services.agents.security import encrypt_value
from src.services.permissions.permission_service import PermissionService


@pytest.fixture
def personal_connection(monkeypatch):
    account = SimpleNamespace(id=uuid4(), status=AccountStatus.ACTIVE, auth_version=0)
    tenant = uuid4()
    app = SimpleNamespace(
        id=12,
        tenant_id=tenant,
        is_platform_app=False,
        provider="jira",
        app_name="App",
        auth_method="oauth",
        client_id="synthetic",
        client_secret=encrypt_value("client-secret"),
        redirect_uri="https://example.invalid",
        config={
            "instance_url": "https://shared.example.invalid",
            "cloud_id": "shared-cloud",
            "cloud_url": "https://shared.atlassian.net",
        },
        access_token="encrypted-shared-token",
        refresh_token=None,
        token_expires_at=None,
    )
    record = UserOAuthToken(
        account_id=account.id,
        oauth_app_id=12,
        provider_config={
            "instance_url": "https://personal.example.invalid",
            "cloud_id": "personal-cloud",
            "cloud_url": "https://personal.atlassian.net",
        },
    )
    record.access_token = "personal-token"
    records = [record]
    db = AsyncMock()
    db.add = MagicMock(side_effect=lambda row: records.__setitem__(0, row))

    async def execute(stmt):
        entity = stmt.column_descriptions[0]["entity"]
        value = {
            Account: account,
            TenantAccountJoin: object(),
            Tenant: SimpleNamespace(disabled_platform_oauth_providers=[]),
            OAuthApp: app,
            UserOAuthToken: records[0],
            AgentTool: SimpleNamespace(oauth_app_id=12),
        }[entity]
        return SimpleNamespace(scalar_one_or_none=lambda: value)

    db.execute.side_effect = execute
    permission = AsyncMock(return_value=False)
    monkeypatch.setattr(PermissionService, "check_permission", permission)
    state = {
        "oauth_app_id": 12,
        "account_id": str(account.id),
        "tenant_id": str(tenant),
        "auth_version": 0,
        "user_level": True,
        "redirect_url": "https://example.invalid",
    }
    context = SimpleNamespace(user_id=account.id, tenant_id=tenant, agent_id=uuid4(), db_session=db)
    return app, records, db, state, context, permission


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["jira", "salesforce"])
@pytest.mark.parametrize("platform", [False, True])
@pytest.mark.parametrize("existing", [False, True])
async def test_personal_callback_stores_only_personal_settings(
    personal_connection, monkeypatch, provider, platform, existing
):
    app, records, db, state, context, permission = personal_connection
    app.provider = provider
    app.is_platform_app = platform
    if not existing:
        records[0] = None
    old_config = dict(app.config)
    module = jira if provider == "jira" else salesforce
    sdk = MagicMock()
    sdk.get_access_token = AsyncMock(
        return_value={
            "access_token": "new-personal-token",
            "expires_in": 3600,
            "instance_url": "https://personal.example.invalid",
        }
    )
    sdk.get_user_info = AsyncMock(
        return_value={
            "id": "person",
            "account_id": "person",
            "email": "person@example.invalid",
            "name": "Person",
            "cloud_id": "personal-cloud",
            "cloud_url": "https://personal.atlassian.net",
        }
    )
    monkeypatch.setattr(module, "get_oauth_state", lambda *a, **k: state)
    monkeypatch.setattr(module, "JiraOAuth" if provider == "jira" else "SalesforceOAuth", lambda **k: sdk)
    monkeypatch.setattr(module, "decrypt_value", lambda x: x)
    monkeypatch.setattr(module, "get_app_base_url", AsyncMock(return_value="https://example.invalid"))
    await getattr(module, provider + "_callback")("code", "state", db)
    assert app.config == old_config and app.access_token == "encrypted-shared-token"
    assert records[0].access_token == "new-personal-token"
    field = "cloud_id" if provider == "jira" else "instance_url"
    expected = "personal-cloud" if provider == "jira" else "https://personal.example.invalid"
    assert records[0].provider_config[field] == expected
    permission.assert_not_awaited()
    resolver = CredentialResolver(context)
    credentials = await getattr(resolver, "get_" + provider + "_credentials")("tool")
    assert credentials[field] == expected and credentials["access_token"] == "new-personal-token"


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["jira", "salesforce"])
async def test_legacy_personal_destination_is_not_guessed(personal_connection, provider):
    app, records, _, _, context, _ = personal_connection
    app.provider = provider
    records[0].provider_config = None
    assert await getattr(CredentialResolver(context), "get_" + provider + "_credentials")("tool") is None


@pytest.mark.asyncio
async def test_jira_refresh_failure_falls_back_to_matching_app_destination(personal_connection, monkeypatch):
    app, records, _, _, context, _ = personal_connection
    records[0].token_expires_at = datetime.now(UTC) - timedelta(hours=1)
    records[0].refresh_token = "personal-refresh"
    sdk = MagicMock()
    sdk.refresh_token = AsyncMock(side_effect=ValueError("synthetic failure"))
    monkeypatch.setattr("src.services.oauth.jira_oauth.JiraOAuth", lambda **k: sdk)
    monkeypatch.setattr(
        "src.services.agents.security.decrypt_value", lambda x: "shared-token" if x == app.access_token else x
    )
    credentials = await CredentialResolver(context).get_jira_credentials("tool")
    assert credentials["access_token"] == "shared-token" and credentials["cloud_id"] == "shared-cloud"


@pytest.mark.asyncio
async def test_jira_refresh_keeps_personal_destination(personal_connection, monkeypatch):
    _, records, _, _, context, _ = personal_connection
    records[0].token_expires_at = datetime.now(UTC) - timedelta(hours=1)
    records[0].refresh_token = "personal-refresh"
    sdk = MagicMock()
    sdk.refresh_token = AsyncMock(return_value={"access_token": "refreshed", "expires_in": 3600})
    monkeypatch.setattr("src.services.oauth.jira_oauth.JiraOAuth", lambda **k: sdk)
    # Only the app client secret is decoded in the module; retain actual token encryption.
    credentials = await CredentialResolver(context).get_jira_credentials("tool")
    assert credentials["access_token"] == "refreshed" and credentials["cloud_id"] == "personal-cloud"
