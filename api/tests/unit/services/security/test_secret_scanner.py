"""Unit tests for secret_scanner.py."""

import pytest

import src.services.security.secret_scanner as scanner_module
from src.services.security.secret_scanner import ScanMode, ScanResult, scan

# ---------------------------------------------------------------------------
# Detection tests
# ---------------------------------------------------------------------------


def test_github_token_detected():
    content = "My token is ghp_abc123def456ghi789jkl012mno345pqr678"
    result = scan(content)
    assert result.has_findings
    assert "github_token" in result.findings


def test_github_fine_grained_token_detected():
    # 82+ char suffix required
    suffix = "A" * 82
    content = f"github_pat_{suffix}"
    result = scan(content)
    assert result.has_findings
    assert "github_fine_grained" in result.findings


def test_aws_key_detected():
    content = "export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE"
    result = scan(content)
    assert result.has_findings
    assert "aws_access_key" in result.findings


def test_slack_token_detected():
    content = "token = xoxb-abc123def456-ghi789jkl012"
    result = scan(content)
    assert result.has_findings
    assert "slack_token" in result.findings


def test_stripe_key_detected():
    # Built via concatenation so this fixture isn't itself flagged as a live-looking secret.
    content = "sk" + "_test_" + "abcdefghijklmnopqrstuvwx"
    result = scan(content)
    assert result.has_findings
    # stripe_key pattern matches first; generic_api_key may also fire
    assert "stripe_key" in result.findings or "generic_api_key" in result.findings


def test_private_key_header_detected():
    content = "-----BEGIN RSA PRIVATE KEY-----\nMIIEow..."
    result = scan(content)
    assert result.has_findings
    assert "private_key" in result.findings


def test_ssn_detected():
    result = scan("My SSN is 123-45-6789")
    assert result.has_findings
    assert "ssn" in result.findings


def test_ssn_space_format_detected():
    result = scan("SSN: 123 45 6789")
    assert result.has_findings
    assert "ssn" in result.findings


def test_credit_card_detected():
    result = scan("Card: 4111111111111111")
    assert result.has_findings
    assert "credit_card" in result.findings


def test_credit_card_mastercard_detected():
    result = scan("Pay with 5500005555555559")
    assert result.has_findings
    assert "credit_card" in result.findings


def test_password_in_json_detected():
    result = scan('{"username": "alice", "password": "supersecret123"}')
    assert result.has_findings
    assert "password_in_json" in result.findings


def test_connection_string_detected():
    result = scan("postgresql://admin:password123@db.example.com:5432/mydb")
    assert result.has_findings
    assert "connection_string" in result.findings


def test_bearer_token_detected():
    result = scan("Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.signature")
    assert result.has_findings
    assert "bearer_token" in result.findings


# ---------------------------------------------------------------------------
# Clean-content tests
# ---------------------------------------------------------------------------


def test_clean_content_passes():
    result = scan("Hello, can you help me write a Python function?")
    assert not result.has_findings
    assert result.content == "Hello, can you help me write a Python function?"


def test_short_numeric_not_flagged_as_ssn():
    # Must match NNN-NN-NNNN; this doesn't
    result = scan("Order #123 placed on 04/05 for $67.89")
    assert "ssn" not in result.findings


def test_aws_secret_key_skipped_without_key_id():
    # A 40-char base64 string alone should NOT trigger aws_secret_key
    # because no AWS key ID is present
    result = scan("somebase64string1234567890abcdefghijklmn")
    assert "aws_secret_key" not in result.findings


def test_aws_secret_key_flagged_with_key_id():
    # Both key ID and a 40-char base64 secret present
    content = "AKIAIOSFODNN7EXAMPLE wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    result = scan(content)
    assert "aws_access_key" in result.findings
    assert "aws_secret_key" in result.findings


# ---------------------------------------------------------------------------
# None / empty / disabled
# ---------------------------------------------------------------------------


def test_none_content_safe():
    result = scan(None)
    assert not result.has_findings


def test_empty_string_safe():
    result = scan("")
    assert not result.has_findings


def test_scanner_disabled(monkeypatch):
    monkeypatch.setattr(scanner_module, "_ENABLED", False)
    # Even a clear token should not fire when disabled
    result = scanner_module.scan("ghp_abc123def456ghi789jkl012mno345pqr678stu")
    assert not result.has_findings


# ---------------------------------------------------------------------------
# Mode tests
# ---------------------------------------------------------------------------


def test_alert_mode_does_not_redact(monkeypatch):
    monkeypatch.setattr(scanner_module, "_MODE", ScanMode.ALERT)
    content = "My SSN is 123-45-6789"
    result = scanner_module.scan(content)
    assert result.has_findings
    assert result.content == content  # content unchanged in ALERT mode
    assert not result.blocked


def test_redact_mode_replaces_ssn(monkeypatch):
    monkeypatch.setattr(scanner_module, "_MODE", ScanMode.REDACT)
    content = "My SSN is 123-45-6789"
    result = scanner_module.scan(content)
    assert result.has_findings
    assert "123-45-6789" not in result.content
    assert "[SSN]" in result.content
    assert not result.blocked


def test_redact_mode_replaces_github_token(monkeypatch):
    monkeypatch.setattr(scanner_module, "_MODE", ScanMode.REDACT)
    token = "ghp_abc123def456ghi789jkl012mno345pqr678"
    result = scanner_module.scan(f"token: {token}")
    assert result.has_findings
    assert token not in result.content
    assert "[GITHUB_TOKEN]" in result.content


def test_block_mode_sets_blocked_flag(monkeypatch):
    monkeypatch.setattr(scanner_module, "_MODE", ScanMode.BLOCK)
    content = "My SSN is 123-45-6789"
    result = scanner_module.scan(content)
    assert result.has_findings
    assert result.blocked
    # In BLOCK mode, content is returned unchanged
    assert result.content == content


def test_block_mode_clean_content_not_blocked(monkeypatch):
    monkeypatch.setattr(scanner_module, "_MODE", ScanMode.BLOCK)
    result = scanner_module.scan("Hello world, help me with Python!")
    assert not result.has_findings
    assert not result.blocked


# ---------------------------------------------------------------------------
# Fail-open
# ---------------------------------------------------------------------------


def test_scan_fails_open_on_exception(monkeypatch):
    """If an internal exception occurs, scan() returns an empty ScanResult (fail-open)."""

    def _bad_impl(content, agent_id):
        raise RuntimeError("simulated internal error")

    monkeypatch.setattr(scanner_module, "_scan_impl", _bad_impl)
    content = "My SSN is 123-45-6789"
    result = scanner_module.scan(content)
    # Must NOT raise, must return safe result
    assert not result.has_findings
    assert not result.blocked
    assert result.content == content


# ---------------------------------------------------------------------------
# ScanResult dataclass
# ---------------------------------------------------------------------------


def test_scan_result_defaults():
    r = ScanResult(has_findings=False, findings=[], content="hello")
    assert not r.blocked
