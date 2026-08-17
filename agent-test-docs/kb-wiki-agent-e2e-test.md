# End-to-End Test: KB Wiki Auto-Compile + Agent RAG

## Overview

Tests the full pipeline:
1. Upload document to KB → auto-compile wiki → embed wiki into vector store → agent retrieves via RAG

## Prerequisites

- API running on `http://localhost:5001`
- Celery workers running (`synkora-celery-worker`, `synkora-celery-worker-agents`)
- Qdrant or Pinecone vector store connected
- At least one KB with existing wiki articles (KB 1 used here)
- At least one agent with KB attached (Coding Agent 2 used here)

---

## Step 1 — Get Auth Token

```python
python3 -c "
import urllib.request, json
data = json.dumps({'email': 'admin@localhost.com', 'password': 'Admin123!'}).encode()
req = urllib.request.Request(
    'http://localhost:5001/console/api/auth/login',
    data=data,
    headers={'Content-Type': 'application/json'},
    method='POST'
)
with urllib.request.urlopen(req) as r:
    d = json.loads(r.read())
    print(d['data']['access_token'])
"
```

Note: email is `admin@localhost.com` (confirmed via DB: `SELECT email FROM accounts WHERE is_platform_admin='true'`).

---

## Step 2 — Verify Celery Workers Have New Tasks Registered

```bash
podman logs --tail 30 synkora-celery-worker-agents 2>&1 | grep "tasks\."
```

Expected to see:
```
. tasks.compile_single_knowledge_wiki
. tasks.embed_wiki_documents
. tasks.process_kb_documents
```

If workers are stale after code changes, restart them:
```bash
podman restart synkora-celery-worker synkora-celery-worker-agents
sleep 5
```

---

## Step 3 — Check Existing Knowledge Bases

```python
python3 -c "
import urllib.request, json
TOKEN = '<your_token>'
req = urllib.request.Request('http://localhost:5001/api/v1/knowledge-bases',
    headers={'Authorization': f'Bearer {TOKEN}'})
with urllib.request.urlopen(req) as r:
    d = json.loads(r.read())
    items = d.get('data', d) if isinstance(d, dict) else d
    for kb in (items if isinstance(items, list) else []):
        print(f\"KB {kb.get('id')}: {kb.get('name')} — docs: {kb.get('total_documents',0)}\")
"
```

KB 1 (`Company Wiki Test`) is the primary test KB with existing wiki articles.

---

## Step 4 — Check Existing Wiki Articles

```python
python3 -c "
import urllib.request, json
TOKEN = '<your_token>'
req = urllib.request.Request('http://localhost:5001/api/v1/knowledge-bases/1/wiki',
    headers={'Authorization': f'Bearer {TOKEN}'})
with urllib.request.urlopen(req) as r:
    d = json.loads(r.read())
    items = d.get('articles', d.get('data', d))
    if isinstance(items, list):
        print(f'Found {len(items)} wiki articles:')
        for a in items[:5]:
            print(f\"  [{a.get('id','?')[:8]}] {a.get('title')} — {a.get('status')}\")
"
```

---

## Step 5 — Upload a Text Document to KB 1

This triggers the auto-compile chain if KB already has wiki articles.

```python
python3 -c "
import urllib.request, json
TOKEN = '<your_token>'
payload = json.dumps({
    'title': 'Auto-compile test doc',
    'content': 'This is a test document about our deployment process. We use Kubernetes for container orchestration. The CI/CD pipeline is built on GitHub Actions. Deployments are automated and happen every sprint. The SRE team owns the pipeline and monitors uptime via Datadog.'
}).encode()
req = urllib.request.Request(
    'http://localhost:5001/api/v1/knowledge-bases/1/documents/text',
    data=payload,
    headers={'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'},
    method='POST'
)
with urllib.request.urlopen(req) as r:
    print(r.read().decode())
"
```

Expected response:
```json
{"success":true,"message":"Text content 'Auto-compile test doc' queued for processing",...}
```

---

## Step 6 — Watch the Auto-Compile Chain in Worker Logs

### Default worker — processes the document upload:
```bash
podman logs --since 2m synkora-celery-worker 2>&1 | grep -E "process_kb|KB document|Triggered|wiki"
```

Expected output:
```
Task tasks.process_kb_documents[...] received
KB document processing done for data_source=2: {'success': True, 'documents_processed': 1, ...}
Triggered wiki recompile for KB 1
Task tasks.process_kb_documents[...] succeeded in 10.5s
```

### Agents worker — runs compile + embed:
```bash
podman logs --since 3m synkora-celery-worker-agents 2>&1 | grep -E "compile|embed|articles|Queued|Embedded|Wiki embedding"
```

Expected output (in order):
```
Task tasks.compile_single_knowledge_wiki[...] received
Compilation KB=1: N docs, N segments, N with content
Calling LLM provider=litellm model=claude-sonnet-4-6 ...
Updated staleness for N articles in KB 1
Queued wiki embedding for KB 1
Task tasks.embed_wiki_documents[...] received
Embedded wiki article 'CI/CD and Deployment Pipeline' (1 chunks) into KB 1
...
Wiki embedding complete for KB 1: 32/32 articles embedded
Task tasks.embed_wiki_documents[...] succeeded in 80s
```

