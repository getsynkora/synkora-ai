---
sidebar_position: 6
---

# Billing

Synkora has two distinct cost layers:

1. **platform usage** tracked through plans, credits, and subscriptions
2. **model usage** billed by the LLM providers whose keys you choose to use

## Platform Billing

At the platform level, Synkora supports:

- plans and subscriptions
- credit accounting
- usage analytics
- monetization surfaces for agent-facing products

## Bring Your Own LLM Keys

Synkora is designed around BYOK. That means your organization chooses which provider keys power your agents.

This has two consequences:

- you keep control of provider selection and model spend
- platform credits are not the same thing as direct OpenAI or Anthropic billing

## What To Track

For any serious deployment, track both:

- tenant/platform consumption
- underlying LLM token and provider usage

Synkora’s observability and billing layers are meant to help with that split.

## Related Pages

- [API Usage Reference](/docs/api-reference/billing/usage)
- [Production Deployment](/docs/guides/deployment/production)
