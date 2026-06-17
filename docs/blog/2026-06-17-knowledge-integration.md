---
slug: knowledge-integration
title: "How We Built the Knowledge Layer: Embedding, Chunking, and Retrieval from the Ground Up"
authors: [engineering]
tags: [engineering, rag, knowledge-base, architecture, embeddings]
---

A document is not knowledge.

A document is ink on paper, or bytes in a bucket. It becomes knowledge the moment you can retrieve the right piece of it in under a second, in response to a question the author never anticipated.

That gap — between storing a file and actually using it — is where most RAG implementations quietly fail. The document is there. The agent just cannot find what it needs.

This is the story of how we closed that gap in Synkora: how a PDF, a Slack thread, an email, or a GitHub README becomes something an agent can actually reason about.

<!-- truncate -->

:::eyebrow
On knowledge bases, vector stores, and the pipeline between them
:::


:::brush-title
a document uploaded
is not a document understood
:::


*The hard part is not storing text. The hard part is making every fragment of it retrievable at the right moment, by the right query, from any provider, in any format.*


## The Problem With Treating All Text The Same

The first design decision we made was not about which vector database to use.

It was about **what kind of text we were actually dealing with**.

A product runbook is not a Slack thread. A Slack thread is not a legal agreement. A legal agreement is not source code. Each one has a completely different structure, a different unit of meaning, and a different way of breaking apart at the seams.

If you apply the same fixed-size chunking to all of them, you get fragments that cut across sentences, sever email headers from bodies, split code functions in the middle, and divorce Slack messages from the thread context that gives them meaning.

The retrieval works — sort of. But the chunks that come back are awkward. The model reconstructs context from half-a-function and an email body without its subject line.

We built a different starting point: **the chunking strategy is a first-class configuration per knowledge base**, not a global default applied blindly.


:::centered-statement
the right chunk
is the right unit of meaning
for that type of document
:::


## Six Chunking Strategies, One Consistent Interface

The `ChunkingStrategy` enum defines the six strategies the platform supports:

```python
# api/src/models/knowledge_base.py

class ChunkingStrategy(enum.StrEnum):
    FIXED    = "FIXED"     # Fixed size with sentence-boundary snapping
    SEMANTIC = "SEMANTIC"  # Paragraph-aware boundaries
    EMAIL    = "EMAIL"     # Header preservation + body chunking
    SLACK    = "SLACK"     # Thread-aware message grouping
    DOCUMENT = "DOCUMENT"  # Section and heading detection
    CODE     = "CODE"      # Function and class boundary detection
```

Each strategy is an implementation in `SmartChunker`. All of them share the same interface: text in, list of chunk dicts out. What changes is the logic that decides where the cuts go.

**FIXED** is the baseline. It targets a configured chunk size (default 1,500 characters), but before making the cut it looks backward from the boundary for a sentence terminator — `.`, `!`, `?`, or `\n`. If one exists, the cut happens there instead of mid-sentence. Chunks shorter than `min_chunk_size` (default 500 characters) are dropped rather than kept as stubs. Each chunk carries an index and total count so the model can orient itself:

```python
# api/src/services/knowledge_base/smart_chunker.py

if end < len(text):
    sentence_end = max(
        text.rfind(". ", start, end),
        text.rfind("! ", start, end),
        text.rfind("? ", start, end),
        text.rfind("\n",  start, end),
    )
    if sentence_end > start:
        end = sentence_end + 1

start = end - self.chunk_overlap if self.chunk_overlap > 0 else end
```

Default overlap is 150 characters — enough for the model to not lose a word that straddles a boundary, but small enough to not meaningfully duplicate content.

**SEMANTIC** splits on double newlines first, treating `\n\n` as a paragraph boundary, then groups paragraphs into target-sized chunks. Large individual paragraphs are split further using the sentence-boundary logic. The result is chunks that map to recognizable units of prose, not arbitrary byte ranges.

**DOCUMENT** goes further. It runs a regex over the text looking for Markdown headings (`#`, `##`, `###`) and all-caps colon patterns typical of structured documents:

