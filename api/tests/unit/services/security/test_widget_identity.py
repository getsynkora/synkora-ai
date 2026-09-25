import hashlib
import hmac
import time
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select, text
from starlette.requests import Request

from src.models.conversation import Conversation
from src.services.security import widget_identity as identity

SECRET = "synthetic-test-key-longer-than-thirty-two-bytes"


@pytest.fixture
def widget(monkeypatch):
    monkeypatch.setattr(identity, "decrypt_value", lambda value: SECRET)
    return SimpleNamespace(id=uuid4(), identity_secret="encrypted", identity_verification_required=False)


def proof(user):
    return hmac.new(SECRET.encode(), user.encode(), hashlib.sha256).hexdigest()


def test_unverified_user_and_forged_organization_rejected_even_when_optional(widget):
    for args in [("victim", None, None), ("victim", proof("attacker"), None), ("victim", proof("victim"), "other-org")]:
        with pytest.raises(HTTPException) as error:
            identity.verify_user(widget, *args)
        assert error.value.status_code == 403
    assert identity.verify_user(widget, "victim", proof("victim"))["organization_id"] is None


def assertion(widget, **changes):
    claims = {
        "sub": "user",
        "organization_id": "org",
        "aud": f"synkora-widget:{widget.id}",
        "iat": int(time.time()),
        "exp": int(time.time()) + 60,
    }
    claims.update(changes)
    return jwt.encode(claims, SECRET, algorithm="HS256")


def test_identity_token_with_multi_day_lifetime_is_accepted(widget):
    """IDENTITY_TOKEN_MAX_LIFETIME_SECONDS was widened from 5 minutes to 7 days
    (2026-09-25) to avoid requiring mobile clients to run a background refresh cycle.
    A 3-day-lifetime token must be accepted -- it would have been rejected under the
    old 300-second limit."""
    token = assertion(widget, exp=int(time.time()) + 3 * 24 * 60 * 60)
    assert identity.verify_user(widget, "user", org_id="org", identity_token=token)["organization_id"] == "org"


def test_signed_organization_identity_is_scoped_and_expires(widget):
    token = assertion(widget)
    assert identity.verify_user(widget, "user", org_id="org", identity_token=token)["organization_id"] == "org"
    for user, org, value in [
        ("other", "org", token),
        ("user", "other", token),
        ("user", "org", assertion(widget, exp=1)),
        ("user", "org", assertion(widget, aud="other-widget")),
        # exceeds IDENTITY_TOKEN_MAX_LIFETIME_SECONDS (7 days) -- must still be rejected
        ("user", "org", assertion(widget, exp=int(time.time()) + 8 * 24 * 60 * 60)),
    ]:
        with pytest.raises(HTTPException):
            identity.verify_user(widget, user, org_id=org, identity_token=value)


def test_anonymous_capability_cannot_cross_widget_or_impersonate_identified_user(widget):
    session, token = identity.new_anonymous_session(widget)
    assert identity.verify_anonymous_session(widget, token) == session
    other = SimpleNamespace(**{**vars(widget), "id": uuid4()})
    with pytest.raises(HTTPException):
        identity.verify_anonymous_session(other, token)
    for bad in [None, token + "x", assertion(widget)]:
        with pytest.raises(HTTPException):
            identity.verify_anonymous_session(widget, bad)


def test_history_predicates_exclude_other_principals_using_real_sql(widget):
    session, token = identity.new_anonymous_session(widget)
    engine = create_engine("sqlite://")
    with engine.begin() as db:
        db.execute(
            text(
                "CREATE TABLE conversations (id TEXT, session_id TEXT, external_user_id TEXT, external_org_id TEXT, account_id TEXT)"
            )
        )
        for index, values in enumerate(
            [
                (session, None, None, None),
                ("other", None, None, None),
                (session, "user", "org", None),
                (session, None, None, uuid4().hex),
            ]
        ):
            db.execute(
                text("INSERT INTO conversations VALUES (:id,:session,:user,:org,:account)"),
                {"id": str(index), "session": values[0], "user": values[1], "org": values[2], "account": values[3]},
            )
        req = Request({"type": "http", "headers": [(b"x-widget-session-token", token.encode())]})
        query = select(Conversation.session_id).where(*identity.conversation_scope(widget, req, Conversation))
        assert db.execute(query).all() == [(session,)]
        req = Request(
            {
                "type": "http",
                "headers": [(b"x-widget-user-id", b"user"), (b"x-widget-identity-token", assertion(widget).encode())],
            }
        )
        query = select(Conversation.external_user_id).where(*identity.conversation_scope(widget, req, Conversation))
        assert db.execute(query).all() == [("user",)]
    engine.dispose()
