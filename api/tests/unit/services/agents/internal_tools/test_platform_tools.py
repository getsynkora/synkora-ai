from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.agents.internal_tools.platform_tools import (
    _resolve_slack_bot_id,
    platform_attach_database_connections,
    platform_attach_knowledge_base,
    platform_attach_mcp_server,
    platform_check_integration,
    platform_create_agent,
    platform_disable_agent_autonomous,
    platform_get_agent_autonomous,
    platform_list_database_connections,
    platform_list_knowledge_bases,
    platform_set_agent_autonomous,
    platform_update_agent,
)


class TestPlatformDatabaseConnectionTools:
    @pytest.fixture
    def runtime_context(self):
        ctx = MagicMock()
        ctx.tenant_id = uuid4()
        ctx.user_id = uuid4()
        ctx.db_session = AsyncMock(spec=AsyncSession)
        return ctx

    @pytest.fixture
    def mock_agent(self):
        agent = MagicMock()
        agent.id = uuid4()
        agent.slug = "elasticsearch-query-agent"
        agent.agent_name = "elasticsearch_query_agent"
        agent.agent_metadata = {"allowed_database_connections": []}
        return agent

    @pytest.fixture
    def mock_connection(self, runtime_context):
        conn = MagicMock()
        conn.id = uuid4()
        conn.name = "Primary Elasticsearch"
        conn.database_type = "ELASTICSEARCH"
        conn.host = "localhost"
        conn.port = 9200
        conn.database_name = "logs"
        conn.database_path = None
        conn.tenant_id = runtime_context.tenant_id
        conn.status = "active"
        return conn

    @pytest.mark.asyncio
    async def test_platform_list_database_connections_marks_attached(
        self, runtime_context, mock_agent, mock_connection
    ):
        mock_agent.agent_metadata = {"allowed_database_connections": [str(mock_connection.id)]}

        result_rows = MagicMock()
        result_rows.scalars.return_value.all.return_value = [mock_connection]
        runtime_context.db_session.execute = AsyncMock(return_value=result_rows)

        with patch(
            "src.services.agents.internal_tools.platform_tools._resolve_target_agent",
            new=AsyncMock(return_value=mock_agent),
        ):
            result = await platform_list_database_connections(
                connection_type="ELASTICSEARCH",
                agent_name=mock_agent.agent_name,
                runtime_context=runtime_context,
            )

        assert result["success"] is True
        assert result["count"] == 1
        assert result["connections"][0]["attached"] is True
        assert result["connections"][0]["type"] == "ELASTICSEARCH"

    @pytest.mark.asyncio
    async def test_platform_attach_database_connections_by_type(self, runtime_context, mock_agent, mock_connection):
        result_rows = MagicMock()
        result_rows.scalars.return_value.all.return_value = [mock_connection]
        runtime_context.db_session.execute = AsyncMock(return_value=result_rows)
        runtime_context.db_session.commit = AsyncMock()

        cache = MagicMock()
        cache.invalidate_agent = AsyncMock()

        with (
            patch(
                "src.services.agents.internal_tools.platform_tools._resolve_target_agent",
                new=AsyncMock(return_value=mock_agent),
            ),
            patch("src.services.cache.get_agent_cache", return_value=cache),
        ):
            result = await platform_attach_database_connections(
                agent_name=mock_agent.agent_name,
                connection_type="ELASTICSEARCH",
                runtime_context=runtime_context,
            )

        assert result["success"] is True
        assert result["attached_connections"][0]["name"] == "Primary Elasticsearch"
        assert str(mock_connection.id) in mock_agent.agent_metadata["allowed_database_connections"]
        runtime_context.db_session.commit.assert_awaited_once()
        cache.invalidate_agent.assert_awaited_once()


