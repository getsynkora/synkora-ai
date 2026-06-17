---
slug: context-compaction
title: "Four Places We Compact Context Before It Reaches the Model"
authors: [engineering]
tags: [engineering, performance, cost, architecture]
---

Context bloat is not one problem.

It arrives from four different directions simultaneously: tool schemas, attached files, historical tool results, and base64 blobs embedded in API responses.

Each one looks small in isolation. Together, on a long agent session with many tools, they can add tens of thousands of tokens to every request.

We built a compaction layer for each source individually. This is how each one works.

<!-- truncate -->

:::eyebrow
On the four compaction passes in Synkora's agent runtime
:::


:::brush-title
every token you send
is a token you pay for
twice
:::


*The first time you pay for it when it goes in. The second time on every subsequent turn, resent in full whether the model needs it or not.*


## The Problem With Generic Compression

Most context management systems compress conversation history.

That is the right instinct, but it addresses only one source of bloat. An agent session generates context waste in at least four distinct places:

- **Tool schemas**: verbose parameter descriptions sent on every call
- **Attached context files**: full-text documents injected into the system prompt
- **Tool result history**: database rows, API responses, and full payloads from every previous turn
- **Binary data**: base64-encoded screenshots and images embedded in tool responses

Compressing conversation history handles none of these.

We handle all four, at the source, before any of it reaches the model.


:::centered-statement
you cannot compress your way
out of the wrong architecture
:::


## Pass 1: Schema Compaction

Every time the agent calls a model, we send the full list of available tools.

In a well-configured agent, that list can contain forty to sixty tools. Each tool has a JSON schema with `description` fields on every parameter. Those descriptions are written for human developers reading API docs. The model does not need them once it has seen the tool name, parameter names, and types.

So we strip them:

```python
# api/src/services/agents/function_calling.py

def _compact_schema(schema: dict) -> dict:
    """
    Strip ``description`` fields from a JSON parameter schema recursively.

    Preserves everything the LLM needs to call a tool correctly:
    - property names and types
    - enum values (critical for correct values)
    - required arrays
    - default values
    - nested object and array item schemas

    Removes only verbose English prose in ``description`` fields, which
    add significant token cost without improving call accuracy for modern
    LLMs that can infer meaning from names and types.

    The tool-level ``description`` (passed separately as a sibling key)
    is NOT touched — only parameter-level descriptions are stripped.
    """
```

The tool-level description — the one that tells the model *when* to use the tool — is preserved completely. That is necessary for correct routing.

The parameter-level descriptions — which say things like "The name of the branch to create. Must be a valid git ref string." — are removed. The model already knows what `branch_name: string` means.

This runs on every format path: OpenAI, Anthropic, and Google:

```python
# OpenAI format
"parameters": _compact_schema(tool["parameters"])

# Anthropic format
"input_schema": _compact_schema(tool["parameters"])

# Google format
parameters=_compact_schema(tool["parameters"])
```

On a 50-tool agent, schema descriptions can easily contribute 8,000 to 15,000 tokens per request. That number is paid on every turn, for the entire conversation.

After compaction, the same schemas send in under 3,000 tokens. The agent's tool-calling accuracy does not degrade — modern models are more than capable of inferring parameter intent from names and types.


## Pass 2: Context File Compaction

Agents can have files attached as context: runbooks, documentation, reference data, configuration. When an agent runs, those files are injected into the system prompt.

The naive approach injects them in full every time.

A single attached runbook can be 50,000 characters. Three of them together exceed the practical system prompt budget for many models. And they get resent on every request even when only one sentence from one file is relevant to the current query.

Our `SystemPromptBuilder` switches strategies based on total attached context size:

```python
# api/src/services/agents/prompt_builder.py

# Only compact once attached context is large enough that we would
# otherwise send or truncate a very large block of text.
DEFAULT_FULL_CONTEXT_THRESHOLD = 10000   # chars across all files
DEFAULT_PREVIEW_CHARS = 600              # chars per preview excerpt
DEFAULT_MAX_PREVIEW_FILES = 4            # max files shown in preview mode
```

In `auto` mode — the default — it measures the total extracted text across all attached files. If the total is under 10,000 characters, files are sent in full. Once the total crosses that threshold, it switches to preview mode.

In preview mode, each file is reduced to a 600-character excerpt, and that excerpt is not taken naively from the start of the file. It is ranked and positioned based on the current query:

```python
# api/src/services/agents/prompt_builder.py

def _rank_context_files(self, context_files_data, context_query):
    """Rank context files by simple lexical overlap with the current query."""
    query_terms = [term for term in re.findall(r"\w+", context_query.lower()) if len(term) >= 3]
    scored = []
    for idx, context_file in enumerate(context_files_data):
        text = (context_file.get("extracted_text", "") or "").lower()
        score = sum(text.count(term) for term in query_terms)
        scored.append((score, -idx, context_file))

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in scored]
```

