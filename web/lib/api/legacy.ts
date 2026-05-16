import type { App } from '../types'
import { apiClient } from './http'

// Apps
export async function getApps(): Promise<App[]> {
  const { data } = await apiClient.axios.get('/api/v1/apps')
  // Synkora returns: { page, limit, total, has_more, data: [...] }
  return data.data || []
}

export async function getApp(id: string): Promise<App> {
  const { data } = await apiClient.axios.get(`/api/v1/apps/${id}`)
  return data
}

export async function createApp(appData: Partial<App>): Promise<App> {
  const { data } = await apiClient.axios.post('/api/v1/apps', appData)
  return data
}

export async function updateApp(id: string, appData: Partial<App>): Promise<App> {
  const { data } = await apiClient.axios.put(`/api/v1/apps/${id}`, appData)
  return data
}

export async function deleteApp(id: string): Promise<void> {
  await apiClient.axios.delete(`/api/v1/apps/${id}`)
}

// Files
export async function uploadFile(file: File): Promise<any> {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await apiClient.axios.post('/api/v1/files/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function uploadAgentAvatar(agentSlug: string, file: File): Promise<any> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('agent_slug', agentSlug)
  formData.append('entity_type', 'agent_avatar')
  const { data } = await apiClient.axios.post('/api/v1/files/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}
