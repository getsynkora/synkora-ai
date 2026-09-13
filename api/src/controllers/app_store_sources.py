"""
App Store Sources Controller.

Handles API endpoints for managing app store sources and review analysis.
"""

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id
from src.models.app_review import AppReview
from src.models.app_store_source import AppStoreSource, StoreType
from src.services.agents.config import ModelConfig
from src.services.app_store import (
    ReviewAnalysisService,
    ReviewSyncService,
    get_connector,
)
from src.tasks.kb_tasks import analyze_app_store_reviews

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/app-store-sources", tags=["App Store Sources"])


# Request/Response Models
class CreateAppStoreSourceRequest(BaseModel):
    """Request model for creating an app store source."""

    knowledge_base_id: int | None = None
    store_type: StoreType
    app_id: str = Field(..., description="Package name (Google Play) or App ID (Apple)")
    app_name: str
    sync_frequency: str = Field(default="daily", pattern="^(daily|weekly|monthly)$")
    min_rating: int = Field(default=1, ge=1, le=5)
    languages: list[str] = Field(default_factory=lambda: ["en"])
    countries: list[str] = Field(default_factory=lambda: ["us"])


class UpdateAppStoreSourceRequest(BaseModel):
    """Request model for updating an app store source."""

    app_name: str | None = None
    sync_frequency: str | None = Field(None, pattern="^(daily|weekly|monthly)$")
    min_rating: int | None = Field(None, ge=1, le=5)
    languages: list[str] | None = None
    countries: list[str] | None = None
    status: str | None = Field(None, pattern="^(active|paused|error)$")


class AppStoreSourceResponse(BaseModel):
    """Response model for app store source."""

    id: UUID
    tenant_id: UUID
    knowledge_base_id: int | None
    store_type: str
    app_id: str
    app_name: str
    sync_frequency: str
    last_sync_at: datetime | None
    next_sync_at: datetime | None
    min_rating: int
    languages: list[str]
    countries: list[str]
    status: str
    total_reviews_collected: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AnalyzeReviewsRequest(BaseModel):
    """Request model for analyzing reviews."""

    limit: int = Field(default=100, ge=1, le=1000)
    only_unanalyzed: bool = Field(default=True)
    llm_provider: str = Field(default="openai")
    llm_model: str = Field(default="gpt-4")
    llm_api_key: str


class ReviewResponse(BaseModel):
    """Response model for a review."""

    id: UUID
    review_id: str
    author_name: str
    rating: int
    title: str | None
    content: str
    language: str | None
    country: str | None
    app_version: str | None
    review_date: datetime
    sentiment: str | None
    sentiment_score: float | None
    topics: list[str] | None
    issues: list[dict] | None
    features_mentioned: list[str] | None

    model_config = ConfigDict(from_attributes=True)