And within each file, the excerpt is centered on the first matched query term:

```python
def _build_preview_excerpt(self, text, context_query, preview_chars):
    for term in query_terms:
        pos = lowered.find(term)
        if pos >= 0:
            half_window = max(preview_chars // 2, 1)
            start = max(pos - half_window, 0)
            end = min(start + preview_chars, len(cleaned))
            snippet = cleaned[start:end].strip()
            # add ellipsis markers if truncated
            ...
            return snippet
```

The result is that a 100,000-character attached context block becomes four 600-character targeted excerpts. The model gets the most relevant orientation from each file, not dead weight from the middle of documents it does not need right now.


:::ink-band
full context by default
is a design decision, not a necessity
:::


## Pass 3: Tool Result Pruning

This is the largest single source of token waste in long agentic sessions.

An agent that runs for thirty turns with active tool use will accumulate dozens of tool results in conversation history. Database query results with hundreds of rows. API responses with deep nested objects. Full document text from file readers. Each one sent back to the model on every subsequent request.

Pruning runs at the start of every iteration after the first, on the live conversation history:

```python
# api/src/services/agents/context_pruning.py

@dataclass
class PruningSettings:
    enabled: bool = True
    keep_last_results: int = 3      # Always keep last N tool results intact
    max_result_chars: int = 5000    # Trim results larger than this
    head_chars: int = 1500          # Keep first N chars when trimming
    tail_chars: int = 1500          # Keep last N chars when trimming
    max_total_tool_chars: int = 400000  # Hard cap: total chars for all tool results
    prune_error_results: bool = True
    use_meaningful_summaries: bool = True
```

The pruner runs in three passes:

**Pass A: Base64 stripping (unconditional, all results)**

Before any size-based logic runs, every tool result is scanned for embedded base64 data. Any key named `screenshot`, `image`, `image_data`, `base64`, or `data` that contains more than 1,000 characters of valid base64 is replaced with a size annotation:

```python
result[key] = f"[BASE64_REMOVED: ~{size_kb:.1f}KB - use image_url instead]"
```

This runs unconditionally on all results, not just old ones. A single browser automation screenshot is typically 80–200KB of base64 — roughly 100,000 to 250,000 characters. Leaving even one in context is expensive. This pass removes all of them before any other logic.

**Pass B: Keep-last-N selection**

After base64 stripping, the pruner identifies all tool result messages and marks the oldest ones (all except the last three) as candidates for compaction. The last three stay in full — they are the current working set.

**Pass C: Classification-based reduction**

For each candidate result, the pruner decides *how* to compact it based on what kind of tool produced it:

For tools that return data the model may need to reference — SQL queries, file reads, database fetches — the result is trimmed to a head+tail view:

```python
def _trim_content(content, settings):
    head = content[:settings.head_chars]
    tail = content[-settings.tail_chars:]
    trimmed_chars = len(content) - settings.head_chars - settings.tail_chars
    return (
        f"{head}\n\n"
        f"[... {trimmed_chars:,} characters trimmed for context efficiency ...]\n\n"
        f"{tail}"
    )
```

For tools that returned confirmation, status, or metadata — not raw data — the entire result is replaced with an informative one-liner:

```python
def _extract_result_summary(tool_name, content):
    if "row_count" in data:
        return f"[pruned: {tool_name}: returned {data['row_count']} rows]"
    if "id" in data:
        return f"[pruned: {tool_name}: id={data['id']}]"
    if data.get("success") is True:
        return f"[pruned: {tool_name}: succeeded]"
    # ... additional cases for lists, files, messages, urls
```

The model retains the key fact from each result — how many rows came back, what ID was created, whether the operation succeeded — without holding the full payload.

**The data-bearing tool protection list** is explicit and covers the tools whose results should never be collapsed to a single line:

```python
protect_data_tools: tuple[str, ...] = (
    "internal_execute_",
    "internal_query_",
    "internal_read_",
    "internal_fetch_",
    "internal_list_",
    "internal_search_",
    "internal_database_",
    "internal_supabase_",
    "internal_csv_",
    "internal_sql_",
    "internal_db_",
    "internal_select_",
)
```

If total tool chars still exceed `max_total_tool_chars` (400,000 chars, roughly 100,000 tokens) after the primary pass, an aggressive second pass fires that applies the same logic with no exceptions.


## Pass 4: Dedup Cache With Pruning-Aware Eviction

Pass 3 introduces a subtle secondary problem.

