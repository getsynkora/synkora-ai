"""
Plan Restriction Middleware

Automatically enforces subscription plan limits on resource creation endpoints.

NOTE: Uses pure ASGI pattern instead of BaseHTTPMiddleware to avoid
TaskGroup cancellation issues with async database sessions.
"""

import json
import logging
from typing import Any
from uuid import UUID

import jwt
from sqlalchemy import select
from starlette.requests import Request as StarletteRequest
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from src.core.database import get_async_session_factory
from src.models.tenant import Tenant, TenantType
from src.services import AuthService
from src.services.billing import PlanRestrictionError, PlanRestrictionService
from src.services.billing.plan_restriction_service import (
    SubscriptionCancelledError,
    SubscriptionExpiredError,
    SubscriptionSuspendedError,
)

logger = logging.getLogger(__name__)


def create_cors_json_response(origin: str, status_code: int, content: dict[str, Any]) -> JSONResponse:
    """
    Create a JSONResponse with CORS headers.

    This is needed because middleware responses bypass the CORS middleware,
    so we need to manually add CORS headers for the browser to read the response.
    """
    response = JSONResponse(status_code=status_code, content=content)
    response.headers["Access-Control-Allow-Origin"] = origin or "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


def extract_tenant_id_from_request(request: StarletteRequest) -> UUID | None:
    """
    Extract tenant_id directly from JWT token in Authorization header.

    This is needed because middleware runs before FastAPI dependencies,
    so request.state.tenant_id is not yet set.
    """
    authorization = request.headers.get("Authorization")
    if not authorization:
        return None

    # Extract token from "Bearer <token>" format
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        token = parts[1]
    elif len(parts) == 1:
        token = parts[0]
    else:
        return None

    try:
        payload = AuthService.decode_token(token)
        if "tenant_id" in payload:
            return UUID(payload["tenant_id"])
    except (jwt.InvalidTokenError, KeyError, ValueError, Exception) as e:
        logger.debug(f"Failed to extract tenant_id from token: {e}")

    return None


# Mapping of endpoint paths to resource types
# NOTE: Each resource type must have a corresponding enforce_{type}_limit method
# in PlanRestrictionService. Add new endpoints here when service methods are implemented.
RESOURCE_LIMIT_ENDPOINTS = {
    # Agents - only the base endpoint for creating new agents
    # More specific paths like /conversations, /chat, /{name}/clone should NOT trigger agent limits
    "/api/v1/agents": "agent",
    # Knowledge Bases
    "/api/v1/knowledge-bases": "knowledge_base",
    # MCP Servers (actual route is /api/v1/mcp/servers)
    "/api/v1/mcp/servers": "mcp_server",
    # Custom Tools
    "/api/v1/custom-tools": "custom_tool",
    # Database Connections
    "/api/v1/database-connections": "database_connection",
    # Data Sources
    "/api/v1/data-sources": "data_source",
    # Scheduled Tasks
    "/api/v1/scheduled-tasks": "scheduled_task",
    # Widgets
    "/api/v1/widgets": "widget",
    # Slack Bots
    "/api/v1/slack-bots": "slack_bot",
    # API Keys
    "/api/v1/agent-api-keys": "api_key",
    # Team Members (invitations)
    "/api/v1/teams/invite": "team_member",
    # Future bot platforms can be added here:
    # "/api/v1/telegram-bots": "telegram_bot",
    # "/api/v1/whatsapp-bots": "whatsapp_bot",
    # "/api/v1/teams-bots": "teams_bot",
}

# Paths that should be excluded from resource limit checks even though they match a prefix
# These are sub-endpoints that don't create new resources of the parent type
RESOURCE_LIMIT_EXCLUSIONS = {
    "/api/v1/agents": [
        "/api/v1/agents/conversations",  # Creating conversations, not agents
        "/api/v1/agents/chat",  # Chat endpoints
        "/api/v1/agents/public",  # Public agent queries
        "/api/v1/agents/explore",  # Explore endpoints
    ],
}

# Pattern-based exclusions - these patterns are checked using 'in' operator
# for paths with dynamic segments like UUIDs
RESOURCE_LIMIT_PATTERN_EXCLUSIONS = {
    "/api/v1/agents": [
        "/capabilities/",  # Enabling capabilities on existing agents, not creating new agents
        "/capabilities",  # Also match without trailing slash
        "/tools/",  # Managing tools on existing agents
        "/tools",
        "/llm-configs/",  # Managing LLM configs on existing agents
        "/llm-configs",
        "/knowledge-bases/",  # Attaching knowledge bases to existing agents
        "/knowledge-bases",
        "/webhooks/",  # Managing webhooks on existing agents
        "/webhooks",
        "/domains/",  # Managing domains on existing agents
        "/domains",
        "/clone",  # Cloning agents (has its own endpoint logic)
    ],
}


