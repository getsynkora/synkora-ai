"""
GitLab OAuth Controller.

Handles GitLab OAuth authorization, callback, and project listing.
Supports self-hosted GitLab instances via base_url in config.
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
from ...models.oauth_app import OAuthApp
from ...models.tenant import Account
from ...models.user_oauth_token import UserOAuthToken
from ...services.agents.security import decrypt_value, encrypt_value
from ...services.security.oauth_state_service import create_oauth_state, get_oauth_state
from .base import (
    _get_oauth_app_secure,
    _get_or_create_tenant_clone,
    _safe_error_redirect,
    _safe_success_redirect,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/gitlab/authorize")
async def gitlab_authorize(
    oauth_app_id: int = Query(..., description="OAuth app ID to authorize"),
    redirect_url: str = Query(None, description="Frontend redirect URL after OAuth"),
    user_level: bool = Query(False, description="Store token at user level instead of app level"),
    current_account: Account | None = Depends(get_optional_account),
    tenant_id: uuid.UUID | None = Depends(get_optional_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Initiate GitLab OAuth authorization for an OAuth app.
    Supports self-hosted GitLab instances via base_url in config.

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
            return _safe_success_redirect(redirect_url, "/oauth-apps", base_url, "gitlab", method="api_token")

        # Decrypt credentials
        client_id = oauth_app.client_id
        try:
            client_secret = decrypt_value(oauth_app.client_secret)
        except Exception as e:
            logger.error(f"Failed to decrypt client secret: {e}")
            raise HTTPException(status_code=500, detail="Failed to decrypt OAuth credentials")

        redirect_uri = oauth_app.redirect_uri

        # Get GitLab instance URL from config (for self-hosted support)
        gitlab_base_url = (
            oauth_app.config.get("base_url", "https://gitlab.com") if oauth_app.config else "https://gitlab.com"
        )

        # Initialize OAuth client
        from ...services.oauth.gitlab_oauth import GitLabOAuth

        oauth = GitLabOAuth(
            client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri, base_url=gitlab_base_url
        )

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
        scopes = oauth_app.scopes or ["api", "read_user", "read_repository", "write_repository"]
        auth_url = oauth.get_authorization_url(state=state, scopes=scopes)

        logger.info(f"Initiating GitLab OAuth for app {oauth_app_id} (user_level={user_level})")
        return RedirectResponse(url=auth_url)

    except Exception as e:
        logger.error(f"GitLab OAuth authorization error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gitlab/callback")
async def gitlab_callback(
    code: str = Query(..., description="Authorization code from GitLab"),
    state: str = Query(..., description="State parameter for CSRF protection"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Handle GitLab OAuth callback and store token.

    If user_level was set in the authorize request, stores in UserOAuthToken.
    Otherwise stores in OAuthApp (legacy behavior).

    Note: GitLab tokens expire, so we also store refresh_token and token_expires_at.
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

        # Get GitLab instance URL from config
        gitlab_base_url = (
            oauth_app.config.get("base_url", "https://gitlab.com") if oauth_app.config else "https://gitlab.com"
        )

        # Initialize OAuth client
        from ...services.oauth.gitlab_oauth import GitLabOAuth

        oauth = GitLabOAuth(
            client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri, base_url=gitlab_base_url
        )

        # Exchange code for token
        token_data = await oauth.get_access_token(code)
        if not token_data.get("access_token"):
            raise HTTPException(status_code=400, detail="Failed to get access token")

        # Get user info
        user_info = await oauth.get_user_info(token_data["access_token"])

        # Calculate token expiration
        token_expires_at = oauth.calculate_token_expiry(token_data.get("expires_in"))

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
                existing_token.access_token = encrypt_value(token_data["access_token"])
                if token_data.get("refresh_token"):
                    existing_token.refresh_token = encrypt_value(token_data["refresh_token"])
                existing_token.token_expires_at = token_expires_at
                existing_token.provider_user_id = str(user_info.get("id"))
                existing_token.provider_email = user_info.get("email")
                existing_token.provider_username = user_info.get("username")
                existing_token.provider_display_name = user_info.get("name")
                existing_token.scopes = ",".join(oauth_app.scopes or [])
            else:
                # Create new user token
                user_token = UserOAuthToken(
                    account_id=uuid.UUID(account_id),
                    oauth_app_id=oauth_app_id,
                    access_token=encrypt_value(token_data["access_token"]),
                    refresh_token=encrypt_value(token_data["refresh_token"])
                    if token_data.get("refresh_token")
                    else None,
                    token_expires_at=token_expires_at,
                    provider_user_id=str(user_info.get("id")),
                    provider_email=user_info.get("email"),
                    provider_username=user_info.get("username"),
                    provider_display_name=user_info.get("name"),
                    scopes=",".join(oauth_app.scopes or []),
                )
                db.add(user_token)

            logger.info(
                f"GitLab OAuth successful (user-level) for app {oauth_app_id}, user {user_info.get('username')}"
            )
        else:
            # Store on a tenant-owned clone for platform apps to prevent cross-tenant leakage
            if oauth_app.is_platform_app:
                _tenant_id_str = state_data.get("tenant_id")
                if _tenant_id_str:
                    import uuid as _uuid

                    oauth_app = await _get_or_create_tenant_clone(db, oauth_app, _uuid.UUID(_tenant_id_str))
            oauth_app.access_token = encrypt_value(token_data["access_token"])
            if token_data.get("refresh_token"):
                oauth_app.refresh_token = encrypt_value(token_data["refresh_token"])
            oauth_app.token_expires_at = token_expires_at.replace(tzinfo=None) if token_expires_at else None
            logger.info(f"GitLab OAuth successful (app-level) for app {oauth_app_id}, user {user_info.get('username')}")

        await db.commit()

        # SECURITY: Use safe redirect with URL-encoded parameters
        base_url = await get_app_base_url(db, oauth_app.tenant_id)
        return _safe_success_redirect(
            redirect_url=redirect_url,
            default_path="/oauth-apps",
            base_url=base_url,
            provider="gitlab",
            user=user_info.get("username") or "",
            user_level=str(user_level),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GitLab OAuth callback error: {e}", exc_info=True)
        # Get redirect URL from state (don't delete, let it expire naturally in error case)
        error_state_data = get_oauth_state(state, delete=False) if state else None
        redirect_url = error_state_data.get("redirect_url") if error_state_data else None
        oauth_app_id = error_state_data.get("oauth_app_id") if error_state_data else None
        base_url = "/"
        if oauth_app_id:
            oauth_app = await _get_oauth_app_secure(db, oauth_app_id)
            if oauth_app:
                base_url = await get_app_base_url(db, oauth_app.tenant_id)
        return _safe_error_redirect(redirect_url, "/oauth-apps", base_url, "gitlab", e)


@router.get("/gitlab/projects")
async def list_gitlab_projects(
    oauth_app_id: int = Query(..., description="OAuth app ID to use"),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List GitLab projects accessible with the given OAuth app.
    This endpoint supports both OAuth and API token (Personal Access Token) authentication methods.

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
                    detail="No API token configured. Please add a GitLab Personal Access Token to this OAuth app.",
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

        # Get GitLab instance URL from config
        gitlab_base_url = (
            oauth_app.config.get("base_url", "https://gitlab.com") if oauth_app.config else "https://gitlab.com"
        )
        api_url = f"{gitlab_base_url.rstrip('/')}/api/v4"

        # Fetch projects from GitLab API
        import aiohttp

        # GitLab uses PRIVATE-TOKEN header for PAT, Authorization header for OAuth
        if oauth_app.auth_method == "api_token":
            headers = {"PRIVATE-TOKEN": access_token}
        else:
            headers = {"Authorization": f"Bearer {access_token}"}

        async with aiohttp.ClientSession() as session:
            # Get user's projects (membership=true returns projects the user is a member of)
            async with session.get(
                f"{api_url}/projects",
                headers=headers,
                params={"per_page": 100, "order_by": "last_activity_at", "sort": "desc", "membership": "true"},
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise HTTPException(status_code=response.status, detail=f"GitLab API error: {error_text}")

                projects = await response.json()

                # Transform to our format
                project_list = [
                    {
                        "id": project["id"],
                        "full_name": project["path_with_namespace"],
                        "name": project["name"],
                        "owner": project["namespace"]["name"] if project.get("namespace") else None,
                        "description": project.get("description"),
                        "private": project.get("visibility") == "private",
                        "url": project["web_url"],
                        "default_branch": project.get("default_branch", "main"),
                        "has_wiki": project.get("wiki_enabled", False),
                        "updated_at": project.get("last_activity_at"),
                    }
                    for project in projects
                ]

                return {"projects": project_list, "count": len(project_list)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List GitLab projects error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
