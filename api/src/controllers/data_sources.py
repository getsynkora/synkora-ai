"""Data Source API endpoints."""

import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.models.data_source import DataSource, DataSourceStatus, DataSourceType, SyncStatus
from src.models.knowledge_base import KnowledgeBase
from src.models.tenant import Account, Tenant, TenantPlan, TenantStatus
from src.services.data_sources.clickup_connector import ClickUpConnector
from src.services.data_sources.confluence_connector import ConfluenceConnector
from src.services.data_sources.databricks_connector import DatabricksConnector
from src.services.data_sources.datadog_connector import DatadogConnector
from src.services.data_sources.docker_logs_connector import DockerLogsConnector
from src.services.data_sources.github_connector import GitHubConnector
from src.services.data_sources.gitlab_connector import GitLabConnector
from src.services.data_sources.gmail_connector import GmailConnector
from src.services.data_sources.jira_connector import JiraConnector
from src.services.data_sources.linear_connector import LinearConnector
from src.services.data_sources.notion_connector import NotionConnector
from src.services.data_sources.slack_connector import SlackConnector
from src.services.data_sources.telegram_connector import TelegramConnector

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data-sources", tags=["data-sources"])


# Request/Response Models
class CreateDataSourceRequest(BaseModel):
    """Request model for creating a data source."""

    name: str = Field(..., min_length=1, max_length=255)
    type: DataSourceType
    knowledge_base_id: int
    config: dict = Field(default_factory=dict)
    oauth_app_id: int | None = None
    slack_bot_id: str | None = None


class UpdateDataSourceRequest(BaseModel):
    """Request model for updating a data source."""

    name: str | None = Field(None, min_length=1, max_length=255)
    config: dict | None = None
    sync_enabled: bool | None = None


class OAuthAppInfo(BaseModel):
    """OAuth app information for data source response."""

    id: int
    app_name: str
    provider: str


class DataSourceResponse(BaseModel):
    """Response model for data source."""

    id: int
    name: str
    type: str
    knowledge_base_id: int | None
    tenant_id: str
    config: dict
    status: str
    sync_enabled: bool
    last_sync_at: str | None
    last_error: str | None
    total_documents: int
    created_at: str
    updated_at: str
    oauth_app: OAuthAppInfo | None = None  # OAuth app if linked

    model_config = ConfigDict(from_attributes=True)


class ConnectionTestResponse(BaseModel):
    """Response model for connection test."""

    success: bool
    message: str
    details: dict


class SyncJobResponse(BaseModel):
    """Response model for sync job."""

    job_id: str
    status: str
    message: str


class SyncStatusResponse(BaseModel):
    """Response model for sync status."""

    status: str
    total_documents: int
    last_sync_at: str | None
    last_error: str | None
    sync_enabled: bool


# Helper functions
def build_data_source_response(ds: DataSource) -> DataSourceResponse:
    """Build DataSourceResponse from DataSource model."""
    oauth_app_info = None
    if ds.oauth_app:
        oauth_app_info = OAuthAppInfo(
            id=ds.oauth_app.id,
            app_name=ds.oauth_app.app_name,
            provider=ds.oauth_app.provider,
        )

    return DataSourceResponse(
        id=ds.id,
        name=ds.name,
        type=ds.type.value,
        knowledge_base_id=ds.knowledge_base_id,
        tenant_id=str(ds.tenant_id),
        config=ds.config,
        status=ds.status.value,
        sync_enabled=ds.sync_enabled,
        last_sync_at=ds.last_sync_at.isoformat() if ds.last_sync_at else None,
        last_error=ds.last_error,
        total_documents=ds.total_documents,
        created_at=ds.created_at.isoformat(),
        updated_at=ds.updated_at.isoformat(),
        oauth_app=oauth_app_info,
    )


async def get_default_tenant(db: AsyncSession) -> UUID:
    """Get or create default tenant."""
    result = await db.execute(select(Tenant))
    tenant = result.scalar_one_or_none()
    if not tenant:
        # Create default tenant
        tenant = Tenant(name="Default Tenant", plan=TenantPlan.FREE, status=TenantStatus.ACTIVE)
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)
    return tenant.id


