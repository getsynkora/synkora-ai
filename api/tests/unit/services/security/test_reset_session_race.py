"""Exercise the reset/login interleaving through actual auth/session methods."""

import asyncio
from copy import copy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.services.auth_service import AuthService
from src.services.session_service import SessionService


@pytest.mark.asyncio
async def test_login_using_old_password_cannot_survive_overlapping_reset(monkeypatch):
    account = SimpleNamespace(
        id=uuid4(),
        email="person@example.com",
        name="Person",
        status="ACTIVE",
        password_hash="hash:old",
        password_history=[],
        auth_version=0,
        reset_token_expires_at=(datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
    )
    committed = copy(account)
    version = [0]
    revoked = asyncio.Event()
    allow_commit = asyncio.Event()
    blacklist = MagicMock()
    blacklist.get_account_token_version.side_effect = lambda *_: version[0]
    blacklist.is_blacklisted.return_value = False

    def revoke(*args):
        version[0] += 1
        revoked.set()
        return True

    blacklist.blacklist_all_account_tokens.side_effect = revoke
    monkeypatch.setattr("src.services.security.token_blacklist.TokenBlacklistService", lambda: blacklist)
    monkeypatch.setattr("src.services.session_service.get_token_blacklist_service", lambda: blacklist)

    async def _mock_lockout(*_):
        return (False, "")

    async def _mock_clear(*_):
        return None

    monkeypatch.setattr(AuthService, "_check_account_lockout", _mock_lockout)
    monkeypatch.setattr(AuthService, "_clear_failed_attempts", _mock_clear)
    monkeypatch.setattr(AuthService, "verify_password", lambda plain, hashed: hashed == "hash:" + plain)
    monkeypatch.setattr(AuthService, "hash_password", lambda plain: "hash:" + plain)
    reset_db = AsyncMock()
    reset_db.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: account)

    async def commit():
        await allow_commit.wait()
        committed.__dict__.update(vars(account))

    reset_db.commit.side_effect = commit
    task = asyncio.create_task(AuthService.reset_password(reset_db, "reset-token", "new"))
    try:
        await asyncio.wait_for(revoked.wait(), 3)
        login_db = AsyncMock()
        login_db.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: copy(committed))
        authenticated = await AuthService.authenticate(login_db, account.email, "old")
        assert authenticated is not None
        session = await SessionService.create_session(login_db, authenticated)
        allow_commit.set()
        await task
        validation_db = AsyncMock()
        validation_db.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: committed)
        assert await SessionService.validate_session(validation_db, session["access_token"]) is None
    finally:
        allow_commit.set()
        if not task.done():
            await task


def test_durable_version_rejects_legacy_and_stale_tokens_after_reset():
    account = SimpleNamespace(auth_version=0)
    AuthService.validate_account_auth_version({}, account)  # Existing sessions survive rollout.
    account.auth_version = 1
    for payload in [{}, {"av": 0}, {"av": True}, {"av": "1"}]:
        with pytest.raises(ValueError):
            AuthService.validate_account_auth_version(payload, account)
    AuthService.validate_account_auth_version({"av": 1}, account)
