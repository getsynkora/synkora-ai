/**
 * Workspaces billed in another system (platform admins only). When on, the workspace's own platform key with
 * billing:manage may set its plan through PUT /api/v1/public/account/subscription.
 */

import { apiClient } from './client'

export interface WorkspaceBilling {
  id: string
  name: string
  external_billing: boolean
  created_at: string
}

export const workspaceBillingApi = {
  // Without a search: every workspace billed in another system
  list: async (search?: string): Promise<WorkspaceBilling[]> =>
    apiClient.request('GET', '/api/v1/platform-settings/workspaces', undefined, {
      params: search ? { search } : undefined,
    }),

  setExternalBilling: async (id: string, externalBilling: boolean): Promise<WorkspaceBilling> =>
    apiClient.request('PATCH', `/api/v1/platform-settings/workspaces/${id}`, { external_billing: externalBilling }),
}
