"""
Unit tests for Authentication Service.

Tests password hashing, JWT token management, authentication, and account operations.
"""

import time
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import AccountRole, AccountStatus
from src.services.auth_service import AuthService


class TestPasswordHashing:
    """Test password hashing and verification."""

    def test_hash_password_returns_string(self):
        """Test that hash_password returns a string."""
        hashed = AuthService.hash_password("test_password")
        assert isinstance(hashed, str)
        assert len(hashed) > 0

    def test_hash_password_is_bcrypt(self):
        """Test that hash uses bcrypt format."""
        hashed = AuthService.hash_password("test_password")
        # bcrypt hashes start with $2b$ or $2a$
        assert hashed.startswith("$2")

    def test_hash_password_different_each_time(self):
        """Test that same password produces different hashes (due to salt)."""
        hash1 = AuthService.hash_password("same_password")
        hash2 = AuthService.hash_password("same_password")
        assert hash1 != hash2

    def test_verify_password_correct(self):
        """Test password verification with correct password."""
        password = "correct_password"
        hashed = AuthService.hash_password(password)
        assert AuthService.verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password."""
        hashed = AuthService.hash_password("correct_password")
        assert AuthService.verify_password("wrong_password", hashed) is False

    def test_verify_password_empty(self):
        """Test password verification with empty password."""
        hashed = AuthService.hash_password("some_password")
        assert AuthService.verify_password("", hashed) is False


class TestAccessTokenGeneration:
    """Test JWT access token generation."""

    @patch("src.services.auth_service.settings")
    def test_generate_access_token_basic(self, mock_settings):
        """Test basic access token generation."""
        mock_settings.jwt_secret_key = "test_secret"
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.jwt_access_token_expires = 3600
        mock_settings.jwt_issuer = "synkora-api"
        mock_settings.jwt_audience = "synkora-app"

        account_id = uuid.uuid4()
        token = AuthService.generate_access_token(account_id)

        assert isinstance(token, str)
        assert len(token) > 0

    @patch("src.services.auth_service.settings")
    def test_generate_access_token_with_tenant(self, mock_settings):
        """Test access token generation with tenant ID."""
        mock_settings.jwt_secret_key = "test_secret"
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.jwt_access_token_expires = 3600
        mock_settings.jwt_issuer = "synkora-api"
        mock_settings.jwt_audience = "synkora-app"

        account_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        token = AuthService.generate_access_token(account_id, tenant_id=tenant_id)

        # Decode and verify tenant_id is included (skip audience validation for test)
        payload = jwt.decode(
            token,
            "test_secret",
            algorithms=["HS256"],
            issuer=AuthService.JWT_ISSUER,
            audience=AuthService.JWT_AUDIENCE,
        )
        assert payload["tenant_id"] == str(tenant_id)

    @patch("src.services.auth_service.settings")
    def test_generate_access_token_with_role(self, mock_settings):
        """Test access token generation with role."""
        mock_settings.jwt_secret_key = "test_secret"
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.jwt_access_token_expires = 3600
        mock_settings.jwt_issuer = "synkora-api"
        mock_settings.jwt_audience = "synkora-app"

        account_id = uuid.uuid4()
        token = AuthService.generate_access_token(account_id, role=AccountRole.ADMIN)

        # Decode and verify role is included (with proper issuer/audience)
        payload = jwt.decode(
            token,
            "test_secret",
            algorithms=["HS256"],
            issuer=AuthService.JWT_ISSUER,
            audience=AuthService.JWT_AUDIENCE,
        )
        assert payload["role"] == "ADMIN"

    @patch("src.services.auth_service.settings")
    def test_generate_access_token_payload_structure(self, mock_settings):
        """Test access token payload has correct structure."""
        mock_settings.jwt_secret_key = "test_secret"
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.jwt_access_token_expires = 3600
        mock_settings.jwt_issuer = "synkora-api"
        mock_settings.jwt_audience = "synkora-app"

        account_id = uuid.uuid4()
        token = AuthService.generate_access_token(account_id)

        payload = jwt.decode(
            token,
            "test_secret",
            algorithms=["HS256"],
            issuer=AuthService.JWT_ISSUER,
            audience=AuthService.JWT_AUDIENCE,
        )
        assert payload["sub"] == str(account_id)
        assert payload["type"] == "access"
        assert "iat" in payload
        assert "exp" in payload


class TestRefreshTokenGeneration:
    """Test JWT refresh token generation."""

    @patch("src.services.auth_service.settings")
    def test_generate_refresh_token(self, mock_settings):
        """Test refresh token generation."""
        mock_settings.jwt_secret_key = "test_secret"
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.jwt_refresh_token_expires = 86400
        mock_settings.jwt_issuer = "synkora-api"
        mock_settings.jwt_audience = "synkora-app"

        account_id = uuid.uuid4()
        token = AuthService.generate_refresh_token(account_id)

        assert isinstance(token, str)
        assert len(token) > 0

    @patch("src.services.auth_service.settings")
    def test_refresh_token_payload_structure(self, mock_settings):
        """Test refresh token payload structure."""
        mock_settings.jwt_secret_key = "test_secret"
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.jwt_refresh_token_expires = 86400
        mock_settings.jwt_issuer = "synkora-api"
        mock_settings.jwt_audience = "synkora-app"

        account_id = uuid.uuid4()
        token = AuthService.generate_refresh_token(account_id)

        payload = jwt.decode(
            token,
            "test_secret",
            algorithms=["HS256"],
            issuer=AuthService.JWT_ISSUER,
            audience=AuthService.JWT_AUDIENCE,
        )
        assert payload["sub"] == str(account_id)
        assert payload["type"] == "refresh"


class TestTokenDecoding:
    """Test JWT token decoding."""

    @patch("src.services.auth_service.settings")
    def test_decode_valid_token(self, mock_settings):
        """Test decoding a valid token."""
        mock_settings.jwt_secret_key = "test_secret"
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.jwt_access_token_expires = 3600
        mock_settings.jwt_issuer = "synkora-api"
        mock_settings.jwt_audience = "synkora-app"

        account_id = uuid.uuid4()
        token = AuthService.generate_access_token(account_id)
        payload = AuthService.decode_token(token)

        assert payload["sub"] == str(account_id)

    @patch("src.services.auth_service.settings")
    def test_decode_invalid_token(self, mock_settings):
        """Test decoding an invalid token raises exception."""
        mock_settings.jwt_secret_key = "test_secret"
        mock_settings.jwt_algorithm = "HS256"

        with pytest.raises(jwt.InvalidTokenError):
            AuthService.decode_token("invalid.token.here")

    @patch("src.services.auth_service.settings")
    def test_decode_expired_token(self, mock_settings):
        """Test decoding an expired token raises exception."""
        mock_settings.jwt_secret_key = "test_secret"
        mock_settings.jwt_algorithm = "HS256"

        # Create an already-expired token
        payload = {
            "sub": str(uuid.uuid4()),
            "iat": datetime.now(UTC) - timedelta(hours=2),
            "exp": datetime.now(UTC) - timedelta(hours=1),
            "type": "access",
        }
        token = jwt.encode(payload, "test_secret", algorithm="HS256")

        with pytest.raises(jwt.ExpiredSignatureError):
            AuthService.decode_token(token)


class TestAccountLockout:
    """Test account lockout mechanism (Redis-backed)."""

    @pytest.fixture(autouse=True)
    def mock_redis(self):
        """Mock Redis for lockout tests."""
        self.redis_mock = MagicMock()
        with patch("src.services.auth_service.AuthService._get_redis_client", return_value=self.redis_mock):
            yield

    @pytest.mark.asyncio
    async def test_no_lockout_initially(self):
        """Test that account is not locked initially."""
        self.redis_mock.zcard.return_value = 0
        is_locked, message = await AuthService._check_account_lockout("test@example.com")
        assert is_locked is False
        assert message is None

    @pytest.mark.asyncio
    async def test_record_failed_attempt(self):
        """Test recording failed login attempts."""
        email = "test@example.com"
        await AuthService._record_failed_attempt(email)

        self.redis_mock.zadd.assert_called_once()
        self.redis_mock.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_lockout_after_threshold(self):
        """Test account locks after threshold failed attempts."""
        self.redis_mock.zcard.return_value = AuthService._LOCKOUT_THRESHOLD
        self.redis_mock.zrange.return_value = [("ts", time.time())]

        is_locked, message = await AuthService._check_account_lockout("test@example.com")
        assert is_locked is True
        assert "locked" in message.lower()

    @pytest.mark.asyncio
    async def test_clear_failed_attempts(self):
        """Test clearing failed attempts on successful login."""
        await AuthService._clear_failed_attempts("test@example.com")
        self.redis_mock.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_case_insensitive_lockout(self):
        """Test lockout is case insensitive."""
        await AuthService._record_failed_attempt("Test@Example.com")
        await AuthService._record_failed_attempt("TEST@EXAMPLE.COM")
        await AuthService._record_failed_attempt("test@example.com")

        # All three should use the same lowercased key
        calls = self.redis_mock.zadd.call_args_list
        assert len(calls) == 3
        for call in calls:
            redis_key = call[0][0]
            assert "test@example.com" in redis_key


class TestAuthenticate:
    """Test authenticate method."""

    @pytest.fixture(autouse=True)
    def mock_redis(self):
        """Mock Redis for lockout during authentication tests."""
        self.redis_mock = MagicMock()
        # Default: no lockout (0 failed attempts)
        self.redis_mock.zcard.return_value = 0
        with patch("src.services.auth_service.AuthService._get_redis_client", return_value=self.redis_mock):
            yield

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return AsyncMock(spec=AsyncSession)

    async def test_authenticate_success(self, mock_db):
        """Test successful authentication."""
        email = "user@example.com"
        password = "correct_password"
        hashed = AuthService.hash_password(password)

        account = MagicMock()
        account.auth_version = 0
        account.email = email
        account.password_hash = hashed
        account.status = AccountStatus.ACTIVE

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = account
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await AuthService.authenticate(mock_db, email, password)

        assert result == account

    async def test_authenticate_wrong_password(self, mock_db):
        """Test authentication with wrong password."""
        email = "user@example.com"
        hashed = AuthService.hash_password("correct_password")

        account = MagicMock()
        account.auth_version = 0
        account.email = email
        account.password_hash = hashed
        account.status = AccountStatus.ACTIVE

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = account
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await AuthService.authenticate(mock_db, email, "wrong_password")

        assert result is None

    async def test_authenticate_account_not_found(self, mock_db):
        """Test authentication when account doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await AuthService.authenticate(mock_db, "unknown@example.com", "password")

        assert result is None

    async def test_authenticate_inactive_account(self, mock_db):
        """Test authentication with inactive account."""
        email = "user@example.com"
        password = "correct_password"
        hashed = AuthService.hash_password(password)

        account = MagicMock()
        account.auth_version = 0
        account.email = email
        account.password_hash = hashed
        account.status = AccountStatus.INACTIVE

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = account
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await AuthService.authenticate(mock_db, email, password)

        assert result is None

    async def test_authenticate_locked_account(self, mock_db):
        """Test authentication when account is locked."""
        # Simulate locked account via Redis
        self.redis_mock.zcard.return_value = AuthService._LOCKOUT_THRESHOLD
        self.redis_mock.zrange.return_value = [("ts", time.time())]

        with pytest.raises(ValueError) as exc_info:
            await AuthService.authenticate(mock_db, "user@example.com", "any_password")

        assert "locked" in str(exc_info.value).lower()

    async def test_authenticate_no_password_hash(self, mock_db):
        """Test authentication when account has no password hash."""
        account = MagicMock()
        account.auth_version = 0
        account.email = "user@example.com"
        account.password_hash = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = account
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await AuthService.authenticate(mock_db, "user@example.com", "password")

        assert result is None