```python
heading_pattern = r"\n(#{1,6}\s+.+|[A-Z][^.!?]*:)\n"
sections = re.split(heading_pattern, text)
```

When a heading is detected, it is prepended to the following content chunk so the model always knows what section it is reading, even in isolation.

**EMAIL** detects the header block — `From:`, `To:`, `Subject:`, `Date:` — finds the double newline that separates it from the body, and keeps the header attached to the first content chunk. Emails under 2,000 characters (configurable via `email_threshold`) are kept whole. Longer emails are chunked from the body, with the header preserved in `chunk_type: email_start`. The model always has sender context.

**SLACK** recognizes thread boundaries by looking for timestamp patterns and `@mention` prefixes:

```python
message_pattern = r"\n(?=\[\d{4}-\d{2}-\d{2}|\d{1,2}:\d{2}|@\w+)"
messages = re.split(message_pattern, text)
```

Threads under `slack_thread_size` (default 1,500 characters) stay intact as `complete_thread` chunks. Longer threads are grouped into message-cluster chunks that preserve conversation flow.

**CODE** detects function and class definitions across multiple languages:

```python
code_pattern = r"\n(def |class |function |const |let |var )"
```

It groups definitions into chunks, keeping functions whole rather than splitting them across a size boundary.

Every chunk carries a `metadata` dict with `chunk_type`, `chunk_index`, `total_chunks`, and any source-specific fields. This metadata travels all the way through to the search results the agent reads.


## Four Embedding Providers, One Knowledge Base Config

Chunking determines the shape of the data. Embedding determines its position in semantic space.

We support five embedding providers, all declared as `EmbeddingProvider` in the model:

```python
# api/src/models/knowledge_base.py

class EmbeddingProvider(enum.StrEnum):
    SENTENCE_TRANSFORMERS = "SENTENCE_TRANSFORMERS"
    OPENAI                = "OPENAI"
    COHERE                = "COHERE"
    HUGGINGFACE           = "HUGGINGFACE"
    LITELLM               = "LITELLM"
```

The `EmbeddingService` handles all five through a single `embed_text` / `embed_texts` interface. The operational decision that shapes the architecture is where `sentence_transformers` and `huggingface` actually run.

They do not run in the API process.

Bundling PyTorch, `sentence-transformers`, and CUDA dependencies into the API image makes it gigabytes heavier, slows startup by minutes, and competes for memory with request handling. Instead, both providers are delegated to a dedicated ML microservice (`synkora-ml`):

```python
# api/src/services/knowledge_base/embedding_service.py

if self.provider in ("sentence_transformers", "huggingface"):
    from src.core.ml_client import get_ml_client
    client = get_ml_client()
    return _run_async(client.embed_text(text, model=self.model_name))
```

The `_run_async` helper spins up a single-thread executor to call the async ML client from synchronous context — the same pattern used for cross-loop calls in Celery workers:

```python
def _run_async(coro) -> object:
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()
```

OpenAI, Cohere, and LiteLLM run in-process since they are HTTP calls to remote APIs — no heavy package load, no memory contention. The default model is `all-MiniLM-L6-v2`, which produces 384-dimensional vectors. The dimension is queryable at runtime:

```python
def get_embedding_dimension(self) -> int:
    if "dimension" in self.config:
        return self.config["dimension"]
    # For ML microservice providers, ask the service
    return _run_async(client.get_embedding_dimension(model=self.model_name))
```

Batch embedding uses `embed_texts()` with a default batch size of 32. The ML service handles batching internally for `sentence_transformers` and `huggingface`. For OpenAI and Cohere, the full list is sent in a single API call and individual embeddings extracted from the response array.


## Two Vector Databases, One Shared Contract

Every embedding needs to land somewhere. We support Qdrant and Pinecone through a provider abstraction that enforces the same contract on both:

