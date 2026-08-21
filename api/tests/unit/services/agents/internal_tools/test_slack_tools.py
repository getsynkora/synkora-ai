"""
Tests for slack_tools.py - Slack Tools for Autonomous Agent Interaction

Tests the Slack tools that allow agents to interact with Slack channels,
including reading messages, sending messages, and searching.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from slack_sdk.errors import SlackApiError


class TestGetSlackClient:
    """Tests for _get_slack_client helper function."""

    @pytest.mark.asyncio
    async def test_returns_none_without_agent_id(self):
        from src.services.agents.internal_tools.slack_tools import _get_slack_client

        result = await _get_slack_client({})
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_with_empty_runtime_context(self):
        from src.services.agents.internal_tools.slack_tools import _get_slack_client

        result = await _get_slack_client(None)
        assert result is None


class TestInternalSlackListChannels:
    """Tests for internal_slack_list_channels function."""

    @pytest.mark.asyncio
    async def test_returns_error_without_slack_client(self):
        from src.services.agents.internal_tools.slack_tools import internal_slack_list_channels

        with patch(
            "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
        ) as mock_client:
            mock_client.return_value = None

            result = await internal_slack_list_channels(runtime_context={})

            assert result["success"] is False
            assert "No Slack connection" in result["error"]

    @pytest.mark.asyncio
    async def test_lists_channels_successfully(self):
        from src.services.agents.internal_tools.slack_tools import internal_slack_list_channels

        mock_slack_client = AsyncMock()
        mock_slack_client.conversations_list.return_value = {
            "channels": [
                {
                    "id": "C123",
                    "name": "general",
                    "is_private": False,
                    "is_member": True,
                    "num_members": 50,
                    "topic": {"value": "General chat"},
                    "purpose": {"value": "Company announcements"},
                },
                {
                    "id": "C456",
                    "name": "random",
                    "is_private": False,
                    "is_member": True,
                    "num_members": 45,
                    "topic": {"value": ""},
                    "purpose": {"value": ""},
                },
            ],
            "response_metadata": {"next_cursor": ""},
        }

        with patch(
            "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_slack_client

            result = await internal_slack_list_channels(runtime_context={"agent_id": "test"})

            assert result["success"] is True
            assert result["total"] == 2
            assert len(result["channels"]) == 2
            assert result["channels"][0]["name"] == "general"

    @pytest.mark.asyncio
    async def test_handles_slack_api_error(self):
        from src.services.agents.internal_tools.slack_tools import internal_slack_list_channels

        mock_slack_client = AsyncMock()
        mock_slack_client.conversations_list.side_effect = SlackApiError(
            message="rate_limited", response={"error": "rate_limited"}
        )

        with patch(
            "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_slack_client

            result = await internal_slack_list_channels(runtime_context={"agent_id": "test"})

            assert result["success"] is False


class TestInternalSlackReadChannelMessages:
    """Tests for internal_slack_read_channel_messages function."""

    @pytest.mark.asyncio
    async def test_returns_error_without_slack_client(self):
        from src.services.agents.internal_tools.slack_tools import internal_slack_read_channel_messages

        with patch(
            "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = None

            result = await internal_slack_read_channel_messages(channel_id="C123", runtime_context={})

            assert result["success"] is False


class TestInternalSlackSendMessage:
    """Tests for internal_slack_send_message function."""

    @pytest.mark.asyncio
    async def test_returns_error_without_slack_client(self):
        from src.services.agents.internal_tools.slack_tools import internal_slack_send_message

        with patch(
            "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = None

            result = await internal_slack_send_message(channel_id="C123", text="Hello!", runtime_context={})

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_sends_message_successfully(self):
        from src.services.agents.internal_tools.slack_tools import internal_slack_send_message

        mock_slack_client = AsyncMock()
        mock_slack_client.chat_postMessage.return_value = {
            "ok": True,
            "ts": "1234567890.123456",
            "channel": "C123",
        }

        with (
            patch(
                "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
            ) as mock_get,
            patch("src.services.slack.formatters.format_text_for_slack", return_value="Hello!"),
        ):
            mock_get.return_value = mock_slack_client

            result = await internal_slack_send_message(
                channel_id="C123", text="Hello!", runtime_context={"agent_id": "test"}
            )

            assert result["success"] is True
            assert result["message_ts"] == "1234567890.123456"

    @pytest.mark.asyncio
    async def test_sends_thread_reply(self):
        from src.services.agents.internal_tools.slack_tools import internal_slack_send_message

        mock_slack_client = AsyncMock()
        mock_slack_client.chat_postMessage.return_value = {
            "ok": True,
            "ts": "1234567890.999999",
            "channel": "C123",
        }

        with (
            patch(
                "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
            ) as mock_get,
            patch("src.services.slack.formatters.format_text_for_slack", return_value="Thread reply!"),
        ):
            mock_get.return_value = mock_slack_client

            result = await internal_slack_send_message(
                channel_id="C123",
                text="Thread reply!",
                thread_ts="1234567890.123456",
                runtime_context={"agent_id": "test"},
            )

            assert result["success"] is True
            mock_slack_client.chat_postMessage.assert_called_once()
            call_kwargs = mock_slack_client.chat_postMessage.call_args.kwargs
            assert call_kwargs["thread_ts"] == "1234567890.123456"

    @pytest.mark.asyncio
    async def test_defaults_to_shared_state_thread_ts_when_omitted(self):
        """When the LLM omits thread_ts, the message must still land in the same
        thread as the triggering Slack message — never split into the main channel."""
        from src.services.agents.internal_tools.slack_tools import internal_slack_send_message

        mock_slack_client = AsyncMock()
        mock_slack_client.chat_postMessage.return_value = {"ok": True, "ts": "1.1", "channel": "C123"}

        with (
            patch(
                "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
            ) as mock_get,
            patch("src.services.slack.formatters.format_text_for_slack", return_value="Hi!"),
        ):
            mock_get.return_value = mock_slack_client

            result = await internal_slack_send_message(
                channel_id="C123",
                text="Hi!",
                runtime_context={"agent_id": "test", "shared_state": {"slack_thread_ts": "1234567890.123456"}},
            )

            assert result["success"] is True
            call_kwargs = mock_slack_client.chat_postMessage.call_args.kwargs
            assert call_kwargs["thread_ts"] == "1234567890.123456"

    @pytest.mark.asyncio
    async def test_explicit_thread_ts_overrides_shared_state_default(self):
        from src.services.agents.internal_tools.slack_tools import internal_slack_send_message

        mock_slack_client = AsyncMock()
        mock_slack_client.chat_postMessage.return_value = {"ok": True, "ts": "1.1", "channel": "C123"}

        with (
            patch(
                "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
            ) as mock_get,
            patch("src.services.slack.formatters.format_text_for_slack", return_value="Hi!"),
        ):
            mock_get.return_value = mock_slack_client

            result = await internal_slack_send_message(
                channel_id="C123",
                text="Hi!",
                thread_ts="9999999999.000000",
                runtime_context={"agent_id": "test", "shared_state": {"slack_thread_ts": "1234567890.123456"}},
            )

            assert result["success"] is True
            call_kwargs = mock_slack_client.chat_postMessage.call_args.kwargs
            assert call_kwargs["thread_ts"] == "9999999999.000000"


class TestInternalSlackJoinChannel:
    """Tests for internal_slack_join_channel function."""

    @pytest.mark.asyncio
    async def test_returns_error_without_client(self):
        from src.services.agents.internal_tools.slack_tools import internal_slack_join_channel

        with patch(
            "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = None

            result = await internal_slack_join_channel(channel_id="C123", runtime_context={})

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_joins_channel_successfully(self):
        from src.services.agents.internal_tools.slack_tools import internal_slack_join_channel

        mock_slack_client = AsyncMock()
        mock_slack_client.conversations_join.return_value = {
            "ok": True,
            "channel": {"id": "C123", "name": "test-channel"},
        }

        with patch(
            "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_slack_client

            result = await internal_slack_join_channel(channel_id="C123", runtime_context={"agent_id": "test"})

            assert result["success"] is True
            assert result["channel_name"] == "test-channel"


class TestInternalSlackCreateChannel:
    """Tests for internal_slack_create_channel function."""

    @pytest.mark.asyncio
    async def test_returns_error_without_client(self):
        from src.services.agents.internal_tools.slack_tools import internal_slack_create_channel

        with patch(
            "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = None

            result = await internal_slack_create_channel(name="bughunt", runtime_context={})

            assert result["success"] is False
            assert "No Slack connection" in result["error"]

    @pytest.mark.asyncio
    async def test_creates_public_channel_successfully(self):
        from src.services.agents.internal_tools.slack_tools import internal_slack_create_channel

        mock_slack_client = AsyncMock()
        mock_slack_client.conversations_create.return_value = {
            "ok": True,
            "channel": {"id": "C999", "name": "bughunt"},
        }

        with patch(
            "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_slack_client

            result = await internal_slack_create_channel(name="bughunt", runtime_context={"agent_id": "test"})

            assert result["success"] is True
            assert result["channel_id"] == "C999"
            assert result["channel_name"] == "bughunt"
            mock_slack_client.conversations_create.assert_called_once_with(name="bughunt", is_private=False)

    @pytest.mark.asyncio
    async def test_creates_private_channel_when_requested(self):
        from src.services.agents.internal_tools.slack_tools import internal_slack_create_channel

        mock_slack_client = AsyncMock()
        mock_slack_client.conversations_create.return_value = {
            "ok": True,
            "channel": {"id": "C998", "name": "secret-room"},
        }

        with patch(
            "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_slack_client

            result = await internal_slack_create_channel(
                name="secret-room", is_private=True, runtime_context={"agent_id": "test"}
            )

            assert result["success"] is True
            mock_slack_client.conversations_create.assert_called_once_with(name="secret-room", is_private=True)

    @pytest.mark.asyncio
    async def test_handles_slack_api_error(self):
        from src.services.agents.internal_tools.slack_tools import internal_slack_create_channel

        mock_slack_client = AsyncMock()
        mock_slack_client.conversations_create.side_effect = SlackApiError(
            message="invalid_name", response={"error": "invalid_name"}
        )

        with patch(
            "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_slack_client

            result = await internal_slack_create_channel(name="bughunt", runtime_context={"agent_id": "test"})

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_reuses_existing_channel_on_name_taken(self):
        """A retried task may attempt to (re)create a channel it already made -- recover by
        looking up the existing channel instead of failing and leaving the LLM to improvise.
        """
        from src.services.agents.internal_tools.slack_tools import internal_slack_create_channel

        mock_slack_client = AsyncMock()
        mock_slack_client.conversations_create.side_effect = SlackApiError(
            message="name_taken", response={"error": "name_taken"}
        )
        mock_slack_client.conversations_list.return_value = {
            "channels": [
                {"id": "C111", "name": "other-channel"},
                {"id": "C222", "name": "bughunt"},
            ],
            "response_metadata": {"next_cursor": ""},
        }

        with patch(
            "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_slack_client

            result = await internal_slack_create_channel(name="bughunt", runtime_context={"agent_id": "test"})

            assert result["success"] is True
            assert result["channel_id"] == "C222"
            assert result["channel_name"] == "bughunt"

    @pytest.mark.asyncio
    async def test_name_taken_lookup_miss_still_returns_error(self):
        """If the channel can't be found after a name_taken error (e.g. it's a channel the
        bot can't see, such as a private channel it's not a member of), fail clearly instead
        of silently pretending success.
        """
        from src.services.agents.internal_tools.slack_tools import internal_slack_create_channel

        mock_slack_client = AsyncMock()
        mock_slack_client.conversations_create.side_effect = SlackApiError(
            message="name_taken", response={"error": "name_taken"}
        )
        mock_slack_client.conversations_list.return_value = {
            "channels": [{"id": "C111", "name": "other-channel"}],
            "response_metadata": {"next_cursor": ""},
        }

        with patch(
            "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_slack_client

            result = await internal_slack_create_channel(name="bughunt", runtime_context={"agent_id": "test"})

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_invites_requesting_slack_user_on_create(self):
        """A newly created channel only has the bot as a member -- a human who asked
        for it in a real Slack conversation would never see it in their channel list
        unless invited. When the triggering message's slack_user_id is known (stored
        in shared_state by slack_message_handler.py), invite them."""
        from src.services.agents.internal_tools.slack_tools import internal_slack_create_channel

        mock_slack_client = AsyncMock()
        mock_slack_client.conversations_create.return_value = {
            "ok": True,
            "channel": {"id": "C998", "name": "bughunt"},
        }

        with patch(
            "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_slack_client

            result = await internal_slack_create_channel(
                name="bughunt",
                runtime_context={"agent_id": "test", "shared_state": {"slack_user_id": "U555"}},
            )

            assert result["success"] is True
            mock_slack_client.conversations_invite.assert_called_once_with(channel="C998", users="U555")

    @pytest.mark.asyncio
    async def test_invites_requesting_slack_user_on_reused_channel(self):
        from src.services.agents.internal_tools.slack_tools import internal_slack_create_channel

        mock_slack_client = AsyncMock()
        mock_slack_client.conversations_create.side_effect = SlackApiError(
            message="name_taken", response={"error": "name_taken"}
        )
        mock_slack_client.conversations_list.return_value = {
            "channels": [{"id": "C222", "name": "bughunt"}],
            "response_metadata": {"next_cursor": ""},
        }

        with patch(
            "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_slack_client

            result = await internal_slack_create_channel(
                name="bughunt",
                runtime_context={"agent_id": "test", "shared_state": {"slack_user_id": "U555"}},
            )

            assert result["success"] is True
            mock_slack_client.conversations_invite.assert_called_once_with(channel="C222", users="U555")

    @pytest.mark.asyncio
    async def test_does_not_invite_when_no_requesting_user_known(self):
        """Tasks triggered outside a real Slack conversation (e.g. the web console) have
        no slack_user_id in shared_state -- there's no one to invite, so skip silently."""
        from src.services.agents.internal_tools.slack_tools import internal_slack_create_channel

        mock_slack_client = AsyncMock()
        mock_slack_client.conversations_create.return_value = {
            "ok": True,
            "channel": {"id": "C998", "name": "bughunt"},
        }

        with patch(
            "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_slack_client

            result = await internal_slack_create_channel(name="bughunt", runtime_context={"agent_id": "test"})

            assert result["success"] is True
            mock_slack_client.conversations_invite.assert_not_called()

    @pytest.mark.asyncio
    async def test_invite_already_in_channel_error_is_ignored(self):
        """Re-running a task in the same thread invites the same already-a-member user
        every time -- Slack's already_in_channel error for that must not fail the tool."""
        from src.services.agents.internal_tools.slack_tools import internal_slack_create_channel

        mock_slack_client = AsyncMock()
        mock_slack_client.conversations_create.return_value = {
            "ok": True,
            "channel": {"id": "C998", "name": "bughunt"},
        }
        mock_slack_client.conversations_invite.side_effect = SlackApiError(
            message="already_in_channel", response={"error": "already_in_channel"}
        )

        with patch(
            "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_slack_client

            result = await internal_slack_create_channel(
                name="bughunt",
                runtime_context={"agent_id": "test", "shared_state": {"slack_user_id": "U555"}},
            )

            assert result["success"] is True


class TestInternalSlackSearchMessages:
    """Tests for internal_slack_search_messages function."""

    @pytest.mark.asyncio
    async def test_returns_error_without_client(self):
        from src.services.agents.internal_tools.slack_tools import internal_slack_search_messages

        with patch(
            "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = None

            result = await internal_slack_search_messages(query="keyword", runtime_context={})

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_searches_messages_successfully(self):
        from src.services.agents.internal_tools.slack_tools import internal_slack_search_messages

        mock_slack_client = AsyncMock()
        mock_slack_client.search_messages.return_value = {
            "ok": True,
            "messages": {
                "matches": [
                    {
                        "type": "message",
                        "text": "Test message with keyword",
                        "username": "testuser",
                        "ts": "1234567890.123456",
                        "channel": {"id": "C123", "name": "general"},
                        "permalink": "https://slack.com/archives/C123/p1234567890123456",
                    },
                ],
                "total": 1,
            },
        }

        with patch(
            "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_slack_client

            result = await internal_slack_search_messages(query="keyword", runtime_context={"agent_id": "test"})

            assert result["success"] is True
            assert result["total_results"] == 1
            assert len(result["matches"]) == 1


class TestInternalSlackAddReaction:
    """Tests for internal_slack_add_reaction function."""

    @pytest.mark.asyncio
    async def test_returns_error_without_client(self):
        from src.services.agents.internal_tools.slack_tools import internal_slack_add_reaction

        with patch(
            "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = None

            result = await internal_slack_add_reaction(
                channel_id="C123", timestamp="1234567890.123456", emoji="thumbsup", runtime_context={}
            )

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_adds_reaction_successfully(self):
        from src.services.agents.internal_tools.slack_tools import internal_slack_add_reaction

        mock_slack_client = AsyncMock()
        mock_slack_client.reactions_add.return_value = {"ok": True}

        with patch(
            "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_slack_client

            result = await internal_slack_add_reaction(
                channel_id="C123", timestamp="1234567890.123456", emoji="thumbsup", runtime_context={"agent_id": "test"}
            )

            assert result["success"] is True
            assert result["emoji"] == "thumbsup"
            mock_slack_client.reactions_add.assert_called_once_with(
                channel="C123",
                timestamp="1234567890.123456",
                name="thumbsup",
            )

    @pytest.mark.asyncio
    async def test_handles_api_error(self):
        from src.services.agents.internal_tools.slack_tools import internal_slack_add_reaction

        mock_slack_client = AsyncMock()
        mock_slack_client.reactions_add.side_effect = SlackApiError(
            message="invalid_name", response={"error": "invalid_name"}
        )

        with patch(
            "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_slack_client

            result = await internal_slack_add_reaction(
                channel_id="C123",
                timestamp="1234567890.123456",
                emoji="invalid_emoji",
                runtime_context={"agent_id": "test"},
            )

            assert result["success"] is False


class TestInternalSlackSendDM:
    """Tests for internal_slack_send_dm function."""

    @pytest.mark.asyncio
    async def test_returns_error_without_client(self):
        from src.services.agents.internal_tools.slack_tools import internal_slack_send_dm

        with patch(
            "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = None

            result = await internal_slack_send_dm(user_id="U456", text="Hello!", runtime_context={})

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_sends_dm_successfully(self):
        from src.services.agents.internal_tools.slack_tools import internal_slack_send_dm

        mock_slack_client = AsyncMock()
        mock_slack_client.conversations_open.return_value = {
            "ok": True,
            "channel": {"id": "D123"},
        }
        mock_slack_client.chat_postMessage.return_value = {
            "ok": True,
            "ts": "1234567890.123456",
            "channel": "D123",
        }

        with (
            patch(
                "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
            ) as mock_get,
            patch("src.services.slack.formatters.format_text_for_slack", return_value="Hello in DM!"),
        ):
            mock_get.return_value = mock_slack_client

            result = await internal_slack_send_dm(
                user_id="U456", text="Hello in DM!", runtime_context={"agent_id": "test"}
            )

            assert result["success"] is True
            assert result["user_id"] == "U456"
            mock_slack_client.conversations_open.assert_called_once_with(users=["U456"])

    @pytest.mark.asyncio
    async def test_handles_dm_channel_open_failure(self):
        from src.services.agents.internal_tools.slack_tools import internal_slack_send_dm

        mock_slack_client = AsyncMock()
        mock_slack_client.conversations_open.return_value = {
            "ok": True,
            "channel": {},  # Missing id
        }

        with (
            patch(
                "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
            ) as mock_get,
            patch("src.services.slack.formatters.format_text_for_slack", return_value="Hello!"),
        ):
            mock_get.return_value = mock_slack_client

            result = await internal_slack_send_dm(user_id="U456", text="Hello!", runtime_context={"agent_id": "test"})

            assert result["success"] is False
            assert "Could not open DM channel" in result["error"]


class TestInternalSlackPostBlocks:
    """Tests for internal_slack_post_blocks function."""

    @pytest.mark.asyncio
    async def test_returns_error_without_client(self):
        from src.services.agents.internal_tools.slack_tools import internal_slack_post_blocks

        with patch(
            "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = None

            result = await internal_slack_post_blocks(channel_id="C123", blocks="[]", runtime_context={})

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_posts_blocks_successfully(self):
        from src.services.agents.internal_tools.slack_tools import internal_slack_post_blocks

        mock_slack_client = AsyncMock()
        mock_slack_client.chat_postMessage.return_value = {"ok": True, "ts": "1.1", "channel": "C123"}

        with patch(
            "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_slack_client

            result = await internal_slack_post_blocks(
                channel_id="C123",
                blocks='[{"type": "section", "text": {"type": "mrkdwn", "text": "hi"}}]',
                runtime_context={"agent_id": "test"},
            )

            assert result["success"] is True
            assert result["message_ts"] == "1.1"

    @pytest.mark.asyncio
    async def test_defaults_to_shared_state_thread_ts_when_omitted(self):
        """A tool-generated blocks post must land in the same thread as the triggering
        message — never split into the main channel — when the LLM omits thread_ts."""
        from src.services.agents.internal_tools.slack_tools import internal_slack_post_blocks

        mock_slack_client = AsyncMock()
        mock_slack_client.chat_postMessage.return_value = {"ok": True, "ts": "1.1", "channel": "C123"}

        with patch(
            "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_slack_client

            result = await internal_slack_post_blocks(
                channel_id="C123",
                blocks="[]",
                runtime_context={"agent_id": "test", "shared_state": {"slack_thread_ts": "1234567890.123456"}},
            )

            assert result["success"] is True
            call_kwargs = mock_slack_client.chat_postMessage.call_args.kwargs
            assert call_kwargs["thread_ts"] == "1234567890.123456"

    @pytest.mark.asyncio
    async def test_reuploads_unreachable_own_image_block_as_file_and_retries(self):
        """Root cause of a real 'invalid_blocks' failure: Slack's OWN servers try to
        download image_url to render an image block. Our presigned MinIO/S3 URLs are
        signed with the public endpoint (e.g. http://localhost:9000 in dev), which is
        only reachable from our own network/browser, never from Slack's infrastructure.
        Slack replies: {'error': 'invalid_blocks', 'errors': ['downloading image failed
        [json-pointer:/blocks/1/image_url]']}. Self-heal: download the image ourselves
        (it's our own storage), upload it as a file attachment instead, drop the failing
        image block, and retry posting the rest of the message."""
        from src.services.agents.internal_tools.slack_tools import internal_slack_post_blocks

        mock_slack_client = AsyncMock()
        mock_slack_client.chat_postMessage.side_effect = [
            SlackApiError(
                message="invalid_blocks",
                response={
                    "error": "invalid_blocks",
                    "errors": ["downloading image failed [json-pointer:/blocks/1/image_url]"],
                },
            ),
            {"ok": True, "ts": "1.1", "channel": "C123"},
        ]
        mock_slack_client.files_upload_v2.return_value = {
            "file": {"id": "F1", "name": "shot.png", "permalink": "https://x", "permalink_public": None}
        }
        mock_s3_storage = AsyncMock()
        mock_s3_storage.download_if_own_url.return_value = b"\x89PNG own bytes"

        blocks = json.dumps(
            [
                {"type": "section", "text": {"type": "mrkdwn", "text": "*Bug Hunt*"}},
                {
                    "type": "image",
                    "image_url": "http://localhost:9000/synkora-bucket/shot.png?X-Amz-Algorithm=foo",
                    "alt_text": "Screenshot",
                },
            ]
        )

        with (
            patch(
                "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "src.services.agents.internal_tools.slack_tools.get_s3_storage",
                return_value=mock_s3_storage,
            ),
        ):
            mock_get.return_value = mock_slack_client

            result = await internal_slack_post_blocks(
                channel_id="C123", blocks=blocks, runtime_context={"agent_id": "test"}
            )

            assert result["success"] is True
            assert mock_slack_client.chat_postMessage.call_count == 2
            retry_blocks = mock_slack_client.chat_postMessage.call_args.kwargs["blocks"]
            assert all(b.get("type") != "image" for b in retry_blocks)
            upload_kwargs = mock_slack_client.files_upload_v2.call_args.kwargs
            assert upload_kwargs["content"] == b"\x89PNG own bytes"
            assert upload_kwargs["channel"] == "C123"

    @pytest.mark.asyncio
    async def test_returns_original_error_when_unreachable_image_is_not_own_storage(self):
        """If the failing image_url isn't our own storage (S3 client can't fetch it
        either), there's nothing we can self-heal — surface the original Slack error."""
        from src.services.agents.internal_tools.slack_tools import internal_slack_post_blocks

        mock_slack_client = AsyncMock()
        mock_slack_client.chat_postMessage.side_effect = SlackApiError(
            message="invalid_blocks",
            response={
                "error": "invalid_blocks",
                "errors": ["downloading image failed [json-pointer:/blocks/0/image_url]"],
            },
        )
        mock_s3_storage = AsyncMock()
        mock_s3_storage.download_if_own_url.return_value = None

        blocks = json.dumps([{"type": "image", "image_url": "https://example.com/not-ours.png", "alt_text": "x"}])

        with (
            patch(
                "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "src.services.agents.internal_tools.slack_tools.get_s3_storage",
                return_value=mock_s3_storage,
            ),
        ):
            mock_get.return_value = mock_slack_client

            result = await internal_slack_post_blocks(
                channel_id="C123", blocks=blocks, runtime_context={"agent_id": "test"}
            )

            assert result["success"] is False
            assert "invalid_blocks" in result["error"]
            assert mock_slack_client.chat_postMessage.call_count == 1


class TestInternalSlackUploadFile:
    """Tests for internal_slack_upload_file function."""

    @pytest.mark.asyncio
    async def test_returns_error_without_client(self):
        from src.services.agents.internal_tools.slack_tools import internal_slack_upload_file

        with patch(
            "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = None

            result = await internal_slack_upload_file(
                channel_id="C123", file_content="data", filename="f.csv", runtime_context={}
            )

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_defaults_to_shared_state_thread_ts_when_omitted(self):
        from src.services.agents.internal_tools.slack_tools import internal_slack_upload_file

        mock_slack_client = AsyncMock()
        mock_slack_client.files_upload_v2.return_value = {
            "file": {"id": "F1", "name": "f.csv", "permalink": "https://x", "permalink_public": None}
        }

        with patch(
            "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_slack_client

            result = await internal_slack_upload_file(
                channel_id="C123",
                file_content="data",
                filename="f.csv",
                runtime_context={"agent_id": "test", "shared_state": {"slack_thread_ts": "1234567890.123456"}},
            )

            assert result["success"] is True
            call_kwargs = mock_slack_client.files_upload_v2.call_args.kwargs
            assert call_kwargs["thread_ts"] == "1234567890.123456"

    @pytest.mark.asyncio
    async def test_uploads_to_channel_using_singular_channel_kwarg(self):
        """Root cause of a real 'channel_not_found' failure: slack_sdk's files_upload_v2
        takes `channel: str` for a single channel and `channels: List[str]` for multiple.
        Passing a plain channel_id string as `channels` gets `",".join()`-ed character by
        character downstream in files_completeUploadExternal (e.g. "C0BRWGTBVED" ->
        "C,0,B,R,W,G,T,B,V,E,D"), which Slack correctly rejects as channel_not_found.
        We upload to exactly one channel per call, so must use the singular `channel` kwarg.
        """
        from src.services.agents.internal_tools.slack_tools import internal_slack_upload_file

        mock_slack_client = AsyncMock()
        mock_slack_client.files_upload_v2.return_value = {
            "file": {"id": "F1", "name": "f.csv", "permalink": "https://x", "permalink_public": None}
        }

        with patch(
            "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_slack_client

            result = await internal_slack_upload_file(
                channel_id="C0BRWGTBVED", file_content="data", filename="f.csv", runtime_context={"agent_id": "test"}
            )

            assert result["success"] is True
            call_kwargs = mock_slack_client.files_upload_v2.call_args.kwargs
            assert call_kwargs["channel"] == "C0BRWGTBVED"
            assert "channels" not in call_kwargs

    @pytest.mark.asyncio
    async def test_requires_file_content_or_file_url(self):
        """Root cause of the 103-retry loop: neither raw content nor a URL was
        ever provided, and the old error didn't hint at the file_url alternative."""
        from src.services.agents.internal_tools.slack_tools import internal_slack_upload_file

        mock_slack_client = AsyncMock()

        with patch(
            "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_slack_client

            result = await internal_slack_upload_file(
                channel_id="C123", filename="screenshot.png", runtime_context={"agent_id": "test"}
            )

            assert result["success"] is False
            assert "file_content" in result["error"]
            assert "file_url" in result["error"]
            mock_slack_client.files_upload_v2.assert_not_called()

    @pytest.mark.asyncio
    async def test_downloads_file_url_and_uploads_bytes_when_no_file_content(self):
        """Screenshots only ever come back as an S3 image_url (never raw bytes) -
        upload_file must be able to fetch that URL itself and attach the bytes."""
        from src.services.agents.internal_tools.slack_tools import internal_slack_upload_file

        mock_slack_client = AsyncMock()
        mock_slack_client.files_upload_v2.return_value = {
            "file": {"id": "F1", "name": "screenshot.png", "permalink": "https://x", "permalink_public": None}
        }

        with (
            patch(
                "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "src.services.agents.internal_tools.slack_tools.internal_download_url_bytes",
                new_callable=AsyncMock,
            ) as mock_download,
        ):
            mock_get.return_value = mock_slack_client
            mock_download.return_value = {"content": b"\x89PNG raw bytes", "content_type": "image/png"}

            result = await internal_slack_upload_file(
                channel_id="C123",
                filename="screenshot.png",
                file_url="https://s3.example.com/presigned/screenshot.png",
                runtime_context={"agent_id": "test"},
            )

            assert result["success"] is True
            mock_download.assert_called_once_with("https://s3.example.com/presigned/screenshot.png", config=None)
            call_kwargs = mock_slack_client.files_upload_v2.call_args.kwargs
            assert call_kwargs["content"] == b"\x89PNG raw bytes"

    @pytest.mark.asyncio
    async def test_fetches_own_s3_url_directly_bypassing_ssrf_guarded_download(self):
        """Screenshot URLs are our own presigned MinIO/S3 URLs signed with the PUBLIC
        endpoint (e.g. http://localhost:9000 in dev). Fetching that host from inside a
        container is correctly SSRF-blocked by internal_download_url_bytes. When the URL
        is provably our own storage, fetch bytes directly via the S3 client instead."""
        from src.services.agents.internal_tools.slack_tools import internal_slack_upload_file

        mock_slack_client = AsyncMock()
        mock_slack_client.files_upload_v2.return_value = {
            "file": {"id": "F1", "name": "screenshot.png", "permalink": "https://x", "permalink_public": None}
        }
        mock_s3_storage = AsyncMock()
        mock_s3_storage.download_if_own_url.return_value = b"\x89PNG own bytes"

        with (
            patch(
                "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "src.services.agents.internal_tools.slack_tools.internal_download_url_bytes",
                new_callable=AsyncMock,
            ) as mock_download,
            patch(
                "src.services.agents.internal_tools.slack_tools.get_s3_storage",
                return_value=mock_s3_storage,
            ),
        ):
            mock_get.return_value = mock_slack_client

            result = await internal_slack_upload_file(
                channel_id="C123",
                filename="screenshot.png",
                file_url="http://localhost:9000/synkora-bucket/agent-uploads/shot.png?X-Amz-Algorithm=foo",
                runtime_context={"agent_id": "test"},
            )

            assert result["success"] is True
            mock_download.assert_not_called()
            call_kwargs = mock_slack_client.files_upload_v2.call_args.kwargs
            assert call_kwargs["content"] == b"\x89PNG own bytes"

    @pytest.mark.asyncio
    async def test_falls_back_to_ssrf_guarded_download_when_url_is_not_own_storage(self):
        from src.services.agents.internal_tools.slack_tools import internal_slack_upload_file

        mock_slack_client = AsyncMock()
        mock_slack_client.files_upload_v2.return_value = {
            "file": {"id": "F1", "name": "screenshot.png", "permalink": "https://x", "permalink_public": None}
        }
        mock_s3_storage = AsyncMock()
        mock_s3_storage.download_if_own_url.return_value = None

        with (
            patch(
                "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "src.services.agents.internal_tools.slack_tools.internal_download_url_bytes",
                new_callable=AsyncMock,
            ) as mock_download,
            patch(
                "src.services.agents.internal_tools.slack_tools.get_s3_storage",
                return_value=mock_s3_storage,
            ),
        ):
            mock_get.return_value = mock_slack_client
            mock_download.return_value = {"content": b"\x89PNG raw bytes", "content_type": "image/png"}

            result = await internal_slack_upload_file(
                channel_id="C123",
                filename="screenshot.png",
                file_url="https://s3.example.com/presigned/screenshot.png",
                runtime_context={"agent_id": "test"},
            )

            assert result["success"] is True
            mock_download.assert_called_once_with("https://s3.example.com/presigned/screenshot.png", config=None)
            call_kwargs = mock_slack_client.files_upload_v2.call_args.kwargs
            assert call_kwargs["content"] == b"\x89PNG raw bytes"

    @pytest.mark.asyncio
    async def test_falls_back_to_ssrf_guarded_download_when_s3_not_configured(self):
        """If S3 isn't configured at all (get_s3_storage raises), the own-URL optimization
        must not break the existing generic download path."""
        from src.services.agents.internal_tools.slack_tools import internal_slack_upload_file

        mock_slack_client = AsyncMock()
        mock_slack_client.files_upload_v2.return_value = {
            "file": {"id": "F1", "name": "screenshot.png", "permalink": "https://x", "permalink_public": None}
        }

        with (
            patch(
                "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "src.services.agents.internal_tools.slack_tools.internal_download_url_bytes",
                new_callable=AsyncMock,
            ) as mock_download,
            patch(
                "src.services.agents.internal_tools.slack_tools.get_s3_storage",
                side_effect=ValueError("S3 bucket name must be provided"),
            ),
        ):
            mock_get.return_value = mock_slack_client
            mock_download.return_value = {"content": b"\x89PNG raw bytes", "content_type": "image/png"}

            result = await internal_slack_upload_file(
                channel_id="C123",
                filename="screenshot.png",
                file_url="https://example.com/screenshot.png",
                runtime_context={"agent_id": "test"},
            )

            assert result["success"] is True
            mock_download.assert_called_once()

    @pytest.mark.asyncio
    async def test_file_url_download_failure_returns_error(self):
        from src.services.agents.internal_tools.slack_tools import internal_slack_upload_file

        mock_slack_client = AsyncMock()

        with (
            patch(
                "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "src.services.agents.internal_tools.slack_tools.internal_download_url_bytes",
                new_callable=AsyncMock,
            ) as mock_download,
        ):
            mock_get.return_value = mock_slack_client
            mock_download.return_value = {"error": "URL blocked for security: Blocked hostname: localhost"}

            result = await internal_slack_upload_file(
                channel_id="C123",
                filename="screenshot.png",
                file_url="http://localhost/evil.png",
                runtime_context={"agent_id": "test"},
            )

            assert result["success"] is False
            assert "blocked for security" in result["error"]
            mock_slack_client.files_upload_v2.assert_not_called()

    @pytest.mark.asyncio
    async def test_prefers_file_content_over_file_url_when_both_given(self):
        from src.services.agents.internal_tools.slack_tools import internal_slack_upload_file

        mock_slack_client = AsyncMock()
        mock_slack_client.files_upload_v2.return_value = {
            "file": {"id": "F1", "name": "f.csv", "permalink": "https://x", "permalink_public": None}
        }

        with (
            patch(
                "src.services.agents.internal_tools.slack_tools._get_slack_client", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "src.services.agents.internal_tools.slack_tools.internal_download_url_bytes",
                new_callable=AsyncMock,
            ) as mock_download,
        ):
            mock_get.return_value = mock_slack_client

            result = await internal_slack_upload_file(
                channel_id="C123",
                file_content="raw data",
                filename="f.csv",
                file_url="https://example.com/should-be-ignored.csv",
                runtime_context={"agent_id": "test"},
            )

            assert result["success"] is True
            mock_download.assert_not_called()
            call_kwargs = mock_slack_client.files_upload_v2.call_args.kwargs
            assert call_kwargs["content"] == "raw data"
