import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.agents.credential_resolver import CredentialResolver
from src.services.agents.runtime_context import RuntimeContext


class TestCredentialResolver:
    @pytest.fixture
    def mock_db_session(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def runtime_context(self, mock_db_session):
        ctx = RuntimeContext(tenant_id=uuid.uuid4(), agent_id=uuid.uuid4(), db_session=mock_db_session)
        return ctx

    @pytest.fixture
    def resolver(self, runtime_context):
        return CredentialResolver(runtime_context)

    @pytest.mark.asyncio
    async def test_get_github_client_success(self, resolver, mock_db_session):
        # Mock AgentTool
        mock_tool = MagicMock()
        mock_tool.oauth_app_id = uuid.uuid4()

        # Mock OAuthApp
        mock_oauth_app = MagicMock()
        mock_oauth_app.auth_method = "oauth"
        mock_oauth_app.access_token = "encrypted_token"

        # Setup execute mock to return different results for sequential calls
        # First call: AgentTool query
        # Second call: OAuthApp query
        mock_result_tool = MagicMock()
        mock_result_tool.scalar_one_or_none.return_value = mock_tool

        mock_result_oauth = MagicMock()
        mock_result_oauth.scalar_one_or_none.return_value = mock_oauth_app

        mock_db_session.execute = AsyncMock(side_effect=[mock_result_tool, mock_result_oauth])

        with (
            patch("src.services.agents.security.decrypt_value", return_value="decrypted_token"),
            patch("github.Github") as MockGithub,
            patch.object(resolver, "_get_user_token", return_value=None),
        ):
            client = await resolver.get_github_client("test_tool")

            assert client is not None
            MockGithub.assert_called_once_with("decrypted_token")

    @pytest.mark.asyncio
    async def test_get_github_client_no_tool(self, resolver, mock_db_session):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        client = await resolver.get_github_client("test_tool")
        assert client is None

    @pytest.mark.asyncio
    async def test_get_github_context(self, resolver, mock_db_session):
        # Mock AgentTool and OAuthApp
        mock_tool = MagicMock()
        mock_tool.oauth_app_id = uuid.uuid4()

        mock_oauth_app = MagicMock()
        mock_oauth_app.config = {"organization": "test-org", "default_branch": "develop"}

        # Mock DB queries using execute
        mock_result_tool = MagicMock()
        mock_result_tool.scalar_one_or_none.return_value = mock_tool

        mock_result_oauth = MagicMock()
        mock_result_oauth.scalar_one_or_none.return_value = mock_oauth_app

        mock_db_session.execute = AsyncMock(side_effect=[mock_result_tool, mock_result_oauth])

        # Mock client and user
        mock_user = MagicMock()
        mock_user.login = "test-user"
        mock_client = MagicMock()
        mock_client.get_user.return_value = mock_user

        with patch.object(resolver, "get_github_client", return_value=mock_client):
            context = await resolver.get_github_context("test_tool")

            assert context["organization"] == "test-org"
            assert context["default_branch"] == "develop"
            assert context["username"] == "test-user"

    @pytest.mark.asyncio
    async def test_get_gmail_service(self, resolver, mock_db_session):
        import json

        # Mock AgentTool with oauth_app_id
        mock_agent_tool = MagicMock()
        mock_agent_tool.oauth_app_id = uuid.uuid4()
        mock_agent_tool.enabled = True

        # Mock OAuthApp with Gmail provider and credentials
        mock_oauth_app = MagicMock()
        mock_oauth_app.id = mock_agent_tool.oauth_app_id
        mock_oauth_app.provider = "gmail"
        mock_oauth_app.is_active = True
        mock_oauth_app.app_name = "Test Gmail App"
        mock_oauth_app.client_id = "test_client_id"
        mock_oauth_app.client_secret = "encrypted_secret"
        mock_oauth_app.access_token = "encrypted_creds_json"

        # Setup mock DB queries using execute
        mock_result_tool = MagicMock()
        mock_result_tool.scalar_one_or_none.return_value = mock_agent_tool

        mock_result_oauth = MagicMock()
        mock_result_oauth.scalar_one_or_none.return_value = mock_oauth_app

        mock_db_session.execute = AsyncMock(side_effect=[mock_result_tool, mock_result_oauth])

        # Gmail credentials JSON that decrypt_value will return
        gmail_creds = json.dumps(
            {
                "access_token": "ya29.test_token",
                "refresh_token": "refresh_test",
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": "test_client_id",
                "client_secret": "test_secret",
            }
        )

        # Mock _get_user_token_record to return None (use app token)
        with (
            patch.object(resolver, "_get_user_token_record", return_value=None),
            patch("src.services.agents.security.decrypt_value", return_value=gmail_creds),
            patch("googleapiclient.discovery.build") as mock_build,
        ):
            mock_build.return_value = MagicMock()

            service = await resolver.get_gmail_service("test_tool")

            assert service is not None
            mock_build.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_youtube_service(self, resolver, mock_db_session):
        mock_tool = MagicMock()
        mock_tool.config = {"YOUTUBE_API_KEY": "encrypted_key"}

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_tool
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with (
            patch("src.services.agents.security.decrypt_value", return_value="api_key"),
            patch("googleapiclient.discovery.build") as mock_build,
        ):
            service = await resolver.get_youtube_service("test_tool")

            assert service is not None
            mock_build.assert_called_with("youtube", "v3", developerKey="api_key")

    @pytest.mark.asyncio
    async def test_get_serpapi_key(self, resolver, mock_db_session):
        mock_tool = MagicMock()
        mock_tool.config = {"SERPAPI_KEY": "encrypted_key"}

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_tool
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with patch("src.services.agents.security.decrypt_value", return_value="real_key"):
            key = await resolver.get_serpapi_key("test_tool")
            assert key == "real_key"

    @pytest.mark.asyncio
    async def test_resolve_for_tool(self, resolver):
        with patch.object(resolver, "get_github_client", return_value="github_client") as mock_get_github:
            result = await resolver.resolve_for_tool("tool", "github")
            assert result == "github_client"
            mock_get_github.assert_called_with("tool")

    @pytest.mark.asyncio
    async def test_resolve_for_tool_unknown(self, resolver):
        result = await resolver.resolve_for_tool("tool", "unknown_type")
        assert result is None


class TestGetGitlabToken:
    """GitLabOAuth.refresh_token() was implemented but never called anywhere — expired
    GitLab tokens (they expire ~2h) just failed outright instead of refreshing."""

    @pytest.fixture
    def mock_db_session(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def runtime_context(self, mock_db_session):
        return RuntimeContext(tenant_id=uuid.uuid4(), agent_id=uuid.uuid4(), db_session=mock_db_session)

    @pytest.fixture
    def resolver(self, runtime_context):
        return CredentialResolver(runtime_context)

    @pytest.fixture
    def mock_oauth_app(self):
        app = MagicMock()
        app.id = uuid.uuid4()
        app.app_name = "My GitLab"
        app.auth_method = "oauth"
        app.config = {"base_url": "https://gitlab.com"}
        app.client_id = "client-id"
        app.client_secret = "encrypted-secret"
        app.redirect_uri = "https://app.example.com/callback"
        app.access_token = "encrypted-access-token"
        app.refresh_token = "encrypted-refresh-token"
        app.token_expires_at = None
        app.api_token = None
        return app

    def _mock_agent_tool_and_app_lookup(self, mock_db_session, mock_oauth_app):
        mock_tool = MagicMock()
        mock_tool.oauth_app_id = mock_oauth_app.id
        result_tool = MagicMock()
        result_tool.scalar_one_or_none.return_value = mock_tool
        result_app = MagicMock()
        result_app.scalar_one_or_none.return_value = mock_oauth_app
        mock_db_session.execute = AsyncMock(side_effect=[result_tool, result_app])

    @pytest.mark.asyncio
    async def test_returns_app_token_directly_when_not_expired(self, resolver, mock_db_session, mock_oauth_app):
        self._mock_agent_tool_and_app_lookup(mock_db_session, mock_oauth_app)

        with (
            patch.object(resolver, "_get_user_token_record", return_value=None),
            patch("src.services.agents.security.decrypt_value", return_value="plain-access-token"),
        ):
            token, base_url = await resolver.get_gitlab_token("internal_gitlab_tool")

        assert token == "plain-access-token"
        assert base_url == "https://gitlab.com"
        mock_db_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_refreshes_expired_app_token_and_persists_it(self, resolver, mock_db_session, mock_oauth_app):
        from datetime import UTC, datetime, timedelta

        mock_oauth_app.token_expires_at = datetime.now(UTC) - timedelta(minutes=5)
        self._mock_agent_tool_and_app_lookup(mock_db_session, mock_oauth_app)
        mock_db_session.commit = AsyncMock()

        mock_gitlab_oauth = AsyncMock()
        mock_gitlab_oauth.refresh_token = AsyncMock(
            return_value={"access_token": "new-access-token", "refresh_token": "new-refresh-token", "expires_in": 7200}
        )

        with (
            patch.object(resolver, "_get_user_token_record", return_value=None),
            patch("src.services.agents.security.decrypt_value", return_value="old-decrypted-refresh-token"),
            patch("src.services.agents.security.encrypt_value", side_effect=lambda v: f"enc:{v}"),
            patch("src.services.oauth.gitlab_oauth.GitLabOAuth", return_value=mock_gitlab_oauth),
        ):
            token, base_url = await resolver.get_gitlab_token("internal_gitlab_tool")

        assert token == "new-access-token"
        assert base_url == "https://gitlab.com"
        mock_gitlab_oauth.refresh_token.assert_awaited_once_with("old-decrypted-refresh-token")
        assert mock_oauth_app.access_token == "enc:new-access-token"
        assert mock_oauth_app.refresh_token == "enc:new-refresh-token"
        assert mock_oauth_app.token_expires_at is not None
        # OAuthApp.token_expires_at is a plain (non-tz) DateTime column — a tz-aware
        # value here makes asyncpg reject the write with a DataError at commit time
        # ("can't subtract offset-naive and offset-aware datetimes"). A mocked
        # oauth_app can't reproduce that failure itself, so this assertion is the
        # regression guard for it.
        assert mock_oauth_app.token_expires_at.tzinfo is None
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_invalid_grant_on_refresh_clears_token_and_returns_none(
        self, resolver, mock_db_session, mock_oauth_app
    ):
        from datetime import UTC, datetime, timedelta

        mock_oauth_app.token_expires_at = datetime.now(UTC) - timedelta(minutes=5)
        self._mock_agent_tool_and_app_lookup(mock_db_session, mock_oauth_app)
        mock_db_session.commit = AsyncMock()

        mock_gitlab_oauth = AsyncMock()
        mock_gitlab_oauth.refresh_token = AsyncMock(side_effect=ValueError("invalid_grant: token revoked"))

        with (
            patch.object(resolver, "_get_user_token_record", return_value=None),
            patch("src.services.agents.security.decrypt_value", return_value="stale-refresh-token"),
            patch("src.services.oauth.gitlab_oauth.GitLabOAuth", return_value=mock_gitlab_oauth),
        ):
            token, base_url = await resolver.get_gitlab_token("internal_gitlab_tool")

        assert (token, base_url) == (None, None)
        assert mock_oauth_app.access_token is None
        assert mock_oauth_app.token_expires_at is None

    @pytest.mark.asyncio
    async def test_refreshes_expired_user_token_without_double_encrypting(
        self, resolver, mock_db_session, mock_oauth_app
    ):
        """UserOAuthToken.access_token/.refresh_token are auto-encrypting properties —
        the new plaintext token must be assigned directly, never wrapped in encrypt_value
        (which would double-encrypt it, unlike OAuthApp's plain Text columns)."""
        from datetime import UTC, datetime, timedelta

        self._mock_agent_tool_and_app_lookup(mock_db_session, mock_oauth_app)
        mock_db_session.commit = AsyncMock()

        mock_user_token = MagicMock()
        mock_user_token.token_expires_at = datetime.now(UTC) - timedelta(minutes=5)
        mock_user_token.refresh_token = "plaintext-user-refresh-token"  # property getter already decrypts

        mock_gitlab_oauth = AsyncMock()
        mock_gitlab_oauth.refresh_token = AsyncMock(
            return_value={"access_token": "new-user-access-token", "expires_in": 7200}
        )

        # encrypt_value must NEVER be called on the user-token branch's new access token
        encrypt_spy = MagicMock(side_effect=lambda v: f"enc:{v}")

        with (
            patch.object(resolver, "_get_user_token_record", return_value=mock_user_token),
            patch("src.services.agents.security.decrypt_value", return_value="decrypted-client-secret"),
            patch("src.services.agents.security.encrypt_value", encrypt_spy),
            patch("src.services.oauth.gitlab_oauth.GitLabOAuth", return_value=mock_gitlab_oauth),
        ):
            token, base_url = await resolver.get_gitlab_token("internal_gitlab_tool")

        assert token == "new-user-access-token"
        mock_gitlab_oauth.refresh_token.assert_awaited_once_with("plaintext-user-refresh-token")
        # Assigned as plain text — the model's own setter property handles encryption.
        assert mock_user_token.access_token == "new-user-access-token"
        encrypt_spy.assert_not_called()


class TestGetJiraCredentials:
    """get_jira_credentials had the same missing-refresh gap as GitLab — Atlassian
    access tokens expire after 1 hour."""

    @pytest.fixture
    def mock_db_session(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def runtime_context(self, mock_db_session):
        return RuntimeContext(tenant_id=uuid.uuid4(), agent_id=uuid.uuid4(), db_session=mock_db_session)

    @pytest.fixture
    def resolver(self, runtime_context):
        return CredentialResolver(runtime_context)

    @pytest.fixture
    def mock_oauth_app(self):
        app = MagicMock()
        app.id = uuid.uuid4()
        app.app_name = "My Jira"
        app.auth_method = "oauth"
        app.config = {"cloud_id": "cloud-123", "cloud_url": "https://myteam.atlassian.net"}
        app.client_id = "client-id"
        app.client_secret = "encrypted-secret"
        app.redirect_uri = "https://app.example.com/callback"
        app.access_token = "encrypted-access-token"
        app.refresh_token = "encrypted-refresh-token"
        app.token_expires_at = None
        app.api_token = None
        return app

    def _mock_agent_tool_and_app_lookup(self, mock_db_session, mock_oauth_app):
        mock_tool = MagicMock()
        mock_tool.oauth_app_id = mock_oauth_app.id
        result_tool = MagicMock()
        result_tool.scalar_one_or_none.return_value = mock_tool
        result_app = MagicMock()
        result_app.scalar_one_or_none.return_value = mock_oauth_app
        mock_db_session.execute = AsyncMock(side_effect=[result_tool, result_app])

    @pytest.mark.asyncio
    async def test_refreshes_expired_app_token_and_persists_it(self, resolver, mock_db_session, mock_oauth_app):
        from datetime import UTC, datetime, timedelta

        mock_oauth_app.token_expires_at = datetime.now(UTC) - timedelta(minutes=5)
        self._mock_agent_tool_and_app_lookup(mock_db_session, mock_oauth_app)
        mock_db_session.commit = AsyncMock()

        mock_jira_oauth = AsyncMock()
        mock_jira_oauth.refresh_token = AsyncMock(
            return_value={"access_token": "new-jira-token", "refresh_token": "new-jira-refresh", "expires_in": 3600}
        )

        with (
            patch.object(resolver, "_get_user_token_record", return_value=None),
            patch("src.services.agents.security.decrypt_value", return_value="old-decrypted-refresh-token"),
            patch("src.services.agents.security.encrypt_value", side_effect=lambda v: f"enc:{v}"),
            patch("src.services.oauth.jira_oauth.JiraOAuth", return_value=mock_jira_oauth),
        ):
            credentials = await resolver.get_jira_credentials("internal_get_jira_issue")

        assert credentials["access_token"] == "new-jira-token"
        assert credentials["cloud_id"] == "cloud-123"
        mock_jira_oauth.refresh_token.assert_awaited_once_with("old-decrypted-refresh-token")
        assert mock_oauth_app.access_token == "enc:new-jira-token"
        # OAuthApp.token_expires_at is a plain (non-tz) DateTime column — regression
        # guard, see the matching GitLab test for why this must be naive.
        assert mock_oauth_app.token_expires_at.tzinfo is None
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_refresh_token_available_returns_none(self, resolver, mock_db_session, mock_oauth_app):
        from datetime import UTC, datetime, timedelta

        mock_oauth_app.token_expires_at = datetime.now(UTC) - timedelta(minutes=5)
        mock_oauth_app.refresh_token = None
        self._mock_agent_tool_and_app_lookup(mock_db_session, mock_oauth_app)

        with (
            patch.object(resolver, "_get_user_token_record", return_value=None),
            patch("src.services.agents.security.decrypt_value", return_value="unused"),
        ):
            credentials = await resolver.get_jira_credentials("internal_get_jira_issue")

        assert credentials is None


class TestResolveUserTokenValue:
    """Every OAuth provider callback (all 16 in src/controllers/oauth/) used to call
    encrypt_value() before assigning to UserOAuthToken.access_token/.refresh_token — but
    those are auto-encrypting properties, so this double-encrypted every personal OAuth
    connection ever saved. Some read paths here also called decrypt_value() a second time
    on top of the property's own decryption, which happened to cancel the double-encrypt
    out by accident for those rows. Both write-side bugs are now fixed at the source, but
    existing DB rows saved before the fix are still double-encrypted, so the read path
    must keep working for both old (double-encrypted) and new (correctly single-encrypted)
    rows without a data migration."""

    def test_returns_plaintext_value_unchanged_when_not_further_encrypted(self):
        """New rows: the property already decrypted once, giving real plaintext. A second
        decrypt attempt must fail (it's not valid ciphertext) and the plaintext must be
        returned as-is, not swallowed or corrupted."""
        from src.services.agents.credential_resolver import CredentialResolver

        plaintext = "glpat-realtoken1234567890"
        assert CredentialResolver._resolve_user_token_value(plaintext) == plaintext

    def test_unwraps_one_extra_layer_for_legacy_double_encrypted_rows(self):
        """Legacy rows: the stored value was encrypt_value(encrypt_value(real)). The
        property's own decryption already peels one layer by the time this helper sees
        it, leaving one layer of ciphertext — this must unwrap that remaining layer and
        return the original real plaintext."""
        from src.services.agents.credential_resolver import CredentialResolver
        from src.services.agents.security import encrypt_value

        real_token = "glpat-realtoken1234567890"
        # Simulates what the property getter hands back for a legacy double-encrypted
        # row: one layer of encryption already stripped by the property, one left.
        value_as_seen_by_helper = encrypt_value(real_token)

        assert CredentialResolver._resolve_user_token_value(value_as_seen_by_helper) == real_token

    def test_returns_none_for_none(self):
        from src.services.agents.credential_resolver import CredentialResolver

        assert CredentialResolver._resolve_user_token_value(None) is None


class TestUserOAuthTokenRoundTrip:
    """Integration-level proof against the real model + real encryption (not mocked) that
    both the old buggy save path and the newly-fixed save path resolve to the same
    plaintext via _get_user_token() — i.e. the fix doesn't require a data migration and
    doesn't break access to tokens saved before it shipped."""

    @pytest.mark.asyncio
    async def test_get_user_token_resolves_both_legacy_and_fixed_rows(self, async_db_session, tenant, account):
        from src.models.oauth_app import OAuthApp
        from src.models.user_oauth_token import UserOAuthToken
        from src.services.agents.security import encrypt_value

        real_token_legacy = "glpat-legacy-real-token"
        real_token_fixed = "glpat-fixed-real-token"

        oauth_app_legacy = OAuthApp(tenant_id=tenant.id, provider="gitlab", app_name="legacy-app", auth_method="oauth")
        oauth_app_fixed = OAuthApp(tenant_id=tenant.id, provider="gitlab", app_name="fixed-app", auth_method="oauth")
        async_db_session.add_all([oauth_app_legacy, oauth_app_fixed])
        await async_db_session.flush()

        legacy_row = UserOAuthToken(account_id=account.id, oauth_app_id=oauth_app_legacy.id)
        # Reproduces the old bug: encrypt_value() called before assigning to the
        # auto-encrypting property, i.e. double-encrypted at rest.
        legacy_row.access_token = encrypt_value(real_token_legacy)

        fixed_row = UserOAuthToken(account_id=account.id, oauth_app_id=oauth_app_fixed.id)
        # The fixed behavior: assign the real plaintext directly.
        fixed_row.access_token = real_token_fixed

        async_db_session.add_all([legacy_row, fixed_row])
        await async_db_session.commit()

        resolver_legacy = CredentialResolver(
            RuntimeContext(tenant_id=tenant.id, agent_id=uuid.uuid4(), db_session=async_db_session, user_id=account.id)
        )
        resolver_fixed = CredentialResolver(
            RuntimeContext(tenant_id=tenant.id, agent_id=uuid.uuid4(), db_session=async_db_session, user_id=account.id)
        )

        assert await resolver_legacy._get_user_token(oauth_app_legacy.id) == real_token_legacy
        assert await resolver_fixed._get_user_token(oauth_app_fixed.id) == real_token_fixed
