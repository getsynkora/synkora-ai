"""
OAuth Controllers Package.

This package handles OAuth authentication flows for various providers.
It has been refactored from a single large file into modular components:

- base.py: Shared helpers, models, and generic OAuth initiation
- apps.py: OAuth Apps CRUD operations
- tokens.py: User tokens and platform apps management
- github.py: GitHub OAuth routes
- gitlab.py: GitLab OAuth routes
- google.py: Gmail, Google Calendar, Google Drive OAuth routes
- slack.py: Slack OAuth routes
- zoom.py: Zoom OAuth routes
- jira.py: Jira OAuth routes
- clickup.py: ClickUp OAuth routes
- twitter.py: Twitter/X OAuth routes
- linkedin.py: LinkedIn OAuth routes
- zendesk.py: Zendesk OAuth routes
- zoho.py: Zoho CRM OAuth routes

SECURITY: Uses Redis-backed state storage for CSRF protection.
SECURITY: Validates redirect URLs and URL-encodes error messages.
"""

from fastapi import APIRouter

from .apps import router as apps_router

# Import shared functions for external use
from .base import (
    GitHubDisconnectRequest,
    InitiateOAuthRequest,
    OAuthAppCreate,
    OAuthAppUpdate,
    SaveUserApiTokenRequest,
    _get_oauth_app_secure,
    _safe_error_redirect,
    _safe_success_redirect,
    get_oauth_app_from_db,
)
from .base import router as base_router
from .clickup import router as clickup_router
from .github import router as github_router
from .gitlab import router as gitlab_router
from .google import router as google_router
from .jira import router as jira_router
from .linkedin import router as linkedin_router
from .micromobility import router as micromobility_router
from .slack import router as slack_router
from .tokens import router as tokens_router
from .twitter import router as twitter_router
from .zendesk import router as zendesk_router
from .zoho import router as zoho_router
from .zoom import router as zoom_router

# Create the main router with prefix
router = APIRouter(prefix="/api/v1/oauth", tags=["oauth"])

# Include all sub-routers
router.include_router(base_router)
router.include_router(apps_router)
router.include_router(tokens_router)
router.include_router(github_router)
router.include_router(gitlab_router)
router.include_router(google_router)
router.include_router(slack_router)
router.include_router(zoom_router)
router.include_router(jira_router)
router.include_router(micromobility_router)
router.include_router(clickup_router)
router.include_router(twitter_router)
router.include_router(linkedin_router)
router.include_router(zendesk_router)
router.include_router(zoho_router)

# Export commonly used items
__all__ = [
    "router",
    "get_oauth_app_from_db",
    "_get_oauth_app_secure",
    "_safe_error_redirect",
    "_safe_success_redirect",
    "InitiateOAuthRequest",
    "OAuthAppCreate",
    "OAuthAppUpdate",
    "GitHubDisconnectRequest",
    "SaveUserApiTokenRequest",
]
