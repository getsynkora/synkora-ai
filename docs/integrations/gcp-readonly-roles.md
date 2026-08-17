# GCP Least-Privilege Setup for Synkora

Create a dedicated service account and grant it these **predefined, read-only** IAM roles at the
project level (no custom role needed):

| Role | Purpose |
|---|---|
| `roles/logging.viewer` | Cloud Logging — read log entries |
| `roles/monitoring.viewer` | Cloud Monitoring — read metrics, alert policies, incidents |
| `roles/compute.viewer` | Compute Engine — read instance/GKE resource status |
| `roles/securitycenter.findingsViewer` | Security Command Center — read findings |
| `roles/resourcemanager.projectIamAdmin` is **not** needed — only used at setup time to grant the
  service account these roles, then can be removed from your own account. |

## Steps

1. In the GCP Console, go to **IAM & Admin → Service Accounts → Create Service Account**.
2. Grant the roles above under **Grant this service account access to project**.
3. Create a JSON key for the service account (**Keys → Add Key → JSON**) and download it.
4. In Synkora, go to **Integrations → Add Integration → Google Cloud Platform**, paste the full
   downloaded JSON as the API token, and set `project_id` in the Config JSON field.

Security Command Center findings require SCC to be enabled on the project/organization — if it
isn't, `internal_gcp_list_security_findings` will return an explicit "not enabled" error rather
than failing silently.
