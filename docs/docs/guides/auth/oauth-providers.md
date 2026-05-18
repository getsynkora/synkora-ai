---
sidebar_position: 2
---

# OAuth Providers

OAuth providers let Synkora agents access external systems through user- or admin-authorized connections.

## Where OAuth Fits

Use OAuth when agents need to work with services such as:

- Google
- Microsoft ecosystems
- GitHub
- Slack
- other supported SaaS applications

## Setup Pattern

1. Create the OAuth app in the external provider
2. Configure client credentials in Synkora
3. Define redirect URIs correctly
4. Authorize the connection from the correct account or workspace
5. Bind the resulting access path to the agent or tool

## Security Advice

- grant only the scopes you actually need
- separate admin-level connections from end-user connections
- keep redirect URIs environment-specific
