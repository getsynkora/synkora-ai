# On-Demand Context File Loading Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-file `load_mode` flag so context files/skills can be injected eagerly into the system prompt (`always`) or loaded on-demand by the LLM via a tool call (`on_demand`), moving file content out of the DB and into S3 + Redis cache.

**Architecture:** `AgentContextFile` gains `load_mode` + `description` columns; `extracted_text` is dropped. The prompt builder injects a manifest (names + descriptions) for on-demand files instead of content. A new `internal_load_context_file` tool lets the LLM fetch content from S3 via Redis cache. Content is cached per-file with 24h TTL, invalidated only on delete.

**Tech Stack:** Python/FastAPI, SQLAlchemy async, Alembic, Redis (via `AgentCacheService`), boto3/S3, React/TypeScript

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `api/src/models/agent_context_file.py` | Modify | Add `load_mode`, `description`; remove `extracted_text` |
| `api/migrations/versions/20260701_0001_context_file_load_mode.py` | Create | Migration: add columns, data backfill, drop `extracted_text` |
| `api/src/services/cache/agent_cache_service.py` | Modify | Add per-file content cache get/set/invalidate |
| `api/src/services/agents/context_file_processor.py` | Modify | Write description to DB; cache content in Redis; no DB text storage |
| `api/src/services/agents/prompt_builder.py` | Modify | Split always/on_demand; inject manifest for on_demand |
| `api/src/services/agents/internal_tools/context_file_tools.py` | Create | `internal_load_context_file` tool function |
| `api/src/services/agents/tool_registrations/context_file_tools_registry.py` | Create | Register the tool with ADKToolRegistry |
| `api/src/services/agents/tool_filter.py` | Modify | Add `internal_load_context_file` to `ALWAYS_INCLUDE_TOOLS` |
| `api/src/services/agents/adk_tools.py` | Modify | Call `register_context_file_tools` in `_register_all_tools` |
| `api/src/controllers/agents/context_files.py` | Modify | PATCH endpoint for `load_mode`/`description`; include new fields in list response |
| `web/components/agents/ContextFilesUpload.tsx` | Modify | Per-file load_mode toggle + description field |
| `api/tests/unit/services/test_context_file_load_mode.py` | Create | Unit tests for cache methods, prompt builder manifest, tool |

---

### Task 1: DB Migration

**Files:**
- Create: `api/migrations/versions/20260701_0001_context_file_load_mode.py`

- [ ] **Step 1: Generate migration skeleton**

```bash
cd api && alembic revision -m "add_context_file_load_mode_description_drop_extracted_text"
```

Rename the generated file to `migrations/versions/20260701_0001_context_file_load_mode.py`.

- [ ] **Step 2: Write migration content**

Replace the generated file content with:

```python
"""add context file load_mode, description, drop extracted_text

Revision ID: 20260701_0001
"""
from alembic import op
import sqlalchemy as sa

# fill in revision/down_revision from the generated file header
revision = "20260701_0001"
# down_revision = "<whatever alembic generated>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add new columns
    op.add_column(
        "agent_context_files",
        sa.Column(
            "load_mode",
            sa.String(20),
            nullable=False,
            server_default="always",
            comment="always | on_demand",
        ),
    )
    op.add_column(
        "agent_context_files",
        sa.Column(
            "description",
            sa.String(500),
            nullable=True,
            comment="Short description shown to LLM in manifest",
        ),
    )

    # 2. Backfill description from first 200 chars of extracted_text
    op.execute(
        """
        UPDATE agent_context_files
        SET description = LEFT(extracted_text, 200)
        WHERE extracted_text IS NOT NULL AND description IS NULL
        """
    )

    # 3. Drop extracted_text
    op.drop_column("agent_context_files", "extracted_text")


def downgrade() -> None:
    op.add_column(
        "agent_context_files",
        sa.Column("extracted_text", sa.Text(), nullable=True),
    )
    op.drop_column("agent_context_files", "description")
    op.drop_column("agent_context_files", "load_mode")
```

- [ ] **Step 3: Run migration**

```bash
cd api && alembic upgrade head
```

Expected output: `Running upgrade ... -> 20260701_0001, add context file load_mode...`

- [ ] **Step 4: Verify schema**

