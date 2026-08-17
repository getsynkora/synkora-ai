"""Unit tests for company_brain_tasks.py."""

from unittest.mock import AsyncMock, MagicMock, patch

from src.tasks.company_brain_tasks import company_brain_consume_active_streams_task


def _mock_source(kb_id=1, tenant_id="tenant-1", source_type="slack"):
    source = MagicMock()
    source.id = 1
    source.tenant_id = tenant_id
    source.knowledge_base_id = kb_id
    source.type = MagicMock(value=source_type)
    return source


class TestConsumeActiveStreamsThroughput:
    def test_drains_multiple_batches_per_source_until_empty(self):
        """Regression guard: must call consume() repeatedly per source, not just once."""
        source = _mock_source()

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [source]
        mock_db.close = MagicMock()

        # Two non-empty batches, then an empty batch signals "drained"
        consume_results = [
            {"read": 100, "indexed": 90, "skipped": 5, "failed": 5},
            {"read": 40, "indexed": 40, "skipped": 0, "failed": 0},
            {"read": 0, "indexed": 0, "skipped": 0, "failed": 0},
        ]

        mock_consumer = MagicMock()
        mock_consumer.consume = AsyncMock(side_effect=consume_results)

        with (
            patch("src.tasks.company_brain_tasks.SessionLocal", return_value=mock_db),
            patch(
                "src.services.company_brain.ingestion.stream_consumer.StreamConsumer",
                return_value=mock_consumer,
            ),
        ):
            result = company_brain_consume_active_streams_task.run()

        assert mock_consumer.consume.await_count == 3
        assert result["read"] == 140
        assert result["indexed"] == 130

    def test_stops_at_time_budget_even_if_stream_not_drained(self):
        """Regression guard: must not loop forever if a stream never empties within one tick."""
        source = _mock_source()

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [source]
        mock_db.close = MagicMock()

        mock_consumer = MagicMock()
        # Always returns a full, non-empty batch — simulates a backlog bigger than the time budget
        mock_consumer.consume = AsyncMock(return_value={"read": 100, "indexed": 100, "skipped": 0, "failed": 0})

        # Tie the fake clock to the number of completed consume() calls rather than a fixed
        # call-count iterator: asyncio's event loop internally calls time.monotonic() its own
        # unpredictable number of times per await (confirmed empirically — NOT just our own
        # explicit calls), so a small fixed-length iterator patched onto the global
        # time.monotonic runs out of values (StopIteration) before our loop's own logic
        # finishes. Keying off consume.call_count is deterministic regardless of how many
        # extra internal calls happen.
        def fake_monotonic():
            return 100.0 if mock_consumer.consume.call_count >= 3 else 0.0

        with (
            patch("src.tasks.company_brain_tasks.SessionLocal", return_value=mock_db),
            patch(
                "src.services.company_brain.ingestion.stream_consumer.StreamConsumer",
                return_value=mock_consumer,
            ),
            patch("time.monotonic", side_effect=fake_monotonic),
        ):
            company_brain_consume_active_streams_task.run()

        assert mock_consumer.consume.await_count == 3
