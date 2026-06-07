---
slug: token-optimization
title: "The Hidden Cost of Memory: How We Keep Agent Conversations From Getting Expensive"
authors: [engineering]
tags: [engineering, performance, cost, architecture]
---


The demo agent looks cheap.


Ten messages, a clever prompt, a fast response. The cost estimate says fractions of a cent per turn. The team is impressed. Someone says "we should ship this."


Then it runs in production for a week.


<!-- truncate -->


:::eyebrow
On token costs and the memory problem
:::


:::brush-title
every token you keep
is a token you pay for
:::


*The expensive part of running agents is not the intelligence. It is the history you drag along with it.*


## It Does Not Start Expensive


The first conversation is fine.


The tenth conversation is fine.


The problem starts around message forty, when an agent has been calling tools for twenty minutes. It has fetched **rows from a database**, pulled a **Slack thread**, queried a **customer record**, run a **web search**, executed a **report**. Each of those returned hundreds of lines.


And every time the user sends another message, the agent sends all of it back to the model.


Every. Single. Turn.


The **database rows** from message three. The **web search** from message eleven. The **Slack thread** the user stopped caring about nine messages ago. All of it, resent in full, on every subsequent request.


The model has already read it. It does not need to read it again. But it is in the context, so you pay for it anyway.


:::centered-statement
the model forgets nothing.
you pay for everything it remembers.
:::


## The Shape of the Problem


Token costs are not linear. They compound.


A ten-message conversation sends roughly the same tokens each turn. A sixty-message conversation with active tool use can easily send **fifty thousand tokens per request** — most of which is dead weight from three turns ago.


We watched this happen with real agents on Synkora. **Support agents** that handled complex multi-step tickets. **Data agents** that queried databases, reformatted results, and iterated. **Research agents** that called a dozen tools to build a single answer.


The costs were not obscene on message one. By message fifty they were.


That is not a model problem. Models are efficient. It is a memory problem.


You are paying to remember things that no longer matter.


:::ink-band
bad memory is expensive memory
:::


## The First Insight: Not All Memory Is Equal


The breakthrough was realizing that context is not one thing.


There is the **system prompt** — permanent, always necessary, never changes.


There is the **conversation summary** — a compressed version of everything that happened before the last fifteen messages. Dense. Useful. Much smaller than the original.


There is the **retrieved context** — knowledge base results, relevant history, pulled in specifically for this query.


And there is the **recent conversation** — the last few turns, in full, because that is where the live reasoning happens.


Most systems treat all of this the same. Everything goes into the same flat array and gets sent in full on every request.


We separated them into **tiers**. Permanent memory always goes in. Summary replaces old messages once they accumulate. Retrieved context flows in and out based on what the current query actually needs. Recent messages stay detailed. Everything else compresses.


The configuration that controls this is explicit — not buried in a prompt:

```python
# api/src/services/agents/context_manager.py

@dataclass
class ContextConfig:
    strategy: ContextStrategy = ContextStrategy.COMBINED
    max_tokens: int = 180000

    sliding_window_size: int = 15        # keep last N messages in full
    keep_recent_messages: int = 15       # messages preserved during summarization

    auto_summarize: bool = True
    summarize_threshold_messages: int = 25   # summarize after 25 messages
    summarize_threshold_tokens: int = 30000  # or after 30k tokens

    summary_max_tokens: int = 1500       # target size for each summary
    incremental_threshold_messages: int = 5  # re-summarize after 5 new messages
```

The result is a context that scales horizontally. A two-hundred-message conversation does not cost twenty times more than a ten-message one. The history has been folded into a fraction of its original size.


## The Second Insight: The Past Can Be Compressed


Summarization sounds expensive. You are calling the LLM to save money on calling the LLM.


But the math works.


One summarization call, paid once, replaces **thousands of tokens** being resent on every subsequent turn. If the summary covers thirty messages and the conversation runs another fifty turns, you pay for one summary and avoid the cost of thirty messages times fifty turns.


