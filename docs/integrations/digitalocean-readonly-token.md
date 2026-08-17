# DigitalOcean Least-Privilege Setup for Synkora

1. In the DigitalOcean control panel, go to **API → Tokens/Keys → Generate New Token**.
2. Give it a descriptive name (e.g. `synkora-readonly`).
3. Set scope to **Read-only** — DigitalOcean personal access tokens support a read-only scope
   toggle at creation time; do not grant write access.
4. Copy the token immediately (it is not shown again) and paste it as the API token when adding
   the integration in Synkora (**Integrations → Add Integration → DigitalOcean**). No Config JSON
   fields are required for DigitalOcean.

Note: DigitalOcean has no log-query API and no security-findings equivalent to AWS Security
Hub/GCP SCC/Azure Defender — `internal_digitalocean_get_logs` and
`internal_digitalocean_list_security_findings` always return a "Not supported by DigitalOcean"
result rather than being omitted from the agent's tool list.
