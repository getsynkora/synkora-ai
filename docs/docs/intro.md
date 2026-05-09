---
sidebar_position: 1
slug: /
---

# Welcome to Synkora

Synkora is a production-ready, multitenant LLM application platform for building, deploying,
and managing AI agents at scale. It provides an application abstraction over LLM workflows —
combining prompt management, multi-provider model routing, RAG-powered knowledge bases,
a tool/function registry, and full observability in a single API-first platform.

:::info Correct Classification
Synkora is an **LLM application platform** — not a low-code workflow tool (Dify, n8n), not an agent orchestration framework (CrewAI, LangChain), and not a domain-specific SaaS. It is infrastructure for building, deploying, and operating AI applications at the application layer.
:::

## What is Synkora?

Synkora is a full-stack platform that combines:

- **Agent Builder**: Create AI agents with custom personalities, knowledge bases, and tool integrations
- **Knowledge Management**: Build RAG-powered agents with vector search across your documents
- **Multi-Channel Deployment**: Deploy to Slack, Telegram, WhatsApp, Teams, or embed on your website
- **Enterprise Features**: Multi-tenancy, SSO, usage billing, and comprehensive security

## Key Features

### Intelligent Agents

Create AI agents powered by leading LLM providers (OpenAI, Anthropic, Google, and more) through a unified interface.

```typescript
const agent = await synkora.agents.create({
  name: 'Support Bot',
  model: 'gpt-4o',
  systemPrompt: 'You are a helpful customer support agent...',
  tools: ['search_knowledge_base', 'create_ticket'],
});
```

### Knowledge Bases

Connect your agents to your data with RAG (Retrieval Augmented Generation):

- Upload PDFs, documents, web pages, and more
- Automatic chunking and embedding
- Vector search with Qdrant or Pinecone
- Hybrid search with reranking

### Tool Integration

Extend agent capabilities with built-in and custom tools:

- **Built-in tools**: Web search, code execution, file operations
- **OAuth integrations**: Google, GitHub, Slack, Jira, and more
- **MCP servers**: Connect Model Context Protocol servers
- **Custom tools**: Build your own tool functions

### Multi-Channel Deployment

Deploy your agents across multiple channels:

| Channel | Features |
|---------|----------|
| **Web Widget** | Embeddable chat widget for any website |
| **Slack** | Slack bot with thread support |
| **Telegram** | Telegram bot integration |
| **WhatsApp** | WhatsApp Business API |
| **MS Teams** | Microsoft Teams bot |
| **API** | Direct API access for custom integrations |

## Architecture Overview

Synkora is built on modern, scalable architecture:

```
┌─────────────────────────────────────────────────────────┐
│                     Frontend (Next.js)                   │
└─────────────────────────────┬───────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────┐
│                     API (FastAPI)                        │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────┐ │
│  │ Agents  │  │   RAG   │  │ Billing │  │ Integrations│ │
│  └─────────┘  └─────────┘  └─────────┘  └─────────────┘ │
└─────────────────────────────┬───────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────┐
│                    Infrastructure                        │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────┐ │
│  │PostgreSQL│ │  Redis  │  │ Qdrant  │  │   Celery    │ │
│  └─────────┘  └─────────┘  └─────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────┘
```

## Quick Links

<div className="row">
  <div className="col col--6">
    <div className="card">
      <div className="card__header">
        <h3>Getting Started</h3>
      </div>
      <div className="card__body">
        <p>Get up and running with Synkora in 5 minutes.</p>
      </div>
      <div className="card__footer">
        <a href="/docs/getting-started/quick-start" className="button button--primary button--block">Quick Start</a>
      </div>
    </div>
  </div>
  <div className="col col--6">
    <div className="card">
      <div className="card__header">
        <h3>API Reference</h3>
      </div>
      <div className="card__body">
        <p>Complete API documentation with examples.</p>
      </div>
      <div className="card__footer">
        <a href="/docs/api-reference/overview" className="button button--primary button--block">View API</a>
      </div>
    </div>
  </div>
</div>

## Next Steps

- **[Quick Start](/docs/getting-started/quick-start)**: Create your first agent in 5 minutes
- **[Core Concepts](/docs/concepts/agents)**: Understand how Synkora works
- **[Guides](/docs/guides/agents/create-rag-agent)**: Step-by-step tutorials
- **[API Reference](/docs/api-reference/overview)**: Complete API documentation
