# Block Slack Bot in Externally-Shared Channels — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-bot, default-off toggle (`allow_external_shared_channels`) that blocks a Slack bot from responding in Slack Connect (externally-shared) channels unless a tenant admin explicitly turns it on.

**Architecture:** One new boolean column on `SlackBot` (default `False`), a single enforcement check moved to the top of `SlackMessageHandler.handle_message()` (the shared entry point for both Socket Mode and Event Mode), pass-through in the `SlackBotManager` + `slack_bots` controller/schemas, and a checkbox on the create/edit bot forms.

**Tech Stack:** FastAPI + SQLAlchemy + Alembic (backend), Next.js/React (frontend), pytest (tests).

**Spec:** `docs/superpowers/specs/2026-08-13-slack-external-shared-channel-block-design.md`

---

### Task 1: Alembic migration — add `allow_external_shared_channels` column

**Files:**
- Create: `api/migrations/versions/20260813_0001_add_allow_external_shared_channels.py`

- [ ] **Step 1: Write the migration**

Follow the exact idempotent pattern used in `api/migrations/versions/20260516_0001_add_created_by_to_slack_bots.py`. The current head revision is `95b0831fc354` (file `20260701_0001_context_file_load_mode.py`) — confirmed via grep that no other migration file has `down_revision = "95b0831fc354"`.

```python
"""add allow_external_shared_channels to slack_bots

Revision ID: 20260813_0001
Revises: 95b0831fc354
Create Date: 2026-08-13

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260813_0001"
down_revision = "95b0831fc354"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = bind.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='slack_bots' AND column_name='allow_external_shared_channels'"
        )
    ).fetchone()
    if not existing:
        op.add_column(
            "slack_bots",
            sa.Column(
                "allow_external_shared_channels",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade() -> None:
    pass
```

Note: `server_default=sa.false()` is required (unlike the `created_by` example) because this column is `nullable=False` — existing rows need a default value at the DB level for the `ADD COLUMN` to succeed.

- [ ] **Step 2: Verify migration applies**

Run: `cd api && alembic upgrade head`
Expected: no errors; `alembic current` shows `20260813_0001 (head)`.

- [ ] **Step 3: Commit**

```bash
cd api
git add migrations/versions/20260813_0001_add_allow_external_shared_channels.py
git commit -m "feat: add allow_external_shared_channels column to slack_bots"
```

---

### Task 2: Model — add field to `SlackBot`

**Files:**
- Modify: `api/src/models/slack_bot.py`

- [ ] **Step 1: Add the column to the model**

In `api/src/models/slack_bot.py`, add directly below the existing `is_active` column (around line 41):

```python
    is_active = Column(Boolean, default=True, nullable=False)
    allow_external_shared_channels = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="If False (default), bot refuses to respond in Slack Connect / externally-shared channels",
    )
```

- [ ] **Step 2: Verify import**

Run: `cd api && python -c "from src.models.slack_bot import SlackBot; print(SlackBot.allow_external_shared_channels)"`
Expected: prints the SQLAlchemy `InstrumentedAttribute` with no import errors.

- [ ] **Step 3: Commit**

```bash
cd api
git add src/models/slack_bot.py
git commit -m "feat: add allow_external_shared_channels field to SlackBot model"
```

---

### Task 3: `SlackBotManager` — pass the field through `create_bot()` / `update_bot()`

**Files:**
- Modify: `api/src/services/slack/slack_bot_manager.py`
- Test: `api/tests/unit/services/slack/test_slack_bot_manager.py`

- [ ] **Step 1: Write the failing tests**

Add to `api/tests/unit/services/slack/test_slack_bot_manager.py`, inside `TestSlackBotManager`:

```python
    @pytest.mark.asyncio
    async def test_create_bot_default_blocks_external_shared(self, manager, mock_db_session):
        with patch("src.services.slack.slack_bot_manager.encrypt_value", return_value="enc"):
            result = await manager.create_bot(
                agent_id=uuid4(),
                tenant_id=uuid4(),
                bot_name="New Bot",
                slack_app_id="A123",
                slack_bot_token="xoxb-token",
                slack_app_token="xapp-token",
            )

        assert result.allow_external_shared_channels is False

    @pytest.mark.asyncio
    async def test_create_bot_allow_external_shared_channels_true(self, manager, mock_db_session):
        with patch("src.services.slack.slack_bot_manager.encrypt_value", return_value="enc"):
            result = await manager.create_bot(
                agent_id=uuid4(),
                tenant_id=uuid4(),
                bot_name="New Bot",
                slack_app_id="A123",
                slack_bot_token="xoxb-token",
                slack_app_token="xapp-token",
                allow_external_shared_channels=True,
            )

        assert result.allow_external_shared_channels is True

    @pytest.mark.asyncio
    async def test_update_bot_allow_external_shared_channels(self, manager, mock_db_session, mock_slack_bot):
        mock_db_session.get.return_value = mock_slack_bot
        mock_slack_bot.allow_external_shared_channels = False

        await manager.update_bot(bot_id=mock_slack_bot.id, allow_external_shared_channels=True)

        assert mock_slack_bot.allow_external_shared_channels is True
```