# Types with a real connector implementation, i.e. an external system that can
# actually be polled/synced. Everything else in DataSourceType (MANUAL, WEB,
# CUSTOM, ASANA, GOOGLE_DRIVE, CSV_FILE, ZIP_FILE, ...) is either upload-only
# (no external source to sync from) or not yet implemented. Used both to build
# connectors below and to keep the periodic auto-sync dispatcher (see
# src/tasks/data_source_tasks.py) from ever queuing a sync for a type that has
# nowhere to sync from.
SYNCABLE_DATA_SOURCE_TYPES = frozenset(
    {
        DataSourceType.SLACK,
        DataSourceType.GMAIL,
        DataSourceType.GITHUB,
        DataSourceType.GITLAB,
        DataSourceType.TELEGRAM,
        DataSourceType.DATADOG,
        DataSourceType.DATABRICKS,
        DataSourceType.DOCKER_LOGS,
        DataSourceType.NOTION,
        DataSourceType.CONFLUENCE,
        DataSourceType.JIRA,
        DataSourceType.CLICKUP,
        DataSourceType.LINEAR,
    }
)


def get_connector(data_source: DataSource, db: AsyncSession):
    """Get the appropriate connector for a data source."""
    if data_source.type == DataSourceType.SLACK:
        return SlackConnector(data_source, db)
    elif data_source.type == DataSourceType.GMAIL:
        return GmailConnector(data_source, db)
    elif data_source.type == DataSourceType.GITHUB:
        return GitHubConnector(data_source, db)
    elif data_source.type == DataSourceType.GITLAB:
        return GitLabConnector(data_source, db)
    elif data_source.type == DataSourceType.TELEGRAM:
        return TelegramConnector(data_source, db)
    elif data_source.type == DataSourceType.DATADOG:
        return DatadogConnector(data_source, db)
    elif data_source.type == DataSourceType.DATABRICKS:
        return DatabricksConnector(data_source, db)
    elif data_source.type == DataSourceType.DOCKER_LOGS:
        return DockerLogsConnector(data_source, db)
    elif data_source.type == DataSourceType.NOTION:
        return NotionConnector(data_source, db)
    elif data_source.type == DataSourceType.CONFLUENCE:
        return ConfluenceConnector(data_source, db)
    elif data_source.type == DataSourceType.JIRA:
        return JiraConnector(data_source, db)
    elif data_source.type == DataSourceType.CLICKUP:
        return ClickUpConnector(data_source, db)
    elif data_source.type == DataSourceType.LINEAR:
        return LinearConnector(data_source, db)
    else:
        raise ValueError(f"Unsupported data source type: {data_source.type}")


