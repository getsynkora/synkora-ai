import { apiClient } from './client'

export interface PlatformOAuthApp {
  id: number
  provider: string
  app_name: string
  client_id: string
  redirect_uri: string
  scopes: string[]
  is_active: boolean
  description: string | null
  config: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface PlatformOAuthAppCreate {
  provider: string
  app_name: string
  auth_method?: string
  client_id: string
  client_secret: string
  redirect_uri?: string
  scopes?: string[]
  description?: string
  config?: Record<string, unknown>
}

export interface PlatformOAuthAppUpdate {
  app_name?: string
  auth_method?: string
  client_id?: string
  client_secret?: string
  redirect_uri?: string
  scopes?: string[]
  description?: string
  config?: Record<string, unknown>
}

const BASE = '/api/v1/admin/platform-oauth-apps'

export const platformOAuthAppsApi = {
  list: async (): Promise<PlatformOAuthApp[]> => {
    const data = await apiClient.request('GET', BASE)
    return Array.isArray(data) ? data : []
  },

  create: async (payload: PlatformOAuthAppCreate): Promise<PlatformOAuthApp> => {
    return apiClient.request('POST', BASE, payload)
  },

  update: async (id: number, payload: PlatformOAuthAppUpdate): Promise<PlatformOAuthApp> => {
    return apiClient.request('PUT', `${BASE}/${id}`, payload)
  },

  toggle: async (id: number): Promise<PlatformOAuthApp> => {
    return apiClient.request('PATCH', `${BASE}/${id}/toggle`)
  },

  remove: async (id: number): Promise<void> => {
    await apiClient.request('DELETE', `${BASE}/${id}`)
  },
}
