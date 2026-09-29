import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { SynkoraClient } from '../src/client.js'
import { AgentNotFoundError, AuthError, RateLimitError, StreamError } from '../src/exceptions.js'
import type { ChunkEvent } from '../src/models.js'

// ---------------------------------------------------------------------------
// Fetch mock helpers
// ---------------------------------------------------------------------------

function sseBody(...events: object[]): ReadableStream<Uint8Array> {
  const text = events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join('')
  const encoder = new TextEncoder()
  return new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(text))
      controller.close()
    },
  })
}

function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function sseResponse(...events: object[]): Response {
  return new Response(sseBody(...events), {
    status: 200,
    headers: { 'Content-Type': 'text/event-stream' },
  })
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('SynkoraClient', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  describe('constructor', () => {
    it('throws AuthError when no API key provided', () => {
      expect(() => new SynkoraClient()).toThrow(AuthError)
    })

    it('accepts apiKey option', () => {
      expect(() => new SynkoraClient({ apiKey: 'sk-test' })).not.toThrow()
    })

    it('reads SYNKORA_API_KEY from process.env', () => {
      process.env['SYNKORA_API_KEY'] = 'sk-env'
      expect(() => new SynkoraClient()).not.toThrow()
      delete process.env['SYNKORA_API_KEY']
    })
  })

  describe('listAgents', () => {
    it('returns agent list', async () => {
      fetchMock.mockResolvedValue(
        jsonResponse([{ id: 'a1', name: 'Agent One', capabilities: [] }]),
      )
      const client = new SynkoraClient({ apiKey: 'sk-test' })
      const agents = await client.listAgents()
      expect(agents).toHaveLength(1)
      expect(agents[0]!.name).toBe('Agent One')
    })

    it('throws AuthError on 401', async () => {
      fetchMock.mockResolvedValue(jsonResponse({ detail: 'Unauthorized' }, 401))
      const client = new SynkoraClient({ apiKey: 'sk-test' })
      await expect(client.listAgents()).rejects.toBeInstanceOf(AuthError)
    })

    it('throws RateLimitError on 429', async () => {
      fetchMock.mockResolvedValue(jsonResponse({ detail: 'Too many requests' }, 429))
      const client = new SynkoraClient({ apiKey: 'sk-test' })
      await expect(client.listAgents()).rejects.toBeInstanceOf(RateLimitError)
    })
  })

  describe('getAgent', () => {
    it('returns agent info', async () => {
      fetchMock.mockResolvedValue(
        jsonResponse({ id: 'uuid-1', name: 'My Agent', model: 'gpt-4o', capabilities: [] }),
      )
      const client = new SynkoraClient({ apiKey: 'sk-test' })
      const agent = await client.getAgent('uuid-1')
      expect(agent.id).toBe('uuid-1')
      expect(agent.model).toBe('gpt-4o')
    })

    it('throws AgentNotFoundError on 404', async () => {
      fetchMock.mockResolvedValue(jsonResponse({ detail: 'Not found' }, 404))
      const client = new SynkoraClient({ apiKey: 'sk-test' })
      await expect(client.getAgent('missing')).rejects.toBeInstanceOf(AgentNotFoundError)
    })
  })

  describe('chatStream', () => {
    it('yields typed events from SSE', async () => {
      fetchMock.mockResolvedValue(
        sseResponse(
          { type: 'chunk', content: 'Hello' },
          { type: 'chunk', content: ' world' },
          { type: 'done', metadata: {}, sources: [] },
        ),
      )
      const client = new SynkoraClient({ apiKey: 'sk-test' })
      const events = []
      for await (const ev of client.chatStream('agent-1', 'Hi')) {
        events.push(ev)
      }
      expect(events).toHaveLength(3)
      expect((events[0] as ChunkEvent).content).toBe('Hello')
    })

    it('throws StreamError when error event received', async () => {
      fetchMock.mockResolvedValue(
        sseResponse({ type: 'error', error: 'Policy violation', error_type: 'policy' }),
      )
      const client = new SynkoraClient({ apiKey: 'sk-test' })
      const gen = client.chatStream('agent-1', 'Bad input')
      await expect(gen.next()).rejects.toBeInstanceOf(StreamError)
    })

    it('sends conversation_id in request body', async () => {
      fetchMock.mockResolvedValue(
        sseResponse({ type: 'done', metadata: {}, sources: [] }),
      )
      const client = new SynkoraClient({ apiKey: 'sk-test' })
      const gen = client.chatStream('agent-1', 'Hello', { conversationId: 'conv-99' })
      for await (const _ of gen) { /* drain */ }
      const body = JSON.parse(fetchMock.mock.calls[0][1].body as string)
      expect(body.conversation_id).toBe('conv-99')
    })

    it('sends Authorization header with Bearer token', async () => {
      fetchMock.mockResolvedValue(
        sseResponse({ type: 'done', metadata: {}, sources: [] }),
      )
      const client = new SynkoraClient({ apiKey: 'sk-my-key' })
      for await (const _ of client.chatStream('agent-1', 'Hi')) { /* drain */ }
      const headers = fetchMock.mock.calls[0][1].headers as Record<string, string>
      expect(headers['Authorization']).toBe('Bearer sk-my-key')
    })
  })

  describe('chat', () => {
    it('aggregates chunk events into a single message', async () => {
      fetchMock.mockResolvedValue(
        sseResponse(
          { type: 'chunk', content: 'Hello' },
          { type: 'chunk', content: ' world' },
          { type: 'done', metadata: { total_tokens: 10 }, sources: [] },
        ),
      )
      const client = new SynkoraClient({ apiKey: 'sk-test' })
      const response = await client.chat('agent-1', 'Hi')
      expect(response.message).toBe('Hello world')
      expect(response.tokensUsed).toBe(10)
    })

    it('returns empty string when no chunks', async () => {
      fetchMock.mockResolvedValue(
        sseResponse({ type: 'done', metadata: {}, sources: [] }),
      )
      const client = new SynkoraClient({ apiKey: 'sk-test' })
      const response = await client.chat('agent-1', 'Hi')
      expect(response.message).toBe('')
    })

    it('includes sources from done event', async () => {
      fetchMock.mockResolvedValue(
        sseResponse({
          type: 'done',
          metadata: {},
          sources: [{ title: 'Doc 1', url: 'https://example.com' }],
        }),
      )
      const client = new SynkoraClient({ apiKey: 'sk-test' })
      const response = await client.chat('agent-1', 'Hi')
      expect(response.sources).toHaveLength(1)
      expect(response.sources[0]!['title']).toBe('Doc 1')
    })
  })

  describe('deleteConversation', () => {
    it('calls DELETE endpoint', async () => {
      fetchMock.mockResolvedValue(new Response(null, { status: 204 }))
      const client = new SynkoraClient({ apiKey: 'sk-test' })
      await client.deleteConversation('agent-1', 'conv-1')
      expect(fetchMock).toHaveBeenCalledOnce()
      expect(fetchMock.mock.calls[0][1].method).toBe('DELETE')
    })
  })
})