# Endpoints
@router.post("", response_model=DataSourceResponse, status_code=201)
async def create_data_source(
    request: CreateDataSourceRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    current_account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
):
    """Create a new data source."""
    try:
        # Verify knowledge base exists
        result = await db.execute(select(KnowledgeBase).filter(KnowledgeBase.id == request.knowledge_base_id))
        kb = result.scalar_one_or_none()

        if not kb:
            raise HTTPException(status_code=404, detail="Knowledge base not found")

        # Start with provided config
        config = dict(request.config) if request.config else {}

        # Verify OAuth app if provided
        if request.oauth_app_id:
            from src.models.oauth_app import OAuthApp
            from src.models.user_oauth_token import UserOAuthToken

            result = await db.execute(
                select(OAuthApp).filter(OAuthApp.id == request.oauth_app_id, OAuthApp.tenant_id == tenant_id)
            )
            oauth_app = result.scalar_one_or_none()

            if not oauth_app:
                raise HTTPException(status_code=404, detail="OAuth app not found")

            # Verify OAuth app provider matches data source type
            if oauth_app.provider.upper() != request.type.value:
                raise HTTPException(
                    status_code=400,
                    detail=f"OAuth app provider ({oauth_app.provider}) does not match data source type ({request.type.value})",
                )

            # Verify connection: personal token OR company-wide token on the OAuth app
            result = await db.execute(
                select(UserOAuthToken).filter(
                    UserOAuthToken.account_id == current_account.id,
                    UserOAuthToken.oauth_app_id == request.oauth_app_id,
                )
            )
            user_token = result.scalar_one_or_none()

            company_connected = bool(oauth_app.access_token or oauth_app.api_token)

            if not user_token and not company_connected:
                raise HTTPException(
                    status_code=400,
                    detail="You haven't connected your account to this OAuth app. Please connect first.",
                )

            # Store the account ID in config for token resolution
            config["connected_by_account_id"] = str(current_account.id)

        # Verify Slack bot if provided (reuse an existing agent's Slack connection)
        slack_bot_uuid = None
        if request.slack_bot_id:
            from uuid import UUID as UUIDType

            from src.models.slack_bot import SlackBot

            try:
                slack_bot_uuid = UUIDType(request.slack_bot_id)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid slack_bot_id")

            result = await db.execute(
                select(SlackBot).filter(SlackBot.id == slack_bot_uuid, SlackBot.tenant_id == tenant_id)
            )
            slack_bot = result.scalar_one_or_none()

            if not slack_bot:
                raise HTTPException(status_code=404, detail="Slack bot not found")

            if request.type != DataSourceType.SLACK:
                raise HTTPException(status_code=400, detail="slack_bot_id can only be used with type=SLACK")

        # Reject connecting the same underlying account/workspace/token to a KB it's
        # already linked to. Without this, real-time webhooks (keyed by kb_id+type,
        # not data_source_id) silently pick one of the duplicates at random, and
        # pull-based syncs double-fetch and double-embed the exact same content.
        existing_result = await db.execute(
            select(DataSource).filter(
                DataSource.tenant_id == tenant_id,
                DataSource.knowledge_base_id == request.knowledge_base_id,
                DataSource.type == request.type,
            )
        )
        duplicate: DataSource | None = None
        for existing in existing_result.scalars().all():
            if request.oauth_app_id and existing.oauth_app_id == request.oauth_app_id:
                duplicate = existing
                break
            if slack_bot_uuid and existing.slack_bot_id == slack_bot_uuid:
                duplicate = existing
                break
            if request.type in (DataSourceType.NOTION, DataSourceType.CONFLUENCE, DataSourceType.LINEAR):
                from src.services.agents.security import decrypt_value

                existing_config = existing.config or {}
                if request.type == DataSourceType.NOTION:
                    raw_token = config.get("internal_token")
                    existing_token_enc = existing_config.get("internal_token_encrypted")
                elif request.type == DataSourceType.CONFLUENCE:
                    raw_token = config.get("pat") or config.get("api_token")
                    existing_token_enc = existing_config.get("pat_encrypted") or existing_config.get(
                        "api_token_encrypted"
                    )
                else:
                    raw_token = config.get("api_key")
                    existing_token_enc = existing_config.get("api_key_encrypted")

                if raw_token and existing_token_enc:
                    try:
                        if decrypt_value(existing_token_enc) == raw_token:
                            duplicate = existing
                            break
                    except Exception:
                        pass

        if duplicate:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"This {request.type.value} account is already connected to this knowledge base "
                    f"as '{duplicate.name}'."
                ),
            )

        # Direct API-token / PAT auth for providers with no OAuth app flow yet
        # (Notion, Confluence, Linear). Plaintext token fields are encrypted at rest
        # and the plaintext copy is dropped from config before it's ever persisted.
        direct_auth_configured = False
        if not request.oauth_app_id and not slack_bot_uuid:
            from src.services.agents.security import encrypt_value

            if request.type == DataSourceType.NOTION:
                token = config.pop("internal_token", None)
                if token:
                    config["internal_token_encrypted"] = encrypt_value(token)
                    direct_auth_configured = True
            elif request.type == DataSourceType.CONFLUENCE:
                pat = config.pop("pat", None)
                api_token = config.pop("api_token", None)
                if pat:
                    config["pat_encrypted"] = encrypt_value(pat)
                    direct_auth_configured = True
                elif api_token and config.get("email"):
                    config["api_token_encrypted"] = encrypt_value(api_token)
                    direct_auth_configured = True
            elif request.type == DataSourceType.LINEAR:
                api_key = config.pop("api_key", None)
                if api_key:
                    config["api_key_encrypted"] = encrypt_value(api_key)
                    direct_auth_configured = True

        # Determine initial status
        initial_status = (
            DataSourceStatus.ACTIVE
            if (request.oauth_app_id or slack_bot_uuid or direct_auth_configured)
            else DataSourceStatus.INACTIVE
        )

        data_source = DataSource(
            name=request.name,
            type=request.type,
            knowledge_base_id=request.knowledge_base_id,
            tenant_id=tenant_id,
            config=config,
            oauth_app_id=request.oauth_app_id,
            slack_bot_id=slack_bot_uuid,
            status=initial_status,
            # sync_enabled defaults to True at the model level for every type —
            # force it off for types with no connector (nothing to poll), so the
            # periodic auto-sync dispatcher never has a reason to pick these up.
            sync_enabled=request.type in SYNCABLE_DATA_SOURCE_TYPES,
        )

        db.add(data_source)
        await db.commit()

        # Re-fetch with oauth_app eagerly loaded
        result = await db.execute(
            select(DataSource).options(selectinload(DataSource.oauth_app)).filter(DataSource.id == data_source.id)
        )
        data_source = result.scalar_one()

        logger.info(
            f"Created data source: {data_source.name} (ID: {data_source.id}) with status {initial_status.value}"
        )

        return build_data_source_response(data_source)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating data source: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=list[DataSourceResponse])
