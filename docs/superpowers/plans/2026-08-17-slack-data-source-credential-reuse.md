# Slack Data Source Credential Reuse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user connect a Slack data source using an already-connected `SlackBot` (agent Slack integration) instead of being forced through Slack OAuth app setup again, and fix the frontend bug where having zero OAuth apps silently strands the user with no error message.

**Architecture:** Add a nullable `slack_bot_id` FK column to `DataSource`, thread it through `CreateDataSourceRequest`/`create_data_source()`, add a new first-priority branch in `SlackConnector._get_access_token()` that resolves the token from the linked `SlackBot.slack_bot_token` (already encrypted the same way as OAuth tokens — both use `src.services.agents.security.{encrypt_value,decrypt_value}`), and update the frontend connect wizard to offer "use an existing Slack bot" alongside "set up OAuth", with a real error message instead of silent failure when no OAuth apps exist.

**Tech Stack:** SQLAlchemy, Alembic, FastAPI, Next.js/React, pytest, existing `apiClient.getSlackBots()`.

---

## Context (verified, no placeholders)

- `api/src/models/data_source.py` (`DataSource(BaseModel, TimestampMixin)`, 138 lines for the class, read in full): no `slack_bot_id` column exists today. Existing FK pattern to follow (`oauth_app_id`, lines 78-80):
  ```python
  oauth_app_id: Mapped[int | None] = mapped_column(
      Integer, ForeignKey("oauth_apps.id", ondelete="SET NULL"), nullable=True
  )
  ```
  and its relationship (line 120): `oauth_app: Mapped[Optional["OAuthApp"]] = relationship("OAuthApp")`.
- `api/src/models/slack_bot.py` (`SlackBot(Base)`, 105 lines, read in full): PK is `id = Column(UUID(as_uuid=True), primary_key=True, ...)` — **UUID, not int** — so the new FK column must be `UUID(as_uuid=True)`, not `Integer`. Token field: `slack_bot_token = Column(Text, nullable=False, comment="Encrypted bot token (xoxb-*)")` — already encrypted via the same `src.services.agents.security.encrypt_value`/`decrypt_value` helpers used for OAuth tokens (confirmed in `api/src/services/slack/slack_bot_manager.py:74`: `encrypted_bot_token = encrypt_value(slack_bot_token)`).
- `api/src/controllers/data_sources.py` (875 lines, read in full):
  - `CreateDataSourceRequest` (lines 33-40):
    ```python
    class CreateDataSourceRequest(BaseModel):
        """Request model for creating a data source."""

        name: str = Field(..., min_length=1, max_length=255)
        type: DataSourceType
        knowledge_base_id: int
        config: dict = Field(default_factory=dict)
        oauth_app_id: int | None = None
    ```
  - `build_data_source_response()` (lines 107-132) is the **single** response-construction function used by every endpoint (list/get/create/update all call it) — unlike `knowledge_bases.py`, there is only one site to update here.
  - `create_data_source()` (lines 171-263) real body: verifies KB exists, builds `config` dict, if `request.oauth_app_id` verifies the OAuth app + user/company token exists, sets `initial_status = DataSourceStatus.ACTIVE if request.oauth_app_id else DataSourceStatus.INACTIVE`, then constructs `DataSource(name=, type=, knowledge_base_id=, tenant_id=, config=, oauth_app_id=, status=)` (lines 233-241).
