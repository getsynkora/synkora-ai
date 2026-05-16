"""Email Templates Controller.

CRUD for email templates + agent assignment endpoints.

Routes:
  GET    /api/v1/email-templates           list all templates for tenant
  POST   /api/v1/email-templates           create template
  GET    /api/v1/email-templates/{id}      get one template
  PUT    /api/v1/email-templates/{id}      update template
  DELETE /api/v1/email-templates/{id}      delete (soft: is_active=False)

  GET    /api/v1/agents/{slug}/email-template         get assigned template
  PUT    /api/v1/agents/{slug}/email-template         assign template to agent
  DELETE /api/v1/agents/{slug}/email-template         remove assignment
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id
from src.models.agent import Agent
from src.models.email_template import EmailTemplate, EmailTemplateType

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class CreateEmailTemplateRequest(BaseModel):
    name: str = Field(..., max_length=100)
    description: str | None = Field(None, max_length=500)
    template_type: EmailTemplateType = EmailTemplateType.BUILTIN
    builtin_name: str | None = Field(None, max_length=50)
    html_content: str | None = None
    external_provider: str | None = Field(None, max_length=50)
    external_template_id: str | None = Field(None, max_length=200)
    external_config: dict[str, Any] | None = None
    preview_html: str | None = None


class UpdateEmailTemplateRequest(BaseModel):
    name: str | None = Field(None, max_length=100)
    description: str | None = Field(None, max_length=500)
    builtin_name: str | None = Field(None, max_length=50)
    html_content: str | None = None
    external_provider: str | None = Field(None, max_length=50)
    external_template_id: str | None = Field(None, max_length=200)
    external_config: dict[str, Any] | None = None
    preview_html: str | None = None
    is_active: bool | None = None


class AssignEmailTemplateRequest(BaseModel):
    email_template_id: uuid.UUID


def _serialize(tmpl: EmailTemplate) -> dict[str, Any]:
    return {
        "id": str(tmpl.id),
        "name": tmpl.name,
        "description": tmpl.description,
        "template_type": tmpl.template_type,
        "builtin_name": tmpl.builtin_name,
        "html_content": tmpl.html_content,
        "external_provider": tmpl.external_provider,
        "external_template_id": tmpl.external_template_id,
        "external_config": tmpl.external_config,
        "preview_html": tmpl.preview_html,
        "is_active": tmpl.is_active,
        "created_at": tmpl.created_at.isoformat() if tmpl.created_at else None,
        "updated_at": tmpl.updated_at.isoformat() if tmpl.updated_at else None,
    }


# ---------------------------------------------------------------------------
# Template CRUD
# ---------------------------------------------------------------------------


@router.get("/email-templates")
async def list_email_templates(
    db: AsyncSession = Depends(get_async_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    result = await db.execute(
        select(EmailTemplate)
        .where(EmailTemplate.tenant_id == tenant_id, EmailTemplate.is_active.is_(True))
        .order_by(EmailTemplate.created_at.desc())
    )
    templates = result.scalars().all()
    return {"success": True, "data": [_serialize(t) for t in templates]}


@router.post("/email-templates", status_code=status.HTTP_201_CREATED)
async def create_email_template(
    body: CreateEmailTemplateRequest,
    db: AsyncSession = Depends(get_async_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    tmpl = EmailTemplate(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=body.name,
        description=body.description,
        template_type=body.template_type,
        builtin_name=body.builtin_name,
        html_content=body.html_content,
        external_provider=body.external_provider,
        external_template_id=body.external_template_id,
        external_config=body.external_config,
        preview_html=body.preview_html,
    )
    db.add(tmpl)
    await db.commit()
    await db.refresh(tmpl)
    return {"success": True, "data": _serialize(tmpl)}


@router.get("/email-templates/{template_id}")
async def get_email_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    result = await db.execute(
        select(EmailTemplate).where(
            EmailTemplate.id == template_id,
            EmailTemplate.tenant_id == tenant_id,
        )
    )
    tmpl = result.scalar_one_or_none()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"success": True, "data": _serialize(tmpl)}


@router.put("/email-templates/{template_id}")
async def update_email_template(
    template_id: uuid.UUID,
    body: UpdateEmailTemplateRequest,
    db: AsyncSession = Depends(get_async_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    result = await db.execute(
        select(EmailTemplate).where(
            EmailTemplate.id == template_id,
            EmailTemplate.tenant_id == tenant_id,
        )
    )
    tmpl = result.scalar_one_or_none()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tmpl, field, value)

    await db.commit()
    await db.refresh(tmpl)
    return {"success": True, "data": _serialize(tmpl)}


@router.delete("/email-templates/{template_id}")
async def delete_email_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    result = await db.execute(
        select(EmailTemplate).where(
            EmailTemplate.id == template_id,
            EmailTemplate.tenant_id == tenant_id,
        )
    )
    tmpl = result.scalar_one_or_none()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")

    tmpl.is_active = False
    await db.commit()
    return {"success": True, "message": "Template deleted"}


# ---------------------------------------------------------------------------
# Agent assignment endpoints
# ---------------------------------------------------------------------------


@router.get("/agents/{agent_slug}/email-template")
async def get_agent_email_template(
    agent_slug: str,
    db: AsyncSession = Depends(get_async_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    result = await db.execute(select(Agent).where(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if not agent.email_template_id:
        return {"success": True, "data": None}

    tmpl_result = await db.execute(select(EmailTemplate).where(EmailTemplate.id == agent.email_template_id))
    tmpl = tmpl_result.scalar_one_or_none()
    return {"success": True, "data": _serialize(tmpl) if tmpl else None}


@router.put("/agents/{agent_slug}/email-template")
async def assign_email_template(
    agent_slug: str,
    body: AssignEmailTemplateRequest,
    db: AsyncSession = Depends(get_async_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    result = await db.execute(select(Agent).where(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Verify template belongs to this tenant
    tmpl_result = await db.execute(
        select(EmailTemplate).where(
            EmailTemplate.id == body.email_template_id,
            EmailTemplate.tenant_id == tenant_id,
            EmailTemplate.is_active.is_(True),
        )
    )
    tmpl = tmpl_result.scalar_one_or_none()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found or inactive")

    agent.email_template_id = body.email_template_id
    await db.commit()
    return {"success": True, "message": "Template assigned", "data": _serialize(tmpl)}


@router.delete("/agents/{agent_slug}/email-template")
async def remove_email_template(
    agent_slug: str,
    db: AsyncSession = Depends(get_async_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    result = await db.execute(select(Agent).where(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent.email_template_id = None
    await db.commit()
    return {"success": True, "message": "Template assignment removed"}
