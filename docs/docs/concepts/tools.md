---
sidebar_position: 3
---

# Tools

Tools are how Synkora agents move from answering to acting.

## Tool Types in Synkora

### Built-in tools

Platform-provided tools such as browser automation, search, file handling, or internal compute paths.

### OAuth-backed tools

Tools that act against connected third-party services after a user or admin authorizes them.

### Custom tools

Tenant- or product-specific tools you define to expose business logic to agents.

### MCP servers

Model Context Protocol servers let you plug external tool ecosystems into Synkora using an increasingly standard interface.

## Choosing the Right Tool Type

- use **built-in tools** for common platform behavior
- use **OAuth tools** when the agent must work inside SaaS systems
- use **custom tools** when the capability is unique to your business
- use **MCP** when you want a standard integration boundary or external tool host

## Tool Governance

Treat tool access as product behavior, not decoration.

Review:

- who can invoke the agent
- what side effects the tool can trigger
- which tenants or workspaces can access the tool
- whether the tool should be available in every surface

## Related Pages

- [Add Tools](/docs/guides/agents/add-tools)
- [Custom Tools](/docs/guides/agents/custom-tools)
- [MCP Servers](/docs/guides/agents/mcp-servers)
