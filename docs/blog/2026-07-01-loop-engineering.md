---
slug: loop-engineering-is-distributed-systems
title: "Loop Engineering Is Distributed Systems. Except for the Four Parts That Aren't."
authors: [engineering]
tags: [engineering, architecture, agents, distributed-systems, production]
---


We were debugging an agent loop that wouldn't stop.


The model kept calling the same broken database query. Same tool, same arguments, same error. Over and over. Classic distributed systems problem — no circuit breaker on the inner loop.


We added one. Fixed it in twenty minutes.


Two hours later we had a different problem. The context had accumulated nine copies of the same error message and the model was making new decisions based on the noise. It was not confused about the tool. It was confused about its own history.


That was not a circuit breaker problem. That was something we had never seen in a distributed system before.


<!-- truncate -->


:::eyebrow
On loop engineering, distributed systems, and what is actually new
:::


:::brush-title
most of it is old.
four parts are not.
:::


*Loop engineering is getting a lot of attention right now. Steinberger, Cherny, Osmani — the framing is compelling: design systems that run agents, not just prompts. They are right. What they have not said out loud is that this framing describes a distributed system. We have been building those for twenty years. The interesting question is which parts are actually different.*


## The Mapping Nobody Publishes


When we started building Synkora, the first thing we did was map every "loop engineering" concept to the distributed systems primitive it corresponds to.


It took about an afternoon.


| What Loop Engineering Calls It | What It Actually Is |
|---|---|
| Agent loop with a stopping condition | Queue worker with iteration limit and circuit breaker |
| Memory outside the conversation | External key-value store (Redis, Postgres) |
| Sub-agents that don't collide | Isolated workers with scoped permissions |
| Verification loop with retry | Consumer with dead-letter and max retry count |
| Event-driven loop — cron or webhooks | Cron scheduler + idempotent event delivery |
| Stopping condition | Circuit breaker + resource budget |
| Human checkpoint | Middleware interceptor with blocking execution gate |
| Hill-climbing feedback loop | Observability pipeline feeding a consumer |


Every term has a twenty-year-old equivalent. Message queues, key-value stores, circuit breakers, cron daemons, dead-letter queues, middleware chains, observability pipelines. We built all of those things into Synkora from day one — not because we read the loop engineering articles, but because we knew what reliable distributed systems look like.


The developer who built a Korean-to-English translation loop — plan, execute, critique, repair, reference translator as impartial witness — described this exact architecture. Their loop failed after two weeks because the critic was never satisfied and the loop had no stopping condition. No circuit breaker. No max-retry count on the verification cycle. Classic distributed systems failure, a classic distributed systems fix.


:::centered-statement
the vocabulary changed.
the patterns did not.
:::


## What Actually Needed Rebuilding


Here is the part the mapping does not capture.


There are four places where the LLM changes the failure mode in a way that standard distributed systems patterns do not cover. We found all four of them by running agents in production and watching things break in ways that surprised us.


### 1. The circuit breaker needs an error signature, not just a count


In a traditional distributed system, you count failures. Five consecutive failures on a database connection — open the circuit.


In an agent loop, count-based circuits are not enough.


The model exploring five different tools, each failing once, looks identical to the model stuck calling the same broken tool five times in a row. A count-based breaker cannot tell the difference. One is healthy exploration. The other is a runaway loop eating tokens.


What we needed was a circuit keyed on **tool name plus error signature**:


```python
# api/src/services/agents/error_tracker.py

error_key = f"{tool_name}:{error_message[:100]}"
self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1

if self.error_counts[error_key] >= self.max_repeated_errors:
    return True  # same tool, same error — break the loop
```


Same tool failing with the same error three times: stop.
Three different tools failing with different errors: keep going.


The standard circuit breaker does not know about tool names. It cannot make this distinction. We had to build a separate breaker for the agent loop specifically.


### 2. The context window is a resource that compounds like no other


In a traditional distributed system, the cost of a request is roughly proportional to its compute.


In an agent loop, the cost of a request is proportional to the **accumulated context** — everything the model has seen since the start of the session. The compute each turn is similar. The token bill is not.


A ten-message session is cheap. A sixty-message session with active tool use sends thirty to forty thousand tokens per request at turn thirty — most of it from database rows, web search results, and Slack threads that were relevant twelve turns ago and have not changed.


The model has already processed all of that. You are paying to send it again anyway.


No distributed systems pattern handles this because traditional systems do not have state that travels with every request, grows over time, and gets billed per byte.


We built a three-layer pruner specifically for this:


