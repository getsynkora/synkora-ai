import { apiClient } from './http'

// Agent CRUD
export async function getAgents(page?: number, pageSize?: number, search?: string): Promise<any> {
  const params: any = {}
  if (page !== undefined) params.page = page
  if (pageSize !== undefined) params.page_size = pageSize
  if (search) params.search = search

  const { data } = await apiClient.axios.get('/api/v1/agents/', { params })
  return data.data || data
}

export async function getAgent(agentName: string): Promise<any> {
  const { data } = await apiClient.axios.get(`/api/v1/agents/${agentName}`)
  return data.data || data
}

export async function createAgent(agentData: any): Promise<any> {
  const { data } = await apiClient.axios.post('/api/v1/agents/', agentData)
  return data
}

export async function updateAgent(agentName: string, agentData: any): Promise<any> {
  const { data } = await apiClient.axios.put(`/api/v1/agents/${agentName}`, agentData)
  return data
}

export async function deleteAgent(agentName: string): Promise<void> {
  await apiClient.axios.delete(`/api/v1/agents/${agentName}`)
}

export async function cloneAgent(agentName: string, cloneData: any): Promise<any> {
  const { data } = await apiClient.axios.post(`/api/v1/agents/${agentName}/clone`, cloneData)
  return data
}

export async function resetAgent(agentName: string): Promise<any> {
  const { data } = await apiClient.axios.post(`/api/v1/agents/${agentName}/reset`)
  return data
}

export async function getAgentStats(agentName: string): Promise<any> {
  const { data } = await apiClient.axios.get(`/api/v1/agents/${agentName}/stats`)
  return data.data || data
}

// Agent LLM Configs
export async function getAgentLLMConfigs(agentName: string): Promise<any[]> {
  const { data } = await apiClient.axios.get(`/api/v1/agents/${agentName}/llm-configs`)
  return data
}

// Agent Tools
export async function getAgentTools(): Promise<any[]> {
  const { data } = await apiClient.axios.get('/api/v1/agents/tools')
  return data.data?.tools || data
}

export async function getAgentToolsForAgent(agentId: string): Promise<any[]> {
  const { data } = await apiClient.axios.get(`/api/v1/agents/${agentId}/tools`)
  return data.data?.tools || data
}

export async function addToolToAgent(agentId: string, toolData: any): Promise<any> {
  const { data } = await apiClient.axios.post(`/api/v1/agents/${agentId}/tools`, toolData)
  return data
}

export async function deleteAgentTool(agentId: string, toolId: string): Promise<void> {
  await apiClient.axios.delete(`/api/v1/agents/${agentId}/tools/${toolId}`)
}

export async function testAgentTool(agentId: string, toolName: string, params?: any): Promise<any> {
  const { data } = await apiClient.axios.post(`/api/v1/agents/${agentId}/tools/${toolName}/test`, params || {})
  return data
}

// Agent Capabilities
export async function getCapabilities(): Promise<any[]> {
  const { data } = await apiClient.axios.get('/api/v1/agents/capabilities')
  return data.data?.capabilities || []
}

export async function enableCapability(agentId: string, capabilityId: string, oauthAppId?: number): Promise<any> {
  const { data } = await apiClient.axios.post(
    `/api/v1/agents/${agentId}/capabilities/${capabilityId}`,
    oauthAppId ? { oauth_app_id: oauthAppId } : {}
  )
  return data
}

export async function enableCapabilitiesBulk(
  agentId: string,
  capabilityIds: string[],
  oauthAppIds?: Record<string, number>
): Promise<any> {
  const { data } = await apiClient.axios.post(`/api/v1/agents/${agentId}/capabilities/bulk`, {
    capability_ids: capabilityIds,
    oauth_app_ids: oauthAppIds
  })
  return data
}

export async function disableCapability(agentId: string, capabilityId: string): Promise<any> {
  const { data } = await apiClient.axios.delete(`/api/v1/agents/${agentId}/capabilities/${capabilityId}`)
  return data
}

// Agent MCP Servers
export async function getAgentMCPServers(agentId: string): Promise<any[]> {
  const { data } = await apiClient.axios.get(`/api/v1/agents/${agentId}/mcp-servers`)
  return data.data?.mcp_servers || data
}

export async function getMCPServerTools(agentId: string, serverId: string): Promise<any> {
  const { data } = await apiClient.axios.get(`/api/v1/agents/${agentId}/mcp-servers/${serverId}/tools`)
  return data
}

export async function addMCPServerToAgent(agentId: string, serverData: any): Promise<any> {
  const { data } = await apiClient.axios.post(`/api/v1/agents/${agentId}/mcp-servers`, serverData)
  return data
}

export async function removeMCPServerFromAgent(agentId: string, serverId: string): Promise<void> {
  await apiClient.axios.delete(`/api/v1/agents/${agentId}/mcp-servers/${serverId}`)
}

export async function updateMCPServerConfig(agentId: string, serverId: string, config: any): Promise<any> {
  const { data } = await apiClient.axios.put(`/api/v1/agents/${agentId}/mcp-servers/${serverId}/config`, config)
  return data
}

export async function getMCPServers(): Promise<any[]> {
  const { data } = await apiClient.axios.get('/api/v1/mcp/servers')
  return data.data?.servers || data.data || data
}

// Agent Knowledge Bases
export async function getAgentKnowledgeBases(agentId: string): Promise<any[]> {
  const { data } = await apiClient.axios.get(`/api/v1/agents/${agentId}/knowledge-bases`)
  return data.data?.knowledge_bases || data
}

export async function addKnowledgeBaseToAgent(agentId: string, kbData: any): Promise<any> {
  const { data } = await apiClient.axios.post(`/api/v1/agents/${agentId}/knowledge-bases`, kbData)
  return data
}

export async function removeKnowledgeBaseFromAgent(agentId: string, kbId: string): Promise<void> {
  await apiClient.axios.delete(`/api/v1/agents/${agentId}/knowledge-bases/${kbId}`)
}

// Agent Context Files
export async function getAgentContextFiles(agentName: string): Promise<any[]> {
  const { data } = await apiClient.axios.get(`/api/v1/agents/${agentName}/context-files`)
  return data.data?.files || data
}

export async function uploadAgentContextFile(agentName: string, file: File): Promise<any> {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await apiClient.axios.post(
    `/api/v1/agents/${agentName}/context-files/upload`,
    formData,
    {
      headers: { 'Content-Type': 'multipart/form-data' }
    }
  )
  return data.data || data
}

export async function deleteAgentContextFile(fileId: string): Promise<void> {
  await apiClient.axios.delete(`/api/v1/agents/context-files/${fileId}`)
}

export async function downloadAgentContextFile(fileId: string): Promise<any> {
  const { data } = await apiClient.axios.get(`/api/v1/agents/context-files/${fileId}/download`)
  return data.data || data
}
