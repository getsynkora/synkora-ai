# Azure Least-Privilege Setup for Synkora

Register an **Azure AD App Registration** and grant it these **built-in, read-only** RBAC roles,
scoped to the subscription (or a specific resource group if you want tighter scope):

| Role | Purpose |
|---|---|
| `Reader` | VM/AKS/general resource metadata and health |
| `Monitoring Reader` | Azure Monitor Logs, Metrics, and Alert rules |
| `Security Reader` | Microsoft Defender for Cloud assessments |

## Steps

1. In the Azure Portal, go to **Azure Active Directory → App registrations → New registration**.
2. Under **Certificates & secrets**, create a new client secret and copy its value immediately (it
   is not shown again).
3. In **Subscriptions → [your subscription] → Access control (IAM) → Add role assignment**, assign
   `Reader`, `Monitoring Reader`, and `Security Reader` to the app registration.
4. In Synkora, go to **Integrations → Add Integration → Microsoft Azure**, enter the app's Client
   ID as the client ID and the client secret as the API token, then set `azure_tenant_id` and
   `subscription_id` in the Config JSON field.

Log Analytics workspace queries additionally require the app to have at least `Reader` access on
the specific workspace resource (covered by the subscription-level `Reader` role above unless the
workspace lives in a different subscription).
