"""SCIM 2.0 controller.

Implements RFC 7643 / 7644 endpoints for automated user provisioning.
All /scim/v2/* endpoints authenticate via SCIM bearer token (issued per-tenant).
Management endpoints (POST/GET/DELETE /api/v1/scim/tokens) use the normal JWT
auth and require ADMIN or OWNER role.

Endpoints
---------
Public (no JWT auth needed):
    GET  /scim/v2/ServiceProviderConfig

SCIM Bearer token auth:
    GET    /scim/v2/Users
    POST   /scim/v2/Users
    GET    /scim/v2/Users/{id}
    PUT    /scim/v2/Users/{id}
    PATCH  /scim/v2/Users/{id}
    DELETE /scim/v2/Users/{id}

JWT admin auth (management):
    POST   /api/v1/scim/tokens
    GET    /api/v1/scim/tokens
    DELETE /api/v1/scim/tokens/{id}
"""

import json
import logging
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

import src.services.scim_service as scim_service
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id, require_role
from src.models.tenant import Account, AccountRole

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
scim_router = APIRouter()

# Content-type for all SCIM responses per RFC 7644 §8.2
_SCIM_MEDIA = "application/scim+json"


def _scim_response(data: dict, status_code: int = 200) -> Response:
    """Return a Response with application/scim+json content-type."""
    return Response(
        content=json.dumps(data),
        status_code=status_code,
        media_type=_SCIM_MEDIA,
    )


def _scim_error(detail: str, status_code: int) -> Response:
    """Return a SCIM-compliant error response."""
    body = {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
        "detail": detail,
        "status": str(status_code),
    }
    return Response(
        content=json.dumps(body),
        status_code=status_code,
        media_type=_SCIM_MEDIA,
    )


# ---------------------------------------------------------------------------
# SCIM Bearer token dependency
# ---------------------------------------------------------------------------


async def get_scim_tenant(
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_async_db),
) -> uuid.UUID:
    """
    Validate the SCIM bearer token and return the associated tenant_id.

    SECURITY: Returns 404 (not 401/403) for missing/invalid tokens to avoid
    leaking information about which tenants have SCIM configured.
    """
    if not authorization or not authorization.startswith("Bearer "):
        # Use 401 only for missing header so IdPs know to send credentials
        raise HTTPException(status_code=401, detail="SCIM Bearer token required")
    token = authorization[7:]
    scim_token = await scim_service.validate_scim_token(db, token)
    if not scim_token:
        # 404 per spec guidance — avoids confirming tenant existence
        raise HTTPException(status_code=404, detail="Not Found")
    return scim_token.tenant_id


# ---------------------------------------------------------------------------
# ServiceProviderConfig (public — no auth)
# ---------------------------------------------------------------------------


@scim_router.get("/scim/v2/ServiceProviderConfig", include_in_schema=True)
async def service_provider_config() -> Response:
    """
    SCIM 2.0 ServiceProviderConfig.

    Advertises which SCIM features this implementation supports.
    This endpoint is intentionally public per RFC 7644 §4.
    """
    config = {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"],
        "documentationUri": "",
        "patch": {"supported": True},
        "bulk": {"supported": False, "maxOperations": 0, "maxPayloadSize": 0},
        "filter": {"supported": True, "maxResults": 200},
        "changePassword": {"supported": False},
        "sort": {"supported": False},
        "etag": {"supported": False},
        "authenticationSchemes": [
            {
                "name": "OAuth Bearer Token",
                "description": "Authentication scheme using the OAuth Bearer Token Standard",
                "specUri": "http://www.rfc-editor.org/info/rfc6750",
                "type": "oauthbearertoken",
                "primary": True,
            }
        ],
        # Groups resource is advertised but not yet implemented (returns 501)
        "supportedResources": [
            {"name": "User", "endpoint": "/scim/v2/Users", "supported": True},
            {"name": "Group", "endpoint": "/scim/v2/Groups", "supported": False},
        ],
        "meta": {
            "resourceType": "ServiceProviderConfig",
            "location": "/scim/v2/ServiceProviderConfig",
        },
    }
    return _scim_response(config)


