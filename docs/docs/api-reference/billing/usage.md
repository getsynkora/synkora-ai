---
sidebar_position: 4
---

# Billing and Usage API

Synkora exposes usage and billing data because platform operations need visibility, not just chat responses.

## What This Area Covers

- plan and subscription state
- credit accounting
- tenant usage metrics
- cost and usage analytics
- monetization-related platform flows

## Important Model

Treat platform usage and provider usage as separate but related concerns:

- platform usage is tracked by Synkora
- model-provider usage is driven by the keys and providers you configure

## Client Advice

- aggregate usage by tenant and environment
- review cost analytics before expanding tools or high-volume surfaces
- do not mix platform credits with direct provider invoices in your own accounting model
