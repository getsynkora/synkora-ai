"""Non-destructive evidence probes. Run from api with PYTHONPATH=.

Uses synthetic identities, patched network/DB handlers, and validators only.
Does not contact URLs or read production credentials. The sandbox test runs only a controlled command reading a temporary synthetic marker.
A True finding means the unsafe behavior is present, NOT that security passed.
"""

import ast
import asyncio
import json
import logging
import os
import ssl
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


async def main():
    logging.disable(logging.CRITICAL)
    from cryptography.fernet import Fernet

    os.environ.update(
        {
            "APP_ENV": "test",
            "SECRET_KEY": "synthetic-review-secret-key-32-characters",
            "JWT_SECRET_KEY": "synthetic-review-jwt-key-32-characters",
            "ENCRYPTION_KEY": Fernet.generate_key().decode(),
            "CELERY_BROKER_URL": "memory://",
            "CELERY_RESULT_BACKEND": "cache+memory://",
        }
    )
    findings = {}
    from src.services.agents.internal_tools.command_tools import _is_command_safe

    # These are passed only to the validator; never executed.
    findings["command_accepts_untrusted_executable_basename"] = _is_command_safe(
        ["/tmp/review-workspace/ls"], "/tmp/review-workspace"
    )
    findings["command_accepts_awk_environment_read"] = _is_command_safe(
        ["awk", 'BEGIN {print ENVIRON["REVIEW_SENTINEL"]}'], "/tmp/review-workspace"
    )
    findings["command_accepts_find_child_execution"] = _is_command_safe(
        ["find", "/tmp/review-workspace", "-exec", "sh", "-c", "echo REVIEW_SENTINEL", "{}", "+"],
        "/tmp/review-workspace",
    )
    from src.config.database import DatabaseConfig

    config = DatabaseConfig(db_extras="sslmode=verify-full")
    ctx = config.sqlalchemy_async_engine_options["connect_args"]["ssl"]
    findings["explicit_verify_full_disables_certificate_validation"] = (
        ctx.verify_mode == ssl.CERT_NONE and not ctx.check_hostname
    )
    from src.services.agents.implementations.claude_code_agent import ClaudeCodeAgent

    fake_agent = SimpleNamespace(_get_api_key=lambda: "synthetic-api-key", _get_base_url=lambda: None)
    with patch.dict(os.environ, {"REVIEW_SENTINEL": "synthetic-marker"}):
        child_env = ClaudeCodeAgent._build_cli_env(fake_agent)
        findings["claude_cli_inherits_parent_marker"] = child_env.get("REVIEW_SENTINEL") == "synthetic-marker"
    del child_env

    # Execute the actual token-minting AST block with synthetic request/secret only.
    import jwt
    from src.services.agents.security import encrypt_value

    source = Path("src/controllers/widgets.py").read_text()
    tree = ast.parse(source)
    mint = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.If) and ast.unparse(node.test) == "request.user and widget.identity_secret"
    )
    key = "synthetic-review-secret-at-least-32-bytes"
    request = SimpleNamespace(
        user=SimpleNamespace(
            id="user-A", org_id="organization-B", name="Test", email="test@example.invalid", org_name="Test"
        ),
        source="widget",
    )
    widget = SimpleNamespace(id=uuid4(), identity_secret=encrypt_value(key), identity_verification_required=False)
    namespace = {
        "request": request,
        "widget": widget,
        "logger": logging.getLogger("probe"),
        "sentry_sdk": MagicMock(),
        "_mcp_user_token": None,
    }
    exec(compile(ast.Module(body=[mint], type_ignores=[]), "<actual-widget-mint-block>", "exec"), namespace)
    payload = jwt.decode(namespace["_mcp_user_token"], key, algorithms=["HS256"])
    findings["widget_mints_signed_claims_without_identity_verification"] = (
        payload["user_id"] == "user-A" and payload["organization_id"] == "organization-B"
    )

    from src.services.agents.internal_tools.news_tools import internal_fetch_rss_feed

    http = MagicMock()
    http.__aenter__ = AsyncMock(return_value=http)
    http.__aexit__ = AsyncMock(return_value=False)
    http.get = AsyncMock(
        return_value=SimpleNamespace(status_code=200, text="<rss><channel><title>synthetic</title></channel></rss>")
    )
    with patch("src.services.agents.internal_tools.news_tools.httpx.AsyncClient", return_value=http):
        await internal_fetch_rss_feed("http://127.0.0.1/private-test")
    findings["rss_dispatches_loopback_url_without_policy"] = http.get.await_count == 1

    from src.controllers.recall_webhooks import receive_recall_webhook
    from starlette.requests import Request

    body = json.dumps({"event": "bot.status_change", "data": {"bot": {"id": "synthetic"}}}).encode()

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [],
            "query_string": b"agent_id=synthetic",
            "client": ("review-test", 0),
        },
        receive,
    )
    with (
        patch("src.controllers.recall_webhooks._get_webhook_secret", AsyncMock(return_value=None)),
        patch("src.controllers.recall_webhooks._handle_bot_status_change", AsyncMock()) as handler,
    ):
        response = await receive_recall_webhook(request, MagicMock())
    findings["recall_unsigned_request_reaches_handler_without_secret"] = (
        handler.await_count == 1 and response["status"] == "ok"
    )
    # Exercise the exact anonymous ownership predicate against synthetic rows in SQLite.
    from sqlalchemy import create_engine, select, text
    from src.models.conversation import Conversation

    widget_tree = ast.parse(Path("src/controllers/widgets.py").read_text())
    anon_assignment = next(
        node
        for node in ast.walk(widget_tree)
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "anon_check" for t in node.targets)
    )
    expression = anon_assignment.value.value.args[0]
    conversation_id, agent_id = uuid4(), uuid4()
    import uuid

    query = eval(
        compile(ast.Expression(expression), "<actual-anonymous-predicate>", "eval"),
        {
            "select": select,
            "Conversation": Conversation,
            "uuid": uuid,
            "resolved_conversation_id": str(conversation_id),
            "agent": SimpleNamespace(id=agent_id),
        },
    )
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE conversations (id TEXT, agent_id TEXT, account_id TEXT, external_user_id TEXT, session_id TEXT)"
            )
        )
        connection.execute(
            text("INSERT INTO conversations VALUES (:id, :agent, NULL, :user, :session)"),
            {"id": conversation_id.hex, "agent": agent_id.hex, "user": "another-user", "session": "another-session"},
        )
        found = connection.execute(select(Conversation.id).where(*query._where_criteria)).first()
        findings["anonymous_predicate_accepts_identified_users_conversation"] = found is not None
    engine.dispose()

    from src.middleware.auth_middleware import get_current_tenant_id

    stale_tenant = uuid4()
    findings["tenant_dependency_accepts_stale_claim_without_membership_lookup"] = (
        get_current_tenant_id(payload={"tenant_id": str(stale_tenant)}, _current_account=SimpleNamespace(id=uuid4()))
        == stale_tenant
    )
    from src.services.agents.internal_tools.file_analysis_tools import _validate_query, _validate_s3_url

    s3_url = "s3://another-tenant-bucket/private.csv"
    fake_query = "SELECT 1 /* read_csv_auto('" + s3_url + "') */"
    findings["duckdb_comment_satisfies_data_source_validation"] = _validate_query(fake_query, s3_url) is None
    findings["duckdb_accepts_unscoped_s3_object"] = _validate_s3_url(s3_url) is None

    # Controlled cross-tenant filesystem test: only temporary synthetic marker data.
    import importlib.util
    import sys
    import tempfile

    spec = importlib.util.spec_from_file_location("review_sandbox", "../services/sandbox/app.py")
    sandbox = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sandbox)
    with tempfile.TemporaryDirectory(prefix="synkora-security-") as directory:
        sandbox.WORKSPACES_BASE = Path(directory)
        sandbox.SANDBOX_API_KEY = "synthetic-review-key"
        victim = Path(directory) / "tenant-B" / "agent-B"
        victim.mkdir(parents=True)
        marker = victim / "marker.txt"
        marker.write_text("SYNTHETIC-OTHER-TENANT")
        result = await sandbox.exec_command(
            sandbox.ExecRequest(
                tenant_id="tenant-A",
                agent_id="agent-A",
                command=[
                    sys.executable,
                    "-c",
                    "from pathlib import Path; import sys; print(Path(sys.argv[1]).read_text())",
                    str(marker),
                ],
            ),
            x_sandbox_key="synthetic-review-key",
        )
        findings["sandbox_tenant_A_command_reads_tenant_B_marker"] = (
            result["success"] and result["output"].strip() == "SYNTHETIC-OTHER-TENANT"
        )
    # Execute the actual enterprise-login policy try blocks under a simulated DB failure.
    from fastapi import HTTPException, status

    auth_tree = ast.parse(Path("src/controllers/console/auth.py").read_text())
    login = next(node for node in auth_tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "login")
    policy_blocks = [
        node
        for node in login.body
        if isinstance(node, ast.Try)
        and (
            "from src.models.saml_config import SAMLConfig" in ast.unparse(node)
            or "from src.models.tenant import Tenant as _Tenant" in ast.unparse(node)
        )
    ]
    policy_function = ast.AsyncFunctionDef(
        name="policies",
        args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
        body=policy_blocks + [ast.Return(value=ast.Constant(True))],
        decorator_list=[],
    )
    policy_module = ast.fix_missing_locations(ast.Module(body=[policy_function], type_ignores=[]))
    silent_logger = MagicMock()
    namespace = {
        "db": SimpleNamespace(execute=AsyncMock(side_effect=RuntimeError("synthetic failure"))),
        "account": SimpleNamespace(id=uuid4()),
        "logger": silent_logger,
        "select": select,
        "HTTPException": HTTPException,
        "status": status,
    }
    exec(compile(policy_module, "<actual-login-policies>", "exec"), namespace)
    findings["saml_and_mfa_policy_errors_continue_login"] = await namespace["policies"]() and len(policy_blocks) == 2

    from datetime import UTC, datetime, timedelta

    from src.services.auth_service import AuthService

    account = SimpleNamespace(
        id=uuid4(), password_history=[], reset_token_expires_at=(datetime.now(UTC) + timedelta(minutes=5)).isoformat()
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = account
    db = SimpleNamespace(execute=AsyncMock(return_value=result), commit=AsyncMock(), refresh=AsyncMock())
    with (
        patch.object(AuthService, "hash_password", return_value="synthetic-new-hash"),
        patch("src.services.security.token_blacklist.TokenBlacklistService") as blacklist,
    ):
        blacklist.return_value.blacklist_all_account_tokens.side_effect = RuntimeError("synthetic revocation failure")
        updated = await AuthService.reset_password(db, "synthetic-reset-token", "SyntheticNewPassword123!")
    findings["password_reset_succeeds_after_revocation_failure"] = updated is account and db.commit.await_count == 1
    from src.controllers.widgets import get_widget_chat_history

    history_widget = SimpleNamespace(
        id=uuid4(), agent_id=uuid4(), tenant_id=uuid4(), identity_verification_required=True
    )
    routes_result, agents_result, conversation_result, messages_result = (MagicMock() for _ in range(4))
    routes_result.scalars.return_value.all.return_value = []
    agents_result.all.return_value = [(history_widget.agent_id,)]
    conversation_result.scalar_one_or_none.return_value = SimpleNamespace(id=uuid4())
    messages_result.scalars.return_value.all.return_value = [
        SimpleNamespace(id=uuid4(), role="assistant", content="SYNTHETIC-PRIVATE-HISTORY", created_at=datetime.now(UTC))
    ]
    history_db = SimpleNamespace(
        execute=AsyncMock(side_effect=[routes_result, agents_result, conversation_result, messages_result])
    )
    history_request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"x-widget-api-key", b"synthetic-public-key")],
            "query_string": b"",
        }
    )
    with patch("src.controllers.widgets.WidgetAuthMiddleware.validate_api_key", AsyncMock(return_value=history_widget)):
        history = await get_widget_chat_history(history_request, external_user_id="victim-user", db=history_db)
    findings["widget_history_ignores_required_identity_verification"] = (
        history.data["messages"][0]["content"] == "SYNTHETIC-PRIVATE-HISTORY"
    )
    print(json.dumps({"unsafe_behaviors_reproduced": findings}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
