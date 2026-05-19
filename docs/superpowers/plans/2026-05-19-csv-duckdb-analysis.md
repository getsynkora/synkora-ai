# CSV / DuckDB File Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users upload large CSV files (up to 1 GB) directly to S3 from the chat UI, then have the agent query them using DuckDB's `read_csv_auto` — no database connection record required.

**Architecture:** A presigned-PUT endpoint returns a direct S3 upload URL so the file never routes through the API server. A new agent tool `query_file_with_duckdb` opens an ephemeral `:memory:` DuckDB, loads `httpfs`, configures credentials from env vars, then runs the user-supplied SQL against `read_csv_auto(s3_url)`. The frontend adds a "Upload for analysis" button to `ChatInput` that drives the whole flow and auto-inserts a prompt when upload completes.

**Tech Stack:** Python / FastAPI (backend), DuckDB + httpfs (query engine), boto3 (presigned URL), React / TypeScript (frontend), existing S3StorageService (credential source)

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Modify | `api/src/controllers/data_analysis.py` | Add `GET /upload-presigned-url` endpoint |
| Create | `api/src/services/agents/internal_tools/file_analysis_tools.py` | `query_file_with_duckdb` tool function |
| Modify | `api/src/services/agents/tool_registrations/data_analysis_tools_registry.py` | Register new tool |
| Create | `api/tests/unit/services/agents/test_file_analysis_tools.py` | Unit tests |
| Modify | `web/lib/api/conversations.ts` | `getAnalysisUploadUrl` + direct-PUT helper |
| Modify | `web/lib/api/client.ts` | Wire new API function |
| Create | `web/components/chat/hooks/useDataFileUpload.ts` | Presigned upload hook with progress |
| Modify | `web/components/chat/components/ChatInput.tsx` | "Upload for analysis" button |

---

## Task 1: Presigned upload URL endpoint

**Files:**
- Modify: `api/src/controllers/data_analysis.py`
- Test: `api/tests/unit/controllers/test_data_analysis_upload.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/unit/controllers/test_data_analysis_upload.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from uuid import uuid4


@pytest.fixture
def client():
    from src.app import create_app
    app = create_app()
    return TestClient(app)


def test_get_upload_presigned_url_returns_url_and_s3_key(client):
    """Endpoint returns presigned PUT url, s3_key, and s3_url."""
    tenant_id = uuid4()
    mock_presigned = "https://minio:9000/bucket/data-uploads/tenant/file.csv?X-Amz-Signature=abc"

    with patch("src.controllers.data_analysis.get_current_tenant_id", return_value=tenant_id), \
         patch("src.controllers.data_analysis.S3StorageService") as MockS3:

        instance = MockS3.return_value
        instance.bucket_name = "synkora"
        instance.presigned_client.generate_presigned_url.return_value = mock_presigned

        resp = client.get(
            "/api/v1/data-analysis/upload-presigned-url",
            params={"filename": "sales.csv", "content_type": "text/csv"},
            headers={"Authorization": "Bearer test-token"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "upload_url" in data
    assert "s3_key" in data
    assert "s3_url" in data
    assert data["s3_url"].startswith("s3://")
    assert "sales.csv" in data["s3_key"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd api && pytest tests/unit/controllers/test_data_analysis_upload.py -v
```

Expected: FAIL (endpoint does not exist yet)

- [ ] **Step 3: Add the endpoint to `api/src/controllers/data_analysis.py`**

Open `api/src/controllers/data_analysis.py`. After the existing imports, add:

```python
import re
from uuid import uuid4 as _uuid4
```

Then add this endpoint after the last existing route in the file (before the final blank line):

