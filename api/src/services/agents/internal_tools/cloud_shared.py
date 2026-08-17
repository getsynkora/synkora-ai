"""Shared credential-resolution helper for the AWS/GCP/Azure/DigitalOcean cloud provider tools.

Generalizes the per-provider `_get_openweather_config`-style pattern (see
`internal_tools/openweather_tools.py`) so all 4 cloud providers share a single implementation
instead of duplicating the AgentTool -> OAuthApp lookup + decryption logic 4 times.
"""

from typing import Any

from sqlalchemy import select

from src.core.database import get_async_session_factory
from src.models.agent_tool import AgentTool
from src.models.oauth_app import OAuthApp
from src.services.agents.security import decrypt_value


async def get_cloud_provider_config(runtime_context: Any, tool_name: str, provider: str) -> dict[str, Any]:
    """Resolve a cloud provider's credentials from the AgentTool -> OAuthApp link.

    Returns a dict shaped as `{"client_id": str, "api_token": str, "config": dict}` — the same
    shape every CloudProviderAdapter constructor expects.
    """
    async with get_async_session_factory()() as db:
        result = await db.execute(
            select(AgentTool).filter(
                AgentTool.agent_id == runtime_context.agent_id,
                AgentTool.tool_name == tool_name,
                AgentTool.enabled,
            )
        )
        agent_tool = result.scalar_one_or_none()
        if not agent_tool or not agent_tool.oauth_app_id:
            raise ValueError(
                f"No OAuth app configured for tool '{tool_name}'. "
                f"Please connect a {provider} OAuth app in Agent Tools settings."
            )

        result = await db.execute(
            select(OAuthApp).filter(
                OAuthApp.id == agent_tool.oauth_app_id,
                OAuthApp.provider.ilike(provider),
                OAuthApp.is_active,
            )
        )
        oauth_app = result.scalar_one_or_none()
        if not oauth_app:
            raise ValueError(f"No active {provider} OAuth app found. Check your integrations.")

        if not oauth_app.api_token:
            raise ValueError(f"{provider} credential is missing. Edit the OAuth app and add your credentials.")

        return {
            "client_id": oauth_app.client_id,
            "api_token": decrypt_value(oauth_app.api_token),
            "config": oauth_app.config or {},
        }
