---
sidebar_position: 3
---

# Knowledge Bases API

The knowledge base API manages the retrieval layer that grounds agents on your data.

## Typical Capabilities

- create and update knowledge bases
- upload and manage documents
- trigger ingestion flows
- search retrieved content
- attach knowledge bases to agents

## Design Notes

Knowledge base APIs are platform APIs, not just vector APIs. They coordinate:

- document metadata
- storage
- parsing and chunking
- embeddings and indexing
- retrieval paths back into agents

## Client Advice

- build ingestion flows around clean document boundaries
- do not assume immediate availability after upload if background processing is involved
- keep tenant and workspace boundaries explicit in client design
