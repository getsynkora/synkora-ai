"""
Console API router.

Handles admin/management console endpoints.
"""

from fastapi import APIRouter

from .apps import router as apps_router
from .auth import router as auth_router
from .gdpr import router as gdpr_router
from .tenant_security import router as tenant_security_router

# Create main console router
console_router = APIRouter()

# Include sub-routers
console_router.include_router(auth_router, prefix="/auth", tags=["console-auth"])
console_router.include_router(apps_router, prefix="/apps", tags=["console-apps"])
console_router.include_router(gdpr_router, prefix="/account", tags=["console-gdpr"])
console_router.include_router(tenant_security_router, prefix="/tenant", tags=["console-tenant-security"])


@console_router.get("/")
async def index():
    """Console API index."""
    return {
        "message": "Console API",
        "version": "1.0.0",
        "endpoints": [
            "/auth/login",
            "/auth/register",
            "/auth/refresh",
            "/auth/logout",
            "/apps",
            "/account/erase-data",
            "/account/export-data",
            "/tenant/security",
        ],
    }