class TestTokenGeneration:
    """Test token generation utilities."""

    def test_generate_reset_token(self):
        """Test reset token generation."""
        token = AuthService.generate_reset_token()

        assert isinstance(token, str)
        assert len(token) > 20  # URL-safe tokens are typically longer

    def test_generate_reset_token_unique(self):
        """Test reset tokens are unique."""
        tokens = [AuthService.generate_reset_token() for _ in range(100)]
        assert len(set(tokens)) == 100

    def test_generate_verification_token(self):
        """Test verification token generation."""
        token = AuthService.generate_verification_token()

        assert isinstance(token, str)
        assert len(token) > 20

    def test_hash_token(self):
        """Test token hashing."""
        token = "test_token_12345"
        hashed = AuthService.hash_token(token)

        assert isinstance(hashed, str)
        assert len(hashed) == 64  # SHA-256 hex length
        assert hashed != token

    def test_hash_token_deterministic(self):
        """Test that same token produces same hash."""
        token = "test_token"
        hash1 = AuthService.hash_token(token)
        hash2 = AuthService.hash_token(token)

        assert hash1 == hash2


class TestCheckPermission:
    """Test permission checking."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return AsyncMock(spec=AsyncSession)

    async def test_check_permission_owner_has_all(self, mock_db):
        """Test that owner has all permissions."""
        membership = MagicMock()
        membership.role = AccountRole.OWNER

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = membership
        mock_db.execute = AsyncMock(return_value=mock_result)

        account_id = uuid.uuid4()
        tenant_id = uuid.uuid4()

        # Owner should have all roles
        assert await AuthService.check_permission(mock_db, account_id, tenant_id, AccountRole.OWNER) is True
        assert await AuthService.check_permission(mock_db, account_id, tenant_id, AccountRole.ADMIN) is True
        assert await AuthService.check_permission(mock_db, account_id, tenant_id, AccountRole.EDITOR) is True
        assert await AuthService.check_permission(mock_db, account_id, tenant_id, AccountRole.NORMAL) is True

    async def test_check_permission_admin(self, mock_db):
        """Test admin permission levels."""
        membership = MagicMock()
        membership.role = AccountRole.ADMIN

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = membership
        mock_db.execute = AsyncMock(return_value=mock_result)

        account_id = uuid.uuid4()
        tenant_id = uuid.uuid4()

        assert await AuthService.check_permission(mock_db, account_id, tenant_id, AccountRole.OWNER) is False
        assert await AuthService.check_permission(mock_db, account_id, tenant_id, AccountRole.ADMIN) is True
        assert await AuthService.check_permission(mock_db, account_id, tenant_id, AccountRole.EDITOR) is True
        assert await AuthService.check_permission(mock_db, account_id, tenant_id, AccountRole.NORMAL) is True

    async def test_check_permission_no_membership(self, mock_db):
        """Test permission check when not a member."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        account_id = uuid.uuid4()
        tenant_id = uuid.uuid4()

        assert await AuthService.check_permission(mock_db, account_id, tenant_id, AccountRole.NORMAL) is False


