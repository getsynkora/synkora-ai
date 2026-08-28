"""
GitHub OAuth Controller.

Handles GitHub OAuth authorization, callback, disconnect, status, and repository listing.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.utils.config_helper import get_app_base_url

from ...core.database import get_async_db
from ...middleware.auth_middleware import get_current_tenant_id, get_optional_account, get_optional_tenant_id
from ...models.agent import Agent
from ...models.agent_tool import AgentTool
from ...models.oauth_app import OAuthApp
from ...models.tenant import Account
from ...models.user_oauth_token import UserOAuthToken
from ...services.agents.security import decrypt_value, encrypt_value
from ...services.oauth import GitHubOAuth
from ...services.security.oauth_state_service import create_oauth_state, get_oauth_state
from .base import (
    GitHubDisconnectRequest,
    _get_oauth_app_secure,
    _get_or_create_tenant_clone,
    _safe_error_redirect,
    _safe_success_redirect,
    get_oauth_app_from_db,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/github/authorize")
async def github_authorize(
    oauth_app_id: int = Query(..., description="OAuth app ID to authorize"),
    redirect_url: str = Query(None, description="Frontend redirect URL after OAuth"),
    user_level: bool = Query(False, description="Store token at user level instead of app level"),
    current_account: Account | None = Depends(get_optional_account),
    tenant_id: uuid.UUID | None = Depends(get_optional_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Initiate GitHub OAuth authorization for an OAuth app.
    This is standalone - authorization happens at OAuth app level.

    If user_level=True and user is authenticated, the token will be stored
    in the UserOAuthToken table for the current user.
    """
    try:
        # Validate user_level requires authentication
        if user_level and not current_account:
            raise HTTPException(status_code=401, detail="Authentication required for user-level OAuth")

        # SECURITY: Validate OAuth app belongs to current tenant when authenticated (prevents IDOR)
        # tenant_id comes from JWT via get_optional_tenant_id dependency
        oauth_app = await _get_oauth_app_secure(db, oauth_app_id, tenant_id=tenant_id)
        if not oauth_app:
            raise HTTPException(status_code=404, detail="OAuth app not found")

        base_url = await get_app_base_url(db, oauth_app.tenant_id)
        redirect_url = redirect_url or f"{base_url}/oauth-apps"

        # If using API token, no OAuth flow needed
        if oauth_app.auth_method == "api_token":
            return RedirectResponse(url=f"{redirect_url}?oauth=success&provider=github&method=api_token")

        # Decrypt credentials
        client_id = oauth_app.client_id
        try:
            client_secret = decrypt_value(oauth_app.client_secret)
        except Exception as e:
            logger.error(f"Failed to decrypt client secret: {e}")
            raise HTTPException(status_code=500, detail="Failed to decrypt OAuth credentials")

        redirect_uri = oauth_app.redirect_uri

        # Initialize OAuth client
        oauth = GitHubOAuth(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri)

        # SECURITY: Generate state for CSRF protection (Redis-backed)
        state = create_oauth_state(
            {
                "oauth_app_id": oauth_app_id,
                "redirect_url": redirect_url,
                "user_level": user_level,
                "account_id": str(current_account.id) if current_account and user_level else None,
                "tenant_id": str(tenant_id) if tenant_id else None,
            }
        )
        if not state:
            raise HTTPException(status_code=500, detail="Failed to create OAuth state")

        # Get authorization URL with scopes from OAuth app
        scopes = oauth_app.scopes or ["repo", "user", "read:org"]
        auth_url = oauth.get_authorization_url(state=state, scopes=scopes)

        logger.info(f"Initiating GitHub OAuth for app {oauth_app_id} (user_level={user_level})")
        return RedirectResponse(url=auth_url)

    except Exception as e:
        logger.error(f"GitHub OAuth authorization error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/github/callback")