async def list_data_sources(
    knowledge_base_id: int | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """List all data sources."""
    try:
        query = select(DataSource).options(selectinload(DataSource.oauth_app)).filter(DataSource.tenant_id == tenant_id)

        if knowledge_base_id:
            query = query.filter(DataSource.knowledge_base_id == knowledge_base_id)

        result = await db.execute(query.offset(skip).limit(limit))
        data_sources = result.scalars().all()

        return [build_data_source_response(ds) for ds in data_sources]

    except Exception as e:
        logger.error(f"Error listing data sources: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ds_id}", response_model=DataSourceResponse)
async def get_data_source(
    ds_id: int,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Get a specific data source.

    SECURITY: Requires authentication and verifies data source belongs to tenant.
    """
    try:
        # SECURITY: Filter by tenant_id to prevent IDOR attacks
        result = await db.execute(
            select(DataSource)
            .options(selectinload(DataSource.oauth_app))
            .filter(DataSource.id == ds_id, DataSource.tenant_id == tenant_id)
        )
        ds = result.scalar_one_or_none()

        if not ds:
            raise HTTPException(status_code=404, detail="Data source not found")

        return build_data_source_response(ds)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting data source: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{ds_id}", response_model=DataSourceResponse)
async def update_data_source(
    ds_id: int,
    request: UpdateDataSourceRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Update a data source.

    SECURITY: Requires authentication and verifies data source belongs to tenant.
    """
    try:
        # SECURITY: Filter by tenant_id to prevent IDOR attacks
        result = await db.execute(select(DataSource).filter(DataSource.id == ds_id, DataSource.tenant_id == tenant_id))
        ds = result.scalar_one_or_none()

        if not ds:
            raise HTTPException(status_code=404, detail="Data source not found")

        # Update fields
        if request.name is not None:
            ds.name = request.name
        if request.config is not None:
            ds.config = request.config
        if request.sync_enabled is not None:
            ds.sync_enabled = request.sync_enabled

        await db.commit()

        # Re-fetch with oauth_app eagerly loaded
        result = await db.execute(
            select(DataSource).options(selectinload(DataSource.oauth_app)).filter(DataSource.id == ds_id)
        )
        ds = result.scalar_one()

        logger.info(f"Updated data source: {ds.name} (ID: {ds.id})")

        return build_data_source_response(ds)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating data source: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{ds_id}", status_code=204)
async def delete_data_source(
    ds_id: int,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Delete a data source.

    SECURITY: Requires authentication and verifies data source belongs to tenant.
    """
    try:
        # SECURITY: Filter by tenant_id to prevent IDOR attacks
        result = await db.execute(select(DataSource).filter(DataSource.id == ds_id, DataSource.tenant_id == tenant_id))
        ds = result.scalar_one_or_none()

        if not ds:
            raise HTTPException(status_code=404, detail="Data source not found")

        await db.delete(ds)
        await db.commit()

        logger.info(f"Deleted data source: {ds.name} (ID: {ds.id})")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting data source: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


class LinkOAuthAppRequest(BaseModel):
    """Request to link an OAuth app to a data source."""

    oauth_app_id: int


@router.post("/{ds_id}/link-oauth-app", response_model=DataSourceResponse)
async def link_oauth_app_to_data_source(
    ds_id: int,
    request: LinkOAuthAppRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    current_account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Link an OAuth app to an existing data source.

    This allows users to connect their account to a data source that was
    created without an OAuth app, or to change the OAuth connection.
    """
    try:
        from src.models.oauth_app import OAuthApp
        from src.models.user_oauth_token import UserOAuthToken

        # SECURITY: Filter by tenant_id to prevent IDOR attacks
        result = await db.execute(select(DataSource).filter(DataSource.id == ds_id, DataSource.tenant_id == tenant_id))
        ds = result.scalar_one_or_none()

        if not ds:
            raise HTTPException(status_code=404, detail="Data source not found")

        # Verify OAuth app exists and belongs to tenant
        result = await db.execute(
            select(OAuthApp).filter(OAuthApp.id == request.oauth_app_id, OAuthApp.tenant_id == tenant_id)
        )
        oauth_app = result.scalar_one_or_none()

        if not oauth_app:
            raise HTTPException(status_code=404, detail="OAuth app not found")

        # Verify OAuth app provider matches data source type
        if oauth_app.provider.upper() != ds.type.value:
            raise HTTPException(
                status_code=400,
                detail=f"OAuth app provider ({oauth_app.provider}) does not match data source type ({ds.type.value})",
            )

        # Verify connection: personal token OR company-wide token on the OAuth app
        result = await db.execute(
            select(UserOAuthToken).filter(
                UserOAuthToken.account_id == current_account.id,
                UserOAuthToken.oauth_app_id == request.oauth_app_id,
            )
        )
        user_token = result.scalar_one_or_none()

        company_connected = bool(oauth_app.access_token or oauth_app.api_token)

        if not user_token and not company_connected:
            raise HTTPException(
                status_code=400,
                detail="You haven't connected your account to this OAuth app. Please connect first.",
            )

        # Update data source
        ds.oauth_app_id = request.oauth_app_id
        ds.config = {
            **(ds.config or {}),
            "connected_by_account_id": str(current_account.id),
        }
        ds.status = DataSourceStatus.ACTIVE

        await db.commit()

        # Re-fetch with oauth_app eagerly loaded
        result = await db.execute(
            select(DataSource).options(selectinload(DataSource.oauth_app)).filter(DataSource.id == ds_id)
        )
        ds = result.scalar_one()

        logger.info(f"Linked OAuth app {oauth_app.app_name} to data source {ds.name} (ID: {ds.id})")

        return build_data_source_response(ds)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error linking OAuth app: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ds_id}/oauth-url")
async def get_oauth_url(
    ds_id: int,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Get OAuth authorization URL for a data source.

    SECURITY: Requires authentication and verifies data source belongs to tenant.
    """
    try:
        # SECURITY: Filter by tenant_id to prevent IDOR attacks
        result = await db.execute(select(DataSource).filter(DataSource.id == ds_id, DataSource.tenant_id == tenant_id))
        ds = result.scalar_one_or_none()

        if not ds:
            raise HTTPException(status_code=404, detail="Data source not found")

        connector = get_connector(ds, db)
        oauth_url = connector.get_oauth_url()

        if not oauth_url:
            raise HTTPException(status_code=400, detail="OAuth not supported for this data source type")

        return {"oauth_url": oauth_url}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting OAuth URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{ds_id}/oauth-callback")
async def handle_oauth_callback(
    ds_id: int,
    code: str = Query(...),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Handle OAuth callback for a data source.

    SECURITY: Requires authentication and verifies data source belongs to tenant.
    """
    try:
        # SECURITY: Filter by tenant_id to prevent IDOR attacks
        result = await db.execute(select(DataSource).filter(DataSource.id == ds_id, DataSource.tenant_id == tenant_id))
        ds = result.scalar_one_or_none()

        if not ds:
            raise HTTPException(status_code=404, detail="Data source not found")

        connector = get_connector(ds, db)
        callback_result = await connector.handle_oauth_callback(code)

        if not callback_result.get("success"):
            raise HTTPException(status_code=400, detail=callback_result.get("message"))

        return callback_result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling OAuth callback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{ds_id}/test-connection", response_model=ConnectionTestResponse)
async def test_connection(
    ds_id: int,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Test connection to a data source.

    SECURITY: Requires authentication and verifies data source belongs to tenant.
    """
    try:
        # SECURITY: Filter by tenant_id to prevent IDOR attacks
        result = await db.execute(select(DataSource).filter(DataSource.id == ds_id, DataSource.tenant_id == tenant_id))
        ds = result.scalar_one_or_none()

        if not ds:
            raise HTTPException(status_code=404, detail="Data source not found")

        connector = get_connector(ds, db)
        test_result = await connector.test_connection()

        return ConnectionTestResponse(
            success=test_result["success"], message=test_result["message"], details=test_result.get("details", {})
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing connection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{ds_id}/sync", response_model=SyncJobResponse, status_code=202)
async def trigger_sync(
    ds_id: int,
    incremental: bool = Query(True),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Trigger a sync job for a data source.

    SECURITY: Requires authentication and verifies data source belongs to tenant.
    """
    try:
        from src.models.data_source import DataSourceSyncJob, SyncStatus
        from src.tasks.data_source_tasks import sync_data_source_task

        result = await db.execute(select(DataSource).filter(DataSource.id == ds_id, DataSource.tenant_id == tenant_id))
        ds = result.scalar_one_or_none()

        if not ds:
            raise HTTPException(status_code=404, detail="Data source not found")

        if ds.status not in (DataSourceStatus.ACTIVE, DataSourceStatus.ERROR):
            raise HTTPException(status_code=400, detail="Data source is not active. Please complete OAuth first.")

        if ds.type not in SYNCABLE_DATA_SOURCE_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"{ds.type.value} data sources have no external system to sync from — nothing to trigger.",
            )

        # Prevent duplicate concurrent syncs
        result = await db.execute(
            select(DataSourceSyncJob).filter(
                DataSourceSyncJob.data_source_id == ds_id, DataSourceSyncJob.status == SyncStatus.IN_PROGRESS
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Sync already in progress")

        # Create sync job row so frontend can poll status immediately
        sync_job = DataSourceSyncJob(
            data_source_id=ds_id, tenant_id=ds.tenant_id, status=SyncStatus.IN_PROGRESS, started_at=datetime.now(UTC)
        )
        db.add(sync_job)
        await db.commit()
        await db.refresh(sync_job)

        # Dispatch to Celery — API returns immediately, worker does the heavy lifting
        sync_data_source_task.delay(data_source_id=ds_id, sync_job_id=sync_job.id, full_sync=not incremental)

        return SyncJobResponse(job_id=str(sync_job.id), status="started", message=f"Sync job started for {ds.name}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ds_id}/sync-status", response_model=SyncStatusResponse)
async def get_sync_status(
    ds_id: int,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Get sync status for a data source.

    SECURITY: Requires authentication and verifies data source belongs to tenant.
    """
    try:
        # SECURITY: Filter by tenant_id to prevent IDOR attacks
        result = await db.execute(select(DataSource).filter(DataSource.id == ds_id, DataSource.tenant_id == tenant_id))
        ds = result.scalar_one_or_none()

        if not ds:
            raise HTTPException(status_code=404, detail="Data source not found")

        return SyncStatusResponse(
            status=ds.status.value,
            total_documents=ds.total_documents,
            last_sync_at=ds.last_sync_at.isoformat() if ds.last_sync_at else None,
            last_error=ds.last_error,
            sync_enabled=ds.sync_enabled,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting sync status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class SyncHistoryItem(BaseModel):
    """Response model for sync history item."""

    id: int
    started_at: str
    completed_at: str | None
    status: str
    documents_processed: int
    documents_added: int
    documents_updated: int
    documents_deleted: int
    documents_failed: int
    error_message: str | None

    model_config = ConfigDict(from_attributes=True)


@router.get("/{ds_id}/sync-history", response_model=list[SyncHistoryItem])
async def get_sync_history(
    ds_id: int,
    limit: int = Query(20, ge=1, le=100),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Get sync history for a data source.

    SECURITY: Requires authentication and verifies data source belongs to tenant.
    """
    try:
        # SECURITY: Filter by tenant_id to prevent IDOR attacks
        result = await db.execute(select(DataSource).filter(DataSource.id == ds_id, DataSource.tenant_id == tenant_id))
        ds = result.scalar_one_or_none()

        if not ds:
            raise HTTPException(status_code=404, detail="Data source not found")

        from src.models.data_source import DataSourceSyncJob

        result = await db.execute(
            select(DataSourceSyncJob)
            .filter(DataSourceSyncJob.data_source_id == ds_id)
            .order_by(DataSourceSyncJob.started_at.desc())
            .limit(limit)
        )
        sync_jobs = result.scalars().all()

        return [
            SyncHistoryItem(
                id=job.id,
                started_at=job.started_at.isoformat() if job.started_at else datetime.now(UTC).isoformat(),
                completed_at=job.completed_at.isoformat() if job.completed_at else None,
                status=job.status.value,
                documents_processed=job.documents_processed,
                documents_added=job.documents_added,
                documents_updated=job.documents_updated,
                documents_deleted=job.documents_deleted,
                documents_failed=job.documents_failed,
                error_message=job.error_message,
            )
            for job in sync_jobs
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting sync history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Stream health — Redis Streams visibility for webhook-based sources
# ---------------------------------------------------------------------------


class StreamHealthResponse(BaseModel):
    """Real-time Redis Stream stats for a data source."""

    stream_key: str
    stream_length: int
    pending_count: int
    consumer_group: str
    consumers: int
    webhook_url: str
    is_stream_active: bool


@router.get("/{ds_id}/stream-health", response_model=StreamHealthResponse)
async def get_stream_health(
    ds_id: int,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Return real-time Redis Stream stats for a webhook-based data source."""
    result = await db.execute(select(DataSource).filter(DataSource.id == ds_id, DataSource.tenant_id == tenant_id))
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Data source not found")
    if not ds.knowledge_base_id:
        raise HTTPException(status_code=400, detail="Data source is not linked to a knowledge base")

    kb_id = ds.knowledge_base_id
    source_type = ds.type.value.lower()
    stream_key = f"kb_ingest:{kb_id}:{source_type}"
    group = "kb_embedder"

    from src.config.redis import get_redis_async

    r = get_redis_async()
    try:
        stream_length = await r.xlen(stream_key)
    except Exception:
        stream_length = 0

    pending_count = 0
    consumers = 0
    try:
        groups = await r.xinfo_groups(stream_key)
        for g in groups:
            name = g.get("name", b"")
            if isinstance(name, bytes):
                name = name.decode()
            if name == group:
                pending_count = int(g.get("pending", 0))
                consumers = int(g.get("consumers", 0))
                break
    except Exception:
        pass

    from src.config.settings import get_settings

    base_url = get_settings().api_base_url.rstrip("/")
    webhook_url = f"{base_url}/api/webhooks/kb/{kb_id}/{source_type}"

    return StreamHealthResponse(
        stream_key=stream_key,
        stream_length=stream_length,
        pending_count=pending_count,
        consumer_group=group,
        consumers=consumers,
        webhook_url=webhook_url,
        is_stream_active=stream_length > 0 or pending_count > 0,
    )


# ---------------------------------------------------------------------------
# Activate / deactivate webhook-based data sources
# ---------------------------------------------------------------------------


@router.post("/{ds_id}/activate", response_model=DataSourceResponse)
async def activate_data_source(
    ds_id: int,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Activate a webhook-based data source (set status = ACTIVE)."""
    result = await db.execute(
        select(DataSource)
        .options(selectinload(DataSource.oauth_app))
        .filter(DataSource.id == ds_id, DataSource.tenant_id == tenant_id)
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Data source not found")

    cfg = ds.config or {}
    if not cfg.get("signing_secret"):
        raise HTTPException(
            status_code=400,
            detail="signing_secret must be configured before activating",
        )

    ds.status = DataSourceStatus.ACTIVE
    await db.commit()
    await db.refresh(ds)
    return build_data_source_response(ds)


@router.post("/{ds_id}/deactivate", response_model=DataSourceResponse)
async def deactivate_data_source(
    ds_id: int,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Deactivate a data source (set status = INACTIVE)."""
    result = await db.execute(
        select(DataSource)
        .options(selectinload(DataSource.oauth_app))
        .filter(DataSource.id == ds_id, DataSource.tenant_id == tenant_id)
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Data source not found")

    ds.status = DataSourceStatus.INACTIVE
    await db.commit()
    await db.refresh(ds)
    return build_data_source_response(ds)
