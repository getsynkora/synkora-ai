"""
Agents controller package.

Exports all agent-related routers.
"""

from fastapi import APIRouter

from .agent_public_profile import public_router as agents_public_profile_public_router
from .agent_public_profile import router as agents_public_profile_router
from .chat import agents_chat_router
from .chat_config import router as agents_chat_config_router
from .context_files import agents_context_files_router
from .conversations import agents_conversations_router
from .custom_tools import agents_custom_tools_router
from .index import agents_index_router
from .knowledge_bases import agents_knowledge_bases_router
from .llm_configs import router as agents_llm_configs_router
from .mcp_servers import agents_mcp_servers_router
from .public import agents_public_router
from .skills import agents_skills_router
from .slack_manifest import slack_manifest_router
from .tools import agents_tools_router
from .versions import versions_router as agents_versions_router

# Create main agents router
agents_router = APIRouter()

# Include all sub-routers
agents_router.include_router(agents_chat_router)
agents_router.include_router(agents_chat_config_router)
agents_router.include_router(agents_tools_router, tags=["agent-tools"])
agents_router.include_router(agents_knowledge_bases_router)
agents_router.include_router(agents_mcp_servers_router)
agents_router.include_router(agents_context_files_router)
agents_router.include_router(agents_skills_router)
agents_router.include_router(agents_custom_tools_router)
agents_router.include_router(agents_conversations_router)
agents_router.include_router(agents_public_router)
agents_router.include_router(agents_llm_configs_router)
agents_router.include_router(agents_versions_router)
agents_router.include_router(slack_manifest_router, tags=["slack-manifest"])
agents_router.include_router(agents_public_profile_router)
agents_router.include_router(agents_index_router)  # Must be last due to /{agent_slug} catch-all route
