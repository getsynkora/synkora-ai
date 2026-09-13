import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from src.middleware.widget_auth import WidgetAuthMiddleware
from tests.integration.test_run_admission import isolated_redis  # noqa: F401


@pytest.mark.asyncio
async def test_concurrent_widget_requests_cannot_exceed_limit(isolated_redis):
    widget = SimpleNamespace(id=uuid4(), rate_limit=3)
    with patch("src.middleware.widget_auth._get_async_redis_rate_limiter", AsyncMock(return_value=isolated_redis)):
        results = await asyncio.gather(*(WidgetAuthMiddleware.check_rate_limit_async(widget) for _ in range(50)))
        assert sum(results) == 3
        assert await isolated_redis.zcard(f"widget:rate_limit:{widget.id}") == 3
        assert 0 < await isolated_redis.ttl(f"widget:rate_limit:{widget.id}") <= 3660
        # Another widget has an independent allowance.
        other = SimpleNamespace(id=uuid4(), rate_limit=1)
        assert await WidgetAuthMiddleware.check_rate_limit_async(other)
        assert not await WidgetAuthMiddleware.check_rate_limit_async(other)
