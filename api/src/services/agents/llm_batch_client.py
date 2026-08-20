"""
LLM Batch API Client

Submits requests to OpenAI Batch API and Anthropic Message Batches API
for 50% cost reduction on background Celery tasks.

IMPORTANT: Batch API has up to 24-hour latency. Only use for scheduled/background
tasks — never for real-time chat.
"""

import json
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class BatchRequest:
    """One request in a batch."""

    custom_id: str
    messages: list[dict]
    model: str
    max_tokens: int
    system_prompt: str | None = None


@dataclass
class BatchResult:
    """Result of one request in a completed batch."""

    custom_id: str
    content: str | None
    error: str | None
    input_tokens: int = 0
    output_tokens: int = 0


class OpenAIBatchClient:
    """
    Submits to OpenAI /v1/batches (50% cost reduction, up to 24h latency).

    Reference: https://platform.openai.com/docs/guides/batch
    """

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def _make_client(self):
        from openai import AsyncOpenAI

        return AsyncOpenAI(api_key=self.api_key)

    async def submit(self, requests: list[BatchRequest]) -> str:
        """
        Upload a JSONL file and create a batch job.

        Returns the batch_id string.
        """
        # async with ensures the SDK client (and its underlying httpx.AsyncClient)
        # closes deterministically before this coroutine returns — Celery tasks
        # run this inside a manually-managed event loop that gets closed right
        # after, and an unclosed client's cleanup then fires on a dead loop
        # ("Task exception was never retrieved: ... Event loop is closed").
        async with self._make_client() as client:
            # Build JSONL content
            lines = []
            for req in requests:
                msgs = list(req.messages)
                if req.system_prompt:
                    msgs = [{"role": "system", "content": req.system_prompt}] + msgs
                lines.append(
                    json.dumps(
                        {
                            "custom_id": req.custom_id,
                            "method": "POST",
                            "url": "/v1/chat/completions",
                            "body": {
                                "model": req.model or self.model,
                                "messages": msgs,
                                "max_completion_tokens": req.max_tokens,
                            },
                        }
                    )
                )
            jsonl_bytes = "\n".join(lines).encode()

            # Upload file
            file_obj = await client.files.create(
                file=("batch_requests.jsonl", jsonl_bytes, "application/jsonl"),
                purpose="batch",
            )

            # Create batch
            batch = await client.batches.create(
                input_file_id=file_obj.id,
                endpoint="/v1/chat/completions",
                completion_window="24h",
            )
            logger.info(f"OpenAI batch submitted: {batch.id} ({len(requests)} requests)")
            return batch.id

    async def poll(self, batch_id: str) -> tuple[str, list[BatchResult] | None]:
        """
        Poll batch status.

        Returns (status, results_or_None).
        status values: "validating" | "in_progress" | "completed" | "failed" | "expired"
        results is None unless status == "completed".
        """
        async with self._make_client() as client:
            batch = await client.batches.retrieve(batch_id)
            status = batch.status

            if status != "completed":
                return status, None

            if not batch.output_file_id:
                return "failed", None

            # Download results
            file_content = await client.files.content(batch.output_file_id)
            raw_text = file_content.text if hasattr(file_content, "text") else file_content.decode()

        results: list[BatchResult] = []
        for line in raw_text.strip().splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
                custom_id = item.get("custom_id", "")
                resp = item.get("response", {})
                body = resp.get("body", {})
                if resp.get("status_code") == 200:
                    choice = (body.get("choices") or [{}])[0]
                    content = (choice.get("message") or {}).get("content")
                    usage = body.get("usage", {})
                    results.append(
                        BatchResult(
                            custom_id=custom_id,
                            content=content,
                            error=None,
                            input_tokens=usage.get("prompt_tokens", 0),
                            output_tokens=usage.get("completion_tokens", 0),
                        )
                    )
                else:
                    error = item.get("error", {}).get("message", "unknown error")
                    results.append(BatchResult(custom_id=custom_id, content=None, error=error))
            except Exception as e:
                logger.warning(f"Failed to parse batch result line: {e}")

        return "completed", results


class AnthropicBatchClient:
    """
    Submits to Anthropic /v1/messages/batches (50% cost reduction, up to 24h latency).

    Reference: https://docs.anthropic.com/en/docs/message-batches
    """

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def _make_client(self):
        from anthropic import AsyncAnthropic

        return AsyncAnthropic(api_key=self.api_key)

    async def submit(self, requests: list[BatchRequest]) -> str:
        """Submit a batch and return batch_id."""
        async with self._make_client() as client:
            batch_requests = []
            for req in requests:
                params: dict = {
                    "model": req.model or self.model,
                    "max_tokens": req.max_tokens,
                    "messages": req.messages,
                }
                if req.system_prompt:
                    params["system"] = req.system_prompt
                batch_requests.append({"custom_id": req.custom_id, "params": params})

            batch = await client.beta.messages.batches.create(requests=batch_requests)
            logger.info(f"Anthropic batch submitted: {batch.id} ({len(requests)} requests)")
            return batch.id

    async def poll(self, batch_id: str) -> tuple[str, list[BatchResult] | None]:
        """
        Poll batch status.

        Returns (status, results_or_None).
        status values: "in_progress" | "ended"
        """
        async with self._make_client() as client:
            batch = await client.beta.messages.batches.retrieve(batch_id)
            status = batch.processing_status  # "in_progress" | "ended"

            if status != "ended":
                return status, None

            # Stream results
            results: list[BatchResult] = []
            async for result in await client.beta.messages.batches.results(batch_id):
                custom_id = result.custom_id
                if result.result.type == "succeeded":
                    msg = result.result.message
                    content = msg.content[0].text if msg.content else None
                    results.append(
                        BatchResult(
                            custom_id=custom_id,
                            content=content,
                            error=None,
                            input_tokens=msg.usage.input_tokens,
                            output_tokens=msg.usage.output_tokens,
                        )
                    )
                else:
                    error = getattr(result.result, "error", None)
                    results.append(BatchResult(custom_id=custom_id, content=None, error=str(error)))

        return "completed", results


def get_batch_client(provider: str, api_key: str, model: str) -> OpenAIBatchClient | AnthropicBatchClient | None:
    """
    Return the appropriate batch client for a provider, or None if unsupported.

    Only OpenAI and Anthropic support batch APIs.
    """
    p = provider.lower()
    if p == "openai":
        return OpenAIBatchClient(api_key=api_key, model=model)
    if p in ("anthropic", "claude"):
        return AnthropicBatchClient(api_key=api_key, model=model)
    return None
