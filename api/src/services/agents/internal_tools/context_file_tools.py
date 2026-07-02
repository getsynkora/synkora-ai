"""
Context File Loading Tool

Allows the LLM to load the content of on-demand context files at runtime.
Only returns files that belong to the current agent (tenant-scoped).
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def internal_load_context_file(
    filename: str,
    config: dict[str, Any] | None = None,
    **kwargs,
) -> dict[str, Any]:
    """
    Load the content of a context file that is available for this agent.

    Use this when you see a file listed under AVAILABLE CONTEXT FILES and need
    its content to complete the current task.

    Args:
        filename: Exact filename as shown in the AVAILABLE CONTEXT FILES list

    Returns:
        Dict with 'content' (the file text) or 'error' if not found
    """
    try:
        if not filename:
            return {"success": False, "error": "filename is required"}

        runtime_context = config.get("_runtime_context") if config else None
        if not runtime_context:
            return {"success": False, "error": "No runtime context available"}

        agent_id = getattr(runtime_context, "agent_id", None)
        tenant_id = getattr(runtime_context, "tenant_id", None)
        if not agent_id or not tenant_id:
            return {"success": False, "error": "Missing agent_id or tenant_id in runtime context"}

        from sqlalchemy import select

        from src.core.database import get_async_session_factory
        from src.models.agent import Agent
        from src.models.agent_context_file import AgentContextFile
        from src.services.cache import get_agent_cache

        session_factory = get_async_session_factory()
        async with session_factory() as session:
            # SECURITY: verify file belongs to this agent AND is on_demand
            result = await session.execute(
                select(AgentContextFile)
                .join(Agent, Agent.id == AgentContextFile.agent_id)
                .filter(
                    AgentContextFile.filename == filename,
                    Agent.id == agent_id,
                    Agent.tenant_id == tenant_id,
                    AgentContextFile.load_mode == "on_demand",
                    AgentContextFile.extraction_status == "COMPLETED",
                )
            )
            context_file = result.scalar_one_or_none()

        if not context_file:
            return {
                "success": False,
                "error": f"Context file '{filename}' not found for this agent",
            }

        file_id = str(context_file.id)

        # 1. Check Redis cache
        cache = get_agent_cache()
        content: str | None = None
        try:
            content = await cache.get_context_file_content(file_id)
        except Exception as e:
            logger.warning(f"Cache read error for file {file_id}: {e}")

        # 2. S3 fallback
        if content is None:
            try:
                from src.services.agents.context_file_processor import AgentContextFileProcessor
                from src.services.storage.s3_storage import S3StorageService

                s3 = S3StorageService()
                s3_url = f"s3://{context_file.s3_bucket}/{context_file.s3_key}"
                raw = await s3.download_file_content(s3_url)
                processor = AgentContextFileProcessor(db=None)
                content = await processor._extract_text(raw, context_file.file_type, filename)

                try:
                    await cache.set_context_file_content(file_id, content)
                except Exception as cache_err:
                    logger.warning(f"Failed to re-cache content for {filename}: {cache_err}")

            except Exception as e:
                logger.error(f"Failed to load {filename} from S3: {e}")
                return {"success": False, "error": f"Failed to load file content: {e}"}

        return {
            "success": True,
            "filename": filename,
            "content": content,
        }

    except Exception as e:
        logger.error(f"Error in internal_load_context_file: {e}")
        return {"success": False, "error": str(e)}
