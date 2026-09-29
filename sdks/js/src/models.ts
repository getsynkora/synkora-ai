// ---------------------------------------------------------------------------
// SSE stream events
// ---------------------------------------------------------------------------

export interface StartEvent {
  type: 'start'
  agent: string
  startTime: number
}

export interface ChunkEvent {
  type: 'chunk'
  content: string
}

export interface StatusEvent {
  type: 'status'
  content: string
}

export interface ToolStatusEvent {
  type: 'tool_status'
  toolName: string
  status: string
  description: string
  details?: string
  durationMs?: number
  inputTokens?: number
  outputTokens?: number
}

export interface LLMCallEvent {
  type: 'llm_call'
  status: 'started' | 'completed'
  model?: string
  callIndex?: number
  inputTokens?: number
  outputTokens?: number
}

export interface FirstTokenEvent {
  type: 'first_token'
  timeToFirstToken: number
}

export interface DoneEvent {
  type: 'done'
  metadata: Record<string, unknown>
  sources: Record<string, unknown>[]
}

export interface CompactionEvent {
  type: 'compaction'
  prunedCount?: number
  tokensSaved?: number
}

export interface SatisfactionPromptEvent {
  type: 'satisfaction_prompt'
  conversationId: string
}

export type StreamEvent =
  | StartEvent
  | ChunkEvent
  | StatusEvent
  | ToolStatusEvent
  | LLMCallEvent
  | FirstTokenEvent
  | DoneEvent
  | CompactionEvent
  | SatisfactionPromptEvent

// ---------------------------------------------------------------------------
// REST response models
// ---------------------------------------------------------------------------

export interface AgentInfo {
  id: string
  name: string
  description?: string
  model?: string
  capabilities: string[]
}

export interface ConversationInfo {
  id: string
  agentId: string
  createdAt: string
  updatedAt: string
  messageCount: number
}

export interface ChatResponse {
  conversationId: string
  message: string
  tokensUsed?: number
  metadata: Record<string, unknown>
  sources: Record<string, unknown>[]
}

// ---------------------------------------------------------------------------
// Request option types
// ---------------------------------------------------------------------------

export interface ChatOptions {
  /** Continue an existing conversation. */
  conversationId?: string
  /** Arbitrary key-value metadata passed to the agent. */
  metadata?: Record<string, unknown>
}
