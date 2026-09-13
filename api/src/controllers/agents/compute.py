"""
Agent Compute Controller.

Provides CRUD endpoints for assigning and managing compute targets
(isolated platform workspace or remote SSH server) for agents.

Routes are prefixed with /api/v1/agents/{agent_id}/compute.
"""

import logging
import time
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel as PydanticModel
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id
from src.models.agent import Agent
from src.models.agent_compute import AgentCompute, ComputeStatus, ComputeType

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class ComputeAssignRequest(PydanticModel):
    """Body for POST /agents/{id}/compute."""

    compute_type: str = Field(
        default="platform_managed",
        description="Compute type: 'platform_managed' (default) or 'remote_server'; legacy 'local' uses isolation",
    )
    remote_host: str | None = Field(
        default=None,
        description="Hostname or IP of the remote server",
    )
    remote_port: int | None = Field(
        default=22,
        description="SSH port (default 22)",
    )
    remote_user: str | None = Field(
        default="root",
        description="SSH username",
    )
    remote_auth_type: str | None = Field(
        default="key",
        description="SSH auth method: 'key' (private key) or 'password'",
    )
    remote_credentials: str | None = Field(
        default=None,
        description=("SSH private key (PEM format) or password. Stored encrypted at rest. Send only on create/update."),
    )
    remote_base_path: str | None = Field(
        default="/tmp/agent_workspace",
        description="Working directory on the remote host",
    )
    timeout_seconds: int = Field(
        default=300,
        ge=10,
        le=3600,
        description="Per-command timeout in seconds",
    )
    max_output_chars: int = Field(
        default=8000,
        ge=1000,
        le=100000,
        description="Max stdout characters returned per command",
    )
    allowed_commands_override: list[str] | None = Field(
        default=None,
        description=(
            "Restrict to these command names only (e.g. ['git', 'ls', 'cat']). "
            "Null = use the global SAFE_COMMANDS default."
        ),
    )


class ComputeUpdateRequest(PydanticModel):
    """Body for PUT /agents/{id}/compute — all fields optional."""

    remote_host: str | None = None
    remote_port: int | None = None
    remote_user: str | None = None
    remote_auth_type: str | None = None
    remote_credentials: str | None = Field(
        default=None,
        description="Provide only when updating credentials",
    )
    remote_base_path: str | None = None
    timeout_seconds: int | None = Field(default=None, ge=10, le=3600)
    max_output_chars: int | None = Field(default=None, ge=1000, le=100000)
    allowed_commands_override: list[str] | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/{agent_id}/compute")
async def get_compute(
    agent_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Get the compute configuration for an agent."""
    await _get_agent_or_404(agent_id, tenant_id, db)

    result = await db.execute(select(AgentCompute).where(AgentCompute.agent_id == agent_id))
    compute = result.scalar_one_or_none()

    if compute is None:
        return {
            "configured": False,
            "compute_type": "platform_managed",
            "message": "Agent uses an isolated platform workspace",
        }

    return {**compute.to_dict(), "configured": True}


@router.post("/{agent_id}/compute", status_code=status.HTTP_201_CREATED)
async def assign_compute(
    agent_id: uuid.UUID,
    body: ComputeAssignRequest,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Assign or replace the compute target for an agent.

    - Use compute_type='platform_managed' for an isolated platform workspace.
      Legacy 'local' configurations use the same isolated backend.
    - Use compute_type='remote_server' and provide SSH credentials to route
      command and file-system tools to a remote host.
    """
    await _get_agent_or_404(agent_id, tenant_id, db)

    # Validate compute_type
    try:
        ComputeType(body.compute_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid compute_type '{body.compute_type}'. Use 'platform_managed', 'remote_server', or 'local'.",
        )

    # Validate remote fields when type is remote_server
    if body.compute_type == ComputeType.REMOTE_SERVER.value and not body.remote_host:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="remote_host is required when compute_type is 'remote_server'",
        )

    # platform_managed requires no extra fields — the platform handles everything
    # based on the tenant's TenantComputeConfig (see /api/v1/tenant/compute-config)

    # Remove existing compute record if any
    existing_result = await db.execute(select(AgentCompute).where(AgentCompute.agent_id == agent_id))
    existing = existing_result.scalar_one_or_none()
    if existing:
        await db.delete(existing)
        await db.flush()

    compute = AgentCompute(
        agent_id=agent_id,
        tenant_id=tenant_id,
        compute_type=body.compute_type,
        status=ComputeStatus.ACTIVE,
        remote_host=body.remote_host,
        remote_port=body.remote_port,
        remote_user=body.remote_user,
        remote_auth_type=body.remote_auth_type,
        remote_base_path=body.remote_base_path,
        timeout_seconds=body.timeout_seconds,
        max_output_chars=body.max_output_chars,
        allowed_commands_override=body.allowed_commands_override,
    )

    if body.remote_credentials:
        compute.set_credentials(body.remote_credentials)

    db.add(compute)
    await db.commit()
    await db.refresh(compute)

    logger.info(f"Compute assigned to agent {agent_id}: type={body.compute_type}")
    return {**compute.to_dict(), "configured": True}


