"""Slack App Manifest generator endpoint."""

import json
import logging
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.models.agent import Agent

logger = logging.getLogger(__name__)

slack_manifest_router = APIRouter()

BOT_SCOPES = [
    "app_mentions:read",
    "assistant:write",
    "channels:history",
    "channels:join",
    "channels:read",
    "channels:manage",
    "chat:write",
    "chat:write.customize",
    "chat:write.public",
    "files:read",
    "files:write",
    "groups:history",
    "groups:read",
    "groups:write",
    "im:history",
    "im:read",
    "im:write",
    "links:read",
    "links:write",
    "metadata.message:read",
    "mpim:history",
    "mpim:read",
    "mpim:write",
    "pins:read",
    "pins:write",
    "reactions:read",
    "reactions:write",
    "team:read",
    "usergroups:read",
    "users:read",
    "users:read.email",
    "users.profile:read",
    "bookmarks:read",
    "bookmarks:write",
    "canvases:read",
    "canvases:write",
]

BOT_EVENTS = [
    "app_mention",
    "assistant_thread_started",
    "assistant_thread_context_changed",
    "message.channels",
    "message.groups",
    "message.im",
    "message.mpim",
    "file_shared",
    "member_joined_channel",
    "reaction_added",
    "reaction_removed",
    "app_home_opened",
]


def _slugify(name: str) -> str:
    """Convert agent name to a safe filename slug."""
    slug = re.sub(r"[^\w\s-]", "", name.lower())
    slug = re.sub(r"[\s_-]+", "-", slug).strip("-")
    return slug or "agent"


def _build_manifest(agent_name: str, description: str | None) -> dict:
    bot_display_name = agent_name[:80]  # Slack limit
    app_description = (description or "AI agent powered by Synkora")[:140]  # Slack limit

    return {
        "_metadata": {"major_version": 1, "minor_version": 1},
        "display_information": {
            "name": agent_name[:35],  # Slack app name limit
            "description": app_description,
            "background_color": "#2563eb",
        },
        "features": {
            "app_home": {
                "home_tab_enabled": True,
                "messages_tab_enabled": True,
                "messages_tab_read_only_enabled": False,
            },
            "assistant": {
                "assistant_description": app_description,
            },
            "bot_user": {
                "display_name": bot_display_name,
                "always_online": True,
            },
        },
        "oauth_config": {
            "scopes": {
                "bot": BOT_SCOPES,
            }
        },
        "settings": {
            "event_subscriptions": {
                "bot_events": BOT_EVENTS,
            },
            "interactivity": {
                "is_enabled": True,
            },
            "org_deploy_enabled": False,
            "socket_mode_enabled": True,
            "token_rotation_enabled": False,
        },
    }


@slack_manifest_router.get("/{agent_id}/slack-manifest")
async def download_slack_manifest(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db),
    current_account=Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    """
    Generate and download a Slack app manifest for this agent.

    The manifest can be pasted directly into https://api.slack.com/apps when
    creating a new app ("Create from manifest"). It pre-configures the app name,
    description, bot scopes, event subscriptions, and socket mode.
    """
    result = await db.execute(select(Agent).where(Agent.id == agent_id, Agent.tenant_id == tenant_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    manifest = _build_manifest(agent.agent_name, agent.description)
    filename = f"slack-manifest-{_slugify(agent.agent_name)}.json"

    return Response(
        content=json.dumps(manifest, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
