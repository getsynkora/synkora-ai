---
sidebar_position: 2
---

# Knowledge Bases

Knowledge bases are how Synkora gives agents durable, organization-specific context.

## What Goes Into a Knowledge Base

Typical sources include:

- PDFs and office documents
- markdown and text files
- uploaded files from the dashboard
- web content
- synced content from external systems

## What Synkora Does With That Data

At a high level, the pipeline is:

1. ingest document
2. parse and normalize
3. split into chunks
4. embed and index
5. retrieve at query time
6. rerank and ground the response

## Storage Model

Synkora uses PostgreSQL as the system of record and supports vector/search backends such as:

- pgvector
- Qdrant
- Pinecone
- Elasticsearch

Choose the provider that fits your operating model, scale, and latency requirements.

## Knowledge Base Design Advice

- keep one knowledge base focused on one domain or team
- avoid mixing unrelated documents into the same retrieval scope
- use smaller, cleaner source sets before tuning prompts
- pair knowledge with tools when the agent needs to both know and act

## Related Pages

- [Create a RAG Agent](/docs/guides/agents/create-rag-agent)
- [Document Processing](/docs/guides/knowledge-base/document-processing)
- [Advanced RAG](/docs/guides/knowledge-base/advanced-rag)
