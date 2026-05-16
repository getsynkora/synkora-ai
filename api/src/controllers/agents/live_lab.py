"""
Live Lab Controller — Agent execution observation endpoints.

Provides real-time and historical views of agent executions across all trigger sources.
"""

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.models.tenant import Account
from src.services.agents.execution_registry import execution_registry

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/live-lab/executions")
async def list_executions(
    status: str = Query("all", pattern="^(all|active|recent)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_account: Account = Depends(get_current_account),
):
    """List active and/or recent executions for the tenant."""
    result = {}

    if status in ("all", "active"):
        result["active"] = await execution_registry.list_active(tenant_id)

    if status in ("all", "recent"):
        result["recent"] = await execution_registry.list_recent(tenant_id, limit=limit, offset=offset)

    return result


@router.get("/live-lab/executions/{execution_id}")
async def get_execution(
    execution_id: str,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_account: Account = Depends(get_current_account),
):
    """Get execution details including full event history."""
    data = await execution_registry.get_execution(tenant_id, execution_id)
    if not data:
        raise HTTPException(status_code=404, detail="Execution not found")

    events = await execution_registry.get_events(execution_id)
    data["events"] = events
    return data


@router.get("/live-lab/executions/{execution_id}/stream")
async def stream_execution(
    execution_id: str,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_account: Account = Depends(get_current_account),
):
    """
    SSE stream for observing a specific execution in real-time.

    For running executions: polls Redis events and streams them as they arrive.
    For completed executions: replays all stored events then closes.
    """
    data = await execution_registry.get_execution(tenant_id, execution_id)
    if not data:
        raise HTTPException(status_code=404, detail="Execution not found")

    async def event_stream():
        last_index = 0
        is_running = data.get("status") == "running"

        while True:
            events = await execution_registry.get_events(execution_id)
            new_events = events[last_index:]
            last_index = len(events)

            for event in new_events:
                yield f"data: {json.dumps(event)}\n\n"

            if not is_running:
                # Completed execution: replay all events and close
                yield f"data: {json.dumps({'type': 'stream_end'})}\n\n"
                return

            # Check if execution completed since we started
            current = await execution_registry.get_execution(tenant_id, execution_id)
            if not current or current.get("status") != "running":
                # Flush remaining events
                final_events = await execution_registry.get_events(execution_id)
                for event in final_events[last_index:]:
                    yield f"data: {json.dumps(event)}\n\n"
                yield f"data: {json.dumps({'type': 'stream_end'})}\n\n"
                return

            await asyncio.sleep(0.3)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
