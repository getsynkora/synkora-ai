"""One deadline for a whole model/tool run, including retries and backpressure."""

import asyncio
from contextlib import aclosing
from functools import wraps


def execution_deadline(function):
    @wraps(function)
    async def stream(self, *args, **kwargs):
        async with asyncio.timeout(self.agentic_config.run_timeout_seconds):
            async with aclosing(function(self, *args, **kwargs)) as events:
                async for event in events:
                    yield event

    return stream


def chat_execution_deadline(function):
    @wraps(function)
    async def stream(self, *args, **kwargs):
        from src.helpers.streaming_helpers import generate_error_event

        try:
            async with asyncio.timeout(3600):
                async with aclosing(function(self, *args, **kwargs)) as events:
                    async for event in events:
                        yield event
        except TimeoutError:
            yield await generate_error_event("The run exceeded its execution deadline")

    return stream
