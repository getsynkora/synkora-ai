---
sidebar_position: 5
---

# Integrations and OAuth API

This part of the API surface supports external service connectivity and authorization-driven workflows.

## Typical Capabilities

- register OAuth apps
- manage provider configuration
- authorize and refresh external connections
- attach external capabilities to agents and tools

## Design Notes

OAuth is not only a user-login problem in Synkora. It is also part of how agents safely gain access to third-party systems.

## Client Advice

- model provider connections separately from user identity auth
- scope OAuth apps by environment
- keep redirect URIs and callback hosts consistent
