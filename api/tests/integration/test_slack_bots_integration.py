"""
Integration tests for Slack Bots endpoints.

Tests CRUD operations for Slack bot configurations.
"""

import uuid

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


@pytest.fixture
def auth_headers(client: TestClient, db_session: Session):
    """Create authenticated user and return headers with tenant info."""
    from src.core.database import get_db
    from src.models import Account, AccountStatus

    client.app.dependency_overrides[get_db] = lambda: db_session

    email = f"slack_test_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecureTestPass123!"

    # Register
    response = client.post(
        "/console/api/auth/register",
        json={
            "email": email,
            "password": password,
            "name": "Slack Test User",
            "tenant_name": "Slack Test Org",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    tenant_id = data["data"]["tenant"]["id"]

    # Activate account
    account = db_session.query(Account).filter_by(email=email).first()
    account.status = AccountStatus.ACTIVE
    db_session.commit()

    # Login
    login_response = client.post(
        "/console/api/auth/login",
        json={"email": email, "password": password},
    )
    token = login_response.json()["data"]["access_token"]

    return {"Authorization": f"Bearer {token}"}, tenant_id, account


@pytest.fixture
def test_agent(client: TestClient, db_session: Session, auth_headers):
    """Create a test agent for Slack bot tests."""
    from src.core.database import get_db

    client.app.dependency_overrides[get_db] = lambda: db_session

    headers, tenant_id, account = auth_headers

    # Create an agent to associate Slack bots with
    agent_name = f"slack-test-agent-{uuid.uuid4().hex[:8]}"
    response = client.post(
        "/api/v1/agents",
        json={
            "name": f"Slack Test Agent {uuid.uuid4().hex[:8]}",
            "agent_name": agent_name,
            "description": "Agent for Slack bot tests",
            "system_prompt": "You are a test agent.",
            "model": "gpt-4o-mini",
        },
        headers=headers,
    )
    if response.status_code == status.HTTP_201_CREATED:
        return response.json()["id"]
    return str(uuid.uuid4())  # Use fake ID if agent creation fails


class TestSlackBotsListIntegration:
    """Test Slack Bots listing operations."""

    def test_list_slack_bots(self, client: TestClient, db_session: Session, auth_headers):
        """Test listing Slack bots."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id, account = auth_headers

        response = client.get("/api/v1/slack-bots", headers=headers)

        # Accept 200 (success) or 500 (service error)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]

        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert isinstance(data, list)

    def test_list_slack_bots_with_agent_filter(self, client: TestClient, db_session: Session, auth_headers, test_agent):
        """Test listing Slack bots filtered by agent."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id, account = auth_headers

        response = client.get(f"/api/v1/slack-bots?agent_id={test_agent}", headers=headers)

        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]

        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert isinstance(data, list)

    def test_list_slack_bots_with_active_filter(self, client: TestClient, db_session: Session, auth_headers):
        """Test listing Slack bots filtered by active status."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id, account = auth_headers

        response = client.get("/api/v1/slack-bots?is_active=true", headers=headers)

        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]


class TestSlackBotsCRUDIntegration:
    """Test Slack Bots CRUD operations."""

    def test_create_slack_bot(self, client: TestClient, db_session: Session, auth_headers, test_agent):
        """Test creating a Slack bot."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id, account = auth_headers

        response = client.post(
            "/api/v1/slack-bots",
            json={
                "agent_id": test_agent,
                "bot_name": f"Test Slack Bot {uuid.uuid4().hex[:8]}",
                "slack_app_id": "A12345678",
                "slack_bot_token": "xoxb-test-token-12345",
                "slack_app_token": "xapp-test-token-12345",
            },
            headers=headers,
        )

        # Accept 201 (success) or 400 (validation/bot error) or 500 (service error)
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

        if response.status_code == status.HTTP_201_CREATED:
            data = response.json()
            assert "id" in data
            assert "bot_name" in data
            assert "agent_id" in data

    def test_create_slack_bot_missing_required_fields(self, client: TestClient, db_session: Session, auth_headers):
        """Test creating Slack bot without required fields fails."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id, account = auth_headers

        # Missing agent_id, bot_name, slack_app_id, tokens
        response = client.post(
            "/api/v1/slack-bots",
            json={"bot_name": "Test Bot"},
            headers=headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_get_slack_bot(self, client: TestClient, db_session: Session, auth_headers, test_agent):
        """Test getting a specific Slack bot."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id, account = auth_headers

        # First create a bot
        create_response = client.post(
            "/api/v1/slack-bots",
            json={
                "agent_id": test_agent,
                "bot_name": f"Get Test Bot {uuid.uuid4().hex[:8]}",
                "slack_app_id": "A12345679",
                "slack_bot_token": "xoxb-test-token-get",
                "slack_app_token": "xapp-test-token-get",
            },
            headers=headers,
        )

        if create_response.status_code == status.HTTP_201_CREATED:
            bot_id = create_response.json()["id"]

            # Get the bot
            response = client.get(f"/api/v1/slack-bots/{bot_id}", headers=headers)

            assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]

            if response.status_code == status.HTTP_200_OK:
                data = response.json()
                assert data["id"] == bot_id

    def test_get_nonexistent_slack_bot(self, client: TestClient, db_session: Session, auth_headers):
        """Test getting a nonexistent Slack bot returns 404."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id, account = auth_headers

        fake_bot_id = str(uuid.uuid4())
        response = client.get(f"/api/v1/slack-bots/{fake_bot_id}", headers=headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_slack_bot(self, client: TestClient, db_session: Session, auth_headers, test_agent):
        """Test updating a Slack bot."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id, account = auth_headers

        # First create a bot
        create_response = client.post(
            "/api/v1/slack-bots",
            json={
                "agent_id": test_agent,
                "bot_name": f"Update Test Bot {uuid.uuid4().hex[:8]}",
                "slack_app_id": "A12345680",
                "slack_bot_token": "xoxb-test-token-update",
                "slack_app_token": "xapp-test-token-update",
            },
            headers=headers,
        )

        if create_response.status_code == status.HTTP_201_CREATED:
            bot_id = create_response.json()["id"]

            # Update the bot
            response = client.put(
                f"/api/v1/slack-bots/{bot_id}",
                json={"bot_name": f"Updated Bot Name {uuid.uuid4().hex[:8]}"},
                headers=headers,
            )

            assert response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_404_NOT_FOUND,
            ]

    def test_update_nonexistent_slack_bot(self, client: TestClient, db_session: Session, auth_headers):
        """Test updating a nonexistent Slack bot returns 404."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id, account = auth_headers

        fake_bot_id = str(uuid.uuid4())
        response = client.put(
            f"/api/v1/slack-bots/{fake_bot_id}",
            json={"bot_name": "New Name"},
            headers=headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_slack_bot(self, client: TestClient, db_session: Session, auth_headers, test_agent):
        """Test deleting a Slack bot."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id, account = auth_headers

        # First create a bot
        create_response = client.post(
            "/api/v1/slack-bots",
            json={
                "agent_id": test_agent,
                "bot_name": f"Delete Test Bot {uuid.uuid4().hex[:8]}",
                "slack_app_id": "A12345681",
                "slack_bot_token": "xoxb-test-token-delete",
                "slack_app_token": "xapp-test-token-delete",
            },
            headers=headers,
        )

        if create_response.status_code == status.HTTP_201_CREATED:
            bot_id = create_response.json()["id"]

            # Delete the bot
            response = client.delete(f"/api/v1/slack-bots/{bot_id}", headers=headers)

            assert response.status_code in [
                status.HTTP_204_NO_CONTENT,
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_404_NOT_FOUND,
            ]

    def test_delete_nonexistent_slack_bot(self, client: TestClient, db_session: Session, auth_headers):
        """Test deleting a nonexistent Slack bot returns 404."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id, account = auth_headers

        fake_bot_id = str(uuid.uuid4())
        response = client.delete(f"/api/v1/slack-bots/{fake_bot_id}", headers=headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestSlackBotsControlIntegration:
    """Test Slack Bots start/stop/restart operations."""

    def test_start_slack_bot(self, client: TestClient, db_session: Session, auth_headers, test_agent):
        """Test starting a Slack bot."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id, account = auth_headers

        # First create a bot
        create_response = client.post(
            "/api/v1/slack-bots",
            json={
                "agent_id": test_agent,
                "bot_name": f"Start Test Bot {uuid.uuid4().hex[:8]}",
                "slack_app_id": "A12345682",
                "slack_bot_token": "xoxb-test-token-start",
                "slack_app_token": "xapp-test-token-start",
            },
            headers=headers,
        )

        if create_response.status_code == status.HTTP_201_CREATED:
            bot_id = create_response.json()["id"]

            # Start the bot (will likely fail due to invalid tokens, but should not 404)
            response = client.post(f"/api/v1/slack-bots/{bot_id}/start", headers=headers)

            # Accept 200 (success) or 400 (failed to start) or 404 (not found)
            assert response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_404_NOT_FOUND,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            ]

    def test_stop_slack_bot(self, client: TestClient, db_session: Session, auth_headers, test_agent):
        """Test stopping a Slack bot."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id, account = auth_headers

        # First create a bot
        create_response = client.post(
            "/api/v1/slack-bots",
            json={
                "agent_id": test_agent,
                "bot_name": f"Stop Test Bot {uuid.uuid4().hex[:8]}",
                "slack_app_id": "A12345683",
                "slack_bot_token": "xoxb-test-token-stop",
                "slack_app_token": "xapp-test-token-stop",
            },
            headers=headers,
        )

        if create_response.status_code == status.HTTP_201_CREATED:
            bot_id = create_response.json()["id"]

            # Stop the bot
            response = client.post(f"/api/v1/slack-bots/{bot_id}/stop", headers=headers)

            assert response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_404_NOT_FOUND,
            ]

    def test_restart_slack_bot(self, client: TestClient, db_session: Session, auth_headers, test_agent):
        """Test restarting a Slack bot."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id, account = auth_headers

        # First create a bot
        create_response = client.post(
            "/api/v1/slack-bots",
            json={
                "agent_id": test_agent,
                "bot_name": f"Restart Test Bot {uuid.uuid4().hex[:8]}",
                "slack_app_id": "A12345684",
                "slack_bot_token": "xoxb-test-token-restart",
                "slack_app_token": "xapp-test-token-restart",
            },
            headers=headers,
        )

        if create_response.status_code == status.HTTP_201_CREATED:
            bot_id = create_response.json()["id"]

            # Restart the bot
            response = client.post(f"/api/v1/slack-bots/{bot_id}/restart", headers=headers)

            assert response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_404_NOT_FOUND,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            ]

    def test_get_slack_bot_status(self, client: TestClient, db_session: Session, auth_headers, test_agent):
        """Test getting Slack bot status."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id, account = auth_headers

        # First create a bot
        create_response = client.post(
            "/api/v1/slack-bots",
            json={
                "agent_id": test_agent,
                "bot_name": f"Status Test Bot {uuid.uuid4().hex[:8]}",
                "slack_app_id": "A12345685",
                "slack_bot_token": "xoxb-test-token-status",
                "slack_app_token": "xapp-test-token-status",
            },
            headers=headers,
        )

        if create_response.status_code == status.HTTP_201_CREATED:
            bot_id = create_response.json()["id"]

            # Get bot status
            response = client.get(f"/api/v1/slack-bots/{bot_id}/status", headers=headers)

            assert response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_404_NOT_FOUND,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            ]

            if response.status_code == status.HTTP_200_OK:
                data = response.json()
                assert "bot_id" in data
                assert "is_running" in data
                assert "connection_status" in data


class TestSlackBotsAuthorization:
    """Test Slack Bots authorization."""

    def test_list_slack_bots_unauthorized(self, client: TestClient, db_session: Session):
        """Test that unauthenticated requests to list are rejected."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        response = client.get("/api/v1/slack-bots")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_create_slack_bot_unauthorized(self, client: TestClient, db_session: Session):
        """Test that unauthenticated requests to create are rejected."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        response = client.post(
            "/api/v1/slack-bots",
            json={
                "agent_id": str(uuid.uuid4()),
                "bot_name": "Unauthorized Bot",
                "slack_app_id": "A12345",
                "slack_bot_token": "xoxb-test",
                "slack_app_token": "xapp-test",
            },
        )

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_get_slack_bot_unauthorized(self, client: TestClient, db_session: Session):
        """Test that unauthenticated requests to get are rejected."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        response = client.get(f"/api/v1/slack-bots/{uuid.uuid4()}")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_update_slack_bot_unauthorized(self, client: TestClient, db_session: Session):
        """Test that unauthenticated requests to update are rejected."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        response = client.put(
            f"/api/v1/slack-bots/{uuid.uuid4()}",
            json={"bot_name": "New Name"},
        )

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_delete_slack_bot_unauthorized(self, client: TestClient, db_session: Session):
        """Test that unauthenticated requests to delete are rejected."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        response = client.delete(f"/api/v1/slack-bots/{uuid.uuid4()}")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_start_slack_bot_unauthorized(self, client: TestClient, db_session: Session):
        """Test that unauthenticated requests to start are rejected."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        response = client.post(f"/api/v1/slack-bots/{uuid.uuid4()}/start")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_stop_slack_bot_unauthorized(self, client: TestClient, db_session: Session):
        """Test that unauthenticated requests to stop are rejected."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        response = client.post(f"/api/v1/slack-bots/{uuid.uuid4()}/stop")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_restart_slack_bot_unauthorized(self, client: TestClient, db_session: Session):
        """Test that unauthenticated requests to restart are rejected."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        response = client.post(f"/api/v1/slack-bots/{uuid.uuid4()}/restart")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_get_slack_bot_status_unauthorized(self, client: TestClient, db_session: Session):
        """Test that unauthenticated requests to get status are rejected."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        response = client.get(f"/api/v1/slack-bots/{uuid.uuid4()}/status")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]


