"""Tests for handoff_tools_registry's concurrent credential resolution.

Regression for: handoff_to_human() fans out six _try_create_*_ticket/lead/
conversation helpers via asyncio.gather(), and each one built a
CredentialResolver straight off the shared runtime_context -- meaning all six
concurrent coroutines hit the ONE shared AsyncSession at the same time.
SQLAlchemy's AsyncSession isn't safe for concurrent use, so whenever two
configured providers needed the DB at once, this raised:

    InvalidRequestError: This session is provisioning a new connection;
    concurrent operations are not permitted

Production trace: /api/v1/widgets/chat -> credential_resolver.get_intercom_credentials.
"""

import asyncio
from unittest.mock import patch

import pytest

from src.services.agents.tool_registrations.handoff_tools_registry import (
    _isolated_credential_context,
    _try_create_intercom_conversation,
    _try_create_zendesk_ticket,
)


class _PoisonedSession:
    """Stands in for runtime_context's shared session -- touching it directly is a bug."""

    async def execute(self, *args, **kwargs):
        raise AssertionError("shared runtime_context.db_session must not be used directly")


class _FakeSession:
    def __init__(self, session_id: int):
        self.session_id = session_id
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        self.closed = True


class _FakeRuntimeContext:
    def __init__(self, db_session, db_session_factory=None, shared_state=None):
        self.db_session = db_session
        self.db_session_factory = db_session_factory
        self.shared_state = shared_state or {}

    def with_db_session(self, session):
        return _FakeRuntimeContext(
            db_session=session, db_session_factory=self.db_session_factory, shared_state=self.shared_state
        )


@pytest.mark.unit
@pytest.mark.asyncio
class TestIsolatedCredentialContext:
    async def test_opens_a_fresh_session_instead_of_the_shared_one(self):
        shared_session = _PoisonedSession()
        created: list[_FakeSession] = []

        def factory():
            session = _FakeSession(len(created))
            created.append(session)
            return session

        rc = _FakeRuntimeContext(db_session=shared_session, db_session_factory=factory)

        async with _isolated_credential_context(rc) as isolated_ctx:
            assert isolated_ctx.db_session is not shared_session
            assert isolated_ctx.db_session is created[0]

        assert created[0].closed is True

    async def test_falls_back_to_global_session_factory_when_none_set(self):
        rc = _FakeRuntimeContext(db_session=_PoisonedSession(), db_session_factory=None)
        fallback_session = _FakeSession(99)

        with patch(
            "src.core.database.get_async_session_factory",
            return_value=lambda: fallback_session,
        ):
            async with _isolated_credential_context(rc) as isolated_ctx:
                assert isolated_ctx.db_session is fallback_session

    async def test_concurrent_calls_each_get_their_own_session(self):
        """Two overlapping isolated contexts must never hand out the same session."""
        shared_session = _PoisonedSession()
        created: list[_FakeSession] = []
        lock_order: list[int] = []

        def factory():
            session = _FakeSession(len(created))
            created.append(session)
            return session

        rc = _FakeRuntimeContext(db_session=shared_session, db_session_factory=factory)

        async def resolve_one(tag: int):
            async with _isolated_credential_context(rc) as isolated_ctx:
                lock_order.append(tag)
                await asyncio.sleep(0)  # yield control, simulating real DB latency
                return isolated_ctx.db_session

        s1, s2 = await asyncio.gather(resolve_one(1), resolve_one(2))
        assert s1 is not s2
        assert s1 is not shared_session
        assert s2 is not shared_session


@pytest.mark.unit
@pytest.mark.asyncio
class TestHandoffHelpersRunConcurrentlyWithoutSharingASession:
    async def test_zendesk_and_intercom_helpers_never_touch_the_shared_session(self):
        """The actual production bug: each helper must build its resolver off an
        isolated session, not runtime_context's shared one -- catches a regression
        back to `CredentialResolver(runtime_context)`."""
        shared_session = _PoisonedSession()
        seen_sessions: list[object] = []

        def factory():
            return _FakeSession(id(object()))

        rc = _FakeRuntimeContext(db_session=shared_session, db_session_factory=factory)

        class _RecordingResolver:
            def __init__(self, ctx):
                seen_sessions.append(ctx.db_session)
                self.ctx = ctx

            async def get_zendesk_credentials(self, _name):
                return None

            async def get_intercom_credentials(self, _name):
                return None

        with patch(
            "src.services.agents.credential_resolver.CredentialResolver",
            _RecordingResolver,
        ):
            results = await asyncio.gather(
                _try_create_zendesk_ticket(rc, "refund request", ""),
                _try_create_intercom_conversation(rc, "refund request", ""),
            )

        assert results == [None, None]
        assert len(seen_sessions) == 2
        assert all(s is not shared_session for s in seen_sessions)
