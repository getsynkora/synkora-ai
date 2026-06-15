'use client'

import { useState, useRef, useEffect } from 'react'
import { Send, Loader2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { secureStorage } from '@/lib/auth/secure-storage'
import { apiClient } from '@/lib/api/http'
import { getPlatformAgentStatus } from '@/lib/api/platformEngineerApi'
import { MessageRenderer } from '../MessageRenderer'
import { QuickActions } from '../QuickActions'
import { parseActionMarkers } from '../types'
import type { ParsedMessage } from '../types'
import type { AgentCreateConfig } from '../cards/ActionConfirmCard'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001'

interface Props {
  agentName?: string
}

export function ChatScreen({ agentName = 'platform_engineer_agent' }: Props) {
  const [messages, setMessages] = useState<ParsedMessage[]>([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [conversationId] = useState<string | null>(null)
  const [peProvider, setPeProvider] = useState<string>('')
  const [peModelName, setPeModelName] = useState<string>('')
  const scrollRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    getPlatformAgentStatus().then((s) => {
      if (s.provider) setPeProvider(s.provider)
      if (s.model_name) setPeModelName(s.model_name)
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  const sendMessage = async (content: string) => {
    if (!content.trim() || isStreaming) return

    // Dismiss any pending action cards from a previous response
    setMessages((prev) =>
      prev.map((m) => ({
        ...m,
        actionCards: m.actionCards?.map((c) =>
          c.status === 'pending' ? { ...c, status: 'cancelled' as const } : c
        ),
      }))
    )

    const userMsg: ParsedMessage = {
      role: 'user',
      content,
      timestamp: new Date(),
    }
    setMessages((prev) => [...prev, userMsg])
    setInput('')

    const assistantPlaceholder: ParsedMessage = {
      role: 'assistant',
      content: '',
      timestamp: new Date(),
    }
    setMessages((prev) => [...prev, assistantPlaceholder])
    setIsStreaming(true)

    try {
      const token = secureStorage.getAccessToken()
      const response = await fetch(`${API_URL}/api/v1/agents/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token && { Authorization: `Bearer ${token}` }),
        },
        body: JSON.stringify({
          agent_slug: agentName,
          message: content,
          conversation_id: conversationId,
          conversation_history: messages.slice(-10).map((m) => ({
            role: m.role,
            content: m.content,
          })),
        }),
      })

      if (!response.ok || !response.body) {
        throw new Error(`HTTP ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let fullResponse = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.trim() || !line.startsWith('data: ')) continue
          const jsonStr = line.slice(6).trim()
          if (jsonStr === '[DONE]') continue

          let data: Record<string, unknown>
          try {
            data = JSON.parse(jsonStr)
          } catch {
            continue // skip malformed JSON
          }

          if (data.type === 'error') {
            throw new Error((data.error as string) || 'Something went wrong')
          }

          if (data.type === 'chunk') {
            fullResponse += data.content
            const { displayText, actionCards, integrationCard } = parseActionMarkers(fullResponse)
            const enrichedCards = actionCards.map((ac) => ({
              ...ac,
              config: { ...ac.config, llm_provider: peProvider, llm_model: peModelName },
            }))
            setMessages((prev) => {
              const next = [...prev]
              const last = next[next.length - 1]
              if (last.role === 'assistant') {
                const merged = enrichedCards.map((ac, i) => ({
                  ...ac,
                  status: last.actionCards?.[i]?.status ?? ('pending' as const),
                  createdAgentName: last.actionCards?.[i]?.createdAgentName,
                  createdAgentSlug: last.actionCards?.[i]?.createdAgentSlug,
                }))
                next[next.length - 1] = {
                  ...last,
                  content: displayText,
                  actionCards: merged.length > 0 ? merged : last.actionCards,
                  integrationCard: integrationCard ?? last.integrationCard,
                }
              }
              return next
            })
          }
        }
      }

      // Final parse after stream ends
      const { displayText, actionCards, integrationCard } = parseActionMarkers(fullResponse)
      const enrichedFinalCards = actionCards.map((ac) => ({
        ...ac,
        config: { ...ac.config, llm_provider: peProvider, llm_model: peModelName },
      }))
      setMessages((prev) => {
        const next = [...prev]
        const last = next[next.length - 1]
        if (last.role === 'assistant') {
          // If stream ended with no content (abrupt close before any chunks), show fallback error
          if (!displayText && !last.content && actionCards.length === 0 && !integrationCard) {
            next[next.length - 1] = {
              ...last,
              content: '⚠ An error occurred while processing your request. Please try again.',
            }
            return next
          }
          const merged = enrichedFinalCards.map((ac, i) => ({
            ...ac,
            status: last.actionCards?.[i]?.status ?? ('pending' as const),
            createdAgentName: last.actionCards?.[i]?.createdAgentName,
            createdAgentSlug: last.actionCards?.[i]?.createdAgentSlug,
          }))
          next[next.length - 1] = {
            ...last,
            content: displayText,
            actionCards: merged.length > 0 ? merged : last.actionCards,
            integrationCard: integrationCard ?? last.integrationCard,
          }
        }
        return next
      })

    } catch (err: any) {
      const errMsg = err?.message || 'Failed to get response'
      setMessages((prev) => {
        const next = [...prev]
        const last = next[next.length - 1]
        if (last?.role === 'assistant') {
          const existing = last.content ? `${last.content}\n\n` : ''
          next[next.length - 1] = { ...last, content: `${existing}⚠ ${errMsg}` }
        } else {
          next.push({ role: 'assistant', content: `⚠ ${errMsg}`, timestamp: new Date() })
        }
        return next
      })
      toast.error(errMsg)
    } finally {
      setIsStreaming(false)
    }
  }

  // Send __CONFIRMED__ back to the PE agent so it calls platform_create_agent and
  // platform_attach_knowledge_base as real tool calls. We stream the response into a
  // new assistant message (showing tool progress) and watch for __AGENT_CREATED__ to
  // flip the action card to 'created'.
  const streamConfirmed = async () => {
    setIsStreaming(true)

    // Add an assistant placeholder so tool-status text streams in visibly
    setMessages((prev) => [
      ...prev,
      { role: 'assistant', content: '', timestamp: new Date() },
    ])

    try {
      const token = secureStorage.getAccessToken()
      const response = await fetch(`${API_URL}/api/v1/agents/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token && { Authorization: `Bearer ${token}` }),
        },
        body: JSON.stringify({
          agent_slug: agentName,
          message: '__CONFIRMED__',
          conversation_id: conversationId,
          conversation_history: messages.slice(-10).map((m) => {
            // Reconstruct __ACTION__ markers so the LLM can read back agent configs
            if (m.actionCards?.length && m.role === 'assistant') {
              const markers = m.actionCards
                .map((c) => `__ACTION__${JSON.stringify({ type: 'create_agent', config: c.config })}__ACTION__`)
                .join('\n')
              return { role: m.role, content: m.content ? `${m.content}\n${markers}` : markers }
            }
            return { role: m.role, content: m.content }
          }),
        }),
      })

      if (!response.ok || !response.body) {
        throw new Error(`HTTP ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let fullResponse = ''
      let agentWasCreated = false

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.trim() || !line.startsWith('data: ')) continue
          const jsonStr = line.slice(6).trim()
          if (jsonStr === '[DONE]') continue

          let data: Record<string, unknown>
          try {
            data = JSON.parse(jsonStr)
          } catch {
            continue
          }

          if (data.type === 'error') {
            throw new Error((data.error as string) || 'Something went wrong')
          }

          if (data.type === 'chunk') {
            fullResponse += data.content
            const { displayText, agentCreated } = parseActionMarkers(fullResponse)

            if (agentCreated && !agentWasCreated) {
              agentWasCreated = true
              setMessages((prev) =>
                prev.map((m) => ({
                  ...m,
                  actionCards: m.actionCards?.map((c) =>
                    c.status === 'creating'
                      ? { ...c, status: 'created' as const, createdAgentName: agentCreated.name, createdAgentSlug: agentCreated.slug }
                      : c
                  ),
                }))
              )
            }

            setMessages((prev) => {
              const next = [...prev]
              const last = next[next.length - 1]
              if (last.role === 'assistant') {
                next[next.length - 1] = { ...last, content: displayText }
              }
              return next
            })
          }
        }
      }

      // Final parse
      const { displayText, agentCreated } = parseActionMarkers(fullResponse)
      if (agentCreated && !agentWasCreated) {
        agentWasCreated = true
        setMessages((prev) =>
          prev.map((m) => ({
            ...m,
            actionCards: m.actionCards?.map((c) =>
              c.status === 'creating'
                ? { ...c, status: 'created' as const, createdAgentName: agentCreated.name, createdAgentSlug: agentCreated.slug }
                : c
            ),
          }))
        )
      }
      setMessages((prev) => {
        const next = [...prev]
        const last = next[next.length - 1]
        if (last.role === 'assistant') {
          next[next.length - 1] = { ...last, content: displayText }
        }
        return next
      })

      // LLM didn't output __AGENT_CREATED__ — reset so user can retry
      if (!agentWasCreated) {
        setMessages((prev) =>
          prev.map((m) => ({
            ...m,
            actionCards: m.actionCards?.map((c) =>
              c.status === 'creating' ? { ...c, status: 'pending' as const } : c
            ),
          }))
        )
      }
    } catch (err: any) {
      const errMsg = err?.message || 'Agent creation failed'
      setMessages((prev) =>
        prev.map((m) => ({
          ...m,
          actionCards: m.actionCards?.map((c) =>
            c.status === 'creating' ? { ...c, status: 'pending' as const } : c
          ),
        }))
      )
      setMessages((prev) => {
        const next = [...prev]
        const last = next[next.length - 1]
        if (last?.role === 'assistant') {
          next[next.length - 1] = { ...last, content: `⚠ ${errMsg}` }
        }
        return next
      })
      toast.error(errMsg)
    } finally {
      setIsStreaming(false)
    }
  }

  const handleConfirm = (_config: AgentCreateConfig) => {
    setMessages((prev) =>
      prev.map((m) => ({
        ...m,
        actionCards: m.actionCards?.map((c) =>
          c.status === 'pending' ? { ...c, status: 'creating' as const } : c
        ),
      }))
    )
    streamConfirmed()
  }

  const handleCancelAction = () => {
    setMessages((prev) =>
      prev.map((m) => ({
        ...m,
        actionCards: m.actionCards?.map((c) =>
          c.status === 'pending' ? { ...c, status: 'cancelled' as const } : c
        ),
      }))
    )
  }

  const isEmpty = messages.length === 0

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4" ref={scrollRef}>
        {isEmpty ? (
          <div className="flex flex-col items-center justify-center h-full text-center space-y-3 py-8">
            <p className="text-sm text-gray-500 max-w-xs">
              I can actually create and manage agents for you. Try a quick action or describe what you need.
            </p>
          </div>
        ) : (
          messages.map((msg, i) => (
            <MessageRenderer
              key={i}
              message={msg}
              onConfirm={handleConfirm}
              onCancelAction={handleCancelAction}
            />
          ))
        )}
        {isStreaming && messages[messages.length - 1]?.role === 'assistant' && !messages[messages.length - 1]?.content && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-xl px-3 py-2.5">
              <div className="flex gap-1">
                {[0, 0.15, 0.3].map((delay, i) => (
                  <div
                    key={i}
                    className="w-2 h-2 rounded-full bg-gray-400 animate-bounce"
                    style={{ animationDelay: `${delay}s` }}
                  />
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Quick actions — only show when no messages */}
      {isEmpty && <QuickActions onSelect={sendMessage} disabled={isStreaming} />}

      {/* Input */}
      <div className="px-4 pb-4 flex-shrink-0">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            sendMessage(input)
          }}
          className="flex gap-2"
        >
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Describe what you need..."
            rows={1}
            className="flex-1 px-3 py-2 border border-gray-300 rounded-xl text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none min-h-[40px] max-h-[120px] overflow-y-auto"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                sendMessage(input)
              }
            }}
          />
          <button
            type="submit"
            disabled={!input.trim() || isStreaming}
            className="h-10 w-10 flex items-center justify-center bg-primary-500 text-white rounded-xl hover:bg-primary-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0"
          >
            {isStreaming ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </button>
        </form>
      </div>
    </div>
  )
}