```python
_SAFE_FILENAME_RE = re.compile(r"[^a-zA-Z0-9._\-]")
_ALLOWED_CONTENT_TYPES = {
    "text/csv",
    "text/tab-separated-values",
    "application/json",
    "application/octet-stream",   # .parquet often has this type
}


@router.get("/upload-presigned-url")
async def get_analysis_upload_presigned_url(
    filename: str,
    content_type: str = "text/csv",
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    """
    Return a presigned S3 PUT URL so the browser can upload a large data file
    directly to S3 without routing through the API server.

    The caller must PUT the file body to `upload_url` with the matching
    Content-Type header.  After upload completes, pass `s3_url` to the agent's
    `query_file_with_duckdb` tool.
    """
    from src.services.storage.s3_storage import S3StorageService
    from datetime import UTC, datetime

    if content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"content_type must be one of: {', '.join(sorted(_ALLOWED_CONTENT_TYPES))}",
        )

    # Sanitise filename: keep only alphanumeric, dot, dash, underscore
    safe_name = _SAFE_FILENAME_RE.sub("_", filename)
    if not safe_name:
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_id = str(_uuid4())
    date_path = datetime.now(UTC).strftime("%Y/%m/%d")
    s3_key = f"data-uploads/{tenant_id}/{date_path}/{file_id}_{safe_name}"

    storage = S3StorageService()
    upload_url = storage.presigned_client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": storage.bucket_name,
            "Key": s3_key,
            "ContentType": content_type,
        },
        ExpiresIn=3600,
    )

    return {
        "upload_url": upload_url,
        "s3_key": s3_key,
        "s3_url": f"s3://{storage.bucket_name}/{s3_key}",
        "expires_in": 3600,
    }
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd api && pytest tests/unit/controllers/test_data_analysis_upload.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd api && git add src/controllers/data_analysis.py tests/unit/controllers/test_data_analysis_upload.py
git commit -m "feat: add presigned S3 PUT URL endpoint for large data file uploads"
```

---

## Task 2: DuckDB file query tool function

**Files:**
- Create: `api/src/services/agents/internal_tools/file_analysis_tools.py`
- Create: `api/tests/unit/services/agents/test_file_analysis_tools.py`

- [ ] **Step 1: Write the failing tests**

Create `api/tests/unit/services/agents/test_file_analysis_tools.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import pandas as pd


@pytest.mark.asyncio
async def test_query_file_with_duckdb_success():
    """Returns rows, columns, and row_count on success."""
    from src.services.agents.internal_tools.file_analysis_tools import query_file_with_duckdb

    mock_df = pd.DataFrame([{"category": "A", "total": 100}, {"category": "B", "total": 200}])

    with patch("src.services.agents.internal_tools.file_analysis_tools._run_duckdb_query", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_df
        result = await query_file_with_duckdb(
            s3_url="s3://bucket/data-uploads/tenant/file.csv",
            query="SELECT category, SUM(amount) AS total FROM read_csv_auto('s3://bucket/data-uploads/tenant/file.csv') GROUP BY category",
        )

    assert result["success"] is True
    assert result["row_count"] == 2
    assert "category" in result["columns"]
    assert result["rows"][0]["category"] == "A"


@pytest.mark.asyncio
async def test_query_file_rejects_non_s3_url():
    """Rejects URLs that are not s3:// scheme."""
    from src.services.agents.internal_tools.file_analysis_tools import query_file_with_duckdb

    result = await query_file_with_duckdb(
        s3_url="file:///etc/passwd",
        query="SELECT 1",
    )
    assert result["success"] is False
    assert "s3://" in result["error"]


@pytest.mark.asyncio
async def test_query_file_rejects_query_without_read_function():
    """Rejects SQL that does not reference read_csv_auto / read_parquet / read_json_auto."""
    from src.services.agents.internal_tools.file_analysis_tools import query_file_with_duckdb

    result = await query_file_with_duckdb(
        s3_url="s3://bucket/data-uploads/tenant/file.csv",
        query="SELECT * FROM some_table",
    )
    assert result["success"] is False
    assert "read_csv_auto" in result["error"]


@pytest.mark.asyncio
async def test_query_file_truncates_large_result():
    """Truncates results when row count exceeds MAX_ROWS."""
    from src.services.agents.internal_tools.file_analysis_tools import query_file_with_duckdb, MAX_ROWS

    large_df = pd.DataFrame([{"id": i, "val": i * 2} for i in range(MAX_ROWS + 500)])

    with patch("src.services.agents.internal_tools.file_analysis_tools._run_duckdb_query", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = large_df
        result = await query_file_with_duckdb(
            s3_url="s3://bucket/data-uploads/tenant/file.csv",
            query="SELECT id, val FROM read_csv_auto('s3://bucket/data-uploads/tenant/file.csv')",
        )

    assert result["success"] is True
    assert result["row_count"] == MAX_ROWS
    assert result["truncated"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd api && pytest tests/unit/services/agents/test_file_analysis_tools.py -v
```

