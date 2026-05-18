---
sidebar_position: 1
---

# Embed the Web Widget

The Synkora widget is the fastest way to put an agent on a website or customer portal.

## What You Need

- a running Synkora instance
- a configured widget in the dashboard
- the widget ID and widget API key

## Basic Embed

```html
<script src="https://your-instance.com/widget.js"></script>
<script>
  SynkoraWidget.init({
    widgetId: "your-widget-id",
    apiKey: "swk_...",
  });
</script>
```

## With Identified User

```html
<script src="https://your-instance.com/widget.js"></script>
<script>
  SynkoraWidget.init({
    widgetId: "your-widget-id",
    apiKey: "swk_...",
    user: {
      id: "usr_123",
      name: "Alice",
      email: "alice@example.com",
      orgId: "acme",
    },
  });
</script>
```

## With Identity Verification

If identity verification is enabled on the widget, your server must compute `userHash` and pass it to the browser. Do not compute it in frontend code.

```html
<script src="https://your-instance.com/widget.js"></script>
<script>
  SynkoraWidget.init({
    widgetId: "your-widget-id",
    apiKey: "swk_...",
    user: { id: "usr_123", orgId: "acme" },
    userHash: "{{ server_computed_hash }}",
  });
</script>
```

## Agent Routing

Widgets can route different organizations to different agents when:

- agent routing is enabled on the widget
- a `user.orgId` is provided
- routes are configured in Synkora

## Operational Advice

- start anonymous if you only need public website chat
- enable identity verification for customer or account-specific use cases
- use org-based routing when one widget must serve many customer workspaces
