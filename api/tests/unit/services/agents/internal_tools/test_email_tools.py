"""
Tests for email_tools.py - Email Tools for AI Agents

Tests the email sending capabilities using configured integration providers.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


class TestInternalSendEmail:
    """Tests for internal_send_email function."""

    @pytest.mark.asyncio
    async def test_requires_runtime_context(self):
        from src.services.agents.internal_tools.email_tools import internal_send_email

        result = await internal_send_email(
            to_email="user@example.com",
            subject="Test",
            body="Hello",
            runtime_context=None,
        )

        assert result["success"] is False
        assert "Runtime context is required" in result["error"]

    @pytest.mark.asyncio
    async def test_validates_email_address(self):
        from src.services.agents.internal_tools.email_tools import internal_send_email

        mock_context = MagicMock()
        mock_context.db_session = AsyncMock(spec=AsyncSession)
        mock_context.tenant_id = "tenant-123"

        result = await internal_send_email(
            to_email="invalid-email",
            subject="Test",
            body="Hello",
            runtime_context=mock_context,
        )

        assert result["success"] is False
        assert "Invalid recipient email" in result["error"]

    @pytest.mark.asyncio
    async def test_validates_empty_email(self):
        from src.services.agents.internal_tools.email_tools import internal_send_email

        mock_context = MagicMock()
        mock_context.db_session = AsyncMock(spec=AsyncSession)
        mock_context.tenant_id = "tenant-123"

        result = await internal_send_email(
            to_email="",
            subject="Test",
            body="Hello",
            runtime_context=mock_context,
        )

        assert result["success"] is False
        assert "Invalid recipient email" in result["error"]

    @pytest.mark.asyncio
    async def test_requires_subject(self):
        from src.services.agents.internal_tools.email_tools import internal_send_email

        mock_context = MagicMock()
        mock_context.db_session = AsyncMock(spec=AsyncSession)
        mock_context.tenant_id = "tenant-123"

        result = await internal_send_email(
            to_email="user@example.com",
            subject="",
            body="Hello",
            runtime_context=mock_context,
        )

        assert result["success"] is False
        assert "subject is required" in result["error"]

    @pytest.mark.asyncio
    async def test_requires_body(self):
        from src.services.agents.internal_tools.email_tools import internal_send_email

        mock_context = MagicMock()
        mock_context.db_session = AsyncMock(spec=AsyncSession)
        mock_context.tenant_id = "tenant-123"

        result = await internal_send_email(
            to_email="user@example.com",
            subject="Test",
            body="",
            runtime_context=mock_context,
        )

        assert result["success"] is False
        assert "body is required" in result["error"]

    @pytest.mark.asyncio
    async def test_sends_async_email_via_celery(self):
        from src.services.agents.internal_tools.email_tools import internal_send_email

        mock_context = MagicMock()
        mock_context.db_session = AsyncMock(spec=AsyncSession)
        mock_context.tenant_id = "tenant-123"

        mock_task = MagicMock()
        mock_task.id = "task-abc123"

        with patch("src.tasks.email_tasks.send_email_task") as mock_send:
            mock_send.delay.return_value = mock_task

            result = await internal_send_email(
                to_email="user@example.com",
                subject="Test Subject",
                body="Hello World",
                runtime_context=mock_context,
            )

            assert result["success"] is True
            assert result["async"] is True
            assert result["task_id"] == "task-abc123"
            assert result["to_email"] == "user@example.com"

    @pytest.mark.asyncio
    async def test_sends_sync_email_when_async_disabled(self):
        from src.services.agents.internal_tools.email_tools import internal_send_email

        mock_context = MagicMock()
        mock_context.db_session = AsyncMock(spec=AsyncSession)
        mock_context.tenant_id = "tenant-123"

        mock_email_service = MagicMock()
        mock_email_service.send_email = AsyncMock(
            return_value={
                "success": True,
                "provider": "smtp",
            }
        )

        with patch(
            "src.services.agents.internal_tools.email_tools.EmailService",
            return_value=mock_email_service,
        ):
            result = await internal_send_email(
                to_email="user@example.com",
                subject="Test Subject",
                body="Hello World",
                runtime_context=mock_context,
                config={"async": False},
            )

            assert result["success"] is True
            assert result["async"] is False
            assert result["provider"] == "smtp"

    @pytest.mark.asyncio
    async def test_falls_back_to_sync_on_celery_error(self):
        from src.services.agents.internal_tools.email_tools import internal_send_email

        mock_context = MagicMock()
        mock_context.db_session = AsyncMock(spec=AsyncSession)
        mock_context.tenant_id = "tenant-123"

        mock_email_service = MagicMock()
        mock_email_service.send_email = AsyncMock(
            return_value={
                "success": True,
                "provider": "sendgrid",
            }
        )

        with (
            patch("src.tasks.email_tasks.send_email_task") as mock_task,
            patch(
                "src.services.agents.internal_tools.email_tools.EmailService",
                return_value=mock_email_service,
            ),
        ):
            mock_task.delay.side_effect = Exception("Celery broker not available")

            result = await internal_send_email(
                to_email="user@example.com",
                subject="Test Subject",
                body="Hello World",
                runtime_context=mock_context,
            )

            assert result["success"] is True
            assert result["async"] is False

    @pytest.mark.asyncio
    async def test_handles_sync_send_failure(self):
        from src.services.agents.internal_tools.email_tools import internal_send_email

        mock_context = MagicMock()
        mock_context.db_session = AsyncMock(spec=AsyncSession)
        mock_context.tenant_id = "tenant-123"

        mock_email_service = MagicMock()
        mock_email_service.send_email = AsyncMock(
            return_value={
                "success": False,
                "message": "SMTP authentication failed",
                "provider": "smtp",
            }
        )

        with patch(
            "src.services.agents.internal_tools.email_tools.EmailService",
            return_value=mock_email_service,
        ):
            result = await internal_send_email(
                to_email="user@example.com",
                subject="Test Subject",
                body="Hello World",
                runtime_context=mock_context,
                config={"async": False},
            )

            assert result["success"] is False
            assert "SMTP authentication failed" in result["error"]

    @pytest.mark.asyncio
    async def test_converts_plain_text_to_html(self):
        from src.services.agents.internal_tools.email_tools import internal_send_email

        mock_context = MagicMock()
        mock_context.db_session = AsyncMock(spec=AsyncSession)
        mock_context.tenant_id = "tenant-123"

        mock_email_service = MagicMock()
        mock_email_service.send_email = AsyncMock(return_value={"success": True, "provider": "smtp"})

        with patch(
            "src.services.agents.internal_tools.email_tools.EmailService",
            return_value=mock_email_service,
        ):
            result = await internal_send_email(
                to_email="user@example.com",
                subject="Test",
                body="Line 1\nLine 2",
                html=False,
                runtime_context=mock_context,
                config={"async": False},
            )

            assert result["success"] is True
            # Verify call args contain converted HTML
            call_kwargs = mock_email_service.send_email.call_args.kwargs
            assert "<br>" in call_kwargs["html_content"]

    @pytest.mark.asyncio
    async def test_passes_cc_and_bcc_to_celery(self):
        from src.services.agents.internal_tools.email_tools import internal_send_email

        mock_context = MagicMock()
        mock_context.db_session = AsyncMock(spec=AsyncSession)
        mock_context.tenant_id = "tenant-123"

        mock_task = MagicMock()
        mock_task.id = "task-123"

        with patch("src.tasks.email_tasks.send_email_task") as mock_send:
            mock_send.delay.return_value = mock_task

            result = await internal_send_email(
                to_email="user@example.com",
                subject="Test",
                body="Hello",
                cc="cc1@example.com, cc2@example.com",
                bcc="bcc@example.com",
                runtime_context=mock_context,
            )

            assert result["success"] is True
            call_kwargs = mock_send.delay.call_args.kwargs
            assert call_kwargs["cc"] == ["cc1@example.com", "cc2@example.com"]
            assert call_kwargs["bcc"] == ["bcc@example.com"]

    @pytest.mark.asyncio
    async def test_handles_exception(self):
        from src.services.agents.internal_tools.email_tools import internal_send_email

        mock_context = MagicMock()
        mock_context.db_session = AsyncMock(spec=AsyncSession)
        mock_context.tenant_id = "tenant-123"

        with (
            patch("src.tasks.email_tasks.send_email_task") as mock_task,
            patch("src.services.agents.internal_tools.email_tools.EmailService") as mock_service,
        ):
            mock_task.delay.side_effect = Exception("Task failed")
            mock_service.side_effect = Exception("Unexpected error")

            result = await internal_send_email(
                to_email="user@example.com",
                subject="Test",
                body="Hello",
                runtime_context=mock_context,
            )

            assert result["success"] is False
            assert "Failed to send email" in result["error"]


class TestInternalSendBulkEmails:
    """Tests for internal_send_bulk_emails function."""

    @pytest.mark.asyncio
    async def test_requires_non_empty_recipients(self):
        from src.services.agents.internal_tools.email_tools import internal_send_bulk_emails

        result = await internal_send_bulk_emails(
            recipients=[],
            subject="Test",
            body="Hello",
        )

        assert result["success"] is False
        assert "non-empty list" in result["error"]

    @pytest.mark.asyncio
    async def test_requires_list_not_none(self):
        from src.services.agents.internal_tools.email_tools import internal_send_bulk_emails

        result = await internal_send_bulk_emails(
            recipients=None,
            subject="Test",
            body="Hello",
        )

        assert result["success"] is False
        assert "non-empty list" in result["error"]

    @pytest.mark.asyncio
    async def test_limits_recipients_to_100(self):
        from src.services.agents.internal_tools.email_tools import internal_send_bulk_emails

        # Generate 101 recipients
        recipients = [f"user{i}@example.com" for i in range(101)]

        result = await internal_send_bulk_emails(
            recipients=recipients,
            subject="Test",
            body="Hello",
        )

        assert result["success"] is False
        assert "Maximum 100 recipients" in result["error"]

    @pytest.mark.asyncio
    async def test_sends_to_all_recipients(self):
        from src.services.agents.internal_tools.email_tools import internal_send_bulk_emails

        mock_context = MagicMock()
        mock_context.db_session = AsyncMock(spec=AsyncSession)
        mock_context.tenant_id = "tenant-123"

        mock_task = MagicMock()
        mock_task.id = "task-123"

        with patch("src.tasks.email_tasks.send_email_task") as mock_send:
            mock_send.delay.return_value = mock_task

            result = await internal_send_bulk_emails(
                recipients=["user1@example.com", "user2@example.com", "user3@example.com"],
                subject="Newsletter",
                body="Weekly update",
                runtime_context=mock_context,
            )

            assert result["success"] is True
            assert result["total"] == 3
            assert result["sent"] == 3
            assert result["failed"] == 0
            assert len(result["results"]) == 3

    @pytest.mark.asyncio
    async def test_counts_failures_correctly(self):
        from src.services.agents.internal_tools.email_tools import internal_send_bulk_emails

        # No runtime context will cause all sends to fail
        result = await internal_send_bulk_emails(
            recipients=["user1@example.com", "user2@example.com"],
            subject="Test",
            body="Hello",
            runtime_context=None,
        )

        assert result["success"] is True  # Overall operation succeeded
        assert result["total"] == 2
        assert result["sent"] == 0
        assert result["failed"] == 2

    @pytest.mark.asyncio
    async def test_handles_exception(self):
        from src.services.agents.internal_tools.email_tools import internal_send_bulk_emails

        # Pass an invalid type to trigger exception
        result = await internal_send_bulk_emails(
            recipients="not-a-list",  # type: ignore
            subject="Test",
            body="Hello",
        )

        assert result["success"] is False
        assert "non-empty list" in result["error"]


class TestInternalSendTemplateEmail:
    """Tests for internal_send_template_email function."""

    @pytest.mark.asyncio
    async def test_returns_not_implemented_error(self):
        from src.services.agents.internal_tools.email_tools import internal_send_template_email

        result = await internal_send_template_email(
            to_email="user@example.com",
            template_name="welcome",
            template_variables={"name": "John"},
        )

        assert result["success"] is False
        assert "not yet implemented" in result["error"]


class TestInternalTestEmailConnection:
    """Tests for internal_test_email_connection function."""

    @pytest.mark.asyncio
    async def test_requires_runtime_context(self):
        from src.services.agents.internal_tools.email_tools import internal_test_email_connection

        result = await internal_test_email_connection(runtime_context=None)

        assert result["success"] is False
        assert "Runtime context is required" in result["error"]

    @pytest.mark.asyncio
    async def test_returns_connection_status_success(self):
        from src.services.agents.internal_tools.email_tools import internal_test_email_connection

        mock_context = MagicMock()
        mock_context.db_session = AsyncMock(spec=AsyncSession)
        mock_context.tenant_id = "tenant-123"

        mock_email_service = MagicMock()
        mock_email_service.test_connection = AsyncMock(
            return_value={
                "success": True,
                "message": "Connection successful",
                "provider": "sendgrid",
            }
        )

        with patch(
            "src.services.agents.internal_tools.email_tools.EmailService",
            return_value=mock_email_service,
        ):
            result = await internal_test_email_connection(runtime_context=mock_context)

            assert result["success"] is True
            assert result["provider"] == "sendgrid"
            assert "successful" in result["message"]

    @pytest.mark.asyncio
    async def test_returns_connection_status_failure(self):
        from src.services.agents.internal_tools.email_tools import internal_test_email_connection

        mock_context = MagicMock()
        mock_context.db_session = AsyncMock(spec=AsyncSession)
        mock_context.tenant_id = "tenant-123"

        mock_email_service = MagicMock()
        mock_email_service.test_connection = AsyncMock(
            return_value={
                "success": False,
                "message": "Authentication failed",
                "provider": "smtp",
            }
        )

        with patch(
            "src.services.agents.internal_tools.email_tools.EmailService",
            return_value=mock_email_service,
        ):
            result = await internal_test_email_connection(runtime_context=mock_context)

            assert result["success"] is False
            assert "Authentication failed" in result["message"]

    @pytest.mark.asyncio
    async def test_handles_exception(self):
        from src.services.agents.internal_tools.email_tools import internal_test_email_connection

        mock_context = MagicMock()
        mock_context.db_session = AsyncMock(spec=AsyncSession)
        mock_context.tenant_id = "tenant-123"

        with patch("src.services.agents.internal_tools.email_tools.EmailService") as mock_service:
            mock_service.side_effect = Exception("Service unavailable")

            result = await internal_test_email_connection(runtime_context=mock_context)

            assert result["success"] is False
            assert "Connection test failed" in result["error"]
