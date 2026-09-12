import ast
import hashlib
import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from src.controllers.agents import war_room
from src.schemas.debate import DebateJoinRequest, DebateRespondRequest, public_participants
from src.services.agents.workflows.debate_executor import DebateExecutor


def debate():
    return SimpleNamespace(
        id=uuid.uuid4(),
        topic="Synthetic debate",
        debate_type="structured",
        rounds=3,
        current_round=1,
        status="active",
        is_public=True,
        allow_external=True,
        share_token="public-share",
        participants=[],
        messages=[],
        external_responses={},
        debate_metadata={},
        verdict=None,
        created_at=None,
        completed_at=None,
    )


@pytest.mark.asyncio
async def test_join_credential_is_private_and_required_for_response():
    session = debate()
    db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    joined = await war_room._join_debate_internal(
        session, DebateJoinRequest(agent_name="Participant", auth_token="CALLBACK_SECRET"), db
    )
    token = joined["participant_token"]
    assert session.participants[0]["participant_token_hash"] == hashlib.sha256(token.encode()).hexdigest()
    public = json.dumps(war_room._session_to_schema(session))
    for secret in ("CALLBACK_SECRET", token, "participant_token_hash", "callback_url"):
        assert secret not in public
    assert public_participants(session.participants) == war_room._session_to_schema(session)["participants"]
    for supplied in (None, "wrong"):
        with pytest.raises(HTTPException) as exc:
            await war_room._respond_internal(
                session,
                DebateRespondRequest(
                    participant_id=joined["participant_id"], participant_token=supplied, round=1, content="forged"
                ),
                db,
            )
        assert exc.value.status_code == 403
        assert not session.external_responses
    request = DebateRespondRequest(
        participant_id=joined["participant_id"], participant_token=token, round=1, content="valid"
    )
    assert (await war_room._respond_internal(session, request, db))["status"] == "accepted"
    # Executor replacing its message snapshot must not reopen the submission slot.
    session.messages = []
    with pytest.raises(HTTPException) as exc:
        await war_room._respond_internal(session, request, db)
    assert exc.value.status_code == 409
    db.refresh.assert_awaited_with(session, with_for_update=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("status,round_num", [("completed", 1), ("active", 2), ("pending", 1)])
async def test_response_requires_active_round(status, round_num):
    session = debate()
    session.status = status
    with pytest.raises(HTTPException) as exc:
        await war_room._respond_internal(
            session,
            DebateRespondRequest(participant_id="arbitrary", round=round_num, content="content"),
            SimpleNamespace(refresh=AsyncMock()),
        )
    assert exc.value.status_code == 409


@pytest.mark.parametrize("provider", ["anthropic", "openai", "ollama"])
def test_generated_script_treats_untrusted_fields_as_data(provider):
    payload = '"; INJECTED = True; #\\\n"""'
    script = war_room._generate_agent_script(payload, payload, payload, provider, payload, payload)
    tree = ast.parse(script)
    assignments = {
        target.id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    assert assignments == {"API_BASE": payload, "SHARE_TOKEN": payload, "AGENT_NAME": payload, "MODEL": payload}
    assert 'result["participant_token"]' in script
    assert '"participant_token": participant_token' in script
    with pytest.raises(ValueError):
        war_room._generate_agent_script("", "", "", 'invalid"', "", "")


@pytest.mark.asyncio
async def test_executor_consumes_independent_submission(monkeypatch):
    session = debate()
    session.external_responses = {"participant:1": {"content": "owned response"}}
    monkeypatch.setattr("src.services.agents.workflows.debate_executor.EXTERNAL_POLL_INTERVAL", 0.001)
    executor = DebateExecutor(SimpleNamespace(refresh=AsyncMock()))
    assert await executor._wait_for_external_push(session, "participant", 1) == "owned response"


def test_debate_migration_preserves_existing_rows():
    import importlib.util
    from pathlib import Path

    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    path = Path(__file__).resolve().parents[4] / "migrations/versions/20260909_0004_debate_responses.py"
    spec = importlib.util.spec_from_file_location("debate_response_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with sa.create_engine("sqlite://").begin() as db:
        db.execute(sa.text("CREATE TABLE debate_sessions (id INTEGER PRIMARY KEY, topic TEXT)"))
        db.execute(sa.text("INSERT INTO debate_sessions VALUES (1, 'Existing debate')"))
        with Operations.context(MigrationContext.configure(db)):
            migration.upgrade()
            assert db.execute(sa.text("SELECT external_responses FROM debate_sessions")).scalar() == "{}"
            assert db.execute(sa.text("SELECT topic FROM debate_sessions")).scalar() == "Existing debate"
            migration.downgrade()
            assert {c["name"] for c in sa.inspect(db).get_columns("debate_sessions")} == {"id", "topic"}
