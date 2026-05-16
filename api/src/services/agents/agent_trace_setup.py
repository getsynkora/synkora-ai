"""
Agent Trace Setup

Creates the Elasticsearch ILM policy, index template, and index for agent session
event tracing. Called once on app startup — idempotent, safe to re-run on every restart.
"""

import logging

logger = logging.getLogger(__name__)

_ILM_POLICY_NAME = "agent-trace-ilm"
_INDEX_TEMPLATE_NAME = "agent-session-events-template"


async def setup_agent_trace() -> None:
    """
    Ensure the ILM policy, index template, and index exist in Elasticsearch.

    Silently skips if tracing is disabled or ES is unreachable — never blocks startup.
    """
    from src.config.settings import settings

    if not settings.agent_trace_enabled:
        logger.info("Agent tracing disabled (AGENT_TRACE_ENABLED=false) — skipping ES setup")
        return

    try:
        from src.services.agents.agent_trace_service import _get_es_client

        es = await _get_es_client()
        index_name = settings.agent_trace_index
        retention_days = settings.agent_trace_retention_days

        await _ensure_ilm_policy(es, retention_days)
        await _ensure_index_template(es, index_name)
        await _ensure_index(es, index_name)
        logger.info("Agent trace ES setup complete (index=%s, retention=%dd)", index_name, retention_days)
    except Exception as e:
        logger.warning("Agent trace ES setup failed (non-critical): %s", e)


async def _ensure_ilm_policy(es, retention_days: int) -> None:
    """Create or update the ILM delete policy."""
    policy_body = {
        "policy": {
            "phases": {
                "delete": {
                    "min_age": f"{retention_days}d",
                    "actions": {"delete": {}},
                }
            }
        }
    }
    await es.ilm.put_lifecycle(name=_ILM_POLICY_NAME, body=policy_body)
    logger.debug("ILM policy '%s' created/updated", _ILM_POLICY_NAME)


async def _ensure_index_template(es, index_name: str) -> None:
    """Create or update the index template with explicit field mappings."""
    template_body = {
        "index_patterns": [f"{index_name}*"],
        "template": {
            "settings": {
                "index.lifecycle.name": _ILM_POLICY_NAME,
                "number_of_replicas": 0,
            },
            "mappings": {
                "properties": {
                    # Common envelope
                    "tenant_id": {"type": "keyword"},
                    "agent_id": {"type": "keyword"},
                    "conversation_id": {"type": "keyword"},
                    "event_type": {"type": "keyword"},
                    "sequence": {"type": "integer"},
                    "timestamp": {"type": "date"},
                    # user_message fields
                    "content": {"type": "text"},
                    "message_id": {"type": "keyword"},
                    "conversation_name": {"type": "keyword"},
                    "conversation_status": {"type": "keyword"},
                    # llm_call fields
                    "model": {"type": "keyword"},
                    "call_index": {"type": "integer"},
                    "input_tokens": {"type": "integer"},
                    "output_tokens": {"type": "integer"},
                    "cost_usd": {"type": "float"},
                    "latency_ms": {"type": "integer"},
                    "response_preview": {"type": "text"},
                    "llm_status": {"type": "keyword"},
                    "llm_error": {"type": "text"},
                    # tool_call fields
                    "tool_name": {"type": "keyword"},
                    "success": {"type": "boolean"},
                    "duration_ms": {"type": "integer"},
                    "retry_count": {"type": "integer"},
                    "args": {"type": "text"},
                    "result": {"type": "text"},
                    "error_message": {"type": "text"},
                    # assistant_message fields
                    "content_preview": {"type": "text"},
                    "total_input_tokens": {"type": "integer"},
                    "total_output_tokens": {"type": "integer"},
                    "total_cost_usd": {"type": "float"},
                    "total_latency_ms": {"type": "integer"},
                }
            },
        },
    }
    await es.indices.put_index_template(name=_INDEX_TEMPLATE_NAME, body=template_body)
    logger.debug("Index template '%s' created/updated", _INDEX_TEMPLATE_NAME)


async def _ensure_index(es, index_name: str) -> None:
    """Create the index if it does not already exist."""
    exists = await es.indices.exists(index=index_name)
    if not exists:
        await es.indices.create(index=index_name)
        logger.info("Created ES index '%s'", index_name)
    else:
        logger.debug("ES index '%s' already exists", index_name)
