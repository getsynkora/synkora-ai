"""
OAuth Base Module.

Contains shared helpers, models, and the generic OAuth initiation endpoint.

SECURITY: Uses Redis-backed state storage for CSRF protection.
SECURITY: Validates redirect URLs and URL-encodes error messages.
"""

import logging
import uuid
from typing import cast

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.utils.config_helper import get_app_base_url

from ...core.database import get_async_db
from ...middleware.auth_middleware import (
    get_current_account,
    get_current_tenant_id,
)
from ...models.oauth_app import OAuthApp
from ...models.tenant import Account
from ...services.agents.security import decrypt_value
from ...services.oauth import GitHubOAuth
from ...services.oauth.clickup_oauth import ClickUpOAuth
from ...services.oauth.gmail_oauth import GmailOAuth
from ...services.oauth.jira_oauth import JiraOAuth
from ...services.oauth.slack_oauth import SlackOAuth
from ...services.security.oauth_security import (
    build_oauth_redirect_url,
    sanitize_redirect_url,
)
from ...services.security.oauth_state_service import create_oauth_state

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Shared Helper Functions
# =============================================================================


async def _get_oauth_app_secure(
    db: AsyncSession,
    oauth_app_id: int,
    tenant_id: uuid.UUID | None = None,
    require_tenant: bool = False,
    allow_platform_apps: bool = True,
) -> OAuthApp | None:
    """
    Securely retrieve an OAuthApp with tenant verification.

    SECURITY: Prevents IDOR attacks by verifying tenant ownership when tenant_id is provided.
    Platform apps (is_platform_app=True) are accessible to all tenants.

    Args:
        db: Async database session
        oauth_app_id: OAuth app ID to retrieve
        tenant_id: Optional tenant ID for authorization check
        require_tenant: If True, raises error when tenant_id is not provided
        allow_platform_apps: If True, allows access to platform apps (default True)

    Returns:
        OAuthApp if found and authorized, None otherwise

    Raises:
        HTTPException: If require_tenant=True and tenant_id is not provided,
                      or if app exists but belongs to different tenant
    """
    if require_tenant and not tenant_id:
        raise HTTPException(
            status_code=401,
            detail="Authentication required to access OAuth apps",
        )

    # Get the app first
    result = await db.execute(select(OAuthApp).filter(OAuthApp.id == oauth_app_id))
    oauth_app = result.scalar_one_or_none()

    if not oauth_app:
        return None

    # Platform apps are accessible to all tenants (if allowed)
    if oauth_app.is_platform_app:
        if allow_platform_apps:
            # Check if platform app is enabled for this tenant
            if tenant_id:
                from ...models.tenant import Tenant

                result = await db.execute(select(Tenant).filter(Tenant.id == tenant_id))
                tenant = result.scalar_one_or_none()
                if tenant:
                    disabled = tenant.disabled_platform_oauth_providers or []
                    if oauth_app.provider.lower() in [p.lower() for p in disabled]:
                        return None
            return oauth_app
        return None

    # For tenant-owned apps, verify tenant ownership
    if tenant_id:
        if oauth_app.tenant_id != tenant_id:
            logger.warning(
                f"IDOR attempt: OAuth app {oauth_app_id} accessed by tenant {tenant_id}, "
                f"but belongs to tenant {oauth_app.tenant_id}"
            )
            return None

    return oauth_app


def _safe_error_redirect(
    redirect_url: str | None,
    default_path: str,
    base_url: str,
    provider: str,
    error: Exception | str,
) -> RedirectResponse:
    """
    Create a safe error redirect response.

    SECURITY: Validates redirect URL and URL-encodes error message.

    Args:
        redirect_url: The redirect URL from state (may be untrusted)
        default_path: Default path if redirect is invalid
        base_url: Base URL for validation
        provider: OAuth provider name
        error: Error exception or message

    Returns:
        Safe RedirectResponse
    """
    # Sanitize redirect URL
    safe_redirect = sanitize_redirect_url(redirect_url, f"{base_url}{default_path}", base_url)

    # Build safe redirect URL with encoded error
    error_msg = str(error) if error else "Unknown error"
    final_url = build_oauth_redirect_url(
        safe_redirect,
        success=False,
        provider=provider,
        error_message=error_msg,
    )
    return RedirectResponse(url=final_url)