- `api/src/services/data_sources/slack_connector.py` (570 lines, read in full): `_get_access_token()` (lines 58-122) resolution order today: (1) `UserOAuthToken` via `oauth_app_id` + `config["connected_by_account_id"]`, (2) `self.data_source.access_token_encrypted`, (3) `self.data_source.oauth_app.access_token`. No `SlackBot` branch exists.
- `web/lib/api/client.ts`: `apiClient.getSlackBots: typeof slackBots.getSlackBots` already wired (line 196, 431) — `getSlackBots(agentId?: string): Promise<any[]>` (`web/lib/api/slack-bots.ts:3-7`) calls `GET /api/v1/slack-bots` (no `agent_id` param needed here — data sources aren't scoped to one agent). Backend `list_slack_bots()` (`api/src/controllers/slack_bots.py:138-170`) returns `list[SlackBotResponse]` with fields `id, agent_id, tenant_id, bot_name, slack_app_id, slack_workspace_id, slack_workspace_name, is_active, connection_status, connection_mode, ...` (all tenant-scoped via `get_current_tenant_id`, confirmed no cross-tenant leak).
- `web/app/(dashboard)/data-sources/connect/page.tsx` (read in full): the real bug is in `handleTypeSelect()`/`handleKbSelect()` (lines 194-218):
  ```typescript
  const handleTypeSelect = async (type: string) => {
    setSelectedType(type)
    const defaultName = `${type.charAt(0).toUpperCase() + type.slice(1)} Data Source`
    setDataSourceName(defaultName)

    if (selectedKbId) {
      const hasOAuthApps = await fetchOAuthApps(type)
      if (hasOAuthApps) {
        setStep('configure')
      }
      // BUG: if hasOAuthApps is false, nothing happens — no error, no fallback, user is stuck
    } else {
      setStep('select-kb')
    }
  }

  const handleKbSelect = async (kbId: number) => {
    setSelectedKbId(kbId)
    const hasOAuthApps = await fetchOAuthApps(selectedType)
    if (hasOAuthApps) {
      setStep('configure')
    }
    // Same bug here
  }
  ```
  `fetchOAuthApps()` (lines 122-141) returns `apps.length > 0`. `handleConnect()` (lines 224-263) currently requires `selectedOAuthAppId` unconditionally (line 230-233) and posts `{name, type, knowledge_base_id, config, oauth_app_id}` (line 249-255) via `apiClient.createDataSource(...)`.
- Migration template (`api/migrations/versions/20260813_0001_add_allow_external_shared_channels.py`, read in full) — exact idempotent pattern used throughout this codebase:
  ```python
  def upgrade() -> None:
      bind = op.get_bind()
      existing = bind.execute(
          sa.text(
              "SELECT column_name FROM information_schema.columns "
              "WHERE table_name='<table>' AND column_name='<column>'"
          )
      ).fetchone()
      if not existing:
          op.add_column("<table>", sa.Column("<column>", <type>, nullable=True))
  ```
  Current migration head confirmed via grep of every file's `down_revision`: **`20260813_0002`** (no file has it as a `down_revision`, so nothing is ahead of it).

## Task 1: Add `slack_bot_id` column to `DataSource`

**Files:**
- Modify: `api/src/models/data_source.py`
- Create: `api/migrations/versions/20260817_0001_add_slack_bot_id_to_data_sources.py`

- [ ] **Step 1: Add the column and relationship to the model**

In `api/src/models/data_source.py`, add the new column right after `oauth_app_id`/`refresh_token_encrypted`/`token_expires_at` (after line 83, before the `# Configuration` comment at line 85):

```python
    # Alternative credential source: reuse an existing agent's Slack bot connection
    # instead of requiring a separate Slack OAuth app for this data source.
    slack_bot_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("slack_bots.id", ondelete="SET NULL"), nullable=True
    )
```

Add the relationship next to the existing `oauth_app` relationship (line 120):

```python
    oauth_app: Mapped[Optional["OAuthApp"]] = relationship("OAuthApp")
    slack_bot: Mapped[Optional["SlackBot"]] = relationship("SlackBot")
```

- [ ] **Step 2: Write the migration**

Create `api/migrations/versions/20260817_0001_add_slack_bot_id_to_data_sources.py`:

```python
"""add slack_bot_id to data_sources

Revision ID: 20260817_0001
Revises: 20260813_0002
Create Date: 2026-08-17

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260817_0001"
down_revision = "20260813_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = bind.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='data_sources' AND column_name='slack_bot_id'"
        )
    ).fetchone()
    if not existing:
        op.add_column(
            "data_sources",
            sa.Column(
                "slack_bot_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("slack_bots.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )


def downgrade() -> None:
    pass
```

- [ ] **Step 3: Run the migration**

Run: `docker compose exec -T api alembic upgrade head`
Expected: Migration applies cleanly, ends at revision `20260817_0001`.

- [ ] **Step 4: Verify the column exists**

Run: `docker compose exec -T api python -c "
from sqlalchemy import inspect, create_engine
import os
e = create_engine(os.environ['DATABASE_URL'].replace('+asyncpg', ''))
cols = [c['name'] for c in inspect(e).get_columns('data_sources')]
print('slack_bot_id' in cols)
"`
Expected output: `True`

- [ ] **Step 5: Commit**

```bash
git add api/src/models/data_source.py api/migrations/versions/20260817_0001_add_slack_bot_id_to_data_sources.py
git commit -m "feat: add slack_bot_id column to data_sources"
```

## Task 2: Accept `slack_bot_id` in `CreateDataSourceRequest` and construction

**Files:**
- Modify: `api/src/controllers/data_sources.py`
- Test: `api/tests/unit/controllers/test_data_sources.py`

- [ ] **Step 1: Write the failing test**

Add to `api/tests/unit/controllers/test_data_sources.py`, inside `class TestCreateDataSource`:

```python
    def test_create_data_source_with_slack_bot_id(self, client):
        """Test creating a Slack data source that reuses an existing SlackBot's credentials."""
        test_client, tenant_id, mock_db = client

        kb_id = 1
        ds_id = 1
        slack_bot_id = str(uuid.uuid4())

        mock_kb = _create_mock_knowledge_base(kb_id, tenant_id)
        mock_bot = MagicMock()
        mock_bot.id = slack_bot_id
        mock_bot.tenant_id = tenant_id
        mock_ds = _create_mock_data_source(ds_id, tenant_id, kb_id, name="Reused Bot Source")
        mock_ds.slack_bot_id = slack_bot_id

        call_count = [0]

        def execute_side_effect(*args, **kwargs):
            call_count[0] += 1
            mock_result = MagicMock()
            if call_count[0] == 1:
                mock_result.scalar_one_or_none.return_value = mock_kb
            elif call_count[0] == 2:
                mock_result.scalar_one_or_none.return_value = mock_bot
            else:
                mock_result.scalar_one.return_value = mock_ds
            return mock_result

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)
        mock_db.add = MagicMock()

        response = test_client.post(
            "/data-sources",
            json={
                "name": "Reused Bot Source",
                "type": "SLACK",
                "knowledge_base_id": kb_id,
                "config": {"channels": ["general"]},
                "slack_bot_id": slack_bot_id,
            },
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_create_data_source_slack_bot_not_found(self, client):
        """Test creating a data source with a non-existent slack_bot_id."""
        test_client, tenant_id, mock_db = client

        kb_id = 1
        mock_kb = _create_mock_knowledge_base(kb_id, tenant_id)

        call_count = [0]

        def execute_side_effect(*args, **kwargs):
            call_count[0] += 1
            mock_result = MagicMock()
            if call_count[0] == 1:
                mock_result.scalar_one_or_none.return_value = mock_kb
            else:
                mock_result.scalar_one_or_none.return_value = None
            return mock_result

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)

        response = test_client.post(
            "/data-sources",
            json={
                "name": "Test Source",
                "type": "SLACK",
                "knowledge_base_id": kb_id,
                "config": {},
                "slack_bot_id": str(uuid.uuid4()),
            },
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T api pytest tests/unit/controllers/test_data_sources.py -v -k slack_bot`
Expected: FAIL — `CreateDataSourceRequest` doesn't accept `slack_bot_id` yet (Pydantic will silently ignore unknown fields by default rather than error, so the real failure is the 404 test expecting a lookup that doesn't happen, and the success test failing on `initial_status`/missing SlackBot verification).

