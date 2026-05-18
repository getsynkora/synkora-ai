---
sidebar_position: 5
---

# Authentication

Synkora uses different authentication models for different surfaces. That is intentional: a dashboard user, a public widget, and a Chrome extension should not authenticate the same way.

## Main Authentication Modes

### Dashboard authentication

Used by the web app for human users managing tenants, agents, knowledge bases, and integrations.

### Agent API keys

Used when an external service or application needs to talk to a specific agent through the API.

### Widget keys

Used by the embeddable web widget. Widgets also support optional identity verification via `userHash`.

### OAuth application connections

Used when agents need access to third-party services such as Google or Microsoft ecosystems.

### Okta / SSO

Used for enterprise authentication flows in environments that need centralized identity control.

### Chrome extension PKCE flow

The Chrome extension authenticates through a browser-safe PKCE flow rather than reusing dashboard cookies directly.

## Practical Rules

- Use **dashboard auth** for people
- Use **agent API keys** for server-to-server agent access
- Use **widget keys** for embedded chat surfaces
- Use **OAuth app connections** when agents need external service permissions
- Use **SSO** for enterprise workforce identity

## Widget Identity Verification

If a widget is configured to require identity verification:

- your server computes an HMAC over the user ID
- the browser receives only the resulting `userHash`
- requests without a valid hash are rejected

This is the right pattern for customer-facing widgets where identity matters.

## Extension Authentication

The Chrome extension uses:

- PKCE
- stored extension-scoped tokens
- per-instance authorization against your Synkora deployment

This keeps the extension isolated from your normal browser session model.

## Related Pages

- [API Keys](/docs/guides/auth/api-keys)
- [OAuth Providers](/docs/guides/auth/oauth-providers)
- [Okta SSO](/docs/guides/auth/sso-okta)
- [Chrome Extension](/docs/guides/integrations/chrome-extension)