```python
# api/src/services/knowledge_base/providers/base_vector_db.py

class BaseVectorDBProvider(ABC):
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def create_collection(self, name, dimension, distance_metric="cosine") -> None: ...
    def collection_exists(self, name) -> bool: ...
    def add_vectors(self, collection_name, vectors) -> list[str]: ...
    def search(self, collection_name, query_vector, limit, filters, score_threshold) -> list[dict]: ...
    def delete_vectors(self, collection_name, vector_ids) -> None: ...
    def update_vector(self, collection_name, vector_id, vector, payload) -> None: ...
    def get_collection_info(self, collection_name) -> dict: ...
    def batch_add_vectors(self, collection_name, vectors, batch_size=100) -> list[str]: ...
    def health_check(self) -> bool: ...
```

`VectorDBProviderFactory` is a plain dict lookup:

```python
_providers = {
    VectorDBProviderEnum.QDRANT:   QdrantProvider,
    VectorDBProviderEnum.PINECONE: PineconeProvider,
}
```

Adding a new provider means implementing `BaseVectorDBProvider` and calling `register_provider()`. Nothing else changes.

**Qdrant** connects via `QdrantClient` with a configurable 30-second timeout to prevent hanging connections in Kubernetes. It supports `host:port` or a full URL and an optional API key. Distance metric mapping converts the generic `cosine`/`euclidean`/`dot_product` values to Qdrant's `Distance.COSINE`, `Distance.EUCLID`, and `Distance.DOT` enums.

**Pinecone** uses KB ID as the namespace on every vector operation. This gives Synkora multi-tenant isolation inside a shared Pinecone index: each knowledge base's vectors live in their own namespace, invisible to other knowledge bases even if they share an index. The collection name maps to Pinecone's `index_name`, resolved from `vector_db_config`:

```python
collection_name = (
    kb.vector_db_config.get("index_name")
    or kb.vector_db_config.get("collection_name")
    or f"kb-{kb.id}"
)
namespace = str(kb.id)
```

Vectors in both providers carry a full payload: the raw chunk text, the source identifier, the document ID, the chunk index, and all document metadata. The payload is what the agent reads — the vector is only used for similarity ranking.


:::ink-band
the vector is the address.
the payload is the content.
:::


## The Retrieval Pipeline: Four Strategies

This is where everything comes together. The `EnhancedRAGService` exposes four retrieval strategies:

```python
class RetrievalStrategy(StrEnum):
    VECTOR_ONLY    = "vector_only"     # Pure cosine similarity
    HYBRID         = "hybrid"          # Vector + BM25 keyword
    HYBRID_RERANK  = "hybrid_rerank"   # Hybrid + cross-encoder reranking (default)
    ADVANCED       = "advanced"        # Full pipeline with LLM query expansion
```

The default is `HYBRID_RERANK`. Here is what that pipeline actually does.

**Step 1: Query embedding with caching**

The user's query is embedded using the same model that was used when the document was indexed. Different knowledge bases may use different embedding providers, so each KB gets its own `EmbeddingService` instance initialized from the KB's stored config.

Query embeddings are cached in a process-level dict keyed by the MD5 hash of the query text:

```python
variation_hash = hashlib.md5(variation.encode()).hexdigest()
if variation_hash in self._embedding_cache:
    query_embedding = self._embedding_cache[variation_hash]
else:
    query_embedding = kb_embedding_service.embed_texts([variation])[0]
    self._embedding_cache[variation_hash] = query_embedding
```

A repeated query in the same session — the agent asking the same follow-up twice — costs zero embedding API calls.

**Step 2: Vector search with generous top-k**

We retrieve with `vector_top_k=20` by default — four times the final output count of `rerank_top_k=5`. This is intentional. Vector cosine similarity is a good first-pass filter but a poor final ranker. It measures geometric distance in embedding space, not semantic relevance to the specific question. Retrieving more and reranking is consistently better than retrieving fewer and stopping.

The minimum score threshold is set low at `0.2` for this stage — again intentional. The reranker will filter aggressively; we do not want to pre-filter relevant chunks with a cosine cutoff that is too conservative.

**Step 3: Hybrid BM25 scoring**

After vector search, each result gets a second score based on lexical overlap with the query. The implementation is a simplified per-document BM25 — no corpus-level IDF since we score against individual chunks, not a corpus:

