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
    # TODO(security): TEMPORARY full-payload diagnostic logging, added 2026-09-24 at explicit
    # request while root-causing a live widget identity failure. This logs the ACTUAL
    # user_hash/identity_token values -- real proof material. Anyone with log-read access
    # can use a logged user_hash to impersonate that exact user_id on this widget until the
    # identity secret is rotated. REMOVE THIS BLOCK once the live issue is resolved; it must
    # not ship as a standing log line.
    logger.warning(
        "TEMP DIAGNOSTIC widget identity payload: widget_id=%s user_id=%s user_hash=%r identity_token=%r org_id=%r",
        widget.id,
        user_id,
        user_hash,
        identity_token,
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
