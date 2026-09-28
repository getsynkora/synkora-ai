"""
Unit tests for session listing and targeted revocation.

Tests cover:
- TokenBlacklistService.store_session_metadata / get_session_metadata
- SessionService.get_active_sessions
- SessionService.revoke_session_by_family
- create_session propagates ip_address / user_agent into metadata
"""

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_redis_mock(family_keys: list[str] | None = None, stored: dict | None = None):
    """Return a minimal synchronous Redis mock."""
    redis = MagicMock()

    # scan returns (0, list_of_bytes) in a single call (cursor=0 → done)
    keys_bytes = [k.encode() for k in (family_keys or [])]
    redis.scan.return_value = (0, keys_bytes)

    stored = stored or {}

    def _get(key):
        v = stored.get(key)
        if v is None:
            return None
        if isinstance(v, str):
            return v.encode()
        return v

    def _exists(key):
        return 1 if key in stored else 0

    def _delete(*keys):
        for k in keys:
            stored.pop(k, None)

    def _set(key, value, ex=None, nx=False):
        if nx and key in stored:
            return None  # nx=True skips if exists
        stored[key] = value if isinstance(value, bytes) else value.encode()
        return True

    def _setex(key, ttl, value):
        stored[key] = value if isinstance(value, bytes) else value.encode()

    redis.get.side_effect = _get
    redis.exists.side_effect = _exists
    redis.delete.side_effect = _delete
    redis.set.side_effect = _set
    redis.setex.side_effect = _setex

    return redis, stored


# ---------------------------------------------------------------------------
# TokenBlacklistService — metadata helpers
# ---------------------------------------------------------------------------


class TestTokenBlacklistMetadata:
    def _service(self, redis):
        from src.services.security.token_blacklist import TokenBlacklistService

        svc = TokenBlacklistService()
        svc._redis = redis
        return svc

    def test_store_and_get_metadata(self):
        redis, stored = _make_redis_mock()
        svc = self._service(redis)

        account_id = uuid.uuid4()
        family_id = "fam1"

        with patch("src.services.security.token_blacklist.settings") as mock_settings:
            mock_settings.jwt_refresh_token_expires = 3600
            result = svc.store_session_metadata(
                account_id, family_id, ip_address="1.2.3.4", user_agent="TestBrowser/1.0"
            )

        assert result is True

        meta = svc.get_session_metadata(account_id, family_id)
        assert meta["ip_address"] == "1.2.3.4"
        assert meta["user_agent"] == "TestBrowser/1.0"

    def test_metadata_nx_prevents_overwrite_on_rotation(self):
        """Second store_session_metadata call (during token rotation) must not overwrite."""
        account_id = uuid.uuid4()
        family_id = "fam2"
        meta_key = f"session:meta:{account_id}:{family_id}"

        # Pre-populate as if login already wrote metadata
        initial = json.dumps({"ip_address": "10.0.0.1", "user_agent": "OriginalAgent"}).encode()
        redis, stored = _make_redis_mock(stored={meta_key: initial})
        svc = self._service(redis)

        with patch("src.services.security.token_blacklist.settings") as mock_settings:
            mock_settings.jwt_refresh_token_expires = 3600
            svc.store_session_metadata(account_id, family_id, ip_address="9.9.9.9", user_agent="NewAgent")

        # Original values must be preserved
        meta = svc.get_session_metadata(account_id, family_id)
        assert meta["ip_address"] == "10.0.0.1"
        assert meta["user_agent"] == "OriginalAgent"

    def test_get_metadata_missing_key_returns_empty(self):
        redis, _ = _make_redis_mock()
        svc = self._service(redis)
        result = svc.get_session_metadata(uuid.uuid4(), "nonexistent")
        assert result == {}

    def test_get_metadata_redis_error_returns_empty(self):
        redis = MagicMock()
        redis.get.side_effect = Exception("Redis down")
        svc = self._service(redis)
        result = svc.get_session_metadata(uuid.uuid4(), "fam")
        assert result == {}

    def test_store_metadata_redis_error_returns_false(self):
        redis = MagicMock()
        redis.set.side_effect = Exception("Redis down")
        svc = self._service(redis)
        with patch("src.services.security.token_blacklist.settings") as mock_settings:
            mock_settings.jwt_refresh_token_expires = 3600
            result = svc.store_session_metadata(uuid.uuid4(), "fam", ip_address="1.1.1.1")
        assert result is False


# ---------------------------------------------------------------------------
# SessionService.get_active_sessions
# ---------------------------------------------------------------------------


