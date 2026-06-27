/**
 * Type definitions for the advanced chat interface
 */

export interface Message {
  id: string
  dbId?: string  // real DB UUID — populated when id is an ephemeral React key
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  attachments?: Attachment[]
  metadata?: MessageMetadata
  sources?: RAGSource[]
  isError?: boolean
  stopped?: boolean
}

export interface Attachment {
  type: 'image' | 'video' | 'pdf' | 'link' | 'chart' | 'table' | 'document'
  url: string
  name?: string
  thumbnail?: string
  size?: number
  // File upload fields
  file_id?: string
  file_name?: string
  file_type?: string
  file_size?: number
  file_url?: string
  thumbnail_url?: string
}

export interface DiagramData {
  id?: string
  title: string
  description?: string
  diagram_type: string
  style?: number
  svg_url?: string
  svg_content?: string
  png_url?: string
  spec?: object
  created_at?: string
}

export interface InfographicData {
  title?: string
  theme?: string
  svg_url?: string
  png_url?: string
  svg_content?: string
}

export interface GeneratedImageData {
  id?: string
  url?: string | null
  prompt?: string
  revised_prompt?: string
  model?: string
  provider?: string
  size?: string
  created_at?: string
}

export interface FormOption {
  label: string
  value: string
}

export interface FormField {
  id: string
  type:
    | 'boolean'
    | 'radio'
    | 'checkbox_group'
    | 'select'
    | 'text'
    | 'textarea'
    | 'number'
    | 'scale'
    | 'image_upload'
    | 'file_upload'
  label: string
  description?: string
  help_text?: string
  placeholder?: string
  required?: boolean
  default_value?: unknown
  options?: FormOption[]
  min?: number
  max?: number
  step?: number
  min_label?: string
  max_label?: string
  max_length?: number
  max_files?: number
  accept?: string[]
}

export interface FormDefinition {
  form_id: string
  title: string
  description?: string
  submit_label?: string
  status?: 'pending' | 'submitted'
  fields: FormField[]
}

export interface MindsetResultData {
  classification?: string
  score?: number | string
  score_percent?: number | string
  headline?: string
  share_caption?: string
  insight?: string
  domain?: string
  strengths?: string[]
  growth_edges?: string[]
  top_growth_signals?: string[]
  top_fixed_signals?: string[]
}

export interface MessageMetadata {
  sources?: Source[]
  charts?: ChartData[]
  diagrams?: DiagramData[]
  infographics?: InfographicData[]
  generated_images?: GeneratedImageData[]
  forms?: FormDefinition[]
  tables?: TableData[]
  keyPeople?: Person[]
  news?: NewsItem[]
  images?: ImageData[]
  usage?: TokenUsage
  timing?: TimingInfo
  workflow?: WorkflowMetadata
  vehicle_maps?: VehicleMapData[]
  fleet_cards?: FleetCardData[]
  mindset_result?: MindsetResultData
  confidence?: number
}

export interface VehicleMapData {
  id: string
  map_url: string
  embed_url?: string
  center?: { lat: number; lng: number }
  zoom?: number
  marker_count?: number
  distance_km?: number
  duration_min?: number
  profile?: string
  created_at?: string
}

export interface FleetCardData {
  id: string
  tool: string
  data: Record<string, any>
  created_at?: string
}

export interface WorkflowMetadata {
  workflow_type?: string
  stages?: any[]
  total_duration?: number
  agent_outputs?: Record<string, any>
}

export interface TokenUsage {
  input_tokens: number
  output_tokens: number
  total_tokens: number
}

export interface TimingInfo {
  start_time?: number
  end_time?: number
  duration?: number
  time_to_first_token?: number
}

export interface Source {
  title: string
  url: string
  favicon?: string
  description?: string
  snippet?: string
  relevance?: number
}

export interface RAGSource {
  index: number
  score: number
  text_preview: string
  knowledge_base: string
  segment_id?: string
  document_id?: string
  title?: string
  source_type?: string
  external_url?: string
  presigned_url?: string
  mime_type?: string
  created_at?: string
  metadata?: Record<string, any>
  display: {
    type: string
    channel?: string
    user?: string
    from?: string
    subject?: string
    timestamp?: string
    link?: string
    title?: string
    [key: string]: any
  }
}

export interface ChartData {
  type?: string
  chart_type?: string
  title: string
  description?: string
  library?: string
  data: any
  config?: any
  table_data?: Array<Record<string, unknown>>
}

export interface TableData {
  title: string
  headers: string[]
  rows: string[][]
}

export interface Person {
  name: string
  title: string
  avatar?: string
  linkedin?: string
  company?: string
}

export interface NewsItem {
  title: string
  source: string
  url: string
  date: string
  thumbnail?: string
}

export interface ImageData {
  url: string
  caption?: string
  width?: number
  height?: number
}

export interface SuggestionPrompt {
  title: string
  description?: string
  icon?: string
  prompt: string
}

export interface Agent {
  agent_name: string
  agent_type: string
  description?: string
  status: string
  model?: string
  provider?: string
  avatar?: string
  suggestion_prompts?: SuggestionPrompt[]
  // Stats and metadata
  likes_count?: number
  dislikes_count?: number
  usage_count?: number
  execution_count?: number
  success_rate?: number
  successful_executions?: number
  failed_executions?: number
  creator_name?: string
  created_at?: string
}

export interface ChatSession {
  id: string
  agentName: string
  title: string
  lastMessage?: string
  timestamp: Date
  messageCount: number
}
