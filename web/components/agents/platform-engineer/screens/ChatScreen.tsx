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
            const { displayText, actionCard, integrationCard } = parseActionMarkers(fullResponse)
            const enrichedCard = actionCard
              ? { ...actionCard, config: { ...actionCard.config, llm_provider: peProvider, llm_model: peModelName } }
              : undefined
            setMessages((prev) => {
              const next = [...prev]
              const last = next[next.length - 1]
              if (last.role === 'assistant') {
                next[next.length - 1] = {
                  ...last,
                  content: displayText,
                  actionCard: enrichedCard ?? last.actionCard,
                  integrationCard: integrationCard ?? last.integrationCard,
                }
              }
              return next
            })
          }
        }
      }

      // Final parse after stream ends
      const { displayText, actionCard, integrationCard } = parseActionMarkers(fullResponse)
      const enrichedFinalCard = actionCard
        ? { ...actionCard, config: { ...actionCard.config, llm_provider: peProvider, llm_model: peModelName } }
        : undefined
      setMessages((prev) => {
        const next = [...prev]
        const last = next[next.length - 1]
        if (last.role === 'assistant') {
          next[next.length - 1] = {
            ...last,
            content: displayText,
            actionCard: enrichedFinalCard ?? last.actionCard,
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
        if (last.role === 'assistant') {
          const existing = last.content ? `${last.content}\n\n` : ''
          next[next.length - 1] = { ...last, content: `${existing}⚠ ${errMsg}` }
        }
        return next
      })
      toast.error(errMsg)
    } finally {
      setIsStreaming(false)
    }
  }

  const handleConfirm = async (config: AgentCreateConfig) => {
    // Optimistic: set card to creating
    setMessages((prev) =>
      prev.map((m) =>
        m.actionCard?.status === 'pending'
          ? { ...m, actionCard: { ...m.actionCard!, status: 'creating' } }
          : m
      )
    )

    try {
      const response = await apiClient.axios.post('/api/v1/agents', {
        config: {
          name: config.name,
          description: config.description,
          system_prompt: config.system_prompt,
          agent_type: 'llm_agent',
          llm_config: {
            provider: '',
            model_name: '',
            temperature: 0.7,
            max_tokens: 4096,
            api_key: '',
          },
          tools: (config.tools_list || []).map((t) => ({ name: t, enabled: true, config: {} })),
          metadata: {},
        },
        agent_type: 'llm',
        is_public: false,
        category: config.category,
        tags: config.tags,
      })

      const createdName = response.data?.agent_name || config.name

      setMessages((prev) =>
        prev.map((m) =>
          m.actionCard?.status === 'creating'
            ? {
                ...m,
                actionCard: {
                  ...m.actionCard!,
                  status: 'created',
                  createdAgentName: createdName,
                },
              }
            : m
        )
      )

      // Append follow-up message
      const followUp: ParsedMessage = {
        role: 'assistant',
        content: `Agent "${createdName}" is ready! You can view it or start chatting right away.`,
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, followUp])
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'Agent creation failed'
      setMessages((prev) =>
        prev.map((m) =>
          m.actionCard?.status === 'creating'
            ? { ...m, actionCard: { ...m.actionCard!, status: 'pending' } }
            : m
        )
      )
      toast.error(detail)
    }
  }

  const handleCancelAction = () => {
    setMessages((prev) =>
      prev.map((m) =>
        m.actionCard?.status === 'pending'
          ? { ...m, actionCard: { ...m.actionCard!, status: 'cancelled' } }
          : m
      )
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