Expected: FAIL (module does not exist)

- [ ] **Step 3: Create `api/src/services/agents/internal_tools/file_analysis_tools.py`**

```python
"""
DuckDB-powered file analysis tool for agents.

Lets agents query large CSV / Parquet / JSON files stored in S3 (or MinIO)
using DuckDB's read_csv_auto() / read_parquet() / read_json_auto() functions.

No DatabaseConnection record is needed — credentials are read from the same
env vars used by S3StorageService (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
AWS_S3_BUCKET, AWS_ENDPOINT_URL, AWS_REGION).
"""

import asyncio
import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

MAX_ROWS = 1_000
MAX_RESULT_CHARS = 50_000

# Allowed DuckDB table-valued functions for reading remote files.
# The query MUST reference at least one of these — prevents arbitrary
# filesystem reads or table references that could leak server-side data.
_ALLOWED_READ_FUNCTIONS = re.compile(
    r"read_csv_auto\s*\(|read_parquet\s*\(|read_json_auto\s*\(",
    re.IGNORECASE,
)


def _validate_s3_url(s3_url: str) -> str | None:
    """Return error message if s3_url is not safe, else None."""
    if not s3_url.startswith("s3://"):
        return "s3_url must start with s3://"
    # No path traversal
    if ".." in s3_url:
        return "s3_url must not contain '..'"
    return None


def _validate_query(query: str, s3_url: str) -> str | None:
    """Return error message if query is not acceptable, else None."""
    if not _ALLOWED_READ_FUNCTIONS.search(query):
        return (
            "query must reference read_csv_auto(), read_parquet(), or "
            "read_json_auto() as the data source"
        )
    # The s3_url must appear inside the query so it cannot be redirected
    # to an arbitrary path by the LLM
    if s3_url not in query:
        return "The s3_url must appear inside the query string"
    return None


async def _run_duckdb_query(query: str) -> Any:
    """
    Execute *query* in a fresh :memory: DuckDB connection in a thread-pool
    executor (DuckDB's Python API is synchronous).

    S3 / MinIO credentials are read from env vars:
        AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION,
        AWS_ENDPOINT_URL (set for MinIO), AWS_S3_BUCKET (unused here).
    """
    import duckdb  # optional dep — deferred import

    def _sync_run():
        conn = duckdb.connect(":memory:")
        try:
            conn.execute("INSTALL httpfs; LOAD httpfs;")

            region = os.getenv("AWS_REGION", "us-east-1")
            access_key = os.getenv("AWS_ACCESS_KEY_ID", "")
            secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "")
            endpoint = os.getenv("AWS_ENDPOINT_URL", "")

            if access_key and secret_key:
                conn.execute(f"SET s3_access_key_id='{access_key.replace(chr(39), chr(39)*2)}'")
                conn.execute(f"SET s3_secret_access_key='{secret_key.replace(chr(39), chr(39)*2)}'")
                conn.execute(f"SET s3_region='{region}'")

            if endpoint:
                # Strip scheme for DuckDB — it expects host:port
                host = endpoint.replace("https://", "").replace("http://", "").rstrip("/")
                conn.execute(f"SET s3_endpoint='{host}'")
                conn.execute("SET s3_use_ssl=false")
                conn.execute("SET s3_url_style='path'")

            rel = conn.execute(query)
            return rel.fetchdf()
        finally:
            conn.close()

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_run)


async def query_file_with_duckdb(
    s3_url: str,
    query: str,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Execute a SQL query against a file stored in S3 / MinIO using DuckDB.

    The query MUST use read_csv_auto(s3_url), read_parquet(s3_url), or
    read_json_auto(s3_url) as its data source.

    Args:
        s3_url:  S3 URL of the uploaded file, e.g. ``s3://bucket/path/file.csv``
        query:   SQL query referencing the file via a DuckDB read function.
        config:  Runtime context (not used — credentials come from env vars).

    Returns:
        ``{"success": bool, "rows": list[dict], "row_count": int,
           "columns": list[str], "truncated": bool, "error": str}``
    """
    # --- validation ---
    url_err = _validate_s3_url(s3_url)
    if url_err:
        return {"success": False, "error": url_err, "rows": [], "columns": [], "row_count": 0, "truncated": False}

    query_err = _validate_query(query, s3_url)
    if query_err:
        return {"success": False, "error": query_err, "rows": [], "columns": [], "row_count": 0, "truncated": False}

    try:
        df = await _run_duckdb_query(query)
    except ImportError:
        return {"success": False, "error": "duckdb is not installed on this server", "rows": [], "columns": [], "row_count": 0, "truncated": False}
    except Exception as exc:
        logger.error("DuckDB query failed: %s", exc)
        return {"success": False, "error": str(exc), "rows": [], "columns": [], "row_count": 0, "truncated": False}

    total = len(df)
    truncated = total > MAX_ROWS
    if truncated:
        df = df.head(MAX_ROWS)

    columns: list[str] = list(df.columns)
    rows: list[dict] = df.to_dict(orient="records")

    # Stringify to avoid non-serialisable numpy types
    import json
    try:
        rows = json.loads(json.dumps(rows, default=str))
    except Exception:
        rows = [{k: str(v) for k, v in row.items()} for row in rows]

    return {
        "success": True,
        "rows": rows,
        "row_count": len(rows),
        "columns": columns,
        "truncated": truncated,
        "total_rows_in_result": total,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd api && pytest tests/unit/services/agents/test_file_analysis_tools.py -v
```

