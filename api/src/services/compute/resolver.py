"""
ComputeSessionResolver — resolves the correct ComputeSession for a tool call.

Resolution order (first non-None wins):
  1. config["_compute_session"] — explicit injection (tests / per-call override).
  2. RuntimeContext.compute_session  — resolved once per conversation.
  3. None — command tools refuse execution without an isolated session.

``build_compute_session_for_agent()`` is called at RuntimeContext creation time
(chat service, autonomous agent executor, etc.) to load the AgentCompute record
and build the correct backend session.  The result is stored on the RuntimeContext
so tool calls within the same conversation reuse it without further DB round-trips.
"""

import logging
import uuid
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from src.services.compute.session import ComputeSession


async def get_compute_session_from_config(
    config: dict[str, Any] | None,
) -> "ComputeSession | None":
    """
    Return the active ComputeSession for a tool call, or None.

    None means command execution is unavailable; file tools retain scoped local access.
    """
    # 1. Explicit per-call injection (useful for tests)
    if config and "_compute_session" in config:
        return config["_compute_session"]

    # 2. RuntimeContext (set once per conversation by build_compute_session_for_agent)
    try:
        from src.services.agents.runtime_context import get_runtime_context

        ctx = get_runtime_context()
        if ctx is not None and getattr(ctx, "compute_session", None) is not None:
            return ctx.compute_session  # type: ignore[return-value]
    except Exception as e:
        logger.debug(f"Could not read compute_session from RuntimeContext: {e}")

    return None


async def build_compute_session_for_agent(
    agent_id: str | uuid.UUID,
    db_session: Any,
    tenant_id: Any = None,
    conversation_id: Any = None,
) -> "ComputeSession | None":
    """
    Build and return a ComputeSession from an agent's AgentCompute DB record.

    Unconfigured and legacy LOCAL agents use the isolated platform backend.
    Provisioning failures propagate; commands never fall back to the API process.

    Called once at RuntimeContext creation time, never per tool call.

    Args:
        agent_id:        Agent UUID.
        db_session:      Async SQLAlchemy session.
        tenant_id:       Tenant UUID — required for PLATFORM_MANAGED backend lookup.
        conversation_id: Conversation UUID — used to name the ephemeral container.
    """
    from sqlalchemy import select

    from src.models.agent_compute import AgentCompute, ComputeStatus, ComputeType

    try:
        agent_uuid = uuid.UUID(str(agent_id)) if not isinstance(agent_id, uuid.UUID) else agent_id
        stmt = select(AgentCompute).where(
            AgentCompute.agent_id == agent_uuid,
            AgentCompute.status == ComputeStatus.ACTIVE,
        )
        result = await db_session.execute(stmt)
        compute = result.scalar_one_or_none()

        # Legacy "local" and unconfigured agents also use the isolated service.
        if compute is None or compute.compute_type in (ComputeType.LOCAL, ComputeType.PLATFORM_MANAGED):
            if tenant_id is None:
                raise RuntimeError(
                    f"Agent {agent_id} uses PLATFORM_MANAGED compute but tenant_id was not "
                    "provided to build_compute_session_for_agent"
                )

            conv_id = str(conversation_id) if conversation_id else str(uuid.uuid4())

            from src.services.compute.backends.factory import get_backend_for_tenant

            backend = await get_backend_for_tenant(tenant_id, db_session)
            session = await backend.checkout_session(
                agent_id=str(agent_uuid),
                tenant_id=str(tenant_id),
                conversation_id=conv_id,
            )
            logger.info(
                f"Built {backend.backend_type} session for agent {agent_id} (tenant={tenant_id}, conv={conv_id[:8]})"
            )
            return session

        # ── REMOTE_SERVER ───────────────────────────────────────────────────────
        if compute.compute_type == ComputeType.REMOTE_SERVER:
            if not compute.remote_host:
                logger.warning(f"Agent {agent_id} has REMOTE_SERVER compute but remote_host is not set")
                return None

            credentials = compute.get_credentials()

            # Read platform-level SSH defaults from DB
            known_hosts_content: str | None = None
            platform_base_path = "/tmp/agent_workspace"
            try:
                from src.services.billing.platform_settings_service import PlatformSettingsService

                ps = PlatformSettingsService(db_session)
                platform_cfg = await ps.get_settings()
                known_hosts_content = platform_cfg.compute_ssh_known_hosts or None
                platform_base_path = platform_cfg.compute_default_base_path or "/tmp/agent_workspace"
            except Exception:
                pass

            from src.services.compute.remote_backend import RemoteSSHComputeSession

            session = RemoteSSHComputeSession(
                host=compute.remote_host,
                port=compute.remote_port or 22,
                username=compute.remote_user or "root",
                auth_type=compute.remote_auth_type or "key",
                credentials=credentials,
                base_path=compute.remote_base_path or platform_base_path,
                timeout=compute.timeout_seconds,
                max_output_chars=compute.max_output_chars,
                known_hosts_content=known_hosts_content,
            )
            logger.info(
                f"Built RemoteSSHComputeSession for agent {agent_id} "
                f"-> {compute.remote_user}@{compute.remote_host}:{compute.remote_port}"
            )
            return session

    except Exception:
        raise
