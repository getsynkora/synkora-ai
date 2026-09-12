from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.services.custom_tools.openapi_parser import OpenAPIParser
from src.services.custom_tools.tool_executor import ToolExecutor


class TestToolExecutor:
    @pytest.fixture
    def mock_parser(self):
        parser = MagicMock(spec=OpenAPIParser)
        parser.server_url = "https://api.example.com"
        parser.get_tool_definition.return_value = {
            "operation_id": "test_operation",
            "method": "GET",
            "path": "/api/test",
            "parameters": [
                {"name": "query_param", "in": "query", "required": False},
                {"name": "path_param", "in": "path", "required": True},
                {"name": "header_param", "in": "header", "required": False},
            ],
        }
        parser.validate_parameters.return_value = (True, [])
        parser.build_request_url.return_value = "https://api.example.com/api/test"
        parser.get_available_operations.return_value = [
            {"operation_id": "get_test", "method": "GET", "path": "/test", "parameters": []}
        ]
        return parser

    @pytest.fixture
    def executor_no_auth(self, mock_parser):
        return ToolExecutor(parser=mock_parser, auth_type="none", auth_config={}, timeout=30)

    @pytest.fixture
    def executor_bearer(self, mock_parser):
        with patch("src.services.custom_tools.tool_executor.decrypt_value") as mock_decrypt:
            mock_decrypt.return_value = "test_token"
            return ToolExecutor(
                parser=mock_parser, auth_type="bearer", auth_config={"token": "encrypted_token"}, timeout=30
            )

    @pytest.fixture
    def executor_basic(self, mock_parser):
        return ToolExecutor(
            parser=mock_parser,
            auth_type="basic",
            auth_config={"username": "encrypted_user", "password": "encrypted_pass"},
            timeout=30,
        )

    @pytest.fixture
    def executor_custom(self, mock_parser):
        return ToolExecutor(
            parser=mock_parser,
            auth_type="custom",
            auth_config={"headers": {"X-API-Key": "encrypted:api_key", "X-Custom": "plain_value"}},
            timeout=30,
        )

    def test_init(self, mock_parser):
        executor = ToolExecutor(parser=mock_parser, auth_type="BEARER", auth_config={"token": "test"}, timeout=60)
        assert executor.parser == mock_parser
        assert executor.auth_type == "bearer"
        assert executor.auth_config == {"token": "test"}
        assert executor.timeout == 60

    def test_build_headers_no_auth(self, executor_no_auth):
        operation = {"operation_id": "test"}
        headers = executor_no_auth._build_headers(operation)

        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"
        assert "Authorization" not in headers

    def test_build_headers_bearer(self, executor_bearer):
        with patch("src.services.custom_tools.tool_executor.decrypt_value") as mock_decrypt:
            mock_decrypt.return_value = "test_token"
            operation = {"operation_id": "test"}
            headers = executor_bearer._build_headers(operation)

            assert headers["Authorization"] == "Bearer test_token"

    def test_build_headers_basic(self, executor_basic):
        with patch("src.services.custom_tools.tool_executor.decrypt_value") as mock_decrypt:
            mock_decrypt.side_effect = ["username", "password"]
            operation = {"operation_id": "test"}
            headers = executor_basic._build_headers(operation)

            assert "Authorization" in headers
            assert headers["Authorization"].startswith("Basic ")

    def test_build_headers_custom(self, executor_custom):
        with patch("src.services.custom_tools.tool_executor.decrypt_value") as mock_decrypt:
            mock_decrypt.return_value = "decrypted_key"
            operation = {"operation_id": "test"}
            headers = executor_custom._build_headers(operation)

            assert headers["X-API-Key"] == "decrypted_key"
            assert headers["X-Custom"] == "plain_value"

    def test_prepare_parameters(self, executor_no_auth):
        operation = {
            "parameters": [
                {"name": "query_param", "in": "query"},
                {"name": "path_param", "in": "path"},
                {"name": "header_param", "in": "header"},
            ],
            "request_body": {"required": False},
        }

        params = {"query_param": "value1", "path_param": "value2", "header_param": "value3", "body": {"key": "value"}}

        path_params, query_params, header_params, body = executor_no_auth._prepare_parameters(operation, params)

        assert path_params == {"path_param": "value2"}
        assert query_params == {"query_param": "value1"}
        assert header_params == {"header_param": "value3"}
        assert body == {"key": "value"}

    def test_prepare_parameters_no_body(self, executor_no_auth):
        operation = {"parameters": [{"name": "query_param", "in": "query"}]}

        params = {"query_param": "value1"}

        path_params, query_params, header_params, body = executor_no_auth._prepare_parameters(operation, params)

        assert body is None

    @pytest.mark.asyncio
    async def test_execute_get_success(self, executor_no_auth, mock_parser):
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"result": "success"}
            mock_response.headers = {"Content-Type": "application/json"}
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await executor_no_auth.execute("test_operation", {"query_param": "value"})

            assert result["success"] is True
            assert result["status_code"] == 200
            assert result["data"] == {"result": "success"}

    @pytest.mark.asyncio
    async def test_execute_post_success(self, executor_no_auth, mock_parser):
        mock_parser.get_tool_definition.return_value = {
            "operation_id": "test_operation",
            "method": "POST",
            "path": "/api/test",
            "parameters": [],
            "request_body": {"required": True},
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"id": 123}
            mock_response.headers = {}
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await executor_no_auth.execute("test_operation", {"body": {"name": "test"}})

            assert result["success"] is True
            assert result["status_code"] == 201

    @pytest.mark.asyncio
    async def test_execute_put_success(self, executor_no_auth, mock_parser):
        mock_parser.get_tool_definition.return_value = {
            "operation_id": "test_operation",
            "method": "PUT",
            "path": "/api/test",
            "parameters": [],
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"updated": True}
            mock_response.headers = {}
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.put = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await executor_no_auth.execute("test_operation", {})

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_patch_success(self, executor_no_auth, mock_parser):
        mock_parser.get_tool_definition.return_value = {
            "operation_id": "test_operation",
            "method": "PATCH",
            "path": "/api/test",
            "parameters": [],
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"patched": True}
            mock_response.headers = {}
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.patch = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await executor_no_auth.execute("test_operation", {})

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_delete_success(self, executor_no_auth, mock_parser):
        import json as json_module

        mock_parser.get_tool_definition.return_value = {
            "operation_id": "test_operation",
            "method": "DELETE",
            "path": "/api/test",
            "parameters": [],
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 204
            mock_response.json.side_effect = json_module.JSONDecodeError("No content", "", 0)
            mock_response.text = ""
            mock_response.headers = {}
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.delete = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await executor_no_auth.execute("test_operation", {})

            assert result["success"] is True
            assert result["status_code"] == 204

    @pytest.mark.asyncio
    async def test_execute_operation_not_found(self, executor_no_auth, mock_parser):
        mock_parser.get_tool_definition.return_value = None

        with pytest.raises(ValueError, match="Operation 'unknown' not found"):
            await executor_no_auth.execute("unknown", {})

    @pytest.mark.asyncio
    async def test_execute_invalid_parameters(self, executor_no_auth, mock_parser):
        mock_parser.validate_parameters.return_value = (False, ["Missing required param"])

        with pytest.raises(ValueError, match="Invalid parameters"):
            await executor_no_auth.execute("test_operation", {})

    @pytest.mark.asyncio
    async def test_execute_http_status_error(self, executor_no_auth, mock_parser):
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_response.json.return_value = {"error": "Not found"}
            mock_response.text = "Not found"

            error = httpx.HTTPStatusError("404", request=MagicMock(), response=mock_response)

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(side_effect=error)
            mock_client_class.return_value = mock_client

            result = await executor_no_auth.execute("test_operation", {})

            assert result["success"] is False
            assert result["status_code"] == 404

    @pytest.mark.asyncio
    async def test_execute_request_error(self, executor_no_auth, mock_parser):
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(side_effect=httpx.RequestError("Connection failed"))
            mock_client_class.return_value = mock_client

            result = await executor_no_auth.execute("test_operation", {})

            assert result["success"] is False
            assert "Request failed" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_unsupported_method(self, executor_no_auth, mock_parser):
        mock_parser.get_tool_definition.return_value = {
            "operation_id": "test_operation",
            "method": "UNKNOWN",
            "path": "/api/test",
            "parameters": [],
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await executor_no_auth.execute("test_operation", {})

            assert result["success"] is False
            assert "Unsupported HTTP method" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_json_decode_error(self, executor_no_auth, mock_parser):
        import json as json_module

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.side_effect = json_module.JSONDecodeError("Invalid JSON", "", 0)
            mock_response.text = "plain text response"
            mock_response.headers = {}
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await executor_no_auth.execute("test_operation", {})

            assert result["success"] is True
            assert result["data"] == {"text": "plain text response"}

    @pytest.mark.asyncio
    async def test_test_connection_success(self, executor_no_auth, mock_parser):
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "ok"}
            mock_response.headers = {}
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await executor_no_auth.test_connection()

            assert result["success"] is True
            assert result["operation_tested"] == "get_test"

    @pytest.mark.asyncio
    async def test_test_connection_no_operations(self, executor_no_auth, mock_parser):
        mock_parser.get_available_operations.return_value = []

        result = await executor_no_auth.test_connection()

        assert result["success"] is False
        assert "No operations available" in result["error"]

    @pytest.mark.asyncio
    async def test_test_connection_no_suitable_operation(self, executor_no_auth, mock_parser):
        mock_parser.get_available_operations.return_value = [
            {
                "operation_id": "post_test",
                "method": "POST",
                "path": "/test",
                "parameters": [{"name": "id", "required": True}],
            }
        ]

        result = await executor_no_auth.test_connection()

        assert result["success"] is False
        assert "No suitable operation found" in result["error"]

    @pytest.mark.asyncio
    async def test_test_connection_execution_error(self, executor_no_auth, mock_parser):
        with patch.object(executor_no_auth, "execute", side_effect=Exception("Test failed")):
            result = await executor_no_auth.test_connection()

            assert result["success"] is False
            assert "Test failed" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_http_status_error_json_decode_error(self, executor_no_auth, mock_parser):
        import json as json_module

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.json.side_effect = json_module.JSONDecodeError("Invalid JSON", "", 0)
            mock_response.text = "Internal server error"

            error = httpx.HTTPStatusError("500", request=MagicMock(), response=mock_response)

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(side_effect=error)
            mock_client_class.return_value = mock_client

            result = await executor_no_auth.execute("test_operation", {})

            assert result["success"] is False
            assert result["data"] == {"text": "Internal server error"}

    @pytest.mark.asyncio
    async def test_execute_unexpected_exception(self, executor_no_auth, mock_parser):
        # Test unexpected exception during request execution
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(side_effect=RuntimeError("Unexpected error"))
            mock_client_class.return_value = mock_client

            result = await executor_no_auth.execute("test_operation", {})

            assert result["success"] is False
            assert "Execution failed" in result["error"]
