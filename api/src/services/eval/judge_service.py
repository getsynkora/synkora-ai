"""
Eval Judge Service

On-demand LLM-as-judge runner for eval datasets.
Dispatched as a Celery task from the API layer.

Flow:
1. Load EvalCases from ES
2. For each case: run agent in non-streaming mode, call LLM judge
3. Write EvalResult docs to ES
4. Write EvalRun summary to ES
5. Push to Langfuse dataset run (if configured)
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


async def _get_es_client():
    """Create a fresh AsyncElasticsearch client each call.

    No module-level caching — callers may run in different asyncio event loops
    (API workers vs Celery tasks), and a cached aiohttp session bound to a
    closed loop raises RuntimeError.
    """
    from elasticsearch import AsyncElasticsearch

    from src.config.settings import settings

    return AsyncElasticsearch(
        [settings.elasticsearch_url],
        basic_auth=(settings.elasticsearch_username, settings.elasticsearch_password),
        verify_certs=False,
        request_timeout=30,
    )


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


_JUDGE_PROMPT = """You are an impartial evaluator assessing an AI assistant's response.

USER INPUT:
{input}

EXPECTED CRITERIA:
{criteria}

ACTUAL RESPONSE:
{actual}

Evaluate whether the actual response meets the expected criteria.
Respond with JSON only:
{{
  "score": <float 0.0-1.0>,
  "passed": <true|false>,
  "reasoning": "<one sentence>"
}}
A score >= 0.7 means passed=true. Be strict but fair."""


async def _run_agent_non_streaming(
    agent_id: UUID,
    tenant_id: UUID,
    message: str,
    db,
) -> str:
    """Run the agent in non-streaming mode and return the response text."""
    try:
        from sqlalchemy import select

        from src.models.agent import Agent
        from src.services.agents.agent_loader_service import AgentLoaderService
        from src.services.agents.chat_service import ChatService
        from src.services.agents.chat_stream_service import ChatStreamService

        result = await db.execute(select(Agent).filter(Agent.id == agent_id, Agent.tenant_id == tenant_id))
        db_agent = result.scalar_one_or_none()
        if not db_agent:
            return ""

        agent_loader = AgentLoaderService(db)
        agent = await agent_loader.load_agent(db_agent)

        chat_service = ChatService(db)
        stream_service = ChatStreamService(chat_service)

        chunks: list[str] = []
        async for event_str in stream_service.stream_response(
            agent=agent,
            db_agent=db_agent,
            message=message,
            conversation_id=None,
            tenant_id=tenant_id,
            db=db,
        ):
            import json

            try:
                if event_str.startswith("data: "):
                    data = json.loads(event_str[6:])
                    if data.get("type") == "chunk":
                        chunks.append(data.get("content", ""))
            except Exception:
                pass

        return "".join(chunks)
    except Exception as e:
        logger.warning("_run_agent_non_streaming failed: %s", e)
        return ""


async def _call_judge(input_text: str, criteria: str, actual: str, llm_config: Any) -> dict:
    """Call the LLM judge using the agent's configured provider and return {score, passed, reasoning}."""
    import json

    from src.config.settings import settings
    from src.services.agents.config import ModelConfig
    from src.services.agents.llm_client import MultiProviderLLMClient

    prompt = _JUDGE_PROMPT.format(input=input_text, criteria=criteria, actual=actual)
    try:
        if llm_config is None:
            logger.warning("No agent LLM config available for judge, skipping")
            return {"score": 0.0, "passed": False, "reasoning": "No LLM config available"}
        # Use agent's provider/api_key but allow model override via eval_judge_model setting
        judge_model = settings.eval_judge_model or llm_config.model_name
        config = ModelConfig(
            provider=llm_config.provider,
            model_name=judge_model,
            max_tokens=settings.eval_judge_max_tokens,
            api_key=llm_config.api_key,
            api_base=llm_config.api_base,
        )
        client = MultiProviderLLMClient(config=config)
        text = await client.generate_content(prompt, max_tokens=settings.eval_judge_max_tokens)
        # Extract JSON from response
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            result = json.loads(text[start:end])
            return {
                "score": float(result.get("score", 0.0)),
                "passed": bool(result.get("passed", False)),
                "reasoning": str(result.get("reasoning", "")),
            }
    except Exception as e:
        logger.warning("LLM judge call failed: %s", e)
    return {"score": 0.0, "passed": False, "reasoning": "Judge call failed"}