```bash
cd api && python -c "
from src.core.database import get_sync_engine
from sqlalchemy import inspect
eng = get_sync_engine()
cols = {c['name'] for c in inspect(eng).get_columns('agent_context_files')}
assert 'load_mode' in cols, 'load_mode missing'
assert 'description' in cols, 'description missing'
assert 'extracted_text' not in cols, 'extracted_text still exists'
print('Schema OK')
"
```

Expected: `Schema OK`

- [ ] **Step 5: Commit**

```bash
git add api/migrations/versions/20260701_0001_context_file_load_mode.py
git commit -m "feat: migration add load_mode/description, drop extracted_text from context files"
```

---

### Task 2: Update Model

**Files:**
- Modify: `api/src/models/agent_context_file.py`

- [ ] **Step 1: Update the model**

Replace the `extracted_text` column and add `load_mode` + `description`:

```python
# Remove this line:
#   extracted_text = Column(Text, nullable=True, comment="Extracted text content from the file")

# Add these two lines in its place:
load_mode = Column(
    String(20),
    nullable=False,
    default="always",
    comment="always | on_demand",
)

description = Column(
    String(500),
    nullable=True,
    comment="Short description shown to LLM in on-demand manifest (auto-generated, user-overridable)",
)
```

Also update the docstring — replace the `extracted_text` attribute line with:

```
        load_mode: "always" (inject into system prompt) or "on_demand" (LLM loads via tool)
        description: Short description shown in manifest for on_demand files
```

Remove `extracted_text` from any other references in the file (none exist beyond the column definition and docstring).

- [ ] **Step 2: Verify import**

```bash
cd api && python -c "from src.models.agent_context_file import AgentContextFile; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add api/src/models/agent_context_file.py
git commit -m "feat: update AgentContextFile model with load_mode and description"
```

---

### Task 3: Per-File Content Cache

**Files:**
- Modify: `api/src/services/cache/agent_cache_service.py`
- Test: `api/tests/unit/services/test_context_file_load_mode.py`

- [ ] **Step 1: Write failing tests**

Create `api/tests/unit/services/test_context_file_load_mode.py`:

```python
"""Tests for per-file context content cache methods."""
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.services.cache.agent_cache_service import AgentCacheService


@pytest.fixture
def cache():
    svc = AgentCacheService()
    return svc


@pytest.mark.asyncio
async def test_set_and_get_context_file_content(cache):
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=b'"hello world"')
    redis_mock.setex = AsyncMock()

    with patch.object(cache, "_get_redis", return_value=redis_mock):
        await cache.set_context_file_content("file-123", "hello world")
        result = await cache.get_context_file_content("file-123")

    redis_mock.setex.assert_called_once()
    assert result == "hello world"


@pytest.mark.asyncio
async def test_get_context_file_content_miss(cache):
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)

    with patch.object(cache, "_get_redis", return_value=redis_mock):
        result = await cache.get_context_file_content("file-999")

    assert result is None


@pytest.mark.asyncio
async def test_invalidate_context_file_content(cache):
    redis_mock = AsyncMock()
    redis_mock.delete = AsyncMock()

    with patch.object(cache, "_get_redis", return_value=redis_mock):
        with patch.object(cache, "_publish_invalidation", new=AsyncMock()):
            await cache.invalidate_context_file_content("file-123")

    redis_mock.delete.assert_called_once()
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd api && pytest tests/unit/services/test_context_file_load_mode.py -v
```

