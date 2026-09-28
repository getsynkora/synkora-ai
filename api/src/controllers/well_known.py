"""Well-known URIs — RFC 8615 / RFC 9116."""

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter(tags=["well-known"])

SECURITY_TXT = """Contact: mailto:security@synkora.ai
Expires: 2027-09-28T00:00:00.000Z
Preferred-Languages: en
Policy: https://synkora.ai/security-policy
Acknowledgments: https://synkora.ai/security/hall-of-fame
Canonical: https://synkora.ai/.well-known/security.txt
"""


@router.get("/.well-known/security.txt", include_in_schema=False)
async def security_txt() -> PlainTextResponse:
    return PlainTextResponse(SECURITY_TXT, media_type="text/plain; charset=utf-8")


@router.get("/.well-known/jwks.json", include_in_schema=False)
async def jwks() -> dict:
    """JSON Web Key Set for JWT public key discovery.

    Returns the public key(s) used to verify JWTs issued by this server.
    For HS256/HS384/HS512 (symmetric), returns an empty key set — there is
    no public key to expose.  For RS256/RS384/RS512/ES256 (asymmetric),
    returns the RSA or EC public key in JWK format so that external services
    can verify tokens without sharing the private key.
    """
    from src.config import settings
    from src.services.security.jwt_keys import get_jwks

    return get_jwks(settings)
