"""
Intercom OAuth 2.0 Implementation.

Standard OAuth flow. Token response returns `token` (not `access_token`).
"""

import logging
import urllib.parse
from typing import Any

from .http_client import get_httpx_client

logger = logging.getLogger(__name__)

_AUTH_URL = "https://app.intercom.com/oauth"
_TOKEN_URL = "https://api.intercom.io/auth/eagle/token"
_USER_INFO_URL = "https://api.intercom.io/me"


class IntercomOAuth:
    """Intercom OAuth 2.0 authentication handler."""

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    def get_authorization_url(self, state: str | None = None, scopes: list[str] | None = None) -> str:
        # Intercom doesn't use scope in the URL — scopes are configured in the developer app
        params: dict[str, str] = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
        }
        if state:
            params["state"] = state
        return f"{_AUTH_URL}?{urllib.parse.urlencode(params)}"

    async def get_access_token(self, code: str) -> dict[str, Any]:
        client = await get_httpx_client()
        response = await client.post(
            _TOKEN_URL,
            json={
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        data = response.json()
        if response.status_code != 200:
            error = data.get("message", data.get("error", "Unknown error"))
            raise ValueError(f"Failed to get Intercom access token: {error}")

        # Intercom returns `token` — normalise to `access_token` for consistency
        if "token" in data and "access_token" not in data:
            data["access_token"] = data["token"]

        return data

    async def get_user_info(self, token: str) -> dict[str, Any]:
        client = await get_httpx_client()
        response = await client.get(
            _USER_INFO_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Intercom-Version": "2.11",
            },
        )
        response.raise_for_status()
        data = response.json()
        # /me returns the Admin object
        return {
            "id": str(data.get("id", "")),
            "email": data.get("email", ""),
            "name": data.get("name", ""),
            "app_id": (data.get("app") or {}).get("id_code", ""),
        }

    async def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        # Intercom tokens do not expire — refresh is a no-op
        logger.info("Intercom tokens do not expire — refresh is a no-op")
        return {}

    async def revoke_token(self, token: str) -> bool:
        # No public revocation endpoint — tokens are managed via developer console
        logger.info("Intercom token revocation requested — manage via Intercom developer console")
        return True
