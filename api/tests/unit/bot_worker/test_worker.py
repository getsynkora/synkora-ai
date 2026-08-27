"""Tests for BotWorker's hash-ring rebalancing — specifically that a worker releases
bots it no longer owns after the ring shifts (e.g. a new worker joins on scale-up).

Regression coverage for a production incident: an existing bot-worker pod never learned
it lost ownership of a Telegram bot to a newly-joined pod, so both kept polling
`getUpdates` for the same token indefinitely, producing a continuous stream of
`telegram.error.Conflict: terminated by other getUpdates request` errors.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot_worker.config import BotWorkerConfig
from src.bot_worker.worker import BotWorker


class _DummyAsyncSessionCM:
    async def __aenter__(self):
        return MagicMock()

    async def __aexit__(self, *args):
        return False


@pytest.fixture
def worker():
    config = BotWorkerConfig(worker_id="worker-a")
    with patch("src.services.agents.agent_manager.AgentManager"):
        w = BotWorker(config=config, redis_client=MagicMock())
    return w


@pytest.fixture
def patched_session_factory():
    with patch(
        "src.bot_worker.worker.get_async_session_factory",
        return_value=lambda: _DummyAsyncSessionCM(),
    ):
        yield


class TestReleaseUnownedBots:
    @pytest.mark.asyncio
    async def test_stops_bots_the_ring_no_longer_assigns_to_this_worker(self, worker, patched_session_factory):
        worker._active_bots = {
            "bot-mine": {"type": "telegram"},
            "bot-reassigned": {"type": "telegram"},
        }
        worker._get_all_active_bot_ids = AsyncMock(return_value=["bot-mine", "bot-reassigned"])
        worker._hash_ring = MagicMock()
        worker._hash_ring.get_keys_for_node.return_value = ["bot-mine"]  # ring only gives us "bot-mine" now
        worker._stop_bot = AsyncMock(return_value=True)

        await worker._release_unowned_bots()

        worker._stop_bot.assert_awaited_once_with("bot-reassigned")

    @pytest.mark.asyncio
    async def test_does_not_stop_bots_still_owned(self, worker, patched_session_factory):
        worker._active_bots = {"bot-mine": {"type": "telegram"}}
        worker._get_all_active_bot_ids = AsyncMock(return_value=["bot-mine"])
        worker._hash_ring = MagicMock()
        worker._hash_ring.get_keys_for_node.return_value = ["bot-mine"]
        worker._stop_bot = AsyncMock(return_value=True)

        await worker._release_unowned_bots()

        worker._stop_bot.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_active_bots_is_a_no_op(self, worker, patched_session_factory):
        worker._active_bots = {}
        worker._get_all_active_bot_ids = AsyncMock(return_value=[])
        worker._hash_ring = MagicMock()
        worker._hash_ring.get_keys_for_node.return_value = []
        worker._stop_bot = AsyncMock(return_value=True)

        await worker._release_unowned_bots()

        worker._stop_bot.assert_not_awaited()
