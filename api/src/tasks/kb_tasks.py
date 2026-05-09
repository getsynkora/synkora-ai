"""
Celery tasks for knowledge base document processing.

Handles chunking, embedding and storage as background jobs so HTTP
requests return immediately.
"""

import asyncio
import logging
from typing import Any  # noqa: F401 — used in inline type hints inside async functions

from src.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.process_kb_documents", bind=True, max_retries=2, default_retry_delay=30)
def process_kb_documents(self, data_source_id: int, tenant_id: str, documents: list[dict[str, Any]]) -> dict:
    """
    Chunk and embed documents for a knowledge base data source.

    Args:
        data_source_id: ID of the DataSource record
        tenant_id: Tenant UUID string
        documents: List of {id, text, metadata} dicts already extracted from files
    """
    try:
        asyncio.run(_process_kb_documents(data_source_id, tenant_id, documents))
        return {"status": "completed", "documents": len(documents)}
    except Exception as exc:
        logger.error(f"process_kb_documents failed for data_source={data_source_id}: {exc}", exc_info=True)
        raise self.retry(exc=exc)


@celery_app.task(name="tasks.crawl_and_process_kb", bind=True, max_retries=1, default_retry_delay=60)
def crawl_and_process_kb(
    self,
    data_source_id: int,
    tenant_id: str,
    url: str,
    max_pages: int,
    include_subpages: bool,
) -> dict:
    """
    Crawl a website and embed its content into a knowledge base data source.

    Args:
        data_source_id: ID of the DataSource record
        tenant_id: Tenant UUID string
        url: Starting URL to crawl
        max_pages: Maximum number of pages to crawl
        include_subpages: Whether to follow same-domain links
    """
    try:
        result = asyncio.run(_crawl_and_process_kb(data_source_id, tenant_id, url, max_pages, include_subpages))
        return {"status": "completed", **(result or {})}
    except Exception as exc:
        logger.error(f"crawl_and_process_kb failed for data_source={data_source_id}: {exc}", exc_info=True)
        raise self.retry(exc=exc)


@celery_app.task(name="tasks.analyze_app_store_reviews", bind=True, max_retries=1, default_retry_delay=60)
def analyze_app_store_reviews(
    self,
    source_id: str,
    tenant_id: str,
    llm_provider: str,
    llm_model: str,
    llm_api_key: str,
    limit: int,
    only_unanalyzed: bool,
) -> dict:
    """
    Analyze app store reviews using LLM in the background.

    Args:
        source_id: AppStoreSource UUID string
        tenant_id: Tenant UUID string
        llm_provider: LLM provider name
        llm_model: LLM model name
        llm_api_key: API key for the LLM provider
        limit: Max reviews to analyze
        only_unanalyzed: Whether to skip already-analyzed reviews
    """
    try:
        asyncio.run(
            _analyze_app_store_reviews(
                source_id, tenant_id, llm_provider, llm_model, llm_api_key, limit, only_unanalyzed
            )
        )
        return {"status": "completed"}
    except Exception as exc:
        logger.error(f"analyze_app_store_reviews failed for source={source_id}: {exc}", exc_info=True)
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Async implementations
# ---------------------------------------------------------------------------


async def _process_kb_documents(data_source_id: int, tenant_id: str, documents: list[dict[str, Any]]) -> None:
    from sqlalchemy import select

    from src.core.database import create_celery_async_session
    from src.models.data_source import DataSource
    from src.services.data_sources.document_processor import DocumentProcessor

    async_session_factory = create_celery_async_session()
    async with async_session_factory() as db:
        result = await db.execute(select(DataSource).filter(DataSource.id == data_source_id))
        data_source = result.scalar_one_or_none()
        if not data_source:
            logger.error(f"DataSource {data_source_id} not found — cannot process documents")
            return

        processor = DocumentProcessor(db)
        result = await processor.process_documents(data_source=data_source, documents=documents)
        logger.info(f"KB document processing done for data_source={data_source_id}: {result}")

        # Auto-recompile wiki if this KB already has wiki articles
        if data_source.knowledge_base_id and result.get("documents_processed", 0) > 0:
            from src.models.wiki_article import WikiArticle
            from src.tasks.knowledge_compiler_task import compile_single_knowledge_wiki

            wiki_check = await db.execute(
                select(WikiArticle.id).filter(WikiArticle.knowledge_base_id == data_source.knowledge_base_id).limit(1)
            )
            if wiki_check.scalar_one_or_none():
                compile_single_knowledge_wiki.delay(data_source.knowledge_base_id, str(data_source.tenant_id))
                logger.info(f"Triggered wiki recompile for KB {data_source.knowledge_base_id}")


