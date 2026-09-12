"""Load Test API endpoints."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import selectinload

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id
from src.models.load_test import LoadTest, LoadTestStatus, TargetType
from src.models.test_scenario import TestScenario
from src.schemas.load_testing import (
    CreateLoadTestRequest,
    CreateTestScenarioRequest,
    LoadTestListResponse,
    LoadTestResponse,
    TestScenarioResponse,
    UpdateLoadTestRequest,
    UpdateTestScenarioRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/load-tests", tags=["load-tests"])


# ============================================================================
# Load Test CRUD Endpoints
# ============================================================================


@router.post("", response_model=LoadTestResponse, status_code=201)
async def create_load_test(
    request: CreateLoadTestRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Create a new load test configuration."""
    try:
        # Validate target type
        try:
            target_type = TargetType(request.target_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid target type: {request.target_type}")

        # Create load test
        load_test = LoadTest(
            tenant_id=tenant_id,
            name=request.name,
            description=request.description,
            target_url=request.target_url,
            target_type=target_type,
            request_config=request.request_config,
            load_config=request.load_config.model_dump() if request.load_config else {},
            proxy_config_id=request.proxy_config_id,
            status=LoadTestStatus.DRAFT,
        )

        # Set encrypted auth config if provided
        if request.auth_config:
            load_test.set_auth_config(request.auth_config)

        db.add(load_test)
        await db.commit()
        await db.refresh(load_test)

        logger.info(f"Created load test: {load_test.name} (ID: {load_test.id})")

        return _load_test_to_response(load_test)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating load test: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("", response_model=LoadTestListResponse)
async def list_load_tests(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    search: str | None = Query(None),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """List all load tests for the tenant."""
    try:
        query = select(LoadTest).filter(LoadTest.tenant_id == tenant_id)

        # Apply filters
        if status:
            try:
                status_enum = LoadTestStatus(status)
                query = query.filter(LoadTest.status == status_enum)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

        if search:
            query = query.filter(LoadTest.name.ilike(f"%{search}%"))

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # Apply pagination, ordering, and eager loading
        query = (
            query.options(selectinload(LoadTest.test_runs))
            .order_by(LoadTest.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await db.execute(query)
        load_tests = result.scalars().all()

        return LoadTestListResponse(
            items=[_load_test_to_response(lt) for lt in load_tests],
            total=total,
            page=page,
            page_size=page_size,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing load tests: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{load_test_id}", response_model=LoadTestResponse)
async def get_load_test(
    load_test_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Get a specific load test."""
    try:
        load_test = await _get_load_test(db, load_test_id, tenant_id)
        return _load_test_to_response(load_test)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting load test: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{load_test_id}", response_model=LoadTestResponse)
async def update_load_test(
    load_test_id: UUID,
    request: UpdateLoadTestRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Update a load test configuration."""
    try:
        load_test = await _get_load_test(db, load_test_id, tenant_id)

        # Check if test is running
        if load_test.status == LoadTestStatus.RUNNING:
            raise HTTPException(status_code=400, detail="Cannot update a running load test")

        # Update fields
        if request.name is not None:
            load_test.name = request.name
        if request.description is not None:
            load_test.description = request.description
        if request.target_url is not None:
            load_test.target_url = request.target_url
        if request.target_type is not None:
            try:
                load_test.target_type = TargetType(request.target_type)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid target type: {request.target_type}")
        if request.auth_config is not None:
            load_test.set_auth_config(request.auth_config)
        if request.request_config is not None:
            load_test.request_config = request.request_config
        if request.load_config is not None:
            load_test.load_config = request.load_config
        if request.proxy_config_id is not None:
            load_test.proxy_config_id = request.proxy_config_id
        if request.status is not None:
            try:
                load_test.status = LoadTestStatus(request.status)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {request.status}")

        await db.commit()
        await db.refresh(load_test)

        logger.info(f"Updated load test: {load_test.name} (ID: {load_test.id})")

        return _load_test_to_response(load_test)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating load test: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{load_test_id}", status_code=204)
async def delete_load_test(
    load_test_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Delete a load test and all associated runs."""
    try:
        load_test = await _get_load_test(db, load_test_id, tenant_id)

        # Check if test is running
        if load_test.status == LoadTestStatus.RUNNING:
            raise HTTPException(status_code=400, detail="Cannot delete a running load test")

        await db.delete(load_test)
        await db.commit()

        logger.info(f"Deleted load test: {load_test.name} (ID: {load_test.id})")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting load test: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# Test Scenario Endpoints
# ============================================================================


@router.get("/{load_test_id}/scenarios", response_model=list[TestScenarioResponse])
async def list_scenarios(
    load_test_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """List all scenarios for a load test."""
    try:
        # Verify load test ownership
        await _get_load_test(db, load_test_id, tenant_id)

        result = await db.execute(
            select(TestScenario).filter(TestScenario.load_test_id == load_test_id).order_by(TestScenario.display_order)
        )
        scenarios = result.scalars().all()

        return [_scenario_to_response(s) for s in scenarios]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing scenarios: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{load_test_id}/scenarios", response_model=TestScenarioResponse, status_code=201)
async def create_scenario(
    load_test_id: UUID,
    request: CreateTestScenarioRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Create a new scenario for a load test."""
    try:
        # Verify load test ownership
        await _get_load_test(db, load_test_id, tenant_id)

        # Get max display order
        result = await db.execute(
            select(func.max(TestScenario.display_order)).filter(TestScenario.load_test_id == load_test_id)
        )
        max_order = result.scalar() or 0

        scenario = TestScenario(
            load_test_id=load_test_id,
            name=request.name,
            description=request.description,
            weight=request.weight,
            prompts=[p.model_dump() for p in request.prompts],
            think_time_config=(request.think_time_config.model_dump() if request.think_time_config else None),
            variables=({k: v.model_dump() for k, v in request.variables.items()} if request.variables else None),
            request_overrides=request.request_overrides,
            display_order=max_order + 1,
        )

        db.add(scenario)
        await db.commit()
        await db.refresh(scenario)

        logger.info(f"Created scenario: {scenario.name} (ID: {scenario.id})")

        return _scenario_to_response(scenario)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating scenario: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{load_test_id}/scenarios/{scenario_id}", response_model=TestScenarioResponse)
async def update_scenario(
    load_test_id: UUID,
    scenario_id: UUID,
    request: UpdateTestScenarioRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Update a scenario."""
    try:
        # Verify load test ownership
        await _get_load_test(db, load_test_id, tenant_id)

        result = await db.execute(
            select(TestScenario).filter(
                TestScenario.id == scenario_id,
                TestScenario.load_test_id == load_test_id,
            )
        )
        scenario = result.scalar_one_or_none()

        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")

        if request.name is not None:
            scenario.name = request.name
        if request.description is not None:
            scenario.description = request.description
        if request.weight is not None:
            scenario.weight = request.weight
        if request.prompts is not None:
            scenario.prompts = [p.model_dump() for p in request.prompts]
        if request.think_time_config is not None:
            scenario.think_time_config = request.think_time_config.model_dump()
        if request.variables is not None:
            scenario.variables = {k: v.model_dump() for k, v in request.variables.items()}
        if request.request_overrides is not None:
            scenario.request_overrides = request.request_overrides
        if request.display_order is not None:
            scenario.display_order = request.display_order

        await db.commit()
        await db.refresh(scenario)

        return _scenario_to_response(scenario)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating scenario: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{load_test_id}/scenarios/{scenario_id}", status_code=204)
async def delete_scenario(
    load_test_id: UUID,
    scenario_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Delete a scenario."""
    try:
        # Verify load test ownership
        await _get_load_test(db, load_test_id, tenant_id)

        result = await db.execute(
            select(TestScenario).filter(
                TestScenario.id == scenario_id,
                TestScenario.load_test_id == load_test_id,
            )
        )
        scenario = result.scalar_one_or_none()

        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")

        await db.delete(scenario)
        await db.commit()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting scenario: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# Helper Functions
# ============================================================================


async def _get_load_test(db: AsyncSession, load_test_id: UUID, tenant_id: UUID) -> LoadTest:
    """Get a load test by ID with tenant verification."""
    result = await db.execute(
        select(LoadTest)
        .options(selectinload(LoadTest.test_runs))
        .filter(LoadTest.id == load_test_id, LoadTest.tenant_id == tenant_id)
    )
    load_test = result.scalar_one_or_none()

    if not load_test:
        raise HTTPException(status_code=404, detail="Load test not found")

    return load_test


def _load_test_to_response(load_test: LoadTest) -> LoadTestResponse:
    """Convert LoadTest model to response schema."""
    last_run_data = None
    # Only access test_runs if it's already loaded to avoid lazy loading issues
    state = inspect(load_test)
    if "test_runs" in state.dict and state.dict["test_runs"]:
        last_run = state.dict["test_runs"][0]
        if last_run:
            last_run_data = {
                "id": str(last_run.id),
                "status": last_run.status.value,
                "started_at": last_run.started_at.isoformat() if last_run.started_at else None,
                "completed_at": (last_run.completed_at.isoformat() if last_run.completed_at else None),
            }

    return LoadTestResponse(
        id=load_test.id,
        tenant_id=load_test.tenant_id,
        name=load_test.name,
        description=load_test.description,
        target_url=load_test.target_url,
        target_type=load_test.target_type.value,
        request_config=load_test.request_config or {},
        load_config=load_test.load_config or {},
        proxy_config_id=load_test.proxy_config_id,
        status=load_test.status.value,
        schedule_config=load_test.schedule_config,
        created_at=load_test.created_at,
        updated_at=load_test.updated_at,
        last_run=last_run_data,
    )


def _scenario_to_response(scenario: TestScenario) -> TestScenarioResponse:
    """Convert TestScenario model to response schema."""
    return TestScenarioResponse(
        id=scenario.id,
        load_test_id=scenario.load_test_id,
        name=scenario.name,
        description=scenario.description,
        weight=scenario.weight,
        prompts=scenario.prompts or [],
        think_time_config=scenario.think_time_config,
        variables=scenario.variables,
        request_overrides=scenario.request_overrides,
        display_order=scenario.display_order,
        created_at=scenario.created_at,
        updated_at=scenario.updated_at,
    )
