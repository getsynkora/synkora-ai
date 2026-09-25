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


def _fingerprint(value: str | None) -> str | None:
    """Short, one-way fingerprint of a secret value for log comparison.

    Lets two log entries -- or a log entry and a locally-recomputed expected value --
    be confirmed equal or different (any difference anywhere in the value changes the
    fingerprint) without ever putting usable proof material in log storage. A prefix/
    suffix mask would hide a single differing character in the middle; this doesn't.
    """
    if not value:
        return None
    return hashlib.sha256(value.encode()).hexdigest()[:12]


# Max allowed lifetime for a widget identity_token, in seconds. Was 300 (5 min) since
# the original security hardening (PR #196, 2026-09-12). Widened to 7 days at explicit
# request (2026-09-25) to avoid requiring a background refresh cycle on mobile clients.
# TRADEOFF (platform-wide, applies to every widget's identity_token, not just one
# caller): a leaked identity_token now stays usable for up to 7 days instead of 5
# minutes -- e.g. via device logs, crash reporters, or a compromised device. Unlike a
# leaked user_hash (which stays valid until the widget's secret is rotated, with no
# expiry at all), this is still bounded, and was chosen over no-expiry for exactly
# that reason.
IDENTITY_TOKEN_MAX_LIFETIME_SECONDS = 7 * 24 * 60 * 60  # 7 days


def verify_user(widget, user_id, user_hash=None, org_id=None, identity_token=None):
    # Shape-only log (safe to leave in permanently): tells "no proof sent" apart from
    # "wrong proof sent" without putting proof material in log storage.
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
    # Permanent diagnostic log: fingerprints (not raw values) of user_hash/identity_token,
    # safe to keep indefinitely -- a fingerprint can confirm "this matches/doesn't match an
    # expected value" but can never itself be replayed as proof. See _fingerprint() above.
    logger.warning(
        "widget identity payload: widget_id=%s user_id=%s user_hash_fp=%s identity_token_fp=%s org_id=%r",
        widget.id,
        user_id,
        _fingerprint(user_hash),
        _fingerprint(identity_token),
        org_id,
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
            if claims["sub"] != user_id or claims["exp"] - claims["iat"] > IDENTITY_TOKEN_MAX_LIFETIME_SECONDS:
                raise ValueError("Invalid identity scope")
            if org_id is not None and claims.get("organization_id") != org_id:
                raise ValueError("Organization mismatch")
            return claims
        except (jwt.InvalidTokenError, ValueError, TypeError) as e:
            logger.warning(
                "widget identity rejected: widget_id=%s reason=invalid_identity_token detail=%s", widget.id, e
            )
            raise HTTPException(403, "Invalid widget identity assertion") from None
    # Legacy HMAC authenticates only a user ID. It cannot authorize an organization.
    # This is unconditional — identity_verification_required only controls whether the
    # anonymous-session fallback is available (see conversation_scope below), never
    # whether an identified user_id needs proof. Relaxing that would let any caller
    # claim any user_id and read/pollute that user's conversation history unverified.
    if not user_id or not user_hash or org_id is not None:
        logger.warning(
            "widget identity rejected: widget_id=%s reason=%s",
            widget.id,
            "missing_user_id" if not user_id else "missing_user_hash" if not user_hash else "org_id_needs_token",
        )
        raise HTTPException(403, "Verified widget identity is required; organization access requires an identity token")
    expected = hmac.new(_key(widget).encode(), user_id.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, user_hash):
        logger.warning("widget identity rejected: widget_id=%s user_id=%s reason=hash_mismatch", widget.id, user_id)
        raise HTTPException(403, "Invalid widget identity proof")
    return {"sub": user_id, "organization_id": None}


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