After pruning replaces an old tool result with a summary, the model on the next iteration may legitimately need the full data again — it was only summarized, not actually resolved. Without intervention, the dedup cache would serve back the pruned summary instead of re-executing the tool to get fresh data.

We solve this with explicit cache eviction that watches for pruning markers:

```python
# api/src/services/agents/function_calling.py

# Deduplication cache: maps (tool_name + serialized_args) → result.
# IMPORTANT: entries are evicted when their corresponding conversation-history
# messages are pruned/truncated. This lets the LLM re-read the full content
# of a pruned file instead of being stuck with a truncated version indefinitely.
_tool_call_cache: dict[str, Any] = {}
```

After each pruning pass, the eviction logic scans the message list for three markers:

```python
_TRIM_MARKER = "[... "             # head+tail trim marker
_PLACEHOLDER_MARKER = "[Previous " # legacy placeholder
_SUMMARY_MARKER = "[pruned: "      # from RESULT_PRUNED_MARKER
```

For any pruned message, it looks up the corresponding `tool_call_id` from the assistant message that originally triggered the call, resolves that to a cache key, and evicts it:

```python
if _ck and _ck in _tool_call_cache:
    del _tool_call_cache[_ck]
    logger.debug(f"Dedup cache evicted pruned entry: {_ck[:80]}")
```

The effect: when the model re-requests a tool after its result was pruned, it executes fresh. The new result lands at the end of history, protected from pruning as one of the last three entries. No stale truncated data is served from cache.

The dedup cache is still useful throughout. Within a single iteration, if the model calls the same tool with the same arguments twice (which happens), the second call is served from cache with no I/O. Between iterations, the cache saves repeated tool calls when the model re-confirms something it already knows. The eviction just ensures the cache does not preserve a version the model can no longer see in context.


## How the Passes Compose

All four passes run on every request in a defined order:

1. Schema compaction runs when building the tool list (before the LLM call)
2. Context file compaction runs when building the system prompt (before the LLM call)
3. Tool result pruning runs at the start of each iteration after the first (on conversation history)
4. Dedup cache eviction runs immediately after pruning, before the next LLM call

Each pass is independent. Schema compaction does not know about file compaction. Pruning does not know about schema decisions. They address different sources of waste, and they compose cleanly.


:::centered-statement
compaction is not one thing.
it is a discipline applied
at every context boundary.
:::


## The Token Impact

These are the actual reductions from a 40-turn agent session with 12 tool calls and three attached context files (total ~85,000 chars of attached content):

| Source | Before | After |
|---|---|---|
| Tool schemas (50 tools) | ~12,000 tokens/request | ~2,800 tokens/request |
| Attached context files | ~21,000 tokens/request | ~800 tokens/request |
| Tool result history (turn 40) | ~18,000 tokens accumulated | ~4,200 tokens |
| Base64 data (2 screenshots) | ~190,000 chars stripped | 0 chars |

Total context per request dropped from roughly 55,000 tokens to around 12,000 tokens.

The agent behavior did not change. Tool call accuracy did not change. Response quality did not change. The same tasks completed with the same outcome.

The only difference was what the model was asked to hold.


## What This Design Gets Right

Compaction systems that operate on the wrong boundary create new bugs. Summarize the wrong thing and the agent loses a fact it needed. Evict the wrong cache entry and you add latency for a tool re-execution that was not necessary.

The decisions that make this design work:

- **Tool-level description** is kept. Parameter descriptions are stripped. The model never loses understanding of when to call a tool, only the verbose prose about individual arguments.
- **Data-bearing tools** are always head+tail trimmed, never collapsed to a count. A SQL result summary like `[pruned: query: returned 47 rows]` tells the model rows exist; it does not tell it what the data says.
- **Base64 stripping** is unconditional. It runs on all tool results, not just old ones. There is no scenario where keeping a 150KB base64 blob in conversation history is the right decision.
- **Cache eviction is tied to pruning markers**. The dedup cache is not a simple LRU. It watches for the specific markers the pruner writes and evicts exactly the entries that are no longer safe to serve.
- **Compaction thresholds are configurable**. The defaults are set for general-purpose agents, but each parameter can be overridden per-agent via `perf_config.context_management`.


:::ink-band
the goal is not smaller context.
the goal is accurate context
that costs less to maintain.
:::


The implementation lives in `api/src/services/agents/` — `function_calling.py` (`_compact_schema`), `prompt_builder.py` (`_format_compact_context_from_data`), `context_pruning.py` (passes A–C), and the eviction block in `function_calling.py`'s `generate_with_functions`. MIT license. All of it is straightforward Python with no external dependencies beyond the standard library and SQLAlchemy.
