import { apiClient } from './http'

// Knowledge Base CRUD
export async function getKnowledgeBases(): Promise<any[]> {
  const { data } = await apiClient.axios.get('/api/v1/knowledge-bases')
  return data
}

export async function getKnowledgeBase(id: string): Promise<any> {
  const { data } = await apiClient.axios.get(`/api/v1/knowledge-bases/${id}`)
  return data
}

export async function createKnowledgeBase(kbData: any): Promise<any> {
  const { data } = await apiClient.axios.post('/api/v1/knowledge-bases', kbData)
  return data
}

export async function updateKnowledgeBase(id: string, kbData: any): Promise<any> {
  const { data } = await apiClient.axios.put(`/api/v1/knowledge-bases/${id}`, kbData)
  return data
}

export async function deleteKnowledgeBase(id: string): Promise<void> {
  await apiClient.axios.delete(`/api/v1/knowledge-bases/${id}`)
}

export async function searchKnowledgeBase(id: string, query: string, topK: number = 5): Promise<any> {
  const { data } = await apiClient.axios.post(`/api/v1/knowledge-bases/${id}/search`, { query, top_k: topK })
  return data
}

// Knowledge Base Documents
export async function uploadDocuments(
  kbId: string,
  files: File[],
  onProgress?: (progress: number) => void
): Promise<any> {
  const formData = new FormData()
  files.forEach(file => formData.append('files', file))

  const { data } = await apiClient.axios.post(
    `/api/v1/knowledge-bases/${kbId}/documents/upload`,
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
  return data
}

export async function getKnowledgeBaseDocuments(
  kbId: string,
  params?: {
    page?: number
    page_size?: number
    search?: string
    source_type?: string
    has_images?: boolean
    sort_by?: string
    sort_order?: string
  }
): Promise<any> {
  const { data } = await apiClient.axios.get(`/api/v1/knowledge-bases/${kbId}/documents`, { params })
  return data
}

export async function getKnowledgeBaseDocument(kbId: string, docId: string): Promise<any> {
  const { data } = await apiClient.axios.get(`/api/v1/knowledge-bases/${kbId}/documents/${docId}`)
  return data
}

export async function deleteKnowledgeBaseDocument(kbId: string, docId: string): Promise<void> {
  await apiClient.axios.delete(`/api/v1/knowledge-bases/${kbId}/documents/${docId}`)
}

export async function bulkDeleteKnowledgeBaseDocuments(kbId: string, docIds: number[]): Promise<void> {
  await apiClient.axios.post(`/api/v1/knowledge-bases/${kbId}/documents/bulk-delete`, docIds)
}

export async function reprocessKnowledgeBaseDocument(kbId: string, docId: string): Promise<void> {
  await apiClient.axios.post(`/api/v1/knowledge-bases/${kbId}/documents/${docId}/reprocess`)
}

export async function cancelKnowledgeBaseDocument(kbId: string, docId: string): Promise<void> {
  await apiClient.axios.post(`/api/v1/knowledge-bases/${kbId}/documents/${docId}/cancel`)
}

export async function downloadKnowledgeBaseDocument(kbId: string, docId: string): Promise<Blob> {
  const { data } = await apiClient.axios.get(
    `/api/v1/knowledge-bases/${kbId}/documents/${docId}/download`,
    { responseType: 'blob' }
  )
  return data
}

export async function addTextContent(
  kbId: string,
  title: string,
  content: string,
  metadata?: Record<string, any>
): Promise<any> {
  const { data } = await apiClient.axios.post(
    `/api/v1/knowledge-bases/${kbId}/documents/text`,
    { title, content, metadata: metadata || {} }
  )
  return data
}

export async function crawlWebsite(
  kbId: string,
  url: string,
  options?: { maxPages?: number; includeSubpages?: boolean }
): Promise<any> {
  const { data } = await apiClient.axios.post(
    `/api/v1/knowledge-bases/${kbId}/documents/crawl`,
    {
      url,
      max_pages: options?.maxPages || 1,
      include_subpages: options?.includeSubpages || false
    }
  )
  return data
}
