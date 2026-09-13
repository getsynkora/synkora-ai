"""
OpenAPI Schema Parser

Parses OpenAPI 3.0/3.1 specifications to extract tool definitions
that can be used by agents.
"""

import logging
from typing import Any
from urllib.parse import quote, urljoin

logger = logging.getLogger(__name__)


class OpenAPIParser:
    """Parser for OpenAPI specifications"""

    def __init__(self, schema: dict[str, Any], server_url: str | None = None):
        """
        Initialize the parser with an OpenAPI schema

        Args:
            schema: The OpenAPI specification as a dictionary
            server_url: Optional override for the server URL
        """
        self.schema = schema
        self.server_url = server_url or self._extract_server_url()
        self.openapi_version = schema.get("openapi", "3.0.0")

    def _extract_server_url(self) -> str:
        """Extract the first server URL from the schema"""
        servers = self.schema.get("servers", [])
        if servers and len(servers) > 0:
            return servers[0].get("url", "")
        return ""

    def get_available_operations(self) -> list[dict[str, Any]]:
        """
        Extract all available operations from the OpenAPI schema

        Returns:
            List of operation definitions with metadata
        """
        operations = []
        paths = self.schema.get("paths", {})

        for path, path_item in paths.items():
            # Skip parameters and other non-operation keys
            for method in ["get", "post", "put", "patch", "delete", "head", "options"]:
                if method not in path_item:
                    continue

                operation = path_item[method]
                operation_id = operation.get("operationId", f"{method}_{path.replace('/', '_')}")

                operations.append(
                    {
                        "operation_id": operation_id,
                        "method": method.upper(),
                        "path": path,
                        "summary": operation.get("summary", ""),
                        "description": operation.get("description", ""),
                        "parameters": self._parse_parameters(operation, path_item),
                        "request_body": self._parse_request_body(operation),
                        "responses": operation.get("responses", {}),
                        "security": operation.get("security", path_item.get("security", [])),
                        "tags": operation.get("tags", []),
                    }
                )

        return operations

    def _parse_parameters(self, operation: dict[str, Any], path_item: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Parse parameters from operation and path item

        Args:
            operation: The operation object
            path_item: The path item object

        Returns:
            List of parameter definitions
        """
        parameters = []

        # Path-level parameters
        path_params = path_item.get("parameters", [])
        # Operation-level parameters
        op_params = operation.get("parameters", [])

        # Combine and deduplicate (operation params override path params)
        all_params = {}
        for param in path_params + op_params:
            # Handle $ref
            if "$ref" in param:
                param = self._resolve_ref(param["$ref"])

            param_key = f"{param.get('in', '')}_{param.get('name', '')}"
            all_params[param_key] = param

        for param in all_params.values():
            param_def = {
                "name": param.get("name"),
                "in": param.get("in"),  # query, header, path, cookie
                "description": param.get("description", ""),
                "required": param.get("required", False),
                "schema": param.get("schema", {}),
                "example": param.get("example"),
            }
            parameters.append(param_def)

        return parameters

    def _parse_request_body(self, operation: dict[str, Any]) -> dict[str, Any] | None:
        """
        Parse request body schema

        Args:
            operation: The operation object

        Returns:
            Request body definition or None
        """
        request_body = operation.get("requestBody")
        if not request_body:
            return None

        # Handle $ref
        if "$ref" in request_body:
            request_body = self._resolve_ref(request_body["$ref"])

        content = request_body.get("content", {})
        # Prefer application/json
        if "application/json" in content:
            schema = content["application/json"].get("schema", {})
        else:
            # Use first available content type
            first_content = next(iter(content.values()), {})
            schema = first_content.get("schema", {})

        return {
            "description": request_body.get("description", ""),
            "required": request_body.get("required", False),
            "schema": schema,
        }

    def _resolve_ref(self, ref: str) -> dict[str, Any]:
        """
        Resolve a $ref pointer in the schema

        Args:
            ref: The reference string (e.g., "#/components/schemas/Pet")

        Returns:
            The resolved object
        """
        if not ref.startswith("#/"):
            logger.warning(f"External references not supported: {ref}")
            return {}

        # Remove leading #/ and split by /
        parts = ref[2:].split("/")

        # Navigate through the schema
        current = self.schema
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part, {})
            else:
                return {}

        return current

    def get_tool_definition(self, operation_id: str) -> dict[str, Any] | None:
        """
        Get a specific tool definition by operation ID

        Args:
            operation_id: The operation ID to retrieve

        Returns:
            Tool definition or None if not found
        """
        operations = self.get_available_operations()
        for op in operations:
            if op["operation_id"] == operation_id:
                return op
        return None

    def build_request_url(self, operation: dict[str, Any], path_params: dict[str, Any]) -> str:
        """
        Build the full request URL for an operation

        Args:
            operation: The operation definition
            path_params: Path parameter values

        Returns:
            The complete URL
        """
        path = operation["path"]

        # Replace path parameters
        for param_name, param_value in path_params.items():
            path = path.replace(f"{{{param_name}}}", quote(str(param_value), safe=""))

        return urljoin(self.server_url, path)

    def validate_parameters(self, operation: dict[str, Any], params: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Validate parameters against the operation schema

        Args:
            operation: The operation definition
            params: The parameters to validate

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []

        # Check required parameters
        for param in operation.get("parameters", []):
            if param.get("required") and param["name"] not in params:
                errors.append(f"Required parameter '{param['name']}' is missing")

        # Check request body if required
        request_body = operation.get("request_body")
        if request_body and request_body.get("required"):
            if "body" not in params:
                errors.append("Request body is required but not provided")

        return len(errors) == 0, errors

    def get_schema_info(self) -> dict[str, Any]:
        """
        Get general information about the API

        Returns:
            Dictionary with API metadata
        """
        info = self.schema.get("info", {})
        return {
            "title": info.get("title", "Unknown API"),
            "version": info.get("version", "1.0.0"),
            "description": info.get("description", ""),
            "server_url": self.server_url,
            "openapi_version": self.openapi_version,
            "operation_count": len(self.get_available_operations()),
        }