Also add `bot.allow_external_shared_channels = False` to the `mock_slack_bot` fixture (it uses `MagicMock(spec=SlackBot)`, so the attribute must be set explicitly once it exists on the spec'd class — otherwise it returns an unset `MagicMock` instance instead of a real bool).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd api && pytest tests/unit/services/slack/test_slack_bot_manager.py -v -k "allow_external_shared"`
Expected: FAIL — `create_bot() got an unexpected keyword argument 'allow_external_shared_channels'` (and similarly for `update_bot`).

- [ ] **Step 3: Implement `create_bot()` change**

In `api/src/services/slack/slack_bot_manager.py`, add the parameter to the signature (after `created_by`):

```python
    async def create_bot(
        self,
        agent_id: UUID,
        tenant_id: UUID,
        bot_name: str,
        slack_app_id: str,
        slack_bot_token: str,
        slack_app_token: str | None = None,
        slack_workspace_id: str | None = None,
        slack_workspace_name: str | None = None,
        connection_mode: str = "socket",
        signing_secret: str | None = None,
        created_by: UUID | None = None,
        allow_external_shared_channels: bool = False,
    ) -> SlackBot:
```

And set it on the constructed `SlackBot` (next to `is_active=True`):

```python
            slack_bot = SlackBot(
                agent_id=agent_id,
                tenant_id=tenant_id,
                bot_name=bot_name,
                slack_app_id=slack_app_id,
                slack_bot_token=encrypted_bot_token,
                slack_app_token=encrypted_app_token,
                slack_workspace_id=slack_workspace_id,
                slack_workspace_name=slack_workspace_name,
                connection_mode=connection_mode,
                signing_secret=encrypted_signing_secret,
                is_active=True,
                allow_external_shared_channels=allow_external_shared_channels,
                connection_status="connected" if connection_mode == "event" else "disconnected",
                created_by=created_by,
            )
```

- [ ] **Step 4: Implement `update_bot()` change**

Add the parameter to the signature (after `is_active`):

```python
    async def update_bot(
        self,
        bot_id: UUID,
        bot_name: str | None = None,
        slack_bot_token: str | None = None,
        slack_app_token: str | None = None,
        signing_secret: str | None = None,
        is_active: bool | None = None,
        allow_external_shared_channels: bool | None = None,
    ) -> SlackBot:
```

And add the conditional-set block (next to the `is_active` block):

```python
            if allow_external_shared_channels is not None:
                slack_bot.allow_external_shared_channels = allow_external_shared_channels
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd api && pytest tests/unit/services/slack/test_slack_bot_manager.py -v`
Expected: PASS (all tests, including the 3 new ones).

- [ ] **Step 6: Commit**

```bash
cd api
git add src/services/slack/slack_bot_manager.py tests/unit/services/slack/test_slack_bot_manager.py
git commit -m "feat: pass allow_external_shared_channels through SlackBotManager"
```

---

### Task 4: Controller — schemas + endpoints

**Files:**
- Modify: `api/src/controllers/slack_bots.py`
- Test: `api/tests/unit/controllers/test_slack_bots.py`

- [ ] **Step 1: Write the failing tests**

Add to `api/tests/unit/controllers/test_slack_bots.py`. First, update `_create_mock_slack_bot()` to set the new attribute (needed since it's a bare `MagicMock()` and `SlackBotResponse` requires a real `bool`):

```python
    bot.allow_external_shared_channels = False
```

(add this line inside `_create_mock_slack_bot`, next to `bot.is_active = True`)

Then add new test cases:

```python
class TestCreateSlackBot:
    ...
    def test_create_slack_bot_allow_external_shared_channels(self, client):
        """Test creating a bot with allow_external_shared_channels=True."""
        test_client, tenant_id, mock_account, mock_db, mock_manager = client
        manager_instance = mock_manager.return_value

        agent_id = uuid.uuid4()
        mock_bot = _create_mock_slack_bot(tenant_id, agent_id)
        mock_bot.allow_external_shared_channels = True
        manager_instance.create_bot = AsyncMock(return_value=mock_bot)

        response = test_client.post(
            "/slack-bots",
            json={
                "agent_id": str(agent_id),
                "bot_name": "Test Slack Bot",
                "slack_app_id": "A12345678",
                "slack_bot_token": "xoxb-test-token",
                "slack_app_token": "xapp-test-token",
                "allow_external_shared_channels": True,
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["allow_external_shared_channels"] is True
        manager_instance.create_bot.assert_called_once()
        assert manager_instance.create_bot.call_args.kwargs["allow_external_shared_channels"] is True

    def test_create_slack_bot_default_allow_external_shared_channels_false(self, client):
        """Test that omitting the field defaults to False."""
        test_client, tenant_id, mock_account, mock_db, mock_manager = client
        manager_instance = mock_manager.return_value

        agent_id = uuid.uuid4()
        mock_bot = _create_mock_slack_bot(tenant_id, agent_id)
        manager_instance.create_bot = AsyncMock(return_value=mock_bot)

        response = test_client.post(
            "/slack-bots",
            json={
                "agent_id": str(agent_id),
                "bot_name": "Test Slack Bot",
                "slack_app_id": "A12345678",
                "slack_bot_token": "xoxb-test-token",
                "slack_app_token": "xapp-test-token",
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert manager_instance.create_bot.call_args.kwargs["allow_external_shared_channels"] is False
```

And in `TestUpdateSlackBot`:

```python
    def test_update_slack_bot_allow_external_shared_channels(self, client):
        """Test updating allow_external_shared_channels."""
        test_client, tenant_id, mock_account, mock_db, mock_manager = client
        manager_instance = mock_manager.return_value

        bot_id = uuid.uuid4()
        mock_bot = _create_mock_slack_bot(tenant_id, uuid.uuid4())
        mock_bot.id = bot_id
        mock_bot.allow_external_shared_channels = True
        manager_instance.get_bot = AsyncMock(return_value=mock_bot)
        manager_instance.update_bot = AsyncMock(return_value=mock_bot)

        response = test_client.put(
            f"/slack-bots/{bot_id}", json={"allow_external_shared_channels": True}
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["allow_external_shared_channels"] is True
        assert manager_instance.update_bot.call_args.kwargs["allow_external_shared_channels"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd api && pytest tests/unit/controllers/test_slack_bots.py -v -k "allow_external_shared"`
Expected: FAIL — `KeyError: 'allow_external_shared_channels'` on `response.json()`, since the field doesn't exist on the schema yet.

- [ ] **Step 3: Implement schema + endpoint changes**

In `api/src/controllers/slack_bots.py`:

`SlackBotCreate` — add after `signing_secret`:
```python
    allow_external_shared_channels: bool = Field(
        default=False,
        description="If False (default), bot refuses to respond in Slack Connect / externally-shared channels",
    )
```

`SlackBotUpdate` — add after `is_active`:
```python
    allow_external_shared_channels: bool | None = None
```

`SlackBotResponse` — add after `is_active`:
```python
    allow_external_shared_channels: bool
```

`create_slack_bot()` — pass through in the `manager.create_bot()` call (after `signing_secret=bot_data.signing_secret,`):
```python
            allow_external_shared_channels=bot_data.allow_external_shared_channels,
```
and in the constructed `SlackBotResponse(...)` (after `is_active=slack_bot.is_active,`):
```python
            allow_external_shared_channels=slack_bot.allow_external_shared_channels,
```

`list_slack_bots()` — add to the `SlackBotResponse(...)` construction in the list comprehension (after `is_active=bot.is_active,`):
```python
            allow_external_shared_channels=bot.allow_external_shared_channels,
```

`get_slack_bot()` — add to its `SlackBotResponse(...)` construction (after `is_active=bot.is_active,`):
```python
        allow_external_shared_channels=bot.allow_external_shared_channels,
```

`update_slack_bot()` — pass through in the `manager.update_bot()` call (after `is_active=bot_data.is_active,`):
```python
            allow_external_shared_channels=bot_data.allow_external_shared_channels,
```
and in the constructed `SlackBotResponse(...)` (after `is_active=updated_bot.is_active,`):
```python
            allow_external_shared_channels=updated_bot.allow_external_shared_channels,
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd api && pytest tests/unit/controllers/test_slack_bots.py -v`
Expected: PASS (all tests, including the 3 new ones).

- [ ] **Step 5: Add an integration test for persistence**

Add to `api/tests/integration/test_slack_bots_integration.py`, inside `TestSlackBotsCRUDIntegration` (this suite requires the real test DB — `docker-compose exec api pytest` or the `postgres-test` service on port 5433; it follows the existing lenient status-code pattern used by the rest of this file since bot creation can fail for unrelated reasons like worker deployment):

```python
    def test_create_slack_bot_persists_allow_external_shared_channels(
        self, client: TestClient, db_session: Session, auth_headers, test_agent
    ):
        """Test that allow_external_shared_channels is persisted and defaults to False."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id, account = auth_headers

        # Omit the field — should default to False
        response = client.post(
            "/api/v1/slack-bots",
            json={
                "agent_id": test_agent,
                "bot_name": f"Default Flag Bot {uuid.uuid4().hex[:8]}",
                "slack_app_id": "A12345690",
                "slack_bot_token": "xoxb-test-token-default",
                "slack_app_token": "xapp-test-token-default",
            },
            headers=headers,
        )

        if response.status_code == status.HTTP_201_CREATED:
            data = response.json()
            assert data["allow_external_shared_channels"] is False

            # Explicitly enable it via update, then confirm persistence on GET
            bot_id = data["id"]
            update_response = client.put(
                f"/api/v1/slack-bots/{bot_id}",
                json={"allow_external_shared_channels": True},
                headers=headers,
            )
            if update_response.status_code == status.HTTP_200_OK:
                assert update_response.json()["allow_external_shared_channels"] is True

                get_response = client.get(f"/api/v1/slack-bots/{bot_id}", headers=headers)
                assert get_response.status_code == status.HTTP_200_OK
                assert get_response.json()["allow_external_shared_channels"] is True
```

- [ ] **Step 6: Run the integration test**

Run: `cd api && docker-compose exec api pytest tests/integration/test_slack_bots_integration.py -v -k "allow_external_shared_channels"` (or `pytest tests/integration/test_slack_bots_integration.py -v -k allow_external_shared_channels` directly if the local `postgres-test` service on port 5433 is reachable)
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
cd api
git add src/controllers/slack_bots.py tests/unit/controllers/test_slack_bots.py tests/integration/test_slack_bots_integration.py
git commit -m "feat: add allow_external_shared_channels to slack-bots API"
```

---

### Task 5: Enforcement — `SlackMessageHandler.handle_message()`

**Files:**
- Modify: `api/src/services/slack/slack_message_handler.py`
- Create: `api/tests/unit/services/slack/test_slack_message_handler.py`

- [ ] **Step 1: Write the failing tests**

Create `api/tests/unit/services/slack/test_slack_message_handler.py`:

```python
"""Tests for SlackMessageHandler externally-shared-channel blocking."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.slack_bot import SlackBot
from src.services.slack.slack_message_handler import SlackMessageHandler


@pytest.fixture
def mock_db_session():
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.rollback = AsyncMock()
    session.get = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def handler(mock_db_session):
    return SlackMessageHandler(db_session=mock_db_session, agent_manager=MagicMock())


@pytest.fixture
def mock_slack_bot():
    bot = MagicMock(spec=SlackBot)
    bot.id = uuid4()
    bot.agent_id = uuid4()
    bot.tenant_id = uuid4()
    bot.slack_app_id = "A123"
    bot.created_by = None
    bot.allow_external_shared_channels = False
    return bot


@pytest.fixture
def mock_client():
    client = AsyncMock()
    return client


class TestExternalSharedChannelBlock:
    @pytest.mark.asyncio
    async def test_blocked_when_ext_shared_and_not_allowed(self, handler, mock_slack_bot, mock_client, mock_db_session):
        mock_client.conversations_info = AsyncMock(
            return_value={"channel": {"is_ext_shared": True, "is_org_shared": False}}
        )
        say = AsyncMock()

        result = await handler.handle_message(
            slack_bot=mock_slack_bot,
            channel_id="C123",
            user_id="U123",
            text="hello",
            message_ts="123.456",
            thread_ts=None,
            client=mock_client,
            say=say,
        )

        say.assert_called_once()
        assert "externally-shared channels" in say.call_args.args[0]
        mock_db_session.add.assert_not_called()
        mock_db_session.commit.assert_not_called()
        assert result is not None

    @pytest.mark.asyncio
    async def test_blocked_uses_chat_postmessage_when_no_say(
        self, handler, mock_slack_bot, mock_client, mock_db_session
    ):
        mock_client.conversations_info = AsyncMock(
            return_value={"channel": {"is_ext_shared": True, "is_org_shared": False}}
        )
        mock_client.chat_postMessage = AsyncMock()

        await handler.handle_message(
            slack_bot=mock_slack_bot,
            channel_id="C123",
            user_id="U123",
            text="hello",
            message_ts="123.456",
            thread_ts="100.000",
            client=mock_client,
            say=None,
        )

        mock_client.chat_postMessage.assert_called_once()
        assert mock_client.chat_postMessage.call_args.kwargs["thread_ts"] == "100.000"
        mock_db_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_allowed_when_flag_enabled(self, handler, mock_slack_bot, mock_client, mock_db_session):
        mock_slack_bot.allow_external_shared_channels = True
        mock_client.conversations_info = AsyncMock(
            return_value={"channel": {"is_ext_shared": True, "is_org_shared": False}}
        )
        mock_client.users_info = AsyncMock(side_effect=Exception("no scope"))

        # Force the flow to bail out cleanly right after the top-of-handler check,
        # so we only assert the check was *skipped*, not the full downstream flow.
        handler._get_or_create_conversation = AsyncMock(side_effect=RuntimeError("stop-here"))
        say = AsyncMock()

        result = await handler.handle_message(
            slack_bot=mock_slack_bot,
            channel_id="C123",
            user_id="U123",
            text="hello",
            message_ts="123.456",
            thread_ts=None,
            client=mock_client,
            say=say,
        )

        # The blocking decline message must NOT have been sent.
        for call in say.call_args_list:
            assert "externally-shared channels" not in call.args[0]
        assert result is None  # generic error path returns None after RuntimeError

    @pytest.mark.asyncio
    async def test_allowed_when_not_externally_shared(self, handler, mock_slack_bot, mock_client, mock_db_session):
        mock_client.conversations_info = AsyncMock(
            return_value={"channel": {"is_ext_shared": False, "is_org_shared": False}}
        )
        handler._get_or_create_conversation = AsyncMock(side_effect=RuntimeError("stop-here"))
        say = AsyncMock()

        await handler.handle_message(
            slack_bot=mock_slack_bot,
            channel_id="C123",
            user_id="U123",
            text="hello",
            message_ts="123.456",
            thread_ts=None,
            client=mock_client,
            say=say,
        )

        for call in say.call_args_list:
            assert "externally-shared channels" not in call.args[0]

    @pytest.mark.asyncio
    async def test_fails_open_when_conversations_info_raises(
        self, handler, mock_slack_bot, mock_client, mock_db_session
    ):
        mock_client.conversations_info = AsyncMock(side_effect=Exception("missing scope"))
        handler._get_or_create_conversation = AsyncMock(side_effect=RuntimeError("stop-here"))
        say = AsyncMock()

        await handler.handle_message(
            slack_bot=mock_slack_bot,
            channel_id="C123",
            user_id="U123",
            text="hello",
            message_ts="123.456",
            thread_ts=None,
            client=mock_client,
            say=say,
        )

        # Fail-open: normal flow proceeds (reaches _get_or_create_conversation, which raises)
        handler._get_or_create_conversation.assert_called_once()
        for call in say.call_args_list:
            assert "externally-shared channels" not in call.args[0]

    @pytest.mark.asyncio
    async def test_org_shared_is_not_blocked(self, handler, mock_slack_bot, mock_client, mock_db_session):
        """is_org_shared (same Enterprise Grid org) must NOT trigger the block."""
        mock_client.conversations_info = AsyncMock(
            return_value={"channel": {"is_ext_shared": False, "is_org_shared": True}}
        )
        handler._get_or_create_conversation = AsyncMock(side_effect=RuntimeError("stop-here"))
        say = AsyncMock()

        await handler.handle_message(
            slack_bot=mock_slack_bot,
            channel_id="C123",
            user_id="U123",
            text="hello",
            message_ts="123.456",
            thread_ts=None,
            client=mock_client,
            say=say,
        )

        handler._get_or_create_conversation.assert_called_once()
```

Note: tests 3-6 rely on `_get_or_create_conversation` raising to short-circuit the rest of the (long) normal flow — this is the cheapest way to assert "the block was skipped and normal flow was reached" without mocking the entire downstream chat pipeline. The generic `except Exception` handler in `handle_message` catches the `RuntimeError`, calls `_send_response` (via `say`), and returns `None` — that's why we assert on `result is None` and inspect `say.call_args_list` for the *absence* of the decline text rather than asserting no calls at all.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd api && pytest tests/unit/services/slack/test_slack_message_handler.py -v`
Expected: FAIL on the blocked-case tests (no blocking logic exists yet); the "allowed"/"fails open" tests should already pass since normal flow is unmodified.

- [ ] **Step 3: Implement the enforcement check**

In `api/src/services/slack/slack_message_handler.py`, insert this block as the very first statement inside the `try:` in `handle_message()` (before the emoji-feedback intercept, i.e. right after the docstring's closing `"""` and `try:`):

```python
        try:
            # Block Slack Connect (externally-shared) channels unless explicitly allowed.
            # is_ext_shared = true external company; is_org_shared = same Enterprise Grid
            # org (not external) and must NOT be blocked.
            channel_info: Any = None
            try:
                channel_info = await client.conversations_info(channel=channel_id)
            except Exception as e:
                logger.warning(
                    f"Could not fetch channel info for {channel_id} (external-share check): {e}. "
                    "Failing open — missing channels:read/groups:read scope?"
                )
                channel_info = None

            if (
                channel_info
                and channel_info.get("channel", {}).get("is_ext_shared")
                and not slack_bot.allow_external_shared_channels
            ):
                decline_msg = (
                    "This bot isn't available in externally-shared channels. An admin can enable "
                    "this for this bot in its settings if this is expected."
                )
                if say:
                    await say(decline_msg)
                else:
                    await client.chat_postMessage(
                        channel=channel_id,
                        text=decline_msg,
                        thread_ts=thread_ts or message_ts,
                    )
                return decline_msg

            # Feedback: intercept 👍/👎 as per-message satisfaction signal
```

- [ ] **Step 4: Reuse `channel_info` in the later parallel fetch**

Replace the existing parallel-fetch block (originally around lines 173-192) so it reuses the `channel_info` fetched at the top instead of calling `conversations_info` a second time:

Old:
```python
            # Fetch user and channel info in parallel (suppress individual failures)
            user_info: Any
            channel_info: Any
            user_info, channel_info = await asyncio.gather(
                client.users_info(user=user_id),
                client.conversations_info(channel=channel_id),
                return_exceptions=True,
            )
            if isinstance(user_info, Exception):
                logger.warning(f"Could not fetch user info for {user_id}: {user_info}. Missing users:read scope?")
                user_name = user_id
            else:
                user_name = user_info["user"]["real_name"] or user_info["user"]["name"]
            if isinstance(channel_info, Exception):
                logger.warning(
                    f"Could not fetch channel info for {channel_id}: {channel_info}. Missing channels:read scope?"
                )
                channel_name = channel_id
            else:
                channel_name = channel_info.get("channel", {}).get("name", channel_id)
```

New:
```python
            # Fetch user info (channel_info was already fetched above for the
            # external-share check, so only one call is needed here now).
            try:
                user_info = await client.users_info(user=user_id)
                user_name = user_info["user"]["real_name"] or user_info["user"]["name"]
            except Exception as e:
                logger.warning(f"Could not fetch user info for {user_id}: {e}. Missing users:read scope?")
                user_name = user_id
            if channel_info:
                channel_name = channel_info.get("channel", {}).get("name", channel_id)
            else:
                channel_name = channel_id
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd api && pytest tests/unit/services/slack/test_slack_message_handler.py -v`
Expected: PASS (all 6 tests).

Run the full existing Slack test suite to confirm no regression:
Run: `cd api && pytest tests/unit/services/slack/ tests/unit/controllers/test_slack_bots.py -v`
Expected: PASS (all tests).

- [ ] **Step 6: Commit**

```bash
cd api
git add src/services/slack/slack_message_handler.py tests/unit/services/slack/test_slack_message_handler.py
git commit -m "feat: block Slack bot in externally-shared channels by default"
```

---

### Task 6: Frontend — create-bot page toggle

**Files:**
- Modify: `web/app/(dashboard)/agents/[agentName]/slack-bots/create/page.tsx`

- [ ] **Step 1: Add the field to `formData` state**

In the `useState` call (around line 15), add `allow_external_shared_channels: false` after `signing_secret: ""`:

```tsx
  const [formData, setFormData] = useState({
    bot_name: "",
    slack_app_id: "",
    slack_bot_token: "",
    slack_app_token: "",
    slack_workspace_id: "",
    slack_workspace_name: "",
    connection_mode: "socket",
    signing_secret: "",
    allow_external_shared_channels: false,
  });
```

- [ ] **Step 2: Add a checkbox-specific change handler**

The existing `handleChange` only handles `input`/`textarea` value changes generically. Add a small dedicated handler for the checkbox (checkboxes need `e.target.checked`, not `e.target.value`):

```tsx
  const handleCheckboxChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.checked,
    });
  };