Expected: PASS (all 4 tests)

- [ ] **Step 5: Commit**

```bash
cd api && git add src/services/agents/internal_tools/file_analysis_tools.py tests/unit/services/agents/test_file_analysis_tools.py
git commit -m "feat: add query_file_with_duckdb agent tool function"
```

---

## Task 3: Register the tool in the agent registry

**Files:**
- Modify: `api/src/services/agents/tool_registrations/data_analysis_tools_registry.py`

- [ ] **Step 1: Add the import and registration call**

Open `api/src/services/agents/tool_registrations/data_analysis_tools_registry.py`.

Inside the `register_data_analysis_tools` function, add this import at the top of the function body (after the existing imports block):

```python
    from src.services.agents.internal_tools.file_analysis_tools import (
        query_file_with_duckdb,
    )
```

Then add the registration **after** the `generate_chart_from_data` registration and before `logger.info(...)`:

```python
    registry.register_tool(
        name="query_file_with_duckdb",
        description=(
            "Execute a SQL query against a large CSV, Parquet, or JSON file that was uploaded to S3. "
            "The file is queried in-process using DuckDB — no database connection record needed. "
            "The query MUST use read_csv_auto(s3_url), read_parquet(s3_url), or read_json_auto(s3_url) "
            "as the table source, where s3_url is the exact s3:// URL provided by the user.\n\n"
            "Examples:\n"
            "  SELECT * FROM read_csv_auto('s3://bucket/path/file.csv') LIMIT 10\n"
            "  SELECT category, SUM(amount) FROM read_csv_auto('s3://bucket/path/file.csv') GROUP BY category\n"
            "  SELECT * FROM read_parquet('s3://bucket/path/data.parquet') WHERE date > '2024-01-01'\n\n"
            "Returns up to 1000 rows. For larger result sets, use GROUP BY / aggregation in your query."
        ),
        parameters={
            "type": "object",
            "properties": {
                "s3_url": {
                    "type": "string",
                    "description": "S3 URL of the uploaded file, e.g. s3://bucket/data-uploads/tenant/2026/05/19/uuid_sales.csv",
                },
                "query": {
                    "type": "string",
                    "description": (
                        "DuckDB SQL query. Must reference the file via read_csv_auto(s3_url), "
                        "read_parquet(s3_url), or read_json_auto(s3_url). "
                        "Example: SELECT region, COUNT(*) FROM read_csv_auto('s3://...') GROUP BY region"
                    ),
                },
            },
            "required": ["s3_url", "query"],
        },
        function=query_file_with_duckdb,
    )
```

