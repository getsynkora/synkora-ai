"""Atomic, distributed admission for long-lived runs (not HTTP request rate)."""

import os
import uuid

ACQUIRE = """
local now = redis.call('TIME')
local seconds = tonumber(now[1])
-- Evict phantom leases: entries are stored with score = creation_time + TTL,
-- so any entry with score <= now has exceeded its TTL and represents a run
-- that ended (or crashed) without calling RELEASE.  This prevents unbounded
-- accumulation of stale entries from crashed processes.
for i = 1, 2 do
    redis.call('ZREMRANGEBYSCORE', KEYS[i], '-inf', seconds)
    if redis.call('ZCARD', KEYS[i]) >= tonumber(ARGV[i]) then return 0 end
end
for i = 1, 2 do
    redis.call('ZADD', KEYS[i], seconds + tonumber(ARGV[3]), ARGV[4])
    redis.call('EXPIRE', KEYS[i], ARGV[3])
end
return 1
"""
RELEASE = """
for i = 1, 2 do redis.call('ZREM', KEYS[i], ARGV[1]) end
return 1
"""


class RunAdmissionError(RuntimeError):
    pass


class RunLease:
    def __init__(self, redis, tenant_id, tenant_limit, global_limit):
        self.redis = redis
        # Same hash slot allows an atomic global + tenant check on Redis Cluster.
        self.keys = ["harness:{runs}:global", f"harness:{{runs}}:tenant:{tenant_id}"]
        self.limits = [global_limit, tenant_limit]
        self.token = uuid.uuid4().hex

    async def acquire(self):
        try:
            acquired = await self.redis.eval(ACQUIRE, 2, *self.keys, *self.limits, 3630, self.token)
        except Exception as exc:
            raise RunAdmissionError("Run admission is temporarily unavailable; try again later") from exc
        if not acquired:
            raise RunAdmissionError("Too many active runs; try again when an existing run finishes")
        return self

    async def release(self):
        await self.redis.eval(RELEASE, 2, *self.keys, self.token)


async def acquire_run_lease(tenant_id):
    tenant_limit = int(os.getenv("HARNESS_MAX_ACTIVE_RUNS_PER_TENANT", "0"))
    if tenant_limit <= 0:
        return None
    from src.config.redis import get_redis_async

    global_limit = int(os.getenv("HARNESS_MAX_ACTIVE_RUNS", "128"))
    if global_limit < tenant_limit:
        raise RunAdmissionError("Global run capacity must be at least the per-tenant capacity")
    return await RunLease(get_redis_async(), tenant_id, tenant_limit, global_limit).acquire()
