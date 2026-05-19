import type { Conversation, Message } from '../types'
import { apiClient } from './http'

// Legacy Conversations (for apps)
export async function getConversations(appId: string): Promise<Conversation[]> {
  const { data } = await apiClient.axios.get(`/console/api/apps/${appId}/conversations`)
  return data
}

export async function createConversation(appId: string): Promise<Conversation> {
  const { data } = await apiClient.axios.post(`/console/api/apps/${appId}/conversations`)
  return data
}

export async function deleteConversation(id: string): Promise<void> {
  await apiClient.axios.delete(`/console/api/conversations/${id}`)
}

// Agent Conversations (New API)
export async function getAgentConversations(agentId: string, limit: number = 50): Promise<any[]> {
  const { data } = await apiClient.axios.get(`/api/v1/agents/${agentId}/conversations`, {
    params: { limit }
  })
  return data.data?.conversations || []
}

export async function createAgentConversation(agentId: string, name?: string): Promise<any> {
  const { data } = await apiClient.axios.post('/api/v1/agents/conversations', {
    agent_id: agentId,
    name: name || 'New Conversation'
  })
  return data.data
}

export async function getConversationById(conversationId: string, includeMessages: boolean = false): Promise<any> {
  const { data } = await apiClient.axios.get(`/api/v1/agents/conversations/${conversationId}`, {
    params: { include_messages: includeMessages }
  })
  return data.data
}

export async function updateConversationName(conversationId: string, name: string): Promise<any> {
  const { data } = await apiClient.axios.put(`/api/v1/agents/conversations/${conversationId}`, {
    name
  })
  return data.data
}

export async function deleteAgentConversation(conversationId: string): Promise<void> {
  await apiClient.axios.delete(`/api/v1/agents/conversations/${conversationId}`)
}

export async function getConversationMessages(conversationId: string, limit?: number): Promise<any[]> {
  const params = limit ? { limit } : {}
  const { data } = await apiClient.axios.get(`/api/v1/agents/conversations/${conversationId}/messages`, {
    params
  })
  return data.data?.messages || []
}

// Legacy Messages
export async function sendMessage(conversationId: string, content: string): Promise<Message> {
  const { data } = await apiClient.axios.post(
    `/console/api/conversations/${conversationId}/messages`,
    { content }
  )
  return data
}

export async function getMessages(conversationId: string): Promise<Message[]> {
  const { data } = await apiClient.axios.get(`/console/api/conversations/${conversationId}/messages`)
  return data
}

// Conversation Shares
export interface ShareLink {
  id: string
  conversation_id: string
  share_url: string
  expires_at: string
  revoked_at: string | null
  is_active: boolean
  created_at: string
  token?: string
}

export interface SharedConversationData {
  conversation: any
  messages: any[]
  agent: { name: string; avatar?: string; description?: string }
  expires_at: string
  share_id: string
}

export async function createConversationShare(
  conversationId: string,
  expiresInSeconds: number
): Promise<ShareLink> {
  const { data } = await apiClient.axios.post(
    `/api/v1/agents/conversations/${conversationId}/shares`,
    { expires_in_seconds: expiresInSeconds }
  )
  return data.data
}

export async function listConversationShares(conversationId: string): Promise<ShareLink[]> {
  const { data } = await apiClient.axios.get(
    `/api/v1/agents/conversations/${conversationId}/shares`
  )
  return data.data?.shares || []
}

export async function revokeConversationShare(shareId: string, conversationId: string): Promise<void> {
  await apiClient.axios.delete(`/api/v1/agents/conversations/${conversationId}/shares/${shareId}`)
}

export async function getSharedConversation(token: string): Promise<SharedConversationData> {
  // Public endpoint — no auth header needed; use plain fetch to avoid auth interceptors
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001'
  const res = await fetch(`${apiUrl}/api/v1/public/share/${encodeURIComponent(token)}`)
  if (!res.ok) {
    throw new Error(res.status === 404 ? 'not_found' : 'fetch_error')
  }
  const json = await res.json()
  return json.data
}

// Chat Attachments
export async function uploadChatAttachment(
  conversationId: string,
  file: File,
  onProgress?: (progress: number) => void
): Promise<any> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('conversation_id', conversationId)

  const { data } = await apiClient.axios.post(
    '/api/v1/agents/chat/upload-attachment',
    formData,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent: any) => {
        if (onProgress && progressEvent.total) {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          onProgress(progress)
        }
      }
    }
  )
  return data.data || data
}

// Data file analysis — presigned S3 PUT URL for large file uploads
export async function getAnalysisUploadUrl(
  filename: string,
  contentType: string = 'text/csv'
): Promise<{ upload_url: string; s3_key: string; s3_url: string; expires_in: number }> {
  const params = new URLSearchParams({ filename, content_type: contentType })
  const { data } = await apiClient.axios.get(
    `/api/v1/data-analysis/upload-presigned-url?${params}`
  )
  return data
}