class TestGetActiveSessions:
    def _patch_blacklist(self, redis, stored=None):
        """Patch get_token_blacklist_service so it uses our mock Redis."""
        from src.services.security.token_blacklist import TokenBlacklistService

        svc = TokenBlacklistService()
        svc._redis = redis
        return svc

    @pytest.mark.asyncio
    async def test_returns_sessions_for_account(self):
        account_id = uuid.uuid4()
        family_id = "abc123"
        ts = datetime(2026, 9, 28, 10, 0, 0, tzinfo=UTC).timestamp()

        ts_key = f"session:created:{account_id}:{family_id}"
        meta_key = f"session:meta:{account_id}:{family_id}"
        meta_val = json.dumps({"ip_address": "1.2.3.4", "user_agent": "Firefox"}).encode()

        family_key = f"refresh:family:{account_id}:{family_id}"
        redis, stored = _make_redis_mock(
            family_keys=[family_key],
            stored={
                ts_key: str(ts).encode(),
                meta_key: meta_val,
            },
        )

        blacklist_svc = self._patch_blacklist(redis, stored)

        from src.services.session_service import SessionService

        with patch(
            "src.services.session_service.get_token_blacklist_service",
            return_value=blacklist_svc,
        ):
            sessions = await SessionService.get_active_sessions(account_id)

        assert len(sessions) == 1
        s = sessions[0]
        assert s["family_id"] == family_id
        assert s["ip_address"] == "1.2.3.4"
        assert s["user_agent"] == "Firefox"
        assert s["is_current"] is False  # caller must set it
        assert s["created_at"] is not None

    @pytest.mark.asyncio
    async def test_empty_when_no_families(self):
        account_id = uuid.uuid4()
        redis, stored = _make_redis_mock(family_keys=[])
        blacklist_svc = self._patch_blacklist(redis, stored)

        from src.services.session_service import SessionService

        with patch(
            "src.services.session_service.get_token_blacklist_service",
            return_value=blacklist_svc,
        ):
            sessions = await SessionService.get_active_sessions(account_id)

        assert sessions == []

    @pytest.mark.asyncio
    async def test_skips_malformed_keys(self):
        account_id = uuid.uuid4()
        # A key that doesn't match expected format (too few colon-separated parts)
        redis, stored = _make_redis_mock(family_keys=["refresh:family"])
        blacklist_svc = self._patch_blacklist(redis, stored)

        from src.services.session_service import SessionService

        with patch(
            "src.services.session_service.get_token_blacklist_service",
            return_value=blacklist_svc,
        ):
            sessions = await SessionService.get_active_sessions(account_id)

        assert sessions == []


# ---------------------------------------------------------------------------
# SessionService.revoke_session_by_family
# ---------------------------------------------------------------------------


class TestRevokeSessionByFamily:
    def _patch_blacklist(self, redis, stored=None):
        from src.services.security.token_blacklist import TokenBlacklistService

        svc = TokenBlacklistService()
        svc._redis = redis
        return svc

    @pytest.mark.asyncio
    async def test_revokes_existing_family(self):
        account_id = uuid.uuid4()
        family_id = "fam_to_revoke"
        family_key = f"refresh:family:{account_id}:{family_id}"
        ts_key = f"session:created:{account_id}:{family_id}"
        meta_key = f"session:meta:{account_id}:{family_id}"

        redis, stored = _make_redis_mock(
            stored={
                family_key: b"some_hash",
                ts_key: b"1234567890.0",
                meta_key: b'{"ip_address": "1.1.1.1", "user_agent": "A"}',
            }
        )

        blacklist_svc = self._patch_blacklist(redis, stored)

        from src.services.session_service import SessionService

        with patch(
            "src.services.session_service.get_token_blacklist_service",
            return_value=blacklist_svc,
        ):
            result = await SessionService.revoke_session_by_family(account_id, family_id)

        assert result is True
        # Family key and metadata must be gone
        assert family_key not in stored
        assert meta_key not in stored

    @pytest.mark.asyncio
    async def test_returns_false_for_nonexistent_family(self):
        account_id = uuid.uuid4()
        family_id = "ghost_family"

        redis, stored = _make_redis_mock(stored={})
        blacklist_svc = self._patch_blacklist(redis, stored)

        from src.services.session_service import SessionService

        with patch(
            "src.services.session_service.get_token_blacklist_service",
            return_value=blacklist_svc,
        ):
            result = await SessionService.revoke_session_by_family(account_id, family_id)

        assert result is False


# ---------------------------------------------------------------------------
# create_session passes ip/user_agent into metadata
# ---------------------------------------------------------------------------


class TestCreateSessionMetadata:
    @pytest.mark.asyncio
    async def test_create_session_stores_metadata(self):
        """Verify create_session calls store_session_metadata with ip/ua."""
        account = MagicMock()
        account.id = uuid.uuid4()
        account.auth_version = 1
        account.status = "ACTIVE"

        db = MagicMock()
        # Simulate no tenant membership found
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute = MagicMock(return_value=result_mock)

        # We only need to verify store_session_metadata is called — patch everything else
        with (
            patch("src.services.session_service.get_token_blacklist_service") as mock_bl,
            patch("src.services.auth_service.AuthService.generate_access_token", return_value="at"),
            patch("src.services.auth_service.AuthService.generate_refresh_token", return_value="rt"),
            patch("src.services.session_service.settings") as mock_settings,
        ):
            mock_settings.jwt_access_token_expires = 3600
            mock_settings.jwt_refresh_token_expires = 86400

            bl_svc = MagicMock()
            bl_svc.get_account_token_version.return_value = 0
            bl_svc._hash_token.return_value = "hashed"
            bl_svc.store_refresh_token_family.return_value = True
            bl_svc.store_session_created_at.return_value = True
            bl_svc.store_session_metadata.return_value = True
            mock_bl.return_value = bl_svc

            # Need AsyncSession mock for db.execute
            import asyncio

            from src.services.session_service import SessionService

            async def _fake_execute(*args, **kwargs):
                return result_mock

            db.execute = _fake_execute

            await SessionService.create_session(
                db,
                account,
                tenant_id=None,
                ip_address="5.6.7.8",
                user_agent="TestClient/2.0",
            )

        bl_svc.store_session_metadata.assert_called_once()
        call_kwargs = bl_svc.store_session_metadata.call_args
        assert call_kwargs.kwargs.get("ip_address") == "5.6.7.8"
        assert call_kwargs.kwargs.get("user_agent") == "TestClient/2.0"
