"""
Public (unauthenticated) endpoint for accessing shared conversations.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.services.conversation_share_service import ConversationShareService
from src.services.share_card_service import extract_share_card_data, render_share_card_png

logger = logging.getLogger(__name__)

share_public_router = APIRouter()


async def _load_shared_conversation_payload(db: AsyncSession, token: str) -> tuple[Any, Any, list[Any], dict]:
    share = await ConversationShareService.validate_token(db, token)
    if not share:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share link not found or expired")

    from src.models.agent import Agent
    from src.models.conversation import Conversation
    from src.models.message import Message

    conv_result = await db.execute(select(Conversation).filter(Conversation.id == share.conversation_id))
    conversation = conv_result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    msg_result = await db.execute(
        select(Message)
        .filter(Message.conversation_id == share.conversation_id)
        .order_by(Message.created_at.asc())
        .limit(500)
    )
    messages = list(msg_result.scalars().all())

    agent_info: dict = {}
    if conversation.agent_id:
        agent_result = await db.execute(
            select(Agent.agent_name, Agent.avatar, Agent.description, Agent.tenant_id).filter(
                Agent.id == conversation.agent_id
            )
        )
        agent_row = agent_result.first()
        if agent_row:
            if str(agent_row.tenant_id) != str(share.tenant_id):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share link not found or expired")
            agent_info = {
                "name": agent_row.agent_name,
                "avatar": agent_row.avatar,
                "description": agent_row.description,
            }

    return share, conversation, messages, agent_info


@share_public_router.get("/api/v1/public/share/{token}")
async def get_shared_conversation(
    token: str,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Return a shared conversation's messages without authentication.

    Hashes the incoming token, validates it against the store, and returns
    conversation + messages (up to 500). Returns 404 for missing, expired,
    or revoked tokens.
    """
    try:
        share, conversation, messages, agent_info = await _load_shared_conversation_payload(db, token)

        return {
            "success": True,
            "data": {
                "conversation": conversation.to_dict(),
                "messages": [msg.to_dict() for msg in messages],
                "agent": agent_info,
                "expires_at": share.expires_at.isoformat(),
                "share_id": str(share.id),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to load shared conversation: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load conversation")


@share_public_router.get("/api/v1/public/share/{token}/image")
async def get_shared_conversation_image(
    token: str,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Return a branded PNG scorecard for a shared conversation.
    """
    try:
        _, conversation, messages, agent_info = await _load_shared_conversation_payload(db, token)
        card = extract_share_card_data(
            conversation_name=getattr(conversation, "name", None),
            agent_name=agent_info.get("name"),
            messages=[msg.to_dict() for msg in messages],
        )
        png_bytes = render_share_card_png(card)
        return Response(
            content=png_bytes,
            media_type="image/png",
            headers={"Cache-Control": "no-cache, no-store"},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to render shared conversation image: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to render share image")
