## ADDED Requirements

### Requirement: Scopes are sourced from OAuthApp, not hardcoded in controllers
The system SHALL use `oauth_app.scopes` as the source of truth for OAuth scopes. Hardcoded defaults in controller code SHALL only apply when `oauth_app.scopes` is null or empty, and they SHALL represent the minimum required scopes for the provider.

#### Scenario: OAuthApp has explicit scopes configured
- **WHEN** `oauth_app.scopes = ["repo", "user"]` and `initiate_oauth` is called for GitHub
- **THEN** the authorization URL is built with exactly `["repo", "user"]`
- **THEN** the hardcoded default `["repo", "user", "read:org"]` is NOT appended or merged

#### Scenario: OAuthApp has no scopes configured
- **WHEN** `oauth_app.scopes` is null
- **THEN** the minimum required default scopes for that provider are used
- **THEN** the defaults are documented per provider in code comments

### Requirement: Controller scope defaults are least-privilege
When `oauth_app.scopes` is null, the fallback defaults in each controller SHALL request only the minimum scopes needed for the tool's functionality. Write scopes SHALL NOT be included unless the tool explicitly requires write access.

#### Scenario: Read-only Slack integration default scopes
- **WHEN** a Slack OAuth app is created without explicit scopes
- **THEN** the default scopes do not include `chat:write` unless the tenant's agent has write tools enabled

#### Scenario: GitHub default includes only necessary scopes
- **WHEN** a GitHub OAuth app is created without explicit scopes
- **THEN** the default scopes are `["repo", "user:email"]`, not `["repo", "user", "read:org"]` unless org features are used

### Requirement: Scope validation is logged on mismatch
When a provider returns a token with scopes that differ from the requested scopes, the system SHALL log a warning with the expected and granted scope lists.

#### Scenario: Provider grants fewer scopes than requested
- **WHEN** the token exchange response includes a `scope` field with fewer scopes than requested
- **THEN** a warning is logged: "OAuth scope mismatch for provider=<X>: requested=<...> granted=<...>"
- **THEN** the token is still stored (provider decision is authoritative)

#### Scenario: Provider does not return scope in response
- **WHEN** the token exchange response does not include a `scope` field (e.g., GitHub)
- **THEN** no warning is logged (provider behavior is expected)

### Requirement: Auth method is enforced at initiation
The system SHALL reject OAuth initiation for apps configured with `auth_method=api_token` or `auth_method=github_app` without triggering a browser OAuth redirect. These methods have no authorization code flow.

#### Scenario: API token app initiation
- **WHEN** `initiate_oauth` is called for an `oauth_app_id` with `auth_method=api_token`
- **THEN** the response returns `{ auth_url: "...?oauth=success&method=api_token" }` immediately
- **THEN** no OAuth state is created in Redis
- **THEN** no redirect to the provider occurs