def _safe_success_redirect(
    redirect_url: str | None,
    default_path: str,
    base_url: str,
    provider: str,
    **kwargs,
) -> RedirectResponse:
    """
    Create a safe success redirect response.

    SECURITY: Validates redirect URL and URL-encodes all parameters.

    Args:
        redirect_url: The redirect URL from state (may be untrusted)
        default_path: Default path if redirect is invalid
        base_url: Base URL for validation
        provider: OAuth provider name
        **kwargs: Additional parameters to include (will be URL-encoded)

    Returns:
        Safe RedirectResponse
    """
    # Sanitize redirect URL
    safe_redirect = sanitize_redirect_url(redirect_url, f"{base_url}{default_path}", base_url)

    # Build safe redirect URL with encoded parameters
    final_url = build_oauth_redirect_url(
        safe_redirect,
        success=True,
        provider=provider,
        **kwargs,
    )
    return RedirectResponse(url=final_url)


async def _get_or_create_tenant_clone(
    db: AsyncSession,
    platform_app: OAuthApp,
    tenant_id: uuid.UUID,
) -> OAuthApp:
    """
    Get or create a tenant-owned clone of a platform OAuth app.

    When an admin connects a platform app company-wide (user_level=False), we create a
    tenant-specific OAuthApp row instead of writing to the shared platform app row.
    This prevents cross-tenant token leakage.

    The clone is identified by config->platform_app_id pointing back to the source.
    Credentials (client_id, client_secret, redirect_uri, scopes) are copied so the
    OAuth flow works identically. The resulting access_token is stored on the clone.
    """
    result = await db.execute(
        select(OAuthApp).filter(
            OAuthApp.tenant_id == tenant_id,
            OAuthApp.provider == platform_app.provider,
            OAuthApp.is_platform_app.is_(False),
            OAuthApp.config["platform_app_id"].as_string() == str(platform_app.id),
        )
    )
    clone = result.scalar_one_or_none()

    if not clone:
        clone = OAuthApp(
            tenant_id=tenant_id,
            provider=platform_app.provider,
            app_name=platform_app.app_name,
            auth_method=platform_app.auth_method,
            client_id=platform_app.client_id,
            client_secret=platform_app.client_secret,  # already encrypted
            redirect_uri=platform_app.redirect_uri,
            scopes=platform_app.scopes,
            config={**(platform_app.config or {}), "platform_app_id": str(platform_app.id)},
            is_active=True,
            is_default=True,
            description=platform_app.description,
        )
        db.add(clone)
        await db.flush()

        # Remap any AgentTool rows in this tenant that were assigned the platform app id
        # (happens when PE assigns tools before admin connects the integration).
        from sqlalchemy import update as sa_update

        from ...models.agent import Agent
        from ...models.agent_tool import AgentTool

        await db.execute(
            sa_update(AgentTool)
            .where(
                AgentTool.oauth_app_id == platform_app.id,
                AgentTool.agent_id.in_(
                    select(Agent.id).where(Agent.tenant_id == tenant_id)
                ),
            )
            .values(oauth_app_id=clone.id)
        )
        logger.info(
            "Remapped AgentTool rows from platform app %s → clone %s (provider=%s, tenant=%s)",
            platform_app.id,
            clone.id,
            platform_app.provider,
            tenant_id,
        )

    return clone


