"""
Zoho CRM OAuth Implementation.

Provides OAuth 2.0 authentication for Zoho CRM API access.
Token URLs are data-center-dependent (.com, .eu, .in, .com.au, .jp).
"""

import logging
import urllib.parse
from typing import Any

from .http_client import get_httpx_client

logger = logging.getLogger(__name__)

VALID_DATA_CENTERS = {"com", "eu", "in", "com.au", "jp"}


class ZohoCRMOAuth:
    """Zoho CRM OAuth 2.0 authentication handler."""

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str, data_center: str = "com"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.data_center = data_center if data_center in VALID_DATA_CENTERS else "com"

    def _accounts_url(self) -> str:
        return f"https://accounts.zoho.{self.data_center}"

    def get_authorization_url(self, state: str | None = None, scopes: list[str] | None = None) -> str:
        if scopes is None:
            scopes = [
                "ZohoCRM.modules.ALL",
                "ZohoCRM.settings.ALL",
                "ZohoCRM.users.READ",
                "ZohoCRM.org.READ",
                "offline_access",
            ]

        params: dict[str, str] = {
            "scope": ",".join(scopes),
            "client_id": self.client_id,
            "response_type": "code",
            "access_type": "offline",
            "redirect_uri": self.redirect_uri,
        }
        if state:
            params["state"] = state

        return f"{self._accounts_url()}/oauth/v2/auth?{urllib.parse.urlencode(params)}"

    async def get_access_token(self, code: str) -> dict[str, Any]:
        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "code": code,
        }
        client = await get_httpx_client()
        response = await client.post(
            f"{self._accounts_url()}/oauth/v2/token",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response_json = response.json()
        if response.status_code != 200 or "error" in response_json:
            error = response_json.get("error", "Unknown error")
            raise ValueError(f"Failed to get Zoho CRM access token: {error}")
        return response_json

    async def get_user_info(self, token: str) -> dict[str, Any]:
        client = await get_httpx_client()
        response = await client.get(
            f"{self._accounts_url()}/oauth/user/info",
            headers={"Authorization": f"Zoho-oauthtoken {token}", "Accept": "application/json"},
        )
        response.raise_for_status()
        data = response.json()
        return {
            "id": data.get("ZUID", ""),
            "email": data.get("Email", ""),
            "name": f"{data.get('First_Name', '')} {data.get('Last_Name', '')}".strip(),
            "data_center": self.data_center,
        }

    async def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
        }
        client = await get_httpx_client()
        response = await client.post(
            f"{self._accounts_url()}/oauth/v2/token",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response_json = response.json()
        if response.status_code != 200 or "error" in response_json:
            error = response_json.get("error", "Unknown error")
            raise ValueError(f"Failed to refresh Zoho CRM token: {error}")
        return response_json

    async def revoke_token(self, token: str) -> bool:
        try:
            client = await get_httpx_client()
            response = await client.post(
                f"{self._accounts_url()}/oauth/v2/token/revoke",
                params={"token": token},
            )
            return response.status_code == 200
        except Exception as exc:
            logger.warning("Failed to revoke Zoho CRM token: %s", exc)
            return False