Also update the log line at the bottom from `"Registered 8 data analysis tools"` to `"Registered 9 data analysis tools"`.

- [ ] **Step 2: Verify it is importable**

```bash
cd api && python -c "from src.services.agents.tool_registrations.data_analysis_tools_registry import register_data_analysis_tools; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd api && git add src/services/agents/tool_registrations/data_analysis_tools_registry.py
git commit -m "feat: register query_file_with_duckdb in data analysis tool registry"
```

---

## Task 4: Frontend — API client function for presigned URL

**Files:**
- Modify: `web/lib/api/conversations.ts`
- Modify: `web/lib/api/client.ts`

- [ ] **Step 1: Add `getAnalysisUploadUrl` to `web/lib/api/conversations.ts`**

Open `web/lib/api/conversations.ts`. After the `uploadChatAttachment` function (around line 160), add:

```typescript
// Data file analysis — presigned upload URL
export async function getAnalysisUploadUrl(
  filename: string,
  contentType: string = 'text/csv'
): Promise<{ upload_url: string; s3_key: string; s3_url: string; expires_in: number }> {
  const params = new URLSearchParams({ filename, content_type: contentType })
  const res = await fetch(`/api/v1/data-analysis/upload-presigned-url?${params}`, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${(await import('@/lib/auth/secure-storage')).secureStorage.getAccessToken()}`,
    },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Failed to get upload URL: ${res.status}`)
  }
  return res.json()
}
```

- [ ] **Step 2: Wire into `web/lib/api/client.ts`**

Open `web/lib/api/client.ts`. Find the interface block that lists `uploadChatAttachment` (around line 117). Add after `uploadChatAttachment`:

```typescript
  getAnalysisUploadUrl: typeof conversations.getAnalysisUploadUrl
```

Find the object literal where `uploadChatAttachment: conversations.uploadChatAttachment` is assigned (around line 348). Add after it:

```typescript
  getAnalysisUploadUrl: conversations.getAnalysisUploadUrl,
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd web && pnpm type-check 2>&1 | grep -E "error|Error" | head -20
```

Expected: no new errors related to `getAnalysisUploadUrl`

- [ ] **Step 4: Commit**

```bash
cd web && git add lib/api/conversations.ts lib/api/client.ts
git commit -m "feat: add getAnalysisUploadUrl API client function"
```

---

## Task 5: Frontend — `useDataFileUpload` hook

**Files:**
- Create: `web/components/chat/hooks/useDataFileUpload.ts`

- [ ] **Step 1: Create `web/components/chat/hooks/useDataFileUpload.ts`**

