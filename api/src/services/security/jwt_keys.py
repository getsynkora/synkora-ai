"""RSA/EC key management for asymmetric JWT signing."""
from __future__ import annotations

import base64
import logging

logger = logging.getLogger(__name__)


def _normalize_pem(pem: str) -> str:
    """Replace literal \\n with real newlines (common in env var injection)."""
    return pem.replace("\\n", "\n").strip()


def load_private_key(pem: str):
    """Load RSA/EC private key from PEM string."""
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    pem = _normalize_pem(pem)
    return load_pem_private_key(pem.encode(), password=None, backend=default_backend())


def load_public_key(pem: str):
    """Load RSA/EC public key from PEM string."""
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.serialization import load_pem_public_key

    pem = _normalize_pem(pem)
    return load_pem_public_key(pem.encode(), backend=default_backend())


def get_signing_key(settings):
    """Return the key to use for signing (private key for asymmetric, secret string for HS*)."""
    if settings.is_asymmetric_jwt:
        if not settings.jwt_private_key:
            raise ValueError("JWT_PRIVATE_KEY must be set when using RS256/RS384/RS512/ES256")
        return load_private_key(settings.jwt_private_key)
    return settings.jwt_secret_key


def get_verification_key(settings):
    """Return the key to use for verification (public key for asymmetric, secret string for HS*)."""
    if settings.is_asymmetric_jwt:
        if settings.jwt_public_key:
            return load_public_key(settings.jwt_public_key)
        # Derive public key from private key when jwt_public_key is not set
        private = load_private_key(settings.jwt_private_key)
        return private.public_key()
    return settings.jwt_secret_key


def get_jwks(settings) -> dict:
    """Return JWKS (JSON Web Key Set) for the current public key.

    Only call this when settings.is_asymmetric_jwt is True.
    Returns {"keys": []} for HS* algorithms (no public key to expose).
    """
    if not settings.is_asymmetric_jwt:
        return {"keys": []}

    from cryptography.hazmat.primitives.asymmetric import ec as _ec
    from cryptography.hazmat.primitives.asymmetric import rsa as _rsa

    pub_key = get_verification_key(settings)

    def _b64url(n: int) -> str:
        """Encode a big integer as URL-safe base64 without padding."""
        byte_length = (n.bit_length() + 7) // 8
        b = n.to_bytes(byte_length, "big")
        return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

    if isinstance(pub_key, _rsa.RSAPublicKey):
        nums = pub_key.public_numbers()
        return {
            "keys": [
                {
                    "kty": "RSA",
                    "use": "sig",
                    "alg": settings.jwt_algorithm,
                    "n": _b64url(nums.n),
                    "e": _b64url(nums.e),
                    "kid": "default",
                }
            ]
        }

    if isinstance(pub_key, _ec.EllipticCurvePublicKey):
        nums = pub_key.public_numbers()
        curve = pub_key.curve
        # Determine key size (bytes) and JWK curve name from the curve instance
        curve_name = type(curve).__name__  # e.g. "SECP256R1"
        crv_map = {
            "SECP256R1": ("P-256", 32),
            "SECP384R1": ("P-384", 48),
            "SECP521R1": ("P-521", 66),
        }
        crv, coord_size = crv_map.get(curve_name, ("P-256", 32))

        def _b64url_fixed(n: int, size: int) -> str:
            b = n.to_bytes(size, "big")
            return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

        return {
            "keys": [
                {
                    "kty": "EC",
                    "use": "sig",
                    "alg": settings.jwt_algorithm,
                    "crv": crv,
                    "x": _b64url_fixed(nums.x, coord_size),
                    "y": _b64url_fixed(nums.y, coord_size),
                    "kid": "default",
                }
            ]
        }

    raise ValueError(f"Unsupported key type for JWKS export: {type(pub_key)}")
