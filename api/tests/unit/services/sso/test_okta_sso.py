"""Unit tests for OktaSSOService OIDC methods."""

from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest

from src.services.sso.okta_sso import OktaSSOService


def _svc(**kwargs):
    defaults = {
        "domain": "mycompany.okta.com",
        "client_id": "client-abc",
        "client_secret": "secret-xyz",
        "redirect_uri": "https://app.example.com/callback",
    }
    defaults.update(kwargs)
    return OktaSSOService(**defaults)


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOktaSSOServiceInit:
    def test_stores_domain(self):
        svc = _svc(domain="acme.okta.com")
        assert svc.domain == "acme.okta.com"

    def test_oidc_endpoint_urls_use_domain(self):
        svc = _svc(domain="acme.okta.com")
        assert "acme.okta.com" in svc._auth_url
        assert "acme.okta.com" in svc._token_url
        assert "acme.okta.com" in svc._user_info_url
        assert "acme.okta.com" in svc._revoke_url

    def test_optional_fields_default_none(self):
        svc = OktaSSOService(domain="x.okta.com")
        assert svc.client_id is None
        assert svc.client_secret is None
        assert svc.redirect_uri is None
        assert svc.saml_settings is None


# ---------------------------------------------------------------------------
# get_oidc_authorization_url
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetOIDCAuthorizationUrl:
    def test_returns_url_containing_auth_endpoint(self):
        svc = _svc()
        url = svc.get_oidc_authorization_url()
        assert "mycompany.okta.com" in url
        assert "oauth2/v1/authorize" in url

    def test_url_contains_client_id(self):
        svc = _svc(client_id="my-client-id")
        url = svc.get_oidc_authorization_url()
        qs = parse_qs(urlparse(url).query)
        assert qs["client_id"] == ["my-client-id"]

    def test_url_contains_redirect_uri(self):
        svc = _svc(redirect_uri="https://app.example.com/cb")
        url = svc.get_oidc_authorization_url()
        qs = parse_qs(urlparse(url).query)
        assert qs["redirect_uri"] == ["https://app.example.com/cb"]

    def test_default_scopes_openid_email_profile(self):
        svc = _svc()
        url = svc.get_oidc_authorization_url()
        qs = parse_qs(urlparse(url).query)
        scopes = set(qs["scope"][0].split())
        assert {"openid", "email", "profile"} == scopes

    def test_custom_scopes(self):
        svc = _svc()
        url = svc.get_oidc_authorization_url(scopes=["openid", "groups"])
        qs = parse_qs(urlparse(url).query)
        scopes = set(qs["scope"][0].split())
        assert scopes == {"openid", "groups"}

    def test_state_included_when_provided(self):
        svc = _svc()
        url = svc.get_oidc_authorization_url(state="csrf-token-abc")
        qs = parse_qs(urlparse(url).query)
        assert qs["state"] == ["csrf-token-abc"]

    def test_state_absent_when_not_provided(self):
        svc = _svc()
        url = svc.get_oidc_authorization_url()
        qs = parse_qs(urlparse(url).query)
        assert "state" not in qs

    def test_response_type_is_code(self):
        svc = _svc()
        url = svc.get_oidc_authorization_url()
        qs = parse_qs(urlparse(url).query)
        assert qs["response_type"] == ["code"]

    def test_missing_client_id_raises_value_error(self):
        svc = OktaSSOService(domain="x.okta.com", redirect_uri="https://app.example.com/cb")
        with pytest.raises(ValueError, match="client_id"):
            svc.get_oidc_authorization_url()

    def test_missing_redirect_uri_raises_value_error(self):
        svc = OktaSSOService(domain="x.okta.com", client_id="cid")
        with pytest.raises(ValueError, match="redirect_uri"):
            svc.get_oidc_authorization_url()


