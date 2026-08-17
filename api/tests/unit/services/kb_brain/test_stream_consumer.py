"""
Unit tests for StreamConsumer.

Tests the filter logic, dedup, chunking, and consume() flow
without real Redis or embedding services.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.company_brain.ingestion.stream_consumer import StreamConsumer


def _mock_kb_session_cm():
    """Build a mock async-session context manager returning a fake KnowledgeBase.

    `_process_batch` unconditionally fetches the KnowledgeBase row via
    `create_celery_async_session()` before doing anything else, so every test that
    exercises `consume()` past the empty-stream short-circuit must mock this lookup.
    """
    mock_kb = MagicMock()
    mock_kb.embedding_provider = MagicMock(value="sentence_transformers")
    mock_kb.embedding_model = "all-MiniLM-L6-v2"
    mock_kb.get_embedding_config_decrypted.return_value = {}

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_kb
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__.return_value = mock_session
    mock_session_cm.__aexit__.return_value = None
    return mock_session_cm

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_doc(doc_id: str, content: str, *, is_bot: bool = False) -> dict:
    return {
        "id": doc_id,
        "external_id": doc_id,
        "content": content,
        "title": "Test",
        "metadata": {"is_bot": is_bot},
    }


SHORT_CONTENT = "hi"  # < 10 tokens (10 chars // 4 = 2 tokens)
NORMAL_CONTENT = "The quick brown fox jumps over the lazy dog. " * 5  # ~50 tokens
BOT_DOC = _make_doc("bot-1", NORMAL_CONTENT, is_bot=True)
NORMAL_DOC = _make_doc("real-1", NORMAL_CONTENT)


# ---------------------------------------------------------------------------
# _passes_filter
# ---------------------------------------------------------------------------


def test_passes_filter_normal_doc():
    consumer = StreamConsumer()
    assert consumer._passes_filter(NORMAL_DOC, min_tokens=10) is True


def test_passes_filter_short_content_rejected():
    consumer = StreamConsumer()
    doc = _make_doc("short-1", SHORT_CONTENT)
    assert consumer._passes_filter(doc, min_tokens=10) is False


def test_passes_filter_empty_content_rejected():
    consumer = StreamConsumer()
    doc = _make_doc("empty-1", "")
    assert consumer._passes_filter(doc, min_tokens=10) is False


def test_passes_filter_whitespace_only_rejected():
    consumer = StreamConsumer()
    doc = _make_doc("ws-1", "   \n\t  ")
    assert consumer._passes_filter(doc, min_tokens=10) is False


def test_passes_filter_bot_rejected():
    consumer = StreamConsumer()
    assert consumer._passes_filter(BOT_DOC, min_tokens=10) is False


def test_passes_filter_text_field_accepted():
    consumer = StreamConsumer()
    doc = {"id": "t1", "text": NORMAL_CONTENT, "metadata": {}}
    assert consumer._passes_filter(doc, min_tokens=10) is True


def test_passes_filter_min_tokens_zero_passes_any_nonempty():
    consumer = StreamConsumer()
    doc = _make_doc("x", "hi")
    assert consumer._passes_filter(doc, min_tokens=0) is True


# ---------------------------------------------------------------------------
# consume — empty stream
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_consume_empty_stream_returns_zeros():
    consumer = StreamConsumer()
    mock_redis = AsyncMock()
    mock_redis.xgroup_create = AsyncMock(side_effect=Exception("BUSYGROUP"))
    mock_redis.xreadgroup = AsyncMock(return_value=None)

    with (
        patch.object(consumer, "_get_redis", return_value=mock_redis),
        patch.object(consumer, "_batch_size", return_value=100),
        patch.object(consumer, "_min_tokens", return_value=10),
    ):
        result = await consumer.consume(kb_id=1, tenant_id="t-abc", source_type="slack")

    assert result == {"read": 0, "indexed": 0, "skipped": 0, "failed": 0}


@pytest.mark.asyncio
async def test_consume_uses_kb_scoped_stream_key():
    consumer = StreamConsumer()
    mock_redis = AsyncMock()
    mock_redis.xgroup_create = AsyncMock(side_effect=Exception("BUSYGROUP"))
    captured_calls = []

    async def fake_xreadgroup(**kwargs):
        captured_calls.append(kwargs)
        return None

    mock_redis.xreadgroup = fake_xreadgroup

    with (
        patch.object(consumer, "_get_redis", return_value=mock_redis),
        patch.object(consumer, "_batch_size", return_value=100),
        patch.object(consumer, "_min_tokens", return_value=10),
    ):
        await consumer.consume(kb_id=42, tenant_id="t-abc", source_type="github")

    assert len(captured_calls) == 1
    streams = captured_calls[0]["streams"]
    assert "kb_ingest:42:github" in streams


@pytest.mark.asyncio
async def test_consume_full_pipeline_mocked():
    """
    End-to-end consume() with one valid document.
    All external services (dedup, chunk, embed, search) are mocked.
    """
    consumer = StreamConsumer()

    # Build a fake Redis xreadgroup response:
    # Format: [(stream_key, [(msg_id, fields), ...])]
    doc = _make_doc("real-doc-1", "Alice pushed PR #847 to fix authentication bug")
    payload = json.dumps(doc)
    fake_messages = [(b"kb_ingest:1:slack", [(b"1-0", {b"payload": payload.encode()})])]

    mock_redis = AsyncMock()
    mock_redis.xgroup_create = AsyncMock(side_effect=Exception("BUSYGROUP"))
    mock_redis.xreadgroup = AsyncMock(return_value=fake_messages)
    mock_redis.xack = AsyncMock(return_value=1)

    # Mock the pipeline internals
    mock_dedup = AsyncMock()
    mock_dedup.filter_unseen = AsyncMock(return_value=["real-doc-1"])
    mock_dedup.mark_seen_batch = AsyncMock()

    mock_search = AsyncMock()
    mock_search.index_documents = AsyncMock(return_value={"indexed": 1, "failed": 0})

    fake_embedding = [[0.1, 0.2, 0.3]]

    # _process_batch uses local imports — patch at the actual source modules
    with (
        patch.object(consumer, "_get_redis", return_value=mock_redis),
        patch.object(consumer, "_batch_size", return_value=100),
        patch.object(consumer, "_min_tokens", return_value=10),
        patch(
            "src.services.company_brain.ingestion.stream_consumer.create_celery_async_session",
            return_value=lambda: _mock_kb_session_cm(),
        ),
        patch("src.services.company_brain.ingestion.dedup.get_dedup_backend", return_value=mock_dedup),
        patch("src.services.company_brain.search.factory.get_search_backend", return_value=mock_search),
        patch.object(consumer, "_embed_batch", AsyncMock(return_value=fake_embedding)),
    ):
        result = await consumer.consume(kb_id=1, tenant_id="t-abc", source_type="slack")

    assert result["read"] == 1
    assert result["indexed"] == 1
    assert result["skipped"] == 0
    assert result["failed"] == 0
    mock_redis.xack.assert_called_once()


@pytest.mark.asyncio
async def test_consume_skips_bot_doc():
    consumer = StreamConsumer()
    doc = _make_doc("bot-1", NORMAL_CONTENT, is_bot=True)
    payload = json.dumps(doc)
    fake_messages = [(b"kb_ingest:1:slack", [(b"1-0", {b"payload": payload.encode()})])]

    mock_redis = AsyncMock()
    mock_redis.xgroup_create = AsyncMock(side_effect=Exception("BUSYGROUP"))
    mock_redis.xreadgroup = AsyncMock(return_value=fake_messages)
    mock_redis.xack = AsyncMock()

    with (
        patch.object(consumer, "_get_redis", return_value=mock_redis),
        patch.object(consumer, "_batch_size", return_value=100),
        patch.object(consumer, "_min_tokens", return_value=10),
        patch(
            "src.services.company_brain.ingestion.stream_consumer.create_celery_async_session",
            return_value=lambda: _mock_kb_session_cm(),
        ),
    ):
        result = await consumer.consume(kb_id=1, tenant_id="t-abc", source_type="slack")

    # Bot doc is filtered — indexed=0, skipped=1
    assert result["read"] == 1
    assert result["indexed"] == 0
    assert result["skipped"] == 1


@pytest.mark.asyncio
async def test_consume_skips_already_seen_doc():
    consumer = StreamConsumer()
    doc = _make_doc("seen-doc-1", NORMAL_CONTENT)
    payload = json.dumps(doc)
    fake_messages = [(b"kb_ingest:1:slack", [(b"1-0", {b"payload": payload.encode()})])]

    mock_redis = AsyncMock()
    mock_redis.xgroup_create = AsyncMock(side_effect=Exception("BUSYGROUP"))
    mock_redis.xreadgroup = AsyncMock(return_value=fake_messages)
    mock_redis.xack = AsyncMock()

    # Dedup returns empty list → doc already seen
    mock_dedup = AsyncMock()
    mock_dedup.filter_unseen = AsyncMock(return_value=[])
    mock_dedup.mark_seen_batch = AsyncMock()

    with (
        patch.object(consumer, "_get_redis", return_value=mock_redis),
        patch.object(consumer, "_batch_size", return_value=100),
        patch.object(consumer, "_min_tokens", return_value=10),
        patch(
            "src.services.company_brain.ingestion.stream_consumer.create_celery_async_session",
            return_value=lambda: _mock_kb_session_cm(),
        ),
        patch("src.services.company_brain.ingestion.dedup.get_dedup_backend", return_value=mock_dedup),
        patch("src.services.company_brain.search.factory.get_search_backend", return_value=AsyncMock()),
    ):
        result = await consumer.consume(kb_id=1, tenant_id="t-abc", source_type="slack")

    assert result["indexed"] == 0
    assert result["skipped"] >= 1  # dedup skip


@pytest.mark.asyncio
async def test_consume_handles_malformed_message():
    """Malformed message should be skipped without crashing."""
    consumer = StreamConsumer()
    fake_messages = [(b"kb_ingest:1:slack", [(b"bad-0", {b"payload": b"NOT JSON!!!"})])]

    mock_redis = AsyncMock()
    mock_redis.xgroup_create = AsyncMock(side_effect=Exception("BUSYGROUP"))
    mock_redis.xreadgroup = AsyncMock(return_value=fake_messages)
    mock_redis.xack = AsyncMock()

    with (
        patch.object(consumer, "_get_redis", return_value=mock_redis),
        patch.object(consumer, "_batch_size", return_value=100),
        patch.object(consumer, "_min_tokens", return_value=10),
    ):
        result = await consumer.consume(kb_id=1, tenant_id="t-abc", source_type="slack")

    # Malformed message skipped, no crash
    assert result["read"] == 0
    assert result["indexed"] == 0