# Mapping of endpoint paths to feature requirements (uses startswith matching)
FEATURE_ACCESS_ENDPOINTS = {
    # Advanced Analytics
    "/api/v1/analytics/advanced": "advanced_analytics",
    # SSO Configuration (actual route is /api/v1/sso/okta)
    "/api/v1/sso/okta": "sso",
    # API Access
    "/api/v1/agent-api-keys": "api_access",
    # Custom Tools (Free tier blocked, Hobby+ allowed)
    "/api/v1/custom-tools": "custom_tools",
    # MCP Servers (Free tier blocked)
    "/api/v1/mcp/servers": "mcp_servers",
    # Knowledge Bases feature flag (in addition to numeric limit)
    "/api/v1/knowledge-bases": "knowledge_bases",
    # Audit/Activity Logs
    "/api/v1/activity-logs": "audit_logs",
}

# Special pattern-based feature checks (for paths with dynamic segments)
# These are checked using 'in' operator instead of startswith
FEATURE_ACCESS_PATTERNS = {
    # Custom Domains - matches /api/v1/agents/{agent_name}/domains
    "/domains": "custom_domains",
    # Webhooks - matches /api/v1/agents/{agent_name}/webhooks
    "/webhooks": "webhooks",
}


async def _cache_plan_check(cache_key: str, value: list) -> None:
    """Store plan check result in Redis with 5-minute TTL."""
    try:
        from src.config.redis import get_redis_async

        redis = get_redis_async()
        if redis:
            await redis.setex(cache_key, 300, json.dumps(value))
    except Exception:
        pass


