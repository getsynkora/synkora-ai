"""
Unit tests for tenant-level console IP allowlist enforcement.

Tests cover:
- IP in allowlist -> login proceeds (no exception)
- IP NOT in allowlist -> 403 raised
- Null allowlist -> all IPs allowed
- CIDR range matches correctly
- Wildcard '*' allows all
- Invalid client IP -> blocked (returns False)
"""

import pytest

from src.services.agent_api.api_key_service import AgentApiKeyService

# ---------------------------------------------------------------------------
# Pure-logic tests for _ip_matches_allowlist (no DB / HTTP required)
# ---------------------------------------------------------------------------


class TestIpMatchesAllowlist:
    """Tests for AgentApiKeyService._ip_matches_allowlist reused by IP allowlist."""

    def test_exact_ipv4_match(self):
        assert AgentApiKeyService._ip_matches_allowlist("192.0.2.1", ["192.0.2.1"]) is True

    def test_exact_ipv4_no_match(self):
        assert AgentApiKeyService._ip_matches_allowlist("192.0.2.2", ["192.0.2.1"]) is False

    def test_cidr_ipv4_match(self):
        assert AgentApiKeyService._ip_matches_allowlist("10.0.0.5", ["10.0.0.0/8"]) is True

    def test_cidr_ipv4_no_match(self):
        assert AgentApiKeyService._ip_matches_allowlist("172.0.0.1", ["10.0.0.0/8"]) is False

    def test_cidr_ipv4_host_bits_set(self):
        """strict=False means 10.0.0.1/8 is accepted as 10.0.0.0/8."""
        assert AgentApiKeyService._ip_matches_allowlist("10.1.2.3", ["10.0.0.1/8"]) is True

    def test_wildcard_allows_all(self):
        assert AgentApiKeyService._ip_matches_allowlist("1.2.3.4", ["*"]) is True

    def test_wildcard_in_mixed_list(self):
        assert AgentApiKeyService._ip_matches_allowlist("8.8.8.8", ["192.168.1.0/24", "*"]) is True

    def test_multiple_entries_first_matches(self):
        assert AgentApiKeyService._ip_matches_allowlist("10.0.0.1", ["10.0.0.0/24", "192.168.1.0/24"]) is True

    def test_multiple_entries_second_matches(self):
        assert AgentApiKeyService._ip_matches_allowlist("192.168.1.5", ["10.0.0.0/24", "192.168.1.0/24"]) is True

    def test_multiple_entries_none_match(self):
        assert AgentApiKeyService._ip_matches_allowlist("8.8.8.8", ["10.0.0.0/24", "192.168.1.0/24"]) is False

    def test_invalid_client_ip_returns_false(self):
        assert AgentApiKeyService._ip_matches_allowlist("not-an-ip", ["10.0.0.0/8"]) is False

    def test_invalid_allowlist_entry_skipped(self):
        """Invalid entries are skipped; valid entries still evaluated."""
        assert AgentApiKeyService._ip_matches_allowlist("10.0.0.1", ["not-valid", "10.0.0.0/8"]) is True

    def test_ipv6_exact_match(self):
        assert AgentApiKeyService._ip_matches_allowlist("::1", ["::1"]) is True

    def test_ipv6_cidr_match(self):
        assert AgentApiKeyService._ip_matches_allowlist("2001:db8::1", ["2001:db8::/32"]) is True

    def test_ipv6_cidr_no_match(self):
        assert AgentApiKeyService._ip_matches_allowlist("2001:db9::1", ["2001:db8::/32"]) is False


# ---------------------------------------------------------------------------
# Login enforcement logic tests (pure Python, no HTTP layer needed)
# ---------------------------------------------------------------------------


class TestConsolIpAllowlistEnforcementLogic:
    """
    Simulate the enforcement logic from the login endpoint.

    The actual login function does:
        if tenant and tenant.console_ip_allowlist:
            if not AgentApiKeyService._ip_matches_allowlist(client_ip, allowlist):
                raise HTTPException(403, ...)

    We test the branch logic directly here so tests don't need a full
    FastAPI test client / DB / Redis setup.
    """

    def _should_block(self, client_ip: str, console_ip_allowlist) -> bool:
        """
        Returns True if the login should be blocked.

        Mirrors the check in controllers/console/auth.py.
        """
        if console_ip_allowlist:  # None or [] -> allow all
            return not AgentApiKeyService._ip_matches_allowlist(client_ip, console_ip_allowlist)
        return False

    def test_null_allowlist_allows_all_ips(self):
        assert self._should_block("1.2.3.4", None) is False

    def test_empty_allowlist_allows_all_ips(self):
        # empty list is falsy — treated same as null
        assert self._should_block("1.2.3.4", []) is False

    def test_ip_in_allowlist_is_not_blocked(self):
        assert self._should_block("203.0.113.5", ["203.0.113.5"]) is False

    def test_ip_not_in_allowlist_is_blocked(self):
        assert self._should_block("8.8.8.8", ["203.0.113.5"]) is True

    def test_cidr_match_is_not_blocked(self):
        assert self._should_block("10.10.10.10", ["10.0.0.0/8"]) is False

    def test_cidr_no_match_is_blocked(self):
        assert self._should_block("172.0.0.1", ["10.0.0.0/8"]) is True

    def test_wildcard_entry_is_not_blocked(self):
        assert self._should_block("8.8.8.8", ["*"]) is False

    def test_mixed_list_match(self):
        assert self._should_block("192.168.1.50", ["10.0.0.0/8", "192.168.1.0/24"]) is False

    def test_mixed_list_no_match(self):
        assert self._should_block("8.8.8.8", ["10.0.0.0/8", "192.168.1.0/24"]) is True

    def test_invalid_client_ip_is_blocked(self):
        """An unparseable client IP should not be allowed through a restricted list."""
        assert self._should_block("not-an-ip", ["10.0.0.0/8"]) is True


# ---------------------------------------------------------------------------
# TenantSecuritySettings validator tests
# ---------------------------------------------------------------------------


class TestTenantSecuritySettingsValidator:
    """Validate the Pydantic model for the PATCH /tenant/security endpoint."""

    def _make(self, allowlist):
        from src.controllers.console.tenant_security import TenantSecuritySettings

        return TenantSecuritySettings(console_ip_allowlist=allowlist)

    def test_valid_ipv4(self):
        m = self._make(["192.0.2.1"])
        assert m.console_ip_allowlist == ["192.0.2.1"]

    def test_valid_cidr(self):
        m = self._make(["10.0.0.0/8"])
        assert m.console_ip_allowlist == ["10.0.0.0/8"]

    def test_valid_wildcard(self):
        m = self._make(["*"])
        assert m.console_ip_allowlist == ["*"]

    def test_null_passthrough(self):
        m = self._make(None)
        assert m.console_ip_allowlist is None

    def test_empty_list_becomes_none(self):
        m = self._make([])
        assert m.console_ip_allowlist is None

    def test_invalid_entry_raises(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            self._make(["not-an-ip"])

    def test_mixed_valid_entries(self):
        m = self._make(["10.0.0.0/8", "192.168.1.1", "*"])
        assert m.console_ip_allowlist == ["10.0.0.0/8", "192.168.1.1", "*"]

    def test_whitespace_stripped(self):
        m = self._make(["  10.0.0.1  "])
        assert m.console_ip_allowlist == ["10.0.0.1"]