class TestPlatformKnowledgeBaseTools:
    @pytest.fixture
    def runtime_context(self):
        ctx = MagicMock()
        ctx.tenant_id = uuid4()
        ctx.user_id = uuid4()
        ctx.db_session = AsyncMock(spec=AsyncSession)
        return ctx

    @pytest.fixture
    def mock_agent(self):
        agent = MagicMock()
        agent.id = uuid4()
        agent.slug = "platform-agent"
        agent.agent_name = "platform_agent"
        return agent

    @pytest.fixture
    def mock_kb(self):
        kb = MagicMock()
        kb.id = 7
        kb.name = "Elasticsearch Docs"
        kb.description = "Indexed Elasticsearch docs"
        kb.status = "ACTIVE"
        kb.vector_db_provider = "QDRANT"
        kb.embedding_provider = "OPENAI"
        kb.total_documents = 12
        kb.total_chunks = 98
        return kb

    @pytest.mark.asyncio
    async def test_platform_list_knowledge_bases_marks_attached(self, runtime_context, mock_agent, mock_kb):
        kb_rows = MagicMock()
        kb_rows.scalars.return_value.all.return_value = [mock_kb]

        attached_rows = MagicMock()
        attached_rows.scalars.return_value.all.return_value = [mock_kb.id]

        runtime_context.db_session.execute = AsyncMock(side_effect=[kb_rows, attached_rows])

        with patch(
            "src.services.agents.internal_tools.platform_tools._resolve_target_agent",
            new=AsyncMock(return_value=mock_agent),
        ):
            result = await platform_list_knowledge_bases(
                agent_name=mock_agent.agent_name,
                runtime_context=runtime_context,
            )

        assert result["success"] is True
        assert result["count"] == 1
        assert result["knowledge_bases"][0]["attached"] is True
        assert result["knowledge_bases"][0]["name"] == "Elasticsearch Docs"

    @pytest.mark.asyncio
    async def test_platform_attach_knowledge_base_creates_link(self, runtime_context, mock_agent, mock_kb):
        kb_lookup = MagicMock()
        kb_lookup.scalar_one_or_none.return_value = mock_kb

        existing_link = MagicMock()
        existing_link.scalar_one_or_none.return_value = None

        runtime_context.db_session.execute = AsyncMock(side_effect=[kb_lookup, existing_link])
        runtime_context.db_session.add = MagicMock()
        runtime_context.db_session.commit = AsyncMock()

        with patch(
            "src.services.agents.internal_tools.platform_tools._resolve_target_agent",
            new=AsyncMock(return_value=mock_agent),
        ):
            result = await platform_attach_knowledge_base(
                agent_name=mock_agent.agent_name,
                knowledge_base_id=mock_kb.id,
                retrieval_config={"max_results": 5},
                runtime_context=runtime_context,
            )

        assert result["success"] is True
        assert result["knowledge_base_name"] == mock_kb.name
        runtime_context.db_session.add.assert_called_once()
        runtime_context.db_session.commit.assert_awaited_once()


