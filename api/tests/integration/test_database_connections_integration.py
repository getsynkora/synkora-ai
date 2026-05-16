"""
Integration tests for Database Connections endpoints.

Tests CRUD operations for database connections (PostgreSQL, SQLite, Elasticsearch).
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

    email = f"dbconn_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecureTestPass123!"

    # Register
    response = client.post(
        "/console/api/auth/register",
        json={
            "email": email,
            "password": password,
            "name": "DB Connection Test User",
            "tenant_name": "DB Connection Test Org",
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

    return {"Authorization": f"Bearer {token}"}, tenant_id


class TestDatabaseConnectionsCRUDIntegration:
    """Test Database Connections CRUD operations."""

    def test_database_connection_full_lifecycle(self, client: TestClient, db_session: Session, auth_headers):
        """Test complete database connection lifecycle: create -> get -> update -> delete."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id = auth_headers
        connection_name = f"TestDBConn_{uuid.uuid4().hex[:8]}"

        # 1. Create Database Connection (PostgreSQL)
        create_response = client.post(
            "/api/v1/database-connections",
            json={
                "name": connection_name,
                "type": "POSTGRESQL",
                "host": "localhost",
                "port": 5432,
                "database": "test_db",
                "username": "test_user",
                "password": "test_password",
            },
            headers=headers,
        )

        assert create_response.status_code == status.HTTP_201_CREATED
        create_data = create_response.json()
        assert create_data["name"] == connection_name
        assert create_data["type"] == "POSTGRESQL"
        assert create_data["host"] == "localhost"
        assert create_data["port"] == 5432
        connection_id = create_data["id"]

        # 2. Get Database Connection
        get_response = client.get(f"/api/v1/database-connections/{connection_id}", headers=headers)
        assert get_response.status_code == status.HTTP_200_OK
        get_data = get_response.json()
        assert get_data["name"] == connection_name

        # 3. List Database Connections
        list_response = client.get("/api/v1/database-connections", headers=headers)
        assert list_response.status_code == status.HTTP_200_OK
        list_data = list_response.json()
        connection_ids = [c["id"] for c in list_data]
        assert connection_id in connection_ids

        # 4. Update Database Connection
        update_response = client.put(
            f"/api/v1/database-connections/{connection_id}",
            json={
                "name": f"{connection_name}_updated",
                "host": "db.example.com",
                "port": 5433,
            },
            headers=headers,
        )
        assert update_response.status_code == status.HTTP_200_OK
        update_data = update_response.json()
        assert update_data["name"] == f"{connection_name}_updated"
        assert update_data["host"] == "db.example.com"
        assert update_data["port"] == 5433
        # Status should be reset to pending since connection details changed
        assert update_data["status"] == "pending"

        # 5. Delete Database Connection
        delete_response = client.delete(f"/api/v1/database-connections/{connection_id}", headers=headers)
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT

        # Verify deletion
        verify_response = client.get(f"/api/v1/database-connections/{connection_id}", headers=headers)
        assert verify_response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_sqlite_connection(self, client: TestClient, db_session: Session, auth_headers):
        """Test creating a SQLite database connection."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id = auth_headers
        connection_name = f"SQLiteConn_{uuid.uuid4().hex[:8]}"

        response = client.post(
            "/api/v1/database-connections",
            json={
                "name": connection_name,
                "type": "SQLITE",
                "database_path": "/tmp/test_database.db",
            },
            headers=headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["type"] == "SQLITE"
        assert data["database_path"] == "/tmp/test_database.db"

    def test_create_elasticsearch_connection(self, client: TestClient, db_session: Session, auth_headers):
        """Test creating an Elasticsearch database connection."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id = auth_headers
        connection_name = f"ESConn_{uuid.uuid4().hex[:8]}"

        response = client.post(
            "/api/v1/database-connections",
            json={
                "name": connection_name,
                "type": "ELASTICSEARCH",
                "host": "localhost",
                "port": 9200,
                # Elasticsearch doesn't require credentials
            },
            headers=headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["type"] == "ELASTICSEARCH"
        assert data["host"] == "localhost"
        assert data["port"] == 9200

    def test_create_postgresql_without_credentials_fails(self, client: TestClient, db_session: Session, auth_headers):
        """Test that creating PostgreSQL connection without credentials fails."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id = auth_headers

        response = client.post(
            "/api/v1/database-connections",
            json={
                "name": f"NoCreds_{uuid.uuid4().hex[:8]}",
                "type": "POSTGRESQL",
                "host": "localhost",
                "port": 5432,
                "database": "test_db",
                # Missing username and password
            },
            headers=headers,
        )

        # 400 for business logic, 422 for pydantic validation
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_CONTENT]

    def test_create_sqlite_without_path_fails(self, client: TestClient, db_session: Session, auth_headers):
        """Test that creating SQLite connection without database_path fails."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id = auth_headers

        response = client.post(
            "/api/v1/database-connections",
            json={
                "name": f"NoPath_{uuid.uuid4().hex[:8]}",
                "type": "SQLITE",
                # Missing database_path
            },
            headers=headers,
        )

        # 400 for business logic, 422 for pydantic validation
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_CONTENT]

    def test_create_http_without_host_fails(self, client: TestClient, db_session: Session, auth_headers):
        """Test that creating non-SQLite connection without host fails."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id = auth_headers

        response = client.post(
            "/api/v1/database-connections",
            json={
                "name": f"NoHost_{uuid.uuid4().hex[:8]}",
                "type": "POSTGRESQL",
                # Missing host and port
                "database": "test_db",
                "username": "user",
                "password": "pass",
            },
            headers=headers,
        )

        # 400 for business logic, 422 for pydantic validation
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_CONTENT]

    def test_get_nonexistent_connection(self, client: TestClient, db_session: Session, auth_headers):
        """Test getting a nonexistent connection returns 404."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id = auth_headers
        fake_id = str(uuid.uuid4())

        response = client.get(f"/api/v1/database-connections/{fake_id}", headers=headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_nonexistent_connection(self, client: TestClient, db_session: Session, auth_headers):
        """Test updating a nonexistent connection returns 404."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id = auth_headers
        fake_id = str(uuid.uuid4())

        response = client.put(
            f"/api/v1/database-connections/{fake_id}",
            json={"name": "Updated"},
            headers=headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_nonexistent_connection(self, client: TestClient, db_session: Session, auth_headers):
        """Test deleting a nonexistent connection returns 404."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id = auth_headers
        fake_id = str(uuid.uuid4())

        response = client.delete(f"/api/v1/database-connections/{fake_id}", headers=headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_connection_status(self, client: TestClient, db_session: Session, auth_headers):
        """Test updating connection status directly."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id = auth_headers
        connection_name = f"StatusConn_{uuid.uuid4().hex[:8]}"

        # Create connection
        create_response = client.post(
            "/api/v1/database-connections",
            json={
                "name": connection_name,
                "type": "POSTGRESQL",
                "host": "localhost",
                "port": 5432,
                "database": "test_db",
                "username": "user",
                "password": "pass",
            },
            headers=headers,
        )
        connection_id = create_response.json()["id"]

        # Update status to inactive
        update_response = client.put(
            f"/api/v1/database-connections/{connection_id}",
            json={"status": "inactive"},
            headers=headers,
        )

        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.json()["status"] == "inactive"

    def test_create_connection_with_params(self, client: TestClient, db_session: Session, auth_headers):
        """Test creating connection with extra connection parameters."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id = auth_headers
        connection_name = f"ParamsConn_{uuid.uuid4().hex[:8]}"

        response = client.post(
            "/api/v1/database-connections",
            json={
                "name": connection_name,
                "type": "POSTGRESQL",
                "host": "localhost",
                "port": 5432,
                "database": "test_db",
                "username": "user",
                "password": "pass",
                "connection_params": {
                    "sslmode": "require",
                    "connect_timeout": 30,
                },
            },
            headers=headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["connection_params"]["sslmode"] == "require"
        assert data["connection_params"]["connect_timeout"] == 30


class TestDatabaseConnectionsTestEndpoint:
    """Test database connection test endpoints."""

    def test_test_postgresql_connection(self, client: TestClient, db_session: Session, auth_headers):
        """Test testing a PostgreSQL connection configuration."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id = auth_headers

        # Test connection (won't actually connect, but validates structure)
        response = client.post(
            "/api/v1/database-connections/test",
            json={
                "name": "Test Connection",
                "type": "POSTGRESQL",
                "host": "localhost",
                "port": 5432,
                "database": "test_db",
                "username": "user",
                "password": "pass",
            },
            headers=headers,
        )

        # Will fail to connect but should return a proper response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Connection likely fails since no real DB, but response structure is correct
        assert "success" in data
        assert "message" in data

    def test_test_existing_connection(self, client: TestClient, db_session: Session, auth_headers):
        """Test testing an existing database connection."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id = auth_headers
        connection_name = f"ExistingConn_{uuid.uuid4().hex[:8]}"

        # Create connection first
        create_response = client.post(
            "/api/v1/database-connections",
            json={
                "name": connection_name,
                "type": "POSTGRESQL",
                "host": "localhost",
                "port": 5432,
                "database": "test_db",
                "username": "user",
                "password": "pass",
            },
            headers=headers,
        )
        connection_id = create_response.json()["id"]

        # Test existing connection
        response = client.post(
            f"/api/v1/database-connections/{connection_id}/test",
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "success" in data
        assert "message" in data

    def test_test_nonexistent_connection(self, client: TestClient, db_session: Session, auth_headers):
        """Test testing a nonexistent connection returns 404."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id = auth_headers
        fake_id = str(uuid.uuid4())

        response = client.post(
            f"/api/v1/database-connections/{fake_id}/test",
            headers=headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestDatabaseConnectionsTenantIsolation:
    """Test database connections tenant isolation."""

    def test_cannot_access_other_tenant_connection(self, client: TestClient, db_session: Session):
        """Test that users cannot access connections from other tenants."""
        from src.core.database import get_db
        from src.models import Account, AccountStatus

        client.app.dependency_overrides[get_db] = lambda: db_session

        # Create first user/tenant
        email1 = f"tenant1_conn_{uuid.uuid4().hex[:8]}@example.com"
        client.post(
            "/console/api/auth/register",
            json={
                "email": email1,
                "password": "SecureTestPass123!",
                "name": "Tenant 1 User",
                "tenant_name": "Tenant 1 Org",
            },
        )
        account1 = db_session.query(Account).filter_by(email=email1).first()
        account1.status = AccountStatus.ACTIVE
        db_session.commit()

        login1 = client.post("/console/api/auth/login", json={"email": email1, "password": "SecureTestPass123!"})
        token1 = login1.json()["data"]["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}

        # Create second user/tenant
        email2 = f"tenant2_conn_{uuid.uuid4().hex[:8]}@example.com"
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

        # Create connection as tenant 1
        connection_name = f"IsolatedConn_{uuid.uuid4().hex[:8]}"
        create_response = client.post(
            "/api/v1/database-connections",
            json={
                "name": connection_name,
                "type": "POSTGRESQL",
                "host": "localhost",
                "port": 5432,
                "database": "test_db",
                "username": "user",
                "password": "pass",
            },
            headers=headers1,
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        connection_id = create_response.json()["id"]

        # Tenant 2 should not be able to access tenant 1's connection
        get_response = client.get(f"/api/v1/database-connections/{connection_id}", headers=headers2)
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

        # Tenant 2 should not be able to update tenant 1's connection
        update_response = client.put(
            f"/api/v1/database-connections/{connection_id}",
            json={"name": "Hacked Connection"},
            headers=headers2,
        )
        assert update_response.status_code == status.HTTP_404_NOT_FOUND

        # Tenant 2 should not be able to delete tenant 1's connection
        delete_response = client.delete(f"/api/v1/database-connections/{connection_id}", headers=headers2)
        assert delete_response.status_code == status.HTTP_404_NOT_FOUND

        # Tenant 2 should not be able to test tenant 1's connection
        test_response = client.post(f"/api/v1/database-connections/{connection_id}/test", headers=headers2)
        assert test_response.status_code == status.HTTP_404_NOT_FOUND

    def test_tenant_list_isolation(self, client: TestClient, db_session: Session):
        """Test that listing connections only shows tenant's own connections."""
        from src.core.database import get_db
        from src.models import Account, AccountStatus

        client.app.dependency_overrides[get_db] = lambda: db_session

        # Create first user/tenant
        email1 = f"list1_{uuid.uuid4().hex[:8]}@example.com"
        client.post(
            "/console/api/auth/register",
            json={
                "email": email1,
                "password": "SecureTestPass123!",
                "name": "Tenant 1 User",
                "tenant_name": "List Tenant 1",
            },
        )
        account1 = db_session.query(Account).filter_by(email=email1).first()
        account1.status = AccountStatus.ACTIVE
        db_session.commit()

        login1 = client.post("/console/api/auth/login", json={"email": email1, "password": "SecureTestPass123!"})
        token1 = login1.json()["data"]["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}

        # Create second user/tenant
        email2 = f"list2_{uuid.uuid4().hex[:8]}@example.com"
        client.post(
            "/console/api/auth/register",
            json={
                "email": email2,
                "password": "SecureTestPass123!",
                "name": "Tenant 2 User",
                "tenant_name": "List Tenant 2",
            },
        )
        account2 = db_session.query(Account).filter_by(email=email2).first()
        account2.status = AccountStatus.ACTIVE
        db_session.commit()

        login2 = client.post("/console/api/auth/login", json={"email": email2, "password": "SecureTestPass123!"})
        token2 = login2.json()["data"]["access_token"]
        headers2 = {"Authorization": f"Bearer {token2}"}

        # Create connection for tenant 1
        conn_name_1 = f"T1Conn_{uuid.uuid4().hex[:8]}"
        client.post(
            "/api/v1/database-connections",
            json={
                "name": conn_name_1,
                "type": "SQLITE",
                "database_path": "/tmp/tenant1.db",
            },
            headers=headers1,
        )

        # Create connection for tenant 2
        conn_name_2 = f"T2Conn_{uuid.uuid4().hex[:8]}"
        client.post(
            "/api/v1/database-connections",
            json={
                "name": conn_name_2,
                "type": "SQLITE",
                "database_path": "/tmp/tenant2.db",
            },
            headers=headers2,
        )

        # List connections for tenant 1
        list_response1 = client.get("/api/v1/database-connections", headers=headers1)
        assert list_response1.status_code == status.HTTP_200_OK
        names1 = [c["name"] for c in list_response1.json()]
        assert conn_name_1 in names1
        assert conn_name_2 not in names1

        # List connections for tenant 2
        list_response2 = client.get("/api/v1/database-connections", headers=headers2)
        assert list_response2.status_code == status.HTTP_200_OK
        names2 = [c["name"] for c in list_response2.json()]
        assert conn_name_2 in names2
        assert conn_name_1 not in names2


class TestDatabaseConnectionsValidation:
    """Test database connection validation."""

    def test_invalid_port_fails(self, client: TestClient, db_session: Session, auth_headers):
        """Test that invalid port number fails validation."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id = auth_headers

        # Port 0 is invalid
        response = client.post(
            "/api/v1/database-connections",
            json={
                "name": f"BadPort_{uuid.uuid4().hex[:8]}",
                "type": "POSTGRESQL",
                "host": "localhost",
                "port": 0,  # Invalid
                "database": "test_db",
                "username": "user",
                "password": "pass",
            },
            headers=headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_invalid_port_too_high_fails(self, client: TestClient, db_session: Session, auth_headers):
        """Test that port > 65535 fails validation."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id = auth_headers

        response = client.post(
            "/api/v1/database-connections",
            json={
                "name": f"HighPort_{uuid.uuid4().hex[:8]}",
                "type": "POSTGRESQL",
                "host": "localhost",
                "port": 70000,  # Invalid - too high
                "database": "test_db",
                "username": "user",
                "password": "pass",
            },
            headers=headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_empty_name_fails(self, client: TestClient, db_session: Session, auth_headers):
        """Test that empty name fails validation."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id = auth_headers

        response = client.post(
            "/api/v1/database-connections",
            json={
                "name": "",  # Empty
                "type": "SQLITE",
                "database_path": "/tmp/test.db",
            },
            headers=headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_invalid_status_update_fails(self, client: TestClient, db_session: Session, auth_headers):
        """Test that invalid status value fails validation."""
        from src.core.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db_session

        headers, tenant_id = auth_headers
        connection_name = f"StatusValConn_{uuid.uuid4().hex[:8]}"

        # Create connection
        create_response = client.post(
            "/api/v1/database-connections",
            json={
                "name": connection_name,
                "type": "SQLITE",
                "database_path": "/tmp/test.db",
            },
            headers=headers,
        )
        connection_id = create_response.json()["id"]

        # Update with invalid status
        response = client.put(
            f"/api/v1/database-connections/{connection_id}",
            json={"status": "invalid_status"},  # Not in allowed values
            headers=headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
