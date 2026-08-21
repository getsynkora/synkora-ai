"""Tests for BrowserSession.new_page() racing against the context "page" event.

Playwright's BrowserContext "page" event fires for every new page, including
ones created via context.new_page() itself. BrowserSession relies on that
event (_on_context_page -> _register_popup) to auto-track genuine popups, with
an idempotency check meant to skip pages already tracked. That check races
with new_page()'s own page registration: if the event-driven task runs first
(which happens in production -- see synkora-scraper logs showing a perfect
popup_N/page_M 1:1 alternation), new_page() blindly adds a SECOND dict entry
for the identical Page object, silently doubling page-slot consumption for
every explicit new_page() call and exhausting MAX_PAGES_PER_SESSION after
only half as many real pages as intended.

Run with: python -m unittest test_browser_session -v
(stdlib only -- no pytest/pytest-asyncio required)
"""

import unittest

from browser_session import BrowserSession


class _FakePage:
    """Minimal fake Page -- no real Playwright behavior needed for this test."""

    def on(self, *args, **kwargs):
        pass


class TestNewPageRaceWithContextPageEvent(unittest.IsolatedAsyncioTestCase):
    async def test_does_not_double_register_page_when_context_event_wins_race(self):
        session = BrowserSession("test-session")
        fake_page = _FakePage()

        async def fake_context_new_page():
            # Simulate the context "page" event's handler (_on_context_page ->
            # _register_popup) winning the race and registering the page
            # BEFORE context.new_page() returns to our caller.
            await session._register_popup(fake_page)
            return fake_page

        session.context = type("FakeContext", (), {"new_page": staticmethod(fake_context_new_page)})()

        await session.new_page()

        matching_keys = [pid for pid, p in session.pages.items() if p is fake_page]
        self.assertEqual(
            len(matching_keys),
            1,
            f"Expected the page tracked under exactly one key, got {matching_keys}",
        )

    async def test_normal_new_page_without_race_is_unaffected(self):
        session = BrowserSession("test-session")
        fake_page = _FakePage()

        async def fake_context_new_page():
            # No race this time -- the context "page" event simply never fires
            # (or fires after this returns), matching the common case.
            return fake_page

        session.context = type("FakeContext", (), {"new_page": staticmethod(fake_context_new_page)})()

        page_id, page = await session.new_page()

        self.assertEqual(page_id, "page_1")
        self.assertIs(page, fake_page)
        self.assertEqual(session.current_page_id, "page_1")

    async def test_returns_existing_page_id_when_context_event_wins_race(self):
        session = BrowserSession("test-session")
        fake_page = _FakePage()

        async def fake_context_new_page():
            await session._register_popup(fake_page)
            return fake_page

        session.context = type("FakeContext", (), {"new_page": staticmethod(fake_context_new_page)})()

        page_id, page = await session.new_page()

        self.assertEqual(page_id, "popup_1")
        self.assertIs(page, fake_page)
        self.assertEqual(session.current_page_id, "popup_1")


if __name__ == "__main__":
    unittest.main()
