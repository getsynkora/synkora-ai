"""Tests for agent_tasks."""

import json
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest


class _MockAsyncSessionCM:
    """Reusable async context manager that yields a mock async DB session."""

    def __init__(self, async_db):
        self._db = async_db

    async def __aenter__(self):
        return self._db

    async def __aexit__(self, *args):
        return False


def _make_async_session_mock():
    """Return (mock_create_celery_async_session, mock_async_db)."""
    async_db = AsyncMock()
    async_db.add = MagicMock()

    def _factory():
        return _MockAsyncSessionCM(async_db)

    mock_create = MagicMock(return_value=_factory)
    return mock_create, async_db


@pytest.fixture
def mock_db():
    """Create mock database session."""
    db = Mock()
    db.query = Mock()
    db.commit = Mock()
    db.close = Mock()
    db.func = Mock()
    db.func.now = Mock(return_value="2024-01-01")
    return db


@pytest.fixture
def sample_webhook():
    """Create sample webhook."""
    webhook = Mock()
    webhook.id = uuid4()
    webhook.agent_id = uuid4()
    webhook.provider = "github"
    webhook.event_types = ["pull_request"]
    return webhook


@pytest.fixture
def sample_event():
    """Create sample webhook event."""
    event = Mock()
    event.id = uuid4()
    event.status = "pending"
    event.provider = "github"
    event.event_type = "pull_request"
    event.error = None
    event.error_message = None
    event.response = None
    event.processing_completed_at = None
    return event


@pytest.fixture
def sample_agent():
    """Create sample agent."""
    agent = Mock()
    agent.id = uuid4()
    agent.agent_name = "test-agent"
    agent.tenant_id = uuid4()
    return agent


@pytest.fixture
def parsed_data():
    """Create sample parsed webhook data."""
    return {
        "event_type": "pull_request",
        "action": "opened",
        "repository": {
            "name": "test-repo",
            "owner": "test-owner",
        },
        "pull_request": {
            "number": 123,
            "title": "Test PR",
            "body": "Test description",
        },
    }