- [ ] **Step 3: Add `slack_bot_id` to the request model and construction logic**

In `api/src/controllers/data_sources.py`, update `CreateDataSourceRequest` (lines 33-40):

```python
class CreateDataSourceRequest(BaseModel):
    """Request model for creating a data source."""

    name: str = Field(..., min_length=1, max_length=255)
    type: DataSourceType
    knowledge_base_id: int
    config: dict = Field(default_factory=dict)
    oauth_app_id: int | None = None
    slack_bot_id: str | None = None
```

In `create_data_source()`, insert a new verification block right after the existing `oauth_app_id` verification block (after line 228, `config["connected_by_account_id"] = str(current_account.id)`, before `# Determine initial status` at line 230):

```python
        # Verify Slack bot if provided (reuse an existing agent's Slack connection)
        slack_bot_uuid = None
        if request.slack_bot_id:
            from uuid import UUID as UUIDType

            from src.models.slack_bot import SlackBot

            try:
                slack_bot_uuid = UUIDType(request.slack_bot_id)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid slack_bot_id")

            result = await db.execute(
                select(SlackBot).filter(SlackBot.id == slack_bot_uuid, SlackBot.tenant_id == tenant_id)
            )
            slack_bot = result.scalar_one_or_none()

            if not slack_bot:
                raise HTTPException(status_code=404, detail="Slack bot not found")

            if request.type != DataSourceType.SLACK:
                raise HTTPException(status_code=400, detail="slack_bot_id can only be used with type=SLACK")
```

