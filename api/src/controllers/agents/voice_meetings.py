"""
Voice & Meetings Hub controller.

Unified settings for phone (Vapi), web call, and meeting bot (Recall.ai),
plus meeting dispatch and transcript history endpoints.
"""

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.models.agent import Agent

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class PhoneSettings(BaseModel):
    enabled: bool = False
    vapi_phone_number_id: str | None = None
    stt_provider: str = "deepgram"
    tts_provider: str = "elevenlabs"
    tts_voice_id: str | None = None


class WebCallSettings(BaseModel):
    enabled: bool = False
    show_on_agent_card: bool = True
    vapi_public_key: str | None = None


class MeetingBotSettings(BaseModel):
    enabled: bool = False
    bot_name: str = "AI Assistant"
    bot_avatar_url: str | None = None
    platforms: list[str] = Field(default_factory=lambda: ["zoom", "google_meet", "teams", "slack_huddle"])
    auto_record: bool = True


class VoiceMeetingsConfig(BaseModel):
    phone: PhoneSettings = Field(default_factory=PhoneSettings)
    web_call: WebCallSettings = Field(default_factory=WebCallSettings)
    meeting_bot: MeetingBotSettings = Field(default_factory=MeetingBotSettings)


class DispatchRequest(BaseModel):
    url: str = Field(..., description="Meeting URL (Zoom, Google Meet, Teams, Slack Huddle)")
    scheduled_at: str | None = Field(None, description="ISO datetime to join. Null = join immediately.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_agent(agent_id: str, tenant_id: int, db):
    """Look up agent by UUID or slug, scoped to tenant."""
    try:
        agent_uuid = UUID(agent_id)
        result = await db.execute(select(Agent).filter(Agent.id == agent_uuid, Agent.tenant_id == tenant_id))
    except ValueError:
        result = await db.execute(select(Agent).filter(Agent.slug == agent_id, Agent.tenant_id == tenant_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return agent


def _get_voice_meetings_config(agent: Agent) -> dict:
    return (agent.agent_metadata or {}).get("voice_meetings_config", {})


# ---------------------------------------------------------------------------
# Settings endpoints
# ---------------------------------------------------------------------------


@router.get("/{agent_id}/voice-meetings")
async def get_voice_meetings_config(
    agent_id: str,
    db=Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """Return voice_meetings_config for an agent."""
    agent = await _get_agent(agent_id, tenant_id, db)
    cfg = _get_voice_meetings_config(agent)
    return VoiceMeetingsConfig(**cfg).model_dump()


@router.put("/{agent_id}/voice-meetings")
async def update_voice_meetings_config(
    agent_id: str,
    body: VoiceMeetingsConfig,
    db=Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """Save voice_meetings_config for an agent."""
    agent = await _get_agent(agent_id, tenant_id, db)
    metadata = dict(agent.agent_metadata or {})
    metadata["voice_meetings_config"] = body.model_dump()
    agent.agent_metadata = metadata
    flag_modified(agent, "agent_metadata")
    await db.commit()
    return body.model_dump()


# ---------------------------------------------------------------------------
# Vapi web call token
# ---------------------------------------------------------------------------


@router.post("/{agent_id}/voice-meetings/web-call-token")
async def get_web_call_token(
    agent_id: str,
    db=Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """
    Return the Vapi public key for initialising the Web SDK in the browser.
    The public key is safe to expose client-side (it is not the API secret).
    """
    agent = await _get_agent(agent_id, tenant_id, db)
    cfg = _get_voice_meetings_config(agent)
    web_call = cfg.get("web_call", {})

    if not web_call.get("enabled"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Web call is not enabled for this agent.")

    public_key = web_call.get("vapi_public_key")
    if not public_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vapi public key is not configured. Add it in Voice & Meetings settings.",
        )

    # The vapi_assistant_id is registered when phone settings are saved.
    # Web calls use the same Vapi assistant (backed by the existing webhook).
    vapi_assistant_id = (agent.phone_config or {}).get("vapi_assistant_id")

    return {
        "public_key": public_key,
        "agent_id": str(agent.id),
        "agent_name": agent.agent_name,
        "vapi_assistant_id": vapi_assistant_id,
    }


# ---------------------------------------------------------------------------
# Meeting dispatch & history
# ---------------------------------------------------------------------------


@router.post("/{agent_id}/meetings/dispatch")
async def dispatch_meeting_bot(
    agent_id: str,
    body: DispatchRequest,
    db=Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """Dispatch a Recall.ai bot to a meeting URL."""
    agent = await _get_agent(agent_id, tenant_id, db)
    cfg = _get_voice_meetings_config(agent)
    meeting_bot = cfg.get("meeting_bot", {})

    if not meeting_bot.get("enabled"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Meeting bot is not enabled for this agent. Enable it in Voice & Meetings settings.",
        )

    from src.services.agents.credential_resolver import CredentialResolver
    from src.services.recall.recall_service import RecallService
    from src.utils.config_helper import get_app_base_url

    class _FakeContext:
        def __init__(self, agent_id, tenant_id, db_session):
            self.agent_id = agent_id
            self.tenant_id = tenant_id
            self.db_session = db_session

    ctx = _FakeContext(agent.id, tenant_id, db)
    resolver = CredentialResolver(ctx)
    api_key, region, _ = await resolver.get_recall_credentials("internal_recall_send_bot")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Recall.ai is not configured. Add a Recall.ai integration in OAuth Apps.",
        )

    service = RecallService(api_key=api_key, region=region, webhook_base_url=get_app_base_url())
    bot_name = meeting_bot.get("bot_name", "AI Assistant")

    join_at: datetime | None = None
    if body.scheduled_at:
        try:
            join_at = datetime.fromisoformat(body.scheduled_at.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid scheduled_at format. Use ISO 8601.")

    result = await service.send_bot_to_meeting(
        meeting_url=body.url,
        bot_name=bot_name,
        join_at=join_at,
        agent_id=str(agent.id),
    )

    if not result.get("success"):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=result.get("error", "Recall.ai error"))

    return result["data"]


@router.get("/{agent_id}/meetings")
async def list_meetings(
    agent_id: str,
    bot_status: str | None = None,
    limit: int = 20,
    db=Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """List meeting bots (active and past) for an agent via Recall.ai."""
    agent = await _get_agent(agent_id, tenant_id, db)
    cfg = _get_voice_meetings_config(agent)

    if not cfg.get("meeting_bot", {}).get("enabled"):
        return {"bots": [], "total": 0}

    from src.services.agents.credential_resolver import CredentialResolver
    from src.services.recall.recall_service import RecallService

    class _FakeContext:
        def __init__(self, agent_id, tenant_id, db_session):
            self.agent_id = agent_id
            self.tenant_id = tenant_id
            self.db_session = db_session

    ctx = _FakeContext(agent.id, tenant_id, db)
    resolver = CredentialResolver(ctx)
    api_key, region, _ = await resolver.get_recall_credentials("internal_recall_list_bots")
    if not api_key:
        return {"bots": [], "total": 0}

    from src.utils.config_helper import get_app_base_url

    service = RecallService(api_key=api_key, region=region, webhook_base_url=get_app_base_url())
    result = await service.list_bots(status=bot_status, limit=limit)
    if not result.get("success"):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=result.get("error", "Recall.ai error"))

    return result["data"]


@router.delete("/{agent_id}/meetings/{bot_id}")
async def remove_meeting_bot(
    agent_id: str,
    bot_id: str,
    db=Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """Remove a Recall.ai bot from a meeting."""
    agent = await _get_agent(agent_id, tenant_id, db)

    from src.services.agents.credential_resolver import CredentialResolver
    from src.services.recall.recall_service import RecallService
    from src.utils.config_helper import get_app_base_url

    class _FakeContext:
        def __init__(self, agent_id, tenant_id, db_session):
            self.agent_id = agent_id
            self.tenant_id = tenant_id
            self.db_session = db_session

    ctx = _FakeContext(agent.id, tenant_id, db)
    resolver = CredentialResolver(ctx)
    api_key, region, _ = await resolver.get_recall_credentials("internal_recall_remove_bot")
    if not api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Recall.ai is not configured.")

    service = RecallService(api_key=api_key, region=region, webhook_base_url=get_app_base_url())
    result = await service.remove_bot(bot_id)
    if not result.get("success"):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=result.get("error", "Recall.ai error"))

    return {"success": True}


@router.get("/{agent_id}/meetings/{bot_id}/transcript")
async def get_meeting_transcript(
    agent_id: str,
    bot_id: str,
    db=Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """Get transcript for a completed meeting."""
    agent = await _get_agent(agent_id, tenant_id, db)

    from src.services.agents.credential_resolver import CredentialResolver
    from src.services.recall.recall_service import RecallService
    from src.utils.config_helper import get_app_base_url

    class _FakeContext:
        def __init__(self, agent_id, tenant_id, db_session):
            self.agent_id = agent_id
            self.tenant_id = tenant_id
            self.db_session = db_session

    ctx = _FakeContext(agent.id, tenant_id, db)
    resolver = CredentialResolver(ctx)
    api_key, region, _ = await resolver.get_recall_credentials("internal_recall_get_transcript")
    if not api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Recall.ai is not configured.")

    service = RecallService(api_key=api_key, region=region, webhook_base_url=get_app_base_url())
    result = await service.get_transcript(bot_id)
    if not result.get("success"):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=result.get("error", "Recall.ai error"))

    return result["data"]
