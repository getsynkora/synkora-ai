"""DigestService — orchestrates daily digest generation for any data source."""

import json
import logging
import uuid
from datetime import date as DateType
from typing import Any, Union

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.daily_digest import DailyDigest, DigestStatus

logger = logging.getLogger(__name__)


class DigestService:
    """
    Generates and stores a DailyDigest for a single data source.

    Two-pass pipeline:
      1. Extractor fetches raw items via the existing connector (full recall, no RAG).
      2. LLM structures the raw text into highlights, decisions, action items, etc.

    The stored digest is then used by scheduled agents instead of hitting external
    APIs at query time — enabling large-scale summaries without rate-limit pressure.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate(
        self,
        data_source_id: int,
        target_date: DateType,
    ) -> DailyDigest:
        """
        Generate (or regenerate) the daily digest for a data source.

        Creates a new DailyDigest row or updates an existing one for the same
        (data_source_id, digest_date) pair.

        Returns the saved DailyDigest instance.
        """
        from src.models.data_source import DataSource

        data_source = await self.db.get(DataSource, data_source_id)
        if not data_source:
            raise ValueError(f"DataSource {data_source_id} not found")

        source_type = str(data_source.type).upper().replace("DATASOURCETYPE.", "")

        # Find or create digest row
        digest = await self._upsert_digest(data_source_id, source_type, target_date, data_source.tenant_id)
        digest.status = DigestStatus.PROCESSING
        digest.error = None
        await self.db.commit()

        try:
            from .registry import get_extractor

            extractor = get_extractor(source_type)
            if not extractor:
                digest.status = DigestStatus.FAILED
                digest.error = f"No extractor registered for source type: {source_type}"
                await self.db.commit()
                return digest

            start, end = extractor.date_range(target_date)
            items = await extractor.fetch_items(data_source, start, end, self.db)
            digest.items_processed = len(items)

            if not items:
                digest.structured_data = _empty_structured_data()
                digest.summary_text = f"No activity recorded on {target_date.isoformat()}."
                digest.status = DigestStatus.COMPLETED
                await self.db.commit()
                return digest

            llm_config = await self._resolve_llm_config(data_source.tenant_id)
            structured_data = await self._process_items(extractor, items, target_date, llm_config)
            digest.structured_data = structured_data
            digest.summary_text = _prose_summary(structured_data, source_type, target_date, len(items))
            digest.status = DigestStatus.COMPLETED

        except Exception as exc:
            logger.error(f"Digest generation failed for {data_source_id} on {target_date}: {exc}", exc_info=True)
            digest.status = DigestStatus.FAILED
            digest.error = str(exc)[:1000]

        await self.db.commit()
        return digest

    async def get_digest(
        self,
        data_source_id: int,
        target_date: DateType,
    ) -> DailyDigest | None:
        """Retrieve an existing digest, or None if not yet generated."""
        result = await self.db.execute(
            select(DailyDigest).where(
                DailyDigest.data_source_id == data_source_id,
                DailyDigest.digest_date == target_date,
            )
        )
        return result.scalar_one_or_none()

    async def get_digests_for_tenant(
        self,
        tenant_id: uuid.UUID,
        target_date: DateType,
        source_type: str | None = None,
    ) -> list[DailyDigest]:
        """Return all completed digests for a tenant on a given date."""
        q = select(DailyDigest).where(
            DailyDigest.tenant_id == tenant_id,
            DailyDigest.digest_date == target_date,
            DailyDigest.status == DigestStatus.COMPLETED,
        )
        if source_type:
            q = q.where(DailyDigest.source_type == source_type.upper())
        result = await self.db.execute(q)
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _upsert_digest(
        self,
        data_source_id: int,
        source_type: str,
        digest_date: DateType,
        tenant_id: uuid.UUID,
    ) -> DailyDigest:
        result = await self.db.execute(
            select(DailyDigest).where(
                DailyDigest.data_source_id == data_source_id,
                DailyDigest.digest_date == digest_date,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing

        digest = DailyDigest(
            tenant_id=tenant_id,
            data_source_id=data_source_id,
            source_type=source_type,
            digest_date=digest_date,
        )
        self.db.add(digest)
        await self.db.flush()
        return digest

    async def _resolve_llm_config(self, tenant_id: uuid.UUID) -> dict[str, Any]:
        """
        Resolve an LLM config to use for digest generation.

        Uses the tenant's default agent LLM config. The tenant must configure
        at least one agent with a default LLM config before digest generation works.
        """
        from src.models.agent import Agent
        from src.models.agent_llm_config import AgentLLMConfig
        from src.services.agents.security import decrypt_value

        result = await self.db.execute(
            select(AgentLLMConfig)
            .join(Agent, Agent.id == AgentLLMConfig.agent_id)
            .where(Agent.tenant_id == tenant_id, AgentLLMConfig.is_default == True)  # noqa: E712
            .limit(1)
        )
        llm_config_row = result.scalar_one_or_none()

        if not llm_config_row or not llm_config_row.api_key:
            raise RuntimeError(
                "No LLM configuration found for digest generation. Configure a default LLM model on one of your agents."
            )

        api_key = decrypt_value(llm_config_row.api_key)
        if not api_key:
            raise RuntimeError(
                "LLM configuration has no API key. Update the API key in the agent's LLM configuration settings."
            )

        return {
            "provider": llm_config_row.provider,
            "model": llm_config_row.model_name,
            "api_key": api_key,
            "api_base": llm_config_row.api_base,
            "max_tokens": 2000,
        }

    async def _process_items(
        self,
        extractor: Any,
        items: list[Any],
        target_date: DateType,
        llm_config: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Build prompt and call LLM. For extreme-volume days (total text > 300k chars)
        split into channel/type chunks, summarize each, then merge. This only triggers
        for very large orgs — the vast majority of data sources fit in one LLM call.
        """
        prompt = extractor.build_prompt(items, target_date)

        # ~300k chars ≈ 75k tokens — safe threshold well below 128k context limit
        if len(prompt) <= 300_000:
            return await self._call_llm(prompt, llm_config)

        # Safety valve: split into 500-item chunks, summarize each, merge
        logger.warning(
            f"Prompt too large ({len(prompt):,} chars) for {extractor.source_type} on {target_date}. "
            f"Splitting {len(items)} items into chunks."
        )
        chunk_size = 500
        chunks = [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]
        partials = []
        for chunk in chunks:
            chunk_prompt = extractor.build_prompt(chunk, target_date)
            partial = await self._call_llm(chunk_prompt, llm_config)
            partials.append(partial)

        return await self._merge_partials(partials, extractor.source_type, target_date, len(items), llm_config)

    async def _merge_partials(
        self,
        partials: list[dict[str, Any]],
        source_type: str,
        target_date: DateType,
        total_items: int,
        llm_config: dict[str, Any],
    ) -> dict[str, Any]:
        """Consolidate partial summaries into one final digest via a second LLM call."""
        from .base import DIGEST_JSON_SCHEMA

        summaries_text = json.dumps(partials, indent=2)
        prompt = f"""You are consolidating {len(partials)} partial {source_type} summaries for {target_date.isoformat()}.
Total items across all parts: {total_items}.

Partial summaries:
{summaries_text}

Merge into a single final summary. Deduplicate highlights and decisions. Sum activity counts.
Return ONLY valid JSON matching: {DIGEST_JSON_SCHEMA}"""

        return await self._call_llm(prompt, llm_config)

    async def _call_llm(self, prompt: str, llm_config: dict[str, Any]) -> dict[str, Any]:
        """Call LLM and parse the JSON response."""
        from src.services.agents.config import ModelConfig
        from src.services.agents.llm_client import MultiProviderLLMClient

        config = ModelConfig(
            provider=llm_config["provider"],
            model_name=llm_config["model"],
            max_tokens=llm_config.get("max_tokens", 2000),
            api_key=llm_config["api_key"],
            api_base=llm_config.get("api_base"),
        )
        client = MultiProviderLLMClient(config=config)
        response = await client.generate_content(prompt, max_tokens=llm_config.get("max_tokens", 2000))

        if not response or not response.strip():
            raise ValueError("LLM returned empty response")

        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            text = text.rsplit("```", 1)[0]

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            logger.error(f"LLM returned invalid JSON: {exc}\nResponse: {text[:500]}")
            raise ValueError(f"LLM returned invalid JSON: {exc}") from exc


def _empty_structured_data() -> dict[str, Any]:
    return {
        "total_items": 0,
        "activity_level": "low",
        "highlights": [],
        "key_decisions": [],
        "action_items": [],
        "topics": [],
        "source_specific": {},
    }


def _prose_summary(data: dict[str, Any], source_type: str, target_date: DateType, item_count: int) -> str:
    highlights = data.get("highlights", [])
    level = data.get("activity_level", "medium")
    topics = data.get("topics", [])
    decisions = data.get("key_decisions", [])
    actions = data.get("action_items", [])

    parts = [f"{source_type.title()} digest for {target_date.isoformat()}: {item_count} items, {level} activity."]
    if topics:
        parts.append(f"Topics: {', '.join(topics[:5])}.")
    if highlights:
        parts.append(f"Highlights: {highlights[0]}")
        if len(highlights) > 1:
            parts.append(f"(+{len(highlights) - 1} more).")
    if decisions:
        parts.append(f"{len(decisions)} decision(s) recorded.")
    if actions:
        parts.append(f"{len(actions)} action item(s) identified.")
    return " ".join(parts)