class TestPasswordReset:
    """Test password reset functionality."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return AsyncMock(spec=AsyncSession)

    async def test_reset_password_success(self, mock_db):
        """Test successful password reset."""
        token = AuthService.generate_reset_token()
        token_hash = AuthService.hash_token(token)

        account = MagicMock()
        account.auth_version = 0
        account.reset_token = token_hash
        account.reset_token_expires_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = account
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch(
            "src.services.security.token_blacklist.TokenBlacklistService.blacklist_all_account_tokens",
            return_value=True,
        ):
            result = await AuthService.reset_password(mock_db, token, "new_password")

        assert result == account
        assert account.reset_token is None
        assert account.reset_token_expires_at is None

    async def test_reset_password_invalid_token(self, mock_db):
        """Test password reset with invalid token."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await AuthService.reset_password(mock_db, "invalid_token", "new_password")

        assert result is None

    async def test_reset_password_expired_token(self, mock_db):
        """Test password reset with expired token."""
        token = AuthService.generate_reset_token()
        token_hash = AuthService.hash_token(token)

        account = MagicMock()
        account.auth_version = 0
        account.reset_token = token_hash
        account.reset_token_expires_at = (datetime.now(UTC) - timedelta(hours=1)).isoformat()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = account
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch(
            "src.services.security.token_blacklist.TokenBlacklistService.blacklist_all_account_tokens",
            return_value=True,
        ):
            result = await AuthService.reset_password(mock_db, token, "new_password")

        assert result is None


