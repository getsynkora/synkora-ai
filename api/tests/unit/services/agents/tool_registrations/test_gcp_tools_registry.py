"""Tests for GCP tool registration with the ADK tool registry."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.agents.tool_registrations.gcp_tools_registry import register_gcp_tools

_EXPECTED_TOOLS = {
    "internal_gcp_get_logs",
    "internal_gcp_get_metrics",
    "internal_gcp_list_alerts",
    "internal_gcp_get_resource_health",
    "internal_gcp_list_security_findings",
}


@pytest.mark.unit
class TestRegisterGcpTools:
    def test_registers_all_five_tools_with_read_category_and_gcp_auth(self):
        registry = MagicMock()
        register_gcp_tools(registry)

        assert registry.register_tool.call_count == 5
        registered_names = set()
        for call in registry.register_tool.call_args_list:
            kwargs = call.kwargs
            registered_names.add(kwargs["name"])
            assert kwargs["requires_auth"] == "gcp"
            assert kwargs["tool_category"] == "read"
            assert callable(kwargs["function"])
        assert registered_names == _EXPECTED_TOOLS

    @pytest.mark.asyncio
    async def test_get_logs_wrapper_forwards_runtime_context_and_kwargs(self):
        registry = MagicMock()
        register_gcp_tools(registry)
        wrapper = next(
            call.kwargs["function"]
            for call in registry.register_tool.call_args_list
            if call.kwargs["name"] == "internal_gcp_get_logs"
        )

        runtime_context = object()
        with patch(
            "src.services.agents.tool_registrations.gcp_tools_registry.internal_gcp_get_logs",
            new=AsyncMock(return_value={"success": True, "error": None, "entries": []}),
        ) as mock_fn:
            result = await wrapper(
                config={"_runtime_context": runtime_context},
                log_source="my-log",
                start_time="a",
                end_time="b",
            )
            mock_fn.assert_called_once_with(
                runtime_context=runtime_context,
                log_source="my-log",
                start_time="a",
                end_time="b",
                filter_query="",
                limit=100,
            )
            assert result["success"] is True