```

- [ ] **Step 3: Include the field in the create payload**

In `handleSubmit`, add to the `botData` object (after `connection_mode: formData.connection_mode,`):

```tsx
      const botData: any = {
        agent_id: agent.id,
        bot_name: formData.bot_name,
        slack_app_id: formData.slack_app_id,
        slack_bot_token: formData.slack_bot_token,
        connection_mode: formData.connection_mode,
        allow_external_shared_channels: formData.allow_external_shared_channels,
      };
```

- [ ] **Step 4: Add the checkbox UI**

Insert this block right before the "Auto-detection notice" div (after the closing `)}` of the Event Mode Notice block, before `{/* Auto-detection notice */}`):

```tsx
            {/* External Shared Channels Toggle */}
            <div className="rounded-[1.2rem] border border-black/10 bg-[#fcfaf5] p-4">
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  name="allow_external_shared_channels"
                  checked={formData.allow_external_shared_channels}
                  onChange={handleCheckboxChange}
                  className="mt-0.5 h-4 w-4 rounded border-gray-300 text-[#171717] focus:ring-[#79dfbc]"
                />
                <div>
                  <span className="text-sm font-semibold text-gray-900">
                    Allow in externally-shared channels (Slack Connect)
                  </span>
                  <p className="mt-1 text-xs text-gray-600">
                    When off (recommended), the bot won't respond in channels shared with another
                    company's Slack workspace. Turn this on only if you intentionally want this bot
                    available to external Slack Connect members.
                  </p>
                </div>
              </label>
            </div>
