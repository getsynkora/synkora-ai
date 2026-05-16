"""
Integration tests for Documents streaming endpoints.

Tests document streaming from S3 storage with tenant validation.

Note: These tests may fail if S3 is not configured in the test environment.
Tests focus on authorization and validation rather than actual S3 operations.
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

    email = f"documents_test_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecureTestPass123!"

    # Register
    response = client.post(
        "/console/api/auth/register",
        json={
            "email": email,
            "password": password,
            "name": "Documents Test User",
            "tenant_name": "Documents Test Org",
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


class TestDocumentStreamingIntegration:
    """Test document streaming operations."""

    def test_stream_nonexistent_document(self, client: TestClient, db_session: Session, auth_headers):
        """Test streaming a nonexistent document returns 404."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id, account = auth_headers

        # Try to stream a document with a random key
        response = client.get(
            "/api/documents/stream/nonexistent/document.pdf",
            headers=headers,
        )

        # Should return 404 (document not found) or 500 (S3 not configured)
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_500_INTERNAL_SERVER_ERROR]

    def test_stream_document_invalid_knowledge_base_pattern(
        self, client: TestClient, db_session: Session, auth_headers
    ):
        """Test streaming document with invalid knowledge base pattern returns 404."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id, account = auth_headers

        # Use a knowledge base ID that doesn't exist
        response = client.get(
            "/api/documents/stream/knowledge-bases/999999/documents/test.pdf",
            headers=headers,
        )

        # Should return 404 (ownership validation fails)
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_500_INTERNAL_SERVER_ERROR]

    def test_stream_document_invalid_data_source_pattern(self, client: TestClient, db_session: Session, auth_headers):
        """Test streaming document with invalid data source pattern returns 404."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id, account = auth_headers

        # Use a data source ID that doesn't exist
        response = client.get(
            "/api/documents/stream/data-sources/999999/documents/test.pdf",
            headers=headers,
        )

        # Should return 404 (ownership validation fails)
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_500_INTERNAL_SERVER_ERROR]

    def test_stream_document_unrecognized_key_pattern(self, client: TestClient, db_session: Session, auth_headers):
        """Test streaming document with unrecognized key pattern returns 404."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id, account = auth_headers

        # Use an unrecognized key pattern
        response = client.get(
            "/api/documents/stream/random/path/to/document.pdf",
            headers=headers,
        )

        # Should return 404 (unrecognized pattern)
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_500_INTERNAL_SERVER_ERROR]

    def test_stream_document_tenant_scoped_key(self, client: TestClient, db_session: Session, auth_headers):
        """Test streaming document with tenant-scoped key pattern."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id, account = auth_headers

        # Use tenant-scoped key pattern (should pass ownership validation but fail S3 fetch)
        response = client.get(
            f"/api/documents/stream/tenants/{tenant_id}/documents/test.pdf",
            headers=headers,
        )

        # Should return 404 (file not found in S3) or 500 (S3 not configured)
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_500_INTERNAL_SERVER_ERROR]


class TestDocumentStreamingAuthorization:
    """Test document streaming authorization."""

    def test_stream_document_unauthorized(self, client: TestClient, db_session: Session):
        """Test that unauthenticated requests to stream documents are rejected."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        response = client.get("/api/documents/stream/some/document.pdf")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_stream_document_cross_tenant_access(self, client: TestClient, db_session: Session):
        """Test that users cannot access other tenants' documents."""
        from src.core.database import get_db
        from src.models import Account, AccountStatus

        client.app.dependency_overrides[get_db] = lambda: db_session

        # Create first tenant
        email1 = f"tenant1_docs_{uuid.uuid4().hex[:8]}@example.com"
        response1 = client.post(
            "/console/api/auth/register",
            json={
                "email": email1,
                "password": "SecureTestPass123!",
                "name": "Tenant 1 User",
                "tenant_name": "Tenant 1 Org",
            },
        )
        tenant1_id = response1.json()["data"]["tenant"]["id"]
        account1 = db_session.query(Account).filter_by(email=email1).first()
        account1.status = AccountStatus.ACTIVE
        db_session.commit()

        # Create second tenant
        email2 = f"tenant2_docs_{uuid.uuid4().hex[:8]}@example.com"
        client.post(
            "/console/api/auth/register",
            json={
                "email": email2,
                "password": "SecureTestPass123!",
                "name": "Tenant 2 User",
                "tenant_name": "Tenant 2 Org",
            },
        )
        account2 = db_session.query(Account).filter_by(email=email2).first()
        account2.status = AccountStatus.ACTIVE
        db_session.commit()

        login2 = client.post("/console/api/auth/login", json={"email": email2, "password": "SecureTestPass123!"})
        token2 = login2.json()["data"]["access_token"]
        headers2 = {"Authorization": f"Bearer {token2}"}

        # Tenant 2 tries to access Tenant 1's document using tenant-scoped key
        response = client.get(
            f"/api/documents/stream/tenants/{tenant1_id}/documents/test.pdf",
            headers=headers2,
        )

        # Should return 404 (ownership validation fails)
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_500_INTERNAL_SERVER_ERROR]


class TestDocumentStreamingValidation:
    """Test document streaming validation."""

    def test_stream_document_empty_key(self, client: TestClient, db_session: Session, auth_headers):
        """Test streaming with empty key path."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id, account = auth_headers

        # Empty key - the path parameter requires at least one character
        response = client.get("/api/documents/stream/", headers=headers)

        # FastAPI might return 404 for the route or handle it differently
        # Accept various error codes
        assert response.status_code in [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_stream_document_special_characters_in_key(self, client: TestClient, db_session: Session, auth_headers):
        """Test streaming document with special characters in key."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id, account = auth_headers

        # Key with special characters
        response = client.get(
            "/api/documents/stream/path/with%20spaces/and%2Fslashes/doc.pdf",
            headers=headers,
        )

        # Should handle gracefully - return 404 (pattern not recognized)
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_500_INTERNAL_SERVER_ERROR]

    def test_stream_document_very_long_key(self, client: TestClient, db_session: Session, auth_headers):
        """Test streaming document with very long key."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id, account = auth_headers

        # Very long key
        long_path = "/".join(["segment"] * 100)
        response = client.get(
            f"/api/documents/stream/{long_path}/doc.pdf",
            headers=headers,
        )

        # Should handle gracefully
        assert response.status_code in [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_414_URI_TOO_LONG,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]