# ---------------------------------------------------------------------------
# Users collection
# ---------------------------------------------------------------------------


@scim_router.get("/scim/v2/Users", include_in_schema=True)
async def list_users(
    request: Request,
    tenant_id: uuid.UUID = Depends(get_scim_tenant),
    db: AsyncSession = Depends(get_async_db),
) -> Response:
    """List Users for the tenant (with optional SCIM filter and pagination)."""
    params = request.query_params
    start_index = max(1, int(params.get("startIndex", "1")))
    count = max(1, min(int(params.get("count", "100")), 200))
    filter_str = params.get("filter")

    data = await scim_service.list_users(db, tenant_id, start_index=start_index, count=count, filter_str=filter_str)
    return _scim_response(data)


@scim_router.post("/scim/v2/Users", include_in_schema=True)
async def create_user(
    request: Request,
    tenant_id: uuid.UUID = Depends(get_scim_tenant),
    db: AsyncSession = Depends(get_async_db),
) -> Response:
    """Provision a new User for the tenant."""
    try:
        body = await request.json()
    except Exception:
        return _scim_error("Invalid JSON body", 400)

    try:
        user = await scim_service.create_user(db, tenant_id, body)
    except ValueError as exc:
        return _scim_error(str(exc), 400)

    return _scim_response(user, status_code=201)


# ---------------------------------------------------------------------------
# Individual User
# ---------------------------------------------------------------------------


@scim_router.get("/scim/v2/Users/{user_id}", include_in_schema=True)
async def get_user(
    user_id: str,
    tenant_id: uuid.UUID = Depends(get_scim_tenant),
    db: AsyncSession = Depends(get_async_db),
) -> Response:
    """Return a single User resource."""
    user = await scim_service.get_user(db, tenant_id, user_id)
    if user is None:
        return _scim_error("User not found", 404)
    return _scim_response(user)


@scim_router.put("/scim/v2/Users/{user_id}", include_in_schema=True)
async def replace_user(
    user_id: str,
    request: Request,
    tenant_id: uuid.UUID = Depends(get_scim_tenant),
    db: AsyncSession = Depends(get_async_db),
) -> Response:
    """Full replace (PUT) of a User resource."""
    try:
        body = await request.json()
    except Exception:
        return _scim_error("Invalid JSON body", 400)

    try:
        user = await scim_service.update_user(db, tenant_id, user_id, body)
    except ValueError as exc:
        return _scim_error(str(exc), 400)
    if user is None:
        return _scim_error("User not found", 404)
    return _scim_response(user)


@scim_router.patch("/scim/v2/Users/{user_id}", include_in_schema=True)
async def patch_user(
    user_id: str,
    request: Request,
    tenant_id: uuid.UUID = Depends(get_scim_tenant),
    db: AsyncSession = Depends(get_async_db),
) -> Response:
    """Partial update (PATCH) of a User resource."""
    try:
        body = await request.json()
    except Exception:
        return _scim_error("Invalid JSON body", 400)

    ops = body.get("Operations", [])
    if not isinstance(ops, list):
        return _scim_error("Operations must be a list", 400)

    try:
        user = await scim_service.patch_user(db, tenant_id, user_id, ops)
    except ValueError as exc:
        return _scim_error(str(exc), 400)
    if user is None:
        return _scim_error("User not found", 404)
    return _scim_response(user)


@scim_router.delete("/scim/v2/Users/{user_id}", include_in_schema=True)
async def delete_user(
    user_id: str,
    tenant_id: uuid.UUID = Depends(get_scim_tenant),
    db: AsyncSession = Depends(get_async_db),
) -> Response:
    """Deactivate (soft-delete) a User."""
    found = await scim_service.delete_user(db, tenant_id, user_id)
    if not found:
        return _scim_error("User not found", 404)
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Groups — stub (not yet implemented, returns 501 / empty list)
# ---------------------------------------------------------------------------

