"""Regression guard for a platform-wide bug found across every OAuth provider callback
in src/controllers/oauth/ AND in src/services/agents/credential_resolver.py:
UserOAuthToken.access_token/.refresh_token are auto-encrypting properties (see
src/models/user_oauth_token.py), but:

1. Every single provider callback was calling encrypt_value() before assigning to them —
   double-encrypting the token at save time, so it never decrypted back to something
   GitLab/Jira/Zoom/etc. would accept.
2. Several credential_resolver.py read/refresh paths were calling decrypt_value() a
   second time on top of the property's own decryption — which happened to cancel bug
   #1 out by accident for existing rows, and would independently break correctly-saved
   (single-encrypted) rows going forward.

Every personal ("user-level") OAuth connection across the whole platform was silently
broken by #1; the fix for #1 alone would have broken every one of those *existing* rows
via #2, since #2 was accidentally compensating for #1. Both are now fixed: writes assign
plaintext directly (the property encrypts), and reads go through
CredentialResolver._resolve_user_token_value(), which transparently decrypts once more
only if the value still looks encrypted — self-healing legacy double-encrypted rows
without a data migration, while leaving correctly-saved rows untouched.

These tests statically scan the source for both anti-patterns. A DB/mock-based test can't
catch this class of bug — double-encrypting still "looks like" a valid Fernet token to a
mock, it only fails against a real UserOAuthToken property or a real provider API call —
so this is deliberately a source-level guard instead.
"""

import re
from pathlib import Path

OAUTH_CONTROLLERS_DIR = Path(__file__).parents[4] / "src" / "controllers" / "oauth"
CREDENTIAL_RESOLVER_FILE = Path(__file__).parents[4] / "src" / "services" / "agents" / "credential_resolver.py"

# Matches `<name>.access_token = encrypt_value(...)` or `<name>.refresh_token = encrypt_value(...)`
# for any receiver name other than oauth_app (OAuthApp's plain columns).
_ASSIGNMENT_PATTERN = re.compile(r"^\s*(?!oauth_app\.)(\w+)\.(access_token|refresh_token)\s*=\s*encrypt_value\(")

# Matches `access_token=encrypt_value(...)` / `refresh_token=encrypt_value(...)` as a
# constructor kwarg (used when building a new UserOAuthToken(...)).
_KWARG_PATTERN = re.compile(r"^\s*(access_token|refresh_token)\s*=\s*encrypt_value\(")


def _iter_oauth_controller_files():
    assert OAUTH_CONTROLLERS_DIR.is_dir(), f"expected oauth controllers dir at {OAUTH_CONTROLLERS_DIR}"
    return sorted(OAUTH_CONTROLLERS_DIR.glob("*.py"))


def test_no_oauth_controller_double_encrypts_user_oauth_token():
    violations = []
    for path in _iter_oauth_controller_files():
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            if _ASSIGNMENT_PATTERN.match(line) or _KWARG_PATTERN.match(line):
                violations.append(f"{path.name}:{lineno}: {line.strip()}")

    assert not violations, (
        "Found encrypt_value() applied to a UserOAuthToken field — this double-encrypts "
        "the token (the model's access_token/refresh_token are auto-encrypting properties) "
        "and produces a token no provider will ever accept:\n" + "\n".join(violations)
    )


def test_oauth_controllers_still_encrypt_app_level_tokens():
    """Sanity check that the guard above isn't just matching nothing — OAuthApp's plain
    Text columns must still go through encrypt_value() explicitly."""
    found_any = False
    for path in _iter_oauth_controller_files():
        text = path.read_text()
        if re.search(r"oauth_app\.access_token\s*=\s*encrypt_value\(", text):
            found_any = True
            break

    assert found_any, "expected at least one oauth controller to still encrypt oauth_app.access_token"


def test_credential_resolver_does_not_double_encrypt_user_oauth_token():
    assert CREDENTIAL_RESOLVER_FILE.is_file(), f"expected credential_resolver.py at {CREDENTIAL_RESOLVER_FILE}"
    violations = []
    for lineno, line in enumerate(CREDENTIAL_RESOLVER_FILE.read_text().splitlines(), start=1):
        if re.match(r"^\s*user_token_record\.(access_token|refresh_token)\s*=\s*encrypt_value\(", line):
            violations.append(f"{lineno}: {line.strip()}")

    assert not violations, (
        "Found encrypt_value() applied to user_token_record.access_token/.refresh_token in "
        "credential_resolver.py — this double-encrypts the token (the property already "
        "encrypts on assignment). Assign the plaintext value directly instead:\n" + "\n".join(violations)
    )


def test_credential_resolver_reads_user_oauth_token_through_resolver_helper():
    """Reading user_token_record.access_token/.refresh_token must go through
    CredentialResolver._resolve_user_token_value(), not a raw decrypt_value() call —
    that helper is what makes both legacy double-encrypted rows and correctly-saved
    single-encrypted rows resolve to the right plaintext."""
    assert CREDENTIAL_RESOLVER_FILE.is_file(), f"expected credential_resolver.py at {CREDENTIAL_RESOLVER_FILE}"
    violations = []
    for lineno, line in enumerate(CREDENTIAL_RESOLVER_FILE.read_text().splitlines(), start=1):
        if re.search(r"decrypt_value\(user_token_record\.(access_token|refresh_token)\)", line):
            violations.append(f"{lineno}: {line.strip()}")

    assert not violations, (
        "Found a raw decrypt_value() call on a UserOAuthToken field — use "
        "CredentialResolver._resolve_user_token_value() instead:\n" + "\n".join(violations)
    )
