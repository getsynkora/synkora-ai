---
sidebar_position: 1
---

# Advanced RAG

Once basic retrieval works, most gains come from data quality, indexing discipline, and retrieval design rather than endlessly rewriting prompts.

## Focus Areas

### Source quality

Clean, current documents outperform larger noisy corpora almost every time.

### Scope control

Use separate knowledge bases for different domains when possible.

### Retrieval tuning

Review:

- chunk size
- metadata quality
- vector backend choice
- reranking behavior

### Prompt grounding

Make it explicit when the agent should:

- rely on retrieved context
- admit missing context
- avoid inventing specifics

## Practical Advice

- fix ingestion quality before tuning the model
- prefer one clean retrieval domain over one giant mixed corpus
- validate grounded answers with real user questions, not toy prompts
