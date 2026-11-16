export interface User {
  id: string
  email: string
  name: string
  avatar?: string
  /** Language of the dashboard saved on the account ('en', 'de'). */
  interface_language?: string
  created_at: string
}

export interface App {
  id: string
  name: string
  mode: 'chat' | 'completion' | 'workflow'
  icon: string
  description: string
  model_config: ModelConfig
  created_at: string
  updated_at: string
}

export interface ModelConfig {
  provider: string
  model: string
  temperature?: number
  max_tokens?: number
  top_p?: number
}

export interface Conversation {
  id: string
  app_id: string
  name: string
  created_at: string
  updated_at: string
}

export interface Message {
  id: string
  conversation_id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export interface Dataset {
  id: string
  name: string
  description: string
  embedding_model: string
  embedding_dimension: number
  document_count: number
  created_at: string
  updated_at: string
}

export interface Document {
  id: string
  dataset_id: string
  name: string
  content: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  created_at: string
  updated_at: string
}

export interface APIResponse<T> {
  data: T
  message?: string
}

export interface PaginatedResponse<T> {
  data: T[]
  total: number
  page: number
  page_size: number
}