class PlanRestrictionMiddleware:
    """
    Pure ASGI middleware to enforce subscription plan restrictions.

    Uses pure ASGI pattern to avoid BaseHTTPMiddleware TaskGroup cancellation issues.

    - POST requests: Enforces both resource limits AND feature access
    - GET requests: Enforces feature access only (can view if feature is available)
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Create request object for header access
        request = StarletteRequest(scope, receive, send)
        path = scope.get("path", "")
        method = scope.get("method", "GET")

        # Check if this endpoint requires resource limit enforcement (POST only)
        resource_type = None
        if method == "POST":
            for endpoint_path, res_type in RESOURCE_LIMIT_ENDPOINTS.items():
                if path.startswith(endpoint_path):
                    # Check if this path is excluded from this resource type's limit check
                    # First check prefix-based exclusions (for fixed paths)
                    exclusions = RESOURCE_LIMIT_EXCLUSIONS.get(endpoint_path, [])
                    is_excluded = any(path.startswith(excl) for excl in exclusions)

                    # Then check pattern-based exclusions (for paths with dynamic segments like UUIDs)
                    if not is_excluded:
                        pattern_exclusions = RESOURCE_LIMIT_PATTERN_EXCLUSIONS.get(endpoint_path, [])
                        is_excluded = any(pattern in path for pattern in pattern_exclusions)

                    if not is_excluded:
                        resource_type = res_type
                    break

        # Check if this endpoint requires feature access (GET, POST, PUT, DELETE)
        required_feature = None
        for endpoint_path, feature in FEATURE_ACCESS_ENDPOINTS.items():
            if path.startswith(endpoint_path):
                required_feature = feature
                break

        # Check pattern-based feature access (for paths with dynamic segments)
        if not required_feature:
            for pattern, feature in FEATURE_ACCESS_PATTERNS.items():
                if pattern in path:
                    required_feature = feature
                    break

        # If no restrictions apply, continue
        if not resource_type and not required_feature:
            await self.app(scope, receive, send)
            return

        # Extract tenant_id directly from JWT token (middleware runs before dependencies)
        tenant_id = extract_tenant_id_from_request(request)

        if not tenant_id:
            # If no tenant_id (unauthenticated), let the auth middleware handle it
            await self.app(scope, receive, send)
            return

        # Get origin for CORS headers
        origin = request.headers.get("origin", "*")

        # Use async session directly instead of blocking thread pool
        async def _check_plan_restrictions() -> tuple[str | None, str | None, str | None]:
            """
            Check plan restrictions asynchronously.

            Returns:
                Tuple of (error_message, error_code, error_type) or (None, None, None) if all checks pass
            """
            # Try Redis cache for subscription validity + feature access checks
            # Resource limit checks (POST resource_type) always run fresh since counts change
            cache_key = f"plan_check:{tenant_id}:{required_feature or 'validity'}"
            if not resource_type:
                try:
                    from src.config.redis import get_redis_async

                    redis = get_redis_async()
                    if redis:
                        cached = await redis.get(cache_key)
                        if cached:
                            return tuple(json.loads(cached))  # type: ignore[return-value]
                except Exception:
                    pass

            async with get_async_session_factory()() as db:
                try:
                    # Platform tenants are exempt from all plan restrictions
                    tenant_result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
                    tenant = tenant_result.scalar_one_or_none()
                    if tenant and tenant.tenant_type == TenantType.PLATFORM:
                        if not resource_type:
                            await _cache_plan_check(cache_key, [None, None, None])
                        return None, None, None

                    restriction_service = PlanRestrictionService(db)

                    # First, check if subscription is valid (not expired, cancelled, or suspended)
                    try:
                        await restriction_service.check_subscription_validity(tenant_id)
                    except SubscriptionExpiredError as e:
                        result = (str(e), "SUBSCRIPTION_EXPIRED", "expired")
                        if not resource_type:
                            await _cache_plan_check(cache_key, list(result))
                        return result
                    except SubscriptionCancelledError as e:
                        result = (str(e), "SUBSCRIPTION_CANCELLED", "cancelled")
                        if not resource_type:
                            await _cache_plan_check(cache_key, list(result))
                        return result
                    except SubscriptionSuspendedError as e:
                        result = (str(e), "SUBSCRIPTION_SUSPENDED", "suspended")
                        if not resource_type:
                            await _cache_plan_check(cache_key, list(result))
                        return result

                    # Enforce resource limit if applicable (not cached — counts change)
                    if resource_type:
                        enforce_method = getattr(restriction_service, f"enforce_{resource_type}_limit", None)
                        if enforce_method:
                            try:
                                await enforce_method(tenant_id)
                            except PlanRestrictionError as e:
                                return str(e), "PLAN_LIMIT_REACHED", "resource_limit"

                    # Enforce feature access if applicable
                    if required_feature:
                        try:
                            await restriction_service.enforce_feature_access(tenant_id, required_feature)
                        except PlanRestrictionError as e:
                            result = (str(e), "FEATURE_NOT_AVAILABLE", "feature_access")
                            if not resource_type:
                                await _cache_plan_check(cache_key, list(result))
                            return result

                    if not resource_type:
                        await _cache_plan_check(cache_key, [None, None, None])
                    return None, None, None
                finally:
                    await db.close()

        try:
            error_message, error_code, error_type = await _check_plan_restrictions()

            if error_message:
                # Map error types to appropriate HTTP status codes and log messages
                if error_type in ("expired", "cancelled", "suspended"):
                    logger.warning(f"Subscription {error_type} for tenant {tenant_id}: {error_message}")
                    response = create_cors_json_response(
                        origin,
                        status_code=402,  # HTTP_402_PAYMENT_REQUIRED
                        content={"success": False, "message": error_message, "error_code": error_code},
                    )
                    await response(scope, receive, send)
                    return
                elif error_type == "resource_limit":
                    logger.warning(
                        f"Plan restriction blocked {resource_type} creation for tenant {tenant_id}: {error_message}"
                    )
                    response = create_cors_json_response(
                        origin,
                        status_code=403,  # HTTP_403_FORBIDDEN
                        content={"success": False, "message": error_message, "error_code": error_code},
                    )
                    await response(scope, receive, send)
                    return
                elif error_type == "feature_access":
                    logger.warning(
                        f"Plan restriction blocked {required_feature} access for tenant {tenant_id}: {error_message}"
                    )
                    response = create_cors_json_response(
                        origin,
                        status_code=403,  # HTTP_403_FORBIDDEN
                        content={"success": False, "message": error_message, "error_code": error_code},
                    )
                    await response(scope, receive, send)
                    return

            # If all checks pass, continue with the request
            await self.app(scope, receive, send)

        except Exception as e:
            logger.error(f"Error in plan restriction middleware: {e}", exc_info=True)
            # On error, block the request (fail closed for security)
            response = create_cors_json_response(
                origin,
                status_code=500,  # HTTP_500_INTERNAL_SERVER_ERROR
                content={
                    "success": False,
                    "message": "Unable to verify subscription. Please try again later.",
                    "error_code": "SUBSCRIPTION_CHECK_FAILED",
                },
            )
            await response(scope, receive, send)