@router.put("/{agent_id}/compute")
async def update_compute(
    agent_id: uuid.UUID,
    body: ComputeUpdateRequest,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Update compute configuration fields for an agent."""
    await _get_agent_or_404(agent_id, tenant_id, db)

    result = await db.execute(select(AgentCompute).where(AgentCompute.agent_id == agent_id))
    compute = result.scalar_one_or_none()
    if compute is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No compute assigned to this agent. Use POST to assign one first.",
        )

    update_data = body.model_dump(exclude_none=True)
    credentials = update_data.pop("remote_credentials", None)

    for field, value in update_data.items():
        setattr(compute, field, value)

    if credentials:
        compute.set_credentials(credentials)

    compute.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(compute)

    return {**compute.to_dict(), "configured": True}


@router.delete("/{agent_id}/compute", status_code=status.HTTP_204_NO_CONTENT)
async def remove_compute(
    agent_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Remove the compute assignment for an agent.

    The agent will revert to the default isolated platform workspace.
    """
    await _get_agent_or_404(agent_id, tenant_id, db)

    result = await db.execute(select(AgentCompute).where(AgentCompute.agent_id == agent_id))
    compute = result.scalar_one_or_none()
    if compute:
        await db.delete(compute)
        await db.commit()
        logger.info(f"Compute removed from agent {agent_id}")


@router.post("/{agent_id}/compute/test")
async def test_compute(
    agent_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Test connectivity to the assigned compute target.

    Runs `echo hello` in the configured isolated platform or remote SSH backend.
    Updates `last_connected_at` and `status` in the DB based on the result.
    """
    await _get_agent_or_404(agent_id, tenant_id, db)

    from src.services.compute.resolver import build_compute_session_for_agent

    session = await build_compute_session_for_agent(str(agent_id), db, tenant_id=tenant_id)

    if session is None:
        return {
            "success": False,
            "message": "Isolated compute is unavailable",
            "output": "",
            "error": "",
            "latency_ms": 0,
        }

    t0 = time.monotonic()
    result = await session.exec_command(["echo", "hello"])
    latency_ms = round((time.monotonic() - t0) * 1000)
    await session.close()

    # Persist connection status
    r = await db.execute(select(AgentCompute).where(AgentCompute.agent_id == agent_id))
    compute = r.scalar_one_or_none()
    if compute:
        if result["success"]:
            compute.last_connected_at = datetime.now(UTC)
            compute.status = ComputeStatus.ACTIVE
            compute.error_message = None
        else:
            compute.status = ComputeStatus.ERROR
            compute.error_message = result.get("error", "")[:500]
        await db.commit()

    return {
        "success": result["success"],
        "message": "Connection successful" if result["success"] else "Connection failed",
        "output": result.get("output", ""),
        "error": result.get("error", ""),
        "latency_ms": latency_ms,
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


async def _get_agent_or_404(
    agent_id: uuid.UUID,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> Agent:
    result = await db.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.tenant_id == tenant_id,
        )
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return agent