class TestEmailVerification:
    """Test email verification functionality."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return AsyncMock(spec=AsyncSession)

    async def test_verify_email_success(self, mock_db):
        """Test successful email verification."""
        token = AuthService.generate_verification_token()
        token_hash = AuthService.hash_token(token)

        account = MagicMock()
        account.auth_version = 0
        account.email_verification_token = token_hash
        account.status = AccountStatus.INACTIVE
        account.email_verification_sent_at = None  # no expiry check needed

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = account
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await AuthService.verify_email(mock_db, token)

        assert result == account
        assert account.email_verification_token is None
        assert account.status == AccountStatus.ACTIVE

    async def test_verify_email_invalid_token(self, mock_db):
        """Test email verification with invalid token."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await AuthService.verify_email(mock_db, "invalid_token")

        assert result is None


class TestGetAccountTenants:
    """Test getting account tenants."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return AsyncMock(spec=AsyncSession)

    async def test_get_account_tenants(self, mock_db):
        """Test getting tenants for an account."""
        tenant_id = uuid.uuid4()

        membership = MagicMock()
        membership.tenant_id = tenant_id
        membership.tenant = MagicMock()
        membership.tenant.name = "Test Tenant"
        membership.role = AccountRole.ADMIN
        membership.is_owner = False
        membership.is_admin = True
        membership.can_edit = True

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [membership]
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await AuthService.get_account_tenants(mock_db, uuid.uuid4())

        assert len(result) == 1
        assert result[0]["tenant_id"] == str(tenant_id)
        assert result[0]["tenant_name"] == "Test Tenant"
        assert result[0]["role"] == "ADMIN"

    async def test_get_account_tenants_empty(self, mock_db):
        """Test getting tenants when account has none."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await AuthService.get_account_tenants(mock_db, uuid.uuid4())

        assert result == []