async def _crawl_and_process_kb(
    data_source_id: int, tenant_id: str, url: str, max_pages: int, include_subpages: bool
) -> dict:
    """
    Crawl a website and embed its pages into a knowledge base.

    Uses concurrent HTTP fetching (up to CRAWL_CONCURRENCY parallel requests)
    and processes pages in batches of CRAWL_BATCH_SIZE to avoid holding the
    entire site in memory at once.
    """
    import asyncio as _asyncio
    from urllib.parse import urljoin, urlparse

    import httpx
    from bs4 import BeautifulSoup
    from sqlalchemy import select

    from src.core.database import create_celery_async_session
    from src.models.data_source import DataSource
    from src.services.data_sources.document_processor import DocumentProcessor
    from src.services.security.url_validator import validate_url

    async_session_factory = create_celery_async_session()

    CRAWL_CONCURRENCY = 10  # max parallel HTTP requests
    CRAWL_BATCH_SIZE = 20  # pages to embed per DB batch

    parsed_base = urlparse(url)
    visited: set[str] = set()
    queue: list[str] = [url]
    semaphore = _asyncio.Semaphore(CRAWL_CONCURRENCY)
    # Use a browser-like UA — "AI-Agent/1.0 (Web Crawler)" triggers Cloudflare/WAF blocks.
    # Googlebot is avoided because sites verify it via reverse DNS (our IP won't pass).
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }

    async def fetch_page(client: httpx.AsyncClient, page_url: str) -> dict[str, Any] | None:
        """Fetch and parse a single page. Returns doc dict or None on failure.

        Strategy:
        1. Try a plain HTTP GET with BeautifulSoup (fast, no JS).
        2. If that fails for any reason (HTTP error, exception, empty text after
           stripping boilerplate) fall back to Jina Reader which handles JS-rendered
           SPAs and Cloudflare-protected sites.
        """
        is_valid, err = validate_url(
            page_url, allowed_schemes=["http", "https"], block_private_ips=True, resolve_dns=True
        )
        if not is_valid:
            logger.warning(f"SSRF blocked: {page_url} — {err}")
            return None

        title = page_url
        text = ""
        new_links: list[str] = []
        _use_jina = False  # set to True whenever plain HTTP can't deliver usable text

        # --- Attempt 1: plain HTTP (fast, no JS) ---
        try:
            async with semaphore:
                response = await client.get(page_url, follow_redirects=True, timeout=20)
            if response.status_code >= 400:
                logger.info(f"Plain HTTP {response.status_code} for {page_url} — trying Jina Reader")
                _use_jina = True
            else:
                content_type = response.headers.get("content-type", "")
                if "text/html" not in content_type and "text/plain" not in content_type:
                    logger.info(f"Non-HTML content-type '{content_type}' for {page_url} — trying Jina Reader")
                    _use_jina = True
                else:
                    soup = BeautifulSoup(response.content, "html.parser")
                    title = soup.title.string.strip() if soup.title and soup.title.string else page_url
                    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
                        tag.decompose()
                    lines = [ln.strip() for ln in soup.get_text(separator="\n").splitlines() if ln.strip()]
                    text = "\n".join(lines)

                    if include_subpages:
                        for a in soup.find_all("a", href=True):
                            href = a["href"]
                            if href.startswith(("#", "mailto:", "javascript:", "tel:")):
                                continue
                            full = urljoin(page_url, href).split("#")[0].rstrip("/")
                            parsed_full = urlparse(full)
                            if parsed_full.netloc == parsed_base.netloc and full not in visited:
                                new_links.append(full)

                    if not text:
                        logger.info(f"Empty text after plain HTTP parse for {page_url} — trying Jina Reader")
                        _use_jina = True
        except Exception as exc:
            logger.info(f"Plain HTTP fetch failed for {page_url}: {exc} — trying Jina Reader")
            _use_jina = True

        # --- Attempt 2: Jina Reader (handles SPAs, Cloudflare, JS-rendered pages) ---
        if _use_jina:
            try:
                from src.services.agents.internal_tools.web_tools import _fetch_via_jina

                jina_result = await _fetch_via_jina(page_url)
                if jina_result.get("error"):
                    logger.warning(f"Crawl skipped {page_url} — Jina fallback failed: {jina_result['error']}")
                    return None
                text = (jina_result.get("content") or "").strip()
                if not text:
                    logger.warning(f"Crawl skipped {page_url} — empty text even after Jina Reader")
                    return None
                # Parse links from Jina's markdown output (avoids a separate scraper call
                # and sidesteps domcontentloaded timing issues with SPAs)
                if include_subpages and not new_links:
                    import re as _re

                    _ASSET_EXTS = {
                        ".svg",
                        ".png",
                        ".jpg",
                        ".jpeg",
                        ".gif",
                        ".webp",
                        ".ico",
                        ".pdf",
                        ".zip",
                        ".css",
                        ".js",
                    }
                    md_links = _re.findall(r"\[(?:[^\]]*)\]\((https?://[^)\s]+)\)", text)
                    for href in md_links:
                        full = href.split("#")[0].rstrip("/")
                        path_lower = urlparse(full).path.lower()
                        if any(path_lower.endswith(ext) for ext in _ASSET_EXTS):
                            continue
                        if urlparse(full).netloc == parsed_base.netloc and full not in visited:
                            new_links.append(full)
                    # Deduplicate while preserving order
                    new_links = list(dict.fromkeys(new_links))
                    logger.info(f"Discovered {len(new_links)} subpage links from Jina markdown for {page_url}")
            except Exception as exc:
                logger.warning(f"Jina fallback failed for {page_url}: {exc}")
                return None

        return {
            "id": page_url,
            "text": text,
            "new_links": new_links,
            "metadata": {
                "title": title,
                "url": page_url,
                "source_type": "web",
                "upload_source": "crawl",
            },
        }

    # Resolve data source once upfront; cache scalar fields before session closes
    _kb_id: int | None = None
    _ds_tenant_id: str | None = None
    async with async_session_factory() as db:
        result = await db.execute(select(DataSource).filter(DataSource.id == data_source_id))
        data_source = result.scalar_one_or_none()
        if data_source:
            _kb_id = data_source.knowledge_base_id
            _ds_tenant_id = str(data_source.tenant_id)
    if not data_source:
        logger.error(f"DataSource {data_source_id} not found — aborting crawl")
        return

    logger.info(
        f"Starting crawl: data_source={data_source_id} url={url} max_pages={max_pages} subpages={include_subpages}"
    )

    total_processed = 0
    batch: list[dict[str, Any]] = []

    async with httpx.AsyncClient(headers=headers) as client:
        while queue and (total_processed + len(batch)) < max_pages:
            # Build a round of concurrent fetches from the current queue
            remaining = max_pages - total_processed - len(batch)
            round_urls: list[str] = []
            while queue and len(round_urls) < CRAWL_CONCURRENCY and len(round_urls) < remaining:
                candidate = queue.pop(0)
                if candidate not in visited:
                    visited.add(candidate)
                    round_urls.append(candidate)

            if not round_urls:
                break

            results = await _asyncio.gather(*[fetch_page(client, u) for u in round_urls])

            for doc in results:
                if doc is None:
                    continue
                new_links = doc.pop("new_links", [])
                batch.append(doc)
                # Enqueue discovered links
                for link in new_links:
                    if link not in visited and len(queue) < max_pages * 2:
                        queue.append(link)

            # Flush batch to DB when it reaches CRAWL_BATCH_SIZE or queue is empty
            if len(batch) >= CRAWL_BATCH_SIZE or (not queue and batch):
                logger.info(f"Processing batch of {len(batch)} pages for data_source={data_source_id}")
                async with async_session_factory() as db:
                    result = await db.execute(select(DataSource).filter(DataSource.id == data_source_id))
                    ds = result.scalar_one_or_none()
                    if ds:
                        processor = DocumentProcessor(db)
                        res = await processor.process_documents(data_source=ds, documents=batch)
                        total_processed += res.get("documents_processed", len(batch))
                        logger.info(f"Batch done: {res}")
                batch = []

    # Final partial batch
    if batch:
        async with async_session_factory() as db:
            result = await db.execute(select(DataSource).filter(DataSource.id == data_source_id))
            ds = result.scalar_one_or_none()
            if ds:
                processor = DocumentProcessor(db)
                res = await processor.process_documents(data_source=ds, documents=batch)
                total_processed += res.get("documents_processed", len(batch))

    logger.info(f"Crawl complete for data_source={data_source_id}: {total_processed} pages processed (url={url})")

    # Auto-recompile wiki if this KB already has wiki articles
    if total_processed > 0 and _kb_id:
        from src.models.wiki_article import WikiArticle
        from src.tasks.knowledge_compiler_task import compile_single_knowledge_wiki

        async with async_session_factory() as db_check:
            wiki_check = await db_check.execute(
                select(WikiArticle.id).filter(WikiArticle.knowledge_base_id == _kb_id).limit(1)
            )
            if wiki_check.scalar_one_or_none():
                compile_single_knowledge_wiki.delay(_kb_id, _ds_tenant_id)
                logger.info(f"Triggered wiki recompile for KB {_kb_id}")

    return {"pages_processed": total_processed, "url": url}


async def _analyze_app_store_reviews(
    source_id: str,
    tenant_id: str,
    llm_provider: str,
    llm_model: str,
    llm_api_key: str,
    limit: int,
    only_unanalyzed: bool,
) -> None:
    import uuid

    from src.core.database import create_celery_async_session
    from src.services.agents.config import ModelConfig
    from src.services.app_store.review_analysis_service import ReviewAnalysisService

    async_session_factory = create_celery_async_session()
    async with async_session_factory() as db:
        analysis_service = ReviewAnalysisService(db)
        llm_config = ModelConfig(provider=llm_provider, model_name=llm_model, api_key=llm_api_key)
        analysis_service.initialize_llm_client(llm_config)
        result = await analysis_service.analyze_batch(
            app_store_source_id=uuid.UUID(source_id),
            limit=limit,
            only_unanalyzed=only_unanalyzed,
        )
        logger.info(f"App store review analysis done for source={source_id}: {result}")
