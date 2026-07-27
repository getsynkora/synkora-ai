"""
Google Calendar OAuth implementation.

Handles OAuth 2.0 authentication flow for Google Calendar API access.
"""

import logging
from typing import Any

from .base_oauth import BaseOAuthService
from .http_client import get_aiohttp_session

logger = logging.getLogger(__name__)


class GoogleCalendarOAuth(BaseOAuthService):
    """Google Calendar OAuth provider."""

    SCOPES = [
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/userinfo.email",
        "openid",
    ]

    AUTHORIZATION_BASE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    REVOKE_URL = "https://oauth2.googleapis.com/revoke"

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        """
        Initialize Google Calendar OAuth provider.

        Args:
            client_id: Google OAuth client ID
            client_secret: Google OAuth client secret
            redirect_uri: OAuth redirect URI
        """
        super().__init__(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
        )
        self.scopes = self.SCOPES

    def get_authorization_url(self, state: str | None = None, scopes: list[str] | None = None) -> str:
        """
        Get OAuth authorization URL.

        Args:
            state: Optional state parameter for CSRF protection
            scopes: Optional custom scopes (uses default if not provided)

        Returns:
            Authorization URL
        """
        use_scopes = scopes or self.scopes

        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(use_scopes),
            "access_type": "offline",
            "prompt": "consent",
        }

        if state:
            params["state"] = state

        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{self.AUTHORIZATION_BASE_URL}?{query_string}"

    async def get_access_token(self, code: str) -> dict[str, Any]:
        """
        Exchange authorization code for access token.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            Token data including access_token, refresh_token, etc.
        """
        try:
            data = {
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
            }

            session = await get_aiohttp_session()
            async with session.post(
                self.TOKEN_URL, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}
            ) as response:
                if response.status != 200:
                    error_data = await response.text()
                    logger.warning(f"Google Calendar token exchange failed: {error_data}")
                    try:
                        import json as _json
                        err = _json.loads(error_data)
                        detail = err.get("error_description") or err.get("error") or error_data
                    except Exception:
                        detail = error_data
                    raise ValueError(f"Google Calendar OAuth error: {detail}")

                token_data = await response.json()
                logger.info("Successfully exchanged code for Google Calendar token")
                return token_data

        except Exception as e:
            logger.error(f"Failed to exchange code for token: {e}", exc_info=True)
            raise

    async def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        """
        Refresh access token using refresh token.

        Args:
            refresh_token: Refresh token

        Returns:
            New token data
        """
        try:
            data = {
                "refresh_token": refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "refresh_token",
            }

            session = await get_aiohttp_session()
            async with session.post(
                self.TOKEN_URL, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}
            ) as response:
                if response.status != 200:
                    error_data = await response.text()
                    logger.warning(f"Google Calendar token refresh failed: {error_data}")
                    raise ValueError(f"Failed to refresh token: {response.status}")

                token_data = await response.json()

                # Google doesn't return a new refresh token on refresh
                # Keep the original refresh token
                if "refresh_token" not in token_data:
                    token_data["refresh_token"] = refresh_token

                logger.info("Successfully refreshed Google Calendar access token")
                return token_data

        except Exception as e:
            logger.error(f"Failed to refresh access token: {e}", exc_info=True)
            raise

    async def revoke_token(self, token: str) -> bool:
        """
        Revoke access token.

        Args:
            token: Access token to revoke

        Returns:
            True if successful
        """
        try:
            session = await get_aiohttp_session()
            async with session.post(
                self.REVOKE_URL,
                data={"token": token},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ) as response:
                if response.status == 200:
                    logger.info("Successfully revoked Google Calendar token")
                    return True
                else:
                    error_data = await response.text()
                    logger.error(f"Failed to revoke token: {error_data}")
                    return False

        except Exception as e:
            logger.error(f"Error revoking token: {e}", exc_info=True)
            return False

    async def get_user_info(self, token: str) -> dict[str, Any]:
        """
        Get user information from Google.

        Args:
            token: Access token

        Returns:
            User information
        """
        try:
            session = await get_aiohttp_session()
            async with session.get(
                "https://www.googleapis.com/oauth2/v2/userinfo", headers={"Authorization": f"Bearer {token}"}
            ) as response:
                if response.status == 200:
                    user_info = await response.json()
                    logger.info(f"Retrieved user info for: {user_info.get('email')}")
                    return user_info
                else:
                    error_data = await response.text()
                    logger.error(f"Failed to get user info: {error_data}")
                    raise ValueError(f"Failed to get user info: {response.status}")

        except Exception as e:
            logger.error(f"Error getting user info: {e}", exc_info=True)
            raise
