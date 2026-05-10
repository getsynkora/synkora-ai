import { apiClient } from './http'

export async function getSlackBots(agentId?: string): Promise<any[]> {
  const params = agentId ? { agent_id: agentId } : {}
  const { data } = await apiClient.axios.get('/api/v1/slack-bots', { params })
  return data
}

export async function getSlackBot(botId: string): Promise<any> {
  const { data } = await apiClient.axios.get(`/api/v1/slack-bots/${botId}`)
  return data
}

export async function createSlackBot(botData: any): Promise<any> {
  const { data } = await apiClient.axios.post('/api/v1/slack-bots', botData)
  return data
}

export async function updateSlackBot(botId: string, botData: any): Promise<any> {
  const { data } = await apiClient.axios.put(`/api/v1/slack-bots/${botId}`, botData)
  return data
}

export async function deleteSlackBot(botId: string): Promise<void> {
  await apiClient.axios.delete(`/api/v1/slack-bots/${botId}`)
}

export async function startSlackBot(botId: string): Promise<any> {
  const { data } = await apiClient.axios.post(`/api/v1/slack-bots/${botId}/start`)
  return data
}

export async function stopSlackBot(botId: string): Promise<any> {
  const { data } = await apiClient.axios.post(`/api/v1/slack-bots/${botId}/stop`)
  return data
}

export async function restartSlackBot(botId: string): Promise<any> {
  const { data } = await apiClient.axios.post(`/api/v1/slack-bots/${botId}/restart`)
  return data
}

export async function getSlackBotStatus(botId: string): Promise<any> {
  const { data } = await apiClient.axios.get(`/api/v1/slack-bots/${botId}/status`)
  return data
}

export async function downloadSlackManifest(agentId: string): Promise<Blob> {
  const response = await apiClient.axios.get(`/api/v1/agents/${agentId}/slack-manifest`, {
    responseType: 'blob',
  })
  return response.data
}
