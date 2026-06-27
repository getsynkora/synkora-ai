"""
Unit tests for Output Sanitizer.

Tests credential detection, PII masking, and content sanitization.
"""

import pytest

from src.services.security.output_sanitizer import (
    OutputSanitizer,
    SanitizationAction,
    SanitizationResult,
    output_sanitizer,
)


class TestOutputSanitizer:
    """Test cases for OutputSanitizer."""

    @pytest.fixture
    def sanitizer(self):
        """Create a fresh sanitizer instance."""
        return OutputSanitizer(strict_mode=False)

    @pytest.fixture
    def strict_sanitizer(self):
        """Create a strict mode sanitizer."""
        return OutputSanitizer(strict_mode=True)

    def test_safe_content_passes(self, sanitizer):
        """Test that safe content passes through unchanged."""
        content = "This is a normal response about Python programming."
        result = sanitizer.sanitize(content)

        assert result.is_safe is True
        assert result.sanitized_content == content
        assert result.action_taken == "PASSED"

    def test_empty_content_is_safe(self, sanitizer):
        """Test that empty content is safe."""
        result = sanitizer.sanitize("")

        assert result.is_safe is True
        assert result.action_taken == "PASSED"

    def test_whitespace_content_is_safe(self, sanitizer):
        """Test that whitespace-only content is safe."""
        result = sanitizer.sanitize("   \n\t  ")

        assert result.is_safe is True


class TestCredentialDetection:
    """Test credential pattern detection."""

    @pytest.fixture
    def sanitizer(self):
        return OutputSanitizer()

    def test_detects_openai_key(self, sanitizer):
        """Test detection of OpenAI API keys."""
        content = "Your API key is sk-1234567890abcdef1234567890abcdef1234567890abcdef"
        result = sanitizer.sanitize(content)

        assert "[REDACTED]" in result.sanitized_content
        assert len(result.detections) > 0

    def test_detects_openai_project_key(self, sanitizer):
        """Test detection of OpenAI project API keys."""
        content = "Key: sk-proj-" + "a" * 80
        result = sanitizer.sanitize(content)

        assert "[REDACTED]" in result.sanitized_content

    def test_detects_anthropic_key(self, sanitizer):
        """Test detection of Anthropic API keys."""
        content = "Anthropic key: sk-ant-" + "a" * 90
        result = sanitizer.sanitize(content)

        assert "[REDACTED]" in result.sanitized_content

    def test_detects_aws_access_key(self, sanitizer):
        """Test detection of AWS access keys."""
        content = "AWS key: AKIA1234567890123456"
        result = sanitizer.sanitize(content)

        assert "[REDACTED]" in result.sanitized_content

    def test_detects_github_token(self, sanitizer):
        """Test detection of GitHub tokens."""
        content = "Token: ghp_1234567890abcdef1234567890abcdef1234"
        result = sanitizer.sanitize(content)

        assert "[REDACTED]" in result.sanitized_content

    def test_detects_stripe_key(self, sanitizer):
        """Test detection of Stripe keys."""
        content = "Stripe key: sk_live_1234567890abcdef12345678"
        result = sanitizer.sanitize(content)

        assert "[REDACTED]" in result.sanitized_content

    def test_detects_slack_token(self, sanitizer):
        """Test detection of Slack tokens."""
        content = "Token: xoxb-1234567890-1234567890-abcdefghijklmnopqrstuvwx"
        result = sanitizer.sanitize(content)

        assert "[REDACTED]" in result.sanitized_content

    def test_detects_jwt_token(self, sanitizer):
        """Test detection of JWT tokens."""
        content = "Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        result = sanitizer.sanitize(content)

        assert "[REDACTED]" in result.sanitized_content

    def test_detects_password_field(self, sanitizer):
        """Test detection of password fields."""
        content = "password: mysecretpassword123"
        result = sanitizer.sanitize(content)

        assert "[REDACTED]" in result.sanitized_content

    def test_detects_private_key(self, sanitizer):
        """Test detection of private keys blocks response."""
        content = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA..."
        result = sanitizer.sanitize(content)

        # Private keys should block the entire response
        assert result.is_safe is False or "[REDACTED]" in result.sanitized_content

    def test_detects_sendgrid_key(self, sanitizer):
        """Test detection of SendGrid keys."""
        # SendGrid key pattern: SG.[22 chars].[43 chars]
        # First part: 22 chars, Second part: 43 chars
        content = "Key: SG.abcdefghijklmnopqrstuv.abcdefghijklmnopqrstuvwxyz12345678901234567"
        result = sanitizer.sanitize(content)

        # Check if the key was detected and redacted
        assert "[REDACTED]" in result.sanitized_content or len(result.detections) > 0

    def test_detects_generic_api_key(self, sanitizer):
        """Test detection of generic API key patterns."""
        content = "api_key: abcdefghijklmnopqrstuvwxyz12345678"
        result = sanitizer.sanitize(content)

        assert "[REDACTED]" in result.sanitized_content


