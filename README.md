<div align="center">

# Synkora

**Self-hosted AI agent platform. No cloud dependency. No vendor lock-in. Your infrastructure, your LLM keys.**

Deploy agents to Slack, WhatsApp, Teams, Telegram, web widget, and REST API — from one platform. MIT licensed.

[![Live Demo](https://img.shields.io/badge/Live%20Demo-synkora.ai-blue?style=for-the-badge)](https://synkora.ai)
[![Quick Start](https://img.shields.io/badge/Quick%20Start-self--host%20in%20minutes-green?style=for-the-badge)](#quick-start)

---

[![CI Pipeline](https://github.com/getsynkora/synkora-ai/actions/workflows/main-ci.yml/badge.svg)](https://github.com/getsynkora/synkora-ai/actions/workflows/main-ci.yml)
[![API Tests](https://github.com/getsynkora/synkora-ai/actions/workflows/api-tests.yml/badge.svg)](https://github.com/getsynkora/synkora-ai/actions/workflows/api-tests.yml)
[![Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/rajuniit/6adfe45792942ae62d18c5e89128498b/raw/coverage-badge.json)](https://github.com/getsynkora/synkora-ai/actions/workflows/api-tests.yml)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Next.js](https://img.shields.io/badge/Next.js-15.1-black)](https://nextjs.org/)
[![Contributors](https://img.shields.io/github/contributors/getsynkora/synkora-ai)](https://github.com/getsynkora/synkora-ai/graphs/contributors)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

[Features](#key-features) • [Quick Start](#quick-start) • [Documentation](#documentation) • [Contributing](#contributing) • [Community](#support--community)

</div>

---

<div align="center">
  <img src="web/public/images/screenshot-hero.png" alt="Synkora — The AI agent platform your team actually owns" width="100%"/>
</div>

---

## Overview

LangChain gives you building blocks. AutoGen gives you patterns. Synkora gives you the entire platform.

Web UI, multi-tenant workspaces, RAG knowledge bases, 50+ tool integrations, multi-channel deployment, billing, scheduled tasks, HITL approval gates, and LLM observability — all self-hosted on your infrastructure, ready in minutes.

**Why Synkora over building your own stack?**

| | DIY with LangChain/CrewAI | Synkora |
|---|---|---|
| Agent UI | Build it | Included |
| Multi-tenancy | Build it | Built-in |
| RAG pipeline | Build it | Built-in |
| Slack/WhatsApp/Teams bots | Build it | Built-in |
| Billing & quotas | Build it | Built-in |
| Human-in-the-loop approvals | Build it | Built-in |
| LLM cost tracking | Build it | Built-in |
| Self-hosted | Depends | Always |

- **Platform, not a framework** — No infrastructure code to write. Deploy agents from a web UI or REST API in minutes
- **You own it** — Self-host on your own servers. MIT licensed. No vendor lock-in, no phone-home
- **Your LLM keys** — OpenAI, Anthropic, Google, or any provider via LiteLLM. Switch anytime
- **Multi-tenant by design** — Per-tenant isolation, API keys, quotas, and model configs out of the box
- **Deploy everywhere** — Slack, WhatsApp, Teams, Telegram, web widget, REST API — from one platform


## See It In Action

> Try it live at **[synkora.ai](https://synkora.ai)** — no installation required.

<table>
  <tr>
    <td align="center" width="50%">
      <strong>Platform Overview</strong><br><br>
      <img src="web/public/images/screenshot-overview.png" alt="Build LLM Applications in Minutes" width="100%"/>
      <br><em>From agent definition to production deployment in minutes — API access, RAG, tool integrations, and multi-channel delivery.</em>
    </td>
    <td align="center" width="50%">
      <strong>Workspace Dashboard</strong><br><br>
      <img src="web/public/images/screenshot-dashboard-full.png" alt="Synkora Dashboard" width="100%"/>
      <br><em>Full workspace overview — agents, knowledge bases, data sources, MCP servers, and recent activity in one view.</em>
    </td>
  </tr>
  <tr>
    <td align="center" width="50%">
      <strong>Agent Library</strong><br><br>
      <img src="web/public/images/screenshot-agents.png" alt="Agents Library" width="100%"/>
      <br><em>Browse, search, and manage all your agents. Each card shows usage, success rate, and team visibility.</em>
    </td>
    <td align="center" width="50%">
      <strong>Agent Detail & Integrations</strong><br><br>
      <img src="web/public/images/screenshot-agent-detail.png" alt="Agent Detail" width="100%"/>
      <br><em>Per-agent configuration — integrations (Slack, WhatsApp, Telegram, databases), deployment channels, and advanced settings.</em>
    </td>
  </tr>
  <tr>
    <td align="center" width="50%">
      <strong>Live Agent Chat</strong><br><br>
      <img src="web/public/images/screenshot-agent-chat.png" alt="Agent Chat Interface" width="100%"/>
      <br><em>Real-time streaming chat with quick-start action cards, session stats, and inline Lens observability.</em>
    </td>
    <td align="center" width="50%">
      <strong>Autonomous Mode</strong><br><br>
      <img src="web/public/images/screenshot-autonomous-mode.png" alt="Autonomous Mode — Background Automation" width="100%"/>
      <br><em>Schedule agents to run on any cadence — every 5 minutes to custom cron. Set tool budgets and enable Human-in-the-Loop approval.</em>
    </td>
  </tr>
  <tr>
    <td align="center" width="50%">
      <strong>Platform Engineer Agent</strong><br><br>
      <img src="web/public/images/screenshot-platform-engineer.png" alt="Platform Engineer Agent" width="100%"/>
      <br><em>Create and manage agents through conversation. Describe what you want — no forms, no config files.</em>
    </td>
    <td align="center" width="50%">
      <strong>Full Navigation</strong><br><br>
      <img src="web/public/images/screenshot-dashboard.png" alt="Synkora Full Navigation" width="100%"/>
      <br><em>Everything accessible from the sidebar — agents, knowledge bases, data sources, scheduled tasks, integrations, billing, and team management.</em>
    </td>
  </tr>
</table>


## Key Features

### What You Can Build
- **Customer support agents** - 24/7 query handling from your knowledge base, with HITL escalation to humans
- **Engineering assistants** - Code review, bug triage, and documentation via GitHub, GitLab, and Sentry
- **Marketing automation** - Content drafting, campaign analysis, and social scheduling
- **Data agents** - Natural language queries over your databases, automated reports, anomaly detection
- **Internal copilots** - HR, finance, and ops agents connected to your existing tools via 50+ integrations
- **Personal AI assistants** - General-purpose assistants with voice, browser control, and messaging integrations

### Core Capabilities
- **Multi-Provider LLM Support**: OpenAI, Anthropic, Google, and more via LiteLLM — use your own keys
- **Knowledge Bases**: Vector-based knowledge management with Qdrant, Pinecone, and Elasticsearch
- **Custom Tools**: 50+ pre-built integrations plus extensible tool system
- **Real-time Chat**: WebSocket-based chat interface with streaming responses
- **MCP Servers**: Model Context Protocol server integration
- **Voice Services**: ElevenLabs integration for voice interactions

### Enterprise Features
- **Multi-Tenant Architecture**: Complete tenant isolation with role-based access control
- **Billing & Subscriptions**: Stripe integration with plan-based resource limits
- **SSO & Authentication**: Okta SSO, SAML, and social authentication
- **Messaging Bots**: Slack, Microsoft Teams, and WhatsApp bot integrations
- **Data Sources**: Connect to databases, APIs, and external services
- **Widgets**: Embeddable chat widgets for websites
- **Observability**: Langfuse integration for LLM observability and analytics

### Developer Experience
- **RESTful API**: Comprehensive FastAPI-based API with OpenAPI documentation
- **Agent API Keys**: Per-agent API keys for secure access
- **Custom Domains**: Configure custom domains for agents
- **Activity Logs**: Comprehensive audit trail
- **Usage Statistics**: Track usage and performance metrics


## Architecture

> For a comprehensive technical analysis, see [ARCHITECTURE.md](ARCHITECTURE.md)

### System Architecture

```
                    ┌─────────────────────────────────────────┐
                    │              Load Balancer                │
                    └────────────────┬────────────────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
    ┌─────────▼─────────┐ ┌─────────▼─────────┐ ┌─────────▼─────────┐
    │   FastAPI Pod 1    │ │   FastAPI Pod 2    │ │   FastAPI Pod N    │
    │  (API + WebSocket) │ │  (API + WebSocket) │ │  (API + WebSocket) │
    └─────────┬─────────┘ └─────────┬─────────┘ └─────────┬─────────┘
              │                      │                      │
    ┌─────────▼──────────────────────▼──────────────────────▼─────────┐
    │                        Redis (Pub/Sub + Cache)                   │
    └─────────┬──────────────────────┬──────────────────────┬─────────┘
              │                      │                      │
    ┌─────────▼─────────┐ ┌─────────▼─────────┐ ┌─────────▼─────────┐
    │  Celery Workers    │ │  Celery Beat       │ │  Bot Workers       │
    │  (default+billing) │ │  (scheduler)       │ │  (Slack/Telegram)  │
    └─────────┬─────────┘ └───────────────────┘ └─────────┬─────────┘
              │                                            │
    ┌─────────▼──────────────────────────────────────────-▼─────────┐
    │  synkora-ml (embeddings + reranking)                           │
    │  synkora-scraper (browser automation + app-store scraping)     │
    └────────────────────────────────────────────────────────────────┘
              │
    ┌─────────▼──────────────────────────────────────────────────────┐
    │                                                                 │
    │  PostgreSQL (pgvector)  │  Qdrant  │  MinIO/S3  │  Elasticsearch│
    └─────────────────────────────────────────────────────────────────┘
```

### Tech Stack

**Backend:**
- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 14+ with pgvector extension
- **Cache**: Redis 7+
- **Vector DB**: Qdrant, Pinecone, Elasticsearch
- **Task Queue**: Celery with Redis broker
- **ORM**: SQLAlchemy 2.0
- **Migrations**: Alembic
- **Validation**: Pydantic v2

**Frontend:**
- **Framework**: Next.js 15.1 with App Router
- **UI**: React 19, Tailwind CSS
- **State Management**: Zustand
- **HTTP Client**: Axios
- **Forms**: React Hook Form with Zod validation

**Infrastructure:**
- **Containerization**: Docker & Docker Compose
- **Orchestration**: Kubernetes (Helm charts included)
- **Storage**: MinIO (S3-compatible) or AWS S3
- **Observability**: Langfuse for LLM tracking


## Project Structure

```
synkora/
├── api/                    # Backend API (FastAPI)
│   ├── src/
│   │   ├── config/        # Configuration management
│   │   ├── core/          # Core functionality (database, cache, websocket)
│   │   ├── models/        # SQLAlchemy models
│   │   ├── schemas/       # Pydantic schemas
│   │   ├── controllers/   # API route handlers
│   │   ├── services/      # Business logic
│   │   ├── middleware/    # Custom middleware
│   │   └── tasks/         # Celery tasks
│   ├── migrations/        # Alembic database migrations
│   ├── tests/             # Test suite
│   └── pyproject.toml     # Python dependencies
│
├── web/                    # Frontend (Next.js)
│   ├── app/               # Next.js App Router pages
│   ├── components/        # React components
│   ├── lib/               # Utilities and API client
│   ├── hooks/             # Custom React hooks
│   └── types/             # TypeScript type definitions
│
├── services/
│   ├── ml/                # ML microservice (embeddings + reranking)
│   └── scraper/           # Scraper microservice (browser + app-store)
│
├── docker-compose.yml      # Local development environment
├── helm/                   # Kubernetes Helm charts
└── docs/                   # Documentation
```


## Cost Efficiency

Five complementary optimizations reduce LLM API costs. Savings figures are either derived from provider-published pricing or from the benchmark script — no figures are estimated or invented.

| Optimization | Mechanism | Typical Savings | Notes |
|---|---|---|---|
| Anthropic Prompt Caching | `cache_control` injected automatically on system prompt + tools for supported models | ~90% on cached prompt tokens (cache reads billed at 10% of input rate — [Anthropic pricing](https://www.anthropic.com/pricing)) | Automatic — no config needed. LLM still runs fresh; output quality unchanged. |
| OpenAI Automatic Caching | Provider-managed prefix caching; Synkora tracks `cached_tokens` in usage logs | 50% on cached prefix tokens ([OpenAI pricing](https://platform.openai.com/docs/guides/prompt-caching)) | Automatic at provider level. No Synkora configuration required. |
| Response Cache | Redis exact-match cache with 6 correctness gates; bypasses LLM entirely on cache hit | 100% cost saving per cache-hit call | Opt-in: requires `enable_response_cache: true` in agent performance config. Only activates for deterministic calls (temp ≤ 0.1, no tool context, no time-sensitive content). |
| Cost-Opt Routing | Routes queries to the cheapest configured model that passes a complexity gate | Depends on model price gap — no universal figure | `cost_opt` mode in `model_router.py`. Savings vary entirely by which models are configured; no benchmark figure is claimed. |
| Batch API | Submits background LLM jobs via Anthropic/OpenAI batch endpoints via Celery | 50% discount on batch calls ([Anthropic](https://docs.anthropic.com/en/api/messages-batch) / [OpenAI](https://platform.openai.com/docs/guides/batch) published pricing) | Applies to scheduled/async tasks only, not real-time chat. |

### Benchmark Results

> Generated by `api/tests/benchmarks/cost_benchmark.py`. API-dependent tests require `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` — run locally with real keys for live latency numbers.

**Cost calculation** — pricing resolution order: DB routing-rules override → `_BUILTIN_COSTS` → `MODEL_COMPARISON_DATA` → `None` (unknown).

| Model | In tokens | Out tokens | Cache read | Cache write | Input rate | Est. cost (USD) |
|-------|----------:|----------:|-----------:|------------:|:----------:|----------------:|
| `claude-haiku-4-5-20251001` | 1,000 | 500 | 0 | 0 | `$0.00025/1k` | `$0.00275000` |
| `gpt-4o` | 1,000 | 200 | 0 | 0 | `$0.00500/1k` | `$0.00700000` |
| `gpt-4o-mini` | 2,000 | 400 | 0 | 0 | `$0.00500/1k` | `$0.01400000` |
| `claude-haiku-4-5-20251001` (with cache) | 500 | 200 | 300 | 100 | `$0.00025/1k` | `$0.00106375` |
| `claude-sonnet-4-6` (with cache) | 1,000 | 300 | 500 | 200 | `$0.00300/1k` | `$0.00630000` |
| Unknown model | 1,000 | 200 | 0 | 0 | `unknown` | `—` |

**Anthropic prompt-cache savings** — 2,000-token system prompt, 100 requests/day:

| Model | Daily cost (no cache) | Daily cost (with cache) | Saving |
|-------|-----------------------:|------------------------:|-------:|
| `claude-haiku-4-5-20251001` | `$0.050000` | `$0.005575` | **88.9%** |

**Response cache correctness gates** — six gates prevent stale hits:

| Gate | Condition | Result |
|------|-----------|--------|
| Opt-in | `temp=0.0`, role=`user` | ✓ cacheable |
| High temperature | `temp=0.8`, role=`user` | ✓ skipped |
| Tool context | `temp=0.0`, role=`tool` | ✓ skipped |
| Time-sensitive | "what is the current price?" | ✓ skipped |

**Cache key stability** — cache is automatically busted when the agent is edited:

| Scenario | Same key? |
|----------|:---------:|
| Identical inputs | ✓ yes |
| Agent re-saved (`agent_updated_at` changed) | ✓ different |
| System prompt edited | ✓ different |

**Unit tests:** `23/23 passed` — `test_llm_cost_service.py` (10) + `test_llm_response_cache.py` (13).

**Implementation files:**

| Feature | File |
|---------|------|
| Cost calculation + analytics API | `api/src/services/billing/llm_cost_service.py` |
| Per-call token usage persistence (fire-and-forget) | `api/src/services/billing/llm_cost_service.py` |
| LLM response cache (Redis, 6 gates, NX write, 50 KB cap, 1 h TTL) | `api/src/services/cache/llm_response_cache.py` |
| DB model (`llm_token_usage`) | `api/src/models/llm_token_usage.py` |
| Migration | `api/migrations/versions/20260424_0001_add_llm_token_usage.py` |

### Running Benchmarks

```bash
cd api && python -m tests.benchmarks.cost_benchmark --provider anthropic --api-key $ANTHROPIC_API_KEY
cd api && python -m tests.benchmarks.cost_benchmark --provider openai --api-key $OPENAI_API_KEY
```

### Comparison vs Other Platforms

> **Research methodology:** Each platform was investigated against its official docs, GitHub issues/PRs, and changelogs as of April 2026. Every cell is sourced — see footnotes. Legend: ✅ Native built-in feature · ⚡ Partial (manual setup or limited scope) · ❌ Not supported

| Feature | Synkora | Dify | Flowise | LangFlow | n8n |
|---------|:-------:|:----:|:-------:|:--------:|:---:|
| **Anthropic prompt caching** (`cache_control`) | ✅ | ⚡ [¹](#fn1) | ❌ [²](#fn2) | ❌ [³](#fn3) | ⚡ [⁴](#fn4) |
| **LLM response cache** (Redis exact-match) | ✅ | ⚡ [⁵](#fn5) | ✅ [⁶](#fn6) | ❌ [⁷](#fn7) | ⚡ [⁸](#fn8) |
| **Smart model routing** (complexity/cost-based) | ✅ | ⚡ [⁹](#fn9) | ⚡ [⁹](#fn9) | ⚡ [¹⁰](#fn10) | ⚡ [⁹](#fn9) |
| **Batch API** (Anthropic / OpenAI async 50% discount) | ✅ | ❌ [¹¹](#fn11) | ❌ [¹²](#fn12) | ❌ [¹³](#fn13) | ⚡ [¹⁴](#fn14) |
| **Per-call token & USD cost tracking** | ✅ | ✅ [¹⁵](#fn15) | ⚡ [¹⁶](#fn16) | ⚡ [¹⁷](#fn17) | ⚡ [¹⁸](#fn18) |

#### Footnotes

<a name="fn1"></a>**¹ Dify prompt caching** — Anthropic only, via official plugin v0.3.10 (Apr 2026). Six opt-in per-call parameters (`prompt_caching_system_message`, `prompt_caching_tool_definitions`, etc.) in the LLM node UI. OpenAI prefix caching is transparent at provider level (Dify does nothing special). Gemini explicitly declined as "not planned" ([issue #2121](https://github.com/langgenius/dify-official-plugins/issues/2121)). Known bug: Haiku 4.5 cache shows 0% ([issue #1946](https://github.com/langgenius/dify-official-plugins/issues/1946)).

<a name="fn2"></a>**² Flowise prompt caching** — No `cache_control` implementation. Open feature request [#4634](https://github.com/FlowiseAI/Flowise/issues/4634) with no maintainer commitment. GitHub code search returns 0 matches for `cache_control` in the repo.

<a name="fn3"></a>**³ LangFlow prompt caching** — No native support. A LangFlow blog post titled "Prompt Caching in LLMs" is educational only — it describes no LangFlow feature. LangChain's `AnthropicPromptCachingMiddleware` exists but is not exposed as a built-in LangFlow node.

<a name="fn4"></a>**⁴ n8n prompt caching** — Anthropic `cache_control` (4-breakpoint strategy) was merged for the internal AI Workflow Builder ([PR #20484](https://github.com/n8n-io/n8n/pull/20484), Oct 2025). The user-facing Anthropic Chat Model node PR ([#22318](https://github.com/n8n-io/n8n/pull/22318)) was still open as of Apr 2026.

<a name="fn5"></a>**⁵ Dify response cache** — No generic Redis-backed LLM output cache. The nearest equivalent is **Annotation Reply**: a manually curated Q&A store with vector-similarity matching that short-circuits LLM calls. A workflow-level caching feature request ([#23598](https://github.com/langgenius/dify/issues/23598)) was closed "not planned" Sep 2025.

<a name="fn6"></a>**⁶ Flowise response cache** — Documented, shipped feature. LangChain cache layer with four backends: InMemory, Redis, Upstash Redis, Momento. Connected to LLM nodes as an optional "Cache" input. ([docs](https://docs.flowiseai.com/integrations/langchain/cache))

<a name="fn7"></a>**⁷ LangFlow response cache** — No LLM output deduplication cache exists. The in-memory cache is for internal flow-graph state (component outputs within a run), not LLM response deduplication. Redis is documented as "experimental" for flow caching only.

<a name="fn8"></a>**⁸ n8n response cache** — No first-class cache node. Achievable via Redis Vector Store node + manual workflow logic ([community template](https://n8n.io/workflows/10887-reduce-llm-costs-with-semantic-caching-using-redis-vector-store-and-huggingface/)), but requires authoring, not a one-click setting.

<a name="fn9"></a>**⁹ Dify / Flowise / n8n model routing** — All three provide routing primitives (If/Else nodes, Condition nodes, Switch nodes) that can be manually wired to route to different models. None has a built-in automatic complexity classifier that routes to a cheaper model. n8n community has a [workflow template](https://n8n.io/workflows/4237-dynamic-ai-model-router-for-query-optimization-with-openrouter/) using OpenRouter for this.

<a name="fn10"></a>**¹⁰ LangFlow model routing** — Shipped a real **LLM Router / LLM Selector** component in v1.7 ([PR #5475](https://github.com/langflow-ai/langflow/pull/5475), Jan 2025) that uses OpenRouter's model-spec API and a judge LLM to pick among attached models by quality/speed/cost/balanced. Requires OpenRouter; incurs a live LLM judgment call per routing decision.

<a name="fn11"></a>**¹¹ Dify batch API** — Explicitly declined as "not planned" ([issue #13126](https://github.com/langgenius/dify/issues/13126), closed Mar 18, 2025).

<a name="fn12"></a>**¹² Flowise batch API** — No evidence of Anthropic Message Batches or OpenAI Batch API integration. The `batchSize` field in the OpenAI node is LangChain-internal concurrency (embedding chunking), not the provider batch endpoint. Async response confirmed "not currently supported" ([discussion #1212](https://github.com/FlowiseAI/Flowise/discussions/1212)).

<a name="fn13"></a>**¹³ LangFlow batch API** — No support. LangFlow's `/v1/flows/batch/` endpoint is for creating/deleting multiple flow definitions, not for submitting LLM calls to provider batch APIs.

<a name="fn14"></a>**¹⁴ n8n batch API** — Anthropic batch API is accessible via an HTTP Request node using a [community workflow template](https://n8n.io/workflows/3409-batch-process-prompts-with-anthropic-claude-api/). No dedicated node. OpenAI Batch API requires the same workaround.

<a name="fn15"></a>**¹⁵ Dify token & cost tracking** — Per-node: `execution_metadata.total_tokens`, `total_price` (USD), `currency` in the `node_finished` SSE event ([issue #8873](https://github.com/langgenius/dify/issues/8873)). Visible in Run History / Debug view. Cache-aware: `cache_creation_input_tokens` (1.25×) and `cache_read_input_tokens` (0.1×) tracked in Anthropic plugin. Caveat: shows $0 for OpenAI-compatible third-party models without `PLUGIN_BASED_TOKEN_COUNTING_ENABLED=true`; fixed in v1.9.2+.

<a name="fn16"></a>**¹⁶ Flowise token & cost tracking** — Token data is generated internally but only surfaced via third-party observability integrations (Langfuse, LangSmith, LunaryAI, LangWatch, Arize, Phoenix, Opik). No native per-call USD cost display in Flowise UI. Non-OpenAI providers (Gemini, DeepSeek) have incomplete cost data in traces ([Langfuse issue #8293](https://github.com/langfuse/langfuse/issues/8293)).

<a name="fn17"></a>**¹⁷ LangFlow token & cost tracking** — Token counts added to the inspection UI in v1.8 ([blog](https://www.langflow.org/blog/langflow-1-8)) and available in the OpenAI Responses API path. USD cost requires Langfuse / LangSmith / LangWatch integration; not calculated natively. Earlier feature request ([#3261](https://github.com/langflow-ai/langflow/issues/3261)) was closed "not planned" Nov 2024.

<a name="fn18"></a>**¹⁸ n8n token & cost tracking** — Token data is in the raw model output for providers that return it (OpenAI, Anthropic, Google) but not displayed natively in the n8n execution UI. Per-call tracking and a cost dashboard require a custom subworkflow ([community template](https://n8n.io/workflows/7398-llm-usage-tracker-and-cost-monitor-with-node-level-analytics-v2/)).

---

## Quick Start

### One-Line Install (Recommended)

Run the interactive installer — it handles everything: prerequisite checks, `.env` generation, database migrations, seeding, and starting all services.

```bash
curl -fsSL https://raw.githubusercontent.com/getsynkora/synkora-ai/main/get.sh | bash
```

Installs into `~/synkora-ai` by default. To choose a different directory:

```bash
curl -fsSL https://raw.githubusercontent.com/getsynkora/synkora-ai/main/get.sh | \
  SYNKORA_INSTALL_DIR=~/my-synkora bash
```

For CI/CD and server deployments (no prompts):

```bash
curl -fsSL https://raw.githubusercontent.com/getsynkora/synkora-ai/main/get.sh | \
  SYNKORA_ADMIN_EMAIL=admin@example.com \
  SYNKORA_ADMIN_PASSWORD=securepass123 \
  SYNKORA_LLM_PROVIDER=openai \
  SYNKORA_LLM_API_KEY=sk-... \
  bash -s -- --non-interactive
```

The installer will:
1. Check system resources (RAM, CPU, disk) and warn if below minimums
2. Verify Docker, openssl, Node.js/pnpm are present (and offer to install Docker if missing)
3. Detect existing installations and offer Upgrade / Reset / Quit
4. Collect admin account details, LLM provider key, and optional Slack bot tokens
5. Generate all `.env` files with secure random secrets
6. Pull images, start services, run migrations, seed plans/roles/template agents
7. Print a summary with all URLs and management commands

### Manual Setup (Docker Compose)

If you prefer to set up manually:

```bash
# 1. Copy and edit environment files
cp api/.env.example api/.env
# Edit api/.env with your configuration

# 2. Start all services
docker compose up -d

# 3. Initialize the database
docker compose exec api alembic upgrade head
docker compose exec api python create_super_admin.py
docker compose exec api python seed_platform_config.py
```

### Prerequisites

- Docker and Docker Compose v2
- Node.js 20+ and pnpm (for local frontend development)
- Python 3.11+ and uv (for local backend development)

### Local Development

#### Backend Setup

```bash
cd api

# Install dependencies (using uv)
uv sync

# Or using pip
pip install -e .

# Set up environment
cp .env.example .env
# Edit .env with your configuration

# Initialize database
alembic upgrade head
python create_super_admin.py
python seed_platform_config.py

# Run development server
uvicorn src.app:app --reload --host 0.0.0.0 --port 5001
```

#### Frontend Setup

```bash
cd web

# Install dependencies
pnpm install

# Set up environment
cp .env.example .env.local
# Edit .env.local if needed

# Run development server
pnpm dev
```


## Configuration

### Environment Variables

#### Backend (`api/.env`)
```bash
# Database
DATABASE_URL=postgresql://synkora:synkora@localhost:5432/synkora

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-secret-key
JWT_SECRET_KEY=your-jwt-secret
ENCRYPTION_KEY=your-encryption-key

# Application
APP_ENV=development
API_HOST=0.0.0.0
API_PORT=5001

# Storage
STORAGE_PROVIDER=s3
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin
AWS_ENDPOINT_URL=http://localhost:9000
AWS_BUCKET_NAME=synkora-storage

# LLM Providers (optional)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Langfuse (optional)
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
LANGFUSE_HOST=http://localhost:3001
```

#### Frontend (`web/.env.local`)
```bash
NEXT_PUBLIC_API_URL=http://localhost:5001
NEXT_PUBLIC_APP_URL=http://localhost:3005
```


## Documentation

- [Architecture Report](ARCHITECTURE.md) - Comprehensive technical analysis, design patterns, and scorecard
- [API Documentation](api/README.md) - Backend API details and setup
- [Frontend Documentation](web/README.md) - Frontend setup and development
- [Contributing Guidelines](CONTRIBUTING.md) - How to contribute
- [Security Policy](SECURITY.md) - Security guidelines and reporting
- [Changelog](CHANGELOG.md) - Version history and changes
- [Load Testing Guide](api/tests/load/README.md) - k6 load testing suite documentation


## Testing

### CI/CD Pipeline

Our CI/CD pipeline runs on every push and pull request:

| Workflow | Description | Status |
|----------|-------------|--------|
| **Main CI** | Orchestrates all tests | [![CI Pipeline](https://github.com/getsynkora/synkora-ai/actions/workflows/main-ci.yml/badge.svg)](https://github.com/getsynkora/synkora-ai/actions/workflows/main-ci.yml) |
| **API Tests** | Python unit & integration tests | [![API Tests](https://github.com/getsynkora/synkora-ai/actions/workflows/api-tests.yml/badge.svg)](https://github.com/getsynkora/synkora-ai/actions/workflows/api-tests.yml) |
| **Web Tests** | Frontend linting & type checks | [![Web Tests](https://github.com/getsynkora/synkora-ai/actions/workflows/web-tests.yml/badge.svg)](https://github.com/getsynkora/synkora-ai/actions/workflows/web-tests.yml) |
| **Style Check** | Code formatting & linting | [![Style](https://github.com/getsynkora/synkora-ai/actions/workflows/style.yml/badge.svg)](https://github.com/getsynkora/synkora-ai/actions/workflows/style.yml) |
| **Docker Build** | Container build validation | [![Docker](https://github.com/getsynkora/synkora-ai/actions/workflows/docker-build.yml/badge.svg)](https://github.com/getsynkora/synkora-ai/actions/workflows/docker-build.yml) |

### Code Coverage

[![Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/rajuniit/6adfe45792942ae62d18c5e89128498b/raw/coverage-badge.json)](https://github.com/getsynkora/synkora-ai/actions/workflows/api-tests.yml)

Coverage reports are generated for every pull request with inline annotations.

### Backend Tests
```bash
cd api
pytest                              # Run all tests
pytest --cov=src                    # With coverage
pytest --cov=src --cov-report=html  # Generate HTML coverage report
pytest tests/unit/                  # Unit tests only
pytest tests/integration/           # Integration tests only
pytest -v -k "test_name"            # Run specific test
pytest -x                           # Stop on first failure
```

### Frontend Tests
```bash
cd web
pnpm test                # Run tests
pnpm type-check          # TypeScript type checking
pnpm lint                # ESLint
```

### Running Tests Locally with Act

You can run GitHub Actions locally using [act](https://github.com/nektos/act):

```bash
# Install act (macOS)
brew install act

# Run API tests locally
act workflow_dispatch -W .github/workflows/api-tests.yml -j test --matrix python-version:3.11 -P ubuntu-latest=catthehacker/ubuntu:act-latest --container-architecture linux/amd64
```


## Development

### Database Migrations

```bash
# Create a new migration
cd api
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Code Quality

**Backend:**
```bash
cd api
ruff format .           # Format code
ruff check .            # Lint code
basedpyright            # Type checking
```

**Frontend:**
```bash
cd web
pnpm lint               # ESLint
pnpm type-check         # TypeScript
```

### Adding Dependencies

**Backend:**
```bash
cd api
uv add package-name              # Production dependency
uv add --dev package-name        # Development dependency
```

**Frontend:**
```bash
cd web
pnpm add package-name            # Production dependency
pnpm add -D package-name         # Development dependency
```


## Deployment

### Docker Compose

```bash
# Build all images
docker-compose build

# Start all services
docker-compose up -d
```

### Kubernetes

Helm charts are provided in the `helm/` directory:

```bash
# Install
helm install synkora ./helm/synkora

# Upgrade
helm upgrade synkora ./helm/synkora

# Uninstall
helm uninstall synkora
```


## System Requirements

Synkora runs ~20 Docker containers. The installer checks your system and warns if below minimums.

### Hardware

| | Minimum | Recommended |
|---|---------|-------------|
| **RAM** | 16 GB | 32 GB |
| **CPU** | 4 cores | 8+ cores |
| **Free disk** | 40 GB | 100 GB |
| **OS** | macOS 12+, Ubuntu 20.04+, Debian 11+, Fedora 36+, RHEL 8+ | — |

> **Why so much RAM?** Elasticsearch is hard-capped at 2 GB. Redis is configured for up to 2 GB. The ML service loads sentence-transformer models (~1–2 GB). Total idle: ~10–12 GB plus OS overhead.

<details>
<summary>Per-service resource breakdown</summary>

| Service | RAM (idle) | Purpose |
|---------|-----------|---------|
| `elasticsearch` | ~1.5 GB | Full-text search (hard limit: 2 GB) |
| `redis` | up to 2 GB | Cache, Celery broker, pub/sub |
| `synkora-ml` | ~1–2 GB | Embeddings + reranking (sentence-transformers) |
| `synkora-scraper` | ~512 MB | Browser automation (Playwright + Chromium) |
| `langfuse-clickhouse` | ~512 MB | LLM observability analytics |
| `langfuse-web` + `langfuse-worker` | ~512 MB | Langfuse UI + background jobs |
| `api` | ~512 MB | FastAPI application server |
| `celery-worker` (×4 workers) | ~1.5 GB | Background tasks |
| `postgres` + `postgres-test` | ~384 MB | PostgreSQL with pgvector |
| `qdrant` | ~256 MB | Vector database |
| `minio` | ~256 MB | S3-compatible object storage |
| `bot-worker`, `celery-beat`, `docs` | ~384 MB | Slack bots, scheduler, docs |
| **Total** | **~10–12 GB** | Plus OS + Docker daemon (~2–3 GB overhead) |

</details>

<details>
<summary>Required software and ports</summary>

| Tool | Version | Required for |
|------|---------|-------------|
| Docker Engine | 24+ | All services |
| Docker Compose v2 | 2.20+ | Orchestration |
| Node.js | 20+ | Frontend (local dev only) |
| pnpm | 8+ | Frontend (local dev only) |
| openssl | any | Secret key generation |

| Port | Service |
|------|---------|
| `3005` | Web frontend |
| `5001` | API (FastAPI) |
| `3001` | Langfuse UI |
| `9001` | MinIO console |
| `6333` | Qdrant HTTP |
| `9200` | Elasticsearch |
| `5438` | PostgreSQL |
| `6379` | Redis (localhost only) |

All ports are configurable in `docker-compose.yml`.

</details>


## Security

> Detailed in [ARCHITECTURE.md — Security](ARCHITECTURE.md#security)

- **Authentication**: JWT with token blacklisting, version tracking, and secure sessionStorage
- **Authorization**: Role-based access control (RBAC) with fine-grained permissions and tenant isolation
- **CSRF Protection**: Server-side token validation in Redis with session binding and fail-closed design
- **Security Headers**: CSP with nonces, HSTS with preload, X-Frame-Options DENY, Permissions-Policy
- **Input Sanitization**: 60+ XSS pattern detection covering HTML5 event handlers
- **Encryption**: Fernet encryption at rest for API keys, OAuth tokens, and secrets
- **Rate Limiting**: Redis-backed distributed rate limiting with per-endpoint configuration
- **SSO**: Okta and SAML support for enterprise authentication


## Monitoring & Observability

- **Langfuse**: LLM observability, tracing, and analytics
- **Prometheus Metrics**: `/metrics` endpoint for scraping (request counts, latencies, LLM usage)
- **Performance Stats**: `/api/v1/stats/performance` for connection pools, circuit breakers
- **Health Checks**: `/health` endpoint for liveness probes
- **Logging**: Structured JSON logging with configurable levels


## Performance & Scalability

> Detailed in [ARCHITECTURE.md — Scalability](ARCHITECTURE.md#scalability--horizontal-scaling)

- **Stateless API**: All state in PostgreSQL/Redis, enabling horizontal pod scaling
- **Distributed WebSocket**: Redis pub/sub for cross-pod message delivery with source-pod deduplication
- **Distributed Cache**: Cross-pod cache invalidation via Redis pub/sub
- **Circuit Breakers**: Full state machine (CLOSED/OPEN/HALF_OPEN) with decorator API
- **Connection Pooling**: 50+25 DB connections, 200 Redis connections, pooled vector DB clients
- **Celery Queue Separation**: Default, email, notifications, agents, billing queues with dedicated workers
- **Streaming Uploads**: Multipart S3 uploads for large files without memory overhead
- **Async Database**: Dual engine architecture (asyncpg for FastAPI, psycopg2 for Celery)

### Load Test Results (Stress Test @ 300 VUs)

| Metric | Target | Achieved | Status |
|--------|--------|----------|--------|
| Health check p95 | < 100ms | 42ms | Pass |
| List agents p95 | < 500ms | 198ms | Pass |
| Chat stream p95 | < 5s | 2.8s | Pass |
| KB search p95 | < 1s | 342ms | Pass |
| Error rate | < 5% | 0.8% | Pass |

See [Load Testing Guide](api/tests/load/README.md) for running your own tests.


## Contributing

We welcome contributions from the community! Whether you're fixing bugs, improving documentation, or proposing new features, your help is appreciated.

### How to Contribute

1. **Fork the repository** and create your branch from `main`
2. **Make your changes** following our coding standards
3. **Add tests** for any new functionality
4. **Run the test suite** to ensure everything passes
5. **Update documentation** as needed
6. **Submit a pull request** with a clear description of your changes

Please read our [Contributing Guidelines](CONTRIBUTING.md) for detailed information.

### Code of Conduct

This project adheres to a [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

### Development Setup

See the [Quick Start](#quick-start) section for development environment setup instructions.


## Bug Reports & Feature Requests

- **Bug Reports**: [Submit a bug report](.github/ISSUE_TEMPLATE/bug_report.md)
- **Feature Requests**: [Request a feature](.github/ISSUE_TEMPLATE/feature_request.md)
- **Security Issues**: See our [Security Policy](SECURITY.md)


## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

You are free to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of this software for any purpose, including commercial use, without restriction.


## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a list of changes and version history.


## Acknowledgments

Built with amazing open source technologies:
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [Next.js](https://nextjs.org/) - React framework
- [LiteLLM](https://github.com/BerriAI/litellm) - LLM provider integration
- [Langfuse](https://langfuse.com/) - LLM observability
- [Qdrant](https://qdrant.tech/) - Vector database
- And many more! See [package files](api/pyproject.toml) for complete list


## Support & Community

- **Live Demo**: [synkora.ai](https://synkora.ai)
- **Documentation**: [docs/](docs/) — architecture, API reference, guides
- **API Reference**: Interactive docs at `/api/v1/docs` when running locally
- **GitHub Discussions**: [Ask questions, share ideas, show what you built](https://github.com/getsynkora/synkora-ai/discussions)
- **Issues**: [Report bugs or request features](https://github.com/getsynkora/synkora-ai/issues)
- **Security**: Report vulnerabilities via our [Security Policy](SECURITY.md)


## Roadmap

See [CHANGELOG.md](CHANGELOG.md) for recent changes and version history.

### Upcoming Features
- Agent monetization — let creators publish and charge for agents
- Enhanced multi-agent workflow orchestration
- Visual workflow DAG editor
- Improved knowledge base search with hybrid retrieval
- Multi-language UI support
- Additional LLM provider integrations


## Project Status

Synkora is actively maintained and in production use. We follow semantic versioning and maintain backward compatibility wherever possible.

- **Stability**: Production-ready
- **Maintenance**: Actively maintained
- **Release Cycle**: Regular updates and security patches

---


<div align="center">

**[synkora.ai](https://synkora.ai)** · **[Documentation](docs/)** · **[Discussions](https://github.com/getsynkora/synkora-ai/discussions)** · **[Issues](https://github.com/getsynkora/synkora-ai/issues)**

If Synkora saves you time, a star helps others find it.

[Back to Top](#synkora)

</div>
