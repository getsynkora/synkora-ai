"""
Salesforce OAuth 2.0 Implementation.

Supports both production (login.salesforce.com) and sandbox (test.salesforce.com).
The instance_url is returned in the token response and stored in OAuthApp.config.
"""

import logging
import urllib.parse
from typing import Any

from .http_client import get_httpx_client

logger = logging.getLogger(__name__)

_DEFAULT_SCOPES = ["api", "refresh_token", "offline_access"]


class SalesforceOAuth:
    """Salesforce OAuth 2.0 authentication handler."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        is_sandbox: bool = False,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self._base = "https://test.salesforce.com" if is_sandbox else "https://login.salesforce.com"

    def get_authorization_url(self, state: str | None = None, scopes: list[str] | None = None) -> str:
        params: dict[str, str] = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(scopes or _DEFAULT_SCOPES),
        }
        if state:
            params["state"] = state
        return f"{self._base}/services/oauth2/authorize?{urllib.parse.urlencode(params)}"

    async def get_access_token(self, code: str) -> dict[str, Any]:
        client = await get_httpx_client()
        response = await client.post(
            f"{self._base}/services/oauth2/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        data = response.json()
        if response.status_code != 200:
            error = data.get("error_description", data.get("error", "Unknown error"))
            raise ValueError(f"Failed to get Salesforce access token: {error}")
        # Response includes: {access_token, refresh_token, instance_url, id, token_type, issued_at}
        return data

    async def get_user_info(self, token: str, instance_url: str | None = None) -> dict[str, Any]:
        base = (instance_url or self._base).rstrip("/")
        client = await get_httpx_client()
        response = await client.get(
            f"{base}/services/oauth2/userinfo",
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        data = response.json()
        return {
            "id": data.get("user_id", data.get("sub", "")),
            "email": data.get("email", ""),
            "name": data.get("name", data.get("display_name", "")),
            "instance_url": instance_url or "",
            "organization_id": data.get("organization_id", ""),
        }

    async def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        client = await get_httpx_client()
        response = await client.post(
            f"{self._base}/services/oauth2/token",
            data={
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        data = response.json()
        if response.status_code != 200:
            raise ValueError(f"Failed to refresh Salesforce token: {data.get('error_description', 'Unknown error')}")
        return data

    async def revoke_token(self, token: str) -> bool:
        try:
            client = await get_httpx_client()
            response = await client.post(
                f"{self._base}/services/oauth2/revoke",
                data={"token": token},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            return response.status_code in (200, 204)
        except Exception as e:
            logger.warning("Salesforce token revocation failed: %s", e)
            return False
