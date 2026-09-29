import { describe, expect, it } from 'vitest'
import { StreamError } from '../src/exceptions.js'
import type { ChunkEvent, DoneEvent } from '../src/models.js'
import { iterSseStream } from '../src/streaming.js'

function makeStream(text: string): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder()
  return new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(text))
      controller.close()
    },
  })
}

function sse(...payloads: object[]): string {
  return payloads.map((p) => `data: ${JSON.stringify(p)}\n\n`).join('')
}

async function collect(text: string) {
  const events = []
  for await (const ev of iterSseStream(makeStream(text))) {
    events.push(ev)
  }
  return events
}

describe('iterSseStream', () => {
  it('parses chunk events', async () => {
    const events = await collect(sse({ type: 'chunk', content: 'Hello' }))
    expect(events).toHaveLength(1)
    expect(events[0]).toMatchObject({ type: 'chunk', content: 'Hello' })
  })

  it('parses start events and maps snake_case fields', async () => {
    const events = await collect(
      sse({ type: 'start', agent: 'my-agent', start_time: 1234.5 }),
    )
    expect(events[0]).toMatchObject({ type: 'start', agent: 'my-agent', startTime: 1234.5 })
  })

  it('parses status events', async () => {
    const events = await collect(sse({ type: 'status', content: 'Thinking...' }))
    expect(events[0]).toMatchObject({ type: 'status', content: 'Thinking...' })
  })

  it('parses tool_status events with snake_case mapping', async () => {
    const events = await collect(
      sse({
        type: 'tool_status',
        tool_name: 'search',
        status: 'done',
        description: 'Searched the web',
        duration_ms: 120,
      }),
    )
    expect(events[0]).toMatchObject({
      type: 'tool_status',
      toolName: 'search',
      status: 'done',
      durationMs: 120,
    })
  })

  it('parses llm_call events', async () => {
    const events = await collect(
      sse({ type: 'llm_call', status: 'completed', model: 'gpt-4o', input_tokens: 50 }),
    )
    expect(events[0]).toMatchObject({
      type: 'llm_call',
      status: 'completed',
      model: 'gpt-4o',
      inputTokens: 50,
    })
  })

  it('parses first_token events', async () => {
    const events = await collect(sse({ type: 'first_token', time_to_first_token: 0.42 }))
    expect(events[0]).toMatchObject({ type: 'first_token', timeToFirstToken: 0.42 })
  })

  it('parses done events', async () => {
    const events = await collect(
      sse({ type: 'done', metadata: { generated_by_ai: true }, sources: [] }),
    )
    expect(events[0]).toMatchObject({
      type: 'done',
      metadata: { generated_by_ai: true },
      sources: [],
    })
  })

  it('parses compaction events', async () => {
    const events = await collect(
      sse({ type: 'compaction', pruned_count: 5, tokens_saved: 300 }),
    )
    expect(events[0]).toMatchObject({ type: 'compaction', prunedCount: 5, tokensSaved: 300 })
  })

  it('parses satisfaction_prompt events', async () => {
    const events = await collect(
      sse({ type: 'satisfaction_prompt', conversation_id: 'abc-123' }),
    )
    expect(events[0]).toMatchObject({ type: 'satisfaction_prompt', conversationId: 'abc-123' })
  })

  it('throws StreamError for error events', async () => {
    await expect(
      collect(sse({ type: 'error', error: 'Policy violation', error_type: 'policy' })),
    ).rejects.toBeInstanceOf(StreamError)
  })

  it('includes error_type on StreamError', async () => {
    let caught: StreamError | undefined
    try {
      await collect(sse({ type: 'error', error: 'Bad', error_type: 'tool_error' }))
    } catch (e) {
      caught = e as StreamError
    }
    expect(caught?.errorType).toBe('tool_error')
  })

  it('silently ignores unknown event types', async () => {
    const events = await collect(sse({ type: 'future_type', data: 'x' }))
    expect(events).toHaveLength(0)
  })

  it('skips non-data SSE lines', async () => {
    const raw = `event: message\n\ndata: ${JSON.stringify({ type: 'chunk', content: 'Hi' })}\n\n`
    const events = await collect(raw)
    expect(events).toHaveLength(1)
    expect((events[0] as ChunkEvent).content).toBe('Hi')
  })

  it('skips malformed JSON', async () => {
    const raw = 'data: not json\n\ndata: ' + JSON.stringify({ type: 'chunk', content: 'ok' }) + '\n\n'
    const events = await collect(raw)
    expect(events).toHaveLength(1)
  })

  it('skips [DONE] sentinel', async () => {
    const events = await collect('data: [DONE]\n\n')
    expect(events).toHaveLength(0)
  })

  it('yields multiple events in order', async () => {
    const events = await collect(
      sse(
        { type: 'chunk', content: 'Hello' },
        { type: 'chunk', content: ' world' },
        { type: 'done', metadata: {}, sources: [] },
      ),
    )
    expect(events).toHaveLength(3)
    expect((events[0] as ChunkEvent).content).toBe('Hello')
    expect((events[1] as ChunkEvent).content).toBe(' world')
    expect((events[2] as DoneEvent).type).toBe('done')
  })
})
