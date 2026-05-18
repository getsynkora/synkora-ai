---
sidebar_position: 3
---

# Use Pinecone

Pinecone is a good fit when you want a managed vector backend and do not want to operate the vector layer yourself.

## Use Pinecone When

- you prefer managed infrastructure
- your deployment already leans on hosted services
- you want to avoid running another database in production

## Configuration Checklist

- create the Pinecone project and index
- provide credentials to Synkora
- attach the knowledge base to the correct index/config
- test retrieval with a small corpus before scaling up

## Tradeoff

Pinecone reduces operating burden, but it also introduces another managed dependency in your AI stack.
