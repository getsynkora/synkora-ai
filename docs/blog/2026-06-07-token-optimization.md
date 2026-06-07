
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


The result is a context that scales horizontally. A two-hundred-message conversation does not cost twenty times more than a ten-message one. The history has been folded into a fraction of its original size.


## The Second Insight: The Past Can Be Compressed


Summarization sounds expensive. You are calling the LLM to save money on calling the LLM.


But the math works.


One summarization call, paid once, replaces **thousands of tokens** being resent on every subsequent turn. If the summary covers thirty messages and the conversation runs another fifty turns, you pay for one summary and avoid the cost of thirty messages times fifty turns.


The critical design detail is **incrementality**.


When five new messages arrive, the system does not discard the existing summary and build a new one from scratch. It **updates** the existing one. The new summary incorporates the changes without throwing away the base.


And it never drops **pending work**.


If the user asked for something three summaries ago and it was not done yet, that task stays in the summary, marked as **pending**, preserved across every incremental update until it is actually completed.


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


We built a **pruner** that handles this specifically.


The **last three tool results** stay in full — they are fresh, the model probably still needs them. Everything older goes through a pass that extracts the minimum useful representation.


For tools that return data the model might still need — **database rows**, **file contents**, **query results** — we trim to a head-and-tail view. The model sees the beginning and end of the data with an indicator for what was in the middle.


For tools that returned **status**, **confirmations**, **IDs**, or **counts** — we replace the entire result with a single informative line. Something like: `returned 47 rows`. Or: `ticket #4217 created`. Or: `message sent successfully`.


The model can still reason about what happened. It just does not need to hold the full payload in memory to do it.


And before any of this, in the very first pass, we strip **base64**. Unconditionally. If a tool result has an embedded image or screenshot, that base64 blob goes. Replaced with a placeholder that says what it was and how large. **Screenshots alone** can save a hundred thousand characters per tool call.


## The Safety Net


Even with all of this, edge cases exist.


A very long system prompt. A model with a small context window. An unusual conversation that compresses badly. An agent running a genuinely complex multi-step task that needs everything.


For those cases, the **context guard** monitors token usage before every request and signals the appropriate response.


If usage is above **sixty percent** of the model's limit, it warns.


If it climbs above **seventy-five percent**, it triggers compression automatically.


If fewer than **a thousand tokens** remain, it blocks the request entirely and surfaces a message to the user rather than letting it fail silently inside the model.


The guard knows the context windows for **sixty-plus model variants**. Claude, GPT, Gemini, reasoning models. It applies the right limits without the developer having to think about it.


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


If you want to see the implementation, it lives in `api/src/services/agents/` — the context manager, the window guard, the pruner, the summarizer. All of it is in the open-source repo. MIT license. No magic, just decisions made explicit.
