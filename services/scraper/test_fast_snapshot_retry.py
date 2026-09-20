"""Regression test: /v1/browser/fast-snapshot must retry through a page.evaluate()
that raises "Execution context was destroyed" right after a click triggers a real
navigation, instead of surfacing that as a hard failure.

Reproduced live: clicking a real link (example.com -> iana.org) navigates the
page, and the very next fast-snapshot call's page.evaluate() raised that exact
error because the new document hadn't started yet. Without a retry, the whole
internal_browser_autopilot run failed with "Snapshot failed" immediately after
a successful click -- indistinguishable, from the caller's side, from a real
error. jev-ultrafast's own observe() loop retries around the equivalent CDP
error for exactly this reason.

Run with: python -m unittest test_fast_snapshot_retry -v
(stdlib only -- no pytest/pytest-asyncio required)
"""

import unittest
from unittest.mock import AsyncMock, patch

import app as scraper_app


class _FakePage:
    def __init__(self, evaluate_results):
        # Each entry is either an exception instance (raised) or a return value.
        self._results = list(evaluate_results)
        self.calls = 0

    async def evaluate(self, _expression):
        self.calls += 1
        result = self._results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


_FAKE_SNAPSHOT = {
    "url": "https://www.iana.org/help/example-domains",
    "title": "Example Domains",
    "text": "...",
    "actions": [],
    "scroll": {"y": 0, "height": 100},
    "marker": [1, "u", 0, 0, 100, 100, "t", "x", [], []],
    "page_key": [1, "u", 0, 0, 100, 100, []],
    "guards": {},
    "omitted_actions": 0,
}


class TestFastSnapshotRetriesThroughDestroyedContext(unittest.IsolatedAsyncioTestCase):
    async def test_retries_and_succeeds_after_transient_navigation_error(self):
        destroyed_context_error = Exception("Page.evaluate: Execution context was destroyed, most likely because of a navigation")
        fake_page = _FakePage([destroyed_context_error, destroyed_context_error, dict(_FAKE_SNAPSHOT)])

        with patch.object(scraper_app, "_get_session_and_page", new=AsyncMock(return_value=(None, fake_page))):
            with patch.object(scraper_app, "_SNAPSHOT_RETRY_DELAY_SECONDS", 0):  # don't slow down the test suite
                result = await scraper_app.browser_fast_snapshot(
                    scraper_app.FastSnapshotRequest(session_id="s", page_id=None)
                )

        self.assertTrue(result["success"], result)
        self.assertEqual(result["url"], "https://www.iana.org/help/example-domains")
        self.assertEqual(fake_page.calls, 3)

    async def test_gives_up_and_reports_failure_after_exhausting_retries(self):
        always_fails = Exception("Execution context was destroyed, most likely because of a navigation")
        fake_page = _FakePage([always_fails] * scraper_app._SNAPSHOT_RETRY_ATTEMPTS)

        with patch.object(scraper_app, "_get_session_and_page", new=AsyncMock(return_value=(None, fake_page))):
            with patch.object(scraper_app, "_SNAPSHOT_RETRY_DELAY_SECONDS", 0):
                result = await scraper_app.browser_fast_snapshot(
                    scraper_app.FastSnapshotRequest(session_id="s", page_id=None)
                )

        self.assertFalse(result["success"])
        self.assertIn("Execution context was destroyed", result["error"])
        self.assertEqual(fake_page.calls, scraper_app._SNAPSHOT_RETRY_ATTEMPTS)

    async def test_no_retry_needed_when_first_attempt_succeeds(self):
        fake_page = _FakePage([dict(_FAKE_SNAPSHOT)])

        with patch.object(scraper_app, "_get_session_and_page", new=AsyncMock(return_value=(None, fake_page))):
            result = await scraper_app.browser_fast_snapshot(
                scraper_app.FastSnapshotRequest(session_id="s", page_id=None)
            )

        self.assertTrue(result["success"], result)
        self.assertEqual(fake_page.calls, 1)


if __name__ == "__main__":
    unittest.main()
