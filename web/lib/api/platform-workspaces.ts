/**
 * Workspaces, for platform admins: suspend or reactivate a workspace, activate (verify) or suspend its owner, and
 * mark it billed in another system (its own platform key with billing:manage may then set its plan through
 * PUT /api/v1/public/account/subscription).
 */

import { apiClient } from './client'

export type WorkspaceStatus = 'ACTIVE' | 'SUSPENDED'

export interface WorkspaceOwner {
  id: string
  name: string
  email: string
  // INACTIVE until the email address is verified
  status: 'ACTIVE' | 'INACTIVE' | 'SUSPENDED' | 'DELETED'
}

export interface PlatformWorkspace {
  id: string
  name: string
  status: WorkspaceStatus | 'DELETED'
  external_billing: boolean
  created_at: string
  owner: WorkspaceOwner | null
}

export const platformWorkspacesApi = {
  // A name, the exact id or the owner's email; without a search, every workspace billed in another system
  list: async (search?: string): Promise<PlatformWorkspace[]> =>
    apiClient.request('GET', '/api/v1/platform-settings/workspaces', undefined, {
      params: search ? { search } : undefined,
    }),

  update: async (
    id: string,
    changes: { status?: WorkspaceStatus; external_billing?: boolean }
  ): Promise<PlatformWorkspace> => apiClient.request('PATCH', `/api/v1/platform-settings/workspaces/${id}`, changes),

  // ACTIVE also marks the owner's email address verified
  setOwnerStatus: async (id: string, status: WorkspaceStatus): Promise<PlatformWorkspace> =>
    apiClient.request('PATCH', `/api/v1/platform-settings/workspaces/${id}/owner`, { status }),
}
