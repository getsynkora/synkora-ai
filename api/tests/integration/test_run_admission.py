"""Exercise admission Lua against an isolated Redis, never a configured database."""

import asyncio
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio
from redis.asyncio import Redis

from src.services.agents.run_admission import RunAdmissionError, RunLease


@pytest_asyncio.fixture
async def isolated_redis():
    binary = shutil.which("redis-server")
    if binary is None:
        pytest.skip("redis-server is required for isolated Lua integration tests")
    with tempfile.TemporaryDirectory(
        prefix="harness-", dir="/private/tmp" if Path("/private/tmp").exists() else "/tmp"
    ) as directory:
        socket = str(Path(directory) / "redis.sock")
        process = subprocess.Popen(
            [binary, "--port", "0", "--unixsocket", socket, "--save", "", "--appendonly", "no"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        client = Redis(unix_socket_path=socket)
        try:
            for _ in range(100):
                if process.poll() is not None:
                    raise RuntimeError(f"Isolated Redis failed to start: {process.stderr.read().decode()}")
                if Path(socket).exists():
                    break
                await asyncio.sleep(0.02)
            await client.ping()
            yield client
        finally:
            await client.aclose()
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            if process.stderr:
                process.stderr.close()


@pytest.mark.asyncio
async def test_atomic_tenant_and_global_limits_and_release(isolated_redis):
    leases_a = [RunLease(isolated_redis, "A", 2, 3) for _ in range(5)]
    results = await asyncio.gather(*(lease.acquire() for lease in leases_a), return_exceptions=True)
    admitted_a = [result for result in results if isinstance(result, RunLease)]
    assert len(admitted_a) == 2
    assert sum(isinstance(result, RunAdmissionError) for result in results) == 3
    lease_b = await RunLease(isolated_redis, "B", 2, 3).acquire()
    with pytest.raises(RunAdmissionError):
        await RunLease(isolated_redis, "B", 2, 3).acquire()
    await admitted_a[0].release()
    another_b = await RunLease(isolated_redis, "B", 2, 3).acquire()
    assert await isolated_redis.zcard(lease_b.keys[0]) == 3
    await asyncio.gather(admitted_a[1].release(), lease_b.release(), another_b.release())
    assert await isolated_redis.zcard(lease_b.keys[0]) == 0


@pytest.mark.asyncio
async def test_abandoned_expired_run_does_not_hold_capacity(isolated_redis):
    lease = await RunLease(isolated_redis, "A", 1, 1).acquire()
    for key in lease.keys:
        await isolated_redis.zadd(key, {lease.token: 0})
    replacement = await RunLease(isolated_redis, "A", 1, 1).acquire()
    await lease.release()  # Late release cannot remove the new owner's reservation.
    assert await isolated_redis.zcard(replacement.keys[0]) == 1
