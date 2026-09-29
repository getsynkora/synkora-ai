import { StreamError } from './exceptions.js'
import type {
  ChunkEvent,
  CompactionEvent,
  DoneEvent,
  FirstTokenEvent,
  LLMCallEvent,
  SatisfactionPromptEvent,
  StartEvent,
  StatusEvent,
  StreamEvent,
  ToolStatusEvent,
} from './models.js'

// ---------------------------------------------------------------------------
// Raw JSON → typed event
// ---------------------------------------------------------------------------

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function parseEvent(data: Record<string, any>): StreamEvent | null {
  const t = data.type as string | undefined

  if (t === 'start') {
    return {
      type: 'start',
      agent: data.agent ?? '',
      startTime: data.start_time ?? 0,
    } satisfies StartEvent
  }

  if (t === 'chunk') {
    return { type: 'chunk', content: data.content ?? '' } satisfies ChunkEvent
  }

  if (t === 'status') {
    return { type: 'status', content: data.content ?? '' } satisfies StatusEvent
  }

  if (t === 'tool_status') {
    return {
      type: 'tool_status',
      toolName: data.tool_name ?? '',
      status: data.status ?? '',
      description: data.description ?? '',
      details: data.details,
      durationMs: data.duration_ms,
      inputTokens: data.input_tokens,
      outputTokens: data.output_tokens,
    } satisfies ToolStatusEvent
  }

  if (t === 'llm_call') {
    return {
      type: 'llm_call',
      status: data.status ?? 'started',
      model: data.model,
      callIndex: data.call_index,
      inputTokens: data.input_tokens,
      outputTokens: data.output_tokens,
    } satisfies LLMCallEvent
  }

  if (t === 'first_token') {
    return {
      type: 'first_token',
      timeToFirstToken: data.time_to_first_token ?? 0,
    } satisfies FirstTokenEvent
  }

  if (t === 'done') {
    return {
      type: 'done',
      metadata: (data.metadata as Record<string, unknown>) ?? {},
      sources: (data.sources as Record<string, unknown>[]) ?? [],
    } satisfies DoneEvent
  }

  if (t === 'error') {
    throw new StreamError(
      (data.error as string | undefined) ?? 'Unknown stream error',
      data.error_type as string | undefined,
      data.violation_id as string | undefined,
    )
  }

  if (t === 'compaction') {
    return {
      type: 'compaction',
      prunedCount: data.pruned_count,
      tokensSaved: data.tokens_saved,
    } satisfies CompactionEvent
  }

  if (t === 'satisfaction_prompt') {
    return {
      type: 'satisfaction_prompt',
      conversationId: (data.conversation_id as string | undefined) ?? '',
    } satisfies SatisfactionPromptEvent
  }

  // Unknown / future event type — silently skip
  return null
}

// ---------------------------------------------------------------------------
// Async generator: ReadableStream<Uint8Array> → StreamEvent
// ---------------------------------------------------------------------------

export async function* iterSseStream(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<StreamEvent> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      // Keep the incomplete last line in the buffer
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed.startsWith('data:')) continue
        const payload = trimmed.slice('data:'.length).trim()
        if (!payload || payload === '[DONE]') continue

        let parsed: Record<string, unknown>
        try {
          parsed = JSON.parse(payload) as Record<string, unknown>
        } catch {
          continue
        }

        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const event = parseEvent(parsed as Record<string, any>)
        if (event !== null) yield event
      }
    }

    // Flush any remaining buffer content after stream ends
    if (buffer.trim().startsWith('data:')) {
      const payload = buffer.trim().slice('data:'.length).trim()
      if (payload && payload !== '[DONE]') {
        try {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const parsed = JSON.parse(payload) as Record<string, any>
          const event = parseEvent(parsed)
          if (event !== null) yield event
        } catch {
          // ignore
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}
