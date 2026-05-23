"""Unit tests for Mailisk inbox tools."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


def _runtime_context() -> SimpleNamespace:
    return SimpleNamespace(agent_id="agent-123")


@pytest.mark.asyncio
async def test_resolve_mailisk_config_from_linked_oauth_app():
    """Mailisk config should resolve from the linked agent tool OAuth app."""
    from src.services.agents.internal_tools.mailisk_tools import _resolve_mailisk_config

    ctx = _runtime_context()
    oauth_app = {
        "provider": "mailisk",
        "is_default": True,
        "is_active": True,
        "api_token": "encrypted-token",
        "config": {"namespace": "tenant-tests"},
    }

    with (
        patch(
            "src.services.agents.internal_tools.mailisk_tools._resolve_mailisk_oauth_app",
            new_callable=AsyncMock,
        ) as mock_resolve_app,
        patch("src.services.agents.security.decrypt_value", return_value="test-api-key"),
    ):
        mock_resolve_app.return_value = oauth_app
        config = await _resolve_mailisk_config(
            runtime_context=ctx,
            tool_name="internal_mailisk_generate_test_email",
        )

    mock_resolve_app.assert_awaited_once_with(ctx, "internal_mailisk_generate_test_email")

    assert config.api_key == "test-api-key"
    assert config.namespace == "tenant-tests"
    assert config.base_url == "https://api.mailisk.com"


@pytest.mark.asyncio
async def test_generate_test_email_uses_configured_namespace():
    """Generated email addresses should use the tenant's configured namespace."""
    from src.services.agents.internal_tools.mailisk_tools import internal_mailisk_generate_test_email

    with (
        patch(
            "src.services.agents.internal_tools.mailisk_tools._resolve_mailisk_oauth_app",
            new_callable=AsyncMock,
        ) as mock_resolve_app,
        patch("src.services.agents.security.decrypt_value", return_value="test-api-key"),
    ):
        mock_resolve_app.return_value = {
            "provider": "mailisk",
            "is_active": True,
            "api_token": "encrypted-token",
            "config": {"namespace": "tenant-tests"},
        }
        result = await internal_mailisk_generate_test_email(
            local_part_prefix="Checkout Flow",
            config={"_tool_name": "internal_mailisk_generate_test_email"},
            runtime_context=_runtime_context(),
        )

    assert result["success"] is True
    assert result["namespace"] == "tenant-tests"
    assert result["email"].endswith("@tenant-tests.mailisk.net")
    assert result["local_part"].startswith("checkout-flow-")
    assert result["to_addr_prefix"] == f"{result['local_part']}@"


def test_extract_verification_code_prefers_target_length():
    """Verification code extraction should return the expected numeric OTP."""
    from src.services.agents.internal_tools.mailisk_tools import _extract_verification_code

    code = _extract_verification_code(
        text="Your verification code is 482913. It expires in 10 minutes.",
        html=None,
        code_length=6,
    )

    assert code == "482913"


def test_extract_links_and_pick_matching_link():
    """Link extraction should preserve absolute links and pick the matching verification URL."""
    from src.services.agents.internal_tools.mailisk_tools import _extract_links_from_email, _pick_matching_link

    links = _extract_links_from_email(
        text="Use https://fallback.example.com/verify?token=abc if the button fails.",
        html=('<html><body><a href="https://app.example.com/verify?token=123">Verify email</a></body></html>'),
    )

    assert "https://app.example.com/verify?token=123" in links
    assert "https://fallback.example.com/verify?token=abc" in links
    assert (
        _pick_matching_link(links, domain_includes="app.example.com", url_includes="verify")
        == "https://app.example.com/verify?token=123"
    )


@pytest.mark.asyncio
async def test_wait_for_verification_code_uses_latest_email():
    """The verification-code helper should extract OTPs from the fetched Mailisk email."""
    from src.services.agents.internal_tools.mailisk_tools import internal_mailisk_wait_for_verification_code

    latest_email = {
        "subject": "Verify your sign in",
        "text": "Security code: 731004",
        "html": None,
        "to_addresses": ["run-123@tenant-tests.mailisk.net"],
    }

    with patch(
        "src.services.agents.internal_tools.mailisk_tools.internal_mailisk_wait_for_email",
        new_callable=AsyncMock,
    ) as mock_wait:
        mock_wait.return_value = {
            "success": True,
            "namespace": "tenant-tests",
            "latest_email": latest_email,
        }

        result = await internal_mailisk_wait_for_verification_code(
            recipient_email="run-123@tenant-tests.mailisk.net",
            timeout_ms=5_000,
        )

    assert result["success"] is True
    assert result["code"] == "731004"
    assert result["namespace"] == "tenant-tests"


@pytest.mark.asyncio
async def test_wait_for_verification_link_returns_matching_link():
    """The verification-link helper should return the filtered magic link."""
    from src.services.agents.internal_tools.mailisk_tools import internal_mailisk_wait_for_verification_link

    latest_email = {
        "subject": "Finish signing in",
        "text": "Fallback link: https://fallback.example.com/login?token=def",
        "html": ('<html><body><a href="https://app.example.com/verify?token=abc">Complete sign in</a></body></html>'),
        "to_addresses": ["run-123@tenant-tests.mailisk.net"],
    }

    with patch(
        "src.services.agents.internal_tools.mailisk_tools.internal_mailisk_wait_for_email",
        new_callable=AsyncMock,
    ) as mock_wait:
        mock_wait.return_value = {
            "success": True,
            "namespace": "tenant-tests",
            "latest_email": latest_email,
        }

        result = await internal_mailisk_wait_for_verification_link(
            recipient_email="run-123@tenant-tests.mailisk.net",
            timeout_ms=5_000,
            domain_includes="app.example.com",
            url_includes="verify",
        )

    assert result["success"] is True
    assert result["link"] == "https://app.example.com/verify?token=abc"
    assert result["namespace"] == "tenant-tests"