Expected: `FAILED` (methods don't exist yet).

- [ ] **Step 3: Add cache methods**

In `api/src/services/cache/agent_cache_service.py`, add after the existing `set_context_files` method (around line 345):

```python
CONTENT_CACHE_TTL = 86400  # 24 hours — content never changes after upload

async def get_context_file_content(self, file_id: str) -> str | None:
    """Get cached extracted text for a single context file."""
    redis = self._get_redis()
    if not redis:
        return None
    try:
        key = self._build_key("context_file_content", file_id)
        cached = await redis.get(key)
        if cached:
            logger.info(f"Cache HIT: context_file_content:{file_id}")
            return json.loads(cached)
        return None
    except Exception as e:
        logger.error(f"Error getting context file content cache: {e}")
        return None

async def set_context_file_content(self, file_id: str, content: str) -> bool:
    """Cache extracted text for a single context file (24h TTL)."""
    redis = self._get_redis()
    if not redis:
        return False
    try:
        key = self._build_key("context_file_content", file_id)
        await redis.setex(key, timedelta(seconds=self.CONTENT_CACHE_TTL), json.dumps(content))
        logger.info(f"Cached context_file_content:{file_id} (TTL: {self.CONTENT_CACHE_TTL}s)")
        return True
    except Exception as e:
        logger.error(f"Error caching context file content: {e}")
        return False

async def invalidate_context_file_content(self, file_id: str) -> None:
    """Delete per-file content cache on file deletion."""
    redis = self._get_redis()
    if not redis:
        return
    try:
        key = self._build_key("context_file_content", file_id)
        await redis.delete(key)
        logger.info(f"Invalidated context_file_content:{file_id}")
    except Exception as e:
        logger.error(f"Error invalidating context file content: {e}")
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd api && pytest tests/unit/services/test_context_file_load_mode.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add api/src/services/cache/agent_cache_service.py \
        api/tests/unit/services/test_context_file_load_mode.py
git commit -m "feat: add per-file context content cache methods (24h TTL)"
```

---

### Task 4: Update Context File Processor

**Files:**
- Modify: `api/src/services/agents/context_file_processor.py`

- [ ] **Step 1: Write failing test**

Add to `api/tests/unit/services/test_context_file_load_mode.py`:

```python
@pytest.mark.asyncio
async def test_process_file_sets_description_not_extracted_text():
    """Processor should set description from first 200 chars, not extracted_text."""
    from unittest.mock import AsyncMock, MagicMock, patch
    import io
    from src.services.agents.context_file_processor import AgentContextFileProcessor

    db_mock = AsyncMock()
    db_mock.execute = AsyncMock(return_value=MagicMock(one=lambda: (0, 0), scalar=lambda: 0))
    db_mock.flush = AsyncMock()
    db_mock.commit = AsyncMock()
    db_mock.add = MagicMock()
    db_mock.rollback = AsyncMock()

    agent_mock = MagicMock()
    agent_mock.id = "agent-1"
    agent_mock.tenant_id = "tenant-1"
    agent_mock.agent_name = "test-agent"

    processor = AgentContextFileProcessor(db_mock)

    long_text = "A" * 300
    file_obj = io.BytesIO(long_text.encode())

    with patch.object(processor.s3_storage, "upload_file_content", new=AsyncMock()):
        with patch.object(processor.s3_storage, "bucket_name", "test-bucket"):
            with patch("src.services.cache.agent_cache_service.get_agent_cache") as mock_cache_factory:
                mock_cache = AsyncMock()
                mock_cache.set_context_file_content = AsyncMock()
                mock_cache_factory.return_value = mock_cache

                context_file = await processor.process_file(
                    agent=agent_mock,
                    file=file_obj,
                    filename="test.md",
                    content_type="text/markdown",
                )

    # description is first 200 chars
    assert context_file.description == "A" * 200
    # extracted_text no longer exists on model
    assert not hasattr(context_file, "extracted_text")
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd api && pytest tests/unit/services/test_context_file_load_mode.py::test_process_file_sets_description_not_extracted_text -v
```

Expected: `FAILED`

- [ ] **Step 3: Update `context_file_processor.py`**

In `process_file` method, replace the extraction block (around line 194-207) that sets `context_file.extracted_text` with:

```python
# Extract text to generate description and prime the cache
try:
    logger.info(f"Extracting text from file {filename}")
    extracted_text = await self._extract_text(file_content, content_type, filename)

    # Store first 200 chars as description (never in DB)
    context_file.description = extracted_text[:200].strip() if extracted_text else None
    context_file.extraction_status = "COMPLETED"
    logger.info(f"Extracted {len(extracted_text)} chars from {filename}")

    # Prime the per-file content cache so first access is instant
    try:
        from src.services.cache import get_agent_cache
        cache = get_agent_cache()
        await cache.set_context_file_content(str(context_file.id), extracted_text)
    except Exception as cache_err:
        logger.warning(f"Failed to prime content cache for {filename}: {cache_err}")

except Exception as e:
    logger.error(f"Error extracting text from {filename}: {e}")
    context_file.extraction_status = "FAILED"
    context_file.extraction_error = str(e)
```

Also remove the `get_context_files_text` method at the bottom of the file (it uses `extracted_text` and is no longer needed).

- [ ] **Step 4: Run test to confirm it passes**

```bash
cd api && pytest tests/unit/services/test_context_file_load_mode.py::test_process_file_sets_description_not_extracted_text -v
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add api/src/services/agents/context_file_processor.py \
        api/tests/unit/services/test_context_file_load_mode.py
git commit -m "feat: processor writes description to DB, caches content in Redis, no extracted_text in DB"
```

---

### Task 5: Update Prompt Builder

**Files:**
- Modify: `api/src/services/agents/prompt_builder.py`

- [ ] **Step 1: Write failing tests**

Add to `api/tests/unit/services/test_context_file_load_mode.py`:

```python
def test_format_manifest_for_on_demand_files():
    """On-demand files should produce a manifest block, not full content."""
    from src.services.agents.prompt_builder import SystemPromptBuilder

    on_demand_files = [
        {"file_id": "f1", "filename": "skill-seo.md", "description": "SEO writing tips", "load_mode": "on_demand"},
        {"file_id": "f2", "filename": "skill-code.md", "description": "Code review checklist", "load_mode": "on_demand"},
    ]
    always_files = [
        {"file_id": "f3", "filename": "guidelines.txt", "description": "Company guidelines", "load_mode": "always",
         "extracted_content": "Always follow company policy.\n"},
    ]

    manifest = SystemPromptBuilder._format_on_demand_manifest(on_demand_files)
    assert "skill-seo.md" in manifest
    assert "SEO writing tips" in manifest
    assert "skill-code.md" in manifest
    assert "load_context_file" in manifest
    # Should NOT contain full content
    assert "Always follow company policy" not in manifest


def test_format_on_demand_manifest_empty():
    """Empty on-demand list returns empty string."""
    from src.services.agents.prompt_builder import SystemPromptBuilder

    result = SystemPromptBuilder._format_on_demand_manifest([])
    assert result == ""
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd api && pytest tests/unit/services/test_context_file_load_mode.py::test_format_manifest_for_on_demand_files tests/unit/services/test_context_file_load_mode.py::test_format_on_demand_manifest_empty -v
```

Expected: `FAILED`

- [ ] **Step 3: Rewrite `_get_context_files_data` to return manifest shape**

In `prompt_builder.py`, update `_get_context_files_data` to load from the new schema.

Replace the method with:

```python
async def _get_context_files_data(self, agent: Agent) -> list[dict]:
    """Load context file metadata (manifest), preferring cache over DB."""
    from src.services.cache import get_agent_cache
    cache = get_agent_cache()

    try:
        cached_data = await cache.get_context_files(str(agent.id))
        if cached_data:
            logger.info(f"Context files manifest cache HIT for agent {agent.id}")
            return cached_data
    except Exception as e:
        logger.warning(f"Context manifest cache read failed: {e}")

    from src.core.database import get_async_session_factory
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(AgentContextFile)
            .filter(
                AgentContextFile.agent_id == agent.id,
                AgentContextFile.extraction_status == "COMPLETED",
            )
            .order_by(AgentContextFile.display_order)
        )
        context_files = list(result.scalars().all())

    if not context_files:
        return []

    manifest_data = [
        {
            "file_id": str(cf.id),
            "filename": cf.filename,
            "description": cf.description or "",
            "load_mode": cf.load_mode or "always",
            "s3_key": cf.s3_key,
            "s3_bucket": cf.s3_bucket,
            "file_type": cf.file_type,
        }
        for cf in context_files
    ]

    try:
        await cache.set_context_files(str(agent.id), manifest_data, ttl=300)
    except Exception as e:
        logger.warning(f"Failed to cache context files manifest: {e}")

    return manifest_data
```

- [ ] **Step 4: Add `_format_on_demand_manifest` static method**

Add after `_format_context_from_data` in `SystemPromptBuilder`:

```python
@staticmethod
def _format_on_demand_manifest(on_demand_files: list[dict]) -> str:
    """Format manifest block listing on-demand files for LLM."""
    if not on_demand_files:
        return ""

    lines = [
        "=" * 60,
        "AVAILABLE CONTEXT FILES (load on demand)",
        "=" * 60,
        "",
        "The following files are available. Use load_context_file(filename)",
        "to load the content of any file you need for the current task.",
        "",
    ]
    for f in on_demand_files:
        desc = f.get("description", "").strip()
        desc_part = f": {desc}" if desc else ""
        lines.append(f"  - {f['filename']}{desc_part}")

    lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 5: Update `_build_context_section` to split always vs on_demand**

Replace `_build_context_section` with:

```python
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
    all_files = await self._get_context_files_data(agent)
    if not all_files:
        return ""

    always_files = [f for f in all_files if f.get("load_mode", "always") == "always"]
    on_demand_files = [f for f in all_files if f.get("load_mode") == "on_demand"]

    parts = []

    # Eager files — fetch content and inject
    if always_files:
        always_with_content = await self._fetch_content_for_files(always_files)
        eager_text = self._format_context_from_data(
            always_with_content,
            max_context_length=max_context_length,
            context_mode=context_mode,
            context_query=context_query,
            full_context_threshold=full_context_threshold,
            preview_chars=preview_chars,
            max_preview_files=max_preview_files,
        )
        if eager_text:
            parts.append(eager_text)

    # On-demand files — inject manifest only
    manifest = self._format_on_demand_manifest(on_demand_files)
    if manifest:
        parts.append(manifest)

    return "\n\n".join(parts)
```

- [ ] **Step 6: Add `_fetch_content_for_files` helper**

Add this private method to `SystemPromptBuilder`:

```python
async def _fetch_content_for_files(self, files: list[dict]) -> list[dict]:
    """
    Fetch extracted text for always-inject files.
    Checks Redis cache first; falls back to S3 download + extraction.
    """
    from src.services.cache import get_agent_cache
    from src.services.storage.s3_storage import S3StorageService
    from src.services.agents.context_file_processor import AgentContextFileProcessor

    cache = get_agent_cache()
    s3 = S3StorageService()
    result = []

    for f in files:
        file_id = f["file_id"]
        content: str | None = None

        # 1. Redis cache
        try:
            content = await cache.get_context_file_content(file_id)
        except Exception as e:
            logger.warning(f"Cache read error for file {file_id}: {e}")

        # 2. S3 fallback
        if content is None:
            try:
                s3_url = f"s3://{f['s3_bucket']}/{f['s3_key']}"
                raw = await s3.download_file_content(s3_url)
                # Reuse extraction logic from processor
                processor = AgentContextFileProcessor(self.db)
                content = await processor._extract_text(raw, f["file_type"], f["filename"])
                # Re-prime cache
                await cache.set_context_file_content(file_id, content)
            except Exception as e:
                logger.error(f"Failed to fetch content for {f['filename']} from S3: {e}")
                content = f"[Content unavailable for {f['filename']}]"

        result.append({**f, "extracted_text": content})

    return result
```

- [ ] **Step 7: Run tests to confirm they pass**

```bash
cd api && pytest tests/unit/services/test_context_file_load_mode.py -v
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add api/src/services/agents/prompt_builder.py \
        api/tests/unit/services/test_context_file_load_mode.py
git commit -m "feat: prompt builder splits always/on_demand files, injects manifest for on_demand"
```

---

### Task 6: `internal_load_context_file` Tool

**Files:**
- Create: `api/src/services/agents/internal_tools/context_file_tools.py`
- Create: `api/src/services/agents/tool_registrations/context_file_tools_registry.py`

- [ ] **Step 1: Write failing test**

Add to `api/tests/unit/services/test_context_file_load_mode.py`:

```python
@pytest.mark.asyncio
async def test_load_context_file_tool_cache_hit():
    """Tool returns cached content without hitting S3."""
    from src.services.agents.internal_tools.context_file_tools import internal_load_context_file

    runtime_context = MagicMock()
    runtime_context.agent_id = "agent-abc"
    runtime_context.tenant_id = "tenant-xyz"

    mock_cache = AsyncMock()
    mock_cache.get_context_file_content = AsyncMock(return_value="Cached skill content here")

    mock_db_result = MagicMock()
    mock_db_row = MagicMock()
    mock_db_row.id = "file-999"
    mock_db_row.s3_key = "agent-context/agent-abc/context-files/file-999.md"
    mock_db_row.s3_bucket = "test-bucket"
    mock_db_row.file_type = "text/markdown"
    mock_db_result.scalar_one_or_none = MagicMock(return_value=mock_db_row)

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_db_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    mock_session_factory = MagicMock(return_value=mock_session)

    config = {"_runtime_context": runtime_context}

    with patch("src.services.agents.internal_tools.context_file_tools.get_agent_cache", return_value=mock_cache):
        with patch("src.services.agents.internal_tools.context_file_tools.get_async_session_factory", return_value=mock_session_factory):
            result = await internal_load_context_file(
                filename="skill-seo.md",
                config=config,
            )

    assert result["success"] is True
    assert result["content"] == "Cached skill content here"
    assert result["filename"] == "skill-seo.md"


@pytest.mark.asyncio
async def test_load_context_file_tool_not_found():
    """Tool returns error when file not found for this agent."""
    from src.services.agents.internal_tools.context_file_tools import internal_load_context_file

    runtime_context = MagicMock()
    runtime_context.agent_id = "agent-abc"
    runtime_context.tenant_id = "tenant-xyz"

    mock_db_result = MagicMock()
    mock_db_result.scalar_one_or_none = MagicMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_db_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    config = {"_runtime_context": MagicMock(agent_id="agent-abc", tenant_id="tenant-xyz")}

    with patch("src.services.agents.internal_tools.context_file_tools.get_agent_cache", return_value=AsyncMock(get_context_file_content=AsyncMock(return_value=None))):
        with patch("src.services.agents.internal_tools.context_file_tools.get_async_session_factory", return_value=MagicMock(return_value=mock_session)):
            result = await internal_load_context_file(filename="missing.md", config=config)

    assert result["success"] is False
    assert "not found" in result["error"].lower()
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd api && pytest tests/unit/services/test_context_file_load_mode.py::test_load_context_file_tool_cache_hit tests/unit/services/test_context_file_load_mode.py::test_load_context_file_tool_not_found -v
```

Expected: `FAILED` (module doesn't exist).

- [ ] **Step 3: Create tool file**

Create `api/src/services/agents/internal_tools/context_file_tools.py`:

```python
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

        from src.services.cache import get_agent_cache
        from src.core.database import get_async_session_factory
        from src.models.agent_context_file import AgentContextFile
        from src.models.agent import Agent
        from sqlalchemy import select

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
                from src.services.storage.s3_storage import S3StorageService
                from src.services.agents.context_file_processor import AgentContextFileProcessor

                s3 = S3StorageService()
                s3_url = f"s3://{context_file.s3_bucket}/{context_file.s3_key}"
                raw = await s3.download_file_content(s3_url)
                # Use a minimal db mock since we only need _extract_text (no DB writes)
                processor = AgentContextFileProcessor(db=None)
                content = await processor._extract_text(raw, context_file.file_type, filename)

                # Re-prime cache
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
```

- [ ] **Step 4: Create registry file**

Create `api/src/services/agents/tool_registrations/context_file_tools_registry.py`:

```python
"""
Context File Tools Registry

Registers the internal_load_context_file tool so agents can load
on-demand context files at runtime.
"""

import logging

logger = logging.getLogger(__name__)


def register_context_file_tools(registry) -> None:
    """Register context file loading tool with ADKToolRegistry."""
    from src.services.agents.internal_tools.context_file_tools import internal_load_context_file

    async def _wrapper(config=None, **kwargs):
        return await internal_load_context_file(
            filename=kwargs.get("filename", ""),
            config=config,
        )

    registry.register_tool(
        name="internal_load_context_file",
        description=(
            "Load the full content of a context file listed under AVAILABLE CONTEXT FILES. "
            "Use this when you need the content of an on-demand file to complete the current task. "
            "Pass the exact filename as shown in the list."
        ),
        parameters={
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Exact filename from the AVAILABLE CONTEXT FILES list",
                }
            },
            "required": ["filename"],
        },
        function=_wrapper,
    )

    logger.info("Registered internal_load_context_file tool")
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
cd api && pytest tests/unit/services/test_context_file_load_mode.py::test_load_context_file_tool_cache_hit tests/unit/services/test_context_file_load_mode.py::test_load_context_file_tool_not_found -v
```

Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add api/src/services/agents/internal_tools/context_file_tools.py \
        api/src/services/agents/tool_registrations/context_file_tools_registry.py \
        api/tests/unit/services/test_context_file_load_mode.py
git commit -m "feat: add internal_load_context_file tool and registry"
```