```

- [ ] **Step 5: Verify build**

Run: `cd web && pnpm type-check`
Expected: no new TypeScript errors.

- [ ] **Step 6: Commit**

```bash
cd web
git add "app/(dashboard)/agents/[agentName]/slack-bots/create/page.tsx"
git commit -m "feat: add externally-shared-channels toggle to Slack bot create form"
```

---

### Task 7: Frontend — edit-bot page toggle

**Files:**
- Modify: `web/app/(dashboard)/agents/[agentName]/slack-bots/[botId]/edit/page.tsx`

- [ ] **Step 1: Add the field to the `SlackBot` interface**

```tsx
interface SlackBot {
  id: string;
  bot_name: string;
  slack_app_id: string;
  slack_workspace_id: string | null;
  slack_workspace_name: string | null;
  connection_mode: string;
  connection_status: string;
  webhook_url: string | null;
  is_active: boolean;
  allow_external_shared_channels: boolean;
}
```

- [ ] **Step 2: Add the field to `formData` state and populate it on load**

```tsx
  const [formData, setFormData] = useState({
    bot_name: "",
    slack_bot_token: "",
    slack_app_token: "",
    signing_secret: "",
    allow_external_shared_channels: false,
  });
```

In `loadBot()`, add to the `setFormData` call:

```tsx
      setFormData({
        bot_name: botData.bot_name || "",
        slack_bot_token: "", // Don't populate for security
        slack_app_token: "", // Don't populate for security
        signing_secret: "", // Don't populate for security
        allow_external_shared_channels: botData.allow_external_shared_channels ?? false,
      });
