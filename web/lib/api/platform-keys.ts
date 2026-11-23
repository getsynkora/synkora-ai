/**
 * Platform keys: tenant-level API keys for connecting another system (manage customer workspaces,
 * read plan and usage, manage webhooks). Owners and admins only.
 */

import { apiClient } from './client'

export interface PlatformKey {
  id: string
  name: string
  key_prefix: string
  permissions: string[]
  is_active: boolean
  last_used_at: string | null
  created_at: string
}

export interface CreatedPlatformKey extends PlatformKey {
  api_key: string
}

export interface PlatformKeyList {
  keys: PlatformKey[]
  available_permissions: Record<string, string>
}

export const platformKeysApi = {
  list: async (): Promise<PlatformKeyList> => apiClient.request('GET', '/api/v1/platform-keys'),

  create: async (name: string, permissions: string[]): Promise<CreatedPlatformKey> =>
    apiClient.request('POST', '/api/v1/platform-keys', { name, permissions }),

  regenerate: async (id: string): Promise<CreatedPlatformKey> =>
    apiClient.request('POST', `/api/v1/platform-keys/${id}/regenerate`),

  setActive: async (id: string, isActive: boolean): Promise<PlatformKey> =>
    apiClient.request('PATCH', `/api/v1/platform-keys/${id}`, { is_active: isActive }),

  remove: async (id: string): Promise<void> => apiClient.request('DELETE', `/api/v1/platform-keys/${id}`),
}
