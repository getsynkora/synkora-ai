"""Monitoring Integration API endpoints."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id
from src.models.monitoring_integration import MonitoringIntegration, MonitoringProvider
from src.schemas.load_testing import (
    CreateMonitoringIntegrationRequest,
    MonitoringIntegrationListResponse,
    MonitoringIntegrationResponse,
    TestConnectionResponse,
    UpdateMonitoringIntegrationRequest,
)
from src.services.security.monitoring_http import monitoring_request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.post("", response_model=MonitoringIntegrationResponse, status_code=201)
async def create_monitoring_integration(
    request: CreateMonitoringIntegrationRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Create a new monitoring integration."""
    try:
        # Validate provider
        try:
            provider = MonitoringProvider(request.provider)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid provider: {request.provider}")

        # Validate config against schema
        config_schema = MonitoringIntegration.get_config_schema(provider)
        for required_field in config_schema.get("required", []):
            if required_field not in request.config:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing required field: {required_field}",
                )

        # Create integration
        integration = MonitoringIntegration(
            tenant_id=tenant_id,
            name=request.name,
            provider=provider,
            export_settings=request.export_settings,
            is_active=True,
        )

        # Encrypt and store config
        integration.set_config(request.config)

        db.add(integration)
        await db.commit()
        await db.refresh(integration)

        logger.info(f"Created monitoring integration: {integration.name} (ID: {integration.id})")

        return _integration_to_response(integration)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating monitoring integration: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("", response_model=MonitoringIntegrationListResponse)
