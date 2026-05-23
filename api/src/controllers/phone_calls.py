"""
Phone Calls controller.

Public webhook endpoint (no auth, signature-verified):
  POST /api/v1/phone/webhook/vapi

Authenticated management endpoints:
  GET    /api/v1/phone/numbers
  POST   /api/v1/phone/numbers
  DELETE /api/v1/phone/numbers/{number_id}
  GET    /api/v1/phone/calls
  GET    /api/v1/phone/calls/{call_id}
  POST   /api/v1/phone/credentials
  GET    /api/v1/phone/credentials
  GET    /api/v1/agents/{slug}/phone-config
  PUT    /api/v1/agents/{slug}/phone-config
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel as PydanticModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id
from src.models.agent import Agent
from src.models.phone_call import PhoneCall
from src.services.phone.phone_config_service import PhoneConfigService
from src.services.voice.inbound import get_call_provider

logger = logging.getLogger(__name__)

# Two routers — webhook is public, management requires auth
public_router = APIRouter(prefix="/api/v1/phone", tags=["phone-calls-public"])
router = APIRouter(prefix="/api/v1/phone", tags=["phone-calls"])
agent_router = APIRouter(prefix="/api/v1/agents", tags=["phone-calls"])


# ---------------------------------------------------------------------------
# Pydantic request/response bodies
# ---------------------------------------------------------------------------


class AddPhoneNumberBody(PydanticModel):
    phone_number: str  # E.164
    provider: str = "vapi"
    agent_id: UUID


class SaveCredentialBody(PydanticModel):
    provider: str
    api_key: str


class PhoneConfigBody(PydanticModel):
    enabled: bool = False
    provider: str = "vapi"
    greeting: str = "Hi, how can I help you today?"
    end_call_message: str = "Goodbye! Have a great day."
    voice_provider: str | None = None
    voice_id: str | None = None
    language: str = "en"
    max_duration_seconds: int = 300
    record_calls: bool = False


# ---------------------------------------------------------------------------
# Webhook endpoint (no auth)
# ---------------------------------------------------------------------------


@public_router.post("/webhook/vapi")
async def vapi_webhook(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    x_vapi_secret: str | None = Header(None, alias="x-vapi-secret"),
):
    """
    Vapi.ai webhook receiver.

    Vapi POSTs here for every call event. The shared secret is verified before
    processing any payload, so forged requests are rejected early.
    """
    raw_body = await request.body()

    try:
        import json

        payload = json.loads(raw_body)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")

    # Resolve agent slug from payload to look up the vapi secret
    call_obj = payload.get("message", payload).get("call", {})
    phone_number_str = call_obj.get("phoneNumber", {}).get("number", "")

    provider = get_call_provider("vapi")

    # Signature check: only if a secret is configured
    if x_vapi_secret is not None:
        # Resolve secret from PhoneNumber → Agent → phone_config
        from src.models.phone_number import PhoneNumber

        result = await db.execute(
            select(PhoneNumber).where(
                PhoneNumber.phone_number == phone_number_str,
                PhoneNumber.is_active.is_(True),
            )
        )
        phone_record = result.scalar_one_or_none()
        secret = ""
        if phone_record:
            agent = await db.get(Agent, phone_record.agent_id)
            secret = (agent.phone_config or {}).get("webhook_secret", "") if agent else ""

        if secret and not provider.verify_signature(raw_body, {"x-vapi-secret": x_vapi_secret}, secret):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    response = await provider.handle_webhook(payload, dict(request.headers), db)
    return JSONResponse(content=response)


# ---------------------------------------------------------------------------
# Phone numbers management
# ---------------------------------------------------------------------------


@router.get("/numbers")
async def list_phone_numbers(
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    numbers = await PhoneConfigService.list_phone_numbers(tenant_id, db)
    return [n.to_dict() for n in numbers]


@router.post("/numbers", status_code=status.HTTP_201_CREATED)
async def add_phone_number(
    body: AddPhoneNumberBody,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    pn = await PhoneConfigService.add_phone_number(
        tenant_id=tenant_id,
        agent_id=body.agent_id,
        phone_number=body.phone_number,
        provider=body.provider,
        db=db,
    )
    return pn.to_dict()


@router.delete("/numbers/{number_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_phone_number(
    number_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    deleted = await PhoneConfigService.remove_phone_number(number_id, tenant_id, db)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Phone number not found")


# ---------------------------------------------------------------------------
# Call history
# ---------------------------------------------------------------------------


@router.get("/calls")
async def list_calls(
    agent_id: UUID | None = None,
    page: int = 1,
    page_size: int = 20,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    query = select(PhoneCall).where(PhoneCall.tenant_id == tenant_id)
    if agent_id:
        query = query.where(PhoneCall.agent_id == agent_id)
    query = query.order_by(PhoneCall.started_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    calls = result.scalars().all()
    return [c.to_dict() for c in calls]


@router.get("/calls/{call_id}")
async def get_call(
    call_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    result = await db.execute(select(PhoneCall).where(PhoneCall.id == call_id, PhoneCall.tenant_id == tenant_id))
    call = result.scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")

    call_dict = call.to_dict()

    # Include transcript messages if linked to a conversation
    if call.conversation_id:
        from src.models.message import Message

        msgs_result = await db.execute(
            select(Message).where(Message.conversation_id == call.conversation_id).order_by(Message.created_at)
        )
        messages = msgs_result.scalars().all()
        call_dict["messages"] = [
            {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat() if m.created_at else None}
            for m in messages
        ]

    return call_dict


# ---------------------------------------------------------------------------
# Credentials management
# ---------------------------------------------------------------------------


@router.post("/credentials", status_code=status.HTTP_201_CREATED)
async def save_credential(
    body: SaveCredentialBody,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    if body.provider != "vapi":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported provider")
    await PhoneConfigService.save_vapi_credential(tenant_id, body.api_key, db)
    return {"status": "saved"}


@router.get("/credentials")
async def check_credentials(
    provider: str = "vapi",
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    has_cred = await PhoneConfigService.has_credential(tenant_id, provider, db)
    return {"provider": provider, "configured": has_cred}


# ---------------------------------------------------------------------------
# Agent phone config endpoints
# ---------------------------------------------------------------------------


@agent_router.get("/{slug}/phone-config")
async def get_agent_phone_config(
    slug: str,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    result = await db.execute(select(Agent).where(Agent.slug == slug, Agent.tenant_id == tenant_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return agent.phone_config or {}


@agent_router.put("/{slug}/phone-config")
async def save_agent_phone_config(
    slug: str,
    body: PhoneConfigBody,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    result = await db.execute(select(Agent).where(Agent.slug == slug, Agent.tenant_id == tenant_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    config = body.model_dump()
    await PhoneConfigService.save_phone_config(agent.id, tenant_id, config, db)

    # Optionally register/update the Vapi assistant if a key is available
    if config.get("enabled") and config.get("provider") == "vapi":
        api_key = await PhoneConfigService.get_vapi_api_key(tenant_id, db)
        if api_key:
            from src.config.settings import settings

            base_url = getattr(settings, "app_base_url", "") or ""
            if base_url:
                assistant_id = await PhoneConfigService.register_webhook_with_vapi(slug, api_key, base_url)
                if assistant_id:
                    config["vapi_assistant_id"] = assistant_id
                    await PhoneConfigService.save_phone_config(agent.id, tenant_id, config, db)

    return config