---

### Task 7: Wire Tool into ADK + Tool Filter

**Files:**
- Modify: `api/src/services/agents/tool_filter.py`
- Modify: `api/src/services/agents/adk_tools.py`

- [ ] **Step 1: Add to `ALWAYS_INCLUDE_TOOLS`**

In `api/src/services/agents/tool_filter.py`, add to the `ALWAYS_INCLUDE_TOOLS` list:

```python
ALWAYS_INCLUDE_TOOLS = [
    "internal_search_available_tools",
    "internal_list_tool_categories",
    "internal_load_context_file",   # <-- add this line
    # Multi-agent orchestration tools ...
    "spawn_agent",
    "check_task",
    "list_background_tasks",
    # Human handoff ...
    "handoff_to_human",
]
```

- [ ] **Step 2: Register in `adk_tools.py`**

In `api/src/services/agents/adk_tools.py`, find the Tool Discovery registration block (around line 241):

```python
        # Tool Discovery tools - meta-tools for on-demand tool loading (always included)
        from src.services.agents.tool_registrations.tool_discovery_registry import (
            register_tool_discovery_tools,
        )

        register_tool_discovery_tools(self)
```

Add immediately after it:

```python
        # Context File tools - allows LLM to load on-demand context files
        from src.services.agents.tool_registrations.context_file_tools_registry import (
            register_context_file_tools,
        )

        register_context_file_tools(self)
```

