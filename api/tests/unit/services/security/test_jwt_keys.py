"""Unit tests for src.services.security.jwt_keys."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives.asymmetric import ec, rsa

from src.services.security.jwt_keys import (
    get_jwks,
    get_signing_key,
    get_verification_key,
    load_private_key,
    load_public_key,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_settings(algorithm: str, private_key_pem: str = "", public_key_pem: str = "") -> SimpleNamespace:
    """Build a minimal settings-like object for testing."""
    return SimpleNamespace(
        jwt_algorithm=algorithm,
        jwt_secret_key="test-secret-key-for-hs256-testing-only",
        jwt_private_key=private_key_pem,
        jwt_public_key=public_key_pem,
        is_asymmetric_jwt=not algorithm.startswith("HS"),
    )


def _generate_rsa_pem_pair() -> tuple[str, str]:
    """Generate a fresh 2048-bit RSA key pair and return (private_pem, public_pem)."""
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import serialization

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


def _generate_ec_pem_pair() -> tuple[str, str]:
    """Generate a fresh P-256 EC key pair and return (private_pem, public_pem)."""
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import serialization

    private_key = ec.generate_private_key(ec.SECP256R1(), backend=default_backend())
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


# ---------------------------------------------------------------------------
# HS256 — symmetric (keep existing behaviour, return the secret string)
# ---------------------------------------------------------------------------


class TestHS256:
    def test_get_signing_key_returns_secret_string(self):
        settings = _make_settings("HS256")
        key = get_signing_key(settings)
        assert key == settings.jwt_secret_key
        assert isinstance(key, str)

    def test_get_verification_key_returns_secret_string(self):
        settings = _make_settings("HS256")
        key = get_verification_key(settings)
        assert key == settings.jwt_secret_key
        assert isinstance(key, str)

    def test_get_jwks_returns_empty_keys(self):
        settings = _make_settings("HS256")
        result = get_jwks(settings)
        assert result == {"keys": []}

    def test_get_signing_key_hs384(self):
        settings = _make_settings("HS384")
        key = get_signing_key(settings)
        assert isinstance(key, str)

    def test_get_signing_key_hs512(self):
        settings = _make_settings("HS512")
        key = get_signing_key(settings)
        assert isinstance(key, str)


# ---------------------------------------------------------------------------
# RS256 — asymmetric RSA
# ---------------------------------------------------------------------------


class TestRS256:
    @pytest.fixture(scope="class")
    def rsa_pem_pair(self):
        return _generate_rsa_pem_pair()

    def test_get_signing_key_returns_rsa_private_key(self, rsa_pem_pair):
        private_pem, _ = rsa_pem_pair
        settings = _make_settings("RS256", private_key_pem=private_pem)
        key = get_signing_key(settings)
        assert isinstance(key, rsa.RSAPrivateKey)

    def test_get_verification_key_derives_public_from_private(self, rsa_pem_pair):
        private_pem, _ = rsa_pem_pair
        settings = _make_settings("RS256", private_key_pem=private_pem)
        key = get_verification_key(settings)
        assert isinstance(key, rsa.RSAPublicKey)

    def test_get_verification_key_uses_explicit_public_key(self, rsa_pem_pair):
        private_pem, public_pem = rsa_pem_pair
        settings = _make_settings("RS256", private_key_pem=private_pem, public_key_pem=public_pem)
        key = get_verification_key(settings)
        assert isinstance(key, rsa.RSAPublicKey)

    def test_get_signing_key_raises_without_private_key(self):
        settings = _make_settings("RS256", private_key_pem="")
        with pytest.raises(ValueError, match="JWT_PRIVATE_KEY must be set"):
            get_signing_key(settings)

    def test_get_jwks_returns_rsa_key(self, rsa_pem_pair):
        private_pem, _ = rsa_pem_pair
        settings = _make_settings("RS256", private_key_pem=private_pem)
        result = get_jwks(settings)
        assert "keys" in result
        assert len(result["keys"]) == 1
        jwk = result["keys"][0]
        assert jwk["kty"] == "RSA"
        assert jwk["use"] == "sig"
        assert jwk["alg"] == "RS256"
        assert jwk["kid"] == "default"
        # n and e must be non-empty base64url strings
        assert jwk["n"] and isinstance(jwk["n"], str)
        assert jwk["e"] and isinstance(jwk["e"], str)

    def test_jwks_n_and_e_are_valid_base64url(self, rsa_pem_pair):
        """JWKS n/e must be URL-safe base64 without padding characters."""
        import base64

        private_pem, _ = rsa_pem_pair
        settings = _make_settings("RS256", private_key_pem=private_pem)
        result = get_jwks(settings)
        jwk = result["keys"][0]
        # Should decode without error when padding is restored
        for field_name in ("n", "e"):
            val = jwk[field_name]
            padded = val + "=" * (-len(val) % 4)
            decoded = base64.urlsafe_b64decode(padded)
            assert len(decoded) > 0

    def test_literal_newline_normalization(self, rsa_pem_pair):
        """A PEM with literal \\n (backslash-n) must be accepted after normalization."""
        private_pem, _ = rsa_pem_pair
        # Replace real newlines with the literal two-character sequence \\n
        escaped_pem = private_pem.replace("\n", "\\n")
        key = load_private_key(escaped_pem)
        assert isinstance(key, rsa.RSAPrivateKey)

    def test_round_trip_sign_verify_rs256(self, rsa_pem_pair):
        """A token signed with the private key must verify with the public key."""
        import jwt as pyjwt

        private_pem, public_pem = rsa_pem_pair
        priv_key = load_private_key(private_pem)
        pub_key = load_public_key(public_pem)

        token = pyjwt.encode({"sub": "test", "iss": "test"}, priv_key, algorithm="RS256")
        payload = pyjwt.decode(token, pub_key, algorithms=["RS256"], options={"verify_aud": False})
        assert payload["sub"] == "test"


# ---------------------------------------------------------------------------
# ES256 — asymmetric EC
# ---------------------------------------------------------------------------


class TestES256:
    @pytest.fixture(scope="class")
    def ec_pem_pair(self):
        return _generate_ec_pem_pair()

    def test_get_signing_key_returns_ec_private_key(self, ec_pem_pair):
        private_pem, _ = ec_pem_pair
        settings = _make_settings("ES256", private_key_pem=private_pem)
        key = get_signing_key(settings)
        assert isinstance(key, ec.EllipticCurvePrivateKey)

    def test_get_verification_key_derives_public_from_private(self, ec_pem_pair):
        private_pem, _ = ec_pem_pair
        settings = _make_settings("ES256", private_key_pem=private_pem)
        key = get_verification_key(settings)
        assert isinstance(key, ec.EllipticCurvePublicKey)

    def test_get_jwks_returns_ec_key(self, ec_pem_pair):
        private_pem, _ = ec_pem_pair
        settings = _make_settings("ES256", private_key_pem=private_pem)
        result = get_jwks(settings)
        assert "keys" in result
        assert len(result["keys"]) == 1
        jwk = result["keys"][0]
        assert jwk["kty"] == "EC"
        assert jwk["use"] == "sig"
        assert jwk["alg"] == "ES256"
        assert jwk["crv"] == "P-256"
        assert jwk["kid"] == "default"
        assert jwk["x"] and isinstance(jwk["x"], str)
        assert jwk["y"] and isinstance(jwk["y"], str)

    def test_round_trip_sign_verify_es256(self, ec_pem_pair):
        """A token signed with the EC private key must verify with the EC public key."""
        import jwt as pyjwt

        private_pem, public_pem = ec_pem_pair
        priv_key = load_private_key(private_pem)
        pub_key = load_public_key(public_pem)

        token = pyjwt.encode({"sub": "test", "iss": "test"}, priv_key, algorithm="ES256")
        payload = pyjwt.decode(token, pub_key, algorithms=["ES256"], options={"verify_aud": False})
        assert payload["sub"] == "test"
