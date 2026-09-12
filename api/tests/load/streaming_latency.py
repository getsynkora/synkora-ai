"""Open-loop SSE measurements. No prompt/answer/token content is written to output.

AUTH_TOKEN=... python tests/load/streaming_latency.py --url http://localhost:5001 \
    --agent my-agent --requests 100 --rate 2 --expected-text expected
"""

import argparse
import asyncio
import json
import math
import os
import time

import httpx


async def sse_events(lines):
    data = []
    async for line in lines:
        if not line:
            if data:
                event = json.loads("\n".join(data))
                if not isinstance(event, dict) or not isinstance(event.get("type"), str):
                    raise ValueError("Invalid SSE event")
                yield event
                data = []
        elif line.startswith("data:"):
            data.append(line[5:].lstrip())
    if data:
        raise ValueError("Incomplete SSE frame")


async def measure(client, url, payload, timeout=120, expected_text=None):
    started = time.perf_counter()
    sample = {"success": False, "first_answer_ms": None, "first_tool_ms": None, "done_ms": None}
    text_parts = []
    try:
        async with asyncio.timeout(timeout):
            async with client.stream("POST", url, json=payload) as response:
                sample["status"] = response.status_code
                response.raise_for_status()
                if "text/event-stream" not in response.headers.get("content-type", ""):
                    raise ValueError("Response was not SSE")
                async for event in sse_events(response.aiter_lines()):
                    elapsed = (time.perf_counter() - started) * 1000
                    if event["type"] == "error":
                        raise ValueError("Application error")
                    if event["type"] == "chunk" and isinstance(event.get("content"), str) and event["content"]:
                        if sample["first_answer_ms"] is None:
                            sample["first_answer_ms"] = elapsed
                        if expected_text is not None:
                            text_parts.append(event["content"])
                    if event["type"] == "tool_status" and event.get("status") == "started":
                        if sample["first_tool_ms"] is None:
                            sample["first_tool_ms"] = elapsed
                    if event["type"] == "done":
                        sample["done_ms"] = elapsed
                sample["success"] = sample["first_answer_ms"] is not None and sample["done_ms"] is not None
                if expected_text is not None:
                    sample["success"] = sample["success"] and expected_text in "".join(text_parts)
    except (httpx.HTTPError, TimeoutError, ValueError) as exc:
        sample["error_category"] = type(exc).__name__
    sample["duration_ms"] = (time.perf_counter() - started) * 1000
    return sample


def percentiles(values):
    values = sorted(value for value in values if value is not None)
    return {f"p{p}": values[max(0, math.ceil(len(values) * p / 100) - 1)] if values else None for p in (50, 95, 99)}


async def run(args):
    payload = {"agent_slug": args.agent, "message": args.message, "conversation_history": []}
    pending = set()
    samples = []
    dropped = 0
    started = time.perf_counter()
    async with httpx.AsyncClient(
        headers={"Authorization": f"Bearer {os.environ['AUTH_TOKEN']}"},
        limits=httpx.Limits(max_connections=args.max_inflight),
        timeout=args.timeout,
    ) as client:
        for index in range(args.requests):
            await asyncio.sleep(max(0, started + index / args.rate - time.perf_counter()))
            finished = {task for task in pending if task.done()}
            samples.extend(task.result() for task in finished)
            pending -= finished
            if len(pending) >= args.max_inflight:
                dropped += 1
                continue
            pending.add(
                asyncio.create_task(
                    measure(
                        client,
                        args.url.rstrip("/") + "/api/v1/agents/chat/stream",
                        payload,
                        args.timeout,
                        args.expected_text,
                    )
                )
            )
        if pending:
            samples.extend(await asyncio.gather(*pending))
    succeeded = [sample for sample in samples if sample["success"]]
    duration = time.perf_counter() - started
    report = {
        "offered": args.requests,
        "sent": len(samples),
        "generator_dropped": dropped,
        "succeeded": len(succeeded),
        "failed": len(samples) - len(succeeded),
        "success_rate_of_offered": len(succeeded) / args.requests,
        "offered_rate_per_second": args.rate,
        "elapsed_seconds": duration,
        "successful_completions_per_second": len(succeeded) / duration,
        "latencies_ms_successful_requests": {
            key: percentiles([sample[key] for sample in succeeded])
            for key in ("first_answer_ms", "first_tool_ms", "done_ms", "duration_ms")
        },
        "expected_text_checked": args.expected_text is not None,
        "samples": samples,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--agent", required=True)
    parser.add_argument("--message", default="Reply with exactly: benchmark complete")
    parser.add_argument("--expected-text")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--rate", type=float, default=1)
    parser.add_argument("--max-inflight", type=int, default=32)
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args()
    if min(args.requests, args.rate, args.max_inflight, args.timeout) <= 0 or not os.environ.get("AUTH_TOKEN"):
        parser.error("Positive workload settings and AUTH_TOKEN are required")
    asyncio.run(run(args))
