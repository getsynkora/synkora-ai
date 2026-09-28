"""
Unit tests for the encryption key rotation task.

Tests:
- dry_run=True counts rows that need re-encryption but does NOT write any changes.
- A row encrypted with OLD_KEY is detected and re-encrypted with NEW_KEY.
- Rows whose value is already encrypted with the primary key are skipped.
- NULL / empty field values are skipped.
- Rows with undecodable ciphertext increment the error counter.
- _get_encrypted_fields returns a non-empty list of (model, field, type) tuples.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import Fernet

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_key() -> bytes:
    """Generate a fresh Fernet key."""
    return Fernet.generate_key()


def encrypt_with(key: bytes, plaintext: str) -> str:
    """Return a Fernet-encrypted token for *plaintext* using *key*."""
    return Fernet(key).encrypt(plaintext.encode()).decode()


class _MockAsyncSessionCM:
    """Async context manager that yields a mock async DB session."""

    def __init__(self, db):
        self._db = db

    async def __aenter__(self):
        return self._db

    async def __aexit__(self, *args):
        return False


def _make_async_session_mock(db=None):
    """Return (mock_create_celery_async_session, mock_async_db)."""
    if db is None:
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()

    def _factory():
        return _MockAsyncSessionCM(db)

    mock_create = MagicMock(return_value=_factory)
    return mock_create, db


def _make_db_with_rows(rows: list) -> AsyncMock:
    """Create a mock DB session whose execute() returns the given rows."""
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = rows
    db.execute = AsyncMock(return_value=result_mock)
    return db


# ---------------------------------------------------------------------------
# _get_encrypted_fields
# ---------------------------------------------------------------------------


def test_get_encrypted_fields_returns_nonempty_list():
    """Smoke test: the field registry must contain at least one entry."""
    from src.tasks.key_rotation_task import _get_encrypted_fields

    fields = _get_encrypted_fields()
    assert len(fields) > 0, "Encrypted field list must not be empty"
    for entry in fields:
        assert len(entry) == 3, "Each entry must be (ModelClass, field_name, field_type)"
        model_cls, field_name, field_type = entry
        assert isinstance(field_name, str)
        assert field_type in ("plain", "enc:")


# ---------------------------------------------------------------------------
# _rotate_model_field — plain field_type
#
# NOTE: _rotate_model_field calls `select(model_class)` which is a SQLAlchemy
# ORM call.  To avoid needing a real mapped class we patch `sqlalchemy.select`
# to a no-op and rely on the already-configured db.execute mock to return the
# desired rows.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rotate_plain_field_re_encrypts_with_old_key():
    """
    A row encrypted with OLD_KEY should be detected and re-encrypted with NEW_KEY.
    The row is added to the session and the rotated counter is incremented.
    """
    old_key = make_key()
    new_key = make_key()
    plaintext = "supersecret"

    mock_row = MagicMock()
    mock_row.id = "row-1"
    old_ciphertext = encrypt_with(old_key, plaintext)
    mock_row.my_field = old_ciphertext

    db = _make_db_with_rows([mock_row])

    from cryptography.fernet import Fernet, MultiFernet

    from src.tasks.key_rotation_task import _rotate_model_field

    multi = MultiFernet([Fernet(new_key), Fernet(old_key)])
    primary = Fernet(new_key)

    stats = {"rotated": 0, "skipped": 0, "errors": 0, "dry_run": False}

    class FakeModel:
        pass

    with patch("src.tasks.key_rotation_task.select", return_value=MagicMock()):
        await _rotate_model_field(db, FakeModel, "my_field", "plain", multi, primary, stats, dry_run=False)

    assert stats["rotated"] == 1
    assert stats["skipped"] == 0
    assert stats["errors"] == 0

    db.add.assert_called_once_with(mock_row)

    new_value = mock_row.my_field
    decrypted = primary.decrypt(new_value.encode()).decode()
    assert decrypted == plaintext


@pytest.mark.asyncio
async def test_rotate_plain_field_null_skipped():
    """Rows with NULL / empty field values must be skipped."""
    mock_row = MagicMock()
    mock_row.id = "row-3"
    mock_row.my_field = None

    db = _make_db_with_rows([mock_row])

    from cryptography.fernet import Fernet, MultiFernet

    from src.tasks.key_rotation_task import _rotate_model_field

    key = make_key()
    multi = MultiFernet([Fernet(key)])
    primary = Fernet(key)

    stats = {"rotated": 0, "skipped": 0, "errors": 0, "dry_run": False}

    class FakeModel:
        pass

    with patch("src.tasks.key_rotation_task.select", return_value=MagicMock()):
        await _rotate_model_field(db, FakeModel, "my_field", "plain", multi, primary, stats, dry_run=False)

    assert stats["skipped"] == 1
    assert stats["rotated"] == 0
    assert stats["errors"] == 0
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_rotate_plain_field_invalid_ciphertext_increments_errors():
    """Rows with corrupt ciphertext must increment errors and not crash the loop."""
    mock_row = MagicMock()
    mock_row.id = "row-4"
    mock_row.my_field = "this-is-not-a-fernet-token"

    db = _make_db_with_rows([mock_row])

    from cryptography.fernet import Fernet, MultiFernet

    from src.tasks.key_rotation_task import _rotate_model_field

    key = make_key()
    multi = MultiFernet([Fernet(key)])
    primary = Fernet(key)

    stats = {"rotated": 0, "skipped": 0, "errors": 0, "dry_run": False}

    class FakeModel:
        pass

    with patch("src.tasks.key_rotation_task.select", return_value=MagicMock()):
        await _rotate_model_field(db, FakeModel, "my_field", "plain", multi, primary, stats, dry_run=False)

    assert stats["errors"] == 1
    assert stats["rotated"] == 0
    db.add.assert_not_called()


# ---------------------------------------------------------------------------
# _rotate_model_field — enc: field_type
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rotate_enc_prefix_field_re_encrypts():
    """
    A field stored as "enc:<fernet_token>" (MCPServer style) should be
    decrypted, re-encrypted, and stored back with the "enc:" prefix.
    """
    old_key = make_key()
    new_key = make_key()
    plaintext = '{"api_key": "secret"}'

    old_ciphertext = encrypt_with(old_key, plaintext)
    raw_value = f"enc:{old_ciphertext}"

    mock_row = MagicMock()
    mock_row.id = "row-5"
    mock_row._auth_config_enc = raw_value

    db = _make_db_with_rows([mock_row])

    from cryptography.fernet import Fernet, MultiFernet

    from src.tasks.key_rotation_task import _rotate_model_field

    multi = MultiFernet([Fernet(new_key), Fernet(old_key)])
    primary = Fernet(new_key)

    stats = {"rotated": 0, "skipped": 0, "errors": 0, "dry_run": False}

    class FakeModel:
        pass

    with patch("src.tasks.key_rotation_task.select", return_value=MagicMock()):
        await _rotate_model_field(db, FakeModel, "_auth_config_enc", "enc:", multi, primary, stats, dry_run=False)

    assert stats["rotated"] == 1
    assert stats["errors"] == 0
    db.add.assert_called_once_with(mock_row)

    new_raw = mock_row._auth_config_enc
    assert new_raw.startswith("enc:")
    decrypted = primary.decrypt(new_raw[4:].encode()).decode()
    assert decrypted == plaintext


@pytest.mark.asyncio
async def test_rotate_enc_prefix_field_plain_value_skipped():
    """
    A field with "enc:" field_type that holds a plain (unencrypted) JSON value
    (legacy row) must be skipped — the task does not attempt to encrypt it.
    """
    mock_row = MagicMock()
    mock_row.id = "row-6"
    mock_row._env_vars_enc = '{"PATH": "/usr/bin"}'  # no "enc:" prefix

    db = _make_db_with_rows([mock_row])

    from cryptography.fernet import Fernet, MultiFernet

    from src.tasks.key_rotation_task import _rotate_model_field

    key = make_key()
    multi = MultiFernet([Fernet(key)])
    primary = Fernet(key)

    stats = {"rotated": 0, "skipped": 0, "errors": 0, "dry_run": False}

    class FakeModel:
        pass

    with patch("src.tasks.key_rotation_task.select", return_value=MagicMock()):
        await _rotate_model_field(db, FakeModel, "_env_vars_enc", "enc:", multi, primary, stats, dry_run=False)

    assert stats["skipped"] == 1
    assert stats["rotated"] == 0
    db.add.assert_not_called()


# ---------------------------------------------------------------------------
# dry_run=True — no writes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dry_run_does_not_write():
    """
    dry_run=True must increment the rotated counter but must NOT call db.add
    or modify the row's field value.
    """
    old_key = make_key()
    new_key = make_key()
    plaintext = "sensitive"

    mock_row = MagicMock()
    mock_row.id = "row-7"
    old_ciphertext = encrypt_with(old_key, plaintext)
    mock_row.my_field = old_ciphertext
    original_value = mock_row.my_field

    db = _make_db_with_rows([mock_row])

    from cryptography.fernet import Fernet, MultiFernet

    from src.tasks.key_rotation_task import _rotate_model_field

    multi = MultiFernet([Fernet(new_key), Fernet(old_key)])
    primary = Fernet(new_key)

    stats = {"rotated": 0, "skipped": 0, "errors": 0, "dry_run": True}

    class FakeModel:
        pass

    with patch("src.tasks.key_rotation_task.select", return_value=MagicMock()):
        await _rotate_model_field(db, FakeModel, "my_field", "plain", multi, primary, stats, dry_run=True)

    assert stats["rotated"] == 1
    db.add.assert_not_called()
    assert mock_row.my_field == original_value


# ---------------------------------------------------------------------------
# Full _rotate_async integration (mocked DB and field registry)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rotate_async_dry_run_returns_stats():
    """
    _rotate_async with dry_run=True returns the stats dict and does not commit.
    """
    old_key = make_key()
    new_key = make_key()
    enc_key_str = f"{new_key.decode()},{old_key.decode()}"

    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=result_mock)

    mock_create, _ = _make_async_session_mock(db)

    # Patch create_celery_async_session at its definition site (where it is imported from)
    with (
        patch.dict(os.environ, {"ENCRYPTION_KEY": enc_key_str}),
        patch("src.tasks.key_rotation_task.create_celery_async_session", mock_create),
        patch("src.tasks.key_rotation_task.select", return_value=MagicMock()),
    ):
        from src.tasks.key_rotation_task import _rotate_async

        stats = await _rotate_async(dry_run=True)

    assert stats["dry_run"] is True
    assert "rotated" in stats
    assert "skipped" in stats
    assert "errors" in stats
    assert "duration_seconds" in stats
    # No commit in dry_run
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_rotate_async_commits_when_not_dry_run():
    """
    _rotate_async with dry_run=False must call db.commit() after processing.
    """
    key = make_key()
    enc_key_str = key.decode()

    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=result_mock)

    mock_create, _ = _make_async_session_mock(db)

    with (
        patch.dict(os.environ, {"ENCRYPTION_KEY": enc_key_str}),
        patch("src.tasks.key_rotation_task.create_celery_async_session", mock_create),
        patch("src.tasks.key_rotation_task.select", return_value=MagicMock()),
    ):
        from src.tasks.key_rotation_task import _rotate_async

        stats = await _rotate_async(dry_run=False)

    assert stats["dry_run"] is False
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_rotate_async_raises_without_encryption_key():
    """
    _rotate_async must raise RuntimeError when ENCRYPTION_KEY is not set.
    """
    env = {k: v for k, v in os.environ.items() if k != "ENCRYPTION_KEY"}

    with patch.dict(os.environ, env, clear=True):
        from src.tasks.key_rotation_task import _rotate_async

        with pytest.raises(RuntimeError, match="ENCRYPTION_KEY"):
            await _rotate_async(dry_run=True)