```typescript
'use client'

import { useState } from 'react'
import { apiClient } from '@/lib/api/client'

export interface DataFileUploadResult {
  s3Url: string
  s3Key: string
  filename: string
}

export interface DataFileUploadState {
  progress: number          // 0–100
  status: 'idle' | 'uploading' | 'done' | 'error'
  error: string | null
}

const ALLOWED_EXTENSIONS = /\.(csv|tsv|json|parquet|ndjson|jsonl)$/i

export function useDataFileUpload() {
  const [state, setState] = useState<DataFileUploadState>({
    progress: 0,
    status: 'idle',
    error: null,
  })

  const reset = () => setState({ progress: 0, status: 'idle', error: null })

  const upload = async (file: File): Promise<DataFileUploadResult> => {
    if (!ALLOWED_EXTENSIONS.test(file.name)) {
      throw new Error(`Unsupported file type. Allowed: CSV, TSV, JSON, Parquet, NDJSON`)
    }

    setState({ progress: 0, status: 'uploading', error: null })

    // 1. Get presigned PUT URL from backend
    const contentType = file.type || 'text/csv'
    const { upload_url, s3_key, s3_url } = await apiClient.getAnalysisUploadUrl(
      file.name,
      contentType
    )

    // 2. Upload file directly to S3 using XMLHttpRequest for progress tracking
    await new Promise<void>((resolve, reject) => {
      const xhr = new XMLHttpRequest()

      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
          const pct = Math.round((e.loaded / e.total) * 100)
          setState((prev) => ({ ...prev, progress: pct }))
        }
      })

      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve()
        } else {
          reject(new Error(`S3 upload failed with status ${xhr.status}`))
        }
      })

      xhr.addEventListener('error', () => reject(new Error('Network error during upload')))
      xhr.addEventListener('abort', () => reject(new Error('Upload aborted')))

      xhr.open('PUT', upload_url)
      xhr.setRequestHeader('Content-Type', contentType)
      xhr.send(file)
    })

    setState({ progress: 100, status: 'done', error: null })

    return { s3Url: s3_url, s3Key: s3_key, filename: file.name }
  }

  const uploadWithErrorHandling = async (file: File): Promise<DataFileUploadResult | null> => {
    try {
      return await upload(file)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Upload failed'
      setState({ progress: 0, status: 'error', error: msg })
      return null
    }
  }

  return { upload: uploadWithErrorHandling, state, reset }
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd web && pnpm type-check 2>&1 | grep -E "error|Error" | head -20
```

Expected: no errors in the new file

- [ ] **Step 3: Commit**

```bash
cd web && git add components/chat/hooks/useDataFileUpload.ts
git commit -m "feat: add useDataFileUpload hook for direct S3 presigned upload with progress"
```

---

## Task 6: Frontend — "Upload for analysis" button in ChatInput

**Files:**
- Modify: `web/components/chat/components/ChatInput.tsx`

- [ ] **Step 1: Add the hook and state to `ChatInput.tsx`**

Open `web/components/chat/components/ChatInput.tsx`.

Add `BarChart2` to the lucide-react import line (line 6):
```typescript
import {
  Send, Paperclip, Mic, Image as ImageIcon, Smile,
  Bold, Italic, Code, Link as LinkIcon, X, Loader2,
  FileText, File, BarChart2,
} from 'lucide-react'
```

Add the hook import after the existing hook imports (around line 21):
```typescript
import { useDataFileUpload } from '../hooks/useDataFileUpload'
```

Inside the `ChatInput` function body, after the `useFileUpload` line (around line 64), add:
```typescript
  const { upload: uploadForAnalysis, state: analysisUploadState, reset: resetAnalysis } = useDataFileUpload()
  const analysisFileInputRef = useRef<HTMLInputElement>(null)
```

- [ ] **Step 2: Add the handler for analysis file selection**

Inside `ChatInput`, after `handleFileSelect` (around line 150), add:

```typescript
  const handleAnalysisFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (analysisFileInputRef.current) analysisFileInputRef.current.value = ''
    if (!file) return

    const result = await uploadForAnalysis(file)
    if (!result) return  // error state already set in hook

    // Auto-send a prompt with the S3 URL so the agent can start immediately
    const prompt = `I've uploaded **${result.filename}** for analysis.\n\nS3 URL: \`${result.s3Url}\`\n\nPlease analyze this file: describe the schema, row count, and key statistics. Then ask me what analysis I'd like to run.`
    resetAnalysis()
    onSend(prompt)
  }
```

- [ ] **Step 3: Add the "Upload for analysis" button and hidden file input to the JSX**

In the `ChatInput` JSX, find the `<input type="file"` for the regular paperclip (the hidden file input, around line 300+). After it, add:

```tsx
{/* Hidden file input for data analysis uploads */}
<input
  ref={analysisFileInputRef}
  type="file"
  accept=".csv,.tsv,.json,.parquet,.ndjson,.jsonl"
  onChange={handleAnalysisFileSelect}
  className="hidden"
/>
```

