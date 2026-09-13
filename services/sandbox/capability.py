"""Short-lived, workspace-bound sandbox capabilities (stdlib only).

Keep service and API copies identical; regression tests verify interoperability.
"""

import base64
import hashlib
import hmac
import json
import time


def issue_capability(secret: str, tenant: str, workspace: str) -> str:
    if not secret or len(secret) < 32:
        raise ValueError("A strong sandbox signing key is required")
    payload = (
        base64.urlsafe_b64encode(
            json.dumps(
                {
                    "aud": "sandbox-workspace",
                    "tenant": str(tenant),
                    "workspace": str(workspace),
                    "exp": int(time.time()) + 60,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        )
        .decode()
        .rstrip("=")
    )
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return payload + "." + signature


def verify_capability(token: str, secret: str, tenant: str, workspace: str) -> bool:
    try:
        if not secret or len(secret) < 32 or not token or len(token) > 2048:
            return False
        payload, signature = token.split(".")
        expected = hmac.new(
            secret.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return False
        claims = json.loads(
            base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
        )
        now = int(time.time())
        return (
            isinstance(claims, dict)
            and claims.get("aud") == "sandbox-workspace"
            and claims.get("tenant") == str(tenant)
            and claims.get("workspace") == str(workspace)
            and type(claims.get("exp")) is int
            and now < claims["exp"] <= now + 60
        )
    except (ValueError, TypeError, UnicodeError):
        return False
