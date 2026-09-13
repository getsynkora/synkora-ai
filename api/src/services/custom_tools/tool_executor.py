"""
Tool Executor

Executes custom tool operations by making HTTP requests based on
OpenAPI specifications and authentication configurations.
"""

import json
import logging
from typing import Any

import httpx

from src.services.agents.security import decrypt_value
from src.services.custom_tools.openapi_parser import OpenAPIParser
from src.services.security.url_validator import validate_url

logger = logging.getLogger(__name__)


class ToolExecutor:
    """Executor for custom tool operations"""

    def __init__(
        self,
        parser: OpenAPIParser,
        auth_type: str,
        auth_config: dict[str, Any],
        timeout: int = 30,
    ):
        """
        Initialize the tool executor

        Args:
            parser: OpenAPI parser instance
            auth_type: Type of authentication (none, basic, bearer, custom)
            auth_config: Encrypted authentication configuration
            timeout: Request timeout in seconds
        """
        self.parser = parser
        self.auth_type = auth_type.lower()
        self.auth_config = auth_config
        self.timeout = timeout

    def _build_headers(self, operation: dict[str, Any]) -> dict[str, str]:
        """
        Build request headers including authentication

        Args:
            operation: The operation definition

        Returns:
            Dictionary of headers
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Add authentication headers
        if self.auth_type == "bearer":
            token = decrypt_value(self.auth_config.get("token", ""))
            headers["Authorization"] = f"Bearer {token}"

        elif self.auth_type == "basic":
            username = decrypt_value(self.auth_config.get("username", ""))
            password = decrypt_value(self.auth_config.get("password", ""))
            import base64

            credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
            headers["Authorization"] = f"Basic {credentials}"

        elif self.auth_type == "custom":
            # Custom headers from auth_config
            custom_headers = self.auth_config.get("headers", {})
            for key, value in custom_headers.items():
                # Decrypt if the value is encrypted
                if isinstance(value, str) and value.startswith("encrypted:"):
                    value = decrypt_value(value)
                headers[key] = value

        return headers

    def _prepare_parameters(
        self, operation: dict[str, Any], params: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], Any | None]:
        """
        Prepare parameters for the request

        Args:
            operation: The operation definition
            params: The parameters provided

        Returns:
            Tuple of (path_params, query_params, header_params, body)
        """
        path_params = {}
        query_params = {}
        header_params = {}
        body = None

        # Categorize parameters
        for param in operation.get("parameters", []):
            param_name = param["name"]
            if param_name not in params:
                continue

            param_value = params[param_name]
            param_in = param.get("in", "query")

            if param_in == "path":
                path_params[param_name] = param_value
            elif param_in == "query":
                query_params[param_name] = param_value
            elif param_in == "header":
                header_params[param_name] = param_value

        # Handle request body
        if "body" in params and operation.get("request_body"):
            body = params["body"]

        return path_params, query_params, header_params, body

    async def execute(self, operation_id: str, params: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a tool operation

        Args:
            operation_id: The operation ID to execute
            params: Parameters for the operation

        Returns:
            Dictionary with execution result

        Raises:
            ValueError: If operation not found or parameters invalid
            httpx.HTTPError: If request fails
        """
        # Get operation definition
        operation = self.parser.get_tool_definition(operation_id)
        if not operation:
            raise ValueError(f"Operation '{operation_id}' not found")

        # Validate parameters
        is_valid, errors = self.parser.validate_parameters(operation, params)
        if not is_valid:
            raise ValueError(f"Invalid parameters: {', '.join(errors)}")

        # Prepare request components
        path_params, query_params, header_params, body = self._prepare_parameters(operation, params)

        # Build URL
        url = self.parser.build_request_url(operation, path_params)

        # Use the HTTP client's own URL normalization, including effective ports.
        # Even a malformed/absolute schema path must not redirect stored credentials.
        try:
            configured = httpx.URL(self.parser.server_url)
            destination = httpx.URL(url)

            def origin(value):
                return value.scheme, value.host, value.port

            if (
                configured.scheme not in {"http", "https"}
                or not configured.host
                or configured.userinfo
                or destination.userinfo
                or origin(destination) != origin(configured)
            ):
                return {"success": False, "error": "Tool destination must match the configured API origin"}
        except (httpx.InvalidURL, ValueError, TypeError):
            return {"success": False, "error": "Invalid tool destination"}

        # SECURITY: Validate URL to prevent SSRF attacks
        is_valid, error_message = validate_url(
            url, allowed_schemes=["http", "https"], block_private_ips=True, resolve_dns=True
        )
        if not is_valid:
            logger.warning(f"SSRF protection blocked URL: {url} - {error_message}")
            return {
                "success": False,
                "error": f"URL validation failed: {error_message}",
            }

        # Build headers
        headers = self._build_headers(operation)
        headers.update(header_params)

        # Make request
        method = operation["method"].lower()

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.info(f"Executing {method.upper()} {url} with params: {query_params}")

                if method == "get":
                    response = await client.get(url, params=query_params, headers=headers)
                elif method == "post":
                    response = await client.post(url, params=query_params, json=body, headers=headers)
                elif method == "put":
                    response = await client.put(url, params=query_params, json=body, headers=headers)
                elif method == "patch":
                    response = await client.patch(url, params=query_params, json=body, headers=headers)
                elif method == "delete":
                    response = await client.delete(url, params=query_params, headers=headers)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                # Raise for HTTP errors
                response.raise_for_status()

                # Parse response
                try:
                    response_data = response.json()
                except json.JSONDecodeError:
                    response_data = {"text": response.text}

                return {
                    "success": True,
                    "status_code": response.status_code,
                    "data": response_data,
                    "headers": dict(response.headers),
                }

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error executing {operation_id}: {e}")
            try:
                error_data = e.response.json()
            except json.JSONDecodeError:
                error_data = {"text": e.response.text}

            return {
                "success": False,
                "status_code": e.response.status_code,
                "error": str(e),
                "data": error_data,
            }

        except httpx.RequestError as e:
            logger.error(f"Request error executing {operation_id}: {e}")
            return {
                "success": False,
                "error": f"Request failed: {str(e)}",
            }

        except Exception as e:
            logger.error(f"Unexpected error executing {operation_id}: {e}")
            return {
                "success": False,
                "error": f"Execution failed: {str(e)}",
            }

    async def test_connection(self) -> dict[str, Any]:
        """
        Test the connection to the API

        Returns:
            Dictionary with test result
        """
        # Try to get the first available operation
        operations = self.parser.get_available_operations()
        if not operations:
            return {
                "success": False,
                "error": "No operations available to test",
            }

        # Find a GET operation with no required parameters
        test_operation = None
        for op in operations:
            if op["method"] == "GET":
                required_params = [p for p in op.get("parameters", []) if p.get("required")]
                if not required_params and not op.get("request_body", {}).get("required"):
                    test_operation = op
                    break

        if not test_operation:
            return {
                "success": False,
                "error": "No suitable operation found for testing (need a GET with no required params)",
            }

        # Execute the test operation
        try:
            result = await self.execute(test_operation["operation_id"], {})
            return {
                "success": result["success"],
                "operation_tested": test_operation["operation_id"],
                "status_code": result.get("status_code"),
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Test failed: {str(e)}",
            }