Find the toolbar area where the `<Paperclip>` button lives. Add a new button right after it:

```tsx
{/* Upload for analysis button */}
<button
  type="button"
  onClick={() => analysisFileInputRef.current?.click()}
  disabled={disabled || analysisUploadState.status === 'uploading'}
  className={cn(
    'flex h-8 w-8 items-center justify-center rounded-lg transition-colors',
    analysisUploadState.status === 'uploading'
      ? 'text-blue-500'
      : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100',
  )}
  title="Upload file for DuckDB analysis (CSV, JSON, Parquet)"
>
  {analysisUploadState.status === 'uploading' ? (
    <Loader2 size={16} className="animate-spin" />
  ) : (
    <BarChart2 size={16} />
  )}
</button>
```

If `analysisUploadState.status === 'error'`, show the error below the input box. Find the area where `uploadError` is rendered (it renders below the textarea). Add after it:

```tsx
{analysisUploadState.error && (
  <div className="mt-1 flex items-center gap-1.5 text-xs text-red-500">
    <X size={12} />
    {analysisUploadState.error}
  </div>
)}
```

Show upload progress when uploading — add after the error display:

```tsx
{analysisUploadState.status === 'uploading' && (
  <div className="mt-1 flex items-center gap-2 text-xs text-blue-500">
    <Loader2 size={12} className="animate-spin" />
    Uploading for analysis… {analysisUploadState.progress}%
  </div>
)}
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd web && pnpm type-check 2>&1 | grep -E "error|Error" | head -20
```

Expected: no errors

- [ ] **Step 5: Commit**

```bash
cd web && git add components/chat/components/ChatInput.tsx
git commit -m "feat: add Upload for Analysis button to ChatInput (DuckDB CSV flow)"
```

---

## Task 7: Manual end-to-end smoke test

- [ ] **Step 1: Ensure `duckdb` is installed in the API**

```bash
cd api && python -c "import duckdb; print(duckdb.__version__)"
```

If not installed:
```bash
cd api && uv add duckdb
```

- [ ] **Step 2: Start the dev stack**

```bash
# In one terminal
cd api && uvicorn src.app:app --reload --host 0.0.0.0 --port 5001

# In another terminal
cd web && pnpm dev
```

- [ ] **Step 3: Test the presigned URL endpoint**

```bash
curl -s -H "Authorization: Bearer $(python api/get_test_token.py)" \
  "http://localhost:5001/api/v1/data-analysis/upload-presigned-url?filename=test.csv&content_type=text%2Fcsv" | python3 -m json.tool
```

Expected: JSON with `upload_url`, `s3_key`, `s3_url`

- [ ] **Step 4: Upload a small CSV and ask the agent to analyze it**

1. Open `http://localhost:3005/agents/<your-agent>/chat`
2. Click the `BarChart2` icon in the chat input
3. Select a CSV file
4. Watch the progress indicator
5. Confirm the auto-prompt appears: `"I've uploaded filename.csv for analysis. S3 URL: s3://..."`
6. The agent should call `query_file_with_duckdb` and return statistics

- [ ] **Step 5: Verify agent tool execution in lens**

Open the Lens session for the conversation and confirm the `query_file_with_duckdb` tool call appears with the correct `s3_url` and `query` arguments.

---

## Self-Review Checklist

- [x] **Spec coverage:** Presigned upload ✓, DuckDB tool ✓, agent registration ✓, UI button ✓, progress tracking ✓, auto-prompt ✓
- [x] **No placeholders:** All code blocks are complete
- [x] **Type consistency:** `DataFileUploadResult.s3Url` used in hook and consumed in handler; `query_file_with_duckdb` signature matches registration
- [x] **Security:** s3_url validated to `s3://` scheme, no `..` path traversal, query must reference the exact s3_url, content_type allowlisted on endpoint, filename sanitised with regex
- [x] **MinIO:** `AWS_ENDPOINT_URL` drives `s3_endpoint` + `s3_use_ssl=false` + `s3_url_style='path'`
- [x] **Large files:** Browser uploads directly to S3 via presigned PUT — API server never buffers the file body
