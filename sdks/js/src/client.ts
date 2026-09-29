import {
  AgentNotFoundError,
  APIError,
  AuthError,
  RateLimitError,
  SynkoraError,
} from './exceptions.js'
import type {
  AgentInfo,
  ChatOptions,
  ChatResponse,
  ConversationInfo,
  DoneEvent,
  StreamEvent,
} from './models.js'
import { iterSseStream } from './streaming.js'

const DEFAULT_BASE_URL = 'https://app.synkora.com'
const DEFAULT_TIMEOUT_MS = 120_000
const SDK_VERSION = '0.1.0'

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

async function raiseForStatus(response: Response): Promise<void> {
  if (response.ok) return

  const status = response.status
  let detail = `HTTP ${status}`
  try {
    const body = (await response.json()) as { detail?: string }
    if (body.detail) detail = body.detail
  } catch {
    // ignore parse error — use status as message
  }

  if (status === 401 || status === 403) throw new AuthError(detail, status)
  if (status === 404) throw new AgentNotFoundError(detail, status)
  if (status === 429) throw new RateLimitError(detail, status)
  if (status >= 500) throw new APIError(`Server error: ${status}`, status)
  throw new SynkoraError(detail, status)
}

// ---------------------------------------------------------------------------
// SynkoraClient
// ---------------------------------------------------------------------------

export interface SynkoraClientOptions {
  /** Your Synkora agent API key. Falls back to SYNKORA_API_KEY env var. */
  apiKey?: string
  /** Override the API base URL. Falls back to SYNKORA_BASE_URL env var. */
  baseUrl?: string
  /** Request timeout in milliseconds. Default: 120 000. */
  timeoutMs?: number
}

export class SynkoraClient {
  private readonly baseUrl: string
  private readonly headers: Record<string, string>
  private readonly timeoutMs: number

  constructor(options: SynkoraClientOptions = {}) {
    // Resolve API key from options → process.env (Node) → globalThis env (Deno/CF Workers)
    const apiKey =
      options.apiKey ??
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (typeof process !== 'undefined' ? process.env['SYNKORA_API_KEY'] : undefined) ??
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ((globalThis as any).SYNKORA_API_KEY as string | undefined)

    if (!apiKey) {
      throw new AuthError(
        'No API key provided. Pass apiKey: or set the SYNKORA_API_KEY environment variable.',
      )
    }

    const baseUrl =
      options.baseUrl ??
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (typeof process !== 'undefined' ? process.env['SYNKORA_BASE_URL'] : undefined) ??
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ((globalThis as any).SYNKORA_BASE_URL as string | undefined) ??
      DEFAULT_BASE_URL

    this.baseUrl = baseUrl.replace(/\/$/, '')
    this.timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS
    this.headers = {
      Authorization: `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
      Accept: 'application/json',
      'User-Agent': `synkora-js/${SDK_VERSION}`,
    }
  }

  // ------------------------------------------------------------------
  // Internal fetch wrapper with AbortController timeout
  // ------------------------------------------------------------------

  private async fetch(path: string, init: RequestInit = {}): Promise<Response> {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), this.timeoutMs)
    try {
      return await fetch(`${this.baseUrl}${path}`, {
        ...init,
        headers: { ...this.headers, ...(init.headers as Record<string, string> | undefined) },
        signal: controller.signal,
      })
    } finally {
      clearTimeout(timer)
    }
  }

  // ------------------------------------------------------------------
  // Agents
  // ------------------------------------------------------------------

  async listAgents(): Promise<AgentInfo[]> {
    const resp = await this.fetch('/api/v1/public/agents')
    await raiseForStatus(resp)
    const data = (await resp.json()) as AgentInfo[] | { agents: AgentInfo[] }
    const agents = Array.isArray(data) ? data : data.agents
    return agents.map((a) => ({
      id: String(a.id),
      name: a.name,
      description: a.description,
      model: a.model,
      capabilities: a.capabilities ?? [],
    }))
  }

  async getAgent(agentId: string): Promise<AgentInfo> {
    const resp = await this.fetch(`/api/v1/public/agents/${agentId}`)
    await raiseForStatus(resp)
    const a = (await resp.json()) as AgentInfo
    return {
      id: String(a.id),
      name: a.name,
      description: a.description,
      model: a.model,
      capabilities: a.capabilities ?? [],
    }
  }

  // ------------------------------------------------------------------
  // Conversations
  // ------------------------------------------------------------------

  async listConversations(agentId: string): Promise<ConversationInfo[]> {
    const resp = await this.fetch(`/api/v1/public/agents/${agentId}/conversations`)
    await raiseForStatus(resp)
    const data = (await resp.json()) as
      | ConversationInfo[]
      | { conversations: ConversationInfo[] }
    const items = Array.isArray(data) ? data : data.conversations
    return items.map((c) => ({
      id: String(c.id),
      agentId: String(c.agentId ?? (c as Record<string, unknown>)['agent_id']),
      createdAt: c.createdAt ?? (c as Record<string, unknown>)['created_at'] as string,
      updatedAt: c.updatedAt ?? (c as Record<string, unknown>)['updated_at'] as string,
      messageCount: c.messageCount ?? (c as Record<string, unknown>)['message_count'] as number ?? 0,
    }))
  }

  async deleteConversation(agentId: string, conversationId: string): Promise<void> {
    const resp = await this.fetch(
      `/api/v1/public/agents/${agentId}/conversations/${conversationId}`,
      { method: 'DELETE' },
    )
    await raiseForStatus(resp)
  }

  // ------------------------------------------------------------------
  // Chat — streaming
  // ------------------------------------------------------------------

  async *chatStream(
    agentId: string,
    message: string,
    options: ChatOptions = {},
  ): AsyncGenerator<StreamEvent> {
    const body: Record<string, unknown> = { message }
    if (options.conversationId) body['conversation_id'] = options.conversationId
    if (options.metadata) body['metadata'] = options.metadata

    const resp = await this.fetch(`/api/v1/public/agents/${agentId}/chat/stream`, {
      method: 'POST',
      body: JSON.stringify(body),
    })
    await raiseForStatus(resp)

    if (!resp.body) throw new APIError('Response body is null — cannot stream.')

    yield* iterSseStream(resp.body)
  }

  // ------------------------------------------------------------------
  // Chat — non-streaming (aggregates stream)
  // ------------------------------------------------------------------

  async chat(
    agentId: string,
    message: string,
    options: ChatOptions = {},
  ): Promise<ChatResponse> {
    const chunks: string[] = []
    let conversationId = options.conversationId ?? ''
    let doneEvent: DoneEvent | undefined

    for await (const event of this.chatStream(agentId, message, options)) {
      if (event.type === 'chunk') chunks.push(event.content)
      if (event.type === 'done') {
        doneEvent = event
        const meta = doneEvent.metadata
        if (meta['conversation_id']) conversationId = String(meta['conversation_id'])
      }
    }

    const metadata = doneEvent?.metadata ?? {}
    return {
      conversationId,
      message: chunks.join(''),
      tokensUsed:
        typeof metadata['total_tokens'] === 'number' ? metadata['total_tokens'] : undefined,
      metadata,
      sources: doneEvent?.sources ?? [],
    }
  }
}
