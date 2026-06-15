"""
Zendesk OAuth Implementation.

Provides OAuth 2.0 authentication for Zendesk API access.
Authorization URL is subdomain-dependent.
"""

import logging
import urllib.parse
from typing import Any

from .http_client import get_httpx_client

logger = logging.getLogger(__name__)


class ZendeskOAuth:
    """Zendesk OAuth 2.0 authentication handler."""

    _TOKEN_PATH = "/oauth/tokens"
    _USER_INFO_PATH = "/api/v2/users/me.json"

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str, subdomain: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.subdomain = subdomain.strip().rstrip("/")

    def _base_url(self) -> str:
        return f"https://{self.subdomain}.zendesk.com"

    def get_authorization_url(self, state: str | None = None, scopes: list[str] | None = None) -> str:
        if not self.subdomain:
            raise ValueError("Zendesk subdomain is required")

        if scopes is None:
            scopes = ["read", "write"]

        params: dict[str, str] = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(scopes),
        }
        if state:
            params["state"] = state

        return f"{self._base_url()}/oauth/authorizations/new?{urllib.parse.urlencode(params)}"

    async def get_access_token(self, code: str) -> dict[str, Any]:
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "scope": "read write",
        }
        client = await get_httpx_client()
        response = await client.post(
            f"{self._base_url()}{self._TOKEN_PATH}",
            json=data,
            headers={"Content-Type": "application/json"},
        )
        response_json = response.json()
        if response.status_code != 200:
            error = response_json.get("error_description", response_json.get("error", "Unknown error"))
            raise ValueError(f"Failed to get Zendesk access token: {error}")
        return response_json

    async def get_user_info(self, token: str) -> dict[str, Any]:
        client = await get_httpx_client()
        response = await client.get(
            f"{self._base_url()}{self._USER_INFO_PATH}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
        response.raise_for_status()
        data = response.json()
        # Zendesk wraps user in {"user": {...}}
        user = data.get("user", data)
        return {
            "id": str(user.get("id", "")),
            "email": user.get("email", ""),
            "name": user.get("name", ""),
            "subdomain": self.subdomain,
        }

    async def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        # Zendesk OAuth tokens do not expire and have no refresh mechanism.
        logger.info("Zendesk tokens do not expire — refresh is a no-op")
        return {}

    async def revoke_token(self, token: str) -> bool:
        # Zendesk does not provide a token revocation endpoint.
        logger.info("Zendesk token revocation requested — tokens expire naturally or via dashboard")
        return True