- [ ] **Step 3: Verify registration**

```bash
cd api && python -c "
from src.services.agents.adk_tools import get_tool_registry
registry = get_tool_registry()
names = {t['name'] for t in registry.list_tools()}
assert 'internal_load_context_file' in names, 'tool not registered'
print('Tool registered OK')
"
```

Expected: `Tool registered OK`

- [ ] **Step 4: Commit**

```bash
git add api/src/services/agents/tool_filter.py \
        api/src/services/agents/adk_tools.py
git commit -m "feat: register internal_load_context_file as always-included tool"
```

---

### Task 8: API Endpoint + Cache Invalidation on Delete

**Files:**
- Modify: `api/src/controllers/agents/context_files.py`

- [ ] **Step 1: Expose `load_mode` and `description` in list response**

In `list_context_files` (around line 188), update the `files_list.append(...)` dict to include the new fields:

```python
files_list.append(
    {
        "id": str(f.id),
        "filename": f.filename,
        "file_type": f.file_type,
        "file_size": f.file_size,
        "extraction_status": f.extraction_status,
        "extraction_error": f.extraction_error,
        "display_order": f.display_order,
        "load_mode": f.load_mode,           # <-- add
        "description": f.description,        # <-- add
        "created_at": f.created_at.isoformat(),
        "updated_at": f.updated_at.isoformat(),
    }
)
```

