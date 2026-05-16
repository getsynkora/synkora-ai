"""
System Prompt Builder for Agent Context Files.


This module provides functionality to build enhanced system prompts by combining
the original agent system prompt with extracted text from context files.
"""

import logging
import re
from datetime import UTC

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.agent_context_file import AgentContextFile

logger = logging.getLogger(__name__)


class SystemPromptBuilder:
    """
    Builds enhanced system prompts by combining original prompts with context files.

    This class handles the formatting and combination of:
    1. Original agent system prompt
    2. Extracted text from attached context files
    3. Proper formatting and separation
    """

    # Only compact once attached context is large enough that we would
    # otherwise send or truncate a very large block of text.
    DEFAULT_FULL_CONTEXT_THRESHOLD = 10000
    DEFAULT_PREVIEW_CHARS = 600
    DEFAULT_MAX_PREVIEW_FILES = 4

    def __init__(self, db: AsyncSession):
        """
        Initialize the prompt builder.

        Args:
            db: Database session
        """
        self.db = db

    async def build_enhanced_prompt(
        self,
        agent: Agent,
        include_context_files: bool = True,
        max_context_length: int | None = None,
        override_system_prompt: str | None = None,
        context_mode: str = "full",
        context_query: str | None = None,
        full_context_threshold: int | None = None,
        preview_chars: int | None = None,
        max_preview_files: int | None = None,
    ) -> str:
        """
        Build an enhanced system prompt for an agent.

        Args:
            agent: The agent to build the prompt for
            include_context_files: Whether to include context files (default: True)
            max_context_length: Maximum length for context text (optional)
            override_system_prompt: If provided, replaces agent.system_prompt without
                touching the ORM object (used by spawned workers to avoid inheriting
                the orchestrator's instructions)
            context_mode: How to include context files: "full", "preview", or "auto"
            context_query: User query used to rank preview snippets when compacting
            full_context_threshold: Auto mode threshold before switching to previews
            preview_chars: Characters per preview when compacting
            max_preview_files: Maximum files to preview when compacting

        Returns:
            Enhanced system prompt string
        """
        from datetime import datetime

        prompt_parts = []

        # 0. Add current date context.
        # Keep this stable within a day so provider prompt caches can reuse the
        # system prefix across turns instead of busting on every request.
        now = datetime.now(UTC)
        date_context = (
            f"Current date: {now.strftime('%A, %B %d, %Y')} (UTC).\n"
            "When users refer to 'today', 'tomorrow', 'next week', etc., use this date as reference."
        )
        prompt_parts.append(date_context)

        # 1. Add system prompt — use override if provided, otherwise use agent's stored prompt
        effective_system_prompt = override_system_prompt if override_system_prompt is not None else agent.system_prompt
        if effective_system_prompt:
            prompt_parts.append(effective_system_prompt.strip())

        # 2. Add context files if requested and available
        if include_context_files:
            context_text = await self._build_context_section(
                agent,
                max_context_length=max_context_length,
                context_mode=context_mode,
                context_query=context_query,
                full_context_threshold=full_context_threshold,
                preview_chars=preview_chars,
                max_preview_files=max_preview_files,
            )
            if context_text:
                prompt_parts.append(context_text)

        # Combine all parts with double newlines
        enhanced_prompt = "\n\n".join(prompt_parts)

        return enhanced_prompt

    async def _build_context_section(
        self,
        agent: Agent,
        max_context_length: int | None = None,
        context_mode: str = "full",
        context_query: str | None = None,
        full_context_threshold: int | None = None,
        preview_chars: int | None = None,
        max_preview_files: int | None = None,
    ) -> str:
        """
        Build the context files section of the prompt.

        Uses its own database session to avoid autoflush issues with the parent session.
        This prevents TimeoutError during load testing when the parent session has dirty
        objects that would trigger autoflush before our SELECT query.

        Args:
            agent: The agent to get context files for
            max_context_length: Maximum length for context text (optional)
            context_mode: "full", "preview", or "auto"
            context_query: User query used to rank compact previews
            full_context_threshold: Auto mode threshold before switching to previews
            preview_chars: Characters per preview when compacting
            max_preview_files: Maximum files to preview when compacting

        Returns:
            Formatted context section string, or empty string if no files
        """
        context_files_data = await self._get_context_files_data(agent)
        return self._format_context_from_data(
            context_files_data,
            max_context_length=max_context_length,
            context_mode=context_mode,
            context_query=context_query,
            full_context_threshold=full_context_threshold,
            preview_chars=preview_chars,
            max_preview_files=max_preview_files,
        )

    async def _get_context_files_data(self, agent: Agent) -> list[dict]:
        """Load completed context files, preferring cache over database."""
        # PERFORMANCE: Check cache first before hitting database
        from src.services.cache import get_agent_cache

        cache = get_agent_cache()

        # Try to get from cache
        try:
            cached_data = await cache.get_context_files(str(agent.id))
            if cached_data:
                logger.info(f"⚡ Context files cache HIT for agent {agent.id}")
                return cached_data
        except Exception as e:
            logger.warning(f"Context cache read failed: {e}")

        # Cache MISS - query database using a fresh session to avoid autoflush issues
        # This prevents TimeoutError when the parent session has pending dirty objects
        from src.core.database import get_async_session_factory

        session_factory = get_async_session_factory()
        async with session_factory() as session:
            result = await session.execute(
                select(AgentContextFile)
                .filter(
                    AgentContextFile.agent_id == agent.id,
                    AgentContextFile.extraction_status == "COMPLETED",
                    AgentContextFile.extracted_text.isnot(None),
                )
                .order_by(AgentContextFile.display_order)
            )
            context_files = list(result.scalars().all())

        if not context_files:
            return []

        context_files_data = [{"filename": cf.filename, "extracted_text": cf.extracted_text} for cf in context_files]

        # Cache the context files data
        try:
            await cache.set_context_files(str(agent.id), context_files_data, ttl=300)  # 5 min cache
        except Exception as e:
            logger.warning(f"Failed to cache context files: {e}")

        return context_files_data

    def _format_context_from_data(
        self,
        context_files_data: list,
        max_context_length: int | None = None,
        context_mode: str = "full",
        context_query: str | None = None,
        full_context_threshold: int | None = None,
        preview_chars: int | None = None,
        max_preview_files: int | None = None,
    ) -> str:
        """Format context section from cached data."""
        if not context_files_data:
            return ""

        threshold = full_context_threshold or self.DEFAULT_FULL_CONTEXT_THRESHOLD
        preview_chars = preview_chars or self.DEFAULT_PREVIEW_CHARS
        max_preview_files = max_preview_files or self.DEFAULT_MAX_PREVIEW_FILES
        resolved_mode = context_mode

        if resolved_mode == "auto":
            total_text_length = sum(len(item.get("extracted_text", "") or "") for item in context_files_data)
            resolved_mode = "preview" if total_text_length > threshold else "full"

        if resolved_mode == "preview":
            return self._format_compact_context_from_data(
                context_files_data,
                max_context_length=max_context_length,
                context_query=context_query,
                preview_chars=preview_chars,
                max_preview_files=max_preview_files,
            )

        # Build context section
        context_parts = [
            "=" * 80,
            "CONTEXT FILES",
            "=" * 80,
            "",
            "The following files have been attached to provide you with additional context.",
            "Use this information to better understand the domain, requirements, or guidelines.",
            "",
        ]

        total_length = 0
        for context_file in context_files_data:
            # Add file header
            file_header = f"\n{'─' * 80}\n📄 {context_file['filename']}\n{'─' * 80}\n"
            context_parts.append(file_header)

            # Add extracted text
            extracted_text = context_file.get("extracted_text", "") or ""

            # Apply length limit if specified
            if max_context_length:
                remaining_length = max_context_length - total_length
                if remaining_length <= 0:
                    context_parts.append("\n[Additional context files omitted due to length limit]\n")
                    break

                if len(extracted_text) > remaining_length:
                    extracted_text = extracted_text[:remaining_length] + "\n\n[Content truncated due to length limit]"

            filename = context_file.get("filename", "unknown")
            context_parts.append(
                f'<context-document source="{filename}" trust="low">\n{extracted_text}\n</context-document>'
            )
            total_length += len(extracted_text)

        # Add closing separator
        context_parts.append(f"\n{'=' * 80}\n")

        return "\n".join(context_parts)

    def _format_compact_context_from_data(
        self,
        context_files_data: list[dict],
        max_context_length: int | None = None,
        context_query: str | None = None,
        preview_chars: int = DEFAULT_PREVIEW_CHARS,
        max_preview_files: int = DEFAULT_MAX_PREVIEW_FILES,
    ) -> str:
        """Format large context files as ranked previews instead of full text."""
        ranked_files = self._rank_context_files(context_files_data, context_query)
        context_parts = [
            "=" * 80,
            "CONTEXT FILES (COMPACTED)",
            "=" * 80,
            "",
            "Large attached context was compacted for token efficiency.",
            "Use the previews below as orientation; file names remain authoritative.",
            "",
        ]

        total_length = 0
        shown = 0
        for context_file in ranked_files:
            if shown >= max_preview_files:
                break

            extracted_text = context_file.get("extracted_text", "") or ""
            preview = self._build_preview_excerpt(extracted_text, context_query, preview_chars)
            if not preview:
                continue

            if max_context_length is not None:
                remaining_length = max_context_length - total_length
                if remaining_length <= 0:
                    context_parts.append("\n[Additional context previews omitted due to length limit]\n")
                    break
                if len(preview) > remaining_length:
                    preview = preview[:remaining_length].rstrip() + "..."

            filename = context_file.get("filename", "unknown")
            text_length = len(extracted_text)
            context_parts.append(f"\n{'─' * 80}\n📄 {filename} ({text_length:,} chars)\n{'─' * 80}\n")
            context_parts.append(
                f'<context-document-preview source="{filename}" trust="low">\n{preview}\n</context-document-preview>'
            )
            total_length += len(preview)
            shown += 1

        omitted = max(0, len(context_files_data) - shown)
        if omitted > 0:
            context_parts.append(f"\n[{omitted} additional context file(s) omitted from compact preview]\n")

        context_parts.append(f"\n{'=' * 80}\n")
        return "\n".join(context_parts)

    def _rank_context_files(self, context_files_data: list[dict], context_query: str | None = None) -> list[dict]:
        """Rank context files by simple lexical overlap with the current query."""
        if not context_query:
            return context_files_data

        query_terms = [term for term in re.findall(r"\w+", context_query.lower()) if len(term) >= 3]
        if not query_terms:
            return context_files_data

        scored: list[tuple[int, int, dict]] = []
        for idx, context_file in enumerate(context_files_data):
            text = (context_file.get("extracted_text", "") or "").lower()
            score = sum(text.count(term) for term in query_terms)
            scored.append((score, -idx, context_file))

        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [item[2] for item in scored]

    def _build_preview_excerpt(self, text: str, context_query: str | None, preview_chars: int) -> str:
        """Extract a compact preview centered on the most relevant matched term."""
        cleaned = (text or "").strip()
        if not cleaned:
            return ""

        if not context_query:
            return cleaned[:preview_chars].rstrip()

        query_terms = [term for term in re.findall(r"\w+", context_query.lower()) if len(term) >= 3]
        lowered = cleaned.lower()

        for term in query_terms:
            pos = lowered.find(term)
            if pos >= 0:
                half_window = max(preview_chars // 2, 1)
                start = max(pos - half_window, 0)
                end = min(start + preview_chars, len(cleaned))
                snippet = cleaned[start:end].strip()
                if start > 0:
                    snippet = "..." + snippet
                if end < len(cleaned):
                    snippet = snippet + "..."
                return snippet

        return cleaned[:preview_chars].rstrip()

    async def get_context_summary(self, agent: Agent) -> dict:
        """
        Get a summary of context files attached to an agent.

        Args:
            agent: The agent to get summary for

        Returns:
            Dictionary with context file statistics
        """
        result = await self.db.execute(select(AgentContextFile).filter(AgentContextFile.agent_id == agent.id))
        context_files = list(result.scalars().all())

        total_files = len(context_files)
        completed_files = sum(1 for f in context_files if f.extraction_status == "COMPLETED")
        pending_files = sum(1 for f in context_files if f.extraction_status == "PENDING")
        failed_files = sum(1 for f in context_files if f.extraction_status == "FAILED")

        total_size = sum(f.file_size for f in context_files)
        total_text_length = sum(
            len(f.extracted_text) if f.extracted_text else 0
            for f in context_files
            if f.extraction_status == "COMPLETED"
        )

        return {
            "total_files": total_files,
            "completed_files": completed_files,
            "pending_files": pending_files,
            "failed_files": failed_files,
            "total_size_bytes": total_size,
            "total_text_length": total_text_length,
            "files": [
                {
                    "filename": f.filename,
                    "file_type": f.file_type,
                    "file_size": f.file_size,
                    "extraction_status": f.extraction_status,
                    "text_length": len(f.extracted_text) if f.extracted_text else 0,
                }
                for f in context_files
            ],
        }

    @staticmethod
    def format_context_for_chat(original_prompt: str, context_text: str, user_message: str) -> str:
        """
        Format a complete prompt for chat including context.

        This is a utility method for formatting prompts in chat scenarios.

        Args:
            original_prompt: The original system prompt
            context_text: The context files text
            user_message: The user's message

        Returns:
            Formatted prompt string
        """
        parts = []

        if original_prompt:
            parts.append(original_prompt)

        if context_text:
            parts.append(context_text)

        if user_message:
            parts.append(f"\nUser: {user_message}\n\nAssistant:")

        return "\n\n".join(parts)
