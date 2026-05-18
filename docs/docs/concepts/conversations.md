---
sidebar_position: 4
---

# Conversations

Conversations are the runtime record of how users interact with agents across the platform.

## What a Conversation Represents

A conversation usually includes:

- a target agent
- user messages
- assistant responses
- streaming state
- surface-specific identifiers
- optional system or tool context

## Where Conversations Happen

Conversations can originate from:

- dashboard chat
- widget sessions
- API clients
- messaging bots
- extension surfaces
- mobile clients using the Flutter chat SDK

## Streaming Model

Synkora is streaming-first. In most interactive surfaces, responses are sent incrementally so the user sees progress immediately instead of waiting for one large response payload.

## Context Model

Conversation behavior is shaped by:

- the agent’s system prompt
- prior message history
- attached knowledge bases
- tool results
- optional page or surface context, depending on the client

## Why Conversations Matter Operationally

Conversations are not just UX data. They drive:

- support workflows
- evaluation and debugging
- usage tracking
- billing attribution
- escalation and follow-up flows