```python
# api/src/services/agents/context_pruning.py

@dataclass
class PruningSettings:
    keep_last_results: int = 3      # last 3 tool results stay intact
    max_result_chars: int = 5000    # older ones get trimmed
    head_chars: int = 1500          # keep first N chars
    tail_chars: int = 1500          # keep last N chars
```


The last three tool results stay in full — the model probably still needs them. Older ones get a head-and-tail view. Base64 blobs — screenshots, image data — get stripped unconditionally. A single browser screenshot can be a hundred thousand characters.


After these optimizations: the same thirty-turn session averages five to ten thousand tokens per request instead of thirty to forty thousand. Same agent, same quality, seventy percent lower cost. That number comes from real sessions on Synkora, not an estimate.


### 3. Observability needs to capture reasoning, not just execution


A distributed systems trace tells you: request came in, service A called service B, B called C, response went out. Each hop has a latency, a status code, a payload.


That is not enough for an agent.


An agent can call the right tool, get the right data, and still produce the wrong answer. Nothing in the execution trace fails. The latency is normal. The status codes are 200. The response looks confident. And it is wrong.


We had a support ticket like this. The agent retrieved correct data on turn four. The model summarized it incorrectly on turn nine. The trace showed clean execution at every step. There was no signal in the logs that anything had gone wrong.


What we needed was a trace that captured **what the model saw** at the moment it made each decision — not just what happened when the tool ran.


Agent Lens records the full sequence: message received, context assembled before the LLM call, tokens at the time of each decision, tool invoked, result returned, pruning fired, response emitted. Each event is structured and written to Elasticsearch. The aggregation runs on the read path — no latency impact on the stream.


The prompt caching bug that cost us months of unnecessary spend? Found by reading Agent Lens traces. Every session showed `cache_read_tokens: 0` on every turn after the first. Clean execution. Wrong cost. No error anywhere in the system. The trace told us before the invoice did.


### 4. State that travels inside natural language is different


In a traditional distributed system, state is explicit. It is a database row, a Redis key, a message payload. You know exactly what it is. You can inspect it, validate it, transform it.


In an agent loop, the most important state is the context window — and it is natural language. The model's "understanding" of the conversation is encoded in tokens, not in typed data structures. You cannot write a schema for it. You cannot validate it. You can only read it and hope.


This creates a failure mode we call context poisoning.


The model's context accumulates noise — stale tool results, outdated information, repeated errors. The model continues to reason from that noise. Its answers degrade. Nothing throws an exception. The degradation is invisible without specific tooling to watch it.


Our incremental summarizer handles one version of this — replacing old messages with a compressed summary while explicitly preserving unfinished tasks:


```python
# api/src/services/agents/context_summarizer.py

"PRESERVE ALL PENDING REQUESTS — Keep any unfulfilled user requests
 from the previous summary unless they were completed in new messages.
 Mark completed tasks as DONE and move them from pending."
```


But the deeper version — the model making wrong inferences from accumulated noise — is still unsolved at the infrastructure level. It requires human oversight or a verification loop with a well-specified rubric. Traditional distributed systems have no equivalent. The failure mode does not exist when state is typed.


:::ink-band
four things are actually new.
everything else you already know how to build.
:::


## What This Means If You Are Building Loops


The loop engineering hype is not wrong. The insight — that system design matters more than prompt crafting — is the right one for where the field is right now.


But if you are building agent loops from scratch, you do not need to invent new infrastructure. You need two things:


**First:** Deploy the distributed systems primitives you already know. Queue-backed workers, circuit breakers, cron schedulers, idempotent event delivery, key-value state, dead-letter queues, observability pipelines. These are well-understood. Synkora ships them all as open-source, MIT-licensed infrastructure.


**Second:** Build the four things that are actually different. An error-signature circuit breaker for the agent loop. A token-aware context pruner that understands tool result types. An observability layer that captures what the model saw, not just what the infrastructure did. A strategy for context poisoning.


The first list is not interesting. It is table stakes for any production system, and good implementations exist.


The second list is where the real work is. Most loop engineering literature does not discuss it. Most agent frameworks do not ship it. It is the difference between a loop that runs and a loop that runs reliably under real load, for real users, for months.


The implementation lives in `api/src/services/agents/` — `function_calling.py` for the bounded executor, `error_tracker.py` for the error-signature breaker, `context_pruning.py` and `context_manager.py` for token-aware memory, `agent_trace_service.py` for reasoning-level observability.


MIT license. Built from running this in production.