- [ ] **Step 2: Add PATCH endpoint for `load_mode` / `description`**

Add after the `list_context_files` endpoint:

```python
from pydantic import BaseModel as PydanticBaseModel


class UpdateContextFileRequest(PydanticBaseModel):
    load_mode: str | None = None   # "always" | "on_demand"
    description: str | None = None


@agents_context_files_router.patch("/context-files/{file_id}", response_model=AgentResponse)
async def update_context_file(
    file_id: uuid.UUID,
    request: UpdateContextFileRequest,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Update load_mode or description for a context file."""
    from src.models.agent_context_file import AgentContextFile
    from src.services.cache import get_agent_cache

    result = await db.execute(
        select(AgentContextFile).filter(
            AgentContextFile.id == file_id,
            AgentContextFile.tenant_id == tenant_id,
        )
    )
    context_file = result.scalar_one_or_none()
    if not context_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    if request.load_mode is not None:
        if request.load_mode not in ("always", "on_demand"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="load_mode must be 'always' or 'on_demand'")
        context_file.load_mode = request.load_mode

    if request.description is not None:
        context_file.description = request.description[:500]

    await db.commit()

    # Invalidate manifest cache so prompt builder picks up the change
    cache = get_agent_cache()
    await cache.invalidate_agent(agent_id=str(context_file.agent_id))

    return AgentResponse(
        success=True,
        message="Context file updated",
        data={"id": str(context_file.id), "load_mode": context_file.load_mode, "description": context_file.description},
    )
```

