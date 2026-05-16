"""
Agent Chat Configuration Controller
Handles endpoints for managing agent chat customization
"""

import logging
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from ...core.database import get_async_db
from ...middleware.auth_middleware import get_current_tenant_id
from ...models.agent import Agent

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatConfigUpdate(BaseModel):
    """Request model for updating chat configuration"""

    chat_title: str | None = Field(None, max_length=200)
    chat_welcome_message: str | None = None
    chat_placeholder: str | None = Field(None, max_length=200)
    chat_primary_color: str | None = Field(None, max_length=7)
    chat_logo_url: str | None = Field(None, max_length=500)
    chat_background_color: str | None = Field(None, max_length=7)
    chat_font_family: str | None = Field(None, max_length=100)
    chat_transport: Literal["sse", "websocket"] | None = Field(
        None,
        description="Chat transport protocol. 'sse' uses HTTP streaming (default); 'websocket' uses a persistent connection.",
    )


@router.get("/agents/{agent_id}/chat-config")
async def get_agent_chat_config(agent_id: uuid.UUID, db: AsyncSession = Depends(get_async_db)):
    """
    Get chat configuration for an agent
    This endpoint can be called without authentication for public access
    """
    try:
        result = await db.execute(select(Agent).filter(Agent.id == agent_id))
        agent = result.scalar_one_or_none()

        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        # Get chat config from agent_metadata
        metadata = agent.agent_metadata or {}
        chat_config = metadata.get("chat_config", {})

        # Return configuration with defaults
        config = {
            "chat_title": chat_config.get("chat_title", ""),
            "chat_welcome_message": chat_config.get("chat_welcome_message", ""),
            "chat_placeholder": chat_config.get("chat_placeholder", ""),
            "chat_primary_color": chat_config.get("chat_primary_color", "#0d9488"),
            "chat_logo_url": chat_config.get("chat_logo_url", ""),
            "chat_background_color": chat_config.get("chat_background_color", "#ffffff"),
            "chat_font_family": chat_config.get("chat_font_family", "Inter"),
            "chat_transport": chat_config.get("chat_transport", "sse"),
        }

        return {"success": True, "data": config}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching agent chat config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/agents/{agent_id}/chat-config")
async def update_agent_chat_config(
    agent_id: uuid.UUID,
    config_data: ChatConfigUpdate,
    db: AsyncSession = Depends(get_async_db),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    """
    Update chat configuration for an agent
    Requires authentication
    """
    try:
        # Find agent by UUID, scoped to tenant for security
        result = await db.execute(select(Agent).filter(Agent.id == agent_id, Agent.tenant_id == tenant_id))
        agent = result.scalar_one_or_none()

        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        # Get existing metadata or create new
        metadata = agent.agent_metadata or {}
        chat_config = metadata.get("chat_config", {})

        # Update only provided fields
        update_data = config_data.dict(exclude_unset=True)
        chat_config.update(update_data)

        # Update metadata
        metadata["chat_config"] = chat_config
        agent.agent_metadata = metadata

        # Mark as modified for SQLAlchemy to detect the change
        flag_modified(agent, "agent_metadata")

        await db.commit()
        await db.refresh(agent)

        # Return updated configuration
        updated_config = {
            "chat_title": chat_config.get("chat_title", ""),
            "chat_welcome_message": chat_config.get("chat_welcome_message", ""),
            "chat_placeholder": chat_config.get("chat_placeholder", ""),
            "chat_primary_color": chat_config.get("chat_primary_color", "#0d9488"),
            "chat_logo_url": chat_config.get("chat_logo_url", ""),
            "chat_background_color": chat_config.get("chat_background_color", "#ffffff"),
            "chat_font_family": chat_config.get("chat_font_family", "Inter"),
            "chat_transport": chat_config.get("chat_transport", "sse"),
        }

        return {"success": True, "message": "Chat configuration updated successfully", "data": updated_config}

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating agent chat config: {e}")
