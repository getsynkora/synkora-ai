"""
Unit tests for Authentication Middleware.

Tests token extraction, account retrieval, and role checking.
"""

import uuid
from inspect import signature
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from fastapi import HTTPException
from fastapi.params import Depends as DependsParam

from src.middleware.auth_middleware import (
    _decode_token,
    _get_token,
    extract_token,
    get_current_account,
    get_current_role,
    get_current_tenant_id,
    get_optional_account,
    require_role,
)
from src.models import AccountRole, AccountStatus


class TestExtractToken:
    """Test token extraction from Authorization header."""

    def test_bearer_token_extraction(self):
        """Test extraction of Bearer token."""
        token = extract_token("Bearer my-jwt-token")
        assert token == "my-jwt-token"

    def test_lowercase_bearer(self):
        """Test extraction with lowercase bearer."""
        token = extract_token("bearer my-jwt-token")
        assert token == "my-jwt-token"

    def test_token_without_bearer(self):
        """Test extraction when token is provided without Bearer prefix."""
        token = extract_token("my-jwt-token")
        assert token == "my-jwt-token"

    def test_none_authorization(self):
        """Test extraction with None authorization."""
        token = extract_token(None)
        assert token is None

    def test_empty_authorization(self):
        """Test extraction with empty authorization."""
        token = extract_token("")
        assert token is None

    def test_invalid_format(self):
        """Test extraction with invalid format (too many parts)."""
        token = extract_token("Bearer token extra")
        assert token is None


class TestGetToken:
    """Test _get_token helper dependency."""

    def test_missing_authorization_raises_401(self):
        """Test that missing authorization raises 401."""
        with pytest.raises(HTTPException) as exc_info:
            _get_token(authorization=None)
        assert exc_info.value.status_code == 401
        assert "Authentication required" in exc_info.value.detail

    def test_valid_authorization_returns_token(self):
        """Test that valid Bearer token is returned."""
        result = _get_token(authorization="Bearer my-token")
        assert result == "my-token"


class TestDecodeToken:
    """Test _decode_token helper dependency."""

    @patch("src.middleware.auth_middleware.AuthService")
    def test_invalid_token_raises_401(self, mock_auth_service):
        """Test that invalid JWT raises 401."""
        mock_auth_service.decode_token.side_effect = jwt.InvalidTokenError("Invalid")
        with pytest.raises(HTTPException) as exc_info:
            _decode_token(token="bad-token")
        assert exc_info.value.status_code == 401
        assert "Invalid authentication token" in exc_info.value.detail

    @patch("src.middleware.auth_middleware.AuthService")
    def test_valid_token_returns_payload(self, mock_auth_service):
        """Test that a valid JWT returns its decoded payload."""
        mock_auth_service.decode_token.return_value = {"sub": "account-id"}
        result = _decode_token(token="good-token")
        assert result == {"sub": "account-id"}


def _make_async_redis_mock(blacklisted: bool = False, version: bytes = b"0"):
    """Return a mock for get_redis_async() whose pipeline.execute() is async."""
    mock_pipe = MagicMock()
    mock_pipe.execute = AsyncMock(return_value=[1 if blacklisted else 0, version])
    mock_aio_redis = MagicMock()
    mock_aio_redis.pipeline.return_value = mock_pipe
    return mock_aio_redis


