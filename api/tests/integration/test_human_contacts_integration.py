"""
Integration tests for Human Contacts endpoints.

Tests CRUD operations for human contacts that agents can escalate to.
"""

import uuid

import pytest
import pytest_asyncio
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture
async def auth_headers(async_client: AsyncClient, async_db_session: AsyncSession):
    """Create authenticated user and return headers with tenant info."""
    from src.models import Account, AccountStatus

    email = f"human_contacts_test_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecureTestPass123!"

    # Register
    response = await async_client.post(
        "/console/api/auth/register",
        json={
            "email": email,
            "password": password,
            "name": "Human Contacts Test User",
            "tenant_name": "Human Contacts Test Org",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    tenant_id = data["data"]["tenant"]["id"]

    # Activate account
    result = await async_db_session.execute(select(Account).filter_by(email=email))
    account = result.scalar_one_or_none()
    account.status = AccountStatus.ACTIVE
    await async_db_session.commit()

    # Login
    login_response = await async_client.post(
        "/console/api/auth/login",
        json={"email": email, "password": password},
    )
    token = login_response.json()["data"]["access_token"]

    return {"Authorization": f"Bearer {token}"}, tenant_id, account


class TestHumanContactsListIntegration:
    """Test Human Contacts listing operations."""

    @pytest.mark.asyncio
    async def test_list_contacts(self, async_client: AsyncClient, auth_headers):
        """Test listing human contacts."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/human-contacts", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_list_contacts_with_active_only_filter(self, async_client: AsyncClient, auth_headers):
        """Test listing contacts with active_only filter."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/human-contacts?active_only=true", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_list_contacts_with_search(self, async_client: AsyncClient, auth_headers):
        """Test listing contacts with search parameter."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/human-contacts?search=test", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)


class TestHumanContactsCRUDIntegration:
    """Test Human Contacts CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_contact(self, async_client: AsyncClient, auth_headers):
        """Test creating a human contact."""
        headers, tenant_id, account = auth_headers

        contact_name = f"Test Contact {uuid.uuid4().hex[:8]}"
        response = await async_client.post(
            "/api/v1/human-contacts",
            json={
                "name": contact_name,
                "email": f"contact_{uuid.uuid4().hex[:8]}@example.com",
                "preferred_channel": "email",
                "timezone": "UTC",
                "notification_preferences": "all",
            },
            headers=headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == contact_name
        assert "id" in data
        assert data["is_active"] is True
        assert data["preferred_channel"] == "email"

    @pytest.mark.asyncio
    async def test_create_contact_with_slack(self, async_client: AsyncClient, auth_headers):
        """Test creating a contact with Slack details."""
        headers, tenant_id, account = auth_headers

        response = await async_client.post(
            "/api/v1/human-contacts",
            json={
                "name": f"Slack Contact {uuid.uuid4().hex[:8]}",
                "slack_user_id": "U12345678",
                "slack_workspace_id": "W12345678",
                "preferred_channel": "slack",
            },
            headers=headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["slack_user_id"] == "U12345678"
        assert data["preferred_channel"] == "slack"

    @pytest.mark.asyncio
    async def test_create_contact_with_whatsapp(self, async_client: AsyncClient, auth_headers):
        """Test creating a contact with WhatsApp number."""
        headers, tenant_id, account = auth_headers

        response = await async_client.post(
            "/api/v1/human-contacts",
            json={
                "name": f"WhatsApp Contact {uuid.uuid4().hex[:8]}",
                "whatsapp_number": "+1234567890",
                "preferred_channel": "whatsapp",
            },
            headers=headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["whatsapp_number"] == "+1234567890"
        assert data["preferred_channel"] == "whatsapp"

    @pytest.mark.asyncio
    async def test_get_contact(self, async_client: AsyncClient, auth_headers):
        """Test getting a specific contact."""
        headers, tenant_id, account = auth_headers

        # Create a contact first
        create_response = await async_client.post(
            "/api/v1/human-contacts",
            json={
                "name": f"Get Test Contact {uuid.uuid4().hex[:8]}",
                "email": f"get_test_{uuid.uuid4().hex[:8]}@example.com",
            },
            headers=headers,
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        contact_id = create_response.json()["id"]

        # Get the contact
        response = await async_client.get(f"/api/v1/human-contacts/{contact_id}", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == contact_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_contact(self, async_client: AsyncClient, auth_headers):
        """Test getting a nonexistent contact returns 404."""
        headers, tenant_id, account = auth_headers

        fake_id = str(uuid.uuid4())
        response = await async_client.get(f"/api/v1/human-contacts/{fake_id}", headers=headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_update_contact(self, async_client: AsyncClient, auth_headers):
        """Test updating a contact."""
        headers, tenant_id, account = auth_headers

        # Create a contact first
        create_response = await async_client.post(
            "/api/v1/human-contacts",
            json={
                "name": f"Update Test Contact {uuid.uuid4().hex[:8]}",
                "email": f"update_test_{uuid.uuid4().hex[:8]}@example.com",
            },
            headers=headers,
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        contact_id = create_response.json()["id"]

        # Update the contact
        new_name = f"Updated Contact {uuid.uuid4().hex[:8]}"
        response = await async_client.put(
            f"/api/v1/human-contacts/{contact_id}",
            json={"name": new_name, "timezone": "America/New_York"},
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == new_name
        assert data["timezone"] == "America/New_York"

    @pytest.mark.asyncio
    async def test_update_nonexistent_contact(self, async_client: AsyncClient, auth_headers):
        """Test updating a nonexistent contact returns 404."""
        headers, tenant_id, account = auth_headers

        fake_id = str(uuid.uuid4())
        response = await async_client.put(
            f"/api/v1/human-contacts/{fake_id}",
            json={"name": "New Name"},
            headers=headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_contact(self, async_client: AsyncClient, auth_headers):
        """Test deleting a contact."""
        headers, tenant_id, account = auth_headers

        # Create a contact first
        create_response = await async_client.post(
            "/api/v1/human-contacts",
            json={
                "name": f"Delete Test Contact {uuid.uuid4().hex[:8]}",
                "email": f"delete_test_{uuid.uuid4().hex[:8]}@example.com",
            },
            headers=headers,
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        contact_id = create_response.json()["id"]

        # Delete the contact
        response = await async_client.delete(f"/api/v1/human-contacts/{contact_id}", headers=headers)

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify it's deleted
        get_response = await async_client.get(f"/api/v1/human-contacts/{contact_id}", headers=headers)
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_nonexistent_contact(self, async_client: AsyncClient, auth_headers):
        """Test deleting a nonexistent contact returns 404."""
        headers, tenant_id, account = auth_headers

        fake_id = str(uuid.uuid4())
        response = await async_client.delete(f"/api/v1/human-contacts/{fake_id}", headers=headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_deactivate_contact(self, async_client: AsyncClient, auth_headers):
        """Test deactivating a contact."""
        headers, tenant_id, account = auth_headers

        # Create a contact first
        create_response = await async_client.post(
            "/api/v1/human-contacts",
            json={
                "name": f"Deactivate Test Contact {uuid.uuid4().hex[:8]}",
                "email": f"deactivate_test_{uuid.uuid4().hex[:8]}@example.com",
            },
            headers=headers,
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        contact_id = create_response.json()["id"]
        assert create_response.json()["is_active"] is True

        # Deactivate the contact
        response = await async_client.post(f"/api/v1/human-contacts/{contact_id}/deactivate", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["is_active"] is False

    @pytest.mark.asyncio
    async def test_deactivate_nonexistent_contact(self, async_client: AsyncClient, auth_headers):
        """Test deactivating a nonexistent contact returns 404."""
        headers, tenant_id, account = auth_headers

        fake_id = str(uuid.uuid4())
        response = await async_client.post(f"/api/v1/human-contacts/{fake_id}/deactivate", headers=headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestHumanContactsValidation:
    """Test Human Contacts validation."""

    @pytest.mark.asyncio
    async def test_create_contact_missing_name(self, async_client: AsyncClient, auth_headers):
        """Test creating contact without name fails validation."""
        headers, tenant_id, account = auth_headers

        response = await async_client.post(
            "/api/v1/human-contacts",
            json={
                "email": "test@example.com",
            },
            headers=headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_create_contact_empty_name(self, async_client: AsyncClient, auth_headers):
        """Test creating contact with empty name fails validation."""
        headers, tenant_id, account = auth_headers

        response = await async_client.post(
            "/api/v1/human-contacts",
            json={
                "name": "",
                "email": "test@example.com",
            },
            headers=headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_create_contact_invalid_email(self, async_client: AsyncClient, auth_headers):
        """Test creating contact with invalid email fails validation."""
        headers, tenant_id, account = auth_headers

        response = await async_client.post(
            "/api/v1/human-contacts",
            json={
                "name": "Test Contact",
                "email": "not-an-email",
            },
            headers=headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_create_contact_invalid_preferred_channel(self, async_client: AsyncClient, auth_headers):
        """Test creating contact with invalid preferred channel fails validation."""
        headers, tenant_id, account = auth_headers

        response = await async_client.post(
            "/api/v1/human-contacts",
            json={
                "name": "Test Contact",
                "preferred_channel": "invalid_channel",
            },
            headers=headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_create_contact_invalid_notification_preferences(self, async_client: AsyncClient, auth_headers):
        """Test creating contact with invalid notification preferences fails validation."""
        headers, tenant_id, account = auth_headers

        response = await async_client.post(
            "/api/v1/human-contacts",
            json={
                "name": "Test Contact",
                "notification_preferences": "invalid_pref",
            },
            headers=headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_get_contact_invalid_id_format(self, async_client: AsyncClient, auth_headers):
        """Test getting contact with invalid ID format returns 400."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/human-contacts/not-a-uuid", headers=headers)

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestHumanContactsTenantIsolation:
    """Test Human Contacts tenant isolation."""

    @pytest.mark.asyncio
    async def test_contacts_are_tenant_isolated(self, async_client: AsyncClient, async_db_session: AsyncSession):
        """Test that contacts are isolated between tenants."""
        from src.models import Account, AccountStatus

        # Create first tenant
        email1 = f"tenant1_contacts_{uuid.uuid4().hex[:8]}@example.com"
        await async_client.post(
            "/console/api/auth/register",
            json={
                "email": email1,
                "password": "SecureTestPass123!",
                "name": "Tenant 1 User",
                "tenant_name": "Tenant 1 Org",
            },
        )
        result1 = await async_db_session.execute(select(Account).filter_by(email=email1))
        account1 = result1.scalar_one_or_none()
        account1.status = AccountStatus.ACTIVE
        await async_db_session.commit()

        login1 = await async_client.post(
            "/console/api/auth/login", json={"email": email1, "password": "SecureTestPass123!"}
        )
        token1 = login1.json()["data"]["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}

        # Create second tenant
        email2 = f"tenant2_contacts_{uuid.uuid4().hex[:8]}@example.com"
        await async_client.post(
            "/console/api/auth/register",
            json={
                "email": email2,
                "password": "SecureTestPass123!",
                "name": "Tenant 2 User",
                "tenant_name": "Tenant 2 Org",
            },
        )
        result2 = await async_db_session.execute(select(Account).filter_by(email=email2))
        account2 = result2.scalar_one_or_none()
        account2.status = AccountStatus.ACTIVE
        await async_db_session.commit()

        login2 = await async_client.post(
            "/console/api/auth/login", json={"email": email2, "password": "SecureTestPass123!"}
        )
        token2 = login2.json()["data"]["access_token"]
        headers2 = {"Authorization": f"Bearer {token2}"}

        # Create a contact in tenant 1
        create_response = await async_client.post(
            "/api/v1/human-contacts",
            json={
                "name": f"Tenant 1 Contact {uuid.uuid4().hex[:8]}",
                "email": f"tenant1_contact_{uuid.uuid4().hex[:8]}@example.com",
            },
            headers=headers1,
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        contact_id = create_response.json()["id"]

        # Tenant 2 should not be able to access tenant 1's contact
        get_response = await async_client.get(f"/api/v1/human-contacts/{contact_id}", headers=headers2)
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

        # Tenant 2's list should not include tenant 1's contact
        list_response = await async_client.get("/api/v1/human-contacts", headers=headers2)
        assert list_response.status_code == status.HTTP_200_OK
        contacts = list_response.json()
        contact_ids = [c["id"] for c in contacts]
        assert contact_id not in contact_ids


class TestHumanContactsAuthorization:
    """Test Human Contacts authorization."""

    @pytest.mark.asyncio
    async def test_list_contacts_unauthorized(self, async_client: AsyncClient):
        """Test that unauthenticated requests to list are rejected."""
        response = await async_client.get("/api/v1/human-contacts")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    async def test_create_contact_unauthorized(self, async_client: AsyncClient):
        """Test that unauthenticated requests to create are rejected."""
        response = await async_client.post(
            "/api/v1/human-contacts",
            json={"name": "Unauthorized Contact"},
        )

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    async def test_get_contact_unauthorized(self, async_client: AsyncClient):
        """Test that unauthenticated requests to get are rejected."""
        response = await async_client.get(f"/api/v1/human-contacts/{uuid.uuid4()}")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    async def test_update_contact_unauthorized(self, async_client: AsyncClient):
        """Test that unauthenticated requests to update are rejected."""
        response = await async_client.put(
            f"/api/v1/human-contacts/{uuid.uuid4()}",
            json={"name": "New Name"},
        )

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    async def test_delete_contact_unauthorized(self, async_client: AsyncClient):
        """Test that unauthenticated requests to delete are rejected."""
        response = await async_client.delete(f"/api/v1/human-contacts/{uuid.uuid4()}")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    async def test_deactivate_contact_unauthorized(self, async_client: AsyncClient):
        """Test that unauthenticated requests to deactivate are rejected."""
        response = await async_client.post(f"/api/v1/human-contacts/{uuid.uuid4()}/deactivate")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