async def run_eval_dataset(
    *,
    run_id: str,
    dataset_id: str,
    agent_id: UUID,
    tenant_id: UUID,
    db,
) -> None:
    """
    Execute an eval run for all cases in a dataset.

    Called from the Celery task. Updates run status in ES as it progresses.
    """
    from sqlalchemy import select

    from src.config.settings import settings
    from src.models.agent import Agent
    from src.services.agents.config import ModelConfig
    from src.services.eval.dataset_service import list_cases

    es = await _get_es_client()

    # Load agent's LLM config for the judge (read direct from JSON column — no full agent load needed)
    result = await db.execute(select(Agent).filter(Agent.id == agent_id, Agent.tenant_id == tenant_id))
    db_agent = result.scalar_one_or_none()
    agent_llm_config = None
    if db_agent and isinstance(db_agent.llm_config, dict):
        raw = db_agent.llm_config
        agent_llm_config = ModelConfig(
            provider=raw.get("provider", "litellm"),
            model_name=raw.get("model_name", raw.get("model", "")),
            api_key=raw.get("api_key"),
            api_base=raw.get("api_base"),
        )

    # Mark run as running
    await es.index(
        index=settings.agent_eval_runs_index,
        id=f"run:{run_id}",
        document={
            "run_id": run_id,
            "dataset_id": dataset_id,
            "agent_id": str(agent_id),
            "tenant_id": str(tenant_id),
            "status": "running",
            "total_cases": 0,
            "passed": 0,
            "failed": 0,
            "pass_rate": 0.0,
            "avg_score": 0.0,
            "avg_latency_ms": 0,
            "ran_at": _now_iso(),
            "@timestamp": _now_iso(),
            "doc_type": "run",
        },
    )

    cases = await list_cases(dataset_id=dataset_id, tenant_id=tenant_id)
    results: list[dict] = []
    total_score = 0.0
    total_latency = 0
    passed_count = 0

    for case in cases:
        start = datetime.now(UTC)
        actual = await _run_agent_non_streaming(agent_id, tenant_id, case["input"], db)
        latency_ms = int((datetime.now(UTC) - start).total_seconds() * 1000)

        judgment = await _call_judge(case["input"], case["expected_criteria"], actual, agent_llm_config)

        result_doc: dict[str, Any] = {
            "result_id": str(uuid.uuid4()),
            "run_id": run_id,
            "case_id": case["case_id"],
            "dataset_id": dataset_id,
            "agent_id": str(agent_id),
            "tenant_id": str(tenant_id),
            "input": case["input"],
            "expected_criteria": case["expected_criteria"],
            "actual_output": actual[:2000],
            "score": judgment["score"],
            "passed": 1 if judgment["passed"] else 0,  # int to match run-summary "passed" ES long mapping
            "reasoning": judgment["reasoning"],
            "latency_ms": latency_ms,
            "@timestamp": _now_iso(),
            "doc_type": "result",
        }
        await es.index(
            index=settings.agent_eval_runs_index,
            id=f"result:{result_doc['result_id']}",
            document=result_doc,
        )

        results.append(result_doc)
        total_score += judgment["score"]
        total_latency += latency_ms
        if judgment["passed"]:
            passed_count += 1

    total = len(cases)
    avg_score = total_score / total if total else 0.0
    avg_latency = total_latency // total if total else 0

    # Write final run summary
    await es.index(
        index=settings.agent_eval_runs_index,
        id=f"run:{run_id}",
        document={
            "run_id": run_id,
            "dataset_id": dataset_id,
            "agent_id": str(agent_id),
            "tenant_id": str(tenant_id),
            "status": "completed",
            "total_cases": total,
            "passed": passed_count,
            "failed": total - passed_count,
            "pass_rate": round(passed_count / total, 3) if total else 0.0,
            "avg_score": round(avg_score, 3),
            "avg_latency_ms": avg_latency,
            "ran_at": _now_iso(),
            "@timestamp": _now_iso(),
            "doc_type": "run",
        },
    )

    # Push to Langfuse if configured
    _push_to_langfuse(run_id, dataset_id, results, agent_id)