- [ ] **Step 3: Invalidate content cache on file delete**

Find the existing `delete_context_file` endpoint in `context_files.py` (it calls `processor.delete_file`). After the delete call, add cache invalidation:

```python
# Invalidate per-file content cache
cache = get_agent_cache()
await cache.invalidate_context_file_content(str(file_id))
await cache.invalidate_agent(agent_id=str(context_file.agent_id))
```

(Import `get_agent_cache` at the top of the endpoint function.)

- [ ] **Step 4: Verify server starts**

```bash
cd api && uvicorn src.app:app --host 0.0.0.0 --port 5001 --reload &
sleep 3
curl -s http://localhost:5001/health | python -m json.tool
kill %1
```

Expected: health check returns `{"status": "ok"}` (or similar).

- [ ] **Step 5: Commit**

```bash
git add api/src/controllers/agents/context_files.py
git commit -m "feat: expose load_mode/description in list response; add PATCH endpoint; invalidate caches on delete"
```

---

### Task 9: Web UI — Load Mode Toggle + Description Field

**Files:**
- Modify: `web/components/agents/ContextFilesUpload.tsx`

- [ ] **Step 1: Update `ContextFile` interface**

In the `ContextFile` interface (around line 18), add the two new fields:

```typescript
interface ContextFile {
  id: string
  filename: string
  file_type: string
  file_size: number
  extraction_status: 'PENDING' | 'COMPLETED' | 'FAILED'
  extraction_error?: string
  display_order: number
  load_mode: 'always' | 'on_demand'   // <-- add
  description?: string                  // <-- add
  created_at: string
}
```