The critical design detail is **incrementality**.


When five new messages arrive, the system does not discard the existing summary and build a new one from scratch. It **updates** the existing one. The new summary incorporates the changes without throwing away the base.


And it never drops **pending work**.


If the user asked for something three summaries ago and it was not done yet, that task stays in the summary, marked as pending, preserved across every incremental update until it is actually completed. This is the prompt that drives it:

```python
# api/src/services/agents/context_summarizer.py

"incremental": """Update the existing summary with new information.

Previous Summary:
{existing_summary}

New Messages to Incorporate:
{messages}

Create an updated summary that:
1. PRESERVE ALL PENDING REQUESTS — Keep any unfulfilled user requests
   from the previous summary unless they were completed in new messages
2. Mark completed tasks as DONE and move them from pending
3. Add new requests, decisions, facts, or state changes
4. Remove only information that is truly outdated or superseded
5. Stays within {max_length} words

CRITICAL: If a user request was pending and still not completed,
it MUST remain in the summary.

Updated Summary:"""
```

The context stays small. The continuity stays intact.


:::centered-statement
compression is not forgetting.
it is remembering more efficiently.
:::


## The Third Insight: Tool Results Are the Real Villain


Conversation history is manageable.


Tool results are not.


An agent that queries a database might get back **a hundred rows**. An agent that fetches a document might get back **three thousand words**. An agent that takes a browser screenshot might send back a **hundred-thousand-character base64 string**.


Every one of those goes into the message history. Every one of those gets resent on every subsequent turn.


We built a pruner that handles this specifically. Its configuration makes the strategy explicit:

```python
# api/src/services/agents/context_pruning.py

@dataclass
class PruningSettings:
    keep_last_results: int = 3     # always keep last N tool results intact
    max_result_chars: int = 5000   # trim results larger than this
    head_chars: int = 1500         # keep first N chars when trimming
    tail_chars: int = 1500         # keep last N chars when trimming

    # Tools that return real data (SQL rows, file contents) get head+tail
    # trimming instead of being collapsed to a 1-liner.
    protect_data_tools: tuple[str, ...] = (
        "internal_execute_",
        "internal_query_",
        "internal_read_",
        "internal_fetch_",
        "internal_list_",
        "internal_search_",
        "internal_database_",
        "internal_sql_",
    )
```

The **last three tool results** stay in full — they are fresh, the model probably still needs them. Everything older goes through a pass that extracts the minimum useful representation.


For tools that return data the model might still need — **database rows**, **file contents**, **query results** — we trim to a head-and-tail view. The model sees the beginning and end of the data with an indicator for what was in the middle:

```python
def _trim_content(content: str, settings: PruningSettings) -> str:
    head = content[: settings.head_chars]
    tail = content[-settings.tail_chars :]
    trimmed_chars = len(content) - settings.head_chars - settings.tail_chars

    return (
        f"{head}\n\n"
        f"[... {trimmed_chars:,} characters trimmed for context efficiency ...]\n\n"
        f"{tail}"
    )
```

For tools that returned **status**, **confirmations**, **IDs**, or **counts** — we replace the entire result with a single informative line. The model can still reason about what happened without holding the full payload:

```python
def _extract_result_summary(tool_name: str, content: Any) -> str:
    # List at top level
    if isinstance(data, list):
        return f"[pruned: {tool_name}: returned {len(data)} items]"

    # Row counts
    if "rows" in data and isinstance(data["rows"], list):
        return f"[pruned: {tool_name}: returned {len(data['rows'])} rows]"

    # Created resource
    if "id" in data:
        return f"[pruned: {tool_name}: id={data['id']}]"

    # Confirmation
    if data.get("success") is True:
        return f"[pruned: {tool_name}: succeeded]"
```

