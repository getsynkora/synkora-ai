/**
 * OIDC SSO API Client
 */

import { apiClient } from './client'
import type { OIDCConfig, OIDCConfigRequest } from '@/types/oidc-config'

export const oidcConfigApi = {
  /**
   * Get the OIDC config for the current tenant.
   * Returns null if no config has been created yet.
   */
  getConfig: async (): Promise<OIDCConfig | null> => {
    try {
      const data = await apiClient.request('GET', '/api/v1/sso/oidc/config')
      return data.data ?? data
    } catch (error: any) {
      if (error?.response?.status === 404) {
        return null
      }
      throw error
    }
  },

  /**
   * Create or update the OIDC config for the current tenant.
   */
  saveConfig: async (config: OIDCConfigRequest): Promise<OIDCConfig> => {
    const data = await apiClient.request('POST', '/api/v1/sso/oidc/config', config)
    return data.data ?? data
  },

  /**
   * Delete the OIDC config for the current tenant. OWNER only.
   */
  deleteConfig: async (): Promise<void> => {
    await apiClient.request('DELETE', '/api/v1/sso/oidc/config')
  },

  /**
   * Get the OIDC login URL for testing.
   */
  getLoginUrl: async (): Promise<string> => {
    const data = await apiClient.request('GET', '/api/v1/sso/oidc/login')
    return (data.data ?? data).login_url
  },
}
