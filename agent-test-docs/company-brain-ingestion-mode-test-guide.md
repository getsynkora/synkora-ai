# Company Brain — Knowledge Base `ingestion_mode` E2E Test Guide

Verifies the Knowledge Base API and creation UI correctly accept, validate, persist, and
return the `ingestion_mode` field (`"standard"` vs `"advanced"`), added as part of the
Company Brain / KB unification work
(`docs/superpowers/specs/2026-08-17-company-brain-kb-unification-design.md`, Plan C).

All steps below were run against the live local stack (`docker-compose`, `api` on
`http://localhost:5001`) using Python's `urllib` (avoids shell `!`/quoting issues — see
project memory). Login credentials: `admin@localhost.com` / `Admin123!` via
`POST /console/api/auth/login`, `Authorization: Bearer {access_token}` on all subsequent
calls.

## Prerequisites

- `docker compose up -d` running, `api` container healthy.
- Alembic migrations applied: `docker compose exec -T api alembic current` shows
  `20260817_0002 (head)` (adds `knowledge_bases.ingestion_mode` column).
- **Gotcha found during this test**: the `api` container's `uvicorn --reload` process can
  get into a state where it does not pick up new code despite the file being correct on
  disk (confirmed identical on host and in-container via `docker compose exec -T api grep`).
  If newly-added response fields are missing from live JSON responses despite the code
  being correct, run `docker compose restart api` and retry before assuming a code bug.

## Step 1 — Create a KB with `ingestion_mode: "advanced"`

```
POST http://localhost:5001/api/v1/knowledge-bases
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "CB Advanced Test KB",
  "description": "Verify ingestion_mode advanced round-trip after api restart",
  "vector_db_provider": "QDRANT",
  "vector_db_config": {"url": "http://qdrant:6333"},
  "embedding_provider": "SENTENCE_TRANSFORMERS",
  "embedding_model": "all-MiniLM-L6-v2",
  "embedding_config": {},
  "chunking_strategy": "SEMANTIC",
  "chunk_size": 1500,
  "chunk_overlap": 150,
  "min_chunk_size": 500,
  "max_chunk_size": 3000,
  "chunking_config": {},
  "ingestion_mode": "advanced"
}
```

Note: `embedding_provider` must be one of the uppercase `EmbeddingProvider` enum values
defined in `api/src/models/knowledge_base.py` (`SENTENCE_TRANSFORMERS`, `OPENAI`, `COHERE`,
`HUGGINGFACE`, `LITELLM`) — lowercase values are rejected with
`400 {"detail": "Invalid embedding provider: ..."}`.

**Actual response (verified live):**

```
Status: 201 Created

{
  "id": 5,
  "name": "CB Advanced Test KB",
  "description": "Verify ingestion_mode advanced round-trip after api restart",
  "tenant_id": "09a1dc51-d0ea-40ff-a50a-29d98ce477a8",
  "embedding_provider": "SENTENCE_TRANSFORMERS",
  "embedding_model": "all-MiniLM-L6-v2",
  "embedding_config": {},
  "vector_db_provider": "QDRANT",
  "vector_db_config": {"url": "http://qdrant:6333"},
  "chunking_strategy": "SEMANTIC",
  "chunk_size": 1500,
  "chunk_overlap": 150,
  "min_chunk_size": 500,
  "max_chunk_size": 3000,
  "chunking_config": {},
  "ingestion_mode": "advanced",
  "document_count": 0,
  "total_chunks": 0,
  "is_active": true,
  "created_at": "2026-08-17T08:15:41.828880+00:00",
  "updated_at": "2026-08-17T08:15:41.828881+00:00"
}
```

`ingestion_mode: "advanced"` is present and correct in the create response.

## Step 2 — Re-fetch the KB and confirm the field persisted

```
GET http://localhost:5001/api/v1/knowledge-bases/5
Authorization: Bearer {token}
```

**Actual response (verified live):**

```
Status: 200 OK
ingestion_mode: "advanced"
```

Full response body matches Step 1's create response exactly (same fields, same value).
Confirms `ingestion_mode` is persisted to the database (not just echoed back from the
request) and correctly deserialized from the DB row on a fresh `GET`.

## Step 3 — Create a KB with `ingestion_mode: "standard"` (default path)

```
POST http://localhost:5001/api/v1/knowledge-bases
{
  ...same shape as Step 1...
  "ingestion_mode": "standard"
}
```

**Actual response (verified live, KB id 3):**

```
Status: 201 Created
ingestion_mode: "standard"
```

```
GET http://localhost:5001/api/v1/knowledge-bases/3
Status: 200 OK
ingestion_mode: "standard"
```

Confirms the `"standard"` value (the field's default) also round-trips correctly.

## Step 4 — Invalid `ingestion_mode` value is rejected with 400

```
POST http://localhost:5001/api/v1/knowledge-bases
{
  ...
  "ingestion_mode": "bogus_mode"
}
```

**Actual response (verified live):**

```
Status: 400 Bad Request
{"detail": "Invalid ingestion mode: bogus_mode"}
```

Confirms `CreateKnowledgeBaseRequest`'s `IngestionMode(request.ingestion_mode)` coercion in
`api/src/controllers/knowledge_bases.py` correctly rejects unknown values instead of
silently accepting or defaulting them.

## Step 5 — Frontend creation UI exposes the ingestion mode selector

File: `web/app/(dashboard)/knowledge-bases/create/page.tsx`

1. Navigate to `/knowledge-bases/create`.
2. Click "Show advanced options" (or equivalent toggle that reveals `showAdvanced` section).
3. Confirm a new "Ingestion Mode" section appears as the **first** section inside the
   advanced-options panel, above "Vector Database", with two selectable cards:
   - **Standard** — "Direct document upload and vector search."
   - **Advanced (Company Brain)** — "Continuous multi-source ingestion with hybrid search
     and tiered storage."
4. Selecting a card visually highlights it (`bg-[#f7f2e7]` + shadow) and unhighlights the
   other.
5. Submitting the form sends `ingestion_mode: "standard"` or `ingestion_mode: "advanced"`
   in the `POST /api/v1/knowledge-bases` payload matching the selected card.

Verified via `pnpm type-check` (0 errors) and `pnpm lint` (0 errors, 2 pre-existing
unrelated warnings in `agents/page.tsx`) before live verification — this test guide's
Steps 1-4 (the API contract the UI depends on) are the parts confirmed against the live
running stack.

## Summary

| Check | Result |
|---|---|
| Create KB with `ingestion_mode: "advanced"` | 201, field present and correct |
| Re-fetch persists `"advanced"` | 200, field present and correct |
| Create KB with `ingestion_mode: "standard"` | 201, field present and correct |
| Re-fetch persists `"standard"` | 200, field present and correct |
| Invalid `ingestion_mode` value | 400, correct error message |
| Frontend selector renders + submits correct value | Verified via type-check/lint + code read |
