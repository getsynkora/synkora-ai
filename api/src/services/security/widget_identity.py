"""Verified widget principals shared by chat and conversation endpoints."""

import hashlib
import hmac
import logging
import time
import uuid

import jwt
from fastapi import HTTPException

from src.services.agents.security import decrypt_value

logger = logging.getLogger(__name__)


def _key(widget):
    if not widget.identity_secret:
        raise HTTPException(503, "Widget identity verification is unavailable")
    return decrypt_value(widget.identity_secret)


def verify_user(widget, user_id, user_hash=None, org_id=None, identity_token=None):
    # Never logs user_hash/identity_token values themselves (they're proof material,
    # not payload we want sitting in log storage) — only the *shape* of what was sent,
    # which is enough to tell "app sent no proof" apart from "app sent a wrong hash".
    logger.info(
        "widget identity check: widget_id=%s user_id=%s has_user_hash=%s has_identity_token=%s "
        "requested_org_id=%s identity_verification_required=%s",
        widget.id,
        user_id,
        bool(user_hash),
        bool(identity_token),
        org_id,
        getattr(widget, "identity_verification_required", None),
    )
    if identity_token:
        try:
            claims = jwt.decode(
                identity_token,
                _key(widget),
                algorithms=["HS256"],
                audience=f"synkora-widget:{widget.id}",
                options={"require": ["exp", "iat", "sub", "aud"]},
            )
            if claims["sub"] != user_id or claims["exp"] - claims["iat"] > 300:
                raise ValueError("Invalid identity scope")
            if org_id is not None and claims.get("organization_id") != org_id:
                raise ValueError("Organization mismatch")
            return claims
        except (jwt.InvalidTokenError, ValueError, TypeError) as e:
            logger.warning(
                "widget identity rejected: widget_id=%s reason=invalid_identity_token detail=%s", widget.id, e
            )
            raise HTTPException(403, "Invalid widget identity assertion") from None
    # Legacy HMAC authenticates only a user ID — it cannot cryptographically prove
    # organization membership (org_id is not an input to the hash at all).
    if not user_id or not user_hash:
        logger.warning(
            "widget identity rejected: widget_id=%s reason=%s",
            widget.id,
            "missing_user_id" if not user_id else "missing_user_hash",
        )
        raise HTTPException(403, "Verified widget identity is required; organization access requires an identity token")
    expected = hmac.new(_key(widget).encode(), user_id.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, user_hash):
        logger.warning("widget identity rejected: widget_id=%s user_id=%s reason=hash_mismatch", widget.id, user_id)
        raise HTTPException(403, "Invalid widget identity proof")
    if org_id is not None:
        # TODO(security): reinstated 2026-09-24, temporarily, for a demo deadline (requested
        # explicitly, with the tradeoff understood) — org_id is trusted here WITHOUT proof.
        # This reopens the exact hole closed in PR #196 (2026-09-12, "remediate cross-tenant,
        # credential, and MCP isolation findings"): a caller with ANY valid (user_id, user_hash)
        # pair can set org_id to ANY value and have it signed into the downstream MCP JWT
        # (widgets.py's `_mcp_user_token`) as if Synkora verified it — because it flows straight
        # into `organization_id` below unchecked. Any downstream consumer that trusts that JWT's
        # organization_id claim for authorization is exposed to cross-org impersonation for as
        # long as this block exists.
        # Proper fix (already speced): mint a signed identity_token JWT (sub,
        # aud=f"synkora-widget:{widget.id}", organization_id, iat, exp <= 300s) server-side and
        # send that instead of user_hash+org_id — see the `identity_token` branch above, which
        # already verifies this correctly.
        # DO NOT let this sit past the demo. Remove this block and restore the `org_id is not
        # None` rejection in the check above once identity_token minting ships for this caller.
        logger.warning(
            "SECURITY TODO: widget_id=%s user_id=%s accepted UNVERIFIED org_id=%s via legacy HMAC path "
            "(see TODO(security) comment in verify_user) — temporary, must be removed before "
            "relying on this in production beyond the demo",
            widget.id,
            user_id,
            org_id,
        )
    return {"sub": user_id, "organization_id": org_id}


def new_anonymous_session(widget):
    now = int(time.time())
    session_id = uuid.uuid4().hex
    token = jwt.encode(
        {"sub": session_id, "aud": f"synkora-anonymous:{widget.id}", "iat": now, "exp": now + 86400},
        _key(widget),
        algorithm="HS256",
    )
    return session_id, token


def verify_anonymous_session(widget, token):
    if not token:
        raise HTTPException(403, "A verified anonymous session is required")
    try:
        claims = jwt.decode(
            token,
            _key(widget),
            algorithms=["HS256"],
            audience=f"synkora-anonymous:{widget.id}",
            options={"require": ["sub", "aud", "exp", "iat"]},
        )
        return claims["sub"]
    except jwt.InvalidTokenError:
        raise HTTPException(403, "Invalid anonymous session") from None


def conversation_scope(widget, http_request, conversation_model, user_id=None):
    user_id = user_id or http_request.headers.get("X-Widget-User-Id")
    if user_id:
        claims = verify_user(
            widget,
            user_id,
            http_request.headers.get("X-Widget-User-Hash"),
            identity_token=http_request.headers.get("X-Widget-Identity-Token"),
        )
        return [
            conversation_model.external_user_id == claims["sub"],
            conversation_model.external_org_id == claims.get("organization_id"),
        ]
    if widget.identity_verification_required:
        raise HTTPException(403, "Verified widget identity is required")
    session = verify_anonymous_session(widget, http_request.headers.get("X-Widget-Session-Token"))
    return [
        conversation_model.session_id == session,
        conversation_model.external_user_id.is_(None),
        conversation_model.account_id.is_(None),
    ]