class TestPlatformMCPAndAutonomousTools:
    @pytest.fixture
    def runtime_context(self):
        ctx = MagicMock()
        ctx.tenant_id = uuid4()
        ctx.user_id = uuid4()
        ctx.db_session = AsyncMock(spec=AsyncSession)
        return ctx

    @pytest.fixture
    def mock_agent(self):
        agent = MagicMock()
        agent.id = uuid4()
        agent.slug = "elasticsearch-query-agent"
        agent.agent_name = "elasticsearch_query_agent"
        agent.autonomous_enabled = False
        return agent

    @pytest.fixture
    def mock_mcp_server(self, runtime_context):
        server = MagicMock()
        server.id = uuid4()
        server.name = "Elastic MCP"
        server.tenant_id = runtime_context.tenant_id
        return server

    @pytest.mark.asyncio
    async def test_platform_attach_mcp_server_creates_link(self, runtime_context, mock_agent, mock_mcp_server):
        server_lookup = MagicMock()
        server_lookup.scalar_one_or_none.return_value = mock_mcp_server

        existing_link = MagicMock()
        existing_link.scalar_one_or_none.return_value = None

        runtime_context.db_session.execute = AsyncMock(side_effect=[server_lookup, existing_link])
        runtime_context.db_session.add = MagicMock()
        runtime_context.db_session.commit = AsyncMock()

        with patch(
            "src.services.agents.internal_tools.platform_tools._resolve_target_agent",
            new=AsyncMock(return_value=mock_agent),
        ):
            result = await platform_attach_mcp_server(
                agent_name=mock_agent.agent_name,
                mcp_server_id=str(mock_mcp_server.id),
                mcp_config={"timeout": 30},
                runtime_context=runtime_context,
            )

        assert result["success"] is True
        assert result["mcp_server_name"] == mock_mcp_server.name
        runtime_context.db_session.add.assert_called_once()
        runtime_context.db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_platform_set_agent_autonomous_creates_task(self, runtime_context, mock_agent):
        existing_task = MagicMock()
        existing_task.scalar_one_or_none.return_value = None

        runtime_context.db_session.execute = AsyncMock(return_value=existing_task)
        runtime_context.db_session.add = MagicMock()
        runtime_context.db_session.commit = AsyncMock()
        runtime_context.db_session.refresh = AsyncMock()

        with (
            patch(
                "src.services.agents.internal_tools.platform_tools._resolve_target_agent",
                new=AsyncMock(return_value=mock_agent),
            ),
            patch(
                "src.schemas.autonomous_agent.parse_schedule",
                return_value={"schedule_type": "interval", "interval_seconds": 3600},
            ),
        ):
            result = await platform_set_agent_autonomous(
                agent_name=mock_agent.agent_name,
                goal="Run Elasticsearch checks every hour",
                schedule="hourly",
                runtime_context=runtime_context,
            )

        assert result["success"] is True
        assert result["enabled"] is True
        assert mock_agent.autonomous_enabled is True
        runtime_context.db_session.add.assert_called_once()
        runtime_context.db_session.commit.assert_awaited_once()
        runtime_context.db_session.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_platform_get_agent_autonomous_returns_task_state(self, runtime_context, mock_agent):
        task = MagicMock()
        task.id = uuid4()
        task.config = {
            "goal": "Run Elasticsearch checks every hour",
            "max_steps": 15,
            "require_approval": True,
            "approval_mode": "explicit",
            "approval_channel": "chat",
        }
        task.cron_expression = None
        task.interval_seconds = 3600
        task.schedule_type = "interval"
        task.is_active = True

        task_row = MagicMock()
        task_row.scalar_one_or_none.return_value = task
        runtime_context.db_session.execute = AsyncMock(return_value=task_row)
        mock_agent.autonomous_enabled = True

        with patch(
            "src.services.agents.internal_tools.platform_tools._resolve_target_agent",
            new=AsyncMock(return_value=mock_agent),
        ):
            result = await platform_get_agent_autonomous(
                agent_name=mock_agent.agent_name,
                runtime_context=runtime_context,
            )

        assert result["success"] is True
        assert result["configured"] is True
        assert result["enabled"] is True
        assert result["schedule"] == 3600
        assert result["approval_mode"] == "explicit"

    @pytest.mark.asyncio
    async def test_platform_disable_agent_autonomous_deletes_task(self, runtime_context, mock_agent):
        task = MagicMock()
        task_row = MagicMock()
        task_row.scalar_one_or_none.return_value = task

        runtime_context.db_session.execute = AsyncMock(return_value=task_row)
        runtime_context.db_session.delete = AsyncMock()
        runtime_context.db_session.commit = AsyncMock()
        mock_agent.autonomous_enabled = True

        with patch(
            "src.services.agents.internal_tools.platform_tools._resolve_target_agent",
            new=AsyncMock(return_value=mock_agent),
        ):
            result = await platform_disable_agent_autonomous(
                agent_name=mock_agent.agent_name,
                delete_task=True,
                runtime_context=runtime_context,
            )

        assert result["success"] is True
        assert result["enabled"] is False
        assert mock_agent.autonomous_enabled is False
        runtime_context.db_session.delete.assert_awaited_once_with(task)
        runtime_context.db_session.commit.assert_awaited_once()


