"""
HubSpot OAuth 2.0 Implementation.

Handles the standard OAuth flow for HubSpot.
Token URL uses application/x-www-form-urlencoded POST.
"""

import logging
import urllib.parse
from typing import Any

from .http_client import get_httpx_client

logger = logging.getLogger(__name__)

_AUTH_URL = "https://app.hubspot.com/oauth/authorize"
_TOKEN_URL = "https://api.hubapi.com/oauth/v1/token"
_USER_INFO_URL = "https://api.hubapi.com/oauth/v1/access-tokens/{token}"

_DEFAULT_SCOPES = [
    "crm.objects.tickets.read",
    "crm.objects.tickets.write",
    "crm.objects.contacts.read",
    "crm.objects.contacts.write",
    "oauth",
]


class HubSpotOAuth:
    """HubSpot OAuth 2.0 authentication handler."""

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    def get_authorization_url(self, state: str | None = None, scopes: list[str] | None = None) -> str:
        params: dict[str, str] = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(scopes or _DEFAULT_SCOPES),
        }
        if state:
            params["state"] = state
        return f"{_AUTH_URL}?{urllib.parse.urlencode(params)}"

    async def get_access_token(self, code: str) -> dict[str, Any]:
        client = await get_httpx_client()
        response = await client.post(
            _TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "code": code,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        data = response.json()
        if response.status_code != 200:
            error = data.get("message", data.get("error", "Unknown error"))
            raise ValueError(f"Failed to get HubSpot access token: {error}")
        return data  # {access_token, refresh_token, expires_in, token_type}

    async def get_user_info(self, token: str) -> dict[str, Any]:
        """Get info from the token introspection endpoint."""
        client = await get_httpx_client()
        response = await client.get(
            _USER_INFO_URL.format(token=token),
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        data = response.json()
        # Returns: {hub_id, user, scopes, hub_domain, app_id, ...}
        return {
            "id": str(data.get("hub_id", "")),
            "email": data.get("user", ""),
            "name": data.get("user", ""),
            "hub_id": data.get("hub_id"),
            "hub_domain": data.get("hub_domain", ""),
        }

    async def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        client = await get_httpx_client()
        response = await client.post(
            _TOKEN_URL,
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
            raise ValueError(f"Failed to refresh HubSpot token: {data.get('message', 'Unknown error')}")
        return data

    async def revoke_token(self, token: str) -> bool:
        try:
            client = await get_httpx_client()
            response = await client.delete(
                f"https://api.hubapi.com/oauth/v1/refresh-tokens/{token}",
                headers={"Authorization": f"Bearer {token}"},
            )
            return response.status_code in (200, 204)
        except Exception as e:
            logger.warning("HubSpot token revocation failed: %s", e)
            return False
