"""Tests for agent domains controller."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from src.controllers.agent_domains import public_router, router
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id


@pytest.fixture
def mock_domain_service():
    with patch("src.controllers.agent_domains.DomainService") as mock:
        mock.return_value = AsyncMock()
        yield mock


@pytest.fixture
def mock_dns_service():
    with patch("src.controllers.agent_domains.DNSService") as mock:
        mock.return_value = AsyncMock()
        yield mock


@pytest.fixture
def mock_domain_resolver():
    with patch("src.controllers.agent_domains.DomainResolver") as mock:
        mock.return_value = AsyncMock()
        yield mock


@pytest.fixture
def mock_db_session():
    return AsyncMock()


@pytest.fixture
def client(mock_domain_service, mock_dns_service, mock_db_session):
    app = FastAPI()
    app.include_router(router)
    app.include_router(public_router)

    # Mock dependencies
    async def mock_db():
        yield mock_db_session

    app.dependency_overrides[get_async_db] = mock_db

    # Mock tenant ID
    tenant_id = uuid.uuid4()
    app.dependency_overrides[get_current_tenant_id] = lambda: tenant_id

    return TestClient(app), tenant_id, mock_db_session, {"domain": mock_domain_service, "dns": mock_dns_service}


def _create_mock_agent(agent_id, agent_slug, tenant_id):
    """Helper to create mock agent."""
    mock_agent = MagicMock()
    mock_agent.id = agent_id
    mock_agent.slug = agent_slug
    mock_agent.agent_name = agent_slug
    mock_agent.tenant_id = tenant_id
    mock_agent.agent_type = "assistant"
    mock_agent.description = "Test agent"
    return mock_agent


def _create_mock_domain(domain_id, agent_id, tenant_id, **kwargs):
    """Helper to create mock domain."""
    mock_domain = MagicMock()
    mock_domain.id = domain_id
    mock_domain.agent_id = agent_id
    mock_domain.tenant_id = tenant_id
    mock_domain.subdomain = kwargs.get("subdomain", "test-agent")
    mock_domain.domain = kwargs.get("domain")
    mock_domain.is_custom_domain = kwargs.get("is_custom_domain", False)
    mock_domain.is_verified = kwargs.get("is_verified", False)
    mock_domain.verification_token = kwargs.get("verification_token", "token123")
    mock_domain.verification_method = kwargs.get("verification_method", "dns")
    mock_domain.chat_page_config = kwargs.get("chat_page_config", {})
    mock_domain.created_at = datetime.now(UTC)
    mock_domain.updated_at = datetime.now(UTC)
    return mock_domain


class TestListAgentDomains:
    """Tests for listing agent domains."""

    def test_list_domains_success(self, client):
        """Test listing domains for an agent."""
        test_client, tenant_id, mock_db, mocks = client
        mock_domain_service = mocks["domain"].return_value

        agent_id = uuid.uuid4()
        agent_name = "test-agent"
        mock_agent = _create_mock_agent(agent_id, agent_name, tenant_id)

        # Mock agent lookup
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_agent
        mock_db.execute.return_value = mock_result

        # Mock domains
        mock_domain = _create_mock_domain(uuid.uuid4(), agent_id, tenant_id)
        mock_domain_service.list_domains.return_value = [mock_domain]

        response = test_client.get(f"/api/v1/agents/{agent_name}/domains")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    def test_list_domains_agent_not_found(self, client):
        """Test listing domains for non-existent agent."""
        test_client, tenant_id, mock_db, mocks = client

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        response = test_client.get("/api/v1/agents/non-existent/domains")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestCreateAgentDomain:
    """Tests for creating agent domains."""

    def test_create_domain_success(self, client):
        """Test creating a domain for an agent."""
        test_client, tenant_id, mock_db, mocks = client
        mock_domain_service = mocks["domain"].return_value

        agent_id = uuid.uuid4()
        agent_name = "test-agent"
        domain_id = uuid.uuid4()

        mock_agent = _create_mock_agent(agent_id, agent_name, tenant_id)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_agent
        mock_db.execute.return_value = mock_result

        mock_domain = _create_mock_domain(domain_id, agent_id, tenant_id, subdomain="my-subdomain")
        mock_domain_service.create_domain.return_value = mock_domain

        response = test_client.post(
            f"/api/v1/agents/{agent_name}/domains",
            json={"subdomain": "my-subdomain", "chat_page_config": {"show_branding": True}},
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_create_custom_domain(self, client):
        """Test creating a custom domain."""
        test_client, tenant_id, mock_db, mocks = client
        mock_domain_service = mocks["domain"].return_value

        agent_id = uuid.uuid4()
        agent_name = "test-agent"
        domain_id = uuid.uuid4()

        mock_agent = _create_mock_agent(agent_id, agent_name, tenant_id)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_agent
        mock_db.execute.return_value = mock_result

        mock_domain = _create_mock_domain(
            domain_id, agent_id, tenant_id, domain="chat.example.com", is_custom_domain=True
        )
        mock_domain_service.create_domain.return_value = mock_domain

        response = test_client.post(
            f"/api/v1/agents/{agent_name}/domains", json={"domain": "chat.example.com", "chat_page_config": {}}
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_create_domain_invalid_data(self, client):
        """Test creating domain with invalid data."""
        test_client, tenant_id, mock_db, mocks = client
        mock_domain_service = mocks["domain"].return_value

        agent_id = uuid.uuid4()
        agent_name = "test-agent"

        mock_agent = _create_mock_agent(agent_id, agent_name, tenant_id)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_agent
        mock_db.execute.return_value = mock_result

        mock_domain_service.create_domain.side_effect = ValueError("Invalid subdomain")

        response = test_client.post(f"/api/v1/agents/{agent_name}/domains", json={"subdomain": "invalid subdomain!"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestGetAgentDomain:
    """Tests for getting a specific domain."""

    def test_get_domain_success(self, client):
        """Test getting a specific domain."""
        test_client, tenant_id, mock_db, mocks = client
        mock_domain_service = mocks["domain"].return_value

        agent_id = uuid.uuid4()
        agent_name = "test-agent"
        domain_id = uuid.uuid4()

        mock_agent = _create_mock_agent(agent_id, agent_name, tenant_id)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_agent
        mock_db.execute.return_value = mock_result

        mock_domain = _create_mock_domain(domain_id, agent_id, tenant_id)
        mock_domain_service.get_domain.return_value = mock_domain

        response = test_client.get(f"/api/v1/agents/{agent_name}/domains/{domain_id}")

        assert response.status_code == status.HTTP_200_OK

    def test_get_domain_not_found(self, client):
        """Test getting non-existent domain."""
        test_client, tenant_id, mock_db, mocks = client
        mock_domain_service = mocks["domain"].return_value

        agent_id = uuid.uuid4()
        agent_name = "test-agent"

        mock_agent = _create_mock_agent(agent_id, agent_name, tenant_id)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_agent
        mock_db.execute.return_value = mock_result

        mock_domain_service.get_domain.return_value = None

        response = test_client.get(f"/api/v1/agents/{agent_name}/domains/{uuid.uuid4()}")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_domain_wrong_agent(self, client):
        """Test getting domain that belongs to different agent."""
        test_client, tenant_id, mock_db, mocks = client
        mock_domain_service = mocks["domain"].return_value

        agent_id = uuid.uuid4()
        other_agent_id = uuid.uuid4()
        agent_name = "test-agent"
        domain_id = uuid.uuid4()

        mock_agent = _create_mock_agent(agent_id, agent_name, tenant_id)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_agent
        mock_db.execute.return_value = mock_result

        # Domain belongs to different agent
        mock_domain = _create_mock_domain(domain_id, other_agent_id, tenant_id)
        mock_domain_service.get_domain.return_value = mock_domain

        response = test_client.get(f"/api/v1/agents/{agent_name}/domains/{domain_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestUpdateAgentDomain:
    """Tests for updating agent domains."""

    def test_update_domain_success(self, client):
        """Test updating a domain."""
        test_client, tenant_id, mock_db, mocks = client
        mock_domain_service = mocks["domain"].return_value

        agent_id = uuid.uuid4()
        agent_name = "test-agent"
        domain_id = uuid.uuid4()

        mock_agent = _create_mock_agent(agent_id, agent_name, tenant_id)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_agent
        mock_db.execute.return_value = mock_result

        mock_domain = _create_mock_domain(domain_id, agent_id, tenant_id)
        mock_domain_service.get_domain.return_value = mock_domain
        mock_domain_service.update_domain.return_value = mock_domain

        response = test_client.put(
            f"/api/v1/agents/{agent_name}/domains/{domain_id}", json={"subdomain": "updated-subdomain"}
        )

        assert response.status_code == status.HTTP_200_OK


class TestDeleteAgentDomain:
    """Tests for deleting agent domains."""

    def test_delete_domain_success(self, client):
        """Test deleting a domain."""
        test_client, tenant_id, mock_db, mocks = client
        mock_domain_service = mocks["domain"].return_value

        agent_id = uuid.uuid4()
        agent_name = "test-agent"
        domain_id = uuid.uuid4()

        mock_agent = _create_mock_agent(agent_id, agent_name, tenant_id)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_agent
        mock_db.execute.return_value = mock_result

        mock_domain = _create_mock_domain(domain_id, agent_id, tenant_id)
        mock_domain_service.get_domain.return_value = mock_domain

        response = test_client.delete(f"/api/v1/agents/{agent_name}/domains/{domain_id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        mock_domain_service.delete_domain.assert_called_once()


class TestDNSRecords:
    """Tests for DNS records endpoint."""

    def test_get_dns_records_success(self, client):
        """Test getting required DNS records."""
        test_client, tenant_id, mock_db, mocks = client
        mock_domain_service = mocks["domain"].return_value
        mock_dns_service = mocks["dns"].return_value

        agent_id = uuid.uuid4()
        agent_name = "test-agent"
        domain_id = uuid.uuid4()

        mock_agent = _create_mock_agent(agent_id, agent_name, tenant_id)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_agent
        mock_db.execute.return_value = mock_result

        mock_domain = _create_mock_domain(
            domain_id, agent_id, tenant_id, domain="chat.example.com", is_custom_domain=True
        )
        mock_domain_service.get_domain.return_value = mock_domain

        mock_dns_service.get_required_dns_records.return_value = [
            {"type": "CNAME", "name": "chat", "value": "app.synkora.ai"}
        ]

        with patch("src.config.settings.settings") as mock_settings:
            mock_settings.platform_domain = "synkora.ai"
            response = test_client.get(f"/api/v1/agents/{agent_name}/domains/{domain_id}/dns-records")

        assert response.status_code == status.HTTP_200_OK

    def test_get_dns_records_not_custom_domain(self, client):
        """Test getting DNS records for non-custom domain."""
        test_client, tenant_id, mock_db, mocks = client
        mock_domain_service = mocks["domain"].return_value

        agent_id = uuid.uuid4()
        agent_name = "test-agent"
        domain_id = uuid.uuid4()

        mock_agent = _create_mock_agent(agent_id, agent_name, tenant_id)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_agent
        mock_db.execute.return_value = mock_result

        mock_domain = _create_mock_domain(domain_id, agent_id, tenant_id, is_custom_domain=False)
        mock_domain_service.get_domain.return_value = mock_domain

        response = test_client.get(f"/api/v1/agents/{agent_name}/domains/{domain_id}/dns-records")

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestVerifyDomain:
    """Tests for domain verification."""

    def test_verify_domain_success(self, client):
        """Test successful domain verification."""
        test_client, tenant_id, mock_db, mocks = client
        mock_domain_service = mocks["domain"].return_value
        mock_dns_service = mocks["dns"].return_value

        agent_id = uuid.uuid4()
        agent_name = "test-agent"
        domain_id = uuid.uuid4()

        mock_agent = _create_mock_agent(agent_id, agent_name, tenant_id)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_agent
        mock_db.execute.return_value = mock_result

        mock_domain = _create_mock_domain(
            domain_id, agent_id, tenant_id, domain="chat.example.com", is_custom_domain=True
        )
        mock_domain_service.get_domain.return_value = mock_domain
        mock_dns_service.verify_custom_domain.return_value = (True, None)

        response = test_client.post(f"/api/v1/agents/{agent_name}/domains/{domain_id}/verify")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["is_verified"] is True

    def test_verify_domain_failed(self, client):
        """Test failed domain verification."""
        test_client, tenant_id, mock_db, mocks = client
        mock_domain_service = mocks["domain"].return_value
        mock_dns_service = mocks["dns"].return_value

        agent_id = uuid.uuid4()
        agent_name = "test-agent"
        domain_id = uuid.uuid4()

        mock_agent = _create_mock_agent(agent_id, agent_name, tenant_id)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_agent
        mock_db.execute.return_value = mock_result

        mock_domain = _create_mock_domain(
            domain_id, agent_id, tenant_id, domain="chat.example.com", is_custom_domain=True
        )
        mock_domain_service.get_domain.return_value = mock_domain
        mock_dns_service.verify_custom_domain.return_value = (False, "DNS records not found")

        response = test_client.post(f"/api/v1/agents/{agent_name}/domains/{domain_id}/verify")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["is_verified"] is False


class TestPublicDomainResolution:
    """Tests for public domain resolution endpoint."""

    def test_resolve_domain_by_hostname(self, client, mock_domain_resolver):
        """Test resolving domain by hostname."""
        test_client, tenant_id, mock_db, mocks = client

        agent_id = uuid.uuid4()
        mock_agent = _create_mock_agent(agent_id, "test-agent", tenant_id)

        resolver_instance = mock_domain_resolver.return_value
        resolver_instance.resolve_agent_from_domain.return_value = mock_agent
        resolver_instance.get_chat_config.return_value = {"theme": "light"}

        response = test_client.get("/api/domains/resolve?hostname=test-agent.synkora.ai")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["agent_id"] == str(agent_id)

    def test_resolve_domain_by_agent_slug(self, client, mock_domain_resolver):
        """Test resolving domain by agent slug."""
        test_client, tenant_id, mock_db, mocks = client

        agent_id = uuid.uuid4()
        mock_agent = _create_mock_agent(agent_id, "test-agent", tenant_id)

        resolver_instance = mock_domain_resolver.return_value
        resolver_instance.resolve_agent_by_slug.return_value = mock_agent
        resolver_instance.get_chat_config.return_value = {"theme": "light"}

        response = test_client.get("/api/domains/resolve?agent_slug=test-agent")

        assert response.status_code == status.HTTP_200_OK

    def test_resolve_domain_not_found(self, client, mock_domain_resolver):
        """Test resolving non-existent domain."""
        test_client, tenant_id, mock_db, mocks = client

        resolver_instance = mock_domain_resolver.return_value
        resolver_instance.resolve_agent_from_domain.return_value = None

        response = test_client.get("/api/domains/resolve?hostname=unknown.example.com")

        assert response.status_code == status.HTTP_404_NOT_FOUND