# ---------------------------------------------------------------------------
# get_oidc_access_token
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetOIDCAccessToken:
    @pytest.mark.asyncio
    async def test_returns_token_response_on_success(self):
        svc = _svc()
        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "tok-abc", "token_type": "Bearer"}

        with patch("src.services.sso.okta_sso.request_checked_url", new_callable=AsyncMock) as request:
            request.configure_mock(return_value=mock_response)

            result = await svc.get_oidc_access_token("auth-code-123")

        assert result["access_token"] == "tok-abc"

    @pytest.mark.asyncio
    async def test_raises_on_error_response(self):
        svc = _svc()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "error": "invalid_grant",
            "error_description": "Authorization code expired",
        }

        with patch("src.services.sso.okta_sso.request_checked_url", new_callable=AsyncMock) as request:
            request.configure_mock(return_value=mock_response)

            with pytest.raises(ValueError, match="Authorization code expired"):
                await svc.get_oidc_access_token("bad-code")

    @pytest.mark.asyncio
    async def test_posts_to_token_url(self):
        svc = _svc()
        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "tok"}

        with patch("src.services.sso.okta_sso.request_checked_url", new_callable=AsyncMock) as request:
            request.configure_mock(return_value=mock_response)

            await svc.get_oidc_access_token("code")

        call_url = request.call_args[0][1]
        assert "oauth2/v1/token" in call_url

    @pytest.mark.asyncio
    async def test_missing_credentials_raises(self):
        svc = OktaSSOService(domain="x.okta.com", client_id="cid")
        with pytest.raises(ValueError, match="client_secret"):
            await svc.get_oidc_access_token("code")


# ---------------------------------------------------------------------------
# get_oidc_user_info
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetOIDCUserInfo:
    @pytest.mark.asyncio
    async def test_returns_user_info(self):
        svc = _svc()
        user_data = {"sub": "user-123", "email": "alice@example.com", "name": "Alice"}
        mock_response = MagicMock()
        mock_response.json.return_value = user_data
        mock_response.raise_for_status = MagicMock()

        with patch("src.services.sso.okta_sso.request_checked_url", new_callable=AsyncMock) as request:
            request.configure_mock(return_value=mock_response)

            result = await svc.get_oidc_user_info("access-token-xyz")

        assert result["email"] == "alice@example.com"

    @pytest.mark.asyncio
    async def test_sends_bearer_auth_header(self):
        svc = _svc()
        mock_response = MagicMock()
        mock_response.json.return_value = {"sub": "u"}
        mock_response.raise_for_status = MagicMock()

        with patch("src.services.sso.okta_sso.request_checked_url", new_callable=AsyncMock) as request:
            request.configure_mock(return_value=mock_response)

            await svc.get_oidc_user_info("my-token")

        headers = request.call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer my-token"


# ---------------------------------------------------------------------------
# refresh_oidc_token
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRefreshOIDCToken:
    @pytest.mark.asyncio
    async def test_returns_new_tokens_on_success(self):
        svc = _svc()
        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "new-tok", "id_token": "new-id"}

        with patch("src.services.sso.okta_sso.request_checked_url", new_callable=AsyncMock) as request:
            request.configure_mock(return_value=mock_response)

            result = await svc.refresh_oidc_token("refresh-tok")

        assert result["access_token"] == "new-tok"

    @pytest.mark.asyncio
    async def test_raises_on_error_in_response(self):
        svc = _svc()
        mock_response = MagicMock()
        mock_response.json.return_value = {"error": "invalid_grant", "error_description": "Token expired"}

        with patch("src.services.sso.okta_sso.request_checked_url", new_callable=AsyncMock) as request:
            request.configure_mock(return_value=mock_response)

            with pytest.raises(ValueError, match="Token expired"):
                await svc.refresh_oidc_token("bad-refresh")

    @pytest.mark.asyncio
    async def test_missing_client_secret_raises(self):
        svc = OktaSSOService(domain="x.okta.com", client_id="cid")
        with pytest.raises(ValueError, match="client_secret"):
            await svc.refresh_oidc_token("tok")


