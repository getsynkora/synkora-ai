"""Run inside the sandbox image: python - < test_isolation.py."""

import asyncio
import base64
import os

os.environ["SANDBOX_API_KEY"] = "synthetic-service-secret-for-tests-only-123"
import app


async def main():
    async with app.lifespan(app.app):
        pass
    assert "/v1/files/binary" in app.app.openapi()["paths"]
    key = app.issue_capability(app.SANDBOX_API_KEY, "attacker", "agent")
    victim = app._workspace("victim", "agent")
    victim.mkdir(parents=True, exist_ok=True)
    (victim / "marker").write_text("FOREIGN_MARKER")
    own = app._workspace("attacker", "agent")
    own.mkdir(parents=True, exist_ok=True)
    (own / "marker").write_text("OWN_MARKER")

    async def execute(command, **kwargs):
        return await app.exec_command(
            app.ExecRequest(
                tenant_id="attacker", agent_id="agent", command=command, **kwargs
            ),
            key,
        )

    # Even a valid capability cannot select another tenant or workspace.
    for tenant, agent, token in [
        ("victim", "agent", key),
        ("attacker", "other", key),
        ("attacker", "agent", app.SANDBOX_API_KEY),
    ]:
        try:
            await app.read_binary(tenant, agent, "marker", token)
            raise AssertionError("Invalid workspace capability accepted")
        except app.HTTPException as exc:
            assert exc.status_code == 401
    # Loopback belongs to the command namespace, not the service namespace.
    result = await execute(
        [
            "python3",
            "-c",
            "import socket; assert socket.if_nameindex() == [(1, 'lo')]; s=socket.socket(); s.settimeout(1); assert s.connect_ex(('127.0.0.1', 5004)) != 0",
        ]
    )
    assert result["success"], result
    result = await execute(["cat", "marker"])
    assert result["success"] and result["output"] == "OWN_MARKER", result
    for path in (str(victim / "marker"), "/app/app.py", "/proc/1/root/app/app.py"):
        result = await execute(["cat", path])
        assert not result["success"], (path, result)
        assert "FOREIGN_MARKER" not in str(result), result
    (own / "foreign-link").symlink_to(victim / "marker")
    result = await execute(["cat", "foreign-link"])
    assert not result["success"], result
    result = await execute(
        ["python3", "-c", "import os; print(os.getenv('SANDBOX_API_KEY', 'ABSENT'))"]
    )
    assert result["success"] and result["output"].strip() == "ABSENT", result
    result = await execute(["python3", "-c", "print('x' * 1000000)"])
    assert result["success"] and len(result["output"]) < 8100, result
    result = await execute(["sleep", "5"], timeout=1)
    assert not result["success"] and "timed out" in result["error"], result
    # A background process may not outlive a completed execution boundary.
    result = await execute(
        ["sh", "-c", "(sleep 2; echo leaked > background-marker) >/dev/null 2>&1 &"]
    )
    assert result["success"], result
    await asyncio.sleep(3)
    assert not (own / "background-marker").exists()
    sleeper = asyncio.create_task(execute(["sleep", "5"]))
    await asyncio.sleep(0.2)
    try:
        await app.read_binary("attacker", "agent", "marker", key)
        raise AssertionError("File operation ran concurrently with untrusted execution")
    except app.HTTPException as exc:
        assert exc.status_code == 503
    sleeper.cancel()
    try:
        await sleeper
    except asyncio.CancelledError:
        pass
    data = b"binary\x00" * 2000
    await app.write_binary(
        app.BinaryWriteRequest(
            tenant_id="attacker",
            agent_id="agent",
            path="binary",
            content_base64=base64.b64encode(data).decode(),
        ),
        key,
    )
    read = await app.read_binary("attacker", "agent", "binary", key)
    assert base64.b64decode(read["content_base64"]) == data
    try:
        await app.read_binary("attacker", "agent", str(victim / "marker"), key)
        raise AssertionError("Cross-tenant binary read accepted")
    except app.HTTPException as exc:
        assert exc.status_code == 400
    os.mkfifo(own / "fifo")
    try:
        await app.read_binary("attacker", "agent", "fifo", key)
        raise AssertionError("FIFO accepted")
    except app.HTTPException as exc:
        assert exc.status_code == 400
    print(
        "PASS: own-file execution, foreign files, symlinks, process environment, output limit, timeout, descendant cleanup, binary round trip and boundary"
    )


asyncio.run(main())
