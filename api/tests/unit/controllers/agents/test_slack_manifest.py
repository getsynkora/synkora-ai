"""Unit tests for the Slack app manifest generator's OAuth scope list."""

import pytest

from src.controllers.agents.slack_manifest import BOT_SCOPES


@pytest.mark.unit
class TestBotScopes:
    def test_includes_links_embed_write_for_video_block_support(self):
        """The `video` Block Kit block type requires links.embed:write on top of the
        links:read/links:write scopes already present — without it, chat.postMessage
        rejects any message containing a video block."""
        assert "links.embed:write" in BOT_SCOPES
