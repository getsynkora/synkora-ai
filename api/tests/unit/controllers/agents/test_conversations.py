import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from src.controllers.agents.conversations import agents_conversations_router
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id


def setup_db_execute_mock(mock_db, return_value):
    """Helper to mock async db.execute() pattern."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = return_value
    mock_result.scalars.return_value.all.return_value = [return_value] if return_value else []
    mock_result.scalars.return_value.first.return_value = return_value
    mock_db.execute = AsyncMock(return_value=mock_result)
    return mock_result


@pytest.fixture
def mock_db_session():
    db = AsyncMock()
    return db


@pytest.fixture
def mock_tenant_id():
    return uuid.uuid4()


@pytest.fixture
def mock_account():
    """Create mock account for user isolation."""
    account = MagicMock()
    account.id = uuid.uuid4()
    account.email = "test@example.com"
    account.name = "Test User"
    return account


@pytest.fixture
def client(mock_db_session, mock_tenant_id, mock_account):
    app = FastAPI()
    app.include_router(agents_conversations_router)

    async def mock_db():
        yield mock_db_session

    app.dependency_overrides[get_async_db] = mock_db
    app.dependency_overrides[get_current_tenant_id] = lambda: mock_tenant_id
    app.dependency_overrides[get_current_account] = lambda: mock_account
    return TestClient(app), mock_db_session, mock_tenant_id, mock_account


class TestConversationsController:
    """Test cases for conversations controller."""

    def test_create_conversation_success(self, client):
        """Test successful conversation creation."""
        test_client, mock_db_session, mock_tenant_id, mock_account = client
        agent_id = uuid.uuid4()

        # Mock database execute for agent lookup
        mock_agent = MagicMock()
        mock_agent.id = agent_id
        setup_db_execute_mock(mock_db_session, mock_agent)

        # Mock create_conversation
        mock_conversation = MagicMock()
        mock_conversation.to_dict.return_value = {
            "id": str(uuid.uuid4()),
            "agent_id": str(agent_id),
            "session_id": "test-session",
            "name": "Test Conversation",
        }

        with (
            patch("src.services.billing.ChatBillingService") as MockBillingService,
            patch("src.services.conversation_service.ConversationService") as mock_service,
        ):
            # Mock billing validation to pass
            mock_billing_instance = MockBillingService.return_value
            mock_billing_result = MagicMock()
            mock_billing_result.is_valid = True
            mock_billing_instance.validate_conversation_creation = AsyncMock(return_value=mock_billing_result)

            mock_service.create_conversation = AsyncMock(return_value=mock_conversation)

            response = test_client.post(
                "/conversations",
                json={"agent_id": str(agent_id), "session_id": "test-session", "name": "Test Conversation"},
            )

            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["success"] is True
            assert data["data"]["session_id"] == "test-session"

    def test_create_conversation_agent_not_found(self, client):
        """Test creation with non-existent agent."""
        test_client, mock_db_session, mock_tenant_id, mock_account = client
        agent_id = uuid.uuid4()

        # Mock database execute returning None
        setup_db_execute_mock(mock_db_session, None)

        with patch("src.services.billing.ChatBillingService") as MockBillingService:
            # Mock billing validation to pass (billing check happens before agent lookup)
            mock_billing_instance = MockBillingService.return_value
            mock_billing_result = MagicMock()
            mock_billing_result.is_valid = True
            mock_billing_instance.validate_conversation_creation = AsyncMock(return_value=mock_billing_result)

            response = test_client.post(
                "/conversations", json={"agent_id": str(agent_id), "session_id": "test-session"}
            )

            assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_conversation_uses_valid_source(self, client):
        """Test creation preserves supported conversation sources."""
        test_client, mock_db_session, mock_tenant_id, mock_account = client
        agent_id = uuid.uuid4()

        mock_agent = MagicMock()
        mock_agent.id = agent_id
        setup_db_execute_mock(mock_db_session, mock_agent)

        mock_conversation = MagicMock()
        mock_conversation.to_dict.return_value = {
            "id": str(uuid.uuid4()),
            "agent_id": str(agent_id),
            "source": "flutter",
        }

        with (
            patch("src.services.billing.ChatBillingService") as MockBillingService,
            patch("src.services.conversation_service.ConversationService") as mock_service,
        ):
            mock_billing_instance = MockBillingService.return_value
            mock_billing_result = MagicMock()
            mock_billing_result.is_valid = True
            mock_billing_instance.validate_conversation_creation = AsyncMock(return_value=mock_billing_result)
            mock_service.create_conversation = AsyncMock(return_value=mock_conversation)

            response = test_client.post(
                "/conversations",
                json={"agent_id": str(agent_id), "name": "Mobile", "source": "flutter"},
            )

            assert response.status_code == status.HTTP_201_CREATED
            assert mock_service.create_conversation.await_args.kwargs["source"] == "flutter"

    def test_create_conversation_falls_back_to_web_for_invalid_source(self, client):
        """Test creation defaults unsupported sources to web."""
        test_client, mock_db_session, mock_tenant_id, mock_account = client
        agent_id = uuid.uuid4()

        mock_agent = MagicMock()
        mock_agent.id = agent_id
        setup_db_execute_mock(mock_db_session, mock_agent)

        mock_conversation = MagicMock()
        mock_conversation.to_dict.return_value = {
            "id": str(uuid.uuid4()),
            "agent_id": str(agent_id),
            "source": "web",
        }

        with (
            patch("src.services.billing.ChatBillingService") as MockBillingService,
            patch("src.services.conversation_service.ConversationService") as mock_service,
        ):
            mock_billing_instance = MockBillingService.return_value
            mock_billing_result = MagicMock()
            mock_billing_result.is_valid = True
            mock_billing_instance.validate_conversation_creation = AsyncMock(return_value=mock_billing_result)
            mock_service.create_conversation = AsyncMock(return_value=mock_conversation)

            response = test_client.post(
                "/conversations",
                json={"agent_id": str(agent_id), "name": "Mobile", "source": "desktop-app"},
            )

            assert response.status_code == status.HTTP_201_CREATED
            assert mock_service.create_conversation.await_args.kwargs["source"] == "web"

    def test_list_agent_conversations(self, client):
        """Test listing conversations."""
        test_client, mock_db_session, mock_tenant_id, mock_account = client
        agent_id = uuid.uuid4()

        # Mock agent query (for first query to check agent exists)
        mock_agent = MagicMock()
        mock_agent.id = agent_id

        # Mock conversation query results
        mock_conv1 = MagicMock()
        mock_conv1.to_dict.return_value = {"id": "1", "name": "Conv 1"}
        mock_conv2 = MagicMock()
        mock_conv2.to_dict.return_value = {"id": "2", "name": "Conv 2"}

        # Track execute calls: first returns agent, second returns conversations
        call_count = [0]

        def execute_side_effect(*args, **kwargs):
            mock_result = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                # Agent lookup
                mock_result.scalar_one_or_none.return_value = mock_agent
            else:
                # Conversations query
                mock_result.scalars.return_value.all.return_value = [mock_conv1, mock_conv2]
            return mock_result

        mock_db_session.execute = AsyncMock(side_effect=execute_side_effect)

        response = test_client.get(f"/{agent_id}/conversations")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["data"]["conversations"]) == 2

    def test_get_conversation(self, client):
        """Test getting a specific conversation."""
        test_client, mock_db_session, mock_tenant_id, mock_account = client
        conversation_id = uuid.uuid4()
        agent_id = uuid.uuid4()

        # Mock conversation
        mock_conversation = MagicMock()
        mock_conversation.id = conversation_id
        mock_conversation.agent_id = agent_id
        mock_conversation.account_id = mock_account.id
        mock_conversation.to_dict.return_value = {"id": str(conversation_id), "name": "Test Conversation"}

        # Mock db.execute to return the conversation
        setup_db_execute_mock(mock_db_session, mock_conversation)

        with patch("src.services.conversation_service.ConversationService") as mock_service:
            mock_service.get_conversation = AsyncMock(return_value=mock_conversation)

            response = test_client.get(f"/conversations/{conversation_id}")

            assert response.status_code == status.HTTP_200_OK
            assert response.json()["data"]["id"] == str(conversation_id)

    def test_get_conversation_not_found(self, client):
        """Test getting non-existent conversation."""
        test_client, mock_db_session, mock_tenant_id, mock_account = client
        conversation_id = uuid.uuid4()

        # Mock db.execute returning None
        setup_db_execute_mock(mock_db_session, None)

        response = test_client.get(f"/conversations/{conversation_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_conversation(self, client):
        """Test updating a conversation."""
        test_client, mock_db_session, mock_tenant_id, mock_account = client
        conversation_id = uuid.uuid4()
        agent_id = uuid.uuid4()

        # Mock conversation
        mock_conversation = MagicMock()
        mock_conversation.id = conversation_id
        mock_conversation.agent_id = agent_id
        mock_conversation.account_id = mock_account.id
        mock_conversation.to_dict.return_value = {
            "id": str(conversation_id),
            "name": "Updated Name",
            "summary": "New Summary",
        }

        # Mock db.execute to return the conversation
        setup_db_execute_mock(mock_db_session, mock_conversation)

        with patch("src.services.conversation_service.ConversationService") as mock_service:
            mock_service.update_conversation = AsyncMock(return_value=mock_conversation)

            response = test_client.put(
                f"/conversations/{conversation_id}", json={"name": "Updated Name", "summary": "New Summary"}
            )

            assert response.status_code == status.HTTP_200_OK
            assert response.json()["data"]["name"] == "Updated Name"

    def test_delete_conversation(self, client):
        """Test deleting a conversation."""
        test_client, mock_db_session, mock_tenant_id, mock_account = client
        conversation_id = uuid.uuid4()
        agent_id = uuid.uuid4()

        # Mock conversation
        mock_conversation = MagicMock()
        mock_conversation.id = conversation_id
        mock_conversation.agent_id = agent_id
        mock_conversation.account_id = mock_account.id

        # Mock db.execute to return the conversation
        setup_db_execute_mock(mock_db_session, mock_conversation)

        with patch("src.services.conversation_service.ConversationService") as mock_service:
            mock_service.delete_conversation = AsyncMock(return_value=True)

            response = test_client.delete(f"/conversations/{conversation_id}")

            assert response.status_code == status.HTTP_200_OK
            assert response.json()["success"] is True

    def test_delete_conversation_not_found(self, client):
        """Test deleting non-existent conversation."""
        test_client, mock_db_session, mock_tenant_id, mock_account = client
        conversation_id = uuid.uuid4()

        # Mock db.execute returning None
        setup_db_execute_mock(mock_db_session, None)

        response = test_client.delete(f"/conversations/{conversation_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_conversation_messages(self, client):
        """Test getting conversation messages."""
        test_client, mock_db_session, mock_tenant_id, mock_account = client
        conversation_id = uuid.uuid4()
        agent_id = uuid.uuid4()

        # Mock conversation
        mock_conversation = MagicMock()
        mock_conversation.id = conversation_id
        mock_conversation.agent_id = agent_id
        mock_conversation.account_id = mock_account.id

        # Mock db.execute to return the conversation
        setup_db_execute_mock(mock_db_session, mock_conversation)

        mock_msg1 = MagicMock()
        mock_msg1.to_dict.return_value = {"id": "1", "content": "Hello"}
        mock_msg2 = MagicMock()
        mock_msg2.to_dict.return_value = {"id": "2", "content": "Hi"}

        with patch("src.services.conversation_service.ConversationService") as mock_service:
            mock_service.get_conversation_messages = AsyncMock(return_value=[mock_msg1, mock_msg2])

            response = test_client.get(f"/conversations/{conversation_id}/messages")

            assert response.status_code == status.HTTP_200_OK
            assert len(response.json()["data"]["messages"]) == 2
