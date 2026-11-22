"""Tests for permission middleware."""

from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.middleware.permissions import (
    check_permission_dependency,
    require_permission,
)
from src.models import Account


class TestRequirePermission:
    """Tests for require_permission decorator."""

    @pytest.mark.asyncio
    async def test_require_permission_success(self):
        """Test decorator allows access when permission granted."""
        # Mock dependencies
        mock_account = Mock(spec=Account)
        mock_account.id = uuid4()
        tenant_id = str(uuid4())
        mock_db = AsyncMock()

        # Mock permission service
        with patch("src.middleware.permissions.PermissionService") as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.check_permission = AsyncMock(return_value=True)

            # Create decorated function
            @require_permission("agents", "create")
            async def test_func(current_account, tenant_id, db):
                return {"success": True}

            # Call function
            result = await test_func(current_account=mock_account, tenant_id=tenant_id, db=mock_db)

            # Verify
            assert result == {"success": True}
            mock_instance.check_permission.assert_called_once()

    @pytest.mark.asyncio
    async def test_require_permission_denied(self):
        """Test decorator blocks access when permission denied."""
        # Mock dependencies
        mock_account = Mock(spec=Account)
        mock_account.id = uuid4()
        tenant_id = str(uuid4())
        mock_db = AsyncMock()

        # Mock permission service
        with patch("src.middleware.permissions.PermissionService") as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.check_permission = AsyncMock(return_value=False)

            # Create decorated function
            @require_permission("agents", "delete")
            async def test_func(current_account, tenant_id, db):
                return {"success": True}

            # Call function and expect error
            with pytest.raises(HTTPException) as exc_info:
                await test_func(current_account=mock_account, tenant_id=tenant_id, db=mock_db)

            # Verify error
            assert exc_info.value.status_code == 403
            assert "Permission denied: agents.delete" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_require_permission_missing_account(self):
        """Test decorator raises error when current_account is missing."""
        tenant_id = str(uuid4())
        mock_db = AsyncMock()

        @require_permission("agents", "create")
        async def test_func(current_account, tenant_id, db):
            return {"success": True}

        # Call without current_account
        with pytest.raises(HTTPException) as exc_info:
            await test_func(current_account=None, tenant_id=tenant_id, db=mock_db)

        # Verify error
        assert exc_info.value.status_code == 500
        assert "Missing required dependencies" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_require_permission_missing_tenant_id(self):
        """Test decorator raises error when tenant_id is missing."""
        mock_account = Mock(spec=Account)
        mock_account.id = uuid4()
        mock_db = AsyncMock()

        @require_permission("agents", "create")
        async def test_func(current_account, tenant_id, db):
            return {"success": True}

        # Call without tenant_id
        with pytest.raises(HTTPException) as exc_info:
            await test_func(current_account=mock_account, tenant_id=None, db=mock_db)

        # Verify error
        assert exc_info.value.status_code == 500
        assert "Missing required dependencies" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_require_permission_missing_db(self):
        """Test decorator raises error when db is missing."""
        mock_account = Mock(spec=Account)
        mock_account.id = uuid4()
        tenant_id = str(uuid4())

        @require_permission("agents", "create")
        async def test_func(current_account, tenant_id, db):
            return {"success": True}

        # Call without db
        with pytest.raises(HTTPException) as exc_info:
            await test_func(current_account=mock_account, tenant_id=tenant_id, db=None)

        # Verify error
        assert exc_info.value.status_code == 500
        assert "Missing required dependencies" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_require_permission_with_different_resources(self):
        """Test decorator with different resource types."""
        mock_account = Mock(spec=Account)
        mock_account.id = uuid4()
        tenant_id = str(uuid4())
        mock_db = AsyncMock()

        with patch("src.middleware.permissions.PermissionService") as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.check_permission = AsyncMock(return_value=True)

            # Test with integration_configs resource
            @require_permission("integration_configs", "update")
            async def test_func(current_account, tenant_id, db):
                return {"success": True}

            result = await test_func(current_account=mock_account, tenant_id=tenant_id, db=mock_db)

            assert result == {"success": True}
            # Verify correct resource/action passed
            call_kwargs = mock_instance.check_permission.call_args.kwargs
            assert call_kwargs["resource"] == "integration_configs"
            assert call_kwargs["action"] == "update"

    @pytest.mark.asyncio
    async def test_require_permission_preserves_function_metadata(self):
        """Test decorator preserves original function metadata."""

        @require_permission("agents", "read")
        async def test_func(current_account, tenant_id, db):
            """Test function docstring."""
            return {"success": True}

        # Verify function name is preserved
        assert test_func.__name__ == "test_func"