def _push_to_langfuse(run_id: str, dataset_id: str, results: list[dict], agent_id: UUID) -> None:
    """Push eval run to Langfuse as a dataset run (best-effort)."""
    try:
        from src.services.observability.langfuse_service import langfuse_service

        if not langfuse_service.is_enabled or not langfuse_service._client:
            return

        client = langfuse_service._client
        dataset_name = f"agent-{agent_id}-{dataset_id[:8]}"

        # Ensure dataset exists in Langfuse
        try:
            client.create_dataset(name=dataset_name)
        except Exception:
            pass  # Already exists

        for r in results:
            try:
                item = client.create_dataset_item(
                    dataset_name=dataset_name,
                    input=r["input"],
                    expected_output=r["expected_criteria"],
                )
                client.create_trace(
                    name=f"eval-{run_id[:8]}",
                    input=r["input"],
                    output=r["actual_output"],
                    metadata={"score": r["score"], "passed": r["passed"], "run_id": run_id},
                )
                item.link(run_id, r.get("actual_output", ""))
            except Exception as e:
                logger.debug("Langfuse dataset item push failed: %s", e)
    except Exception as e:
        logger.warning("Langfuse eval push failed (non-critical): %s", e)


async def get_run(*, run_id: str, tenant_id: UUID) -> dict | None:
    """Get a run summary by ID."""
    from elasticsearch import NotFoundError

    from src.config.settings import settings

    es = await _get_es_client()
    try:
        result = await es.get(index=settings.agent_eval_runs_index, id=f"run:{run_id}")
        doc = result["_source"]
        if doc.get("tenant_id") != str(tenant_id):
            return None
        return doc
    except NotFoundError:
        return None


async def list_runs(*, agent_id: UUID, tenant_id: UUID) -> list[dict]:
    """List all completed runs for an agent, most recent first."""
    from elasticsearch import NotFoundError

    from src.config.settings import settings

    es = await _get_es_client()
    body = {
        "query": {
            "bool": {
                "filter": [
                    {"term": {"agent_id.keyword": str(agent_id)}},
                    {"term": {"tenant_id.keyword": str(tenant_id)}},
                    {"term": {"doc_type.keyword": "run"}},
                ]
            }
        },
        "size": 50,
        "sort": [{"@timestamp": {"order": "desc"}}],
    }
    try:
        resp = await es.search(index=settings.agent_eval_runs_index, body=body)
        return [h["_source"] for h in resp["hits"]["hits"]]
    except NotFoundError:
        return []


async def get_run_results(*, run_id: str, tenant_id: UUID) -> list[dict]:
    """Get all per-case results for a run."""
    from elasticsearch import NotFoundError

    from src.config.settings import settings

    es = await _get_es_client()
    body = {
        "query": {
            "bool": {
                "filter": [
                    {"term": {"run_id.keyword": run_id}},
                    {"term": {"tenant_id.keyword": str(tenant_id)}},
                    {"term": {"doc_type.keyword": "result"}},
                ]
            }
        },
        "size": 500,
        "sort": [{"@timestamp": {"order": "asc"}}],
    }
    try:
        resp = await es.search(index=settings.agent_eval_runs_index, body=body)
        return [h["_source"] for h in resp["hits"]["hits"]]
    except NotFoundError:
        return []