```

- [ ] **Step 3: Add a checkbox-specific change handler**

```tsx
  const handleCheckboxChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.checked,
    });
  };
```

- [ ] **Step 4: Include the field in the update payload**

In `handleSubmit`, add to `updateData` (it's always included, not conditionally, since it's a plain boolean toggle rather than an optional secret):

```tsx
      const updateData: any = {
        bot_name: formData.bot_name,
        allow_external_shared_channels: formData.allow_external_shared_channels,
      };
```

- [ ] **Step 5: Add the checkbox UI**

Insert this block right before the "Help Link" div (after the closing of the Event Mode Signing Secret conditional block, before `{/* Help Link */}`):

```tsx
            {/* External Shared Channels Toggle */}
            <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  name="allow_external_shared_channels"
                  checked={formData.allow_external_shared_channels}
                  onChange={handleCheckboxChange}
                  className="mt-0.5 h-4 w-4 rounded border-gray-300 text-red-600 focus:ring-red-500"
                />
                <div>
                  <span className="text-sm font-medium text-gray-900">
                    Allow in externally-shared channels (Slack Connect)
                  </span>
                  <p className="mt-1 text-xs text-gray-500">
                    When off (recommended), the bot won't respond in channels shared with another
                    company's Slack workspace. Turn this on only if you intentionally want this bot
                    available to external Slack Connect members.
                  </p>
                </div>
              </label>
            </div>
