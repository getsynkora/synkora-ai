---
sidebar_position: 3
---

# Build Custom Tools

Custom tools let you expose business-specific capabilities to Synkora agents.

## Use Custom Tools When

- the action is unique to your product or workflow
- a built-in tool is not enough
- an OAuth provider does not model the behavior you need
- you want a controlled interface over internal business logic

## What Makes a Good Custom Tool

A good custom tool has:

- a narrow purpose
- a predictable schema
- clear success and error outputs
- explicit side-effect boundaries

## Design Rules

- keep parameters explicit
- avoid one giant “do anything” tool
- make write actions obvious
- return structured output the model can reason about

## Security Advice

- validate every input server-side
- authenticate outside the model layer
- enforce tenant boundaries in the tool implementation
- log sensitive actions

## When To Use MCP Instead

If the capability already exists behind an MCP server or you want a standard external tool boundary, prefer MCP over inventing a custom one-off integration layer.