async def github_callback(
    code: str = Query(..., description="Authorization code from GitHub"),
    state: str = Query(..., description="State parameter for CSRF protection"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Handle GitHub OAuth callback and store token.

    If user_level was set in the authorize request, stores in UserOAuthToken.
    Otherwise stores in OAuthApp (legacy behavior).
    """
    try:
        # Verify state
        # SECURITY: Retrieve and delete state (single-use, Redis-backed)
        state_data = get_oauth_state(state)
        if state_data is None:
            raise HTTPException(status_code=400, detail="Invalid or expired state parameter")
        oauth_app_id = state_data["oauth_app_id"]
        redirect_url = state_data["redirect_url"]
        user_level = state_data.get("user_level", False)
        account_id = state_data.get("account_id")

        # SECURITY: Get OAuth app (state is already validated from Redis)
        oauth_app = await _get_oauth_app_secure(db, oauth_app_id)
        if not oauth_app:
            raise HTTPException(status_code=404, detail="OAuth app not found")

        # Decrypt credentials
        client_id = oauth_app.client_id
        client_secret = decrypt_value(oauth_app.client_secret)
        redirect_uri = oauth_app.redirect_uri

        # Initialize OAuth client
        oauth = GitHubOAuth(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri)

        # Exchange code for token
        token = await oauth.get_access_token(code)
        if not token:
            raise HTTPException(status_code=400, detail="Failed to get access token")

        # Get user info
        user_info = await oauth.get_user_info(token)

        # Store token based on user_level flag
        if user_level and account_id:
            # Store in UserOAuthToken (per-user)
            result = await db.execute(
                select(UserOAuthToken).filter(
                    UserOAuthToken.account_id == uuid.UUID(account_id), UserOAuthToken.oauth_app_id == oauth_app_id
                )
            )
            existing_token = result.scalar_one_or_none()

            if existing_token:
                # Update existing token
                # UserOAuthToken.access_token/.refresh_token are auto-encrypting
                # properties — assigning an already-encrypted value here would
                # double-encrypt it, producing a token that never decrypts back
                # to something usable.
                existing_token.access_token = token
                existing_token.provider_user_id = str(user_info.get("id"))
                existing_token.provider_email = user_info.get("email")
                existing_token.provider_username = user_info.get("login")
                existing_token.provider_display_name = user_info.get("name")
                existing_token.scopes = ",".join(oauth_app.scopes or [])
            else:
                # Create new user token
                user_token = UserOAuthToken(
                    account_id=uuid.UUID(account_id),
                    oauth_app_id=oauth_app_id,
                    # See comment above — this property encrypts on assignment.
                    access_token=token,
                    provider_user_id=str(user_info.get("id")),
                    provider_email=user_info.get("email"),
                    provider_username=user_info.get("login"),
                    provider_display_name=user_info.get("name"),
                    scopes=",".join(oauth_app.scopes or []),
                )
                db.add(user_token)

            logger.info(f"GitHub OAuth successful (user-level) for app {oauth_app_id}, user {user_info.get('login')}")
        else:
            # Store on a tenant-owned clone for platform apps to prevent cross-tenant leakage
            if oauth_app.is_platform_app:
                _tenant_id_str = state_data.get("tenant_id")
                if _tenant_id_str:
                    import uuid as _uuid

                    oauth_app = await _get_or_create_tenant_clone(db, oauth_app, _uuid.UUID(_tenant_id_str))
            oauth_app.access_token = encrypt_value(token)
            logger.info(f"GitHub OAuth successful (app-level) for app {oauth_app_id}, user {user_info.get('login')}")

        await db.commit()

        # SECURITY: Use safe redirect with URL-encoded parameters
        base_url = await get_app_base_url(db, oauth_app.tenant_id)
        return _safe_success_redirect(
            redirect_url=redirect_url,
            default_path="/oauth-apps",
            base_url=base_url,
            provider="github",
            user=user_info.get("login") or "",
            user_level=str(user_level),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GitHub OAuth callback error: {e}", exc_info=True)
        # SECURITY: Get redirect URL from state and validate it
        error_state_data = get_oauth_state(state, delete=False) if state else None
        redirect_url = error_state_data.get("redirect_url") if error_state_data else None
        oauth_app_id = error_state_data.get("oauth_app_id") if error_state_data else None

        # Get base URL for validation
        base_url = "/"
        if oauth_app_id:
            oauth_app = await _get_oauth_app_secure(db, oauth_app_id)
            if oauth_app:
                base_url = await get_app_base_url(db, oauth_app.tenant_id)

        return _safe_error_redirect(redirect_url, "/oauth-apps", base_url, "github", e)


@router.post("/github/disconnect")
async def github_disconnect(
    data: GitHubDisconnectRequest,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Disconnect GitHub OAuth for an agent.

    This removes the OAuth token from the tool configuration.
    SECURITY: Requires authentication and validates tenant ownership.
    """
    try:
        # Convert agent_id string to UUID
        agent_uuid = uuid.UUID(data.agent_id)

        # SECURITY: Find the tool configuration with tenant validation
        result = await db.execute(
            select(AgentTool)
            .join(Agent, AgentTool.agent_id == Agent.id)
            .filter(
                AgentTool.agent_id == agent_uuid,
                AgentTool.tool_name == data.tool_name,
                Agent.tenant_id == tenant_id,
            )
        )
        tool = result.scalar_one_or_none()

        if not tool:
            raise HTTPException(status_code=404, detail="Tool configuration not found")

        # Get the token to revoke it
        config = tool.config or {}
        encrypted_token = config.get("GITHUB_OAUTH_TOKEN")

        if encrypted_token:
            try:
                # Try to decrypt and revoke the token
                token = decrypt_value(encrypted_token)

                # SECURITY: Get OAuth app from database with tenant validation
                oauth_app = await get_oauth_app_from_db(db, "github", tenant_id=tenant_id)

                # Decrypt client secret
                client_id = oauth_app.client_id
                client_secret = decrypt_value(oauth_app.client_secret)
                redirect_uri = oauth_app.redirect_uri

                # Initialize OAuth client and revoke token
                oauth = GitHubOAuth(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri)

                await oauth.revoke_token(token)
                logger.info("Successfully revoked GitHub OAuth token")
            except Exception as revoke_error:
                # If decryption or revocation fails, just log it and continue with deletion
                # This can happen if the token was encrypted with a different key
                logger.warning(f"Could not revoke GitHub OAuth token (will still remove from config): {revoke_error}")

        # Remove OAuth token from config
        config.pop("GITHUB_OAUTH_TOKEN", None)
        config.pop("GITHUB_USER", None)
        config.pop("GITHUB_USER_NAME", None)
        tool.config = config

        # If no other config remains, disable the tool
        if not config:
            tool.enabled = False

        await db.commit()

        logger.info(f"GitHub OAuth disconnected for agent {data.agent_id}")

        return {"success": True, "message": "GitHub OAuth disconnected successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GitHub OAuth disconnect error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/github/status")
async def github_status(
    agent_id: str,
    tool_name: str,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Check GitHub OAuth connection status for an agent.
    SECURITY: Requires authentication and validates tenant ownership.
    """
    try:
        # Convert agent_id string to UUID
        agent_uuid = uuid.UUID(agent_id)

        # SECURITY: Find the tool configuration with tenant validation
        result = await db.execute(
            select(AgentTool)
            .join(Agent, AgentTool.agent_id == Agent.id)
            .filter(
                AgentTool.agent_id == agent_uuid,
                AgentTool.tool_name == tool_name,
                Agent.tenant_id == tenant_id,
            )
        )
        tool = result.scalar_one_or_none()

        if not tool:
            return {"connected": False, "user": None}

        config = tool.config or {}
        has_oauth = "GITHUB_OAUTH_TOKEN" in config

        return {"connected": has_oauth, "user": config.get("GITHUB_USER"), "user_name": config.get("GITHUB_USER_NAME")}

    except Exception as e:
        logger.error(f"GitHub OAuth status check error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/github/repositories")
async def list_github_repositories(
    oauth_app_id: int = Query(..., description="OAuth app ID to use"),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List GitHub repositories accessible with the given OAuth app.
    This endpoint supports both OAuth and API token authentication methods.

    SECURITY: Requires authentication and verifies app belongs to tenant.
    """
    try:
        # SECURITY: Filter by tenant_id to prevent IDOR attacks
        result = await db.execute(select(OAuthApp).filter(OAuthApp.id == oauth_app_id, OAuthApp.tenant_id == tenant_id))
        oauth_app = result.scalar_one_or_none()
        if not oauth_app:
            raise HTTPException(status_code=404, detail="OAuth app not found")

        # Determine which authentication method to use
        access_token = None

        if oauth_app.auth_method == "api_token":
            # Use API token (PAT)
            if not oauth_app.api_token:
                raise HTTPException(
                    status_code=400,
                    detail="No API token configured. Please add a GitHub Personal Access Token to this OAuth app.",
                )
            try:
                access_token = decrypt_value(oauth_app.api_token)
            except Exception as e:
                logger.error(f"Failed to decrypt API token: {e}")
                raise HTTPException(status_code=500, detail="Failed to decrypt API token")
        else:
            # Use OAuth token
            if not oauth_app.access_token:
                raise HTTPException(
                    status_code=400,
                    detail="No OAuth access token available. Please complete OAuth flow first or use API token method.",
                )
            try:
                access_token = decrypt_value(oauth_app.access_token)
            except Exception as e:
                logger.error(f"Failed to decrypt access token: {e}")
                raise HTTPException(status_code=500, detail="Failed to decrypt access token")

        # Fetch repositories from GitHub API
        import aiohttp

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        async with aiohttp.ClientSession() as session:
            # Get user's repositories (including private repos if authorized)
            async with session.get(
                "https://api.github.com/user/repos",
                headers=headers,
                params={"per_page": 100, "sort": "updated", "affiliation": "owner,collaborator,organization_member"},
            ) as response:
                if response.status != 200:
                    error_data = await response.json()
                    raise HTTPException(
                        status_code=response.status,
                        detail=f"GitHub API error: {error_data.get('message', 'Unknown error')}",
                    )

                repos = await response.json()

                # Transform to our format
                repository_list = [
                    {
                        "id": repo["id"],
                        "full_name": repo["full_name"],
                        "name": repo["name"],
                        "owner": repo["owner"]["login"],
                        "description": repo.get("description"),
                        "private": repo["private"],
                        "url": repo["html_url"],
                        "default_branch": repo.get("default_branch", "main"),
                        "has_wiki": repo.get("has_wiki", False),
                        "updated_at": repo.get("updated_at"),
                    }
                    for repo in repos
                ]

                return {"repositories": repository_list, "count": len(repository_list)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List GitHub repositories error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