```

- [ ] **Step 6: Verify build**

Run: `cd web && pnpm type-check`
Expected: no new TypeScript errors.

- [ ] **Step 7: Commit**

```bash
cd web
git add "app/(dashboard)/agents/[agentName]/slack-bots/[botId]/edit/page.tsx"
git commit -m "feat: add externally-shared-channels toggle to Slack bot edit form"
```

---

### Task 8: Full regression pass

**Files:** none (verification only)

- [ ] **Step 1: Run the full backend Slack test suite**

Run: `cd api && pytest tests/unit/services/slack/ tests/unit/controllers/test_slack_bots.py tests/integration/test_slack_bots_integration.py -v`
Expected: PASS (all tests).

- [ ] **Step 2: Run backend linting**

Run: `cd api && ruff check src/models/slack_bot.py src/services/slack/slack_bot_manager.py src/services/slack/slack_message_handler.py src/controllers/slack_bots.py migrations/versions/20260813_0001_add_allow_external_shared_channels.py`
Expected: no errors.

- [ ] **Step 3: Run frontend lint**

Run: `cd web && pnpm lint`
Expected: no new errors on the two modified files.

- [ ] **Step 4: Final commit (if any lint fixes were needed)**

```bash
git add -A
git commit -m "chore: fix lint issues for externally-shared-channels toggle"
```

(Skip this step if Steps 1-3 produced no changes.)
