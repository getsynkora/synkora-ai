'use client'

import { useCallback, useEffect, useRef } from 'react'
import { secureStorage } from '@/lib/auth/secure-storage'

// ── Event types ───────────────────────────────────────────────────────────────

export type ChatEvent =
  | { type: 'start'; agent?: string; start_time?: number }
  | { type: 'first_token'; time_to_first_token?: number }
  | { type: 'chunk'; content: string }
  | { type: 'status'; content?: string }
  | {
      type: 'tool_status'
      tool_name: string
      status: 'started' | 'completed' | 'error'
      description?: string
      details?: Record<string, unknown>
      duration_ms?: number
      input_tokens?: number
      output_tokens?: number
    }
  | { type: 'chart'; chart?: unknown; [key: string]: unknown }
  | { type: 'diagram'; diagram?: unknown; [key: string]: unknown }
  | { type: 'infographic'; infographic?: unknown; [key: string]: unknown }
  | { type: 'vehicle_map'; map?: unknown; [key: string]: unknown }
  | { type: 'fleet_card'; card?: unknown; [key: string]: unknown }
  | { type: 'generated_image'; generated_image?: unknown; [key: string]: unknown }
  | { type: 'form'; form?: unknown; [key: string]: unknown }
  | {
      type: 'done'
      sources?: unknown[]
      metadata?: {
        input_tokens?: number
        output_tokens?: number
        total_tokens?: number
        total_time?: number
        time_to_first_token?: number
      }
    }
  | { type: 'error'; error: string; error_code?: string; error_type?: string }

export interface ChatPayload {
  agent_slug: string
  message: string
  conversation_id?: string
  conversation_history?: Array<{ role: string; content: string }>
  attachments?: unknown[]
  llm_config_id?: string
}

// ── Internal WS callback type ─────────────────────────────────────────────────

interface WsCallback {
  onEvent: (data: ChatEvent) => void
  onDone: () => void
  onError: (err: Error) => void
}

// ── SSE stream generator ──────────────────────────────────────────────────────