And before any of this, in the very first pass, we strip **base64**. Unconditionally. If a tool result has an embedded image or screenshot, that base64 blob goes — replaced with a note describing what it was and how large. Screenshots alone can save a hundred thousand characters per tool call:

```python
# Catches screenshots, images, and any base64 blob by key name or content pattern
if key.lower() in ("screenshot", "image", "image_data", "base64", "data"):
    if len(value) > 1000 and _looks_like_base64(value):
        size_kb = len(value) * 3 / 4 / 1024
        result[key] = f"[BASE64_REMOVED: ~{size_kb:.1f}KB - use image_url instead]"
```


## The Safety Net


Even with all of this, edge cases exist.


A very long system prompt. A model with a small context window. An unusual conversation that compresses badly. An agent running a genuinely complex multi-step task that needs everything.


For those cases, the **context guard** monitors token usage before every request:

```python
# api/src/services/agents/context_window_guard.py

class ContextWindowGuard:
    WARN_THRESHOLD = 0.40      # warn when 40% remaining
    SUMMARIZE_THRESHOLD = 0.25 # trigger summarization at 25% remaining
    BLOCK_THRESHOLD = 1000     # hard block at 1,000 tokens remaining

    def evaluate(self, model: str, current_tokens: int) -> ContextGuardResult:
        max_tokens = self.get_model_limit(model)
        remaining = max_tokens - current_tokens
        remaining_pct = remaining / max_tokens

        if remaining <= self.BLOCK_THRESHOLD:
            return ContextGuardResult(action=ContextGuardAction.BLOCK, ...)

        if remaining_pct <= self.SUMMARIZE_THRESHOLD:
            return ContextGuardResult(action=ContextGuardAction.SUMMARIZE, ...)

        if remaining_pct <= self.WARN_THRESHOLD:
            return ContextGuardResult(action=ContextGuardAction.WARN, ...)

        return ContextGuardResult(action=ContextGuardAction.OK, ...)
```

The guard knows the context windows for sixty-plus model variants. Claude, GPT, Gemini, reasoning models. No developer configuration required:

```python
MODEL_CONTEXT_LIMITS = {
    "claude-sonnet-4-6": 180000,
    "gpt-4.1":           1000000,
    "gpt-4.1-mini":      1000000,
    "gemini-2.5-pro":    1000000,
    "gemini-2.5-flash":  1000000,
    "o3":                180000,
    "o4-mini":           180000,
    # ... 60+ entries
}
```

If usage climbs above the warn threshold, it logs. If it hits the summarize threshold, compression fires automatically. If fewer than a thousand tokens remain, the request is blocked and the user sees a clear message rather than a silent failure inside the model.


## What This Looks Like in Practice


An agent session with thirty turns and ten tool calls used to send **thirty to forty thousand tokens** per request at turn thirty.


After these optimizations, the same session at the same turn count averages **five to ten thousand tokens**.


The agents behave the same. The responses are the same quality. The continuity is preserved. The cost is **seventy to eighty percent lower**.


The difference is not in what the model does. It is in what you are asking it to hold.


:::centered-statement
an agent should remember what matters.
not everything that ever happened.
:::


## The Principle Behind All of It


Every layer we built was motivated by the same idea.


Context is not a log. It is not an obligation to carry everything forward indefinitely. It is a **communication surface**. You are telling the model what it needs to know to do the next thing well.


The question is not "what happened?" It is "**what does the model need right now?**"


When you answer that question honestly, most of what was in the context can go. The **summary** captures the decisions. The **recent messages** capture the current thread. The **tool results** are pruned to their useful facts. The **base64** is gone.


What remains is lean. What remains is relevant. What remains costs a fraction of what the naive approach costs.


:::ink-band
lean context is a product quality
:::


If you want to see the full implementation, it lives in `api/src/services/agents/` — `context_manager.py`, `context_window_guard.py`, `context_pruning.py`, `context_summarizer.py`. MIT license. No magic, just decisions made explicit.