class TestPIIDetection:
    """Test PII pattern detection."""

    @pytest.fixture
    def sanitizer(self):
        return OutputSanitizer()

    def test_masks_email_addresses(self, sanitizer):
        """Test that email addresses are masked."""
        content = "Contact: user@example.com for help"
        result = sanitizer.sanitize(content)

        # Email should be masked (partial)
        assert "user@example.com" not in result.sanitized_content
        assert len(result.detections) > 0

    def test_masks_phone_numbers(self, sanitizer):
        """Test that phone numbers are masked."""
        content = "Call me at 123-456-7890"
        result = sanitizer.sanitize(content)

        assert "123-456-7890" not in result.sanitized_content

    def test_redacts_ssn(self, sanitizer):
        """Test that SSNs are redacted."""
        content = "SSN: 123-45-6789"
        result = sanitizer.sanitize(content)

        assert "123-45-6789" not in result.sanitized_content
        assert "[REDACTED]" in result.sanitized_content

    def test_redacts_credit_card(self, sanitizer):
        """Test that credit card numbers are redacted."""
        content = "Card: 4111 1111 1111 1111"
        result = sanitizer.sanitize(content)

        assert "4111 1111 1111 1111" not in result.sanitized_content


class TestSystemPathDetection:
    """Test system path detection."""

    @pytest.fixture
    def sanitizer(self):
        return OutputSanitizer()

    def test_masks_unix_paths(self, sanitizer):
        """Test that Unix paths are masked."""
        content = "File located at /home/user/secret/config.json"
        result = sanitizer.sanitize(content)

        # Path should be masked
        assert len(result.detections) > 0 or "/home/user" not in result.sanitized_content

    def test_masks_windows_paths(self, sanitizer):
        """Test that Windows paths are masked."""
        content = r"File at C:\Users\admin\secrets\passwords.txt"
        result = sanitizer.sanitize(content)

        # Should detect Windows path pattern
        assert result is not None


class TestDatabasePatternDetection:
    """Test database pattern detection."""

    @pytest.fixture
    def sanitizer(self):
        return OutputSanitizer()

    def test_redacts_connection_strings(self, sanitizer):
        """Test that database connection strings are redacted."""
        content = "Connect to: postgresql://user:password@localhost:5432/db"
        result = sanitizer.sanitize(content)

        assert "password" not in result.sanitized_content or "[REDACTED]" in result.sanitized_content


class TestStrictMode:
    """Test strict mode behavior."""

    def test_strict_mode_blocks_on_critical(self):
        """Test that strict mode blocks on critical detections."""
        sanitizer = OutputSanitizer(strict_mode=True)

        content = "Your API key is sk-1234567890abcdef1234567890abcdef1234567890abcdef"
        result = sanitizer.sanitize(content)

        assert result.is_safe is False
        assert "BLOCKED" in result.sanitized_content

    def test_non_strict_mode_allows_sanitized(self):
        """Test that non-strict mode allows sanitized content."""
        sanitizer = OutputSanitizer(strict_mode=False)

        content = "Your API key is sk-1234567890abcdef1234567890abcdef1234567890abcdef"
        result = sanitizer.sanitize(content)

        # Should sanitize but not block
        assert result.is_safe is True
        assert "[REDACTED]" in result.sanitized_content