# ---------------------------------------------------------------------------
# revoke_oidc_token
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRevokeOIDCToken:
    @pytest.mark.asyncio
    async def test_returns_true_on_200(self):
        svc = _svc()
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("src.services.sso.okta_sso.request_checked_url", new_callable=AsyncMock) as request:
            request.configure_mock(return_value=mock_response)

            result = await svc.revoke_oidc_token("tok")

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_on_non_200(self):
        svc = _svc()
        mock_response = MagicMock()
        mock_response.status_code = 400

        with patch("src.services.sso.okta_sso.request_checked_url", new_callable=AsyncMock) as request:
            request.configure_mock(return_value=mock_response)

            result = await svc.revoke_oidc_token("bad-tok")

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_exception(self):
        svc = _svc()
        with patch("src.services.sso.okta_sso.request_checked_url", new_callable=AsyncMock) as request:
            request.configure_mock(side_effect=ConnectionError("network down"))

            result = await svc.revoke_oidc_token("tok")

        assert result is False

    @pytest.mark.asyncio
    async def test_default_token_type_hint_is_access_token(self):
        svc = _svc()
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("src.services.sso.okta_sso.request_checked_url", new_callable=AsyncMock) as request:
            request.configure_mock(return_value=mock_response)

            await svc.revoke_oidc_token("tok")

        post_data = request.call_args[1]["data"]
        assert post_data["token_type_hint"] == "access_token"

    @pytest.mark.asyncio
    async def test_missing_credentials_returns_false(self):
        svc = OktaSSOService(domain="x.okta.com", client_id="cid")
        result = await svc.revoke_oidc_token("tok")
        assert result is False


# ---------------------------------------------------------------------------
# validate_domain / get_oidc_configuration
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestValidateDomain:
    @pytest.mark.asyncio
    async def test_returns_true_on_200(self):
        svc = _svc()
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("src.services.sso.okta_sso.request_checked_url", new_callable=AsyncMock) as request:
            request.configure_mock(return_value=mock_response)

            result = await svc.validate_domain()

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_on_non_200(self):
        svc = _svc()
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("src.services.sso.okta_sso.request_checked_url", new_callable=AsyncMock) as request:
            request.configure_mock(return_value=mock_response)

            result = await svc.validate_domain()

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_network_error(self):
        svc = _svc()
        with patch("src.services.sso.okta_sso.request_checked_url", new_callable=AsyncMock) as request:
            request.configure_mock(side_effect=ConnectionError("timeout"))

            result = await svc.validate_domain()

        assert result is False


@pytest.mark.unit
class TestGetOIDCConfiguration:
    @pytest.mark.asyncio
    async def test_returns_configuration_dict(self):
        svc = _svc()
        config_data = {"issuer": "https://mycompany.okta.com", "token_endpoint": "https://..."}
        mock_response = MagicMock()
        mock_response.json.return_value = config_data
        mock_response.raise_for_status = MagicMock()

        with patch("src.services.sso.okta_sso.request_checked_url", new_callable=AsyncMock) as request:
            request.configure_mock(return_value=mock_response)

            result = await svc.get_oidc_configuration()

        assert result["issuer"] == "https://mycompany.okta.com"

    @pytest.mark.asyncio
    async def test_raises_value_error_on_http_error(self):
        svc = _svc()
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("503 Service Unavailable")

        with patch("src.services.sso.okta_sso.request_checked_url", new_callable=AsyncMock) as request:
            request.configure_mock(return_value=mock_response)

            with pytest.raises(ValueError, match="Failed to get OIDC configuration"):
                await svc.get_oidc_configuration()


# ---------------------------------------------------------------------------
# SAML – no real SAML lib calls, just guard rails
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSAMLGuards:
    def test_get_saml_auth_raises_when_no_settings(self):
        svc = OktaSSOService(domain="x.okta.com")
        with pytest.raises(ValueError, match="SAML settings"):
            svc.get_saml_auth({})

    def test_process_saml_logout_response_returns_false_on_exception(self):
        svc = OktaSSOService(domain="x.okta.com", saml_settings={"sp": {}})
        # get_saml_auth itself will fail (invalid settings for OneLogin),
        # but the method should catch and return False
        result = svc.process_saml_logout_response({})
        assert result is False