---

## Step 7 — Verify Wiki Documents in DB

```bash
python3 -c "
import subprocess
result = subprocess.run(
  ['podman','exec','synkora-postgres','psql','-U','synkora','-d','synkora','-c',
   \"SELECT source_type, COUNT(*) as count, SUM(char_count) as total_chars FROM documents WHERE knowledge_base_id = 1 GROUP BY source_type ORDER BY source_type;\"],
  capture_output=True, text=True
)
print(result.stdout)
"
```

Expected output:
```
 source_type | count | total_chars
-------------+-------+-------------
 MANUAL      |     9 |       10720
 WEB         |     1 |        3594
 wiki        |    32 |       55670
```

The `wiki` rows confirm articles were embedded as searchable Documents.

---

## Step 8 — Ensure Agent Has KB Attached

Check via DB:
```bash
python3 -c "
import subprocess
result = subprocess.run(
  ['podman','exec','synkora-postgres','psql','-U','synkora','-d','synkora','-c',
   \"SELECT a.agent_name, akb.knowledge_base_id FROM agents a LEFT JOIN agent_knowledge_bases akb ON akb.agent_id = a.id WHERE lower(a.agent_name) LIKE '%coding agent 2%';\"],
  capture_output=True, text=True
)
print(result.stdout)
"
```

If not attached, attach via API:
```python
python3 -c "
import urllib.request, json
TOKEN = '<your_token>'
AGENT_ID = '27767a48-7e59-48fa-906c-4c723acdd446'  # Coding Agent 2
payload = json.dumps({'knowledge_base_id': 1}).encode()
req = urllib.request.Request(
    f'http://localhost:5001/api/v1/agents/{AGENT_ID}/knowledge-bases',
    data=payload,
    headers={'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'},
    method='POST'
)
with urllib.request.urlopen(req) as r:
    print(r.read().decode()[:300])
"
```

---

## Step 9 — Chat with Agent and Verify KB is Used

```python
python3 -c "
import urllib.request, json
TOKEN = '<your_token>'

payload = json.dumps({
    'agent_name': 'Coding Agent 2',
    'message': 'What do you know about our CI/CD and deployment pipeline? How do deployments work?'
}).encode()

req = urllib.request.Request(
    'http://localhost:5001/api/v1/agents/chat/stream',
    data=payload,
    headers={'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'},
    method='POST'
)

with urllib.request.urlopen(req, timeout=60) as r:
    for line in r:
        line = line.decode('utf-8').strip()
        if line.startswith('data: '):
            data = line[6:]
            if data == '[DONE]':
                break
            try:
                obj = json.loads(data)
                chunk = obj.get('content','') or obj.get('text','') or obj.get('delta','') or obj.get('chunk','')
                if chunk:
                    print(chunk, end='', flush=True)
            except Exception:
                pass
print()
"
```

### What to look for in the response:

1. **`Searching knowledge bases...`** — confirms RAG ran
2. **Accurate content** — Kubernetes, GitHub Actions, sprint cadence, SRE, Datadog (from the uploaded doc)
3. **Sources line** — e.g. `*Sources: CI/CD and Deployment Pipeline wiki doc, Auto-compile test doc*`
   - `CI/CD and Deployment Pipeline wiki doc` = wiki article (compiled + embedded)
   - `Auto-compile test doc` = original raw document

Both sources being cited confirms the wiki RAG path and raw doc RAG path both work.

---

## Key Agent / Resource IDs (local dev)

| Resource | Name | ID |
|----------|------|----|
| Knowledge Base | Company Wiki Test | `1` |
| Agent | Coding Agent 2 | `27767a48-7e59-48fa-906c-4c723acdd446` |
| Tenant | synkora | `f56a839a-a62b-430f-9439-408dc9e38a64` |

---

## What the Auto-Compile Chain Does

```
Document uploaded to KB
  → process_kb_documents (default Celery queue)
      → DocumentProcessor embeds raw content into vector store
      → checks: does KB have any wiki articles?
        YES → compile_single_knowledge_wiki.delay(kb_id, tenant_id)
                  → KnowledgeCompiler.compile()
                    → LLM extracts/refreshes wiki articles from all KB docs
                    → saves WikiArticle records to DB
                    → embed_wiki_documents.delay(kb_id, tenant_id)
                        → creates/updates Document records (source_type="wiki")
                        → chunks + embeds each wiki article
                        → upserts to vector store (deterministic IDs, idempotent)
                        → agents now retrieve wiki content via RAG automatically
```

## Notes

- Auto-compile only fires if KB **already has** wiki articles. First compile must be done manually via the UI.
- Wiki articles are stored as `Document` records with `source_type="wiki"` and `external_id="wiki:{slug}"`.
- Vector IDs are deterministic (`wiki-{kb_id}-{article_id}-seg-{i}`) so re-embedding is idempotent.
- Both raw docs and wiki articles appear in agent RAG results — they are complementary, not duplicates.
