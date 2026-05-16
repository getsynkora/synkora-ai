import { apiClient } from './http'

export interface BrainDomain {
  id: string
  tenant_id: string
  name: string
  slug: string
  description: string | null
  rerank_weight: number
  is_active: boolean
  knowledge_base_id: number | null
  created_at: string
  updated_at: string
}

export interface BrainDomainCreate {
  name: string
  slug: string
  description?: string
  rerank_weight?: number
  is_active?: boolean
  knowledge_base_id?: number | null
}

export interface BrainDomainUpdate {
  name?: string
  description?: string
  rerank_weight?: number
  is_active?: boolean
  knowledge_base_id?: number | null
}

const B = '/api/v1'

export const listBrainDomains = (): Promise<BrainDomain[]> =>
  apiClient.request('GET', `${B}/brain/domains`)

export const createBrainDomain = (body: BrainDomainCreate): Promise<BrainDomain> =>
  apiClient.request('POST', `${B}/brain/domains`, body)

export const updateBrainDomain = (id: string, body: BrainDomainUpdate): Promise<BrainDomain> =>
  apiClient.request('PATCH', `${B}/brain/domains/${id}`, body)

export const deleteBrainDomain = (id: string): Promise<void> =>
  apiClient.request('DELETE', `${B}/brain/domains/${id}`)