class TestResolveSlackBotId:
    """A SlackBot connected to one agent must never be silently reused as the
    Slack credential for a different agent — each agent needs its own bot."""

    @pytest.mark.asyncio
    async def test_does_not_fall_back_to_another_agents_bot(self):
        db = AsyncMock(spec=AsyncSession)
        agent_scoped_result = MagicMock()
        agent_scoped_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=agent_scoped_result)

        tenant_id = uuid4()
        this_agent_id = uuid4()

        result = await _resolve_slack_bot_id(db, tenant_id, this_agent_id)

        assert result is None
        # Only the agent-scoped lookup should run — no tenant-wide fallback query.
        db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_bot_linked_to_this_agent(self):
        db = AsyncMock(spec=AsyncSession)
        bot_id = uuid4()
        agent_scoped_result = MagicMock()
        agent_scoped_result.scalar_one_or_none.return_value = bot_id
        db.execute = AsyncMock(return_value=agent_scoped_result)

        result = await _resolve_slack_bot_id(db, uuid4(), uuid4())

        assert result == bot_id

    @pytest.mark.asyncio
    async def test_no_agent_id_returns_none_without_querying(self):
        db = AsyncMock(spec=AsyncSession)
        db.execute = AsyncMock()

        result = await _resolve_slack_bot_id(db, uuid4(), None)

        assert result is None
        db.execute.assert_not_awaited()


class TestPlatformCheckIntegrationSlack:
    """platform_check_integration('slack') must not report connected:True based on
    another agent's SlackBot — that previously caused the Platform Engineer to tell
    users 'Slack OAuth is already connected' when it wasn't."""

    @pytest.fixture
    def runtime_context(self):
        ctx = MagicMock()
        ctx.tenant_id = uuid4()
        ctx.user_id = uuid4()
        ctx.db_session = AsyncMock(spec=AsyncSession)
        return ctx

    @pytest.mark.asyncio
    async def test_returns_not_connected_when_only_other_agents_bot_exists(self, runtime_context):
        empty_result = MagicMock()
        empty_result.first.return_value = None
        empty_result.scalar_one_or_none.return_value = None
        runtime_context.db_session.execute = AsyncMock(return_value=empty_result)

        result = await platform_check_integration(provider="slack", runtime_context=runtime_context)

        assert result["connected"] is False


class TestPlatformCreateAgentSlug:
    """platform_create_agent must always set Agent.slug — the chat-builder creation path
    previously only set agent_name, leaving slug NULL and breaking /agents/<slug>/* routing."""

    @pytest.fixture
    def runtime_context(self):
        ctx = MagicMock()
        ctx.tenant_id = uuid4()
        ctx.user_id = uuid4()
        ctx.db_session = AsyncMock(spec=AsyncSession)
        ctx.conversation_id = None
        return ctx

    @staticmethod
    def _no_match_result():
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        return result

    @pytest.mark.asyncio
    async def test_generates_slug_from_name(self, runtime_context):
        db = runtime_context.db_session
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.execute = AsyncMock(side_effect=[self._no_match_result(), self._no_match_result()])

        with patch("src.services.billing.plan_restriction_service.PlanRestrictionService") as MockRestriction:
            MockRestriction.return_value.enforce_agent_limit = AsyncMock()

            result = await platform_create_agent(
                name="Product Agent!",
                description="desc",
                system_prompt="prompt",
                llm_provider="openai",
                llm_model="gpt-4o",
                api_key="sk-test",
                runtime_context=runtime_context,
            )

        assert result["success"] is True
        assert result["slug"] == "product-agent"
        created_agent = db.add.call_args_list[0].args[0]
        assert created_agent.slug == "product-agent"

    @pytest.mark.asyncio
    async def test_appends_suffix_on_slug_collision(self, runtime_context):
        """Agent.slug is unique across ALL tenants (unlike agent_name, per-tenant only) —
        a collision must be disambiguated rather than raising an IntegrityError later."""
        db = runtime_context.db_session
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()

        slug_conflict = MagicMock()
        slug_conflict.scalar_one_or_none.return_value = MagicMock()  # another agent already has this slug
        db.execute = AsyncMock(side_effect=[self._no_match_result(), slug_conflict])

        with patch("src.services.billing.plan_restriction_service.PlanRestrictionService") as MockRestriction:
            MockRestriction.return_value.enforce_agent_limit = AsyncMock()

            result = await platform_create_agent(
                name="Product Agent",
                description="desc",
                system_prompt="prompt",
                llm_provider="openai",
                llm_model="gpt-4o",
                api_key="sk-test",
                runtime_context=runtime_context,
            )

        assert result["success"] is True
        assert result["slug"] != "product-agent"
        assert result["slug"].startswith("product-agent-")