```python
# BM25 parameters
k1 = 1.2
b  = 0.75
avg_dl = 500  # approximate average document length in terms

for term in query_terms:
    if term in term_freq:
        tf = term_freq[term]
        score = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / avg_dl))
        bm25_score += score
```

An exact phrase match adds a 0.3 bonus on top. The combined score blends vector and keyword at `(1 - 0.3) * vector_score + 0.3 * keyword_score`.

The keyword component matters for technical queries. A query for `"connection_id a6339a53"` will score zero on vector similarity against a chunk that contains that exact UUID, since the UUID does not exist in the model's embedding space. BM25 term frequency will catch it directly.

**Step 4: Reciprocal Rank Fusion (when query expansion is on)**

In `ADVANCED` mode, the LLM generates up to three alternative phrasings of the query. Each phrasing gets its own vector search. The results are merged using RRF:

```python
def _reciprocal_rank_fusion(self, results_by_variation, k=60):
    # RRF score: sum(1 / (k + rank_i)) across all result lists
    for variation, results in results_by_variation.items():
        for rank, result in enumerate(results, 1):
            rrf_score = 1 / (k + rank)
            scores[result_id] = scores.get(result_id, 0) + rrf_score
```

RRF with `k=60` is deliberately conservative. A result ranked first in one variation scores `1/61 ≈ 0.016`. A result that appears ranked first in all three variations scores `3/61 ≈ 0.049`. Results that appear across multiple query phrasings rise to the top regardless of their individual cosine scores. `k=60` prevents any single high-ranked result from dominating the fusion.

For single-query operation (the default), this function short-circuits and returns the original list without fusion overhead.

**Step 5: Cross-encoder reranking**

The top 20 candidates go to the cross-encoder reranker. The default model is `cross-encoder/ms-marco-MiniLM-L-6-v2`, served via the ML microservice:

```python
# api/src/services/knowledge_base/reranker_service.py

DEFAULT_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
```

A cross-encoder is architecturally different from a bi-encoder (which is what standard embedding models are). A bi-encoder encodes query and document independently and compares their vectors. A cross-encoder processes the query and document *together* in a single forward pass, attending across both simultaneously. This is slower — you cannot precompute document representations — but it produces much more accurate relevance scores.

The final score blends reranker judgment with original retrieval score:

```python
combined = (1 - score_weight) * rerank_score + score_weight * original_score
# score_weight = 0.3
```

The reranker gets 70% of the final score. The original retrieval signal gets 30% — enough to break ties where the cross-encoder is uncertain, but not enough to override clear reranker preferences.

For teams without an ML service, Cohere Rerank API is the drop-in alternative: the interface is identical, the provider flag changes.

**Step 6: Deduplication**

Before returning, near-duplicate chunks are removed using Jaccard similarity across tokenized chunk text:

```python
result_words = set(result.text.lower().split())
seen_words   = set(seen_text.lower().split())
similarity = len(result_words & seen_words) / len(result_words | seen_words)
if similarity >= 0.9:
    is_duplicate = True
```

The 0.9 threshold is conservative — it only removes near-exact duplicates, not semantically similar passages. A document indexed twice (or two documents with overlapping sections) will not return the same chunk twice.


## Multi-Knowledge-Base Fusion

An agent can have multiple knowledge bases attached simultaneously. Each retrieval call queries all of them:

```python
# api/src/services/knowledge_base/rag_service.py

for agent_kb in agent_kbs:
    kb = agent_kb.knowledge_base
    query_embedding = await self.generate_embedding(query, kb)
    vector_db = self.get_vector_db(kb)

    results = vector_db.search(
        collection_name=collection_name,
        query_vector=query_embedding,
        limit=search_limit,
        score_threshold=search_threshold,
        namespace=namespace,
    )
    for result in results:
        result["knowledge_base_id"] = kb.id
        result["knowledge_base_name"] = kb.name
        all_results.append(result)
```

