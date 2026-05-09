"""
Knowledge Compiler — Core service for generating wiki articles from knowledge base documents.

Takes raw documents from a knowledge base, uses LLM to extract entities and relationships,
and generates structured wiki articles with cross-references.
"""

import logging
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.wiki_article import WikiArticle, WikiCompilationJob

logger = logging.getLogger(__name__)

# Default categories for auto-generated articles
WIKI_CATEGORIES = ["projects", "people", "decisions", "processes", "architecture", "general"]


def _recover_partial_json(text: str) -> list[dict]:
    """
    Attempt to recover complete article objects from a truncated JSON array.
    Extracts any fully-closed objects before the truncation point.
    """

    articles = []
    # Find all complete JSON objects using brace depth tracking
    depth = 0
    start = None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                candidate = text[start : i + 1]
                try:
                    obj = __import__("json").loads(candidate)
                    if isinstance(obj, dict) and "title" in obj and "content" in obj:
                        articles.append(obj)
                except Exception:
                    pass
                start = None
    return articles


# Slug generation
def _slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug[:200]


class KnowledgeCompiler:
    """Compiles knowledge base documents into wiki articles."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def compile(
        self,
        knowledge_base_id: int,
        tenant_id: str,
        llm_config: dict[str, Any] | None = None,
        llm_config_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Run a full compilation of a knowledge base into wiki articles.

        1. Fetch recent/new documents from the knowledge base
        2. For each batch, extract entities via LLM
        3. Generate/update wiki articles
        4. Resolve cross-references (backlinks)

        Returns compilation summary.
        """
        from src.models.document import Document, DocumentStatus
        from src.models.document_segment import DocumentSegment

        job = WikiCompilationJob(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            knowledge_base_id=knowledge_base_id,
            status="running",
            started_at=datetime.now(UTC),
        )
        self.db.add(job)
        await self.db.commit()

        articles_created = 0
        articles_updated = 0
        errors: list[str] = []

        try:
            # Fetch documents from this knowledge base
            # Include COMPLETED and documents that have content (handles stuck PENDING status)
            result = await self.db.execute(
                select(Document)
                .filter(
                    Document.knowledge_base_id == knowledge_base_id,
                    (
                        (Document.status == DocumentStatus.COMPLETED)
                        | (Document.content.isnot(None) & (Document.content != ""))
                    ),
                )
                .order_by(Document.created_at.desc())
                .limit(100)
            )
            documents = result.scalars().all()

            if not documents:
                job.status = "completed"
                job.completed_at = datetime.now(UTC)
                job.compilation_metadata = {"documents_processed": 0}
                await self.db.commit()
                return {"status": "completed", "documents_processed": 0}

            # Fetch segments for content
            doc_ids = [d.id for d in documents]
            seg_result = await self.db.execute(
                select(DocumentSegment)
                .filter(DocumentSegment.document_id.in_(doc_ids))
                .order_by(DocumentSegment.position)
                .limit(500)
            )
            segments = seg_result.scalars().all()

            # Group content by document — prefer segments, fall back to document.content
            doc_content: dict[str, str] = {}
            for seg in segments:
                doc_id = str(seg.document_id)
                if doc_id not in doc_content:
                    doc_content[doc_id] = ""
                doc_content[doc_id] += (seg.content or "") + "\n"

            # Fall back to document-level content for docs without segments
            for doc in documents:
                doc_id = str(doc.id)
                if doc_id not in doc_content or not doc_content[doc_id].strip():
                    if doc.content and doc.content.strip():
                        doc_content[doc_id] = doc.content

            logger.info(
                f"Compilation KB={knowledge_base_id}: {len(documents)} docs, "
                f"{len(segments)} segments, {sum(1 for v in doc_content.values() if v.strip())} with content"
            )

            # Resolve LLM config — prefer KB's own key, fall back to agent configs
            resolved_llm = await self._resolve_llm_config(knowledge_base_id, tenant_id, llm_config, llm_config_id)

            # Extract entities and generate articles via LLM
            article_proposals = await self._extract_entities(documents, doc_content, resolved_llm)

            # Create or update articles
            for proposal in article_proposals:
                try:
                    slug = _slugify(proposal["title"])

                    # Check if article exists
                    existing = await self.db.execute(
                        select(WikiArticle).filter(
                            WikiArticle.knowledge_base_id == knowledge_base_id,
                            WikiArticle.slug == slug,
                        )
                    )
                    article = existing.scalar_one_or_none()

                    if article:
                        article.content = proposal["content"]
                        article.summary = proposal.get("summary", "")
                        article.category = proposal.get("category", "general")
                        article.source_documents = proposal.get("sources", [])
                        article.last_compiled_at = datetime.now(UTC)
                        article.staleness_score = 0.0
                        article.status = "published"
                        articles_updated += 1
                    else:
                        article = WikiArticle(
                            id=uuid.uuid4(),
                            tenant_id=tenant_id,
                            knowledge_base_id=knowledge_base_id,
                            title=proposal["title"],
                            slug=slug,
                            content=proposal["content"],
                            category=proposal.get("category", "general"),
                            summary=proposal.get("summary", ""),
                            source_documents=proposal.get("sources", []),
                            auto_generated=True,
                            last_compiled_at=datetime.now(UTC),
                            status="published",
                        )
                        self.db.add(article)
                        articles_created += 1

                except Exception as e:
                    logger.warning(f"Failed to create/update article: {e}")
                    errors.append(str(e))

            await self.db.commit()

            # Resolve cross-references
            await self._resolve_links(knowledge_base_id)

            # Mark ALL articles in this KB as freshly compiled.
            # The compiler reviewed the latest documents; any article not regenerated
            # in this run was deliberately kept — it is still current.
            compiled_now = datetime.now(UTC)
            all_articles_result = await self.db.execute(
                select(WikiArticle).filter(
                    WikiArticle.knowledge_base_id == knowledge_base_id,
                    WikiArticle.status == "published",
                )
            )
            for art in all_articles_result.scalars().all():
                art.last_compiled_at = compiled_now
                art.staleness_score = 0.0
            await self.db.commit()
            logger.info(f"Reset staleness to 0 for all published articles in KB {knowledge_base_id}")

            job.status = "completed"
            job.completed_at = datetime.now(UTC)
            job.articles_created = articles_created
            job.articles_updated = articles_updated
            job.errors = errors
            job.compilation_metadata = {
                "documents_processed": len(documents),
                "segments_processed": len(segments),
                "total_articles": articles_created + articles_updated,
            }
            await self.db.commit()

            # Queue embedding of wiki articles into the KB vector store so agents can RAG them
            try:
                from src.tasks.knowledge_compiler_task import embed_wiki_documents

                embed_wiki_documents.delay(knowledge_base_id, tenant_id)
                logger.info(f"Queued wiki embedding for KB {knowledge_base_id}")
            except Exception as e:
                logger.warning(f"Failed to queue wiki embedding: {e}")

            return {
                "status": "completed",
                "job_id": str(job.id),
                "articles_created": articles_created,
                "articles_updated": articles_updated,
                "documents_processed": len(documents),
                "errors": errors,
            }

        except Exception as e:
            logger.error(f"Compilation failed: {e}", exc_info=True)
            await self.db.rollback()
            job.status = "failed"
            job.completed_at = datetime.now(UTC)
            job.errors = errors + [str(e)]
            try:
                self.db.add(job)
                await self.db.commit()
            except Exception:
                logger.warning("Failed to update compilation job status after error")
            return {"status": "failed", "error": str(e)}

    async def _resolve_llm_config(
        self,
        knowledge_base_id: int,
        tenant_id: str,
        llm_config: dict[str, Any] | None,
        llm_config_id: str | None = None,
    ) -> dict[str, Any]:
        """Resolve LLM configuration.

        Priority order:
        1. Explicit llm_config dict (e.g. from API with api_key)
        2. Specific AgentLLMConfig by llm_config_id (user-selected on wiki page)

        A llm_config_id is required when no explicit config dict is supplied.
        API key is then overridden with KB's embedding_config key if available.
        """
        if llm_config and llm_config.get("api_key"):
            return llm_config

        from src.models.agent_llm_config import AgentLLMConfig
        from src.models.knowledge_base import KnowledgeBase
        from src.services.agents.security import decrypt_value

        if not llm_config_id:
            raise ValueError(
                "No LLM configuration selected. Choose an LLM configuration on the knowledge base settings page."
            )

        result = await self.db.execute(select(AgentLLMConfig).filter(AgentLLMConfig.id == llm_config_id))
        agent_config = result.scalar_one_or_none()
        if not agent_config:
            raise ValueError(f"LLM configuration '{llm_config_id}' not found.")

        provider = agent_config.provider
        model = agent_config.model_name
        api_base = agent_config.api_base
        temperature = agent_config.temperature or 0.7
        max_tokens = agent_config.max_tokens

        # Use KB's embedding_config API key (user updates this via KB edit page).
        # If the KB has no key of its own, use the selected agent LLM config's key.
        api_key = ""
        kb_result = await self.db.execute(select(KnowledgeBase).filter(KnowledgeBase.id == knowledge_base_id))
        kb = kb_result.scalar_one_or_none()

        if kb and kb.embedding_config and kb.embedding_config.get("api_key"):
            try:
                kb_api_key = decrypt_value(kb.embedding_config["api_key"])
                if kb_api_key and kb_api_key.strip():
                    api_key = kb_api_key
                    if not api_base and kb.embedding_config.get("api_base"):
                        api_base = kb.embedding_config["api_base"]
                    logger.info("Using KB embedding API key for compilation")
            except Exception as e:
                raise ValueError(f"Failed to decrypt knowledge base API key: {e}") from e

        if not api_key or not api_key.strip():
            api_key = decrypt_value(agent_config.api_key) if agent_config.api_key else ""

        if not api_key or not api_key.strip():
            raise ValueError(
                "No API key found. Set an API key in the knowledge base settings or in the selected LLM configuration."
            )

        return {
            "provider": provider,
            "model": model,
            "api_key": api_key,
            "api_base": api_base,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

    async def _extract_entities(
        self,
        documents: list,
        doc_content: dict[str, str],
        llm_config: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Use LLM to extract wiki-worthy entities from documents.

        Returns a list of article proposals:
        [{title, content, category, summary, sources}]
        """
        import json

        # Build a combined text summary (first 8000 chars per doc)
        combined_text = ""
        source_refs = []
        for doc in documents[:20]:  # Process up to 20 docs per batch
            content = doc_content.get(str(doc.id), "")[:8000]
            if content.strip():
                combined_text += f"\n--- Document: {doc.name or 'Untitled'} ---\n{content}\n"
                source_refs.append({"doc_id": str(doc.id), "doc_title": doc.name or "Untitled"})

        if not combined_text.strip():
            logger.warning(f"No text content found in {len(documents)} documents — nothing to compile")
            return []

        logger.info(f"Extracting entities from {len(source_refs)} documents ({len(combined_text)} chars)")

        prompt = f"""Analyze the following documents and extract wiki-worthy articles.

For each article, provide:
- title: A clear, concise title
- category: One of: projects, people, decisions, processes, architecture, general
- summary: 1-2 sentence summary
- content: Full markdown article (3-10 paragraphs)

Return as JSON array:
[{{"title": "...", "category": "...", "summary": "...", "content": "..."}}]

Extract 3-8 meaningful articles. Focus on:
- Key projects and their status
- Important decisions and rationale
- Technical architecture patterns
- Processes and workflows
- Key people and their roles

Documents:
{combined_text[:30000]}

Return ONLY valid JSON array, no other text."""

        provider = llm_config.get("provider", "litellm")
        model = llm_config.get("model", "gpt-4o-mini")
        api_key = llm_config.get("api_key", "")
        api_base = llm_config.get("api_base") or None
        # Use configured max_tokens, but enforce a minimum of 4000 to avoid truncated JSON
        max_tokens = max(llm_config.get("max_tokens") or 4000, 4000)

        logger.info(
            f"Calling LLM provider={provider} model={model} max_tokens={max_tokens} api_base={api_base or 'default'}"
        )

        from src.services.agents.config import ModelConfig
        from src.services.agents.llm_client import MultiProviderLLMClient

        config = ModelConfig(
            provider=provider,
            model_name=model,
            max_tokens=max_tokens,
            api_key=api_key,
            api_base=api_base,
        )
        client = MultiProviderLLMClient(config=config)
        response = await client.generate_content(prompt, max_tokens=max_tokens)

        if not response or not response.strip():
            logger.error("LLM returned empty response")
            return []

        # Parse JSON from response
        text = response.strip()
        # Handle markdown code blocks
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            text = text.rsplit("```", 1)[0]

        try:
            articles = json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"LLM returned truncated JSON, attempting repair: {e}")
            # Attempt to recover partial articles from truncated JSON
            articles = _recover_partial_json(text)
            if not articles:
                logger.error(f"Could not recover JSON: {e}\nResponse: {text[:500]}")
                raise ValueError(f"LLM returned invalid JSON: {e}") from e
            logger.info(f"Recovered {len(articles)} articles from truncated JSON")

        if not isinstance(articles, list):
            articles = [articles]

        logger.info(f"LLM extracted {len(articles)} article proposals")

        # Attach source refs
        for article in articles:
            article["sources"] = source_refs

        return articles

    async def _resolve_links(self, knowledge_base_id: int) -> None:
        """Resolve cross-references between articles in the same KB."""
        result = await self.db.execute(
            select(WikiArticle).filter(
                WikiArticle.knowledge_base_id == knowledge_base_id,
                WikiArticle.status == "published",
            )
        )
        articles = result.scalars().all()

        title_map = {a.title.lower(): str(a.id) for a in articles}

        for article in articles:
            forward_links = []
            content_lower = article.content.lower()

            for title, article_id in title_map.items():
                if article_id == str(article.id):
                    continue
                if title in content_lower:
                    forward_links.append(article_id)

            article.forward_links = forward_links

        # Build backlinks
        for article in articles:
            backlinks = []
            article_id = str(article.id)
            for other in articles:
                if article_id in (other.forward_links or []):
                    backlinks.append(str(other.id))
            article.backlinks = backlinks

        await self.db.commit()