async def get_oauth_app_from_db(
    db: AsyncSession,
    provider: str,
    tenant_id: uuid.UUID = None,
    app_id: int = None,
    auth_method: str = None,
    include_platform_apps: bool = True,
) -> OAuthApp:
    """
    Get OAuth app credentials from database with platform app fallback.

    Args:
        db: Async database session
        provider: OAuth provider name (e.g., 'github')
        tenant_id: Tenant ID for security filtering (REQUIRED for authenticated requests)
        app_id: Specific app ID (optional, will use default if not provided)
        auth_method: Filter by auth method ('oauth' or 'api_token'). If None, returns any.
        include_platform_apps: If True, fallback to platform apps when no tenant app found

    Returns:
        OAuthApp instance

    Raises:
        HTTPException: If no OAuth app is configured
    """
    provider = provider.lower()
    oauth_app = None

    # If specific app_id provided, get that app
    if app_id:
        oauth_app = await _get_oauth_app_secure(
            db, app_id, tenant_id=tenant_id, allow_platform_apps=include_platform_apps
        )
        if oauth_app:
            return oauth_app
        raise HTTPException(
            status_code=404,
            detail=f"{provider.title()} OAuth app not found.",
        )

    # Try tenant's own apps first
    if tenant_id:
        base_query = select(OAuthApp).filter(
            OAuthApp.provider == provider,
            OAuthApp.is_active.is_(True),
            OAuthApp.tenant_id == tenant_id,
        )

        # Get default app for this provider (prefer OAuth method if not specified)
        if not auth_method:
            # First try to get default OAuth app
            result = await db.execute(base_query.filter(OAuthApp.is_default.is_(True), OAuthApp.auth_method == "oauth"))
            oauth_app = result.scalar_one_or_none()

            # If no OAuth default, try API token default
            if not oauth_app:
                result = await db.execute(base_query.filter(OAuthApp.is_default.is_(True)))
                oauth_app = result.scalar_one_or_none()
        else:
            result = await db.execute(
                base_query.filter(OAuthApp.auth_method == auth_method, OAuthApp.is_default.is_(True))
            )
            oauth_app = result.scalar_one_or_none()

        # If no default, get any active app (prefer OAuth if not specified)
        if not oauth_app:
            if not auth_method:
                result = await db.execute(base_query.filter(OAuthApp.auth_method == "oauth"))
                oauth_app = result.scalar_one_or_none()
            if not oauth_app:
                if auth_method:
                    result = await db.execute(base_query.filter(OAuthApp.auth_method == auth_method))
                else:
                    result = await db.execute(base_query)
                oauth_app = result.scalar_one_or_none()

    # Fallback to platform app if no tenant app found and platform apps are enabled
    if not oauth_app and include_platform_apps:
        # Check if platform app is enabled for this tenant
        platform_enabled = True
        if tenant_id:
            from ...models.tenant import Tenant

            result = await db.execute(select(Tenant).filter(Tenant.id == tenant_id))
            tenant = result.scalar_one_or_none()
            if tenant:
                disabled = tenant.disabled_platform_oauth_providers or []
                platform_enabled = provider not in [p.lower() for p in disabled]

        if platform_enabled:
            platform_query = select(OAuthApp).filter(
                OAuthApp.provider == provider,
                OAuthApp.is_active.is_(True),
                OAuthApp.is_platform_app.is_(True),
                OAuthApp.tenant_id.is_(None),
            )
            if auth_method:
                platform_query = platform_query.filter(OAuthApp.auth_method == auth_method)
            result = await db.execute(platform_query)
            oauth_app = result.scalar_one_or_none()

    if not oauth_app:
        raise HTTPException(
            status_code=404,
            detail=f"{provider.title()} OAuth not configured. Please create an OAuth app for {provider.title()} in the OAuth Apps settings page first.",
        )

    return oauth_app


# =============================================================================
# Pydantic Models
# =============================================================================


class InitiateOAuthRequest(BaseModel):
    """Request model for initiating OAuth via AJAX."""

    oauth_app_id: int
    redirect_url: str | None = None
    user_level: bool = False


class OAuthAppCreate(BaseModel):
    provider: str
    app_name: str
    auth_method: str = "oauth"  # 'oauth' or 'api_token'

    # OAuth fields (required when auth_method = 'oauth')
    client_id: str | None = None
    client_secret: str | None = None
    redirect_uri: str | None = None
    scopes: list[str] | None = None

    # API Token fields (required when auth_method = 'api_token')
    api_token: str | None = None

    # Provider-specific config (e.g., region for Recall.ai, base_url for GitLab)
    config: dict | None = None

    # Common fields
    is_default: bool = False
    description: str | None = None
    tags: list[str] | None = None
    is_internal_tool: bool = False


