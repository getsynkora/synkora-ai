---
sidebar_position: 5
---

# Multi-Tenancy

Multi-tenancy is foundational in Synkora. It is not a feature layered on after the fact.

## What It Means in Practice

Synkora scopes platform objects around tenants and workspaces, including:

- agents
- knowledge bases
- API keys
- usage and billing data
- integrations and OAuth connections
- roles and permissions

## Why This Matters

Multi-tenancy makes Synkora usable as:

- a SaaS platform serving many customers
- an internal platform serving many teams
- a self-hosted installation with strong logical separation

## Isolation Boundaries

At a high level, tenant boundaries affect:

- data visibility
- access control
- quota and credit accounting
- deployment configuration
- monitoring and reporting

## Design Guidance

- keep production tenants separate even if the use case feels similar
- do not treat “projects” as a replacement for true tenant boundaries
- pair tenant boundaries with clear role models and API key ownership
