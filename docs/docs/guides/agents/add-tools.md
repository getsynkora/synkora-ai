---
sidebar_position: 1
---

# Add Tools to an Agent

Tools turn a Synkora agent from a text responder into an operator that can fetch, act, transform, and orchestrate work.

## Tool Sources

In Synkora, tools usually come from one of four places:

- built-in platform tools
- OAuth-backed integrations
- custom tools
- MCP servers

## Typical Workflow

1. Open the target agent in the dashboard
2. Go to the tools section
3. Enable only the tools the agent actually needs
4. Save the agent
5. Test with prompts that require tool use

## Good Tool Design

- add tools only when the agent needs to act
- scope tools to a narrow task domain
- avoid giving write-capable tools to broad “general assistant” agents unless necessary
- review tenant and permission boundaries before rollout

## Common Tool Patterns

- support agent: KB retrieval + ticketing + Slack notifications
- research agent: web/browser tools + note capture + export
- internal ops agent: custom tools + OAuth apps + scheduled runs

## Related Pages

- [Custom Tools](/docs/guides/agents/custom-tools)
- [MCP Servers](/docs/guides/agents/mcp-servers)
