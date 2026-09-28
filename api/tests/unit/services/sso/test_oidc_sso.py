"""Unit tests for OIDCSSOService."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(
    *,
    discovery_url: str | None = None,
    authorization_endpoint: str | None = "https://idp.example.com/oauth2/authorize",
    token_endpoint: str | None = "https://idp.example.com/oauth2/token",
    userinfo_endpoint: str | None = "https://idp.example.com/oauth2/userinfo",
    jwks_uri: str | None = None,
    email_claim: str = "email",
    name_claim: str = "name",
    auto_provision: bool = True,
    is_enabled: bool = True,
    scopes: str = "openid email profile",
    client_id: str = "client-abc",
    client_secret: str = "encrypted-secret",
) -> MagicMock:
    cfg = MagicMock()
    cfg.discovery_url = discovery_url
    cfg.authorization_endpoint = authorization_endpoint
    cfg.token_endpoint = token_endpoint
    cfg.userinfo_endpoint = userinfo_endpoint
    cfg.jwks_uri = jwks_uri
    cfg.email_claim = email_claim
    cfg.name_claim = name_claim
    cfg.auto_provision = auto_provision
    cfg.is_enabled = is_enabled
    cfg.scopes = scopes
    cfg.client_id = client_id
    cfg.client_secret = client_secret
    return cfg


def _make_svc(**kwargs):
    from src.services.sso.oidc_sso import OIDCSSOService

    return OIDCSSOService(_make_config(**kwargs))


# ---------------------------------------------------------------------------
# _discover — manual endpoints
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDiscover:
    @pytest.mark.asyncio
    async def test_uses_manual_endpoints_when_no_discovery_url(self):
        svc = _make_svc(
            discovery_url=None,
            authorization_endpoint="https://idp.example.com/auth",
            token_endpoint="https://idp.example.com/token",
            userinfo_endpoint="https://idp.example.com/userinfo",
        )
        doc = await svc._discover()
        assert doc["authorization_endpoint"] == "https://idp.example.com/auth"
        assert doc["token_endpoint"] == "https://idp.example.com/token"
        assert doc["userinfo_endpoint"] == "https://idp.example.com/userinfo"

    @pytest.mark.asyncio
    async def test_fetches_discovery_url_when_set(self):
        from src.services.sso.oidc_sso import OIDCSSOService

        cfg = _make_config(
            discovery_url="https://idp.example.com/.well-known/openid-configuration",
        )
        svc = OIDCSSOService(cfg)

        discovery_doc = {
            "authorization_endpoint": "https://idp.example.com/auth",
            "token_endpoint": "https://idp.example.com/token",
            "userinfo_endpoint": "https://idp.example.com/userinfo",
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = discovery_doc
        mock_resp.raise_for_status = MagicMock()

        with patch("src.services.sso.oidc_sso.request_checked_url", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_resp
            doc = await svc._discover()

        assert doc["authorization_endpoint"] == "https://idp.example.com/auth"
        mock_req.assert_called_once()

    @pytest.mark.asyncio
    async def test_discovery_result_is_cached(self):
        from src.services.sso.oidc_sso import OIDCSSOService

        cfg = _make_config(discovery_url="https://idp.example.com/.well-known/openid-configuration")
        svc = OIDCSSOService(cfg)

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "authorization_endpoint": "https://a",
            "token_endpoint": "https://b",
            "userinfo_endpoint": "https://c",
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("src.services.sso.oidc_sso.request_checked_url", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_resp
            await svc._discover()
            await svc._discover()

        # Should only make one network call
        assert mock_req.call_count == 1


# ---------------------------------------------------------------------------
# get_authorization_url
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetAuthorizationUrl:
    @pytest.mark.asyncio
    async def test_builds_correct_url_with_state_and_scope(self):
        svc = _make_svc(
            scopes="openid email profile",
            client_id="my-client",
        )
        url = await svc.get_authorization_url(
            redirect_uri="https://app.example.com/callback",
            state="csrf-abc",
        )
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)

        assert parsed.scheme == "https"
        assert qs["response_type"] == ["code"]
        assert qs["client_id"] == ["my-client"]
        assert qs["redirect_uri"] == ["https://app.example.com/callback"]
        assert qs["state"] == ["csrf-abc"]
        scopes = set(qs["scope"][0].split())
        assert scopes == {"openid", "email", "profile"}

    @pytest.mark.asyncio
    async def test_raises_when_no_authorization_endpoint(self):
        svc = _make_svc(
            discovery_url=None,
            authorization_endpoint=None,
        )
        with pytest.raises(ValueError, match="authorization_endpoint"):
            await svc.get_authorization_url(
                redirect_uri="https://app.example.com/cb",
                state="s",
            )

    @pytest.mark.asyncio
    async def test_custom_scopes_used(self):
        svc = _make_svc(scopes="openid groups admin")
        url = await svc.get_authorization_url(
            redirect_uri="https://app.example.com/cb",
            state="st",
        )
        qs = parse_qs(urlparse(url).query)
        assert set(qs["scope"][0].split()) == {"openid", "groups", "admin"}


# ---------------------------------------------------------------------------
# extract_user_attributes
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExtractUserAttributes:
    def test_uses_configured_email_claim(self):
        svc = _make_svc(email_claim="upn", name_claim="displayName")
        attrs = svc.extract_user_attributes({"upn": "alice@corp.example.com", "displayName": "Alice Smith"})
        assert attrs["email"] == "alice@corp.example.com"
        assert attrs["name"] == "Alice Smith"

    def test_falls_back_to_email_key(self):
        svc = _make_svc(email_claim="nonexistent_claim")
        attrs = svc.extract_user_attributes({"email": "bob@example.com", "name": "Bob"})
        assert attrs["email"] == "bob@example.com"

    def test_email_is_lowercased_and_stripped(self):
        svc = _make_svc()
        attrs = svc.extract_user_attributes({"email": "  ALICE@Example.COM  ", "name": "Alice"})
        assert attrs["email"] == "alice@example.com"

    def test_raises_when_no_email_claim_present(self):
        svc = _make_svc(email_claim="upn")
        with pytest.raises(ValueError, match="No email found"):
            svc.extract_user_attributes({"name": "Alice"})

    def test_uses_configured_name_claim(self):
        svc = _make_svc(name_claim="preferred_username")
        attrs = svc.extract_user_attributes({"email": "a@b.com", "preferred_username": "alice42"})
        assert attrs["name"] == "alice42"

    def test_falls_back_to_name_key(self):
        svc = _make_svc(name_claim="displayName")
        attrs = svc.extract_user_attributes({"email": "a@b.com", "name": "Alice"})
        assert attrs["name"] == "Alice"


# ---------------------------------------------------------------------------
# provision_or_get_account
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestProvisionOrGetAccount:
    @pytest.mark.asyncio
    async def test_creates_account_when_not_found(self):
        import uuid as _uuid

        svc = _make_svc(auto_provision=True)

        tenant_id = _uuid.uuid4()
        email = "newuser@example.com"
        name = "New User"

        db = AsyncMock()
        # First execute (account lookup) → None; second (membership lookup) → None
        execute_result = MagicMock()
        execute_result.scalar_one_or_none = MagicMock(side_effect=[None, None])
        db.execute = AsyncMock(return_value=execute_result)

        await svc.provision_or_get_account(db, tenant_id, email, name)

        # db.add should have been called twice: once for Account, once for TenantAccountJoin
        assert db.add.call_count == 2

        # The first added object should be an Account with the right attributes
        first_added = db.add.call_args_list[0][0][0]
        assert first_added.email == email.lower()
        assert first_added.name == name
        # OIDC-provisioned accounts have no password
        assert first_added.password_hash == ""

    @pytest.mark.asyncio
    async def test_raises_when_auto_provision_false_and_account_missing(self):
        import uuid as _uuid

        svc = _make_svc(auto_provision=False)

        db = AsyncMock()
        db.execute.return_value.scalar_one_or_none = MagicMock(return_value=None)

        with pytest.raises(ValueError, match="auto-provisioning is disabled"):
            await svc.provision_or_get_account(db, _uuid.uuid4(), "nobody@example.com", "Nobody")

    @pytest.mark.asyncio
    async def test_returns_existing_account_without_creating(self):
        import uuid as _uuid

        svc = _make_svc(auto_provision=True)

        existing_account = MagicMock()
        existing_account.id = _uuid.uuid4()

        existing_membership = MagicMock()

        db = AsyncMock()
        db.execute.return_value.scalar_one_or_none = MagicMock(side_effect=[existing_account, existing_membership])

        result = await svc.provision_or_get_account(db, _uuid.uuid4(), "existing@example.com", "Existing")

        # No new objects should be added to the session
        db.add.assert_not_called()
        assert result is existing_account

    @pytest.mark.asyncio
    async def test_raises_when_auto_provision_false_and_not_tenant_member(self):
        import uuid as _uuid

        svc = _make_svc(auto_provision=False)

        existing_account = MagicMock()
        existing_account.id = _uuid.uuid4()

        db = AsyncMock()
        # Account exists, but no membership
        db.execute.return_value.scalar_one_or_none = MagicMock(side_effect=[existing_account, None])

        with pytest.raises(ValueError, match="auto-provisioning is disabled"):
            await svc.provision_or_get_account(db, _uuid.uuid4(), "existing@example.com", "E")


# ---------------------------------------------------------------------------
# exchange_code
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExchangeCode:
    @pytest.mark.asyncio
    async def test_posts_to_token_endpoint_and_returns_dict(self):
        svc = _make_svc(client_id="cid", client_secret="encrypted-s3cret")

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"access_token": "at-123", "token_type": "Bearer"}
        mock_resp.raise_for_status = MagicMock()

        with (
            patch("src.services.sso.oidc_sso.request_checked_url", new_callable=AsyncMock) as mock_req,
            patch("src.services.agents.security.decrypt_value", return_value="plaintext-secret"),
        ):
            mock_req.return_value = mock_resp
            result = await svc.exchange_code(code="auth-code", redirect_uri="https://app/cb")

        assert result["access_token"] == "at-123"
        call_data = mock_req.call_args[1]["data"]
        assert call_data["grant_type"] == "authorization_code"
        assert call_data["code"] == "auth-code"
        assert call_data["client_secret"] == "plaintext-secret"

    @pytest.mark.asyncio
    async def test_raises_when_no_token_endpoint(self):
        svc = _make_svc(discovery_url=None, token_endpoint=None)

        with pytest.raises(ValueError, match="token_endpoint"):
            await svc.exchange_code(code="c", redirect_uri="https://r")


# ---------------------------------------------------------------------------
# get_user_info
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetUserInfo:
    @pytest.mark.asyncio
    async def test_sends_bearer_auth_and_returns_userinfo(self):
        svc = _make_svc()

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"email": "alice@example.com", "name": "Alice"}
        mock_resp.raise_for_status = MagicMock()

        with patch("src.services.sso.oidc_sso.request_checked_url", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_resp
            result = await svc.get_user_info("my-access-token")

        headers = mock_req.call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer my-access-token"
        assert result["email"] == "alice@example.com"

    @pytest.mark.asyncio
    async def test_raises_when_no_userinfo_endpoint(self):
        svc = _make_svc(discovery_url=None, userinfo_endpoint=None)

        with pytest.raises(ValueError, match="userinfo_endpoint"):
            await svc.get_user_info("tok")