Update `initial_status` (line 231) to also treat a linked Slack bot as an active credential source:

```python
        # Determine initial status
        initial_status = (
            DataSourceStatus.ACTIVE if (request.oauth_app_id or slack_bot_uuid) else DataSourceStatus.INACTIVE
        )
```

Update the `DataSource(...)` construction (lines 233-241) to pass it through:

```python
        data_source = DataSource(
            name=request.name,
            type=request.type,
            knowledge_base_id=request.knowledge_base_id,
            tenant_id=tenant_id,
            config=config,
            oauth_app_id=request.oauth_app_id,
            slack_bot_id=slack_bot_uuid,
            status=initial_status,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T api pytest tests/unit/controllers/test_data_sources.py -v`
Expected: All tests PASS, including the 2 new ones and no regressions in the rest of the file.

- [ ] **Step 5: Commit**

```bash
git add api/src/controllers/data_sources.py api/tests/unit/controllers/test_data_sources.py
git commit -m "feat: accept slack_bot_id to reuse existing Slack bot credentials for data sources"
```

## Task 3: Resolve Slack token from `SlackBot` in `SlackConnector`

**Files:**
- Modify: `api/src/services/data_sources/slack_connector.py`
- Test: `api/tests/unit/services/agents/internal_tools/test_git_helpers.py` — **not applicable here**; create a new test file instead.
- Test: Create `api/tests/unit/services/data_sources/test_slack_connector.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/unit/services/data_sources/test_slack_connector.py`:

```python
"""Tests for SlackConnector._get_access_token() SlackBot resolution."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.services.data_sources.slack_connector import SlackConnector


@pytest.mark.asyncio
async def test_get_access_token_uses_slack_bot_when_linked():
    """When data_source.slack_bot_id is set, resolve the token from the SlackBot row."""
    data_source = MagicMock()
    data_source.slack_bot_id = uuid4()
    data_source.oauth_app_id = None
    data_source.access_token_encrypted = None

    mock_bot = MagicMock()
    mock_bot.slack_bot_token = "encrypted-bot-token"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_bot

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    connector = SlackConnector(data_source, mock_db)

    with patch("src.services.agents.security.decrypt_value", return_value="xoxb-real-token") as mock_decrypt:
        token = await connector._get_access_token()

    assert token == "xoxb-real-token"
    mock_decrypt.assert_called_once_with("encrypted-bot-token")


@pytest.mark.asyncio
async def test_get_access_token_falls_back_when_no_slack_bot():
    """When slack_bot_id is None, existing oauth/direct-token resolution still works unchanged."""
    data_source = MagicMock()
    data_source.slack_bot_id = None
    data_source.oauth_app_id = None
    data_source.access_token_encrypted = "encrypted-direct-token"

    mock_db = AsyncMock()

    connector = SlackConnector(data_source, mock_db)

    with patch("src.services.agents.security.decrypt_value", return_value="xoxb-direct-token") as mock_decrypt:
        token = await connector._get_access_token()

    assert token == "xoxb-direct-token"
    mock_decrypt.assert_called_once_with("encrypted-direct-token")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/unit/services/data_sources/test_slack_connector.py -v`
