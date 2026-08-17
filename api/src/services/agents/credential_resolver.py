"""
Credential resolution without exposing secrets.

Returns authenticated clients, NOT raw credentials.
This is the ONLY place that handles credential decryption for tools.
"""

import logging
from datetime import UTC
from typing import Any

from sqlalchemy import select

logger = logging.getLogger(__name__)


class CredentialResolver:
    """
    Resolves and creates authenticated clients on-demand.

    Key principles:
    1. Never return raw credentials to callers
    2. Return authenticated, ready-to-use clients
    3. Decrypt credentials only when needed (lazy loading)
    4. One-time use per request (no caching across requests)
    5. User tokens take priority over OAuthApp tokens (user-first resolution)

    This class is the single source of truth for credential management.
    """

    def __init__(self, runtime_context):
        """
        Initialize credential resolver with runtime context.

        Args:
            runtime_context: RuntimeContext with tenant_id, agent_id, db_session
                             May also contain user_id for user-level token resolution
        """
        self.context = runtime_context
        self.db = runtime_context.db_session

    async def _get_user_token_record(self, oauth_app_id: int) -> Any | None:
        """
        Get user's personal token record if available.

        This implements user-first token resolution - if the current user
        has connected their own account, their token record is returned.

        Falls back to finding any user token for this oauth_app within the tenant
        when user_id is not available (e.g., Slack messages where we don't have
        a synkora account mapping).

        Args:
            oauth_app_id: ID of the OAuth app to check for user token

        Returns:
            UserOAuthToken record or None if not found
        """
        from src.models.user_oauth_token import UserOAuthToken

        try:
            # First, try user-specific token if user_id is available
            if hasattr(self.context, "user_id") and self.context.user_id:
                result = await self.db.execute(
                    select(UserOAuthToken).filter(
                        UserOAuthToken.account_id == self.context.user_id, UserOAuthToken.oauth_app_id == oauth_app_id
                    )
                )
                user_token = result.scalar_one_or_none()

                if user_token and user_token.access_token:
                    logger.info(
                        f"✅ Found user-level token record for user {self.context.user_id}, OAuth app {oauth_app_id}"
                    )
                    return user_token

            # Fallback: no user_id (e.g., Slack bot context). Scope strictly to the
            # current tenant so we never return a token belonging to a different tenant.
            if hasattr(self.context, "tenant_id") and self.context.tenant_id:
                from src.models.tenant import TenantAccountJoin

                result = await self.db.execute(
                    select(UserOAuthToken)
                    .join(TenantAccountJoin, TenantAccountJoin.account_id == UserOAuthToken.account_id)
                    .filter(
                        UserOAuthToken.oauth_app_id == oauth_app_id,
                        TenantAccountJoin.tenant_id == self.context.tenant_id,
                    )
                    .limit(1)
                )
            else:
                return None
            user_token = result.scalar_one_or_none()

            if user_token and user_token.access_token:
                logger.info(
                    f"✅ Found user-level token record by oauth_app_id {oauth_app_id} (user: {user_token.account_id})"
                )
                return user_token

        except Exception as e:
            logger.warning(f"Failed to get user token record: {e}")

        return None

    async def _get_user_token(self, oauth_app_id: int) -> str | None:
        """
        Get user's personal token (simple lookup without refresh).

        For tokens that need refresh support, use the provider-specific methods
        like get_google_calendar_token which handle refresh.

        Args:
            oauth_app_id: ID of the OAuth app to check for user token

        Returns:
            Decrypted access token string or None if not found
        """
        from src.services.agents.security import decrypt_value

        user_token_record = await self._get_user_token_record(oauth_app_id)
        if user_token_record and user_token_record.access_token:
            return decrypt_value(user_token_record.access_token)
        return None

    async def get_github_client(self, tool_name: str, owner: str | None = None, repo: str | None = None) -> Any | None:
        """
        Get authenticated GitHub client for a tool.

        Uses user-first resolution: checks for user's personal token first,
        then falls back to OAuthApp token.

        Args:
            tool_name: Name of the tool requesting GitHub access
            owner: Repository owner/org being accessed (required for GitHub Apps
                installed on multiple orgs, so the correct installation is used)
            repo: Repository name being accessed (used with owner)

        Returns:
            Authenticated Github client or None if not configured
        """
        from github import Github

        from src.models.agent_tool import AgentTool
        from src.models.oauth_app import OAuthApp
        from src.services.agents.security import decrypt_value

        # Find tool configuration
        result = await self.db.execute(
            select(AgentTool).filter(
                AgentTool.agent_id == self.context.agent_id, AgentTool.tool_name == tool_name, AgentTool.enabled
            )
        )
        agent_tool = result.scalar_one_or_none()

        if not agent_tool or not agent_tool.oauth_app_id:
            logger.warning(f"No GitHub OAuth configured for tool '{tool_name}' (agent: {self.context.agent_id})")
            return None

        # Get OAuth app
        result = await self.db.execute(
            select(OAuthApp).filter(
                OAuthApp.id == agent_tool.oauth_app_id, OAuthApp.provider == "github", OAuthApp.is_active
            )
        )
        oauth_app = result.scalar_one_or_none()

        if not oauth_app:
            logger.warning(f"GitHub OAuth app {agent_tool.oauth_app_id} not found or inactive")
            return None

        # Try user token first (user-first resolution)
        try:
            user_token = await self._get_user_token(oauth_app.id)
            if user_token:
                client = Github(user_token)
                logger.info(
                    f"✅ Created authenticated GitHub client for tool '{tool_name}' "
                    f"using user's personal token (OAuth app: '{oauth_app.app_name}')"
                )
                return client
        except Exception as e:
            logger.warning(f"Failed to use user token for GitHub: {e}")

        # Fall back to OAuthApp token
        try:
            token = None
            if oauth_app.auth_method == "oauth" and oauth_app.access_token:
                token = decrypt_value(oauth_app.access_token)
            elif oauth_app.auth_method == "api_token" and oauth_app.api_token:
                token = decrypt_value(oauth_app.api_token)
            elif oauth_app.auth_method == "github_app":
                # Generate installation access token from App ID + Private Key
                token = await self._get_github_app_installation_token(oauth_app, tool_name, owner=owner, repo=repo)

            if not token:
                logger.warning(f"No valid token for GitHub OAuth app {oauth_app.app_name}")
                return None

            # Create and return authenticated client
            # Token is consumed here and never returned
            client = Github(token)
            logger.info(
                f"✅ Created authenticated GitHub client for tool '{tool_name}' "
                f"using OAuth app '{oauth_app.app_name}' (auth_method: {oauth_app.auth_method}, fallback)"
            )
            return client

        except Exception as e:
            logger.error(f"Failed to create GitHub client: {e}", exc_info=True)
            return None

    async def _get_github_app_installation_token(
        self, oauth_app: Any, tool_name: str, owner: str | None = None, repo: str | None = None
    ) -> str | None:
        """
        Get a GitHub App installation access token.

        When `owner`/`repo` are provided, looks up the exact installation for that
        repository (GitHub Apps are commonly installed on multiple orgs/accounts, so
        picking "the first installation" would silently return a token scoped to the
        wrong org). Falls back to the first available installation only when no
        owner/repo context is available.
        """
        import time

        import httpx
        import jwt as pyjwt

        from src.services.agents.security import decrypt_value, normalize_pem_private_key

        try:
            app_id = oauth_app.client_id
            if not app_id or not oauth_app.client_secret:
                logger.warning(f"GitHub App {oauth_app.app_name} missing App ID or private key")
                return None

            private_key = normalize_pem_private_key(decrypt_value(oauth_app.client_secret))
            now = int(time.time())
            app_jwt = pyjwt.encode(
                {"iat": now - 60, "exp": now + 600, "iss": str(app_id)},
                private_key,
                algorithm="RS256",
            )

            headers = {
                "Authorization": f"Bearer {app_jwt}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }

            async with httpx.AsyncClient() as client:
                if owner and repo:
                    # Look up the exact installation for this repository
                    inst_resp = await client.get(
                        f"https://api.github.com/repos/{owner}/{repo}/installation",
                        headers=headers,
                        timeout=15.0,
                    )
                    if inst_resp.status_code != 200:
                        if inst_resp.status_code == 404:
                            logger.warning(
                                f"GitHub App '{oauth_app.app_name}' is not installed on {owner}/{repo}: "
                                f"{inst_resp.status_code} {inst_resp.text}"
                            )
                        else:
                            # e.g. 401 "Bad credentials" means the JWT itself was rejected
                            # (invalid signature, expired, or clock skew) — the app may still
                            # be installed. Don't conflate this with "not installed".
                            logger.warning(
                                f"GitHub App '{oauth_app.app_name}' JWT authentication failed for "
                                f"{owner}/{repo}: {inst_resp.status_code} {inst_resp.text}"
                            )
                        return None
                    installation_id = inst_resp.json()["id"]
                else:
                    resp = await client.get(
                        "https://api.github.com/app/installations",
                        headers=headers,
                        timeout=15.0,
                    )
                    if resp.status_code != 200 or not resp.json():
                        logger.warning(f"GitHub App '{oauth_app.app_name}' has no installations")
                        return None
                    installation_id = resp.json()[0]["id"]

                token_resp = await client.post(
                    f"https://api.github.com/app/installations/{installation_id}/access_tokens",
                    headers=headers,
                    timeout=15.0,
                )
                if token_resp.status_code != 201:
                    logger.warning(f"Failed to get GitHub App installation token: {token_resp.text}")
                    return None

                logger.info(
                    "Got GitHub App installation token for tool '%s' (app: %s, installation: %s)",
                    tool_name,
                    oauth_app.app_name,
                    installation_id,
                )
                return token_resp.json()["token"]

        except Exception as e:
            logger.error(f"Failed to get GitHub App installation token: {e}", exc_info=True)
            return None

    async def get_github_context(self, tool_name: str) -> dict[str, str | None]:
        """
        Get GitHub context information (org/username) from OAuth configuration.

        This provides context that can be auto-injected into tool calls:
        - organization: GitHub org name from OAuth app config
        - username: GitHub username from authenticated user API
        - default_branch: Default branch name (from config or 'main')

        Args:
            tool_name: Name of the tool requesting GitHub context

        Returns:
            Dictionary with GitHub context {organization, username, default_branch}
        """
        context = {"organization": None, "username": None, "default_branch": "main"}

        try:
            from src.models.agent_tool import AgentTool
            from src.models.oauth_app import OAuthApp

            # Find tool configuration
            result = await self.db.execute(
                select(AgentTool).filter(
                    AgentTool.agent_id == self.context.agent_id, AgentTool.tool_name == tool_name, AgentTool.enabled
                )
            )
            agent_tool = result.scalar_one_or_none()

            if not agent_tool or not agent_tool.oauth_app_id:
                return context

            # Get OAuth app
            result = await self.db.execute(
                select(OAuthApp).filter(
                    OAuthApp.id == agent_tool.oauth_app_id, OAuthApp.provider == "github", OAuthApp.is_active
                )
            )
            oauth_app = result.scalar_one_or_none()

            if not oauth_app:
                return context

            # Extract from OAuth app config
            if oauth_app.config and isinstance(oauth_app.config, dict):
                context["organization"] = oauth_app.config.get("organization")
                context["default_branch"] = oauth_app.config.get("default_branch", "main")

                if context["organization"]:
                    logger.info(f"📋 GitHub organization from OAuth config: {context['organization']}")

            # Get authenticated user info
            try:
                github_client = await self.get_github_client(tool_name)
                if github_client:
                    user = github_client.get_user()
                    context["username"] = user.login
                    logger.info(f"📋 GitHub authenticated user: {user.login}")
            except Exception as e:
                logger.debug(f"Could not get GitHub user info: {e}")

            return context

        except Exception as e:
            logger.error(f"Failed to get GitHub context: {e}", exc_info=True)
            return context

    async def get_gitlab_token(self, tool_name: str) -> tuple[str | None, str | None]:
        """
        Get GitLab access token and base URL for a tool.

        Uses user-first resolution: checks for user's personal token first,
        then falls back to OAuthApp token.

        Args:
            tool_name: Name of the tool requesting GitLab access

        Returns:
            Tuple of (access_token, base_url) or (None, None) if not configured
        """
        from src.models.agent_tool import AgentTool
        from src.models.oauth_app import OAuthApp
        from src.services.agents.security import decrypt_value

        try:
            # Find tool configuration
            result = await self.db.execute(
                select(AgentTool).filter(
                    AgentTool.agent_id == self.context.agent_id, AgentTool.tool_name == tool_name, AgentTool.enabled
                )
            )
            agent_tool = result.scalar_one_or_none()

            if not agent_tool or not agent_tool.oauth_app_id:
                logger.warning(f"No GitLab OAuth configured for tool '{tool_name}' (agent: {self.context.agent_id})")
                return None, None

            # Get OAuth app (case-insensitive provider check)
            result = await self.db.execute(
                select(OAuthApp).filter(
                    OAuthApp.id == agent_tool.oauth_app_id, OAuthApp.provider.ilike("gitlab"), OAuthApp.is_active
                )
            )
            oauth_app = result.scalar_one_or_none()

            if not oauth_app:
                logger.warning(f"GitLab OAuth app {agent_tool.oauth_app_id} not found or inactive")
                return None, None

            # Get base URL from config (default to gitlab.com)
            base_url = "https://gitlab.com"
            if oauth_app.config and isinstance(oauth_app.config, dict):
                base_url = oauth_app.config.get("base_url", base_url)

            # Try user token first (user-first resolution)
            try:
                user_token = await self._get_user_token(oauth_app.id)
                if user_token:
                    logger.info(
                        f"✅ Using user's personal GitLab token for tool '{tool_name}' "
                        f"(OAuth app: '{oauth_app.app_name}')"
                    )
                    return user_token, base_url
            except Exception as e:
                logger.warning(f"Failed to use user token for GitLab: {e}")

            # Fall back to OAuthApp token
            token = None
            if oauth_app.auth_method == "oauth" and oauth_app.access_token:
                token = decrypt_value(oauth_app.access_token)
            elif oauth_app.auth_method == "api_token" and oauth_app.api_token:
                token = decrypt_value(oauth_app.api_token)

            if not token:
                logger.warning(f"No valid token for GitLab OAuth app {oauth_app.app_name}")
                return None, None

            logger.info(
                f"✅ Using GitLab token for tool '{tool_name}' "
                f"(OAuth app: '{oauth_app.app_name}', auth_method: {oauth_app.auth_method})"
            )
            return token, base_url

        except Exception as e:
            logger.error(f"Failed to get GitLab token: {e}", exc_info=True)
            return None, None

    async def get_gmail_token(self, tool_name: str, retry_refresh: bool = True) -> str | None:
        """
        Get Gmail access token for the given tool.
        Automatically refreshes expired tokens using refresh_token.

        Uses user-first resolution: checks for user's personal token first,
        then falls back to OAuthApp token.

        Args:
            tool_name: Name of the Gmail tool requesting access
            retry_refresh: Whether to attempt token refresh on first call (default True)

        Returns:
            Access token string or None if not configured
        """
        import json

        from src.models.agent_tool import AgentTool
        from src.models.oauth_app import OAuthApp
        from src.services.agents.security import decrypt_value, encrypt_value
        from src.services.oauth.gmail_oauth import GmailOAuth

        try:
            # Get agent tool configuration
            result = await self.db.execute(
                select(AgentTool).filter(
                    AgentTool.agent_id == self.context.agent_id, AgentTool.tool_name == tool_name, AgentTool.enabled
                )
            )
            agent_tool = result.scalar_one_or_none()

            if not agent_tool or not agent_tool.oauth_app_id:
                logger.warning(f"No OAuth app configured for tool {tool_name}")
                return None

            # Get OAuth app (case-insensitive provider check)
            result = await self.db.execute(
                select(OAuthApp).filter(
                    OAuthApp.id == agent_tool.oauth_app_id, OAuthApp.provider.ilike("gmail"), OAuthApp.is_active
                )
            )
            oauth_app = result.scalar_one_or_none()

            if not oauth_app:
                logger.warning(f"No active Gmail OAuth app found for tool {tool_name}")
                return None

            # Helper function to parse credentials JSON and get access token
            def parse_gmail_credentials(encrypted_token: str) -> dict[str, Any] | None:
                try:
                    decrypted = decrypt_value(encrypted_token)
                    # Gmail stores credentials as JSON
                    if decrypted.startswith("{"):
                        return json.loads(decrypted)
                    # Plain token (shouldn't happen but handle it)
                    return {"access_token": decrypted}
                except Exception as e:
                    logger.warning(f"Failed to parse Gmail credentials: {e}")
                    return None

            # Helper function to refresh Gmail token
            async def refresh_gmail_token(creds: dict, oauth_app: OAuthApp) -> str | None:
                refresh_token = creds.get("refresh_token")
                if not refresh_token:
                    logger.warning("No refresh token available for Gmail")
                    return None

                try:
                    client_id = creds.get("client_id") or oauth_app.client_id
                    client_secret = creds.get("client_secret")
                    if not client_secret and oauth_app.client_secret:
                        client_secret = decrypt_value(oauth_app.client_secret)

                    if not client_id or not client_secret:
                        logger.error("Missing client credentials for Gmail OAuth")
                        return None

                    gmail_oauth = GmailOAuth(
                        client_id=client_id, client_secret=client_secret, redirect_uri=oauth_app.redirect_uri
                    )

                    token_data = await gmail_oauth.refresh_access_token(refresh_token)
                    return token_data.get("access_token")
                except Exception as e:
                    logger.error(f"Failed to refresh Gmail token: {e}", exc_info=True)
                    return None

            # Try user token first (user-first resolution)
            user_token_record = await self._get_user_token_record(oauth_app.id)
            if user_token_record and user_token_record.access_token:
                creds = parse_gmail_credentials(user_token_record.access_token)
                if creds:
                    access_token = creds.get("access_token")

                    # Check if token needs refresh (Gmail tokens expire in ~1 hour)
                    # For simplicity, always try the token first, refresh on failure
                    if access_token:
                        logger.info(
                            f"✅ Resolved Gmail token for tool '{tool_name}' "
                            f"using user's personal token (OAuth app: '{oauth_app.app_name}')"
                        )
                        return access_token

            # Fall back to OAuthApp token
            if oauth_app.access_token:
                creds = parse_gmail_credentials(oauth_app.access_token)
                if creds:
                    access_token = creds.get("access_token")

                    # Try to refresh if we have a refresh token
                    if retry_refresh and creds.get("refresh_token"):
                        refreshed_token = await refresh_gmail_token(creds, oauth_app)
                        if refreshed_token:
                            # Update stored credentials with new access token
                            creds["access_token"] = refreshed_token
                            oauth_app.access_token = encrypt_value(json.dumps(creds))
                            await self.db.commit()
                            logger.info(f"✅ Refreshed Gmail token for app '{oauth_app.app_name}'")
                            return refreshed_token

                    if access_token:
                        logger.info(
                            f"✅ Resolved Gmail OAuth token for tool '{tool_name}' "
                            f"using app '{oauth_app.app_name}' (fallback)"
                        )
                        return access_token

            logger.warning(f"No valid token found for Gmail OAuth app '{oauth_app.app_name}'")
            return None

        except Exception as e:
            logger.error(f"Failed to get Gmail token: {e}", exc_info=True)
            return None

    async def get_gmail_service(self, tool_name: str) -> Any | None:
        """
        Get authenticated Gmail service for a tool.

        Uses user-first resolution: checks for user's personal token first,
        then falls back to OAuthApp token.

        Args:
            tool_name: Name of the tool requesting Gmail access

        Returns:
            Authenticated Gmail service or None if not configured
        """
        import json

        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        from src.models.agent_tool import AgentTool
        from src.models.oauth_app import OAuthApp
        from src.services.agents.security import decrypt_value

        try:
            # Get agent tool configuration
            result = await self.db.execute(
                select(AgentTool).filter(
                    AgentTool.agent_id == self.context.agent_id, AgentTool.tool_name == tool_name, AgentTool.enabled
                )
            )
            agent_tool = result.scalar_one_or_none()

            if not agent_tool or not agent_tool.oauth_app_id:
                logger.warning(f"No OAuth app configured for Gmail tool '{tool_name}'")
                return None

            # Get OAuth app (case-insensitive provider check)
            result = await self.db.execute(
                select(OAuthApp).filter(
                    OAuthApp.id == agent_tool.oauth_app_id, OAuthApp.provider.ilike("gmail"), OAuthApp.is_active
                )
            )
            oauth_app = result.scalar_one_or_none()

            if not oauth_app:
                logger.warning(f"No active Gmail OAuth app found for tool {tool_name}")
                return None

            # Helper function to parse credentials JSON
            def parse_gmail_credentials(encrypted_token: str) -> dict | None:
                try:
                    decrypted = decrypt_value(encrypted_token)
                    # Gmail stores credentials as JSON
                    if decrypted.startswith("{"):
                        return json.loads(decrypted)
                    return None
                except Exception as e:
                    logger.warning(f"Failed to parse Gmail credentials: {e}")
                    return None

            # Try user token first (user-first resolution)
            user_token_record = await self._get_user_token_record(oauth_app.id)
            creds_data = None

            if user_token_record and user_token_record.access_token:
                creds_data = parse_gmail_credentials(user_token_record.access_token)
                if creds_data:
                    logger.info(f"✅ Using user's personal Gmail token (OAuth app: '{oauth_app.app_name}')")

            # Fall back to OAuthApp token
            if not creds_data and oauth_app.access_token:
                creds_data = parse_gmail_credentials(oauth_app.access_token)
                if creds_data:
                    logger.info(f"✅ Using Gmail OAuth app token '{oauth_app.app_name}' (fallback)")

            if not creds_data:
                logger.warning(f"No valid Gmail credentials found for tool '{tool_name}'")
                return None

            # Create Google credentials object
            creds = Credentials(
                token=creds_data.get("access_token"),
                refresh_token=creds_data.get("refresh_token"),
                token_uri=creds_data.get("token_uri", "https://oauth2.googleapis.com/token"),
                client_id=creds_data.get("client_id") or oauth_app.client_id,
                client_secret=creds_data.get("client_secret")
                or (decrypt_value(oauth_app.client_secret) if oauth_app.client_secret else None),
            )

            service = build("gmail", "v1", credentials=creds)
            logger.info(f"✅ Created authenticated Gmail service for tool '{tool_name}'")
            return service

        except Exception as e:
            logger.error(f"Failed to create Gmail service: {e}", exc_info=True)
            return None

    async def get_youtube_service(self, tool_name: str) -> Any | None:
        """
        Get authenticated YouTube service for a tool.

        Args:
            tool_name: Name of the tool requesting YouTube access

        Returns:
            Authenticated YouTube service or None if not configured
        """
        from googleapiclient.discovery import build

        from src.models.agent_tool import AgentTool
        from src.services.agents.security import decrypt_value

        result = await self.db.execute(
            select(AgentTool).filter(
                AgentTool.agent_id == self.context.agent_id, AgentTool.tool_name == tool_name, AgentTool.enabled
            )
        )
        agent_tool = result.scalar_one_or_none()

        if not agent_tool:
            return None

        config = agent_tool.config or {}
        api_key_encrypted = config.get("YOUTUBE_API_KEY")

        if not api_key_encrypted:
            logger.warning(f"No YouTube API key configured for tool '{tool_name}'")
            return None

        try:
            # Decrypt API key and create service
            api_key = decrypt_value(api_key_encrypted)
            service = build("youtube", "v3", developerKey=api_key)
            logger.info(f"✅ Created authenticated YouTube service for tool '{tool_name}'")
            return service
        except Exception as e:
            logger.error(f"Failed to create YouTube service: {e}", exc_info=True)
            return None

    async def get_serpapi_key(self, tool_name: str) -> str | None:
        """
        Get SerpAPI key for a tool.

        Note: This returns a raw API key because SerpAPI doesn't have a client library
        that accepts credentials via constructor. Use sparingly.

        Args:
            tool_name: Name of the tool requesting SerpAPI access

        Returns:
            Decrypted API key or None if not configured
        """
        from src.models.agent_tool import AgentTool
        from src.services.agents.security import decrypt_value

        result = await self.db.execute(
            select(AgentTool).filter(
                AgentTool.agent_id == self.context.agent_id, AgentTool.tool_name == tool_name, AgentTool.enabled
            )
        )
        agent_tool = result.scalar_one_or_none()

        if not agent_tool:
            return None

        config = agent_tool.config or {}
        api_key_encrypted = config.get("SERPAPI_KEY")

        if not api_key_encrypted:
            logger.warning(f"No SerpAPI key configured for tool '{tool_name}'")
            return None

        try:
            api_key = decrypt_value(api_key_encrypted)
            logger.info(f"✅ Resolved SerpAPI key for tool '{tool_name}'")
            return api_key
        except Exception as e:
            logger.error(f"Failed to decrypt SerpAPI key: {e}", exc_info=True)
            return None

    async def get_zoom_token(self, tool_name: str, retry_refresh: bool = True) -> str | None:
        """
        Get Zoom access token for the given tool.
        Automatically refreshes expired tokens using refresh_token.

        Uses user-first resolution: checks for user's personal token first,
        then falls back to OAuthApp token.

        Args:
            tool_name: Name of the Zoom tool requesting access
            retry_refresh: Whether to attempt token refresh on first call (default True)

        Returns:
            Access token string or None if not configured
        """
        from datetime import datetime

        from src.models.agent_tool import AgentTool
        from src.models.oauth_app import OAuthApp
        from src.services.agents.security import decrypt_value, encrypt_value
        from src.services.oauth.zoom_oauth import ZoomOAuth

        try:
            # Get agent tool configuration
            result = await self.db.execute(
                select(AgentTool).filter(
                    AgentTool.agent_id == self.context.agent_id, AgentTool.tool_name == tool_name, AgentTool.enabled
                )
            )
            agent_tool = result.scalar_one_or_none()

            if not agent_tool or not agent_tool.oauth_app_id:
                logger.warning(f"No OAuth app configured for tool {tool_name}")
                return None

            # Get OAuth app
            result = await self.db.execute(
                select(OAuthApp).filter(
                    OAuthApp.id == agent_tool.oauth_app_id, OAuthApp.provider == "zoom", OAuthApp.is_active
                )
            )
            oauth_app = result.scalar_one_or_none()

            if not oauth_app:
                logger.warning(f"No active Zoom OAuth app found for tool {tool_name}")
                return None

            # Try user token first (user-first resolution)
            user_token_record = await self._get_user_token_record(oauth_app.id)
            if user_token_record:
                # Check if user token is expired
                user_token_expired = False
                if user_token_record.token_expires_at:
                    now = datetime.now(UTC)
                    expires_at = user_token_record.token_expires_at
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=UTC)
                    user_token_expired = expires_at <= now

                if user_token_expired and retry_refresh and user_token_record.refresh_token:
                    # Refresh user token
                    try:
                        logger.info("🔄 Refreshing expired user Zoom token...")

                        # Get credentials from OAuth app (client_id is plain text, client_secret is encrypted)
                        client_id = oauth_app.client_id
                        client_secret = decrypt_value(oauth_app.client_secret) if oauth_app.client_secret else None
                        refresh_token = decrypt_value(user_token_record.refresh_token)

                        if client_id and client_secret:
                            zoom_oauth = ZoomOAuth(
                                client_id=client_id, client_secret=client_secret, redirect_uri=oauth_app.redirect_uri
                            )

                            token_data = await zoom_oauth.refresh_access_token(refresh_token)

                            # Update user token record
                            user_token_record.access_token = encrypt_value(token_data["access_token"])
                            if "refresh_token" in token_data:
                                user_token_record.refresh_token = encrypt_value(token_data["refresh_token"])
                            if "expires_in" in token_data:
                                from datetime import timedelta

                                user_token_record.token_expires_at = datetime.now(UTC) + timedelta(
                                    seconds=token_data["expires_in"]
                                )

                            await self.db.commit()
                            logger.info("✅ Successfully refreshed user Zoom token")
                            return token_data["access_token"]

                    except Exception as refresh_error:
                        logger.error(f"Failed to refresh user Zoom token: {refresh_error}", exc_info=True)
                        # Fall through to try OAuthApp token

                elif not user_token_expired:
                    # Token is still valid
                    token = decrypt_value(user_token_record.access_token)
                    logger.info(
                        f"✅ Resolved Zoom token for tool '{tool_name}' "
                        f"using user's personal token (OAuth app: '{oauth_app.app_name}')"
                    )
                    return token
                else:
                    logger.warning("User Zoom token expired but no refresh token available")

            # Check if OAuthApp token is expired and needs refresh
            needs_refresh = False
            if oauth_app.auth_method == "oauth" and oauth_app.token_expires_at:
                # Check if token expires within next 5 minutes (proactive refresh)
                now = datetime.now(UTC)
                expires_at = oauth_app.token_expires_at
                if expires_at.tzinfo is None:
                    # Make expires_at timezone-aware if it isn't
                    expires_at = expires_at.replace(tzinfo=UTC)

                if expires_at <= now:
                    needs_refresh = True
                    logger.info(f"🔄 Zoom token expired for app '{oauth_app.app_name}', will refresh")

            # Attempt token refresh if needed and allowed
            if needs_refresh and retry_refresh and oauth_app.refresh_token:
                try:
                    logger.info(f"🔄 Refreshing expired Zoom token for app '{oauth_app.app_name}'...")

                    # Get credentials (client_id is plain text, client_secret is encrypted)
                    client_id = oauth_app.client_id
                    client_secret = decrypt_value(oauth_app.client_secret) if oauth_app.client_secret else None
                    refresh_token = decrypt_value(oauth_app.refresh_token)

                    if not client_id or not client_secret:
                        logger.error(f"Missing client credentials for Zoom OAuth app '{oauth_app.app_name}'")
                        return None

                    # Create Zoom OAuth client and refresh token
                    zoom_oauth = ZoomOAuth(
                        client_id=client_id, client_secret=client_secret, redirect_uri=oauth_app.redirect_uri
                    )

                    token_data = await zoom_oauth.refresh_access_token(refresh_token)

                    # Update OAuth app with new tokens
                    oauth_app.access_token = encrypt_value(token_data["access_token"])

                    # Update refresh token if provided (some providers rotate it)
                    if "refresh_token" in token_data:
                        oauth_app.refresh_token = encrypt_value(token_data["refresh_token"])

                    # Update expiration time
                    if "expires_in" in token_data:
                        from datetime import timedelta

                        oauth_app.token_expires_at = datetime.now(UTC) + timedelta(seconds=token_data["expires_in"])

                    await self.db.commit()

                    logger.info(f"✅ Successfully refreshed Zoom token for app '{oauth_app.app_name}'")

                    # Return the new token
                    return token_data["access_token"]

                except Exception as refresh_error:
                    logger.error(f"Failed to refresh Zoom token: {refresh_error}", exc_info=True)
                    # Token is expired and refresh failed - user needs to re-authenticate
                    # Check if it's an invalid_grant error (refresh token is invalid/revoked)
                    error_str = str(refresh_error).lower()
                    if "invalid_grant" in error_str or "invalid token" in error_str:
                        logger.error(
                            f"❌ Zoom refresh token is invalid for app '{oauth_app.app_name}'. "
                            f"This usually means the token was already used (Zoom rotates tokens) "
                            f"or was revoked. User must reconnect their Zoom account."
                        )
                        # Mark the OAuth app as needing re-authentication
                        oauth_app.access_token = None
                        oauth_app.token_expires_at = None
                        await self.db.commit()
                    else:
                        logger.error(
                            f"❌ Zoom token refresh failed for app '{oauth_app.app_name}'. "
                            f"User may need to reconnect their Zoom account."
                        )
                    return None

            # If token is expired but no refresh token available, return None
            if needs_refresh:
                logger.error(
                    f"❌ Zoom token expired for app '{oauth_app.app_name}' but no refresh token available. "
                    f"User needs to re-authenticate with Zoom."
                )
                return None

            # Decrypt and return token (only if not expired)
            if oauth_app.auth_method == "oauth" and oauth_app.access_token:
                token = decrypt_value(oauth_app.access_token)
                logger.info(f"✅ Resolved Zoom OAuth token for tool '{tool_name}' using app '{oauth_app.app_name}'")
                return token
            elif oauth_app.auth_method == "api_token" and oauth_app.api_token:
                token = decrypt_value(oauth_app.api_token)
                logger.info(f"✅ Resolved Zoom API token for tool '{tool_name}' using app '{oauth_app.app_name}'")
                return token

            logger.warning(f"No valid token found in Zoom OAuth app '{oauth_app.app_name}'")
            return None

        except Exception as e:
            logger.error(f"Failed to get Zoom token: {e}", exc_info=True)
            return None

    async def get_google_calendar_token(self, tool_name: str, retry_refresh: bool = True) -> str | None:
        """
        Get Google Calendar access token for the given tool.
        Automatically refreshes expired tokens using refresh_token.

        Uses user-first resolution: checks for user's personal token first,
        then falls back to OAuthApp token.

        Args:
            tool_name: Name of the Google Calendar tool requesting access
            retry_refresh: Whether to attempt token refresh on first call (default True)

        Returns:
            Access token string or None if not configured
        """
        from datetime import datetime

        from src.models.agent_tool import AgentTool
        from src.models.oauth_app import OAuthApp
        from src.services.agents.security import decrypt_value, encrypt_value
        from src.services.oauth.google_calendar_oauth import GoogleCalendarOAuth

        try:
            # Get agent tool configuration
            result = await self.db.execute(
                select(AgentTool).filter(
                    AgentTool.agent_id == self.context.agent_id, AgentTool.tool_name == tool_name, AgentTool.enabled
                )
            )
            agent_tool = result.scalar_one_or_none()

            if not agent_tool or not agent_tool.oauth_app_id:
                logger.warning(f"No OAuth app configured for tool {tool_name}")
                return None

            # Get OAuth app
            result = await self.db.execute(
                select(OAuthApp).filter(
                    OAuthApp.id == agent_tool.oauth_app_id, OAuthApp.provider == "google_calendar", OAuthApp.is_active
                )
            )
            oauth_app = result.scalar_one_or_none()

            if not oauth_app:
                logger.warning(f"No active Google Calendar OAuth app found for tool {tool_name}")
                return None

            # Try user token first (user-first resolution)
            user_token_record = await self._get_user_token_record(oauth_app.id)
            if user_token_record:
                # Check if user token is expired
                user_token_expired = False
                if user_token_record.token_expires_at:
                    now = datetime.now(UTC)
                    expires_at = user_token_record.token_expires_at
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=UTC)
                    user_token_expired = expires_at <= now

                if user_token_expired and retry_refresh and user_token_record.refresh_token:
                    # Refresh user token
                    try:
                        logger.info("🔄 Refreshing expired user Google Calendar token...")

                        # Get credentials from OAuth app (client_id is plain text, client_secret is encrypted)
                        client_id = oauth_app.client_id
                        client_secret = decrypt_value(oauth_app.client_secret) if oauth_app.client_secret else None
                        refresh_token = decrypt_value(user_token_record.refresh_token)

                        if client_id and client_secret:
                            google_oauth = GoogleCalendarOAuth(
                                client_id=client_id, client_secret=client_secret, redirect_uri=oauth_app.redirect_uri
                            )

                            token_data = await google_oauth.refresh_token(refresh_token)

                            # Update user token record
                            user_token_record.access_token = encrypt_value(token_data["access_token"])
                            if "refresh_token" in token_data:
                                user_token_record.refresh_token = encrypt_value(token_data["refresh_token"])
                            if "expires_in" in token_data:
                                from datetime import timedelta

                                user_token_record.token_expires_at = datetime.now(UTC) + timedelta(
                                    seconds=token_data["expires_in"]
                                )

                            await self.db.commit()
                            logger.info("✅ Successfully refreshed user Google Calendar token")
                            return token_data["access_token"]

                    except Exception as refresh_error:
                        logger.error(f"Failed to refresh user Google Calendar token: {refresh_error}", exc_info=True)
                        # Fall through to try OAuthApp token

                elif not user_token_expired:
                    # Token is still valid
                    token = decrypt_value(user_token_record.access_token)
                    logger.info(
                        f"✅ Resolved Google Calendar token for tool '{tool_name}' "
                        f"using user's personal token (OAuth app: '{oauth_app.app_name}')"
                    )
                    return token
                else:
                    logger.warning("User Google Calendar token expired but no refresh token available")

            # Check if OAuthApp token is expired and needs refresh
            needs_refresh = False
            if oauth_app.auth_method == "oauth" and oauth_app.token_expires_at:
                now = datetime.now(UTC)
                expires_at = oauth_app.token_expires_at
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=UTC)

                if expires_at <= now:
                    needs_refresh = True
                    logger.info(f"🔄 Google Calendar token expired for app '{oauth_app.app_name}', will refresh")

            # Attempt token refresh if needed and allowed
            if needs_refresh and retry_refresh and oauth_app.refresh_token:
                try:
                    logger.info(f"🔄 Refreshing expired Google Calendar token for app '{oauth_app.app_name}'...")

                    # Get credentials (client_id is plain text, client_secret is encrypted)
                    client_id = oauth_app.client_id
                    client_secret = decrypt_value(oauth_app.client_secret) if oauth_app.client_secret else None
                    refresh_token = decrypt_value(oauth_app.refresh_token)

                    if not client_id or not client_secret:
                        logger.error(f"Missing client credentials for Google Calendar OAuth app '{oauth_app.app_name}'")
                        return None

                    # Create Google Calendar OAuth client and refresh token
                    google_oauth = GoogleCalendarOAuth(
                        client_id=client_id, client_secret=client_secret, redirect_uri=oauth_app.redirect_uri
                    )

                    token_data = await google_oauth.refresh_token(refresh_token)

                    # Update OAuth app with new tokens
                    oauth_app.access_token = encrypt_value(token_data["access_token"])

                    # Update refresh token if provided
                    if "refresh_token" in token_data and token_data["refresh_token"] != refresh_token:
                        oauth_app.refresh_token = encrypt_value(token_data["refresh_token"])

                    # Update expiration time
                    if "expires_in" in token_data:
                        from datetime import timedelta

                        oauth_app.token_expires_at = datetime.now(UTC) + timedelta(seconds=token_data["expires_in"])

                    await self.db.commit()

                    logger.info(f"✅ Successfully refreshed Google Calendar token for app '{oauth_app.app_name}'")

                    # Return the new token
                    return token_data["access_token"]

                except Exception as refresh_error:
                    logger.error(f"Failed to refresh Google Calendar token: {refresh_error}", exc_info=True)
                    # Token is expired and refresh failed - user needs to re-authenticate
                    logger.error(
                        f"❌ Google Calendar token expired and refresh failed for app '{oauth_app.app_name}'. "
                        f"User needs to re-authenticate with Google Calendar."
                    )
                    return None

            # If token is expired but no refresh token available, return None
            if needs_refresh:
                logger.error(
                    f"❌ Google Calendar token expired for app '{oauth_app.app_name}' but no refresh token available. "
                    f"User needs to re-authenticate with Google Calendar."
                )
                return None

            # Decrypt and return token (only if not expired)
            if oauth_app.auth_method == "oauth" and oauth_app.access_token:
                token = decrypt_value(oauth_app.access_token)
                logger.info(
                    f"✅ Resolved Google Calendar OAuth token for tool '{tool_name}' using app '{oauth_app.app_name}'"
                )
                return token

            logger.warning(f"No valid token found in Google Calendar OAuth app '{oauth_app.app_name}'")
            return None

        except Exception as e:
            logger.error(f"Failed to get Google Calendar token: {e}", exc_info=True)
            return None

    async def get_google_drive_token(self, tool_name: str, retry_refresh: bool = True) -> str | None:
        """
        Get Google Drive access token for the given tool.
        Automatically refreshes expired tokens using refresh_token.

        Uses user-first resolution: checks for user's personal token first,
        then falls back to OAuthApp token.

        Args:
            tool_name: Name of the Google Drive tool requesting access
            retry_refresh: Whether to attempt token refresh on first call (default True)

        Returns:
            Access token string or None if not configured
        """
        from datetime import datetime

        from src.models.agent_tool import AgentTool
        from src.models.oauth_app import OAuthApp
        from src.services.agents.security import decrypt_value, encrypt_value
        from src.services.oauth.google_drive_oauth import GoogleDriveOAuth

        try:
            # Get agent tool configuration
            result = await self.db.execute(
                select(AgentTool).filter(
                    AgentTool.agent_id == self.context.agent_id, AgentTool.tool_name == tool_name, AgentTool.enabled
                )
            )
            agent_tool = result.scalar_one_or_none()

            if not agent_tool or not agent_tool.oauth_app_id:
                logger.warning(f"No OAuth app configured for tool {tool_name}")
                return None

            # Get OAuth app
            result = await self.db.execute(
                select(OAuthApp).filter(
                    OAuthApp.id == agent_tool.oauth_app_id, OAuthApp.provider == "google_drive", OAuthApp.is_active
                )
            )
            oauth_app = result.scalar_one_or_none()

            if not oauth_app:
                logger.warning(f"No active Google Drive OAuth app found for tool {tool_name}")
                return None

            # Try user token first (user-first resolution)
            user_token_record = await self._get_user_token_record(oauth_app.id)
            if user_token_record:
                # Check if user token is expired
                user_token_expired = False
                if user_token_record.token_expires_at:
                    now = datetime.now(UTC)
                    expires_at = user_token_record.token_expires_at
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=UTC)
                    user_token_expired = expires_at <= now

                if user_token_expired and retry_refresh and user_token_record.refresh_token:
                    # Refresh user token
                    try:
                        logger.info("🔄 Refreshing expired user Google Drive token...")

                        # Get credentials from OAuth app (client_id is plain text, client_secret is encrypted)
                        client_id = oauth_app.client_id
                        client_secret = decrypt_value(oauth_app.client_secret) if oauth_app.client_secret else None
                        refresh_token = decrypt_value(user_token_record.refresh_token)

                        if client_id and client_secret:
                            google_oauth = GoogleDriveOAuth(
                                client_id=client_id, client_secret=client_secret, redirect_uri=oauth_app.redirect_uri
                            )

                            token_data = await google_oauth.refresh_token(refresh_token)

                            # Update user token record
                            user_token_record.access_token = encrypt_value(token_data["access_token"])
                            if "refresh_token" in token_data:
                                user_token_record.refresh_token = encrypt_value(token_data["refresh_token"])
                            if "expires_in" in token_data:
                                from datetime import timedelta

                                user_token_record.token_expires_at = datetime.now(UTC) + timedelta(
                                    seconds=token_data["expires_in"]
                                )

                            await self.db.commit()
                            logger.info("✅ Successfully refreshed user Google Drive token")
                            return token_data["access_token"]

                    except Exception as refresh_error:
                        logger.error(f"Failed to refresh user Google Drive token: {refresh_error}", exc_info=True)
                        # Fall through to try OAuthApp token

                elif not user_token_expired:
                    # Token is still valid
                    token = decrypt_value(user_token_record.access_token)
                    logger.info(
                        f"✅ Resolved Google Drive token for tool '{tool_name}' "
                        f"using user's personal token (OAuth app: '{oauth_app.app_name}')"
                    )
                    return token
                else:
                    logger.warning("User Google Drive token expired but no refresh token available")

            # Check if OAuthApp token is expired and needs refresh
            needs_refresh = False
            if oauth_app.auth_method == "oauth" and oauth_app.token_expires_at:
                now = datetime.now(UTC)
                expires_at = oauth_app.token_expires_at
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=UTC)

                if expires_at <= now:
                    needs_refresh = True
                    logger.info(f"🔄 Google Drive token expired for app '{oauth_app.app_name}', will refresh")

            # Attempt token refresh if needed and allowed
            if needs_refresh and retry_refresh and oauth_app.refresh_token:
                try:
                    logger.info(f"🔄 Refreshing expired Google Drive token for app '{oauth_app.app_name}'...")

                    # Get credentials (client_id is plain text, client_secret is encrypted)
                    client_id = oauth_app.client_id
                    client_secret = decrypt_value(oauth_app.client_secret) if oauth_app.client_secret else None
                    refresh_token = decrypt_value(oauth_app.refresh_token)

                    if not client_id or not client_secret:
                        logger.error(f"Missing client credentials for Google Drive OAuth app '{oauth_app.app_name}'")
                        return None

                    # Create Google Drive OAuth client and refresh token
                    google_oauth = GoogleDriveOAuth(
                        client_id=client_id, client_secret=client_secret, redirect_uri=oauth_app.redirect_uri
                    )

                    token_data = await google_oauth.refresh_token(refresh_token)

                    # Update OAuth app with new tokens
                    oauth_app.access_token = encrypt_value(token_data["access_token"])

                    # Update refresh token if provided
                    if "refresh_token" in token_data and token_data["refresh_token"] != refresh_token:
                        oauth_app.refresh_token = encrypt_value(token_data["refresh_token"])

                    # Update expiration time
                    if "expires_in" in token_data:
                        from datetime import timedelta

                        oauth_app.token_expires_at = datetime.now(UTC) + timedelta(seconds=token_data["expires_in"])

                    await self.db.commit()

                    logger.info(f"✅ Successfully refreshed Google Drive token for app '{oauth_app.app_name}'")

                    # Return the new token
                    return token_data["access_token"]

                except Exception as refresh_error:
                    logger.error(f"Failed to refresh Google Drive token: {refresh_error}", exc_info=True)
                    # Token is expired and refresh failed - user needs to re-authenticate
                    logger.error(
                        f"❌ Google Drive token expired and refresh failed for app '{oauth_app.app_name}'. "
                        f"User needs to re-authenticate with Google Drive."
                    )
                    return None

            # If token is expired but no refresh token available, return None
            if needs_refresh:
                logger.error(
                    f"❌ Google Drive token expired for app '{oauth_app.app_name}' but no refresh token available. "
                    f"User needs to re-authenticate with Google Drive."
                )
                return None

            # Decrypt and return token (only if not expired)
            if oauth_app.auth_method == "oauth" and oauth_app.access_token:
                token = decrypt_value(oauth_app.access_token)
                logger.info(
                    f"✅ Resolved Google Drive OAuth token for tool '{tool_name}' using app '{oauth_app.app_name}'"
                )
                return token

            logger.warning(f"No valid token found in Google Drive OAuth app '{oauth_app.app_name}'")
            return None

        except Exception as e:
            logger.error(f"Failed to get Google Drive token: {e}", exc_info=True)
            return None

    async def get_slack_token(self, tool_name: str) -> str | None:
        """
        Get Slack access token for the given tool.
        Supports both OAuth apps and legacy Slack bots.

        Uses user-first resolution: checks for user's personal token first,
        then falls back to OAuthApp token.

        Args:
            tool_name: Name of the Slack tool requesting access

        Returns:
            Access token string or None if not configured
        """
        from src.models.agent_tool import AgentTool
        from src.models.oauth_app import OAuthApp
        from src.models.slack_bot import SlackBot
        from src.services.agents.security import decrypt_value

        try:
            # First, try OAuth app (preferred method)
            result = await self.db.execute(
                select(AgentTool).filter(
                    AgentTool.agent_id == self.context.agent_id, AgentTool.tool_name == tool_name, AgentTool.enabled
                )
            )
            agent_tool = result.scalar_one_or_none()

            logger.info(
                f"🔍 Looking for Slack OAuth: tool_name='{tool_name}', agent_tool={agent_tool}, oauth_app_id={agent_tool.oauth_app_id if agent_tool else None}"
            )

            if agent_tool and agent_tool.oauth_app_id:
                # Use OAuth app (case-insensitive provider check)
                result = await self.db.execute(
                    select(OAuthApp).filter(
                        OAuthApp.id == agent_tool.oauth_app_id, OAuthApp.provider.ilike("slack"), OAuthApp.is_active
                    )
                )
                oauth_app = result.scalar_one_or_none()

                logger.info(
                    f"🔍 Found OAuth app: {oauth_app.app_name if oauth_app else 'None'}, provider={oauth_app.provider if oauth_app else 'N/A'}, has_token={bool(oauth_app.access_token) if oauth_app else False}"
                )

                if oauth_app:
                    # Try user token first (user-first resolution)
                    user_token = await self._get_user_token(oauth_app.id)
                    if user_token:
                        logger.info(
                            f"✅ Resolved Slack token for tool '{tool_name}' "
                            f"using user's personal token (OAuth app: '{oauth_app.app_name}')"
                        )
                        return user_token

                    # Fall back to OAuthApp token
                    if oauth_app.auth_method == "oauth" and oauth_app.access_token:
                        token = decrypt_value(oauth_app.access_token)
                        logger.info(
                            f"✅ Resolved Slack OAuth token for tool '{tool_name}' "
                            f"using app '{oauth_app.app_name}' (fallback)"
                        )
                        return token
                    elif oauth_app.auth_method == "api_token" and oauth_app.api_token:
                        token = decrypt_value(oauth_app.api_token)
                        logger.info(
                            f"✅ Resolved Slack API token for tool '{tool_name}' using app '{oauth_app.app_name}'"
                        )
                        return token

            # Pinned Slack bot: use the explicitly selected bot for this tool
            if agent_tool and agent_tool.slack_bot_id:
                result = await self.db.execute(
                    select(SlackBot).filter(
                        SlackBot.id == agent_tool.slack_bot_id, SlackBot.connection_status == "connected"
                    )
                )
                pinned_bot = result.scalar_one_or_none()
                if pinned_bot and pinned_bot.slack_bot_token:
                    token = decrypt_value(pinned_bot.slack_bot_token)
                    logger.info(
                        f"✅ Resolved Slack token from pinned bot '{pinned_bot.bot_name}' for tool '{tool_name}'"
                    )
                    return token
                logger.warning(
                    f"Pinned Slack bot {agent_tool.slack_bot_id} not found or disconnected for tool '{tool_name}'"
                )

            # Auto-discover: find any connected bot for this agent
            result = await self.db.execute(
                select(SlackBot)
                .filter(SlackBot.agent_id == self.context.agent_id, SlackBot.connection_status == "connected")
                .limit(1)
            )
            slack_bot = result.scalar_one_or_none()

            if slack_bot and slack_bot.slack_bot_token:
                token = decrypt_value(slack_bot.slack_bot_token)
                logger.info(f"✅ Resolved Slack token from auto-discovered bot for tool '{tool_name}'")
                return token

            logger.warning(
                f"No Slack OAuth app or bot configured for tool '{tool_name}' (agent: {self.context.agent_id})"
            )
            return None

        except Exception as e:
            logger.error(f"Failed to get Slack token: {e}", exc_info=True)
            return None

    async def get_clickup_token(self, tool_name: str) -> str | None:
        """
        Get ClickUp access token for the given tool.

        Uses user-first resolution: checks for user's personal token first,
        then falls back to OAuthApp token.

        Args:
            tool_name: Name of the ClickUp tool requesting access

        Returns:
            Access token string or None if not configured
        """
        from src.models.agent_tool import AgentTool
        from src.models.oauth_app import OAuthApp
        from src.services.agents.security import decrypt_value

        try:
            result = await self.db.execute(
                select(AgentTool).filter(
                    AgentTool.agent_id == self.context.agent_id, AgentTool.tool_name == tool_name, AgentTool.enabled
                )
            )
            agent_tool = result.scalar_one_or_none()

            if not agent_tool or not agent_tool.oauth_app_id:
                logger.warning(f"No OAuth app configured for tool {tool_name}")
                return None

            result = await self.db.execute(
                select(OAuthApp).filter(
                    OAuthApp.id == agent_tool.oauth_app_id, OAuthApp.provider.ilike("clickup"), OAuthApp.is_active
                )
            )
            oauth_app = result.scalar_one_or_none()

            if not oauth_app:
                logger.warning(f"ClickUp OAuth app not found for tool {tool_name}")
                return None

            # Try user token first (user-first resolution)
            user_token = await self._get_user_token(oauth_app.id)
            if user_token:
                logger.info(
                    f"✅ Resolved ClickUp token for tool '{tool_name}' "
                    f"using user's personal token (OAuth app: '{oauth_app.app_name}')"
                )
                return user_token

            # Fall back to OAuthApp token
            if oauth_app.auth_method == "oauth" and oauth_app.access_token:
                token = decrypt_value(oauth_app.access_token)
                logger.info(
                    f"✅ Resolved ClickUp OAuth token for tool '{tool_name}' "
                    f"using app '{oauth_app.app_name}' (fallback)"
                )
                return token
            elif oauth_app.auth_method == "api_token" and oauth_app.api_token:
                token = decrypt_value(oauth_app.api_token)
                logger.info(f"✅ Resolved ClickUp API token for tool '{tool_name}' using app '{oauth_app.app_name}'")
                return token

            logger.warning(f"No ClickUp token configured for tool '{tool_name}'")
            return None

        except Exception as e:
            logger.error(f"Failed to get ClickUp token: {e}", exc_info=True)
            return None

    async def get_jira_credentials(self, tool_name: str) -> dict[str, Any] | None:
        """
        Get Jira credentials for the given tool.
        Supports both OAuth (Bearer token) and API token (Basic Auth).

        Uses user-first resolution: checks for user's personal token first,
        then falls back to OAuthApp token.

        Args:
            tool_name: Name of the Jira tool requesting access

        Returns:
            Dictionary with Jira credentials or None if not configured.
            For OAuth: {auth_type: 'oauth', cloud_id, access_token, domain}
            For API token: {auth_type: 'basic', domain, email, api_token}
        """
        from src.models.agent_tool import AgentTool
        from src.models.oauth_app import OAuthApp
        from src.services.agents.security import decrypt_value

        try:
            # Get agent tool configuration
            result = await self.db.execute(
                select(AgentTool).filter(
                    AgentTool.agent_id == self.context.agent_id, AgentTool.tool_name == tool_name, AgentTool.enabled
                )
            )
            agent_tool = result.scalar_one_or_none()

            if not agent_tool or not agent_tool.oauth_app_id:
                logger.warning(f"No OAuth app configured for tool {tool_name}")
                return None

            # Get OAuth app (case-insensitive provider check)
            result = await self.db.execute(
                select(OAuthApp).filter(
                    OAuthApp.id == agent_tool.oauth_app_id, OAuthApp.provider.ilike("jira"), OAuthApp.is_active
                )
            )
            oauth_app = result.scalar_one_or_none()

            if not oauth_app:
                logger.warning(f"No active Jira OAuth app found for tool {tool_name}")
                return None

            config = oauth_app.config or {}

            # Check if this is OAuth or API token authentication
            if oauth_app.auth_method == "api_token":
                # API token authentication (Basic Auth)
                api_token = decrypt_value(oauth_app.api_token) if oauth_app.api_token else None
                if not api_token:
                    logger.warning(f"No API token found in Jira OAuth app '{oauth_app.app_name}'")
                    return None

                domain = config.get("base_url", "").replace("https://", "").replace(".atlassian.net", "")
                email = config.get("email")

                if not domain or not email:
                    logger.warning(f"Missing domain or email in Jira OAuth app '{oauth_app.app_name}' config")
                    return None

                logger.info(
                    f"✅ Resolved Jira API token credentials for tool '{tool_name}' using app '{oauth_app.app_name}'"
                )
                return {
                    "auth_type": "basic",
                    "domain": domain,
                    "email": email,
                    "api_token": api_token,
                }

            else:
                # OAuth authentication (Bearer token)
                # cloud_id is shared across all users (stored in OAuth app config)
                cloud_id = config.get("cloud_id")
                domain = config.get("cloud_url", "").replace("https://", "").replace(".atlassian.net", "")

                logger.info(f"🔍 Jira OAuth app '{oauth_app.app_name}' config: {config}")

                if not cloud_id:
                    logger.warning(f"No cloud_id found in Jira OAuth app '{oauth_app.app_name}' config")
                    return None

                # Try user token first (user-first resolution)
                user_token = await self._get_user_token(oauth_app.id)
                if user_token:
                    logger.info(
                        f"✅ Resolved Jira OAuth token for tool '{tool_name}' "
                        f"using user's personal token (OAuth app: '{oauth_app.app_name}')"
                    )
                    return {
                        "auth_type": "oauth",
                        "cloud_id": cloud_id,
                        "access_token": user_token,
                        "domain": domain,
                    }

                # Fall back to OAuthApp token
                if oauth_app.access_token:
                    access_token = decrypt_value(oauth_app.access_token)
                    cloud_id = config.get("cloud_id")
                    domain = config.get("cloud_url", "").replace("https://", "").replace(".atlassian.net", "")

                    if not cloud_id:
                        logger.warning(f"No cloud_id found in Jira OAuth app '{oauth_app.app_name}' config")
                        return None

                    logger.info(
                        f"✅ Resolved Jira OAuth token for tool '{tool_name}' "
                        f"using app '{oauth_app.app_name}' (fallback)"
                    )
                    return {
                        "auth_type": "oauth",
                        "cloud_id": cloud_id,
                        "access_token": access_token,
                        "domain": domain,
                    }

                logger.warning(f"No valid token found in Jira OAuth app '{oauth_app.app_name}'")
                return None

        except Exception as e:
            logger.error(f"Failed to get Jira credentials: {e}", exc_info=True)
            return None

    async def get_zendesk_credentials(self, tool_name: str) -> dict[str, Any] | None:
        """
        Get Zendesk credentials for the given tool.
        Supports OAuth (Bearer token) and API token (Basic Auth).

        Returns:
            For OAuth:     {auth_type: 'oauth', subdomain, access_token}
            For API token: {auth_type: 'api_token', subdomain, email, api_token}
        """
        from src.models.agent_tool import AgentTool
        from src.models.oauth_app import OAuthApp
        from src.services.agents.security import decrypt_value

        try:
            result = await self.db.execute(
                select(AgentTool).filter(
                    AgentTool.agent_id == self.context.agent_id,
                    AgentTool.tool_name == tool_name,
                    AgentTool.enabled,
                )
            )
            agent_tool = result.scalar_one_or_none()

            if not agent_tool or not agent_tool.oauth_app_id:
                logger.warning(f"No OAuth app configured for tool {tool_name}")
                return None

            result = await self.db.execute(
                select(OAuthApp).filter(
                    OAuthApp.id == agent_tool.oauth_app_id,
                    OAuthApp.provider.ilike("zendesk"),
                    OAuthApp.is_active,
                )
            )
            oauth_app = result.scalar_one_or_none()

            if not oauth_app:
                logger.warning(f"No active Zendesk OAuth app found for tool {tool_name}")
                return None

            config = oauth_app.config or {}
            subdomain = config.get("subdomain", "").strip()
            if not subdomain:
                logger.warning(f"No subdomain in Zendesk OAuth app '{oauth_app.app_name}'")
                return None

            if oauth_app.auth_method == "api_token":
                api_token = decrypt_value(oauth_app.api_token) if oauth_app.api_token else None
                email = config.get("email", "").strip()
                if not api_token or not email:
                    logger.warning(f"Missing api_token or email in Zendesk OAuth app '{oauth_app.app_name}'")
                    return None
                logger.info(f"✅ Resolved Zendesk API token credentials for tool '{tool_name}'")
                return {"auth_type": "api_token", "subdomain": subdomain, "email": email, "api_token": api_token}

            # OAuth — try user token first
            user_token = await self._get_user_token(oauth_app.id)
            if user_token:
                logger.info(f"✅ Resolved Zendesk OAuth token for tool '{tool_name}' (user-level)")
                return {"auth_type": "oauth", "subdomain": subdomain, "access_token": user_token}

            if oauth_app.access_token:
                access_token = decrypt_value(oauth_app.access_token)
                logger.info(f"✅ Resolved Zendesk OAuth token for tool '{tool_name}' (app-level fallback)")
                return {"auth_type": "oauth", "subdomain": subdomain, "access_token": access_token}

            logger.warning(f"No valid token found in Zendesk OAuth app '{oauth_app.app_name}'")
            return None

        except Exception as e:
            logger.error(f"Failed to get Zendesk credentials: {e}", exc_info=True)
            return None

    async def get_zoho_crm_credentials(self, tool_name: str) -> dict[str, Any] | None:
        """
        Get Zoho CRM credentials for the given tool (OAuth only).

        Returns:
            {auth_type: 'oauth', data_center, access_token}
        """
        from src.models.agent_tool import AgentTool
        from src.models.oauth_app import OAuthApp
        from src.services.agents.security import decrypt_value

        try:
            result = await self.db.execute(
                select(AgentTool).filter(
                    AgentTool.agent_id == self.context.agent_id,
                    AgentTool.tool_name == tool_name,
                    AgentTool.enabled,
                )
            )
            agent_tool = result.scalar_one_or_none()

            if not agent_tool or not agent_tool.oauth_app_id:
                logger.warning(f"No OAuth app configured for tool {tool_name}")
                return None

            result = await self.db.execute(
                select(OAuthApp).filter(
                    OAuthApp.id == agent_tool.oauth_app_id,
                    OAuthApp.provider.ilike("zoho_crm"),
                    OAuthApp.is_active,
                )
            )
            oauth_app = result.scalar_one_or_none()

            if not oauth_app:
                logger.warning(f"No active Zoho CRM OAuth app found for tool {tool_name}")
                return None

            config = oauth_app.config or {}
            data_center = config.get("data_center", "com")

            # Try user token first
            user_token = await self._get_user_token(oauth_app.id)
            if user_token:
                logger.info(f"✅ Resolved Zoho CRM OAuth token for tool '{tool_name}' (user-level)")
                return {"auth_type": "oauth", "data_center": data_center, "access_token": user_token}

            if oauth_app.access_token:
                access_token = decrypt_value(oauth_app.access_token)
                logger.info(f"✅ Resolved Zoho CRM OAuth token for tool '{tool_name}' (app-level fallback)")
                return {"auth_type": "oauth", "data_center": data_center, "access_token": access_token}

            logger.warning(f"No valid token found in Zoho CRM OAuth app '{oauth_app.app_name}'")
            return None

        except Exception as e:
            logger.error(f"Failed to get Zoho CRM credentials: {e}", exc_info=True)
            return None

    async def get_micromobility_credentials(self, tool_name: str) -> dict[str, Any] | None:
        """
        Get micromobility credentials for the given tool.
        Supports oauth, api_token, and basic_auth methods.

        Returns a config dict keyed on auth_type:
        - basic_auth:  {auth_type, base_url, username, password, endpoints, ...}
        - api_key:     {auth_type, base_url, api_token, api_key_header, api_key_format, endpoints, ...}
        - oauth:       {auth_type, base_url, access_token, endpoints, ...}
        """
        import httpx

        from src.core.database import get_async_session_factory
        from src.models.agent_tool import AgentTool
        from src.models.oauth_app import OAuthApp
        from src.models.user_oauth_token import UserOAuthToken
        from src.services.agents.security import decrypt_value, encrypt_value

        try:
            # Use a fresh independent session so that concurrent parallel tool calls
            # (e.g. LLM calling list_trips + list_vehicles simultaneously) don't share
            # the same session and trigger SQLAlchemy's "concurrent operations" error.
            async with get_async_session_factory()() as db:
                result = await db.execute(
                    select(AgentTool).filter(
                        AgentTool.agent_id == self.context.agent_id,
                        AgentTool.tool_name == tool_name,
                        AgentTool.enabled,
                    )
                )
                agent_tool = result.scalar_one_or_none()

                if not agent_tool or not agent_tool.oauth_app_id:
                    logger.warning(f"No OAuth app configured for tool {tool_name}")
                    return None

                result = await db.execute(
                    select(OAuthApp).filter(
                        OAuthApp.id == agent_tool.oauth_app_id,
                        OAuthApp.provider.ilike("micromobility"),
                        OAuthApp.is_active,
                    )
                )
                oauth_app = result.scalar_one_or_none()

                if not oauth_app:
                    logger.warning(f"No active micromobility OAuth app found for tool {tool_name}")
                    return None

                # Snapshot all needed values from the ORM object before session closes
                app_name = oauth_app.app_name
                auth_method = oauth_app.auth_method
                config = oauth_app.config or {}
                base_url = config.get("base_url", "").rstrip("/")
                endpoints = config.get("endpoints", {})
                raw_api_token = oauth_app.api_token
                raw_access_token = oauth_app.access_token
                oauth_app_id = oauth_app.id

                if not base_url:
                    logger.warning(f"No base_url in micromobility OAuth app '{app_name}'")
                    return None

                if auth_method == "basic_auth":
                    password = decrypt_value(raw_api_token) if raw_api_token else None
                    username = config.get("username")
                    if not password or not username:
                        logger.warning(f"Missing username or password for basic_auth micromobility app '{app_name}'")
                        return None

                    login_endpoint = config.get("login_endpoint", "/admin-login-jwt/")
                    token_field = config.get("token_response_field", "token")
                    username_field = config.get("login_username_field", "username")
                    password_field = config.get("login_password_field", "password")
                    timeout = float(config.get("request_timeout_seconds", 30))
                    login_url = f"{base_url}{login_endpoint}"
                    refresh_meta = {
                        "_login_url": login_url,
                        "_login_username": username,
                        "_login_password": password,
                        "_login_token_field": token_field,
                        "_login_username_field": username_field,
                        "_login_password_field": password_field,
                    }

                    # Try cached access_token first (avoid a login call on every tool use)
                    if raw_access_token:
                        cached_token = decrypt_value(raw_access_token)
                        logger.info(f"✅ Resolved micromobility basic_auth (cached JWT) for tool '{tool_name}'")
                        return {
                            "auth_type": "api_key",
                            "base_url": base_url,
                            "api_token": cached_token,
                            "api_key_header": "Authorization",
                            "api_key_format": "Bearer {token}",
                            "endpoints": endpoints,
                            "custom_headers": config.get("custom_headers", {}),
                            "request_timeout_seconds": timeout,
                            **refresh_meta,
                        }

                    # No cached token — call login endpoint to obtain a fresh JWT
                    login_body = {username_field: username, password_field: password}
                    logger.info(
                        f"[micromobility login] POST {login_url} | "
                        f"body={{{username_field}: '{username}', {password_field}: '***'}} | "
                        f"token_field='{token_field}'"
                    )
                    try:
                        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
                            resp = await client.post(
                                login_url,
                                json=login_body,
                                headers={"Content-Type": "application/json", "Accept": "application/json"},
                            )
                        logger.info(
                            f"[micromobility login] response: HTTP {resp.status_code} | "
                            f"final_url={resp.url} | body={resp.text[:500]}"
                        )
                        if not resp.is_success:
                            logger.error(
                                f"Micromobility login failed for app '{app_name}': "
                                f"HTTP {resp.status_code} — see response above"
                            )
                            return None
                        jwt_token = resp.json().get(token_field)
                        if not jwt_token:
                            logger.error(
                                f"Micromobility login response missing field '{token_field}' "
                                f"for app '{app_name}'. Response keys: {list(resp.json().keys())}"
                            )
                            return None
                    except Exception as login_err:
                        logger.error(f"Micromobility login request failed: {login_err}", exc_info=True)
                        return None

                    # Cache the token on the OAuthApp so subsequent calls skip the login
                    oauth_app.access_token = encrypt_value(jwt_token)
                    await db.commit()

                    logger.info(f"✅ Resolved micromobility basic_auth (fresh JWT) for tool '{tool_name}'")
                    return {
                        "auth_type": "api_key",
                        "base_url": base_url,
                        "api_token": jwt_token,
                        "api_key_header": "Authorization",
                        "api_key_format": "Bearer {token}",
                        "endpoints": endpoints,
                        "custom_headers": config.get("custom_headers", {}),
                        "request_timeout_seconds": timeout,
                        **refresh_meta,
                    }

                if auth_method == "api_token":
                    api_token = decrypt_value(raw_api_token) if raw_api_token else None
                    if not api_token:
                        logger.warning(f"No API token in micromobility OAuth app '{app_name}'")
                        return None
                    logger.info(f"✅ Resolved micromobility api_key credentials for tool '{tool_name}'")
                    return {
                        "auth_type": "api_key",
                        "base_url": base_url,
                        "api_token": api_token,
                        "api_key_header": config.get("api_key_header", "Authorization"),
                        "api_key_format": config.get("api_key_format", "Bearer {token}"),
                        "endpoints": endpoints,
                        "custom_headers": config.get("custom_headers", {}),
                        "request_timeout_seconds": config.get("request_timeout_seconds", 30),
                    }

                # OAuth — user-first resolution (inline to stay within this session)
                user_token = None
                try:
                    if hasattr(self.context, "user_id") and self.context.user_id:
                        ut_result = await db.execute(
                            select(UserOAuthToken).filter(
                                UserOAuthToken.account_id == self.context.user_id,
                                UserOAuthToken.oauth_app_id == oauth_app_id,
                            )
                        )
                        ut = ut_result.scalar_one_or_none()
                        if ut and ut.access_token:
                            user_token = decrypt_value(ut.access_token)
                    if not user_token:
                        ut_result = await db.execute(
                            select(UserOAuthToken).filter(UserOAuthToken.oauth_app_id == oauth_app_id)
                        )
                        ut = ut_result.scalar_one_or_none()
                        if ut and ut.access_token:
                            user_token = decrypt_value(ut.access_token)
                except Exception as ut_err:
                    logger.warning(f"Failed to get user token record: {ut_err}")

                if user_token:
                    logger.info(
                        f"✅ Resolved micromobility OAuth token for tool '{tool_name}' "
                        f"using user's personal token (app: '{app_name}')"
                    )
                    return {
                        "auth_type": "oauth",
                        "base_url": base_url,
                        "access_token": user_token,
                        "endpoints": endpoints,
                        "custom_headers": config.get("custom_headers", {}),
                        "request_timeout_seconds": config.get("request_timeout_seconds", 30),
                    }

                if raw_access_token:
                    access_token = decrypt_value(raw_access_token)
                    logger.info(
                        f"✅ Resolved micromobility OAuth token for tool '{tool_name}' "
                        f"using app token (app: '{app_name}') (fallback)"
                    )
                    return {
                        "auth_type": "oauth",
                        "base_url": base_url,
                        "access_token": access_token,
                        "endpoints": endpoints,
                        "custom_headers": config.get("custom_headers", {}),
                        "request_timeout_seconds": config.get("request_timeout_seconds", 30),
                    }

                logger.warning(f"No valid token found in micromobility OAuth app '{app_name}'")
                return None

        except Exception as e:
            logger.error(f"Failed to get micromobility credentials: {e}", exc_info=True)
            return None

    async def get_freshdesk_credentials(self, tool_name: str) -> dict[str, Any] | None:
        """
        Get Freshdesk credentials (API key + subdomain).

        Returns:
            {auth_type: 'api_key', subdomain, api_key}
        """
        from src.models.agent_tool import AgentTool
        from src.models.oauth_app import OAuthApp
        from src.services.agents.security import decrypt_value

        try:
            result = await self.db.execute(
                select(AgentTool).filter(
                    AgentTool.agent_id == self.context.agent_id,
                    AgentTool.tool_name == tool_name,
                    AgentTool.enabled,
                )
            )
            agent_tool = result.scalar_one_or_none()
            if not agent_tool or not agent_tool.oauth_app_id:
                logger.warning(f"No OAuth app configured for tool {tool_name}")
                return None

            result = await self.db.execute(
                select(OAuthApp).filter(
                    OAuthApp.id == agent_tool.oauth_app_id,
                    OAuthApp.provider.ilike("freshdesk"),
                    OAuthApp.is_active,
                )
            )
            oauth_app = result.scalar_one_or_none()
            if not oauth_app:
                logger.warning(f"No active Freshdesk OAuth app found for tool {tool_name}")
                return None

            config = oauth_app.config or {}
            subdomain = config.get("subdomain", "").strip()
            if not subdomain:
                logger.warning(f"No subdomain in Freshdesk OAuth app '{oauth_app.app_name}'")
                return None

            api_key = decrypt_value(oauth_app.api_token) if oauth_app.api_token else None
            if not api_key:
                logger.warning(f"No API key in Freshdesk OAuth app '{oauth_app.app_name}'")
                return None

            logger.info(f"✅ Resolved Freshdesk API key credentials for tool '{tool_name}'")
            return {"auth_type": "api_key", "subdomain": subdomain, "api_key": api_key}

        except Exception as e:
            logger.error(f"Failed to get Freshdesk credentials: {e}", exc_info=True)
            return None

    async def get_hubspot_credentials(self, tool_name: str) -> dict[str, Any] | None:
        """
        Get HubSpot credentials (OAuth access token or Private App token).

        Returns:
            {auth_type: 'oauth'|'api_token', access_token}
        """
        from src.models.agent_tool import AgentTool
        from src.models.oauth_app import OAuthApp
        from src.services.agents.security import decrypt_value

        try:
            result = await self.db.execute(
                select(AgentTool).filter(
                    AgentTool.agent_id == self.context.agent_id,
                    AgentTool.tool_name == tool_name,
                    AgentTool.enabled,
                )
            )
            agent_tool = result.scalar_one_or_none()
            if not agent_tool or not agent_tool.oauth_app_id:
                logger.warning(f"No OAuth app configured for tool {tool_name}")
                return None

            result = await self.db.execute(
                select(OAuthApp).filter(
                    OAuthApp.id == agent_tool.oauth_app_id,
                    OAuthApp.provider.ilike("hubspot"),
                    OAuthApp.is_active,
                )
            )
            oauth_app = result.scalar_one_or_none()
            if not oauth_app:
                logger.warning(f"No active HubSpot OAuth app found for tool {tool_name}")
                return None

            # Private App token stored as api_token
            if oauth_app.auth_method == "api_token":
                token = decrypt_value(oauth_app.api_token) if oauth_app.api_token else None
                if not token:
                    logger.warning(f"No API token in HubSpot OAuth app '{oauth_app.app_name}'")
                    return None
                logger.info(f"✅ Resolved HubSpot private app token for tool '{tool_name}'")
                return {"auth_type": "api_token", "access_token": token}

            # OAuth — user token first
            user_token = await self._get_user_token(oauth_app.id)
            if user_token:
                logger.info(f"✅ Resolved HubSpot OAuth token for tool '{tool_name}' (user-level)")
                return {"auth_type": "oauth", "access_token": user_token}

            if oauth_app.access_token:
                token = decrypt_value(oauth_app.access_token)
                logger.info(f"✅ Resolved HubSpot OAuth token for tool '{tool_name}' (app-level fallback)")
                return {"auth_type": "oauth", "access_token": token}

            logger.warning(f"No valid token found in HubSpot OAuth app '{oauth_app.app_name}'")
            return None

        except Exception as e:
            logger.error(f"Failed to get HubSpot credentials: {e}", exc_info=True)
            return None

    async def get_salesforce_credentials(self, tool_name: str) -> dict[str, Any] | None:
        """
        Get Salesforce credentials (OAuth — instance_url + access_token).

        Returns:
            {auth_type: 'oauth', instance_url, access_token}
        """
        from src.models.agent_tool import AgentTool
        from src.models.oauth_app import OAuthApp
        from src.services.agents.security import decrypt_value

        try:
            result = await self.db.execute(
                select(AgentTool).filter(
                    AgentTool.agent_id == self.context.agent_id,
                    AgentTool.tool_name == tool_name,
                    AgentTool.enabled,
                )
            )
            agent_tool = result.scalar_one_or_none()
            if not agent_tool or not agent_tool.oauth_app_id:
                logger.warning(f"No OAuth app configured for tool {tool_name}")
                return None

            result = await self.db.execute(
                select(OAuthApp).filter(
                    OAuthApp.id == agent_tool.oauth_app_id,
                    OAuthApp.provider.ilike("salesforce"),
                    OAuthApp.is_active,
                )
            )
            oauth_app = result.scalar_one_or_none()
            if not oauth_app:
                logger.warning(f"No active Salesforce OAuth app found for tool {tool_name}")
                return None

            config = oauth_app.config or {}
            instance_url = config.get("instance_url", "").strip()
            if not instance_url:
                logger.warning(f"No instance_url in Salesforce OAuth app '{oauth_app.app_name}'")
                return None

            user_token = await self._get_user_token(oauth_app.id)
            if user_token:
                logger.info(f"✅ Resolved Salesforce OAuth token for tool '{tool_name}' (user-level)")
                return {"auth_type": "oauth", "instance_url": instance_url, "access_token": user_token}

            if oauth_app.access_token:
                token = decrypt_value(oauth_app.access_token)
                logger.info(f"✅ Resolved Salesforce OAuth token for tool '{tool_name}' (app-level fallback)")
                return {"auth_type": "oauth", "instance_url": instance_url, "access_token": token}

            logger.warning(f"No valid token found in Salesforce OAuth app '{oauth_app.app_name}'")
            return None

        except Exception as e:
            logger.error(f"Failed to get Salesforce credentials: {e}", exc_info=True)
            return None

    async def get_intercom_credentials(self, tool_name: str) -> dict[str, Any] | None:
        """
        Get Intercom credentials (OAuth access token or Personal Access Token).

        Returns:
            {auth_type: 'oauth'|'api_token', access_token}
        """
        from src.models.agent_tool import AgentTool
        from src.models.oauth_app import OAuthApp
        from src.services.agents.security import decrypt_value

        try:
            result = await self.db.execute(
                select(AgentTool).filter(
                    AgentTool.agent_id == self.context.agent_id,
                    AgentTool.tool_name == tool_name,
                    AgentTool.enabled,
                )
            )
            agent_tool = result.scalar_one_or_none()
            if not agent_tool or not agent_tool.oauth_app_id:
                logger.warning(f"No OAuth app configured for tool {tool_name}")
                return None

            result = await self.db.execute(
                select(OAuthApp).filter(
                    OAuthApp.id == agent_tool.oauth_app_id,
                    OAuthApp.provider.ilike("intercom"),
                    OAuthApp.is_active,
                )
            )
            oauth_app = result.scalar_one_or_none()
            if not oauth_app:
                logger.warning(f"No active Intercom OAuth app found for tool {tool_name}")
                return None

            if oauth_app.auth_method == "api_token":
                token = decrypt_value(oauth_app.api_token) if oauth_app.api_token else None
                if not token:
                    logger.warning(f"No personal access token in Intercom OAuth app '{oauth_app.app_name}'")
                    return None
                logger.info(f"✅ Resolved Intercom personal access token for tool '{tool_name}'")
                return {"auth_type": "api_token", "access_token": token}

            user_token = await self._get_user_token(oauth_app.id)
            if user_token:
                logger.info(f"✅ Resolved Intercom OAuth token for tool '{tool_name}' (user-level)")
                return {"auth_type": "oauth", "access_token": user_token}

            if oauth_app.access_token:
                token = decrypt_value(oauth_app.access_token)
                logger.info(f"✅ Resolved Intercom OAuth token for tool '{tool_name}' (app-level fallback)")
                return {"auth_type": "oauth", "access_token": token}

            logger.warning(f"No valid token found in Intercom OAuth app '{oauth_app.app_name}'")
            return None

        except Exception as e:
            logger.error(f"Failed to get Intercom credentials: {e}", exc_info=True)
            return None

    async def get_twitter_token(self, tool_name: str, retry_refresh: bool = True) -> str | None:
        """
        Get Twitter access token for the given tool.
        Automatically refreshes expired tokens using refresh_token.

        Uses user-first resolution: checks for user's personal token first,
        then falls back to OAuthApp token.

        Args:
            tool_name: Name of the Twitter tool requesting access
            retry_refresh: Whether to attempt token refresh on first call (default True)

        Returns:
            Access token string or None if not configured
        """
        from datetime import datetime

        from src.models.agent_tool import AgentTool
        from src.models.oauth_app import OAuthApp
        from src.services.agents.security import decrypt_value, encrypt_value
        from src.services.oauth.twitter_oauth import TwitterOAuth

        try:
            result = await self.db.execute(
                select(AgentTool).filter(
                    AgentTool.agent_id == self.context.agent_id, AgentTool.tool_name == tool_name, AgentTool.enabled
                )
            )
            agent_tool = result.scalar_one_or_none()

            if not agent_tool or not agent_tool.oauth_app_id:
                logger.warning(f"No OAuth app configured for tool {tool_name}")
                return None

            result = await self.db.execute(
                select(OAuthApp).filter(
                    OAuthApp.id == agent_tool.oauth_app_id, OAuthApp.provider.ilike("twitter"), OAuthApp.is_active
                )
            )
            oauth_app = result.scalar_one_or_none()

            if not oauth_app:
                logger.warning(f"No active Twitter OAuth app found for tool {tool_name}")
                return None

            # Try user token first (user-first resolution)
            user_token_record = await self._get_user_token_record(oauth_app.id)
            if user_token_record:
                user_token_expired = False
                if user_token_record.token_expires_at:
                    now = datetime.now(UTC)
                    expires_at = user_token_record.token_expires_at
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=UTC)
                    user_token_expired = expires_at <= now

                if user_token_expired and retry_refresh and user_token_record.refresh_token:
                    try:
                        logger.info("🔄 Refreshing expired user Twitter token...")
                        client_id = oauth_app.client_id
                        client_secret = decrypt_value(oauth_app.client_secret) if oauth_app.client_secret else None
                        refresh_token = decrypt_value(user_token_record.refresh_token)

                        if client_id and client_secret:
                            twitter_oauth = TwitterOAuth(
                                client_id=client_id, client_secret=client_secret, redirect_uri=oauth_app.redirect_uri
                            )
                            token_data = await twitter_oauth.refresh_access_token(refresh_token)

                            user_token_record.access_token = encrypt_value(token_data["access_token"])
                            if "refresh_token" in token_data:
                                user_token_record.refresh_token = encrypt_value(token_data["refresh_token"])
                            if "expires_in" in token_data:
                                from datetime import timedelta

                                user_token_record.token_expires_at = datetime.now(UTC) + timedelta(
                                    seconds=token_data["expires_in"]
                                )

                            await self.db.commit()
                            logger.info("✅ Successfully refreshed user Twitter token")
                            return token_data["access_token"]
                    except Exception as refresh_error:
                        logger.error(f"Failed to refresh user Twitter token: {refresh_error}", exc_info=True)

                elif not user_token_expired:
                    token = decrypt_value(user_token_record.access_token)
                    logger.info(
                        f"✅ Resolved Twitter token for tool '{tool_name}' "
                        f"using user's personal token (OAuth app: '{oauth_app.app_name}')"
                    )
                    return token

            # Fall back to OAuthApp token
            if oauth_app.auth_method == "oauth" and oauth_app.access_token:
                token = decrypt_value(oauth_app.access_token)
                logger.info(f"✅ Resolved Twitter OAuth token for tool '{tool_name}' using app '{oauth_app.app_name}'")
                return token
            elif oauth_app.auth_method == "api_token" and oauth_app.api_token:
                token = decrypt_value(oauth_app.api_token)
                logger.info(f"✅ Resolved Twitter API token for tool '{tool_name}' using app '{oauth_app.app_name}'")
                return token

            logger.warning(f"No valid token found in Twitter OAuth app '{oauth_app.app_name}'")
            return None

        except Exception as e:
            logger.error(f"Failed to get Twitter token: {e}", exc_info=True)
            return None

    async def get_linkedin_token(self, tool_name: str, retry_refresh: bool = True) -> str | None:
        """
        Get LinkedIn access token for the given tool.
        Automatically refreshes expired tokens using refresh_token.

        Uses user-first resolution: checks for user's personal token first,
        then falls back to OAuthApp token.

        Args:
            tool_name: Name of the LinkedIn tool requesting access
            retry_refresh: Whether to attempt token refresh on first call (default True)

        Returns:
            Access token string or None if not configured
        """
        from datetime import datetime

        from src.models.agent_tool import AgentTool
        from src.models.oauth_app import OAuthApp
        from src.services.agents.security import decrypt_value, encrypt_value
        from src.services.oauth.linkedin_oauth import LinkedInOAuth

        try:
            result = await self.db.execute(
                select(AgentTool).filter(
                    AgentTool.agent_id == self.context.agent_id, AgentTool.tool_name == tool_name, AgentTool.enabled
                )
            )
            agent_tool = result.scalar_one_or_none()

            if not agent_tool or not agent_tool.oauth_app_id:
                logger.warning(f"No OAuth app configured for tool {tool_name}")
                return None

            result = await self.db.execute(
                select(OAuthApp).filter(
                    OAuthApp.id == agent_tool.oauth_app_id, OAuthApp.provider.ilike("linkedin"), OAuthApp.is_active
                )
            )
            oauth_app = result.scalar_one_or_none()

            if not oauth_app:
                logger.warning(f"No active LinkedIn OAuth app found for tool {tool_name}")
                return None

            # Try user token first (user-first resolution)
            user_token_record = await self._get_user_token_record(oauth_app.id)
            if user_token_record:
                user_token_expired = False
                if user_token_record.token_expires_at:
                    now = datetime.now(UTC)
                    expires_at = user_token_record.token_expires_at
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=UTC)
                    user_token_expired = expires_at <= now

                if user_token_expired and retry_refresh and user_token_record.refresh_token:
                    try:
                        logger.info("🔄 Refreshing expired user LinkedIn token...")
                        client_id = oauth_app.client_id
                        client_secret = decrypt_value(oauth_app.client_secret) if oauth_app.client_secret else None
                        refresh_token = decrypt_value(user_token_record.refresh_token)

                        if client_id and client_secret:
                            linkedin_oauth = LinkedInOAuth(
                                client_id=client_id, client_secret=client_secret, redirect_uri=oauth_app.redirect_uri
                            )
                            token_data = await linkedin_oauth.refresh_access_token(refresh_token)

                            user_token_record.access_token = encrypt_value(token_data["access_token"])
                            if "refresh_token" in token_data:
                                user_token_record.refresh_token = encrypt_value(token_data["refresh_token"])
                            if "expires_in" in token_data:
                                from datetime import timedelta

                                user_token_record.token_expires_at = datetime.now(UTC) + timedelta(
                                    seconds=token_data["expires_in"]
                                )

                            await self.db.commit()
                            logger.info("✅ Successfully refreshed user LinkedIn token")
                            return token_data["access_token"]
                    except Exception as refresh_error:
                        logger.error(f"Failed to refresh user LinkedIn token: {refresh_error}", exc_info=True)

                elif not user_token_expired:
                    token = decrypt_value(user_token_record.access_token)
                    logger.info(
                        f"✅ Resolved LinkedIn token for tool '{tool_name}' "
                        f"using user's personal token (OAuth app: '{oauth_app.app_name}')"
                    )
                    return token

            # Fall back to OAuthApp token
            if oauth_app.auth_method == "oauth" and oauth_app.access_token:
                token = decrypt_value(oauth_app.access_token)
                logger.info(f"✅ Resolved LinkedIn OAuth token for tool '{tool_name}' using app '{oauth_app.app_name}'")
                return token
            elif oauth_app.auth_method == "api_token" and oauth_app.api_token:
                token = decrypt_value(oauth_app.api_token)
                logger.info(f"✅ Resolved LinkedIn API token for tool '{tool_name}' using app '{oauth_app.app_name}'")
                return token

            logger.warning(f"No valid token found in LinkedIn OAuth app '{oauth_app.app_name}'")
            return None

        except Exception as e:
            logger.error(f"Failed to get LinkedIn token: {e}", exc_info=True)
            return None

    async def get_recall_credentials(self, tool_name: str) -> tuple[str | None, str, str | None]:
        """
        Get Recall.ai API credentials for meeting bot tools.

        Uses user-first resolution: checks for user's personal token first,
        then falls back to OAuthApp token.

        Args:
            tool_name: Name of the tool requesting Recall.ai access

        Returns:
            Tuple of (api_key, region, webhook_secret) or (None, "us-east-1", None) if not configured
        """
        from src.models.agent_tool import AgentTool
        from src.models.oauth_app import OAuthApp
        from src.services.agents.security import decrypt_value

        default_region = "us-east-1"

        try:
            # Find tool configuration
            result = await self.db.execute(
                select(AgentTool).filter(
                    AgentTool.agent_id == self.context.agent_id, AgentTool.tool_name == tool_name, AgentTool.enabled
                )
            )
            agent_tool = result.scalar_one_or_none()

            if not agent_tool or not agent_tool.oauth_app_id:
                logger.warning(f"No Recall.ai OAuth configured for tool '{tool_name}' (agent: {self.context.agent_id})")
                return None, default_region, None

            # Get OAuth app (case-insensitive provider check)
            result = await self.db.execute(
                select(OAuthApp).filter(
                    OAuthApp.id == agent_tool.oauth_app_id, OAuthApp.provider.ilike("recall"), OAuthApp.is_active
                )
            )
            oauth_app = result.scalar_one_or_none()

            if not oauth_app:
                logger.warning(f"Recall.ai OAuth app {agent_tool.oauth_app_id} not found or inactive")
                return None, default_region, None

            # Get config values (region, webhook_secret)
            region = default_region
            webhook_secret = None
            logger.info(f"🔧 Recall OAuth app config: {oauth_app.config}")
            if oauth_app.config and isinstance(oauth_app.config, dict):
                region = oauth_app.config.get("region", default_region)
                webhook_secret = oauth_app.config.get("webhook_secret")
                if webhook_secret and webhook_secret.startswith("enc:"):
                    webhook_secret = decrypt_value(webhook_secret)
            logger.info(f"🔧 Recall region resolved: {region}")

            # Try user token first (user-first resolution)
            try:
                user_token = await self._get_user_token(oauth_app.id)
                if user_token:
                    logger.info(
                        f"✅ Using user's personal Recall.ai token for tool '{tool_name}' "
                        f"(OAuth app: '{oauth_app.app_name}')"
                    )
                    return user_token, region, webhook_secret
            except Exception as e:
                logger.warning(f"Failed to use user token for Recall.ai: {e}")

            # Fall back to OAuthApp token (api_token for Recall.ai)
            token = None
            if oauth_app.api_token:
                token = decrypt_value(oauth_app.api_token)

            if not token:
                logger.warning(f"No valid API token for Recall.ai OAuth app {oauth_app.app_name}")
                return None, region, webhook_secret

            logger.info(f"✅ Using Recall.ai token for tool '{tool_name}' (OAuth app: '{oauth_app.app_name}')")
            return token, region, webhook_secret

        except Exception as e:
            logger.error(f"Failed to get Recall.ai credentials: {e}", exc_info=True)
            return None, default_region, None

    async def resolve_for_tool(self, tool_name: str, auth_type: str) -> Any | None:
        """
        Resolve and return authenticated client based on auth type.

        This is the main entry point for credential resolution.

        Args:
            tool_name: Name of the tool requesting access
            auth_type: Type of authentication required (e.g., "github", "gmail")

        Returns:
            Authenticated client/service or None if not available
        """
        logger.debug(f"Resolving credentials for tool '{tool_name}' (auth_type: {auth_type})")

        resolvers = {
            "github": self.get_github_client,
            "gmail": self.get_gmail_service,
            "youtube": self.get_youtube_service,
            "serpapi": self.get_serpapi_key,
            "zoom": self.get_zoom_token,
            "google_calendar": self.get_google_calendar_token,
            "google_drive": self.get_google_drive_token,
            "slack": self.get_slack_token,
            "clickup": self.get_clickup_token,
            "jira": self.get_jira_credentials,
            "micromobility": self.get_micromobility_credentials,
            "twitter": self.get_twitter_token,
            "linkedin": self.get_linkedin_token,
            "recall": self.get_recall_credentials,
        }

        resolver = resolvers.get(auth_type)
        if not resolver:
            logger.warning(f"Unknown auth type: {auth_type}")
            return None

        return await resolver(tool_name)