class TestCheckPermissionDependency:
    """Tests for check_permission_dependency function."""

    @pytest.mark.asyncio
    async def test_check_permission_dependency_success(self):
        """Test dependency function allows access when permission granted."""
        mock_account = Mock(spec=Account)
        mock_account.id = uuid4()
        tenant_id = str(uuid4())
        mock_db = AsyncMock()

        with patch("src.middleware.permissions.PermissionService") as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.check_permission = AsyncMock(return_value=True)

            # Call dependency function
            result = await check_permission_dependency(
                resource="knowledge_bases",
                action="create",
                current_account=mock_account,
                tenant_id=tenant_id,
                db=mock_db,
            )

            # Verify returns None on success
            assert result is None
            mock_instance.check_permission.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_permission_dependency_denied(self):
        """Test dependency function blocks access when permission denied."""
        mock_account = Mock(spec=Account)
        mock_account.id = uuid4()
        tenant_id = str(uuid4())
        mock_db = AsyncMock()

        with patch("src.middleware.permissions.PermissionService") as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.check_permission = AsyncMock(return_value=False)

            # Call dependency function
            with pytest.raises(HTTPException) as exc_info:
                await check_permission_dependency(
                    resource="knowledge_bases",
                    action="delete",
                    current_account=mock_account,
                    tenant_id=tenant_id,
                    db=mock_db,
                )

            # Verify error
            assert exc_info.value.status_code == 403
            assert "Permission denied: knowledge_bases.delete" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_check_permission_dependency_calls_service_correctly(self):
        """Test dependency function calls permission service with correct parameters."""
        account_id = uuid4()
        mock_account = Mock(spec=Account)
        mock_account.id = account_id
        tenant_id = str(uuid4())
        mock_db = AsyncMock()

        with patch("src.middleware.permissions.PermissionService") as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.check_permission = AsyncMock(return_value=True)

            # Call dependency function
            await check_permission_dependency(
                resource="data_sources", action="read", current_account=mock_account, tenant_id=tenant_id, db=mock_db
            )

            # Verify service called with correct params
            call_kwargs = mock_instance.check_permission.call_args.kwargs
            assert str(call_kwargs["account_id"]) == str(account_id)
            assert str(call_kwargs["tenant_id"]) == tenant_id
            assert call_kwargs["resource"] == "data_sources"
            assert call_kwargs["action"] == "read"

    @pytest.mark.asyncio
    async def test_check_permission_dependency_with_various_actions(self):
        """Test dependency function with different action types."""
        mock_account = Mock(spec=Account)
        mock_account.id = uuid4()
        tenant_id = str(uuid4())
        mock_db = AsyncMock()

        actions = ["create", "read", "update", "delete"]

        with patch("src.middleware.permissions.PermissionService") as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.check_permission = AsyncMock(return_value=True)

            for action in actions:
                result = await check_permission_dependency(
                    resource="test_resource",
                    action=action,
                    current_account=mock_account,
                    tenant_id=tenant_id,
                    db=mock_db,
                )

                assert result is None
                # Verify action is passed correctly
                call_kwargs = mock_instance.check_permission.call_args.kwargs
                assert call_kwargs["action"] == action


def test_handoff_permissions_must_be_listed_exactly():
    """'*' used to grant handoff:read and handoff:write; scoped permissions now need to be listed."""
    import uuid as _uuid

    from fastapi import HTTPException

    from src.middleware.agent_api_auth import HandoffAccess

    for permission in ("handoff:read", "handoff:write"):
        with pytest.raises(HTTPException):
            HandoffAccess(_uuid.uuid4(), _uuid.uuid4(), frozenset({"*"})).require(permission)
        HandoffAccess(_uuid.uuid4(), _uuid.uuid4(), frozenset({permission})).require(permission)  # allowed
    HandoffAccess(_uuid.uuid4()).require("handoff:write")  # a logged-in account is unaffected