class TestPlatformUpdateAgentSlug:
    """platform_update_agent's slug param lets Platform Engineer backfill agents created
    before slug generation existed, but only while the slug is still unset — slugs are
    otherwise immutable (mirrors the REST update endpoint's immutable-slug rule)."""

    @pytest.fixture
    def runtime_context(self):
        ctx = MagicMock()
        ctx.tenant_id = uuid4()
        ctx.user_id = uuid4()
        ctx.db_session = AsyncMock(spec=AsyncSession)
        return ctx

    @pytest.fixture
    def mock_agent(self):
        agent = MagicMock()
        agent.id = uuid4()
        agent.agent_name = "product_agent"
        agent.slug = None
        agent.status = "ACTIVE"
        return agent

    @staticmethod
    def _result_for(value):
        result = MagicMock()
        result.scalar_one_or_none.return_value = value
        return result

    @pytest.mark.asyncio
    async def test_sets_slug_when_currently_unset(self, runtime_context, mock_agent):
        db = runtime_context.db_session
        db.commit = AsyncMock()

        existing_llm = MagicMock(api_key="enc-key", provider="openai", model_name="gpt-4o", api_base=None)
        existing_llm.additional_params = {}
        db.execute = AsyncMock(
            side_effect=[
                self._result_for(mock_agent),  # agent lookup by agent_name
                self._result_for(None),  # slug uniqueness check: no conflict
                self._result_for(existing_llm),  # existing AgentLLMConfig already has an api_key
            ]
        )

        result = await platform_update_agent(
            agent_name="product_agent", slug="  Product Agent!! ", runtime_context=runtime_context
        )

        assert result["success"] is True
        assert result["slug"] == "product-agent"
        assert mock_agent.slug == "product-agent"
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_refuses_to_change_an_already_set_slug(self, runtime_context, mock_agent):
        mock_agent.slug = "already-set"
        db = runtime_context.db_session
        db.commit = AsyncMock()
        db.execute = AsyncMock(return_value=self._result_for(mock_agent))

        result = await platform_update_agent(
            agent_name="product_agent", slug="new-slug", runtime_context=runtime_context
        )

        assert result["success"] is False
        assert "already-set" in result["message"]
        assert mock_agent.slug == "already-set"  # unchanged
        db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_refuses_slug_already_used_by_another_agent(self, runtime_context, mock_agent):
        db = runtime_context.db_session
        db.commit = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                self._result_for(mock_agent),  # agent lookup
                self._result_for(MagicMock()),  # slug taken by a different agent
            ]
        )

        result = await platform_update_agent(
            agent_name="product_agent", slug="taken-slug", runtime_context=runtime_context
        )

        assert result["success"] is False
        assert mock_agent.slug is None  # left untouched
        db.commit.assert_not_awaited()
