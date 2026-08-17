## Why

The OAuth integration handles sensitive credentials and access tokens for 15+ providers across a multi-tenant platform, yet no systematic security audit has been done end-to-end. Vulnerabilities here — token leakage, CSRF bypass, open redirects, improper state management, or cross-tenant access — could expose user accounts across all tenants.

## What Changes

- Audit and harden the OAuth state/CSRF protection layer
- Audit token storage, encryption, and cross-tenant isolation for both app-level and user-level tokens
- Audit the platform app clone mechanism for cross-tenant token leakage
- Audit the callback handlers for all 15 providers for code injection, open redirect, and state fixation issues
- Audit the credential resolver for token leakage and privilege escalation paths
- Audit `redirect_uri` validation, error redirect flows, and information disclosure
- Audit scope handling and over-permissioning across providers
- Fix all identified vulnerabilities
- Document the security model and remaining risks

## Capabilities

### New Capabilities

- `oauth-state-security`: Redis-backed state lifecycle, CSRF guarantees, PKCE support
- `oauth-token-isolation`: Tenant-scoped token storage, platform app cloning, cross-tenant isolation guarantees
- `oauth-callback-hardening`: Per-provider callback security (redirect validation, state verification, error handling)
- `oauth-credential-resolver-security`: Runtime credential resolution, token priority chain, privilege escalation prevention
- `oauth-scope-governance`: Scope minimization, provider-specific defaults, over-permission detection

### Modified Capabilities

<!-- No existing spec-level capabilities are changing — this is net-new audit coverage -->

## Impact

- `api/src/controllers/oauth/` — all provider callback controllers
- `api/src/controllers/oauth/base.py` — generic initiation, platform clone logic, IDOR protection
- `api/src/services/oauth/` — all provider OAuth service classes
- `api/src/services/security/oauth_state_service.py` — state management
- `api/src/services/security/oauth_security.py` — redirect validation
- `api/src/services/agents/credential_resolver.py` — runtime token resolution
- `api/src/models/oauth_app.py` and `user_oauth_token.py` — data model security
- No breaking API changes expected; fixes will be backward-compatible
