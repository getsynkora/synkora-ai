---
sidebar_position: 4
---

# Connect MCP Servers

Synkora supports MCP servers as a standard way to extend agent capabilities with external tools and resources.

## Why Use MCP

Use MCP when you want:

- a cleaner boundary between Synkora and external tools
- reusable tool ecosystems
- less custom integration glue

## Typical Flow

1. Prepare or identify an MCP server
2. Configure access and authentication
3. Connect it to the target agent
4. Test with narrow prompts first

## Good Use Cases

- file systems
- internal databases
- operational tooling
- domain-specific service layers

## Operational Advice

- isolate MCP servers from your main app runtime
- authenticate every connection
- limit exposed capabilities
- monitor latency and failure paths

## Related Pages

- [Tools](/docs/concepts/tools)
- [Custom Tools](/docs/guides/agents/custom-tools)
