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

## Page Context Awareness

Tell the agent what the visitor is currently looking at, so questions like "is
this overdue?" or "what's this user's plan?" don't need to be spelled out.
`page_context` is free-form — use whatever shape fits your domain.

```html
<script>
  SynkoraWidget.init({ widgetId: "your-widget-id", apiKey: "swk_..." });

  SynkoraWidget.setContext("your-widget-id", {
    entity_type: "invoice",
    invoice_id: "INV-88213",
    customer_name: "Acme Rockets",
    amount_due: "$4,250.00",
    status: "overdue",
  });
</script>
```

- Call `setContext` again whenever the visitor navigates to a new record or page —
  it **replaces** the previous value, it does not merge.
- On single-page apps, the widget automatically resets context back to a
  `{url, title}` baseline whenever it detects client-side navigation
  (`pushState`/`replaceState`/`popstate`/`hashchange`), so stale context never
  leaks onto an unrelated page even if you forget to clear it.
- Call `SynkoraWidget.clearContext("your-widget-id")` to explicitly reset back to
  the baseline (e.g. when leaving a record page for a generic one).
- Context is capped at ~500 bytes serialized; oversized payloads are silently
  dropped for that message rather than failing the request.
- This is purely situational awareness for the agent's answers — it does not let
  the widget take actions on your app. Actions still go through your own MCP
  server/tool integration, which the agent already connects to separately.

## Agent Routing

Widgets can route different organizations to different agents when:

- agent routing is enabled on the widget
- a `user.orgId` is provided
- routes are configured in Synkora

## Operational Advice

- start anonymous if you only need public website chat
- enable identity verification for customer or account-specific use cases
- use org-based routing when one widget must serve many customer workspaces
