import httpx
import pytest

from tests.load.streaming_latency import measure, sse_events


@pytest.mark.asyncio
async def test_parser_handles_comments_and_multiline_data():
    async def lines():
        for line in [": heartbeat", "", 'data: {"type":', 'data: "done"}', ""]:
            yield line

    assert [event async for event in sse_events(lines())] == [{"type": "done"}]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body,success",
    [
        ('data: {"type":"status","content":"working"}\n\ndata: {"type":"done"}\n\n', False),
        ('data: {"type":"chunk","content":"answer"}\n\ndata: {"type":"done"}\n\n', True),
        ('data: {"type":"chunk","content":"answer"}\n\ndata: {"type":"error"}\n\n', False),
        ('data: {"type":"error"}\n\n', False),
        ('data: {"type":"chunk","content":"answer"}\n\n', False),
    ],
)
async def test_measure_requires_successful_answer(body, success):
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, headers={"content-type": "text/event-stream"}, text=body)
    )
    async with httpx.AsyncClient(transport=transport) as client:
        sample = await measure(client, "https://example.com/stream", {})
    assert sample["success"] is success