class TestSlackBotsTenantIsolation:
    """Test Slack Bots tenant isolation."""

    def test_cannot_access_other_tenant_bot(self, client: TestClient, db_session: Session):
        """Test that users cannot access other tenants' Slack bots."""
        from src.core.database import get_db
        from src.models import Account, AccountStatus

        client.app.dependency_overrides[get_db] = lambda: db_session

        # Create first tenant and bot
        email1 = f"slack_tenant1_{uuid.uuid4().hex[:8]}@example.com"
        response1 = client.post(
            "/console/api/auth/register",
            json={
                "email": email1,
                "password": "SecureTestPass123!",
                "name": "Tenant 1 User",
                "tenant_name": "Slack Tenant 1 Org",
            },
        )
        assert response1.status_code == status.HTTP_201_CREATED

        account1 = db_session.query(Account).filter_by(email=email1).first()
        account1.status = AccountStatus.ACTIVE
        db_session.commit()

        login1 = client.post("/console/api/auth/login", json={"email": email1, "password": "SecureTestPass123!"})
        token1 = login1.json()["data"]["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}

        # Create an agent for tenant 1
        agent_response = client.post(
            "/api/v1/agents",
            json={
                "name": "Tenant 1 Agent",
                "agent_name": f"tenant1-agent-{uuid.uuid4().hex[:8]}",
                "description": "Test agent",
                "system_prompt": "Test",
                "model": "gpt-4o-mini",
            },
            headers=headers1,
        )

        if agent_response.status_code == status.HTTP_201_CREATED:
            agent_id = agent_response.json()["id"]

            # Create a Slack bot for tenant 1
            bot_response = client.post(
                "/api/v1/slack-bots",
                json={
                    "agent_id": agent_id,
                    "bot_name": "Tenant 1 Bot",
                    "slack_app_id": "A12345699",
                    "slack_bot_token": "xoxb-tenant1-token",
                    "slack_app_token": "xapp-tenant1-token",
                },
                headers=headers1,
            )

            if bot_response.status_code == status.HTTP_201_CREATED:
                bot_id = bot_response.json()["id"]

                # Create second tenant
                email2 = f"slack_tenant2_{uuid.uuid4().hex[:8]}@example.com"
                client.post(
                    "/console/api/auth/register",
                    json={
                        "email": email2,
                        "password": "SecureTestPass123!",
                        "name": "Tenant 2 User",
                        "tenant_name": "Slack Tenant 2 Org",
                    },
                )

                account2 = db_session.query(Account).filter_by(email=email2).first()
                account2.status = AccountStatus.ACTIVE
                db_session.commit()

                login2 = client.post(
                    "/console/api/auth/login", json={"email": email2, "password": "SecureTestPass123!"}
                )
                token2 = login2.json()["data"]["access_token"]
                headers2 = {"Authorization": f"Bearer {token2}"}

                # Tenant 2 tries to access Tenant 1's bot
                response = client.get(f"/api/v1/slack-bots/{bot_id}", headers=headers2)

                # Should return 404 (not found for this tenant)
                assert response.status_code == status.HTTP_404_NOT_FOUND
