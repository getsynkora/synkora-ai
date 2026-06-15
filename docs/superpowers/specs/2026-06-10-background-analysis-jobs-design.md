# Background Analysis Jobs — Design Spec

**Date:** 2026-06-10
**Status:** Approved

## Problem

Some database queries — complex aggregations, large ES queries, cross-table joins, write-back operations — take 30–120 seconds. Holding the SSE/HTTP connection open for that long either times out or blocks the user staring at a spinner. This is a latency and reliability problem, not a data quality problem.

Data quality is already handled by existing guards in `database_tools.py`:
- Row count guard (blocks broad queries over 50k rows, forces aggregation)
- Broad SELECT detection (rejects queries without LIMIT/GROUP BY/aggregates)
- Result truncation (caps at 50k chars)
- Write-statement guard (blocks INSERT/UPDATE/DELETE)

## Solution

When a query is expected to take long, defer it to a Celery background job. The agent responds immediately with a "running in background" message. When the job finishes, it saves the result as an assistant message in the same conversation and pushes a WebSocket event so the UI updates instantly.

No new tools needed. Existing `internal_query_database` handles all sources already.

## Architecture

```
User message
  → Agent calls internal_query_database(...)
  → Timeout/size check: will this be slow?
      → No  → run inline, return result (existing behavior, unchanged)
      → Yes → create analysis_job row
             → stream "Analyzing in background, I'll post results here."
             → Celery picks up job
             → Executes query against source
             → ChatService.save_assistant_message(conversation_id, result)
             → connection_manager.send_to_room("conversation:{id}", ws_event)
             → (optional) delivery channels if configured
```

## Deferral Decision

```python
def _should_defer(estimated_rows: int, forced: str | None = None) -> bool:
    if forced == "background":
        return True
    if forced == "inline":
        return False
    return estimated_rows > BACKGROUND_JOB_ROW_THRESHOLD  # default: 10_000, env-configurable
```

The `forced` flag is extracted from the user message by the agent — "run this in background" or "give me results now". Otherwise threshold decides automatically.

For ES, estimated rows comes from a lightweight `_count` query before execution.
For SQL, it uses the existing `_estimate_row_count()` already in `database_tools.py`.
For REST APIs, deferral is triggered by explicit user request or if the tool is flagged as slow.

## Data Model

One new table: `analysis_jobs`

```
id                UUID PK
tenant_id         UUID FK
agent_id          UUID FK
conversation_id   UUID FK
status            enum: pending | running | completed | failed
job_type          enum: read | write
source_type       str  (ELASTICSEARCH, POSTGRESQL, MYSQL, etc.)
connection_id     UUID FK (database_connections)
query             TEXT (the actual query string sent to the source)
analysis_spec     JSONB (intent description, filters, groupings — for human readability)
result_summary    JSONB (compact result stored here after completion)
write_log         JSONB (audit trail for write operations: what changed, when, row IDs)
rows_processed    INT
error             TEXT
started_at        TIMESTAMPTZ
completed_at      TIMESTAMPTZ
created_at        TIMESTAMPTZ
```

No separate artifacts table. Result lives on the job row. Follow-up turns reference `job_id` to get context if needed.

## Celery Task

```python
@celery_app.task(bind=True, max_retries=2)
def run_analysis_job(self, job_id: str):
    # 1. Load job, mark status=running
    # 2. Get connector via existing _get_or_create_connector()
    # 3. Execute query (existing connector.execute_query())
    # 4. Truncate/format result via existing _truncate_rows_for_llm()
    # 5. Save to job.result_summary, mark status=completed
    # 6. ChatService.save_assistant_message(job.conversation_id, formatted_result)
    # 7. connection_manager.send_to_room(f"conversation:{id}", {type: "analysis_job_completed", job_id})
    # 8. Trigger delivery channels if agent has them configured
    # On failure: mark status=failed, save_assistant_message with error notice
```

Everything in steps 2–4 reuses existing code. Steps 6–8 reuse existing primitives.

## API Endpoints

Two new endpoints on the agents router:

```
GET  /agents/{agent_name}/analysis-jobs
     → list jobs for current conversation (query param: conversation_id)
     → returns: id, status, source_type, created_at, completed_at

GET  /agents/{agent_name}/analysis-jobs/{job_id}
     → job detail + result_summary if completed
```

No endpoint needed to trigger jobs — they are triggered by the agent tool call internally.

## WebSocket Event

When job completes, the Celery task pushes:

```json
{
  "type": "analysis_job_completed",
  "data": {
    "conversation_id": "...",
    "job_id": "...",
    "status": "completed"
  }
}
```

The frontend handles this event by refreshing the conversation message list. No special rendering needed — the result arrives as a standard assistant message.

## Agent Prompt Change

One addition to the system prompt for database-connected agents:

> "For queries that may take a long time (large aggregations, complex joins, bulk writes), you may defer to background processing. If you do, respond with: 'This analysis is running in the background. I'll post the results here when it's ready.' Then continue the conversation normally."

## Migration

```sql
-- migrations/versions/20260610_0001_add_analysis_jobs.py
CREATE TABLE analysis_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    agent_id UUID NOT NULL REFERENCES agents(id),
    conversation_id UUID NOT NULL REFERENCES conversations(id),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    job_type VARCHAR(10) NOT NULL DEFAULT 'read',
    source_type VARCHAR(50),
    connection_id UUID REFERENCES database_connections(id),
    query TEXT,
    analysis_spec JSONB DEFAULT '{}',
    result_summary JSONB,
    write_log JSONB,
    rows_processed INTEGER,
    error TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_analysis_jobs_tenant_id ON analysis_jobs(tenant_id);
CREATE INDEX ix_analysis_jobs_conversation_id ON analysis_jobs(conversation_id);
CREATE INDEX ix_analysis_jobs_status ON analysis_jobs(status) WHERE status IN ('pending', 'running');
```

## Files Touched

| File | Change |
|------|--------|
| `api/src/models/analysis_job.py` | New model |
| `api/src/models/__init__.py` | Export new model |
| `api/migrations/versions/20260610_0001_add_analysis_jobs.py` | Migration |
| `api/src/services/agents/internal_tools/database_tools.py` | Add deferral check in `internal_query_database` |
| `api/src/tasks/analysis_tasks.py` | New Celery task |
| `api/src/controllers/agents/analysis.py` | New controller (2 GET endpoints) |
| `api/src/router_registry.py` | Register new router |
| `api/src/schemas/analysis_job.py` | Request/response schemas |

Frontend: handle `analysis_job_completed` WebSocket event (already refreshes messages on WS events — may need no change at all).

## What This Does Not Change

- Existing `internal_query_database` behavior for fast queries — completely unchanged
- Existing connectors, guards, truncation logic — reused as-is
- Existing delivery channels — called from Celery task on completion
- Existing WebSocket infrastructure — reused as-is
- No new tools, no changes to tool registration