class TestGetCurrentAccount:
    """Test get_current_account dependency."""

    @pytest.fixture
    def mock_db(self):
        """Create mock async database session."""
        return AsyncMock()

    @pytest.fixture
    def valid_account(self):
        """Create a valid account object."""
        account = MagicMock()
        account.id = uuid.uuid4()
        account.status = AccountStatus.ACTIVE
        account.name = "Test User"
        return account

    @pytest.mark.asyncio
    @patch("src.middleware.auth_middleware.get_redis_async")
    async def test_account_not_found_raises_401(self, mock_get_redis, mock_db):
        """Test that a missing account raises 401."""
        account_id = uuid.uuid4()
        mock_get_redis.return_value = _make_async_redis_mock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_account(
                token="valid-token",
                payload={"sub": str(account_id)},
                db=mock_db,
            )

        assert exc_info.value.status_code == 401
        assert "Invalid or inactive account" in exc_info.value.detail

    @pytest.mark.asyncio
    @patch("src.middleware.auth_middleware.get_redis_async")
    async def test_inactive_account_raises_401(self, mock_get_redis, mock_db, valid_account):
        """Test that an inactive account raises 401."""
        valid_account.status = AccountStatus.INACTIVE
        mock_get_redis.return_value = _make_async_redis_mock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = valid_account
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_account(
                token="valid-token",
                payload={"sub": str(valid_account.id)},
                db=mock_db,
            )

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    @patch("src.middleware.auth_middleware.get_redis_async")
    async def test_valid_account_returned(self, mock_get_redis, mock_db, valid_account):
        """Test that a valid account is returned."""
        mock_get_redis.return_value = _make_async_redis_mock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = valid_account
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await get_current_account(
            token="valid-token",
            payload={"sub": str(valid_account.id)},
            db=mock_db,
        )

        assert result == valid_account

    @pytest.mark.asyncio
    @patch("src.middleware.auth_middleware.get_redis_async")
    async def test_blacklisted_token_raises_401(self, mock_get_redis, mock_db):
        """Test that a blacklisted token raises 401."""
        account_id = uuid.uuid4()
        mock_get_redis.return_value = _make_async_redis_mock(blacklisted=True)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_account(
                token="blacklisted-token",
                payload={"sub": str(account_id)},
                db=mock_db,
            )

        assert exc_info.value.status_code == 401
        assert "Token has been revoked" in exc_info.value.detail

    @pytest.mark.asyncio
    @patch("src.middleware.auth_middleware.get_redis_async")
    async def test_stale_token_version_raises_401(self, mock_get_redis, mock_db, valid_account):
        """Test that a stale token version raises 401."""
        # Pipeline returns: not blacklisted, current version=5
        mock_get_redis.return_value = _make_async_redis_mock(blacklisted=False, version=b"5")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = valid_account
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Token has ver=0, which is older than current version 5
        with pytest.raises(HTTPException) as exc_info:
            await get_current_account(
                token="stale-token",
                payload={"sub": str(valid_account.id), "ver": 0},
                db=mock_db,
            )

        assert exc_info.value.status_code == 401
        assert "Token has been revoked" in exc_info.value.detail

    @pytest.mark.asyncio
    @patch("src.middleware.auth_middleware.get_redis_async")
    async def test_redis_failure_raises_401(self, mock_get_redis, mock_db):
        """Test that a Redis failure fails closed (raises 401)."""
        account_id = uuid.uuid4()
        mock_pipe = MagicMock()
        mock_pipe.execute = AsyncMock(side_effect=Exception("Redis down"))
        mock_aio_redis = MagicMock()
        mock_aio_redis.pipeline.return_value = mock_pipe
        mock_get_redis.return_value = mock_aio_redis

        with pytest.raises(HTTPException) as exc_info:
            await get_current_account(
                token="some-token",
                payload={"sub": str(account_id)},
                db=mock_db,
            )

        assert exc_info.value.status_code == 401


class TestGetCurrentTenantId:
    """Test get_current_tenant_id dependency."""

    def test_missing_tenant_id_raises_400(self):
        """Test that a payload without tenant_id raises 400."""
        with pytest.raises(HTTPException) as exc_info:
            get_current_tenant_id(payload={"sub": "account-id"})

        assert exc_info.value.status_code == 400
        assert "Tenant context required" in exc_info.value.detail

    def test_valid_tenant_id_returned(self):
        """Test that a valid tenant_id is returned from payload."""
        tenant_id = uuid.uuid4()
        result = get_current_tenant_id(payload={"sub": "account", "tenant_id": str(tenant_id)})
        assert result == tenant_id

    def test_tenant_id_dependency_requires_current_account(self):
        """Tenant-only routes must still enforce revocation and account status."""
        param = signature(get_current_tenant_id).parameters["_current_account"]
        assert isinstance(param.default, DependsParam)
        assert param.default.dependency is get_current_account


class TestGetCurrentRole:
    """Test get_current_role dependency."""

    def test_missing_role_raises_400(self):
        """Test that a payload without role raises 400."""
        with pytest.raises(HTTPException) as exc_info:
            get_current_role(payload={"sub": "account-id"})

        assert exc_info.value.status_code == 400
        assert "Role context required" in exc_info.value.detail

    def test_valid_role_returned(self):
        """Test that a valid role is returned from payload."""
        result = get_current_role(payload={"sub": "account", "role": "ADMIN"})
        assert result == AccountRole.ADMIN


class TestRequireRole:
    """Test require_role dependency factory."""

    def test_creates_dependency_function(self):
        """Test that require_role creates a dependency function."""
        dependency = require_role(AccountRole.ADMIN)

        assert callable(dependency)

    @pytest.mark.asyncio
    @patch("src.middleware.auth_middleware.AuthService")
    async def test_insufficient_permission_raises_403(self, mock_auth_service):
        """Test that insufficient permission raises 403."""
        mock_db = AsyncMock()
        mock_account = MagicMock()
        mock_account.id = uuid.uuid4()
        tenant_id = uuid.uuid4()

        mock_auth_service.check_permission = AsyncMock(return_value=False)

        check_role = require_role(AccountRole.ADMIN)

        with pytest.raises(HTTPException) as exc_info:
            await check_role(current_account=mock_account, tenant_id=tenant_id, db=mock_db)

        assert exc_info.value.status_code == 403
        assert "Insufficient permissions" in exc_info.value.detail

    @pytest.mark.asyncio
    @patch("src.middleware.auth_middleware.AuthService")
    async def test_sufficient_permission_passes(self, mock_auth_service):
        """Test that sufficient permission passes."""
        mock_db = AsyncMock()
        mock_account = MagicMock()
        mock_account.id = uuid.uuid4()
        tenant_id = uuid.uuid4()

        mock_auth_service.check_permission = AsyncMock(return_value=True)

        check_role = require_role(AccountRole.NORMAL)
        result = await check_role(current_account=mock_account, tenant_id=tenant_id, db=mock_db)

        assert result is None  # Should not raise