async function* makeSseStream(
  apiUrl: string,
  payload: ChatPayload,
  signal?: AbortSignal,
): AsyncGenerator<ChatEvent> {
  const token = secureStorage.getAccessToken()

  const response = await fetch(`${apiUrl}/api/v1/agents/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(payload),
    signal,
  })

  if (!response.ok) {
    if (response.status === 402) {
      let msg = 'Insufficient credits or subscription issue.'
      try {
        const errorData = await response.json()
        msg = errorData?.detail?.message || errorData?.message || msg
      } catch {
        // JSON parse failed — keep default message
      }
      throw new Error(msg)
    }
    throw new Error(`HTTP error! status: ${response.status}`)
  }

  if (!response.body) throw new Error('No response body')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        if (!line.trim() || !line.startsWith('data: ')) continue
        const jsonStr = line.slice(6).trim()
        if (jsonStr === '[DONE]') return

        let data: ChatEvent
        try {
          data = JSON.parse(jsonStr) as ChatEvent
        } catch {
          continue
        }

        yield data
        if (data.type === 'error') return
      }
    }
  } finally {
    reader.cancel().catch(() => {})
  }
}

// ── WebSocket async-iterable stream ──────────────────────────────────────────
//
// Bridges the callback-based WebSocket.onmessage into an AsyncIterable<ChatEvent>
// using a queue + resolver pattern:
//   - onmessage pushes items into `queue` and resolves any waiting `next()` call
//   - `next()` drains `queue` or suspends until the next push
//   - `return()` cleans up the callback ref to stop future events being routed here

function makeWsStream(
  ws: WebSocket,
  callbackRef: React.MutableRefObject<WsCallback | null>,
  payload: ChatPayload,
): AsyncIterable<ChatEvent> {
  return {
    [Symbol.asyncIterator]() {
      type QueueItem =
        | { kind: 'event'; value: ChatEvent }
        | { kind: 'done' }
        | { kind: 'error'; error: Error }

      const queue: QueueItem[] = []
      let resolver: (() => void) | null = null
      let settled = false

      const notify = () => {
        if (resolver) {
          const r = resolver
          resolver = null
          r()
        }
      }

      callbackRef.current = {
        onEvent(data) {
          queue.push({ kind: 'event', value: data })
          notify()
        },
        onDone() {
          settled = true
          queue.push({ kind: 'done' })
          notify()
        },
        onError(err) {
          settled = true
          queue.push({ kind: 'error', error: err })
          notify()
        },
      }

      // Send the chat frame once the callback is registered
      ws.send(JSON.stringify({ type: 'chat', ...payload }))

      return {
        async next(): Promise<IteratorResult<ChatEvent>> {
          while (true) {
            const item = queue.shift()
            if (item) {
              if (item.kind === 'error') throw item.error
              if (item.kind === 'done') return { done: true, value: undefined }
              return { done: false, value: item.value }
            }
            if (settled) return { done: true, value: undefined }
            await new Promise<void>((res) => {
              resolver = res
            })
          }
        },

        return(): Promise<IteratorResult<ChatEvent>> {
          callbackRef.current = null
          return Promise.resolve({ done: true, value: undefined })
        },
      }
    },
  }
}

// ── Public hook ───────────────────────────────────────────────────────────────

export function useChatTransport(
  chatTransport: 'sse' | 'websocket' = 'sse',
  apiUrl: string,
): { sendMessage: (payload: ChatPayload) => AsyncIterable<ChatEvent>; stopStreaming: () => void } {
  const wsRef = useRef<WebSocket | null>(null)
  const wsAuthReadyRef = useRef(false)
  const wsCallbackRef = useRef<WsCallback | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  // Manage the persistent WebSocket connection lifecycle.
  // Only active when chatTransport === 'websocket'.
  // Auth uses a first-message frame so the token never appears in the URL.
  useEffect(() => {
    if (chatTransport !== 'websocket') return

    let unmounted = false
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null

    const connect = () => {
      if (unmounted) return

      const wsBase = apiUrl.replace(/^https/, 'wss').replace(/^http/, 'ws')
      const ws = new WebSocket(`${wsBase}/api/v1/agents/chat/ws`)
      wsRef.current = ws
      wsAuthReadyRef.current = false

      ws.onopen = () => {
        const token = secureStorage.getAccessToken()
        if (!token) {
          ws.close()
          return
        }
        ws.send(JSON.stringify({ type: 'auth', token }))
      }

      ws.onmessage = (event: MessageEvent) => {
        let data: Record<string, unknown>
        try {
          data = JSON.parse(event.data as string) as Record<string, unknown>
        } catch {
          return
        }

        if (data.type === 'auth_ok') {
          wsAuthReadyRef.current = true
          return
        }
        if (data.type === 'auth_error') {
          ws.close()
          return
        }

        const cb = wsCallbackRef.current
        if (!cb) return

        const chatEvent = data as unknown as ChatEvent
        if (data.type === 'done') {
          cb.onEvent(chatEvent)
          cb.onDone()
          wsCallbackRef.current = null
        } else if (data.type === 'error') {
          cb.onEvent(chatEvent)
          cb.onDone()
          wsCallbackRef.current = null
        } else {
          cb.onEvent(chatEvent)
        }
      }

      ws.onclose = () => {
        wsAuthReadyRef.current = false
        if (!unmounted) {
          reconnectTimer = setTimeout(connect, 3000)
        }
      }

      // onerror always fires before onclose — reconnect logic lives in onclose
      ws.onerror = () => {}
    }

    connect()

    return () => {
      unmounted = true
      if (reconnectTimer) clearTimeout(reconnectTimer)
      if (wsRef.current) {
        wsRef.current.onclose = null
        wsRef.current.close()
        wsRef.current = null
      }
      wsAuthReadyRef.current = false
    }
  }, [chatTransport, apiUrl])

  const stopStreaming = useCallback(() => {
    abortControllerRef.current?.abort()
    abortControllerRef.current = null
    // For WebSocket: stop routing events to the current request
    wsCallbackRef.current = null
  }, [])

  const sendMessage = useCallback(
    (payload: ChatPayload): AsyncIterable<ChatEvent> => {
      if (chatTransport === 'websocket') {
        const ws = wsRef.current
        if (!ws || ws.readyState !== WebSocket.OPEN || !wsAuthReadyRef.current) {
          // WebSocket not ready — return an iterable that rejects immediately so
          // the caller's catch block handles it gracefully
          return {
            [Symbol.asyncIterator]() {
              return {
                next: () =>
                  Promise.reject(
                    new Error('WebSocket is not connected. Please wait and try again.'),
                  ),
                return: () => Promise.resolve({ done: true, value: undefined }),
              }
            },
          }
        }
        return makeWsStream(ws, wsCallbackRef, payload)
      }

      // SSE: create a fresh AbortController for this request
      const controller = new AbortController()
      abortControllerRef.current = controller
      return {
        [Symbol.asyncIterator]: () =>
          makeSseStream(apiUrl, payload, controller.signal)[Symbol.asyncIterator](),
      }
    },
    [chatTransport, apiUrl],
  )

  return { sendMessage, stopStreaming }
}
