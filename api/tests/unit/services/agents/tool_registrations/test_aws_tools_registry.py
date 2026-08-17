"""Tests for AWS tool registration with the ADK tool registry."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.agents.tool_registrations.aws_tools_registry import register_aws_tools

_EXPECTED_TOOLS = {
    "internal_aws_get_logs",
    "internal_aws_get_metrics",
    "internal_aws_list_alerts",
    "internal_aws_get_resource_health",
    "internal_aws_list_security_findings",
}


@pytest.mark.unit
class TestRegisterAwsTools:
    def test_registers_all_five_tools_with_read_category_and_aws_auth(self):
        registry = MagicMock()
        register_aws_tools(registry)

        assert registry.register_tool.call_count == 5
        registered_names = set()
        for call in registry.register_tool.call_args_list:
            kwargs = call.kwargs
            registered_names.add(kwargs["name"])
            assert kwargs["requires_auth"] == "aws"
            assert kwargs["tool_category"] == "read"
            assert callable(kwargs["function"])
            assert kwargs["parameters"]["type"] == "object"
        assert registered_names == _EXPECTED_TOOLS

    @pytest.mark.asyncio
    async def test_get_logs_wrapper_forwards_runtime_context_and_kwargs(self):
        registry = MagicMock()
        register_aws_tools(registry)
        wrapper = next(
            call.kwargs["function"]
            for call in registry.register_tool.call_args_list
            if call.kwargs["name"] == "internal_aws_get_logs"
        )

        runtime_context = object()
        with patch(
            "src.services.agents.tool_registrations.aws_tools_registry.internal_aws_get_logs",
            new=AsyncMock(return_value={"success": True, "error": None, "entries": []}),
        ) as mock_fn:
            result = await wrapper(
                config={"_runtime_context": runtime_context},
                log_source="/aws/lambda/foo",
                start_time="a",
                end_time="b",
            )
            mock_fn.assert_called_once_with(
                runtime_context=runtime_context,
                log_source="/aws/lambda/foo",
                start_time="a",
                end_time="b",
                filter_query="",
                limit=100,
            )
            assert result["success"] is True
