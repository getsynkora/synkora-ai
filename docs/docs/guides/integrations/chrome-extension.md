---
sidebar_position: 6
---

# Use the Chrome Extension

The Synkora Chrome extension gives agents a browser-native side panel with page context and selection-aware workflows.

## What the Extension Does

- opens as a browser side panel
- authenticates against your Synkora instance with PKCE
- reads page context from the active tab
- lets users ask an agent about the current page
- supports selection-based “ask agent” flows

## Local Development

```bash
cd extension
pnpm install
pnpm dev
```

For a production build:

```bash
pnpm build
```

## Connect the Extension

1. Open the extension popup or side panel
2. Enter your Synkora instance URL
3. Complete the authorization flow
4. Choose an agent

## Typical Use Cases

- summarize the current page
- extract takeaways from research
- draft replies based on page content
- ask an internal agent about a document or tool UI you are viewing

## Notes

- this is a browser companion, not a full desktop app
- page context comes from the active tab
- authentication is isolated to the extension’s PKCE flow
