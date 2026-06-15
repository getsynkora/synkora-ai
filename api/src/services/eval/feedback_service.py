"""
Eval Feedback Service

Records per-message user feedback (thumbs up/down) across all channels.
Writes fire-and-forget to Elasticsearch and optionally scores the Langfuse trace.
"""

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

logger = logging.getLogger(__name__)

_feedback_bg_tasks: set[asyncio.Task] = set()
_es_client = None


async def _get_es_client():
    global _es_client
    if _es_client is not None:
        return _es_client
    from elasticsearch import AsyncElasticsearch

    from src.config.settings import settings

    _es_client = AsyncElasticsearch(
        [settings.elasticsearch_url],
        basic_auth=(settings.elasticsearch_username, settings.elasticsearch_password),
        verify_certs=False,
        request_timeout=5,
    )
    return _es_client


def _fire_feedback_event(event: dict) -> None:
    """Schedule ES index — returns in ~1µs, never raises."""
    try:
        task = asyncio.create_task(_index_feedback(event))
        _feedback_bg_tasks.add(task)
        task.add_done_callback(_feedback_bg_tasks.discard)
    except Exception as e:
        logger.warning("_fire_feedback_event scheduling error: %s", e)


async def _index_feedback(event: dict) -> None:
    """Index feedback doc to ES; silently discards on error. Uses message_id as doc ID for upsert."""
    try:
        from src.config.settings import settings

        es = await _get_es_client()
        await es.index(
            index=settings.agent_feedback_index,
            id=event["message_id"],
            document=event,
        )
    except Exception as e:
        logger.warning("ES feedback index failed (non-critical): %s", e)


def record_feedback(
    *,
    message_id: str,
    agent_id: UUID,
    tenant_id: UUID,
    channel: str,
    rating: int,  # 1 = thumbs up, -1 = thumbs down
    comment: str | None = None,
    trace_id: str | None = None,
) -> None:
    """
    Record per-message user feedback.

    Fires a MessageFeedback document to Elasticsearch (fire-and-forget) and,
    if a Langfuse trace_id is provided, scores the trace.

    Args:
        message_id: ID of the assistant message being rated
        agent_id: Agent that produced the message
        tenant_id: Tenant owning the agent
        channel: Source channel (widget/slack/whatsapp/teams/console)
        rating: 1 for thumbs up, -1 for thumbs down
        comment: Optional free-text comment from the user
        trace_id: Langfuse trace ID to attach the score to
    """
    _fire_feedback_event(
        {
            "message_id": str(message_id),
            "agent_id": str(agent_id),
            "tenant_id": str(tenant_id),
            "channel": channel,
            "rating": rating,
            "comment": comment,
            "trace_id": trace_id,
            "@timestamp": datetime.now(UTC).isoformat(),
        }
    )

    if trace_id:
        try:
            from src.services.observability.langfuse_service import langfuse_service

            score_value = 1.0 if rating > 0 else 0.0
            langfuse_service.score_generation(
                trace_id=trace_id,
                name="user_feedback",
                value=score_value,
                comment=comment,
            )
        except Exception as e:
            logger.warning("Langfuse score failed (non-critical): %s", e)
