"""Tests for browser tool registration with the ADK tool registry.

Focused on session_id resolution: browser automation tools must not silently
share one global "default" browser session/page-pool across unrelated
conversations and tenants.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.agents.tool_registrations.browser_tools_registry import (
    _resolve_session_id,
    register_browser_tools,
)


@pytest.mark.unit
class TestResolveSessionId:
    def test_explicit_kwarg_wins_over_runtime_context(self):
        runtime_context = SimpleNamespace(tenant_id=uuid.uuid4(), conversation_id=uuid.uuid4())

        result = _resolve_session_id({"session_id": "custom-session"}, runtime_context)

        assert result == "custom-session"

    def test_scopes_to_conversation_id_when_no_explicit_session_id(self):
        conversation_id = uuid.uuid4()
        runtime_context = SimpleNamespace(tenant_id=uuid.uuid4(), conversation_id=conversation_id)

        result = _resolve_session_id({}, runtime_context)

        assert result == str(conversation_id)

    def test_falls_back_to_stable_per_tenant_id_when_no_conversation_id(self):
        """Background tasks (e.g. Celery) have no conversation_id."""
        tenant_id = uuid.uuid4()
        runtime_context = SimpleNamespace(tenant_id=tenant_id, conversation_id=None)

        result = _resolve_session_id({}, runtime_context)

        assert result != "default"
        # Deterministic: same tenant always resolves to the same fallback session.
        assert result == _resolve_session_id({}, SimpleNamespace(tenant_id=tenant_id, conversation_id=None))

    def test_falls_back_to_default_when_no_runtime_context(self):
        result = _resolve_session_id({}, None)

        assert result == "default"

    def test_different_conversations_resolve_to_different_session_ids(self):
        runtime_context_a = SimpleNamespace(tenant_id=uuid.uuid4(), conversation_id=uuid.uuid4())
        runtime_context_b = SimpleNamespace(tenant_id=uuid.uuid4(), conversation_id=uuid.uuid4())

        assert _resolve_session_id({}, runtime_context_a) != _resolve_session_id({}, runtime_context_b)


@pytest.mark.unit
class TestBrowserNavigateWrapperSessionScoping:
    """
    register_browser_tools() imports internal_browser_navigate locally
    (`from ... import internal_browser_navigate`), so the patch must be active
    *before* register_browser_tools() runs for the wrapper's closure to
    capture the mock.
    """

    @pytest.mark.asyncio
    async def test_uses_conversation_scoped_session_id_not_literal_default(self):
        conversation_id = uuid.uuid4()
        runtime_context = SimpleNamespace(tenant_id=uuid.uuid4(), conversation_id=conversation_id)

        with patch(
            "src.services.agents.internal_tools.browser_interactive.internal_browser_navigate",
            new=AsyncMock(return_value={"success": True}),
        ) as mock_fn:
            registry = MagicMock()
            register_browser_tools(registry)
            wrapper = next(
                call.kwargs["function"]
                for call in registry.register_tool.call_args_list
                if call.kwargs["name"] == "internal_browser_navigate"
            )

            await wrapper(config={"_runtime_context": runtime_context}, url="https://deriv.com")

            assert mock_fn.call_args.kwargs["session_id"] == str(conversation_id)

    @pytest.mark.asyncio
    async def test_explicit_session_id_still_respected(self):
        runtime_context = SimpleNamespace(tenant_id=uuid.uuid4(), conversation_id=uuid.uuid4())

        with patch(
            "src.services.agents.internal_tools.browser_interactive.internal_browser_navigate",
            new=AsyncMock(return_value={"success": True}),
        ) as mock_fn:
            registry = MagicMock()
            register_browser_tools(registry)
            wrapper = next(
                call.kwargs["function"]
                for call in registry.register_tool.call_args_list
                if call.kwargs["name"] == "internal_browser_navigate"
            )

            await wrapper(
                config={"_runtime_context": runtime_context},
                url="https://deriv.com",
                session_id="my-explicit-session",
            )

            assert mock_fn.call_args.kwargs["session_id"] == "my-explicit-session"