Expected: `test_get_access_token_uses_slack_bot_when_linked` FAILS (no SlackBot branch exists, falls through to `access_token_encrypted` which is `None`, returns `None` instead of the bot token). `test_get_access_token_falls_back_when_no_slack_bot` should already PASS (verifying no regression).

- [ ] **Step 3: Add the SlackBot resolution branch**

In `api/src/services/data_sources/slack_connector.py`, insert a new first-priority branch at the top of `_get_access_token()` (immediately after the docstring at line 66, before `# First, try to get user's personal token if OAuth app is linked` at line 72), and update the docstring's priority list:

```python
    async def _get_access_token(self) -> str | None:
        """
        Get decrypted access token using user-first resolution.

        Priority:
        1. Linked SlackBot's own bot token (data_source.slack_bot_id), reusing an
           existing agent's Slack connection instead of a separate OAuth app
        2. User's personal OAuth token (from UserOAuthToken table)
        3. Data source's direct access_token_encrypted
        4. OAuth app's admin token (fallback)
        """
        from uuid import UUID as UUIDType

        from src.models.user_oauth_token import UserOAuthToken
        from src.services.agents.security import decrypt_value

        # First, reuse an existing agent's Slack bot connection if linked
        if self.data_source.slack_bot_id:
            from src.models.slack_bot import SlackBot

            result = await self.db.execute(select(SlackBot).filter(SlackBot.id == self.data_source.slack_bot_id))
            slack_bot = result.scalar_one_or_none()

            if slack_bot and slack_bot.slack_bot_token:
                logger.info(f"Using linked SlackBot token for data source {self.data_source.name}")
                return decrypt_value(slack_bot.slack_bot_token)

        # Then, try to get user's personal token if OAuth app is linked
        if self.data_source.oauth_app_id:
```

