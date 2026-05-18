---
sidebar_position: 3
---

# Okta SSO

Okta SSO is the right choice when Synkora is being adopted as an internal platform and user identity must stay under centralized enterprise control.

## Use Okta When

- employees should not manage local credentials in Synkora
- identity lifecycle is already owned by IT
- environment access must follow enterprise group policies

## High-Level Flow

1. Create the Okta app
2. Configure redirect URIs
3. Enter the Okta settings in Synkora
4. Test with a staging environment first
5. Roll out tenant by tenant or environment by environment

## Rollout Advice

- do not enable SSO first in production
- test group mappings and tenant access carefully
- document an emergency break-glass admin path before rollout
