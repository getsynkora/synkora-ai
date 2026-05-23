import { apiClient } from './http'

export interface PortalBrandingConfig {
  logo_url?: string
  favicon_url?: string
  primary_color?: string
  secondary_color?: string
  font_family?: string
  site_title?: string
  tagline?: string
  footer_text?: string
  social_links?: {
    twitter?: string
    linkedin?: string
    github?: string
    website?: string
  }
}

export interface PortalSEOConfig {
  meta_description?: string
  og_image_url?: string
}

export interface TenantPortal {
  id: string
  tenant_id: string
  portal_enabled: boolean
  subdomain: string | null
  portal_domain: string | null
  branding_config: PortalBrandingConfig | null
  featured_agent_slugs: string[] | null
  seo_config: PortalSEOConfig | null
  created_at: string
  updated_at: string
}

export interface UpdatePortalSettingsBody {
  portal_enabled?: boolean
  portal_domain?: string | null
  branding_config?: PortalBrandingConfig
  featured_agent_slugs?: string[]
  seo_config?: PortalSEOConfig
}

export async function getPortalSettings(): Promise<TenantPortal> {
  const { data } = await apiClient.axios.get('/api/v1/portal/settings')
  return data.data
}

export async function updatePortalSettings(body: UpdatePortalSettingsBody): Promise<TenantPortal> {
  const { data } = await apiClient.axios.put('/api/v1/portal/settings', body)
  return data.data
}
