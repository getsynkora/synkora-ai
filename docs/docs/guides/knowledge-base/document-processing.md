---
sidebar_position: 2
---

# Document Processing

Document processing is the part of RAG work most teams underestimate.

## Processing Pipeline

At a high level:

1. upload or fetch source
2. extract usable text
3. normalize structure
4. split into chunks
5. embed and index

## Sources That Usually Work Well

- markdown
- PDFs with clean text layers
- plain text
- structured internal docs

## Sources That Need More Care

- scanned PDFs
- image-heavy files
- long mixed-format exports
- highly duplicated content

## Operational Advice

- start with a small set of high-quality documents
- remove duplicates early
- separate very different document families into separate KBs
- reprocess content when the source structure changes meaningfully