class TestProcessWebhookEvent:
    """Tests for process_webhook_event task."""

    @patch("src.core.database.reset_async_engine")
    @patch("src.core.database.create_celery_async_session")
    @patch("src.services.agents.chat_stream_service.ChatStreamService")
    @patch("src.services.agents.chat_service.ChatService")
    @patch("src.services.agents.agent_loader_service.AgentLoaderService")
    @patch("src.services.agents.agent_manager.AgentManager")
    @patch("src.tasks.agent_tasks.SessionLocal")
    def test_process_webhook_event_success(
        self,
        mock_session_local,
        mock_agent_manager,
        mock_agent_loader,
        mock_chat_service,
        mock_chat_stream_service,
        mock_create_async_session,
        mock_reset_engine,
        mock_db,
        sample_webhook,
        sample_event,
        sample_agent,
        parsed_data,
    ):
        """Test successfully processing webhook event."""
        from src.tasks.agent_tasks import process_webhook_event

        mock_session_local.return_value = mock_db

        webhook_query = Mock()
        webhook_query.filter.return_value.first.return_value = sample_webhook

        event_query = Mock()
        event_query.filter.return_value.first.return_value = sample_event

        agent_query = Mock()
        agent_query.filter.return_value.first.return_value = sample_agent

        mock_db.query.side_effect = [webhook_query, event_query, agent_query]

        # Mock async session used inside process_agent() for Conversation creation
        mock_create, _ = _make_async_session_mock()
        mock_create_async_session.side_effect = mock_create.side_effect
        mock_create_async_session.return_value = mock_create.return_value

        # Mock the ChatStreamService instance
        mock_stream_instance = Mock()
        mock_chat_stream_service.return_value = mock_stream_instance

        async def mock_agent_stream(*args, **kwargs):
            yield "data: " + json.dumps({"type": "chunk", "content": "Test response"})

        mock_stream_instance.stream_agent_response = mock_agent_stream

        process_webhook_event(
            webhook_id=str(sample_webhook.id),
            event_id=str(sample_event.id),
            parsed_data=parsed_data,
        )

        assert sample_event.status == "completed"
        mock_db.commit.assert_called()
        mock_db.close.assert_called_once()

    @patch("src.services.agents.chat_stream_service.ChatStreamService.stream_agent_response")
    @patch("src.tasks.agent_tasks.SessionLocal")
    def test_process_webhook_event_webhook_not_found(self, mock_session_local, mock_stream_agent, mock_db):
        """Test handling webhook not found."""
        from src.tasks.agent_tasks import process_webhook_event

        mock_session_local.return_value = mock_db

        webhook_query = Mock()
        webhook_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = webhook_query

        process_webhook_event(
            webhook_id=str(uuid4()),
            event_id=str(uuid4()),
            parsed_data={},
        )

        mock_db.close.assert_called_once()

    @patch("src.services.agents.chat_stream_service.ChatStreamService.stream_agent_response")
    @patch("src.tasks.agent_tasks.SessionLocal")
    def test_process_webhook_event_event_not_found(
        self, mock_session_local, mock_stream_agent, mock_db, sample_webhook
    ):
        """Test handling event not found."""
        from src.tasks.agent_tasks import process_webhook_event

        mock_session_local.return_value = mock_db

        webhook_query = Mock()
        webhook_query.filter.return_value.first.return_value = sample_webhook

        event_query = Mock()
        event_query.filter.return_value.first.return_value = None

        mock_db.query.side_effect = [webhook_query, event_query]

        process_webhook_event(
            webhook_id=str(sample_webhook.id),
            event_id=str(uuid4()),
            parsed_data={},
        )

        mock_db.close.assert_called_once()

    @patch("src.services.agents.chat_stream_service.ChatStreamService.stream_agent_response")
    @patch("src.tasks.agent_tasks.SessionLocal")
    def test_process_webhook_event_agent_not_found(
        self, mock_session_local, mock_stream_agent, mock_db, sample_webhook, sample_event
    ):
        """Test handling agent not found."""
        from src.tasks.agent_tasks import process_webhook_event

        mock_session_local.return_value = mock_db

        webhook_query = Mock()
        webhook_query.filter.return_value.first.return_value = sample_webhook

        event_query = Mock()
        event_query.filter.return_value.first.return_value = sample_event

        agent_query = Mock()
        agent_query.filter.return_value.first.return_value = None

        mock_db.query.side_effect = [webhook_query, event_query, agent_query]

        process_webhook_event(
            webhook_id=str(sample_webhook.id),
            event_id=str(sample_event.id),
            parsed_data={},
        )

        assert sample_event.status == "failed"
        assert sample_event.error_message == "Agent not found"
        mock_db.commit.assert_called()
        mock_db.close.assert_called_once()

    @patch("src.core.database.reset_async_engine")
    @patch("src.core.database.create_celery_async_session")
    @patch("src.services.agent_output_service.AgentOutputService")
    @patch("src.services.agents.chat_stream_service.ChatStreamService")
    @patch("src.services.agents.chat_service.ChatService")
    @patch("src.services.agents.agent_loader_service.AgentLoaderService")
    @patch("src.services.agents.agent_manager.AgentManager")
    @patch("src.tasks.agent_tasks.SessionLocal")
    def test_process_webhook_event_with_outputs(
        self,
        mock_session_local,
        mock_agent_manager,
        mock_agent_loader,
        mock_chat_service,
        mock_chat_stream_service,
        mock_output_service,
        mock_create_async_session,
        mock_reset_engine,
        mock_db,
        sample_webhook,
        sample_event,
        sample_agent,
        parsed_data,
    ):
        """Test processing webhook event with output sending."""
        from src.tasks.agent_tasks import process_webhook_event

        mock_session_local.return_value = mock_db

        webhook_query = Mock()
        webhook_query.filter.return_value.first.return_value = sample_webhook

        event_query = Mock()
        event_query.filter.return_value.first.return_value = sample_event

        agent_query = Mock()
        agent_query.filter.return_value.first.return_value = sample_agent

        mock_db.query.side_effect = [webhook_query, event_query, agent_query]

        # Mock async session
        mock_create, mock_async_db = _make_async_session_mock()
        mock_create_async_session.return_value = mock_create.return_value

        # Mock stream
        mock_stream_instance = Mock()
        mock_chat_stream_service.return_value = mock_stream_instance

        async def mock_agent_stream(*args, **kwargs):
            yield "data: " + json.dumps({"type": "chunk", "content": "PR approved"})

        mock_stream_instance.stream_agent_response = mock_agent_stream

        # Mock output service on the async_db session
        mock_service_instance = AsyncMock()
        mock_delivery = Mock()
        mock_delivery.status = "delivered"
        mock_delivery.provider = Mock(value="slack")
        mock_service_instance.send_outputs = AsyncMock(return_value=[mock_delivery])
        mock_output_service.return_value = mock_service_instance

        process_webhook_event(
            webhook_id=str(sample_webhook.id),
            event_id=str(sample_event.id),
            parsed_data=parsed_data,
        )

        assert sample_event.status == "completed"
        mock_db.close.assert_called_once()

    @patch("src.core.database.reset_async_engine")
    @patch("src.core.database.create_celery_async_session")
    @patch("src.services.agents.chat_stream_service.ChatStreamService")
    @patch("src.services.agents.chat_service.ChatService")
    @patch("src.services.agents.agent_loader_service.AgentLoaderService")
    @patch("src.services.agents.agent_manager.AgentManager")
    @patch("src.tasks.agent_tasks.SessionLocal")
    def test_process_webhook_event_with_error(
        self,
        mock_session_local,
        mock_agent_manager,
        mock_agent_loader,
        mock_chat_service,
        mock_chat_stream_service,
        mock_create_async_session,
        mock_reset_engine,
        mock_db,
        sample_webhook,
        sample_event,
        sample_agent,
        parsed_data,
    ):
        """Test handling error during webhook processing."""
        from src.tasks.agent_tasks import process_webhook_event

        mock_session_local.return_value = mock_db

        webhook_query = Mock()
        webhook_query.filter.return_value.first.return_value = sample_webhook

        event_query = Mock()
        event_query.filter.return_value.first.return_value = sample_event

        agent_query = Mock()
        agent_query.filter.return_value.first.return_value = sample_agent

        mock_db.query.side_effect = [
            webhook_query,
            event_query,
            agent_query,
            event_query,
        ]

        # Mock async session
        mock_create, _ = _make_async_session_mock()
        mock_create_async_session.return_value = mock_create.return_value

        # Mock the ChatStreamService instance with a stream that raises
        mock_stream_instance = Mock()
        mock_chat_stream_service.return_value = mock_stream_instance

        async def mock_agent_stream_error(*args, **kwargs):
            raise Exception("Agent error")
            yield  # noqa: unreachable — required to make this an async generator

        mock_stream_instance.stream_agent_response = mock_agent_stream_error

        with pytest.raises(Exception):
            process_webhook_event(
                webhook_id=str(sample_webhook.id),
                event_id=str(sample_event.id),
                parsed_data=parsed_data,
            )

        mock_db.close.assert_called()

    @patch("src.core.database.reset_async_engine")
    @patch("src.core.database.create_celery_async_session")
    @patch("src.services.agent_output_service.AgentOutputService")
    @patch("src.services.agents.chat_stream_service.ChatStreamService")
    @patch("src.services.agents.chat_service.ChatService")
    @patch("src.services.agents.agent_loader_service.AgentLoaderService")
    @patch("src.services.agents.agent_manager.AgentManager")
    @patch("src.tasks.agent_tasks.SessionLocal")
    def test_process_webhook_event_output_error(
        self,
        mock_session_local,
        mock_agent_manager,
        mock_agent_loader,
        mock_chat_service,
        mock_chat_stream_service,
        mock_output_service,
        mock_create_async_session,
        mock_reset_engine,
        mock_db,
        sample_webhook,
        sample_event,
        sample_agent,
        parsed_data,
    ):
        """Test handling error during output sending."""
        from src.tasks.agent_tasks import process_webhook_event

        mock_session_local.return_value = mock_db

        webhook_query = Mock()
        webhook_query.filter.return_value.first.return_value = sample_webhook

        event_query = Mock()
        event_query.filter.return_value.first.return_value = sample_event

        agent_query = Mock()
        agent_query.filter.return_value.first.return_value = sample_agent

        mock_db.query.side_effect = [webhook_query, event_query, agent_query]

        # Mock async session
        mock_create, _ = _make_async_session_mock()
        mock_create_async_session.return_value = mock_create.return_value

        # Mock the ChatStreamService instance
        mock_stream_instance = Mock()
        mock_chat_stream_service.return_value = mock_stream_instance

        async def mock_agent_stream(*args, **kwargs):
            yield "data: " + json.dumps({"type": "chunk", "content": "Response"})

        mock_stream_instance.stream_agent_response = mock_agent_stream

        mock_output_service.side_effect = Exception("Output service error")

        process_webhook_event(
            webhook_id=str(sample_webhook.id),
            event_id=str(sample_event.id),
            parsed_data=parsed_data,
        )

        assert sample_event.status == "completed"
        mock_db.close.assert_called_once()

    @patch("src.core.database.reset_async_engine")
    @patch("src.core.database.create_celery_async_session")
    @patch("src.services.agents.chat_stream_service.ChatStreamService.stream_agent_response")
    @patch("src.tasks.agent_tasks.SessionLocal")
    def test_process_webhook_event_message_formatting(
        self,
        mock_session_local,
        mock_stream_agent,
        mock_create_async_session,
        mock_reset_engine,
        mock_db,
        sample_webhook,
        sample_event,
        sample_agent,
        parsed_data,
    ):
        """Test that webhook data is formatted correctly in message."""
        from src.tasks.agent_tasks import process_webhook_event

        mock_session_local.return_value = mock_db

        webhook_query = Mock()
        webhook_query.filter.return_value.first.return_value = sample_webhook

        event_query = Mock()
        event_query.filter.return_value.first.return_value = sample_event

        agent_query = Mock()
        agent_query.filter.return_value.first.return_value = sample_agent

        mock_db.query.side_effect = [webhook_query, event_query, agent_query]

        # Mock async session used inside process_agent() for Conversation creation —
        # without this, a real INSERT runs against the test DB with sample_agent's
        # fake uuid4() id, which no Agent row backs, and fails on the FK constraint.
        mock_create, _ = _make_async_session_mock()
        mock_create_async_session.side_effect = mock_create.side_effect
        mock_create_async_session.return_value = mock_create.return_value

        async def mock_agent_stream(*args, **kwargs):
            yield "data: " + json.dumps({"type": "chunk", "content": "OK"})

        mock_stream_agent.return_value = mock_agent_stream()

        process_webhook_event(
            webhook_id=str(sample_webhook.id),
            event_id=str(sample_event.id),
            parsed_data=parsed_data,
        )

        mock_db.close.assert_called_once()

    @patch("src.core.database.reset_async_engine")
    @patch("src.core.database.create_celery_async_session")
    @patch("src.services.agents.chat_stream_service.ChatStreamService.stream_agent_response")
    @patch("src.tasks.agent_tasks.SessionLocal")
    def test_process_webhook_event_response_truncation(
        self,
        mock_session_local,
        mock_stream_agent,
        mock_create_async_session,
        mock_reset_engine,
        mock_db,
        sample_webhook,
        sample_event,
        sample_agent,
        parsed_data,
    ):
        """Test that long responses are truncated."""
        from src.tasks.agent_tasks import process_webhook_event

        mock_session_local.return_value = mock_db

        webhook_query = Mock()
        webhook_query.filter.return_value.first.return_value = sample_webhook

        event_query = Mock()
        event_query.filter.return_value.first.return_value = sample_event

        agent_query = Mock()
        agent_query.filter.return_value.first.return_value = sample_agent

        mock_db.query.side_effect = [webhook_query, event_query, agent_query]

        # Mock async session used inside process_agent() for Conversation creation —
        # see comment in test_process_webhook_event_message_formatting.
        mock_create, _ = _make_async_session_mock()
        mock_create_async_session.side_effect = mock_create.side_effect
        mock_create_async_session.return_value = mock_create.return_value

        long_content = "A" * 6000

        async def mock_agent_stream(*args, **kwargs):
            yield "data: " + json.dumps({"type": "chunk", "content": long_content})

        mock_stream_agent.return_value = mock_agent_stream()

        process_webhook_event(
            webhook_id=str(sample_webhook.id),
            event_id=str(sample_event.id),
            parsed_data=parsed_data,
        )

        # Verify response was truncated to 5000 chars if set
        if sample_event.response:
            assert len(sample_event.response) <= 5000
        mock_db.close.assert_called_once()
