---
sidebar_position: 1
slug: /
---

# Welcome to Synkora

Synkora is an open-source, multi-tenant **LLM application platform** for building, deploying, and operating AI agents.

It is designed for teams that need more than a framework and more than a single chat UI. Synkora gives you a control plane for agents: web UI, API, knowledge bases, tools, messaging surfaces, billing, scheduling, and observability in one system.

## What Synkora Includes

- A Next.js dashboard for creating and managing agents
- A FastAPI backend with streaming chat, tenant-aware APIs, and role-based access
- Knowledge bases with PostgreSQL + pgvector and optional Qdrant, Pinecone, or Elasticsearch
- Tooling via built-in tools, OAuth-backed integrations, custom tools, and MCP servers
- Deployment surfaces across web widget, REST API, Slack, WhatsApp, Teams, Telegram, and browser/mobile companion surfaces
- Background execution with Redis + Celery for ingestion, automation, retries, and scheduling
- Usage tracking, credits, subscriptions, and observability integrations

## What Synkora Is Not

Synkora is **not**:

- just a prompt playground
- just an orchestration framework
- just a website chat widget
- just a low-code builder

It sits one layer above model SDKs and one layer below your product-specific workflows.

## Start Here

- [Quick Start](/docs/getting-started/quick-start): get a local environment running fast
- [Installation](/docs/getting-started/installation): choose the right install path
- [Create Your First Agent](/docs/getting-started/first-agent): go from blank workspace to working agent
- [Agents](/docs/concepts/agents): understand the core product model
- [Architecture Overview](/docs/architecture/overview): see how the platform is structured

## Core Ideas

### Platform, not framework

Synkora is meant to help teams ship AI products without rebuilding the same platform layer over and over.

### Multi-tenant by design

Tenant isolation, quotas, API keys, usage, and billing are built into the platform model from the start.

### Bring your own model stack

Synkora uses LiteLLM so you can work with OpenAI, Anthropic, Google, and other providers without tying the entire platform to one vendor.

### Deploy where work already happens

Agents are useful only if they can show up in the right place. Synkora supports web, API, and messaging surfaces, and the repo also includes a Chrome extension and Flutter chat SDK for companion experiences.

## Recommended Reading Order

1. [Quick Start](/docs/getting-started/quick-start)
2. [Configuration](/docs/getting-started/configuration)
3. [Agents](/docs/concepts/agents)
4. [Knowledge Bases](/docs/concepts/knowledge-bases)
5. [Tools](/docs/concepts/tools)
6. [Deployment Guides](/docs/guides/deployment/docker)
