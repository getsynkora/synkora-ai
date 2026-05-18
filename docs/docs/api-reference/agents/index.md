---
sidebar_position: 2
---

# Agents API

The agents API is the center of the platform. It covers creating, configuring, and operating agents as first-class product objects.

## Typical Capabilities

- create and update agents
- configure model behavior
- attach knowledge bases
- enable tools and integrations
- chat with agents
- manage agent outputs and deployment surfaces

## Design Notes

In Synkora, an “agent” is more than prompt text. API operations usually touch one or more of:

- identity and metadata
- model settings
- knowledge attachments
- tool configuration
- deployment surfaces
- keys, monetization, or billing controls

## Client Advice

- treat agent IDs and slugs as stable integration references
- separate configuration writes from runtime chat traffic
- use streaming-compatible clients for interactive chat

## See Also

- [Concept: Agents](/docs/concepts/agents)
- [Guide: Create a RAG Agent](/docs/guides/agents/create-rag-agent)