class OAuthAppUpdate(BaseModel):
    app_name: str | None = None
    auth_method: str | None = None

    # OAuth fields
    client_id: str | None = None
    client_secret: str | None = None
    redirect_uri: str | None = None
    scopes: list[str] | None = None

    # API Token fields
    api_token: str | None = None

    # Provider-specific config
    config: dict | None = None

    # Common fields
    is_active: bool | None = None
    is_default: bool | None = None
    description: str | None = None
    tags: list[str] | None = None
    is_internal_tool: bool | None = None


class GitHubDisconnectRequest(BaseModel):
    agent_id: str  # UUID as string
    tool_name: str


class SaveUserApiTokenRequest(BaseModel):
    """Request model for saving user's personal API token."""

    oauth_app_id: int
    api_token: str


# =============================================================================
# Generic OAuth Initiation Endpoint
# =============================================================================


@router.post("/initiate")
async def initiate_oauth(
    data: InitiateOAuthRequest,
    current_account: Account = Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Securely initiate OAuth flow for user-level token storage.

    This is the industry-standard approach for cross-origin OAuth:
    1. Frontend calls this endpoint via AJAX with Authorization header
    2. Backend creates OAuth state with user context
    3. Returns the auth_url for frontend to redirect to
    4. Callback uses state to look up user context (no token in URL)

    Args:
        data: OAuth initiation request
        current_account: Authenticated user (from Authorization header)
        db: Database session

    Returns:
        auth_url: The OAuth provider's authorization URL to redirect to
    """
    try:
        # SECURITY: Validate OAuth app belongs to current tenant (prevents IDOR)
        oauth_app = await _get_oauth_app_secure(db, data.oauth_app_id, tenant_id=tenant_id)
        if not oauth_app:
            raise HTTPException(status_code=404, detail="OAuth app not found")

        provider = oauth_app.provider.lower()
        base_url = await get_app_base_url(db, oauth_app.tenant_id or tenant_id)
        redirect_url = data.redirect_url or f"{base_url}/oauth-apps"

        # API token / basic_auth / github_app don't need an OAuth browser flow
        if oauth_app.auth_method in ("api_token", "basic_auth", "github_app"):
            # For platform GitHub App, create the tenant clone immediately — no callback will do it
            if oauth_app.is_platform_app and oauth_app.auth_method == "github_app":
                await _get_or_create_tenant_clone(db, oauth_app, tenant_id)
                await db.commit()
            return {
                "auth_url": f"{redirect_url}?oauth=success&provider={provider}&method={oauth_app.auth_method}",
                "method": oauth_app.auth_method,
            }

        # Decrypt credentials
        client_id = oauth_app.client_id
        try:
            client_secret = decrypt_value(oauth_app.client_secret)
        except Exception as e:
            logger.error(f"Failed to decrypt client secret: {e}")
            raise HTTPException(status_code=500, detail="Failed to decrypt OAuth credentials")

        redirect_uri = oauth_app.redirect_uri

        # SECURITY: Generate state for CSRF protection with user context (Redis-backed)
        state = create_oauth_state(
            {
                "oauth_app_id": data.oauth_app_id,
                "redirect_url": redirect_url,
                "user_level": data.user_level,
                "account_id": str(current_account.id) if data.user_level else None,
                "tenant_id": str(tenant_id),
            }
        )
        if not state:
            raise HTTPException(status_code=500, detail="Failed to create OAuth state")

        # Get authorization URL based on provider
        auth_url = None
        if provider == "github":
            oauth = GitHubOAuth(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri)
            scopes = oauth_app.scopes or ["repo", "user", "read:org"]
            auth_url = oauth.get_authorization_url(state=state, scopes=scopes)
        elif provider == "slack":
            oauth = SlackOAuth(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri)
            scopes = oauth_app.scopes or ["chat:write", "users:read", "channels:read"]
            auth_url = oauth.get_authorization_url(state=state, scopes=scopes)
        elif provider == "zoom":
            from ...services.oauth.zoom_oauth import ZoomOAuth

            oauth = ZoomOAuth(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri)
            auth_url = oauth.get_authorization_url(state=state)
        elif provider == "google_calendar":
            from ...services.oauth.google_calendar_oauth import GoogleCalendarOAuth

            oauth = GoogleCalendarOAuth(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri)
            auth_url = oauth.get_authorization_url(state=state)
        elif provider == "google_drive":
            from ...services.oauth.google_drive_oauth import GoogleDriveOAuth

            oauth = GoogleDriveOAuth(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri)
            auth_url = oauth.get_authorization_url(state=state)
        elif provider == "gmail":
            oauth = GmailOAuth(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri)
            auth_url = oauth.get_authorization_url(state=state)
        elif provider == "gitlab":
            gitlab_base_url = (
                oauth_app.config.get("base_url", "https://gitlab.com") if oauth_app.config else "https://gitlab.com"
            )
            from ...services.oauth.gitlab_oauth import GitLabOAuth

            oauth = GitLabOAuth(
                client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri, base_url=gitlab_base_url
            )
            scopes = oauth_app.scopes or ["api", "read_user", "read_repository", "write_repository"]
            auth_url = oauth.get_authorization_url(state=state, scopes=scopes)
        elif provider == "jira":
            oauth = JiraOAuth(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri)
            scopes = oauth_app.scopes or [
                "read:me",
                "read:jira-work",
                "read:jira-user",
                "write:jira-work",
                "read:board-scope:jira-software",
                "read:sprint:jira-software",
                "write:sprint:jira-software",
                "offline_access",
            ]
            auth_url = oauth.get_authorization_url(state=state, scopes=scopes)
        elif provider == "clickup":
            oauth = ClickUpOAuth(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri)
            auth_url = oauth.get_authorization_url(state=state)
        elif provider == "twitter":
            from ...services.oauth.twitter_oauth import TwitterOAuth

            oauth = TwitterOAuth(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri)
            scopes = oauth_app.scopes or ["tweet.read", "tweet.write", "users.read", "offline.access"]
            code_verifier: str
            auth_url, code_verifier = cast(tuple[str, str], oauth.get_authorization_url(state=state, scopes=scopes))
            # Store code_verifier in state for PKCE verification
            from ...services.security.oauth_state_service import update_oauth_state

            update_oauth_state(state, {"code_verifier": code_verifier})
        elif provider == "linkedin":
            from ...services.oauth.linkedin_oauth import LinkedInOAuth

            oauth = LinkedInOAuth(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri)
            scopes = oauth_app.scopes or ["openid", "profile", "email", "w_member_social"]
            auth_url = oauth.get_authorization_url(state=state, scopes=scopes)
        elif provider == "zendesk":
            from ...services.oauth.zendesk_oauth import ZendeskOAuth

            subdomain = (oauth_app.config or {}).get("subdomain", "").strip()
            if not subdomain:
                raise HTTPException(status_code=400, detail="Zendesk subdomain not configured for this OAuth app")
            oauth = ZendeskOAuth(
                client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri, subdomain=subdomain
            )
            scopes = oauth_app.scopes or ["read", "write"]
            auth_url = oauth.get_authorization_url(state=state, scopes=scopes)
        elif provider == "zoho_crm":
            from ...services.oauth.zoho_crm_oauth import ZohoCRMOAuth

            dc = (oauth_app.config or {}).get("data_center", "com")
            oauth = ZohoCRMOAuth(
                client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri, data_center=dc
            )
            scopes = oauth_app.scopes or [
                "ZohoCRM.modules.ALL",
                "ZohoCRM.settings.ALL",
                "ZohoCRM.users.READ",
                "ZohoCRM.org.READ",
                "offline_access",
            ]
            auth_url = oauth.get_authorization_url(state=state, scopes=scopes)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

        logger.info(
            f"Initiated OAuth for {provider} app {data.oauth_app_id} (user_level={data.user_level}, account={current_account.id})"
        )

        return {"auth_url": auth_url, "state": state, "provider": provider}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OAuth initiation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