(The `UUIDType` import is unused by this new branch but stays — it's still used further down for `account_id_str` conversion in the existing OAuth-token branch.)

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/unit/services/data_sources/test_slack_connector.py -v`
Expected: Both tests PASS.

Also run the full connector test suite to confirm no regression: `docker compose exec -T api pytest tests/unit/services/data_sources/ -v` (if this directory doesn't exist yet, `docker compose exec -T api pytest tests/unit/ -v -k slack_connector` as a fallback — confirm which applies by checking `ls api/tests/unit/services/data_sources/` first).

- [ ] **Step 5: Commit**

```bash
git add api/src/services/data_sources/slack_connector.py api/tests/unit/services/data_sources/test_slack_connector.py
git commit -m "feat: resolve Slack token from linked SlackBot before OAuth app"
```

## Task 4: Fix frontend silent-stuck bug and add "use existing Slack bot" option

**Files:**
- Modify: `web/app/(dashboard)/data-sources/connect/page.tsx`

- [ ] **Step 1: Add Slack bot state and fetch logic**

Add a new interface and state near the existing `OAuthApp` interface/state (after line 22's `interface OAuthApp {...}` and near line 61-62's `oauthApps`/`selectedOAuthAppId` state):

```typescript
interface SlackBot {
  id: string
  bot_name: string
  slack_workspace_name: string | null
  connection_status: string
}
```

```typescript
  const [slackBots, setSlackBots] = useState<SlackBot[]>([])
  const [selectedSlackBotId, setSelectedSlackBotId] = useState<string | null>(null)
  const [useExistingSlackBot, setUseExistingSlackBot] = useState(false)
```

- [ ] **Step 2: Fetch Slack bots and fix the silent-stuck bug**

Replace `fetchOAuthApps()` (lines 122-141) with a version that also fetches Slack bots when the type is `SLACK`, and update `handleTypeSelect()`/`handleKbSelect()` to show an error instead of silently doing nothing when there are zero OAuth apps AND zero Slack bots:

```typescript
  const fetchOAuthApps = async (provider: string) => {
    setCheckingOAuth(true)
    try {
      const data = await apiClient.getOAuthApps(provider)
      const apps = Array.isArray(data) ? data : []
      setOauthApps(apps)

      if (apps.length === 1) {
        setSelectedOAuthAppId(apps[0].id)
      }

      let hasSlackBots = false
      if (provider === 'SLACK') {
        const bots = await apiClient.getSlackBots()
        const activeBots = (Array.isArray(bots) ? bots : []).filter(
          (b: SlackBot) => b.connection_status === 'connected'
        )
        setSlackBots(activeBots)
        hasSlackBots = activeBots.length > 0
        if (activeBots.length === 1) {
          setSelectedSlackBotId(activeBots[0].id)
          setUseExistingSlackBot(true)
        }
      }

      return apps.length > 0 || hasSlackBots
    } catch (err) {
      console.error('Failed to fetch OAuth apps:', err)
      return false
    } finally {
      setCheckingOAuth(false)
    }
  }
```

Update `handleTypeSelect()` (lines 194-209) and `handleKbSelect()` (lines 211-218) to surface an error instead of silently stalling:

```typescript
  const handleTypeSelect = async (type: string) => {
    setSelectedType(type)
    const defaultName = `${type.charAt(0).toUpperCase() + type.slice(1)} Data Source`
    setDataSourceName(defaultName)

    if (selectedKbId) {
      const hasCredentials = await fetchOAuthApps(type)
      if (hasCredentials) {
        setStep('configure')
      } else {
        setError(
          `No connected ${type} account found. Please connect an OAuth app (or a Slack bot) for ${type} first.`
        )
      }
    } else {
      setStep('select-kb')
    }
  }

  const handleKbSelect = async (kbId: number) => {
    setSelectedKbId(kbId)
    const hasCredentials = await fetchOAuthApps(selectedType)
    if (hasCredentials) {
      setStep('configure')
    } else {
      setError(
        `No connected ${selectedType} account found. Please connect an OAuth app (or a Slack bot) for ${selectedType} first.`
      )
    }
  }
```

- [ ] **Step 3: Update `handleConnect()` to support the Slack-bot path**

Replace `handleConnect()` (lines 224-263):

```typescript
  const handleConnect = async () => {
    if (!selectedType || !selectedKbId || !dataSourceName.trim()) {
      setError('Please provide a name for the data source')
      return
    }

    const usingSlackBot = selectedType === 'SLACK' && useExistingSlackBot && selectedSlackBotId
    if (!usingSlackBot && !selectedOAuthAppId) {
      setError('Please select an OAuth app or an existing Slack bot')
      return
    }

    setLoading(true)
    setError(null)

    try {
      let sourceConfig
      if (selectedType === 'SLACK') {
        sourceConfig = slackConfig
      } else if (selectedType === 'GMAIL') {
        sourceConfig = gmailConfig
      } else if (selectedType === 'GITHUB') {
        sourceConfig = githubConfig
      }

      await apiClient.createDataSource({
        name: dataSourceName.trim(),
        type: selectedType,
        knowledge_base_id: selectedKbId,
        config: sourceConfig,
        oauth_app_id: usingSlackBot ? null : selectedOAuthAppId,
        slack_bot_id: usingSlackBot ? selectedSlackBotId : null,
      })

      router.push('/data-sources')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
      setLoading(false)
    }
  }
```

- [ ] **Step 4: Add the "use existing Slack bot" toggle to the configure step UI**

In the `'configure'` step JSX (the section rendering OAuth app selection — locate the block that renders `oauthApps.map(...)` inside the configure step), add a toggle above it, shown only `selectedType === 'SLACK' && slackBots.length > 0`:

```tsx
                {selectedType === 'SLACK' && slackBots.length > 0 && (
                  <div className="mb-5 space-y-3">
                    <div className="flex gap-3">
                      <button
                        type="button"
                        onClick={() => setUseExistingSlackBot(true)}
                        className={`flex-1 rounded-[1.1rem] border px-4 py-3 text-sm font-semibold transition-all ${
                          useExistingSlackBot
                            ? 'border-[#d7bea3] bg-[#f6ede4] text-gray-900'
                            : 'border-gray-200 bg-white text-gray-600'
                        }`}
                      >
                        Use existing Slack bot
                      </button>
                      <button
                        type="button"
                        onClick={() => setUseExistingSlackBot(false)}
                        className={`flex-1 rounded-[1.1rem] border px-4 py-3 text-sm font-semibold transition-all ${
                          !useExistingSlackBot
                            ? 'border-[#d7bea3] bg-[#f6ede4] text-gray-900'
                            : 'border-gray-200 bg-white text-gray-600'
                        }`}
                      >
                        Set up new OAuth app
                      </button>
                    </div>

                    {useExistingSlackBot && (
                      <select
                        value={selectedSlackBotId || ''}
                        onChange={(e) => setSelectedSlackBotId(e.target.value)}
                        className="w-full rounded-[1rem] border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-900"
                      >
                        <option value="" disabled>
                          Select a Slack bot
                        </option>
                        {slackBots.map((bot) => (
                          <option key={bot.id} value={bot.id}>
                            {bot.bot_name} {bot.slack_workspace_name ? `(${bot.slack_workspace_name})` : ''}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>
                )}
```

The existing OAuth-app-selection block in that same step should be wrapped so it only renders when `!(selectedType === 'SLACK' && useExistingSlackBot)`, since selecting an existing Slack bot makes OAuth app selection redundant.

- [ ] **Step 5: Manual verification**

This page has no existing frontend unit test file (`web/` uses Next.js without a component test harness for this route per repo convention) — verify manually per `agent-test-docs/` convention:
1. `pnpm dev` in `web/`, log in, navigate to a Knowledge Base, click "Connect Data Source" → select Slack.
2. With zero Slack OAuth apps and zero connected Slack bots configured for the tenant: confirm the page now shows the new error message instead of silently doing nothing.
3. With at least one connected `SlackBot` (create one via `/agents/{slug}/tools` → Slack integration, or via `POST /api/v1/slack-bots`) and zero OAuth apps: confirm the wizard advances to `'configure'`, the "Use existing Slack bot"/"Set up new OAuth app" toggle appears, selecting a bot and clicking Connect creates the data source successfully with `slack_bot_id` set (verify via `GET /api/v1/data-sources/{id}`).
4. Write up the exact steps and results in `agent-test-docs/slack-data-source-credential-reuse-test-guide.md` per the project's `agent-test-docs/` convention (real endpoints hit, real responses observed — not speculative).

- [ ] **Step 6: Commit**

```bash
git add "web/app/(dashboard)/data-sources/connect/page.tsx" agent-test-docs/slack-data-source-credential-reuse-test-guide.md
git commit -m "feat: allow reusing an existing Slack bot when connecting a Slack data source"
```

## Self-Review Notes

- **Spec coverage:** Covers Phase 1.2 of `docs/superpowers/specs/2026-08-17-company-brain-kb-unification-design.md` in full: backend `slack_bot_id` column + credential resolution, and the frontend silent-stuck bug fix + "use existing Slack bot" UI path.
- **No placeholders:** All code is complete; the one open item (exact OAuth-app-selection JSX block boundaries in Step 4) is a wrap-with-condition edit on existing code, not new logic — the engineer executing this step reads the surrounding ~20 lines in the file (already partially quoted in Context above) to find the exact wrap points.
- **Type consistency:** `slack_bot_id: str | None` in the Pydantic request model (JSON strings) vs. `slack_bot_uuid: UUID | None` after parsing in the controller vs. `slack_bot_id: Mapped[str | None]` (UUID column) on the model — consistent with how `oauth_app_id`/`tenant_id` are handled elsewhere in this codebase (Pydantic sees strings, SQLAlchemy stores UUID objects).