class TestGetOptionalAccount:
    """Test get_optional_account dependency."""

    @pytest.fixture
    def mock_request(self):
        """Create mock request."""
        request = MagicMock()
        request.cookies = {}
        return request

    @pytest.fixture
    def mock_db(self):
        """Create mock async database session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_no_auth_returns_none(self, mock_request, mock_db):
        """Test that no authentication returns None."""
        result = await get_optional_account(request=mock_request, authorization=None, db=mock_db)
        assert result is None

    @pytest.mark.asyncio
    @patch("src.middleware.auth_middleware.AuthService")
    async def test_invalid_token_returns_none(self, mock_auth_service, mock_request, mock_db):
        """Test that invalid token returns None instead of raising."""
        mock_auth_service.decode_token.side_effect = jwt.InvalidTokenError("Invalid")

        result = await get_optional_account(request=mock_request, authorization="Bearer invalid", db=mock_db)

        assert result is None

    @pytest.mark.asyncio
    @patch("src.middleware.auth_middleware.get_redis_async")
    @patch("src.middleware.auth_middleware.AuthService")
    async def test_valid_token_returns_account(self, mock_auth_service, mock_get_redis, mock_request, mock_db):
        """Test that valid token returns account."""
        mock_get_redis.return_value = _make_async_redis_mock()
        account_id = uuid.uuid4()
        account = MagicMock()
        account.id = account_id
        account.status = AccountStatus.ACTIVE

        mock_auth_service.decode_token.return_value = {"sub": str(account_id)}

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = account
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await get_optional_account(request=mock_request, authorization="Bearer valid", db=mock_db)

        assert result == account

    @pytest.mark.asyncio
    @patch("src.middleware.auth_middleware.get_redis_async")
    @patch("src.middleware.auth_middleware.AuthService")
    async def test_token_from_cookie(self, mock_auth_service, mock_get_redis, mock_request, mock_db):
        """Test token extraction from cookie."""
        mock_get_redis.return_value = _make_async_redis_mock()
        account_id = uuid.uuid4()
        account = MagicMock()
        account.id = account_id
        account.status = AccountStatus.ACTIVE

        mock_request.cookies = {"access_token": "cookie-token"}
        mock_auth_service.decode_token.return_value = {"sub": str(account_id)}

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = account
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await get_optional_account(request=mock_request, authorization=None, db=mock_db)

        assert result == account

    @pytest.mark.asyncio
    @patch("src.middleware.auth_middleware.get_redis_async")
    @patch("src.middleware.auth_middleware.AuthService")
    async def test_inactive_account_returns_none(self, mock_auth_service, mock_get_redis, mock_request, mock_db):
        """Test that inactive account returns None."""
        mock_get_redis.return_value = _make_async_redis_mock()
        account_id = uuid.uuid4()
        account = MagicMock()
        account.id = account_id
        account.status = AccountStatus.INACTIVE

        mock_auth_service.decode_token.return_value = {"sub": str(account_id)}

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = account
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await get_optional_account(request=mock_request, authorization="Bearer token", db=mock_db)

        assert result is None

    @pytest.mark.asyncio
    @patch("src.middleware.auth_middleware.get_redis_async")
    @patch("src.middleware.auth_middleware.AuthService")
    async def test_blacklisted_token_returns_none(self, mock_auth_service, mock_get_redis, mock_request, mock_db):
        """Test that blacklisted token returns None."""
        mock_get_redis.return_value = _make_async_redis_mock(blacklisted=True)
        account_id = uuid.uuid4()
        mock_auth_service.decode_token.return_value = {"sub": str(account_id)}

        result = await get_optional_account(request=mock_request, authorization="Bearer blacklisted", db=mock_db)

        assert result is None

    @pytest.mark.asyncio
    @patch("src.middleware.auth_middleware.get_redis_async")
    @patch("src.middleware.auth_middleware.AuthService")
    async def test_stale_token_version_returns_none(self, mock_auth_service, mock_get_redis, mock_request, mock_db):
        """Test that stale token version returns None."""
        # not blacklisted, but current version=5
        mock_get_redis.return_value = _make_async_redis_mock(blacklisted=False, version=b"5")
        account_id = uuid.uuid4()

        # Token has version 0, which is less than current version 5
        mock_auth_service.decode_token.return_value = {"sub": str(account_id), "ver": 0}

        result = await get_optional_account(request=mock_request, authorization="Bearer stale", db=mock_db)

        assert result is None
