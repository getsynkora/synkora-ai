"""Unit tests for Langfuse trace PII redactor."""

from __future__ import annotations

import pytest

from src.services.observability.trace_redactor import redact, redact_messages


class TestRedact:
    def test_aws_key_is_redacted(self):
        text = "Access key: AKIAIOSFODNN7EXAMPLE and more text"
        result = redact(text)
        assert "[AWS_KEY]" in result
        assert "AKIAIOSFODNN7EXAMPLE" not in result

    def test_asia_aws_key_is_redacted(self):
        # ASIA prefix + exactly 16 uppercase alphanumeric chars followed by space
        # IOSFODNN7EXAMPLES = 16 chars (I-O-S-F-O-D-N-N-7-E-X-A-M-P-L-E-S)
        text = "Temporary key ASIAIOSFODNN7EXAMPL3 used here"
        result = redact(text)
        assert "[AWS_KEY]" in result

    def test_github_token_is_redacted(self):
        token = "ghp_" + "A" * 36
        text = f"token={token}"
        result = redact(text)
        assert "[GITHUB_TOKEN]" in result
        assert token not in result

    def test_github_oauth_token_is_redacted(self):
        token = "gho_" + "B" * 40
        result = redact(f"Authorization: Bearer {token}")
        # Bearer redaction may fire first, but either way the token is gone
        assert token not in result

    def test_generic_sk_api_key_is_redacted(self):
        text = "key=sk-abcdefghijklmnopqrstuvwxyz123456"
        result = redact(text)
        assert "[API_KEY]" in result

    def test_generic_pk_api_key_is_redacted(self):
        text = "pk_live_abcdefghijklmnopqrstuvwxyz"
        result = redact(text)
        assert "[API_KEY]" in result

    def test_bearer_token_is_redacted(self):
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.sig"
        result = redact(text)
        assert "Bearer [REDACTED]" in result
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result

    def test_credit_card_visa_is_redacted(self):
        text = "Card: 4111111111111111 was charged"
        result = redact(text)
        assert "[CARD_NUMBER]" in result
        assert "4111111111111111" not in result

    def test_credit_card_mastercard_is_redacted(self):
        text = "MC: 5500005555555559"
        result = redact(text)
        assert "[CARD_NUMBER]" in result

    def test_ssn_is_redacted(self):
        text = "SSN: 123-45-6789 on file"
        result = redact(text)
        assert "[SSN]" in result
        assert "123-45-6789" not in result

    def test_ssn_space_format_is_redacted(self):
        text = "ssn 123 45 6789"
        result = redact(text)
        assert "[SSN]" in result

    def test_private_key_is_redacted(self):
        key = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA\n-----END RSA PRIVATE KEY-----"
        result = redact(key)
        assert "[PRIVATE_KEY]" in result
        assert "MIIEpAIBAAKCAQEA" not in result

    def test_clean_text_passes_through_unchanged(self):
        text = "The weather today is sunny with a high of 72 degrees."
        result = redact(text)
        assert result == text

    def test_non_string_passes_through_unchanged(self):
        assert redact(None) is None  # type: ignore[arg-type]
        assert redact(42) == 42  # type: ignore[arg-type]

    def test_multiple_patterns_in_same_string(self):
        text = "key=AKIAIOSFODNN7EXAMPLE ssn=123-45-6789"
        result = redact(text)
        assert "[AWS_KEY]" in result
        assert "[SSN]" in result
        assert "AKIAIOSFODNN7EXAMPLE" not in result
        assert "123-45-6789" not in result


class TestRedactMessages:
    def test_redacts_content_in_messages(self):
        messages = [
            {"role": "user", "content": "My SSN is 123-45-6789"},
            {"role": "assistant", "content": "I see your SSN"},
        ]
        result = redact_messages(messages)
        assert "[SSN]" in result[0]["content"]
        assert "123-45-6789" not in result[0]["content"]
        assert result[1]["content"] == "I see your SSN"  # no PII here

    def test_preserves_non_string_content(self):
        messages = [
            {"role": "user", "content": None},
            {"role": "system", "content": [{"type": "text", "text": "complex"}]},
        ]
        result = redact_messages(messages)
        assert result[0]["content"] is None
        assert result[1]["content"] == [{"type": "text", "text": "complex"}]

    def test_preserves_other_message_fields(self):
        messages = [{"role": "user", "content": "hello", "name": "alice"}]
        result = redact_messages(messages)
        assert result[0]["role"] == "user"
        assert result[0]["name"] == "alice"

    def test_empty_list_returns_empty_list(self):
        assert redact_messages([]) == []