# Endpoints
@router.post("", response_model=AppStoreSourceResponse, status_code=status.HTTP_201_CREATED)
async def create_app_store_source(
    request: CreateAppStoreSourceRequest,
    db: AsyncSession = Depends(get_async_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Create a new app store source."""
    try:
        # Create app store source
        source = AppStoreSource(
            tenant_id=tenant_id,
            knowledge_base_id=request.knowledge_base_id,
            store_type=request.store_type,
            app_id=request.app_id,
            app_name=request.app_name,
            sync_frequency=request.sync_frequency,
            min_rating=request.min_rating,
            languages=request.languages,
            countries=request.countries,
            status="active",
            total_reviews_collected=0,
        )

        db.add(source)
        await db.commit()
        await db.refresh(source)

        logger.info(f"Created app store source {source.id} for {source.app_name} ({source.store_type})")

        return source

    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create app store source: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create app store source",
        )


@router.get("", response_model=list[AppStoreSourceResponse])
async def list_app_store_sources(
    db: AsyncSession = Depends(get_async_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """List all app store sources for the current tenant."""
    stmt = select(AppStoreSource).where(AppStoreSource.tenant_id == tenant_id)
    result = await db.execute(stmt)
    sources = result.scalars().all()

    return sources


@router.get("/{source_id}", response_model=AppStoreSourceResponse)
async def get_app_store_source(
    source_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Get a specific app store source."""
    stmt = select(AppStoreSource).where(AppStoreSource.id == source_id, AppStoreSource.tenant_id == tenant_id)
    result = await db.execute(stmt)
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="App store source not found")

    return source


@router.patch("/{source_id}", response_model=AppStoreSourceResponse)
async def update_app_store_source(
    source_id: UUID,
    request: UpdateAppStoreSourceRequest,
    db: AsyncSession = Depends(get_async_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Update an app store source."""
    stmt = select(AppStoreSource).where(AppStoreSource.id == source_id, AppStoreSource.tenant_id == tenant_id)
    result = await db.execute(stmt)
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="App store source not found")

    # Update fields
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(source, field, value)

    await db.commit()
    await db.refresh(source)

    logger.info(f"Updated app store source {source_id}")

    return source


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_app_store_source(
    source_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Delete an app store source."""
    stmt = select(AppStoreSource).where(AppStoreSource.id == source_id, AppStoreSource.tenant_id == tenant_id)
    result = await db.execute(stmt)
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="App store source not found")

    await db.delete(source)
    await db.commit()

    logger.info(f"Deleted app store source {source_id}")


@router.post("/{source_id}/sync")
async def sync_reviews(
    source_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Manually trigger review sync for an app store source."""
    stmt = select(AppStoreSource).where(AppStoreSource.id == source_id, AppStoreSource.tenant_id == tenant_id)
    result = await db.execute(stmt)
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="App store source not found")

    try:
        # Get connector and sync reviews
        get_connector(source, db)
        sync_service = ReviewSyncService(db)

        result = await sync_service.sync_source(source.id)

        logger.info(f"Synced reviews for source {source_id}: {result}")

        return result

    except Exception as e:
        logger.error(f"Failed to sync reviews for source {source_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync reviews",
        )


@router.post("/{source_id}/analyze")
async def analyze_reviews(
    source_id: UUID,
    request: AnalyzeReviewsRequest,
    db: AsyncSession = Depends(get_async_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Analyze reviews for an app store source."""
    stmt = select(AppStoreSource).where(AppStoreSource.id == source_id, AppStoreSource.tenant_id == tenant_id)
    result = await db.execute(stmt)
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="App store source not found")

    try:
        # Dispatch LLM analysis to Celery — returns immediately
        analyze_app_store_reviews.delay(
            source_id=str(source_id),
            tenant_id=str(tenant_id),
            llm_provider=request.llm_provider,
            llm_model=request.llm_model,
            llm_api_key=request.llm_api_key,
            limit=request.limit,
            only_unanalyzed=request.only_unanalyzed,
        )

        logger.info(f"Queued review analysis for source {source_id}")
        return {"status": "queued", "message": "Review analysis started in the background"}

    except Exception as e:
        logger.error(f"Failed to queue review analysis for source {source_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to queue review analysis",
        )


@router.get("/{source_id}/insights")
async def get_insights(
    source_id: UUID,
    limit: int = 500,
    db: AsyncSession = Depends(get_async_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Get AI-generated insights for an app store source."""
    from src.models.knowledge_base import KnowledgeBase
    from src.services.agents.security import decrypt_value

    stmt = select(AppStoreSource).where(AppStoreSource.id == source_id, AppStoreSource.tenant_id == tenant_id)
    result = await db.execute(stmt)
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="App store source not found")

    try:
        # Initialize analysis service
        analysis_service = ReviewAnalysisService(db)

        # Get LLM config from knowledge base if available
        if source.knowledge_base_id:
            kb_stmt = select(KnowledgeBase).where(KnowledgeBase.id == source.knowledge_base_id)
            kb_result = await db.execute(kb_stmt)
            knowledge_base = kb_result.scalar_one_or_none()

            if knowledge_base and knowledge_base.llm_provider and knowledge_base.llm_model:
                # Decrypt API key if available
                api_key = None
                if knowledge_base.llm_api_key:
                    api_key = decrypt_value(knowledge_base.llm_api_key)

                if api_key:
                    llm_config = ModelConfig(
                        provider=knowledge_base.llm_provider,
                        model_name=knowledge_base.llm_model,
                        api_key=api_key,
                    )
                    analysis_service.initialize_llm_client(llm_config)
                    logger.info(
                        f"Using LLM config from knowledge base: {knowledge_base.llm_provider}/{knowledge_base.llm_model}"
                    )

        # Generate insights
        insights = await analysis_service.generate_insights(app_store_source_id=source_id, limit=limit)

        return insights

    except Exception as e:
        logger.error(f"Failed to generate insights for source {source_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate insights",
        )


@router.get("/{source_id}/reviews", response_model=list[ReviewResponse])
async def list_reviews(
    source_id: UUID,
    limit: int = 100,
    offset: int = 0,
    min_rating: int | None = None,
    max_rating: int | None = None,
    sentiment: str | None = None,
    db: AsyncSession = Depends(get_async_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """List reviews for an app store source with optional filters."""
    # Verify source exists and belongs to user
    stmt = select(AppStoreSource).where(AppStoreSource.id == source_id, AppStoreSource.tenant_id == tenant_id)
    result = await db.execute(stmt)
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="App store source not found")

    # Build query
    stmt = select(AppReview).where(AppReview.app_store_source_id == source_id)

    if min_rating is not None:
        stmt = stmt.where(AppReview.rating >= min_rating)
    if max_rating is not None:
        stmt = stmt.where(AppReview.rating <= max_rating)
    if sentiment:
        stmt = stmt.where(AppReview.sentiment == sentiment)

    stmt = stmt.order_by(AppReview.review_date.desc()).limit(limit).offset(offset)

    result = await db.execute(stmt)
    reviews = result.scalars().all()

    return reviews
