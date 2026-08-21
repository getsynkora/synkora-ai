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
    platform_disable_agent_autonomous,
    platform_get_agent_autonomous,
    platform_list_database_connections,
    platform_list_knowledge_bases,
    platform_set_agent_autonomous,
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
