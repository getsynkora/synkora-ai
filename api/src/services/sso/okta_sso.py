"""
Okta SSO Implementation.

Provides SAML 2.0 and OIDC SSO authentication for Okta.
"""

import logging
import re
from typing import TYPE_CHECKING, Any

from src.services.security.public_http import request_checked_url

if TYPE_CHECKING:
    from onelogin.saml2.auth import OneLogin_Saml2_Auth

logger = logging.getLogger(__name__)


def validate_okta_domain(domain: str) -> str:
    """Only a DNS hostname, never URL syntax that can change the credential origin."""
    domain = domain.lower()
    if (
        len(domain) > 253
        or "." not in domain
        or not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in domain.split("."))
    ):
        raise ValueError("Okta domain must be a DNS hostname without a scheme, path or port")
    return domain


class OktaSSOService:
    """Okta SSO authentication handler supporting both SAML and OIDC."""

    def __init__(
        self,
        domain: str,
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_uri: str | None = None,
        saml_settings: dict[str, Any] | None = None,
    ):
        """
        Initialize Okta SSO service.

        Args:
            domain: Okta domain (e.g., 'mycompany.okta.com')
            client_id: OIDC client ID (for OIDC flow)
            client_secret: OIDC client secret (for OIDC flow)
            redirect_uri: OIDC redirect URI (for OIDC flow)
            saml_settings: SAML configuration dictionary (for SAML flow)
        """
        domain = validate_okta_domain(domain)
        self.domain = domain
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.saml_settings = saml_settings

        # OIDC endpoints
        self._auth_url = f"https://{domain}/oauth2/v1/authorize"
        self._token_url = f"https://{domain}/oauth2/v1/token"
        self._user_info_url = f"https://{domain}/oauth2/v1/userinfo"
        self._revoke_url = f"https://{domain}/oauth2/v1/revoke"

    # OIDC Methods

    def get_oidc_authorization_url(self, state: str | None = None, scopes: list[str] | None = None) -> str:
        """
        Get the Okta OIDC authorization URL.

        Args:
            state: Optional state parameter for CSRF protection
            scopes: List of OAuth scopes to request (default: openid, email, profile)

        Returns:
            Authorization URL
        """
        if not all([self.client_id, self.redirect_uri]):
            raise ValueError("client_id and redirect_uri are required for OIDC")

        if scopes is None:
            scopes = ["openid", "email", "profile"]

        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
        }

        if state:
            params["state"] = state

        from urllib.parse import urlencode

        return f"{self._auth_url}?{urlencode(params)}"

    async def get_oidc_access_token(self, code: str) -> dict[str, Any]:
        """
        Exchange OIDC authorization code for access token.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            Dictionary containing access_token, id_token, refresh_token, etc.

        Raises:
            ValueError: If token exchange fails
        """
        if not all([self.client_id, self.client_secret, self.redirect_uri]):
            raise ValueError("client_id, client_secret, and redirect_uri are required for OIDC")

        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
        }

        response = await request_checked_url("POST", self._token_url, data=data)
        response.raise_for_status()
        response_json = response.json()

        if "error" in response_json:
            error = response_json.get("error_description", response_json.get("error", "Unknown error"))
            raise ValueError(f"Failed to get access token: {error}")

        return response_json

    async def get_oidc_user_info(self, token: str) -> dict[str, Any]:
        """
        Get user information using OIDC access token.

        Args:
            token: Okta access token

        Returns:
            User information dictionary with:
            - sub: Okta user ID
            - email: User email
            - name: User display name
            - preferred_username: Username
        """
        headers = {"Authorization": f"Bearer {token}"}

        response = await request_checked_url("GET", self._user_info_url, headers=headers)
        response.raise_for_status()
        return response.json()

    async def refresh_oidc_token(self, refresh_token: str) -> dict[str, Any]:
        """
        Refresh an expired OIDC access token.

        Args:
            refresh_token: Refresh token

        Returns:
            Dictionary containing new access_token and id_token

        Raises:
            ValueError: If token refresh fails
        """
        if not all([self.client_id, self.client_secret]):
            raise ValueError("client_id and client_secret are required for OIDC")

        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        response = await request_checked_url("POST", self._token_url, data=data)
        response.raise_for_status()
        response_json = response.json()

        if "error" in response_json:
            error = response_json.get("error_description", response_json.get("error", "Unknown error"))
            raise ValueError(f"Failed to refresh token: {error}")

        return response_json

    async def revoke_oidc_token(self, token: str, token_type_hint: str = "access_token") -> bool:
        """
        Revoke an OIDC access or refresh token.

        Args:
            token: Access or refresh token to revoke
            token_type_hint: Type of token ('access_token' or 'refresh_token')

        Returns:
            True if successful, False otherwise
        """
        try:
            if not all([self.client_id, self.client_secret]):
                raise ValueError("client_id and client_secret are required for OIDC")

            data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "token": token,
                "token_type_hint": token_type_hint,
            }

            response = await request_checked_url("POST", self._revoke_url, data=data)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to revoke token: {e}")
            return False

    # SAML Methods

    def get_saml_auth(self, request_data: dict[str, Any]) -> "OneLogin_Saml2_Auth":
        """
        Get SAML authentication object.

        Args:
            request_data: Request data dictionary containing:
                - https: 'on' or 'off'
                - http_host: Host name
                - script_name: Script name
                - get_data: GET parameters
                - post_data: POST parameters

        Returns:
            SAML authentication object

        Raises:
            ValueError: If SAML settings are not configured
        """
        if not self.saml_settings:
            raise ValueError("SAML settings are required for SAML authentication")

        from onelogin.saml2.auth import OneLogin_Saml2_Auth

        return OneLogin_Saml2_Auth(request_data, self.saml_settings)

    def get_saml_login_url(self, request_data: dict[str, Any]) -> str:
        """
        Get SAML login URL.

        Args:
            request_data: Request data dictionary

        Returns:
            SAML login URL
        """
        auth = self.get_saml_auth(request_data)
        return auth.login()

    def process_saml_response(self, request_data: dict[str, Any]) -> dict[str, Any]:
        """
        Process SAML response and extract user information.

        Args:
            request_data: Request data dictionary containing SAML response

        Returns:
            User information dictionary with:
            - id: User ID (NameID)
            - email: User email
            - name: User display name
            - attributes: Additional SAML attributes

        Raises:
            ValueError: If SAML response is invalid
        """
        auth = self.get_saml_auth(request_data)
        auth.process_response()

        errors = auth.get_errors()
        if errors:
            error_reason = auth.get_last_error_reason()
            raise ValueError(f"SAML authentication failed: {error_reason}")

        if not auth.is_authenticated():
            raise ValueError("SAML authentication failed: User not authenticated")

        attributes = auth.get_attributes()
        name_id = auth.get_nameid()

        return {
            "id": name_id,
            "email": attributes.get("email", [name_id])[0] if attributes.get("email") else name_id,
            "name": attributes.get("name", [""])[0] if attributes.get("name") else "",
            "attributes": attributes,
        }

    def get_saml_logout_url(self, request_data: dict[str, Any], name_id: str | None = None) -> str:
        """
        Get SAML logout URL.

        Args:
            request_data: Request data dictionary
            name_id: User's NameID (optional)

        Returns:
            SAML logout URL
        """
        auth = self.get_saml_auth(request_data)
        return auth.logout(name_id=name_id)

    def process_saml_logout_response(self, request_data: dict[str, Any]) -> bool:
        """
        Process SAML logout response.

        Args:
            request_data: Request data dictionary containing SAML logout response

        Returns:
            True if logout was successful, False otherwise
        """
        try:
            auth = self.get_saml_auth(request_data)
            auth.process_slo()

            errors = auth.get_errors()
            if errors:
                logger.error(f"SAML logout failed: {auth.get_last_error_reason()}")
                return False

            return True
        except Exception as e:
            logger.error(f"Failed to process SAML logout: {e}")
            return False

    # Utility Methods

    async def validate_domain(self) -> bool:
        """
        Validate that the Okta domain is accessible.

        Returns:
            True if domain is valid and accessible, False otherwise
        """
        try:
            response = await request_checked_url("GET", f"https://{self.domain}/.well-known/openid-configuration")
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Failed to validate Okta domain: {e}")
            return False

    async def get_oidc_configuration(self) -> dict[str, Any]:
        """
        Get OIDC configuration from Okta.

        Returns:
            OIDC configuration dictionary

        Raises:
            ValueError: If configuration cannot be retrieved
        """
        try:
            response = await request_checked_url("GET", f"https://{self.domain}/.well-known/openid-configuration")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise ValueError(f"Failed to get OIDC configuration: {e}")