Each KB runs its own embedding service (its vectors were embedded with its configured model), its own vector DB connection, and its own retrieval config (per-KB `max_results` and `min_score` from `agent_kb.retrieval_config`). Results from all KBs are pooled, sorted by score, and then deduplicated and reranked as a unified set.

The `retrieval_config` on the `AgentKnowledgeBase` join lets operators tune retrieval per KB per agent. A high-precision technical KB might use a 0.8 score threshold. A broad general-knowledge KB might use 0.5. The thresholds are not global.


## Result Enrichment and Source Attribution

After retrieval, results are enriched with full document metadata via a single batch query — no N+1:

```python
# Collect all doc_ids first
doc_ids = [result.get("payload", {}).get("doc_id") for result in results if ...]

# Single SELECT ... WHERE id IN (...)
result = await self.db.execute(select(Document).filter(Document.id.in_(doc_ids)))
documents_map = {doc.id: doc for doc in documents}
```

For documents stored in S3, a presigned URL is generated per document (1-hour expiry). Source-specific display metadata is added based on `source_type`:

```python
if document.source_type == "SLACK":
    source["display"] = {
        "type": "Slack Message",
        "channel": meta.get("channel"),
        "user": meta.get("user"),
        "timestamp": meta.get("timestamp"),
        "link": document.external_url,
    }
elif document.source_type == "GMAIL":
    source["display"] = {
        "type": "Email",
        "from": meta.get("from"),
        "subject": meta.get("subject"),
        "timestamp": meta.get("timestamp"),
    }
```

The agent does not just see a text fragment. It sees a fragment annotated with where it came from, who wrote it, when, and a direct link to the source. The model can cite sources with specificity. The user can click through.


## Caching at Two Levels

**Embedding cache**: per-process in-memory dict, keyed by MD5 hash of the input text. Identical queries within a session cost zero embedding API calls. Across sessions, embeddings are recomputed (the cache is not persisted — intentionally, since model configs can change between deployments).

**RAG result cache**: per-process in-memory dict, keyed by MD5 of `query + sorted(kb_ids)`. TTL is 3,600 seconds (one hour). Cache size is capped at 1,000 entries; when that limit is reached, the oldest 100 entries are evicted:

```python
if len(self._cache) > 1000:
    oldest_keys = sorted(self._cache.keys(), key=lambda k: self._cache[k][0])[:100]
    for key in oldest_keys:
        del self._cache[key]
```

Both caches are per-instance, not shared across workers. A Celery worker and the API process each maintain their own cache. For most agents, this is fine — the working set of active queries fits comfortably in memory. For high-query-volume production deployments, the result cache can be moved to Redis by swapping the dict for a Redis client; the interface is the same.


:::centered-statement
store everything.
retrieve exactly what matters.
tell the model where it came from.
:::


## The Full Picture

A document enters Synkora as bytes. Before it can help an agent answer a question:

1. **It is chunked** using the strategy appropriate to its content type — email preserves headers, Slack preserves thread context, code preserves function boundaries, documents preserve section headings.

2. **Each chunk is embedded** using the provider configured for that knowledge base — `all-MiniLM-L6-v2` via the ML microservice by default, with OpenAI, Cohere, or any LiteLLM-compatible model as alternatives.

3. **Embeddings land in a vector database** — Qdrant for self-hosted, Pinecone for managed — stored with the full chunk payload and indexed under a per-KB namespace for isolation.

4. **At query time**, the pipeline embeds the query, retrieves 20 candidate chunks using cosine similarity, rescores with BM25, optionally fuses across query variations using RRF, reranks the top candidates with a cross-encoder, deduplicates near-identical fragments, and returns the top 5.

5. **Results are enriched** with document metadata and source attribution via a single batch DB query, with presigned S3 URLs and source-specific display formatting for Slack and Gmail.

6. **The agent receives** not a blob of retrieved text but a structured, ranked, attributed context block it can cite, reason over, and link back to.


The whole pipeline lives in `api/src/services/knowledge_base/`. MIT license. Every threshold, every strategy, every provider is configurable per knowledge base without touching code.


:::ink-band
documents are not knowledge.
a retrieval pipeline is.
:::