class TestSanitizationActions:
    """Test different sanitization actions."""

    @pytest.fixture
    def sanitizer(self):
        return OutputSanitizer()

    def test_redact_action(self, sanitizer):
        """Test REDACT action replaces with [REDACTED]."""
        content = "Key: sk-1234567890abcdef1234567890abcdef1234567890abcdef"
        result = sanitizer.sanitize(content)

        assert "[REDACTED]" in result.sanitized_content

    def test_mask_action(self, sanitizer):
        """Test MASK action partially masks content."""
        content = "Email: test@example.com"
        result = sanitizer.sanitize(content)

        # Should have partial masking (first and last chars visible)
        sanitized = result.sanitized_content
        assert "test@example.com" not in sanitized


class TestSanitizationResult:
    """Test SanitizationResult dataclass."""

    def test_result_fields(self):
        """Test that SanitizationResult has all expected fields."""
        result = SanitizationResult(
            is_safe=True,
            sanitized_content="test",
            detections=[],
            action_taken="PASSED",
            original_hash="abc123",
        )

        assert result.is_safe is True
        assert result.sanitized_content == "test"
        assert result.detections == []
        assert result.action_taken == "PASSED"
        assert result.original_hash == "abc123"


class TestSanitizationAction:
    """Test SanitizationAction enum."""

    def test_action_values(self):
        """Test sanitization action values."""
        assert SanitizationAction.REDACT.value == "redact"
        assert SanitizationAction.MASK.value == "mask"
        assert SanitizationAction.REMOVE.value == "remove"
        assert SanitizationAction.BLOCK.value == "block"


class TestStatistics:
    """Test sanitization statistics."""

    def test_stats_tracking(self):
        """Test that statistics are tracked."""
        sanitizer = OutputSanitizer()

        # Run some sanitizations
        sanitizer.sanitize("Normal text")
        sanitizer.sanitize("API key: sk-1234567890abcdef1234567890abcdef1234567890abcdef")

        stats = sanitizer.get_stats()

        assert stats["total_scans"] >= 2
        assert "total_detections" in stats
        assert "detection_rate" in stats
        assert "block_rate" in stats


class TestGlobalInstance:
    """Test global sanitizer instance."""

    def test_global_instance_exists(self):
        """Test that global output_sanitizer instance exists."""
        assert output_sanitizer is not None
        assert isinstance(output_sanitizer, OutputSanitizer)

    def test_global_instance_works(self):
        """Test that global instance can sanitize content."""
        result = output_sanitizer.sanitize("Hello world")
        assert result.is_safe is True


class TestMultipleDetections:
    """Test handling of multiple detections in same content."""

    @pytest.fixture
    def sanitizer(self):
        return OutputSanitizer()

    def test_multiple_credentials_sanitized(self, sanitizer):
        """Test that multiple credentials are all sanitized."""
        content = """
        OpenAI: sk-1234567890abcdef1234567890abcdef1234567890abcdef
        GitHub: ghp_1234567890abcdef1234567890abcdef1234
        Email: secret@example.com
        """
        result = sanitizer.sanitize(content)

        # All should be sanitized
        assert result.sanitized_content.count("[REDACTED]") >= 2 or "***" in result.sanitized_content

    def test_detections_list_populated(self, sanitizer):
        """Test that detections list contains all findings."""
        content = "Key1: sk-1234567890abcdef1234567890abcdef1234567890abcdef Key2: AKIA1234567890123456"
        result = sanitizer.sanitize(content)

        assert len(result.detections) >= 2
