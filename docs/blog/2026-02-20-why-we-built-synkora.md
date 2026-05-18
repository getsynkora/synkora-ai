---
slug: why-we-built-synkora
title: "Why We Built Synkora: Closing the Gap Between 'It Works' and 'It Works in Production'"
authors: [engineering]
tags: [engineering, architecture, product]
---

There is a specific moment when an AI project changes character.

On Friday, it is a demo.  
On Monday, it is an application someone wants to trust.

That is where most teams discover the real problem was never the prompt.

<!-- truncate -->

:::eyebrow
From AI demo to production system
:::

:::centered-statement
it worked in the demo.
that was the easy part.
:::

![Prototype to production gap](/images/blog/prototype-gap.svg)

*The hardest part of AI is not generating the first answer. It is building everything around the answer.*

## We Kept Watching The Same Story Repeat

A team would connect to a model API, wire up a prompt, and get something useful almost immediately.

That first success is intoxicating. It creates the impression that the rest will be easy.

Then the next requests start arriving:

- "Can we connect it to our knowledge base?"
- "Can we deploy it to Slack too?"
- "Can we separate enterprise customers by workspace?"
- "Can we see usage and cost?"
- "Can we schedule it?"
- "Can we add retries?"
- "Can we give it tools?"
- "Can we self-host this?"

At that point, the project stops being a model experiment and starts becoming an application platform problem.

That is the gap Synkora is designed to close.

:::brush-title
close the gap
between demo and production
:::

## We Did Not Want To Build Another Framework

Frameworks are useful. We use them too.

But frameworks usually hand you building blocks, not a finished operating surface.

You still have to assemble:

- auth
- tenant isolation
- persistence
- background jobs
- delivery surfaces
- monitoring
- cost tracking
- admin tooling
- deployment infrastructure

That is a lot of reinvention for teams whose real job is not "build AI plumbing forever."

We wanted a platform that would let teams spend their energy on agent behavior and business value instead of continually rebuilding the same scaffolding.

:::ink-band
a **production** structure
:::

## The Architecture Decisions We Made

We made a few decisions early that shaped everything afterward.

## Multi-tenancy first, not later

We did not want tenant isolation bolted on after the fact. It changes too much: schemas, permissions, usage attribution, billing, APIs, and operational boundaries.

By treating multi-tenancy as foundational, Synkora can work as:

- a product for multiple customers
- a platform used by multiple internal teams
- a self-hosted system for a single organization with strong logical separation

That decision made the system more opinionated, but also much more honest about real production requirements.

## Stateless API, coordinated execution

The API layer is designed to stay stateless, with durable state living in PostgreSQL, Redis, and external systems.

That makes horizontal scaling straightforward.

It also keeps the architecture clean:

- request/response and WebSocket surfaces at the edge
- Redis for cache, coordination, and cross-pod messaging
- Celery for asynchronous work, retries, and scheduling

This is one of the biggest differences between a toy agent system and a production one. You do not just need "logic." You need controlled execution.

![Runtime architecture](/images/blog/runtime-architecture.svg)

*The platform is organized like an application system, not a notebook stretched too far.*

## Queue separation matters

Background work is not one thing.

Billing operations do not have the same risk profile as notifications. Document processing does not behave like a user-facing conversation. Bot traffic should not starve critical internal jobs.

So Synkora separates queues for default work, notifications, agents, and billing, with dedicated workers where it matters.

That sounds operationally boring. It is. It is also exactly the kind of boring that keeps a system dependable under load.

:::centered-statement
boring infrastructure
is what makes ambitious products trustworthy.
:::

## PostgreSQL as the system of record

We chose PostgreSQL with `pgvector` as the core database because the platform needs a strong transactional center, not just a vector index.

Agents, users, tenants, API keys, billing state, conversations, workflows, and permissions all want a real relational backbone.

For retrieval-heavy deployments, Synkora can also work with Qdrant, Pinecone, and Elasticsearch. That gives teams flexibility without fragmenting the heart of the platform.

## Specialized services where they help

Not every capability belongs inside the main API process.

So the architecture uses dedicated services where that boundary pays off:

- an ML service for embeddings and reranking
- a scraper/browser automation service for Playwright-based work
- background workers for asynchronous tasks
- observability integrations for tracing and evaluation

This keeps the core platform simpler while still supporting richer agent behaviors.

## Observability and cost attribution are not extras

One of the most common failure modes in AI systems is discovering too late that nobody can explain:

- why a response was slow
- which model calls got expensive
- where quality dropped
- which tenant drove usage
- what happened before a failure

That is why Synkora bakes in usage tracking, billing infrastructure, and Langfuse-based observability as part of the architecture story, not as an afterthought.

## The Product Surface Grew With The Architecture

As the platform matured, so did the places agents could live.

What started as an architecture problem naturally became a delivery problem:

- dashboard-driven agent management
- embeddable web widget
- REST API access
- Slack, Telegram, WhatsApp, and Teams bots
- voice-oriented assistant experiences
- browser-aware companion surfaces like the Chrome extension
- app embedding paths like the Flutter SDK

That expansion was important for one reason: useful agents need to meet people where they already work.

## What We Were Really Building

At some point it became clear that we were not building "a chatbot product."

We were building the application layer for AI agents:

- the control plane
- the delivery layer
- the operational model
- the ownership model

That is why Synkora is open source, self-hostable, and provider-agnostic.

The goal is not just to help teams experiment with AI. The goal is to help them own it.

## The Feeling We Want Teams To Have

Not excitement alone.

Confidence.

Confidence that an agent can move from prototype to production without being rewritten from scratch.

Confidence that the platform underneath it understands tenants, scheduling, channels, usage, and ops.

Confidence that the system can grow with the business instead of collapsing under the weight of its first real users.

:::ink-band
confidence is a product feature
:::

That is why we built Synkora.

If that problem feels familiar, start with the [architecture overview](/docs/architecture/overview), explore the [Quick Start Guide](/docs/getting-started/quick-start), and see how the platform is put together in the [documentation](/docs).
