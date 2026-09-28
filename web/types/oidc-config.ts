/**
 * OIDC SSO Types
 */

export interface OIDCConfig {
  id: string
  tenant_id: string
  provider_name: string
  discovery_url: string
  client_id: string
  has_client_secret: boolean
  scopes: string[]
  email_claim: string
  name_claim: string
  jit_provisioning: boolean
  force_oidc: boolean
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface OIDCConfigRequest {
  provider_name: string
  discovery_url: string
  client_id: string
  client_secret?: string | null
  scopes?: string[]
  email_claim?: string
  name_claim?: string
  jit_provisioning?: boolean
  force_oidc?: boolean
  is_active?: boolean
}