- [ ] **Step 2: Add `handleUpdateFile` function**

After `handleDownload` (around line 274), add:

```typescript
const handleUpdateFile = async (fileId: string, updates: { load_mode?: string; description?: string }) => {
  try {
    await apiClient.request('PATCH', `/api/v1/agents/context-files/${fileId}`, updates)
    await loadExistingFiles()
  } catch (error) {
    console.error('Failed to update file:', error)
    toast.error('Failed to update file settings')
  }
}
```

- [ ] **Step 3: Add per-file toggle and description in the file list**

In the existing files list (inside the `.map((file) => ...)` block, after the `getExtractionStatusBadge` line and before the action buttons), add:

```tsx
{/* Load mode toggle */}
{file.extraction_status === 'COMPLETED' && (
  <div className="flex items-center gap-2 mt-2">
    <button
      onClick={() => handleUpdateFile(file.id, {
        load_mode: file.load_mode === 'always' ? 'on_demand' : 'always'
      })}
      className={`inline-flex items-center gap-1.5 px-2 py-1 text-xs font-medium rounded-full border transition-colors ${
        file.load_mode === 'on_demand'
          ? 'bg-purple-50 text-purple-700 border-purple-200 hover:bg-purple-100'
          : 'bg-blue-50 text-blue-700 border-blue-200 hover:bg-blue-100'
      }`}
      title={file.load_mode === 'always' ? 'Click to switch to on-demand loading' : 'Click to always inject into prompt'}
    >
      {file.load_mode === 'on_demand' ? 'On demand' : 'Always inject'}
    </button>
    {file.description && (
      <span className="text-xs text-gray-400 truncate max-w-[160px]" title={file.description}>
        {file.description}
      </span>
    )}
  </div>
)}
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd web && pnpm type-check 2>&1 | head -30
```

Expected: no errors related to `ContextFile` or `ContextFilesUpload`.

- [ ] **Step 5: Commit**

```bash
git add web/components/agents/ContextFilesUpload.tsx
git commit -m "feat: add load_mode toggle and description display to context files UI"
```

---

### Task 10: Run Full Test Suite

- [ ] **Step 1: Run all new tests**

```bash
cd api && pytest tests/unit/services/test_context_file_load_mode.py -v
```

Expected: all tests pass.

- [ ] **Step 2: Run broader unit suite to check for regressions**

```bash
cd api && pytest tests/unit/ -v --tb=short 2>&1 | tail -30
```

Expected: no new failures.

- [ ] **Step 3: Final commit**

```bash
git add .
git commit -m "feat: on-demand context file loading — complete implementation"
```