_SCIM_GROUPS_NOT_IMPLEMENTED = {
    "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
    "detail": "Groups resource is not yet implemented.",
    "status": "501",
}


@scim_router.get("/scim/v2/Groups", include_in_schema=True)
async def list_groups(
    tenant_id: uuid.UUID = Depends(get_scim_tenant),
) -> Response:
    """Return an empty Groups list (Groups not yet implemented)."""
    data = {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
        "totalResults": 0,
        "startIndex": 1,
        "itemsPerPage": 0,
        "Resources": [],
    }
    return _scim_response(data)


@scim_router.post("/scim/v2/Groups", include_in_schema=True)
async def create_group(
    tenant_id: uuid.UUID = Depends(get_scim_tenant),
) -> Response:
    """Groups creation is not yet implemented — returns 501."""
    return _scim_response(_SCIM_GROUPS_NOT_IMPLEMENTED, status_code=501)


@scim_router.get("/scim/v2/Groups/{group_id}", include_in_schema=True)
async def get_group(
    group_id: str,
    tenant_id: uuid.UUID = Depends(get_scim_tenant),
) -> Response:
    """Group lookup is not yet implemented — returns 404."""
    not_found = {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
        "detail": f"Group {group_id} not found.",
        "status": "404",
    }
    return _scim_response(not_found, status_code=404)


@scim_router.put("/scim/v2/Groups/{group_id}", include_in_schema=True)
async def replace_group(
    group_id: str,
    tenant_id: uuid.UUID = Depends(get_scim_tenant),
) -> Response:
    """Group replacement is not yet implemented — returns 501."""
    return _scim_response(_SCIM_GROUPS_NOT_IMPLEMENTED, status_code=501)


@scim_router.delete("/scim/v2/Groups/{group_id}", include_in_schema=True)
async def delete_group(
    group_id: str,
    tenant_id: uuid.UUID = Depends(get_scim_tenant),
) -> Response:
    """Group deletion is not yet implemented — returns 501."""
    return _scim_response(_SCIM_GROUPS_NOT_IMPLEMENTED, status_code=501)


# ---------------------------------------------------------------------------
# SCIM Token management (JWT admin auth)
# ---------------------------------------------------------------------------


@scim_router.post("/api/v1/scim/tokens", include_in_schema=True)
async def create_token(
    request: Request,
    current_account: Account = Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    _: None = Depends(require_role(AccountRole.ADMIN)),
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    """
    Generate a new SCIM bearer token for the tenant.

    The plaintext token is returned ONCE. Store it securely — it cannot be
    retrieved again.
    """
    try:
        body = await request.json()
        description = body.get("description")
    except Exception:
        description = None

    plaintext, token = await scim_service.create_scim_token(db, tenant_id, description=description)
    return {
        "id": str(token.id),
        "token": plaintext,  # shown once only
        "description": token.description,
        "is_active": token.is_active,
        "created_at": token.created_at.isoformat() if token.created_at else None,
    }


@scim_router.get("/api/v1/scim/tokens", include_in_schema=True)
async def list_tokens(
    current_account: Account = Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    _: None = Depends(require_role(AccountRole.ADMIN)),
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    """List all SCIM tokens for the tenant (no plaintext returned)."""
    tokens = await scim_service.list_scim_tokens(db, tenant_id)
    return {
        "tokens": [
            {
                "id": str(t.id),
                "description": t.description,
                "is_active": t.is_active,
                "last_used_at": t.last_used_at.isoformat() if t.last_used_at else None,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tokens
        ]
    }


@scim_router.delete("/api/v1/scim/tokens/{token_id}", include_in_schema=True)
async def revoke_token(
    token_id: uuid.UUID,
    current_account: Account = Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    _: None = Depends(require_role(AccountRole.ADMIN)),
    db: AsyncSession = Depends(get_async_db),
) -> Response:
    """Revoke (deactivate) a SCIM token."""
    revoked = await scim_service.revoke_scim_token(db, tenant_id, token_id)
    if not revoked:
        raise HTTPException(status_code=404, detail="SCIM token not found")
    return Response(status_code=204)
