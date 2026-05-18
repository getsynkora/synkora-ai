---
sidebar_position: 2
---

# Create a RAG Agent

RAG is the fastest way to make an agent useful on your own data without training a model.

## Goal

Create an agent that:

- answers from your documents
- cites or grounds responses through retrieval
- stays focused on a specific domain

## Step 1: Create a Knowledge Base

In the dashboard:

1. Open **Knowledge Bases**
2. Create a new knowledge base
3. Give it a clear scope such as “Support Docs” or “Internal Policies”

## Step 2: Ingest Documents

Upload a small, clean set first:

- product docs
- runbooks
- FAQs
- internal procedures

Avoid dumping everything in on day one.

## Step 3: Create or Open an Agent

Create a new agent or edit an existing one. Use a system prompt that explicitly tells the agent to rely on retrieved knowledge when answering domain-specific questions.

## Step 4: Attach the Knowledge Base

Associate the knowledge base with the agent in the dashboard.

## Step 5: Test Retrieval Behavior

Ask questions that should be answerable only from the uploaded material.

Look for:

- grounded answers
- stable domain behavior
- fewer hallucinated specifics

## Step 6: Refine

If quality is weak, adjust in this order:

1. source quality
2. document scope
3. chunking and retrieval setup
4. prompt guidance

## Related Pages

- [Knowledge Bases](/docs/concepts/knowledge-bases)
- [Document Processing](/docs/guides/knowledge-base/document-processing)
- [Advanced RAG](/docs/guides/knowledge-base/advanced-rag)