async def list_monitoring_integrations(
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List monitoring integrations (paginated)."""
    try:
        # Get total count
        count_result = await db.execute(
            select(func.count(MonitoringIntegration.id)).filter(
                MonitoringIntegration.tenant_id == tenant_id
            )
        )
        total = count_result.scalar() or 0

        result = await db.execute(
            select(MonitoringIntegration)
            .filter(MonitoringIntegration.tenant_id == tenant_id)
            .order_by(MonitoringIntegration.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        integrations = result.scalars().all()

        return MonitoringIntegrationListResponse(
            items=[_integration_to_response(i) for i in integrations],
            total=total,
        )

    except Exception as e:
        logger.error(f"Error listing monitoring integrations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{integration_id}", response_model=MonitoringIntegrationResponse)
async def get_monitoring_integration(
    integration_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Get a specific monitoring integration."""
    try:
        integration = await _get_integration(db, integration_id, tenant_id)
        return _integration_to_response(integration)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting monitoring integration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{integration_id}", response_model=MonitoringIntegrationResponse)
async def update_monitoring_integration(
    integration_id: UUID,
    request: UpdateMonitoringIntegrationRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Update a monitoring integration."""
    try:
        integration = await _get_integration(db, integration_id, tenant_id)

        if request.name is not None:
            integration.name = request.name
        if request.config is not None:
            integration.set_config(request.config)
        if request.export_settings is not None:
            integration.export_settings = request.export_settings
        if request.is_active is not None:
            integration.is_active = request.is_active

        await db.commit()
        await db.refresh(integration)

        logger.info(f"Updated monitoring integration: {integration.name} (ID: {integration.id})")

        return _integration_to_response(integration)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating monitoring integration: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{integration_id}", status_code=204)
async def delete_monitoring_integration(
    integration_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Delete a monitoring integration."""
    try:
        integration = await _get_integration(db, integration_id, tenant_id)

        await db.delete(integration)
        await db.commit()

        logger.info(f"Deleted monitoring integration: {integration.name} (ID: {integration.id})")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting monitoring integration: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{integration_id}/test", response_model=TestConnectionResponse)
async def test_monitoring_connection(
    integration_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Test connection to a monitoring platform."""
    try:
        integration = await _get_integration(db, integration_id, tenant_id)
        config = integration.get_config()

        # Test connection based on provider
        provider = integration.provider
        success = False
        message = ""
        details = {}

        if provider == MonitoringProvider.DATADOG:
            success, message, details = await _test_datadog(config, tenant_id=tenant_id)
        elif provider == MonitoringProvider.OPENTELEMETRY:
            success, message, details = await _test_otlp(config, tenant_id=tenant_id)
        elif provider == MonitoringProvider.GRAFANA_CLOUD:
            success, message, details = await _test_grafana_cloud(config, tenant_id=tenant_id)
        elif provider == MonitoringProvider.PROMETHEUS:
            success, message, details = await _test_prometheus(config, tenant_id=tenant_id)
        elif provider == MonitoringProvider.WEBHOOK:
            success, message, details = await _test_webhook(config, tenant_id=tenant_id)
        elif provider == MonitoringProvider.SLACK:
            success, message, details = await _test_slack(config, tenant_id=tenant_id)
        elif provider == MonitoringProvider.PAGERDUTY:
            success, message, details = await _test_pagerduty(config, tenant_id=tenant_id)
        else:
            message = f"Testing not supported for provider: {provider.value}"

        # Update sync status
        integration.sync_status = "success" if success else "failed"
        integration.sync_error = None if success else message
        await db.commit()

        return TestConnectionResponse(
            success=success,
            message=message,
            details=details if details else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing monitoring connection: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/providers/schema")
async def get_provider_schemas():
    """Get configuration schemas for all providers."""
    schemas = {}
    for provider in MonitoringProvider:
        schemas[provider.value] = MonitoringIntegration.get_config_schema(provider)
    return schemas


# ============================================================================
# Connection Test Functions
# ============================================================================


async def _test_request(method: str, url: str, *, tenant_id: UUID | None = None, **kwargs) -> tuple[bool, str, dict]:
    try:
        response = await monitoring_request(method, url, tenant_id=tenant_id, **kwargs)
        if 200 <= response.status_code < 300:
            return True, "Connection successful", {"status_code": response.status_code}
        return False, f"Connection failed: HTTP {response.status_code}", {}
    except Exception:
        # Never return destination bodies, credentials, or internal addresses.
        return False, "Connection failed or destination is not permitted", {}


async def _test_datadog(config: dict, *, tenant_id: UUID | None = None) -> tuple[bool, str, dict]:
    return await _test_request(
        "GET",
        f"https://api.{config.get('site', 'datadoghq.com')}/api/v1/validate",
        tenant_id=tenant_id,
        headers={"DD-API-KEY": config.get("api_key"), "DD-APPLICATION-KEY": config.get("app_key")},
    )


async def _test_otlp(config: dict, *, tenant_id: UUID | None = None) -> tuple[bool, str, dict]:
    return await _test_request(
        "OPTIONS", config.get("endpoint"), tenant_id=tenant_id, headers=config.get("headers", {})
    )


async def _test_grafana_cloud(config: dict, *, tenant_id: UUID | None = None) -> tuple[bool, str, dict]:
    return await _test_request(
        "GET",
        f"{config.get('prometheus_url', '').rstrip('/')}/api/v1/query?query=up",
        tenant_id=tenant_id,
        auth=(config.get("username"), config.get("api_key")),
    )


async def _test_prometheus(config: dict, *, tenant_id: UUID | None = None) -> tuple[bool, str, dict]:
    credentials = config.get("basic_auth")
    auth = (credentials.get("username"), credentials.get("password")) if credentials else None
    return await _test_request(
        "GET",
        f"{config.get('pushgateway_url', '').rstrip('/')}/metrics",
        tenant_id=tenant_id,
        auth=auth,
    )


async def _test_webhook(config: dict, *, tenant_id: UUID | None = None) -> tuple[bool, str, dict]:
    method = str(config.get("method", "POST")).upper()
    if method not in {"POST", "PUT", "PATCH"}:
        return False, "Webhook tests support POST, PUT and PATCH only", {}
    return await _test_request(
        method,
        config.get("url"),
        tenant_id=tenant_id,
        headers=config.get("headers", {}),
        json={"test": True, "source": "synkora"},
    )


async def _test_slack(config: dict, *, tenant_id: UUID | None = None) -> tuple[bool, str, dict]:
    return await _test_request(
        "POST",
        config.get("webhook_url"),
        tenant_id=tenant_id,
        json={"text": "Synkora monitoring test - connection verified"},
    )


async def _test_pagerduty(config: dict, *, tenant_id: UUID | None = None) -> tuple[bool, str, dict]:
    return await _test_request(
        "POST",
        "https://events.pagerduty.com/v2/enqueue",
        tenant_id=tenant_id,
        json={
            "routing_key": config.get("routing_key"),
            "event_action": "trigger",
            "payload": {"summary": "Synkora monitoring test", "severity": "info", "source": "synkora-test"},
        },
    )


# ============================================================================
# Helper Functions
# ============================================================================


async def _get_integration(db: AsyncSession, integration_id: UUID, tenant_id: UUID) -> MonitoringIntegration:
    """Get a monitoring integration by ID with tenant verification."""
    result = await db.execute(
        select(MonitoringIntegration).filter(
            MonitoringIntegration.id == integration_id,
            MonitoringIntegration.tenant_id == tenant_id,
        )
    )
    integration = result.scalar_one_or_none()

    if not integration:
        raise HTTPException(status_code=404, detail="Monitoring integration not found")

    return integration


def _integration_to_response(
    integration: MonitoringIntegration,
) -> MonitoringIntegrationResponse:
    """Convert MonitoringIntegration model to response schema."""
    return MonitoringIntegrationResponse(
        id=integration.id,
        tenant_id=integration.tenant_id,
        name=integration.name,
        provider=integration.provider.value,
        is_active=integration.is_active,
        export_settings=integration.export_settings,
        last_sync_at=integration.last_sync_at,
        sync_status=integration.sync_status,
        sync_error=integration.sync_error,
        created_at=integration.created_at,
        updated_at=integration.updated_at,
    )
